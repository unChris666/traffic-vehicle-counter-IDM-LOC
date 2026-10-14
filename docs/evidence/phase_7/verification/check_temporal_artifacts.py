"""Independent retained Phase 7 full-history temporal artifact audit.

Never loads/runs YOLO, BoT-SORT, an encoder, resolver, or geometry state machine.
Reconstructs episode partitions and association arithmetic from original linked
measurements; reads actual CUDA kernel profiles and saved frame pixel hashes.
Optional complete source decode verifies donor pixels without model execution.
"""
from __future__ import annotations
import argparse
import ast
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

VEHICLES = {'motorcycle', 'car', 'truck', 'bus'}
KEYS = ('track_id', 'frame_index', 'original_detection_index', 'raw_bbox', 'class_id', 'class_name', 'confidence', 'measurement_provenance')
PROVENANCE = 'retained_phase_7_detection'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    def bad(value): raise ValueError('Nonfinite JSON constant: ' + value)
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as stream:
        return json.load(stream, parse_constant=bad)


def rows(path):
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def hashed_id(prefix, value):
    return prefix + digest(canonical(value).encode())


def family(label):
    return 'vehicle' if label in VEHICLES else 'person' if label == 'person' else 'other'


def bc(box):
    return [(box[0] + box[2]) / 2, box[3]]


