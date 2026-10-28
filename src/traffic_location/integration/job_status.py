"""Bounded status observations. Liveness is never interpreted as progress."""
import os,time
from pathlib import Path
from ..artifacts import read,write

LABELS={'traffic_runtime_validation':'Validasi runtime Traffic','traffic_model_preparation':'Menyiapkan bobot Traffic','traffic_gpu_discovery':'Memeriksa slot GPU Traffic','traffic_videos':'Memproses video Traffic','engine_execution':'Menjalankan engine yang dipilih','bq_snapshot':'Membaca snapshot toko/kompetitor','pbf_download_verify':'Menyiapkan PBF lokal',
'pbf_extract_and_parse':'Ekstraksi dan pembacaan wilayah PBF','source_bundle_freeze':'Membekukan sumber job',
'source_cache_upload':'Menyimpan snapshot sumber ke GCS','gpu_preflight':'Uji GPU',
'runtime_validation':'Validasi runtime','normalization':'Normalisasi bangunan',
'graph_routing':'Graf dan routing','market_allocation':'Alokasi pasar/kompetitor',
'gpu_release':'Melepas resource GPU','renderer':'Membuat peta HTML','export':'Menyelesaikan artefak',
'ppac_calculation':'Menghitung PPAC','publication':'Publikasi hasil GCS/BQ','request_snapshot':'Menyimpan input job ke GCS'}

def stage(root,name,status='RUNNING',**extra):
    path=Path(root)/'job-status.json';now=time.time();previous={}
    try:previous=read(path)
    except (OSError,ValueError):pass
    started=previous.get('stage_started_epoch',now) if previous.get('stage')==name else now
    events=(previous.get('events',[])+[{'stage':name,'status':status,'at':now,'duration_seconds':max(0,now-started)}])[-100:]
    value={'job_id':previous.get('job_id'),'input_sha256':previous.get('input_sha256'),'events':events,'schema_version':'job_status_v1','stage':name,'status':status,'pid':os.getpid(),
           'stage_started_epoch':started,'updated_epoch':now,**extra}
    temporary=path.with_suffix('.partial');write(temporary,value);temporary.replace(path)
    return value

def observation(pid):
    try:
        import psutil
        process=psutil.Process(pid);processes=[process]+process.children(recursive=True)
        cpu=0.;rss=0
        for p in processes:
            try:
                t=p.cpu_times();cpu+=t.user+t.system;rss+=p.memory_info().rss
            except psutil.Error:pass
        return {'process_alive':process.is_running() and process.status()!=psutil.STATUS_ZOMBIE,
                'cpu_seconds_current_processes':round(cpu,2),'rss_bytes_current_processes':rss,
                'scope':'POINT_IN_TIME_INCLUDES_CURRENT_CHILDREN_NOT_PEAK_OR_PROGRESS_PROOF'}
    except Exception as error:
        if type(error).__name__ in ('NoSuchProcess','ZombieProcess'):return {'process_alive':False,'scope':'PROCESS_EXITED'}
        return {'process_alive':None,'scope':'OBSERVATION_UNAVAILABLE'}

def lines(base,since):
    found=[];visited=0
    # Do not recursively scan national/source datasets on every UI heartbeat.
    for folder,dirs,files in os.walk(base):
        dirs[:]=[d for d in dirs if d not in {'area-source','national','uploads','models','work','computation','cloud-payload','inputs','measurement'}]
        visited+=1
        if visited>3000:break
        for name in [n for n in files if n in ('job-status.json','checkpoint.json','worker-heartbeat.json','area-trace.json') or n.endswith('progress.json')]:
            if name not in files:continue
            p=Path(folder)/name
            try:
                if p.stat().st_mtime<since or p.stat().st_size>65536:continue
                value=read(p)
                if not isinstance(value,dict):continue
                value.setdefault('status',value.get('execution_status','UNKNOWN'))
                found.append((p.stat().st_mtime,p,value))
            except (OSError,ValueError):pass
    output=[]
    for _,path,v in sorted(found,key=lambda x:x[0],reverse=True)[:10]:
        now=time.time();started=v.get('stage_started_epoch',v.get('updated_epoch',now));age=now-v.get('updated_epoch',now)
        item=('Job '+v['job_id']+' | ' if v.get('job_id') else '')+LABELS.get(v.get('stage'),v.get('stage','worker'))+' — '+v.get('status','UNKNOWN')
        if v.get('completed') is not None:item+=f" | {v['completed']}/{v.get('total','?')} {v.get('unit','frame')}"
        if v.get('fps_actual') is not None:item+=f" | {v['fps_actual']:.1f} FPS"
        end=now if v.get('status')=='RUNNING' else v.get('updated_epoch',now)
        item+=f' | durasi tahap {max(0,end-started):.0f} detik | umur checkpoint {max(0,age):.0f} detik'
        if v.get('pid'):
            o=observation(v['pid']);item+=' | proses '+('hidup' if o['process_alive'] else 'berhenti/tidak teramati')
            if 'cpu_seconds_current_processes' in o:item+=f" | CPU kumulatif proses aktif {o['cpu_seconds_current_processes']:.1f}s | RAM saat ini {o['rss_bytes_current_processes']/1024**2:.0f} MiB"
        output.append(item)
    if output:output.append(gpu_line())
    if output:output.append('Proses hidup/checkpoint lama bukan bukti komputasi maju; persentase/ETA tidak dibuat jika tidak terukur.')
    return output


_GPU_CACHE=(0.,'')
def gpu_line():
    global _GPU_CACHE
    now=time.time()
    if now-_GPU_CACHE[0]<15:return _GPU_CACHE[1]
    try:
        import subprocess,csv,io
        result=subprocess.run(['nvidia-smi','--query-gpu=index,name,utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,check=True)
        rows=list(csv.reader(io.StringIO(result.stdout)))
        text='; '.join('GPU '+r[0].strip()+' '+r[1].strip()+f': utilisasi {float(r[2]):.0f}%, VRAM {float(r[3]):.0f}/{float(r[4]):.0f} MiB' for r in rows if len(r)==5)
        if text:text+=' (runtime saat ini; bukan atribusi khusus job atau bukti progres)'
    except Exception:text='Observasi GPU tidak tersedia; ini tidak menentukan status engine.'
    _GPU_CACHE=(now,text)
    return text
