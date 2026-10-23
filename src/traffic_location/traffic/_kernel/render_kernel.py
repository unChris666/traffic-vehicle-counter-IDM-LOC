"""B v6 render-only audit: exact observation roles and readable raw-ID callouts.

The B v3 log compiler is extended locally for BUS and invalid audit rows.
Old modules remain unchanged. Layout does not resolve
identity, propagate roles, create observations, or recompute counting. Native
source pixels are not resized; a fixed, separately reserved audit area carries
labels which cannot be placed without collision inside the image.
"""
from __future__ import annotations
from bisect import bisect_right
from collections import defaultdict
from copy import deepcopy
import gzip
import json
from pathlib import Path
import csv
import hashlib
import shutil
import subprocess
import time
from . import render_base as previous
frozen = previous.frozen
VERSION = 'phase8_b_v6_annotation_v1'
SEMANTICS = 'Offline final accepted ledger replay; cancelled/invalid source candidates are audit-only +0 at every frame. Measured/inferred remains source-time scoped.'
VEHICLE_CATEGORIES = ('motorcycle', 'car', 'truck', 'bus')
CATEGORIES = VEHICLE_CATEGORIES + ('pedestrian',)
CATEGORY_LETTERS = {'motorcycle': 'M', 'car': 'C', 'truck': 'T', 'bus': 'B', 'pedestrian': 'P'}
DIRECTIONS = previous.DIRECTIONS
CATEGORY_COLORS = dict(previous.CATEGORY_COLORS, bus=(200, 180, 45))
ROUTE_LABELS = dict(previous.ROUTE_LABELS)
_require = frozen._require
LABEL_SCALE = 0.45
LABEL_LINE_HEIGHT = 20
PANEL_WIDTH = 640

def invalid_decisions(result, frame_count=None):
    """One invalid row per passage, with offline source attribution, never +1.

    frame_index/decision_frame retain when the decision was available. The
    separately named offline_attribution_frame is where its retained source
    candidate became active, and must not be read as a causal online decision.
    """
    rows = result.get('invalid_decisions', [])
    _require(isinstance(rows, list), 'invalid_decisions must be an array')
    decisions = result.get('decisions', [])
    _require(isinstance(decisions, list), 'decisions must be an array')
    candidates = rows + [entry for entry in decisions if entry.get('status') == 'invalid']
    indexed = {}
    active = {(entry['physical_unit_id'], entry.get('episode_id'), entry['passage_id']) for entry in result.get('events', [])}
    for entry in candidates:
        _require(isinstance(entry, dict) and entry.get('status') == 'invalid', 'Invalid audit needs explicit invalid status')
        _require(entry.get('accepted_count_event') is not True and entry.get('count_delta', 0) == 0, 'Invalid passage must contribute +0')
        key = (entry.get('physical_unit_id'), entry.get('episode_id'), entry.get('passage_id'))
        _require(all((isinstance(value, str) and value for value in key)), 'Invalid passage needs unit/episode/passage scope')
        _require(key not in active, 'A final accepted passage cannot also be invalid')
        frame = frozen._integer(entry.get('frame_index'), 'invalid frame')
        if frame_count is not None:
            _require(frame < frame_count, 'Invalid outside source frames')
        if key in indexed:
            _require(indexed[key] == entry, 'Conflicting invalid decisions for one passage')
        indexed[key] = deepcopy(entry)
    cancelled = {entry['event_id']: entry for entry in result.get('cancelled_events', [])}
    for entry in indexed.values():
        source_id = entry.get('cancelled_candidate_event_id', entry.get('source_event_id'))
        source = cancelled.get(source_id, {})
        attribution = source.get('activation_frame')
        if attribution is None:
            attribution = (entry.get('source_ref') or {}).get('frame_index')
        if attribution is None:
            attribution = entry['frame_index']
        frozen._integer(attribution, 'invalid offline attribution frame')
        if frame_count is not None:
            _require(attribution < frame_count, 'Invalid attribution outside source frames')
        entry['decision_frame'] = entry.get('decision_frame', entry['frame_index'])
        entry['offline_attribution_frame'] = attribution
        entry['attribution_semantics'] = 'OFFLINE_FINAL_REVIEW_NOT_CAUSAL'
    return sorted(indexed.values(), key=lambda entry: (entry['offline_attribution_frame'], entry['passage_id']))
_identity = previous._identity
_compile_assignments = previous._compile_assignments

def _display_id(value, category, direction):
    import re
    _require(isinstance(value, str) and re.fullmatch('[PMCTB][1-9][0-9]{3}', value), 'Final passage needs one category letter and four digits, without leading zero')
    _require(value[0] == CATEGORY_LETTERS[category], 'Display ID category differs')
    _require((int(value[1]) % 2 == 0) == (direction == 'A_TO_B'), 'Display ID direction parity differs')
    return value

