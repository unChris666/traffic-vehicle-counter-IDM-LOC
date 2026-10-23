"""Local immutable artifact boundaries; storage vendor adapters remain external."""
import gzip,hashlib,json
from pathlib import Path

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def semantic_hash(value):return hashlib.sha256(canonical(value)).hexdigest()
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def require(test,message):
 if not test:raise ValueError(message)
def artifact(ref,root):
 require(isinstance(ref,dict) and set(ref)>={'path','sha256'},'Explicit artifact path and SHA256 required')
 p=Path(ref['path']);p=Path(root)/p if not p.is_absolute() else p
 require(not p.is_symlink(),'Symlink artifact is not supported')
 p=p.resolve()
 require(p.is_file(),'Artifact missing/unsafe')
 require(isinstance(ref['sha256'],str) and len(ref['sha256'])==64 and sha(p)==ref['sha256'],'Artifact checksum differs: '+p.name)
 return p
def read(path):
 data=Path(path).read_bytes()
 return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)
def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);data=canonical(value)
 path.write_bytes(gzip.compress(data,mtime=0) if path.suffix=='.gz' else data)
