#!/workspace/.venvs/kaggle-cli/bin/python
"""Bounded official Kaggle SDK log/metadata retention, never bulk MP4 downloads."""
from __future__ import annotations
import argparse, gzip, hashlib, json, os, re, signal, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
import requests
from kaggle.api.kaggle_api_extended import KaggleApi, ApiListKernelSessionOutputRequest, ApiGetKernelRequest

KERNEL='chrisbiran/phase-8-tgdi-b-v3-review'
HOST='www.kaggleusercontent.com'
VIDEOS=tuple(f'{d}_{p}' for d in ('weekday','weekend') for p in ('pagi','siang','sore','malam'))
SOURCE_COMMIT='ee4bda7795fcf7b43b9dd57561ee140c60d9aa9d'
BUNDLE='2476763591f2212e9b70622753f7e01173c536c63fc2fd10f1f79ac44f4954de'
EXPECTED_CODE_CELLS_SHA256='9a15e2ec29bf016007427ca830a999d8aa6cedfdb0e020598a78123bca02233a'

def now(): return datetime.now(timezone.utc).isoformat()
def sha(data): return hashlib.sha256(data).hexdigest()
def require(value,msg):
    if not value: raise ValueError(msg)
def write(path,value,mode=0o600):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,mode)
    with os.fdopen(descriptor,'w') as dest: json.dump(value,dest,indent=2);dest.write('\n')
    os.chmod(path,mode)
def safe_text(text):
    text=re.sub(r'https?://[^\s\"<>]+','[URL REDACTED]',text)
    text=re.sub(r'(?i)(authorization|bearer|token|secret)([\s:=]+)[^\s,;\"\']+',r'\1\2[REDACTED]',text)
    return text

def api():
    result=KaggleApi();result.authenticate();return result

def log_mode(args):
    client=api();status=client.kernels_status(KERNEL)
    lines=[];finished=False;stream_error=None
    def alarm(_sig,_frame): raise TimeoutError('bounded log read ended')
    previous=signal.signal(signal.SIGALRM,alarm);signal.alarm(args.seconds)
    try:
        for item in client.kernels_logs_stream(KERNEL):
            data=str(item.get('data',''))
            lines.append(safe_text(data))
            if sum(map(len,lines))>800000: lines=lines[-400:]
        finished=True
    except TimeoutError: pass
    except requests.RequestException as error: stream_error=type(error).__name__
    finally: signal.alarm(0);signal.signal(signal.SIGALRM,previous)
    result={'claim_type':'ACTUAL_OFFICIAL_KAGGLE_LOG_STREAM_BOUNDED_READ','recorded_at_utc':now(),
        'kernel':KERNEL,'status_at_read_start':str(status.status),'expected_submission_version':2,
        'stream_version_selection':'LATEST_SESSION_WITH_EXPECTED_BUNDLE_IN_LOG_NOT_NUMERIC_PIN',
        'stream_finished':finished,'stream_error_type':stream_error,'events_retained':len(lines),'seconds_bound':args.seconds,'signed_urls_or_credentials_retained':False,
        'log':''.join(lines)}
    if args.proof: write(args.proof,result)
    print(json.dumps({k:v for k,v in result.items() if k!='log'}))
    print(result['log'][-args.tail:])

def validated_url(value):
    parsed=urlsplit(value)
    require(parsed.scheme=='https' and parsed.netloc==HOST and parsed.hostname==HOST and not parsed.username
        and not parsed.password and not parsed.fragment,'Unexpected output download host')
    return value

def listing(client):
    owner,slug=KERNEL.split('/');token=None;rows=[];logs=[]
    with client.build_kaggle_client() as sdk:
        while True:
            req=ApiListKernelSessionOutputRequest();req.user_name=owner;req.kernel_slug=slug
            # SDK version_label is a named label, not numeric version; require observed version2 around retrieval.
            req.page_size=100
            if token:req.page_token=token
            response=sdk.kernels.kernels_api_client.list_kernel_session_output(req)
            for item in response.files or []:
                name=item.file_name;p=PurePosixPath(name)
                require(not p.is_absolute() and '..' not in p.parts and not any(ord(c)<32 for c in name),
                    'Unsafe output relative filename')
                rows.append({'name':name,'url':validated_url(item.url)})
            if response.log:logs.append(safe_text(response.log))
            token=response.next_page_token
            if not token: break
    require(len({r['name'] for r in rows})==len(rows),'Duplicate output file listing')
    return rows,logs

