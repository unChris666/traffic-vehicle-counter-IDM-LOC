"""Isolated fresh detector/tracker/ReID worker; no counting or historical replay.

Run a new OS process for each job: tracker global counters cannot leak between jobs.
External assets are mandatory hash-bound inputs; this module never downloads weights.
"""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import json,sys,random,platform,time
from pathlib import Path
from ..artifacts import artifact,read,write,require,sha,semantic_hash
from .experiments.performance import Progress, batch_size, decode_batches


def execute_baseline(request,output):
 import cv2,numpy as np,torch,ultralytics,onnxruntime
 from ultralytics import YOLO
 from ultralytics.trackers.bot_sort import BOTSORT
 from ultralytics.utils import YAML,IterableSimpleNamespace
 r=request;require(r['schema_version']=='fresh_inference_request_v1','Unsupported fresh request')
 output=Path(output);require(not output.exists(),'Fresh output must not overwrite existing artifacts')
 perf=Progress(output.parent/'progress.json');size=batch_size(r)
 root=Path(r['input_root']);paths={k:artifact(v,root) for k,v in r['artifacts'].items()}
 require(set(paths)=={'video','detector','reid'},'Video/detector/ReID refs required')
 require(ultralytics.__version__==r['ultralytics_version'],'Pinned Ultralytics differs')
 require(r['device'] in {'cpu','cuda:0'},'Explicit supported device required')
 if r['device'].startswith('cuda'):
  require(torch.cuda.is_available(),'Requested GPU unavailable; no CPU fallback')
  require('CUDAExecutionProvider' in onnxruntime.get_available_providers(),'CUDA ReID provider unavailable')
 require(r['start_frame']==0 and type(r['frame_limit']) is int and r['frame_limit']>0,'Bounded prefix only; no skipped tracking context')
 require(r['preprocessing']=='RAW' and r['half'] is False,'Only declared RAW FP32 experiment profile supported')
 if r['device'].startswith('cuda'):torch.cuda.reset_peak_memory_stats()
 random.seed(r['seed']);np.random.seed(r['seed']);torch.manual_seed(r['seed']);torch.set_num_threads(r['threads'])
 torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 print(json.dumps({'stage':'loading_detector','device':r['device']}),flush=True)
 with perf.stage('detector_load'):
  model=YOLO(str(paths['detector']))
 require(model.task=='detect','Unexpected model task')
 config=YAML.load(Path(ultralytics.__file__).parent/'cfg/trackers/botsort.yaml')
 config.update(r['tracker']);config.update(with_reid=True,model=str(paths['reid']),device=r['device'])
 print(json.dumps({'stage':'loading_reid','device':r['device']}),flush=True)
 with perf.stage('reid_load'):
  tracker=BOTSORT(IterableSimpleNamespace(**config))
 require(tracker.encoder is not None,'ReID must remain enabled')
 actual_providers=tracker.encoder.model.session.get_providers()
 require(('CUDAExecutionProvider' in actual_providers) if r['device'].startswith('cuda') else actual_providers==['CPUExecutionProvider'],'Actual ReID provider differs')
 cap=cv2.VideoCapture(str(paths['video']));require(cap.isOpened(),'Video decode unavailable')
 metadata={'width':int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),'height':int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
   'reported_frame_count':int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),'reported_fps':cap.get(cv2.CAP_PROP_FPS)}
 require(metadata['reported_frame_count']>=r['frame_limit'],'Source shorter than requested prefix')
 records=[];started=time.monotonic()
 print(json.dumps({'stage':'inference_start','frames':r['frame_limit'],'providers':actual_providers}),flush=True)
 try:
  batches=iter(decode_batches(cap,r['frame_limit'],size))
  while True:
   with perf.stage('decode'):
    batch=next(batches,None)
   if batch is None:break
   start,images=batch
   with perf.stage('evidence'):
    pixel_hashes=[__import__('hashlib').sha256(image.tobytes()).hexdigest() for image in images]
   # quantize=None is exactly the pinned API's replacement for half=False.
   # Preserve scalar input/shape on baseline; batching is an explicit experiment.
   with perf.stage('detector_wall'):
    with perf.cuda_sample('detector',torch,r['device'].startswith('cuda') and start%128<size):
     predictions=model.predict(images[0] if size==1 else images,device=r['device'],imgsz=r['imgsz'],conf=r['conf'],iou=r['iou'],quantize=None,verbose=False)
   require(len(predictions)==len(images),'Detector batch length differs')
   require(len(model.predictor.batch[1])==len(images),'Effective predictor batch differs')
   print(json.dumps({'stage':'batch_completed','start_frame':start,'frames':len(images),'effective_batch':len(model.predictor.batch[1])}),flush=True) if size==150 else None
   require(not model.predictor.model.fp16,'FP32 experiment unexpectedly enabled FP16')
   for offset,(image,prediction,pixel_sha) in enumerate(zip(images,predictions,pixel_hashes)):
    index=start+offset
    with perf.stage('detector_to_cpu'):
     raw=prediction.boxes.cpu().numpy()
    with perf.stage('tracker_reid'):
     tracks=tracker.update(raw,img=image)
    with perf.stage('evidence'):
     detections=[{'bbox':box.xyxy[0].tolist(),'confidence':float(box.conf[0]),'class_id':int(box.cls[0])} for box in raw]
     observations=[]
     for row in tracks:
      di=int(row[-1]);require(0<=di<len(detections),'Tracker detection link invalid')
      obs={'track_id':int(row[4]),'original_detection_index':di,'raw_detection':detections[di],
        'tracker_box':row[:4].tolist(),'observed':True,'emitted':True}
      require(int(row[6])==detections[di]['class_id'],'Tracker/raw class differs')
      observations.append(obs)
     features=[{'track_id':int(t.track_id),'shape':list(t.curr_feat.shape),'sha256':__import__('hashlib').sha256(t.curr_feat.tobytes()).hexdigest()}
       for t in tracker.tracked_stracks if t.curr_feat is not None]
     require(__import__('hashlib').sha256(image.tobytes()).hexdigest()==pixel_sha,'Inference mutated source pixels')
     records.append({'frame_index':index,'source_pixel_sha256':pixel_sha,
       'detections':detections,'emitted_measurements':observations,'reid_features':features})
    if (index+1)%128==0 or index+1==r['frame_limit']:
     progress=perf.snapshot('inference',completed=index+1,total=r['frame_limit'])
     print(json.dumps({'stage':'inference','frame':index,'of':r['frame_limit'],'fps_actual':round((index+1)/max(time.monotonic()-started,1e-9),2),'progress':progress}),flush=True)
 finally:cap.release()
 print(json.dumps({'stage':'inference_finished','frames':len(records),'wall_seconds':round(time.monotonic()-started,2),'fps_actual':round(len(records)/max(time.monotonic()-started,1e-9),2)}),flush=True)
 require(all(sha(paths[k])==v['sha256'] for k,v in r['artifacts'].items()),'Fresh input changed')
 environment={'python':platform.python_version(),'torch':torch.__version__,'ultralytics':ultralytics.__version__,
   'onnxruntime':onnxruntime.__version__,'opencv':cv2.__version__,'numpy':np.__version__,
   'device':r['device'],'batch_size':size,'precision':'FP32','reid_providers':actual_providers,'torch_threads':torch.get_num_threads()}
 if r['device'].startswith('cuda'):
  environment['cuda_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
  environment['cuda_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
 result={'schema_version':'fresh_inference_result_v1','status':'SUCCEEDED','scope':'BOUNDED_SOURCE_PREFIX_NOT_COUNTING_BENCHMARK',
  'frames':len(records),'metadata':metadata,'class_names':model.names,'source_sha256':r['artifacts']['video']['sha256'],'request_fingerprint':semantic_hash(r),
  'environment':environment,'effective_tracker_config':config,'records':records,'records_semantic_sha256':semantic_hash(records),
  'counting_executed':False,'physical_identity_accuracy_established':False,'vehicle_reid_suitability':'NOT_ESTABLISHED_PERSON_DOMAIN_CONTROL',
  'worker_process_isolation':True}
 output.mkdir(parents=True)
 with perf.stage('serialization'):
  write(output/'result.json.gz',result)
 write(output/'performance.json',perf.snapshot('finished',completed=len(records),total=r['frame_limit']))
 print(json.dumps({'status':'PASS','frames':len(records),'records_semantic_sha256':result['records_semantic_sha256'],'environment':environment}),flush=True)
 return result

def execute(request,output):
 from .execution_profile import resolve_profile
 profile=resolve_profile(request)
 if profile is None:return execute_baseline(request,output)
 from .model_worker import execute as accelerated
 return accelerated(request,output,profile=profile)

if __name__=='__main__':
 try:execute(read(sys.argv[1]),sys.argv[2])
 except Exception as error:
  print(json.dumps({'status':'FAILED','reason':str(error)}),file=sys.stderr);sys.exit(1)
