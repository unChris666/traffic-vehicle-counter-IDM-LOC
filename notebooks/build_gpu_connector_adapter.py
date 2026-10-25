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
 text=text.replace('def generate_connectors(', 'def generate_connectors_gpu(').replace('*, alternative_targets=None):','*, alternative_targets=None,device=0,audit_path=None,candidate_window=32):',1)
 text=text.replace('    from shapely.ops import nearest_points','    from shapely.ops import nearest_points\n    from location_intelligent_li3_connectors import barrier_index,check_barriers\n    from location_intelligent_gpu_geometry import GpuGeometry,GpuCandidatePlanner',1)
 text=text.replace('entrance, access = target, nearest_points(target,', 'entrance, access = rep, nearest_points(rep,')
 text=text.replace('[target.x, target.y]', '[rep.x, rep.y]')
 marker='    def candidate(kind, building_id, rep, footprint, index, measured_distance=None):'
 assert marker in text;text=text.replace(marker,'    def prepare(kind, building_id, rep, footprint, index, measured_distance=None):',1)
 # Speculative preparation must never mutate the canonical rejection/cut lists.
 text=text.replace("            rejected.append({'kind': kind, 'building_id': building_id, 'source_segment': group_id, 'reason': reason, 'distance_m': distance})\n            return None",
                   "            return {'rejection': {'kind': kind, 'building_id': building_id, 'source_segment': group_id, 'reason': reason, 'distance_m': distance}}",1)
 start=text.index('        clear, hits = check_barriers(line, barrier, epsilon)');end=text.index('        if clear is not True:',start)
 prefix='''        return {'kind':kind,'building_id':building_id,'target':rep,'line':line,'epsilon':epsilon,
                'group_id':group_id,'node':node,'position':position,'coords':coords,'distance':distance}

    def commit(item,clear,hits):
        if item is None:return None
        if 'rejection' in item:
            rejected.append(item['rejection']);return None
        kind=item['kind'];building_id=item['building_id'];group_id=item['group_id']
        node=item['node'];position=item['position'];coords=item['coords'];distance=item['distance'];line=item['line']
        name=groups[group_id]['road_class'];name=name[:-5] if name.endswith('_link') else name
'''
 text=text[:start]+prefix+text[end:]
 # Preserve candidate value construction and all final graph splitting code.
 start=text.index('    # No numerical target search cap.');end=text.index('    nodes = ',start)
 batch='''    if not isinstance(candidate_window,int) or not 1<=candidate_window<=256:
        raise ValueError('GPU_CANDIDATE_WINDOW_MUST_BE_1_TO_256')
    from itertools import islice
    from time import perf_counter
    geometry=GpuGeometry(device)
    planner=GpuCandidatePlanner(geometry,geometries,group_ids,tree,metrics,alternative_targets,maximum)
    def evaluate(requests):
        items=[prepare(*request) for request in requests]
        valid=[item if item is not None and 'rejection' not in item else None for item in items]
        barriers=geometry.barrier_batch(valid,barrier,epsilon)
        footprint_hits=geometry.footprint_clear_batch(valid,footprint_ids,footprints,footprint_tree,inset_geometry)
        results=[]
        for item,(clear,hits),obstacles in zip(items,barriers,footprint_hits):
            if clear is True and obstacles:clear=False;hits=hits+obstacles
            results.append((item,clear,hits))
        return results
    def process(entries):
        pending={};started=perf_counter();waves=0;tested=0;consumed=0;exhausted=0
        for key,kind,bid,point,footprint in entries:
            iterator=iter(planner.ordered(point,maximum if kind=='BUILDING' else None))
            pending[key]=[kind,bid,point,footprint,iterator]
        while pending:
            # Finite windows are an execution batch size, never a search cap.
            # Only consume the prefix through the FIRST valid canonical option.
            order=sorted(pending)[:max(1,4096//candidate_window)]
            requests=[];spans={}
            for key in order:
                kind,bid,point,footprint,iterator=pending[key]
                options=list(islice(iterator,candidate_window));spans[key]=(len(requests),len(options))
                requests.extend((kind,bid,point,footprint,index,distance) for distance,index in options)
            answers=evaluate(requests)
            tested+=len(requests);waves+=1
            for key in order:
                state=pending[key];start,count=spans[key];answer=None
                for item,clear,hits in answers[start:start+count]:
                    consumed+=1;answer=commit(item,clear,hits)
                    if answer is not None:break
                if answer is not None:
                    if state[0]=='TARGET' and key!='candidate':
                        answer['connector_id']='alternative_'+key+'_'+answer['connector_id'];answer['alternative_store_key']=key
                    del pending[key]
                elif count<candidate_window:
                    exhausted+=1;del pending[key]
            if waves==1 or waves%10==0 or not pending:
                print('GPU connectors: batches='+str(waves)+'; evaluated='+str(tested)+
                      '; canonical_checked='+str(consumed)+'; remaining='+str(len(pending))+
                      '; exhausted='+str(exhausted)+'; elapsed='+format(perf_counter()-started,'.1f')+'s',flush=True)
        geometry.audit.update(candidate_window=candidate_window,speculative_evaluated=tested,
            canonical_candidates_checked=consumed,exhausted_targets=exhausted,batch_count=waves,
            connector_elapsed_s=perf_counter()-started)
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
