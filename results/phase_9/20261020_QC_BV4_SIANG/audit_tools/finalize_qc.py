"""QC artifact compilation only; never runs the application counting pipeline."""
import csv, gzip, hashlib, json, shutil
from collections import Counter
from pathlib import Path

R = Path('/workspace/traffic-vehicle-counter-IDM-LOC')
O = R / 'results/phase_9/20261020_QC_BV4_SIANG'
BASE = R / 'results/b_v4/execution/pilot_machine_final/weekday_siang'

def read_gzip(name):
    return json.loads(gzip.decompress((BASE / (name + '.json.gz')).read_bytes()))

def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def jsonl(path, rows):
    path.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

baseline = read_gzip('counting_result')
events = {e['event_id']: e for e in baseline['events']}
track_events = {e['track_id']: e for e in baseline['events']}
pending = {d['passage_id']: d for d in baseline['decisions'] if d['status'] == 'pending'}
assert len(pending) == 68
normalized = []
for group in ('roles', 'identity', 'duplicates'):
    path = O / group / 'per_case_decisions.jsonl'
    rows = lines(path)
    assert len(rows) == {'roles': 29, 'identity': 31, 'duplicates': 8}[group]
    for row in rows:
        if group == 'roles':
            pid, rid = row['baseline_passage_id'], row['raw_track_id']
            resolved = row['status'] == 'QC_DECIDED'
            action, delta = row['counting_recommendation'], row['independent_person_proposed_delta']
            cid, viewed = row['qc_case_id'], row['role_scope']['exact_source_frames_viewed']
        elif group == 'identity':
            pid, rid = row['passage_id'], row['track_id']
            resolved = row['review_status'] == 'QC_DECIDED'
            action, delta = row['recommended_decision'], row['accepted_delta_vs_baseline']
            cid, viewed = row['case_id'], row['reviewed_source_frames']
        else:
            pid, rid = row['baseline_pending_passage_id'], row['pending_raw_id']
            resolved = row['qc_status'].startswith('QC_RESOLVED')
            action, delta = row['decision'], row['recommended_count_delta']
            cid, viewed = row['case_id'], row['reviewed_source_frames']
        assert pid in pending and pending[pid]['track_id'] == rid
        assert row['video_sha256'] == baseline['source_identity']['video_sha256']
        assert viewed
        checked_evidence = []
        for item in row['evidence']:
            p = R / item['path']
            if not p.is_file():
                p = O / group / item['path']
            expected_sha = item.get('sha256', item.get('png_sha256'))
            assert expected_sha and p.is_file() and sha(p) == expected_sha, str(p)
            checked_evidence.append(dict(item, path=str(p.relative_to(R)), sha256=expected_sha))
        normalized.append({'case_id': cid, 'group': group, 'baseline_passage_id': pid,
            'raw_track_id': rid, 'baseline_decision_frame': pending[pid]['frame_index'],
            'qc_status': 'QC_RECOMMEND_CLOSE' if resolved else 'UNRESOLVED',
            'recommended_action': action, 'proposed_count_delta_vs_machine': delta if resolved else None,
            'proposed_pending_delta': -1 if resolved else 0,
            'source_frames_viewed': viewed, 'evidence': checked_evidence,
            'detail_ledger': str(path.relative_to(R)), 'human_confirmation_status': 'AI_QC_RECOMMENDATION',
            'applied_to_machine': False})

assert {r['baseline_passage_id'] for r in normalized} == set(pending)
assert len({r['baseline_passage_id'] for r in normalized}) == 68
assert len({r['case_id'] for r in normalized}) == 68
jsonl(O / 'review_decisions.jsonl', normalized)
with (O / 'case_index.csv').open('w', newline='') as f:
    keys = ['case_id', 'group', 'raw_track_id', 'baseline_decision_frame', 'qc_status',
            'recommended_action', 'proposed_count_delta_vs_machine', 'baseline_passage_id', 'detail_ledger']
    writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore'); writer.writeheader(); writer.writerows(normalized)

