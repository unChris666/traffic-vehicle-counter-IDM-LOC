"""Real frozen-measurement replay; no detector/tracker/encoder inference."""
import argparse,gc,json,time
from pathlib import Path
from traffic_location.artifacts import read,write,semantic_hash
from traffic_location.traffic.pipeline import run
from traffic_location.persistence import publish,reopen_traffic
ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--branch',choices=['machine','review_assisted'],required=True)
 parser.add_argument('--output',required=True);parser.add_argument('--repetitions',type=int,default=3)
 a=parser.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 base=ROOT/'results/engine_modularization/20261023'
 request=read(base/'requests'/f'{a.branch}.json');golden=read(base/'goldens/baselines.json')[a.branch]
 runs=[]
 for i in range(a.repetitions):
  request['profile']='replay' if i%2 else a.branch
  if request['profile']=='replay':request['replay_branch']=a.branch
  else:request.pop('replay_branch',None)
  start=time.perf_counter();value=run(request,root=ROOT);native=value['native']
  diff=[k for k in sorted(set(native)|set(golden['field_hashes'])) if semantic_hash(native.get(k))!=golden['field_hashes'].get(k)]
  row={'iteration':i+1,'profile':request['profile'],'native_equal':not diff,'different_native_fields':diff,
   'result':value['result'],'wall_seconds':time.perf_counter()-start}
  if i==0:
   publish(out/'packet',{'native.json.gz':native,'result.json':value['result'],'request.json':request,'adapter_audit.json':value['adapter_audit']},metadata={'engine':'traffic'})
   assert reopen_traffic(out/'packet')==value['result']
  runs.append(row);write(out/'comparison.json',{'branch':a.branch,'runs':runs,'status':'RUNNING'})
  print(json.dumps(row),flush=True)
  assert not diff, 'Native baseline parity failed'
  del native,value;gc.collect()
 assert len({r['result']['result_version'] for r in runs})==1,'Same input/code/runtime yielded different result versions'
 receipt={'branch':a.branch,'status':'PASS','runs':runs,'same_result_version':True,'reopen_verified':True}
 write(out/'comparison.json',receipt)
if __name__=='__main__':main()
