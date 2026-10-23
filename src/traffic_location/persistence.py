"""Atomic local publication and read-only reopen, without rerunning an engine."""
import json,shutil,tempfile
from pathlib import Path
from .artifacts import require,sha,read,write,semantic_hash

def verify_manifest(root):
 root=Path(root).resolve();m=read(root/'manifest.json')
 paths=[r['path'] for r in m['files']]
 require(len(paths)==len(set(paths)),'Duplicate manifest path')
 actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'}
 require(actual==set(paths),'Missing/unlisted output artifacts')
 for row in m['files']:
  p=root/row['path'];require(p.resolve().is_relative_to(root) and not p.is_symlink(),'Unsafe artifact path')
  require(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'Artifact checksum mismatch')
 return m

def publish(output,files,*,metadata=None):
 output=Path(output).resolve();require(not output.exists(),'Output already exists; revisions immutable')
 output.parent.mkdir(parents=True,exist_ok=True)
 stage=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent))
 try:
  for name,value in files.items():
   p=stage/name;require(p.resolve().is_relative_to(stage.resolve()) and name!='manifest.json','Unsafe output name')
   write(p,value)
  rows=[{'path':str(p.relative_to(stage)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(stage.rglob('*')) if p.is_file()]
  write(stage/'manifest.json',{'schema_version':'engine_artifacts_v1','files':rows,'metadata':metadata or {}})
  verify_manifest(stage);require(not output.exists(),'Output appeared during build');stage.rename(output)
 except BaseException:
  shutil.rmtree(stage,ignore_errors=True);raise
 return read(output/'manifest.json')

def reopen_traffic(root):
 verify_manifest(root)
 from .traffic.results import validate_native
 native=read(Path(root)/'native.json.gz');result=read(Path(root)/'result.json')
 validate_native(native)
 require(semantic_hash(native)==result['native_semantic_sha256'],'Native/result binding differs')
 return result
