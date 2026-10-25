"""Explicit backend selection; GPU absence never selects CPU silently."""
def generate(*args,backend,**kwargs):
    if backend=='gpu':
        from ..backends.geometry_gpu import generate_connectors_gpu
        return generate_connectors_gpu(*args,**kwargs)
    if backend=='cpu':
        from ..backends.geometry_cpu import generate_connectors
        return generate_connectors(*args,**kwargs)
    raise ValueError('AREA_CONNECTOR_BACKEND_UNKNOWN')
