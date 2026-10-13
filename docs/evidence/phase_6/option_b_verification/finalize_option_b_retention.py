#!/usr/bin/env python3
"""Hash retained Option B outputs and check source/document preservation.

No detector, tracker, encoder, video decoder, geometry state machine or
identity resolver runs here. Original execution manifests are read-only.
"""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[4]
RUN = REPO / 'docs/evidence/phase_6/20261013T104301_354775Z'
MANIFEST = RUN / 'retention_manifest.json'
VALIDATION = RUN / 'final_retention_validation.json'
ROOTS = [
    'docs/evidence/phase_6/20261013T103406_717807Z',
    'docs/evidence/phase_6/20261013T104301_354775Z',
    'docs/evidence/phase_6/option_b_a_updated_20261013',
    'docs/evidence/phase_6/option_b_calibration',
    'docs/evidence/phase_6/option_b_temporal_review',
    'docs/evidence/phase_6/option_b_verification',
]
FILES = [
    'AGENTS.md', 'README.md', 'docs/API_CONTRACT.md', 'docs/ARCHITECTURE.md',
    'docs/CONFIG_SCHEMA.md', 'docs/COUNTING_LOGIC.md', 'docs/MODEL_SPEC.md',
    'docs/OPEN_DECISIONS.md', 'docs/PROJECT_CONTEXT.md', 'docs/TEST_PLAN.md',
    'docs/PHASE_6_OPTION_B_PROPOSAL.md', 'docs/PHASE_6_OPTION_B_TASK.md',
    'docs/PHASE_6_OPTION_B_REVIEW.md',
    'docs/evidence/phase_6/config/TOR3-PAGI_option_b_v0.json',
    'docs/evidence/phase_6/config/TOR3-PAGI_option_b_v1.json',
    'docs/evidence/phase_6/reviews/TOR3-PAGI_option_a_updated_20261013.json',
    'docs/evidence/phase_6/reviews/TOR3-PAGI_option_b_v1_reviewed.json',
    'docs/evidence/phase_6/verification/build_option_b_temporal_review.py',
    'docs/evidence/phase_6/verification/check_option_b_artifacts.py',
    'notebooks/06b_identity_resolution_comparison.ipynb',
    'notebooks/phase_6_identity_resolution_helpers.py',
    'notebooks/phase_6_identity_resolution_tests.py',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = []

    def check(name, success, detail=None):
        row = {'check': name, 'pass': bool(success)}
        if detail is not None:
            row['detail'] = detail
        checks.append(row)

    paths = {REPO / p for p in FILES}
    for root in ROOTS:
        paths.update(p for p in (REPO / root).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc')
    paths -= {MANIFEST, VALIDATION}
    paths = sorted(paths)
    check('no_source_video_in_retained_scope', not any(p.suffix.lower() in
          {'.mp4', '.avi', '.mov', '.mkv', '.webm'} for p in paths))
    check('all_retained_files_exist', all(p.is_file() for p in paths))
    old = json.loads((REPO / 'docs/evidence/phase_6/20261012T144625_030645Z/retention_manifest.json').read_text())
    for item in old['artifacts']:
        p = REPO / item['path']
        check('original_A_immutable:' + item['path'], p.stat().st_size == item['size_bytes']
              and sha(p) == item['sha256'])
    for p in paths:
        relative = str(p.relative_to(REPO))
        if p.suffix == '.py':
            ast.parse(p.read_text())
            check('python_parse:' + relative, True)
        if p.suffix in {'.json', '.ipynb'}:
            json.loads(p.read_text())
            check('json_parse:' + relative, True)
        if p.suffix == '.md':
            for target in re.findall(r'\]\(([^)]+)\)', p.read_text()):
                if '://' in target or target.startswith('#'):
                    continue
                target = target.split('#', 1)[0].strip('<>')
                check('markdown_link:' + relative + ':' + target,
                      (p.parent / target).exists())
    source = json.loads((RUN / 'source_code_sha256.json').read_text())
    for label, name, archive in [
        ('identity_resolution_helper', 'notebooks/phase_6_identity_resolution_helpers.py',
         'phase_6_identity_resolution_helpers.executed_source.py.gz'),
        ('identity_resolution_tests', 'notebooks/phase_6_identity_resolution_tests.py',
         'phase_6_identity_resolution_tests.executed_source.py.gz'),
        ('repository_notebook_source', 'notebooks/06b_identity_resolution_comparison.ipynb',
         '06b_identity_resolution_comparison.original_source.ipynb.gz'),
    ]:
        check('frozen_source_matches_executed:' + label, sha(REPO / name) == source[label]
              and gzip.decompress((RUN / archive).read_bytes()) == (REPO / name).read_bytes())
    nb = json.loads((REPO / 'notebooks/06b_identity_resolution_comparison.ipynb').read_text())
    check('source_notebook_outputs_empty', all(not c.get('outputs') and
          c.get('execution_count') is None for c in nb['cells'] if c['cell_type'] == 'code'))
    executed = json.loads(gzip.decompress((RUN / '06b_identity_resolution_comparison.executed.ipynb.gz').read_bytes()))
    check('executed_notebook_no_error_outputs', all(o.get('output_type') != 'error'
          for c in executed['cells'] for o in c.get('outputs', [])))
    manifest = {'claim_type': 'POST_EXECUTION_OPTION_B_RETENTION_NOT_MODEL_METRICS',
                'run_id': RUN.name, 'original_A_retention_artifacts_unchanged': len(old['artifacts']),
                'original_video_included': False,
                'artifacts': [{'path': str(p.relative_to(REPO)), 'sha256': sha(p),
                               'size_bytes': p.stat().st_size} for p in paths]}
    manifest['artifact_count'] = len(paths)
    manifest['total_bytes'] = sum(a['size_bytes'] for a in manifest['artifacts'])
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    for item in manifest['artifacts']:
        check('final_retained_hash:' + item['path'], sha(REPO / item['path']) == item['sha256'])
    result = {'claim_type': 'ACTUALLY_EXECUTED_RETENTION_SOURCE_DOC_CHECKS_NOT_ACCURACY',
              'passed': sum(c['pass'] for c in checks), 'failed': sum(not c['pass'] for c in checks),
              'artifact_count': len(paths), 'manifest_sha256': sha(MANIFEST),
              'pipeline_or_video_rerun': False, 'checks': checks}
    VALIDATION.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}))
    if result['failed']:
        raise SystemExit('Retention checks failed; inspect final_retention_validation.json')


if __name__ == '__main__':
    main()
