"""Operation and measurement origin are separate, explicit dimensions."""
from dataclasses import dataclass
from enum import Enum
from .source import FrozenDocument

class Operation(str, Enum):
    COUNT_REPLAY = 'count_replay'
    FRESH_INFERENCE = 'fresh_inference'
    RERENDER = 'rerender'
    REOPEN = 'reopen'

class Branch(str, Enum):
    MACHINE = 'machine'
    REVIEW_ASSISTED = 'review_assisted'

@dataclass(frozen=True, slots=True)
class VideoRequest:
    legacy: FrozenDocument
    branch: Branch
    operation: Operation = Operation.COUNT_REPLAY

    def __post_init__(self) -> None:
        if not isinstance(self.legacy, FrozenDocument):
            raise TypeError('Immutable request payload required')
        if not isinstance(self.branch, Branch) or self.operation is not Operation.COUNT_REPLAY:
            raise ValueError('Counting facade accepts COUNT_REPLAY only; use inference/runtime port for fresh inference')