def _compile_ledger_timeline(result, *, frame_count=None, component_relations=None, unit_assignments=None):
    """Validate one source ledger and compile constant-size counter snapshots.

    Changes in route/category revise the same final event. Candidates cancelled
    by the offline result never enter the pivot, even before their cancellation
    decision; their original operations remain explicitly void audit rows.
    Input objects are not modified.
    """
    identity = result.get('source_identity')
    _identity(identity)
    if frame_count is not None:
        frozen._integer(frame_count, 'frame_count', 1)
    events, cancelled = (result.get('events', []), result.get('cancelled_events', []))
    _require(isinstance(events, list) and isinstance(cancelled, list), 'Event arrays required')
    by_id, final_ids, final_display_ids = ({}, set(), set())
    for event in events + cancelled:
        _require(isinstance(event, dict), 'Event must be an object')
        event_id = frozen._identifier(event.get('event_id'), 'event ID')
        _require(event_id not in by_id, 'Duplicate event ID')
        _require(event.get('source_identity') == identity, 'Event belongs to another source')
        frozen._identifier(event.get('physical_unit_id'), 'physical unit')
        frozen._identifier(event.get('passage_id'), 'passage')
        frozen._integer(event.get('track_id'), 'vehicle track', 1)
        _require(event.get('category') in CATEGORIES, 'Unsupported product category')
        _require(event.get('direction') in DIRECTIONS, 'Invalid event direction')
        _require(event.get('route') in ROUTE_LABELS, 'Unknown event route')
        measured = event.get('evidence', {}).get('measured_crossing')
        _require(type(measured) is bool, 'Event requires explicit measured_crossing evidence')
        _require(event['route'] == 'LINE_MARGIN' or measured is False, 'Polygon/timeout cannot claim a measured line crossing')
        by_id[event_id] = deepcopy(event)
        if event in events:
            _require(event.get('accepted_count_event') is True, 'Final event must explicitly contribute to the operational count')
            _require(event.get('status') == 'accepted', 'Pending cannot enter accepted ledger')
            final_ids.add(event_id)
            display_id = _display_id(event.get('display_id'), event['category'], event['direction'])
            _require(display_id not in final_display_ids, 'Duplicate final display ID')
            final_display_ids.add(display_id)
    final_passages = [(by_id[key]['physical_unit_id'], by_id[key]['passage_id']) for key in final_ids]
    _require(len(final_passages) == len(set(final_passages)), 'Duplicate final physical passage')
    logs = result.get('passage_log', [])
    _require(isinstance(logs, list), 'passage_log must be an array')
    logs = sorted(enumerate(deepcopy(logs)), key=lambda pair: (pair[1].get('frame_index', -1), pair[0]))
    active, active_passages, snapshots, operations, displayed = ({}, {}, [], [], [])
    pivot = {category: {direction: 0 for direction in DIRECTIONS} for category in CATEGORIES}
    route_counts = {route: 0 for route in ROUTE_LABELS}

    def adjust(event, increment):
        pivot[event['category']][event['direction']] += increment
        route_counts[event['route']] += increment
    for _, log in logs:
        frame = frozen._integer(log.get('frame_index'), 'log frame')
        if frame_count is not None:
            _require(frame < frame_count, 'Log outside source frames')
        delta = log.get('count_delta', 0)
        _require(type(delta) is int and delta in (-1, 0, 1), 'Invalid passage count_delta')
        event_id = log.get('event_id')
        status = log.get('status')
        operational = delta != 0 or status == 'upgraded'
        if not operational:
            continue
        _require(event_id in by_id, 'Count log has no retained event')
        payload = dict(by_id[event_id])
        for key in ('track_id', 'category', 'direction', 'route'):
            if key in log:
                payload[key] = log[key]
        _require(payload['category'] in CATEGORIES and payload['direction'] in DIRECTIONS and (payload['route'] in ROUTE_LABELS), 'Invalid logged passage semantics')
        measured = log.get('measured_crossing')
        _require(type(measured) is bool, 'Operational log requires explicit measured_crossing')
        _require(payload['route'] == 'LINE_MARGIN' or measured is False, 'Polygon/timeout log cannot claim a measured line crossing')
        payload['_measured_crossing'] = measured
        frozen._integer(payload['track_id'], 'log vehicle track', 1)
        passage = (payload['physical_unit_id'], payload['passage_id'])
        if event_id not in final_ids:
            pass
        elif delta == 1:
            _require(event_id not in active and passage not in active_passages, 'Log attempts to increment one passage twice')
            active[event_id] = payload
            active_passages[passage] = event_id
            adjust(payload, 1)
        elif delta == -1:
            _require(event_id in active, 'Cancellation has no active event')
            previous = active.pop(event_id)
            adjust(previous, -1)
            active_passages.pop((previous['physical_unit_id'], previous['passage_id']))
        else:
            _require(event_id in active, 'Upgrade has no previously accepted event')
            previous = active[event_id]
            _require((previous['physical_unit_id'], previous['passage_id']) == passage, 'Upgrade changed physical passage identity')
            adjust(previous, -1)
            active[event_id] = payload
            adjust(payload, 1)
        display = dict(log, track_id=payload['track_id'], category=payload['category'], direction=payload['direction'], route=payload['route'], display_id=by_id[event_id].get('display_id'), display_category=by_id[event_id]['category'] if event_id in final_ids else payload['category'], display_direction=by_id[event_id]['direction'] if event_id in final_ids else payload['direction'], requested_label=ROUTE_LABELS[payload['route']])
        if event_id not in final_ids:
            display.update(status='offline_void', original_status=status, original_count_delta=delta, count_delta=0, display_id=None, requested_label='VOID +0 / OFFLINE FINAL')
        displayed.append(display)
        operations.append(frame)
        measured = sum((item['_measured_crossing'] for item in active.values()))
        snapshots.append({'pivot': deepcopy(pivot), 'route_counts': dict(route_counts), 'accepted_so_far': len(active), 'measured_so_far': measured, 'inferred_so_far': len(active) - measured, 'vehicle_so_far': sum((sum(pivot[key].values()) for key in VEHICLE_CATEGORIES)), 'pedestrian_so_far': sum(pivot['pedestrian'].values())})
    _require(set(active) == final_ids, 'Event log does not reconcile with final accepted ledger')
    for event_id in final_ids:
        for key in ('category', 'direction', 'route', 'track_id'):
            _require(active[event_id][key] == by_id[event_id][key], 'Final log/ledger differs: ' + key)
        _require(active[event_id]['_measured_crossing'] == by_id[event_id]['evidence']['measured_crossing'], 'Final log/ledger measured evidence differs')
    pending = []
    decisions = result.get('decisions', result.get('machine_decisions', []))
    _require(isinstance(decisions, list), 'Decisions must be an array')
    for decision in decisions:
        if decision.get('status') not in ('pending', 'pending_review'):
            continue
        _require(decision.get('accepted_count_event') is not True, 'Pending decision cannot contribute')
        frame = decision.get('frame_index', decision.get('diagnostic', {}).get('frame_index'))
        frozen._integer(frame, 'pending frame')
        if frame_count is not None:
            _require(frame < frame_count, 'Pending outside source frames')
        pending.append({'frame_index': frame, 'track_id': decision.get('track_id'), 'reasons': decision.get('reasons', decision.get('hard_block_reasons', []))})
    pending.sort(key=lambda item: item['frame_index'])
    relations = component_relations if component_relations is not None else result.get('component_links', [])
    links = defaultdict(list)
    for relation in relations:
        _require(relation.get('type') == 'COMPONENT_OF', 'Only explicit component relations may merge display boxes')
        vehicle = frozen._integer(relation.get('vehicle_track_id'), 'component parent', 1)
        component = frozen._integer(relation.get('component_track_id'), 'component track', 1)
        _require(vehicle != component, 'Component cannot be its own vehicle')
        frozen._identifier(relation.get('relation_id'), 'component relation ID')
        support = relation.get('support_frames')
        _require(isinstance(support, list) and bool(support), 'Component needs retained measured support frames')
        _require(len(support) == len(set(support)), 'Repeated component support frame')
        for frame in support:
            frozen._integer(frame, 'component support frame')
            if frame_count is not None:
                _require(frame < frame_count, 'Component support outside source frames')
            links[frame].append(deepcopy(relation))
    assignments = _compile_assignments(unit_assignments if unit_assignments is not None else result.get('frame_assignments', []), frame_count)
    display_by_unit = defaultdict(list)
    for event_id in sorted(final_ids):
        event = by_id[event_id]
        refs = event.get('evidence', {}).get('source_refs', [])
        source_frames = [ref.get('frame_index') for ref in refs if isinstance(ref, dict)]
        supplied = next((entry for entry in result.get('display_assignments', []) if entry.get('event_id') == event_id), {})
        source_frames += list(supplied.get('source_frames', []))
        source_frames = [frame for frame in source_frames if type(frame) is int and frame >= 0]
        if not source_frames:
            source_frames = [event.get('activation_frame')]
        start = min((frozen._integer(frame, 'display source frame') for frame in source_frames))
        episode = event.get('episode_id', supplied.get('episode_id'))
        if episode is None:
            continue
        frozen._identifier(episode, 'event episode')
        display_by_unit[event['physical_unit_id'], episode].append({'start_frame': start, 'display_id': event['display_id'], 'category': event['category'], 'passage_id': event['passage_id'], 'event_id': event_id})
    for candidates in display_by_unit.values():
        candidates.sort(key=lambda item: (item['start_frame'], item['event_id']))
        _require(len({entry['start_frame'] for entry in candidates}) == len(candidates), 'Ambiguous display passage start in one physical episode')
    return {'source_identity': deepcopy(identity), 'event_by_id': by_id, 'final_accepted': len(final_ids), 'final_pending': len(pending), 'operations': operations, 'snapshots': snapshots, 'display_logs': displayed, 'pending': pending, 'pending_frames': [item['frame_index'] for item in pending], 'component_links_by_frame': dict(links), 'frame_count': frame_count, 'unit_assignments_by_frame': assignments, 'display_by_unit': dict(display_by_unit), 'final_vehicle': sum((by_id[key]['category'] in VEHICLE_CATEGORIES for key in final_ids)), 'final_pedestrian': sum((by_id[key]['category'] == 'pedestrian' for key in final_ids)), 'semantics': SEMANTICS}

