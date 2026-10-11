import json, hashlib, pathlib, time, platform, importlib.metadata, urllib.request
import cv2, numpy as np, torch, onnx, onnxruntime as ort
from ultralytics.trackers.utils.reid import ReID
from ultralytics.trackers.bot_sort import BOTSORT
from ultralytics.engine.results import Boxes
from ultralytics.utils import YAML, IterableSimpleNamespace

ROOT=pathlib.Path('/workspace/traffic-vehicle-counter-IDM-LOC')
MODEL=pathlib.Path('/tmp/phase4-verified-assets/yolo26n-reid.onnx')
IMG=ROOT/'docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/samples/frame_000005140_raw.png'
CACHE=pathlib.Path('/tmp/kaggle-phase2-retained-cache-dataset-20261011/frame_detections.jsonl')
torch.set_num_threads(4)
for i,line in enumerate(CACHE.open()):
    if i==5140:
        row=json.loads(line);break
image=cv2.imread(str(IMG));assert image.shape==(720,1280,3)
boxes=Boxes(np.array([d['bbox_xyxy_pixels']+[d['confidence'],d['class_id']] for d in row['detections']],dtype=np.float32),orig_shape=image.shape[:2])
dets=np.column_stack([boxes.xywh,np.arange(len(boxes))]).astype(np.float32)
t0=time.perf_counter();encoder=ReID(str(MODEL),device='cpu');load_s=time.perf_counter()-t0
t0=time.perf_counter();features=encoder(image,dets);infer_s=time.perf_counter()-t0
assert len(features)==len(boxes)
assert all(f.shape==(512,) and np.isfinite(f).all() and np.linalg.norm(f)>0 for f in features)
again=encoder(image,dets);repeat_delta=max(float(np.max(np.abs(a-b)))for a,b in zip(features,again))
onnxmodel=onnx.load(str(MODEL));onnx.checker.check_model(onnxmodel)
settings=YAML.load('/workspace/.venvs/traffic-detection-validation/lib/python3.12/site-packages/ultralytics/cfg/trackers/botsort.yaml')
settings.update(with_reid=True,gmc_method='none',model=str(MODEL),device='cpu')
tracker=BOTSORT(IterableSimpleNamespace(**settings))
out=tracker.update(boxes,img=image)
assert tracker.encoder is not None and tracker.encoder.model.session.get_providers()==['CPUExecutionProvider']
assert len(tracker.tracked_stracks)==len(boxes)
assert all(t.curr_feat is not None and t.curr_feat.shape==(512,) and np.isclose(np.linalg.norm(t.curr_feat),1.,rtol=1e-5)for t in tracker.tracked_stracks)
source_files=['ultralytics/trackers/bot_sort.py','ultralytics/trackers/byte_tracker.py','ultralytics/trackers/utils/reid.py','ultralytics/trackers/utils/matching.py','ultralytics/nn/backends/onnx.py','ultralytics/nn/autobackend.py','ultralytics/utils/plotting.py']
source=[]
base=pathlib.Path('/workspace/.venvs/traffic-detection-validation/lib/python3.12/site-packages')
for rel in source_files:
    url='https://raw.githubusercontent.com/ultralytics/ultralytics/v8.4.175/'+rel
    with urllib.request.urlopen(url,timeout=30) as response:official=response.read()
    actual=(base/rel).read_bytes();assert official==actual
    source.append({'path':rel,'official_url':url,'official_sha256':hashlib.sha256(official).hexdigest(),'installed_sha256':hashlib.sha256(actual).hexdigest(),'match':True})
meta=encoder.model.session.get_modelmeta().custom_metadata_map
result={'scope':'Tiny actual CPU appearance-encoder and direct BoT-SORT integration validation on six cached detections from retained native TOR3-PAGI frame 5140. No YOLO detector weights loaded or detector inference; no full-video identity-quality claim.',
 'model':{'path':str(MODEL),'sha256':hashlib.sha256(MODEL.read_bytes()).hexdigest(),'size_bytes':MODEL.stat().st_size,'metadata':{k:v for k,v in meta.items() if k!='names'},'opset':[(o.domain,o.version)for o in onnxmodel.opset_import],'ir_version':onnxmodel.ir_version},
 'environment':{'python':platform.python_version(),'torch':torch.__version__,'ultralytics':importlib.metadata.version('ultralytics'),'onnx':onnx.__version__,'onnxruntime':ort.__version__,'available_providers':ort.get_available_providers(),'actual_session_providers':encoder.model.session.get_providers(),'device':str(encoder.device)},
 'inputs':{'frame_index':5140,'raw_png_sha256':hashlib.sha256(IMG.read_bytes()).hexdigest(),'cache_sha256':hashlib.sha256(CACHE.read_bytes()).hexdigest(),'detection_count':len(boxes),'encoder_crop_size':list(encoder.imgsz),'batch_size':encoder.batch_size,'onnx_inputs':[{'name':i.name,'shape':i.shape,'type':i.type}for i in encoder.model.session.get_inputs()]},
 'outputs':{'onnx_outputs':[{'name':i.name,'shape':i.shape,'type':i.type}for i in encoder.model.session.get_outputs()],'features':[{'shape':list(f.shape),'dtype':str(f.dtype),'finite':bool(np.isfinite(f).all()),'l2_norm':float(np.linalg.norm(f)),'sha256':hashlib.sha256(f.tobytes()).hexdigest()}for f in features],'repeat_max_abs_delta':repeat_delta,'track_count':len(tracker.tracked_stracks),'tracker_output_shape':list(out.shape),'all_tracks_have_normalized_current_features':True},
 'measurements':{'encoder_load_seconds':load_s,'first_batch_encode_seconds':infer_s,'not_a_benchmark':True},'source_files':source,'status':'PASS','vehicle_identity_suitability':'UNESTABLISHED; model metadata names MSMT17-v1 training, dedicated person ReID dataset; smoke verifies integration only'}
pathlib.Path('/tmp/phase4_reid_candidate_smoke.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['scope','environment','inputs','outputs','measurements','status']},indent=2))
