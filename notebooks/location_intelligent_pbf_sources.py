"""Local PBF -> existing raw input contracts; no provider HTTP calls."""
from pathlib import Path
import hashlib,json,re,subprocess,os
from copy import deepcopy
from location_intelligent_li3_sources import read_json,write_json,utc


def matches(tags,filters):
    for selector in filters:
        clauses=re.findall(r'\["([^"]+)"\s*(?:(=|!=|~|!~)\s*"([^"]*)")?\]',selector)
        if not clauses or ''.join('['+c+']' for c in re.findall(r'\[([^]]+)\]',selector))!=selector:
            raise ValueError('UNSUPPORTED_OSM_FILTER')
        good=True
        for key,operator,value in clauses:
            actual=tags.get(key)
            if not operator:valid=actual is not None
            elif operator=='=':valid=actual==value
            elif operator=='!=':valid=actual!=value
            elif operator=='~':valid=actual is not None and bool(re.search(value,actual))
            else:valid=actual is None or not re.search(value,actual)
            good &= bool(valid)
        if good:return True
    return False


def read_extract(path):
    import osmium
    nodes={};ways={};relations={}
    def meta(item):return {'id':int(item.id),'version':int(item.version) or None,'tags':dict(item.tags),
                           'timestamp':item.timestamp.isoformat().replace('+00:00','Z') if item.version else None}
    class Handler(osmium.SimpleHandler):
        def node(self,n):nodes[n.id]={'type':'node',**meta(n),'lon':n.location.lon,'lat':n.location.lat}
        def way(self,w):ways[w.id]={'type':'way',**meta(w),'nodes':[n.ref for n in w.nodes]}
        def relation(self,r):relations[r.id]={'type':'relation',**meta(r),'members':[
            {'type':{'n':'node','w':'way','r':'relation'}[m.type],'ref':m.ref,'role':m.role} for m in r.members]}
    Handler().apply_file(str(path))
    return nodes,ways,relations