def download(row,root):
    # Keep inherited proxy/CA verification; signed capabilities never leave local private memory/files.
    target=root/row['name'];target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.partial')
    response=requests.get(row['url'],stream=True,timeout=(15,60),allow_redirects=False)
    require(response.status_code==200,'Metadata download failed with HTTP '+str(response.status_code))
    count=0;digest=hashlib.sha256()
    with temp.open('wb') as dest:
        for block in response.iter_content(1024*1024):
            if not block:continue
            count+=len(block);require(count<=80*1024**2,'Metadata file exceeds bound')
            digest.update(block);dest.write(block)
    response.close();temp.replace(target)
    return {'path':row['name'],'size_bytes':count,'sha256':digest.hexdigest()}

def observed_latest_identity(client):
    owner,slug=KERNEL.split('/')
    with client.build_kaggle_client() as sdk:
        req=ApiGetKernelRequest();req.user_name=owner;req.kernel_slug=slug
        response=sdk.kernels.kernels_api_client.get_kernel(req)
    require(response.metadata.current_version_number==2 and response.metadata.ref==KERNEL,
        'Observed latest kernel version differs from expected submission2')
    notebook=json.loads(response.blob.source)
    code_cells=[''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type']=='code']
    digest=sha(json.dumps(code_cells,separators=(',',':')).encode())
    require(digest==EXPECTED_CODE_CELLS_SHA256,'Observed remote notebook code cells differ from submitted packet')
    return {'claim_type':'ACTUAL_OFFICIAL_GET_KERNEL_LATEST_METADATA',
        'recorded_at_utc':now(),'current_version_number':response.metadata.current_version_number,
        'ref':response.metadata.ref,'remote_code_cell_count':len(code_cells),
        'remote_code_cells_sha256':digest,'matches_submitted_version2_code_cells':True}

def fetch_mode(args):
    root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=True)
    client=api();status=client.kernels_status(KERNEL)
    require(str(status.status).endswith('.COMPLETE') or str(status.status).endswith('.COMPLETED'),
        'Kernel is not terminal-complete; no metadata fetched')
    identity_before=observed_latest_identity(client)
    rows,logs=listing(client)
    require(rows,'No completed output files')
    mp4=[r for r in rows if r['name'].endswith('-b-v3-annotated.mp4')]
    require(len(mp4)==8,'Expected exactly eight actual rendered MP4 output files')
    downloads=[]
    for vid in VIDEOS:
        matches=[r for r in mp4 if PurePosixPath(r['name']).name==vid+'-b-v3-annotated.mp4']
        require(len(matches)==1,'MP4 output video IDs differ')
        downloads.append({'video_id':vid,'url':matches[0]['url']})
    write(args.capabilities,downloads)
    nonvideo=[r for r in rows if not r['name'].lower().endswith(('.mp4','.avi','.mov','.mkv','.webm'))]
    allowed={'.json','.gz','.log','.txt','.csv','.py','.ipynb','.md'}
    small=[r for r in nonvideo if PurePosixPath(r['name']).suffix in allowed]
    omitted=[{'path':r['name'],'reason':'NON_METADATA_EXTENSION_NOT_DOWNLOADED'} for r in nonvideo if r not in small]
    with ThreadPoolExecutor(max_workers=4) as executor:
        retained=list(executor.map(lambda r:download(r,root),small))
    if logs:
        p=root/'official_kernel_log_redacted.txt';p.write_text('\n'.join(logs),encoding='utf-8')
        retained.append({'path':p.name,'size_bytes':p.stat().st_size,'sha256':sha(p.read_bytes()),'url_redacted':True})
    identity_after=observed_latest_identity(client)
    proof={'claim_type':'ACTUAL_OFFICIAL_KAGGLE_VERSION_2_METADATA_RETRIEVAL','recorded_at_utc':now(),
        'kernel':KERNEL,'expected_submission_version':2,'observed_current_version_before':identity_before,
        'observed_current_version_after':identity_after,
        'output_api_version_selection':'LATEST_SESSION_OUTPUT_BOUND_TO_OBSERVED_VERSION_2_AND_EXACT_CODE_CELLS_NOT_NUMERIC_VERSION_LABEL',
        'status_at_retrieval':str(status.status),
        'retrieval_helper':{'path':'results/b_v3/verification/retrieve_kaggle_execution.py','sha256':sha(Path(__file__).read_bytes())},
        'executed_source_commit':SOURCE_COMMIT,'expected_source_bundle_binding_sha256':BUNDLE,
        'downloaded_metadata_files':retained,'omitted_non_metadata_files':omitted,'mp4_listed_not_downloaded':8,
        'signed_urls_or_credentials_retained':False,'private_capability_file_permission':'0600',
        'original_output_names':[r['name'] for r in rows]}
    write(root/'metadata_retrieval.json',proof)
    print(json.dumps({'status':'ACTUAL_METADATA_FETCHED','metadata_files':len(retained),
        'metadata_bytes':sum(r['size_bytes'] for r in retained),'mp4_count':8,'output':str(root)}))

