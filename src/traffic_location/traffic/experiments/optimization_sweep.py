"""Single-video controlled sweep; throughput selection requires domain-equivalence gates."""
import copy
import json
import subprocess
import sys
import time
from pathlib import Path
from ...artifacts import read,write,sha,require,semantic_hash
from .video150 import monitored,COUNT_SCRIPT
from .benchmark import first_difference

EVENT_KEYS=('track_id','physical_unit_id','episode_id','passage_id','activation_frame','decision_frame',
            'category','direction','role','route','status','accepted_count_event','display_id')
DECISION_KEYS=('frame_index','decision_frame','track_id','unit_id','physical_unit_id','physical_episode_id',
               'episode_id','passage_id','category','direction','status','reason','reasons','count_delta','accepted_count_event')
ASSIGN_KEYS=('frame_index','track_id','original_detection_index','unit_id','physical_episode_id','episode_id',
             'role','resolved_class_name','component_of_unit_id')


def project(rows,keys):return [{k:r[k] for k in keys if k in r} for r in rows]


def compare_results(reference,candidate):
    a=read(Path(reference)/'measurement/result.json.gz');b=read(Path(candidate)/'measurement/result.json.gz')
    x=read(Path(reference)/'count-result.json.gz')['native'];y=read(Path(candidate)/'count-result.json.gz')['native']
    links=lambda rows:[(r['frame_index'],sorted((t['track_id'],t['original_detection_index'],t['raw_detection']['class_id']) for t in r['emitted_measurements'])) for r in rows]
    checks={'detector_preprocessing':a['environment'].get('first_preprocessed_sha256')==b['environment'].get('first_preprocessed_sha256') if 'first_preprocessed_sha256' in a['environment'] and 'first_preprocessed_sha256' in b['environment'] else True,
            'frame_coverage': [r['frame_index'] for r in a['records']]==[r['frame_index'] for r in b['records']],
            'track_links':links(a['records'])==links(b['records']), 'aggregate':x['aggregate']==y['aggregate'],
            'accepted_event_anchors':project(x['events'],EVENT_KEYS)==project(y['events'],EVENT_KEYS),
            'cancelled_event_anchors':project(x.get('cancelled_events',[]),EVENT_KEYS)==project(y.get('cancelled_events',[]),EVENT_KEYS),
            'decision_anchors':project(x['decisions'],DECISION_KEYS)==project(y['decisions'],DECISION_KEYS),
            'invalid_decision_anchors':project(x.get('invalid_decisions',[]),DECISION_KEYS)==project(y.get('invalid_decisions',[]),DECISION_KEYS),
            'frame_assignments':project(x.get('frame_assignments',[]),ASSIGN_KEYS)==project(y.get('frame_assignments',[]),ASSIGN_KEYS)}
    return {'domain_equivalent':all(checks.values()),'checks':checks,
            'exact_records_equal':a['records']==b['records'],'raw_event_ids_equal':[r['event_id'] for r in x['events']]==[r['event_id'] for r in y['events']],
            'first_record_difference':first_difference(a['records'],b['records']),
            'first_event_anchor_difference':first_difference(project(x['events'],EVENT_KEYS),project(y['events'],EVENT_KEYS)),
            'first_decision_anchor_difference':first_difference(project(x['decisions'],DECISION_KEYS),project(y['decisions'],DECISION_KEYS)),
            'note':'Artifact-bound event IDs retained separately. Anchor projections do not establish accuracy.'}


def configurations():
    base={'batch_size':1,'precision':'FP32','backend':'pytorch','reid_transport':'original','reid_window':1,'crop_batch':32,'reid_precision':'FP32'}
    changes=[('baseline',{}),('yolo_b4',{'batch_size':4}),('yolo_b8',{'batch_size':8}),('yolo_b16',{'batch_size':16}),
             ('yolo_fp16',{'precision':'FP16'}),('reid_cpu_input',{'reid_transport':'cpu_input'}),
             ('reid_io_binding',{'reid_transport':'io_binding'}),('reid_window8',{'reid_window':8}),
             ('reid_fp16',{'reid_precision':'FP16'}),('trt_fp32',{'backend':'tensorrt','input_shape':[448,640]}),
             ('trt_fp16',{'backend':'tensorrt','precision':'FP16','input_shape':[448,640]})]
    return [{'name':name,**base,**delta} for name,delta in changes]


def pair_configurations():
    base=configurations()[0]
    return [base,{**base,'name':'candidate_fp32','batch_size':4,
                  'reid_transport':'io_binding','reid_window':8}]


