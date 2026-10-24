"""Physical episodes and scoped roles are distinct from raw tracker IDs."""
from dataclasses import dataclass
from enum import Enum
from .source import FrameScope, FrozenDocument

class Role(str, Enum):
    VEHICLE = 'vehicle'
    RIDER = 'rider'
    PEDESTRIAN = 'pedestrian'
    UNKNOWN_PERSON = 'unknown_person'

@dataclass(frozen=True, slots=True)
class EpisodeRef:
    physical_unit_id: str
    episode_id: str
    scope: FrameScope

    def __post_init__(self) -> None:
        if not isinstance(self.physical_unit_id, str) or not self.physical_unit_id or not isinstance(self.episode_id, str) or not self.episode_id or not isinstance(self.scope, FrameScope):
            raise ValueError('Explicit immutable episode scope required')

@dataclass(frozen=True, slots=True)
class RoleAssociation:
    track_id: int
    role: Role
    scope: FrameScope
    parent_unit_id: str | None
    evidence: FrozenDocument

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, FrozenDocument) or not isinstance(self.scope, FrameScope) or type(self.track_id) is not int or self.track_id <= 0:
            raise TypeError('Immutable role evidence/scope and positive raw ID required')
        if self.parent_unit_id is not None and (not isinstance(self.parent_unit_id, str) or not self.parent_unit_id):
            raise TypeError('Explicit parent unit ID required')
        if not isinstance(self.role, Role) or (self.role is Role.RIDER and not self.parent_unit_id):
            raise ValueError('Rider requires explicit parent unit')
