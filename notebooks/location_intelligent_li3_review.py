"""Source-evidence case inventory and static map; not a UI or field survey."""
import argparse
from collections import Counter
from pathlib import Path

from location_intelligent_li3_sources import read_json, write_json


def review(root):
    graph = read_json(root/'graph/graph.json.gz')
    sources = read_json(root/'graph/edge_sources.json.gz')
    connections = read_json(root/'connectors/connectors.json.gz')
    rejected = read_json(root/'connectors/rejected.json.gz')
    decisions = read_json(root/'building_results/decisions.json.gz')
    report = read_json(root/'report.json')
    by_way = {}
    for source in sources.values():
        by_way[source['osm_way_id']] = source['raw_tags']
    cases = {}
    predicates = {
        'one_way': lambda t: t.get('oneway') in {'yes','1','-1','true'} or t.get('junction') == 'roundabout',
        'alley_or_service': lambda t: t.get('highway') == 'service' or t.get('service') == 'alley',
        'motorcar_ban_motorcycle_exception': lambda t: t.get('motorcar') == 'no' and t.get('motorcycle') in {'yes','designated','permissive'},
        'motor_permitted_track_path': lambda t: t.get('highway') in {'track','path'} and (t.get('motorcycle') in {'yes','designated','permissive'} or t.get('motor_vehicle') in {'yes','designated','permissive'}),
        'private': lambda t: 'private' in [t.get(k) for k in ['access','vehicle','motor_vehicle','motorcycle']],
        'motorcycle_prohibition': lambda t: t.get('motorcycle') == 'no',
        'bridge': lambda t: t.get('bridge') not in {None,'no'},
        'tunnel_or_elevated': lambda t: t.get('tunnel') not in {None,'no'} or t.get('layer','0') not in {'0','0.0'},
        'conditional_access': lambda t: any(':conditional' in k for k in t),
    }
    for name, predicate in predicates.items():
        found = [(i,t) for i,t in sorted(by_way.items()) if predicate(t)]
        cases[name] = {'source_way_count':len(found), 'examples':[{'osm_way_id':i,'raw_tags':t} for i,t in found[:5]],
                       'evidence_type':'ACTUAL_SOURCE_TAGS_NOT_FIELD_VERIFICATION'}
    selected_rows = [r for r in decisions if r['selection_status']=='SELECTED']
    cases['building_outcomes'] = {'counts':dict(Counter(r['decision_state'] for r in selected_rows)),
        'examples_by_state':{state:[{'building_id':r['building_id'],'source_row_index':r['source_row_index'],'reason':r['reason']} for r in selected_rows if r['decision_state']==state][:5] for state in sorted({r['decision_state'] for r in selected_rows})}}
    used = set()
    for r in selected_rows:
        if r.get('selected_candidate'):
            used.update(r['selected_candidate']['network_edges'])
    bridge_used = sorted({sources[e]['osm_way_id'] for e in used if sources[e]['raw_tags'].get('bridge') not in {None,'no'}})
    cases['selected_paths_bridge_usage'] = {'bridge_way_ids':bridge_used,'count':len(bridge_used),
        'claim':'Source graph route traverses mapped bridge; connector does not jump river'}
    cases['connector_rejections'] = {'candidate_denominator':len(rejected),'reason_counts':dict(Counter(r['reason'] for r in rejected)),
                                   'note':'Candidate counts are not building counts; same building can have many rejected alternatives'}
    cases['target_connector'] = next((c for c in connections if c['kind']=='TARGET'), None)
    cases['turn_relations'] = report['connector_diagnostics']['turn_relations']
    cases['graph_diagnostics'] = report['graph']
    cases['limitations'] = ['Narrowness not inferred from service classification; width only if source supplies it',
        'Source tags/geometric checks are not a site visit', 'Synthetic fixtures cover unavailable/unresolved edge cases separately',
        'No implication that all real edge cases have been validated', 'Non-atomic source timestamps remain explicit in report']
    write_json(root/'validation/case_review.json', cases)
    return cases


def plot(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection, PatchCollection
    from matplotlib.patches import Polygon
    import numpy as np
    graph = read_json(root/'graph/graph.json.gz')
    metrics = read_json(root/'normalized/metric_buildings.json')
    decisions = read_json(root/'building_results/decisions.json.gz')
    target = metrics['target_xy']; x,y = target
    colors={'ACCEPTED':'#269d68','ACCESS_UNVERIFIED':'#9765bc','NO_VALID_CONNECTOR':'#d65d49','OVER_TIME_LIMIT':'#e5a02b','EXCLUDED_BY_SELECTION':'#d5d5d5'}
    by_id={r['building_id']:r['decision_state'] for r in decisions}
    fig,ax=plt.subplots(figsize=(11,10))
    lines=[];linecolors=[]
    for edge in graph['edges']:
        coords=edge['geometry']['coordinates']
        if max(p[0] for p in coords)<x-470 or min(p[0] for p in coords)>x+470 or max(p[1] for p in coords)<y-470 or min(p[1] for p in coords)>y+470:
            continue
        lines.append(coords);linecolors.append('#7aafcb' if edge['access_allowed'] is True else '#b8b8b8')
    ax.add_collection(LineCollection(lines,colors=linecolors,linewidths=.6,zorder=1))
    patches=[];facecolors=[]
    for b in metrics['all_buildings']:
        geometry=b['metric_geometry'];polygons=geometry['coordinates'] if geometry['type']=='MultiPolygon' else [geometry['coordinates']]
        for poly in polygons:
            patches.append(Polygon(np.asarray(poly[0]),closed=True));facecolors.append(colors.get(by_id.get(b['building_id']),'#dddddd'))
    ax.add_collection(PatchCollection(patches,facecolor=facecolors,edgecolor='white',linewidth=.15,alpha=.8,zorder=2))
    ax.plot(x,y,'*',color='#111111',markersize=15,label='N1 technical target',zorder=5)
    for state,color in colors.items():ax.plot([],[],marker='s',linestyle='',color=color,label=state)
    ax.set_xlim(x-470,x+470);ax.set_ylim(y-470,y+470);ax.set_aspect('equal');ax.ticklabel_format(useOffset=False,style='plain')
    ax.set_title('LI-3 source-based pilot decisions\nAssumed entrances /7kmh scenario; no physical-access validation')
    ax.set_xlabel('EPSG:32748 easting (m)');ax.set_ylabel('northing (m)');ax.legend(loc='upper left',fontsize=7)
    fig.tight_layout();path=root/'validation/pilot_overview.png';path.parent.mkdir(parents=True,exist_ok=True);fig.savefig(path,dpi=160);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--plot',action='store_true');a=p.parse_args()
    if a.plot:plot(a.root)
    else:review(a.root)
