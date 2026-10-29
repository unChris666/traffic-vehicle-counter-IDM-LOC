"""One job per process. Baseline ZIPs remain immutable; compute uses private copies."""
from pathlib import Path
import json,sys,zipfile,gzip,copy,subprocess
from ..sources.snapshots import MarketSnapshot
from ..artifact_refs import checked
from ..domain.capacity import estimate_capacity
from ..domain.market import huff
from ..domain.aggregation import reconcile
from ..domain.routing import replay_recorded
from ..runtime.environment import fingerprint
from .checkpoints import record
from ....artifacts import read,write,semantic_hash


def execute(request,root):
    source=checked(request['baseline']['path'],request['baseline']['sha256'])
    if request['operation']=='compute_gpu_sources':
        from ..sources.bundle import SourceBundle
        snapshot=SourceBundle(source)
    else:snapshot=MarketSnapshot(source)
    work=root/'work';work.mkdir()
    with zipfile.ZipFile(source) as z:z.extractall(work)
    record(root,'inputs','SUCCEEDED')
    config=copy.deepcopy(snapshot.config['CONFIG']);policy=snapshot.config['MARKET_CONFIG']
    pilot=work/'pilot';native=copy.deepcopy(snapshot.native)
    scope={};fresh=request['operation'] in {'compute_gpu_frozen','compute_gpu_sources'}
    if fresh:
        from .._kernel.location_intelligent_gpu import gpu_preflight
        from ..backends.runtime_gpu import build_gpu,build_market_gpu
        from .._kernel.location_intelligent_osm_buildings import prepare_osm_from_network
        from .._kernel.location_intelligent_li3 import make_manifest
        from .._kernel.location_intelligent_market_scope import market_scope
        record(root,'gpu_preflight','RUNNING')
        report=gpu_preflight(0)
        write(root/'gpu_preflight.json',report)
        # Fresh CUDA cannot proceed on a different declared scientific runtime.
        record(root,'runtime_validation','RUNNING')
        import importlib.metadata,platform
        expected=(snapshot.runtime_profile['scientific']['packages'] if snapshot.native is None else read(work/'pilot/config/source_software.json')['packages'])
        names=['numpy','pandas','shapely','pyproj','networkx','folium','osmnx']
        differences=[n for n in names if importlib.metadata.version(n)!=expected[n]]
        command='import json,platform,pyproj;from osgeo import gdal;print(json.dumps({"python":platform.python_version(),"gdal":gdal.VersionInfo("RELEASE_NAME"),"pyproj":pyproj.__version__}))'
        core=json.loads(subprocess.check_output([request['core_python'],'-c',command],text=True))
        if core!=(snapshot.runtime_profile['core'] if snapshot.native is None else read(work/'pilot/config/core_software.json')):differences.append('core_runtime')
        if differences:raise RuntimeError('AREA_FROZEN_RUNTIME_MISMATCH: '+','.join(differences))
        config['core_python']=request['core_python'];pilot=root/'computation/pilot'
        normalized={**config,'osm_poi_snapshot_path':str(work/'sources/optional_poi_result.json')}
        record(root,'normalization','RUNNING')
        prepare_osm_from_network(normalized,pilot,work/'sources/network_roads_only',work/'sources/osm_buildings_raw.json.gz')
        record(root,'graph_routing','RUNNING')
        build_gpu(pilot,root/'gpu_runtime.json',device=0);make_manifest(pilot)
        from .._kernel.location_intelligent_li3 import map_decisions
        calc_paths=['graph/graph.json.gz','connectors/connectors.json.gz','normalized/metric_buildings.json',
                    'building_results/routing.json.gz','building_results/decisions.json.gz']
        from ..domain.comparison import routing_view
        calc_mismatch=[]
        for name in calc_paths:
            if snapshot.native is None:continue
            observed,expected_value=read(pilot/name),read(work/'pilot'/name)
            if name=='building_results/routing.json.gz':observed,expected_value=routing_view(observed),routing_view(expected_value)
            if observed!=expected_value:calc_mismatch.append(name)
        if calc_mismatch:raise RuntimeError('AREA_FROZEN_CALCULATION_PARITY_FAILED: '+','.join(calc_mismatch))
        record(root,'calculation','SUCCEEDED')
        layers={kind:read(work/'bq_snapshot'/f'{kind}.json') for kind in ['competitor','indomaret']}
        facilities=read(work/'sources/optional_poi_result.json')
        record(root,'market_allocation','RUNNING')
        with market_scope():native=build_market_gpu(config,policy,pilot,layers,facilities,root/'computed_market',report_path=root/'gpu_runtime.json',device=0)
        from .._kernel.location_intelligent_gpu import release_gpu
        record(root,'market_allocation','SUCCEEDED')
        record(root,'gpu_release','RUNNING')
        write(root/'gpu_release.json',release_gpu(0))
        fields=['rows','summary','stores','excluded_stores','attractor_gate','market_inputs_complete','competitor_groups','routing_clusters']
        mismatch=[k for k in fields if native[k]!=snapshot.native[k]] if snapshot.native is not None else []
        scope={'status':'PASS' if snapshot.native is not None else 'NOT_REQUESTED','fresh_gpu_executed':True,'compared':fields if snapshot.native is not None else [],
               'calculation_compared':calc_paths if snapshot.native is not None else [],'mismatches':mismatch,
               'golden_result_required':False,'prior_result_used':snapshot.native is not None}
        if mismatch:raise RuntimeError('AREA_FROZEN_GPU_PARITY_FAILED: '+','.join(mismatch))
    else:
        record(root,'recorded_routing','RUNNING')
        from .._kernel.location_intelligent_li3_sources import read_json
        old_route=read(pilot/'building_results/routing.json.gz')
        subprocess.run([request['core_python'],'-m',
            'traffic_location.location.area._kernel.location_intelligent_gpu_worker',
            '--root',str(pilot),'--scope',str(work/'gpu_runtime/pilot-gpu-weighted.json.gz'),
            '--weighted','--audit-path',str(root/'routing_audit.json')],check=True)
        if read(pilot/'building_results/routing.json.gz')!=old_route:raise RuntimeError('AREA_RECORDED_ROUTING_PARITY_FAILED')
        write(root/'routing_replay.json.gz',read(pilot/'building_results/routing.json.gz'))
        # Restore original bytes so the native pilot manifest remains valid.
        with zipfile.ZipFile(source) as z:(pilot/'building_results/routing.json.gz').write_bytes(z.read('pilot/building_results/routing.json.gz'))
        selection=read(pilot/'building_results/selection.json');frozen=read(pilot/'config/pilot.json')
        capacity=estimate_capacity(selection,frozen['policy'])
        if capacity!=snapshot.capacity:raise RuntimeError('AREA_CAPACITY_PARITY_FAILED')
        scored=0
        for row in native['rows']:
            if row['scores']:
                values=[{k:v for k,v in s.items() if k!='huff_score'} for s in row['scores']]
                if huff(values,policy['allocation_requirements']['huff_exponent'])!=row['scores']:
                    raise RuntimeError('AREA_RETAINED_HUFF_PARITY_FAILED')
                scored+=1
        if reconcile(native['rows'])!=native['summary']:raise RuntimeError('AREA_AGGREGATION_PARITY_FAILED')
        scope={'status':'PASS_RETAINED_EVIDENCE_ONLY','fresh_gpu_executed':False,'retained_routing_rows':len(old_route['routes']),
               'retained_scored_contender_groups':scored,'capacity_exact':True,'routing_exact':True,
               'huff_retained_contenders_exact':True,'aggregate_exact':True,
               'not_compared':['fresh candidate generation','fresh graph/connectors','full market route matrix generation']}
        record(root,'recorded_routing','SUCCEEDED')
    if request.get('population_rwi'):
        from ....integration.population import records
        native['population_estimates']=records(read(pilot/'normalized/buildings.geojson')['features'],native['rows'],request['population_rwi'])
    # Render from a relocated copy. Only presentation output_path changes.
    if request['render']:
        from ..outputs.map import render_safely
        native=copy.deepcopy(native);target=root/'presentation';target.mkdir()
        native['output_path']=str(target);write(target/'result.json',native)
        facilities=read(work/'sources/optional_poi_result.json')
        record(root,'renderer','RUNNING')
        presentation=render_safely(config,policy,pilot,facilities,native)
        presentation_ref=str(Path(presentation['html']).relative_to(root)) if presentation['status']=='SUCCEEDED' else None
        record(root,'renderer',presentation['status'],code=presentation.get('code'),html=presentation_ref)
    record(root,'export','RUNNING')
    write(root/'native.json.gz',native)
    write(root/'capacity.json',snapshot.capacity if not fresh else read(pilot/'building_results/capacity.json'))
    result={'schema_version':'area_execution_result_v1','execution_status':'SUCCEEDED',
        'operation':request['operation'],'data_quality_status':native['status'],
        'claim_type':'EXPERIMENTAL_SCENARIO','source_zip_sha256':snapshot.source_zip_sha256,
        'summary':native['summary'],'native_domain_sha256':semantic_hash({k:v for k,v in native.items() if k not in {'identity','fingerprint','output_path'}}),
        'parity_scope':scope,'environment':fingerprint(),'gpu_cpu_equivalence':'NOT_VERIFIED',
        'production_ready':False,'presentation_ref':presentation_ref if request['render'] else None,
        'presentation_status':presentation['status'] if request['render'] else 'NOT_REQUESTED'}
    write(root/'result.json',result);record(root,'worker','SUCCEEDED')
    return result


if __name__=='__main__':
    request=read(sys.argv[1]);root=Path(sys.argv[2])
    try:execute(request,root)
    except BaseException as error:
        try:checkpoint=read(root/'checkpoint.json')
        except (OSError,ValueError):checkpoint={'stage':'startup'}
        write(root/'failure.json',{'execution_status':'FAILED','stage':checkpoint['stage'],'error_type':type(error).__name__,'code':getattr(error,'code',type(error).__name__),'message':str(error)[:1000],'published_success':False})
        raise
