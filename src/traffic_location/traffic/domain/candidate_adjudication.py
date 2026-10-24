"""POST_COUNTING +0 only; no raw role edits, new events or accepted promotions."""
from collections import Counter
from copy import deepcopy
from .._kernel.review_finalizer import _require, _pending_index, _scope, _digest, SCOPE_FIELDS, STATUS, REASON
from ..contracts.review import CandidateAdjudication

def apply(result, adjudication, *, baseline_result, finalization_frame):
    if not isinstance(adjudication, CandidateAdjudication):
        raise ValueError('POST_COUNTING adjudication required')
    adjudications = adjudication.payload.object()
    frame = finalization_frame
    _require(type(frame) is int and frame == result['report']['last_frame_index'], 'Adjudication requires source EOF')
    baseline = _pending_index(baseline_result)
    candidate = _pending_index(result)
    validated, ids, scopes = [], set(), set()
    for review in adjudications['adjudications']:
        key = _scope(review['baseline_candidate_scope'])
        _require(key in baseline and key in candidate, 'Candidate no longer pending')
        _require(review['adjudication_id'] not in ids and key not in scopes, 'Duplicate adjudication')
        ids.add(review['adjudication_id']); scopes.add(key)
        _require(candidate[key].get('source_ref') == baseline[key].get('source_ref') and candidate[key].get('role') == baseline[key].get('role'), 'Candidate source/context differs')
        validated.append((key, review))
    output = deepcopy(result)
    pending = _pending_index(output)
    audits = []
    for key, review in validated:
        row = pending[key]
        original = deepcopy(row)
        source = deepcopy(row['source_ref'])
        origin = 'AI_ASSISTED_SOURCE_REVIEW' if review['reviewer_origin'] == 'AI_PIXELS_REVIEW' else 'EXPLICIT_USER_SOURCE_REVIEW'
        row.update(status=STATUS, count_delta=0, accepted_count_event=False, display_id=None, candidate_decision_frame=original.get('frame_index'), decision_frame=frame, resolved_at_frame=frame, resolution_reason=REASON, reasons=[REASON], previous_status='pending', previous_reasons=deepcopy(original.get('reasons', [])), previous_reason_evidence=deepcopy(original.get('reason_evidence', [])), reviewed_role=review['reviewed_role'], adjudication_id=review['adjudication_id'], decision_origin=origin, finalization_mode='OFFLINE_REVIEWED_PLUS_ZERO', role_assignment_effect='EXACT_PENDING_SOURCE_SAMPLE_ONLY_NO_HISTORY_RELABEL_OR_PARENT_ALIAS', reason_evidence=[{'reason': REASON, 'source_ref': source, 'adjudication_id': review['adjudication_id'], 'proof_artifacts': deepcopy(review['proof_artifacts']), 'role_scope': deepcopy(review['role_scope'])}])
        output['passage_log'].append({'frame_index': frame, 'candidate_decision_frame': original.get('frame_index'), **{name: deepcopy(row.get(name)) for name in SCOPE_FIELDS}, 'status': STATUS, 'count_delta': 0, 'event_id': None, 'source_ref': source, 'message': REASON, 'adjudication_id': review['adjudication_id'], 'decision_origin': origin, 'reviewed_role': review['reviewed_role']})
        for diagnostic in output.get('open_passage_diagnostics', []):
            if _scope(diagnostic) == key:
                diagnostic.update(previous_disposition=diagnostic.get('disposition'), disposition=REASON, timeout_eligible=False, reviewed_pending_adjudication_id=review['adjudication_id'])
        audits.append({'adjudication_id': review['adjudication_id'], 'baseline_candidate_scope': deepcopy(review['baseline_candidate_scope']), 'baseline_source_ref': source, 'previous_decision': original, 'final_status': STATUS, 'reason': REASON, 'reviewed_role': review['reviewed_role'], 'candidate_decision_frame': original.get('frame_index'), 'decision_frame': frame, 'count_delta': 0, 'decision_origin': origin, 'review': deepcopy(review), 'crossing_evidence_changed': False, 'physical_identity_merged': False, 'not_a_recovered_physical_passage': True})
    output['aggregate']['pending'] = len(_pending_index(output))
    _require(output['events'] == result['events'] and output.get('cancelled_events') == result.get('cancelled_events') and (output.get('invalid_decisions') == result.get('invalid_decisions')), 'Reviewed pending closure must not change accepted or invalid passage decisions')
    _require(sum((item.get('count_delta', 0) for item in output['passage_log'])) == output['aggregate']['total'], 'Published log no longer reconciles')
    output['v8_pending_finalization_audit'] = audits
    if 'open_passage_diagnostic_counts' in output['report']:
        output['report']['open_passage_diagnostic_counts'] = dict(sorted(Counter((row['disposition'] for row in output.get('open_passage_diagnostics', []))).items()))
    output['report']['v8_reviewed_pending_finalization'] = {'baseline_pending': len(baseline), 'candidate_pending_before': len(candidate), 'candidate_pending_after': output['aggregate']['pending'], 'resolved_not_eligible': len(audits), 'resolved_to_invalid': 0, 'accepted_events_added': 0, 'actual_offline_decision_frame': frame, 'roles': dict(sorted(Counter((a['reviewed_role'] for a in audits)).items())), 'review_manifest_sha256_semantic': _digest(adjudications), 'baseline_result_sha256': adjudications['baseline_result_sha256'], 'source_observations_or_histories_reassigned': False, 'qc_adjudications_used_as_machine_predictions': False}
    return output
