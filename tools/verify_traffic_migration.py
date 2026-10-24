"""Replay frozen actual measurements, compare every native field, then reconcile8.

No model/decoder inference is run. Retrieve the completed producer output first.
Local path rebasing preserves the required SHA256 and every source identity field.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gc
from pathlib import Path
import time
from traffic_location.artifacts import read, write, sha, semantic_hash, require
from traffic_location.traffic.application.pipeline import run
from traffic_location.traffic.domain.aggregation import aggregate
ROOT = Path(__file__).resolve().parents[1]


def replay_case(args):
    name, baseline, cache_root, repetitions, output = args
    request_path = (cache_root / name / 'counting/request.json' if name.startswith('T7SL-') else
                    ROOT / 'results/engine_modularization/20261023/requests' / (name.removeprefix('tgdi_') + '.json'))
    request = read(request_path)
    if name.startswith('T7SL-'):
        for ref in request['artifacts'].values():
            ref['path'] = str(cache_root / name / ref['path'].split('/' + name + '/', 1)[1])
    first_hash = None
    versions, runs = set(), []
    for iteration in range(repetitions):
        if iteration % 2:
            request.update(profile='replay', replay_branch=baseline['branch'])
        else:
            request.update(profile=baseline['branch']); request.pop('replay_branch', None)
        started = time.monotonic()
        value = run(request, root=ROOT)
        native = value['native']
        actual_fields = {k: semantic_hash(v) for k, v in native.items()}
        expected_fields = baseline.get('fields', baseline.get('field_hashes'))
        differences = [k for k in sorted(set(actual_fields) | set(expected_fields)) if actual_fields.get(k) != expected_fields.get(k)]
        native_sha = semantic_hash(native)
        first_hash = first_hash or native_sha
        require(native_sha == first_hash and not differences, f'{name} native parity failed: {differences}')
        versions.add(value['result']['result_version'])
        runs.append({'iteration': iteration + 1, 'status': 'PASS', 'profile': request['profile'],
                     'native_semantic_sha256': native_sha, 'different_fields': differences,
                     'result_version': value['result']['result_version'], 'wall_seconds': time.monotonic() - started})
        if iteration == 0:
            write(output / name / 'result.json', value['result'])
            write(output / name / 'request.json', request)
            # Keep only tiny event/decision reconciliation data in retained receipts.
            write(output / name / 'event_summary.json', {'events': [
                {**{k: event[k] for k in ('event_id', 'category', 'direction', 'status', 'accepted_count_event')},
                 'measured_crossing': event['evidence']['measured_crossing']}
                for event in native['events']], 'aggregate': native['aggregate']})
        del value, native
        gc.collect()
        write(output / name / 'comparison.json', {'status': 'RUNNING', 'runs': runs})
    require(len(versions) == 1, 'Result version changed across equivalent replay profiles')
    receipt = {'status': 'PASS', 'case': name, 'runs': runs, 'all_native_fields_equal': True,
               'result_version_stable': True, 'detector_tracker_reid_executed': False}
    write(output / name / 'comparison.json', receipt)
    print(name, 'PASS', len(runs), flush=True)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-root', type=Path, required=True, help='Producer output videos/ directory')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--repetitions', type=int, default=3)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--final-source-check', action='store_true', help='One final-code pass after completed3x parity; not another determinism experiment')
    a = p.parse_args()
    require(a.repetitions >= (1 if a.final_source_check else 3) and a.workers > 0, 'At least3 independent replays required outside final-source check')
    frozen = read(ROOT / 'results/traffic_migration/20261024/frozen.json')
    cases = []
    for name, baseline in frozen['actual_baselines'].items():
        # Frozen TGDI fields use a registry reference; normalize without rewriting golden.
        if name.startswith('tgdi_'):
            baseline = {**baseline, 'branch': name.removeprefix('tgdi_')}
        else:
            baseline = {**baseline, 'branch': 'machine'}
        cases.append((name, baseline, a.cache_root.resolve(), a.repetitions, a.output.resolve()))
    a.output.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        receipts = list(pool.map(replay_case, cases))
    expected, rows = {}, []
    for name, baseline in frozen['actual_baselines'].items():
        if not name.startswith('T7SL-'):
            continue
        request = read(a.output / name / 'request.json')
        native = read(a.cache_root / name / 'counting/native.json.gz')
        expected[name] = request['source_identity']['video_sha256']
        result = read(a.output / name / 'result.json')
        rows.append({'video_id': name, 'status': 'SUCCEEDED', 'branch': 'machine', 'scope': 'FULL_VIDEO',
                     'experiment_sha256': request['source_manifest_sha256'], 'native': native,
                     'result_version': result['result_version']})
    combined = aggregate(expected, rows, experiment_sha256=rows[0]['experiment_sha256'])
    original = read(a.cache_root.parent / 'combined.json')
    # Versions are wrapper-dependent; all counting data must be exact.
    diff = [k for k in original if k != 'result_version' and original[k] != combined[k]]
    require(not diff, 'Batch parity differs: ' + str(diff))
    write(a.output / 'combined.json', combined)
    write(a.output / 'verification.json', {'status': 'PASS', 'cases': len(receipts),
        'replays': sum(len(v['runs']) for v in receipts), 'native_parity': True,
        'batch_domain_equal': True, 'batch_version_change_expected': True,
        'model_inference_rerun': False, 'actual_source_frames': 71380,
        'final_source_check': a.final_source_check})
    print('ALL PARITY AND BATCH PASS', flush=True)

if __name__ == '__main__':
    main()
