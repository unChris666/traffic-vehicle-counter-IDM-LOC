"""Known boundary decoders only. Unknown schemas never fall forward silently."""
from typing import Callable, cast
from .source import FrozenDocument, JSON
from .execution import VideoRequest, Branch
from .review import SourceContextReview, CandidateAdjudication
from ..validation import validate_request

SUPPORTED = frozenset({'traffic_request_v1', 'phase8_b_v4_review_overlay_v1', 'phase9_b_v8_pending_adjudications_v1'})

def decode_request(value: object) -> VideoRequest:
    validator = cast(Callable[[object], tuple[dict[str, JSON], str]], validate_request)
    request, branch = validator(value)
    return VideoRequest(FrozenDocument.freeze(request), Branch(branch))

def decode_review(value: object) -> SourceContextReview | CandidateAdjudication:
    doc = FrozenDocument.freeze(value)
    schema = doc.object().get('schema_version')
    if schema == 'phase8_b_v4_review_overlay_v1':
        return SourceContextReview(doc)
    if schema == 'phase9_b_v8_pending_adjudications_v1':
        return CandidateAdjudication(doc)
    raise ValueError('Unknown review schema')
