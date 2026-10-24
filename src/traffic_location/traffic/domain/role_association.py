"""Scoped component relations are produced inside the frozen identity resolver."""
def relations(resolved):
    # Do not run association twice: it is part of identity.resolve's atomic kernel.
    return resolved.get('unit_relations', []), resolved.get('component_links', [])
