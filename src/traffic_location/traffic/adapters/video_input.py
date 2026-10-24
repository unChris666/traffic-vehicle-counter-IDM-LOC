"""Source-bound frame decoding. Never subsample a full-video operation."""
from pathlib import Path
from ...artifacts import sha, require

def verify_video(path, expected_sha256):
    path = Path(path).resolve()
    require(path.is_file() and sha(path) == expected_sha256, 'Video SHA differs')
    return path

def decode_all(path, *, expected_frames):
    import cv2
    cap = cv2.VideoCapture(str(path))
    try:
        require(cap.isOpened(), 'Video cannot be opened')
        index = 0
        while True:
            ok, image = cap.read()
            if not ok:
                break
            yield index, image
            index += 1
        require(index == expected_frames, 'Decoded frame count differs')
    finally:
        cap.release()


def load_geometry(path, source):
    from ...artifacts import read
    from .._kernel.geometry import Geometry, _point
    draft = read(path)
    if draft.get('source_video', {}).get('sha256'):
        require(draft['source_video']['sha256'] == source['video_sha256'], 'Geometry belongs to a different source video')
    width, height = source['width'], source['height']
    def resolve(point):
        u, v = _point(point)
        require(0 <= u <= 1 and 0 <= v <= 1, 'Normalized template coordinate outside [0,1]')
        return (u * width, v * height)
    normalized = draft['normalized']
    return Geometry(resolve(normalized['line']['P1']), resolve(normalized['line']['P2']),
        tuple(resolve(p) for p in normalized['side_a_polygon']), tuple(resolve(p) for p in normalized['side_b_polygon']),
        width, height, draft.get('draft_id', 'explicit-template'), draft.get('source_video', {}).get('sha256'), draft.get('status'))
