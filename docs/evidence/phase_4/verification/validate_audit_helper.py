"""Small software-only audit fixtures, never detector/tracker/encoder execution."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('audit_reid', HERE/'audit_reid.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
checks = []

prior = {'video_sha256': 'fixture', 'tracks': [{'track_id': 7, 'trajectory': [{'frame_index': 3, 'raw_bbox': [1,2,3,4]}]}]}
actual = {**prior, 'variant': 'off', 'tracks': [{'track_id': 7, 'trajectory': [{'frame_index': 3, 'raw_bbox': [1,2,3,4], 'added_field': 'fixture'}]}]}
assert module.project_to_contract(actual, prior) == prior
checks.append('Added fields preserve every original baseline contract key')
for corrupted in [{'video_sha256': 'changed', 'tracks': prior['tracks']},
                  {**prior, 'tracks': [{**prior['tracks'][0], 'track_id': 8}]},
                  {'video_sha256': 'fixture', 'tracks': []}]:
    try:
        projected = module.project_to_contract(corrupted, prior)
        assert projected != prior
    except ValueError:
        pass
checks.append('Changed video, ID, or list cardinality is rejected')

with tempfile.TemporaryDirectory(dir=HERE) as temporary:
    directory = Path(temporary)
    (directory/'prior.json').write_text(json.dumps({**prior, 'run_id': 'old', 'track_id_scope': 'one tracker', 'summary_semantics': 'old wording'}))
    (directory/'new.json').write_text(json.dumps({**actual, 'run_id': 'new', 'track_id_scope': 'one variant', 'summary_semantics': 'new wording'}))
    summary = module.baseline_summary_equivalence(directory/'new.json', directory/'prior.json')
    assert summary['canonical_off_sha256'] == summary['canonical_original_phase3_sha256']
    checks.append('Only run ID/declarative wording is excluded from exact full-track equivalence')
    matrix_motion = np.float32(.52); matrix_actual = np.float32(.1)
    reduction = float(np.abs(matrix_actual-matrix_motion))
    report = {'variant_configurations': {'reid_on': {'track_high_thresh': .25, 'appearance_thresh': .8, 'proximity_thresh': .5}},
              'variants': {'reid_on': {'association_mechanism_diagnostics': {'calls': 1, 'candidate_pairs': 1,
                  'nonempty_feature_association_calls': 1, 'appearance_eligible_pairs': 1,
                  'appearance_changed_cost_pairs': 1, 'calls_with_changed_costs': 1},
                  'embedding_diagnostics': {'encoder_calls': 1, 'finite_nonzero_features_produced': 1,
                  'embedding_dimension': 512, 'encoder_observer_wall_seconds': .005}}}}
    call = {'frame_index': 0, 'track_ids': [7], 'detection_indices': [0], 'matrix_shape': [1,1],
            'candidate_pairs': 1, 'features_present_in_nonempty_association': True,
            'appearance_eligible_pairs': 1, 'appearance_changed_cost_pairs': 1,
            'max_cost_reduction': reduction, 'parent_get_dists_wall_seconds': .001,
            'parent_formula_exact_match': True, 'motion_costs': [[float(matrix_motion)]],
            'actual_costs': [[float(matrix_actual)]], 'appearance_raw_half_cosine': [[float(matrix_actual)]],
            'appearance_gated_costs': [[float(matrix_actual)]]}
    row = {'variant': 'reid_on', 'frame_index': 0, 'encoder_wall_seconds': .005,
           'encoder_calls': [{'feature_count': 1, 'dimensions': [512], 'feature_l2_norms': [1.0],
                              'feature_sha256': ['0'*64], 'encoder_wall_seconds': .005}],
           'association_calls': [call]}
    path = directory/'fixture.jsonl'
    path.write_text(json.dumps(row)+'\n')
    diagnostics = module.audit_appearance_records(path, 'reid_on', [{'detections': [{'confidence': .8}]}], report)
    assert diagnostics['full_retained_association_matrices_recomputed'] == 1
    checks.append('Float32 min/gating/reduction/counters reconcile from fixture JSON')
    call['actual_costs'] = [[.2]]
    path.write_text(json.dumps(row)+'\n')
    try:
        module.audit_appearance_records(path, 'reid_on', [{'detections': [{'confidence': .8}]}], report)
    except ValueError as exc:
        assert 'minimum motion/appearance' in str(exc)
    else:
        raise AssertionError('Corrupted cost matrix accepted')
    checks.append('Corrupted actual appearance-cost matrix is rejected')

result = {'scope': 'Software fixture-only audit helper validation; no detector/tracker/encoder or actual Phase 4 inference.',
          'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
          'audit_method_sha256': module.P3.file_sha256(HERE/'audit_reid.py')}
(HERE/'helper_validation.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
