"""Compatibility boundary; verified baseline algorithms are retained."""
from .._kernel.location_intelligent_kaggle_esri import upload_result
__all__ = ['upload_result']


def publish_gcs(root,archive,*,bucket):
    """Caller supplies authenticated bucket. No Kaggle Secret/auth inside engine."""
    from .export import archive_result
    from ....artifacts import read
    from pathlib import Path
    path=archive_result(root,archive)
    receipt=upload_result(None,path,bucket=bucket)
    return {**receipt,'engine_result_version':read(Path(root)/'result.json')['result_version'],
            'content_schema':'area_modular_local_packet_v1'}
