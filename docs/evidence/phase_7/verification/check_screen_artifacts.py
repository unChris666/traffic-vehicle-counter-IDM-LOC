"""Independent read-only audit of retained Phase 7 DEV detection screening.

Does not import the experimental helper, load a model, run inference, or alter
retained images. Native photometric/annotation mathematics is checked separately
against saved PNG pixels; sequential video decode is optional but explicit.
"""
from __future__ import annotations
import argparse
import ast
import base64
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

import cv2
import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def digest(b):
    return hashlib.sha256(b).hexdigest()


def read_json(path):
    def bad(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(Path(path).read_text(), parse_constant=bad)


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-12)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--run', type=Path, default=Path('docs/evidence/phase_7/screening/20261014T060849_366767Z'))
    parser.add_argument('--video', type=Path, default=Path('/tmp/traffic-phase7-source/TOR3-MALAM.mp4'))
    parser.add_argument('--weights', type=Path, default=Path('/tmp/traffic-phase7-screen-output/phase_7_night/weights/yolo26m.pt'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    run = args.run if args.run.is_absolute() else repo / args.run
    output = args.output or run / 'independent_artifact_audit.json'
    checks, diagnostics = [], {}

    def check(name, condition, detail=None):
        row = {'check': name, 'passed': bool(condition)}
        if detail is not None:
            row['detail'] = detail
        checks.append(row)
        return bool(condition)

    report = read_json(run / 'report.json')
    config = read_json(run / 'config.json')
    plan = read_json(run / 'sampling_plan.json')
    execution = read_json(run / 'notebook_execution_manifest.json')
    positions = read_json(run / 'sample_source_positions.json')
    guard = read_json(run / 'pre_execution_guard/synthetic_test_results.json')
    hashes = read_json(run / 'pre_execution_guard/source_code_sha256.json')
    indices = plan['development']['sample_frame_indices']
    holdout_ranges = [(s['start_frame'], s['end_frame']) for s in plan['holdout']['segments']]
    native_shape = (plan['input_identity']['height'], plan['input_identity']['width'], 3)
    kaggle_root = Path(report['output_directory'])

    def local_path(declared):
        p = Path(declared)
        if p.is_absolute():
            p = p.relative_to(kaggle_root)
        if '..' in p.parts:
            raise ValueError('Artifact path escapes run root')
        return run / p

    for manifest_name in ('manifest.json', 'notebook_archive_manifest.json'):
        manifest = read_json(run / manifest_name)
        for artifact in manifest['artifacts']:
            p = local_path(artifact['path'])
            label = manifest_name + ':' + artifact['path']
            ok = check(label + ':exists', p.is_file())
            if ok:
                check(label + ':bytes', p.stat().st_size == artifact.get('bytes', artifact.get('size_bytes')))
                check(label + ':sha256', sha(p) == artifact['sha256'])
    check('run ID/report status actual', report['run_id'] == run.name and report['status'] == 'completed_detection_screen_no_temporal_claims' and report['execution_kind'] == 'ACTUAL_MODEL_EXECUTION' and report['stage'] == 'detection' and report['phase'] == 7)
    check('15 sorted unique development samples', indices == sorted(set(indices)) and len(indices) == 15 and report['sample_indices'] == indices)
    check('development indices excluded from all holdout ranges', all(not any(a <= i <= b for a, b in holdout_ranges) for i in indices))
    check('all development indices inside own declared continuous segments', all(any(s['start_frame'] <= i <= s['end_frame'] for s in plan['development']['segments']) for i in indices))
    check('configuration same logical values across retained/source/pre-execution', config == report['configuration'] == read_json(repo / 'docs/evidence/phase_7/config/TOR3-MALAM_screen_v1.json') == read_json(run / 'pre_execution_guard/configuration_input.json'))
    check('configuration original bytes SHA bound', sha(run / 'pre_execution_guard/configuration_input.json') == execution['configuration_sha256'])
    check('sampling bytes original SHA bound', sha(run / 'pre_execution_guard/sampling_plan_input.json') == execution['sampling_plan_sha256'] == config['expected_sampling_sha256'] == report['sampling_sha256'])
    check('sampling logical copy equal original source', plan == read_json(run / 'pre_execution_guard/sampling_plan_input.json') == read_json(repo / 'docs/evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json'))
    check('night input identity/native full frame', report['input_identity']['video_sha256'] == config['expected_video_sha256'] == plan['input_identity']['video_sha256'] and native_shape == (720, 1280, 3) and report['input_identity']['size_bytes'] == 52906523 and plan['input_identity']['decoded_frame_count'] == 9590)
    check('no holdout/temporal/counting/selected performance claims', all(report[k] is False for k in ('holdout_enhancement_or_inference_executed', 'heldout_evaluation_executed', 'temporal_pipeline_executed', 'count_events_generated')) and report['selected_configuration'] is None and execution['holdout_evaluation_executed'] is False and execution['tracking_reid_geometry_crossing_counting_executed'] is False and execution['selected_enhancement'] is None and execution['formal_ground_truth_available'] is False)
    check('60 real pre-execution synthetic tests passed', guard['tests_run'] == guard['tests_passed'] == 60 and guard['successful'] is True and not guard['failures'] and not guard['errors'] and not guard['skipped'] and execution['test_guard'] == {'successful': True, 'tests_run': 60} and 'Ran 60 tests' in guard['output'] and guard['output'].rstrip().endswith('OK'))
    resource = report['resource']
    check('CUDA actual FP32 device0 with two visible T4 GPUs', resource['model_inference_executed'] is True and resource['cuda_available'] is True and resource['execution_device'] == 'cuda:0' and resource['cuda_device_name'] == 'Tesla T4' and resource['visible_cuda_device_count'] == 2 and resource['actual_backend']['device'] == 'cuda:0' and resource['actual_backend']['fp16'] is False and resource['actual_backend']['end2end'] is False and resource['actual_backend']['imgsz'] == [640, 640])
    check('actual runtime/execution resource identical', execution['actual_helper_model_resource'] == resource and report['environment']['opencv_version'] == '4.13.0' and report['environment']['numpy_version'] == '2.0.2' and report['environment']['cpu_count'] == 4)
    baseline = read_json(repo / config['detector']['baseline_provenance'])
    settings = config['detector']['settings']
    check('actual predictor arguments exactly frozen Phase2 controls', resource['actual_predictor_arguments'] == settings and all(type(settings[k]) is type(baseline['effective_predictor_arguments'][k]) and settings[k] == baseline['effective_predictor_arguments'][k] for k in settings))
    check('model asset SHA/size/version equal frozen baseline', resource['weights_sha256'] == config['detector']['weights_sha256'] == '401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7' and resource['weights_bytes'] == 44255705 and resource['package_version'] == config['detector']['package_version'] == '8.4.175')
    check('class mapping immutable vs Phase2; raw labels not GT', resource['class_names'] == baseline['model']['class_names'] and len(resource['class_names']) == 80)
    check('resource/execution/helper timing nonnegative', 0 < report['total_wall_seconds'] <= execution['measured_screen_wall_seconds'] and datetime.fromisoformat(execution['execution_started_utc']) <= datetime.fromisoformat(report['started_utc']) < datetime.fromisoformat(report['finished_utc']) <= datetime.fromisoformat(execution['execution_finished_utc']))
    check('before-setup real nvidia-smi two T4s', execution['runtime']['gpu_probe']['returncode'] == 0 and execution['runtime']['gpu_probe']['stdout'].count('Tesla T4') == 2)
    check('actual explicit package installation success', execution['package_setup'] == read_json(run / 'pre_execution_guard/detector_package_installation.json') and execution['package_setup']['returncode'] == 0 and 'Successfully installed ultralytics-8.4.175' in execution['package_setup']['stdout'])
    check('source code hashes same before/execution', hashes == execution['source_code_sha256'])
    sources = {'preprocessing_helper': 'phase_7_night_helpers.py', 'preprocessing_tests': 'phase_7_night_tests.py', 'repository_notebook_source': '07_night_preprocessing.ipynb'}
    for key, name in sources.items():
        archived = gzip.decompress((run / 'source_snapshot' / (name + '.gz')).read_bytes())
        check('executed source archive ' + name, digest(archived) == hashes[key])
        check('working source unchanged ' + name, sha(repo / 'notebooks' / name) == hashes[key])
    check('helper exact separately retained executed source', digest(gzip.decompress((run / 'phase_7_night_helpers.executed_source.py.gz').read_bytes())) == hashes['preprocessing_helper'] == report['source_helper_sha256'] == config['source_helper_sha256'])
    check('guard tests SHA frozen config', hashes['preprocessing_tests'] == config['source_test_sha256'])
    submission_root = repo / 'docs/evidence/phase_7/kaggle_submission'
    submission = read_json(submission_root / 'screen_submission.json')
    submitted_bytes = gzip.decompress((submission_root / 'screen_submitted.ipynb.gz').read_bytes())
    check('submitted notebook SHA bound to actual COMPLETE record', digest(submitted_bytes) == submission['notebook_sha256'] and submission['observed_status'] == 'KernelWorkerStatus.COMPLETE' and submission['actual_run_id'] == run.name)
    submitted = json.loads(submitted_bytes)
    bootstrap = ast.parse(''.join(submitted['cells'][1]['source']))
    bundle_literal = next(n.value.args[0] for n in bootstrap.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SOURCE_BUNDLE' for t in n.targets))
    bundle = json.loads(ast.literal_eval(bundle_literal))
    for name, row in bundle.items():
        data = gzip.decompress(base64.b64decode(row['gzip_base64']))
        check('hash-bound submitted payload ' + name, digest(data) == row['sha256'] and len(data) == row['bytes'] and (repo / name).read_bytes() == data)
    nb = read_json(repo / 'notebooks/07_night_preprocessing.ipynb')
    check('source notebook output-free', all(c.get('outputs', []) == [] and c.get('execution_count') is None for c in nb['cells'] if c['cell_type'] == 'code'))
    check('submission only explicit mode change after bundle bootstrap', len(submitted['cells']) == len(nb['cells']) + 2 and all(a['cell_type'] == b['cell_type'] and ''.join(a['source']).replace("MODE = 'detection_screen'  #", "MODE = 'photometric_only'  #") == ''.join(b['source']) for a, b in zip(submitted['cells'][2:], nb['cells'])))
    log_path = submission_root / 'screen_execution.log.gz'
    if check('real Kaggle log retained', log_path.is_file()):
        check('real Kaggle log SHA bound', sha(log_path) == submission['execution_log_sha256'])
        log_rows = json.loads(gzip.decompress(log_path.read_bytes()))
        log = ''.join(row['data'] for row in log_rows)
        check('log contains actual completed source run and no traceback', run.name in log and 'completed_detection_screen_no_temporal_claims' in log and '\"tests_run\": 60' in log and '\"successful\": true' in log and 'Traceback (most recent call last)' not in log)
    check('five independently configured single-operation variants', report['variants'] and [v['variant'] for v in report['variants']] == config['variants'] and len(config['variants']) == 5 and sum(v['method'] == 'raw' for v in config['variants']) == 1)
    check('float64 rint clipping/native BGR policy retained', report['rounding'] == 'float64, numpy.rint ties-to-even, clip [0,255], uint8' and 'BGR' in report['channel_order'] and 'no crop/resize/stabilization' in report['channel_order'])
    check('sequential source prefix metadata unchanged', positions == report['decode'] and positions['sampled_indices'] == indices and positions['sequential_decoded_frames'] == indices[-1] + 1 == 7312 and positions['decode_method'] == 'sequential_from_frame_zero_no_seek' and positions['width'] == 1280 and positions['height'] == 720 and positions['frame_count_backend'] == 9590.0)
    source_pixels = {}
    check('exact source-frame set contains only DEV', [s['frame_index'] for s in report['source_frames']] == indices and sorted(p.name for p in (run / 'source_frames').glob('*.png')) == sorted(f'frame_{i:09d}.png' for i in indices))
    for row in report['source_frames']:
        i = row['frame_index']
        p = local_path(row['path'])
        check(f'source {i}: SHA', sha(p) == row['sha256'])
        image = cv2.imread(str(p), cv2.IMREAD_COLOR)
        check(f'source {i}: native uint8 BGR', image is not None and image.shape == native_shape and image.dtype == np.uint8)
        source_pixels[i] = image
    pixel_diagnostics = []
    observed_rows, actual_warmups, bbox_count = 0, 0, 0
    for entry in report['variants']:
        variant = entry['variant']
        name, method = variant['name'], variant['method']
        check(name + ': same15 source frames', entry['sample_indices'] == indices and [s['frame_index'] for s in entry['samples']] == indices)
        check(name + ': explicit excluded warmup', entry['warmup']['frame_index'] == indices[0] and entry['warmup']['saved_as_measurement'] is False and entry['warmup']['timing_excluded_from_prediction_statistics'] is True and entry['warmup']['wall_seconds_including_transform'] > 0)
        actual_warmups += 1
        detection_path = local_path(entry['detections_path'])
        check(name + ': JSONL SHA', sha(detection_path) == entry['detections_sha256'])
        with gzip.open(detection_path, 'rt') as stream:
            rows = [json.loads(line) for line in stream]
        observed_rows += len(rows)
        check(name + ': exactly15 measured sample predictions', len(rows) == entry['prediction_calls_measured'] == 15 and [x['frame_index'] for x in rows] == indices)
        times = [x['prediction_wall_seconds'] for x in rows]
        check(name + ': actual wall timings agree with JSONL', all(math.isfinite(x) and x > 0 for x in times) and close(sum(times), entry['prediction_wall_seconds_total_excluding_warmup']) and close(statistics.mean(times) * 1000, entry['prediction_wall_ms_mean']) and close(statistics.median(times) * 1000, entry['prediction_wall_ms_median']))
        check(name + ': transform/io/warmup timings distinct', entry['transformation_wall_seconds'] >= 0 and entry['variant_total_wall_seconds_including_io_and_warmup'] >= sum(times) + entry['warmup']['wall_seconds_including_transform'])
        check(name + ': actual peak allocated/reserved memory bounded', 0 < entry['resource']['cuda_peak_allocated_bytes'] <= entry['resource']['cuda_peak_reserved_bytes'] <= resource['cuda_total_memory_bytes'])
        classes, confidence = Counter(), []
        for sample, row in zip(entry['samples'], rows):
            i = row['frame_index']
            prefix = name + ':' + str(i)
            check(prefix + ': raw native model provenance no count', row['variant'] == name and row['execution_kind'] == 'ACTUAL_MODEL_EXECUTION' and row['input_video_sha256'] == config['expected_video_sha256'] and row['coordinate_space'] == 'native_full_frame_xyxy_pixels' and row['width'] == 1280 and row['height'] == 720 and row['accepted_count_event'] is False)
            check(prefix + ': library speed finite nonnegative', set(row['library_speed_ms']) == {'preprocess', 'inference', 'postprocess'} and all(math.isfinite(t) and t >= 0 for t in row['library_speed_ms'].values()))
            check(prefix + ': measured sample count consistent', sample['detection_count'] == len(row['detections']))
            for j, det in enumerate(row['detections']):
                bbox_count += 1
                box = det['bbox_xyxy']
                check(prefix + ': bbox' + str(j) + ' native full frame/raw immutable class', len(box) == 4 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in box) and 0 <= box[0] < box[2] <= 1280 and 0 <= box[1] < box[3] <= 720 and type(det['class_id']) is int and resource['class_names'].get(str(det['class_id'])) == det['class_name'] and det['detection_index'] == j and math.isfinite(det['confidence']) and settings['conf'] <= det['confidence'] <= 1)
                classes[det['class_name']] += 1
                confidence.append(det['confidence'])
            for kind in ('transformed', 'annotated'):
                p = local_path(sample[kind]['path'])
                check(prefix + ':' + kind + ' SHA', sha(p) == sample[kind]['sha256'])
            source = source_pixels[i]
            pixels = source.astype(np.float64)
            if method == 'raw':
                expected = source.copy()
            else:
                if method == 'gamma':
                    pixels = 255 * (pixels / 255) ** variant['gamma']
                elif method == 'exposure':
                    pixels = pixels * variant['gain']
                elif method == 'contrast':
                    pixels = variant['pivot'] + variant['factor'] * (pixels - variant['pivot'])
                elif method == 'unsharp':
                    blur = cv2.GaussianBlur(pixels, (0, 0), sigmaX=variant['sigma'], sigmaY=variant['sigma'], borderType=cv2.BORDER_REFLECT_101)
                    pixels = pixels + variant['amount'] * (pixels - blur)
                else:
                    raise ValueError('unsupported actual transform')
                expected = np.clip(np.rint(pixels), 0, 255).astype(np.uint8)
            actual = cv2.imread(str(local_path(sample['transformed']['path'])), cv2.IMREAD_COLOR)
            difference = np.abs(expected.astype(np.int16) - actual.astype(np.int16))
            pixel_diagnostics.append({'variant': name, 'frame_index': i, 'mismatched_channels': int(np.count_nonzero(difference)), 'maximum_channel_difference': int(difference.max())})
            check(prefix + ': independent exact transform pixels/native', actual.shape == native_shape and actual.dtype == np.uint8 and np.array_equal(expected, actual))
            gray = cv2.cvtColor(actual, cv2.COLOR_BGR2GRAY)
            measured = sample['photometric_descriptors']
            check(prefix + ': independently recomputed photometric descriptors', close(float(gray.mean()), measured['mean_grayscale_8bit']) and np.array_equal(np.percentile(gray, [1, 50, 99]), measured['grayscale_percentiles_1_50_99']) and close(float(np.mean(gray == 0)), measured['fraction_grayscale_zero']) and close(float(np.mean(gray == 255)), measured['fraction_grayscale_255']) and measured['claim_limits'].startswith('Pixel descriptors only;'))
            annotation = actual.copy()
            for det in row['detections']:
                x1, y1, x2, y2 = det['bbox_xyxy']
                first = (round(x1), round(y1))
                last = (min(1279, round(x2)), min(719, round(y2)))
                cv2.rectangle(annotation, first, last, (0, 220, 0), 2)
                cv2.putText(annotation, f"d{det['detection_index']} {det['class_name']} {det['confidence']:.3f}", (first[0], max(12, first[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 0), 1, cv2.LINE_AA)
            stored_annotation = cv2.imread(str(local_path(sample['annotated']['path'])), cv2.IMREAD_COLOR)
            check(prefix + ': raw detection annotation exact native pixels', stored_annotation.shape == native_shape and np.array_equal(annotation, stored_annotation))
        check(name + ': frame observation totals not traffic/category count', dict(classes) == entry['detection_class_observation_totals'] and close(statistics.mean(confidence), entry['detection_confidence_mean']) and entry['observation_totals_limits'] == 'Frame-level observations; not physical units/counts/quality metrics')
        check(name + ': no additional native transformed/annotated frame outputs', sorted(p.name for p in (run / name).glob('*.png')) == sorted(f'frame_{i:09d}_{kind}.png' for i in indices for kind in ('transformed', 'annotated')))
    check('75 measured native sample rows +5 separately recorded warmups', observed_rows == 75 and actual_warmups == 5)
    diagnostics['transform_pixel_reproduction'] = pixel_diagnostics
    diagnostics['screen_observation_rows'] = observed_rows
    diagnostics['separately_recorded_warmups'] = actual_warmups
    diagnostics['raw_bbox_observations'] = bbox_count
    diagnostics['kaggle_opencv_version'] = report['environment']['opencv_version']
    diagnostics['audit_opencv_version'] = cv2.__version__
    diagnostics['audit_numpy_version'] = np.__version__
    diagnostics['bitwise_reproduction_is_pixels_not_inference_repeatability'] = True
    if check('actual input local copy available for independent video decode', args.video.is_file()):
        check('input bytes independently rehashed', sha(args.video) == config['expected_video_sha256'] and args.video.stat().st_size == report['input_identity']['size_bytes'])
        cap = cv2.VideoCapture(str(args.video))
        sampled = set(indices)
        try:
            check('local video decoder opened', cap.isOpened())
            for i in range(indices[-1] + 1):
                ok, frame = cap.read()
                if not ok:
                    check('native sequential prefix decode completed', False, {'failed_frame': i})
                    break
                if i in sampled:
                    check('independent actual source video pixels frame' + str(i), np.array_equal(frame, source_pixels[i]))
            else:
                check('native sequential prefix decode completed', True)
        finally:
            cap.release()
        diagnostics['independent_video_prefix_frames_decoded'] = indices[-1] + 1
    if check('actual downloaded model asset locally retained outside Git', args.weights.is_file()):
        check('model asset bytes independently rehashed without loading', sha(args.weights) == resource['weights_sha256'] and args.weights.stat().st_size == resource['weights_bytes'])
    old_manifest = read_json(repo / 'docs/evidence/phase_6/20261012T144625_030645Z/retention_manifest.json')
    for row in old_manifest['artifacts']:
        p = repo / row['path']
        check('immutable original Phase6A ' + row['path'], p.is_file() and sha(p) == row['sha256'] and p.stat().st_size == row['size_bytes'])
    failures = [c for c in checks if not c['passed']]
    result = {
        'claim_type': 'ACTUALLY_EXECUTED_INDEPENDENT_RETAINED_SCREEN_ARTIFACT_AUDIT_NOT_MODEL_BENCHMARK',
        'audited_utc': datetime.now(timezone.utc).isoformat(), 'run_id': run.name,
        'method_path': str(Path(__file__).resolve().relative_to(repo)), 'method_sha256': sha(__file__),
        'source_report_sha256': sha(run / 'report.json'), 'model_inference_rerun': False,
        'image_source_or_retained_outputs_mutated': False,
        'checks_run': len(checks), 'checks_passed': len(checks) - len(failures),
        'successful': not failures, 'failures': failures, 'diagnostics': diagnostics,
        'limits': [
            'Artifact correctness and exact saved-pixel/source reproduction are not detector/tracker/counting accuracy.',
            '75 sparse frame predictions and five warmups are not unique vehicles or passages.',
            'Hold-out source prefix discard during sequential decode is not enhancement/inference evaluation.',
            'Kaggle model inference was not repeated by this audit; CUDA resources are retained runtime evidence.',
            'No temporal/reidentification/geometry/counting performance is established by sparse screening.',
        ],
        'checks': checks,
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({k: result[k] for k in ('run_id', 'successful', 'checks_run', 'checks_passed', 'failures')}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == '__main__':
    main()
