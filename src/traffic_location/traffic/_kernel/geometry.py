"""Phase 5 notebook geometry, independent of detector/tracker/model quality.

Outputs are geometric diagnostics, never accepted traffic-count events. All
noise/confirmation parameters are required experimental inputs. ``neutral_band_px``
is the distance on EACH side of the line, not the full width of that band.

Only floating-point roundoff is tolerated by primitives (1e-12 times coordinate
scale); that numerical tolerance is not a jitter/counting threshold.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import gzip
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any, Iterable
Point = tuple[float, float]

def _point(value: Iterable[float]) -> Point:
    try:
        values = tuple(value)
    except TypeError as exc:
        raise ValueError('A point requires two finite numeric coordinates') from exc
    if len(values) != 2 or any((isinstance(x, bool) or not isinstance(x, Real) for x in values)):
        raise ValueError('A point requires two finite numeric coordinates')
    try:
        result = (float(values[0]), float(values[1]))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('A point requires two finite numeric coordinates') from exc
    if not all((math.isfinite(x) for x in result)):
        raise ValueError('Non-finite geometry coordinate')
    return result

def _epsilon(*points: Point) -> float:
    return 1e-12 * max(1.0, *(abs(v) for p in points for v in p))

def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]

def _subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])

def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])

def _on_segment(point: Point, a: Point, b: Point) -> bool:
    tolerance = _epsilon(point, a, b)
    length = _distance(a, b)
    if length <= tolerance:
        return _distance(point, a) <= tolerance
    if abs(_cross(_subtract(b, a), _subtract(point, a))) / length > tolerance:
        return False
    return min(a[0], b[0]) - tolerance <= point[0] <= max(a[0], b[0]) + tolerance and min(a[1], b[1]) - tolerance <= point[1] <= max(a[1], b[1]) + tolerance

def point_in_polygon(point: Iterable[float], polygon: Iterable[Iterable[float]]) -> str:
    """Return inside/boundary/outside; no implicit pixel or jitter margin."""
    point = _point(point)
    vertices = tuple((_point(p) for p in polygon))
    if len(vertices) < 3:
        raise ValueError('A polygon needs at least three vertices')
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if _on_segment(point, a, b):
            return 'boundary'
        if (a[1] > point[1]) != (b[1] > point[1]):
            intersection_x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < intersection_x:
                inside = not inside
    return 'inside' if inside else 'outside'

def signed_distance(point: Iterable[float], p1: Iterable[float], p2: Iterable[float]) -> float:
    """Signed perpendicular distance in pixels; sign has no A/B semantics."""
    point, p1, p2 = (_point(point), _point(p1), _point(p2))
    length = _distance(p1, p2)
    if length <= _epsilon(p1, p2):
        raise ValueError('Counting-line endpoints must be distinct')
    return _cross(_subtract(p2, p1), _subtract(point, p1)) / length

def segment_intersection(a, b, c, d) -> dict[str, Any]:
    """Intersect finite path a-b with finite line c-d.

    ``proper``: interior of both segments. ``endpoint``: configured-line c/d
    contact. ``touch``: path endpoint at line interior. ``overlap``: positive
    collinear overlap. ``none`` includes intersections of infinite extensions.
    ``t`` and ``u`` are path and counting-line fractions, respectively.
    """
    a, b, c, d = (_point(a), _point(b), _point(c), _point(d))
    r, s = (_subtract(b, a), _subtract(d, c))
    r_length, s_length = (_distance(a, b), _distance(c, d))
    tolerance = _epsilon(a, b, c, d)
    empty = {'kind': 'none', 'point': None, 't': None, 'u': None}
    if s_length <= tolerance:
        raise ValueError('Configured line must have distinct endpoints')
    if r_length <= tolerance:
        if not _on_segment(a, c, d):
            return empty
        u = sum(((a[i] - c[i]) * s[i] for i in (0, 1))) / (s_length * s_length)
        endpoint = _distance(a, c) <= tolerance or _distance(a, d) <= tolerance
        return {'kind': 'endpoint' if endpoint else 'touch', 'point': list(a), 't': 0.0, 'u': u}
    denominator = _cross(r, s)
    delta = _subtract(c, a)
    if abs(denominator) <= tolerance * max(r_length, s_length):
        if abs(_cross(delta, r)) / r_length > tolerance:
            return empty
        t_c = sum((delta[i] * r[i] for i in (0, 1))) / (r_length * r_length)
        t_d = sum(((d[i] - a[i]) * r[i] for i in (0, 1))) / (r_length * r_length)
        lower, upper = (max(0.0, min(t_c, t_d)), min(1.0, max(t_c, t_d)))
        fraction_tolerance = tolerance / r_length
        if lower > upper + fraction_tolerance:
            return empty
        point = (a[0] + lower * r[0], a[1] + lower * r[1])
        if upper - lower > fraction_tolerance:
            end = [a[0] + upper * r[0], a[1] + upper * r[1]]
            return {'kind': 'overlap', 'point': list(point), 'end_point': end, 't': lower, 't_end': upper, 'u': None}
        endpoint = _distance(point, c) <= tolerance or _distance(point, d) <= tolerance
        u = sum(((point[i] - c[i]) * s[i] for i in (0, 1))) / (s_length * s_length)
        return {'kind': 'endpoint' if endpoint else 'touch', 'point': list(point), 't': lower, 'u': u}
    t, u = (_cross(delta, s) / denominator, _cross(delta, r) / denominator)
    t_tolerance, u_tolerance = (tolerance / r_length, tolerance / s_length)
    if not (-t_tolerance <= t <= 1 + t_tolerance and -u_tolerance <= u <= 1 + u_tolerance):
        return empty
    t, u = (min(1.0, max(0.0, t)), min(1.0, max(0.0, u)))
    point = [a[0] + t * r[0], a[1] + t * r[1]]
    endpoint = u <= u_tolerance or u >= 1 - u_tolerance
    touch = t <= t_tolerance or t >= 1 - t_tolerance
    return {'kind': 'endpoint' if endpoint else 'touch' if touch else 'proper', 'point': point, 't': t, 'u': u}

def _validate_polygon(vertices: tuple[Point, ...], name: str) -> None:
    if len(vertices) < 3:
        raise ValueError(f'{name} requires at least three vertices')
    edges = list(zip(vertices, vertices[1:] + vertices[:1]))
    if any((_distance(a, b) <= _epsilon(a, b) for a, b in edges)):
        raise ValueError(f'{name} has a zero-length edge')
    twice_area = sum((_cross(a, b) for a, b in edges))
    if abs(twice_area) <= _epsilon(*vertices) * sum((_distance(a, b) for a, b in edges)):
        raise ValueError(f'{name} has zero area')
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i or j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if segment_intersection(a, b, c, d)['kind'] != 'none':
                raise ValueError(f'{name} is not a simple polygon')

def _interior_samples(vertices: tuple[Point, ...]):
    """Interior points from horizontal scan intervals, including concave shapes.

    Used only for topology validation, not placement/noise thresholds. Samples
    are strict interior interval midpoints rather than a possibly exterior
    centroid. They detect coincident outlines with different vertex sampling.
    """
    levels = sorted(set((p[1] for p in vertices)))
    for lower, upper in zip(levels, levels[1:]):
        y = (lower + upper) / 2
        intersections = []
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            if (a[1] > y) != (b[1] > y):
                intersections.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
        intersections.sort()
        for left, right in zip(intersections[::2], intersections[1::2]):
            point = ((left + right) / 2, y)
            if point_in_polygon(point, vertices) == 'inside':
                yield point

@dataclass(frozen=True)
class Geometry:
    p1: Point
    p2: Point
    side_a: tuple[Point, ...]
    side_b: tuple[Point, ...]
    width: int | None = None
    height: int | None = None
    geometry_id: str = 'explicit-fixture'
    video_sha256: str | None = None
    source_draft_status: str | None = None

    def __post_init__(self):
        for name in ('p1', 'p2'):
            object.__setattr__(self, name, _point(getattr(self, name)))
        for name in ('side_a', 'side_b'):
            vertices = tuple((_point(p) for p in getattr(self, name)))
            _validate_polygon(vertices, name)
            object.__setattr__(self, name, vertices)
        signed_distance(self.p1, self.p1, self.p2)
        if (self.width is None) != (self.height is None):
            raise ValueError('Both width and height must be provided, or neither')
        if self.width is not None:
            if any((isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in (self.width, self.height))):
                raise ValueError('Native dimensions must be positive integers')
            for x, y in (self.p1, self.p2, *self.side_a, *self.side_b):
                if not (0 <= x <= self.width and 0 <= y <= self.height):
                    raise ValueError('Geometry exceeds declared continuous image-edge coordinates')
        for first, second in ((self.side_a, self.side_b), (self.side_b, self.side_a)):
            if any((point_in_polygon(p, second) == 'inside' for p in _interior_samples(first))):
                raise ValueError('Side A/B polygon interiors overlap')
            for a, b in zip(first, first[1:] + first[:1]):
                midpoint = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if any((point_in_polygon(p, second) == 'inside' for p in (a, midpoint))):
                    raise ValueError('Side A/B polygon interiors overlap')
                for c, d in zip(second, second[1:] + second[:1]):
                    if segment_intersection(a, b, c, d)['kind'] == 'proper':
                        raise ValueError('Side A/B polygon interiors overlap')

    @classmethod
    def from_draft(cls, path, width: int, height: int) -> Geometry:
        """Resolve recorded normalized coordinates without snapping/cropping."""
        draft = json.loads(Path(path).read_text(encoding='utf-8'))
        normalized = draft['normalized']

        def resolve(p):
            u, v = _point(p)
            if not (0 <= u <= 1 and 0 <= v <= 1):
                raise ValueError('Normalized template coordinate outside [0,1]')
            return (u * width, v * height)
        return cls(resolve(normalized['line']['P1']), resolve(normalized['line']['P2']), tuple((resolve(p) for p in normalized['side_a_polygon'])), tuple((resolve(p) for p in normalized['side_b_polygon'])), width, height, draft.get('draft_id', 'explicit-template'), draft.get('source_video', {}).get('sha256'), draft.get('status'))

    def side(self, point: Iterable[float]) -> str | None:
        states = (point_in_polygon(point, self.side_a), point_in_polygon(point, self.side_b))
        if 'boundary' in states:
            return None
        if states == ('inside', 'outside'):
            return 'A'
        if states == ('outside', 'inside'):
            return 'B'
        return None

    def as_dict(self) -> dict[str, Any]:
        return {'geometry_id': self.geometry_id, 'width': self.width, 'height': self.height, 'coordinate_space': 'native decoded-frame continuous image-edge pixels', 'line': {'P1': list(self.p1), 'P2': list(self.p2)}, 'side_a_polygon': [list(p) for p in self.side_a], 'side_b_polygon': [list(p) for p in self.side_b], 'video_sha256': self.video_sha256, 'source_draft_status': self.source_draft_status}

class GeometryStateMachine:
    """One track's measured trajectory, with no category/counting policy.

    Origin and destination require polygon interior and distance outside the
    experimental neutral band. Missing/predicted observations never bridge a
    passage. A successful transition rebases geometric origin, so future return
    diagnostics remain available while their business counting policy stays open.
    """

    def __init__(self, geometry: Geometry, *, neutral_band_px: float, confirmation_observations: int):
        if isinstance(neutral_band_px, bool) or not isinstance(neutral_band_px, Real) or (not math.isfinite(neutral_band_px)) or (neutral_band_px < 0):
            raise ValueError('neutral_band_px must be an explicit finite nonnegative value')
        if isinstance(confirmation_observations, bool) or not isinstance(confirmation_observations, int) or confirmation_observations < 1:
            raise ValueError('confirmation_observations must be an explicit positive integer')
        self.geometry = geometry
        self.neutral_band_px = float(neutral_band_px)
        self.confirmation_observations = confirmation_observations
        self.last_update_frame = None
        self.last_observed = None
        self.origin = None
        self.pending = None
        self.touch_sequence = None
        self.continuity_broken = False
        self.transition_sequence = 0

    def _observation(self, frame_index, point, metadata):
        distance = signed_distance(point, self.geometry.p1, self.geometry.p2)
        zero = abs(distance) <= _epsilon(point, self.geometry.p1, self.geometry.p2)
        sign = 0 if zero else 1 if distance > 0 else -1
        side = self.geometry.side(point)
        stable_side = side if abs(distance) > self.neutral_band_px and (not zero) else None
        return {'frame_index': frame_index, 'point': list(point), 'metadata': dict(metadata or {}), 'side': side, 'stable_side': stable_side, 'signed_distance_px': distance, 'sign': sign}

    def _diagnostic(self, kind, **fields):
        return {'type': kind, 'geometry_id': self.geometry.geometry_id, 'accepted_count_event': False, 'repeat_business_policy_open': True, **fields}

    def _establish_origin(self, observation, diagnostics):
        if observation['stable_side'] is not None:
            self.origin = observation
            diagnostics.append(self._diagnostic('ORIGIN_ESTABLISHED', origin_side=observation['stable_side'], origin_frame=observation['frame_index'], origin_point=observation['point'], metadata=observation['metadata']))

    def update(self, frame_index: int, point, *, observed: bool=True, metadata=None) -> list[dict[str, Any]]:
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise ValueError('frame_index must be a nonnegative integer')
        if self.last_update_frame is not None and frame_index <= self.last_update_frame:
            raise ValueError('Track updates must have strictly increasing frame indices')
        if not isinstance(observed, bool):
            raise ValueError('observed must explicitly be boolean')
        self.last_update_frame = frame_index
        diagnostics = []
        if not observed:
            self.pending = None
            self.touch_sequence = None
            self.continuity_broken = True
            return [self._diagnostic('PREDICTION_IGNORED', frame_index=frame_index, metadata=dict(metadata or {}))]
        point = _point(point)
        current = self._observation(frame_index, point, metadata)
        previous = self.last_observed
        if previous is not None and (frame_index != previous['frame_index'] + 1 or self.continuity_broken):
            intersection = segment_intersection(previous['point'], point, self.geometry.p1, self.geometry.p2)
            possible_passage = self.pending is not None or self.touch_sequence is not None or (self.origin is not None and (previous['stable_side'] != current['stable_side'] or previous['sign'] != current['sign'] or intersection['kind'] != 'none'))
            if possible_passage:
                diagnostics.append(self._diagnostic('AMBIGUOUS_GAP', previous_observation=previous, current_observation=current, missing_observation_frames=frame_index - previous['frame_index'] - 1, interpolation_used=False))
            self.origin = self.pending = self.touch_sequence = None
            self.last_observed = current
            self.continuity_broken = False
            self._establish_origin(current, diagnostics)
            return diagnostics
        self.continuity_broken = False
        if self.origin is None:
            self._establish_origin(current, diagnostics)
        elif previous is not None:
            intersection = segment_intersection(previous['point'], point, self.geometry.p1, self.geometry.p2)
            overlap_reaches_endpoint = intersection['kind'] == 'overlap' and any((_on_segment(endpoint, _point(previous['point']), point) for endpoint in (self.geometry.p1, self.geometry.p2)))
            if intersection['kind'] == 'endpoint' or overlap_reaches_endpoint:
                diagnostics.append(self._diagnostic('AMBIGUOUS_ENDPOINT', previous_observation=previous, current_observation=current, intersection=intersection))
                self.pending = self.touch_sequence = None
            else:
                crossing = None
                if intersection['kind'] == 'proper' and previous['sign'] * current['sign'] == -1:
                    crossing = {'intersection': intersection, 'start_observation': previous, 'end_observation': current, 'method': 'consecutive_measured_segment', 'entry_sign': previous['sign'], 'exit_sign': current['sign']}
                elif current['sign'] == 0 and intersection['kind'] in ('touch', 'overlap'):
                    if self.touch_sequence is None and previous['sign'] != 0:
                        self.touch_sequence = {'entry_sign': previous['sign'], 'start_observation': previous, 'first_touch_observation': current, 'last_touch_observation': current, 'intersection': intersection}
                    elif self.touch_sequence is not None:
                        self.touch_sequence['last_touch_observation'] = current
                elif previous['sign'] == 0 and current['sign'] != 0:
                    if self.touch_sequence is not None and current['sign'] == -self.touch_sequence['entry_sign']:
                        crossing = {'intersection': self.touch_sequence['intersection'], 'start_observation': self.touch_sequence['start_observation'], 'end_observation': current, 'method': 'measured_touch_then_opposite_sign', 'entry_sign': self.touch_sequence['entry_sign'], 'exit_sign': current['sign'], 'first_touch_observation': self.touch_sequence['first_touch_observation'], 'last_touch_observation': self.touch_sequence['last_touch_observation']}
                    self.touch_sequence = None
                if self.pending is not None and current['sign'] == self.pending['crossing']['entry_sign']:
                    self.pending = None
                if crossing is not None:
                    self.pending = {'origin': self.origin, 'crossing': crossing, 'confirmations': [], 'left_origin_region': current['side'] != self.origin['stable_side']}
                elif self.pending is not None:
                    if current['side'] != self.origin['stable_side']:
                        self.pending['left_origin_region'] = True
                    elif current['stable_side'] == self.origin['stable_side'] and self.pending['left_origin_region']:
                        self.pending = None
                if self.pending is not None:
                    destination = 'B' if self.origin['stable_side'] == 'A' else 'A'
                    if current['stable_side'] == destination and current['sign'] == self.pending['crossing']['exit_sign']:
                        self.pending['confirmations'].append(current)
                    else:
                        self.pending['confirmations'] = []
                    if len(self.pending['confirmations']) >= self.confirmation_observations:
                        crossing = self.pending['crossing']
                        self.transition_sequence += 1
                        diagnostics.append(self._diagnostic('GEOMETRY_TRANSITION', software_transition_sequence=self.transition_sequence, origin_side=self.origin['stable_side'], destination_side=destination, direction=f"{self.origin['stable_side']}_TO_{destination}", origin_frame=self.origin['frame_index'], origin_point=self.origin['point'], crossing_frame_start=crossing['start_observation']['frame_index'], crossing_frame_end=crossing['end_observation']['frame_index'], crossing_point=crossing['intersection']['point'], confirmation_frame=frame_index, confirmation_point=current['point'], origin_observation=self.origin, crossing_evidence=crossing, confirmation_observations=self.pending['confirmations'], metadata=current['metadata']))
                        self.origin = current
                        self.pending = self.touch_sequence = None
        self.last_observed = current
        return diagnostics

def replay_cached_records(records_path, geometry: Geometry, *, neutral_band_px: float, confirmation_observations: int) -> dict[str, Any]:
    """Stream existing ReID emitted observations; no model inference or totals.

    Only raw detector-linked boxes of persistent emitted tracks provide BC.
    All raw classes remain diagnostic inputs, not accepted product categories.
    Source links, dimensions, video identity and measurement provenance are
    validated; predictions/lifecycle boxes are never substituted.
    """
    GeometryStateMachine(geometry, neutral_band_px=neutral_band_px, confirmation_observations=confirmation_observations)
    path = Path(records_path)
    source_hash = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            source_hash.update(block)
    opener = gzip.open if path.suffix == '.gz' else open
    machines, diagnostics = ({}, [])
    frame_count = observation_count = 0
    previous_frame = None
    source_video_sha256 = None
    source_parent_run_id = source_variant = None
    with opener(path, 'rt', encoding='utf-8') as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                raise ValueError(f'Empty source record on line {line_number}')
            record = json.loads(line)
            frame = record['frame_index']
            if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0 or (previous_frame is not None and frame <= previous_frame):
                raise ValueError('Cached frame records must be strictly increasing nonnegative indices')
            previous_frame = frame
            frame_count += 1
            if (record['width'], record['height']) != (geometry.width, geometry.height):
                raise ValueError('Cached native dimensions do not match effective geometry')
            video_sha256 = record['video_sha256']
            if source_video_sha256 is None:
                source_video_sha256 = video_sha256
            if video_sha256 != source_video_sha256 or (geometry.video_sha256 is not None and video_sha256 != geometry.video_sha256):
                raise ValueError('Cached source video identity changed or does not match geometry')
            if frame_count == 1:
                source_parent_run_id, source_variant = (record['parent_run_id'], record['variant'])
            elif (record['parent_run_id'], record['variant']) != (source_parent_run_id, source_variant):
                raise ValueError('Cached parent run or variant changed within one replay input')
            raw_detections = record['raw_detections']
            frame_ids, frame_detection_indices = (set(), set())
            for observation in record['emitted_tracks']:
                track_id = observation['track_id']
                if isinstance(track_id, bool) or not isinstance(track_id, int) or track_id < 1 or (track_id in frame_ids):
                    raise ValueError('Emitted track IDs must be positive and unique within a frame')
                frame_ids.add(track_id)
                if observation['frame_index'] != frame or observation.get('emitted') is not True:
                    raise ValueError('Emitted measurement/frame contract mismatch')
                if observation.get('measurement_provenance') != 'retained_phase_2_detection':
                    raise ValueError('Geometry requires retained measured detection provenance')
                index = observation['original_detection_index']
                if isinstance(index, bool) or not isinstance(index, int) or (not 0 <= index < len(raw_detections)):
                    raise ValueError('Broken source-detection index')
                if index in frame_detection_indices:
                    raise ValueError('One source detection cannot supply two emitted track measurements in the same frame')
                frame_detection_indices.add(index)
                raw_bbox = observation['raw_bbox']
                if len(raw_bbox) != 4:
                    raise ValueError('Raw bbox must have four xyxy coordinates')
                a, b = (_point(raw_bbox[:2]), _point(raw_bbox[2:]))
                if a[0] >= b[0] or a[1] >= b[1]:
                    raise ValueError('Raw bbox must have positive width/height')
                detection = raw_detections[index]
                for confidence in (observation['confidence'], detection['confidence']):
                    if isinstance(confidence, bool) or not isinstance(confidence, Real) or (not math.isfinite(confidence)):
                        raise ValueError('Source and observation confidence must be finite numeric measurements')
                if list(raw_bbox) != detection['bbox_xyxy_pixels']:
                    raise ValueError('Raw bbox is not byte-value linked to source detection')
                if any((observation[key] != detection[key] for key in ('class_id', 'class_name', 'confidence'))):
                    raise ValueError('Track measurement class/confidence does not match linked source')
                metadata = {'track_id': track_id, 'video_sha256': video_sha256, 'parent_run_id': record['parent_run_id'], 'variant': record['variant'], 'original_detection_index': index, 'raw_bbox': list(raw_bbox), 'class_id': observation['class_id'], 'class_name': observation['class_name'], 'confidence': observation['confidence'], 'measurement_provenance': observation['measurement_provenance'], 'timestamp_estimate_from_index_fps_seconds': record.get('timestamp_estimate_from_index_fps_seconds'), 'timestamp_is_verified_source_pts': False}
                machine = machines.setdefault(track_id, GeometryStateMachine(geometry, neutral_band_px=neutral_band_px, confirmation_observations=confirmation_observations))
                anchor = ((a[0] + b[0]) / 2, b[1])
                for diagnostic in machine.update(frame, anchor, metadata=metadata):
                    diagnostics.append({'track_id': track_id, 'frame_index': frame, **diagnostic})
                observation_count += 1
    return {'diagnostics': diagnostics, 'report': {'claim_type': 'EXECUTED_SOFTWARE_GEOMETRY_DIAGNOSTICS_NOT_TRAFFIC_COUNTS', 'source_records_path': str(path), 'source_records_file_sha256': source_hash.hexdigest(), 'video_sha256': source_video_sha256, 'source_parent_run_id': source_parent_run_id, 'source_variant': source_variant, 'frames_processed': frame_count, 'emitted_measured_observations_processed': observation_count, 'software_track_ids': len(machines), 'software_diagnostic_counts': dict(Counter((d['type'] for d in diagnostics))), 'effective_geometry': geometry.as_dict(), 'anchor': 'raw_bbox_bottom_center', 'neutral_band_px': float(neutral_band_px), 'neutral_band_semantics': 'half-width per side', 'confirmation_observations': confirmation_observations, 'category_filter': 'none_all_raw_classes_are_diagnostic_inputs_only', 'detector_tracker_encoder_rerun': False, 'accepted_count_events_emitted': False, 'physical_identity_or_counting_accuracy_established': False, 'repeat_business_policy': 'OPEN', 'gap_policy': 'no interpolation; ambiguous passage; origin reset'}}
