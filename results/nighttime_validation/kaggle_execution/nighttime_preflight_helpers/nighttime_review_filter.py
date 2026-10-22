"""Explicit photometric contract shared with results/nighttime_review_filter.js.

New experiment, never an automatic replacement for the retained raw baseline.
"""
import copy
import hashlib
import json
import math

SCHEMA = 'night_review_filter_v1'
ORDER = ['gamma', 'exposure', 'brightness', 'shadows', 'sharpness']
CONDITIONS = [f'{day}_{period}' for day in ['weekday', 'weekend'] for period in ['pagi', 'siang', 'sore', 'malam']]
RAW = {'gamma': 1.0, 'exposure': 0.0, 'sharpness': 0.0, 'brightness': 0.0, 'shadows': 0.0}
RANGES = {'gamma': (.2, 3.), 'exposure': (-3., 3.), 'sharpness': (0., 2.), 'brightness': (-100., 100.), 'shadows': (-100., 100.)}


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != set(RAW):
        raise ValueError('Exactly gamma/exposure/sharpness/brightness/shadows required')
    for key, (low, high) in RANGES.items():
        value = settings[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'Unsupported {key}: expected finite number in [{low},{high}]')
    return copy.deepcopy(settings)


def validate_config(config):
    if config.get('schema_version') != SCHEMA or config.get('operation_order') != ORDER:
        raise ValueError('Unknown schema or transform order')
    if set(config.get('profiles', {})) != set(CONDITIONS):
        raise ValueError('Eight independent condition profiles required, not eight assumed input videos')
    for settings in config['profiles'].values():
        validate_settings(settings)
    if not isinstance(config.get('videos'), list):
        raise ValueError('Explicit video list required')
    hashes = set()
    import re
    for video in config['videos']:
        sha = video.get('source_sha256')
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or sha in hashes:
            raise ValueError('Unique actual video SHA256 required')
        hashes.add(sha)
        if not isinstance(video.get('filename'), str) or not video['filename']:
            raise ValueError('Actual video filename required')
        if video.get('condition') is not None and video['condition'] not in CONDITIONS:
            raise ValueError('Unknown condition; leave null instead of guessing')
        validate_settings(video['settings'])
    return copy.deepcopy(config)


def settings_for_video(config, source_sha256):
    validated = validate_config(config)
    for video in validated['videos']:
        if video['source_sha256'] == source_sha256:
            return copy.deepcopy(video['settings'])
    raise ValueError('Source video has no explicit saved settings; do not silently use another slot')


def apply_filter(frame_bgr, settings):
    """Preserves BGR order and native dimensions; half-up rounding after each stage."""
    import numpy as np
    s = validate_settings(settings)
    if not isinstance(frame_bgr, np.ndarray) or frame_bgr.dtype != np.uint8 or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3 or min(frame_bgr.shape[:2]) < 1:
        raise ValueError('Nonempty HxWx3 BGR uint8 required')
    def quantize(x):
        return np.floor(np.clip(x, 0, 255) + .5).astype(np.uint8)
    result = frame_bgr.copy()
    if s['gamma'] != 1:
        result = quantize(255. * (result.astype(np.float64)/255.) ** s['gamma'])
    if s['exposure']:
        result = quantize(result.astype(np.float64) * 2. ** s['exposure'])
    if s['brightness']:
        result = quantize(result.astype(np.float64) + s['brightness'])
    if s['shadows']:
        x = result.astype(np.float64)
        result = quantize(x + .64 * s['shadows'] * (1. - x/255.) ** 2)
    if s['sharpness']:
        x = result.astype(np.float64)
        padded = np.pad(x, ((1, 1), (1, 1), (0, 0)), mode='edge')
        smooth = np.zeros_like(x)
        for j, wy in enumerate([1, 2, 1]):
            for i, wx in enumerate([1, 2, 1]):
                smooth += padded[j:j+x.shape[0], i:i+x.shape[1]] * wy * wx / 16.
        result = quantize(x + s['sharpness'] * (x - smooth))
    return result


def prepare_inference_frame(raw_frame_bgr, config, source_sha256):
    """Use this SAME result for detector and ReID frame input, never raw in one branch."""
    result = apply_filter(raw_frame_bgr, settings_for_video(config, source_sha256))
    return result, {'schema_version': SCHEMA, 'source_sha256': source_sha256,
                    'operation_order': ORDER, 'settings': settings_for_video(config, source_sha256),
                    'output_bgr_sha256': hashlib.sha256(result.tobytes()).hexdigest(),
                    'config_sha256': hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
