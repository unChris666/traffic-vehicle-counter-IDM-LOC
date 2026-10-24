"""Wait for Kaggle terminal output, independently reconcile all eight sources."""
import subprocess,time,json,sys,shutil
from pathlib import Path
from traffic_location.artifacts import read,write,sha,semantic_hash,require
from traffic_location.traffic.batch import aggregate
from traffic_location.traffic.fresh_bridge import frames
ROOT=Path(__file__).resolve().parents[1];CLI='/workspace/.venvs/kaggle-cli/bin/kaggle';KERNEL='chrisbiran/t7sl-fresh-modular-traffic-batch'
WATCH_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
def publish_review():
 """Publish small verified summaries, never videos/models or measurement caches."""
 out=ROOT/'results/t7sl_modular/execution';g1=read(out/'verified_summary.json') if (out/'verified_summary.json').exists() else {}
 g2=ROOT/'results/t7sl_modular/g2_execution';second=read(g2/'review.json') if (g2/'review.json').exists() else {}
 failure=read(out/'collector_error.json') if (out/'collector_error.json').exists() else None
 report=ROOT/'results/t7sl_modular/RUNTIME_RESULT.md'
 report.write_text('# T7SL — observed runtime result\n\n'
  + 'Kernel: https://www.kaggle.com/code/'+KERNEL+'\n\n'
  + 'G1 Kaggle validation: '+g1.get('status','NOT_VERIFIED')+'; vehicles: '+str(g1.get('combined_vehicle_total'))+'\n\n'
  + 'G2 local counting replay: '+second.get('status','NOT_VERIFIED')+'; vehicles: '+str(second.get('vehicle_total'))+'\n\n'
  + 'GPU inference is not rerun for G2. Counts are experimental passages; geometry remains provisional, physical accuracy is not established. Pending/invalid are excluded; pedestrian is separate.\n\n'
  + ('Validation error: '+str(failure)+'\n' if failure else '')
  + '\nSee execution/verified_summary.json, execution/combined.csv and g2_execution/combined.csv. Large caches/native audit files remain in Kaggle outputs or the execution workspace.\n')
 staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True)
 if staged.strip() or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=WATCH_HEAD or subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='work':
  (out/'publication_pending.txt').write_text('Independent Git state changed; automatic publication skipped.');return
 paths=[report]
 paths += [p for p in out.glob('*') if p.suffix in {'.json','.csv','.log'}]
 paths += [p for p in g2.glob('*') if p.is_file() and p.suffix in {'.json','.csv'}] if g2.exists() else []
 if g2.exists():paths += [p for folder in g2.iterdir() if folder.is_dir() for name in ['result.json','request.json','checks.json'] if (p:=folder/name).is_file()]
 subprocess.run(['git','add','--',*[str(p.relative_to(ROOT)) for p in paths]],cwd=ROOT,check=True)
 if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode==0:return
 subprocess.run(['git','commit','-m','Retain observed T7SL execution and independent eight-video validation'],cwd=ROOT,check=True)
 subprocess.run(['git','push','origin','HEAD:refs/heads/codex/engine-adapters-20261023'],cwd=ROOT,check=True)
