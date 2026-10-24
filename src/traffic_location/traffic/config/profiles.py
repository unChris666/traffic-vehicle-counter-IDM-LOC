"""Only existing keys may be explicitly overridden; every override is fingerprinted."""
from copy import deepcopy
from ..contracts.source import JSON

def merge_policy(base: dict[str, JSON], video_overrides: dict[str, JSON] | None = None,
                 job_overrides: dict[str, JSON] | None = None) -> dict[str, JSON]:
    result = deepcopy(base)
    def apply(target: dict[str, JSON], patch: dict[str, JSON]) -> None:
        if not isinstance(patch, dict):
            raise ValueError('Override must be an object')
        for key, value in patch.items():
            if key not in target or key in {'execution_branch', 'schema_version', 'policy_version'}:
                raise ValueError('Unknown/protected policy override: ' + key)
            previous = target[key]
            if isinstance(value, dict) and isinstance(previous, dict):
                apply(previous, value)
            else:
                if type(value) is not type(target[key]):
                    raise ValueError('Policy override changes value type: ' + key)
                target[key] = deepcopy(value)
    for patch in (video_overrides, job_overrides):
        if patch is not None:
            apply(result, patch)
    return result
