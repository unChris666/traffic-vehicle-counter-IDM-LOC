"""Chronological source scope gate; a gap never becomes an interpolated sample."""
def validate_scope(frames, frame_count):
    if [r['frame_index'] for r in frames] != list(range(frame_count)):
        raise ValueError('Missing/extra source frames')
    return frames