def _ledger_timeline_at(timeline, frame_index):
    frozen._integer(frame_index, 'frame index')
    if timeline['frame_count'] is not None:
        _require(frame_index < timeline['frame_count'], 'Frame outside source')
    position = bisect_right(timeline['operations'], frame_index)
    pending_n = bisect_right(timeline['pending_frames'], frame_index)
    state = deepcopy(timeline['snapshots'][position - 1]) if position else {'pivot': {category: {direction: 0 for direction in DIRECTIONS} for category in CATEGORIES}, 'route_counts': {route: 0 for route in ROUTE_LABELS}, 'accepted_so_far': 0, 'measured_so_far': 0, 'inferred_so_far': 0, 'vehicle_so_far': 0, 'pedestrian_so_far': 0}
    state.update(frame_index=frame_index, accepted_final=timeline['final_accepted'], pending_so_far=pending_n, pending_final=timeline['final_pending'], vehicle_final=timeline['final_vehicle'], pedestrian_final=timeline['final_pedestrian'], recent_logs=list(reversed(timeline['display_logs'][max(0, position - 4):position])), recent_pending=list(reversed(timeline['pending'][max(0, pending_n - 2):pending_n])))
    _require(sum((sum(row.values()) for row in state['pivot'].values())) == state['accepted_so_far'], 'Pivot/event mismatch')
    return state

def build_b_v6_timeline(result, geometry=None, frame_count=None, review_source_sha256=None, component_relations=None, unit_assignments=None):
    """Compile ledger counters and exact-frame assignments, without mutation."""
    timeline = _compile_ledger_timeline(result, frame_count=frame_count, component_relations=component_relations, unit_assignments=unit_assignments)
    if geometry is not None:
        identity = timeline['source_identity']
        previous._geometry_native(geometry, identity['width'], identity['height'])
    if review_source_sha256 is not None:
        _require(isinstance(review_source_sha256, str) and len(review_source_sha256) == 64 and all((c in '0123456789abcdef' for c in review_source_sha256)), 'review_source_sha256 must be a lowercase SHA256')
    audit = result.get('eligibility_audit', [])
    _require(isinstance(audit, list), 'eligibility_audit must be an array')
    indexed = []
    for position, entry in enumerate(audit):
        _require(isinstance(entry, dict), 'eligibility audit entry must be an object')
        frame = entry.get('frame_index', entry.get('decision_frame'))
        frozen._integer(frame, 'eligibility audit frame')
        if frame_count is not None:
            _require(frame < frame_count, 'Eligibility audit outside source')
        indexed.append((frame, position, deepcopy(entry)))
    indexed.sort(key=lambda item: (item[0], item[1]))
    timeline['eligibility_audit'] = [item[2] for item in indexed]
    timeline['eligibility_audit_frames'] = [item[0] for item in indexed]
    timeline['review_source_sha256'] = review_source_sha256
    event_logs = defaultdict(list)
    for entry in timeline['display_logs']:
        event_logs[entry.get('event_id')].append(entry)
    timeline['event_logs'] = dict(event_logs)
    timeline['layout_max_units'] = max((len(items) for items in timeline['unit_assignments_by_frame'].values()), default=0)
    invalid = invalid_decisions(result, frame_count)
    timeline['invalid_decisions'] = invalid
    timeline['invalid_frames'] = [entry['offline_attribution_frame'] for entry in invalid]
    invalid_by_unit = defaultdict(list)
    for entry in invalid:
        invalid_by_unit[entry['physical_unit_id'], entry['episode_id']].append(entry)
    timeline['invalid_by_unit'] = dict(invalid_by_unit)
    timeline['final_invalid'] = len(invalid)
    not_eligible = [deepcopy(entry) for entry in result.get('decisions', []) if entry.get('status') in ('resolved_not_eligible', 'not_eligible')]
    not_eligible.sort(key=lambda entry: entry.get('frame_index', -1))
    timeline['not_eligible_decisions'] = not_eligible
    timeline['not_eligible_frames'] = [entry['frame_index'] for entry in not_eligible]
    aggregate = result.get('aggregate', {})
    if aggregate:
        _require(aggregate.get('total') == timeline['final_accepted'], 'Aggregate accepted differs from event ledger')
        _require(aggregate.get('invalid', len(invalid)) == len(invalid), 'Aggregate invalid differs from audit ledger')
        for category in CATEGORIES:
            actual = sum((entry['category'] == category for entry in result.get('events', [])))
            _require(aggregate.get('by_category', {}).get(category, 0) == actual, 'Aggregate category differs from accepted ledger')
    timeline['b_v6_timeline'] = True
    return timeline

def timeline_at(timeline, frame_index):
    state = _ledger_timeline_at(timeline, frame_index)
    upto = bisect_right(timeline.get('eligibility_audit_frames', []), frame_index)
    state['recent_eligibility_audit'] = list(reversed(timeline.get('eligibility_audit', [])[max(0, upto - 3):upto]))
    invalid_upto = bisect_right(timeline.get('invalid_frames', []), frame_index)
    state.update(invalid_so_far=invalid_upto, invalid_final=timeline.get('final_invalid', 0), recent_invalid=list(reversed(timeline.get('invalid_decisions', [])[max(0, invalid_upto - 2):invalid_upto])), not_eligible_so_far=bisect_right(timeline.get('not_eligible_frames', []), frame_index), not_eligible_final=len(timeline.get('not_eligible_decisions', [])))
    return state

