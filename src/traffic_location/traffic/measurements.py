"""Read and validate native detector-linked observations, with no inference."""
from ._kernel.measurement_adapter import adapted_frames,relationship_evidence
from ._kernel.support import require

def read_measurements(path,source_identity,frame_count,*,relationships=None,baseline_reviews=None,baseline_reviews_sha256=None,audit=None):
 # Legacy historical review context is explicit; it is never a new model prediction.
 yield from adapted_frames(path,source_identity,frame_count,relationships=relationships,
   reviews=baseline_reviews or [],reviews_sha256=baseline_reviews_sha256,application_proof=audit)
