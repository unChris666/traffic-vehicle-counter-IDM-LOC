"""Preserved eligibility → crossing → finalization operation, with per-call state."""
from .._kernel.publication import replay_frames

def count(frames, geometry, *, source_identity, policy):
    return replay_frames(frames, geometry, source_identity=source_identity, policy=policy)
