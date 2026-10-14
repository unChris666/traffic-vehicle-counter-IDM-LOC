#!/usr/bin/env python3
"""Package the tested repository notebook and hash-bound minimal sources for Kaggle.

Does not upload, execute, create a kernel or choose scientific parameters.
"""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(repo, destination, *, mode='temporal_raw_selected'):
    repo, destination = Path(repo).resolve(), Path(destination).resolve()
    relative_paths = [
        'notebooks/phase_7_night_helpers.py',
        'notebooks/phase_7_temporal_helpers.py',
        'notebooks/phase_7_temporal_tests.py',
        'notebooks/phase_5_geometry_helpers.py',
        'notebooks/phase_6_identity_resolution_helpers.py',
        'notebooks/07b_night_temporal_comparison.ipynb',
        'docs/evidence/phase_7/config/TOR3-MALAM_temporal_v1.json',
        'docs/evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json',
        'docs/evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json',
        'docs/evidence/phase_7/feedback/N1_review_001.json',
        'docs/evidence/phase_7/selection/TOR3-MALAM_DEV_shortlist_v1.json',
        'docs/evidence/phase_6/option_b_calibration/frozen_thresholds.json',
    ]
    selection = json.loads((repo / 'docs/evidence/phase_7/selection/TOR3-MALAM_DEV_shortlist_v1.json').read_text())
    relative_paths.append('docs/evidence/phase_7/screening/' + selection['source_detection_screen_run_id'] + '/report.json')
    source_files = {}
    for relative in relative_paths:
        data = (repo / relative).read_bytes()
        source_files[relative] = {
            'sha256': sha(data), 'bytes': len(data),
            'gzip_base64': base64.b64encode(gzip.compress(data, mtime=0)).decode('ascii'),
        }
    source_manifest = {key: {name: value[name] for name in ('sha256', 'bytes')} for key, value in source_files.items()}
    binding = sha(json.dumps(source_manifest, sort_keys=True).encode())
    nb = json.loads((repo / 'notebooks/07b_night_temporal_comparison.ipynb').read_text())
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            cell['execution_count'] = None
            cell['outputs'] = []
    bootstrap = '''# Hash-bound minimal source snapshot packaged from the GitHub source checkout.
from pathlib import Path
import base64
import gzip
import hashlib
import json

SOURCE_BUNDLE = json.loads(%r)
BUNDLE_BINDING_SHA256 = %r
REPO_ROOT = Path('/kaggle/working/phase7_temporal_source_snapshot_' + BUNDLE_BINDING_SHA256[:16])
for relative, entry in SOURCE_BUNDLE.items():
    relative_path = Path(relative)
    if relative_path.is_absolute() or '..' in relative_path.parts:
        raise ValueError('Unsafe bundle source path.')
    source_bytes = gzip.decompress(base64.b64decode(entry['gzip_base64']))
    if len(source_bytes) != entry['bytes'] or hashlib.sha256(source_bytes).hexdigest() != entry['sha256']:
        raise ValueError('Packaged source checksum mismatch: ' + relative)
    target = REPO_ROOT / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != source_bytes:
        raise ValueError('Existing source snapshot differs; use a fresh kernel.')
    target.write_bytes(source_bytes)
print('Verified source snapshot:', REPO_ROOT)
''' % (json.dumps(source_files, sort_keys=True), binding)
    nb['cells'] = [
        {'cell_type': 'markdown', 'id': 'phase7-bundle-note', 'metadata': {}, 'source': [
            '# Kaggle Phase7 temporal execution bundle\n',
            'This upload contains a hash-bound minimal source snapshot from the repository.\n',
            'The selected mode is `' + mode + '`. Scientific inputs and settings are unchanged.\n',
            'It does not access or modify the previous traffic-counter notebook.\n',
        ]},
        {'cell_type': 'code', 'id': 'phase7-bundle-bootstrap', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': bootstrap.splitlines(keepends=True)},
    ] + nb['cells']
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n')
    manifest = {
        'claim_type': 'SOURCE_PACKAGING_NOT_EXECUTION', 'mode': mode,
        'source_bundle_binding_sha256': binding,
        'source_files': source_manifest,
        'output': {'path': str(destination), 'sha256': sha(destination.read_bytes()), 'bytes': destination.stat().st_size},
        'parameter_change': None, 'actual_inference_executed': False,
        'holdout_enhancement_or_inference_executed': False, 'holdout_execution_authorized_after_frozen_DEV_selection': True,
    }
    manifest_path = destination.with_suffix('.source_bundle_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=('temporal_raw_selected',), default='temporal_raw_selected')
    args = parser.parse_args()
    print(json.dumps(build(args.repo, args.output, mode=args.mode), indent=2, sort_keys=True))
