"""Wait for the existing GPU producer; submit one CPU annotation run after success."""
from pathlib import Path
import subprocess,json,time,sys
ROOT=Path(__file__).resolve().parents[1];CLI='/workspace/.venvs/kaggle-cli/bin/kaggle';OUT=ROOT/'results/t7sl_modular/annotation_submission';PRODUCER='chrisbiran/t7sl-traffic-counter-readable'
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 for _ in range(360):
  p=subprocess.run([CLI,'kernels','status',PRODUCER],capture_output=True,text=True);status=p.stdout+p.stderr
  (OUT/'producer_status.json').write_text(json.dumps({'observed_at_unix':time.time(),'response':status,'producer':PRODUCER},indent=2))
  upper=status.upper()
  if 'KERNELWORKERSTATUS.COMPLETE' in upper:break
  if 'KERNELWORKERSTATUS.ERROR' in upper or 'KERNELWORKERSTATUS.CANCEL' in upper:
   (OUT/'blocked.json').write_text(json.dumps({'status':'BLOCKED','reason':'Producer failed/cancelled; eight complete results not assumed','response':status},indent=2));return 1
  time.sleep(40)
 else:raise RuntimeError('Producer did not reach terminal state in monitoring window')
 # Verify completed all-eight summary before spending even CPU rendering quota.
 download=Path('/workspace/scratch/t7sl/annotation-producer-summary')
 subprocess.run([CLI,'kernels','output',PRODUCER,'-p',str(download),'--file-pattern',r'.*(?:combined\.json|jobs\.json)$','-q'],check=True)
 matches=list(download.rglob('combined.json'));assert len(matches)==1,'Completed eight-video summary unavailable'
 summary=json.loads(matches[0].read_text());jobs=json.loads((matches[0].parent/'jobs.json').read_text())
 assert summary['videos_completed']==8 and len(jobs)==8 and all(j['status']=='SUCCEEDED' for j in jobs),'Partial producer; annotation blocked'
 (OUT/'verified_producer.json').write_text(json.dumps({'videos':8,'source_frames':sum(j['frames'] for j in jobs),'inference_rerun':False,'counting_rerun':False},indent=2))
 with (OUT/'submission.log').open('w') as log:
  result=subprocess.run([CLI,'kernels','push','-p',str(OUT),'-t','7200'],stdout=log,stderr=subprocess.STDOUT)
 assert result.returncode==0,'CPU annotation submission failed'
 content=(OUT/'submission.log').read_text();assert 'not valid' not in content.lower(),'Input attachment rejected; do not claim annotation started'
 print(content,flush=True);return 0
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as e:
  (OUT/'blocked.json').write_text(json.dumps({'status':'BLOCKED','reason':str(e)},indent=2));raise
