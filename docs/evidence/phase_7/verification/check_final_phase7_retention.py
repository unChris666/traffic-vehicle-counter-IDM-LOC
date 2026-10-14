#!/usr/bin/env python3
"""Finalize or independently verify retained Phase 7 evidence, without inference.

``--capture`` is only for the final documentation/artifact freeze. The default
checks an existing manifest and never rewrites it. This checker imports no
detector, tracker, encoder, geometry state machine or counting resolver. Raw BC,
finite-segment arithmetic, source links and aggregate arithmetic are checked
directly from the retained records. Physical review remains review, not truth.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

PHASE7 = 'docs/evidence/phase_7'
RUN_REL = PHASE7 + '/temporal/20261014T062858_002323Z'
SCREEN_REL = PHASE7 + '/screening/20261014T060849_366767Z'
MANIFEST_REL = PHASE7 + '/final_retention_manifest.json'
VALIDATION_REL = PHASE7 + '/final_artifact_validation.json'
TOP_FILES = (
    'AGENTS.md', 'README.md', 'docs/PROJECT_CONTEXT.md',
    'docs/OPEN_DECISIONS.md', 'docs/PHASE_7_TASK.md',
    'docs/NIGHT_PREPROCESSING_EXPERIMENT.md', 'docs/PHASE_7_REVIEW.md',
    'notebooks/07_night_preprocessing.ipynb',
    'notebooks/07b_night_temporal_comparison.ipynb',
    'notebooks/phase_7_night_helpers.py', 'notebooks/phase_7_night_tests.py',
    'notebooks/phase_7_temporal_helpers.py', 'notebooks/phase_7_temporal_tests.py',
)
FROZEN_SOURCE = {
    'notebooks/phase_7_night_helpers.py': '6a31794bad0c5cd346575ad4602adb5d10f17bd14cc1094dd5f2b207b0935889',
    'notebooks/phase_7_night_tests.py': '620a6238695158c99d721750ad56f31e24dbba56269ac94f676a95653d5ed451',
    'notebooks/07_night_preprocessing.ipynb': 'aa40f4240c292d14c5428877907ff8ab9e9281e3882ca8edc8ddd6f0d8d873b5',
    'notebooks/phase_7_temporal_helpers.py': '2ef8de2d0d309b86bae6a75a2135c59d8dd09e203610fc444c6023c0614d9c74',
    'notebooks/phase_7_temporal_tests.py': '800bce2db891aedb03b841a95455acdfaf8c27ca22bec506274f8c4d24d07124',
    'notebooks/07b_night_temporal_comparison.ipynb': '99cf4f22c6f63c7211b68467cfe8185a74b80a2228d1d24a74dc6655065b6081',
    'notebooks/phase_5_geometry_helpers.py': 'c344aa5b73b8b75fcdd567355b867e977a3d8e170feb512cdf0d15ac61b123c9',
    'notebooks/phase_6_counting_helpers.py': '99a98807d315b42bd3995b8e68afc749e47c76b03b39329dbb5f4b867661f4c5',
    'notebooks/phase_6_identity_resolution_helpers.py': '18949e7a44b6d73b9d50269f9d4569fbda781ba48269046b982287376ec3f054',
}
VIDEO_SUFFIXES = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v'}
WEIGHT_SUFFIXES = {'.pt', '.pth', '.onnx', '.engine', '.safetensors'}
VEHICLES = {'motorcycle', 'car', 'truck', 'bus'}
CATEGORIES = {'motorcycle', 'car', 'truck', 'bus_angkot', 'pedestrian'}
PROVENANCE = 'retained_phase_7_detection'
VIDEO_SHA = 'a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def reject_nonfinite(value):
    raise ValueError('Nonfinite JSON value: ' + value)


def read(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as stream:
        return json.load(stream, parse_constant=reject_nonfinite)


def contains_pending_placeholder(value):
    """Reject saved JSON placeholders while allowing this guard's source text."""
    marker = 'PENDING_FINAL_RETENTION_CAPTURE_NOT_EXECUTED_RESULT'
    if isinstance(value, str):
        return value == marker
    if isinstance(value, dict):
        return any(contains_pending_placeholder(k) or contains_pending_placeholder(v)
                   for k, v in value.items())
    if isinstance(value, list):
        return any(contains_pending_placeholder(v) for v in value)
    return False


