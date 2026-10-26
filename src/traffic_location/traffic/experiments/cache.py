"""Local completed-stage cache. Failed attempts remain inspectable, never reusable."""
import fcntl
import os
import platform
import tempfile
import subprocess
from importlib import metadata
from pathlib import Path
from ...artifacts import read, write, sha, semantic_hash, require


def runtime_identity():
    packages = {}
    for name in ('torch', 'ultralytics', 'onnxruntime-gpu', 'onnxruntime', 'opencv-python',
                 'numpy', 'scipy', 'lap', 'cupy-cuda12x', 'pandas', 'shapely', 'pyproj',
                 'osmnx', 'geopandas', 'osmium', 'networkx', 'google-cloud-bigquery'):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    identity = {'python': platform.python_version(), 'platform': platform.platform(), 'packages': packages}
    # Installed package metadata alone cannot bind GPU/runtime/backend identity.
    try:
        import torch
        identity['torch_cuda'] = torch.version.cuda
        identity['cudnn'] = torch.backends.cudnn.version()
        identity['devices'] = [dict(name=torch.cuda.get_device_name(i),
                                   capability=list(torch.cuda.get_device_capability(i)))
                               for i in range(torch.cuda.device_count())]
    except ImportError:
        identity['devices'] = []
    try:
        identity['nvidia_driver'] = subprocess.check_output(['nvidia-smi','--query-gpu=driver_version,uuid','--format=csv,noheader'], text=True, timeout=10).strip()
    except (OSError, subprocess.SubprocessError):
        identity['nvidia_driver'] = None
    return identity


def source_identity():
    root = Path(__file__).resolve().parents[2]
    return semantic_hash({str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*.py'))})


class StageCache:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def get_or_create(self, stage, identity, build):
        key = semantic_hash({'stage': stage, 'identity': identity})
        folder = self.root / stage / key
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            manifest = folder / 'complete.json'
            if manifest.exists():
                value = read(manifest)
                require(value['identity'] == identity, 'CACHE_IDENTITY_MISMATCH')
                attempt = folder / value['attempt']
                require(attempt.parent == folder and not attempt.is_symlink(), 'CACHE_PATH_INVALID')
                actual = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob('*') if p.is_file()}
                require(actual == value['files'] and all(not p.is_symlink() for p in attempt.rglob('*')),
                        'CACHE_INTEGRITY_FAILED: completed artifacts changed or missing')
                return read(attempt / 'value.json'), True
            attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=folder))
            value = build(attempt)
            write(attempt / 'value.json', value)
            files = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob('*') if p.is_file()}
            pending = folder / 'complete.tmp'
            write(pending, {'identity': identity, 'attempt': attempt.name, 'files': files})
            os.replace(pending, manifest)
            return value, False
