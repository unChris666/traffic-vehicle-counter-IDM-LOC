"""Pinned local references; no URI fetching or authentication at import."""
from pathlib import Path
from ...artifacts import sha

def checked(path, digest):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or sha(path)!=digest:
        raise ValueError('AREA_ARTIFACT_MISSING_OR_CHANGED')
    return path.resolve()
