"""Read-only integrity checks. Never runs inference or counting."""
from pathlib import Path
import hashlib,json,gzip,re,subprocess
ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'results/b_v8'
CACHE={}
def digest(path):
 p=Path(path).resolve()
 if p not in CACHE:
  with p.open('rb') as f:CACHE[p]=hashlib.file_digest(f,'sha256').hexdigest()
 return CACHE[p]
def load(p):return json.loads(Path(p).read_text())
def verify(p,expected):
 actual=digest(p)
 assert actual==expected, f'Hash mismatch:{p}'
def main():
 (R/'verification/final_verification.json').write_text(json.dumps({'status':'RUNNING_NOT_YET_VERIFIED'})+'\n')
 frozen=load(R/'verification/frozen_inputs_before.json')
 for item in frozen['files']:verify(ROOT/item['path'],item['sha256'])
 oldroot=ROOT/'results/b_v7';old_manifest=load(oldroot/'retention_manifest.json')
 for item in old_manifest['files']:verify(oldroot/item['path'],item['sha256'])
 for item in old_manifest['code_and_document_bindings']:
  verify(ROOT/item['path'],item['sha256'])
  assert hashlib.sha256(gzip.decompress((oldroot/item['retained_path']).read_bytes())).hexdigest()==item['sha256']
 receipt=load(R/'verification/notebook_selected_configuration_receipt.json')
 verify(ROOT/receipt['path'],receipt['after_sha256'])
 current=load(ROOT/receipt['path'])
 run_counts={};source_counts={};guard_counts={}
 for run_id in ['pilot_p1_reviewed_v1','pilot_p1_reviewed_v2','pilot_p1_reviewed_v3']:
  run=R/'execution'/run_id
  manifest=load(run/'retention_manifest.json')
  for item in manifest['files']:verify(run/item['path'],item['sha256'])
  run_counts[run_id]=len(manifest['files'])
  sources=load(run/'source_snapshot.json')
  for path,info in sources.items():
   original=gzip.decompress((run/info['retained_path']).read_bytes())
   assert hashlib.sha256(original).hexdigest()==info['sha256']
   if Path(path).name=='09e_p1_pending_recovery.ipynb':
    assert info['sha256']==receipt['before_sha256']
    notebook=json.loads(original)
    replacements=receipt['replacements'];counts={key:0 for key in replacements}
    for cell in notebook['cells']:
     text=''.join(cell['source'])
     for old,new in replacements.items():
      counts[old]+=text.count(old);text=text.replace(old,new)
     cell['source']=text.splitlines(keepends=True)
    assert all(n==1 for n in counts.values())
    expected_normalized=json.loads(json.dumps(notebook));current_normalized=json.loads(json.dumps(current))
    for document in [expected_normalized,current_normalized]:
     for cell in document['cells']:cell['source']=''.join(cell['source'])
    assert expected_normalized==current_normalized,'Notebook changes exceed declared two config paths'
   else: verify(Path(path),info['sha256'])
  source_counts[run_id]=len(sources)
  guarded=load(run/'guarded_inputs.json')
  for item in guarded:verify(Path(item['path']),item['sha256'])
  guard_counts[run_id]=len(guarded)
  report=load(run/'batch_report.json')
  assert report['inputs_and_sources_unchanged'] and report['frames_processed']==9128
  assert not report['new_detector_tracker_reid_execution'] and not report['new_enhancement_execution']
 freeze=load(R/'verification/configuration_freeze_v3.json')
 for path,sha in {**freeze['source_sha256'],**freeze['validation_source_sha256']}.items():
  verify(ROOT/path,receipt['after_sha256'] if path==receipt['path'] else sha)
 verify(R/freeze['policy_path'].removeprefix('results/b_v8/'),freeze['policy_sha256'])
 verify(R/freeze['overlay_path'].removeprefix('results/b_v8/'),freeze['overlay_sha256'])
 verify(R/'config/pending_adjudications.json',freeze['pending_adjudications_sha256'])
 tests=load(R/'verification/tests.json');assert sum(t['tests'] for t in tests)==302
 assert all(t['returncode']==0 and t['status']=='PASS' and (R/'verification'/t['log']).is_file() for t in tests)
 q=load(R/'review/full_pilot_v3_qc.json');assert q['scoped_checks_pass']
 verify(ROOT/q['candidate_path'],q['candidate_sha256'])
 selected=load(R/'selected_run.json');verify(ROOT/selected['baseline_path'],selected['baseline_sha256'])
 assert selected['candidate_sha256']==q['candidate_sha256']
 assert q['pending_dispositions']=={'accepted':1,'pending':1,'resolved_not_eligible':22}
 assert q['additional_handoff_has_one_clean_inferred_event'] and q['red_exactly_one_clean_inferred_passage']
 assert not q['unsupported_blue_destination_presence_events']
 comp=load(R/'comparison/pilot_p1_reviewed_v3/comparison.json')
 assert comp['event_counts']=={'unchanged':70,'changed':2,'removed':0,'added':2}
 import nbformat
 nbformat.validate(nbformat.read(ROOT/receipt['path'],as_version=4))
 for cell in current['cells']:
  if cell['cell_type']=='code':
   assert not cell.get('outputs');compile(''.join(cell['source']),receipt['path'],'exec')
 links=0
 for doc in [ROOT/'docs/B_V8_P1_CONTRACT.md',ROOT/'docs/B_V8_P1_REVIEW.md',R/'README.md']:
  for target in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
   if '://' in target or target.startswith('#'):continue
   target=target.split('#')[0]
   assert (doc.parent/target).exists(),f'Broken link {doc}: {target}'
   links+=1
 diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
 assert diff.returncode==0,diff.stdout+diff.stderr
 forbidden=[str(p.relative_to(R)) for p in R.rglob('*') if p.is_file() and p.suffix.lower() in {'.mp4','.avi','.mov','.pt','.onnx','.engine'}]
 assert not forbidden
 result={'schema_version':'b_v8_p1_final_verification_v1','status':'PASS','historical_files_unchanged':len(frozen['files']),'b_v7_retention_files_verified':len(old_manifest['files']),'b_v7_current_source_document_bindings_verified':len(old_manifest['code_and_document_bindings']),'run_retention_files_verified':run_counts,'archived_sources_verified':source_counts,'guarded_inputs_verified':guard_counts,'notebook_only_declared_configuration_change':True,'notebook_valid_and_unexecuted':True,'tests_passed':302,'selected_full_video_frames':9128,'final_source_qc_pass':True,'all_24_pending_dispositions_reconciled':True,'markdown_relative_links_verified':links,'git_diff_check':'PASS','new_model_execution':False,'private_video_or_model_assets_in_package':False,'production_ready':False}
 (R/'verification/final_verification.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
