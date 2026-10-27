"""Best-effort observations, never admission thresholds or accuracy claims."""
import csv
import io
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys


def snapshot(root):
    value={'schema_version':'runtime_resources_v1',
           'sampling_scope':'POINT_IN_TIME_NOT_A_CAPACITY_BENCHMARK',
           'pid':os.getpid()}
    try:
        disk=shutil.disk_usage(root)
        value['disk']={'total_bytes':disk.total,'free_bytes':disk.free}
    except OSError:value['disk']={'status':'UNAVAILABLE'}
    scale=1 if sys.platform=='darwin' else 1024
    value['process_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*scale
    value['rss_scope']='THIS_PROCESS_ONLY_EXCLUDES_CHILDREN'
    try:
        fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in Path('/proc/meminfo').read_text().splitlines()}
        value['host_memory_available_bytes']=int(fields['MemAvailable'].split()[0])*1024
    except (OSError,KeyError,ValueError):pass
    try:
        command=['nvidia-smi','--query-gpu=index,uuid,memory.used,memory.total,utilization.gpu',
                 '--format=csv,noheader,nounits']
        result=subprocess.run(command,capture_output=True,text=True,timeout=3,check=True)
        rows=list(csv.reader(io.StringIO(result.stdout)))
        value['gpus']=[{'index':r[0].strip(),'uuid':r[1].strip(),'memory_used_mib':float(r[2]),
                        'memory_total_mib':float(r[3]),'utilization_percent':float(r[4])} for r in rows if len(r)==5]
        value['gpu_status']='OBSERVED'
    except (OSError,ValueError,subprocess.SubprocessError):value['gpu_status']='UNAVAILABLE'
    value['gpu_scope']='HOST_VISIBLE_DEVICES_NOT_PROCESS_ATTRIBUTED; includes non-Torch allocations'
    return value


def record(root,name):
    """Diagnostics must not turn an otherwise valid engine result into failure."""
    from .artifacts import write
    try:write(Path(root)/('resources-'+name+'.json'),snapshot(root))
    except (OSError,ValueError):pass