def build_mode(args):
    metadata=Path(args.output).resolve();repo=Path(args.repo).resolve()
    packet=json.loads((Path(args.packet)/'source_bundle_manifest.json').read_text())
    require(packet['source_bundle_binding_sha256']==BUNDLE,'Packet source bundle differs')
    completed=[]
    for path in metadata.rglob('batch_report.json'):
        value=json.loads(path.read_text())
        if value.get('schema_version')=='phase8_b_v3_batch_v1':completed.append((path,value))
    require(len(completed)==1,'Exactly one B v3 batch report required')
    report_path,report=completed[0];run=report_path.parent
    require(report['all_eight_completed'] and report['all_selected_completed'],'Not all eight completed')
    require(report['frames_processed']==72590,'Unexpected frame total')
    require(report['render_requested'] and not report['new_detector_tracker_reid_execution'],'Wrong execution scope')
    require(report['source_files_unchanged_during_execution'] and report['original_inputs_and_reviews_unchanged_during_execution'],
        'Sources or inputs changed during execution')
    require(len(report['videos'])==8 and {r['video_id'] for r in report['videos']}==set(VIDEOS),'Actual video set differs')
    provenance=list(metadata.rglob('b_v3_source_provenance.json'))
    require(len(provenance)==1,'Exactly one actual bootstrap provenance required')
    extracted=json.loads(provenance[0].read_text())
    require(extracted['source_bundle_binding_sha256']==BUNDLE,'Actual source bundle differs')
    require(extracted['source_files']==packet['source_files'],'Actual extracted source file set differs')
    required=set(('phase_8_b_v2_counting.py','phase_8_b_v2_annotation.py','phase_8_b_v2_batch.py',
        'phase_8_b_v3_counting.py','phase_8_b_v3_annotation.py','phase_8_b_v3_batch.py',
        'phase_5_geometry_helpers.py','phase_8_annotation_helpers.py','phase_8_annotation_batch.py'))
    require(len(report['executed_source_files'])==9,'Exactly nine executed sources required')
    require({PurePosixPath(path).name for path in report['executed_source_files']}==required,
        'Executed source filename set differs')
    sources=[]
    for original,item in report['executed_source_files'].items():
        name=PurePosixPath(original).name;relative='notebooks/'+name
        require(name in required,'Unexpected executed source')
        data=gzip.decompress((run/item['retained_path']).read_bytes())
        require(sha(data)==item['sha256']==sha((repo/relative).read_bytes()),'Actual/source file hash differs')
        old=subprocess.run(['git','-C',str(repo),'show',SOURCE_COMMIT+':'+relative],capture_output=True,check=True).stdout
        require(sha(old)==item['sha256'],'Executed-commit source differs')
        require(packet['source_files'][relative]['sha256']==item['sha256'],'Source packet differs')
        sources.append({'path':relative,'sha256':item['sha256']})
    configurations=[]
    for relative in ('results/b_v3/input/review_decisions.json','results/b_v3/config/policy.json'):
        data=(repo/relative).read_bytes();digest=sha(data)
        actual=(provenance[0].parent/relative).read_bytes()
        require(sha(actual)==digest==packet['source_files'][relative]['sha256'],'Actual configuration differs')
        old=subprocess.run(['git','-C',str(repo),'show',SOURCE_COMMIT+':'+relative],capture_output=True,check=True).stdout
        require(sha(old)==digest,'Executed-commit config differs')
        configurations.append({'path':relative,'sha256':digest})
    require(report['policy_sha256']==configurations[1]['sha256'] and report['reviews_sha256']==configurations[0]['sha256'],
        'Report config hashes differ')
    assets=[];comparisons=[]
    for vid in VIDEOS:
        row=next(r for r in report['videos'] if r['video_id']==vid)
        require(row['status']=='completed','Video did not complete')
        annotation=json.loads((run/vid/'annotation_report.json').read_text())
        require(annotation==row['annotation'],'Embedded and per-video annotation reports differ')
        output=annotation['output_video'];aggregate=row['aggregate']
        require(output['frames_written']==output['frames_redecoded']==row['frames'],'Full actual decode frame mismatch')
        require(annotation['frame_pixel_and_raw_link_verified_every_frame'] and annotation['inputs_unchanged_after_render'],
            'Video source measurement proof missing')
        require(not annotation['new_detector_tracker_encoder_inference'] and not annotation['counting_rerun_by_renderer'],
            'Renderer scope differs')
        require(annotation['final_accepted']==aggregate['total'] and annotation['final_measured']==aggregate['measured_total']
            and annotation['final_inferred']==aggregate['inferred_total'],'Annotation/ledger totals differ')
        day,period=vid.split('_');assets.append({'video_id':vid,
            'filename':f'TGDI-{day.upper()}-{period.upper()}-b-v3-annotated.mp4',
            'sha256':output['sha256'],'size_bytes':output['size_bytes'],'frame_count':output['frames_redecoded'],
            'source_output_path':output['path'],'operational_total':aggregate['total'],
            'measured_total':aggregate['measured_total'],'inferred_total':aggregate['inferred_total'],
            'vehicle_total':aggregate['vehicle_total'],'pedestrian_total':aggregate['pedestrian_total'],
            'pending_unique_unit_episode_passages':row['pending_unique_unit_episode_passages'],
            'unknown_person_role_keys':row['unknown_person_role_keys'],
            'codec':output['codec'],'fps':output['fps'],'width':output['width'],'height':output['height']})
        actual_count=run/vid/'counting_result.json'
        local_count=Path(args.local_replay)/vid/'counting_result.json'
        actual_data=actual_count.read_bytes();local_data=local_count.read_bytes()
        same=sha(actual_data)==sha(local_data)
        actual_parsed=json.loads(actual_data);local_parsed=json.loads(local_data)
        require(actual_parsed==local_parsed,'Actual Kaggle counting differs from final local replay')
        comparisons.append({'video_id':vid,'local_sha256':sha(local_data),'actual_kaggle_sha256':sha(actual_data),
            'exact_bytes_equal':same,'parsed_entire_result_equal':True})
    manifest={'schema_version':'phase8_b_v3_delivery_v1','repository':'unChris666/traffic-vehicle-counter-IDM-LOC',
        'claim_type':'ACTUAL_COMPLETED_KAGGLE_ANNOTATED_VIDEOS_NOT_ACCURACY',
        'recorded_at_utc':now(),'source_commit':SOURCE_COMMIT,'executed_source_commit':SOURCE_COMMIT,
        'source_bundle_binding_sha256':BUNDLE,'executed_source_files':sorted(sources,key=lambda r:r['path']),
        'executed_configuration_files':configurations,
        'kaggle_kernel':KERNEL,'kaggle_kernel_version':2,'kaggle_run_id':report['run_id'],
        'all_eight_completed':True,'frames_processed':72590,
        'new_detector_tracker_reid_execution':False,'original_model_caches_modified':False,
        'mp4_hash_provenance':'ACTUAL_KAGGLE_RENDERER_FULL_DECODE_ANNOTATION_REPORTS_NOT_LOCAL_ENCODINGS',
        'operational_total':sum(r['operational_total'] for r in assets),
        'measured_total':sum(r['measured_total'] for r in assets),
        'inferred_total':sum(r['inferred_total'] for r in assets),
        'vehicle_total':sum(r['vehicle_total'] for r in assets),'pedestrian_total':sum(r['pedestrian_total'] for r in assets),
        'physical_identity_or_counting_accuracy_established':False,
        'release_tag':'phase8-b-v3-tgdi-review-v1','assets':assets}
    write(args.manifest,manifest,mode=0o644)
    proof={'claim_type':'ACTUAL_KAGGLE_LOCAL_LEDGER_AND_FROZEN_SOURCE_COMPARISON',
        'recorded_at_utc':now(),'kernel':KERNEL,'kernel_version':2,'run_id':report['run_id'],
        'source_bundle_binding_sha256':BUNDLE,'source_files_verified':9,'configuration_files_verified':2,
        'entire_counting_result_json_equal_all_eight':True,'videos':comparisons,
        'all_mp4s_full_frame_decoded_in_kaggle':True,'mp4s_downloaded_in_codex':False,
        'delivery_manifest_sha256':sha(Path(args.manifest).read_bytes())}
    write(args.comparison_proof,proof,mode=0o644)
    print(json.dumps({'status':'ACTUAL_DELIVERY_MANIFEST_BUILT','manifest':args.manifest,'assets':8,
        'frames':72590,'operational_total':manifest['operational_total'],
        'measured_total':manifest['measured_total'],'inferred_total':manifest['inferred_total'],
        'entire_actual_local_counting_equal':True}))

