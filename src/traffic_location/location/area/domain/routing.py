"""Recorded GPU labels are an explicit replay input, not fresh GPU execution."""
def replay_recorded(root,labels,audit):
    from .._kernel.location_intelligent_gpu_worker import route_weighted
    return route_weighted(root,labels,audit)
