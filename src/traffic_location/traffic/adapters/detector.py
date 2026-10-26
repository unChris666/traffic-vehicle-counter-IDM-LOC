"""Isolated model process port, with retained logs and explicit timeout."""
import os
from pathlib import Path
import subprocess


def execute_worker(request_path, worker_output, *, python_executable, log_path, timeout_seconds, gpu_id=None):
    source_root = str(Path(__file__).resolve().parents[3])
    with Path(log_path).open('w') as log:
        import time
        from ...artifacts import read
        progress_path = Path(worker_output).parent / 'progress.json'
        started = time.monotonic()
        last = None
        env={**os.environ, 'PYTHONPATH': source_root}
        if gpu_id is not None:env['CUDA_VISIBLE_DEVICES']=str(gpu_id)
        with subprocess.Popen([str(python_executable), '-B', '-m',
                'traffic_location.traffic.inference_worker', str(Path(request_path).resolve()), str(worker_output)],
                env=env, stdout=log, stderr=subprocess.STDOUT) as process:
            try:
                while True:
                    remaining = timeout_seconds - (time.monotonic() - started)
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(process.args, timeout_seconds)
                    try:
                        return process.wait(timeout=min(10, remaining))
                    except subprocess.TimeoutExpired:
                        if progress_path.exists():
                            value = read(progress_path)
                            if value != last:
                                print({'video': Path(request_path).parent.name, **value}, flush=True)
                                last = value
            except BaseException:
                process.kill()
                process.wait()
                raise
