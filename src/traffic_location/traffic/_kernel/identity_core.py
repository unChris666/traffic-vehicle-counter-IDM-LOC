"""Explicit B v4 identity/role experiment over retained measured observations.

This module performs no detection, tracking, embedding inference or interpolation.
It does not establish physical identity from raw IDs. Geometry-only component
association is an inspectable research hypothesis, not a trained role classifier.
All new numerical controls are returned with their experimental status. The
median-motion candidate deliberately keeps the frozen 0.15 limit; it does not
raise the limit to make development examples pass.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
from statistics import median
VEHICLES = frozenset(('motorcycle', 'car', 'truck', 'bus'))

def experimental_identity_policy(*, component_profile='median_temporal_v1'):
    """Return explicit research controls, never an implied production default."""
    return {'schema_version': 'phase8_b_v4_identity_policy_v1', 'status': 'EXPERIMENTAL_CANDIDATE_NOT_VALIDATED_PRODUCTION_DEFAULT', 'component_motion_profile': component_profile, 'max_unobserved_frames': 60, 'max_center_jump_norm': 1.0, 'min_component_run': 3, 'component_motion_limit': 0.15, 'component_bc_inside_fraction': 1.0, 'component_center_limit': 0.51, 'possible_handoff_center_limit': 0.1, 'possible_handoff_min_iou': 0.59, 'control_provenance': {'max_unobserved_frames': 'EXISTING_TIMEOUT_HORIZON_REUSED_AS_EXPERIMENT_NOT_VALIDATED_IDENTITY_LIFECYCLE', 'max_center_jump_norm': 'NEW_PROPOSAL_CONTEXT_DISCONTINUITY_CONTROL_NOT_IDENTITY_PROOF', 'component_motion_profile': 'NEW_PROPOSAL_MEDIAN_VS_RETAINED_MAX_ABLATION', 'component_controls': 'FROZEN_PHASE8_COMPONENT_3_0.15_1.0_0.51_REUSED', 'possible_handoff_controls': 'FROZEN_SAME_VEHICLE_CENTER_0.1_IOU_0.59_REUSED_FOR_HOLD_ONLY'}, 'automatic_handoff': 'DISABLED_WITHOUT_POSITIVE_SOURCE_BOUND_ASSOCIATION', 'appearance_features_used': False, 'role_propagation': 'EXACT_OBSERVED_CONSECUTIVE_SUPPORTED_RUN_ONLY', 'unknown_person_is_pedestrian': False}

def _require(condition, message):
    if not condition:
        raise ValueError(message)

def _hash(prefix, value):
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return prefix + hashlib.sha256(data.encode()).hexdigest()[:24]

def _center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)

def _diag(box):
    return math.hypot(box[2] - box[0], box[3] - box[1])

def _distance(first, second):
    return math.hypot(first[0] - second[0], first[1] - second[1])

def _iou(first, second):
    intersection = max(0, min(first[2], second[2]) - max(first[0], second[0])) * max(0, min(first[3], second[3]) - max(first[1], second[1]))
    areas = (first[2] - first[0]) * (first[3] - first[1]) + (second[2] - second[0]) * (second[3] - second[1])
    return intersection / (areas - intersection)

def _jump(first, second):
    return _distance(_center(first['raw_bbox']), _center(second['raw_bbox'])) / ((_diag(first['raw_bbox']) + _diag(second['raw_bbox'])) / 2)

def _positive_review(observation):
    return bool(observation.get('review_refs') or observation.get('review_ref'))

def _verified_review_continuity(first, second):
    """Role/category review is not a positive physical-identity association."""

    def reviewed_association(item):
        association = item.get('association_id')
        refs = list(item.get('review_refs', []))
        if isinstance(item.get('review_ref'), dict):
            refs.append(item['review_ref'])
        return association if item.get('association_verified') is True and association is not None and any((ref.get('review_id') == association for ref in refs)) else None
    first_id, second_id = (reviewed_association(first), reviewed_association(second))
    return first_id is not None and first_id == second_id and (first.get('_source_unit_id', first['unit_id']) == second['unit_id']) and (first.get('_source_episode_id', first['episode_id']) == second['episode_id'])

def _validate_policy(policy):
    controls = deepcopy(policy.get('identity', policy))
    expected = experimental_identity_policy()
    _require(isinstance(controls, dict) and controls.get('schema_version') == expected['schema_version'], 'Explicit B v4 identity policy is required')
    _require(controls.get('component_motion_profile') in ('median_temporal_v1', 'retained_max_v1'), 'Unknown component motion experiment')
    for key in ('max_unobserved_frames', 'min_component_run'):
        _require(type(controls.get(key)) is int and controls[key] >= 1, f'Invalid {key}')
    for key in ('max_center_jump_norm', 'component_motion_limit', 'component_bc_inside_fraction', 'component_center_limit', 'possible_handoff_center_limit', 'possible_handoff_min_iou'):
        value = controls.get(key)
        _require(type(value) in (int, float) and math.isfinite(value) and (value >= 0), f'Invalid {key}')
    _require(controls['component_bc_inside_fraction'] <= 1 and controls['possible_handoff_min_iou'] <= 1, 'Fractions must be in [0,1]')
    _require(controls.get('appearance_features_used') is False, 'Appearance embeddings are not available')
    return controls

def _validated_frames(frames):
    result = deepcopy(list(frames))
    by_track = defaultdict(list)
    for index, row in enumerate(result):
        _require(row.get('frame_index') == index, 'Full measured frames must be continuous from zero')
        seen = set()
        for item in row.get('observations', []):
            track, box = (item.get('track_id'), item.get('raw_bbox'))
            _require(type(track) is int and track > 0 and (track not in seen), 'Invalid/repeated raw track')
            seen.add(track)
            _require(item.get('observed') is True and item.get('emitted') is True, 'Prediction/non-emitted observations cannot enter identity replay')
            _require(item.get('frame_index', index) == index, 'Measurement frame differs')
            _require(isinstance(box, (tuple, list)) and len(box) == 4 and all((type(x) in (int, float) and math.isfinite(x) for x in box)) and (box[0] < box[2]) and (box[1] < box[3]), 'Invalid measured bbox')
            _require(item.get('class_name') in VEHICLES | {'person'}, 'Unsupported raw observation family')
            _require(item.get('role') in ('vehicle', 'unknown_person', 'rider', 'pedestrian'), 'Source adapter must attach an explicit role')
            _require(item.get('role') not in ('rider', 'pedestrian') or item['class_name'] == 'person', 'Person roles require raw person measurements')
            item['frame_index'] = index
            item['_source_association_verified'] = item.get('association_verified') is True
            item['_source_association_id'] = item.get('association_id')
            item.setdefault('identity_timeout_hold', [])
            _require(isinstance(item['identity_timeout_hold'], list), 'Timeout hold must list explicit reasons')
            by_track[track].append(item)
    return (result, by_track)

def _role_candidates(frames, controls):
    """Candidate runs contain observed co-presence only, never gap interpolation."""
    pairs = defaultdict(list)
    for row in frames:
        people = [o for o in row['observations'] if o['class_name'] == 'person' and o['role'] != 'pedestrian' and (not _positive_review(o))]
        motors = [o for o in row['observations'] if o['class_name'] == 'motorcycle' and o['role'] == 'vehicle']
        for person in people:
            for motor in motors:
                distance = _distance(_center(person['raw_bbox']), _center(motor['raw_bbox'])) / _diag(motor['raw_bbox'])
                if distance <= controls['component_center_limit']:
                    pairs[person['track_id'], motor['track_id']].append((person, motor))
    candidates = []
    for (person_id, motor_id), observations in sorted(pairs.items()):
        runs, current = ([], [])
        for pair in observations:
            if current and (pair[0]['frame_index'] != current[-1][0]['frame_index'] + 1 or _jump(current[-1][0], pair[0]) > controls['max_center_jump_norm'] or pair[1]['_identity_parent_context'] != current[-1][1]['_identity_parent_context']):
                runs.append(current)
                current = []
            current.append(pair)
        if current:
            runs.append(current)
        for run in runs:
            residuals, inside = ([], [])
            offsets, lengths = ([], [])
            for person, motor in run:
                box, parent = (person['raw_bbox'], motor['raw_bbox'])
                center, parent_center = (_center(box), _center(parent))
                offsets.append((center[0] - parent_center[0], center[1] - parent_center[1]))
                lengths.append(_diag(parent))
                foot = ((box[0] + box[2]) / 2, box[3])
                inside.append(parent[0] <= foot[0] <= parent[2] and parent[1] <= foot[1] <= parent[3])
            for index in range(1, len(run)):
                residuals.append(_distance(offsets[index], offsets[index - 1]) / ((lengths[index] + lengths[index - 1]) / 2))
            score = (median(residuals) if controls['component_motion_profile'] == 'median_temporal_v1' else max(residuals)) if residuals else None
            reasons = []
            if len(run) < controls['min_component_run']:
                reasons.append('INSUFFICIENT_CONSECUTIVE_COMPONENT_OBSERVATIONS')
            if sum(inside) / len(inside) < controls['component_bc_inside_fraction']:
                reasons.append('PERSON_BC_NOT_CONSISTENTLY_INSIDE_PARENT')
            if score is None or score > controls['component_motion_limit']:
                reasons.append('COMPONENT_RELATIVE_MOTION_NOT_SUPPORTED')
            if any((p.get('identity_conflict') or m.get('identity_conflict') for p, m in run)):
                reasons.append('SOURCE_IDENTITY_CONFLICT_IN_COMPONENT_RUN')
            frames_in_run = [p['frame_index'] for p, _ in run]
            candidates.append({'relation_id': _hash('b4-component:', [person_id, motor_id, frames_in_run, controls['component_motion_profile']]), 'type': 'COMPONENT_OF', 'component_track_id': person_id, 'vehicle_track_id': motor_id, 'support_frames': frames_in_run, 'status': 'SUPPORTED' if not reasons else 'REJECTED', 'reasons': reasons, 'features': {'common_frames': len(run), 'first_frame': frames_in_run[0], 'last_frame': frames_in_run[-1], 'bc_inside_fraction': sum(inside) / len(inside), 'relative_motion_max': max(residuals) if residuals else None, 'relative_motion_median': median(residuals) if residuals else None, 'relative_motion_selected_score': score, 'appearance_features_used': False}, 'claim_type': 'EXPERIMENTAL_GEOMETRY_MOTION_ASSOCIATION_NOT_HUMAN_ROLE_PROOF', 'profile': controls['component_motion_profile'], '_pairs': run})
    return candidates

def _apply_roles(candidates, frames):
    active = defaultdict(list)
    for relation in candidates:
        if relation['status'] == 'SUPPORTED':
            for person, motor in relation['_pairs']:
                active[person['frame_index'], person['track_id']].append((relation, person, motor))
    for (frame, track), values in sorted(active.items()):
        parents = {motor['track_id'] for _, _, motor in values}
        person = values[0][1]
        if len(parents) != 1:
            person['identity_timeout_hold'].append('COMPETING_COMPONENT_PARENTS')
            person.update(role='unknown_person')
            person.pop('component_of_unit_id', None)
            person.pop('component_of_track_id', None)
            for relation, _, _ in values:
                relation.setdefault('ambiguous_frames', []).append(frame)
            continue
        relation, person, motor = values[0]
        person.update(role='rider', component_of_unit_id=motor['unit_id'], component_of_track_id=motor['track_id'], role_scope_id=relation['relation_id'], component_parent_context_id=motor['_identity_parent_context'], role_source='B_V4_EXPERIMENTAL_BOUNDED_COMPONENT_RUN')

def _parent_contexts(by_track, controls):
    """Parent raw ID reuse must not join component evidence across contexts."""
    for track, observations in by_track.items():
        previous, context = (None, None)
        for item in observations:
            if item['role'] != 'vehicle':
                continue
            source_key = (item['unit_id'], item['episode_id'])
            discontinuous = previous is None or source_key != (previous['unit_id'], previous['episode_id']) or (not _verified_review_continuity(previous, item) and (item['frame_index'] - previous['frame_index'] > controls['max_unobserved_frames'] or (_jump(previous, item) > controls['max_center_jump_norm'] and _iou(previous['raw_bbox'], item['raw_bbox']) == 0)))
            if discontinuous:
                context = _hash('b4-parent-context:', [track, source_key, item['frame_index']])
            item['_identity_parent_context'] = context
            previous = item

def _split_contexts(by_track, controls):
    audits = []
    for track, observations in sorted(by_track.items()):
        previous, segment_start, segment_reason, segment_items = (None, None, None, [])
        context_parent, boundary_episode, segment_identity = (None, None, None)
        seen_counting_keys = set()

        def finish():
            if not segment_items:
                return
            first, last = (segment_items[0], segment_items[-1])
            audits.append({'physical_episode_id': first['physical_episode_id'], 'track_id': track, 'physical_unit_id': first['unit_id'], 'episode_id': first['episode_id'], 'start_frame': first['frame_index'], 'end_frame': last['frame_index'], 'observed_frames': len(segment_items), 'boundary_reason': segment_reason, 'raw_category_observations': dict(Counter((o['class_name'] for o in segment_items))), 'source_measurements_unchanged': True, 'claim_type': 'DETERMINISTIC_CONTEXT_SEGMENT_NOT_VERIFIED_PHYSICAL_IDENTITY'})
        for item in observations:
            reason = None
            explicit = _positive_review(item)
            if previous is None:
                reason = 'INITIAL_OBSERVATION'
            elif (item['unit_id'], item['episode_id']) != (previous.get('_source_unit_id', previous['unit_id']), previous.get('_source_episode_id', previous['episode_id'])) and (explicit or _positive_review(previous)):
                reason = 'SOURCE_BOUND_ASSIGNMENT_CHANGE'
            else:
                delta = item['frame_index'] - previous['frame_index']
                jump = _jump(previous, item)
                continuity_review = _verified_review_continuity(previous, item)
                if delta > controls['max_unobserved_frames'] and (not continuity_review):
                    reason = 'LONG_MEASUREMENT_GAP_NO_IDENTITY_CONTINUITY_PROOF'
                elif jump > controls['max_center_jump_norm'] and _iou(previous['raw_bbox'], item['raw_bbox']) == 0 and (not continuity_review):
                    reason = 'SPATIAL_JUMP_WITH_DISJOINT_BOX_CONTEXT'
                elif previous['class_name'] in VEHICLES and item['class_name'] == 'person' and (item.get('component_of_track_id') not in (None, track)) and (item['role'] == 'rider'):
                    reason = 'VEHICLE_TO_PERSON_WITH_DIFFERENT_POSITIVE_PARENT_CONTEXT'
                elif item['class_name'] in VEHICLES and context_parent is not None:
                    reason = 'RAW_VEHICLE_AFTER_BOUNDED_COMPONENT_CONTEXT_NO_ORIGIN_INHERITANCE'
                elif item['role'] == 'rider' and context_parent is not None and ((item.get('component_of_track_id'), item.get('component_parent_context_id')) != context_parent):
                    reason = 'POSITIVE_COMPONENT_PARENT_CHANGED'
            if reason is not None:
                finish()
                segment_start, segment_reason, segment_items = (item['frame_index'], reason, [])
                context_parent = None
                segment_identity = [track, item['unit_id'], item['episode_id'], segment_start]
                boundary_episode = None if reason in ('INITIAL_OBSERVATION', 'SOURCE_BOUND_ASSIGNMENT_CHANGE') else f"{item['episode_id']}|b4-raw:{track}:start:{segment_start}"
                if reason == 'SOURCE_BOUND_ASSIGNMENT_CHANGE' and (item['unit_id'], item['episode_id']) in seen_counting_keys:
                    boundary_episode = f"{item['episode_id']}|b4-raw:{track}:start:{segment_start}"
            original_unit, original_episode = (item['unit_id'], item['episode_id'])
            item['_source_unit_id'], item['_source_episode_id'] = (original_unit, original_episode)
            if boundary_episode is not None:
                item['episode_id'] = boundary_episode
                item['source_bound_episode_id_before_context_split'] = original_episode
                item.update(association_verified=False)
                item.pop('association_id', None)
            item['identity_episode_boundary'] = reason is not None
            item['identity_episode_reason'] = segment_reason
            item['physical_episode_id'] = _hash('b4-physical-episode:', segment_identity)
            if reason and previous is not None:
                item['previous_physical_episode_id'] = previous['physical_episode_id']
            if item['role'] == 'rider' and item.get('component_of_track_id') is not None:
                context_parent = (item['component_of_track_id'], item.get('component_parent_context_id'))
            seen_counting_keys.add((item['unit_id'], item['episode_id']))
            segment_items.append(item)
            previous = item
        finish()
    return audits

def _bind_components(frames, candidates):
    links = defaultdict(list)
    for row in frames:
        present = {o['track_id']: o for o in row['observations']}
        for item in row['observations']:
            if item['role'] != 'rider':
                continue
            parent = present.get(item.get('component_of_track_id'))
            if parent is None:
                matches = [o for o in present.values() if o['role'] == 'vehicle' and o['class_name'] == 'motorcycle' and (o['unit_id'] == item.get('component_of_unit_id'))]
                parent = matches[0] if len(matches) == 1 else None
            if parent is None or parent['class_name'] != 'motorcycle':
                continue
            item.update(component_of_unit_id=parent['unit_id'], component_of_track_id=parent['track_id'], component_of_episode_id=parent['episode_id'], component_parent_context_id=parent.get('_identity_parent_context'))
            scope = item.get('role_scope_id', item.get('retained_component_relation_id', 'source-bound-review'))
            links[scope, item['track_id'], parent['track_id']].append(row['frame_index'])
    return sorted([{'type': 'COMPONENT_OF', 'relation_id': relation, 'component_track_id': child, 'vehicle_track_id': parent, 'support_frames': support, 'claim_type': 'EXACT_OBSERVED_ROLE_SCOPE_DISPLAY_ONLY_RAW_VEHICLE_BC_PRESERVED'} for (relation, child, parent), support in sorted(links.items())], key=lambda link: (link['support_frames'][0], link['component_track_id'], link['vehicle_track_id']))

def _align_local_alias_contexts(frames, episode_audit):
    """Align a new alias with the CURRENT positively co-observed context.

    A whole-ID retained clique must not reconnect a later alias to a closed
    earlier object that reused a raw ID. Actual exact-frame positive clique
    evidence may instead align the alias to the current local episode. This
    is never back-propagated to earlier frames. Subsequent observations in the
    same local episode retain that counting namespace as an operational
    continuity assumption; ``association_verified`` remains true only where
    the original source adapter supplied positive exact-frame evidence.
    """
    starts = {row['physical_episode_id']: row['start_frame'] for row in episode_audit}
    aliases, prior_keys, aligned = ({}, {}, [])
    by_physical = defaultdict(list)
    for row in frames:
        for item in row['observations']:
            mapped = aliases.get(item['physical_episode_id']) if item['role'] == 'vehicle' else None
            if mapped is not None:
                item['unit_id'], item['episode_id'] = mapped
        positive = defaultdict(list)
        for item in row['observations']:
            proof = item.get('source_ref', {}).get('retained_same_vehicle_association', {})
            if item['role'] == 'vehicle' and item.get('_source_association_verified') and (item.get('_source_association_id') is not None) and (proof.get('frame_index') == row['frame_index']) and (proof.get('whole_id_support_implied') is False):
                positive[item['_source_association_id']].append(item)
        for association, items in positive.items():
            tracks = {o['track_id'] for o in items}
            if len(items) < 2 or any((o.get('identity_conflict') or _positive_review(o) for o in items)) or any((set(o['source_ref']['retained_same_vehicle_association'].get('track_ids', [])) != tracks for o in items)):
                continue
            anchor = min(items, key=lambda item: (starts[item['physical_episode_id']], item['track_id']))
            canonical = (anchor['unit_id'], anchor['episode_id'])
            for item in items:
                prior = (item['unit_id'], item['episode_id'])
                if prior != canonical:
                    aligned.append({'frame_index': row['frame_index'], 'track_id': item['track_id'], 'physical_episode_id': item['physical_episode_id'], 'old_counting_key': list(prior), 'current_counting_key': list(canonical), 'anchor_track_id': anchor['track_id'], 'association_id': association, 'claim_type': 'EXACT_FRAME_SUPPORTED_ALIAS_CURRENT_CONTEXT_NOT_WHOLE_RAW_ID', 'earlier_frames_reassigned': False})
                item['unit_id'], item['episode_id'] = canonical
                item.update(association_verified=True, association_id=association)
                aliases[item['physical_episode_id']] = canonical
        for item in row['observations']:
            key = (item['unit_id'], item['episode_id'])
            prior = prior_keys.get(item['track_id'])
            if prior is not None and prior[0] != key and (prior[1] == item['physical_episode_id']) and (prior[2] == item['role'] == 'vehicle') and (not item['identity_episode_boundary']):
                item['identity_episode_boundary'] = True
                item['identity_episode_reason'] = 'SOURCE_FRAME_VERIFIED_ALIAS_CONTEXT_ALIGNMENT'
            prior_keys[item['track_id']] = (key, item['physical_episode_id'], item['role'])
            by_physical[item['physical_episode_id']].append(item)
    for audit in episode_audit:
        items = by_physical[audit['physical_episode_id']]
        audit['physical_unit_id'], audit['episode_id'] = (items[0]['unit_id'], items[0]['episode_id'])
        contexts = defaultdict(list)
        for item in items:
            contexts[item['unit_id'], item['episode_id']].append(item['frame_index'])
        audit['counting_contexts'] = [{'physical_unit_id': key[0], 'episode_id': key[1], 'first_frame': min(indices), 'last_frame': max(indices), 'observed_frames': len(indices)} for key, indices in sorted(contexts.items())]
    return aligned

def _possible_handoffs(by_track, controls):
    """Similar endpoint boxes only HOLD estimates; they never verify a merge."""
    episodes = defaultdict(list)
    for observations in by_track.values():
        for item in observations:
            if item['role'] == 'vehicle':
                episodes[item['physical_episode_id']].append(item)
    ordered = sorted(episodes.values(), key=lambda values: (values[0]['frame_index'], values[0]['track_id']))
    audits = []
    for index, first in enumerate(ordered):
        a = first[-1]
        for second in ordered[index + 1:]:
            b = second[0]
            delta = b['frame_index'] - a['frame_index']
            if b['frame_index'] - a['frame_index'] > controls['max_unobserved_frames']:
                break
            if delta <= 0 or a['track_id'] == b['track_id']:
                continue
            category_a = a.get('resolved_class_name', a['class_name'])
            category_b = b.get('resolved_class_name', b['class_name'])
            if category_a != category_b:
                continue
            if a.get('association_verified') is True and b.get('association_verified') is True and (a.get('association_id') == b.get('association_id')) and (a.get('association_id') is not None) and ((a['unit_id'], a['episode_id']) == (b['unit_id'], b['episode_id'])):
                continue
            distance = _jump(a, b)
            overlap = _iou(a['raw_bbox'], b['raw_bbox'])
            if distance > controls['possible_handoff_center_limit'] or overlap < controls['possible_handoff_min_iou']:
                continue
            reason = 'POSSIBLE_UNVERIFIED_RAW_ID_HANDOFF_TIMEOUT_HELD'
            for item in first + second:
                if reason not in item['identity_timeout_hold']:
                    item['identity_timeout_hold'].append(reason)
            audits.append({'first_track_id': a['track_id'], 'second_track_id': b['track_id'], 'first_episode_id': a['physical_episode_id'], 'second_episode_id': b['physical_episode_id'], 'last_first_frame': a['frame_index'], 'first_second_frame': b['frame_index'], 'gap_source_frames': delta, 'endpoint_center_distance_norm': distance, 'endpoint_iou': overlap, 'status': 'UNRESOLVED_HOLD_TIMEOUT_ONLY', 'automatic_alias_created': False, 'appearance_features_used': False, 'reason': reason})
    return audits

def prepare_identity_frames(frames, geometry, policy, relationships=None):
    """Decorate measured frames and return inspectable episode/role/hold evidence.

    ``frames`` is the full B v3 adapter iterator. Its source link and reviews
    must already have been verified by that adapter. ``relationships`` is kept
    as an explicit provenance input; it is never a license to extend a relation
    outside actual supported observation frames. ``geometry`` is accepted to
    keep the integration boundary explicit; geometry is not modified here.
    """
    controls = _validate_policy(policy)
    result, by_track = _validated_frames(frames)
    _parent_contexts(by_track, controls)
    candidates = _role_candidates(result, controls)
    _apply_roles(candidates, result)
    _bind_components(result, candidates)
    episode_audit = _split_contexts(by_track, controls)
    alias_audit = _align_local_alias_contexts(result, episode_audit)
    component_links = _bind_components(result, candidates)
    handoff_audit = _possible_handoffs(by_track, controls)
    assignments = []
    for row in result:
        for item in row['observations']:
            assignments.append({'frame_index': row['frame_index'], 'track_id': item['track_id'], 'physical_unit_id': item['unit_id'], 'episode_id': item['episode_id'], 'role': item['role'], 'category': item.get('resolved_class_name', item['class_name']), 'raw_category': item['class_name'], 'review_refs': deepcopy(item.get('review_refs', [])), 'association_verified': item.get('association_verified', False), 'association_id': item.get('association_id'), **{key: deepcopy(item[key]) for key in ('component_of_unit_id', 'component_of_track_id', 'component_of_episode_id', 'component_parent_context_id', 'physical_episode_id', 'identity_episode_boundary', 'identity_episode_reason', 'previous_physical_episode_id', 'identity_timeout_hold', 'source_bound_episode_id_before_context_split', 'role_scope_id', 'role_source') if key in item}})
            item.pop('_source_unit_id', None)
            item.pop('_source_episode_id', None)
            item.pop('_identity_parent_context', None)
            item.pop('_source_association_verified', None)
            item.pop('_source_association_id', None)
    for candidate in candidates:
        candidate['applied_support_frames'] = [person['frame_index'] for person, _ in candidate['_pairs'] if person.get('role_scope_id') == candidate['relation_id'] and person['role'] == 'rider']
        candidate['application_status'] = 'APPLIED_EXACT_OBSERVED_FRAME_SCOPE' if candidate['applied_support_frames'] else 'NOT_APPLIED_REJECTED_OR_COMPETING_PARENT'
        candidate.pop('_pairs', None)
    return {'frames': result, 'episode_audit': episode_audit, 'role_audit': candidates, 'handoff_audit': handoff_audit, 'policy': controls, 'assignments': assignments, 'component_links': component_links, 'alias_context_audit': alias_audit, 'provenance': {'source_measurements_unchanged': True, 'geometry_unchanged': True, 'source_adapter_relations_present': relationships is not None, 'no_observations_synthesized': True, 'no_detector_tracker_reid_or_enhancement': True, 'appearance_features_used': False, 'replay_is_causal': False, 'offline_role_runs_may_use_later_observations_within_exact_scope': True}}