def materialize(config,folder,pbf,osmium_binary,pbf_ref):
    import osmium
    from pyproj import Transformer
    from location_intelligent_config import get_config
    from location_intelligent_validator import canonical_hash
    from location_intelligent_li3_sources import build_queries
    from location_intelligent_map_pilot import query_bbox,sha
    from location_intelligent_map_poi import normalize_pois
    from location_intelligent_market_runtime import source_request_config,verify_market_source_packet
    root=Path(folder)
    if (root/'source_manifest.json').exists():verify_market_source_packet(root,config);return
    if config['network_feature_mode']!='ROADS_ONLY_EXPERIMENT':raise RuntimeError('PBF_FULL_FEATURE_PROFILE_NOT_VALIDATED')
    root.mkdir(parents=True,exist_ok=True);network=root/'network_roads_only'
    def emit(path,value,**kwargs):
        path=Path(path)
        if path.exists():
            if read_json(path)!=value:raise RuntimeError('PBF_DRAFT_CONTENT_CHANGED: '+path.name)
            return
        temp=path.with_name(path.stem+'.partial'+path.suffix)
        write_json(temp,value);temp.replace(path)
    policy=get_config();policy['li3'].update(latitude=config['latitude'],longitude=config['longitude'],
        metric_crs=config['metric_crs'],network_bbox_radius_m=config['network_radius_m'])
    tx=Transformer.from_crs(4326,config['metric_crs'],always_xy=True);inv=Transformer.from_crs(config['metric_crs'],4326,always_xy=True)
    x,y=tx.transform(config['longitude'],config['latitude']);r=config['network_radius_m']
    corners=[inv.transform(a,b) for a in (x-r,x+r) for b in (y-r,y+r)]
    road_box=[min(a for a,b in corners),min(b for a,b in corners),max(a for a,b in corners),max(b for a,b in corners)]
    building_box=query_bbox(config['latitude'],config['longitude'],config['building_radius_m']+config['building_query_padding_m'])
    poi_box=query_bbox(config['latitude'],config['longitude'],config['poi_radius_m']+100)
    box=[min(b[0] for b in [road_box,building_box,poi_box]),min(b[1] for b in [road_box,building_box,poi_box]),
         max(b[2] for b in [road_box,building_box,poi_box]),max(b[3] for b in [road_box,building_box,poi_box])]
    with osmium.io.Reader(str(pbf)) as reader:
        header=reader.header();stamp=header.get('osmosis_replication_timestamp')
        if not stamp:raise RuntimeError('PBF_HEADER_SNAPSHOT_TIMESTAMP_MISSING')
        b=header.box();boxes=[(b.bottom_left.lon,b.bottom_left.lat,b.top_right.lon,b.top_right.lat)] if b.valid() else []
    if not boxes or not any(b[0]<=box[0] and b[1]<=box[1] and b[2]>=box[2] and b[3]>=box[3] for b in boxes):
        raise RuntimeError('REQUEST_OUTSIDE_PBF_HEADER_COVERAGE')
    local=root/'local_extract.osm.pbf'
    receipt=local.with_suffix('.receipt.json')
    if not local.exists():
        tmp=local.with_name('local_extract.partial.osm.pbf')
        print('PBF: local extraction START; native CPU scan, no Overpass',flush=True)
        subprocess.run([str(osmium_binary),'extract','--bbox',','.join(map(str,box)),'--strategy','smart',
                        '--overwrite','--output',str(tmp),str(pbf)],check=True)
        tmp.replace(local)
        emit(receipt,{'sha256':sha(local),'pbf_sha256':pbf_ref['sha256'],'bbox':box})
    if not receipt.exists() or read_json(receipt)!={'sha256':sha(local),'pbf_sha256':pbf_ref['sha256'],'bbox':box}:
        raise RuntimeError('PBF_LOCAL_EXTRACT_CHANGED')
    nodes,ways,relations=read_extract(local)
    def inside(n,b):return b[0]<=n['lon']<=b[2] and b[1]<=n['lat']<=b[3]
    def geometry(w):
        missing=[i for i in w['nodes'] if i not in nodes]
        if missing:raise RuntimeError('PBF_MISSING_WAY_NODE: '+str(w['id']))
        return [{'lon':nodes[i]['lon'],'lat':nodes[i]['lat']} for i in w['nodes']]
    def intersects(w,b):return any(inside(nodes[i],b) for i in w['nodes'] if i in nodes)
    filters=build_queries(road_box,policy)['filters']
    roads=[w for w in ways.values() if matches(w['tags'],filters) and intersects(w,road_box)]
    if not roads:raise RuntimeError('PBF_NO_ROADS_IN_REQUESTED_EXTENT')
    wanted={i for w in roads for i in w['nodes']}
    for w in roads:geometry(w)
    payload={'elements':sorted([*roads,*[nodes[i] for i in wanted]],key=lambda e:(e['type'],e['id'])),
             'osm3s':{'timestamp_osm_base':stamp},'generator':'PBF_LOCAL_V1'}
    buildings=[{**w,'geometry':geometry(w)} for w in ways.values()
               if w['tags'].get('building') not in {None,'no'} and intersects(w,building_box)]
    for relation in relations.values():
        if relation['tags'].get('type')!='multipolygon' or relation['tags'].get('building') in {None,'no'}:continue
        members=[ways.get(m['ref']) for m in relation['members'] if m['type']=='way']
        if not any(w and intersects(w,building_box) for w in members):continue
        row=deepcopy(relation)
        for member in row['members']:
            if member['type']=='way':
                if member['ref'] not in ways:raise RuntimeError('PBF_MULTIPOLYGON_MEMBER_MISSING')
                member['geometry']=geometry(ways[member['ref']])
        buildings.append(row)
    pois=[]
    from location_intelligent_map_poi import classify_poi
    for entry in [*nodes.values(),*ways.values(),*relations.values()]:
        if not classify_poi(entry['tags'],market=True):continue
        row=deepcopy(entry)
        if entry['type']!='node':
            coordinates=[]
            if entry['type']=='way':coordinates=geometry(entry)
            else:
                for m in entry['members']:
                    if m['type']=='way' and m['ref'] in ways:coordinates.extend(geometry(ways[m['ref']]))
                    elif m['type']=='node' and m['ref'] in nodes:coordinates.append(nodes[m['ref']])
            if coordinates:row['center']={'lon':(min(n['lon'] for n in coordinates)+max(n['lon'] for n in coordinates))/2,
                                          'lat':(min(n['lat'] for n in coordinates)+max(n['lat'] for n in coordinates))/2}
        pois.append(row)
    layer=normalize_pois(config,{'elements':pois,'osm3s':{'timestamp_osm_base':stamp}})
    layer.update(provider='OPENSTREETMAP_GCS_PBF',raw_payload={'elements':pois,'osm3s':{'timestamp_osm_base':stamp}},
        source_profile='PBF_LOCAL_V1_CENTERS_FROM_SMART_EXTRACT',attempts=[])
    emit(root/'optional_poi_result.json',layer)
    emit(root/'optional_poi_result.receipt.json',{'sha256':sha(root/'optional_poi_result.json')})
    raw={'provider':'OPENSTREETMAP','schema_version':'osm_buildings_adapter_v1','release':stamp,'source_as_of':stamp,
         'bbox':building_box,'payload':{'elements':buildings,'osm3s':{'timestamp_osm_base':stamp}},
         'use_poi_nodes':[n for n in nodes.values() if inside(n,building_box)],'attempts':[],
         'acquired_at':read_json(root/'osm_buildings_raw.json.gz')['acquired_at'] if (root/'osm_buildings_raw.json.gz').exists() else utc(),
         'truncated':False,'bounded_query_complete':True,'source_profile':'PBF_LOCAL_V1'}
    emit(root/'osm_buildings_raw.json.gz',raw)
    network.mkdir(exist_ok=True)
    frozen={'schema_version':'li3_pilot_config_v1','algorithm_version':'LI3_V1','analysis_run_id':network.name,
        'frozen_at':raw['acquired_at'],'policy':policy,'target_xy':[x,y],'reference_metric_bbox':[x-r,y-r,x+r,y+r],
        'extraction_bbox_wgs84':road_box,'diagnostic_gap_m':10.,'building_cache_files':{},
        'source_scope':'GCS_PBF_LOCAL_V1','pbf_input':pbf_ref}
    frozen['config_hash']=canonical_hash(frozen);emit(network/'config/pilot.json',frozen)
    roads_raw={'status':'SUCCEEDED','payload':payload,'provider':'GCS_PBF','pbf_input':pbf_ref}
    emit(network/'raw/osm_roads.json.gz',roads_raw)
    emit(network/'raw/osm_features_roads_only.json.gz',{'status':'SUCCEEDED','payload':payload,
        'coverage':'ROAD_EXTRACT_ONLY_EXTERNAL_FEATURES_NOT_REQUESTED','external_features_requested':False},exclusive=True)
    emit(network/'network_manifest.json',{'config':source_request_config(config),
        'files':{str(p.relative_to(network)):sha(p) for p in network.rglob('*') if p.is_file() and p.name!='network_manifest.json'}},exclusive=True)
    emit(root/'pbf_source.json',{'input':pbf_ref,'header_timestamp':stamp,'profile':'PBF_LOCAL_V1',
        'extract_sha256':sha(local),'extract_bbox':box,'nodes':len(nodes),'ways':len(ways),'relations':len(relations),
        'limits':['New snapshot/source profile; no exact parity claim against older Overpass data',
                  'Header bounding box is a coarse coverage check, not a verified Indonesia boundary polygon',
                  'POI inventory bounded by complete-way/multipolygon extract, not complete real-world inventory']},exclusive=True)
    emit(root/'source_manifest.json',{'config':source_request_config(config),
        'files':{str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}},exclusive=True)
    print('GCS PBF source finalized:',root,flush=True)
