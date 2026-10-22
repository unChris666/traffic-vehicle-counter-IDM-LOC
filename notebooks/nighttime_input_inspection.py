"""Read-only source inspection. No model, enhancement, tracking or counting."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import time

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.mts', '.mpeg', '.mpg'}
DATASET = 'chrisbiran/video-traffic-malam'


def file_sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def positive(value):
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None


def probe(path):
    """Keep absent metadata unknown; ffprobe durations are not physical ground truth."""
    if not shutil.which('ffprobe'):
        return {'available': False, 'error': 'ffprobe not installed', 'stream': {}, 'format': {}}
    command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams',
               '-show_format', '-of', 'json', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        return {'available': True, 'error': result.stderr.strip(), 'stream': {}, 'format': {}}
    data = json.loads(result.stdout)
    return {'available': True, 'error': None, 'stream': next(iter(data.get('streams', [])), {}),
            'format': data.get('format', {})}


def fraction_rate(text):
    try:
        a, b = text.split('/')
        return positive(float(a) / float(b))
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        return None


def inspect_video(path, output, dataset_root):
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw

    started = time.perf_counter()
    path, output = Path(path), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    before = file_sha256(path)
    info = probe(path)
    stream = info['stream']
    cap = cv2.VideoCapture(str(path))
    opened = cap.isOpened()
    declared = positive(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if opened else None
    declared_count = int(declared) if declared is not None and declared.is_integer() else None
    fps_opencv = positive(cap.get(cv2.CAP_PROP_FPS)) if opened else None
    target_count = declared_count
    targets = sorted(set([0, *[round((target_count - 1) * p) for p in [.25, .5, .75, 1]]])) if target_count else [0]
    samples, decoded, dimensions, first_failure = [], 0, set(), None
    last_frame = None
    while opened:
        ok, frame = cap.read()
        if not ok:
            first_failure = decoded
            break
        last_frame = frame
        height, width = frame.shape[:2]
        dimensions.add((width, height))
        if decoded in targets:
            name = f'frame_{decoded:06d}.png'
            assert cv2.imwrite(str(output / name), frame), 'Could not save native frame'
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            samples.append({'frame_index': decoded, 'native_image': name, 'image_sha256': file_sha256(output/name),
                            'decoded_bgr_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
                            'reported_position_msec': cap.get(cv2.CAP_PROP_POS_MSEC),
                            'luma_p05_p50_p95': [float(x) for x in np.percentile(gray, [5, 50, 95])],
                            'fraction_luma_le_16': float(np.mean(gray <= 16)),
                            'fraction_luma_ge_240': float(np.mean(gray >= 240)),
                            'metric_limits': 'Pixel summaries only; no detection/noise/visibility quality threshold.'})
        decoded += 1
    cap.release()
    # Retain actual end even if header count was inaccurate; do not fabricate 25/50/75% coverage.
    if decoded and decoded-1 not in [s['frame_index'] for s in samples]:
        name = f'frame_{decoded-1:06d}.png'
        assert cv2.imwrite(str(output/name), last_frame)
        samples.append({'frame_index': decoded-1, 'native_image': name, 'image_sha256': file_sha256(output/name),
                        'decoded_bgr_sha256': hashlib.sha256(last_frame.tobytes()).hexdigest(),
                        'note': 'Actual last decodable frame; header-based sampling may be incomplete.'})
    if samples:
        sheet = Image.new('RGB', (360 * len(samples), 292), '#202020')
        draw = ImageDraw.Draw(sheet)
        for i, sample in enumerate(samples):
            im = Image.open(output/sample['native_image']).convert('RGB')
            im.thumbnail((360, 250))
            sheet.paste(im, (i*360, 24))
            draw.text((i*360+5, 5), f"source frame {sample['frame_index']}", fill='white')
        sheet.save(output/'contact_sheet.jpg', quality=92)
    after = file_sha256(path)
    assert before == after, 'Source video changed during read-only inspection'
    if not opened or decoded == 0:
        status = 'UNREADABLE_OR_NO_DECODABLE_FRAMES'
    elif declared_count is not None and decoded != declared_count:
        status = 'DECODE_HEADER_COUNT_MISMATCH_REVIEW_REQUIRED'
    else:
        status = 'SEQUENTIAL_DECODE_TO_EOF'
    duration = None
    for value in [stream.get('duration'), info['format'].get('duration')]:
        try:
            duration = positive(float(value))
        except (TypeError, ValueError):
            pass
        if duration is not None:
            break
    result = {'filename': path.name, 'relative_path': str(path.relative_to(dataset_root)),
              'extension': path.suffix, 'size_bytes': path.stat().st_size, 'source_sha256': before,
              'source_unchanged': True, 'width': stream.get('width'), 'height': stream.get('height'),
              'fps_reported_ffprobe': fraction_rate(stream.get('avg_frame_rate')),
              'fps_reported_opencv': fps_opencv, 'duration_reported_seconds': duration,
              'duration_from_decoded_count_and_reported_fps_seconds': decoded / fps_opencv if fps_opencv else None,
              'codec': stream.get('codec_name'), 'codec_tag': stream.get('codec_tag_string'),
              'pixel_format': stream.get('pix_fmt'), 'frame_count_reported_opencv': declared_count,
              'frame_count_decoded': decoded, 'decoded_dimensions': sorted(dimensions),
              'decode_status': status, 'first_unsuccessful_read_frame': first_failure,
              'decode_limit': 'OpenCV sequential EOF plus header comparison; not a bitstream corruption certification.',
              'ffprobe': info, 'samples': samples, 'sampling': 'Sequential source indices at header-based 0/25/50/75/100%; actual end retained.',
              'condition': None, 'condition_assignment': 'UNASSIGNED_REQUIRES_REVIEW_NOT_FILENAME_INFERENCE',
              'wall_seconds': time.perf_counter()-started}
    (output/'inspection.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return result


def inspect_dataset(dataset_root, output, *, execution_context):
    root, output = Path(dataset_root).resolve(), Path(output).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f'Actual dataset directory unavailable: {root}')
    if root == output or root in output.parents:
        raise ValueError('Inspection output must not modify the original dataset tree')
    files = sorted(p for p in root.rglob('*') if p.is_file())
    if not files:
        raise ValueError('Dataset directory contains no files')
    output.mkdir(parents=True, exist_ok=False)
    inventory, unsupported = [], []
    for i, path in enumerate(files):
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            unsupported.append({'relative_path': str(path.relative_to(root)), 'size_bytes': path.stat().st_size,
                                'reason': 'Extension not in declared video list; not silently treated as video'})
            continue
        target = output/f'video_{i:03d}'
        row = inspect_video(path, target, root)
        row['evidence_directory'] = target.name
        inventory.append(row)
        print(json.dumps({'filename': path.name, 'decoded_frames': row['frame_count_decoded'], 'status': row['decode_status']}), flush=True)
    import cv2
    environment = {'python': platform.python_version(), 'opencv': cv2.__version__, 'execution_context': execution_context,
                   'actual_dataset_directory': str(root), 'kaggle_input_exists': Path('/kaggle/input').is_dir(),
                   'cpu_count': __import__('os').cpu_count(),
                   'kaggle_input_top_level_actual': sorted(p.name for p in Path('/kaggle/input').iterdir()) if Path('/kaggle/input').is_dir() else [],
                   'gpu_required_for_inspection': False}
    report = {'schema_version': 'official_night_input_inspection_v1', 'designated_dataset': DATASET,
              'environment': environment, 'actual_files': [{'path': str(p.relative_to(root)), 'size_bytes': p.stat().st_size} for p in files],
              'video_count': len(inventory), 'inventory': inventory, 'unsupported_files': unsupported,
              'unreadable_or_mismatched': [r['filename'] for r in inventory if r['decode_status'] != 'SEQUENTIAL_DECODE_TO_EOF'],
              'manual_visual_review_status': 'PENDING', 'new_model_execution': False,
              'review_filter_implemented_or_validated_by_this_inspection': False,
              'counting_smoke_test_executed': False, 'production_reliability_established': False}
    (output/'inventory.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    import csv
    fields = ['filename', 'extension', 'size_bytes', 'duration_reported_seconds', 'fps_reported_ffprobe', 'width', 'height',
              'codec', 'frame_count_decoded', 'decode_status', 'source_sha256', 'evidence_directory']
    with (output/'inventory.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(inventory)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--execution-context', required=True, choices=['codex_downloaded_dataset', 'actual_kaggle_mount'])
    args = parser.parse_args()
    inspect_dataset(args.dataset_root, args.output, execution_context=args.execution_context)
