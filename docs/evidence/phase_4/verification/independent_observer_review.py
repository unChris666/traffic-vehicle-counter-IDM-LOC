import json,pathlib,hashlib,math,time
from contextlib import contextmanager
from collections import Counter
import numpy as np,cv2,torch,onnxruntime as ort
from ultralytics.trackers.bot_sort import BOTSORT
from ultralytics.trackers.basetrack import TrackState
from ultralytics.trackers.utils import matching
from ultralytics.engine.results import Boxes
from ultralytics.utils import YAML,IterableSimpleNamespace

p=pathlib.Path('/workspace/traffic-vehicle-counter-IDM-LOC/notebooks/04_reid_comparison.ipynb')
n=json.loads(p.read_text());source_sha=hashlib.sha256(p.read_bytes()).hexdigest()
BURSTS=[(0,29)];FPS=29.81501660256117
def require(c,m):
    if not c:raise ValueError(m)
exec(compile(''.join(n['cells'][7]['source']),str(p)+':cell7','exec'))
exec(compile(''.join(n['cells'][8]['source']),str(p)+':cell8','exec'))
torch.set_num_threads(4)
settings=YAML.load('/workspace/.venvs/traffic-detection-validation/lib/python3.12/site-packages/ultralytics/cfg/trackers/botsort.yaml')
settings.update(with_reid=True,gmc_method='none',model='/tmp/phase4-verified-assets/yolo26n-reid.onnx',device='cpu')
cache=pathlib.Path('/tmp/kaggle-phase2-retained-cache-dataset-20261011/frame_detections.jsonl')
for i,line in enumerate(cache.open()):
    if i==5140:row=json.loads(line);break
imgp=pathlib.Path('/workspace/traffic-vehicle-counter-IDM-LOC/docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/samples/frame_000005140_raw.png')
image=cv2.imread(str(imgp))
original_factory=ort.InferenceSession
reference=BOTSORT(IterableSimpleNamespace(**settings))
with profiled_ort_session_creation(pathlib.Path('/tmp/phase4-independent-review-profile')):
    observed=AppearanceEvidenceBOTSORT(IterableSimpleNamespace(**settings))
assert ort.InferenceSession is original_factory
signatures=[]
for repeat in range(3):
    a=reference.update(detection_boxes(row),img=image)
    b=observed.update(detection_boxes(row),img=image)
    assert np.array_equal(a,b)
    assert pool_signature(reference)==pool_signature(observed)
    assert all(np.array_equal(x.curr_feat,y.curr_feat) and np.array_equal(x.smooth_feat,y.smooth_feat)for x,y in zip(reference.tracked_stracks,observed.tracked_stracks))
    signatures.append({'synthetic_repeat_index':repeat,'output_shape':list(b.shape),'output_exact_equal':True,'pool_lifecycle_exact_equal':True,'current_and_smoothed_features_exact_equal':True})
profilep=pathlib.Path(observed.encoder_evidence.encoder.model.session.end_profiling());profile=json.loads(profilep.read_text())
counts=Counter(e.get('args',{}).get('provider')for e in profile if e.get('cat')=='Node'and e.get('args',{}).get('provider'))
assert counts['CPUExecutionProvider']>0
assert observed.cost_totals['nonempty_feature_association_calls']>0
assert observed.encoder_evidence.total_features==18
report={'status':'PASS','scope':'Independent direct actual CPU encoder/observer equivalence and profilingfactory validation only. Same retained frame5140 pixels and six cached detections replayed three times as an explicit software fixture, not three chronological source frames or identity-quality evidence. No detector inference.',
 'reviewed_source_sha256':source_sha,'profile_factory_positional_options_support':True,'profile_factory_restored':True,'encoder_feature_total':observed.encoder_evidence.total_features,'output_equivalence_fixture':signatures,'cost_observer_reference_exact_match':all(c['parent_formula_exact_match']for c in observed.cost_calls),'association_cost_diagnostics':dict(observed.cost_totals),'profile':{'path':str(profilep),'sha256':hashlib.sha256(profilep.read_bytes()).hexdigest(),'node_provider_counts':dict(counts),'cuda_execution_tested':False},'notes':['Initial profiling factory positional sess_options bug was corrected before this validation.','Actual Kaggle CUDA execution must still be proven by actual encoder profile; CPU smoke cannot establish it.','Model officialperson-domain training metadata and actual512D output are supported; vehicle transfer remains unknown.']}
pathlib.Path('/tmp/phase4_independent_observer_review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
