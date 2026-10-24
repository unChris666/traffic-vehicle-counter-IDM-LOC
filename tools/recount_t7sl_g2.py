"""Geometry-only revision on retained fresh measurements; never runs models."""
import sys,concurrent.futures
from pathlib import Path
from traffic_location.artifacts import read,write,sha,require,semantic_hash
from traffic_location.traffic.pipeline import run,implementation_hash
from traffic_location.traffic.batch import aggregate
from traffic_location.persistence import publish
ROOT=Path(__file__).resolve().parents[1]
def worker(args):
 vid,source_root,revision_sha,output=args;job=Path(source_root)/'videos'/vid;out=Path(output)/vid
 q=read(job/'counting/request.json');q['artifacts']={k:{'path':str(job/('measurement/result.json.gz' if k=='measurements' else k+'.json')),'sha256':v['sha256']} for k,v in q['artifacts'].items()}
 # First prove unchanged G1 on this counting runtime before attributing G2 differences to geometry.
 baseline=run(q,root=ROOT);original=read(job/'counting/native.json.gz')
 require(semantic_hash(baseline['native'])==semantic_hash(original),'Cross-runtime G1 replay mismatch: '+vid)
 del baseline,original
 geometry=ROOT/'results/t7sl_modular/geometry_g2'/f'{vid}.json';q['artifacts']['geometry']={'path':str(geometry),'sha256':sha(geometry)}
 q['source_identity']['geometry_sha256']=sha(geometry);q['source_manifest_sha256']=revision_sha
 first=run(q,root=ROOT);checks=[]
 for _ in range(2):
  again=run(q,root=ROOT);require(semantic_hash(again['native'])==semantic_hash(first['native']) and again['result']['result_version']==first['result']['result_version'],'G2 repeat mismatch')
  checks.append({'native_sha256':semantic_hash(again['native']),'result_version':again['result']['result_version']})
 publish(out,{'result.json':first['result'],'native.json.gz':first['native'],'request.json':q,'checks.json':{'g1_cross_runtime_native_equal':True,'g2_counting_runs':3,'checks':checks}},metadata={'engine':'traffic','revision':'G2'})
 return {'video_id':vid,'status':'SUCCEEDED','scope':'FULL_VIDEO','experiment_sha256':revision_sha,'branch':'machine','result_version':first['result']['result_version'],'native':first['native']}
def main(source_root):
 revision=ROOT/'results/t7sl_modular/geometry_g2/revision.json';config=read(revision)
 require(config['counting_implementation_sha256']==implementation_hash(),'Counting code changed after G2 freeze')
 for name,digest in config['geometry_files'].items():require(sha(revision.parent/name)==digest,'G2 geometry changed')
 source_root=Path(source_root);output=ROOT/'results/t7sl_modular/g2_execution';require(not output.exists(),'G2 output immutable');output.mkdir()
 expected={Path(v['filename']).stem:v['sha256'] for v in read(ROOT/'results/t7sl_modular/config/experiment.json')['videos']}
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:rows=list(pool.map(worker,[(v,str(source_root),sha(revision),str(output)) for v in expected]))
 result=aggregate(expected,rows,experiment_sha256=sha(revision));write(output/'combined.json',result)
 import csv
 with (output/'combined.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['category','direction','measured','estimated','accepted_total'])
  for c,ds in result['pivot'].items():
   for d,n in ds.items():w.writerow([c,d,n['measured'],n['estimated'],sum(n.values())])
 write(output/'review.json',{'status':'PASS_TECHNICAL_EXPERIMENT','revision':'G2','full_video_count':len(rows),'g1_cross_runtime_native_equal_all':True,'g2_repeats_per_video':3,'vehicle_total':result['complete_vehicle_total'],'source_inference_not_reexecuted':True,'geometry_quality':'ENGINEERING_PROVISIONAL','physical_accuracy_established':False})
if __name__=='__main__':main(sys.argv[1])
