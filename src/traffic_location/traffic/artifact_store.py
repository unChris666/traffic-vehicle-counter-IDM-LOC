"""Artifact port: atomic immutable JSON, CSV, images and video publication.

Local storage is implemented and tested. GCS can implement this same port;
this module never provisions a bucket or guesses credentials.
"""
from pathlib import Path
from typing import Protocol
import gzip
import fcntl
import hashlib
import os
import shutil
import tempfile
from .contracts.source import ArtifactRef
from ..artifacts import require, read, write, sha, canonical
from ..persistence import verify_manifest, reopen_traffic


class ArtifactStore(Protocol):
    def publish_result(self, key: str, files: dict, *, metadata: dict) -> dict: ...
    def reopen(self, key: str) -> dict: ...
    def exists(self, key: str) -> bool: ...
    def read_document(self, key: str, name: str) -> dict: ...


def _payload_digest(name, value):
    if isinstance(value, ArtifactRef):
        require(Path(value.path).is_file() and sha(value.path) == value.sha256, 'Binary artifact source differs')
        return value.sha256
    data = value if isinstance(value, bytes) else canonical(value)
    if not isinstance(value, bytes) and name.endswith('.gz'):
        data = gzip.compress(data, mtime=0)
    return hashlib.sha256(data).hexdigest()


class LocalArtifactStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        require(isinstance(key, str) and bool(key), 'Storage key required')
        path = self.root / key
        require(bool(Path(key).parts) and Path(key).parts[0] != '.locks', 'Reserved/empty storage key')
        require(not Path(key).is_absolute() and path.resolve().is_relative_to(self.root) and path.resolve() != self.root, 'Unsafe storage key')
        require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink storage path forbidden')
        return path

    def publish_result(self, key: str, files: dict, *, metadata: dict) -> dict:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # A POSIX advisory lock is released by the OS even after worker crash.
        # Lock files persist: unlinking them can permit two different inodes
        # to be locked concurrently during a retry race.
        lock_root = self.root / '.locks'
        lock_root.mkdir(exist_ok=True)
        require(not lock_root.is_symlink(), 'Unsafe lock directory')
        lock = lock_root / (hashlib.sha256(key.encode()).hexdigest() + '.lock')
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(fd)
            raise
        stage = None
        try:
            # Compute all payload digests before allowing a success publication.
            expected = {name: _payload_digest(name, value) for name, value in files.items()}
            if path.exists():
                manifest = verify_manifest(path)
                require(manifest['metadata'] == metadata, 'Existing job fingerprint differs; use a new revision')
                require(expected == {r['path']: r['sha256'] for r in manifest['files']}, 'Retry artifact contents/set differ')
                return manifest
            stage = Path(tempfile.mkdtemp(prefix='.' + path.name + '-', dir=path.parent))
            for name, value in files.items():
                target = stage / name
                require(target.resolve().is_relative_to(stage) and name != 'manifest.json', 'Unsafe output artifact name')
                target.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(value, ArtifactRef):
                    shutil.copyfile(value.path, target)
                elif isinstance(value, bytes):
                    target.write_bytes(value)
                else:
                    write(target, value)
                require(sha(target) == expected[name], 'Artifact changed while being published')
            rows = [{'path': str(p.relative_to(stage)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                    for p in sorted(stage.rglob('*')) if p.is_file()]
            write(stage / 'manifest.json', {'schema_version': 'engine_artifacts_v1', 'files': rows, 'metadata': metadata})
            verify_manifest(stage)
            # A malformed result must never become an apparently successful job.
            if 'native.json.gz' in files and 'result.json' in files:
                reopen_traffic(stage)
            require(not path.exists(), 'Output appeared during publication')
            stage.rename(path)
            return read(path / 'manifest.json')
        finally:
            if stage is not None and stage.exists():
                shutil.rmtree(stage)
            os.close(fd)


    def reopen(self, key: str) -> dict:
        return reopen_traffic(self.path(key))

    def exists(self, key: str) -> bool:
        return self.path(key).exists()

    def read_document(self, key: str, name: str) -> dict:
        root = self.path(key)
        verify_manifest(root)
        target = root / name
        require(target.resolve().is_relative_to(root) and target.is_file(), 'Unsafe/missing document')
        value = read(target)
        require(isinstance(value, dict), 'Expected a JSON document')
        return value
