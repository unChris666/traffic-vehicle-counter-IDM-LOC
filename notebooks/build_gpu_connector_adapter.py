"""Generate visible batched GPU connector adapter from frozen canonical source.

Pure control-flow/graph assembly remains baseline. Domain source is never edited.
"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent

def build():
 source=(ROOT/'location_intelligent_li3_connectors.py').read_text()
 baseline=json.loads((ROOT.parent/'docs/AREA_COVERAGE_GPU_BASELINE.json').read_text())
 if hashlib.sha256(source.encode()).hexdigest()!=baseline['cpu_helpers_sha256']['location_intelligent_li3_connectors.py']:raise ValueError('CONNECTOR_BASELINE_CHANGED_REBASE_REQUIRED')
 text=source[source.index('def generate_connectors('):]
 text=text.replace('def generate_connectors(', 'def generate_connectors_gpu(').replace('*, alternative_targets=None):','*, alternative_targets=None,device=0,audit_path=None):',1)
 text=text.replace('    from shapely.ops import nearest_points','    from shapely.ops import nearest_points\n    from location_intelligent_li3_connectors import barrier_index,check_barriers\n    from location_intelligent_gpu_geometry import GpuGeometry,GpuCandidatePlanner',1)
 text=text.replace('entrance, access = target, nearest_points(target,', 'entrance, access = rep, nearest_points(rep,')
 text=text.replace('[target.x, target.y]', '[rep.x, rep.y]')
 marker='    def candidate(kind, building_id, rep, footprint, index, measured_distance=None):'
 assert marker in text;text=text.replace(marker,'    def prepare(kind, building_id, rep, footprint, index, measured_distance=None):',1)
 start=text.index('        clear, hits = check_barriers(line, barrier, epsilon)');end=text.index('        if clear is not True:',start)
 prefix='''        return {'kind':kind,'building_id':building_id,'target':rep,'line':line,'epsilon':epsilon,
                'group_id':group_id,'node':node,'position':position,'coords':coords,'distance':distance}

    def commit(item,clear,hits):
        if item is None:return None
        kind=item['kind'];building_id=item['building_id'];group_id=item['group_id']
        node=item['node'];position=item['position'];coords=item['coords'];distance=item['distance'];line=item['line']
        name=groups[group_id]['road_class'];name=name[:-5] if name.endswith('_link') else name
'''
 text=text[:start]+prefix+text[end:]
 # Preserve candidate value construction and all final graph splitting code.
 start=text.index('    # No numerical target search cap.');end=text.index('    nodes = ',start)
 batch='''    geometry=GpuGeometry(device)
    planner=GpuCandidatePlanner(geometry,geometries,group_ids,tree,metrics,alternative_targets,maximum)
    def evaluate(requests):
        items=[prepare(*request) for request in requests]
        barriers=geometry.barrier_batch(items,barrier,epsilon)
        footprint_hits=geometry.footprint_clear_batch(items,footprint_ids,footprints,footprint_tree,inset_geometry)
        results=[]
        for item,(clear,hits),obstacles in zip(items,barriers,footprint_hits):
            if clear is True and obstacles:clear=False;hits=hits+obstacles
            results.append(commit(item,clear,hits))
        return results
    def process(entries):
        pending={}
        for key,kind,bid,point,footprint in entries:
            iterator=iter(planner.ordered(point,maximum if kind=='BUILDING' else None))
            option=next(iterator,None)
            if option is not None:pending[key]=[kind,bid,point,footprint,iterator,option]
        while pending:
            order=sorted(pending,key=lambda key:(group_ids[pending[key][5][1]],key))
            requests=[]
            for key in order:
                kind,bid,point,footprint,iterator,(distance,index)=pending[key]
                requests.append((kind,bid,point,footprint,index,distance))
            answers=evaluate(requests)
            for key,answer in zip(order,answers):
                state=pending[key]
                if answer is not None:
                    if state[0]=='TARGET' and key!='candidate':
                        answer['connector_id']='alternative_'+key+'_'+answer['connector_id'];answer['alternative_store_key']=key
                    del pending[key]
                else:
                    option=next(state[4],None)
                    if option is None:del pending[key]
                    else:state[5]=option
            print('GPU connector batch: '+str(len(order))+' candidates; remaining='+str(len(pending)),flush=True)
    entries=[('candidate','TARGET',None,Point(*metrics['target_xy']),None)]
    entries += [(row['store_key'],'TARGET',None,Point(*row['target_xy']),None) for row in sorted(alternative_targets or [],key=lambda r:r['store_key'])]
    entries += [(b['building_id'],'BUILDING',b['building_id'],Point(*b['representative_point_m']),footprints[b['building_id']]) for b in sorted(metrics['selected_buildings'],key=lambda b:b['building_id'])]
    if not nearest:
        raise ValueError('GPU_CONNECTORS_V2_REQUIRES_FROZEN_NEAREST_PROFILE')
    process(entries)
    diagnostics.update(gpu_geometry=dict(geometry.audit),building_entrance_profile=profile)
    if audit_path is not None:
        from location_intelligent_gpu_runtime import _report
        _report(audit_path,{'stage':'connectors','geometry':dict(geometry.audit)})
'''
 text=text[:start]+batch+text[end:]
 header='''"""Visible GPU-batched adapter; generated from frozen CPU graph assembly.

Rebuild with build_gpu_connector_adapter.py; business baseline is unchanged.
GPU FP64 candidate distances + batched polygon intersection. Canonical scalar
endpoint construction remains GEOS; ambiguous intersection falls back with audit.
"""
from collections import defaultdict
from copy import deepcopy
import math
'''
 (ROOT/'location_intelligent_gpu_connectors.py').write_text(header+text)

if __name__=='__main__':build()
