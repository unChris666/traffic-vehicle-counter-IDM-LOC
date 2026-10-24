"""Version dispatch without inferring a format from a filename."""
from . import notebook_measurements, fresh_measurements

def read_frames(request, paths, *, links, baseline_reviews, audit):
    args = (paths['measurements'], request['source_identity'], request['frame_count'])
    if request.get('measurement_format', 'notebook_native') == 'fresh_v1':
        return fresh_measurements.frames(*args, audit=audit)
    return notebook_measurements.read_measurements(*args, relationships=links,
        baseline_reviews=baseline_reviews,
        baseline_reviews_sha256=request['artifacts'].get('baseline_reviews', {}).get('sha256'), audit=audit)
