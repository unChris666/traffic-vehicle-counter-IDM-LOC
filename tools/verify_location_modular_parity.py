"""Actual frozen N1 checks in the separately recorded geometry runtimes."""
import argparse,tempfile
from pathlib import Path
from traffic_location.artifacts import read,write,sha,semantic_hash
from traffic_location.location.engine import run_selection,run_recount
from traffic_location.persistence import publish,verify_manifest
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/location_intelligent'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['selection','recount']);parser.add_argument('--output',required=True)
 a=parser.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True);requests=ROOT/'results/engine_modularization/20261023/requests'
 if a.operation=='selection':
  q=read(requests/'location_selection.json');runs=[run_selection(q,root=ROOT) for _ in range(3)]
  first=runs[0];same=all(v==first for v in runs)
  selection_equal=first['selection']==read(BASE/'li4_n1_20261023_v1/snapshot/building_results/selection.json')
  capacity_equal=first['capacity']==read(BASE/'li4_n1_20261023_v1/snapshot/building_results/capacity.json')
  assert same and selection_equal and capacity_equal
  publish(out/'packet',{'result.json':first,'request.json':q},metadata={'engine':'location'})
  receipt={'status':'PASS','operation':a.operation,'repetitions':3,'identical_results_and_version':same,
   'selection_equal':selection_equal,'capacity_equal':capacity_equal,'source_rows':first['selection']['summary'],
   'result_version':first['result_version'],'result_quality':first['result_quality'],'source_analysis_status':first['source_analysis_status'],
   'runtime':first['runtime'],'engine_sha256':first['engine_sha256']}
 else:
  receipts=[];values={}
  for rev in ['r1','r2']:
   q=read(requests/f'location_recount_{rev}.json');runs=[run_recount(q,root=ROOT) for _ in range(3)];first=runs[0]
   assert all(v==first for v in runs)
   old=read(BASE/f'li5_n1_20261023_{rev}/result.json');exclude={'result_version','engine_sha256'}
   assert {k:v for k,v in old.items() if k not in exclude}=={k:v for k,v in first['result'].items() if k not in exclude}
   assert first['membership']==read(BASE/f'li5_n1_20261023_{rev}/membership.json')
   publish(out/rev,{'result.json':first,'request.json':q},metadata={'engine':'location'})
   values[rev]=first
   receipts.append({'revision':rev,'repetitions':3,'identical_results_and_version':True,'native_domain_equal':True,
    'allowed_version_differences':sorted(exclude),'membership_equal':True,'membership_semantic_sha256':semantic_hash(first['membership']),
    'source_records':first['result']['source_records'],'selected':first['result']['evaluated_selected'],'union':first['result']['union_count'],
    'analysis_status':first['result']['analysis_status'],'software':first['result']['software'],'result_version':first['result']['result_version']})
  q=read(requests/'location_recount_r2.json');p=out/'r1/result.json';q['previous']={'path':str(p.resolve()),'sha256':sha(p)}
  delta=run_recount(q,root=ROOT)['delta'];old=read(BASE/'li5_n1_20261023_r2/delta.json')
  assert delta['union']==old['union'] and delta['polygons']==old['polygons']
  receipt={'status':'PASS','operation':a.operation,'runs':receipts,'delta_membership_equal':True,
   'delta_union_entered':len(delta['union']['entered']),'delta_union_exited':len(delta['union']['exited'])}
 for p in out.glob('packet'):verify_manifest(p)
 write(out/'comparison.json',receipt)
 print(receipt)
if __name__=='__main__':main()
