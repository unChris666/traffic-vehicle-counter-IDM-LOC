"""One complete video/job. Invoke in a new process, one visible GPU per job."""
import argparse,sys,json,shutil
from pathlib import Path
from traffic_location.artifacts import read,write,sha,require,semantic_hash
from traffic_location.traffic.inference_worker import execute
from traffic_location.traffic.pipeline import run
from traffic_location.persistence import publish

def main():
 p=argparse.ArgumentParser();p.add_argument('config');p.add_argument('video_root');p.add_argument('output');p.add_argument('slot');p.add_argument('--smoke',action='store_true');p.add_argument('--measurement');a=p.parse_args()
 config=read(a.config);job=next(j for j in config['videos'] if Path(j['filename']).stem==a.slot)
 out=Path(a.output)/a.slot;out.mkdir(parents=True,exist_ok=False);video=Path(a.video_root)/job['filename']
 require(sha(video)==job['sha256'],'Source dataset changed')
 assets=Path(a.config).parent/'assets';r=read(Path(a.config).parent/'fresh_request.json')
 r.update(input_root=str(assets),device='cuda:0',frame_limit=min(96,job['decoded_frames']) if a.smoke else job['decoded_frames'])
 r['artifacts']['video']={'path':str(video),'sha256':job['sha256']}
 for k in ['detector','reid']:r['artifacts'][k]['path']=str(assets/Path(r['artifacts'][k]['path']).name)
 write(out/'inference_request.json',r)
 if a.measurement and not a.smoke:
  cached=Path(a.measurement);fresh=read(cached)
  prior_path=cached.parent.parent/'inference_request.json' if cached.name in {'result.json','result.json.gz'} else cached.with_name(cached.name.split('.result.json')[0]+'.inference_request.json')
  prior=read(prior_path)
  require(fresh['frames']==job['decoded_frames'] and fresh['source_sha256']==job['sha256'],'Resume source/scope differs')
  require(all(prior[k]==r[k] for k in ['conf','iou','imgsz','preprocessing','half','tracker','ultralytics_version','seed']),'Resume model profile differs')
  require(all(prior['artifacts'][k]['sha256']==r['artifacts'][k]['sha256'] for k in ['detector','reid','video']),'Resume assets differ')
  require(fresh['records_semantic_sha256']==semantic_hash(fresh['records']),'Corrupt cached measurement')
  (out/'measurement').mkdir();write(out/'measurement/result.json.gz',fresh)
  print(json.dumps({'stage':'measurement_reused','video':a.slot,'frames':fresh['frames']}),flush=True)
 else:fresh=execute(r,out/'measurement')
 geometry=read(Path(a.config).parent/'geometry'/f'{a.slot}.json');write(out/'geometry.json',geometry)
 policy=read(Path(a.config).parent/'policy.json');write(out/'policy.json',policy)
 measurement=out/'measurement/result.json.gz'
 source={'video_sha256':job['sha256'],'records_sha256':sha(measurement),'geometry_sha256':sha(out/'geometry.json'),
  'width':job['width'],'height':job['height'],'variant':'raw','parent_run_id':config['experiment_id']}
 q={'schema_version':'traffic_request_v1','profile':'machine','measurement_format':'fresh_v1','video_id':a.slot,
  'frame_count':r['frame_limit'],'source_identity':source,'source_manifest_sha256':sha(a.config),'artifacts':
  {k:{'path':str(v),'sha256':sha(v)} for k,v in [('measurements',measurement),('geometry',out/'geometry.json'),('policy',out/'policy.json')]}}
 print(json.dumps({'stage':'counting_start','video':a.slot,'frames':r['frame_limit']}),flush=True)
 result=run(q,root=Path.cwd());checks=[]
 for _ in range(2):
  again=run(q,root=Path.cwd())
  require(semantic_hash(again['native'])==semantic_hash(result['native']) and again['result']['result_version']==result['result']['result_version'],'Counting repeat mismatch')
  checks.append({'native_sha256':semantic_hash(again['native']),'result_version':again['result']['result_version']})
 result['result']['fresh_inference_executed']=not bool(a.measurement and not a.smoke)
 publish(out/'counting',{'result.json':result['result'],'native.json.gz':result['native'],'request.json':q,'adapter_audit.json':result['adapter_audit'],'repetitions.json':{'total_runs':3,'status':'PASS','checks':checks}},metadata={'engine':'traffic'})
 from traffic_location.traffic.annotation import render
 annotated=Path(a.output).parent/'annotated'/(a.slot+('_smoke' if a.smoke else '')+'.mp4')
 print(json.dumps({'stage':'annotation_start','video':a.slot,'output':str(annotated)}),flush=True)
 render(video,measurement,out/'counting/native.json.gz',out/'geometry.json',annotated,preview_limit=96 if a.smoke else None)
 write(out/'job.json',{'status':'SUCCEEDED','video_id':a.slot,'experiment_sha256':sha(a.config),'branch':'machine',
   'result_version':result['result']['result_version'],'annotated_path':str(annotated),'measurement_reused':bool(a.measurement and not a.smoke),'scope':'SMOKE' if a.smoke else 'FULL_VIDEO','frames':r['frame_limit'],'native_path':str(out/'counting/native.json.gz')})
 print(json.dumps(result['result']['summary']),flush=True)
if __name__=='__main__':main()
