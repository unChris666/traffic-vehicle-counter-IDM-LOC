"""Artifact I/O then explicit merge, validation and freeze. No implicit defaults."""
from pathlib import Path
from typing import Callable, cast
import hashlib
from .schema import EffectiveConfig
from .profiles import merge_policy
from .validation import validate_policy
from ..contracts.source import ArtifactRef, FrozenDocument, JSON
from ..contracts.execution import Branch
from ...artifacts import artifact, read

def load_effective_config(ref: ArtifactRef, *, root: str | Path, branch: Branch,
                          video_overrides: dict[str, JSON] | None = None,
                          job_overrides: dict[str, JSON] | None = None) -> EffectiveConfig:
    resolve = cast(Callable[[dict[str, JSON], str | Path], Path], artifact)
    read_json = cast(Callable[[Path], object], read)
    policy = FrozenDocument.freeze(read_json(resolve({'path': ref.path, 'sha256': ref.sha256}, root))).object()
    policy = merge_policy(policy, video_overrides, job_overrides)
    validate_policy(policy, branch)
    precedence = ('frozen_policy',) + (('video_overrides',) if video_overrides is not None else ()) + (('job_overrides',) if job_overrides is not None else ())
    doc = FrozenDocument.freeze(policy)
    return EffectiveConfig(doc, branch, hashlib.sha256(doc.encoded).hexdigest(), precedence=precedence)
