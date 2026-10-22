"""P1 replay isolation and provenance contracts; no model inference."""
from copy import deepcopy
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch

import phase_8_b_v8_batch as batch
from phase_8_b_v7_handoff import experimental_handoff_policy


class P1BatchGuards(unittest.TestCase):
    def attempt(self, change_policy=None, change_overlay=None, change_adjudications=None,
                change_gate=None, source_change=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = {"video_sha256": "a" * 64, "records_sha256": "b" * 64,
                      "geometry_sha256": "c" * 64, "width": 640, "height": 480}
            baseline_source = {**source, **(source_change or {})}
            baseline_path = root / batch.BASELINE_RESULT
            batch._write(baseline_path, {"source_identity": baseline_source, "aggregate": {"total": 72}})
            baseline_hash = batch._hash(baseline_path)
            gate = {"active_candidate_sha256": baseline_hash}
            if change_gate:
                change_gate(gate)
            batch._write(root / batch.BASELINE_GATE, gate)
            base = {"schema_version": "phase9_b_v7_handoff_policy_v1", "timeout_frames": 60,
                "line_margin_half_width_px": 25, "identity": {"frozen": True},
                "v7_handoff": experimental_handoff_policy(), "execution_branch": "machine",
                "review_manifest_sha256": "d" * 64, "review_overlay_sha256": None,
                "qc_adjudications_used_as_machine_predictions": False}
            base_path = root / batch.previous.POLICY_PATH
            batch._write(base_path, base)
            overlay = {"videos": [{"video_id": "weekday_siang", **source, "reviews": []}]}
            adjudications = {"schema_version": "phase9_b_v8_pending_adjudications_v1",
                "baseline_result_sha256": baseline_hash, "source_identity": source,
                "adjudications": []}
            (root / "review-proof.bin").write_bytes(b"synthetic-proof")
            if change_overlay:
                change_overlay(overlay)
            if change_adjudications:
                change_adjudications(adjudications)
            batch._write(root / batch.OVERLAY_PATH, overlay)
            batch._write(root / batch.ADJUDICATIONS_PATH, adjudications)
            policy = batch.build_policy(root)
            if change_policy:
                change_policy(policy)
            batch._write(root / batch.POLICY_PATH, policy)
            prepared = {"policy": deepcopy(base), "policy_sha256": batch._hash(base_path),
                "guarded_inputs": [], "jobs": [{"video_id": "weekday_siang",
                "metadata": {"frame_count": 9128}, "b_v2_source_identity": source}]}
            with patch.object(batch.previous, "prepare_b_v7_batch", return_value=prepared):
                return batch.prepare_b_v8_batch(repo_root=root)

    def test_preserves_machine_controls_and_binds_reviewed_branch_inputs(self):
        result = self.attempt()
        self.assertEqual(result["branch"], "review_assisted")
        self.assertEqual(result["policy"]["timeout_frames"], 60)
        self.assertEqual(result["policy"]["v7_handoff"], experimental_handoff_policy())
        self.assertEqual(result["policy"]["identity"], {"frozen": True})
        self.assertEqual(result["policy"]["v8_review"]["branch"], "review_assisted")
        self.assertIs(result["policy"]["v8_review"]["baseline_is_retained_not_reexecuted"], True)
        self.assertIs(result["policy"]["qc_adjudications_used_as_machine_predictions"], False)
        self.assertEqual(len(result["guarded_inputs"]), 5)

    def test_timer_or_handoff_control_change_is_rejected(self):
        for change in (lambda p: p.update(timeout_frames=90),
                       lambda p: p["v7_handoff"].update(window_observations=1)):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "preserve B v7"):
                self.attempt(change_policy=change)

    def test_foreign_review_manifest_digest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact review manifests"):
            self.attempt(change_policy=lambda p: p["v8_review"].update(overlay_sha256="e" * 64))

    def test_review_data_cannot_be_declared_machine_predictions(self):
        with self.assertRaisesRegex(ValueError, "preserve B v7"):
            self.attempt(change_policy=lambda p: p.update(qc_adjudications_used_as_machine_predictions=True))

    def test_retained_machine_baseline_must_match_its_gate(self):
        with self.assertRaisesRegex(ValueError, "gate binding"):
            self.attempt(change_gate=lambda g: g.update(active_candidate_sha256="f" * 64))

    def test_different_baseline_source_is_rejected(self):
        for key in ("video_sha256", "records_sha256", "geometry_sha256"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "B v7 comparator"):
                self.attempt(source_change={key: "e" * 64})

    def test_pending_adjudications_bind_exact_baseline_result(self):
        with self.assertRaisesRegex(ValueError, "exact B v7 result bytes"):
            self.attempt(change_adjudications=lambda a: a.update(baseline_result_sha256="e" * 64))

    def test_unknown_pending_schema_is_rejected_before_replay(self):
        with self.assertRaisesRegex(ValueError, "Unknown P1"):
            self.attempt(change_adjudications=lambda a: a.update(schema_version="unknown"))

    def test_pending_source_proof_is_bound_and_guarded_before_replay(self):
        proof = {"path": "review-proof.bin",
                 "sha256": hashlib.sha256(b"synthetic-proof").hexdigest()}
        result = self.attempt(change_adjudications=lambda a: a["adjudications"].append(
            {"proof_artifacts": [proof]}))
        self.assertEqual(len(result["guarded_inputs"]), 6)
        self.assertEqual(result["guarded_inputs"][-1]["sha256"], proof["sha256"])

    def test_missing_or_foreign_pending_source_proof_is_rejected(self):
        for proof in ({"path": "missing.jpg", "sha256": "e" * 64},
                      {"path": "review-proof.bin", "sha256": "f" * 64},
                      {"path": "../escape.png", "sha256": "e" * 64}):
            with self.subTest(proof=proof), self.assertRaisesRegex(ValueError, "proof artifact"):
                self.attempt(change_adjudications=lambda a: a["adjudications"].append(
                    {"proof_artifacts": [proof]}))

    def test_review_source_bindings_and_video_selection_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "source binding"):
            self.attempt(change_overlay=lambda o: o["videos"][0].update(video_sha256="f" * 64))
        with self.assertRaisesRegex(ValueError, "exactly the selected"):
            self.attempt(change_overlay=lambda o: o["videos"].append(deepcopy(o["videos"][0])))

    def test_reviewed_replay_cannot_pretend_to_be_machine_branch(self):
        with self.assertRaisesRegex(ValueError, "machine baseline is read-only"):
            batch.prepare_b_v8_batch(repo_root=".", branch="machine")

    def output_case(self, root):
        return {"source_run_root": root / "cache", "jobs": [{"video_path": root / "videos/input.mp4"}]}

    def test_output_cannot_enter_old_results_or_new_fixture_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ("b_v1", "b_v6", "b_v7", "b_v8/fixtures", "b_v8/config", "phase_9"):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "historical results"):
                    batch._new_output(root, root / "results" / path, "trial", self.output_case(root))

    def test_output_cannot_enter_source_or_reuse_previous_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ("cache", "videos"):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "frozen source/cache"):
                    batch._new_output(root, root / path, "trial", self.output_case(root))
            result = batch._new_output(root, "results/b_v8/execution", "trial", self.output_case(root))
            self.assertEqual(result, root / "results/b_v8/execution/trial")
            result.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "new and outside"):
                batch._new_output(root, "results/b_v8/execution", "trial", self.output_case(root))

    def test_run_identifier_must_not_escape_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for identifier in ("../old", "", ".", "..", "nested/run", "nested\\run"):
                with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, "Unsafe"):
                    batch._new_output(root, "results/b_v8/execution", identifier, self.output_case(root))

    def test_namespace_rename_changes_event_references_not_physical_identity(self):
        value = {"events": [{"event_id": "b_v7_example", "physical_unit_id": "unchanged"}],
            "cancelled_events": [], "audit": {"b_v7_example": ["b_v7_example", "unchanged"]}}
        old = deepcopy(value)
        result = batch._rename_event_ids(value)
        self.assertEqual(value, old)
        self.assertEqual(result["events"][0]["event_id"], "b_v8_example")
        self.assertEqual(result["audit"], {"b_v8_example": ["b_v8_example", "unchanged"]})
        self.assertEqual(result["events"][0]["physical_unit_id"], "unchanged")

    def test_decision_provenance_does_not_rewrite_candidate_time_or_source(self):
        value = {"events": [{"event_id": "candidate", "status": "accepted", "decision_frame": 9,
            "evidence": {"source_refs": [{"review_refs": [{"review_id": "new-review"}]}]}}],
            "decisions": [{"status": "pending", "decision_frame": 10, "track_id": 2}]}
        old = deepcopy(value)
        overlay = {"videos": [{"reviews": [{"review_id": "new-review",
            "claim_type": "ADJUDICATED_AI_PIXELS_REVIEW"}]}]}
        batch._decision_provenance(value, overlay, finalization_frame=20, overlay_sha256="a" * 64)
        self.assertEqual(value["events"], old["events"])
        self.assertEqual(value["decisions"], old["decisions"])
        first, second = value["v8_decision_provenance"]
        self.assertEqual(first["decision_origin"], "SOURCE_REVIEW_ASSISTED_REPLAY")
        self.assertEqual(first["candidate_decision_frame"], 9)
        self.assertEqual(first["offline_finalization_frame"], 20)
        self.assertEqual(second["decision_origin"], "REPLAYED_MACHINE_RULES")
        self.assertEqual(second["p1_review_ids"], [])

    def test_runner_orders_review_identity_count_and_finalization_with_separate_baseline(self):
        import phase_8_b_v6_identity as identity
        import phase_8_b_v7_counting as counting
        import phase_8_b_v8_review as review
        import phase_8_b_v8_finalize as finalizer
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            geometry_path = root / "geometry.json"
            batch._write(geometry_path, {"synthetic_test_only": True})
            source = {"width": 640, "height": 480}
            rows = [{"frame_index": frame, "observations": []} for frame in range(9128)]
            baseline = {"aggregate": {"total": 72}}
            controls = {"v7_handoff": experimental_handoff_policy(), "timeout_frames": 60}
            overlay = {"videos": [{"reviews": [{"review_id": "positive-proof",
                "claim_type": "USER_REVIEW"}]}]}
            prepared = {"jobs": [{"video_id": "weekday_siang", "b_v2_source_identity": source,
                "video_path": root / "videos/input.mp4", "b_v2_geometry_path": geometry_path,
                "paths": {"relations": root / "relations.json", "records": root / "records.json.gz"}}],
                "source_run_root": root / "cache", "policy": controls,
                "policy_sha256": "a" * 64, "effective_policy_sha256": "b" * 64,
                "baseline_result_sha256": "c" * 64, "baseline_result_path": root / "baseline.json.gz",
                "baseline_result": baseline, "p1_overlay": overlay, "p1_overlay_sha256": "d" * 64,
                "adjudications": {"synthetic_test_only": True}, "base_reviews": {"weekday_siang": {}},
                "reviews_sha256": "e" * 64, "guarded_inputs": []}
            order = []
            def apply(*args, **kwargs):
                order.append("source_review")
                self.assertEqual(kwargs["source_records_path"], root / "records.json.gz")
                return {"frames": rows, "application_audit": {}, "provenance": {}, "guarded_inputs": []}
            def resolve(*args, **kwargs):
                order.append("identity")
                return {"frames": rows, "assignments": [], "unit_relations": []}
            def replay(*args, **kwargs):
                order.append("counting")
                self.assertEqual(kwargs["policy"]["v7_handoff"], experimental_handoff_policy())
                return {"events": [{"event_id": "b_v7_synthetic", "status": "accepted",
                    "decision_frame": 9, "evidence": {"source_refs": [{"review_refs": [
                        {"review_id": "positive-proof"}]}]}}], "decisions": [], "cancelled_events": [],
                    "aggregate": {"total": 1}, "report": {"last_frame_index": 9127}}
            def finalize(value, manifest, **kwargs):
                order.append("pending_finalization")
                self.assertEqual(kwargs["baseline_result"], baseline)
                self.assertEqual(kwargs["finalization_frame"], 9127)
                self.assertEqual(kwargs["repo_root"], root)
                return value
            adapter = batch.previous.previous.old.previous.previous
            with patch.object(batch, "prepare_b_v8_batch", return_value=prepared), \
                 patch.object(batch, "_snapshot", return_value={}), \
                 patch.object(batch.Geometry, "from_draft", return_value=object()), \
                 patch.object(adapter, "relationship_evidence", return_value={}), \
                 patch.object(adapter, "adapted_frames", return_value=rows), \
                 patch.object(review, "prepare_reviewed_frames", side_effect=apply), \
                 patch.object(identity, "prepare_identity_frames", side_effect=resolve), \
                 patch.object(counting, "replay_frames", side_effect=replay), \
                 patch.object(finalizer, "finalize_reviewed_pending", side_effect=finalize):
                report = batch.run_b_v8_batch(repo_root=root, run_id="synthetic", progress=None)
            self.assertEqual(order, ["source_review", "identity", "counting", "pending_finalization"])
            self.assertFalse(report["machine_baseline_replayed"])
            self.assertFalse(report["qc_adjudications_used_as_machine_predictions"])
            self.assertFalse(report["new_detector_tracker_reid_execution"])
            self.assertTrue(report["inputs_and_sources_unchanged"])
            output = root / "results/b_v8/execution/synthetic"
            result = batch._read(output / "weekday_siang/counting_result.json.gz")
            self.assertEqual(result["events"][0]["event_id"], "b_v8_synthetic")
            self.assertEqual(result["events"][0]["decision_frame"], 9)
            self.assertEqual(result["branch"], "review_assisted")
            self.assertEqual(result["v8_decision_provenance"][0]["offline_finalization_frame"], 9127)
            self.assertEqual(batch._read(output / "baseline_reference.json")["aggregate"], {"total": 72})


if __name__ == "__main__":
    unittest.main()