def summary(rows):
    if len(rows)!=1 or rows[0]['status']!='SUCCEEDED':return {'status':'INCOMPLETE','runs':rows}
    row=rows[0]
    return {'status':'COMPLETE','processing_plus_counting_seconds':row['processing_seconds']+row['counting_seconds'],
            'startup_seconds':row['startup_seconds'],
            'total_plus_counting_seconds':row['inference_process_seconds']+row['counting_seconds'],
            'runs':rows}


def run_job(base,config,folder,source,geometry,policy,frames,assets,*,legacy_source=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    request=copy.deepcopy(base);request.update(device='cuda:0',frame_limit=frames,start_frame=0,half=config['precision']=='FP16')
    request['experiment']=config
    if config['backend']=='tensorrt':
        key='trt_'+config['precision'].lower()
        if key not in assets:return {'status':'UNAVAILABLE','reason':assets.get('errors',{}).get(key,'Engine unavailable'),'config':config['name']}
        request['artifacts']['detector']=assets[key]
    if config['reid_precision']=='FP16':
        if 'reid_fp16' not in assets:return {'status':'UNAVAILABLE','reason':assets.get('errors',{}).get('reid_fp16','Encoder unavailable'),'config':config['name']}
        request['artifacts']['reid']=assets['reid_fp16']
    if legacy_source is not None:request.pop('experiment');request['half']=False;source=legacy_source
    write(folder/'producer.json',request)
    module='traffic_location.traffic.inference_worker' if legacy_source else 'traffic_location.traffic.experiments.optimization_worker'
    print('START',folder.name,'frames',frames,'config',config['name'],flush=True)
    code,process_seconds=monitored([sys.executable,'-u','-m',module,str(folder/'producer.json'),str(folder/'measurement')],folder,source)
    if code:
        text=(folder/'worker.log').read_text(errors='replace')
        return {'status':'FAILED','reason':'GPU_OUT_OF_MEMORY' if 'out of memory' in text.lower() else 'WORKER_FAILED',
                'tail':text.splitlines()[-12:],'folder':str(folder),'config':config['name']}
    measurement=folder/'measurement/result.json.gz';m=read(measurement);meta=m['metadata']
    require(m['frames']==frames and [r['frame_index'] for r in m['records']]==list(range(frames)),'Frame coverage invalid')
    identity={'video_sha256':request['artifacts']['video']['sha256'],'records_sha256':sha(measurement),'geometry_sha256':sha(geometry),
              'width':meta['width'],'height':meta['height'],'variant':'raw','parent_run_id':'single_gpu_optimization_sweep'}
    q={'schema_version':'traffic_request_v1','profile':'machine','measurement_format':'fresh_v1','video_id':'T7SL-WEEKDAY-PAGI',
       'frame_count':frames,'source_identity':identity,'source_manifest_sha256':semantic_hash({'video':identity['video_sha256'],'frames':frames}),
       'artifacts':{k:{'path':str(p),'sha256':sha(p)} for k,p in [('measurements',measurement),('geometry',geometry),('policy',policy)]}}
    write(folder/'count-request.json',q);script=folder/'count.py';script.write_text(COUNT_SCRIPT)
    with (folder/'counting.log').open('w') as stream:
        result=subprocess.run([sys.executable,str(script),str(folder/'count-request.json'),str(folder),str(folder/'count-result.json.gz'),str(folder/'counting-time.json')],env={**__import__('os').environ,'PYTHONPATH':str(source)},stdout=stream,stderr=subprocess.STDOUT,timeout=5400)
    if result.returncode:return {'status':'FAILED','reason':'COUNTING_FAILED','folder':str(folder),'config':config['name']}
    native=read(folder/'count-result.json.gz')['native'];perf=read(folder/'measurement/performance.json') if not legacy_source else {}
    return {'status':'SUCCEEDED','config':config['name'],'folder':str(folder),'frames':frames,'inference_process_seconds':process_seconds,
        'startup_seconds':process_seconds-perf['processing_seconds'] if perf else None,'model_setup_and_warmup_seconds':perf.get('startup_seconds'),'processing_seconds':perf.get('processing_seconds'),
        'counting_seconds':read(folder/'counting-time.json')['counting_wall_seconds'],'aggregate':native['aggregate'],
        'records_sha256':m['records_semantic_sha256'],'environment':m['environment'],'performance':perf}


def prepare_assets(base,output):
    """Derived models are new hash-bound inputs. Failures remain explicit."""
    assets={'errors':{},'preparation_seconds':{}};output=Path(output);output.mkdir(parents=True,exist_ok=True)
    import shutil
    for key in ('reid_fp16','trt_fp32','trt_fp16'):
        started=time.monotonic()
        try:
            if key=='reid_fp16':
                import onnx
                from onnxconverter_common import float16
                model=onnx.load(base['artifacts']['reid']['path']);model=float16.convert_float_to_float16(model,keep_io_types=False)
                onnx.checker.check_model(model);target=output/'reid-fp16.onnx';onnx.save(model,target)
            else:
                import tensorrt
                from ultralytics import YOLO
                weights=output/(key+'.pt');shutil.copyfile(base['artifacts']['detector']['path'],weights)
                target=Path(YOLO(str(weights)).export(format='engine',device=0,imgsz=[448,640],batch=1,
                            dynamic=False,quantize=16 if key.endswith('fp16') else None,simplify=False,workspace=2,verbose=False))
            assets[key]={'path':str(target.resolve()),'sha256':sha(target)}
        except Exception as exc:assets['errors'][key]=type(exc).__name__+': '+str(exc)
        assets['preparation_seconds'][key]=time.monotonic()-started
        write(output/'manifest.json',assets)
    return assets


def sweep(base,output,source,geometry,policy,full_frames,assets,*,pair_only=False):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    source=Path(source).resolve();geometry=Path(geometry).resolve();policy=Path(policy).resolve()
    configs=pair_configurations() if pair_only else configurations()
    report={'schema_version':'single_gpu_config_sweep_v2','full_frames':full_frames,'runs_per_config':1,
            'automatic_promotion':False,'ground_truth_accuracy':'NOT_EVALUATED','assets':assets,
            'screen':{},'best_config':None}
    for config in configs:
        folder=output/f"full-{config['name']}"
        try:row=run_job(base,config,folder,source,geometry,policy,full_frames,assets)
        except Exception as exc:row={'status':'FAILED','reason':type(exc).__name__+': '+str(exc),'folder':str(folder),'config':config['name']}
        report['screen'][config['name']]=summary([row]);write(output/'report.json',report)
    baseline=report['screen']['baseline']['runs'][0]
    require(baseline['status']=='SUCCEEDED','Baseline failed; cannot select optimized config')
    eligible=[]
    for config in configs:
        score=report['screen'][config['name']]
        if score['status']!='COMPLETE':continue
        score['comparison']=compare_results(baseline['folder'],score['runs'][0]['folder']) if config['name']!='baseline' else None
        score['eligible']=score['comparison']['domain_equivalent'] if score['comparison'] else True
        if score['eligible']:eligible.append(config)
    write(output/'report.json',report)
    if pair_only:
        report['best_config']=min(eligible,key=lambda c:report['screen'][c['name']]['total_plus_counting_seconds'])
        report['selection_scope']='FASTEST_ELIGIBLE_OF_TWO_CONFIGS_ONE_FULL_VIDEO_RUN_EACH'
        report['status']='COMPLETE';write(output/'report.json',report);return report
    # Combine best independently eligible detector and ReID settings, keeping explicit baseline factors.
    det_names={'baseline','yolo_b4','yolo_b8','yolo_b16','yolo_fp16','trt_fp32','trt_fp16'}
    reid_names={'baseline','reid_cpu_input','reid_io_binding','reid_window8','reid_fp16'}
    key=lambda c:report['screen'][c['name']]['processing_plus_counting_seconds']
    best_det=min((c for c in eligible if c['name'] in det_names),key=key)
    best_reid=min((c for c in eligible if c['name'] in reid_names),key=key)
    combo={**best_det,'name':'combined'}
    for k in ('reid_transport','reid_window','crop_batch','reid_precision'):combo[k]=best_reid[k]
    report['combination_factors']={'detector':best_det['name'],'reid':best_reid['name']}
    identical=next((c for c in eligible if {k:v for k,v in c.items() if k!='name'}=={k:v for k,v in combo.items() if k!='name'}),None)
    if identical is not None:
        report['combination_identical_to']=identical['name']
    else:
        try:row=run_job(base,combo,output/'full-combined',source,geometry,policy,full_frames,assets)
        except Exception as exc:row={'status':'FAILED','reason':str(exc),'config':'combined'}
        score=summary([row]);report['screen']['combined']=score
        if score['status']=='COMPLETE':
            score['comparison']=compare_results(baseline['folder'],row['folder'])
            score['eligible']=score['comparison']['domain_equivalent']
            if score['eligible']:eligible.append(combo)
    best=min(eligible,key=lambda c:report['screen'][c['name']]['total_plus_counting_seconds'])
    report['best_config']=best;report['selection_scope']='FASTEST_ELIGIBLE_IN_ONE_FULL_VIDEO_RUN_PER_CONFIG_NOT_REPRODUCIBILITY_PROVEN'
    report['status']='COMPLETE';write(output/'report.json',report);return report