def scoped_paths(repo):
    paths = {repo / p for p in TOP_FILES}
    paths.update(p for p in (repo / PHASE7).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts
                 and p.suffix != '.pyc')
    paths -= {repo / MANIFEST_REL, repo / VALIDATION_REL}
    return sorted(paths)


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def minus(a, b):
    return [a[0] - b[0], a[1] - b[1]]


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8)


def point_close(a, b):
    return isinstance(a, list) and len(a) == 2 and all(close(x, y) for x, y in zip(a, b))


def bc(box):
    return [(box[0] + box[2]) / 2, box[3]]


def strict_inside(point, polygon):
    """Independent scalar point-in-polygon check; a boundary is neutral."""
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        delta = minus(b, a)
        relative = minus(point, a)
        if close(cross(delta, relative), 0) and min(a[0], b[0]) <= x <= max(a[0], b[0]) and min(a[1], b[1]) <= y <= max(a[1], b[1]):
            return False
        if (a[1] > y) != (b[1] > y):
            intersect_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if intersect_x > x:
                inside = not inside
    return inside


def notebook_checks(path, check, relative, require_blank):
    nb = read(path)
    check('notebook_format:' + relative, nb.get('nbformat') == 4 and isinstance(nb.get('cells'), list))
    try:
        import nbformat
    except ImportError:
        check('notebook_schema_validator_available:' + relative, False,
              'Run with the prepared traffic-inspection or Phase7 audit interpreter.')
    else:
        nbformat.validate(nbformat.from_dict(nb))
        check('notebook_schema:' + relative, True)
    if require_blank:
        check('source_notebook_blank:' + relative,
              all(not c.get('outputs') and c.get('execution_count') is None
                  for c in nb['cells'] if c.get('cell_type') == 'code'))
    for index, cell in enumerate(nb['cells']):
        check('notebook_no_error_output:' + relative + ':' + str(index),
              not any(o.get('output_type') == 'error' for o in cell.get('outputs', [])))
        if cell.get('cell_type') == 'code':
            source = ''.join(cell.get('source', [])) if isinstance(cell.get('source'), list) else cell.get('source', '')
            # Notebook package-install magics are valid IPython, not Python AST.
            source = '\n'.join(line for line in source.splitlines()
                               if not line.lstrip().startswith(('%', '!')))
            if source.strip():
                ast.parse(source)
                check('notebook_code_parse:' + relative + ':' + str(index), True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--capture', action='store_true', help='Capture only after root declares final documentation/artifact freeze.')
    parser.add_argument('--preflight', action='store_true', help='Read-only dry check; writes neither final manifest nor final validation.')
    args = parser.parse_args()
    if args.capture and args.preflight:
        parser.error('--capture and --preflight are mutually exclusive')
    repo = args.repo.resolve()
    run = repo / RUN_REL
    screen = repo / SCREEN_REL
    manifest_path, validation_path = repo / MANIFEST_REL, repo / VALIDATION_REL
    checks = []

    def check(name, success, detail=None):
        row = {'check': name, 'passed': bool(success)}
        if detail is not None:
            row['detail'] = detail
        checks.append(row)

    def check_manifest_document(document, base, prefix, expected_count=None):
        artifacts = document['artifacts']
        if expected_count is not None:
            check(prefix + ':declared_artifact_count', len(artifacts) == expected_count)
        for item in artifacts:
            target = base / item['path']
            check(prefix + ':exists:' + item['path'], target.is_file())
            if target.is_file():
                check(prefix + ':hash_and_size:' + item['path'],
                      sha(target) == item['sha256'] and target.stat().st_size == item.get('size_bytes', item.get('bytes')))
        return document

    def check_manifest(path, base, prefix, expected_count=None):
        return check_manifest_document(read(path), base, prefix, expected_count)

    scope = scoped_paths(repo)
    if args.capture or args.preflight:
        check('all_scope_files_exist_before_capture', all(p.is_file() for p in scope))
        manifest = {
            'claim_type': 'FINAL_PHASE7_RETENTION_NOT_MODEL_PERFORMANCE_OR_GROUND_TRUTH',
            'captured_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'Phase7 source, documentation, retained execution, review and verification; historical A/B immutable evidence checked separately',
            'excluded_recursive_outputs': [MANIFEST_REL, VALIDATION_REL],
            'excluded_caches': ['__pycache__', '*.pyc'],
            'source_video_included': False, 'model_weights_included': False,
            'original_A_artifact_count': 103, 'original_B_artifact_count': 172,
            'artifacts': [{'path': str(p.relative_to(repo)), 'sha256': sha(p), 'size_bytes': p.stat().st_size}
                          for p in scope if p.is_file()],
        }
        manifest['artifact_count'] = len(manifest['artifacts'])
        manifest['total_bytes'] = sum(a['size_bytes'] for a in manifest['artifacts'])
        if args.capture:
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    else:
        manifest = read(manifest_path)
    check('manifest_scope_current_file_set', {a['path'] for a in manifest['artifacts']} == {str(p.relative_to(repo)) for p in scope})
    check_manifest_document(manifest, repo, 'final_retention', manifest['artifact_count'])
    check('manifest_total_bytes', manifest['total_bytes'] == sum(a['size_bytes'] for a in manifest['artifacts']))
    check('no_source_video_in_scope', not any(p.suffix.lower() in VIDEO_SUFFIXES for p in scope))
    check('no_model_weights_in_scope', not any(p.suffix.lower() in WEIGHT_SUFFIXES for p in scope))
    check('no_individual_artifact_over_100MB', all(p.stat().st_size < 100_000_000 for p in scope))
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=repo).decode().split('\0')
    check('no_source_video_or_model_weights_tracked', not any(Path(p).suffix.lower() in VIDEO_SUFFIXES | WEIGHT_SUFFIXES for p in tracked if p))
    for relative, expected in FROZEN_SOURCE.items():
        check('frozen_executable_source:' + relative, sha(repo / relative) == expected)

    original_a = repo / 'docs/evidence/phase_6/20261012T144625_030645Z/retention_manifest.json'
    check_manifest(original_a, repo, 'original_A_immutable', 103)
    mapping_path = repo / PHASE7 / 'baseline_retention/context_retention_mapping.json'
    mapping = read(mapping_path)
    archive_map = {a['original_path']: a for a in mapping['artifacts']}
    check('original_B_context_archive_count', len(archive_map) == 13)
    original_b = repo / mapping['original_manifest_path']
    check('original_B_manifest_itself_immutable', sha(original_b) == mapping['original_manifest_sha256'])
    old_b = read(original_b)
    check('original_B_artifact_count', len(old_b['artifacts']) == 172)
    for item in old_b['artifacts']:
        relative = item['path']
        if relative in archive_map:
            archive = archive_map[relative]
            target = repo / archive['retained_path']
            data = gzip.decompress(target.read_bytes())
            check('original_B_context_archive:' + relative,
                  sha(target) == archive['retained_sha256'] and digest(data) == item['sha256']
                  and len(data) == item['size_bytes'] and archive['logical_bytes_preserved'] is True)
        else:
            target = repo / relative
            check('original_B_immutable:' + relative,
                  target.is_file() and sha(target) == item['sha256'] and target.stat().st_size == item['size_bytes'])

    check_manifest(screen / 'manifest.json', screen, 'actual_screen_manifest')
    check_manifest(run / 'retention_manifest.json', run, 'actual_temporal_manifest', 85)
    for relative in ['independent_artifact_audit.json']:
        for label, base in [('screen', screen), ('temporal', run)]:
            audit = read(base / relative)
            check(label + ':retained_independent_audit_passed', audit['successful'] is True and not audit['failures'] and audit['checks_passed'] == audit['checks_run'])
            method = repo / audit['method_path']
            check(label + ':independent_audit_method_bound', sha(method) == audit['method_sha256'])
    submission_dir = repo / PHASE7 / 'kaggle_submission'
    screen_submission = read(submission_dir / 'screen_submission.json')
    temporal_submission = read(submission_dir / 'temporal_v1_submission.json')
    check('screen_submission_actually_complete', screen_submission['observed_status'] == 'KernelWorkerStatus.COMPLETE' and screen_submission['actual_run_id'] == screen.name)
    check('screen_submitted_source_original_bytes_bound', digest(gzip.decompress((submission_dir / 'screen_submitted.ipynb.gz').read_bytes())) == screen_submission['notebook_sha256'])
    check('screen_actual_execution_log_bound', sha(repo / screen_submission['execution_log_path']) == screen_submission['execution_log_sha256'])
    check('temporal_submission_actually_complete', temporal_submission['execution_status'] == 'COMPLETE' and temporal_submission['execution_run_id'] == run.name and temporal_submission['source_frame_count_per_variant'] == 9590)
    check('temporal_submitted_source_original_bytes_bound', digest(gzip.decompress((submission_dir / 'temporal_v1_submitted.ipynb.gz').read_bytes())) == temporal_submission['submitted_source_sha256'])
    check('temporal_actual_report_bound', sha(repo / temporal_submission['retained_report_path']) == temporal_submission['retained_report_sha256'])
    log_path = repo / temporal_submission['execution_log_path']
    check('temporal_actual_execution_log_both_hashes_bound', sha(log_path) == temporal_submission['execution_log_compressed_sha256'] and digest(gzip.decompress(log_path.read_bytes())) == temporal_submission['execution_log_uncompressed_sha256'])
    actual_report = read(run / 'report.json')
    config = actual_report['configuration']
    for label in ('geometry', 'sampling', 'selection'):
        check('actual_temporal_bound_input:' + label, sha(repo / config[label + '_path']) == config['expected_' + label + '_sha256'])
    check('actual_temporal_native_video_identity', config['expected_video_sha256'] == VIDEO_SHA and config['expected_frame_count'] == 9590)
    check('holdout_not_used_for_candidate_selection', actual_report['holdout_selection_used'] is False and actual_report['selection_frozen_before_temporal_execution'] is True)
    for relative in ['verification/pre_execution_synthetic_tests.json', 'verification/pre_execution_temporal_synthetic_tests.json']:
        test = read(repo / PHASE7 / relative)
        check('actual_pre_execution_tests:' + relative, test['successful'] is True and test['tests_run'] == test['tests_passed'] and not test['failures'] and not test['errors'])
    for path in scope:
        relative = str(path.relative_to(repo))
        if path.suffix == '.py':
            ast.parse(path.read_text())
            check('python_parse:' + relative, True)
        elif path.suffix == '.ipynb':
            notebook_checks(path, check, relative, True)
        elif path.suffix == '.json':
            value = read(path)
            check('strict_json_parse:' + relative, True)
            check('no_unexecuted_final_retention_placeholder:' + relative,
                  not contains_pending_placeholder(value))
        elif path.name.endswith('.json.gz'):
            value = read(path)
            check('strict_gzip_json_parse:' + relative, True)
            check('no_unexecuted_final_retention_placeholder:' + relative,
                  not contains_pending_placeholder(value))
        elif path.name.endswith('.ipynb.gz'):
            notebook_checks(path, check, relative, False)
        if path.suffix == '.md':
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                target = target.strip().strip('<>')
                parsed = urlsplit(target)
                if parsed.scheme or target.startswith('#'):
                    continue
                local = unquote(parsed.path)
                if local:
                    check('relative_markdown_link:' + relative + ':' + local, (path.parent / local).exists())
    final_review = (repo / 'docs/PHASE_7_REVIEW.md').read_text()
    final_review_links = re.findall(r'\]\(([^)]+)\)', final_review)
    check('final_review_links_to_canonical_executed_validation',
          'evidence/phase_7/final_artifact_validation.json' in final_review_links
          and 'evidence/phase_7/verification/final_artifact_validation.json' not in final_review_links)
    check('no_noncanonical_final_validation_placeholder_file',
          not (repo / PHASE7 / 'verification/final_artifact_validation.json').exists())
    check('final_review_has_no_current_running_status', not re.search(r'job sedang berjalan|temporal sedang berjalan|status\s*[:=]\s*[`\"\']?running', final_review, re.I))

    # These native records are read, never replayed through tracking/counting.
    native = read(repo / PHASE7 / 'accepted_geometry/TOR3-MALAM-N1.json')['rendered_native_pixels']
    line_a, line_b = native['line']['P1'], native['line']['P2']
    line_delta = minus(line_b, line_a)
    reviewed_stats = {}
    for variant in ('raw', 'gamma_070'):
        machine_dir, reviewed_dir = run / variant, run / (variant + '_reviewed')
        machine_decisions = read(machine_dir / 'machine_passage_decisions.json.gz')
        machine_events = read(machine_dir / 'machine_count_events.json.gz')
        decisions = read(reviewed_dir / 'resolved_decisions.json.gz')
        events = read(reviewed_dir / 'accepted_events.json.gz')
        aggregate = read(reviewed_dir / 'aggregate.json')
        overlay_report = read(reviewed_dir / 'report.json')
        review_input = read(reviewed_dir / 'review_input.json')
        source_episodes = {e['episode_id']: e for e in read(machine_dir / 'episodes.json.gz')}
        machine_index = {d['candidate_id']: d for d in machine_decisions}
        event_index = {e['event_id']: e for e in events}
        check_manifest(reviewed_dir / 'execution_manifest.json', reviewed_dir, variant + ':reviewed_manifest')
        check(variant + ':no_model_geometry_resolver_rerun', overlay_report['model_geometry_resolver_rerun'] is False and overlay_report['original_machine_artifacts_modified'] is False)
        check(variant + ':review_not_ground_truth_or_automatic_gain', overlay_report['formal_ground_truth'] is False and overlay_report['manual_review_is_formal_ground_truth'] is False and overlay_report['automatic_improvement_established'] is False and overlay_report['new_automatic_success_claimed'] is False and overlay_report['whole_video_traffic_result'] is False)
        check(variant + ':source_decisions_bound', review_input['source_machine_decisions_sha256'] == sha(machine_dir / 'machine_passage_decisions.json.gz'))
        check(variant + ':automatic_event_payload_immutable', all(event_index.get(e['event_id']) == e for e in machine_events))
        check(variant + ':accepted_event_ids_unique', len(event_index) == len(events))
        check(variant + ':physical_passage_deduplicated', len({(e['physical_unit_id'], e['passage_id']) for e in events}) == len(events))
        check(variant + ':candidate_status_partition', len(decisions) == len(machine_decisions) == 8 and Counter(d['status'] for d in decisions) == Counter({'accepted': 7, 'pending_review': 1}))
        check(variant + ':pending_category_conflict_not_promoted', all(not d.get('accepted_count_event') and d.get('event_id') is None and 'CATEGORY_CONFLICT' in d['hard_block_reasons'] for d in decisions if d['status'] == 'pending_review'))
        check(variant + ':accepted_decisions_match_events', {d['event_id'] for d in decisions if d['accepted_count_event']} == set(event_index))
        check(variant + ':aggregate_total_and_ids', aggregate['total'] == len(events) == overlay_report['accepted_events'] and set(aggregate['event_ids']) == set(event_index))
        check(variant + ':category_aggregate', aggregate['by_category'] == {k: sum(e['category'] == k for e in events) for k in aggregate['by_category']})
        check(variant + ':direction_aggregate', aggregate['by_direction'] == {k: sum(e['direction'] == k for e in events) for k in aggregate['by_direction']})
        check(variant + ':aggregate_excludes_pending', aggregate['scope'] == 'reviewed_accepted_passage_subtotal_not_complete_traffic')
        guard = read(reviewed_dir / 'synthetic_tests.json')
        check(variant + ':executed_overlay_software_guards', guard['passed'] == 32 and guard['failed'] == 0 and guard['model_geometry_resolver_rerun'] is False)
        adapter = read(reviewed_dir / 'review_adapter_provenance.json')
        base = repo / adapter['base_path']
        adapted = reviewed_dir / 'review_adapter.executed_source.py'
        base_text = base.read_text()
        check(variant + ':review_adapter_literal_only', sha(base) == adapter['base_source_sha256'] and sha(adapted) == adapter['adapted_source_sha256'] and base_text.count(adapter['old_guard']) == 1 and base_text.replace(adapter['old_guard'], adapter['new_guard']) == adapted.read_text() and adapter['production_substitution_count'] == 1 and adapter['algorithm_category_geometry_identity_controls_changed'] is False)
        needed = {(m['frame_index'], m['track_id'], m['original_detection_index'])
                  for e in events for m in e['measurement_support']}
        emitted = {}
        with gzip.open(machine_dir / 'track_records.jsonl.gz', 'rt') as stream:
            for line in stream:
                record = json.loads(line, parse_constant=reject_nonfinite)
                for observation in record['emitted_tracks']:
                    key = (record['frame_index'], observation['track_id'], observation['original_detection_index'])
                    if key in needed:
                        emitted[key] = observation
        check(variant + ':all_event_measurements_have_retained_emitted_sources', set(emitted) == needed)
        for event in events:
            label = variant + ':event:' + event['event_id']
            source = machine_index[event['candidate_id']]
            diagnostic = event['geometry_evidence']
            check(label + ':typed_CountEvent', event['type'] == 'CountEvent' and event['status'] == 'accepted' and event['accepted_count_event'] is True and isinstance(event['track_id'], int) and event['category'] in CATEGORIES and event['direction'] in {'A_TO_B', 'B_TO_A'} and bool(event['physical_unit_id']) and bool(event['passage_id']))
            check(label + ':geometry_payload_not_repaired', diagnostic == source['diagnostic'] and event['measurement_support'] == source['measurement_support'] and diagnostic['accepted_count_event'] is False)
            check(label + ':native_source_identity', event['source_identity']['variant'] == variant and event['source_identity']['video_sha256'] == VIDEO_SHA and event['source_identity']['records_sha256'] == sha(machine_dir / 'track_records.jsonl.gz') and event['source_identity']['width'] == 1280 and event['source_identity']['height'] == 720)
            vehicle_episode = source_episodes[event['vehicle_measurement_episode_id']]
            check(label + ':source_vehicle_episode_not_person', vehicle_episode['family'] == 'vehicle' and vehicle_episode['track_id'] == event['track_id'] and all(m['class_name'] in VEHICLES for m in vehicle_episode['observations']))
            check(label + ':rider_component_not_crossing_source', event['vehicle_measurement_episode_id'] in event['vehicle_episode_ids'] and all(source_episodes[eid]['family'] == 'vehicle' for eid in event['vehicle_episode_ids']) and all(source_episodes[eid]['family'] == 'person' for eid in event['component_episode_ids']) and event['vehicle_measurement_episode_id'] not in event['component_episode_ids'])
            category_labels = {'bus_angkot': {'bus'}, 'motorcycle': {'motorcycle'}, 'car': {'car'}, 'truck': {'truck'}, 'pedestrian': {'person'}}
            check(label + ':frozen_temporal_category_unanimity', {m['class_name'] for m in vehicle_episode['observations']} == category_labels[event['category']])
            support = event['measurement_support']
            check(label + ':continuous_measured_support', [m['frame_index'] for m in support] == list(range(diagnostic['origin_frame'], diagnostic['confirmation_frame'] + 1)) and all(m['track_id'] == event['track_id'] and m['class_name'] in VEHICLES for m in support))
            for measurement in support:
                key = (measurement['frame_index'], measurement['track_id'], measurement['original_detection_index'])
                actual = emitted.get(key)
                check(label + ':raw_detector_link:' + str(measurement['frame_index']), actual is not None and all(measurement[k] == actual[k] for k in ('raw_bbox', 'class_id', 'class_name', 'confidence', 'measurement_provenance', 'emitted', 'is_activated')) and measurement['measurement_provenance'] == PROVENANCE and measurement['emitted'] is True)
                check(label + ':raw_BC:' + str(measurement['frame_index']), point_close(measurement['point'], bc(measurement['raw_bbox'])))
            observations = [diagnostic['origin_observation'], diagnostic['crossing_evidence']['start_observation'], diagnostic['crossing_evidence']['end_observation'], *diagnostic['confirmation_observations']]
            for observation in observations:
                check(label + ':geometry_observation_raw_BC:' + str(observation['frame_index']), observation['metadata']['measurement_provenance'] == PROVENANCE and observation['metadata']['track_id'] == event['track_id'] and point_close(observation['point'], bc(observation['metadata']['raw_bbox'])))
            start, end = diagnostic['crossing_evidence']['start_observation'], diagnostic['crossing_evidence']['end_observation']
            movement = minus(end['point'], start['point'])
            denominator = cross(movement, line_delta)
            proper = denominator != 0
            if proper:
                t = cross(minus(line_a, start['point']), line_delta) / denominator
                u = cross(minus(line_a, start['point']), movement) / denominator
                intersection = diagnostic['crossing_evidence']['intersection']
                proper = 0 < t < 1 and 0 < u < 1 and close(t, intersection['t']) and close(u, intersection['u']) and point_close(intersection['point'], [start['point'][0] + t * movement[0], start['point'][1] + t * movement[1]])
            check(label + ':proper_finite_segment_without_gap_endpoint_touch', proper and end['frame_index'] == start['frame_index'] + 1 and diagnostic['crossing_evidence']['method'] == 'consecutive_measured_segment' and diagnostic['crossing_evidence']['intersection']['kind'] == 'proper')
            check(label + ':confirmed_origin_destination_ROIs', strict_inside(diagnostic['origin_point'], native['side_a_polygon'] if diagnostic['origin_side'] == 'A' else native['side_b_polygon']) and strict_inside(diagnostic['confirmation_point'], native['side_a_polygon'] if diagnostic['destination_side'] == 'A' else native['side_b_polygon']) and event['direction'] == diagnostic['origin_side'] + '_TO_' + diagnostic['destination_side'])
            if event.get('manual_review_applied'):
                check(label + ':manual_acceptance_marked', event['automatic_acceptance'] is False and event['claim_type'] == 'EXPLICIT_REVIEWED_PASSAGE_OVERLAY_NOT_AUTOMATIC_B_SUCCESS_OR_GROUND_TRUTH' and bool(event['review_references']))
                for reference in event['review_references']:
                    review = reference['review']
                    check(label + ':explicit_positive_review', review['disposition'] == 'CONFIRM_PASSAGE' and all(review[k] is True for k in ('unit_confirmed', 'category_confirmed', 'identity_confirmed')) and review['category'] == event['category'] and review['physical_unit_id'] == event['physical_unit_id'] and review['passage_id'] == event['passage_id'])
                    for evidence in review['evidence']:
                        path = repo / evidence['path']
                        check(label + ':review_image_hash:' + evidence['path'], path.is_file() and sha(path) == evidence['sha256'])
            else:
                check(label + ':retained_machine_event_not_reclassified', any(event == original for original in machine_events))
        reviewed_stats[variant] = {'accepted': len(events), 'pending': sum(d['status'] == 'pending_review' for d in decisions), 'manual_accepted': sum(bool(e.get('manual_review_applied')) for e in events), 'machine_events_preserved': len(machine_events)}

    result = {
        'claim_type': 'ACTUALLY_EXECUTED_FINAL_RETENTION_AND_TYPED_SOURCE_CHECKS_NOT_ACCURACY',
        'audited_utc': datetime.now(timezone.utc).isoformat(),
        'method_path': str(Path(__file__).resolve().relative_to(repo)),
        'method_sha256': sha(Path(__file__)),
        'manifest_path': None if args.preflight else MANIFEST_REL,
        'manifest_sha256': None if args.preflight else sha(manifest_path),
        'read_only_preflight': args.preflight,
        'artifact_count': len(manifest['artifacts']), 'total_bytes': manifest['total_bytes'],
        'checks_run': len(checks), 'checks_passed': sum(c['passed'] for c in checks),
        'successful': all(c['passed'] for c in checks),
        'model_tracker_encoder_geometry_resolver_rerun': False,
        'source_video_decode_rerun': False,
        'reviewed_variant_statistics': reviewed_stats,
        'limits': ['Hash integrity and software/source linkage do not establish physical-object accuracy.',
                   'Actual pixel review is retained separately and is not formal ground truth.',
                   'Unretained embedding vectors/cost matrices cannot be independently recomputed here.',
                   'Counting scope is five declared windows, not the full-video traffic population.',
                   'Manifest and this validation are excluded from recursive artifact hashing; validation binds manifest SHA.'],
        'failures': [c for c in checks if not c['passed']], 'checks': checks,
    }
    if not args.preflight:
        validation_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'checks', 'failures', 'limits'}}, indent=2))
    if result['failures']:
        print(json.dumps({'failures': result['failures']}, indent=2))
    return 0 if result['successful'] else 1


if __name__ == '__main__':
    sys.exit(main())
