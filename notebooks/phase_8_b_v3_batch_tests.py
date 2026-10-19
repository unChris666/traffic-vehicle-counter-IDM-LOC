"""Transport and source-bound reviewed-episode safeguards; synthetic inputs only."""
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import phase_8_b_v3_batch as batch
from phase_8_b_v2_batch_tests import IDENTITY, POLICY, fixture


def review(kind="SAME_VEHICLE", scopes=None, **extra):
    return {"review_id": "review:test", "type": kind, "claim_type": "USER_REVIEW", "confirmed_frames": [1],
        "physical_unit_id": "physical:test", "episode_id": "reviewed:test", "scopes": scopes or [
            {"track_id": 1, "start_frame": 1, "end_frame": 2, "raw_family": "vehicle"},
            {"track_id": 2, "start_frame": 2, "end_frame": 3, "raw_family": "vehicle"}], **extra}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)
        self.path = self.root / "records.jsonl.gz"

    def tearDown(self):
        self.temporary.cleanup()

    def adapt(self, rows, **kwargs):
        with gzip.open(self.path, "wt") as stream:
            for row in rows: stream.write(json.dumps(row) + "\n")
        return list(batch.adapted_frames(self.path, IDENTITY, len(rows), **kwargs))

    def person(self, frame, track=1):
        row = fixture(frame)
        row["raw_detections"][0].update(class_name="person", class_id=0)
        row["emitted_tracks"][0].update(class_name="person", class_id=0, track_id=track)
        return row

    def test_person_preserved_with_unknown_role_never_automatically_pedestrian(self):
        result = self.adapt([self.person(0)])[0]["observations"][0]
        self.assertEqual(result["role"], "unknown_person")
        self.assertEqual(result["class_name"], "person")
        self.assertNotIn("resolved_class_name", result)

    def test_review_is_window_bound_and_source_fields_unchanged(self):
        rows = [fixture(f) for f in range(4)]
        assignments, proof = [], {}
        out = self.adapt(rows, reviews=[review()], reviews_sha256="a" * 64,
            assignments=assignments, application_proof=proof)
        self.assertEqual(out[0]["observations"][0]["unit_id"], "track:1")
        self.assertEqual(out[1]["observations"][0]["unit_id"], "physical:test")
        self.assertEqual(out[3]["observations"][0]["unit_id"], "track:1")
        self.assertEqual(out[1]["observations"][0]["raw_bbox"], rows[1]["emitted_tracks"][0]["raw_bbox"])
        self.assertEqual(proof["applied_measurements"]["review:test"], 2)
        self.assertTrue(out[1]["observations"][0]["association_verified"])
        self.assertEqual(len(assignments), 4)

    def test_pre_review_raw_id_history_not_merged(self):
        rows = [fixture(f) for f in range(4)]
        for row in rows: row["emitted_tracks"][0]["track_id"] = 2
        out = self.adapt(rows, reviews=[review()])
        self.assertEqual(out[0]["observations"][0]["unit_id"], "track:2")
        self.assertEqual(out[1]["observations"][0]["unit_id"], "track:2")
        self.assertEqual(out[2]["observations"][0]["unit_id"], "physical:test")

    def test_raw_person_alias_is_not_vehicle_anchor(self):
        rows = [self.person(f, track=2) for f in range(4)]
        rows[2] = fixture(2); rows[2]["emitted_tracks"][0]["track_id"] = 2
        out = self.adapt(rows, reviews=[review()])
        self.assertEqual(out[1]["observations"][0]["role"], "unknown_person")
        self.assertEqual(out[1]["observations"][0]["unit_id"], "person-track:2")
        self.assertEqual(out[2]["observations"][0]["role"], "vehicle")

    def test_rider_role_only_explicit_local_person_interval(self):
        r = review("COMPONENT_OF", scopes=[{"track_id": 1, "start_frame": 1, "end_frame": 1,
            "raw_family": "person"}], component_of_unit_id="vehicle:parent")
        rows = [self.person(0), self.person(1), fixture(2)]
        out = self.adapt(rows, reviews=[r])
        self.assertEqual([row["observations"][0]["role"] for row in out], ["unknown_person", "rider", "vehicle"])
        self.assertEqual(out[1]["observations"][0]["component_of_unit_id"], "vehicle:parent")

    def test_positive_pedestrian_role_keeps_own_raw_person_and_separate_episode(self):
        r = review("PEDESTRIAN_ROLE", scopes=[{"track_id": 1, "start_frame": 1, "end_frame": 1,
            "raw_family": "person"}])
        out = self.adapt([self.person(f) for f in range(3)], reviews=[r])
        self.assertEqual(out[1]["observations"][0]["class_name"], "person")
        self.assertEqual(out[1]["observations"][0]["resolved_class_name"], "pedestrian")
        self.assertNotEqual(out[0]["observations"][0]["episode_id"], out[1]["observations"][0]["episode_id"])
        self.assertEqual(out[2]["observations"][0]["role"], "unknown_person")

    def test_review_clears_exact_ambiguous_pair_but_not_competitor(self):
        relations = {"identity_pairs_by_frame": {1: [(1, 2), (1, 3)]}}
        local_review = review(); local_review["scopes"][1]["start_frame"] = 1
        out = self.adapt([fixture(0), fixture(1)], relationships=relations, reviews=[local_review])
        self.assertTrue(out[1]["observations"][0]["identity_conflict"])
        relations["identity_pairs_by_frame"][1] = [(1, 2)]
        out = self.adapt([fixture(0), fixture(1)], relationships=relations, reviews=[local_review])
        self.assertFalse(out[1]["observations"][0]["identity_conflict"])

    def test_pair_clear_requires_both_members_active_not_envelope(self):
        r = review(scopes=[{"track_id": 73, "start_frame": 139, "end_frame": 372, "raw_family": "vehicle"},
            {"track_id": 93, "start_frame": 221, "end_frame": 224, "raw_family": "vehicle"}])
        self.assertFalse(batch._same_reviewed_pair([r], (73, 93), 200))
        self.assertTrue(batch._same_reviewed_pair([r], (73, 93), 221))

    def test_category_correction_does_not_relabel_raw_source(self):
        r = review("SPLIT_IDENTITY", resolved_class_name="truck")
        out = self.adapt([fixture(0), fixture(1)], reviews=[r])[1]["observations"][0]
        self.assertEqual(out["class_name"], "car")
        self.assertEqual(out["resolved_class_name"], "truck")
        self.assertFalse(out["association_verified"])

    def test_source_link_corruption_rejected(self):
        row = fixture(0); row["emitted_tracks"][0]["raw_bbox"] = [1, 2, 3, 4]
        with self.assertRaisesRegex(ValueError, "original detection"):
            self.adapt([row])

    def test_foreign_identity_rejected(self):
        row = fixture(0); row["video_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "identity"):
            self.adapt([row])

    def test_empty_frames_preserved_and_no_fake_eof(self):
        row = fixture(1); row.update(raw_detections=[], emitted_tracks=[])
        out = self.adapt([fixture(0), row, fixture(2)])
        self.assertEqual([x["frame_index"] for x in out], [0, 1, 2]); self.assertEqual(out[1]["observations"], [])

    def test_unmatched_review_scope_fails_instead_of_claiming_applied(self):
        with self.assertRaisesRegex(ValueError, "did not match"):
            self.adapt([fixture(0)], reviews=[review()])

    def test_omitted_frame_rejected(self):
        with self.assertRaisesRegex(ValueError, "continuous"):
            self.adapt([fixture(0), fixture(2)])

    def test_pending_dedup_and_reason_union(self):
        decisions = [{"status": "pending", "physical_unit_id": "u", "episode_id": "e", "passage_id": "p",
            "reasons": [reason], "source_ref": {"track_id": 1}} for reason in
            ("CATEGORY_ENDPOINT_CONFLICT", "NO_VALID_FINITE_LINE_OR_OCCLUSION_EVIDENCE")]
        out = batch.pending_groups({"decisions": decisions})
        self.assertEqual(out["unique_unit_episode_passages"], 1)
        self.assertEqual(out["cases"][0]["case_groups"], ["CATEGORY_CONFLICT", "CROSSING_EVIDENCE"])

    def duplicate(self, frame, x=20, tracks=(1, 2)):
        row = fixture(frame, x)
        for track in tracks[1:]:
            row["raw_detections"].append(deepcopy(row["raw_detections"][0]))
            observation = deepcopy(row["emitted_tracks"][0])
            observation.update(track_id=track, original_detection_index=len(row["raw_detections"]) - 1)
            row["emitted_tracks"].append(observation)
        return row

    def local_links(self):
        return {"unit_by_track": {1: "retained-clique:1,2", 2: "retained-clique:1,2"},
            "supported_pairs_by_frame": {1: [(1, 2)]},
            "supported_relation_ids_by_frame": {1: {(1, 2): ["relation:positive"]}}}

    def test_positive_retained_pair_verified_only_exact_support_frame(self):
        out = self.adapt([self.duplicate(frame) for frame in range(3)], relationships=self.local_links())
        self.assertEqual([[o["association_verified"] for o in row["observations"]] for row in out],
            [[False, False], [True, True], [False, False]])
        middle = out[1]["observations"]
        self.assertEqual(middle[0]["association_id"], middle[1]["association_id"])
        self.assertEqual(middle[0]["source_ref"]["retained_same_vehicle_association"]["relation_ids"],
            ["relation:positive"])

    def test_unresolved_pair_remains_conflicted_despite_positive_support(self):
        links = self.local_links(); links["identity_pairs_by_frame"] = {1: [(1, 2)]}
        out = self.adapt([self.duplicate(0), self.duplicate(1)], relationships=links)
        self.assertTrue(all(o["identity_conflict"] and not o["association_verified"]
            for o in out[1]["observations"]))

    def test_chain_support_cannot_verify_three_member_clique(self):
        links = self.local_links(); links["unit_by_track"][3] = "retained-clique:1,2"
        links["supported_pairs_by_frame"][1] = [(1, 2), (2, 3)]
        out = self.adapt([self.duplicate(0, tracks=(1, 2, 3)), self.duplicate(1, tracks=(1, 2, 3))], relationships=links)
        self.assertTrue(all(not o["association_verified"] for o in out[1]["observations"]))

    def test_overlapping_separate_units_are_not_verified_or_merged(self):
        links = self.local_links(); links["unit_by_track"] = {1: "unit:one", 2: "unit:two"}
        out = self.adapt([self.duplicate(0), self.duplicate(1)], relationships=links)
        self.assertEqual([o["unit_id"] for o in out[1]["observations"]], ["unit:one", "unit:two"])
        self.assertTrue(all(not o["association_verified"] for o in out[1]["observations"]))

    def test_exact_local_supported_clique_reaches_counting_core_once(self):
        import phase_8_b_v3_counting as counting
        from phase_5_geometry_helpers import Geometry
        geo_path = self.root / "geometry.json"
        batch._write(geo_path, {"normalized": {"line": {"P1": [.5, 0], "P2": [.5, 1]},
            "side_a_polygon": [[0, 0], [.4, 0], [.4, 1], [0, 1]],
            "side_b_polygon": [[.6, 0], [1, 0], [1, 1], [.6, 1]]}})
        geometry = Geometry.from_draft(geo_path, 100, 100)
        links = self.local_links(); links["supported_pairs_by_frame"] = {f: [(1, 2)] for f in range(3)}
        frames = self.adapt([self.duplicate(f, x) for f, x in enumerate((20, 50, 80))], relationships=links)
        result = counting.replay_frames(frames, geometry, source_identity=IDENTITY, policy=POLICY)
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["aggregate"]["measured_total"], 1)


