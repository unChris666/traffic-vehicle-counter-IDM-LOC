"""Bounded real-CUDA smoke; synthetic geometry, no BigQuery/OSM/full-location job."""
import hashlib,json,random,time
from pathlib import Path


def run(output):
    import cupy as cp
    from shapely import STRtree
    from shapely.geometry import Point,LineString,Polygon,box
    from location_intelligent_gpu_diagnostics import compile_cuda_kernels
    from location_intelligent_gpu_validation import gpu_compute_preflight
    from location_intelligent_gpu_geometry import GpuGeometry
    from location_intelligent_gpu_connectors import generate_connectors_gpu
    from location_intelligent_li3_connectors import generate_connectors
    from area_coverage_gpu_batch_tests import parallel_case
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    report={'scope':'SYNTHETIC_CUDA_SMOKE_NOT_LOCATION_BENCHMARK','status':'RUNNING','actual_cuda_executed':False}
    path=output/'gpu_connector_smoke.json';path.write_text(json.dumps(report,indent=2))
    try:
        report['compiler']=compile_cuda_kernels(output)
        report['preflight']=gpu_compute_preflight()
        report['connector_cases']=[]
        for first in [0,40,None]:
            f=parallel_case(first_valid=first)
            expected=generate_connectors(f.base,f.metrics,f.features,f.f)
            actual=generate_connectors_gpu(f.base,f.metrics,f.features,f.f)
            fields=['graph','connectors','edge_sources','edge_rules','blocked_turns','rejected_candidates']
            different=[name for name in fields if actual[name]!=expected[name]]
            if different:raise RuntimeError('GPU_CONNECTOR_EQUIVALENCE_FAILED:'+','.join(different))
            report['connector_cases'].append({'first_valid':first,'status':'PASS','gpu':actual['diagnostics']['gpu_geometry']})
        rng=random.Random(251026);footprints={f'b{j}':box(j*12.,0.,j*12.+8.,8.) for j in range(100)}
        footprints['hole']=Polygon([(0,20),(20,20),(20,40),(0,40)],holes=[[(5,25),(15,25),(15,35),(5,35)]])
        ids=sorted(footprints);tree=STRtree([footprints[k] for k in ids]);geometry=GpuGeometry()
        prepared=[]
        for j in range(400):
            line=LineString([(rng.uniform(-20,1250),rng.uniform(-20,50)),(rng.uniform(-20,1250),rng.uniform(-20,50))])
            prepared.append({'kind':'TARGET','building_id':None,'target':Point(line.coords[1]),'line':line,'epsilon':1e-6})
        prepared += [{'kind':'TARGET','building_id':None,'target':Point(20,0),'line':LineString([(-1,0),(20,0)]),'epsilon':1e-6},
                     {'kind':'BUILDING','building_id':'b0','target':Point(2,2),'line':LineString([(2,2),(20,2)]),'epsilon':1e-6}]
        expected=[]
        for item in prepared:
            expected.append(sorted(k for k,g in footprints.items() if k!=item['building_id']
                and not (item['kind']=='TARGET' and g.covers(item['target'])) and item['line'].intersection(g).length>item['epsilon']))
        elapsed=[]
        for _ in range(2):
            started=time.perf_counter();actual=geometry.footprint_clear_batch(prepared,ids,footprints,tree,footprints.__getitem__)
            cp.cuda.Stream.null.synchronize();elapsed.append(time.perf_counter()-started)
            if [sorted(hit['source'] for hit in row) for row in actual]!=expected:raise RuntimeError('GPU_RESIDENT_RANDOM_EQUIVALENCE_FAILED')
        if geometry.audit['resident_polygon_uploads']!=1:raise RuntimeError('GPU_RESIDENT_REUPLOAD')
        props=cp.cuda.runtime.getDeviceProperties(0)
        report.update(status='PASS',actual_cuda_executed=True,device=props['name'].decode(),
            resident_queries=len(prepared),resident=geometry.audit,resident_batch_seconds=elapsed,
            source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('location_intelligent_gpu*.py')})
    except Exception as error:
        report.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':run('/kaggle/working/gpu_connector_smoke')
