"""Immutable JSON and source references; importing these types performs no I/O."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TypeAlias, cast
import json

JSON: TypeAlias = None | bool | int | float | str | list['JSON'] | dict[str, 'JSON']

@dataclass(frozen=True, slots=True)
class FrozenDocument:
    """Canonical bytes prevent mutable nested aliases and retain every source field."""
    encoded: bytes

    def __post_init__(self) -> None:
        if type(self.encoded) is not bytes:
            raise TypeError("FrozenDocument requires immutable bytes")
        value = json.loads(self.encoded)
        canonical = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        if canonical != self.encoded:
            raise ValueError('FrozenDocument requires canonical JSON')

    @classmethod
    def freeze(cls, value: object) -> FrozenDocument:
        return cls(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode())

    def thaw(self) -> JSON:
        return cast(JSON, json.loads(self.encoded))  # independent mutable copy, never internal state

    def object(self) -> dict[str, JSON]:
        value = self.thaw()
        if not isinstance(value, dict):
            raise ValueError('Expected a JSON object')
        return value


def digest(value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Expected SHA256')
    return value

@dataclass(frozen=True, slots=True)
class ArtifactRef:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path:
            raise ValueError('Artifact path required')
        digest(self.sha256)

@dataclass(frozen=True, slots=True)
class SourceIdentity:
    document: FrozenDocument

    def __post_init__(self) -> None:
        if not isinstance(self.document, FrozenDocument):
            raise TypeError('Immutable source document required')
        obj = self.document.object()
        for key in ('video_sha256', 'records_sha256', 'geometry_sha256'):
            value = obj.get(key)
            if not isinstance(value, str):
                raise ValueError('Missing source hash: ' + key)
            digest(value)
        for key in ('width', 'height'):
            value = obj.get(key)
            if type(value) is not int or value <= 0:
                raise ValueError('Positive native dimensions required')

@dataclass(frozen=True, slots=True)
class FrameScope:
    start: int
    end: int

    def __post_init__(self) -> None:
        if type(self.start) is not int or type(self.end) is not int or not 0 <= self.start <= self.end:
            raise ValueError('Invalid source-frame scope')
