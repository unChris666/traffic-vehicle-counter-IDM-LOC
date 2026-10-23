"""Offline B v7 joint publication gate over the immutable B v6 engine.

Trajectory compatibility is an unresolved identity conflict, never an alias or
crossing measurement. The private B v6 result is not published until this gate
has finalized the exact implicated candidate passages. No model executes here.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from . import eligibility as previous
INVALID_REASON = 'INVALID_AMBIGUOUS_UNIT'
SCOPE = 'THIS_CANDIDATE_PASSAGE_NOT_GLOBAL_RAW_ID'

def _require(condition, message):
    if not condition:
        raise ValueError(message)

def _source_index(frames):
    index = {}
    for row in frames:
        frame = row['frame_index']
        for obs in row.get('observations', []):
            if obs.get('observed') is not True or obs.get('emitted') is not True or obs.get('role', 'vehicle') != 'vehicle' or (obs.get('class_name') == 'person'):
                continue
            key = (obs.get('track_id'), obs.get('physical_episode_id'), frame)
            index.setdefault(key, []).append(obs)
    return index

def _validate_endpoint(event, relation, prefix, source_index):
    """Use each endpoint's own window; another endpoint cannot extend it."""
    _require(event['track_id'] == relation.get(prefix + '_track_id'), 'Handoff event and raw track do not match')
    _require(event['physical_unit_id'] == relation.get(prefix + '_unit_id') and event.get('episode_id') == relation.get(prefix + '_episode_id'), 'Handoff belongs to another unit/episode')
    physical = relation.get(prefix + '_physical_episode_id')
    _require(isinstance(physical, str) and bool(physical), 'Physical context required')
    refs = [ref for ref in event['evidence'].get('source_refs', []) if ref.get('track_id') == event['track_id'] and ref.get('physical_episode_id') == physical]
    _require(bool(refs), 'Handoff has no source reference in this physical context')
    low, high = (min((r['frame_index'] for r in refs)), max((r['frame_index'] for r in refs)))
    support = relation.get(prefix + '_support_frames', [])
    _require(isinstance(support, list) and len(support) == 5 and all((type(f) is int for f in support)) and (support == list(range(support[0], support[0] + 5))), 'Handoff needs five consecutive actual observations at each endpoint')
    _require(all((low <= frame <= high for frame in support)), "Handoff support is outside the candidate's own measured window")
    _require(all(((event['track_id'], physical, frame) in source_index for frame in support)), 'Handoff support is absent from actual vehicle observations')
    return support

