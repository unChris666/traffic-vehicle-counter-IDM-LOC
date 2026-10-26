"""Bounded single-device fresh-inference trial; no automatic baseline promotion.

python -m traffic_location.traffic.experiments.benchmark REQUEST OUTPUT \
  --geometry GEOMETRY --policy POLICY --frames 256 --batch 4 --repetitions 3
"""
import argparse
import copy
import sys
from pathlib import Path
from ...artifacts import read,write,sha,semantic_hash,require
from ..application.runtime import fresh_inference
from ..application.pipeline import run
from .performance import profile_to


def first_difference(a,b,path='$'):
    if type(a) is not type(b):return {'path':path,'baseline':a,'candidate':b}
    if isinstance(a,dict):
        if a.keys()!=b.keys():return {'path':path,'baseline_keys':sorted(a),'candidate_keys':sorted(b)}
        for key in a:
            found=first_difference(a[key],b[key],path+'.'+str(key))
            if found:return found
    elif isinstance(a,list):
        if len(a)!=len(b):return {'path':path,'baseline_length':len(a),'candidate_length':len(b)}
        for i,(x,y) in enumerate(zip(a,b)):
            found=first_difference(x,y,path+f'[{i}]')
            if found:return found
    elif a!=b:return {'path':path,'baseline':a,'candidate':b}
    return None


def trial(request,output,*,geometry,policy,frames=256,batch=4,repetitions=3,device='cuda:0'):
    require(repetitions>=3,'At least three independent repetitions required')
    require(batch>1,'Candidate batch must be greater than one')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    base=read(request);rows=[]
    # Fail before expensive inference if mandatory counting inputs are unavailable.
    read(geometry);read(policy)
    for size in (1,batch):
        for repeat in range(repetitions):
            folder=output/f'batch{size}-repeat{repeat+1}';folder.mkdir()
            q=copy.deepcopy(base);q.update(frame_limit=frames,start_frame=0,device=device,half=False,
                                           performance={'batch_size':size},execution_profile='baseline_fp32')
            write(folder/'producer.json',q)
            measurement=fresh_inference(folder/'producer.json',folder/'measurement',python_executable=sys.executable)
            ref=folder/'measurement/result.json.gz';meta=measurement['metadata']
            source={'video_sha256':q['artifacts']['video']['sha256'],'records_sha256':sha(ref),
                    'geometry_sha256':sha(geometry),'width':meta['width'],'height':meta['height'],
                    'variant':'raw','parent_run_id':'single_gpu_performance_trial'}
            count_request={'schema_version':'traffic_request_v1','profile':'machine','measurement_format':'fresh_v1',
                           'video_id':'performance-prefix','frame_count':frames,'source_identity':source,
                           'source_manifest_sha256':sha(request),'artifacts':{k:{'path':str(Path(p).resolve()),'sha256':sha(p)}
                            for k,p in [('measurements',ref),('geometry',geometry),('policy',policy)]}}
            write(folder/'count-request.json',count_request)
            with profile_to(folder/'counting-performance.json'):
                result=run(count_request,root=folder)
            write(folder/'count-result.json.gz',result)
            rows.append({'batch':size,'repeat':repeat+1,'records_sha256':measurement['records_semantic_sha256'],
                         'events_sha256':semantic_hash(result['native']['events']),
                         'aggregate':result['native']['aggregate'],
                         'native_sha256':semantic_hash(result['native']),
                         'performance':read(folder/'measurement/performance.json')})
            write(output/'progress.json',rows)
    def signature(row):
        return (row['records_sha256'],row['events_sha256'],semantic_hash(row['aggregate']),row['native_sha256'])
    baseline=[r for r in rows if r['batch']==1];candidate=[r for r in rows if r['batch']==batch]
    report={'schema_version':'single_gpu_performance_trial_v1','device':device,'frames':frames,
            'baseline_repeatable':len({signature(r) for r in baseline})==1,
            'candidate_repeatable':len({signature(r) for r in candidate})==1,
            'exact_native_match':all(r['native_sha256']==baseline[0]['native_sha256'] for r in candidate),
            'exact_records_events_aggregates_match':all(signature(r)==signature(baseline[0]) for r in candidate),
            'automatic_promotion':False,'gpu_validation':device.startswith('cuda'),'runs':rows,
            'scope':'BOUNDED_PREFIX_NOT_ACCURACY_OR_FULL_VIDEO_VALIDATION'}
    report['first_record_difference']=first_difference(
        read(output/'batch1-repeat1/measurement/result.json.gz')['records'],
        read(output/f'batch{batch}-repeat1/measurement/result.json.gz')['records'])
    write(output/'report.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('request');p.add_argument('output')
    p.add_argument('--geometry',required=True);p.add_argument('--policy',required=True)
    p.add_argument('--frames',type=int,default=256);p.add_argument('--batch',type=int,default=4)
    p.add_argument('--repetitions',type=int,default=3);p.add_argument('--device',choices=['cpu','cuda:0'],default='cuda:0')
    a=p.parse_args();print(trial(a.request,a.output,geometry=a.geometry,policy=a.policy,frames=a.frames,
                               batch=a.batch,repetitions=a.repetitions,device=a.device))

if __name__=='__main__':main()