# Current accepted findings, deduplicated by immutable machine event ID.
# The ambiguous156 and927 groups remain unresolved rather than being forced into a cancellation.
reasons = {
    2536: ('STATIONARY_NO_PASSAGE', 'Motor merah tetap parkir; perubahan bbox akibat occlusion.'),
    2584: ('STATIONARY_NO_PASSAGE', 'BBox mobil sebenarnya mengamati van/pickup parkir.'),
    2680: ('STATIONARY_NO_PASSAGE', 'Motor merah parkir, bukan motor foreground yang melintas.'),
    3512: ('STATIONARY_NO_PASSAGE', 'Van/pickup parkir tertutup motor/gerobak; bbox bergeser.'),
    4569: ('STATIONARY_NO_PASSAGE', 'BBox melekat pada van parkir meski Honda melintas di depannya.'),
    4627: ('MIXED_OBJECT_AND_STATIONARY_CONTEXT', 'BBox awal mencakup Honda, lalu berubah ke van parkir; bukan passage konsisten.'),
    2583: ('MIXED_PHYSICAL_OBJECTS', 'Motor merah parkir lalu box pada roda SUV yang bergerak; origin/akhir beda objek.'),
    1107: ('MIXED_PHYSICAL_OBJECTS_AND_DIRECTION', 'Mulai pada pickup datang, berakhir pada fragmen motor berbeda; bukan motorcycle B_TO_A yang dibuktikan.'),
    4567: ('MIXED_PHYSICAL_OBJECTS', 'Riwayat van parkir, Honda datang, lalu motor lain; tidak boleh mewarisi origin/timer.'),
    4541: ('NO_NEW_REVERSE_PASSAGE', 'Honda bergerak mendekati kamera, sementara timeout mengklaim passage balik B_TO_A.'),
    4367: ('COMPLETED_PASSAGE_NEW_ID_FALSE_RETURN', 'Ekor pickup biru4149 yang sudah counted A_TO_B7422, bukan return B_TO_A baru.'),
    2697: ('DUPLICATE_CROSS_CATEGORY', 'MPV abu-abu yang sama sudah diterima sebagai car2706; truck timeout tidak menambah unit.'),
    4934: ('DUPLICATE_COMPONENT_HISTORY', 'Satu motor Gojek4934/4946/4953; pertahankan maksimal satu passage.'),
    4946: ('DUPLICATE_COMPONENT_HISTORY', 'BBox belakang dari motor yang sama dengan4934/4953, bukan kendaraan kedua.'),
    4281: ('DUPLICATE_SAME_PHYSICAL_MOTORCYCLE', 'Motor yang sama dengan4251; penumpang/kain dan koeksistensi bbox mendukung satu unit.'),
    3555: ('CARGO_COMPONENT_NOT_TRUCK_UNIT', 'Muatan kardus terikat pada motor3563, bukan truck terpisah.')}
keep = {4367: 4149, 2697: 2706, 4934: 4953, 4946: 4953, 4281: 4251, 3555: 3563}
extra_evidence = {
    4367: O/'accepted_timeout_control/evidence/pair-blue4149_4367.jpg',
    4541: O/'accepted_timeout_control/evidence/pair-honda4541_4567.jpg',
    4567: O/'accepted_timeout_control/evidence/pair-honda4541_4567.jpg',
    2697: O/'accepted_timeout_control/evidence/pair-mpv2697_2706.jpg',
    4934: O/'accepted_timeout_control/evidence/pair-gojek4934_4946_4953.jpg',
    4946: O/'accepted_timeout_control/evidence/pair-gojek4934_4946_4953.jpg',
    4281: O/'roles/evidence/accepted-4251-4281-comparison.jpg',
    3555: O/'unmatched/evidence/box-motor-1.jpg'}
selected = json.loads((O/'accepted_timeout_control/selected_events.json').read_text())
selected_by_track = {s['track_id']: s for s in selected}
actions = []
for rid, (reason, observation) in reasons.items():
    event = track_events[rid]
    sheet = extra_evidence.get(rid)
    if sheet is None:
        s = selected_by_track[rid]
        sheet = O/f"accepted_timeout_control/evidence/{s['case_id']}-raw{rid}.jpg"
    assert sheet.is_file()
    actions.append({'case_id': f'ACCEPTED-QC-{rid}', 'event_id': event['event_id'],
        'raw_track_id': rid, 'display_id': event['display_id'], 'category': event['category'],
        'direction': event['direction'], 'route': event['route'],
        'measured_crossing': event['evidence']['measured_crossing'], 'activation_frame': event['activation_frame'],
        'action': 'PROPOSE_CANCEL', 'reason': reason, 'observation': observation,
        'proposed_count_delta': -1, 'keep_event_id': track_events[keep[rid]]['event_id'] if rid in keep else None,
        'canonical_route_stays_inferred_if_originally_inferred': True,
        'evidence': [{'path': str(sheet.relative_to(R)), 'sha256': sha(sheet)}],
        'claim_type': 'AI_QC_SOURCE_REVIEW_NOT_GROUND_TRUTH', 'applied_to_machine': False})
