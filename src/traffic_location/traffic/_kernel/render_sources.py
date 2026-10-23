"""Render-only Phase 8 audit video from immutable, selected result evidence.

This module does not detect, track, associate, classify, or count again. The
pivot replays the FINAL OFFLINE accepted-event ledger at retained geometry
confirmation frames. Category/identity evidence can occur later; this display
is explicitly not an online decision or latency measurement.
"""
from __future__ import annotations
from bisect import bisect_right
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
import math
from pathlib import Path
import time
VERSION = 'phase8_review_annotation_v1'
TIMELINE_SEMANTICS = 'OFFLINE_FINAL_SNAPSHOT_REPLAY_AT_GEOMETRY_CONFIRMATION_NOT_CAUSAL_DECISION_TIME'
DIRECTIONS = ('A_TO_B', 'B_TO_A')
CATEGORIES = ('motorcycle', 'car', 'truck', 'bus_angkot', 'pedestrian')
CATEGORY_COLORS = {'motorcycle': (95, 210, 250), 'car': (245, 175, 90), 'truck': (65, 125, 245), 'bus': (80, 190, 115), 'person': (210, 125, 245), 'other': (175, 180, 185)}
DISPLAY_CATEGORY = {'motorcycle': 'Motor', 'car': 'Mobil', 'truck': 'Truk', 'bus_angkot': 'Bus / angkot', 'pedestrian': 'Pejalan kaki'}

def _require(condition, message):
    if not condition:
        raise ValueError(message)

def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def _integer(value, name, minimum=0):
    _require(isinstance(value, int) and (not isinstance(value, bool)) and (value >= minimum), name + ' must be an integer >= ' + str(minimum))
    return value

def _finite(value, name):
    _require(isinstance(value, (int, float)) and (not isinstance(value, bool)) and math.isfinite(value), name + ' must be finite')
    return value

def _identifier(value, name):
    _require(isinstance(value, str) and bool(value.strip()), name + ' must be nonempty')
    return value

def _frame(value, frame_count, name):
    _integer(value, name)
    _require(value < frame_count, name + ' outside source frames')
    return value

def _bbox(value):
    _require(isinstance(value, (list, tuple)) and len(value) == 4, 'raw_bbox needs four coordinates')
    box = [_finite(number, 'raw_bbox coordinate') for number in value]
    _require(box[0] < box[2] and box[1] < box[3], 'raw_bbox has no positive area')
    return box

def _bc(box):
    return [(box[0] + box[2]) / 2.0, box[3]]

