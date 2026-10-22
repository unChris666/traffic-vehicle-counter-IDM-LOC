"""Input isolation guards for post-QC user policy, not traffic accuracy tests."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import phase_8_b_v6_batch as batch


class UserPolicyGuards(unittest.TestCase):
    def attempt(self, modify=None):
        base = {key: {"value": key} for key in (
            "line_margin_half_width_px", "timeout_frames", "timeout_clock", "category_policy", "p0_counting")}
        base.update(supported_categories=["motorcycle", "car", "truck", "pedestrian"],
                    execution_branch="machine", review_manifest_sha256="a" * 64,
                    review_overlay_sha256=None)
        prepared = {"policy": base, "policy_sha256": "b" * 64, "guarded_inputs": []}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / batch.DECISION_PATH
            document.parent.mkdir(parents=True)
            document.write_text("explicit user decision fixture")
            policy = deepcopy(base)
            policy.update(schema_version="phase9_b_v6_user_policy_v1",
                base_b_v5_policy_sha256="b" * 64,
                decision_document_sha256=batch.old._hash(document),
                supported_categories=base["supported_categories"] + ["bus"],
                qc_adjudications_used_as_machine_predictions=False)
            if modify:
                modify(policy)
            path = root / "policy.json"
            batch.old._write(path, policy)
            with patch.object(batch.old, "prepare_b_v5_batch", return_value=prepared):
                return batch.prepare_b_v6_batch(repo_root=root, policy_path=path)

    def test_explicit_bus_and_frozen_controls_accepted(self):
        result = self.attempt()
        self.assertIn("bus", result["policy"]["supported_categories"])
        self.assertEqual(len(result["guarded_inputs"]), 2)
        self.assertEqual(result["effective_policy_sha256"], batch.old.previous._digest_json(result["policy"]))

    def test_foreign_v5_policy_rejected(self):
        with self.assertRaisesRegex(ValueError, "immutable B v5"):
            self.attempt(lambda p: p.update(base_b_v5_policy_sha256="c" * 64))

    def test_timeout_not_silently_tuned(self):
        with self.assertRaisesRegex(ValueError, "frozen controls"):
            self.attempt(lambda p: p.update(timeout_frames=99))

    def test_other_category_not_silently_added(self):
        with self.assertRaisesRegex(ValueError, "BUS coverage"):
            self.attempt(lambda p: p["supported_categories"].append("bicycle"))

    def test_qc_labels_not_used_as_automatic_predictions(self):
        with self.assertRaisesRegex(ValueError, "machine provenance"):
            self.attempt(lambda p: p.update(qc_adjudications_used_as_machine_predictions=True))

    def test_modified_decision_document_binding_rejected(self):
        with self.assertRaisesRegex(ValueError, "decision binding"):
            self.attempt(lambda p: p.update(decision_document_sha256="e" * 64))


if __name__ == "__main__":
    unittest.main()
