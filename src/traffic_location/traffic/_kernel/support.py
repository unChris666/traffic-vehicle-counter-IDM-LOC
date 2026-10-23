"""Local read-only guards shared by extracted source adapters."""
import gzip,hashlib,json,math
from pathlib import Path

def require(condition,message):
 if not condition:raise ValueError(message)

def read(path):
 data=Path(path).read_bytes()
 return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def bound(root,name,digest,guarded):
 relative=Path(name);p=(Path(root)/relative).resolve()
 require(not relative.is_absolute() and p.is_relative_to(Path(root).resolve()) and p.is_file() and not p.is_symlink(),'Missing/unsafe proof')
 require(sha(p)==digest,'Proof checksum differs')
 guarded.append({'path':str(p),'sha256':digest});return p

def bbox(value):
 require(isinstance(value,(list,tuple)) and len(value)==4,'raw_bbox needs four coordinates')
 require(all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in value),'raw_bbox must be finite')
 box=list(value);require(box[0]<box[2] and box[1]<box[3],'Invalid bbox');return box

def records(path):
 opener=gzip.open if str(path).endswith('.gz') else open
 with opener(path,'rt',encoding='utf-8') as f:
  for line in f:
   require(bool(line.strip()),'Empty source record');yield json.loads(line)

# Retained relation arrays are bounded (~5.8MB gzip for the pilot). No network.
def iter_json_array(path):
 yield from read(path)