def retain_mode(args):
    metadata=Path(args.output).resolve();target=Path(args.retained).resolve()
    require(not target.exists(),'Retention target must be new')
    fetch_proof=json.loads((metadata/'metadata_retrieval.json').read_text())
    require(fetch_proof['kernel']==KERNEL and fetch_proof['expected_submission_version']==2,'Wrong retrieved execution')
    require(fetch_proof['signed_urls_or_credentials_retained'] is False,'Unsafe metadata provenance')
    target.mkdir(parents=True)
    mappings=[]
    expected={row['path']:row for row in fetch_proof['downloaded_metadata_files']}
    expected['metadata_retrieval.json']={'path':'metadata_retrieval.json','sha256':sha((metadata/'metadata_retrieval.json').read_bytes())}
    for relative,row in sorted(expected.items()):
        source=metadata/relative;data=source.read_bytes()
        require(sha(data)==row['sha256'],'Downloaded metadata changed before retention')
        require(HOST.encode() not in data,'Signed-download host unexpectedly retained')
        dest=target/'files'/(relative+'.gz');dest.parent.mkdir(parents=True,exist_ok=True)
        compressed=gzip.compress(data,mtime=0);dest.write_bytes(compressed)
        require(gzip.decompress(dest.read_bytes())==data,'Exact retention roundtrip failed')
        mappings.append({'original_output_path':relative,'original_sha256':sha(data),'original_size_bytes':len(data),
            'retained_path':dest.relative_to(target).as_posix(),'retained_sha256':sha(compressed),
            'retained_size_bytes':len(compressed),'encoding':'GZIP_MTIME_0_EXACT_ORIGINAL_BYTES',
            'source_kind':'REDACTED_OFFICIAL_LOG_DIAGNOSTIC' if row.get('url_redacted') else
                'RETRIEVAL_PROVENANCE' if relative=='metadata_retrieval.json' else 'EXACT_KAGGLE_OUTPUT_DOWNLOAD'})
    proof={'schema_version':'phase8_b_v3_actual_kaggle_retention_v1',
        'claim_type':'EXACT_ACTUAL_KAGGLE_METADATA_RETENTION_NOT_REEXECUTION',
        'recorded_at_utc':now(),'kernel':KERNEL,'kernel_version':2,'executed_source_commit':SOURCE_COMMIT,
        'source_bundle_binding_sha256':BUNDLE,'file_count':len(mappings),
        'original_bytes':sum(r['original_size_bytes'] for r in mappings),
        'retained_bytes':sum(r['retained_size_bytes'] for r in mappings),
        'mp4_videos_retained_here':False,'signed_urls_or_credentials_retained':False,
        'mp4_delivery':'GITHUB_RELEASE_ASSETS_SEPARATE_FROM_GIT','files':mappings}
    write(target/'retention_manifest.json',proof,mode=0o644)
    print(json.dumps({'status':'ACTUAL_METADATA_EXACT_BYTES_RETAINED','files':len(mappings),
        'original_bytes':proof['original_bytes'],'retained_bytes':proof['retained_bytes'],'path':str(target)}))

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
    l=s.add_parser('logs');l.add_argument('--seconds',type=int,default=45);l.add_argument('--tail',type=int,default=12000);l.add_argument('--proof')
    f=s.add_parser('fetch');f.add_argument('--output',required=True);f.add_argument('--capabilities',required=True)
    b=s.add_parser('build');b.add_argument('--output',required=True);b.add_argument('--repo',required=True);b.add_argument('--packet',required=True)
    b.add_argument('--local-replay',required=True);b.add_argument('--manifest',required=True);b.add_argument('--comparison-proof',required=True)
    t=s.add_parser('retain');t.add_argument('--output',required=True);t.add_argument('--retained',required=True)
    args=p.parse_args();require(1<=getattr(args,'seconds',45)<=45,'Log bound must be at most45seconds')
    try: {'logs':log_mode,'fetch':fetch_mode,'build':build_mode,'retain':retain_mode}[args.mode](args)
    except Exception as error:
        # No HTTP exception/stringification: upstream diagnostic URLs can be capabilities.
        print(json.dumps({'status':'FAILED','error_type':type(error).__name__,
            'safe_reason':str(error) if type(error) is ValueError else 'External operation failed; no credentials retained'}))
        raise SystemExit(1)
if __name__=='__main__':main()
