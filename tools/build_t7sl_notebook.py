"""Reproducible private Kaggle packet: source bundle plus locked experiment."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 config=ROOT/'results/t7sl_modular/config';lock=json.loads((config/'experiment.json').read_text())
 files=list((ROOT/'src/traffic_location').rglob('*.py'))+list((ROOT/'src/traffic_location').rglob('*.json'))+[ROOT/'tools/run_t7sl_job.py',ROOT/'tools/run_t7sl_batch.py']+list(config.glob('*.json'))+list((config/'geometry').glob('*.json'))
 files=[p for p in files if p!=config/'experiment.json'];lock['files']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
 (config/'experiment.json').write_text(json.dumps(lock,indent=2)+'\n');files.append(config/'experiment.json')
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(files):z.writestr(str(p.relative_to(ROOT)),p.read_bytes())
 payload=stream.getvalue();digest=hashlib.sha256(payload).hexdigest()
 bootstrap=f'''import base64,hashlib,zipfile,io,os,sys,subprocess,json
from pathlib import Path
payload=base64.b64decode({base64.b64encode(payload).decode()!r})
assert hashlib.sha256(payload).hexdigest()=={digest!r}
ROOT=Path('/kaggle/working/t7sl_source');ROOT.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(payload)) as z:z.extractall(ROOT)
os.chdir(ROOT);sys.path.insert(0,str(ROOT/'src'));os.environ['PYTHONPATH']=str(ROOT/'src')
subprocess.run([sys.executable,'-m','pip','install','--quiet','ultralytics==8.4.175','lap==0.5.13','onnx==1.20.1','onnxruntime-gpu==1.24.4'],check=True)
import torch,onnxruntime as ort
if hasattr(ort,'preload_dlls'):ort.preload_dlls()
from traffic_location.artifacts import read,write,sha
CONFIG=ROOT/'results/t7sl_modular/config';lock=read(CONFIG/'experiment.json')
for name,wanted in lock['files'].items():assert sha(ROOT/name)==wanted,name
hits=list(Path('/kaggle/input').rglob(lock['videos'][0]['filename']))
assert len(hits)==1,('Dataset mount missing/ambiguous',hits)
VIDEO_ROOT=hits[0].parent
assets=CONFIG/'assets';assets.mkdir()
import requests
r=read(CONFIG/'fresh_request.json')
for k in ['detector','reid']:
 ref=r['artifacts'][k];name=Path(ref['path']).name;dest=assets/name
 response=requests.get('https://github.com/ultralytics/assets/releases/download/v8.4.0/'+name,timeout=180);response.raise_for_status();dest.write_bytes(response.content)
 assert sha(dest)==ref['sha256'],name
print('Mounted dataset:',VIDEO_ROOT,'CUDA:',torch.cuda.device_count(),[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],flush=True)
from tools.run_t7sl_batch import main
main(CONFIG/'experiment.json',VIDEO_ROOT,Path('/kaggle/working/results/t7sl_fresh_machine_v1'))
'''
 packet=ROOT/'results/t7sl_modular/kaggle_packet';packet.mkdir(exist_ok=True)
 nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':[{'cell_type':'markdown','metadata':{},'source':['# T7SL fresh modular batch — experimental\nT4x2 required; RAW baseline; per-source provisional geometry; no legacy review overlay. Source hashes, GPU observations, smoke and eight full jobs retained.']},{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':bootstrap.splitlines(True)}]}
 (ROOT/'notebooks/10_t7sl_fresh_modular_batch.ipynb').write_text(json.dumps(nb))
 (packet/'10_t7sl_fresh_modular_batch.ipynb').write_text(json.dumps(nb))
 (packet/'kernel-metadata.json').write_text(json.dumps({'id':'chrisbiran/t7sl-fresh-modular-traffic-batch','title':'T7SL fresh modular traffic batch','code_file':'10_t7sl_fresh_modular_batch.ipynb','language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_tpu':False,'enable_internet':True,'dataset_sources':['chrisbiran/t7sl-traffic-videos'],'kernel_sources':[],'competition_sources':[]},indent=2))
 (packet/'bundle_receipt.json').write_text(json.dumps({'sha256':digest,'bytes':len(payload),'files':len(files)},indent=2))
 print(packet,len(payload))
if __name__=='__main__':main()
