"""Fresh old-wheel vs batch150 comparison, on one video/device. No cache/fallback."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from ...artifacts import read,write,sha,require,semantic_hash
from .benchmark import first_difference

COUNT_SCRIPT = '''import sys,time
from traffic_location.artifacts import read,write
from traffic_location.traffic.application.pipeline import run
q=read(sys.argv[1]);start=time.monotonic()
r=run(q,root=sys.argv[2]);write(sys.argv[3],r)
write(sys.argv[4],{'counting_wall_seconds':time.monotonic()-start})
'''


def monitored(command,folder,source,timeout=5400):
    start=time.monotonic();last=None
    with (folder/'worker.log').open('w') as log:
        with subprocess.Popen(command,env={**os.environ,'PYTHONPATH':str(source)},stdout=log,stderr=subprocess.STDOUT) as proc:
            try:
                while True:
                    try:
                        code=proc.wait(timeout=min(15,max(.1,timeout-(time.monotonic()-start))))
                        return code,time.monotonic()-start
                    except subprocess.TimeoutExpired:
                        if time.monotonic()-start>=timeout:raise
                        lines=(folder/'worker.log').read_text(errors='replace').splitlines()
                        events=[s for s in lines if s.startswith('{')]
                        latest=events[-1] if events else None
                        if latest and latest!=last:print(latest,flush=True);last=latest
            except BaseException:
                proc.kill();proc.wait();raise


def run_one(base,folder,source,geometry,policy,frames,*,batch,baseline,video_id):
    folder.mkdir(parents=True)
    q=copy.deepcopy(base);q.update(frame_limit=frames,start_frame=0,device='cuda:0',half=False)
    if baseline:q.pop('performance',None)
    else:q['performance']={'batch_size':batch}
    write(folder/'producer.json',q)
    print('START',folder.name,'frames',frames,'batch',batch,flush=True)
    code,seconds=monitored([sys.executable,'-u','-m','traffic_location.traffic.inference_worker',
                           str(folder/'producer.json'),str(folder/'measurement')],folder,source)
    if code:
        text=(folder/'worker.log').read_text(errors='replace')
        return {'status':'FAILED','batch':batch,'baseline':baseline,'frames':frames,'inference_process_seconds':seconds,
                'reason':'GPU_OUT_OF_MEMORY' if 'out of memory' in text.lower() else 'WORKER_FAILED',
                'log':str(folder/'worker.log'),'tail':text.splitlines()[-15:]}
    ref=folder/'measurement/result.json.gz';m=read(ref)
    require(m['frames']==frames and [r['frame_index'] for r in m['records']]==list(range(frames)), 'Frame coverage differs')
    meta=m['metadata'];source_identity={'video_sha256':q['artifacts']['video']['sha256'],'records_sha256':sha(ref),
        'geometry_sha256':sha(geometry),'width':meta['width'],'height':meta['height'],'variant':'raw','parent_run_id':'t7sl_batch150_trial'}
    request={'schema_version':'traffic_request_v1','profile':'machine','measurement_format':'fresh_v1','video_id':video_id,
        'frame_count':frames,'source_identity':source_identity,'source_manifest_sha256':semantic_hash({'video':q['artifacts']['video']['sha256'],'scope':frames}),
        'artifacts':{k:{'path':str(p),'sha256':sha(p)} for k,p in [('measurements',ref),('geometry',geometry),('policy',policy)]}}
    write(folder/'count-request.json',request)
    script=folder/'count.py';script.write_text(COUNT_SCRIPT)
    with (folder/'counting.log').open('w') as stream:
        result=subprocess.run([sys.executable,str(script),str(folder/'count-request.json'),str(folder),
            str(folder/'count-result.json.gz'),str(folder/'counting-time.json')],
            env={**os.environ,'PYTHONPATH':str(source)},stdout=stream,stderr=subprocess.STDOUT,timeout=5400)
    if result.returncode:return {'status':'FAILED','reason':'COUNTING_FAILED','log':str(folder/'counting.log'),'batch':batch}
    native=read(folder/'count-result.json.gz')['native']
    return {'status':'SUCCEEDED','batch':batch,'baseline':baseline,'frames':frames,
        'inference_process_seconds':seconds,**read(folder/'counting-time.json'),
        'records_sha256':m['records_semantic_sha256'],'native_sha256':semantic_hash(native),
        'aggregate':native['aggregate'],'environment':m['environment'],'folder':str(folder)}


def compare(a,b):
    if a['status']!='SUCCEEDED' or b['status']!='SUCCEEDED':return {'status':'NOT_COMPARABLE','baseline':a,'candidate':b}
    x=Path(a['folder']);y=Path(b['folder'])
    ma=read(x/'measurement/result.json.gz');mb=read(y/'measurement/result.json.gz')
    na=read(x/'count-result.json.gz')['native'];nb=read(y/'count-result.json.gz')['native']
    return {'status':'COMPARED','exact_records_match':ma['records']==mb['records'],'exact_native_match':na==nb,
        'aggregate_match':na['aggregate']==nb['aggregate'],'first_record_difference':first_difference(ma['records'],mb['records']),
        'first_event_difference':first_difference(na['events'],nb['events']),
        'first_decision_difference':first_difference(na['decisions'],nb['decisions']),
        'baseline':a,'candidate':b,'process_speed_ratio':a['inference_process_seconds']/b['inference_process_seconds']}


def trial(base,output,baseline_source,candidate_source,geometry,policy,frames,video_id):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    geometry=Path(geometry).resolve();policy=Path(policy).resolve()
    require(frames>=300,'Video shorter than preflight scope')
    report={'schema_version':'t7sl_batch150_vs_basic_v1','video_id':video_id,'frames':frames,
            'automatic_promotion':False,'device':'cuda:0','preflight':[],'full_video':None}
    for repeat in range(3):
        pair=[]
        for baseline,size,source in [(True,1,baseline_source),(False,150,candidate_source)]:
            row=run_one(base,output/f'prefix300-r{repeat+1}-batch{size}',source,geometry,policy,300,
                        batch=size,baseline=baseline,video_id=video_id)
            pair.append(row);write(output/'latest-job.json',row)
        report['preflight'].append(compare(*pair));write(output/'report.json',report)
        if any(r['status']!='SUCCEEDED' for r in pair):
            report['full_video']={'status':'NOT_RUN','reason':'PREFLIGHT_FAILED_NO_SILENT_BATCH_REDUCTION'}
            write(output/'report.json',report);return report
    pair=[]
    for baseline,size,source in [(True,1,baseline_source),(False,150,candidate_source)]:
        row=run_one(base,output/f'full-batch{size}',source,geometry,policy,frames,
                    batch=size,baseline=baseline,video_id=video_id)
        pair.append(row);write(output/'latest-job.json',row)
    report['full_video']=compare(*pair)
    report['full_video_reproducibility']='NOT_VALIDATED_SINGLE_PAIR_ONLY'
    write(output/'report.json',report);return report
