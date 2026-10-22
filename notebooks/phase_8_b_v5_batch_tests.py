"""Input protection for the P0 research replay, not counting accuracy tests."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import phase_8_b_v5_batch as batch


class P0BatchGuards(unittest.TestCase):
    def prepared(self):
        policy = {key: {"value": key} for key in batch.FROZEN_KEYS}
        policy.update(execution_branch="machine", review_manifest_sha256="a" * 64,
                      review_overlay_sha256=None)
        return {"policy": policy, "policy_sha256": "b" * 64,
                "guarded_inputs": []}

    def attempt(self, modify=None):
        prepared = self.prepared()
        policy = deepcopy(prepared["policy"])
        policy.update(schema_version="phase8_b_v5_p0_policy_v1",
                      base_b_v4_policy_sha256="b" * 64,
                      qc_adjudications_used_as_machine_predictions=False)
        if modify:
            modify(policy)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            batch._write(path, policy)
            with patch.object(batch.previous, "prepare_b_v4_batch", return_value=prepared):
                return batch.prepare_b_v5_batch(repo_root=directory, policy_path=path)

    def test_unchanged_counting_controls_and_explicit_policy_accepted(self):
        result = self.attempt()
        self.assertEqual(result["policy"]["execution_branch"], "machine")
        self.assertEqual(len(result["guarded_inputs"]), 1)

    def test_foreign_baseline_policy_rejected(self):
        with self.assertRaisesRegex(ValueError, "immutable B v4"):
            self.attempt(lambda policy: policy.update(base_b_v4_policy_sha256="c" * 64))

    def test_geometry_or_timer_cannot_change_silently(self):
        with self.assertRaisesRegex(ValueError, "frozen"):
            self.attempt(lambda policy: policy.update(timeout_frames=99))

    def test_qc_adjudication_cannot_be_machine_prediction(self):
        with self.assertRaisesRegex(ValueError, "automatic inference"):
            self.attempt(lambda policy: policy.update(qc_adjudications_used_as_machine_predictions=True))

    def test_compressed_result_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.json.gz"
            data = {"evidence": [{"frame_index": 3, "raw_bbox": [1, 2, 3, 4]}]}
            batch._write(path, data)
            self.assertEqual(batch._read(path), data)


if __name__ == "__main__":
    unittest.main()