def _rename_event_ids(result):
    mapping = {e['event_id']: e['event_id'].replace('b_v6_', 'b_v7_', 1) for e in result['events'] + result.get('cancelled_events', [])}

    def walk(value):
        if isinstance(value, dict):
            return {mapping.get(key, key): walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            return mapping.get(value, value)
        return value
    return walk(result)

def finalize_handoff_candidates(provisional, proposal, *, frames, finalization_frame=None):
    """Finalize only exact active pairs. Never revisit old pending decisions.

    The input is a private candidate snapshot, not an already published ledger.
    Rejected candidates retain their source evidence and candidate timestamps;
    the actual offline invalid decision is recorded at the last supplied frame.
    """
    frames = list(frames)
    last_frame = max((row['frame_index'] for row in frames))
    decision_frame = last_frame if finalization_frame is None else finalization_frame
    _require(decision_frame == last_frame == provisional['report']['last_frame_index'], 'Offline publication decision must use the actual source EOF')
    output = deepcopy(provisional)
    candidates = {e['event_id']: e for e in output['events']}
    _require(len(candidates) == len(output['events']), 'Duplicate candidate event IDs')
    source_index = _source_index(frames)
    implicated, audits, seen_relations = ({}, [], set())
    for relation in proposal.get('relations', []):
        rid = relation.get('relation_id')
        _require(isinstance(rid, str) and rid and (rid not in seen_relations), 'Handoff relation must have a unique ID')
        seen_relations.add(rid)
        _require(relation.get('verified') is False and relation.get('candidate_kind') == 'UNVERIFIED_ORIGIN_HANDOFF' and (relation.get('relation_type', relation.get('type')) == 'SAME_UNIT'), 'Only explicit unverified handoff conflicts are supported')
        ids = [relation.get('first_event_id'), relation.get('second_event_id')]
        _require(len(set(ids)) == 2 and all((eid in candidates for eid in ids)) and (sorted(relation.get('event_ids', [])) == sorted(ids)), 'Handoff must name exactly two distinct active candidate events')
        first, second = [candidates[eid] for eid in ids]
        _require(first.get('role') == second.get('role') == 'vehicle' and first['category'] == second['category'] and (first['category'] != 'pedestrian') and (first['direction'] == second['direction']) and (first['direction'] in ('A_TO_B', 'B_TO_A')), 'Handoff must concern same-category same-direction vehicle candidates')
        _require(not all((e['evidence']['measured_crossing'] for e in (first, second))), 'This experiment cannot suppress two measured passages')
        first_support = _validate_endpoint(first, relation, 'first', source_index)
        second_support = _validate_endpoint(second, relation, 'second', source_index)
        _require(0 < second_support[0] - first_support[-1] <= 60, 'Handoff must be ordered and bounded by the existing source-frame horizon')
        _require(relation.get('support_frames') == sorted(set(first_support + second_support)), 'Combined support must preserve actual separate endpoint observations')
        for event in (first, second):
            implicated.setdefault(event['event_id'], []).append(rid)
        audits.append({'relation_id': rid, 'event_ids': ids, 'status': 'INVALID_PLUS_ZERO_SCOPED_AMBIGUITY', 'physical_episodes_merged': False, 'identity_verified': False, 'decision_frame': decision_frame, 'support_frames': deepcopy(relation['support_frames'])})
    original_pending = [deepcopy(d) for d in output['decisions'] if d['status'] == 'pending']
    invalid_keys = {previous._key(d) for d in output.get('invalid_decisions', [])}
    for event_id, relation_ids in sorted(implicated.items()):
        event = candidates.pop(event_id)
        key = previous._key(event)
        _require(key not in invalid_keys, 'Candidate already has an invalid passage decision')
        invalid_keys.add(key)
        candidate_frame = event['decision_frame']
        event.update(status='cancelled', accepted_count_event=False, display_id=None, cancellation_reason=INVALID_REASON, never_published=True, candidate_decision_frame=candidate_frame, decision_frame=decision_frame, finalization_mode='OFFLINE_BEFORE_PUBLICATION')
        output['cancelled_events'].append(event)
        for log in output['passage_log']:
            if log.get('event_id') == event_id:
                log.update(candidate_count_delta=log.get('count_delta', 0), count_delta=0, candidate_status=log['status'], status='provisional_not_published', accepted_count_event=False, never_published=True, final_decision_frame=decision_frame)
        for old in output['decisions']:
            if old.get('event_id') == event_id and old.get('status') == 'superseded_by_accepted':
                old.update(status='superseded_by_invalid', superseded_at_frame=decision_frame)
        decision = {'frame_index': decision_frame, 'decision_frame': decision_frame, 'candidate_decision_frame': candidate_frame, **{field: deepcopy(event.get(field)) for field in ('track_id', 'physical_unit_id', 'episode_id', 'passage_id', 'role', 'category', 'direction')}, 'status': 'invalid', 'invalid_reason': INVALID_REASON, 'reasons': [INVALID_REASON], 'count_delta': 0, 'accepted_count_event': False, 'display_id': None, 'source_event_id': event_id, 'cancelled_candidate_event_id': event_id, 'source_ref': deepcopy(event['evidence']['source_refs'][-1]), 'physical_episodes_merged': False, 'invalid_scope': SCOPE, 'relation_ids': sorted(relation_ids), 'never_published': True, 'finalization_mode': 'OFFLINE_BEFORE_PUBLICATION', 'reason_evidence': [{'reason': INVALID_REASON, 'relation_ids': sorted(relation_ids), 'intentional_exclusion_not_zero_traffic': True, 'trajectory_compatibility_is_not_identity_proof': True}]}
        output['decisions'].append(decision)
        output['passage_log'].append({'frame_index': decision_frame, 'candidate_decision_frame': candidate_frame, **{field: decision.get(field) for field in ('track_id', 'physical_unit_id', 'episode_id', 'passage_id', 'category', 'direction')}, 'event_id': None, 'source_event_id': event_id, 'status': 'invalid', 'count_delta': 0, 'message': INVALID_REASON, 'invalid_scope': SCOPE})
    output['events'] = list(candidates.values())
    scoped_keys = {previous._key(e) for e in output['cancelled_events'] if e.get('never_published') is True}
    for row in output.get('open_passage_diagnostics', []):
        if previous._key(row) in scoped_keys:
            row.update(disposition=INVALID_REASON, timeout_eligible=False)
    previous._refresh(output)
    _require([d for d in output['decisions'] if d['status'] == 'pending'] == original_pending, 'The handoff gate must not modify previously pending candidates')
    _require(sum((log.get('count_delta', 0) for log in output['passage_log'])) == output['aggregate']['total'], 'Final passage log does not reconcile')
    output['v7_handoff_relations'] = deepcopy(proposal.get('relations', []))
    output['v7_handoff_audit'] = deepcopy(proposal.get('audit', []))
    output['v7_publication_audit'] = audits
    output['report'].update(version='b_v7_scoped_handoff_publication_v1', previous_engine_version='b_v6_user_invalid_policy_v1', v7_handoff_controls=deepcopy(proposal.get('controls', {})), open_passage_diagnostic_counts=dict(sorted(Counter((r['disposition'] for r in output.get('open_passage_diagnostics', []))).items())), v7_publication={'mode': 'OFFLINE_BEFORE_PUBLICATION', 'decision_frame': decision_frame, 'private_candidate_count': len(provisional['events']), 'additional_invalid_candidates': len(implicated), 'previous_pending_changed': 0, 'physical_episodes_merged': 0, 'newly_created_accepted_events': 0, 'inference_promoted_to_measured': 0, 'unpublished_candidate_logs_have_zero_delta': True, 'finalized_active_event_ids': sorted(candidates)})
    return _rename_event_ids(output)

def replay_frames(frames, geometry, *, source_identity, policy):
    """One isolated offline replay; only the finalized B v7 result is returned."""
    from .handoff import propose_handoff_conflicts
    copied = deepcopy(list(frames))
    provisional = previous.replay_frames(copied, geometry, source_identity=source_identity, policy=deepcopy(policy))
    proposal = propose_handoff_conflicts(provisional, copied, geometry, policy)
    return finalize_handoff_candidates(provisional, proposal, frames=copied)