def main():
 out=ROOT/'results/t7sl_modular/execution';out.mkdir(parents=True,exist_ok=True)
 download=Path('/workspace/scratch/t7sl/terminal-output');lock=read(ROOT/'results/t7sl_modular/config/experiment.json');expected={Path(j['filename']).stem:j for j in lock['videos']}
 for _ in range(360):
  p=subprocess.run([CLI,'kernels','status',KERNEL],capture_output=True,text=True)
  text=p.stdout+p.stderr;write(out/'scheduler_status.json',{'kernel':KERNEL,'observed_at_unix':time.time(),'response':text,'exit_code':p.returncode})
  if p.returncode==0 and any(k in text.upper() for k in ['STATUS "KERNELWORKERSTATUS.COMPLETE"','STATUS "KERNELWORKERSTATUS.ERROR"','STATUS "KERNELWORKERSTATUS.CANCEL']):break
  time.sleep(40)
 else:raise RuntimeError('No terminal scheduler observation within monitoring window')
 subprocess.run([CLI,'kernels','output',KERNEL,'-p',str(download),'--file-pattern',r'.*(?:\.json|\.json\.gz|\.csv|\.log)$','-q'],check=True)
 logs=subprocess.run([CLI,'kernels','logs',KERNEL],capture_output=True,text=True);(out/'terminal.log').write_text(logs.stdout+logs.stderr)
 roots=list(download.rglob('combined.json'))
 if len(roots)!=1:
  write(out/'verified_summary.json',{'status':'FAILED_OR_NO_COMBINED_OUTPUT','scheduler':text,'logs':str(out/'terminal.log')});publish_review();return 1
 root=roots[0].parent;environment=read(root/'environment.json')
 require(len(environment['devices'])==2 and all('T4' in n for n in environment['devices']),'Actual T4x2 was not verified')
 require(read(root/'locked_config.json')==lock,'Runtime experiment lock differs')
 receipts=read(root/'jobs.json');rows=[];verified=[]
 for r in receipts:
  if r['status']!='SUCCEEDED':rows.append(r);continue
  vid=r['video_id'];job=root/'videos'/vid;native=read(job/'counting/native.json.gz');fresh=read(job/'measurement/result.json.gz')
  require(r['frames']==expected[vid]['decoded_frames']==fresh['frames']==fresh['metadata']['reported_frame_count'],'Incomplete source coverage')
  require('CUDAExecutionProvider' in fresh['environment']['reid_providers'],'ReID CUDA execution not verified')
  source=native['source_identity'];require(sha(job/'measurement/result.json.gz')==source['records_sha256'],'Measurement/native binding differs')
  require(sha(job/'geometry.json')==source['geometry_sha256'] and read(job/'geometry.json')==read(ROOT/'results/t7sl_modular/config/geometry'/f'{vid}.json'),'Geometry binding differs')
  require(read(job/'policy.json')==read(ROOT/'results/t7sl_modular/config/policy.json'),'Effective input policy differs')
  require(source['video_sha256']==expected[vid]['sha256'],'Source differs')
  count=sum(1 for _ in frames(job/'measurement/result.json.gz',source,r['frames']));require(count==r['frames'],'Adapter coverage differs')
  repeat=read(job/'counting/repetitions.json');require(repeat['status']=='PASS' and repeat['total_runs']==3 and all(v['native_sha256']==semantic_hash(native) and v['result_version']==r['result_version'] for v in repeat['checks']),'Replay reproducibility failed')
  rows.append({**r,'native':native});verified.append({'video_id':vid,'frames':count,'aggregate':native['aggregate'],'result_version':r['result_version'],'measurement_sha256':source['records_sha256'],'repetitions':repeat})
 recomputed=aggregate({k:v['sha256'] for k,v in expected.items()},rows,experiment_sha256=sha(ROOT/'results/t7sl_modular/config/experiment.json'))
 require(recomputed==read(root/'combined.json'),'Stored combined output differs from independent aggregation')
 for name in ['combined.json','combined.csv','environment.json','jobs.json','smoke_status.json','mounted_dataset.json']:shutil.copyfile(root/name,out/name)
 write(out/'verified_summary.json',{'status':'PASS' if len(verified)==8 else 'PARTIAL','verified_videos':verified,'source_frames':sum(v['frames'] for v in verified),'actual_gpu':environment['devices'],'combined_vehicle_total':recomputed['complete_vehicle_total'],'measured_vehicles':sum(d['measured'] for c,dirs in recomputed['pivot'].items() if c!='pedestrian' for d in dirs.values()),'estimated_vehicles':sum(d['estimated'] for c,dirs in recomputed['pivot'].items() if c!='pedestrian' for d in dirs.values()),'geometry_quality':'ENGINEERING_PROVISIONAL','physical_accuracy_established':False,'raw_download':str(download)})
 print(read(out/'verified_summary.json'),flush=True)
 if len(verified)==8:
  subprocess.run([sys.executable,'-B',str(ROOT/'tools/recount_t7sl_g2.py'),str(root)],cwd=ROOT,check=True)
 publish_review();return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:
  out=ROOT/'results/t7sl_modular/execution';out.mkdir(parents=True,exist_ok=True);write(out/'collector_error.json',{'status':'FAILED_VALIDATION','reason':str(e)})
  try:publish_review()
  except Exception as publication_error:print('Publication failed:',publication_error,flush=True)
  raise
