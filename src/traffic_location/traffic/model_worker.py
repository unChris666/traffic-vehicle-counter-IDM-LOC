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


def execute(request,output,*,profile=None):
 import cv2,numpy as np,torch,ultralytics,onnxruntime
 from ultralytics import YOLO
 from ultralytics.trackers.bot_sort import BOTSORT
 from ultralytics.utils import YAML,IterableSimpleNamespace
 r=request;require(r['schema_version']=='fresh_inference_request_v1','Unsupported fresh request')
 output=Path(output);require(not output.exists(),'Fresh output must not overwrite existing artifacts')
 experiment=profile if profile is not None else r['experiment'];size=experiment.get('batch_size',1);window=experiment.get('reid_window',1)
 require(type(size) is int and 1<=size<=16,'Invalid detector batch')
 require(type(window) is int and 1<=window<=16,'Invalid ReID window')
 precision=experiment.get('precision','FP32');require(precision in ('FP32','FP16'),'Invalid detector precision')
 require(r['half']==(precision=='FP16'),'Declared precision differs')
 perf=Progress(output.parent/'progress.json')
 worker_started=time.monotonic()
 root=Path(r['input_root']);paths={k:artifact(v,root) for k,v in r['artifacts'].items()}
 require(set(paths)=={'video','detector','reid'},'Video/detector/ReID refs required')
 require(ultralytics.__version__==r['ultralytics_version'],'Pinned Ultralytics differs')
 require(r['device'] in {'cpu','cuda:0'},'Explicit supported device required')
 if r['device'].startswith('cuda'):
  require(torch.cuda.is_available(),'Requested GPU unavailable; no CPU fallback')
  require('CUDAExecutionProvider' in onnxruntime.get_available_providers(),'CUDA ReID provider unavailable')
 require(r['start_frame']==0 and type(r['frame_limit']) is int and r['frame_limit']>0,'Bounded prefix only; no skipped tracking context')
 require(r['preprocessing']=='RAW','Only RAW source supported')
 if r['device'].startswith('cuda'):torch.cuda.reset_peak_memory_stats()
 random.seed(r['seed']);np.random.seed(r['seed']);torch.manual_seed(r['seed']);torch.set_num_threads(r['threads'])
 torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 print(json.dumps({'stage':'loading_detector','device':r['device']}),flush=True)
 with perf.stage('detector_load'):
  model=YOLO(str(paths['detector']),task='detect')
 require(model.task=='detect','Unexpected model task')
 config=YAML.load(Path(ultralytics.__file__).parent/'cfg/trackers/botsort.yaml')
 config.update(r['tracker']);config.update(with_reid=True,model=str(paths['reid']),device=r['device'])
 print(json.dumps({'stage':'loading_reid','device':r['device']}),flush=True)
 with perf.stage('reid_load'):
  tracker=BOTSORT(IterableSimpleNamespace(**config))
 require(tracker.encoder is not None,'ReID must remain enabled')
 actual_providers=tracker.encoder.model.session.get_providers()
 require(('CUDAExecutionProvider' in actual_providers) if r['device'].startswith('cuda') else actual_providers==['CPUExecutionProvider'],'Actual ReID provider differs')
 from .adapters.reid_encoder import EncoderProfile
 encoder=EncoderProfile(tracker.encoder,perf,experiment.get('reid_transport','original'),experiment.get('crop_batch',32))
 tracker.encoder=encoder
 cap=cv2.VideoCapture(str(paths['video']));require(cap.isOpened(),'Video decode unavailable')
 metadata={'width':int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),'height':int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
   'reported_frame_count':int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),'reported_fps':cap.get(cv2.CAP_PROP_FPS)}
 require(metadata['reported_frame_count']>=r['frame_limit'],'Source shorter than requested prefix')
 warmup_started=time.monotonic()
 blank=np.zeros((metadata['height'],metadata['width'],3),dtype=np.uint8)
 model.predict(blank if size==1 else [blank]*size,device=r['device'],imgsz=experiment.get('input_shape',r['imgsz']),conf=r['conf'],iou=r['iou'],quantize=16 if precision=='FP16' else None,verbose=False)
 encoder.encode_group(blank,np.array([[100.,100.,80.,80.,0.]],dtype=np.float32))
 if r['device'].startswith('cuda'):torch.cuda.synchronize()
 warmup_seconds=time.monotonic()-warmup_started
 startup_stages=dict(perf.seconds);perf.seconds.clear();encoder.encoder_seconds=0.;encoder.calls=0
 startup_seconds=time.monotonic()-worker_started
 records=[];first_preprocessed_sha256=None;first_input_shape=None;started=time.monotonic()
 print(json.dumps({'stage':'inference_start','frames':r['frame_limit'],'providers':actual_providers}),flush=True)
 try:
  batches=iter(decode_batches(cap,r['frame_limit'],max(size,window)))
  while True:
   with perf.stage('decode'):
    batch=next(batches,None)
   if batch is None:break
   start,images=batch
   with perf.stage('evidence'):
    pixel_hashes=[__import__('hashlib').sha256(image.tobytes()).hexdigest() for image in images]
   predictions=[]
   for off in range(0,len(images),size):
    selected=images[off:off+size]
    engine=experiment.get('backend','pytorch')=='tensorrt'
    predict_images=selected
    if engine and len(selected)<size:predict_images=selected+[selected[-1]]*(size-len(selected))
    with perf.stage('detector_wall'):
     result=model.predict(predict_images[0] if size==1 else predict_images,device=r['device'],
         imgsz=experiment.get('input_shape',r['imgsz']),conf=r['conf'],iou=r['iou'],
         quantize=16 if precision=='FP16' else None,verbose=False)
    require(bool(model.predictor.model.fp16)==(precision=='FP16'),'Effective precision differs')
    predictions.extend(result[:len(selected)])
   require(len(predictions)==len(images),'Detector frame coverage differs')
   if first_preprocessed_sha256 is None:
    transformed=model.predictor.pre_transform([images[0]])[0]
    first_preprocessed_sha256=__import__('hashlib').sha256(transformed.tobytes()).hexdigest();first_input_shape=list(transformed.shape)
   with perf.stage('detector_to_cpu'):
    raw_frames=[prediction.boxes.cpu().numpy() for prediction in predictions]
   prefetched=encoder.prepare(tracker,list(zip(images,raw_frames))) if window>1 else None
   for offset,(image,raw,pixel_sha) in enumerate(zip(images,raw_frames,pixel_hashes)):
    index=start+offset
    if prefetched is not None:encoder.queue=prefetched[offset]
    elapsed_encoder=encoder.encoder_seconds;t0=time.monotonic()
    with perf.stage('tracker_reid'):
     tracks=tracker.update(raw,img=image)
    perf.seconds['association_and_track_bookkeeping']+=max(0,time.monotonic()-t0-(encoder.encoder_seconds-elapsed_encoder))
    if prefetched is not None:require(not encoder.queue,'Unused prefetched embeddings')
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
   'device':r['device'],'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'batch_size':size,'precision':precision,'experiment':experiment,'input_shape':list(model.predictor.imgsz),'encoder_input':tracker.encoder.model.session.get_inputs()[0].shape,'first_preprocessed_sha256':first_preprocessed_sha256,'first_input_shape':first_input_shape,'reid_providers':actual_providers,'torch_threads':torch.get_num_threads()}
 if r['device'].startswith('cuda'):
  environment['cuda_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
  environment['cuda_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
 from ..runtime_resources import snapshot as resource_snapshot
 environment['resource_observation']=resource_snapshot(output.parent)
 result={'schema_version':'fresh_inference_result_v1','status':'SUCCEEDED','scope':'BOUNDED_SOURCE_PREFIX_NOT_COUNTING_BENCHMARK',
  'frames':len(records),'metadata':metadata,'class_names':model.names,'source_sha256':r['artifacts']['video']['sha256'],'request_fingerprint':semantic_hash(r),
  'environment':environment,'effective_tracker_config':config,'records':records,'records_semantic_sha256':semantic_hash(records),
  'counting_executed':False,'physical_identity_accuracy_established':False,'vehicle_reid_suitability':'NOT_ESTABLISHED_PERSON_DOMAIN_CONTROL',
  'worker_process_isolation':True}
 output.mkdir(parents=True)
 with perf.stage('serialization'):
  write(output/'result.json.gz',result)
 performance=perf.snapshot('finished',completed=len(records),total=r['frame_limit'])
 performance.update(warmup_seconds=warmup_seconds,startup_stages=startup_stages,startup_seconds=startup_seconds,processing_seconds=time.monotonic()-started,worker_total_seconds=time.monotonic()-worker_started,encoder_calls=encoder.calls)
 write(output/'performance.json',performance)
 print(json.dumps({'status':'PASS','frames':len(records),'records_semantic_sha256':result['records_semantic_sha256'],'environment':environment}),flush=True)
 return result

if __name__=='__main__':
 try:execute(read(sys.argv[1]),sys.argv[2])
 except Exception as error:
  print(json.dumps({'status':'FAILED','reason':str(error)}),file=sys.stderr);sys.exit(1)
