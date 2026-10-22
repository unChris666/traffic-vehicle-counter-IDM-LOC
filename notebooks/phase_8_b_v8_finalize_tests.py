"""Reviewed candidate closure safety contracts; not model-quality measurements."""
from copy import deepcopy
import base64
import hashlib
from pathlib import Path
import tempfile
import unittest

from phase_8_b_v8_finalize import (
    REASON, SCHEMA, STATUS, finalize_reviewed_pending,
)


SOURCE = {"video_sha256": "1" * 64, "records_sha256": "2" * 64,
          "geometry_sha256": "3" * 64}


def pending(track, frame):
    return {"frame_index": frame, "track_id": track,
        "physical_unit_id": f"person-track:{track}", "episode_id": "person-context",
        "passage_id": f"person-track:{track}:passage:1", "status": "pending",
        "role": "unknown_person", "reasons": ["PERSON_ROLE_UNRESOLVED"],
        "source_ref": {"frame_index": frame, "track_id": track,
            "original_detection_index": 0, "raw_bbox": [10.0, 10.0, 20.0, 30.0],
            "point": [15.0, 30.0], "class_name": "person", "role": "unknown_person",
            "observed": True, "emitted": True,
            "measurement_provenance": "retained_phase_8_detection"},
        "reason_evidence": [{"reason": "PERSON_ROLE_UNRESOLVED", "frame_index": frame}],
        "latest_frame_index": frame + 10}


def baseline():
    first, second = pending(2, 10), pending(3, 20)
    return {"source_identity": deepcopy(SOURCE), "events": [{"event_id": "b_v7_existing",
        "category": "motorcycle", "evidence": {"measured_crossing": True}}],
        "cancelled_events": [{"event_id": "b_v7_cancelled", "status": "cancelled"}],
        "invalid_decisions": [{"track_id": 9, "status": "invalid", "count_delta": 0}],
        "decisions": [first, second, {"track_id": 9, "status": "invalid"}],
        "passage_log": [{"event_id": "b_v7_existing", "count_delta": 1}],
        "aggregate": {"total": 1, "measured_total": 1, "inferred_total": 0,
            "pending": 2, "invalid": 1},
        "open_passage_diagnostics": [{**{field: first[field] for field in (
            "track_id", "physical_unit_id", "episode_id", "passage_id")},
            "disposition": "ROLE_UNKNOWN", "timeout_eligible": False}],
        "report": {"last_frame_index": 100, "open_passage_diagnostic_counts": {"ROLE_UNKNOWN": 1}}}


class PendingFinalizationContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        image = self.root / "review.png"
        image.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4eQAAAAASUVORK5CYII="))
        self.proof = {"path": image.name, "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}
        self.old = baseline()
        row = self.old["decisions"][0]
        self.review = {"adjudication_id": "review-component-2",
            "baseline_candidate_scope": {field: row[field] for field in (
                "track_id", "physical_unit_id", "episode_id", "passage_id")},
            "baseline_source_ref": deepcopy(row["source_ref"]),
            "reviewed_role": "RIDER_PASSENGER", "reviewer_origin": "AI_PIXELS_REVIEW",
            "source_video_sha256": SOURCE["video_sha256"],
            "records_sha256": SOURCE["records_sha256"],
            "role_scope": {"start_frame": 5, "end_frame": 15},
            "positive_source_frames": [10], "proof_artifacts": [deepcopy(self.proof)],
            "related_vehicle_raw_ids": [], "parent_attribution_status": "UNRESOLVED"}
        self.manifest = {"schema_version": SCHEMA, "baseline_result_sha256": "4" * 64,
            "source_identity": deepcopy(SOURCE), "adjudications": [deepcopy(self.review)]}

    def tearDown(self):
        self.temp.cleanup()

    def run_review(self, result=None, manifest=None, **kwargs):
        return finalize_reviewed_pending(self.old if result is None else result,
            self.manifest if manifest is None else manifest,
            baseline_result=self.old, source_identity=SOURCE, repo_root=self.root, **kwargs)

    def test_positive_component_closes_exact_candidate_plus_zero(self):
        result = self.run_review()
        self.assertEqual(result["aggregate"], {**self.old["aggregate"], "pending": 1})
        closed = result["decisions"][0]
        self.assertEqual(closed["status"], STATUS)
        self.assertEqual(closed["resolution_reason"], REASON)
        self.assertEqual(closed["count_delta"], 0)
        self.assertFalse(closed["accepted_count_event"])
        self.assertEqual(closed["decision_origin"], "AI_ASSISTED_SOURCE_REVIEW")
        self.assertEqual(result["decisions"][1], self.old["decisions"][1])

    def test_geometry_and_old_measurement_role_are_not_rewritten(self):
        result = self.run_review()
        row = result["decisions"][0]
        self.assertEqual(row["source_ref"], self.old["decisions"][0]["source_ref"])
        self.assertEqual(row["role"], "unknown_person")
        self.assertEqual(row["reviewed_role"], "RIDER_PASSENGER")
        self.assertEqual(row["previous_reasons"], ["PERSON_ROLE_UNRESOLVED"])
        self.assertEqual(result["events"], self.old["events"])
        self.assertEqual(result["invalid_decisions"], self.old["invalid_decisions"])
        self.assertEqual(result["cancelled_events"], self.old["cancelled_events"])

    def test_parent_ambiguity_does_not_force_an_identity_alias(self):
        result = self.run_review()
        self.assertNotIn("parent_unit_id", result["decisions"][0])
        audit = result["v8_pending_finalization_audit"][0]
        self.assertFalse(audit["physical_identity_merged"])
        self.assertTrue(audit["not_a_recovered_physical_passage"])

    def test_candidate_and_actual_offline_decision_times_are_separate(self):
        result = self.run_review()
        row, log = result["decisions"][0], result["passage_log"][-1]
        self.assertEqual(row["frame_index"], 10)
        self.assertEqual(row["candidate_decision_frame"], 10)
        self.assertEqual(row["decision_frame"], 100)
        self.assertEqual(log["frame_index"], 100)
        self.assertEqual(sum(item["count_delta"] for item in result["passage_log"]), 1)
        self.assertEqual(result["report"]["open_passage_diagnostic_counts"], {REASON: 1})

    def test_inputs_immutable_and_repeated_result_deterministic(self):
        snapshots = deepcopy((self.old, self.manifest))
        first, second = self.run_review(), self.run_review()
        self.assertEqual(first, second)
        self.assertEqual((self.old, self.manifest), snapshots)

    def test_unknown_or_pedestrian_role_cannot_be_closed_as_component(self):
        for role in ("UNKNOWN", "PEDESTRIAN", "vehicle"):
            with self.subTest(role=role):
                self.manifest["adjudications"][0]["reviewed_role"] = role
                with self.assertRaisesRegex(ValueError, "Only positive"):
                    self.run_review()

    def test_no_accepted_promotion_or_invalid_relabeling(self):
        for status in ("accepted", "invalid"):
            with self.subTest(status=status):
                self.manifest["adjudications"][0]["final_status"] = status
                with self.assertRaisesRegex(ValueError, "cannot promote"):
                    self.run_review()

    def test_source_video_or_cache_mismatch_rejected(self):
        for field in ("source_video_sha256", "records_sha256"):
            with self.subTest(field=field):
                manifest = deepcopy(self.manifest)
                manifest["adjudications"][0][field] = "f" * 64
                with self.assertRaisesRegex(ValueError, "another video/cache"):
                    self.run_review(manifest=manifest)
        manifest = deepcopy(self.manifest)
        manifest["source_identity"]["geometry_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "source identities"):
            self.run_review(manifest=manifest)

    def test_positive_review_frame_must_be_own_candidate_witness(self):
        self.manifest["adjudications"][0]["positive_source_frames"] = [11]
        with self.assertRaisesRegex(ValueError, "exact candidate witness"):
            self.run_review()

    def test_future_or_other_interval_cannot_resolve_candidate(self):
        self.manifest["adjudications"][0]["role_scope"] = {"start_frame": 11, "end_frame": 20}
        with self.assertRaisesRegex(ValueError, "candidate's own source"):
            self.run_review()

    def test_different_source_bbox_or_scope_rejected(self):
        manifest = deepcopy(self.manifest)
        manifest["adjudications"][0]["baseline_source_ref"]["raw_bbox"][0] = 11.0
        with self.assertRaisesRegex(ValueError, "witness differs"):
            self.run_review(manifest=manifest)
        manifest = deepcopy(self.manifest)
        manifest["adjudications"][0]["baseline_candidate_scope"]["episode_id"] = "another-episode"
        with self.assertRaisesRegex(ValueError, "baseline pending"):
            self.run_review(manifest=manifest)

    def test_duplicate_or_conflicting_adjudication_rejected(self):
        self.manifest["adjudications"].append(deepcopy(self.review))
        with self.assertRaisesRegex(ValueError, "Duplicate or conflicting"):
            self.run_review()

    def test_candidate_already_changed_or_resolved_requires_new_review(self):
        candidate = deepcopy(self.old)
        candidate["decisions"][0]["status"] = STATUS
        with self.assertRaisesRegex(ValueError, "no longer pending"):
            self.run_review(result=candidate)
        candidate = deepcopy(self.old)
        candidate["decisions"][0]["role"] = "pedestrian"
        with self.assertRaisesRegex(ValueError, "changed candidate"):
            self.run_review(result=candidate)

    def test_proof_bytes_and_path_binding_verified(self):
        (self.root / "review.png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA256 differs"):
            self.run_review()
        self.manifest["adjudications"][0]["proof_artifacts"][0]["path"] = "../outside.png"
        with self.assertRaisesRegex(ValueError, "missing or outside"):
            self.run_review()

    def test_only_document_proof_is_insufficient_for_pixel_role_review(self):
        path = self.root / "claim.txt"
        path.write_text("Synthetic review claim without source pixels")
        self.manifest["adjudications"][0]["proof_artifacts"] = [
            {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
        with self.assertRaisesRegex(ValueError, "pixel artifact"):
            self.run_review()

    def test_machine_claim_or_unbound_user_claim_rejected(self):
        self.manifest["adjudications"][0]["reviewer_origin"] = "MACHINE"
        with self.assertRaisesRegex(ValueError, "decision origin"):
            self.run_review()
        self.manifest["adjudications"][0]["reviewer_origin"] = "USER_REVIEW"
        with self.assertRaisesRegex(ValueError, "instruction authority"):
            self.run_review()

    def test_cargo_needs_positive_related_vehicle_context(self):
        self.old["decisions"][0]["source_ref"]["class_name"] = "truck"
        review = self.manifest["adjudications"][0]
        review["baseline_source_ref"] = deepcopy(self.old["decisions"][0]["source_ref"])
        review["reviewed_role"] = "CARGO"
        with self.assertRaisesRegex(ValueError, "Cargo exclusion"):
            self.run_review()
        review["related_vehicle_raw_ids"] = [4]
        self.assertEqual(self.run_review()["aggregate"]["pending"], 1)

    def test_pixel_artifact_cannot_impersonate_explicit_user_instruction(self):
        review = self.manifest["adjudications"][0]
        review["reviewer_origin"] = "USER_REVIEW"
        review["reviewed_decision_authority"] = {**self.proof,
            "kind": "EXPLICIT_USER_INSTRUCTION", "exact_supporting_excerpt": "Rider +0"}
        with self.assertRaisesRegex(ValueError, "retained text"):
            self.run_review()

    def test_user_authority_requires_matching_text_excerpt_and_hash(self):
        path = self.root / "user_instruction.txt"
        path.write_text("Synthetic explicit instruction: this candidate is a rider, +0.")
        proof = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        review = self.manifest["adjudications"][0]
        review["reviewer_origin"] = "USER_REVIEW"
        review["proof_artifacts"].append(proof)
        review["reviewed_decision_authority"] = {**proof, "kind": "EXPLICIT_USER_INSTRUCTION",
            "exact_supporting_excerpt": "this candidate is a rider, +0"}
        self.assertEqual(self.run_review()["decisions"][0]["decision_origin"],
                         "EXPLICIT_USER_SOURCE_REVIEW")
        review["reviewed_decision_authority"]["exact_supporting_excerpt"] = "unrecorded assertion"
        with self.assertRaisesRegex(ValueError, "exact authority excerpt"):
            self.run_review()

    def test_no_review_leaves_unknown_pending_and_all_counts_unchanged(self):
        self.manifest["adjudications"] = []
        result = self.run_review()
        self.assertEqual(result["decisions"], self.old["decisions"])
        self.assertEqual(result["aggregate"], self.old["aggregate"])
        self.assertEqual(result["v8_pending_finalization_audit"], [])

    def test_non_eof_finalization_rejected(self):
        with self.assertRaisesRegex(ValueError, "actual source EOF"):
            self.run_review(finalization_frame=99)


if __name__ == "__main__":
    unittest.main()
