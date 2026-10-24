"""Reject profile mixing; numerical domain controls retain original validators."""
from ..contracts.execution import Branch
from ..contracts.source import JSON

def validate_policy(policy: dict[str, JSON], branch: Branch) -> dict[str, JSON]:
    if not isinstance(policy, dict) or policy.get('execution_branch') != branch.value:
        raise ValueError('Effective policy branch differs from request')
    if policy.get('schema_version') not in {'phase9_b_v7_handoff_policy_v1', 'phase9_b_v8_p1_review_policy_v1'}:
        raise ValueError('Explicit frozen policy schema required')
    # Exact supported schema and numeric constraints are also checked by the
    # preserved identity/counting kernels before any event can be published.
    return policy
