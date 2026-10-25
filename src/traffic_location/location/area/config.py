"""Use the verified effective policy, never silently load N1 defaults."""
from copy import deepcopy

def frozen_policy(snapshot):return deepcopy(snapshot.config)
