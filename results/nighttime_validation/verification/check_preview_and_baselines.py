"""Read-only pixel parity + historical retention verification; no inference."""
import json,sys,pathlib,cv2,numpy as np,hashlib
root=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'notebooks'));import nighttime_review_filter as filters
r=root/'results/nighttime_validation';p=r/'browser_validation';cfg=json.loads((p/'test_export_not_selected_for_inference.json').read_text());filters.validate_config(cfg)
raw=cv2.imread(str(p/'raw_native.png'));browser=cv2.imread(str(p/'filtered_native.png'));selected=next(v for v in cfg['videos'] if v['filename']=='F1YV-WEEKDAY-MALAM.mp4');backend,proof=filters.prepare_inference_frame(raw,cfg,selected['source_sha256']);different=int(np.any(backend!=browser,axis=2).sum());assert different==0,(different,int(np.abs(backend.astype(int)-browser.astype(int)).max()))
source=cv2.imread(str(r/'local_inspection/video_000/frame_000000.png'));delta=np.abs(source.astype(int)-raw.astype(int));d={'status':'PASS','actual_browser_canvas_to_python_preprocessing_different_pixels':different,'native_dimensions_preserved':list(raw.shape),'same_settings_config_consumed_by_backend':True,'browser_vs_opencv_raw_decoder_max_channel_difference':int(delta.max()),'browser_vs_opencv_raw_decoder_different_pixels':int(np.any(delta,axis=2).sum()),'decoded_source_equivalence_limit':'Browser presentation timestamps/color conversion may differ from OpenCV. Preprocessing parity is checked on identical decoded pixels; no detector run claimed.','inference_executed':False,'test_settings_not_selected_for_production':True};(p/'preview_backend_parity.json').write_text(json.dumps(d,indent=2)+'\n');print(d)
cache={}
def sha(p):
 p=p.resolve()
 if p not in cache:
  with p.open('rb') as f:cache[p]=hashlib.file_digest(f,'sha256').hexdigest()
 return cache[p]
reports={}
for name in ['b_v7','b_v8']:
 folder=root/'results'/name;m=json.loads((folder/'retention_manifest.json').read_text())
 for e in m['files']:assert sha(folder/e['path'])==e['sha256'],e['path']
 for e in m['code_and_document_bindings']:assert sha(root/e['path'])==e['sha256'],e['path']
 reports[name]={'manifest_sha256':sha(folder/'retention_manifest.json'),'retained_files_unchanged':len(m['files']),'live_source_bindings_unchanged':len(m['code_and_document_bindings'])}
(r/'verification/baseline_retention.json').write_text(json.dumps({'status':'PASS','baselines':reports,'area_coverage_and_ppac_modified':False},indent=2)+'\n');print(reports)
