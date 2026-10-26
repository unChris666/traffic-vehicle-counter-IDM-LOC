"""One active video per visible GPU. Each inference launches a fresh child process."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from queue import Queue,Empty


def visible_gpu_ids():
    # Discover in a subprocess: the coordinator never initializes CUDA state.
    count=json.loads(subprocess.check_output([sys.executable,'-c',
        'import torch,json;print(json.dumps(torch.cuda.device_count()))'],text=True))
    mask=os.environ.get('CUDA_VISIBLE_DEVICES')
    ids=[v.strip() for v in mask.split(',')] if mask is not None else [str(i) for i in range(count)]
    return ids[:count]


def run_video_jobs(jobs,worker,*,gpu_ids=None):
    """worker(job,gpu_id); ordered receipts; one failure does not stop other videos."""
    jobs=list(jobs)
    ids=list(visible_gpu_ids() if gpu_ids is None else gpu_ids)
    if not jobs:return []
    if not ids or len(set(map(str,ids)))!=len(ids):raise ValueError('Unique visible GPU IDs required; no CPU fallback')
    queue=Queue()
    for i,job in enumerate(jobs):queue.put((i,job))
    results=[None]*len(jobs)
    def lane(gpu):
        while True:
            try:i,job=queue.get_nowait()
            except Empty:return
            try:
                value=worker(job,gpu)
                results[i]={'execution_status':'SUCCEEDED','gpu_id':str(gpu),'result':value}
            except Exception as exc:
                results[i]={'execution_status':'FAILED','gpu_id':str(gpu),
                            'error_type':type(exc).__name__,'message':str(exc)}
            finally:queue.task_done()
    with ThreadPoolExecutor(max_workers=min(len(ids),len(jobs))) as pool:
        futures=[pool.submit(lane,gpu) for gpu in ids[:len(jobs)]]
        for future in futures:future.result()
    return results
