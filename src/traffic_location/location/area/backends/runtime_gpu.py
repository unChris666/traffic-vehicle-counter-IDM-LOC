"""Scoped runtime adapters for source calculation and market GPU connectors."""
from .geometry_gpu import geometry_scope
from .._kernel.location_intelligent_gpu_runtime import build_gpu as _build,build_market_gpu as _market

def build_gpu(*args,**kwargs):
    with geometry_scope():return _build(*args,**kwargs)

def build_market_gpu(*args,**kwargs):
    with geometry_scope():return _market(*args,**kwargs)