class ReviewValidatorTests(unittest.TestCase):
    def value(self):
        return {"schema_version": "phase8_b_v3_review_decisions_v1",
            "donor_manifest_sha256": batch.donor.DONOR_MANIFEST_SHA256,
            "videos": [{"video_id": video, **{k: IDENTITY[k] for k in
                ("video_sha256", "records_sha256", "geometry_sha256")},
                "reviews": [review()] if video == "weekday_pagi" else []} for video in batch.donor.VIDEO_IDS]}

    def jobs(self):
        return [{"video_id": "weekday_pagi", "b_v2_source_identity": IDENTITY, "metadata": {"frame_count": 10}}]

    def test_all_eight_bindings_with_only_selected_video_reviewed(self):
        self.assertEqual(len(batch.validate_reviews(self.value(), self.jobs())), 8)

    def test_foreign_source_review_rejected(self):
        value = self.value(); value["videos"][0]["records_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "binding"):
            batch.validate_reviews(value, self.jobs())

    def test_unbounded_or_overlapping_review_rejected(self):
        value = self.value(); value["videos"][0]["reviews"][0]["scopes"][0]["end_frame"] = 10
        with self.assertRaisesRegex(ValueError, "scope"):
            batch.validate_reviews(value, self.jobs())
        value = self.value(); value["videos"][0]["reviews"].append({**review(), "review_id": "second"})
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            batch.validate_reviews(value, self.jobs())

    def test_ai_automatic_identity_claim_rejected(self):
        value = self.value(); value["videos"][0]["reviews"][0]["claim_type"] = "AI_ASSISTED_PIXELS_REVIEW"
        with self.assertRaisesRegex(ValueError, "anchors"):
            batch.validate_reviews(value, self.jobs())

    def test_relative_repository_root_resolves_before_all_artifact_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            evidence_path = root / "results/b_v3/review/proof.json"
            batch._write(evidence_path, {"video_sha256": IDENTITY["video_sha256"],
                "source_records_sha256": IDENTITY["records_sha256"], "images": [{"frame_index": 1,
                    "verified_decode_pixel_sha256": True, "raw_bgr_pixel_sha256": "a" * 64,
                    "observations": []}]})
            baseline_path = root / "results/b_v3/input/baseline.json"
            batch._write(baseline_path, {"frames_processed": 72590, "operational_total": 3717, "per_video": []})
            value = self.value()
            value["b_v2_baseline_reference"] = {"path": baseline_path.relative_to(root).as_posix(),
                "sha256": batch.donor.sha256_file(baseline_path)}
            value["videos"][0]["reviews"] = [review("PEDESTRIAN_ROLE",
                scopes=[{"track_id": 1, "start_frame": 1, "end_frame": 2, "raw_family": "person"}],
                claim_type="AI_ASSISTED_PIXELS_REVIEW", evidence=[{
                    "path": evidence_path.relative_to(root).as_posix(),
                    "sha256": batch.donor.sha256_file(evidence_path), "frame_index": 1,
                    "source_frame_pixel_sha256": "a" * 64}])]
            batch._write(root / batch.REVIEWS, value)
            batch._write(root / "results/b_v3/config/policy.json", {**POLICY,
                "base_b_v2_policy_sha256": "b" * 64})
            donor_prepared = {"jobs": self.jobs(), "policy_sha256": "b" * 64, "policy": POLICY}
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.object(batch.baseline, "prepare_b_v2_batch", return_value=donor_prepared) as prepare:
                    result = batch.prepare_b_v3_batch(repo_root=".")
                self.assertEqual(result["reviews_path"], root / batch.REVIEWS)
                self.assertEqual(prepare.call_args.kwargs["repo_root"], root)
                self.assertTrue(result["reviews"]["weekday_pagi"]["reviews"][0]["_pixel_anchor_proofs"])
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main(verbosity=2)