def load_json(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as handle:
        return json.load(handle)

def iter_json_array(path):
    """Stream large retained relation arrays without loading rejected graphs."""
    opener = gzip.open if str(path).endswith('.gz') else open
    decoder = json.JSONDecoder()
    with opener(path, 'rt', encoding='utf-8') as handle:
        buffer, position, started, finished, need_value = ('', 0, False, False, True)
        while not finished:
            if position >= len(buffer) or not buffer[position:].strip():
                buffer = buffer[position:] + handle.read(65536)
                position = 0
                if not buffer.strip():
                    raise ValueError('Truncated JSON array')
            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if not started:
                _require(buffer[position] == '[', 'Expected a retained JSON array')
                started = True
                position += 1
                continue
            if position >= len(buffer):
                continue
            char = buffer[position]
            if char == ']':
                position += 1
                finished = True
                break
            if not need_value:
                _require(char == ',', 'Missing JSON array separator')
                position += 1
                need_value = True
                while True:
                    while position < len(buffer) and buffer[position].isspace():
                        position += 1
                    if position < len(buffer):
                        _require(buffer[position] != ']', 'Trailing JSON array comma')
                        break
                    more = handle.read(65536)
                    _require(bool(more), 'Truncated JSON array')
                    buffer = buffer[position:] + more
                    position = 0
            while True:
                try:
                    value, end = decoder.raw_decode(buffer, position)
                    break
                except json.JSONDecodeError:
                    more = handle.read(65536)
                    _require(bool(more), 'Invalid or truncated JSON array item')
                    buffer = buffer[position:] + more
                    position = 0
            yield value
            position = end
            need_value = False
        _require(not (buffer[position:] + handle.read()).strip(), 'Trailing data after JSON array')

def _validated_geometry(event, identity, frame_count):
    diagnostic = event.get('geometry_evidence')
    _require(isinstance(diagnostic, dict) and diagnostic.get('type') == 'GEOMETRY_TRANSITION' and (diagnostic.get('accepted_count_event') is False), 'Accepted event requires retained measured geometry transition')
    frames = [diagnostic.get(key) for key in ('origin_frame', 'crossing_frame_start', 'crossing_frame_end', 'confirmation_frame')]
    for frame in frames:
        _frame(frame, frame_count, 'geometry frame')
    _require(frames == sorted(frames), 'Geometry frame order invalid')
    _require(event.get('direction') in DIRECTIONS and diagnostic.get('direction') == event['direction'], 'Geometry/event direction mismatch')
    _require(diagnostic.get('track_id') == event.get('track_id'), 'Geometry source track differs')
    support = event.get('measurement_support')
    _require(isinstance(support, list) and bool(support), 'Event lacks measured vehicle BC support')
    _require([item.get('frame_index') for item in support] == list(range(frames[0], frames[3] + 1)), 'Measured passage support must be contiguous origin through confirmation')
    for item in support:
        _require(item.get('track_id') == event['track_id'] and item.get('emitted') is True, 'Accepted passage must use emitted source vehicle track')
        _require(item.get('measurement_provenance') == 'retained_phase_8_detection', 'Expected actual retained Phase 8 measurement provenance')
        _integer(item.get('original_detection_index'), 'source detection index')
        _require(item.get('class_name') in ('motorcycle', 'car', 'truck', 'bus'), 'Person/other component cannot supply vehicle BC')
        _require(item.get('point') == _bc(_bbox(item.get('raw_bbox'))), 'Vehicle BC differs from raw measurement')
    for endpoint in ('origin_observation',):
        observation = diagnostic.get(endpoint)
        _require(isinstance(observation, dict), 'Geometry origin source observation missing')
        metadata = observation.get('metadata', {})
        for key in ('video_sha256', 'records_sha256', 'parent_run_id', 'variant'):
            _require(metadata.get(key) == identity.get(key), 'Geometry source mismatch: ' + key)
        _require(metadata.get('track_id') == event['track_id'] and observation.get('point') == _bc(_bbox(metadata.get('raw_bbox'))), 'Geometry origin BC/source mismatch')
    return frames

def build_review_timeline(events, decisions, relations, *, source_identity, frame_count, ledger_entries=None, video_id=None):
    """Validate a selected result snapshot and create an immutable display index.

    ``relations`` may be a generator: only IDs already used by accepted events
    are retained. Pending/exploratory component fields never create connectors.
    This is reconciliation and presentation, not a new identity/count resolver.
    """
    _integer(frame_count, 'frame_count', 1)
    _require(isinstance(events, list) and isinstance(decisions, list), 'Events/decisions must be arrays')
    for key in ('video_sha256', 'records_sha256', 'geometry_sha256', 'parent_run_id', 'variant'):
        _identifier(source_identity.get(key), 'source identity ' + key)
    _require(source_identity['variant'] == 'raw', 'This review renderer preserves raw Phase 8 source pixels')
    by_candidate, pending = ({}, [])
    for decision in decisions:
        candidate_id = _identifier(decision.get('candidate_id'), 'candidate ID')
        _require(candidate_id not in by_candidate, 'Duplicate candidate decision')
        by_candidate[candidate_id] = decision
        _integer(decision.get('track_id'), 'decision track', 1)
        diagnostic = decision.get('diagnostic')
        _require(isinstance(diagnostic, dict), 'Candidate diagnostic missing')
        frame = _frame(diagnostic.get('frame_index'), frame_count, 'candidate frame')
        if decision.get('status') == 'pending_review':
            _require(decision.get('accepted_count_event') is False, 'Pending candidate cannot contribute count')
            pending.append({'candidate_id': candidate_id, 'frame': frame, 'track_id': decision['track_id'], 'category': decision.get('category'), 'diagnostic_type': diagnostic.get('type'), 'reasons': list(dict.fromkeys(decision.get('hard_block_reasons', []) + decision.get('reasons', [])))})
    selected, event_ids, physical_passages, representative_candidates = ([], set(), set(), set())
    for event in events:
        _require(event.get('type') == 'CountEvent' and event.get('status') == 'accepted' and (event.get('accepted_count_event') is True), 'Only selected accepted CountEvents enter pivot')
        event_id = _identifier(event.get('event_id'), 'event ID')
        _require(event_id not in event_ids, 'Duplicate event ID')
        event_ids.add(event_id)
        unit = _identifier(event.get('physical_unit_id'), 'physical unit ID')
        passage = _identifier(event.get('passage_id'), 'passage ID')
        _require((unit, passage) not in physical_passages, 'Duplicate physical unit/passage')
        physical_passages.add((unit, passage))
        _require(event.get('source_identity') == source_identity, 'Event belongs to another source snapshot')
        _require(event.get('category') in ('motorcycle', 'car', 'truck'), 'Unsupported accepted category for frozen B v1 coverage')
        _require(event.get('is_causal_online_decision') is False, 'Offline result semantics must be explicit')
        decision = by_candidate.get(event.get('candidate_id'))
        _require(decision is not None and decision.get('status') == 'accepted' and (decision.get('accepted_count_event') is True), 'Event lacks accepted representative decision')
        for key in ('event_id', 'category', 'track_id', 'physical_unit_id', 'passage_id'):
            _require(decision.get(key) == event.get(key), 'Accepted event/decision mismatch: ' + key)
        _require(not decision.get('reasons') and (not decision.get('hard_block_reasons')), 'Accepted representative retains unresolved conflicts')
        _require(decision.get('diagnostic') == event.get('geometry_evidence') and decision.get('measurement_support') == event.get('measurement_support'), 'Event changed retained geometry/raw BC support')
        _require(decision.get('episode_id') == event.get('vehicle_measurement_episode_id'), 'Event/decision measurement episode mismatch')
        for key in ('component_episode_ids', 'vehicle_episode_ids', 'identity_relation_ids', 'passage_identity_relation_evidence'):
            _require(decision.get(key) == event.get(key), 'Event/decision association mismatch: ' + key)
        representative_candidates.add(event['candidate_id'])
        origin, crossing_start, crossing_end, confirmation = _validated_geometry(event, source_identity, frame_count)
        latest = _frame(event.get('category_decision_latest_evidence_frame'), frame_count, 'category evidence frame')
        _require(latest >= confirmation, 'Full-episode category evidence ends before confirmation')
        selected.append({'event': deepcopy(event), 'activation_frame': confirmation, 'origin_frame': origin, 'crossing_start': crossing_start, 'crossing_end': crossing_end, 'category_latest_evidence_frame': latest})
    _require({cid for cid, decision in by_candidate.items() if decision.get('accepted_count_event') is True} == representative_candidates, 'Representative decisions and accepted ledger differ')
    if ledger_entries is not None:
        _identifier(video_id, 'video ID')
        ledger = [entry for entry in ledger_entries if entry.get('video_id') == video_id]
        _require(len(ledger) == len(events), 'Selected video ledger event count differs')
        _require(len({item.get('source_event_id') for item in ledger}) == len(ledger), 'Repeated ledger event')
        by_event = {event['event_id']: event for event in events}
        kinds, runs = (set(), set())
        for entry in ledger:
            _require(entry.get('source_identity') == source_identity, 'Ledger source snapshot differs')
            _require(entry.get('source_event_id') in by_event and entry.get('event') == by_event[entry['source_event_id']], 'Ledger and selected event payload differ')
            _require(entry.get('category') == entry['event']['category'] and entry.get('direction') == entry['event']['direction'], 'Ledger category/direction mismatch')
            kinds.add(entry.get('snapshot_kind'))
            runs.add(entry.get('run_id'))
        _require(len(kinds) <= 1 and len(runs) <= 1 and (kinds <= {'machine', 'reviewed'}), 'Ledger mixes machine/reviewed or rerun snapshots')
    selected.sort(key=lambda item: (item['activation_frame'], item['event']['event_id']))
    units = {unit: f'U{index + 1:03d}' for index, unit in enumerate(sorted({item['event']['physical_unit_id'] for item in selected}))}
    wanted_relations = {rid for item in selected for rid in item['event'].get('identity_relation_ids', [])}
    relation_index = {}
    for relation in relations:
        rid = relation.get('relation_id')
        if rid in wanted_relations:
            _require(rid not in relation_index, 'Duplicate retained identity relation')
            relation_index[rid] = relation
    _require(set(relation_index) == wanted_relations, 'Accepted identity relation evidence missing')
    connections, measurements, crossing_frames, event_cards = (defaultdict(list), defaultdict(dict), defaultdict(list), [])
    for index, item in enumerate(selected, 1):
        event = item['event']
        item['event_alias'] = f'E{index:03d}'
        item['unit_alias'] = units[event['physical_unit_id']]
        local = {entry['relation_id']: entry for entry in event.get('passage_identity_relation_evidence', [])}
        component_track_ids, supporting_vehicle_ids = (set(), {event['track_id']})
        for rid in event.get('identity_relation_ids', []):
            relation, evidence = (relation_index[rid], local.get(rid))
            _require(relation.get('status') == 'SUPPORTED' and evidence is not None and (evidence.get('status') == 'SUPPORTED'), 'Accepted identity lacks supported local relation')
            kind = relation.get('type')
            _require(kind in ('COMPONENT_OF', 'SAME_VEHICLE') and evidence.get('type') == kind, 'Identity relation type mismatch')
            first, second = (relation.get('first_episode_id'), relation.get('second_episode_id'))
            vehicle_ids, component_ids = (event.get('vehicle_episode_ids', []), event.get('component_episode_ids', []))
            _require(second in vehicle_ids and first in (component_ids if kind == 'COMPONENT_OF' else vehicle_ids), 'Accepted relation points outside event member episodes')
            first_track = _integer(relation.get('first_track_id'), 'relation first track', 1)
            second_track = _integer(relation.get('second_track_id'), 'relation second track', 1)
            (component_track_ids if kind == 'COMPONENT_OF' else supporting_vehicle_ids).add(first_track)
            supporting_vehicle_ids.add(second_track)
            frames = evidence.get('features', {}).get('common_frame_indices')
            _require(isinstance(frames, list) and bool(frames) and (frames == sorted(set(frames))), 'Accepted local relation needs unique measured common frames')
            global_frames = set(relation.get('features', {}).get('common_frame_indices', []))
            _require(evidence.get('passage_support_window') == [item['origin_frame'], item['activation_frame']], 'Relation passage support window differs')
            for frame in frames:
                _frame(frame, frame_count, 'relation support frame')
                _require(item['origin_frame'] <= frame <= item['activation_frame'] and frame in global_frames, 'Relation support lies outside measured passage/global support')
                connections[frame].append({'first_track_id': first_track, 'second_track_id': second_track, 'type': kind, 'event_alias': item['event_alias'], 'unit_alias': item['unit_alias'], 'event_id': event['event_id'], 'relation_id': rid})
        for observation in event['measurement_support']:
            frame = observation['frame_index']
            key = (event['track_id'], observation['original_detection_index'])
            existing = measurements[frame].get(key)
            _require(existing is None or existing['observation'] == observation, 'Conflicting accepted raw source observation')
            measurements[frame][key] = {'observation': deepcopy(observation), 'event_alias': item['event_alias'], 'unit_alias': item['unit_alias']}
        for frame in range(item['crossing_start'], item['crossing_end'] + 1):
            crossing_frames[frame].append(item)
        event_cards.append({'event_alias': item['event_alias'], 'unit_alias': item['unit_alias'], 'event_id': event['event_id'], 'candidate_id': event['candidate_id'], 'physical_unit_id': event['physical_unit_id'], 'passage_id': event['passage_id'], 'category': event['category'], 'direction': event['direction'], 'source_vehicle_track_id': event['track_id'], 'supporting_vehicle_track_ids': sorted(supporting_vehicle_ids), 'component_track_ids': sorted(component_track_ids), 'activation_frame': item['activation_frame'], 'origin_frame': item['origin_frame'], 'crossing_start': item['crossing_start'], 'crossing_end': item['crossing_end'], 'category_latest_evidence_frame': item['category_latest_evidence_frame'], 'identity_latest_evidence_frame': event.get('identity_decision_latest_evidence_frame'), 'replay_is_causal': False, 'accepted_increment': 1, 'component_additional_increment': 0})
    pending.sort(key=lambda item: (item['frame'], item['candidate_id']))
    return {'semantics': TIMELINE_SEMANTICS, 'frame_count': frame_count, 'source_identity': deepcopy(source_identity), 'events': selected, 'event_cards': event_cards, 'activation_frames': [item['activation_frame'] for item in selected], 'pending': pending, 'pending_frames': [item['frame'] for item in pending], 'connections_by_frame': dict(connections), 'source_measurements_by_frame': dict(measurements), 'crossings_by_frame': dict(crossing_frames), 'final_accepted': len(selected), 'final_pending': len(pending), 'decision_status_counts': dict(Counter((decision.get('status') for decision in decisions)))}

def timeline_at(timeline, frame_index):
    """Pure display pivot: unique selected events only, never bbox/ID totals."""
    _frame(frame_index, timeline['frame_count'], 'replay frame')
    n = bisect_right(timeline['activation_frames'], frame_index)
    pending_n = bisect_right(timeline['pending_frames'], frame_index)
    pivot = {category: {direction: 0 if category in ('motorcycle', 'car', 'truck') else None for direction in DIRECTIONS} for category in CATEGORIES}
    for item in timeline['events'][:n]:
        event = item['event']
        pivot[event['category']][event['direction']] += 1
    _require(sum((value for row in pivot.values() for value in row.values() if value is not None)) == n, 'Pivot reconciliation failed')
    return {'frame_index': frame_index, 'accepted_so_far': n, 'accepted_final': timeline['final_accepted'], 'pending_so_far': pending_n, 'pending_final': timeline['final_pending'], 'pivot': pivot, 'recent_events': list(reversed(timeline['event_cards'][:n][-3:])), 'recent_pending': list(reversed(timeline['pending'][:pending_n][-2:])), 'connections': deepcopy(timeline['connections_by_frame'].get(frame_index, [])), 'crossings': timeline['crossings_by_frame'].get(frame_index, [])}

def _validate_record(record, frame, identity, image):
    _require(record.get('frame_index') == frame, 'Record/source frame alignment failed')
    for key in ('video_sha256', 'parent_run_id', 'variant', 'width', 'height'):
        _require(record.get(key) == identity.get(key), 'Source record identity mismatch: ' + key)
    donor = record.get('detector_input_frame_pixel_sha256')
    _require(isinstance(donor, str) and hashlib.sha256(image.tobytes()).hexdigest() == donor, 'Decoded source pixels differ from retained detector input; use compatible decoder')
    raw, observations = (record.get('raw_detections'), record.get('emitted_tracks'))
    _require(isinstance(raw, list) and isinstance(observations, list), 'Missing retained measured source arrays')
    by_track, seen_detection = ({}, set())
    for observation in observations:
        track = _integer(observation.get('track_id'), 'source track', 1)
        _require(track not in by_track, 'Duplicate emitted source track/frame')
        index = _integer(observation.get('original_detection_index'), 'source detection index')
        _require(index < len(raw) and index not in seen_detection, 'Broken or repeated emitted detection link')
        _require(observation.get('frame_index') == frame and observation.get('emitted') is True and (observation.get('measurement_provenance') == 'retained_phase_8_detection'), 'Only retained raw measured emitted observations may be drawn')
        box = _bbox(observation.get('raw_bbox'))
        detection = raw[index]
        _require(box == detection.get('bbox_xyxy_pixels') and all((observation.get(key) == detection.get(key) for key in ('class_name', 'class_id', 'confidence'))), 'Emitted bbox/class differs from linked raw detector measurement')
        by_track[track] = observation
        seen_detection.add(index)
    return by_track

def _text(image, text, position, *, scale=0.46, color=(225, 232, 239), thickness=1):
    import cv2
    cv2.putText(image, str(text), position, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

def _wrap(text, max_chars):
    words, lines, line = (str(text).split(), [], '')
    for word in words:
        if len(line) + len(word) + 1 > max_chars and line:
            lines.append(line)
            line = ''
        line += (' ' if line else '') + word
    if line:
        lines.append(line)
    return lines

def _label(image, text, x, y, color, max_width):
    import cv2
    scale, thickness = (0.38, 1)
    (width, height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    width = min(width + 8, max_width)
    x = max(0, min(int(x), image.shape[1] - width))
    y = max(height + 7, min(int(y), image.shape[0] - baseline - 2))
    cv2.rectangle(image, (x, y - height - 5), (x + width, y + baseline), color, -1)
    _text(image, text, (x + 4, y - 2), scale=scale, color=(15, 20, 25))

def render_review_frame(source_frame, record, timeline, geometry, *, fps, video_id, panel_width=520, footer_height=240):
    """Return an expanded audit canvas. Native road image is never resized."""
    import cv2
    import numpy as np
    _require(panel_width >= 500 and footer_height >= 240, 'Review layout needs readable panel/footer space')
    image = source_frame.copy()
    h, w = image.shape[:2]
    identity = timeline['source_identity']
    _require((w, h) == (identity['width'], identity['height']), 'Native source dimensions differ')
    frame_index = record.get('frame_index')
    by_track = _validate_record(record, frame_index, identity, source_frame)
    state = timeline_at(timeline, frame_index)
    linked_indices = {observation['original_detection_index'] for observation in record['emitted_tracks']}
    raw_only = [(index, detection) for index, detection in enumerate(record['raw_detections']) if index not in linked_indices]
    state['raw_only_detection_count'] = len(raw_only)
    for index, detection in raw_only:
        box = _bbox(detection.get('bbox_xyxy_pixels'))
        raw_class = _identifier(detection.get('class_name'), 'raw-only class')
        color = CATEGORY_COLORS.get(raw_class, CATEGORY_COLORS['other'])
        cv2.rectangle(image, (round(box[0]), round(box[1])), (round(box[2]), round(box[3])), color, 1, cv2.LINE_AA)
        _label(image, f'DET {index} | {raw_class} | no track +0', box[0], box[1] - 5, color, w)
    native_geometry = geometry.get('rendered_native_pixels', {})
    _require((native_geometry.get('width'), native_geometry.get('height')) == (w, h), 'Geometry native frame differs')
    for key, color, letter in (('side_a_polygon', (235, 155, 65), 'A'), ('side_b_polygon', (65, 155, 245), 'B')):
        polygon = np.array(native_geometry[key], dtype=float)
        cv2.polylines(image, [np.rint(polygon).astype(np.int32)], True, color, 1, cv2.LINE_AA)
        point = tuple(np.rint(polygon.mean(axis=0)).astype(int))
        _label(image, letter, point[0], point[1], color, w)
    line = native_geometry['line']
    p1, p2 = (tuple((round(v) for v in line[key])) for key in ('P1', 'P2'))
    cv2.line(image, p1, p2, (70, 235, 250), 2, cv2.LINE_AA)
    for connection in state['connections']:
        first = by_track.get(connection['first_track_id'])
        second = by_track.get(connection['second_track_id'])
        _require(first is not None and second is not None, 'Retained local relation lacks simultaneous measured source observations')
        if connection['type'] == 'COMPONENT_OF':
            _require(first['class_name'] == 'person' and second['class_name'] in ('motorcycle', 'car', 'truck', 'bus'), 'Component relation disagrees with current raw unit families')
        first_point = (round((first['raw_bbox'][0] + first['raw_bbox'][2]) / 2), round((first['raw_bbox'][1] + first['raw_bbox'][3]) / 2))
        second_point = (round((second['raw_bbox'][0] + second['raw_bbox'][2]) / 2), round((second['raw_bbox'][1] + second['raw_bbox'][3]) / 2))
        cv2.line(image, first_point, second_point, (160, 225, 180), 1, cv2.LINE_AA)
    measured = timeline['source_measurements_by_frame'].get(frame_index, {})
    for observation in record['emitted_tracks']:
        track, box, raw_class = (observation['track_id'], observation['raw_bbox'], observation['class_name'])
        color = CATEGORY_COLORS.get(raw_class, CATEGORY_COLORS['other'])
        cv2.rectangle(image, (round(box[0]), round(box[1])), (round(box[2]), round(box[3])), color, 2, cv2.LINE_AA)
        text = f'ID {track} | {raw_class}'
        _label(image, text, box[0], box[1] - 5, color, w)
        if raw_class in ('motorcycle', 'car', 'truck', 'bus'):
            point = tuple((round(v) for v in _bc(box)))
            cv2.circle(image, point, 4, (15, 20, 25), -1, cv2.LINE_AA)
            cv2.circle(image, point, 3, color, -1, cv2.LINE_AA)
        source = measured.get((track, observation['original_detection_index']))
        if source:
            _require(source['observation']['raw_bbox'] == observation['raw_bbox'], 'Accepted BC source differs from record')
            _label(image, source['unit_alias'] + ' / ' + source['event_alias'] + ' vehicle BC', box[0], box[3] + 15, (150, 225, 180), w)
        for connection in state['connections']:
            if connection['type'] == 'COMPONENT_OF' and track == connection['first_track_id']:
                _label(image, f"{connection['unit_alias']} component +0", box[0], box[3] + 15, (150, 225, 180), w)
    for crossing in state['crossings']:
        point = crossing['event']['geometry_evidence'].get('crossing_point')
        if point is not None:
            point = tuple((round(v) for v in point))
            cv2.drawMarker(image, point, (255, 255, 255), cv2.MARKER_CROSS, 16, 2, cv2.LINE_AA)
    canvas_height = max(h + footer_height, 680)
    canvas = np.full((canvas_height, w + panel_width, 3), (20, 25, 33), dtype=np.uint8)
    canvas[:h, :w] = image
    cv2.rectangle(canvas, (w, 0), (w + panel_width - 1, canvas_height - 1), (27, 34, 44), -1)
    x, right = (w + 20, w + panel_width - 20)
    _text(canvas, 'REVIEW PASSAGE KENDARAAN', (x, 29), scale=0.6, color=(245, 247, 250), thickness=2)
    _text(canvas, video_id, (x, 53), scale=0.49, color=(170, 192, 211))
    _text(canvas, 'OFFLINE FINAL SNAPSHOT', (x, 78), scale=0.48, color=(100, 205, 250), thickness=1)
    _text(canvas, 'Replay konfirmasi geometri; bukan keputusan online', (x, 98), scale=0.37)
    cv2.line(canvas, (x, 112), (right, 112), (65, 76, 91), 1)
    _text(canvas, 'PASSAGE ACCEPTED', (x, 138), scale=0.48, thickness=1)
    _text(canvas, f"{state['accepted_so_far']} / {state['accepted_final']}", (right - 120, 138), scale=0.7, color=(150, 235, 185), thickness=2)
    _text(canvas, 'replay / akhir video', (right - 130, 158), scale=0.34)
    _text(canvas, 'Kategori', (x, 188), scale=0.43, color=(170, 190, 210))
    _text(canvas, 'A > B', (x + 207, 188), scale=0.43, color=(170, 190, 210))
    _text(canvas, 'B > A', (x + 309, 188), scale=0.43, color=(170, 190, 210))
    _text(canvas, 'Total', (x + 411, 188), scale=0.43, color=(170, 190, 210))
    for index, category in enumerate(CATEGORIES):
        y = 218 + index * 29
        color = CATEGORY_COLORS.get(category, (150, 160, 175))
        cv2.rectangle(canvas, (x, y - 11), (x + 8, y - 3), color, -1)
        _text(canvas, DISPLAY_CATEGORY[category], (x + 17, y), scale=0.43)
        row = state['pivot'][category]
        supported = category in ('motorcycle', 'car', 'truck')
        values = [str(row[direction]) for direction in DIRECTIONS] + [str(sum(row.values()))] if supported else ['--'] * 3
        for offset, value in zip((228, 330, 424), values):
            _text(canvas, value, (x + offset, y), scale=0.49, color=(220, 234, 241), thickness=1)
    _text(canvas, 'A>B mendekati kamera | B>A menjauhi kamera', (x, 367), scale=0.36, color=(170, 192, 211))
    _text(canvas, '-- cakupan belum didukung; nol != tidak ada', (x, 387), scale=0.35, color=(170, 192, 211))
    cv2.line(canvas, (x, 400), (right, 400), (65, 76, 91), 1)
    _text(canvas, f"PENDING  {state['pending_so_far']} / {state['pending_final']}", (x, 425), scale=0.48, color=(100, 205, 250), thickness=1)
    _text(canvas, 'Kandidat, bukan kendaraan unik; di luar subtotal', (x, 446), scale=0.36)
    _text(canvas, 'ACCEPTED TERAKHIR / +1 PER EVENT', (x, 476), scale=0.4, color=(170, 192, 211))
    if not state['recent_events']:
        _text(canvas, 'Belum ada accepted pada posisi replay ini', (x, 504), scale=0.4)
    for index, event in enumerate(state['recent_events']):
        y = 500 + index * 55
        direction = event['direction'].replace('_TO_', '>')
        _text(canvas, f"{event['event_alias']}  {event['unit_alias']}  {event['category']}  {direction}  +1", (x, y), scale=0.42, color=(155, 230, 185))
        components = ','.join((str(track) for track in event['component_track_ids'])) or 'none'
        _text(canvas, f"BC ID {event['source_vehicle_track_id']} | component IDs {components}", (x, y + 17), scale=0.34)
        _text(canvas, f"confirm f{event['activation_frame']} | category evidence <= f{event['category_latest_evidence_frame']}", (x, y + 34), scale=0.33, color=(170, 192, 211))
    _text(canvas, f"FRAME {frame_index:06d} / {timeline['frame_count'] - 1:06d}", (16, h + 28), scale=0.62, color=(245, 247, 250), thickness=2)
    _text(canvas, f't ~= {frame_index / fps:8.3f}s  |  index / FPS; source PTS unknown', (16, h + 52), scale=0.43)
    _text(canvas, 'MEASURED BOX COLOR = CURRENT RAW CLASS', (16, h + 81), scale=0.43, color=(170, 192, 211))
    for index, label in enumerate(('motorcycle', 'car', 'truck', 'bus', 'person', 'other')):
        lx = 16 + index * 102
        cv2.rectangle(canvas, (lx, h + 95), (lx + 9, h + 104), CATEGORY_COLORS[label], -1)
        _text(canvas, label, (lx + 13, h + 105), scale=0.31)
    _text(canvas, 'BC dot = raw vehicle measurement  |  white cross = retained crossing', (16, h + 129), scale=0.37)
    _text(canvas, 'Komponen rider +0; kendaraan + komponen = SATU event accepted.', (16, h + 151), scale=0.36)
    _text(canvas, f'DET tanpa track: {len(raw_only)} (+0). ID pascaocclusion belum diperbaiki.', (16, h + 173), scale=0.35, color=(160, 180, 200))
    if state['recent_pending']:
        pending = state['recent_pending'][0]
        _text(canvas, f"LAST PENDING: ID {pending['track_id']} | f{pending['frame']} | {pending['diagnostic_type']}", (16, h + 198), scale=0.36, color=(100, 205, 250))
        reason = ', '.join(pending['reasons']) or 'Unresolved; inspect retained decision evidence'
        _text(canvas, _wrap(reason.replace('_', ' '), 85)[0], (16, h + 220), scale=0.34)
    return (canvas, state)

def _records(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as handle:
        for line in handle:
            _require(bool(line.strip()), 'Empty source record')
            yield json.loads(line)

def render_review_video(video_path, records_path, geometry_path, decisions_path, events_path, relations_path, output_dir, *, source_identity, fps, expected_frame_count, video_id, ledger_path, expected_input_sha256=None, preview_frames=(), progress=None):
    """Re-render all source frames, decode-check MP4, and retain an audit report.

    No model/runtime dependency is imported. Output must be a new empty folder;
    original videos, original annotated MP4s and scientific results stay intact.
    Optional expected_input_sha256 maps the input keys below to original donor
    retention hashes, adding explicit transport validation to source bindings.
    """
    import cv2
    start = time.perf_counter()
    _finite(fps, 'fps')
    _require(fps > 0, 'FPS must be positive')
    _integer(expected_frame_count, 'expected_frame_count', 1)
    _identifier(video_id, 'video ID')
    paths = {'video': Path(video_path), 'records': Path(records_path), 'geometry': Path(geometry_path), 'decisions': Path(decisions_path), 'events': Path(events_path), 'relations': Path(relations_path), 'ledger': Path(ledger_path)}
    inputs = {key: {'path': str(path), 'sha256': sha256_file(path), 'size_bytes': path.stat().st_size} for key, path in paths.items()}
    for key, field in (('video', 'video_sha256'), ('records', 'records_sha256'), ('geometry', 'geometry_sha256')):
        _require(inputs[key]['sha256'] == source_identity.get(field), 'Input/source SHA mismatch: ' + key)
    for key, expected in (expected_input_sha256 or {}).items():
        _require(key in inputs and inputs[key]['sha256'] == expected, 'Original donor retention SHA mismatch: ' + key)
    _require(expected_input_sha256 is not None and {'decisions', 'events', 'relations', 'ledger'} <= set(expected_input_sha256), 'Donor hashes required for decisions/events/relations/ledger')
    geometry = load_json(paths['geometry'])
    _require(geometry.get('source_video', {}).get('sha256') == source_identity['video_sha256'], 'Geometry belongs to another source video')
    _require(geometry.get('geometry_review_confirmed') is True and geometry.get('geometry_contract_accepted') is True, 'Geometry lacks initial trial review')
    events, decisions, ledger = (load_json(paths[key]) for key in ('events', 'decisions', 'ledger'))
    timeline = build_review_timeline(events, decisions, iter_json_array(paths['relations']), source_identity=source_identity, frame_count=expected_frame_count, ledger_entries=ledger, video_id=video_id)
    event_file_hash = inputs['events']['sha256']
    _require(all((entry.get('snapshot_events_sha256') == event_file_hash for entry in ledger if entry.get('video_id') == video_id)), 'Selected ledger snapshot event hash differs')
    target = Path(output_dir)
    _require(not target.exists() or not any(target.iterdir()), 'Choose a new empty output directory; original results are immutable')
    _require(all((target.resolve() != path.resolve().parent for path in paths.values())), 'Output cannot be an input directory')
    target.mkdir(parents=True, exist_ok=True)
    preview = {_frame(frame, expected_frame_count, 'preview frame') for frame in preview_frames}
    preview.update((0, expected_frame_count - 1))
    if timeline['event_cards']:
        first = timeline['event_cards'][0]
        preview.update((first['origin_frame'], first['crossing_start'], first['activation_frame']))
    preview.update(list(sorted(timeline['connections_by_frame']))[:1])
    capture = cv2.VideoCapture(str(video_path))
    _require(capture.isOpened(), 'Source video decoder unavailable')
    writer, count, dimension, preview_records = (None, 0, None, [])
    output_path = target / 'annotated_review.mp4'
    try:
        for record in _records(records_path):
            ok, frame = capture.read()
            _require(ok and record.get('frame_index') == count, 'Source/cache contiguous full-frame alignment failed')
            canvas, state = render_review_frame(frame, record, timeline, geometry, fps=fps, video_id=video_id)
            if writer is None:
                dimension = (canvas.shape[1], canvas.shape[0])
                _require(dimension[0] % 2 == 0 and dimension[1] % 2 == 0, 'MP4 canvas dimensions must be even')
                writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*'mp4v'), fps, dimension)
                _require(writer.isOpened(), 'MP4v writer unavailable; no silent codec substitution')
            writer.write(canvas)
            if count in preview:
                path = target / f'preview_frame_{count:09d}.png'
                _require(cv2.imwrite(str(path), canvas), 'Preview PNG writer failed')
                preview_records.append({'path': path.name, 'sha256': sha256_file(path), 'frame_index': count, 'accepted_so_far': state['accepted_so_far'], 'pending_so_far': state['pending_so_far']})
            count += 1
            if progress and (count % 500 == 0 or count == expected_frame_count):
                progress({'video_id': video_id, 'frames_rendered': count, 'expected_frame_count': expected_frame_count})
        more, _ = capture.read()
        _require(not more and count == expected_frame_count, 'Source/cache/manifest full-frame counts differ')
    finally:
        capture.release()
        if writer is not None:
            writer.release()
    _require(writer is not None, 'No source frames rendered')
    verify, decoded = (cv2.VideoCapture(str(output_path)), 0)
    try:
        _require(verify.isOpened(), 'Written review video cannot be reopened')
        while True:
            ok, image = verify.read()
            if not ok:
                break
            _require((image.shape[1], image.shape[0]) == dimension, 'Written canvas dimensions changed')
            decoded += 1
    finally:
        verify.release()
    _require(decoded == count, 'Review MP4 re-decoded frame count differs')
    for key, path in paths.items():
        _require(sha256_file(path) == inputs[key]['sha256'], 'Input changed during rendering: ' + key)
    final = timeline_at(timeline, expected_frame_count - 1)
    audit_path = target / 'passage_display_index.json'
    audit_path.write_text(json.dumps({'schema_version': VERSION, 'semantics': TIMELINE_SEMANTICS, 'events': timeline['event_cards'], 'pending_candidates': timeline['pending'], 'final_pivot': final['pivot'], 'final_accepted': timeline['final_accepted'], 'final_pending': timeline['final_pending']}, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    report = {'schema_version': VERSION, 'claim_type': 'ACTUAL_RENDER_ONLY_RESULT_REPLAY_NOT_NEW_MODEL_OR_COUNTING_RUN', 'video_id': video_id, 'timeline_semantics': TIMELINE_SEMANTICS, 'source_identity': deepcopy(source_identity), 'inputs': inputs, 'source_image_region': {'x': 0, 'y': 0, 'width': source_identity['width'], 'height': source_identity['height'], 'resized': False, 'coordinate_transform': 'IDENTITY_NATIVE_TOP_LEFT'}, 'canvas': {'width': dimension[0], 'height': dimension[1], 'sidebar_width': 520, 'footer_minimum_height': 240}, 'output_video': {'path': output_path.name, 'sha256': sha256_file(output_path), 'size_bytes': output_path.stat().st_size, 'codec': 'mp4v', 'frames_written': count, 'frames_redecoded': decoded, 'fps': fps, 'source_audio_preserved': False, 'timestamp_semantics': 'frame_index/FPS; source PTS unknown'}, 'final_accepted': timeline['final_accepted'], 'final_pending_candidates': timeline['final_pending'], 'final_pivot': final['pivot'], 'decision_status_counts': timeline['decision_status_counts'], 'category_coverage': {'motorcycle': 'experimental_vehicle_passage', 'car': 'experimental_vehicle_passage', 'truck': 'experimental_vehicle_passage', 'bus_angkot': 'BUS_ANGKOT_MAPPING_OPEN', 'pedestrian': 'NOT_IMPLEMENTED_BY_FROZEN_B_V1'}, 'source_pixel_hash_verified_every_frame': True, 'inputs_unchanged_after_render': True, 'new_detector_tracker_encoder_inference': False, 'counting_or_identity_resolver_rerun': False, 'occlusion_identity_recovery_modified': False, 'category_color_basis': 'CURRENT_RAW_MEASURED_CLASS', 'component_connector_policy': 'ACCEPTED_EVENT_SUPPORTED_PASSAGE_LOCAL_MEASURED_COMMON_FRAMES_ONLY', 'accepted_increment_policy': 'ONE_UNIQUE_EVENT_PER_PHYSICAL_UNIT_PASSAGE; COMPONENT_ADDITIONAL_INCREMENT_ZERO', 'pending_excluded_from_pivot': True, 'previews': preview_records, 'passage_display_index': {'path': audit_path.name, 'sha256': sha256_file(audit_path)}, 'opencv_version': cv2.__version__, 'render_and_decode_wall_seconds': time.perf_counter() - start, 'software_source_sha256': sha256_file(__file__)}
    (target / 'annotation_report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return report
