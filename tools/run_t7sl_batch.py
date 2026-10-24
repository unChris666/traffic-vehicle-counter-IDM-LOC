"""Visible progress, bounded jobs and resumable source-bound T7SL experiment."""
import os,sys,subprocess,json,concurrent.futures,platform,time,threading,signal
from pathlib import Path
from traffic_location.artifacts import read,write,sha,require
from traffic_location.traffic.batch import aggregate

def main(config_path,video_root,output):
 import torch,onnxruntime
 config=read(config_path);out=Path(output);out.mkdir(parents=True,exist_ok=False)
 gpu={'python':platform.python_version(),'torch':torch.__version__,'cuda':torch.version.cuda,'devices':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],'ort_providers':onnxruntime.get_available_providers()}
 write(out/'environment.json',gpu);print('RUNTIME',json.dumps(gpu),flush=True)
 require(len(gpu['devices'])==2 and all('T4' in n for n in gpu['devices']),'T4x2 required')
 require('CUDAExecutionProvider' in gpu['ort_providers'],'CUDA ReID required')
 jobs=config['videos'];cache={}
 for j in jobs:require(sha(Path(video_root)/j['filename'])==j['sha256'],'Mounted source changed')
 by_sha={j['sha256']:Path(j['filename']).stem for j in jobs}
 for p in Path('/kaggle/input').rglob('*result.json*'):
  if '/smoke/' not in str(p):
   if not p.is_file():continue
   v=read(p)
   if v.get('source_sha256') in by_sha and v.get('frames')==v.get('metadata',{}).get('reported_frame_count'):cache[by_sha[v['source_sha256']]]=p
 print('RESUME_CACHE',list(cache),flush=True)
 require(len(cache)>=5,'Previous five completed measurements must be attached; refusing duplicate GPU inference')
 write(out/'locked_config.json',config)
 stop=threading.Event()
 def worker(job,gpu_id,dest,smoke=False):
  vid=Path(job['filename']).stem;dest.mkdir(parents=True,exist_ok=True)
  command=[sys.executable,'-u','tools/run_t7sl_job.py',str(Path(config_path).resolve()),str(video_root),str(dest),vid]+(['--smoke'] if smoke else ['--measurement',str(cache[vid])] if vid in cache else [])
  limit=300 if smoke else 3600
  with (dest/(vid+'.log')).open('w') as log:
   proc=subprocess.Popen(command,env={**os.environ,'CUDA_VISIBLE_DEVICES':str(gpu_id),'OMP_NUM_THREADS':'4','MKL_NUM_THREADS':'4'},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
   def relay():
    for line in proc.stdout:
     log.write(line);log.flush()
     if "'half' is deprecated" not in line:print(f'[GPU{gpu_id} {vid}] '+line.rstrip(),flush=True)
   thread=threading.Thread(target=relay,daemon=True);thread.start();start=time.monotonic()
   while proc.poll() is None:
    if stop.is_set() or time.monotonic()-start>limit:
     os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=20);print('TIMEOUT',vid,flush=True);break
    print(f'HEARTBEAT {vid} elapsed={time.monotonic()-start:.0f}s',flush=True);time.sleep(20)
   thread.join(timeout=5)
   return proc.returncode
 smoke=next(j for j in jobs if 'WEEKDAY-PAGI' in j['filename'])
 rc=worker(smoke,0,out/'smoke',True);write(out/'smoke_status.json',{'status':'PASS' if rc==0 else 'FAILED','exit_code':rc})
 require(rc==0,'Smoke failed: full batch blocked')
 def queue(slot):
  rows=[]
  for j in jobs[slot::2]:
   if stop.is_set():raise RuntimeError('Other GPU queue failed; stopping batch')
   vid=Path(j['filename']).stem;code=worker(j,slot,out/'videos')
   row=read(out/'videos'/vid/'job.json') if code==0 else {'video_id':vid,'status':'FAILED','exit_code':code}
   rows.append(row);write(out/f'progress_gpu{slot}.json',rows)
   print('VIDEO_FINISHED',vid,row['status'],flush=True)
   if code:stop.set();raise RuntimeError('First job failed; queue stopped: '+vid)
  return rows
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(queue,g) for g in [0,1]];receipts=[r for f in futures for r in f.result()]
 rows=[{**r,'native':read(r['native_path'])} for r in receipts]
 combined=aggregate({Path(j['filename']).stem:j['sha256'] for j in jobs},rows,experiment_sha256=sha(config_path))
 write(out/'combined.json',combined);write(out/'jobs.json',receipts)
 import csv
 with (out/'combined.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['category','direction','measured','estimated','accepted_total'])
  for c,ds in combined['pivot'].items():
   for d,n in ds.items():w.writerow([c,d,n['measured'],n['estimated'],sum(n.values())])
 print('BATCH_RESULT',json.dumps({k:v for k,v in combined.items() if k not in ['events','pivot']}),flush=True)
if __name__=='__main__':main(*sys.argv[1:])
