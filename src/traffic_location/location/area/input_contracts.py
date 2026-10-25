"""Public artifact operations; no provider credentials or execution globals."""
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class AreaArtifactRequest:
    schema_version: Literal['area_artifact_request_v1']
    operation: Literal['freeze', 'reopen']
    path: str
    sha256: str

    @classmethod
    def parse(cls, value):
        if set(value) != {'schema_version', 'operation', 'path', 'sha256'}:
            raise ValueError('AREA_REQUEST_FIELDS_INVALID')
        if not all(isinstance(v,str) for v in value.values()):
            raise ValueError('AREA_REQUEST_TYPES_INVALID')
        if value['schema_version'] != 'area_artifact_request_v1' or value['operation'] not in {'freeze','reopen'}:
            raise ValueError('AREA_REQUEST_VERSION_OR_OPERATION_INVALID')
        if not isinstance(value['path'],str) or not value['path']:
            raise ValueError('AREA_REQUEST_PATH_INVALID')
        digest=value['sha256']
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('AREA_REQUEST_SHA_INVALID')
        return cls(**value)