def _display_units(by_track, timeline, frame_index):
    """Union boxes only when the child is positively assigned at this frame.

    Even a previously supported component link cannot override an unknown or
    pedestrian assignment now. A supported exact-frame link or bounded reviewed
    assignment must identify the same physical parent. Parent absent => no union.
    """
    assignments = timeline['unit_assignments_by_frame'].get(frame_index, {})
    _require(set(assignments).issubset(by_track), 'Assignment has no measured emitted track at this frame')
    local_relations = timeline['component_links_by_frame'].get(frame_index, [])
    parents = defaultdict(set)
    for child, assignment in assignments.items():
        if assignment['role'] != 'rider':
            continue
        _require(by_track[child]['class_name'] == 'person', 'Rider requires a raw person box')
        parent_unit = assignment.get('component_of_unit_id')
        parent_episode = assignment.get('component_of_episode_id')
        direct_parent = assignment.get('component_of_track_id', assignment.get('parent_vehicle_track_id', assignment.get('vehicle_track_id')))
        supported = {relation['vehicle_track_id'] for relation in local_relations if relation['component_track_id'] == child}
        has_provenance = bool(assignment.get('review_refs') or assignment.get('role_provenance') or assignment.get('association_provenance') or assignment.get('evidence_refs'))
        for parent, parent_assignment in assignments.items():
            if parent == child or parent_assignment['role'] != 'vehicle':
                continue
            if by_track[parent]['class_name'] != 'motorcycle':
                continue
            same_parent = parent_unit is not None and parent_assignment['physical_unit_id'] == parent_unit
            if parent_episode is not None and parent_assignment['episode_id'] != parent_episode:
                continue
            direct = direct_parent == parent
            if parent_unit is not None and (not same_parent):
                continue
            if parent in supported and (parent_unit is None or same_parent):
                parents[child].add(parent)
            elif (same_parent or direct) and has_provenance:
                parents[child].add(parent)
    children = defaultdict(list)
    for child, options in parents.items():
        if len(options) == 1:
            children[next(iter(options))].append(child)
    suppressed = {child for members in children.values() for child in members}
    units = []
    for track, observation in sorted(by_track.items()):
        if track in suppressed:
            continue
        assignment = assignments.get(track, {})
        role = assignment.get('role', 'unknown_person' if observation['class_name'] == 'person' else 'vehicle')
        if role != 'vehicle':
            _require(observation['class_name'] == 'person', 'Person role requires raw person measurement')
        else:
            _require(observation['class_name'] != 'person', 'Raw person cannot silently become a vehicle')
        components = sorted(children.get(track, []))
        boxes = [observation['raw_bbox']] + [by_track[child]['raw_bbox'] for child in components]
        union = [min((box[0] for box in boxes)), min((box[1] for box in boxes)), max((box[2] for box in boxes)), max((box[3] for box in boxes))]
        candidates = timeline['display_by_unit'].get((assignment.get('physical_unit_id'), assignment.get('episode_id')), [])
        applicable = [candidate for candidate in candidates if candidate['start_frame'] <= frame_index]
        passage = applicable[-1] if applicable and role in ('vehicle', 'pedestrian') else {}
        event = timeline['event_by_id'].get(passage.get('event_id'), {})
        if passage:
            _require((passage['category'] == 'pedestrian') == (role == 'pedestrian'), 'Passage display category conflicts with observation role')
        active_logs = [entry for entry in timeline['event_logs'].get(passage.get('event_id'), []) if entry['frame_index'] <= frame_index]
        counted = sum((log.get('count_delta', 0) for log in active_logs)) > 0
        invalid_candidates = [entry for entry in timeline['invalid_by_unit'].get((assignment.get('physical_unit_id'), assignment.get('episode_id')), []) if entry['offline_attribution_frame'] <= frame_index]
        invalid = invalid_candidates[-1] if invalid_candidates else None
        if invalid is not None and (not passage or invalid['offline_attribution_frame'] >= passage['start_frame']):
            passage, event, active_logs, counted = ({}, {}, [], False)
        else:
            invalid = None
        category = passage.get('category') or ('pedestrian' if role == 'pedestrian' else observation['class_name'])
        bc = frozen._bc(observation['raw_bbox']) if role in ('vehicle', 'pedestrian') else None
        parent_tracks = sorted({parent for parent, entry in assignments.items() if entry.get('role') == 'vehicle' and entry.get('physical_unit_id') == assignment.get('component_of_unit_id') and (assignment.get('component_of_episode_id') is None or entry.get('episode_id') == assignment['component_of_episode_id'])})
        if not parent_tracks and assignment.get('component_of_track_id') in by_track:
            supplied_parent = assignment['component_of_track_id']
            if assignment.get('component_of_episode_id') is None or assignments.get(supplied_parent, {}).get('episode_id') == assignment['component_of_episode_id']:
                parent_tracks = [supplied_parent]
        if role == 'rider':
            status = 'RIDER +0'
        elif role in ('unknown', 'unknown_person'):
            status = 'ROLE UNKNOWN / NO COUNT'
        elif invalid:
            status = 'INVALID +0 / OFFLINE FINAL'
        elif passage and (not counted):
            status = 'OFFLINE ID / NOT COUNTED YET'
        elif counted:
            measured = active_logs[-1]['measured_crossing']
            status = 'COUNTED MEASURED' if measured else 'COUNTED ESTIMATE'
        else:
            status = 'NO ACCEPTED PASSAGE'
        units.append({'track_id': track, 'raw_track_ids': [track] + components, 'class_name': category, 'raw_class_name': observation['class_name'], 'role': role, 'physical_unit_id': assignment.get('physical_unit_id'), 'episode_id': assignment.get('episode_id'), 'display_id': passage.get('display_id'), 'passage_id': passage.get('passage_id'), 'event_id': passage.get('event_id'), 'event_activation_frame': event.get('activation_frame'), 'counted_at_frame': counted, 'display_bbox': union, 'raw_vehicle_bbox': list(observation['raw_bbox']), 'vehicle_bc': bc if role == 'vehicle' else None, 'counting_bc': bc, 'person_bc': bc if role == 'pedestrian' else None, 'component_track_ids': components, 'component_additional_increment': 0, 'parent_vehicle_track_ids': parent_tracks, 'status_label': status, 'invalid_decision': deepcopy(invalid), 'assignment_provenance': deepcopy(assignment)})
    return units

def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and (a[1] < b[3]) and (b[1] < a[3])

def _label_lines(unit):
    raw = 'raw' + '+'.join(map(str, unit['raw_track_ids']))
    first = raw + ' | ' + unit['class_name'].upper()
    if unit['display_id']:
        first += ' | ' + unit['display_id']
    second = unit['status_label']
    if unit['component_track_ids']:
        second += ' | rider ' + ','.join(map(str, unit['component_track_ids'])) + ' +0'
    if unit['role'] == 'rider':
        second += ' -> raw' + ','.join(map(str, unit['parent_vehicle_track_ids'])) if unit['parent_vehicle_track_ids'] else ' | parent not observed'
    return [first, second]

def _text_size(lines):
    import cv2
    return (max((cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, LABEL_SCALE, 1)[0][0] for line in lines)) + 12, len(lines) * LABEL_LINE_HEIGHT + 6)

