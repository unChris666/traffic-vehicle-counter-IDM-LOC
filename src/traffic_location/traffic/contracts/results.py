"""Versioned immutable consumer result; original native document is lossless."""
from dataclasses import dataclass
from .source import FrozenDocument
from .execution import Operation

@dataclass(frozen=True, slots=True)
class VideoResult:
    envelope: FrozenDocument
    native: FrozenDocument
    adapter_audit: FrozenDocument
    operation: Operation = Operation.COUNT_REPLAY

    def __post_init__(self) -> None:
        if not all(isinstance(v, FrozenDocument) for v in (self.envelope, self.native, self.adapter_audit)) or self.operation is not Operation.COUNT_REPLAY:
            raise TypeError('Immutable result documents and counting operation required')
        if self.envelope.object().get('schema_version') != 'traffic_result_v2':
            raise ValueError('Unsupported VideoResult version')