def finite_box(box, native=False):
    return isinstance(box, list) and len(box) == 4 and all(type(x) in (int, float) and math.isfinite(x) for x in box) and box[0] < box[2] and box[1] < box[3] and (not native or 0 <= box[0] < box[2] <= 1280 and 0 <= box[1] < box[3] <= 720)


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-11)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--video', type=Path, default=Path('/tmp/traffic-phase7-source/TOR3-MALAM.mp4'))
    parser.add_argument('--pixel-decode', choices=('all', 'samples', 'none'), default='all')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--prior-context-map', type=Path)
    parser.add_argument('--submission', type=Path, default=Path('docs/evidence/phase_7/kaggle_submission/temporal_v1_submission.json'))
    args = parser.parse_args()
    repo = args.repo.resolve()
    run = args.run.resolve() if args.run.is_absolute() else repo / args.run
    output = args.output or run / 'independent_artifact_audit.json'
    totals, passed, failures = Counter(), Counter(), []
    diagnostics = {'model_or_tracker_encoder_resolver_rerun': False, 'audited_run_input_path': str(run)}

    def check(name, condition, detail=None):
        totals[name] += 1
        if condition:
            passed[name] += 1
        elif sum(f['check'] == name for f in failures) < 20:
            item = {'check': name, 'passed': False}
            if detail is not None: item['detail'] = detail
            failures.append(item)
        return bool(condition)

    # Reuse ONLY independent old audit mathematics, never processing algorithms.
    old_math_path = repo / 'docs/evidence/phase_6/verification/check_option_b_artifacts.py'
    spec = importlib.util.spec_from_file_location('phase7_independent_previous_audit_math', old_math_path)
    independent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(independent)
    report = read(run / 'report.json')
    config = read(run / 'configuration.json')
    source_config = read(repo / 'docs/evidence/phase_7/config/TOR3-MALAM_temporal_v1.json')
    submission_path = args.submission if args.submission.is_absolute() else repo / args.submission
    submission = read(submission_path)
    notebook_archive = submission_path.with_name('temporal_v1_submitted.ipynb.gz')
    notebook_bytes = gzip.decompress(notebook_archive.read_bytes())
    submitted_notebook = json.loads(notebook_bytes)
    check('submitted notebook exact SHA, not fabricated executed notebook',
          digest(notebook_bytes) == submission['submitted_source_sha256'] and
          submission['claim_type'] == 'KAGGLE_SUBMISSION_NOT_EXECUTION_RESULT' and
          all(c.get('execution_count') is None and not c.get('outputs')
              for c in submitted_notebook['cells'] if c['cell_type'] == 'code'))
    bundle_assignments = []
    for cell in submitted_notebook['cells']:
        if cell['cell_type'] != 'code': continue
        for node in ast.parse(''.join(cell['source'])).body:
            if (isinstance(node, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == 'SOURCE_BUNDLE' for t in node.targets)):
                bundle_assignments.append(node.value)
    check('exactly one declarative submitted source bundle', len(bundle_assignments) == 1)
    bundle_call = bundle_assignments[0]
    if not (isinstance(bundle_call, ast.Call) and isinstance(bundle_call.func, ast.Attribute)
            and isinstance(bundle_call.func.value, ast.Name)
            and bundle_call.func.value.id == 'json' and bundle_call.func.attr == 'loads'
            and len(bundle_call.args) == 1):
        raise ValueError('Submission source bundle is not a literal JSON declaration')
    submitted_bundle = json.loads(ast.literal_eval(bundle_call.args[0]))
    for path, artifact in submitted_bundle.items():
        data = gzip.decompress(base64.b64decode(artifact['gzip_base64'], validate=True))
        check('submitted source bundle original bytes/SHA',
              len(data) == artifact['bytes'] and digest(data) == artifact['sha256'], path)
        check('frozen submitted source/config matches current retained source',
              (repo / path).is_file() and (repo / path).read_bytes() == data, path)
    check('submitted temporal helper exact executed source binding',
          submitted_bundle['notebooks/phase_7_temporal_helpers.py']['sha256'] == report['source_helper_sha256'])
    helper_ast = ast.parse((repo / 'notebooks/phase_7_temporal_helpers.py').read_text())
    package_source_controls = ast.literal_eval(next(n.value for n in helper_ast.body if isinstance(n, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'EXPECTED_PACKAGE_SOURCES' for target in n.targets)))
    check('actual completed raw-selected temporal execution', report['phase'] == 7 and report['execution_kind'] == 'ACTUAL_MODEL_EXECUTION' and report['run_id'] == run.name and report['status'] == 'completed_raw_selected_temporal_machine_outputs_physical_review_pending')
    check('bound config only runtime repo root changes', {k: v for k, v in config.items() if k != 'repo_root'} == {k: v for k, v in source_config.items() if k != 'repo_root'} and report['configuration'] == config)
    for path_key, hash_key in (('sampling_path', 'expected_sampling_sha256'), ('geometry_path', 'expected_geometry_sha256'), ('selection_path', 'expected_selection_sha256')):
        check('frozen input SHA:' + path_key, sha(repo / config[path_key]) == config[hash_key])
    plan = read(repo / config['sampling_path'])
    geometry = read(repo / config['geometry_path'])
    selection = read(repo / config['selection_path'])
    check('approved N1 source identity/counting gate', geometry['source_video']['sha256'] == config['expected_video_sha256'] and geometry['geometry_contract_accepted'] is True and geometry['counting_execution_allowed'] is True and geometry['status'] == 'ACCEPTED_PHASE7_INITIAL_GEOMETRY_BASELINE_NUMERIC_DEFAULTS_OPEN')
    feedback = geometry['approval_feedback']
    check('actual user feedback directions hash bound', sha(repo / feedback['path']) == feedback['sha256'] and read(repo / feedback['path'])['confirmed_decisions']['direction_metadata'] == {'A_TO_B': 'approaching camera', 'B_TO_A': 'moving away from camera', 'scope': 'TOR3-MALAM'})
    check('DEV-only candidate frozen before holdout', selection['status'] == 'FROZEN_DEV_SHORTLIST' and selection['selection_basis'] == 'DEVELOPMENT_ONLY' and selection['holdout_used'] is False and selection['selection_parameters_tuning_after_holdout_allowed'] is False and config['variants'] == [{'name': 'raw', 'method': 'raw'}, selection['selected_variant']] and report['selection_frozen_before_temporal_execution'] is True and report['holdout_selection_used'] is False)
    screen = repo / 'docs/evidence/phase_7/screening' / selection['source_detection_screen_run_id'] / 'report.json'
    check('selected candidate from retained actual DEV-only screen', sha(screen) == selection['source_detection_screen_report_sha256'] and read(screen)['execution_kind'] == 'ACTUAL_MODEL_EXECUTION' and read(screen)['holdout_enhancement_or_inference_executed'] is False)
    check('DEV visual review bound to shortlist', sha(repo / selection['source_visual_review_path']) == selection['source_visual_review_sha256'])
    check('actual GPU0 inference and CPU association environment', report['environment']['association_device'] == 'cpu' and report['environment']['detector_and_encoder_device'] == 'cuda:0')
    check('full video frame0 continuous independent variants', config['expected_frame_count'] == 9590 and config['frame_scope'] == 'FULL_VIDEO_FROM_FRAME_ZERO_NO_TRACKER_RESET_WITHIN_VARIANT' and config['counting_scope'] == 'DECLARED_DEV_AND_HOLDOUT_SAMPLING_WINDOWS_DYNAMIC_OBSERVED_IDS_FULL_HISTORY')
    calibration = read(repo / config['counting']['calibration_path'])
    check('PAGI counting controls never tuned for night', sha(repo / config['counting']['source_path']) == config['counting']['source_sha256'] == '18949e7a44b6d73b9d50269f9d4569fbda781ba48269046b982287376ec3f054' and sha(repo / config['counting']['calibration_path']) == config['counting']['calibration_sha256'] and calibration['thresholds'] == config['counting']['association'] and config['counting']['neutral_band_px'] == 0.0 and config['counting']['confirmation_observations'] == 1)
    check('unchanged Phase5 geometry source', sha(repo / 'notebooks/phase_5_geometry_helpers.py') == config['counting']['geometry_source_sha256'])
    check('frozen temporal executed helper source', report['source_helper_sha256'] == sha(repo / 'notebooks/phase_7_temporal_helpers.py'))
    guard = read(run / 'pre_execution_guard/synthetic_validation.json')
    check('actual pre-execution 41 software tests passed', guard['tests_run'] == guard['tests_passed'] == 41 and guard['successful'] is True and not guard['failures'] and not guard['errors'])
    for artifact in read(run / 'retention_manifest.json')['artifacts']:
        p = Path(artifact['path'])
        if p.is_absolute():
            p = p.relative_to(Path(config['output_root']) / run.name)
        p = run / p
        check('retained execution artifact SHA/bytes', p.is_file() and p.stat().st_size == artifact.get('bytes', artifact.get('size_bytes')) and sha(p) == artifact['sha256'], artifact['path'])
    native = geometry['rendered_native_pixels']
    # Actual geometry JSON uses uppercase endpoint names in the line object.
    line = native['line']
    p1, p2 = line['P1'], line['P2']
    windows = sorted([[s['start_frame'], s['end_frame']] for split in ('development', 'holdout') for s in plan[split]['segments']])
    samples = sorted(set(plan['development']['sample_frame_indices'] + plan['holdout']['sample_frame_indices']))
    frame_hashes = {}
    totals_by_variant = {}
    for variant in config['variants']:
        name = variant['name']; directory = run / name; stats = report['variants'][name]
        check(name + ': completed9590 continuous frames', stats['frames_processed'] == 9590 and stats['status'] == 'completed_full_video_inference_geometry_counting_review_pending' and stats['variant'] == variant)
        check(name + ': source cache byte hashes', sha(directory / 'track_records.jsonl.gz') == stats['track_records_sha256'] and sha(directory / 'appearance_records.jsonl.gz') == stats['appearance_records_sha256'])
        runtime = stats['encoder_runtime']
        check(name + ': actual CUDA512 external encoder not final vehicle choice', runtime['providers'][0] == 'CUDAExecutionProvider' and runtime['device'] == runtime['backend_device'] == 'cuda:0' and runtime['imgsz'] == [224, 224] and runtime['fp16'] is False and runtime['static_batch_size'] is None and runtime['no_runtime_fallback'] is True and runtime['encoder_asset_sha256'] == config['encoder']['sha256'] and runtime['encoder_input_policy'] == 'SAME_TRANSFORMED_FRAME_AS_DETECTOR' and runtime['final_vehicle_configuration'] is False)
        check(name + ': exact upstream tracker/encoder source controls', {x['path']: x['sha256'] for x in runtime['tracker_source_checks']} == package_source_controls)
        effective = dict(config['tracker'], model=config['encoder']['path'])
        check(name + ': effective frozen tracker controls', runtime['effective_configuration'] == effective)
        detector = stats['detector_resources']
        check(name + ': actual detector CUDA0/weights/settings/class mapping', report['execution_kind'] == 'ACTUAL_MODEL_EXECUTION' and detector['execution_device'] == 'cuda:0' and detector['weights_sha256'] == config['detector']['weights_sha256'] and detector['weights_bytes'] == config['detector']['weights_bytes'] and detector['package_version'] == '8.4.175' and detector['actual_predictor_arguments'] == config['detector']['settings'] and detector['actual_backend']['device'] == 'cuda:0' and detector['actual_backend']['fp16'] is False and detector['visible_cuda_device_count'] == 2)
        check(name + ': detector class mapping same source screen', detector['class_names'] == read(screen)['resource']['class_names'])
        proof = read(directory / 'encoder_provider_evidence.json')
        profile_path = directory / proof['profile']
        profile = read(profile_path)
        kernel_counts = Counter(e.get('args', {}).get('provider') for e in profile if isinstance(e, dict) and e.get('cat') == 'Node' and e.get('args', {}).get('provider'))
        check(name + ': real CUDA provider kernel execution profile', sha(profile_path) == proof['profile_sha256'] and dict(kernel_counts) == proof['provider_kernel_event_counts'] and kernel_counts['CUDAExecutionProvider'] > 0 and proof['actual_cuda_execution_confirmed'] is True and proof['execution_kind'] == 'ACTUAL_MODEL_EXECUTION' and stats['cuda_execution_evidence'] == proof)
        frame_records, measurements, assigned_histories = {}, {}, defaultdict(list)
        counters, costs = Counter(), Counter()
        encoder_calls = feature_count = 0; encoder_seconds = 0.0; discovered = set()
        detection_rows = rows(directory / 'track_records.jsonl.gz')
        appearance_rows = rows(directory / 'appearance_records.jsonl.gz')
        for index, pair in enumerate(__import__('itertools').zip_longest(detection_rows, appearance_rows)):
            record, appearances = pair
            if not check(name + ': aligned full record/appearance rows', record is not None and appearances is not None and record['frame_index'] == appearances['frame_index'] == index): break
            frame_records[index] = record
            shape_identity = {'video_sha256': config['expected_video_sha256'], 'variant': name, 'parent_run_id': run.name, 'width': 1280, 'height': 720}
            check(name + ': frame phase/source/native context', record['phase'] == appearances['phase'] == 7 and record['measurement_provenance'] == PROVENANCE and all(record[k] == v for k, v in shape_identity.items()) and record['transform'] == variant and appearances['variant'] == name, index)
            pixel_sha = record['detector_input_frame_pixel_sha256']
            check(name + ': detector/encoder same donor pixels', pixel_sha == record['encoder_input_frame_pixel_sha256'] == appearances['donor_frame_pixel_sha256'] and isinstance(pixel_sha, str) and len(pixel_sha) == 64, index)
            frame_hashes.setdefault(name, {})[index] = pixel_sha
            fps = stats['decode_metadata']['fps_backend']
            check(name + ': explicit timestamp estimate, not verified PTS', close(record['timestamp_estimate_from_index_fps_seconds'], index / fps), index)
            raw, emitted, assigned = record['raw_detections'], record['emitted_tracks'], record['assigned_observations_including_unconfirmed']
            counters.update(raw_detections=len(raw), emitted_observations=len(emitted), empty_detection_frames=int(not raw), no_emitted_track_frames=int(not emitted))
            for det in raw:
                check(name + ': all raw detections native/conf/class', finite_box(det['bbox_xyxy_pixels'], True) and type(det['class_id']) is int and detector['class_names'].get(str(det['class_id'])) == det['class_name'] and config['detector']['settings']['conf'] <= det['confidence'] <= 1, index)
            emitted_ids, emitted_indices, assigned_ids = set(), set(), set()
            for item in assigned:
                track, raw_index = item['track_id'], item['original_detection_index']
                valid = type(track) is int and track > 0 and track not in assigned_ids and type(raw_index) is int and 0 <= raw_index < len(raw)
                check(name + ': assigned including unconfirmed direct source index', valid, [index, track, raw_index]); assigned_ids.add(track)
                if not valid: continue
                det = raw[raw_index]
                check(name + ': assigned raw source values/provenance', item['frame_index'] == index and item['raw_bbox'] == det['bbox_xyxy_pixels'] and all(item[k] == det[k] for k in ('class_id', 'class_name', 'confidence')) and item['measurement_provenance'] == PROVENANCE and finite_box(item['bbox']), [index, track])
                assigned_histories[track].append(item)
            for item in emitted:
                track, raw_index = item['track_id'], item['original_detection_index']
                valid = track not in emitted_ids and raw_index not in emitted_indices and track in assigned_ids and 0 <= raw_index < len(raw)
                check(name + ': emitted unique/current measurement link', valid, [index, track, raw_index]); emitted_ids.add(track); emitted_indices.add(raw_index)
                if not valid: continue
                det = raw[raw_index]
                check(name + ': emitted exact raw detection and BC center metadata', item['frame_index'] == index and item['raw_bbox'] == det['bbox_xyxy_pixels'] and all(item[k] == det[k] for k in ('class_id', 'class_name', 'confidence')) and item['measurement_provenance'] == PROVENANCE and item['emitted'] is True and item['is_activated'] is True and item['center'] == [(item['raw_bbox'][0] + item['raw_bbox'][2]) / 2, (item['raw_bbox'][1] + item['raw_bbox'][3]) / 2], [index, track])
                measurements[track, index] = item
                if any(a <= index <= b for a, b in windows): discovered.add(track)
            for snap in record['lifecycle_snapshots']:
                check(name + ': lifecycle predictions explicitly marked', snap['observed_this_frame'] is (snap['track_id'] in assigned_ids) and snap['emitted'] is (snap['track_id'] in emitted_ids) and snap['bbox_provenance'] == ('filtered_current_detection' if snap['observed_this_frame'] else 'tracker_estimate_not_current_detection'), [index, snap['track_id']])
            for call in appearances['encoder_calls']:
                encoder_calls += 1; feature_count += call['feature_count']; encoder_seconds += call['encoder_wall_seconds']
                check(name + ': actual finite nonzero512features/donor hashes', call['feature_dimension'] == 512 and call['feature_count'] == len(call['feature_l2_norms']) == len(call['feature_sha256']) and all(math.isfinite(x) and x > 1e-12 for x in call['feature_l2_norms']) and all(len(x) == 64 for x in call['feature_sha256']) and call['donor_frame_pixel_sha256'] == pixel_sha and call['encoder_wall_seconds'] >= 0, index)
            for call in appearances['association_calls']:
                shape = call['matrix_shape']; count = shape[0] * shape[1]
                check(name + ': retained parent cost observer exact/shape/control', call['frame_index'] == index and call['parent_formula_exact_match'] is True and call['candidate_pairs'] == count and len(call['track_ids']) == shape[0] and len(call['detection_indices']) == shape[1] and 0 <= call['appearance_changed_cost_pairs'] <= count and 0 <= call['appearance_eligible_pairs'] <= count and call['features_present_in_nonempty_association'] is bool(shape[0] and shape[1]), index)
                costs.update(calls=1, candidate_pairs=count, nonempty_feature_association_calls=int(call['features_present_in_nonempty_association']), appearance_eligible_pairs=call['appearance_eligible_pairs'], appearance_changed_cost_pairs=call['appearance_changed_cost_pairs'])
        check(name + ': exactly9590 raw/appearance records incl emptyframes', len(frame_records) == config['expected_frame_count'] and set(frame_records) == set(range(9590)))
        appearance_diag = stats['appearance_diagnostics']
        check(name + ': appearance/cost counter reconciliation', all(appearance_diag[k] == v for k, v in costs.items()) and appearance_diag['encoder_calls'] == encoder_calls and appearance_diag['finite_nonzero_features_produced'] == feature_count and appearance_diag['embedding_dimension'] == 512 and encoder_calls > 0 and feature_count > 0 and costs['nonempty_feature_association_calls'] > 0)
        check(name + ': measured timing/resource semantics', all(math.isfinite(x) and x >= 0 for x in stats['timing'].values()) and close(encoder_seconds, stats['timing']['encoder_wall_seconds_inside_tracker']) and stats['resource']['cuda_peak_reserved_bytes'] >= stats['resource']['cuda_peak_allocated_bytes'] > 0 and stats['resource']['process_peak_rss_bytes'] > 0)
        summary = read(directory / 'track_summary.json')['tracks']
        gaps = changes = 0
        for track in summary:
            history = assigned_histories.get(track['track_id'], [])
            if not check(name + ': lifecycle summary track observed', bool(history), track['track_id']): continue
            expected_gaps = [{'previous_frame': a['frame_index'], 'next_frame': b['frame_index'], 'missing_frames': b['frame_index'] - a['frame_index'] - 1} for a, b in zip(history, history[1:]) if b['frame_index'] > a['frame_index'] + 1]
            expected_changes = [{'frame_index': b['frame_index'], 'old_class_id': a['class_id'], 'new_class_id': b['class_id']} for a, b in zip(history, history[1:]) if a['class_id'] != b['class_id']]
            gaps += len(expected_gaps); changes += len(expected_changes)
            check(name + ': lifecycle summary reconstructed from raw assigned history', track['first_observed_frame'] == history[0]['frame_index'] and track['last_observed_frame'] == history[-1]['frame_index'] and track['observed_count'] == len(history) and track['emitted_count'] == sum(x['emitted'] for x in history) and track['class_histogram'] == dict(Counter(x['class_name'] for x in history)) and track['gap_events'] == expected_gaps and track['class_changes'] == expected_changes, track['track_id'])
        expected_obs = dict(counters, captured_ids_including_unconfirmed=len(assigned_histories), within_id_gap_events=gaps, within_id_raw_class_changes=changes)
        check(name + ': observed diagnostic counters exact not physical counts', stats['observed_diagnostics'] == expected_obs and {t['track_id'] for t in summary} == set(assigned_histories))
        adapter = (directory / 'counting_adapter.executed_source.py').read_bytes()
        base = (repo / config['counting']['source_path']).read_bytes()
        expected_adapter = base.replace(b'"retained_phase_2_detection"', b'"retained_phase_7_detection"', 1)
        provenance = read(directory / 'counting_adapter_provenance.json')
        check(name + ': exact single provenance-only source adapter', base.count(b'"retained_phase_2_detection"') == 1 and adapter == expected_adapter and provenance['adapted_source_sha256'] == digest(adapter) and provenance['base_source_sha256'] == config['counting']['source_sha256'] and provenance['literal_substitution_count'] == 1 and provenance['behavior_changes'] == 'SOURCE_PROVENANCE_ENUM_ONLY_NO_ALGORITHM_OR_THRESHOLD_CHANGE')
        cc = read(directory / 'counting_configuration.json')
        identity = cc['input_identity']
        check(name + ': counting source identity exact full cache', identity == {'video_sha256': config['expected_video_sha256'], 'records_sha256': stats['track_records_sha256'], 'geometry_sha256': config['expected_geometry_sha256'], 'variant': name, 'width': 1280, 'height': 720, 'parent_run_id': run.name})
        check(name + ': five predeclared windows and dynamically observed IDs', cc['scope'] == {'association_frame_windows': windows, 'track_ids': sorted(discovered)} and len(windows) == 5)
        check(name + ': frozen counting semantic controls', all(cc[k] == config['counting'][k] for k in ('policy_version', 'metric', 'neutral_band_px', 'confirmation_observations', 'association', 'grouping_enabled')))
        episodes = read(directory / 'episodes.json.gz'); by_episode = {e['episode_id']: e for e in episodes}
        source_index = read(directory / 'source_index.json.gz')
        check(name + ': entire source cache retained before scope selection', source_index['input_identity'] == identity and source_index['source_frame_count'] == 9590 and source_index['source_measured_observation_count'] == len(measurements) and source_index['selected_track_ids'] == sorted(discovered))
        expected_partitions = []
        for track in sorted({t for t, _ in measurements}):
            history = sorted((o for (t, _), o in measurements.items() if t == track), key=lambda o: o['frame_index'])
            chunks, chunk, reasons, previous = [], [], [], None
            for observation in history:
                changed = previous is not None and family(observation['class_name']) != family(previous['class_name'])
                gap = previous is not None and observation['frame_index'] != previous['frame_index'] + 1
                if previous is None or changed or gap:
                    if chunk: chunks.append(chunk)
                    chunk = []; reasons.append('INITIAL_OBSERVATION' if previous is None else 'FAMILY_CHANGE_AND_GAP' if changed and gap else 'FAMILY_CHANGE' if changed else 'MEASUREMENT_GAP')
                chunk.append(observation); previous = observation
            if chunk: chunks.append(chunk)
            preceding = []
            for sequence, chunk in enumerate(chunks, 1):
                ep_id = hashed_id('ve6b_', {'source_identity': identity, 'track_id': track, 'first_frame': chunk[0]['frame_index'], 'last_frame': chunk[-1]['frame_index'], 'family': family(chunk[0]['class_name'])})
                expected_partitions.append(ep_id)
                if track in discovered:
                    episode = by_episode.get(ep_id)
                    check(name + ': selected all family-gap episode partitions/full origins', episode is not None and episode['track_id'] == track and episode['family'] == family(chunk[0]['class_name']) and episode['boundary_reason'] == reasons[sequence-1] and episode['episode_sequence'] == sequence and episode['start_frame'] == chunk[0]['frame_index'] and episode['end_frame'] == chunk[-1]['frame_index'] and len(episode['observations']) == len(chunk), ep_id)
                    if episode is not None:
                        for a, b in zip(episode['observations'], chunk):
                            check(name + ': episode raw observation BC source', all(a[k] == b[k] for k in KEYS) and a['point'] == bc(b['raw_bbox']), [track, b['frame_index']])
                        check(name + ': excluded preceding origins preserved', len(episode['excluded_preceding_observations']) == len(preceding) and all(all(a[k] == b[k] for k in KEYS) and a['point'] == bc(b['raw_bbox']) for a, b in zip(episode['excluded_preceding_observations'], preceding)), ep_id)
                preceding.extend(chunk)
        expected_source_links = [{'episode_id': e['episode_id'], 'track_id': e['track_id'], 'frame_index': o['frame_index'], 'original_detection_index': o['original_detection_index'], 'raw_bbox': o['raw_bbox'], 'class_name': o['class_name']} for e in episodes for o in e['observations']]
        check(name + ': selected source link inventory exact', source_index['selected_source_links'] == expected_source_links)
        check(name + ': source and selected episode counts exact', source_index['all_source_episode_count'] == len(expected_partitions) and source_index['selected_measured_observation_count'] == sum(len(e['observations']) for e in episodes) and len(episodes) == len(by_episode))
        relations = read(directory / 'relations.json.gz'); by_relation = {r['relation_id']: r for r in relations}
        for relation in relations:
            first, second = by_episode[relation['first_episode_id']], by_episode[relation['second_episode_id']]
            features = independent.feature_values(first, second, relation['type'], windows)
            controls = cc['association']['component' if relation['type'] == 'COMPONENT_OF' else 'same_vehicle']
            check(name + ': independent global relation feature arithmetic/control', independent.equal_value(features, relation['features']) and relation['thresholds'] == controls and relation['features']['appearance_features_used'] is False, relation['relation_id'])
            check(name + ': supported relation meets exact controls', relation['status'] != 'SUPPORTED' or independent.control_passes(features, controls, relation['type']), relation['relation_id'])
            check(name + ': relation component/duplicate type separation', (first['family'] == 'person' and second['family'] == 'vehicle' and {o['class_name'] for o in second['observations']} == {'motorcycle'}) if relation['type'] == 'COMPONENT_OF' else (first['family'] == second['family'] == 'vehicle' and first['track_id'] != second['track_id']), relation['relation_id'])
        derived = read(directory / 'geometry_diagnostics.json.gz')
        decisions = read(directory / 'machine_passage_decisions.json.gz')
        events = read(directory / 'machine_count_events.json.gz')
        aggregate = read(directory / 'machine_aggregate.json')
        counting_report = read(directory / 'counting_report.json')
        eligible_diagnostics = [d for d in derived
            if d['type'] in {'GEOMETRY_TRANSITION', 'AMBIGUOUS_GAP', 'AMBIGUOUS_ENDPOINT'}
            and all(any(lo <= frame <= hi for lo, hi in windows) for frame in
                    ([d['crossing_frame_start'], d['crossing_frame_end'], d['confirmation_frame']]
                     if d['type'] == 'GEOMETRY_TRANSITION' else [d['frame_index']]))]
        check(name + ': exact candidate inventory from every eligible scoped diagnostic',
              sorted(canonical(d) for d in eligible_diagnostics) ==
              sorted(canonical(c['diagnostic']) for c in decisions) and
              len({c['candidate_id'] for c in decisions}) == len(decisions))
        for diagnostic in derived:
            check(name + ': geometry diagnostics have no CountEvent authority',
                  diagnostic['accepted_count_event'] is False and
                  diagnostic['episode_id'] in by_episode and
                  by_episode[diagnostic['episode_id']]['family'] == 'vehicle' and
                  diagnostic['track_id'] == by_episode[diagnostic['episode_id']]['track_id'])
            if diagnostic['type'] == 'ORIGIN_ESTABLISHED':
                observation = measurements[diagnostic['track_id'], diagnostic['origin_frame']]
                check(name + ': all origins raw vehicle BC with interior ROI',
                      diagnostic['origin_point'] == bc(observation['raw_bbox']) and
                      all(diagnostic['metadata'][k] == observation[k] for k in
                          ('track_id', 'original_detection_index', 'raw_bbox', 'class_id', 'class_name', 'confidence', 'measurement_provenance')) and
                      independent.inside_polygon(diagnostic['origin_point'],
                          native['side_' + diagnostic['origin_side'].lower() + '_polygon']))
            elif diagnostic['type'] == 'AMBIGUOUS_GAP':
                previous, current = diagnostic['previous_observation'], diagnostic['current_observation']
                check(name + ': gap diagnostics exact measurements no interpolation',
                      diagnostic['interpolation_used'] is False and
                      current['frame_index'] > previous['frame_index'] + 1 and
                      all(all(o[k] == measurements[diagnostic['track_id'], o['frame_index']][k] for k in KEYS)
                          and o['point'] == bc(o['raw_bbox']) for o in (previous, current)))
        event_ids = {e['event_id'] for e in events}
        check(name + ': unique typed accepted machine events/aggregate', len(event_ids) == len(events) == aggregate['total'] and aggregate['event_ids'] == sorted(event_ids) and all(e['type'] == 'CountEvent' and e['accepted_count_event'] is True and e['status'] == 'accepted' for e in events) and len({(e['physical_unit_id'], e['passage_id']) for e in events}) == len(events))
        for key, field in (('by_category', 'category'), ('by_direction', 'direction')):
            expected = Counter(e[field] for e in events)
            check(name + ': aggregate reconciles ' + field, sum(aggregate[key].values()) == len(events) and all(v == expected.get(k, 0) for k, v in aggregate[key].items()))
        check(name + ': counting report derived statuses/evidence', counting_report['input_identity'] == identity and counting_report['accepted_events'] == len(events) and counting_report['decision_status_counts'] == dict(Counter(d['status'] for d in decisions)) and counting_report['relation_status_counts'] == dict(Counter(r['status'] for r in relations)) and counting_report['geometry_diagnostic_counts'] == dict(Counter(d['type'] for d in derived)) and counting_report['source_cache_created_by_phase7_new_inference'] is True and counting_report['physical_identity_or_counting_accuracy_established'] is False and counting_report['detector_tracker_encoder_rerun'] is False and counting_report['appearance_features_used'] is False and counting_report == stats['counting_report'])
        for candidate in decisions:
            ep = by_episode[candidate['episode_id']]; diagnostic = candidate['diagnostic']
            semantic = {k: cc[k] for k in ('policy_version', 'metric', 'neutral_band_px', 'confirmation_observations', 'association', 'grouping_enabled')}
            semantic['association_frame_windows'] = windows
            selector = {k: diagnostic[k] for k in ('track_id', 'episode_id', 'frame_index', 'type')}
            if diagnostic['type'] == 'GEOMETRY_TRANSITION':
                selector.update({k: diagnostic[k] for k in ('origin_frame', 'crossing_frame_start', 'crossing_frame_end', 'confirmation_frame', 'direction')})
            check(name + ': deterministic source-bound candidate ID',
                  candidate['selector'] == selector and candidate['candidate_id'] == hashed_id('pc6b_',
                      {'source_identity': identity, 'selector': selector,
                       'geometry_id': diagnostic['geometry_id'], 'policy': semantic}), candidate['candidate_id'])
            check(name + ': candidate uses vehicle episode not rider', ep['family'] == 'vehicle' and candidate['track_id'] == ep['track_id'] and candidate['episode_id'] in candidate['vehicle_episode_ids'], candidate['candidate_id'])
            if diagnostic['type'] != 'GEOMETRY_TRANSITION':
                check(name + ': ambiguous geometry never accepted', candidate['accepted_count_event'] is False and candidate['event_id'] is None and candidate['status'] == 'pending_review', candidate['candidate_id']); continue
            start, end = diagnostic['origin_frame'], diagnostic['confirmation_frame']
            check(name + ': crossing and confirmation within declared windows', all(any(a <= diagnostic[k] <= b for a, b in windows) for k in ('crossing_frame_start', 'crossing_frame_end', 'confirmation_frame')), candidate['candidate_id'])
            support = candidate['measurement_support']
            check(name + ': consecutive full measured vehicle passage', [o['frame_index'] for o in support] == list(range(start, end+1)) and all(o['track_id'] == candidate['track_id'] and o['class_name'] in VEHICLES and all(o[k] == measurements[o['track_id'], o['frame_index']][k] for k in KEYS) for o in support), candidate['candidate_id'])
            geo_obs = [diagnostic['origin_observation'], diagnostic['crossing_evidence']['start_observation'], diagnostic['crossing_evidence']['end_observation'], *diagnostic['confirmation_observations']]
            for g in geo_obs:
                observation = measurements[candidate['track_id'], g['frame_index']]
                check(name + ': geometry original measured vehicle BC metadata', g['point'] == bc(observation['raw_bbox']) and all(g['metadata'][k] == observation[k] for k in ('track_id', 'original_detection_index', 'raw_bbox', 'class_id', 'class_name', 'confidence', 'measurement_provenance')) and g['metadata']['video_sha256'] == config['expected_video_sha256'], [candidate['candidate_id'], g['frame_index']])
                line_vector = [p2[0]-p1[0], p2[1]-p1[1]]
                offset = [g['point'][0]-p1[0], g['point'][1]-p1[1]]
                distance = independent.cross(line_vector, offset) / math.hypot(*line_vector)
                zero = abs(distance) <= 1e-12 * max(1.0, *(abs(x) for p in (g['point'],p1,p2) for x in p))
                expected_sign = 0 if zero else (1 if distance > 0 else -1)
                check(name + ': independent signed distance and neutral-band sign',
                      close(distance, g['signed_distance_px']) and g['sign'] == expected_sign and
                      g['stable_side'] == (g['side'] if abs(distance) > cc['neutral_band_px'] and not zero else None),
                      [candidate['candidate_id'], g['frame_index']])
            direction = diagnostic['direction']; origin, destination = direction.split('_TO_')
            check(name + ': source/destination interior polygon agreement', independent.inside_polygon(geo_obs[0]['point'], native['side_' + origin.lower() + '_polygon']) and all(independent.inside_polygon(g['point'], native['side_' + destination.lower() + '_polygon']) for g in diagnostic['confirmation_observations']), candidate['candidate_id'])
            crossing = diagnostic['crossing_evidence']; first = crossing['start_observation']['point']; last = crossing['end_observation']['point']
            if crossing['method'] == 'consecutive_measured_segment':
                point = independent.proper_finite_intersection(first, last, p1, p2)
                check(name + ': proper finite measured line crossing',
                      crossing['end_observation']['frame_index'] == crossing['start_observation']['frame_index'] + 1 and
                      point is not None and independent.equal_value(point, crossing['intersection']['point']) and
                      independent.equal_value(point, diagnostic['crossing_point']) and
                      crossing['entry_sign'] == crossing['start_observation']['sign'] and
                      crossing['exit_sign'] == crossing['end_observation']['sign'] and
                      crossing['entry_sign'] * crossing['exit_sign'] == -1, candidate['candidate_id'])
            else:
                check(name + ': explicit measured touch crossing method', crossing['method'] == 'measured_touch_then_opposite_sign', candidate['candidate_id'])
            labels = {o['class_name'] for eid in candidate['vehicle_episode_ids'] for o in by_episode[eid]['observations']}
            expected_category = next(iter(labels)) if len(labels) == 1 and next(iter(labels)) in {'car', 'motorcycle', 'truck'} else None
            check(name + ': full vehicle-episode offline category excludes person', candidate['category'] == expected_category and candidate['vehicle_class_histogram'] == dict(Counter(o['class_name'] for eid in candidate['vehicle_episode_ids'] for o in by_episode[eid]['observations'])), candidate['candidate_id'])
            local_supported, identity_frames = set(), set()
            for evidence in candidate.get('passage_identity_relation_evidence', []):
                relation = by_relation[evidence['relation_id']]
                local = [[max(start, lo), min(end, hi)] for lo, hi in windows if max(start, lo) <= min(end, hi)]
                features = independent.feature_values(by_episode[relation['first_episode_id']], by_episode[relation['second_episode_id']], relation['type'], local)
                controls = cc['association']['component' if relation['type'] == 'COMPONENT_OF' else 'same_vehicle']
                supported = independent.control_passes(features, controls, relation['type'])
                check(name + ': independent passage-local identity arithmetic', independent.equal_value(features, evidence['features']) and evidence['thresholds'] == controls and evidence['passage_support_window'] == [start, end] and evidence['evaluated_frame_windows'] == local and (evidence['status'] == 'SUPPORTED') is supported, [candidate['candidate_id'], relation['relation_id']])
                if supported: local_supported.add(relation['relation_id']); identity_frames.update(features['common_frame_indices'])
            check(name + ': identity support constrained to own measured passage', set(candidate['identity_relation_ids']) == local_supported and candidate.get('identity_decision_evidence_frame_indices', []) == sorted(identity_frames) and all(start <= frame <= end for frame in identity_frames), candidate['candidate_id'])
            linked_episodes = set(candidate['vehicle_episode_ids']) | set(candidate['component_episode_ids'])
            competitors = []
            for frame in sorted(set(range(start, end+1)) | identity_frames):
                linked = [o for eid in linked_episodes for o in by_episode[eid]['observations'] if o['frame_index'] == frame]
                owned = {o['original_detection_index'] for o in linked}
                for j, det in enumerate(frame_records[frame]['raw_detections']):
                    if j in owned or det['class_name'] not in VEHICLES: continue
                    box = det['bbox_xyxy_pixels']
                    if any(independent.area_intersection(o['raw_bbox'], box) > 0 or o['class_name'] == 'person' and box[0] <= bc(o['raw_bbox'])[0] <= box[2] and box[1] <= bc(o['raw_bbox'])[1] <= box[3] for o in linked):
                        competitors.append({'frame_index': frame, 'original_detection_index': j, 'class_name': det['class_name'], 'raw_bbox': box, 'emitted_track_ids': sorted(o['track_id'] for o in frame_records[frame]['emitted_tracks'] if o['original_detection_index'] == j)})
            check(name + ': all raw competitors independently screened', competitors == candidate['raw_competitor_evidence'] and (not competitors or 'RAW_UNRESOLVED_VEHICLE_COMPETITOR' in candidate['hard_block_reasons']), candidate['candidate_id'])
            source_tracks = {by_episode[eid]['track_id'] for eid in candidate['vehicle_episode_ids']}
            prior = any(d['type'] == 'GEOMETRY_TRANSITION' and d['track_id'] in source_tracks and d['confirmation_frame'] <= start and not (d['episode_id'] == candidate['episode_id'] and d['crossing_frame_start'] == diagnostic['crossing_frame_start']) for d in derived)
            check(name + ': full-history genuine return guard preserved', not prior or candidate['accepted_count_event'] is False and candidate['event_id'] is None and 'GENUINE_RETURN_REVIEW_REQUIRED' in candidate['reasons'], candidate['candidate_id'])
            check(name + ': accepted authority only clean geometry/identity/category', not candidate['accepted_count_event'] or candidate['status'] == 'accepted' and not candidate['reasons'] and not candidate['hard_block_reasons'] and bool(local_supported) and expected_category is not None and candidate['event_id'] in event_ids, candidate['candidate_id'])
        accepted_candidates = {d['candidate_id']: d for d in decisions if d['accepted_count_event']}
        check(name + ': exactly one accepted authority per machine event', len(accepted_candidates) == len(events) and set(accepted_candidates) == {e['candidate_id'] for e in events})
        for event in events:
            candidate = accepted_candidates[event['candidate_id']]
            check(name + ': event source crossing/category exactly candidate', event['geometry_evidence'] == candidate['diagnostic'] and event['measurement_support'] == candidate['measurement_support'] and event['source_identity'] == identity and event['track_id'] == candidate['track_id'] and event['category'] == candidate['category'] and event['direction'] == candidate['diagnostic']['direction'] and event['vehicle_measurement_episode_id'] == candidate['episode_id'], event['event_id'])
            check(name + ': vehicle duplicate group is clique, not transitive guess', all(any(r['type'] == 'SAME_VEHICLE' and r['status'] == 'SUPPORTED' and {r['first_episode_id'], r['second_episode_id']} == {a,b} for r in relations) for a in event['vehicle_episode_ids'] for b in event['vehicle_episode_ids'] if a < b), event['event_id'])
            check(name + ': offline category latest evidence and local identity semantics', event['category_decision_latest_evidence_frame'] == max(by_episode[eid]['end_frame'] for eid in event['vehicle_episode_ids']) and event['identity_evidence_policy'] == 'measured_relation_support_inside_origin_to_confirmation_only' and event['is_causal_online_decision'] is False and event['appearance_features_used'] is False, event['event_id'])
        for sample in stats['samples']:
            png = directory / sample['input_png']; image = cv2.imread(str(png))
            check(name + ': actual sample native input pixels/hash', sha(png) == sample['input_png_sha256'] and image.shape == (720,1280,3) and digest(image.tobytes()) == sample['pixel_sha256'] == frame_hashes[name][sample['frame_index']], sample['frame_index'])
        check(name + ': samples cover declared DEV/holdout frame indices', [s['frame_index'] for s in stats['samples']] == samples and set(map(int, stats['native_sample_pixel_hashes'])) == set(samples))
        totals_by_variant[name] = {'source_frames': len(frame_records), 'source_raw_observations': counters['raw_detections'], 'source_emitted_observations': counters['emitted_observations'], 'encoder_calls': encoder_calls, 'finite_nonzero512_features': feature_count, 'cost_observer_calls': costs['calls'], 'source_episode_count': source_index['all_source_episode_count'], 'selected_episodes': len(episodes), 'selected_ids': len(discovered), 'machine_decision_statuses': counting_report['decision_status_counts'], 'machine_accepted_events': len(events), 'physical_passage_accuracy_established': False}
        print('Audited', name, totals_by_variant[name], flush=True)
    check('native source samples same across independent variants', report['native_sample_pixel_equality'] == {'passed': True, 'frame_indices': samples} and all(report['variants']['raw']['native_sample_pixel_hashes'][str(i)] == report['variants'][config['variants'][1]['name']]['native_sample_pixel_hashes'][str(i)] for i in samples))
    if args.pixel_decode != 'none':
        check('actual local input video independently SHA verified', args.video.is_file() and sha(args.video) == config['expected_video_sha256'])
        capture = cv2.VideoCapture(str(args.video)); check('actual source decoder opened', capture.isOpened())
        gamma = config['variants'][1]['gamma']; table = np.clip(np.rint(255 * np.power(np.arange(256, dtype=np.float64) / 255, gamma)),0,255).astype(np.uint8)
        selected_indices = set(range(9590)) if args.pixel_decode == 'all' else set(samples)
        count = decoded_frames = 0
        try:
            for index in range(9590):
                ok, image = capture.read()
                if not check('full native sequential source decode', ok and image.shape == (720,1280,3), index): break
                decoded_frames += 1
                if index in selected_indices:
                    check('actual raw donor frame exact pixel SHA', digest(image.tobytes()) == frame_hashes['raw'][index], index)
                    transformed = table[image]
                    check('independent gamma donor frame exact pixel SHA', digest(transformed.tobytes()) == frame_hashes[config['variants'][1]['name']][index], index)
                    count += 1
                if (index+1) % 1000 == 0: print('Pixel source audit:', index+1, '/9590', flush=True)
            check('no extra decoded frame beyond expected source', not capture.read()[0])
        finally: capture.release()
        diagnostics['independent_source_decode_frames'] = decoded_frames
        diagnostics['donor_frames_verified_each_variant'] = count
    for folder in ('docs/evidence/phase_6/20261012T144625_030645Z', 'docs/evidence/phase_6/20261013T104301_354775Z'):
        manifest = read(repo / folder / 'retention_manifest.json')
        mapping = read(args.prior_context_map) if args.prior_context_map else None
        for artifact in manifest['artifacts']:
            p = repo / artifact['path']
            if mapping and (not p.is_file() or sha(p) != artifact['sha256']):
                matches = [row for row in mapping.get('artifacts', []) if row.get('original_path') == artifact['path'] and row.get('original_sha256', row.get('sha256')) == artifact['sha256']]
                if len(matches) == 1:
                    archived = matches[0]
                    p = repo / archived['retained_path']
                    archive_valid = p.is_file() and sha(p) == archived['retained_sha256']
                    data = gzip.decompress(p.read_bytes()) if archive_valid else b''
                    check('historical context archive exact compressed bytes', archive_valid, artifact['path'])
                    check('historical context archive exact original bytes', digest(data) == artifact['sha256'] and len(data) == artifact['size_bytes'], artifact['path'])
                    continue
            check('historical immutable evidence or explicit context archive:' + folder, p.is_file() and sha(p) == artifact['sha256'] and p.stat().st_size == artifact.get('size_bytes', artifact.get('bytes')), artifact['path'])
    check_count = sum(totals.values()); pass_count = sum(passed.values())
    result = {'claim_type': 'ACTUALLY_EXECUTED_INDEPENDENT_TEMPORAL_ARTIFACT_AUDIT_NOT_ACCURACY_BENCHMARK', 'run_id': run.name, 'audited_utc': datetime.now(timezone.utc).isoformat(), 'method_path': str(Path(__file__).resolve().relative_to(repo)), 'method_sha256': sha(__file__), 'independent_math_source_path': str(old_math_path.relative_to(repo)), 'independent_math_source_sha256': sha(old_math_path), 'source_report_sha256': sha(run/'report.json'), 'checks_run': check_count, 'checks_passed': pass_count, 'successful': check_count == pass_count, 'failures': failures, 'check_groups': [{'check': k, 'checks_run': v, 'checks_passed': passed[k]} for k, v in sorted(totals.items())], 'observed_variant_diagnostics': totals_by_variant, 'diagnostics': dict(diagnostics, audit_opencv_version=cv2.__version__, audit_numpy_version=np.__version__, pixel_decode_policy=args.pixel_decode), 'limits': ['No model/tracker/encoder/resolver inference is rerun by this audit.', 'Actual CUDA kernels and feature hashes/norms are retained evidence; embeddings/cost matrix vectors are not retained for independent vector recomputation.', 'Parent-formula equality is a source-bound runtime observer assertion whose shapes/counters/flags are independently reconciled, not an independent numerical cost-vector replay.', 'Machine accepted candidate subtotals are scoped to five declared windows, not full-video traffic volume.', 'Cross-variant physical passage identity, split leakage, false merges/duplicates and enhancement benefit require separate pixel/temporal review.', 'Software artifact correctness is not accuracy/precision/recall/F1/MAPE or physical-identity ground truth.']}
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({k: result[k] for k in ('run_id','checks_run','checks_passed','successful','failures')},indent=2))
    raise SystemExit(0 if result['successful'] else 1)


if __name__ == '__main__':
    main()
