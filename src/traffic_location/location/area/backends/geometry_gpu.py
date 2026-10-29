"""GPU geometry adapter: an empty batch has no intersections to evaluate.

Retain frozen kernels; do not initialize CUDA, upload polygons, or query a GEOS
index for zero connector candidates. Nonempty batches use the same algorithm.
"""
from contextlib import contextmanager
from threading import RLock
from unittest.mock import patch
from .._kernel.location_intelligent_gpu_geometry import GpuGeometry as FrozenGpuGeometry
from .._kernel.location_intelligent_gpu_connectors import generate_connectors_gpu as _generate
_LOCK=RLock()

class BatchSafeGpuGeometry(FrozenGpuGeometry):
    def footprint_clear_batch(self,prepared,footprint_ids,footprints,tree,inset_geometry):
        if len(prepared)==0:return []
        return super().footprint_clear_batch(prepared,footprint_ids,footprints,tree,inset_geometry)

    def resident_footprint_batch(self,prepared,footprint_ids,footprints,tree,inset_geometry):
        if len(prepared)==0:return []
        return super().resident_footprint_batch(prepared,footprint_ids,footprints,tree,inset_geometry)

@contextmanager
def geometry_scope():
    with _LOCK,patch('traffic_location.location.area._kernel.location_intelligent_gpu_geometry.GpuGeometry',BatchSafeGpuGeometry):
        yield

def generate_connectors_gpu(*args,**kwargs):
    with geometry_scope():return _generate(*args,**kwargs)

__all__=['generate_connectors_gpu','BatchSafeGpuGeometry','geometry_scope']
