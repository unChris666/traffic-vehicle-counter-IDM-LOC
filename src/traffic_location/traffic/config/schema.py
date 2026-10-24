"""Effective policies are immutable; no global notebook or environment defaults."""
from dataclasses import dataclass
from ..contracts.source import FrozenDocument
from ..contracts.execution import Branch

@dataclass(frozen=True, slots=True)
class EffectiveConfig:
    policy: FrozenDocument
    branch: Branch
    fingerprint: str
    schema_version: str = 'traffic_effective_config_v1'
    precedence: tuple[str, ...] = ('frozen_policy',)


    def __post_init__(self) -> None:
        import hashlib
        if not isinstance(self.policy, FrozenDocument):
            raise TypeError('Immutable policy document required')
        if self.schema_version != 'traffic_effective_config_v1' or not isinstance(self.branch, Branch):
            raise ValueError('Unknown effective config version/branch')
        if hashlib.sha256(self.policy.encoded).hexdigest() != self.fingerprint:
            raise ValueError('Effective config fingerprint differs')
        if self.policy.object().get('execution_branch') != self.branch.value:
            raise ValueError('Effective config branch differs')
        if not isinstance(self.precedence, tuple):
            raise ValueError('Immutable precedence required')
