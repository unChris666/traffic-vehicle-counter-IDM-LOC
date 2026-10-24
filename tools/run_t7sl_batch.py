"""Kaggle batch launcher: two isolated GPU slots, frozen assets, explicit partial."""
import os,sys,subprocess,json,concurrent.futures,platform
from pathlib import Path
from traffic_location.artifacts import read,write,sha,require
from traffic_location.traffic.batch import aggregate

def main(config_path,video_root,output):
 import torch,onnxruntime
 config=read(config_path);out=Path(output);out.mkdir(parents=True,exist_ok=False)
 gpu={'python':platform.python_version(),'torch':torch.__version__,'cuda':torch.version.cuda,'devices':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],'ort_providers':onnxruntime.get_available_providers()}
 write(out/'environment.json',gpu)
 require(len(gpu['devices'])==2 and all('T4' in n for n in gpu['devices']),'Exactly T4x2 required; no CPU fallback')
 require('CUDAExecutionProvider' in gpu['ort_providers'],'CUDA encoder provider required')
 jobs=config['videos'];mount=[]
 for j in jobs:
  p=Path(video_root)/j['filename'];require(p.is_file() and sha(p)==j['sha256'],'Mounted dataset/source differs: '+j['filename']);mount.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
 write(out/'mounted_dataset.json',mount);write(out/'locked_config.json',config)
 def worker(job,gpu_id,dest,smoke=False):
  vid=Path(job['filename']).stem;dest.mkdir(parents=True,exist_ok=True)
  command=[sys.executable,'-B','tools/run_t7sl_job.py',str(Path(config_path).resolve()),str(video_root),str(dest),vid]+(['--smoke'] if smoke else [])
  with (dest/(vid+'.log')).open('w') as log:r=subprocess.run(command,env={**os.environ,'CUDA_VISIBLE_DEVICES':str(gpu_id)},stdout=log,stderr=subprocess.STDOUT)
  return r.returncode
 # Daylight smoke first, separate from the full-video result namespace.
 smoke=next(j for j in jobs if 'WEEKDAY-PAGI' in j['filename'])
 rc=worker(smoke,0,out/'smoke',True);write(out/'smoke_status.json',{'exit_code':rc,'status':'PASS' if rc==0 else 'FAILED'})
 require(rc==0,'Smoke failed; full-video inference not started')
 def queue(slot):
  receipts=[]
  for j in jobs[slot::2]:
   vid=Path(j['filename']).stem;code=worker(j,slot,out/'videos')
   row=read(out/'videos'/vid/'job.json') if code==0 else {'video_id':vid,'status':'FAILED','exit_code':code}
   receipts.append(row);write(out/f'progress_gpu{slot}.json',receipts)
  return receipts
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(queue,g) for g in [0,1]];receipts=[r for f in futures for r in f.result()]
 rows=[]
 for r in receipts:
  if r['status']=='SUCCEEDED':r={**r,'native':read(r['native_path'])}
  rows.append(r)
 combined=aggregate({Path(j['filename']).stem:j['sha256'] for j in jobs},rows,experiment_sha256=sha(config_path))
 write(out/'combined.json',combined);write(out/'jobs.json',receipts)
 import csv
 with (out/'combined.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['category','direction','measured','estimated','accepted_total'])
  for c,ds in combined['pivot'].items():
   for d,n in ds.items():w.writerow([c,d,n['measured'],n['estimated'],sum(n.values())])
 print(json.dumps({k:v for k,v in combined.items() if k not in ['events','pivot']}),flush=True)
 require(combined['videos_completed']==8,'Batch partial; see failed slots')
if __name__=='__main__':main(*sys.argv[1:])
