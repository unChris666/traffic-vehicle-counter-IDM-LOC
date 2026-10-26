"""Canonical GCS locations for frozen Traffic detector/ReID assets.

Storage addresses only: no downloads, credentials or model inference at import.
The supplied artifact's SHA remains the model identity checked during staging.
"""
from pathlib import Path
import re

MODEL_BUCKET = 'feeder-location-intelligent'
MODEL_PREFIXES = {'detector': 'models/traffic/detector', 'reid': 'models/traffic/reid'}


def gcs_model_ref(role, artifact):
    if role not in MODEL_PREFIXES:
        raise ValueError('Unsupported Traffic model role')
    digest = artifact['sha256']
    if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
        raise ValueError('Explicit model SHA256 required')
    name = Path(artifact['path']).name
    if name != {'detector': 'yolo26m.pt', 'reid': 'yolo26n-reid.onnx'}[role]:
        raise ValueError('Model filename differs from the frozen Traffic profile')
    return {'bucket': MODEL_BUCKET, 'object': f'{MODEL_PREFIXES[role]}/{digest}/{name}', 'sha256': digest}
