"""Describe and validate the frozen worker's tracker/ReID configuration."""
def require_reid(request):
    # No alternate tracker, feature encoder, or per-video state is injected here.
    if not isinstance(request, dict) or request.get('schema_version') != 'fresh_inference_request_v1':
        raise ValueError('Explicit fresh worker request required')
    if request.get('preprocessing') != 'RAW' or request.get('half') is not False or not isinstance(request.get('tracker'), dict):
        raise ValueError('Unsupported model profile; expected frozen RAW FP32 with explicit tracker')
    from ..experiments.performance import batch_size
    batch_size(request)
    from ..execution_profile import resolve_profile
    resolve_profile(request)
    return {'worker': 'traffic_location.traffic.inference_worker',
            'state_scope': 'ONE_PROCESS_PER_VIDEO', 'request': request.copy()}
