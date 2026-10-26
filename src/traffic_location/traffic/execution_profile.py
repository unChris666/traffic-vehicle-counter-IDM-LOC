"""Named execution profiles; counting rules and model weights remain caller-bound."""
CANDIDATE = dict(name='candidate_fp32', backend='pytorch', batch_size=4,
                 precision='FP32', reid_transport='io_binding', reid_window=8,
                 crop_batch=32, reid_precision='FP32')


def resolve_profile(request):
    name=request.get('execution_profile','candidate_fp32' if request.get('device')=='cuda:0' else 'baseline_fp32')
    if name=='baseline_fp32':return None
    if name!='candidate_fp32':raise ValueError('Unknown traffic execution_profile')
    if request.get('device')!='cuda:0':raise ValueError('candidate_fp32 requires an isolated CUDA GPU')
    if request.get('half') is not False:raise ValueError('candidate_fp32 requires FP32')
    if request.get('performance',{}).get('batch_size',4)!=4:
        raise ValueError('candidate_fp32 fixes batch_size=4; use baseline_fp32 for older batch experiments')
    return CANDIDATE.copy()
