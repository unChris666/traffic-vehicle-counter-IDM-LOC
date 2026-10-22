"""Build a NEW P1 delivery manifest; historical manifests are never touched."""
from pathlib import Path
import gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'results/b_v8'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert json.loads((R/'verification/final_verification.json').read_text())['status']=='PASS'
paths=sorted(set((ROOT/'notebooks').glob('phase_8_b_v8_*.py'))|set((ROOT/'notebooks').glob('phase_9_v8_*.py'))|{ROOT/'notebooks/09e_p1_pending_recovery.ipynb',ROOT/'docs/B_V8_P1_CONTRACT.md',ROOT/'docs/B_V8_P1_REVIEW.md'})
bindings=[]
for path in paths:
 relative=path.relative_to(ROOT);target=R/'delivery_source_snapshot'/str(relative)
 target=target.with_name(target.name+'.gz');target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(gzip.compress(path.read_bytes(),mtime=0))
 bindings.append({'path':str(relative),'sha256':sha(path),'retained_path':str(target.relative_to(R))})
files=[]
for p in sorted(R.rglob('*')):
 if not p.is_file() or p==R/'retention_manifest.json' or '__pycache__' in p.parts or p.suffix=='.pyc':continue
 files.append({'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)})
manifest={'schema_version':'b_v8_p1_delivery_retention_v1','self_excluded':True,'gate':'PASS_REVIEW_ASSISTED_SINGLE_VIDEO_DEVELOPMENT_PILOT','files':files,'code_and_document_bindings':bindings,'historical_manifests_modified':False,'private_original_video_included':False,'new_model_assets_included':False,'machine_baseline_promoted':False}
(R/'retention_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Check exactly what was retained, including the live source bindings.
for entry in files:assert sha(R/entry['path'])==entry['sha256']
for entry in bindings:
 assert sha(ROOT/entry['path'])==entry['sha256']
 assert hashlib.sha256(gzip.decompress((R/entry['retained_path']).read_bytes())).hexdigest()==entry['sha256']
print(json.dumps({'retention_status':'PASS','package_files':len(files),'source_document_bindings':len(bindings),'gate':manifest['gate']}))
