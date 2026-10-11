"""Independent read-only retained Phase 4 audit. No detector/tracker/encoder execution.

Phase 3's already retained independent schema auditor is imported for the unchanged
measurement/lifecycle contract; no notebook helpers or model code are executed.
All output check details are compact, not copies of full input sequences.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import importlib.util
import itertools
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/workspace/traffic-vehicle-counter-IDM-LOC')
sys.dont_write_bytecode = True  # Imported retained evidence stays byte-for-byte unchanged.
SPEC = importlib.util.spec_from_file_location('phase3_artifact_contract', REPO / 'docs/evidence/phase_3/verification/audit_tracking.py')
P3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P3)

EXPECTED_MODEL_SHA256 = '8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb'
BURSTS = [(0, 29), (2555, 2584), (5125, 5154), (7696, 7725), (10252, 10281)]

def require(value, message):
    if not value:
        raise ValueError(message)

def read_json(path):
    if str(path).endswith('.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as fh:
            return json.load(fh)
    return P3.load_json(Path(path))

def read_jsonl(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as fh:
        for index, line in enumerate(fh):
            require(bool(line.strip()), f'Blank JSONL line at {index}')
            yield json.loads(line)

def project_to_contract(value, contract, path='root'):
    """Project onto every prior contract key; added Phase 4 fields are inspectable elsewhere."""
    if isinstance(contract, dict):
        require(isinstance(value, dict), f'{path}: dict expected')
        result = {}
        for key, item in contract.items():
            require(key in value, f'{path}: missing retained contract key {key}')
            result[key] = project_to_contract(value[key], item, f'{path}.{key}')
        return result
    if isinstance(contract, list):
        require(isinstance(value, list) and len(value) == len(contract), f'{path}: list length differs')
        return [project_to_contract(v, c, f'{path}[{i}]') for i, (v, c) in enumerate(zip(value, contract))]
    return value

def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def baseline_frame_equivalence(new_path, prior_path):
    left_digest, right_digest = hashlib.sha256(), hashlib.sha256()
    count = 0
    for index, pair in enumerate(itertools.zip_longest(read_jsonl(new_path), read_jsonl(prior_path))):
        actual, prior = pair
        require(actual is not None and prior is not None, f'Baseline length differs at {index}')
        # Timing is an actual new measurement; association/measurement/lifecycle keys are identical.
        prior = {key: value for key, value in prior.items() if key != 'tracker_update_wall_seconds'}
        actual = project_to_contract(actual, prior, f'frame[{index}]')
        require(actual == prior, f'Off replay differs from original Phase 3 at frame {index}')
        left_digest.update(canonical_json(actual) + b'\n')
        right_digest.update(canonical_json(prior) + b'\n')
        count += 1
    require(count == P3.EXPECTED_FRAME_COUNT, 'Baseline full sequence count mismatch')
    return {'compared_frames': count, 'canonical_off_sha256': left_digest.hexdigest(),
            'canonical_original_phase3_sha256': right_digest.hexdigest(),
            'ignored_original_keys': ['tracker_update_wall_seconds'],
            'scope': 'Every original per-frame association, source, history observation, lifecycle field; additional Phase 4 instrumentation audited separately.'}

def baseline_summary_equivalence(new_path, prior_path):
    actual, prior = read_json(new_path), read_json(prior_path)
    ignored = {key: prior.pop(key) for key in ['run_id', 'track_id_scope', 'summary_semantics']}
    projected = project_to_contract(actual, prior)
    require(projected == prior, 'Off summary differs from original Phase 3')
    return {'compared_ids_including_unconfirmed': len(prior['tracks']),
            'canonical_off_sha256': hashlib.sha256(canonical_json(projected)).hexdigest(),
            'canonical_original_phase3_sha256': hashlib.sha256(canonical_json(prior)).hexdigest(),
            'ignored_original_metadata': ignored,
            'new_declarative_metadata': {key: actual[key] for key in ['run_id', 'track_id_scope', 'summary_semantics']},
            'comparison_scope': 'Exact video identity and every original track/history/lifecycle field; metadata wording is not association behavior.'}

def summarize_frame_audit(result):
    return {**result['diagnostics'], 'per_frame_track_ids_and_source_detection_links': 'unique',
            'measurement_and_lifecycle_contract': 'verified', 'full_input_sequences_persisted_in_check_details': False}

def paired_detection_trace(off_rows, on_rows, first, last):
    frames = []
    for index in range(first, last + 1):
        left, right = off_rows[index], on_rows[index]
        require(left['frame_index'] == index == right['frame_index'], 'Trace frame order mismatch')
        require(left['raw_detections'] == right['raw_detections'], 'Paired raw detector evidence differs')
        left_obs = {o['original_detection_index']: o for o in left['assigned_observations_including_unconfirmed']}
        right_obs = {o['original_detection_index']: o for o in right['assigned_observations_including_unconfirmed']}
        frames.append({'frame_index': index,
                       'detections': [{'original_detection_index': det_index, **detection,
                                       'reid_off_assignment': left_obs.get(det_index),
                                       'reid_on_assignment': right_obs.get(det_index)}
                                      for det_index, detection in enumerate(left['raw_detections'])],
                       'reid_off_emitted_tracks': left['emitted_tracks'],
                       'reid_on_emitted_tracks': right['emitted_tracks'],
                       'reid_off_lifecycle_snapshots': left['lifecycle_snapshots'],
                       'reid_on_lifecycle_snapshots': right['lifecycle_snapshots'],
                       'reid_off_lifecycle_transitions': left['lifecycle_transitions'],
                       'reid_on_lifecycle_transitions': right['lifecycle_transitions']})
    return {'scope': 'Paired retained records linked by actual source frame/detection index; ID equality across variants does not establish physical identity.',
            'start_frame': first, 'end_frame': last, 'frames': frames}

def compare_assignments(off_rows, on_rows):
    count_changed_id = count_changed_emit = count_changed_assignment = 0
    first_difference = None
    for left, right in zip(off_rows, on_rows):
        left_map = {o['original_detection_index']: o for o in left['assigned_observations_including_unconfirmed']}
        right_map = {o['original_detection_index']: o for o in right['assigned_observations_including_unconfirmed']}
        if left_map.keys() != right_map.keys():
            count_changed_assignment += 1
        keys = set(left_map) & set(right_map)
        id_diff = sum(left_map[k]['track_id'] != right_map[k]['track_id'] for k in keys)
        emit_diff = sum(left_map[k]['emitted'] != right_map[k]['emitted'] for k in keys)
        count_changed_id += id_diff
        count_changed_emit += emit_diff
        if first_difference is None and (id_diff or emit_diff or left_map.keys() != right_map.keys()):
            first_difference = {'frame_index': left['frame_index'], 'numeric_id_differences': id_diff,
                                'emitted_flag_differences': emit_diff,
                                'off_assigned_detection_indices': sorted(left_map),
                                'on_assigned_detection_indices': sorted(right_map)}
    return {'frames_with_different_assigned_detection_index_sets': count_changed_assignment,
            'paired_detection_observations_with_different_numeric_ids': count_changed_id,
            'paired_detection_observations_with_different_emitted_flags': count_changed_emit,
            'first_software_assignment_difference': first_difference,
            'interpretation': 'Variant software differences only; numeric ID shifts can propagate and are not physical ID-switch/improvement counts.'}

def focused_case_mapping(off_rows, on_rows):
    cases = [('beginning_stable_comparison', 0, 29, [1, 2, 3]),
             ('receding_rider_scooter_stable_comparison', 2555, 2584, [933, 935]),
             ('previously_observed_concurrent_red_scooter_ids', 5125, 5154, [1934, 1951, 1937]),
             ('entering_class_component_handoff_and_roadside_gap', 7696, 7725, [3680, 3681, 3683, 3622]),
             ('end_distant_car_comparison', 10252, 10281, [4829])]
    result = []
    for name, first, last, baseline_ids in cases:
        frames = []; mapping_counts = {track_id: Counter() for track_id in baseline_ids}
        for index in range(first,last+1):
            left, right = off_rows[index], on_rows[index]
            right_by_index = {obs['original_detection_index']: obs for obs in right['assigned_observations_including_unconfirmed']}
            links = []
            for obs in left['assigned_observations_including_unconfirmed']:
                if obs['track_id'] not in baseline_ids: continue
                paired = right_by_index.get(obs['original_detection_index'])
                mapping_counts[obs['track_id']][paired['track_id'] if paired else 'unassigned'] += 1
                links.append({'original_detection_index': obs['original_detection_index'], 'class_name': obs['class_name'],
                              'raw_bbox': obs['raw_bbox'], 'reid_off_track_id': obs['track_id'], 'reid_off_emitted': obs['emitted'],
                              'reid_on_track_id': paired['track_id'] if paired else None,
                              'reid_on_emitted': paired['emitted'] if paired else None})
            frames.append({'frame_index': index, 'same_source_detection_links': links,
                           'off_target_lifecycle': [snap for snap in left['lifecycle_snapshots'] if snap['track_id'] in baseline_ids]})
        result.append({'case': name, 'start_frame': first, 'end_frame': last, 'original_phase3_ids': baseline_ids,
                       'paired_on_numeric_ids_by_off_id': {str(key): dict(value) for key,value in mapping_counts.items()}, 'frames': frames})
    return {'scope': 'Focused source-detection linkage for previously visually inspected baseline cases. On numeric IDs are mapped by identical source frame/detection index, not asserted equivalent physical identities.',
            'cases': result}

class Audit:
    def __init__(self):
        self.checks = []
    def check(self, name, function, summarize=lambda value: value):
        try:
            result = function()
            details = summarize(result)
            self.checks.append({'check': name, 'passed': True, 'details': details})
            return result
        except Exception as exc:
            self.checks.append({'check': name, 'passed': False,
                                'details': {'error_type': type(exc).__name__, 'message': str(exc)}})
            return None
    def export(self, output_dir, run_id, diagnostics):
        errors = [c for c in self.checks if not c['passed']]
        result = {'claim_type': 'EXPERIMENT_RESULT', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                  'run_id': run_id, 'scope': 'Independent read-only retained Phase 4 artifact audit; no detector, tracker or encoder execution.',
                  'status': 'passed' if not errors else 'failed',
                  'checks_passed': len(self.checks)-len(errors), 'checks_total': len(self.checks),
                  'checks': self.checks, 'errors': errors, 'diagnostics': diagnostics,
                  'limitations': ['Software/provenance checks do not establish physical identity or model accuracy.',
                                  'Only retained rendered clips may be decoded; source video is only hashed.',
                                  'Baseline canonical comparison excludes new timing/run ID and audits all original measurement/lifecycle fields.']}
        path = output_dir/'artifact_audit.json'
        path.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
        print(json.dumps({'status': result['status'], 'checks_passed': result['checks_passed'],
                          'checks_total': result['checks_total'], 'errors': errors, 'audit_path': str(path)}, indent=2))
        return 0 if not errors else 1

def audit_provenance(report, parent_path, cache_path, video_path):
    proxy = {**report, 'phase': 3}
    result = P3.audit_provenance(proxy, parent_path, cache_path, video_path)
    require(report['phase'] == 4, 'Actual report is not Phase 4')
    require(report['frames_processed'] == 2*P3.EXPECTED_FRAME_COUNT, 'Paired frame count is incomplete')
    require(report['status'] == 'completed_controlled_reid_sequences_manual_review_pending', 'Actual full-run status is incomplete')
    require(set(report['variants']) == {'reid_off', 'reid_on'}, 'Unexpected variant set')
    P3.reject_identity_metrics(report)
    return result

def audit_configuration_and_sources(report, phase3_verification, candidate_smoke, candidate_asset):
    import onnx
    verified = read_json(phase3_verification)
    smoke = read_json(candidate_smoke)
    env = report['environment']
    require(env['package_versions']['ultralytics'] == '8.4.175', 'Ultralytics runtime mismatch')
    require(env['package_versions']['lap'] == '0.5.13', 'lap runtime mismatch')
    require(env['package_versions']['onnxruntime-gpu'] == '1.24.4', 'ORT GPU runtime mismatch')
    require(env['association_device'] == 'cpu', 'Association device misdeclared')
    require(env['detector_inference_executed'] is False and env['reid_inference_executed'] is True, 'Wrong actual inference scope')
    require(report['tracker']['class'] == 'ultralytics.trackers.bot_sort.BOTSORT', 'Tracker substituted')
    off, on = report['variant_configurations']['reid_off'], report['variant_configurations']['reid_on']
    require(off == verified['contracts']['experiment_config'], 'Off configuration differs from original Phase 3')
    invariant_keys = set(off) | set(on)
    invariant_keys -= {'with_reid', 'model', 'device'}
    require(all(off.get(k) == on.get(k) for k in invariant_keys), 'Motion/lifecycle threshold changed across variants')
    require(on['with_reid'] is True and off['with_reid'] is False, 'Comparison does not toggle ReID')
    require(off['gmc_method'] == on['gmc_method'] == 'none', 'GMC is not isolated')
    require(on['device'] == 'cuda:0', 'Unexpected encoder device')
    for variant in ['reid_off', 'reid_on']:
        require(report['variants'][variant]['configuration'] == report['variant_configurations'][variant], 'Variant actual configuration differs')
    expected = {item['path'].removeprefix('ultralytics/'): item['official_sha256'] for item in verified['files']}
    expected.update({item['path'].removeprefix('ultralytics/'): item['official_sha256'] for item in smoke['source_files']})
    actual = {item['path']: item['sha256'] for item in report['tracker_source_verification']}
    require(actual == expected and all(item['verified'] is True for item in report['tracker_source_verification']), 'Pinned official source hash mismatch')
    candidate = report['encoder_candidate']
    require(candidate['sha256'] == EXPECTED_MODEL_SHA256 and candidate['size_bytes'] == 9873245, 'Encoder candidate asset identity mismatch')
    require(candidate['source_url'] == 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-reid.onnx', 'Encoder candidate source changed')
    runtime = report['variants']['reid_on']['encoder_runtime']
    require(runtime['providers'][0] == 'CUDAExecutionProvider', 'CUDA not selected first')
    require(runtime['device'] == runtime['backend_device'] == 'cuda:0', 'Encoder runtime actual device mismatch')
    require(runtime['imgsz'] == [224, 224] and runtime['fp16'] is False and runtime['static_batch_size'] is None, 'Runtime crop/precision/batch changed')
    require(runtime['no_runtime_fallback'] is True, 'Fallback policy is not explicit')
    require(runtime['model_inputs'] == smoke['inputs']['onnx_inputs'], 'Encoder model input changed')
    require(runtime['model_outputs'] == smoke['outputs']['onnx_outputs'], 'Encoder model output changed')
    require(P3.file_sha256(candidate_asset) == EXPECTED_MODEL_SHA256 and candidate_asset.stat().st_size == 9873245, 'Independent official candidate bytes differ')
    raw_model_metadata = {prop.key: prop.value for prop in onnx.load(candidate_asset).metadata_props}
    require(runtime['metadata'] == raw_model_metadata, 'Actual encoder metadata differs from independently hashed official asset')
    require({key:value for key,value in runtime['metadata'].items() if key != 'names'} == smoke['model']['metadata'], 'Encoder non-name metadata differs from retained CPU smoke')
    return {'source_files_verified': len(actual), 'package_versions': env['package_versions'],
            'encoder_asset_sha256': candidate['sha256'], 'variant_changed_keys': ['with_reid', 'model', 'device'],
            'association_device': 'cpu', 'encoder_device': 'cuda:0', 'person_domain_vehicle_suitability': 'unknown'}

def audit_cuda_profile(run_dir, report):
    record = report['variants']['reid_on']['cuda_execution_evidence']
    path = run_dir / record['profile']
    require(P3.file_sha256(path) == record['profile_sha256'], 'Actual ORT profile hash mismatch')
    events = read_json(path)
    counts = Counter(event.get('args', {}).get('provider') for event in events
                     if event.get('cat') == 'Node' and event.get('args', {}).get('provider'))
    require(dict(counts) == record['provider_kernel_event_counts'], 'Actual ORT provider counters differ')
    require(counts['CUDAExecutionProvider'] > 0 and record['actual_cuda_execution_confirmed'] is True, 'No actual CUDA node execution evidence')
    examples = [{'name': event.get('name'), 'provider': event.get('args', {}).get('provider'),
                 'op_name': event.get('args', {}).get('op_name'), 'duration_us': event.get('dur')}
                for event in events if event.get('cat') == 'Node' and event.get('args', {}).get('provider') == 'CUDAExecutionProvider'][:8]
    require(examples == record['cuda_kernel_event_examples'], 'CUDA profile examples differ')
    export = read_json(run_dir/'reid_on/encoder_provider_evidence.json')
    require(project_to_contract(record, export) == export, 'Provider report differs from original exported supplement')
    require(record['profiled_source_frame'] == 0, 'Unexpected first actual encoder-bearing frame')
    return {'raw_profile_sha256': record['profile_sha256'], 'provider_kernel_event_counts': dict(counts),
            'profiled_source_frame': record['profiled_source_frame'],
            'scope': 'Actual first appearance-bearing update profile only; CPU graph partitions, if present, are reported.'}

def audit_appearance_records(path, variant, cache_rows, report):
    import numpy as np
    import struct
    calls = features = 0
    wall = 0.0
    totals = Counter()
    full_matrix_calls = 0
    feature_norm_min, feature_norm_max = math.inf, -math.inf
    for index, row in enumerate(read_jsonl(path)):
        require(index < len(cache_rows) and row['frame_index'] == index and row['variant'] == variant, 'Appearance row order/variant mismatch')
        expected_features = sum(det['confidence'] >= report['variant_configurations'][variant]['track_high_thresh']
                                for det in cache_rows[index]['detections'])
        actual_features = 0
        for call in row['encoder_calls']:
            require(variant == 'reid_on', 'Off variant executed encoder')
            count = P3.require_int(call['feature_count'], 'Encoder feature count')
            require(count > 0 and call['dimensions'] == [512], 'Encoder dimension/cardinality malformed')
            require(len(call['feature_l2_norms']) == len(call['feature_sha256']) == count, 'Feature metadata cardinality differs')
            for norm, digest in zip(call['feature_l2_norms'], call['feature_sha256']):
                norm = P3.finite_number(norm, 'Feature L2 norm')
                require(norm > 1e-12, 'Zero-norm feature retained')
                require(isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'Malformed feature digest')
                feature_norm_min = min(feature_norm_min, norm); feature_norm_max = max(feature_norm_max, norm)
            seconds = P3.finite_number(call['encoder_wall_seconds'], 'Encoder wall seconds')
            require(seconds >= 0, 'Negative actual encoder timing')
            calls += 1; actual_features += count; wall += seconds
        require(actual_features == (expected_features if variant == 'reid_on' else 0), f'Per-frame feature coverage mismatch at {index}')
        features += actual_features
        P3.equal_float(row['encoder_wall_seconds'], sum(c['encoder_wall_seconds'] for c in row['encoder_calls']), 'Appearance row encoder sum', 1e-9)
        for call in row['association_calls']:
            require(call['frame_index'] == index and call['parent_formula_exact_match'] is True, 'Association row/formula declaration malformed')
            shape = call['matrix_shape']
            require(shape == [len(call['track_ids']), len(call['detection_indices'])], 'Association matrix/ID cardinality mismatch')
            require(len(set(call['track_ids'])) == len(call['track_ids']) and len(set(call['detection_indices'])) == len(call['detection_indices']), 'Duplicate association axes')
            require(all(type(det_index) is int and 0 <= det_index < len(cache_rows[index]['detections']) for det_index in call['detection_indices']), 'Association source index invalid')
            size = shape[0]*shape[1]
            require(call['candidate_pairs'] == size, 'Candidate pair count mismatch')
            eligible, changed = call['appearance_eligible_pairs'], call['appearance_changed_cost_pairs']
            require(type(eligible) is int and type(changed) is int and 0 <= changed <= eligible <= size, 'Appearance pair counters invalid')
            require(call['features_present_in_nonempty_association'] == (variant == 'reid_on' and size > 0), 'Appearance association feature flag incoherent')
            reduction = P3.finite_number(call['max_cost_reduction'], 'Association maximum reduction')
            require(reduction >= 0 and (changed > 0) == (reduction > 1e-12), 'Changed-cost flag/max mismatch')
            require(P3.finite_number(call['parent_get_dists_wall_seconds'], 'Parent get_dists time') >= 0, 'Negative actual get_dists timing')
            if variant == 'reid_off':
                require(eligible == changed == 0, 'Off variant has appearance effect')
            if 'actual_costs' in call:
                # The pinned matching/embedding routines return float32 arrays. Preserve
                # that arithmetic after JSON roundtrip, including subtraction/max rounding.
                motion = np.asarray(call['motion_costs'], dtype=np.float32).reshape(shape)
                actual = np.asarray(call['actual_costs'], dtype=np.float32).reshape(shape)
                require(np.isfinite(motion).all() and np.isfinite(actual).all(), 'Nonfinite retained association matrix')
                if variant == 'reid_on':
                    raw = np.asarray(call['appearance_raw_half_cosine'], dtype=np.float32).reshape(shape)
                    gated = np.asarray(call['appearance_gated_costs'], dtype=np.float32).reshape(shape)
                    require(np.isfinite(raw).all() and np.isfinite(gated).all(), 'Nonfinite retained appearance matrix')
                    require(np.array_equal(actual, np.minimum(motion, gated)), 'Actual association matrix is not minimum motion/appearance')
                    scores = np.asarray([struct.unpack('f', struct.pack('f', cache_rows[index]['detections'][d]['confidence']))[0]
                                         for d in call['detection_indices']], dtype=np.float32)
                    recovered_iou = 1-(1-motion)/scores if size else motion.copy()
                    threshold_appearance = 1-report['variant_configurations'][variant]['appearance_thresh']
                    threshold_iou = 1-report['variant_configurations'][variant]['proximity_thresh']
                    recovered_gated = raw.copy()
                    recovered_gated[raw > threshold_appearance] = 1.0
                    recovered_gated[recovered_iou > threshold_iou] = 1.0
                    require(np.array_equal(gated, recovered_gated), 'Gated appearance matrix differs from retained threshold/motion evidence')
                    derived_eligible = int(((raw <= threshold_appearance) & (recovered_iou <= threshold_iou)).sum())
                    require(eligible == derived_eligible, 'Appearance eligibility count differs from matrix')
                else:
                    require(call['appearance_raw_half_cosine'] is None and call['appearance_gated_costs'] is None, 'Off matrix contains appearance')
                    require(np.array_equal(actual, motion), 'Off matrix not pure fused-motion')
                delta = np.abs(actual-motion)
                require(changed == int(np.count_nonzero(delta > 1e-12)), 'Changed-cost count differs from retained matrix')
                P3.equal_float(reduction, float(delta.max()) if delta.size else 0.0, 'Max matrix cost reduction', 1e-9)
                full_matrix_calls += 1
            totals.update(calls=1, candidate_pairs=size, nonempty_feature_association_calls=int(call['features_present_in_nonempty_association']),
                          appearance_eligible_pairs=eligible, appearance_changed_cost_pairs=changed,
                          calls_with_changed_costs=int(changed > 0))
    require(index+1 == len(cache_rows), 'Appearance sequence ended early')
    require(dict(totals) == report['variants'][variant]['association_mechanism_diagnostics'], 'Reported association counters differ from full records')
    if variant == 'reid_on':
        declared = report['variants'][variant]['embedding_diagnostics']
        require(declared['encoder_calls'] == calls and declared['finite_nonzero_features_produced'] == features and declared['embedding_dimension'] == 512, 'Reported embedding counters differ')
        P3.equal_float(declared['encoder_observer_wall_seconds'], wall, 'Full encoder counter timing', 1e-9)
    return {'ordered_appearance_rows': index+1, 'encoder_calls': calls, 'feature_metadata_rows': features,
            'feature_norm_min': feature_norm_min if calls else None, 'feature_norm_max': feature_norm_max if calls else None,
            'encoder_wall_seconds': wall, 'full_retained_association_matrices_recomputed': full_matrix_calls,
            'association_mechanism_counters': dict(totals),
            'limits': 'Full vectors are not retained; finite/nonzero evidence is supplied by the actual validated encoder observer, with per-feature norms/digests. Cost matrices independently reconcile where retained.'}

def audit_variant_statistics(report, variant, frame_audit, summary_diagnostics, appearance_diagnostics):
    import statistics
    execution = report['variants'][variant]
    expected = {**frame_audit['diagnostics'], **{k: v for k, v in summary_diagnostics.items() if k != 'interpretation'}}
    require(all(execution['diagnostics'][key] == value for key, value in expected.items()), 'Reported variant diagnostics differ')
    require(execution['diagnostics']['id_switch_count'] is None and execution['diagnostics']['traffic_count'] is None, 'Unsupported identity/count totals')
    require(execution['frames_processed'] == P3.EXPECTED_FRAME_COUNT, 'Variant full processing count differs')
    times = [P3.finite_number(row['tracker_update_wall_seconds'], 'Actual tracker time') for row in frame_audit['records']]
    require(all(t >= 0 for t in times), 'Negative tracker timing')
    timing = execution['timing']
    require(timing['tracker_update_calls'] == P3.EXPECTED_FRAME_COUNT and timing['decoder_read_calls_including_final_probe'] == P3.EXPECTED_FRAME_COUNT+1, 'Update/read totals differ')
    P3.equal_float(timing['tracker_update_wall_seconds'], sum(times), 'Full tracker update time', 1e-9)
    P3.equal_float(timing['tracker_update_wall_ms_mean'], statistics.mean(times)*1000, 'Mean tracker update time', 1e-9)
    P3.equal_float(timing['tracker_update_wall_ms_median'], statistics.median(times)*1000, 'Median tracker update time', 1e-9)
    P3.equal_float(timing['encoder_wall_seconds_inside_tracker'], appearance_diagnostics['encoder_wall_seconds'], 'Embedded encoder time', 1e-9)
    require(timing['loop_wall_seconds'] >= timing['tracker_update_wall_seconds'] >= timing['encoder_wall_seconds_inside_tracker'], 'Contained timing totals incoherent')
    return {**expected, 'timing': timing, 'interpretation': 'Software diagnostics and instrumented timings, not physical identity/traffic metrics.'}

def audit_all_artifact_hashes(run_dir, report):
    checked = []
    def one(path, expected):
        full = (run_dir/path).resolve()
        require(full.is_relative_to(run_dir.resolve()), 'Artifact path escapes run directory')
        require(full.is_file() and P3.file_sha256(full) == expected, f'Declared artifact hash mismatch: {path}')
        checked.append(path)
    for variant, artifacts in report['artifacts']['variants'].items():
        for key in ['track_records', 'track_summary', 'appearance_records', 'representative_temporal_track_records']:
            one(artifacts[key], artifacts[key+'_sha256'])
        for sample in artifacts['sample_frames']:
            for key in ['raw', 'annotated']:
                one(sample[key], sample[key+'_sha256'])
                pixels = P3.pixel_digest(run_dir/sample[key])
                require([pixels['width'], pixels['height']] == [report['input']['width'], report['input']['height']], 'Sample not native dimensions')
        for burst in artifacts['temporal_bursts']:
            for key in ['clip', 'contact_sheet']:
                one(burst[key], burst[key+'_sha256'])
    for sheet in report['artifacts']['paired_contact_sheets']:
        one(sheet['path'], sheet['sha256'])
    profile = report['variants']['reid_on']['cuda_execution_evidence']
    one(profile['profile'], profile['profile_sha256'])
    return {'declared_artifact_files_rehashed': len(checked), 'paths': checked}

def audit_temporal_and_pixels(run_dir, report, frame_audits, parent_path):
    import cv2
    parent = read_json(parent_path)
    parent_dir = parent_path.parent
    variant_raw = {}
    clips = []
    for variant in ['reid_off', 'reid_on']:
        artifacts = report['artifacts']['variants'][variant]
        samples = {sample['frame_index']: sample for sample in artifacts['sample_frames']}
        expected = set([0,2570,5140,7711,10281]+list(range(7711,7719)))
        require(set(samples) == expected, 'Native representative/focused samples incomplete')
        variant_raw[variant] = {index: P3.file_sha256(run_dir/sample['raw']) for index, sample in samples.items()}
        for original in parent['sample_frames']:
            index = original['frame_index']
            require(P3.pixel_digest(run_dir/samples[index]['raw']) == P3.pixel_digest(parent_dir/original['raw']), 'Native source PNG pixels differ from Phase 2')
            require(P3.file_sha256(run_dir/samples[index]['raw']) == P3.file_sha256(parent_dir/original['raw']), 'Native source PNG bytes differ from Phase 2')
        require([(b['start_frame'],b['end_frame']) for b in artifacts['temporal_bursts']] == BURSTS, 'Burst boundaries differ')
        temporal = read_json(run_dir/artifacts['representative_temporal_track_records'])
        rows = frame_audits[variant]['records']
        require(temporal == [row for row in rows if any(first <= row['frame_index'] <= last for first,last in BURSTS)], 'Temporal subset differs from full inherited-state sequence')
        for burst in artifacts['temporal_bursts']:
            cap = cv2.VideoCapture(str(run_dir/burst['clip']))
            count = 0
            try:
                require(cap.isOpened(), 'Retained rendered MP4 cannot open')
                while True:
                    ok, image = cap.read()
                    if not ok: break
                    require(image.shape[:2] == (report['input']['height'],report['input']['width']), 'Rendered clip not native dimensions')
                    count += 1
            finally:
                cap.release()
            require(count == burst['frame_count'] == 30, 'Retained temporal clip not complete')
            clips.append({'variant': variant, 'start_frame': burst['start_frame'], 'end_frame': burst['end_frame'], 'decoded_rendered_frames': count})
    require(variant_raw['reid_off'] == variant_raw['reid_on'], 'Actual native source pixels differ across paired decoder passes')
    return {'identical_phase2_raw_samples_per_variant': 5, 'identical_off_on_native_raw_frames': sorted(variant_raw['reid_off']),
            'temporal_record_subset_rows_per_variant': 150, 'rendered_clips': clips,
            'scope': 'Pixel/source preservation and retained export completeness, not physical identity quality.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--phase2-report', type=Path, required=True)
    parser.add_argument('--video', type=Path)
    parser.add_argument('--phase3-dir', type=Path, default=REPO/'docs/evidence/phase_3/20261011T060227_579936Z_05ebe213')
    parser.add_argument('--phase3-verification', type=Path, default=REPO/'docs/evidence/phase_3/verification/source_verification.json')
    parser.add_argument('--candidate-smoke', type=Path, default=Path('/tmp/phase4_reid_candidate_smoke.json'))
    parser.add_argument('--candidate-asset', type=Path, default=Path('/tmp/phase4-verified-assets/yolo26n-reid.onnx'))
    parser.add_argument('--output-dir', type=Path, default=Path('/tmp/phase4-artifact-audit/actual_run'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit = Audit(); diagnostics = {}; frame_audits = {}
    report = audit.check('original_execution_report_json', lambda: read_json(args.run_dir/'reid_report.json'),
                         lambda r: {key: r[key] for key in ['phase','run_id','status','frames_processed']})
    cache_result = audit.check('original_phase2_cache_identity_order_and_schema', lambda: P3.check_detection_cache(args.cache), lambda result: result[1])
    if report is not None and cache_result is not None:
        cache_rows, cache_diagnostics = cache_result
        diagnostics['retained_cache'] = cache_diagnostics
        audit.check('retained_parent_input_and_complete_controlled_scope', lambda: audit_provenance(report,args.phase2_report,args.cache,args.video))
        audit.check('pinned_off_on_configuration_asset_sources_and_runtime', lambda: audit_configuration_and_sources(report,args.phase3_verification,args.candidate_smoke,args.candidate_asset))
        audit.check('actual_onnx_cuda_node_profile_execution', lambda: audit_cuda_profile(args.run_dir,report))
        audit.check('original_manifest_equals_execution_report', lambda: require(read_json(args.run_dir/'run_manifest.json') == report, 'Manifest/report differ'))
        audit.check('all_declared_output_artifact_hashes_and_native_dimensions', lambda: audit_all_artifact_hashes(args.run_dir,report))
        for variant in ['reid_off','reid_on']:
            artifacts = report['artifacts']['variants'][variant]
            frame_audit = audit.check(variant+'_full_measurement_links_lifecycle_and_history_contract',
                                     lambda: P3.audit_frame_records(args.run_dir/artifacts['track_records'],cache_rows,report['input']['fps_from_parent_opencv']), summarize_frame_audit)
            if frame_audit is None: continue
            frame_audits[variant] = frame_audit
            summary = audit.check(variant+'_full_track_summary_and_gap_class_lifecycle_counters',
                                  lambda: P3.audit_track_summary(args.run_dir/artifacts['track_summary'],frame_audit,report['run_id']))
            appearance = audit.check(variant+'_all_embedding_metadata_and_association_mechanism_records',
                                     lambda: audit_appearance_records(args.run_dir/artifacts['appearance_records'],variant,cache_rows,report))
            if summary is not None and appearance is not None:
                diagnostics[variant] = audit.check(variant+'_reported_software_counters_and_actual_timings_reconcile',
                                                   lambda: audit_variant_statistics(report,variant,frame_audit,summary,appearance))
        if set(frame_audits) == {'reid_off','reid_on'}:
            off = report['artifacts']['variants']['reid_off']
            audit.check('off_all_frames_exact_original_phase3_contract_equivalence',
                        lambda: baseline_frame_equivalence(args.run_dir/off['track_records'],args.phase3_dir/'track_records.jsonl.gz'))
            audit.check('off_all_tracks_exact_original_phase3_summary_equivalence',
                        lambda: baseline_summary_equivalence(args.run_dir/off['track_summary'],args.phase3_dir/'track_summary.json.gz'))
            audit.check('native_source_pixel_preservation_and_full_paired_temporal_exports',
                        lambda: audit_temporal_and_pixels(args.run_dir,report,frame_audits,args.phase2_report))
            diagnostics['paired_software_assignment_differences'] = compare_assignments(frame_audits['reid_off']['records'],frame_audits['reid_on']['records'])
            def traces():
                outputs = []
                for first,last in BURSTS:
                    result = paired_detection_trace(frame_audits['reid_off']['records'],frame_audits['reid_on']['records'],first,last)
                    path = args.output_dir/f'paired_trace_{first:09d}_{last:09d}.json'
                    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
                    outputs.append({'path': path.name, 'start_frame': first, 'end_frame': last, 'frame_count': len(result['frames'])})
                return outputs
            audit.check('focused_paired_traces_linked_by_original_detection_indices', traces)
            focused = focused_case_mapping(frame_audits['reid_off']['records'],frame_audits['reid_on']['records'])
            (args.output_dir/'focused_case_source_link_mapping.json').write_text(json.dumps(focused,indent=2,allow_nan=False)+'\n')
    raise SystemExit(audit.export(args.output_dir, report.get('run_id') if report else None, diagnostics))

if __name__ == '__main__':
    main()
