"""Accepted measured/estimated events are not pending or invalid decisions."""
from dataclasses import dataclass
from enum import Enum
from .source import FrozenDocument

class Disposition(str, Enum):
    ACCEPTED = 'accepted'
    PENDING = 'pending'
    INVALID = 'invalid'
    NOT_ELIGIBLE = 'resolved_not_eligible'

class CrossingEvidence(str, Enum):
    MEASURED = 'measured'
    ESTIMATED = 'estimated'

@dataclass(frozen=True, slots=True)
class Passage:
    event_id: str
    category: str
    direction: str
    evidence: CrossingEvidence
    native: FrozenDocument

    def __post_init__(self) -> None:
        if not isinstance(self.native, FrozenDocument):
            raise TypeError('Immutable passage source required')
        if not isinstance(self.event_id, str) or not self.event_id or self.category not in {'motorcycle', 'car', 'truck', 'bus', 'pedestrian'} or self.direction not in {'A_TO_B', 'B_TO_A'} or not isinstance(self.evidence, CrossingEvidence):
            raise ValueError('Invalid passage')
