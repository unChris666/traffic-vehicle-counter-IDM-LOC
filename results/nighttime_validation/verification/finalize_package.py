"""Verify new nighttime package without changing any historical baseline."""
from pathlib import Path
import json,gzip,hashlib,re,subprocess
import nbformat
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'results/nighttime_validation'
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(path.read_text())
def main():
 gate=read(R/'readiness.json');assert gate['overall_status']=='PARTIAL'
 kaggle=read(R/'kaggle_execution/nighttime_input_inspection/inventory.json')
 local=read(R/'local_inspection/inventory.json')
 assert kaggle['environment']['execution_context']=='actual_kaggle_mount'
 assert kaggle['environment']['kaggle_input_exists']
 assert kaggle['environment']['actual_dataset_directory']=='/kaggle/input/datasets/chrisbiran/video-traffic-malam'
 assert kaggle['video_count']==10 and sum(v['frame_count_decoded'] for v in kaggle['inventory'])==89199
 assert not kaggle['unreadable_or_mismatched'] and not kaggle['unsupported_files']
 local_by_sha={v['source_sha256']:v for v in local['inventory']}
 for row in kaggle['inventory']:
  original=Path('/tmp/official-night-dataset')/row['filename'];assert sha(original)==row['source_sha256']
  assert row['source_unchanged'] and row['decode_status']=='SEQUENTIAL_DECODE_TO_EOF'
  assert row['frame_count_decoded']==local_by_sha[row['source_sha256']]['frame_count_decoded']
  assert [(s['frame_index'],s['decoded_bgr_sha256']) for s in row['samples']]==[(s['frame_index'],s['decoded_bgr_sha256']) for s in local_by_sha[row['source_sha256']]['samples']]
  for sample in row['samples']:
   assert sha(R/'kaggle_execution/nighttime_input_inspection'/row['evidence_directory']/sample['native_image'])==sample['image_sha256']
 for relative,expected in read(R/'verification/submission_sources.json').items():assert sha(ROOT/relative)==expected
 for name in ['nighttime_input_inspection.py','nighttime_review_filter.py']:
  assert sha(ROOT/'notebooks'/name)==sha(R/'kaggle_execution/nighttime_preflight_helpers'/name)
 current=nbformat.read(ROOT/'notebooks/09f_nighttime_validation.ipynb',as_version=4);nbformat.validate(current)
 retained=nbformat.read(R/'kaggle_retained_source/b-v8-nighttime-input-inspection.ipynb',as_version=4)
 assert [c['source'] for c in current.cells]==[c['source'] for c in retained.cells]
 for c in current.cells:
  if c.cell_type=='code':compile(c.source,'09f','exec');assert not c.outputs
 assert read(R/'kaggle_retained_source/kernel-metadata.json')['dataset_sources']==['chrisbiran/video-traffic-malam']
 browser=read(R/'browser_validation/browser_test.json');assert browser['status']=='PASS' and len(browser['all_eight_condition_profile_edits_verified'])==8
 parity=read(R/'browser_validation/preview_backend_parity.json');assert parity['status']=='PASS' and parity['actual_browser_canvas_to_python_preprocessing_different_pixels']==0
 testlog=(R/'software_tests.log').read_text();assert 'Ran 16 tests' in testlog and testlog.rstrip().endswith('OK')
 for version in ['b_v7','b_v8']:
  base=ROOT/'results'/version;manifest=read(base/'retention_manifest.json')
  for entry in manifest['files']:assert sha(base/entry['path'])==entry['sha256'],entry['path']
  for entry in manifest['code_and_document_bindings']:assert sha(ROOT/entry['path'])==entry['sha256'],entry['path']
 linked=0
 for doc in [ROOT/'docs/NIGHTTIME_VALIDATION_REVIEW.md',R/'README.md',R/'inspection_report.md']:
  for target in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
   if '://' in target or target.startswith('#'):continue
   path=(doc.parent/target.split('#')[0]).resolve()
   if path==R/'retention_manifest.json':continue  # generated after all checks below
   assert path.exists(),f'Broken link:{doc}:{target}'
   linked+=1
 diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True);assert diff.returncode==0,diff.stdout
 assert not list(R.rglob('*.mp4')) and not list(R.rglob('*.pt')) and not list(R.rglob('*.onnx'))
 receipt={'schema_version':'nighttime_delivery_verification_v1','status':'PASS_WITH_EXPLICIT_E2E_BLOCKERS','dataset_mounted_and_decoded_in_kaggle':True,'video_count':10,'source_frames':89199,'source_file_and_sample_pixels_match_local':True,'source_notebook_and_embedded_helpers_match_retained_execution':True,'software_tests':16,'browser_real_files':10,'condition_profiles_tested':8,'transform_parity_same_decoded_pixels':True,'historical_b_v7_b_v8_retention_intact':True,'relative_document_links_checked':linked,'git_diff_check':'PASS','area_coverage_or_ppac_modified':False,'actual_model_counting_smoke_executed':False,'night_reliability_established':False}
 (R/'verification/final_verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
 sources=[ROOT/'results/review-filter.html',ROOT/'results/nighttime_review_filter.js',ROOT/'docs/NIGHTTIME_VALIDATION_REVIEW.md',ROOT/'notebooks/09f_nighttime_validation.ipynb',ROOT/'notebooks/nighttime_input_inspection.py',ROOT/'notebooks/nighttime_review_filter.py',ROOT/'notebooks/nighttime_validation_tests.py']
 bindings=[]
 for source in sources:
  rel=source.relative_to(ROOT);target=R/'delivery_source_snapshot'/str(rel);target=target.with_name(target.name+'.gz');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(gzip.compress(source.read_bytes(),mtime=0));bindings.append({'path':str(rel),'sha256':sha(source),'retained_path':str(target.relative_to(R))})
 files=[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(R.rglob('*')) if p.is_file() and p!=R/'retention_manifest.json' and '__pycache__' not in p.parts and p.suffix!='.pyc']
 manifest={'schema_version':'nighttime_input_review_filter_delivery_v1','self_excluded':True,'overall_gate':'PARTIAL_E2E_SMOKE_BLOCKED','files':files,'code_and_document_bindings':bindings,'original_videos_included':False,'old_baselines_modified':False}
 (R/'retention_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 for entry in files:assert sha(R/entry['path'])==entry['sha256']
 for entry in bindings:
  assert sha(ROOT/entry['path'])==entry['sha256']
  assert hashlib.sha256(gzip.decompress((R/entry['retained_path']).read_bytes())).hexdigest()==entry['sha256']
 print(json.dumps({'verification':receipt,'retained_package_files':len(files),'source_bindings':len(bindings)}))
if __name__=='__main__':main()
