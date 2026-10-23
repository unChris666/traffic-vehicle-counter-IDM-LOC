"""LI-5 offline Recount; consumes stored LI-4 decisions, never routes or retrieves.

Experimental policy only. Coordinates use explicit CRS; polygon edit is a new revision.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
if __name__ == '__main__':
    sys.dont_write_bytecode = True
from location_intelligent_li3_sources import read_json, write_json, canonical_bytes
from location_intelligent_li3 import verify_manifest
from location_intelligent_li4 import verify as verify_li4, capacity_groups, digest, csv_value

VERSION = 'LI5_OFFLINE_V1'
HERE = Path(__file__).resolve().parent
INPUTS = ['buildings.json', 'summary.json', 'snapshot/building_results/selection.json', 'snapshot/config/pilot.json', 'snapshot/normalized/context.json']


def software_versions():
    import shapely,pyproj
    return {'shapely':shapely.__version__,'geos':shapely.geos_version_string,
            'pyproj':pyproj.__version__,'proj':pyproj.proj_version_str}


def checked_policy(policy):
    expected = read_json(HERE/'fixtures/li5/policy.json')
    if set(policy) != set(expected) or any(policy[k] != expected[k] for k in expected if k not in {'predicate','policy_version'}):
        raise ValueError('Unsupported or implicit Recount policy')
    if policy['predicate'] not in {'covers','contains'} or not isinstance(policy['policy_version'],str) or not policy['policy_version']:
        raise ValueError('Explicit predicate and version required')
    return policy


def validate_polygons(collection):
    from shapely.geometry import shape
    if collection.get('type') != 'FeatureCollection' or collection.get('schema_version') != 'li_recount_polygons_v1':
        raise ValueError('Explicit polygon collection schema required')
    if collection.get('crs') != 'EPSG:4326' or not collection.get('revision_id') or not collection.get('claim_type'):
        raise ValueError('Polygon CRS/revision/claim required')
    ids = set()
    for f in collection['features']:
        pid = f['properties']['polygon_id']
        if not isinstance(pid,str) or not pid or pid in ids:
            raise ValueError('Missing/duplicate polygon ID')
        ids.add(pid)
        g = shape(f['geometry'])
        if g.geom_type not in {'Polygon','MultiPolygon'} or g.is_empty or not g.is_valid:
            raise ValueError('Invalid polygon; no silent repair')
        for ring in rings(g):
            for xy in ring.coords:
                if len(xy)!=2 or not all(math.isfinite(x) for x in xy) or not -180<=xy[0]<=180 or not -90<=xy[1]<=90:
                    raise ValueError('Invalid lon/lat polygon coordinate')
    return collection


def rings(g):
    for p in g.geoms if g.geom_type=='MultiPolygon' else [g]:
        yield p.exterior
        yield from p.interiors


def evaluate(records, polygons, *, center, radius, predicate='covers'):
    """Metric-only membership core. Coverage is analytic disk, not source completeness."""
    from shapely.geometry import Point
    if predicate not in {'covers','contains'} or not math.isfinite(radius) or radius<=0:
        raise ValueError('Invalid predicate/radius')
    indices=[r['source_row_index'] for r in records]
    if len(set(indices))!=len(indices):raise ValueError('Duplicate source row')
    keys=[r['building_key'] for r in records]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate building source key')
    if any(len(r['point_m'])!=2 or not all(math.isfinite(x) for x in r['point_m']) for r in records):raise ValueError('Invalid representative point')
    output,union={},set()
    for pid,g in sorted(polygons.items()):
        if g.geom_type not in {'Polygon','MultiPolygon'} or not g.is_valid or g.is_empty:
            raise ValueError('Invalid polygon')
        inside = [r for r in records if getattr(g,predicate)(Point(r['point_m']))]
        indices=sorted(r['source_row_index'] for r in inside)
        union.update(indices)
        # An entire linear polygon is in a convex disk iff all vertices are in it.
        outside=any(math.hypot(x-center[0],y-center[1])>radius for ring in rings(g) for x,y in ring.coords)
        output[pid]={'source_row_indices':indices,'coverage_status':'PARTIAL_OUTSIDE_ANALYSIS_DOMAIN' if outside else 'WITHIN_FROZEN_ANALYSIS_DOMAIN',
            'decision_counts':dict(sorted(Counter(r['decision_state'] for r in inside).items())),
            'capacity_by_decision_and_unit':capacity_groups(inside),'mixed_unit_total':None}
    return output,sorted(union)


def load_inputs(root):
    rows=read_json(root/'input/buildings.json')
    selection=read_json(root/'input/snapshot/building_results/selection.json')
    summary=read_json(root/'input/summary.json')
    config=read_json(root/'input/snapshot/config/pilot.json')
    indices=[r['source_row_index'] for r in rows]
    if sorted(indices)!=list(range(summary['source_records'])):
        raise ValueError('Source row reconciliation failed')
    selected={b['source_row_index']:b for b in selection['selected']}
    if len(selected)!=len(selection['selected']) or set(selected)!={r['source_row_index'] for r in rows if r['selection_status']=='SELECTED'}:
        raise ValueError('Selected universe mismatch')
    if dict(sorted(Counter(r['decision_state'] for r in rows if r['selection_status']=='SELECTED').items()))!=summary['decision_counts_selected']:
        raise ValueError('Frozen decision reconciliation failed')
    return rows,selected,summary,config


def derive(root):
    from shapely.geometry import shape
    from shapely import transform as _transform
    def transform(fn,g):return _transform(g,fn,interleaved=False)
    from pyproj import Transformer
    root=Path(root)
    policy=checked_policy(read_json(root/'policy.json'))
    fc=validate_polygons(read_json(root/'polygons.geojson'))
    rows,selected,source,config=load_inputs(root)
    crs=config['policy']['li3']['metric_crs']
    tx=Transformer.from_crs(4326,crs,always_xy=True)
    target=config['policy']['li3']
    center=tx.transform(target['longitude'],target['latitude'])
    # Radius comes from the actual LI-1 context retained in the validated parent packet.
    radius=read_json(root/'input/snapshot/normalized/context.json')['config']['area_coverage']['parameters']['building_radius_m']['value']
    if radius!=read_json(root/'input_binding.json')['analysis_radius_m']:raise ValueError('Radius differs from source')
    records=[]
    for r in rows:
        if r['source_row_index'] not in selected:continue
        b=selected[r['source_row_index']]
        if b['building_id']!=r['building_id']:raise ValueError('Building identity mismatch')
        key=b['building_key']
        point=tx.transform(*b['representative_point']['coordinates'])
        records.append({**r,'building_key':json.dumps(key,sort_keys=True,separators=(',',':')),'point_m':point})
    metric={f['properties']['polygon_id']:transform(tx.transform,shape(f['geometry'])) for f in fc['features']}
    groups,union=evaluate(records,metric,center=center,radius=radius,predicate=policy['predicate'])
    membership={pid:set(g['source_row_indices']) for pid,g in groups.items()}
    ledger=[]
    for row in rows:
        i=row['source_row_index'];inside=sorted(pid for pid,ids in membership.items() if i in ids)
        ledger.append({**row,'building_key':selected[i]['building_key'] if i in selected else None,
            'membership_point':selected[i]['representative_point'] if i in selected else None,
            'recount_evaluated':i in selected,'polygon_ids':inside,'in_union':bool(inside),
            'membership_reason':'EVALUATED_STORED_REPRESENTATIVE_POINT' if i in selected else 'OUTSIDE_SELECTED_UNIVERSE_NOT_EVALUATED'})
    union_rows=[r for r in rows if r['source_row_index'] in set(union)]
    input_hash=hashlib.sha256(canonical_bytes(read_json(root/'input_binding.json'))).hexdigest()
    source_partial=source['analysis_status']=='PARTIAL'
    result={'schema_version':'li_recount_result_v1','engine_version':VERSION,'engine_sha256':digest(Path(__file__)),'software':software_versions(),'policy':policy,
        'result_version':hashlib.sha256(canonical_bytes({'inputs':input_hash,'policy':policy,'polygons':fc,'engine':VERSION,'engine_sha256':digest(Path(__file__)),'software':software_versions()})).hexdigest(),
        'input_fingerprint':input_hash,'polygon_sha256':hashlib.sha256(canonical_bytes(fc)).hexdigest(),'polygon_revision':fc['revision_id'],'polygon_claim_type':fc['claim_type'],
        'source_records':len(rows),'evaluated_selected':len(records),'not_evaluated_source_rows':len(rows)-len(records),
        'analysis_status':'PARTIAL' if source_partial or any(g['coverage_status'].startswith('PARTIAL') for g in groups.values()) else source['analysis_status'],
        'source_analysis_status':source['analysis_status'],'polygons':groups,'union_source_row_indices':union,
        'union_count':len(union),'union_decision_counts':dict(sorted(Counter(r['decision_state'] for r in union_rows).items())),
        'union_capacity_by_decision_and_unit':capacity_groups(union_rows),'mixed_unit_total':None,'final_business_capacity':None,
        'physical_access_validated':False,'claim_type':'OFFLINE_EXPERIMENT_NOT_APPROVED_BUSINESS_BOUNDARY',
        'coverage_meaning':'Geometric relation to frozen LI-1 analysis disk; not completeness of real buildings or permissions',
        'no_retrieval_routing_or_capacity_recalculation':True,'source_warnings':source['source_warnings']}
    previous=root/'previous_result.json'
    delta=None
    if previous.exists():
        old=read_json(previous)
        if old['input_fingerprint']!=input_hash or old['policy']!=policy or old['engine_sha256']!=result['engine_sha256'] or old['software']!=result['software']:raise ValueError('Delta requires same source and policy')
        if old['polygon_revision']==fc['revision_id'] and old['polygon_sha256']!=result['polygon_sha256']:raise ValueError('Changed polygon requires new revision ID')
        delta={'previous_result_version':old['result_version'],'current_result_version':result['result_version'],'polygons':{}}
        for pid in sorted(set(old['polygons'])|set(groups)):
            before=set(old['polygons'].get(pid,{}).get('source_row_indices',[]));after=set(groups.get(pid,{}).get('source_row_indices',[]))
            delta['polygons'][pid]={'entered':sorted(after-before),'exited':sorted(before-after)}
        before=set(old['union_source_row_indices']);after=set(union)
        delta['union']={'entered':sorted(after-before),'exited':sorted(before-after)}
    return result,ledger,delta


def render(result,ledger,fc):
    """Small standalone SVG audit, not a drawing UI or production app."""
    import html
    from shapely.geometry import shape
    allgeom=[shape(f['geometry']) for f in fc['features']]
    points=[r['membership_point']['coordinates'] for r in ledger if r.get('membership_point')]
    from shapely.geometry import Point
    allgeom += [Point(p) for p in points]
    if allgeom:
        west=min(g.bounds[0] for g in allgeom);south=min(g.bounds[1] for g in allgeom)
        east=max(g.bounds[2] for g in allgeom);north=max(g.bounds[3] for g in allgeom)
    else:west,south,east,north=0,0,1,1
    dx=max(east-west,1e-9);dy=max(north-south,1e-9)
    def ringpath(g):
        return ' '.join('M'+' L'.join(f'{20+(x-west)/dx*760:.3f},{20+(north-y)/dy*520:.3f}' for x,y in ring.coords)+' Z' for ring in rings(g))
    polygons=''.join('<path d="'+ringpath(shape(f['geometry']))+'" fill="#539bdf" fill-opacity=".15" stroke="#2686cc" fill-rule="evenodd"/><text x="20" y="'+str(30+i*20)+'">'+html.escape(f['properties']['polygon_id'])+'</text>' for i,f in enumerate(fc['features']))
    dots=''.join('<circle cx="'+str(20+(r['membership_point']['coordinates'][0]-west)/dx*760)+'" cy="'+str(20+(north-r['membership_point']['coordinates'][1])/dy*520)+'" r="2" fill="'+({'ACCEPTED':'#158057','ACCESS_UNVERIFIED':'#9c4bd0'}.get(r['decision_state'],'#b67e12'))+'"><title>'+html.escape(str(r['source_row_index'])+' '+r['building_id']+' '+r['decision_state']+' '+','.join(r['polygon_ids']))+'</title></circle>' for r in ledger if r.get('membership_point'))
    totals='<p>Source rows: '+str(result['source_records'])+'; evaluated selected: '+str(result['evaluated_selected'])+'; union unique: '+str(result['union_count'])+'; analysis: '+result['analysis_status']+'</p>'
    groups='<table><tr><th>Polygon</th><th>Members</th><th>Decision counts</th><th>Coverage</th></tr>'+''.join('<tr><td>'+html.escape(pid)+'</td><td>'+str(len(g['source_row_indices']))+'</td><td>'+html.escape(json.dumps(g['decision_counts']))+'</td><td>'+g['coverage_status']+'</td></tr>' for pid,g in result['polygons'].items())+'</table>'
    summary=html.escape(json.dumps(result,ensure_ascii=False,indent=2))
    table=''.join('<tr><td>'+str(r['source_row_index'])+'</td><td>'+html.escape(r['building_id'])+'</td><td>'+html.escape(r['decision_state'])+'</td><td>'+html.escape(', '.join(r['polygon_ids']))+'</td></tr>' for r in ledger)
    return ('<!doctype html><html lang="id"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>LI-5 N1 Recount</title><style>body{font:14px system-ui;margin:24px;color:#183049}pre{white-space:pre-wrap;max-height:500px;overflow:auto}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:6px}.scroll{max-height:500px;overflow:auto}svg{max-width:100%;height:auto}</style><h1>LI-5 · Recount offline</h1><p>SKENARIO EKSPERIMEN. Polygon otomatis untuk demonstrasi; bukan batas bisnis. Akses unknown tetap unknown. Kapasitas tidak dicampur.</p><svg viewBox="0 0 800 560">'+polygons+dots+'</svg>'+totals+groups+'<p>Titik hijau: accepted skenario; ungu: akses unverified; kuning: status lain. Hover untuk source ID. Polygon biru adalah demo otomatis.</p><h2>Ringkasan dan membership per polygon</h2><pre>'+summary+'</pre><h2>Seluruh baris sumber</h2><div class="scroll"><table><tr><th>Baris</th><th>Bangunan</th><th>Status sumber</th><th>Polygon</th></tr>'+table+'</table></div><p>membership.csv · membership.json · polygons.geojson · result.json · delta.json</p></html>').encode()


def output_bytes(root):
    result,ledger,delta=derive(root)
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(['source_row_index','building_id','decision_state','recount_evaluated','polygon_ids_json','in_union'])
    for r in ledger:writer.writerow([csv_value(v) for v in [r['source_row_index'],r['building_id'],r['decision_state'],r['recount_evaluated'],r['polygon_ids'],r['in_union']]])
    return {'result.json':canonical_bytes(result),'membership.json':canonical_bytes(ledger),'membership.csv':stream.getvalue().encode(),
        'delta.json':canonical_bytes(delta),'review.html':render(result,ledger,read_json(root/'polygons.geojson'))}


def verify(root):
    root=Path(root);manifest=verify_manifest(root)
    if manifest.get('software')!=software_versions():raise ValueError('Use recorded geometry software versions')
    if manifest['schema_version']!='li5_manifest_v1':raise ValueError('Not LI-5')
    binding=read_json(root/'input_binding.json');parent=read_json(root/'input/parent_manifest.json')
    if digest(root/'input/parent_manifest.json')!=binding['parent_manifest_sha256']:raise ValueError('Parent binding changed')
    files={r['path']:r for r in parent['files']}
    for name in INPUTS:
        if digest(root/'input'/name)!=files[name]['sha256']:raise ValueError('Input differs from parent')
    for name,data in output_bytes(root).items():
        if (root/name).read_bytes()!=data:raise ValueError('Recount output mismatch: '+name)
    result=read_json(root/'result.json')
    return {'status':'PASS','analysis_status':result['analysis_status'],'source_rows':result['source_records'],
        'evaluated':result['evaluated_selected'],'union':result['union_count'],'result_version':result['result_version']}


def build(source,output,polygons,policy,previous=None):
    source,output=Path(source).resolve(),Path(output).resolve()
    if source==output or output.is_relative_to(source) or source.is_relative_to(output):raise ValueError('Separate output required')
    if output.exists():raise ValueError('Immutable output: choose new directory')
    verify_li4(source);checked_policy(policy);validate_polygons(polygons)
    if previous:verify(Path(previous))
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent))
    try:
        for name in INPUTS:
            dest=stage/'input'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,dest)
        shutil.copyfile(source/'manifest.json',stage/'input/parent_manifest.json')
        context=read_json(source/'snapshot/normalized/context.json')
        radius=context['config']['area_coverage']['parameters']['building_radius_m']['value']
        write_json(stage/'input_binding.json',{'parent_manifest_sha256':digest(source/'manifest.json'),'analysis_radius_m':radius,
            'radius_source':'Verified parent snapshot normalized/context.json config.area_coverage.parameters.building_radius_m.value'})
        write_json(stage/'polygons.geojson',polygons);write_json(stage/'policy.json',policy)
        if previous:shutil.copyfile(Path(previous)/'result.json',stage/'previous_result.json')
        for name,data in output_bytes(stage).items():(stage/name).write_bytes(data)
        for name in ['location_intelligent_recount.py','location_intelligent_li4.py','location_intelligent_li3.py','location_intelligent_li3_sources.py','location_intelligent_validator.py']:
            dest=stage/'engine_source'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(HERE/name,dest)
        dest=stage/'engine_source/fixtures/li5/policy.json';dest.parent.mkdir(parents=True);shutil.copyfile(HERE/'fixtures/li5/policy.json',dest)
        manifest={'schema_version':'li5_manifest_v1','package_status':'SUCCEEDED_WITH_WARNINGS','software':software_versions(),
            'files':[{'path':str(p.relative_to(stage)),'bytes':p.stat().st_size,'sha256':digest(p),'dependencies':[]} for p in sorted(stage.rglob('*')) if p.is_file()]}
        write_json(stage/'manifest.json',manifest);receipt=verify(stage)
        if output.exists():raise ValueError('Output appeared during build')
        stage.rename(output);return receipt
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True);raise


def demo(source,revision):
    """Two overlapping, automatically generated test polygons inside N1 disk."""
    from shapely.geometry import Point,box,mapping
    from shapely import transform as _transform
    def transform(fn,g):return _transform(g,fn,interleaved=False)
    from pyproj import Transformer
    config=read_json(Path(source)/'snapshot/config/pilot.json')['policy']['li3']
    context=read_json(Path(source)/'snapshot/normalized/context.json')
    radius=context['config']['area_coverage']['parameters']['building_radius_m']['value']
    forward=Transformer.from_crs(4326,config['metric_crs'],always_xy=True)
    inverse=Transformer.from_crs(config['metric_crs'],4326,always_xy=True)
    x,y=forward.transform(config['longitude'],config['latitude'])
    fraction={'demo-r1':0.75,'demo-r2':0.90}[revision]
    circle=Point(x,y).buffer(radius*fraction,quad_segs=64)
    west=circle.intersection(box(x-radius,y-radius,x+radius*.15,y+radius))
    east=circle.intersection(box(x-radius*.15,y-radius,x+radius,y+radius))
    return {'type':'FeatureCollection','schema_version':'li_recount_polygons_v1','crs':'EPSG:4326','revision_id':revision,
        'claim_type':'SYNTHETIC_DEMONSTRATION_NOT_BUSINESS_BOUNDARY','generation':{'method':'Overlapping clipped circles','radius_fraction':fraction,'overlap_halfwidth_fraction':0.15,'quad_segs':64},
        'features':[{'type':'Feature','properties':{'polygon_id':name},'geometry':mapping(transform(inverse.transform,g))} for name,g in [('DEMO_WEST',west),('DEMO_EAST',east)]]}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['demo','build','verify']);parser.add_argument('--source',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--root',type=Path)
    parser.add_argument('--polygons',type=Path);parser.add_argument('--policy',type=Path,default=HERE/'fixtures/li5/policy.json');parser.add_argument('--revision',default='demo-r1');parser.add_argument('--previous',type=Path)
    a=parser.parse_args()
    try:
        if a.command=='verify':result=verify(a.root)
        else:
            polygons=demo(a.source,a.revision) if a.command=='demo' else read_json(a.polygons)
            result=build(a.source,a.output,polygons,read_json(a.policy),a.previous)
        print(json.dumps(result,sort_keys=True))
    except Exception as error:
        print(json.dumps({'status':'FAILED','reason':str(error)}),file=sys.stderr);sys.exit(1)
