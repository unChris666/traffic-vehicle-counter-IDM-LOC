"""Explicit provenance-only normalization for relocated calculation artifacts.

No decision, geometry, route, score or numeric value is removed or rounded.
"""
from copy import deepcopy

def routing_view(value):
    result=deepcopy(value)
    provenance=result.get('provenance',{})
    for key in ['context_hash','selection_hash','policy_hash']:provenance.pop(key,None)
    if 'effective_policy' in provenance:
        provenance['effective_policy']['li3']['building_cache']='<relocated-input-cache>'
    return result