assert len({a['event_id'] for a in actions}) == 16
assert not ({a['event_id'] for a in actions} & {a['keep_event_id'] for a in actions if a['keep_event_id']})
jsonl(O/'accepted_event_actions.jsonl', actions)

control = []
by_event = {a['event_id']: a for a in actions}
for s in selected:
    action = by_event.get(s['event_id'])
    sheet = O/f"accepted_timeout_control/evidence/{s['case_id']}-raw{s['track_id']}.jpg"
    assert sheet.is_file()
    control.append({'case_id': s['case_id'], 'event_id': s['event_id'], 'raw_track_id': s['track_id'],
        'display_id': s['display_id'], 'qc_status': 'PROPOSE_CANCEL' if action else 'UNRESOLVED_ESTIMATE_NOT_FINALIZED',
        'reason': action['reason'] if action else 'Source samples show traffic but unique identity/category/passage still needs reconciliation; not automatically valid or false.',
        'source_frames_viewed': s['frames_review_planned'],
        'evidence': [{'path': str(sheet.relative_to(R)), 'sha256': sha(sheet)}],
        'proposed_count_delta': -1 if action else None, 'applied_to_machine': False,
        'review_basis': 'AI subreviewer viewed34source sheets; root independently challenged selected positive/negative cases.'})
jsonl(O/'accepted_timeout_control/per_event_decisions.jsonl', control)

summary = {'baseline': baseline['aggregate'], 'all_pending_cases_accounted_for': True,
    'pending_cases': len(normalized), 'recommend_close': sum(x['qc_status']=='QC_RECOMMEND_CLOSE' for x in normalized),
    'recommend_close_plus_zero': sum(x['qc_status']=='QC_RECOMMEND_CLOSE' and x['proposed_count_delta_vs_machine']==0 for x in normalized),
    'recommend_count_plus_one': sum(x['qc_status']=='QC_RECOMMEND_CLOSE' and x['proposed_count_delta_vs_machine']==1 for x in normalized),
    'unresolved_pending_cases': [dict(case_id=x['case_id'],raw_track_id=x['raw_track_id'],group=x['group']) for x in normalized if x['qc_status']=='UNRESOLVED'],
    'pending_groups': {g: dict(Counter(x['qc_status'] for x in normalized if x['group']==g)) for g in ['identity','roles','duplicates']},
    'unique_accepted_cancel_proposals': len(actions), 'accepted_timeout_control': dict(Counter(x['qc_status'] for x in control)),
    'partial_closed_decision_delta_vs_machine': sum(x['proposed_count_delta_vs_machine'] for x in normalized if x['qc_status']=='QC_RECOMMEND_CLOSE') - len(actions),
    'partial_delta_is_not_final_video_total': True, 'machine_ledger_changed': False, 'new_model_or_counting_run': False,
    'prior_review_assisted_pedestrian54_must_not_be_added_twice': True,
    'physical_groups_crosslinked': [['IDENTITY-18','QC_DUP_2549'], ['QC_DUP_4774','QC_DUP_4820'], ['4934','4946','4953']]}
assert summary['recommend_close'] == 59 and summary['recommend_close_plus_zero'] == 57 and summary['recommend_count_plus_one'] == 2
write(O/'qc_summary.json', summary)

# Keep exact audit helpers, not application executable modifications.
tools = O/'audit_tools'; tools.mkdir(exist_ok=True)
for p in Path('/tmp/qc-tools').glob('*.py'):
    shutil.copyfile(p, tools/p.name)
print(json.dumps({k:v for k,v in summary.items() if k not in ['unresolved_pending_cases','physical_groups_crosslinked']}, indent=2))
