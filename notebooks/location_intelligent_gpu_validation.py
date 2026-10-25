"""Mandatory CPU equivalence gate; reference uses frozen business algorithms."""
from pathlib import Path
import shutil

def _record(path,stage,report):
    from location_intelligent_li3_sources import read_json,write_json
    path=Path(path);result=read_json(path) if path.exists() else {'schema':'gpu_equivalence_v2'}
    result[stage]=report;write_json(path,result)

def validate_calculation(pilot,reference,report_path):
    from location_intelligent_li3 import build,make_manifest,verify_manifest
    from location_intelligent_li3_sources import read_json
    pilot=Path(pilot);reference=Path(reference);verify_manifest(pilot)
    print('GPU VALIDATION: CPU reference calculation; this validation pass also costs CPU time',flush=True)
    if (reference/'manifest.json').exists():verify_manifest(reference)
    else:
        if reference.exists():raise ValueError('INCOMPLETE_CPU_REFERENCE_INSPECT_REQUIRED')
        shutil.copytree(pilot,reference);(reference/'manifest.json').unlink()
        from unittest.mock import patch
        from location_intelligent_gpu_runtime import run_core_with_python
        with patch('location_intelligent_li3.run_core',run_core_with_python):build(reference)
        make_manifest(reference)
    paths=['normalized/metric_buildings.json','building_results/selection.json','building_results/capacity.json',
           'graph/graph.json.gz','connectors/connectors.json.gz','building_results/routing.json.gz','building_results/decisions.json.gz']
    mismatches=[name for name in paths if read_json(pilot/name)!=read_json(reference/name)]
    report={'status':'PASS' if not mismatches else 'FAIL','reference':str(reference),'compared':paths,'mismatches':mismatches}
    _record(report_path,'calculation',report)
    if mismatches:raise RuntimeError('GPU_CALCULATION_EQUIVALENCE_FAILED: '+','.join(mismatches))
    print('GPU VALIDATION calculation: PASS',flush=True)
    return reference

def validate_market(config,market_config,pilot,layers,facilities,actual,output,report_path):
    from location_intelligent_market_runtime import build_market
    print('GPU VALIDATION: CPU reference market',flush=True)
    expected=build_market(config,market_config,pilot,layers,facilities,output)
    fields=['rows','summary','stores','excluded_stores','attractor_gate','market_inputs_complete','competitor_groups','routing_clusters']
    mismatches=[name for name in fields if actual[name]!=expected[name]]
    report={'status':'PASS' if not mismatches else 'FAIL','compared':fields,'mismatches':mismatches}
    _record(report_path,'market',report)
    if mismatches:raise RuntimeError('GPU_MARKET_EQUIVALENCE_FAILED: '+','.join(mismatches))
    print('GPU VALIDATION market: PASS',flush=True)
    return report


def gpu_compute_preflight(device=0):
    """Run all V2 CUDA kernels against small canonical fixtures before data fetch."""
    from shapely.geometry import Point,LineString,Polygon,MultiPolygon
    from location_intelligent_gpu_geometry import GpuGeometry
    from location_intelligent_gpu_weighted import CupyWeightedRouter
    from location_intelligent_motor_routing import _path_index
    geometry=GpuGeometry(device)
    points=[[1.,2.],[0.,0.]];segments=[[0.,0.,10.,0.],[0.,0.,0.,10.]];pairs=[(0,0),(1,1)]
    distances=geometry.distances(points,segments,pairs)
    for value,(p,s) in zip(distances,pairs):
        if abs(value-Point(*points[p]).distance(LineString([segments[s][:2],segments[s][2:]])))>1e-12:raise RuntimeError('GPU_DISTANCE_SELF_TEST_FAILED')
    polygon=Polygon([(0,0),(10,0),(10,10),(0,10)],holes=[[(3,3),(7,3),(7,7),(3,7)]])
    lines=[LineString([(-1,5),(11,5)]),LineString([(4,4),(6,6)]),LineString([(-1,0),(11,0)]),LineString([(1,1),(2,2)])]
    for number,(line,(value,uncertain,error)) in enumerate(zip(lines,geometry.polygon_lengths([(line,polygon) for line in lines]))):
        if number in [0,1,3] and uncertain:raise RuntimeError('GPU_POLYGON_SELF_TEST_UNEXPECTED_AMBIGUITY')
        if not uncertain and abs(value-line.intersection(polygon).length)>max(error,1e-10):raise RuntimeError('GPU_POLYGON_SELF_TEST_FAILED')
    multi=MultiPolygon([polygon,Polygon([(20,0),(30,0),(30,10),(20,10)])])
    line=LineString([(-1,5),(31,5)])
    value,uncertain,error=geometry.polygon_lengths([(line,multi)])[0]
    if uncertain or abs(value-line.intersection(multi).length)>max(error,1e-10):raise RuntimeError('GPU_MULTIPOLYGON_SELF_TEST_FAILED')
    primitive=LineString([(0,5),(10,5)])
    hit,uncertain=geometry.primitive_intersections([(LineString([(5,0),(5,10)]),primitive)])[0]
    if not hit or uncertain:raise RuntimeError('GPU_BARRIER_SELF_TEST_FAILED')
    # Exercise resident indexing, ownership exclusions, holes and reuse on device.
    from shapely import STRtree
    footprints={'a':polygon,'b':Polygon([(20,0),(30,0),(30,10),(20,10)])}
    ids=sorted(footprints);tree=STRtree([footprints[fid] for fid in ids])
    prepared=[{'kind':'TARGET','building_id':None,'target':Point(-1,5),'line':line,'epsilon':1e-6}
              for line in [LineString([(-1,5),(31,5)]),LineString([(4,4),(6,6)]),LineString([(-1,0),(11,0)])]]
    for _ in range(2):
        actual=geometry.footprint_clear_batch(prepared,ids,footprints,tree,footprints.__getitem__)
        expected=[[{'source':fid,'kind':'other_building'} for fid in ids
                   if not footprints[fid].covers(item['target']) and item['line'].intersection(footprints[fid]).length>item['epsilon']]
                  for item in prepared]
        if [sorted(h,key=lambda x:x['source']) for h in actual]!=expected:raise RuntimeError('GPU_RESIDENT_FOOTPRINT_SELF_TEST_FAILED')
    if geometry.audit.get('resident_polygon_uploads')!=1:raise RuntimeError('GPU_RESIDENT_REUSE_SELF_TEST_FAILED')
    graph={'nodes':[{'node_id':n} for n in 'abcd'],'edges':[
      {'edge_id':'ab','u':'a','v':'b','length_m':2.}, {'edge_id':'bc','u':'b','v':'c','length_m':3.},
      {'edge_id':'ac','u':'a','v':'c','length_m':9.}, {'edge_id':'cd','u':'c','v':'d','length_m':1.}]}
    allowed={e['edge_id']:True for e in graph['edges']};blocked=set()
    for blocked in [set(),{('ab','bc')}]:
        router=CupyWeightedRouter(graph,allowed,blocked,device);router.compute(['c','d'])
        for target in ['c','d']:
            gpu=router.lookup(target);cpu=_path_index(graph,allowed,blocked,target)
            for start in 'abcd':
                if gpu(start)!=cpu(start):raise RuntimeError('GPU_WEIGHTED_SELF_TEST_FAILED')
    return {'status':'SUCCEEDED','backend':'GPU_WEIGHTED_GEOMETRY_V2','actual_cuda_executed':True,
            'geometry':geometry.audit,'weighted':router.audit}
