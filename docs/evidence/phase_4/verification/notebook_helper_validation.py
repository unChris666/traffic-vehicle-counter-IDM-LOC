import ast, json, pathlib, hashlib, platform, importlib.metadata, copy, time
import subprocess, types
ROOT=pathlib.Path('/workspace/traffic-vehicle-counter-IDM-LOC')
NB=ROOT/'notebooks/04_reid_comparison.ipynb'
TARGET=pathlib.Path('/tmp/phase4-notebook-helper-validation')
TARGET.mkdir(exist_ok=True)
checks=[]
def check(name,fn):
    t=time.perf_counter()
    try:
        details=fn(); checks.append({'name':name,'status':'PASS','details':details,'wall_seconds':time.perf_counter()-t})
        print(name,'PASS',flush=True)
    except Exception as exc:
        checks.append({'name':name,'status':'FAIL','exception':type(exc).__name__,'message':str(exc),'wall_seconds':time.perf_counter()-t})
        print(name,'FAIL',str(exc),flush=True)
        save(); raise
def save():
    result={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL',
            'scope':'Software helper and tiny actual CPU ReID observer validation; no detector rerun, no full-video Phase4 result or identity-quality claim. Actual Kaggle CUDA/full sequence must execute separately.',
            'python':platform.python_version(),'notebook_sha256':hashlib.sha256(NB.read_bytes()).hexdigest(),
            'checks':checks,'passed':sum(c['status']=='PASS' for c in checks),'failed':sum(c['status']=='FAIL' for c in checks)}
    (TARGET/'helper_validation.json').write_text(json.dumps(result,indent=2)+'\n')
nb=types.SimpleNamespace(cells=[types.SimpleNamespace(**c)for c in json.loads(NB.read_text())['cells']])
def notebook_schema():
    subprocess.run(['/workspace/.venvs/traffic-inspection/bin/python','-c',
                    'import nbformat; n=nbformat.read('+repr(str(NB))+',as_version=4); nbformat.validate(n)'],check=True)
    assert all(c.cell_type!='code' or (c.execution_count is None and not c.outputs) for c in nb.cells)
    return {'nbformat_validation':'passed','all_cells_output_free':True}
check('notebook_schema_and_output_free',notebook_schema)
check('all_code_cells_compile',lambda:[compile(c.source,f'cell{i}','exec') and i for i,c in enumerate(nb.cells) if c.cell_type=='code'])
ns={}
config=nb.cells[1].source.replace("Path('/kaggle/working/reid_comparison')",f"Path({str(TARGET/'runs')!r})")
exec(config,ns)
def only_definitions(code):
    tree=ast.parse(code)
    nodes=[n for n in tree.body if not isinstance(n,(ast.With,ast.AsyncWith))]
    return compile(ast.Module(body=nodes,type_ignores=[]),'helpers','exec')
exec(only_definitions(nb.cells[3].source),ns)
exec(only_definitions(nb.cells[4].source),ns)
exec(nb.cells[7].source,ns)
exec(nb.cells[8].source,ns)
exec(nb.cells[10].source,ns)
exec(only_definitions(nb.cells[12].source),ns)
ns['torch'].set_num_threads(4)
CACHE=pathlib.Path('/tmp/kaggle-phase2-retained-cache-dataset-20261011/frame_detections.jsonl')
rows=[json.loads(line) for line in CACHE.open()]
report=json.loads((CACHE.parent/'detection_report.json').read_text())
ns['CLASS_NAMES']=report['model']['class_names'];ns['FPS']=float(report['input']['opencv_metadata']['fps'])
ns['WIDTH']=1280;ns['HEIGHT']=720
np,cv2=ns['np'],ns['cv2']
settings=ns['YAML'].load('/workspace/.venvs/traffic-detection-validation/lib/python3.12/site-packages/ultralytics/cfg/trackers/botsort.yaml')
settings.update(gmc_method='none',with_reid=False)
ns['TRACKER_CONFIG']=settings
MODEL='/tmp/phase4-verified-assets/yolo26n-reid.onnx'
IMG=ROOT/'docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/samples/frame_000005140_raw.png'
image=cv2.imread(str(IMG));realrow=rows[5140]
boxes=ns['detection_boxes'](realrow)

def cachecheck():
    assert ns['sha256_file'](CACHE)==ns['EXPECTED_CACHE_SHA256']
    for i,row in enumerate(rows):ns['validate_detection_row'](row,i,ns['EXPECTED_VIDEO_SHA256'],1280,720,ns['CLASS_NAMES'])
    assert len(rows)==10282
    return {'rows':len(rows),'raw_observations':sum(len(r['detections'])for r in rows),'source_cache_sha256':ns['sha256_file'](CACHE)}
check('same_actual_cache_identity_and_all_rows',cachecheck)

def offobserver():
    a=ns['BOTSORT'](ns['IterableSimpleNamespace'](**settings))
    b=ns['AppearanceEvidenceBOTSORT'](ns['IterableSimpleNamespace'](**settings))
    for row in rows[:200]:
        av=a.update(ns['detection_boxes'](row),img=None);bv=b.update(ns['detection_boxes'](row),img=None)
        assert np.array_equal(av,bv); assert ns['pool_signature'](a)==ns['pool_signature'](b)
    assert not b.encoder; assert b.cost_totals['calls']>0; assert b.cost_totals['appearance_changed_cost_pairs']==0
    return {'actual_cached_prefix_rows':200,'output_and_lifecycle_exact_equal':True,'cost_calls':b.cost_totals['calls']}
