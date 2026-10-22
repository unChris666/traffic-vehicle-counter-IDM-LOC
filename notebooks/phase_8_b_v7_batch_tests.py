"""B v7 input/output isolation contracts; no model or real counting replay."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import phase_8_b_v7_batch as batch


class Bv7ReplayGuards(unittest.TestCase):
    def attempt(self, modify=None, *, frame_count=9128, source_override=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = {"schema_version": "phase9_b_v6_user_policy_v1", "timeout_frames": 60,
                "line_margin_half_width_px": 25, "identity": {"frozen": True},
                "execution_branch": "machine", "review_manifest_sha256": "a" * 64,
                "review_overlay_sha256": None}
            base_path = root / batch.previous.POLICY_PATH
            batch._write(base_path, base)
            source = {"video_sha256": "b" * 64, "records_sha256": "c" * 64,
                      "geometry_sha256": "d" * 64}
            baseline_source = {**source, **(source_override or {})}
            batch._write(root / batch.BASELINE_RESULT, {"source_identity": baseline_source})
            policy = batch.build_policy(root)
            if modify:
                modify(policy)
            path = root / batch.POLICY_PATH
            batch._write(path, policy)
            prepared = {"policy": deepcopy(base), "policy_sha256": batch._hash(base_path),
                "guarded_inputs": [], "jobs": [{"metadata": {"frame_count": frame_count},
                "b_v2_source_identity": source}]}
            with patch.object(batch.previous, "prepare_b_v6_batch", return_value=prepared):
                return batch.prepare_b_v7_batch(repo_root=root)

    def test_bound_bv6_policy_and_full_machine_pilot_are_accepted(self):
        prepared = self.attempt()
        self.assertEqual(prepared["policy"]["timeout_frames"], 60)
        self.assertEqual(prepared["policy"]["identity"], {"frozen": True})
        self.assertEqual(prepared["policy"]["v7_handoff"], batch.experimental_handoff_policy())
        self.assertEqual(len(prepared["guarded_inputs"]), 2)

    def test_baseline_configuration_cannot_be_changed(self):
        with self.assertRaisesRegex(ValueError, "frozen B v6"):
            self.attempt(lambda policy: policy.update(timeout_frames=90))

    def test_handoff_configuration_cannot_be_silently_changed(self):
        with self.assertRaisesRegex(ValueError, "explicit handoff"):
            self.attempt(lambda policy: policy["v7_handoff"].update(window_observations=1))

    def test_foreign_bv6_policy_binding_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "frozen B v6"):
            self.attempt(lambda policy: policy.update(base_b_v6_policy_sha256="e" * 64))

    def test_qc_labels_cannot_be_added_to_machine_policy(self):
        with self.assertRaisesRegex(ValueError, "frozen B v6"):
            self.attempt(lambda policy: policy.update(qc_adjudications_used_as_machine_predictions=True))

    def test_cropped_frame_history_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "9128"):
            self.attempt(frame_count=153)

    def test_different_source_or_cache_or_geometry_is_rejected(self):
        for field in ("video_sha256", "records_sha256", "geometry_sha256"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "frozen B v6 comparator"):
                self.attempt(source_override={field: "f" * 64})

    def test_reviewed_branch_or_other_video_is_rejected_before_prepare(self):
        for options in ({"branch": "reviewed"}, {"video_ids": ["weekend_siang"]},
                        {"video_ids": ["weekday_siang", "weekday_malam"]}):
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, "restricted"):
                batch.prepare_b_v7_batch(repo_root=".", **options)

    def output_case(self, root):
        return {"source_run_root": root / "cache", "jobs": [{"video_path": root / "videos/input.mp4"}]}

    def test_output_cannot_enter_historical_results_or_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("b_v1", "b_v5", "b_v6", "b_v7/fixtures", "phase_9", "model_experiments"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "old results"):
                    batch._new_output(root, root / "results" / name, "trial", self.output_case(root))

    def test_output_cannot_enter_frozen_source_or_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("cache", "videos"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "frozen source/cache"):
                    batch._new_output(root, root / name, "trial", self.output_case(root))

    def test_new_output_isolated_but_existing_run_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "results/b_v7/execution/trial"
            actual = batch._new_output(root, "results/b_v7/execution", "trial", self.output_case(root))
            self.assertEqual(actual, expected)
            actual.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "new and outside"):
                batch._new_output(root, "results/b_v7/execution", "trial", self.output_case(root))

    def test_run_id_cannot_escape_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for identifier in ("../old", ".", "..", "", "nested/run", "nested\\run"):
                with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, "Unsafe"):
                    batch._new_output(root, "results/b_v7/execution", identifier, self.output_case(root))


if __name__ == "__main__":
    unittest.main()
