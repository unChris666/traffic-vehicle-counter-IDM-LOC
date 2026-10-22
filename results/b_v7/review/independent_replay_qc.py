"""Read retained results only. No pipeline replay or model execution."""
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'notebooks'))

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASELINE = ROOT / 'results/b_v6/execution/pilot_v6_machine_final/weekday_siang/counting_result.json.gz'
CONTROLS = [4251, 4281, 4149, 4367, 4934, 4946, 4953, 2445, 4552, 4480, 1101, 1070]


def read(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scope(event):
    return (event.get('physical_unit_id'), event.get('episode_id'), event.get('passage_id'))


def event_content(event, *, include_display=True):
    # Namespace and event IDs intentionally bind the complete experiment policy.
    # All source witnesses, physical scope, route, display label and decision
    # semantics must remain equal for a preserved event.
    excluded = ('namespace', 'event_id') if include_display else ('namespace', 'event_id', 'display_id')
    return {k: v for k, v in event.items() if k not in excluded}


def compact(event):
    return {k: event.get(k) for k in ('event_id', 'track_id', 'physical_unit_id',
        'episode_id', 'passage_id', 'activation_frame', 'decision_frame',
        'category', 'direction', 'route', 'display_id')} | {
        'measured_crossing': event['evidence']['measured_crossing']}


def control(result, track):
    return {
        'active': [event_content(e) for e in result['events'] if e['track_id'] == track],
        'invalid': [{k: d.get(k) for k in ('frame_index', 'decision_frame', 'physical_unit_id',
            'episode_id', 'passage_id', 'role', 'category', 'direction', 'status', 'reasons')}
            for d in result['invalid_decisions'] if d.get('track_id') == track],
        'pending': [d for d in result['decisions'] if d.get('track_id') == track and d['status'] == 'pending'],
        'assignments': [a for a in result.get('frame_assignments', []) if a.get('track_id') == track]}


def main(candidate_path):
    candidate_path = Path(candidate_path).resolve()
    before, after = read(BASELINE), read(candidate_path)
    first, second = ({scope(e): e for e in r['events']} for r in (before, after))
    assert len(first) == len(before['events']) and len(second) == len(after['events'])
    removed = [first[k] for k in first.keys() - second.keys()]
    added = [second[k] for k in second.keys() - first.keys()]
    changed = [{'before': compact(first[k]), 'after': compact(second[k])}
        for k in first.keys() & second.keys() if event_content(first[k]) != event_content(second[k])]
    functional_changed = [{'before': compact(first[k]), 'after': compact(second[k])}
        for k in first.keys() & second.keys()
        if event_content(first[k], include_display=False) != event_content(second[k], include_display=False)]
    display_only = [{'track_id':first[k]['track_id'],'passage_id':first[k]['passage_id'],
        'baseline_display_id':first[k]['display_id'],'candidate_display_id':second[k]['display_id'],
        'source_event_content_except_display_and_namespace_equal':True}
        for k in first.keys() & second.keys()
        if event_content(first[k]) != event_content(second[k])
        and event_content(first[k],include_display=False) == event_content(second[k],include_display=False)]
    old_pending = [d for d in before['decisions'] if d['status'] == 'pending']
    new_pending = [d for d in after['decisions'] if d['status'] == 'pending']
    old_scope = {scope(d) for d in before['invalid_decisions']}
    new_invalid = [d for d in after['invalid_decisions'] if scope(d) not in old_scope]
    controls = [{'track_id': t, 'exact_source_decisions_and_assignments_unchanged': control(before,t) == control(after,t),
                 'accepted_before': len(control(before,t)['active']), 'accepted_after': len(control(after,t)['active'])}
                for t in CONTROLS]
    target_after = [e for e in after['events'] if e['track_id'] in (1049, 1123)]
    target_removed = sorted(e['track_id'] for e in removed) == [1049,1123]
    exact_delta = target_removed and not added and not functional_changed and len(new_invalid) == 2
    target_gate = 'PASS_SCOPED_DUPLICATE_PREVENTION_WITH_INTENTIONAL_COVERAGE_LOSS' if exact_delta and not target_after else 'BLOCKED'
    source_issue = [e for e in after['events'] if e['track_id'] == 4843 and e['activation_frame'] == 7935]
    from phase_9_v6_qc_review import review_results
    previous_reference = read(ROOT / 'results/b_v5/execution/pilot_p0_v2/weekday_siang/counting_result.json.gz')
    inventory_review = review_results(previous_reference, after,
        ROOT / 'results/phase_9/20261020_QC_BV4_SIANG')
    (OUT/'legacy_inventory_comparison.json').write_text(json.dumps(inventory_review,indent=2)+'\n')
    baseline_inventory = read(BASELINE.parent/'qc_review.json')
    def without_policy_bound_ids(value):
        if isinstance(value, list):
            return [without_policy_bound_ids(v) for v in value]
        if isinstance(value, dict):
            return {k:without_policy_bound_ids(v) for k,v in value.items()
                if k != 'namespace' and not k.endswith('event_id') and not k.endswith('event_ids')}
        return value
    inventory_changes = {}
    for group in ('pending','cancellations','discovery'):
        a = {r['case_id']:r for r in baseline_inventory['original_qc_comparison'][group]}
        b = {r['case_id']:r for r in inventory_review['original_qc_comparison'][group]}
        inventory_changes[group] = {'baseline_case_count':len(a),'candidate_case_count':len(b),
            'case_ids_equal':set(a)==set(b),
            'changed_source_dispositions':sorted(k for k in a.keys() & b.keys()
                if without_policy_bound_ids(a[k]) != without_policy_bound_ids(b[k]))}
    data = {
        'schema_version':'phase9_bv7_independent_replay_qc_v1',
        'baseline_path':str(BASELINE.relative_to(ROOT)), 'baseline_sha256':digest(BASELINE),
        'candidate_path':str(candidate_path.relative_to(ROOT)), 'candidate_sha256':digest(candidate_path),
        'review_type':'RETAINED_SOURCE_IMAGE_REVIEW_PLUS_EVENT_SCOPE_COMPARISON',
        'baseline_aggregate':before['aggregate'],'candidate_aggregate':after['aggregate'],
        'source_identity_equal':before['source_identity'] == after['source_identity'],
        'full_identity_assignments_equal':before.get('frame_assignments') == after.get('frame_assignments'),
        'pending_decisions_exactly_equal':old_pending == new_pending,
        'accepted_events_removed':[compact(e) for e in sorted(removed,key=lambda e:e['track_id'])],
        'accepted_events_added':[compact(e) for e in added], 'accepted_events_changed':changed,
        'accepted_events_with_source_or_counting_changes':functional_changed,
        'display_only_renumberings':sorted(display_only,key=lambda e:e['track_id']),
        'new_invalid_decisions':new_invalid, 'regression_controls':controls,
        'published_log_total':sum(row.get('count_delta',0) for row in after['passage_log']),
        'legacy_qc_inventory_reconciliation':inventory_changes,
        'legacy_inventory_reference_duplicate_blockers':inventory_review['known_reference_duplicate_blockers'],
        'legacy_inventory_reference_controls_requiring_review':inventory_review['known_reference_controls_requiring_review'],
        'target_scope_gate':target_gate,
        'target_physical_passages_in_source_review':1,
        'target_published_events_after':len(target_after),
        'target_intentional_physical_passage_coverage_loss':1 if exact_delta else None,
        'new_source_confirmed_duplicates_from_candidate':0 if exact_delta else None,
        'new_distinct_vehicle_suppression_observed_in_actual_delta':0 if exact_delta else None,
        'no_global_error_rate_established':True,
        'preexisting_unresolved_identity_contamination_event':[compact(e) for e in source_issue],
        'overall_p0_gate':'BLOCKED',
        'overall_p0_reason':'4843 origin and destination source boxes refer to different physical motorcycles across occlusion; current accepted inferred event remains unresolved.' if source_issue else 'Source identity-contamination case4843 requires an explicit reviewed disposition and regression before overall closure.',
        'all_eight_baseline_inferred_review_reference':'all_baseline_inferred_review.json',
        'new_blocker_evidence_reference':'independent_4843_identity_review.json',
        'negative_actual_source_controls':[
            {'tracks':[1123,1101],'frame':1376,'verdict':'DISTINCT_CO_PRESENT_FOLLOWING_MOTORCYCLES'},
            {'tracks':[1123,1070],'frames':[1355,1376],'verdict':'DISTINCT_OPPOSITE_DIRECTION_MOTORCYCLES'}],
        'actual_negative_control_limit':'Raw1101 and1070 have no baseline active accepted event. Actual source review proves distinct physical units and preservation of assignments; preservation of accepted close-following/return counts is demonstrated only by the synthetic controls, not by these two source units.',
        'reviewer_exposure':'Known development case and retained annotations were reviewed; not blind or held-out.',
        'model_tracker_reid_counting_enhancement_executed_by_qc':False,
        'accuracy_zero_mistakes_or_production_reliability_claimed':False}
    (OUT/'independent_replay_qc.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({k:data[k] for k in ['target_scope_gate','overall_p0_gate','pending_decisions_exactly_equal','full_identity_assignments_equal','published_log_total']},indent=2))


if __name__ == '__main__':
    main(sys.argv[1])
