"""Publication verification independent of GPU/backend availability."""
from pathlib import Path
from ...persistence import verify_manifest
from ...artifacts import read

def reopen_execution(root):
    root=Path(root);manifest=verify_manifest(root);result=read(root/'result.json')
    if result['result_version']!=manifest['metadata']['result_version']:raise ValueError('AREA_RESULT_VERSION_MISMATCH')
    return result
