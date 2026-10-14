"""Join retained machine, pixel-review and guarded-overlay outputs; no inference."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

RUN = Path('docs/evidence/phase_7/temporal/20261014T062858_002323Z')


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(root):
    run = root / RUN
    source = run / 'temporal_review/physical_passage_comparison.json'
    comparison = read(source)
    inputs = {str(source.relative_to(root)): sha(source)}
    branches = {}
    rows = []
    summaries = {}
    for variant in ('raw', 'gamma_070'):
        paths = {name: run / (variant + '_reviewed') / name for name in
                 ('report.json', 'resolved_decisions.json.gz', 'accepted_events.json.gz', 'aggregate.json')}
        inputs.update({str(p.relative_to(root)): sha(p) for p in paths.values()})
        report = read(paths['report.json'])
        decisions = read(paths['resolved_decisions.json.gz'])
        events = read(paths['accepted_events.json.gz'])
        aggregate = read(paths['aggregate.json'])
        assert not report['original_machine_artifacts_modified']
        assert not report['model_geometry_resolver_rerun']
        assert not report['automatic_improvement_established']
        assert len(events) == report['accepted_events'] == aggregate['total']
        assert len({x['event_id'] for x in events}) == len(events)
        branches[variant] = ({x['candidate_id']: x for x in decisions}, {x['candidate_id']: x for x in events})
        summaries[variant] = {
            'machine': read(run / variant / 'counting_report.json')['decision_status_counts'],
            'reviewed': report['decision_status_counts'],
            'manual_confirmed': report['manual_confirmed_physical_passages'],
            'preserved_automatic': report['preserved_machine_accepted_events'],
            'by_category': aggregate['by_category'], 'by_direction': aggregate['by_direction'],
        }
    for passage in comparison['passages']:
        row = {'physical_passage_review_id': passage['physical_passage_review_id'],
               'split': passage['split'], 'case_id': passage['case_id'],
               'physical_observation': passage['visual_observation'],
               'comparison': passage['comparison'], 'branches': {}}
        for variant, branch in passage['branches'].items():
            resolved, events = branches[variant]
            candidate = branch['candidate_id']
            decision = resolved[candidate]
            event = events.get(candidate)
            item = {k: branch[k] for k in ('candidate_id', 'track_id', 'machine_status', 'direction',
                                          'origin_frame', 'crossing_frame_start', 'crossing_frame_end',
                                          'confirmation_frame', 'source_anchor')}
            item.update({'reviewed_status': decision['status'],
                         'reviewed_reasons': decision['reasons'],
                         'accepted_event_id': event['event_id'] if event else None,
                         'category': event['category'] if event else decision['category'],
                         'manual_review_applied': bool(event and event.get('manual_review_applied'))})
            if event:
                assert event['direction'] == branch['direction']
                geometry = event['geometry_evidence']
                assert geometry['crossing_evidence']['start_observation']['frame_index'] == branch['crossing_frame_start']
                assert geometry['crossing_evidence']['end_observation']['frame_index'] == branch['crossing_frame_end']
            row['branches'][variant] = item
        rows.append(row)
    assert len(rows) == 8
    result = {'claim_type': 'ACTUAL_RETAINED_PHYSICAL_PASSAGE_COMPARISON_WITH_SEPARATE_REVIEWED_OUTPUTS_NOT_GROUND_TRUTH',
              'run_id': run.name, 'method_path': str(Path(__file__).resolve().relative_to(root)),
              'method_sha256': sha(Path(__file__)), 'source_bindings': inputs,
              'scope': 'eight emitted candidate physical passages in five predeclared windows; not complete traffic',
              'pairing_uses_numeric_ids_across_variants': False,
              'model_tracker_encoder_resolver_geometry_rerun': False,
              'branch_summaries': summaries, 'passages': rows,
              'holdout_reused_for_tuning': False,
              'conclusion': 'Retain raw for the next research baseline. Gamma0.7 is not promoted: reviewed passages agree; the sole automatic difference is sensitive to offline episode boundaries, regressions remain, and measured processing cost increases.'}
    destination = run / 'final_physical_passage_comparison.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    with (run / 'final_physical_passage_comparison.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['physical_passage', 'split', 'crossing_start', 'crossing_end', 'direction',
                         'raw_machine', 'gamma_machine', 'raw_reviewed', 'gamma_reviewed', 'raw_category', 'gamma_category'])
        for row in rows:
            raw, gamma = row['branches']['raw'], row['branches']['gamma_070']
            writer.writerow([row['physical_passage_review_id'], row['split'], raw['crossing_frame_start'],
                             raw['crossing_frame_end'], raw['direction'], raw['machine_status'], gamma['machine_status'],
                             raw['reviewed_status'], gamma['reviewed_status'], raw['category'], gamma['category']])
    decision_path = root / 'docs/evidence/phase_7/selection/TOR3-MALAM_final_decision_v1.json'
    temporal = read(run / 'report.json')
    decision = {'claim_type': 'ENGINEERING_RECOMMENDATION_FROM_COMPLETED_SCOPED_EXPERIMENT_NOT_PRODUCTION_VALIDATION',
                'phase_status': 'COMPLETED_SCOPED_PHASE7_EXPERIMENT_WITH_EXPLICIT_LIMITATIONS',
                'recommended_next_research_baseline': 'raw', 'production_enhancement_selected': None,
                'candidate_not_promoted': 'gamma_070', 'gamma': 0.7,
                'holdout_outcomes_used_to_retune': False,
                'frozen_development_selection_path': 'docs/evidence/phase_7/selection/TOR3-MALAM_DEV_shortlist_v1.json',
                'final_comparison_path': str(destination.relative_to(root)),
                'final_comparison_sha256': sha(destination),
                'actual_temporal_report_sha256': sha(run / 'report.json'),
                'independent_temporal_audit_sha256': sha(run / 'independent_artifact_audit.json'),
                'loop_wall_seconds': {k: temporal['variants'][k]['timing']['loop_wall_seconds'] for k in ('raw', 'gamma_070')},
                'findings': [
                    'Gamma opens shadow/midtone pixels in actual review, while blur/glare and category ambiguity remain.',
                    'Both reviewed branches accept the same six motorcycle and one truck passages; one category-conflicting vehicle remains pending.',
                    'Gamma sole automatic acceptance uses valid measured vehicle BC but depends on a shorter vehicle episode after bicycle labels; a general improvement is not established.',
                    'Both holdout branches originally retain two machine pending cases; positive manual reviews resolve them without tuning.',
                    'Instrumented sequential gamma loop takes about1.79 times raw; no production throughput or monetary cost is claimed.'
                ],
                'open_decisions': [
                    'Separate investigation of whole-episode category unanimity and global relation rejection outside the passage-local support window.',
                    'Final suitable vehicle ReID model/configuration, tested independently.',
                    'Jitter/duplicate controls, genuine-return automation and unresolved product taxonomy.',
                    'Missed physical passages and full-video completeness require wider audit; eight candidate cases are not ground truth.',
                    'Confirm exact eight-video inventory/metadata and review geometry per video before an authorized Phase8 task.'
                ], 'phase8_started': False, 'formal_ground_truth': False}
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'physical_passage_rows': len(rows), 'reviewed_branch_summaries': summaries}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    finalize(parser.parse_args().repo.resolve())
