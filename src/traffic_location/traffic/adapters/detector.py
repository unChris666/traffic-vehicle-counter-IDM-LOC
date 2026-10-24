"""Isolated model process port, with retained logs and explicit timeout."""
import os
from pathlib import Path
import subprocess


def execute_worker(request_path, worker_output, *, python_executable, log_path, timeout_seconds):
    source_root = str(Path(__file__).resolve().parents[3])
    with Path(log_path).open('w') as log:
        return subprocess.run([str(python_executable), '-B', '-m',
            'traffic_location.traffic.inference_worker', str(Path(request_path).resolve()), str(worker_output)],
            env={**os.environ, 'PYTHONPATH': source_root}, stdout=log, stderr=subprocess.STDOUT,
            timeout=timeout_seconds, check=False).returncode