check('off_cost_lifecycle_observer_preserves_parent_200_rows',offobserver)

onsettings=dict(settings,with_reid=True,model=MODEL,device='cpu')
def onobserver():
    a=ns['BOTSORT'](ns['IterableSimpleNamespace'](**onsettings))
    b=ns['AppearanceEvidenceBOTSORT'](ns['IterableSimpleNamespace'](**onsettings))
    for _ in range(3):
        av=a.update(boxes,img=image);bv=b.update(boxes,img=image)
        assert np.array_equal(av,bv); assert ns['pool_signature'](a)==ns['pool_signature'](b)
    assert b.encoder_evidence.total_features==18
    assert b.cost_totals['nonempty_feature_association_calls']>0
    assert all(c['parent_formula_exact_match']for c in b.cost_calls)
    return {'actual_native_frame':5140,'software_repeated_updates':3,'finite_nonzero_features':b.encoder_evidence.total_features,
            'embedding_dimension':512,'instrumented_outputs_lifecycle_exact_equal':True,'association_diagnostics':dict(b.cost_totals)}
check('actual_cpu_encoder_and_cost_observer_preserve_parent',onobserver)

def profilefixture():
    original=ns['ort'].InferenceSession
    with ns['profiled_ort_session_creation'](TARGET/'cpu_actual_encoder_profile'):
        tracker=ns['AppearanceEvidenceBOTSORT'](ns['IterableSimpleNamespace'](**onsettings))
    assert ns['ort'].InferenceSession is original
    tracker.update(boxes,img=image)
    session=tracker.encoder_evidence.encoder.model.session
    p=pathlib.Path(session.end_profiling());events=json.loads(p.read_text())
    nodeevents=[e for e in events if e.get('cat')=='Node' and e.get('args',{}).get('provider')=='CPUExecutionProvider']
    assert nodeevents
    return {'actual_backend_positional_session_options_supported':True,'actual_cpu_encoder_profile':str(p),
            'cpu_kernel_events':len(nodeevents),'gpu_execution_claimed':False,'factory_restored':True}
check('actual_ort_profile_factory_positional_options_and_restore',profilefixture)

def rejection(kind):
    class Fake:
        def __call__(self,img,dets):
            f=np.zeros(512,dtype=np.float32) if kind=='zero' else np.full(512,np.nan,dtype=np.float32)
            return [f for _ in dets]
    observer=ns['EncoderEvidence'](Fake())
    try:observer(image,np.zeros((1,5)))
    except ValueError:return {'invalid_feature_rejected':kind}
    raise AssertionError('Invalid feature accepted')
check('zero_norm_features_rejected',lambda:rejection('zero'))
check('nonfinite_features_rejected',lambda:rejection('nan'))

def wrongdim():
    class Fake:
        def __call__(self,img,dets):return [np.ones(128,dtype=np.float32)for _ in dets]
    try:ns['EncoderEvidence'](Fake())(image,np.zeros((1,5)))
    except ValueError:return {'wrong_dimension_rejected':128}
    raise AssertionError('Wrong dimension accepted')
check('wrong_embedding_dimension_rejected',wrongdim)

def fresh():
    trackers=[ns['AppearanceEvidenceBOTSORT'](ns['IterableSimpleNamespace'](**settings))for _ in range(2)]
    outs=[t.update(ns['detection_boxes'](rows[0])) for t in trackers]
    assert np.array_equal(outs[0],outs[1]);assert int(outs[0][:,4].min())==1
    return {'independent_first_frame_ids_equal':True,'minimum_first_id':1,'pinned_id_iterator_scope':'per tracker'}
check('independent_fresh_variant_ids',fresh)

def empty():
    t=ns['AppearanceEvidenceBOTSORT'](ns['IterableSimpleNamespace'](**onsettings))
    row=copy.deepcopy(rows[0]);row['detections']=[]
    o=t.update(ns['detection_boxes'](row),img=image)
    assert np.asarray(o).size==0 and t.frame_id==1 and t.encoder_evidence.total_calls==0
    return {'empty_update_ages_tracker':True,'encoder_not_called':True}
check('empty_detection_update_no_fake_embedding',empty)

def pairedsheet():
    off=[(5140,image),(5141,image)];on=off
    path=TARGET/'paired_fixture.png'
    ns['make_paired_contact_sheet'](off,on,'actual-frame software fixture',path,crop=(0,250,750,720))
    assert cv2.imread(str(path)) is not None
    try:ns['make_paired_contact_sheet'](off,[(5142,image),(5143,image)],'bad',TARGET/'bad.png')
    except ValueError:pass
    else:raise AssertionError('Mismatched paired indices accepted')
    return {'paired_actual_pixel_crop_written':True,'wrong_pairing_rejected':True}
check('paired_temporal_display_and_index_guard',pairedsheet)

save()
print(json.dumps({'checks_passed':len(checks),'report':str(TARGET/'helper_validation.json')},indent=2))