def _layout_labels(units, width, height, max_units):
    """Deterministic, fixed-font placement; collision => outside-source callout."""
    occupied, layouts, overflow = ([], [], 0)
    for item in units:
        lines = _label_lines(item)
        label_width, label_height = _text_size(lines)
        _require(label_width <= width - 8, 'Label exceeds source width; use a wider explicit audit canvas')
        x1, y1, x2, y2 = item['display_bbox']
        clamp_x = lambda x: max(4, min(int(x), width - label_width - 4))
        candidates = [(clamp_x(x1), int(y1) - label_height - 4), (clamp_x(x1), int(y2) + 4), (clamp_x(x2 + 4), int(y1)), (clamp_x(x1 - label_width - 4), int(y1))]
        candidates += [(4, y) for y in range(4, height - label_height - 3, label_height + 4)]
        rectangle = None
        for x, y in candidates:
            candidate = [x, y, x + label_width, y + label_height]
            if 0 <= y and candidate[2] <= width and (candidate[3] <= height) and (not any((_overlaps(candidate, prior) for prior in occupied))):
                rectangle = candidate
                break
        outside = rectangle is None
        if outside:
            y = height + 166 + overflow * (2 * LABEL_LINE_HEIGHT + 10)
            rectangle = [4, y, 4 + label_width, y + label_height]
            overflow += 1
            _require(overflow <= max_units, 'Reserved callout capacity exceeded')
        occupied.append(rectangle)
        layouts.append({'track_id': item['track_id'], 'raw_track_ids': item['raw_track_ids'], 'lines': lines, 'text': ' / '.join(lines), 'rectangle': rectangle, 'outside_source': outside, 'font_scale': LABEL_SCALE, 'connector_from': [min(width - 1, max(0, round((x1 + x2) / 2))), min(height - 1, max(0, round(y1)))], 'connector_to': [rectangle[0], rectangle[1] + label_height // 2]})
        layout = layouts[-1]
        layout['connector_polyline'] = [layout['connector_from'], [width - 2, layout['connector_from'][1]], [width - 2, layout['connector_to'][1]], layout['connector_to']] if outside else [layout['connector_from'], layout['connector_to']]
    return layouts

def _audit_lines(entry):
    track = entry.get('track_id', entry.get('raw_track_id', '?'))
    status = entry.get('status', entry.get('decision', entry.get('eligibility', 'AUDIT')))
    reason = entry.get('reasons', entry.get('reason', entry.get('reason_codes', [])))
    if isinstance(reason, list):
        reason = '; '.join(map(str, reason))
    frame = entry.get('frame_index', entry.get('decision_frame'))
    lines = [f'raw{track} | f{frame} | {status}', str(reason or 'Inspect retained eligibility evidence')]
    details = []
    for key in ('last_origin_frame', 'last_observed_origin_frame', 'timeout_frame', 'elapsed_source_frames', 'identity_conflict', 'identity_timeout_hold', 'episode_id'):
        if key in entry:
            details.append(f'{key}={entry[key]}')
    if details:
        lines.append(' | '.join(details))
    return lines

def _render(source_frame, record, timeline, geometry, *, fps, video_id, frame_index=None):
    import cv2
    import numpy as np
    frozen._finite(fps, 'FPS')
    _require(fps > 0, 'FPS must be positive')
    height, width = source_frame.shape[:2]
    identity = timeline['source_identity']
    _require((width, height) == (identity['width'], identity['height']), 'Native source dimensions differ')
    index = record.get('frame_index') if frame_index is None else frame_index
    by_track = frozen._validate_record(record, index, identity, source_frame)
    native, margin = previous._geometry_native(geometry, width, height)
    state = timeline_at(timeline, index)
    image = source_frame.copy()
    p1, p2 = (np.asarray(native['line']['P1'], float), np.asarray(native['line']['P2'], float))
    direction = (p2 - p1) / np.linalg.norm(p2 - p1)
    normal = np.asarray([-direction[1], direction[0]])
    band = np.asarray([p1 + normal * margin, p2 + normal * margin, p2 - normal * margin, p1 - normal * margin])
    overlay = image.copy()
    cv2.fillPoly(overlay, [np.rint(band).astype(np.int32)], (50, 205, 235))
    cv2.addWeighted(overlay, 0.18, image, 0.82, 0, image)
    cv2.polylines(image, [np.rint(band).astype(np.int32)], True, (90, 225, 250), 1, cv2.LINE_AA)
    cv2.line(image, tuple(np.rint(p1).astype(int)), tuple(np.rint(p2).astype(int)), (90, 225, 250), 2, cv2.LINE_AA)
    for key, color in (('side_a_polygon', (235, 155, 65)), ('side_b_polygon', (65, 155, 245))):
        cv2.polylines(image, [np.rint(native[key]).astype(np.int32)], True, color, 1, cv2.LINE_AA)
    units = _display_units(by_track, timeline, index)
    maximum = max(len(units), timeline.get('layout_max_units', 0), 1)
    layouts = _layout_labels(units, width, height, maximum)
    overflow_capacity = timeline.get('layout_callout_capacity', sum((item['outside_source'] for item in layouts)))
    _require(sum((item['outside_source'] for item in layouts)) <= overflow_capacity, 'Reserved callout capacity exceeded')
    canvas_height = max(1450, height + 174 + overflow_capacity * (2 * LABEL_LINE_HEIGHT + 10))
    canvas_height += canvas_height % 2
    canvas = np.full((canvas_height, width + PANEL_WIDTH, 3), (20, 25, 33), np.uint8)
    canvas[:height, :width] = image
    source_canvas = canvas[:height, :width]
    for item in units:
        box = item['display_bbox']
        color = CATEGORY_COLORS.get(item['class_name'], CATEGORY_COLORS['other'])
        cv2.rectangle(source_canvas, (round(box[0]), round(box[1])), (round(box[2]), round(box[3])), color, 2, cv2.LINE_AA)
        if item['counting_bc'] is not None:
            point = tuple((round(value) for value in item['counting_bc']))
            cv2.circle(source_canvas, point, 4, (10, 15, 20), -1, cv2.LINE_AA)
            cv2.circle(source_canvas, point, 3, color, -1, cv2.LINE_AA)
    for item, layout in zip(units, layouts):
        item['label'] = layout['text']
        color = CATEGORY_COLORS.get(item['class_name'], CATEGORY_COLORS['other'])
        cv2.polylines(canvas, [np.asarray(layout['connector_polyline'], dtype=np.int32)], False, color, 1, cv2.LINE_AA)
    for item, layout in zip(units, layouts):
        color = CATEGORY_COLORS.get(item['class_name'], CATEGORY_COLORS['other'])
        x1, y1, x2, y2 = layout['rectangle']
        cv2.rectangle(canvas, (x1, y1), (x2 - 1, y2 - 1), color, -1)
        for offset, line in enumerate(layout['lines']):
            frozen._text(canvas, line, (x1 + 6, y1 + 17 + offset * LABEL_LINE_HEIGHT), scale=LABEL_SCALE, color=(8, 12, 18))
    x, right = (width + 18, width + PANEL_WIDTH - 18)
    cv2.rectangle(canvas, (width, 0), (width + PANEL_WIDTH - 1, canvas_height - 1), (27, 34, 44), -1)
    panel_text = []

    def text(value, y, *, offset=0, scale=0.45, color=(225, 232, 239), thickness=1):
        value = str(value)
        _require(cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0][0] <= right - x - offset, 'Panel text exceeds reserved width')
        panel_text.append({'text': value, 'x': x + offset, 'y': y})
        frozen._text(canvas, value, (x + offset, y), scale=scale, color=color, thickness=thickness)

    def wrapped(value, y, *, max_chars=76, scale=0.4, max_lines=None):
        lines = frozen._wrap(str(value), max_chars)
        if max_lines is not None:
            lines = lines[:max_lines]
        for line in lines:
            text(line, y, scale=scale)
            y += 18
        return y
    text('REVIEW COUNTING B v6', 28, scale=0.62, thickness=2)
    wrapped(video_id, 52)
    text('OFFLINE FINAL ID; COUNTERS FOLLOW LOG FRAME', 77, scale=0.42, color=(100, 205, 250))
    text('Event ledger only. Reviewed overlay not added.', 99, scale=0.4)
    cv2.line(canvas, (x, 111), (right, 111), (65, 76, 91), 1)
    text('PASSAGE ACCEPTED (OPERASIONAL)', 137, scale=0.49)
    text(f"{state['accepted_so_far']} / {state['accepted_final']}", 169, scale=0.8, thickness=2, color=(150, 235, 185))
    text(f"Measured {state['measured_so_far']} | inferred {state['inferred_so_far']}", 193)
    text(f"Vehicle {state['vehicle_so_far']} | pedestrian {state['pedestrian_so_far']}", 217)
    text('Kategori', 246)
    text('A > B', 246, offset=290)
    text('B > A', 246, offset=400)
    text('Total', 246, offset=515)
    for position, category in enumerate(CATEGORIES):
        y = 272 + position * 25
        text(category, y, color=CATEGORY_COLORS[category])
        row = state['pivot'][category]
        for offset, number in zip((310, 420, 533), [row[key] for key in DIRECTIONS] + [sum(row.values())]):
            text(number, y, offset=offset)
    text('A>B mendekati | B>A menjauhi kamera', 409, scale=0.42)
    text('LINE / POLYGON / TIMEOUT : ' + ' / '.join((str(state['route_counts'][key]) for key in ROUTE_LABELS)), 432, scale=0.42)
    text('Timeout = ESTIMATE, not proof of ID change.', 455, scale=0.4, color=(100, 205, 250))
    text('LOG KENDARAAN LEWAT', 491, scale=0.49, color=(150, 235, 185))
    text('Final ledger only; VOID candidates always +0 (offline).', 512, scale=0.4)
    if not state['recent_logs']:
        text('No accepted passage at this replay frame', 537)
    for position, log in enumerate(state['recent_logs']):
        y = 538 + position * 60
        name = log.get('display_id') or 'NO FINAL ID'
        text(f"raw{log['track_id']} | {name} | {log['display_category']} | {log['display_direction'].replace('_TO_', '>')}", y)
        text(f"{log['requested_label']} | {('MEASURED' if log['measured_crossing'] else 'INFERRED')}", y + 18, scale=0.4)
        text(f"f{log['frame_index']} | delta {log.get('count_delta', 0):+d}", y + 36, scale=0.4)
    cv2.line(canvas, (x, 776), (right, 776), (65, 76, 91), 1)
    text(f"INVALID AMBIGUITY +0 : {state['invalid_so_far']} / {state['invalid_final']}", 802, scale=0.49, color=(100, 160, 255))
    text('OFFLINE final exclusions; actual traffic is not zero.', 824, scale=0.4)
    for position, entry in enumerate(state['recent_invalid']):
        y = 850 + position * 47
        text(f"raw{entry['track_id']} | source f{entry['offline_attribution_frame']} | decision f{entry['decision_frame']} | +0", y, scale=0.4)
        wrapped(', '.join(map(str, entry.get('reasons', [entry.get('invalid_reason', 'INVALID_AMBIGUOUS_UNIT')]))), y + 18, max_lines=1)
    text(f"PENDING {state['pending_so_far']} / {state['pending_final']}", 972, scale=0.49, color=(100, 205, 250))
    text('Outside subtotal; pending keys != physical vehicles', 993, scale=0.4)
    for position, entry in enumerate(state['recent_pending']):
        y = 1019 + position * 55
        text(f"raw{entry['track_id']} | f{entry['frame_index']}", y)
        wrapped(', '.join(map(str, entry['reasons'])), y + 18, max_lines=1)
    text(f"NOT ELIGIBLE: {state['not_eligible_so_far']} / {state['not_eligible_final']}", 1140, scale=0.42)
    text('ELIGIBILITY / CLOCK / IDENTITY AUDIT', 1177, scale=0.46, color=(170, 205, 240))
    if not state['recent_eligibility_audit']:
        text('No eligibility audit entry at this frame', 1202, scale=0.4)
    for position, entry in enumerate(state['recent_eligibility_audit'][:2]):
        y = 1202 + position * 55
        lines = _audit_lines(entry)
        text(lines[0], y, scale=0.4)
        wrapped(lines[1], y + 18, max_lines=1)
        if len(lines) > 2:
            wrapped(lines[2], y + 36, max_lines=1)
    parent_links = []
    for item in units:
        parent_links += [{'component_track_id': child, 'vehicle_track_id': item['track_id'], 'frame_index': index, 'additional_increment': 0} for child in item['component_track_ids']]
        if item['role'] == 'rider' and len(item['parent_vehicle_track_ids']) == 1:
            parent_links.append({'component_track_id': item['track_id'], 'vehicle_track_id': item['parent_vehicle_track_ids'][0], 'frame_index': index, 'additional_increment': 0})
    text('RIDER PARENT / EXACT OBSERVATION FRAME', 1342, scale=0.42)
    for position, link in enumerate(parent_links[:2]):
        text(f"raw{link['component_track_id']} -> motorcycle raw{link['vehicle_track_id']} | +0 | f{index}", 1364 + position * 19, scale=0.4)
    if not parent_links:
        text('No positive parent link at this measured frame', 1364, scale=0.4)
    frozen._text(canvas, f'FRAME {index:06d} | t ~= {index / fps:.3f}s', (12, height + 28), scale=0.6, thickness=2)
    frozen._text(canvas, 'Native image, zero-based frame index / recorded FPS.', (12, height + 53), scale=0.43)
    frozen._text(canvas, 'BC from raw parent; union bbox is display-only. Rider +0.', (12, height + 78), scale=0.41)
    frozen._text(canvas, f'Finite band half-width {margin:g}px. A blue / B orange.', (12, height + 103), scale=0.42)
    frozen._text(canvas, 'OVERFLOW RAW-ID CALLOUTS (fixed font, no hidden labels)', (12, height + 140), scale=0.41)
    state.update(display_units=units, band_vertices_native=band.tolist(), label_layouts=layouts, panel_text=panel_text, panel_sections_y={'accepted': 137, 'passage_log': 491, 'invalid': 802, 'pending': 972, 'not_eligible': 1140, 'eligibility_audit': 1177}, label_font_scale=LABEL_SCALE, maximum_visible_units=maximum, role_parent_links=parent_links, source_image_region={'x': 0, 'y': 0, 'width': width, 'height': height, 'resized': False}, raw_ids_visible=sorted((track for item in layouts for track in item['raw_track_ids'])))
    _require(state['raw_ids_visible'] == sorted(by_track), 'A raw ID is missing or duplicated in visible labels')
    for layout in layouts:
        _require(0 <= layout['rectangle'][0] < layout['rectangle'][2] <= width and 0 <= layout['rectangle'][1] < layout['rectangle'][3] <= canvas_height, 'Label outside reserved canvas')
    return (canvas, state)

def render_b_v6_frame(source_frame, record, result_or_timeline, geometry, *, fps, video_id, frame_index=None, unit_assignments=None, component_relations=None, review_source_sha256=None):
    timeline = result_or_timeline if result_or_timeline.get('b_v6_timeline') else build_b_v6_timeline(result_or_timeline, geometry, review_source_sha256=review_source_sha256, unit_assignments=unit_assignments, component_relations=component_relations)
    return _render(source_frame, record, timeline, geometry, fps=fps, video_id=video_id, frame_index=frame_index)

def render_b_v6_video(video_path, records_path, result, geometry, output_path, *, fps, expected_frame_count, source_identity, component_relations=None, unit_assignments=None, progress=None, review_source_sha256=None):
    """Sequential source verification, H264 encode and full decode; no inference."""
    import cv2
    frozen._finite(fps, 'FPS')
    _require(fps > 0, 'FPS must be positive')
    frozen._integer(expected_frame_count, 'expected frame count', 1)
    previous._identity(source_identity)
    _require(result.get('source_identity') == source_identity, 'Renderer result/source identity differs')
    source, records, target = (Path(video_path), Path(records_path), Path(output_path))
    _require(not target.exists(), 'Output already exists; preserve previous evidence')
    _require(target.resolve() not in (source.resolve(), records.resolve()), 'Output cannot replace an input')
    _require(target.suffix.lower() == '.mp4', 'Output must be an MP4')
    hashes = {'video_sha256': frozen.sha256_file(source), 'records_sha256': frozen.sha256_file(records)}
    for key, actual in hashes.items():
        _require(actual == source_identity[key], 'Input source SHA differs: ' + key)
    if geometry.get('source_video', {}).get('sha256') is not None:
        _require(geometry['source_video']['sha256'] == hashes['video_sha256'], 'Geometry belongs to another video')
    timeline = build_b_v6_timeline(result, geometry, frame_count=expected_frame_count, component_relations=component_relations, unit_assignments=unit_assignments, review_source_sha256=review_source_sha256)
    maximum, overflow_capacity = (0, 0)
    for record in frozen._records(records):
        by_track = {item['track_id']: item for item in record.get('emitted_tracks', [])}
        units = _display_units(by_track, timeline, record['frame_index'])
        maximum = max(maximum, len(by_track))
        layouts = _layout_labels(units, source_identity['width'], source_identity['height'], max(len(by_track), 1))
        overflow_capacity = max(overflow_capacity, sum((item['outside_source'] for item in layouts)))
    timeline['layout_max_units'] = maximum
    timeline['layout_callout_capacity'] = overflow_capacity
    ffmpeg = shutil.which('ffmpeg')
    _require(ffmpeg is not None, 'ffmpeg with libx264 must be installed')
    target.parent.mkdir(parents=True, exist_ok=True)
    log_path, labels_path = (target.with_suffix('.ffmpeg.log'), target.with_suffix('.labels.jsonl.gz'))
    _require(not log_path.exists() and (not labels_path.exists()), 'Render evidence exists; choose a fresh output')
    capture = cv2.VideoCapture(str(source))
    _require(capture.isOpened(), 'Source video decoder unavailable')
    started = time.perf_counter()
    process, count, dimension, final_state, command = (None, 0, None, None, None)
    try:
        with log_path.open('wb') as codec_log, gzip.open(labels_path, 'wt', encoding='utf-8') as labels:
            for record in frozen._records(records):
                ok, image = capture.read()
                _require(ok and record.get('frame_index') == count, 'Source/cache frame alignment differs')
                canvas, final_state = _render(image, record, timeline, geometry, fps=fps, video_id=result.get('video_id', source.stem), frame_index=count)
                if process is None:
                    dimension = (canvas.shape[1], canvas.shape[0])
                    _require(all((value % 2 == 0 for value in dimension)), 'H264 dimensions must be even')
                    command = [ffmpeg, '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s:v', f'{dimension[0]}x{dimension[1]}', '-r', format(fps, '.17g'), '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)]
                    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=codec_log)
                _require((canvas.shape[1], canvas.shape[0]) == dimension, 'Layout dimensions changed during video')
                process.stdin.write(canvas.tobytes())
                labels.write(json.dumps({'frame_index': count, 'raw_ids_visible': final_state['raw_ids_visible'], 'label_layouts': final_state['label_layouts'], 'accepted_so_far': final_state['accepted_so_far'], 'measured_so_far': final_state['measured_so_far'], 'inferred_so_far': final_state['inferred_so_far'], 'pending_so_far': final_state['pending_so_far'], 'invalid_so_far': final_state['invalid_so_far'], 'not_eligible_so_far': final_state['not_eligible_so_far'], 'role_parent_links': final_state['role_parent_links'], 'display_units': [{key: item.get(key) for key in ('track_id', 'raw_track_ids', 'role', 'physical_unit_id', 'episode_id', 'display_id', 'passage_id', 'event_id', 'event_activation_frame', 'counted_at_frame', 'component_track_ids', 'parent_vehicle_track_ids', 'status_label', 'raw_vehicle_bbox', 'counting_bc')} for item in final_state['display_units']]}, sort_keys=True) + '\n')
                count += 1
                if progress and (count % 500 == 0 or count == expected_frame_count):
                    progress({'frames_rendered': count, 'expected_frame_count': expected_frame_count})
            more, _ = capture.read()
            _require(not more and count == expected_frame_count, 'Full source/cache frame count differs')
            _require(process is not None, 'No frames rendered')
            process.stdin.close()
            _require(process.wait() == 0, 'H264 encoding failed; inspect codec log')
    finally:
        capture.release()
        if process is not None and process.poll() is None:
            if process.stdin is not None and (not process.stdin.closed):
                process.stdin.close()
            process.terminate()
            process.wait()
    decoder, decoded = (cv2.VideoCapture(str(target)), 0)
    try:
        _require(decoder.isOpened(), 'H264 output cannot be decoded')
        while True:
            ok, image = decoder.read()
            if not ok:
                break
            _require((image.shape[1], image.shape[0]) == dimension, 'Encoded dimensions changed')
            decoded += 1
    finally:
        decoder.release()
    _require(decoded == count, 'Encoded full frame count differs')
    for key, path in (('video_sha256', source), ('records_sha256', records)):
        _require(frozen.sha256_file(path) == hashes[key], 'Source changed during rendering')
    return {'schema_version': VERSION, 'claim_type': 'ACTUAL_B_V6_LEDGER_RENDER_NOT_MODEL_INFERENCE', 'semantics': SEMANTICS, 'source_identity': deepcopy(source_identity), 'output_video': {'path': str(target), 'sha256': frozen.sha256_file(target), 'size_bytes': target.stat().st_size, 'codec': 'h264', 'pixel_format': 'yuv420p', 'frames_written': count, 'frames_redecoded': decoded, 'fps': fps, 'width': dimension[0], 'height': dimension[1], 'audio_preserved': False}, 'source_image_region': final_state['source_image_region'], 'final_accepted': final_state['accepted_so_far'], 'final_pending': final_state['pending_final'], 'final_invalid': final_state['invalid_final'], 'final_not_eligible': final_state['not_eligible_final'], 'final_vehicle': final_state['vehicle_so_far'], 'final_pedestrian': final_state['pedestrian_so_far'], 'final_pivot': final_state['pivot'], 'route_counts': final_state['route_counts'], 'final_measured': final_state['measured_so_far'], 'final_inferred': final_state['inferred_so_far'], 'frame_pixel_and_raw_link_verified_every_frame': True, 'inputs_unchanged_after_render': True, 'new_detector_tracker_encoder_inference': False, 'counting_rerun_by_renderer': False, 'component_policy': 'EXACT_FRAME_POSITIVE_RIDER_PARENT_ASSIGNMENT_UNION_RAW_PARENT_BC_PRESERVED', 'display_id_policy': 'RAW_ID_FIRST_WITH_OFFLINE_PREACTIVATION_VS_COUNTED_STATUS', 'label_layout_policy': 'FIXED_FONT_COLLISION_FREE_OR_RESERVED_OUTSIDE_SOURCE_CALLOUT', 'maximum_visible_units': timeline['layout_max_units'], 'pending_excluded_from_pivot': True, 'invalid_excluded_from_pivot': True, 'categories': list(CATEGORIES), 'maximum_overflow_callouts': timeline['layout_callout_capacity'], 'layout_audit': {'path': str(labels_path), 'sha256': frozen.sha256_file(labels_path)}, 'review_source_sha256': review_source_sha256, 'ffmpeg_command': command, 'codec_log': {'path': str(log_path), 'sha256': frozen.sha256_file(log_path)}, 'opencv_version': cv2.__version__, 'software_source_sha256': frozen.sha256_file(__file__), 'render_and_decode_wall_seconds': time.perf_counter() - started}
build_timeline = build_b_v6_timeline
render_frame = render_b_v6_frame
render_video = render_b_v6_video

def export_audit(result, output_directory):
    """Export one immutable snapshot; ambiguity loss is visible and never +1.

    Classification/identity/counting are not performed here. BUS zero rows are
    schema coverage, not invented bus observations. Machine and reviewed input
    snapshots are exported independently, never added together.
    """
    output = Path(output_directory)
    _require(not output.exists(), 'Export output exists; choose a new snapshot directory')
    timeline = build_timeline(result)
    last = max(timeline['operations'] + timeline.get('invalid_frames', []) + timeline['pending_frames'] + [0])
    state = timeline_at(timeline, last)
    _require(state['accepted_so_far'] == len(result.get('events', [])), 'Accepted CSV/pivot do not reconcile')
    output.mkdir(parents=True)

    def write_csv(name, rows, fieldnames):
        path = output / name
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: json.dumps(row.get(field), sort_keys=True, ensure_ascii=False) if isinstance(row.get(field), (dict, list, tuple)) else row.get(field) for field in fieldnames})
    identity = result['source_identity']
    shared = {'video_id': result.get('video_id'), 'branch': result.get('branch'), 'video_sha256': identity['video_sha256'], 'records_sha256': identity['records_sha256'], 'geometry_sha256': identity.get('geometry_sha256')}
    common = ['video_id', 'branch', 'video_sha256', 'records_sha256', 'geometry_sha256', 'status', 'count_delta', 'track_id', 'physical_unit_id', 'episode_id', 'passage_id']
    events = [{**shared, **entry, 'count_delta': 1, 'measured_crossing': entry['evidence']['measured_crossing'], 'source_refs': entry['evidence'].get('source_refs', [])} for entry in result.get('events', [])]
    write_csv('accepted_events.csv', events, common + ['event_id', 'display_id', 'category', 'direction', 'route', 'measured_crossing', 'activation_frame', 'decision_frame', 'source_refs'])
    invalid = [{**shared, **entry, 'count_delta': 0} for entry in timeline['invalid_decisions']]
    decision_fields = common + ['frame_index', 'decision_frame', 'offline_attribution_frame', 'attribution_semantics', 'invalid_reason', 'reasons', 'source_event_id', 'cancelled_candidate_event_id', 'source_ref', 'reason_evidence']
    write_csv('invalid_passages.csv', invalid, decision_fields)
    pending = [{**shared, **entry, 'count_delta': 0} for entry in result.get('decisions', []) if entry.get('status') in ('pending', 'pending_review')]
    write_csv('pending_passages.csv', pending, decision_fields)
    not_eligible = [{**shared, **entry, 'count_delta': 0} for entry in timeline['not_eligible_decisions']]
    write_csv('not_eligible_passages.csv', not_eligible, decision_fields + ['resolution_reason'])
    pivot_rows = []
    for category in CATEGORIES:
        for direction in DIRECTIONS:
            members = [entry for entry in result.get('events', []) if entry['category'] == category and entry['direction'] == direction]
            measured = sum((entry['evidence']['measured_crossing'] for entry in members))
            pivot_rows.append(dict(shared, category=category, direction=direction, accepted=len(members), measured=measured, inferred=len(members) - measured))
    write_csv('summary_pivot.csv', pivot_rows, list(shared) + ['category', 'direction', 'accepted', 'measured', 'inferred'])
    files = [{'path': path.name, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(output.glob('*.csv'))]
    report = {'schema_version': 'phase8_b_v6_audit_export_v1', 'source_identity': deepcopy(identity), 'branch': result.get('branch'), 'accepted': len(events), 'invalid': len(invalid), 'pending': len(pending), 'not_eligible': len(not_eligible), 'measured': sum((entry['measured_crossing'] for entry in events)), 'inferred': sum((not entry['measured_crossing'] for entry in events)), 'categories': list(CATEGORIES), 'invalid_contribution': 0, 'pending_contribution': 0, 'deliberate_ambiguity_exclusions_are_not_zero_actual_traffic': True, 'new_counting_or_model_execution': False, 'machine_and_reviewed_not_added': True, 'files': files, 'manifest_self_excluded': True}
    (output / 'export_manifest.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report
