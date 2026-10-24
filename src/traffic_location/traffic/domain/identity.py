"""Pure episode resolver. Original kernel call order and policies are unchanged."""
from .._kernel.identity import prepare_identity_frames

def resolve(frames, geometry, policy, *, relationships):
    return prepare_identity_frames(frames, geometry, policy, relationships=relationships)
