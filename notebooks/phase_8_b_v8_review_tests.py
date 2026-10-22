"""P1 source-review adapter contracts; synthetic pixels are not performance data."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import phase_8_b_v4_batch as previous
import phase_8_b_v6_identity as identity
from phase_8_b_v8_review import prepare_reviewed_frames


def digest(data):
    return hashlib.sha256(data).hexdigest()


def observation(track, frame, *, category="motorcycle", x=20):
    return {"frame_index": frame, "track_id": track, "original_detection_index": track,
        "raw_bbox": [x, 20, x+10, 40], "class_name": category,
        "observed": True, "emitted": True, "role": "unknown_person" if category == "person" else "vehicle",
        "unit_id": f"track:{track}", "episode_id": "unreviewed",
        "association_verified": False, "measurement_provenance": "retained_phase_8_detection"}


class ReviewFixture:
    def __init__(self, root):
        self.root = Path(root)
        self.frames = [{"frame_index": frame, "observations": (
            [observation(1, frame), observation(2, frame, x=70)] if frame <= 2
            else [observation(2, frame)] if frame >= 4 else [])} for frame in range(6)]
        self.source = {"video_sha256": "a"*64, "geometry_sha256": "b"*64,
                       "width": 100, "height": 100}
        self.write_cache_and_receipt()

    def write_cache_and_receipt(self):
        rows = [{"frame_index": row["frame_index"], "video_sha256": self.source["video_sha256"],
            "width": 100, "height": 100,
            "detector_input_frame_pixel_sha256": f"{row['frame_index']+1:064x}",
            "emitted_tracks": deepcopy(row["observations"])} for row in self.frames]
        self.cache = self.root / "cache.jsonl.gz"
        self.cache.write_bytes(gzip.compress(("\n".join(json.dumps(r) for r in rows)+"\n").encode(), mtime=0))
        self.source["records_sha256"] = digest(self.cache.read_bytes())
        receipt = {"video_sha256": self.source["video_sha256"],
            "source_records_sha256": self.source["records_sha256"], "images": [
                {"frame_index": r["frame_index"], "verified_decode_pixel_sha256": True,
                 "raw_bgr_pixel_sha256": r["detector_input_frame_pixel_sha256"],
                 "observations": deepcopy(r["emitted_tracks"])} for r in rows]}
        self.receipt = self.root / "synthetic_pixel_receipt.json"
        self.receipt.write_text(json.dumps(receipt))

    def scope(self, track, start, end, *, unit="reviewed:one", family="vehicle"):
        return {"track_id": track, "start_frame": start, "end_frame": end,
            "raw_family": family, "physical_unit_id": unit, "episode_id": "reviewed:episode"}

    def review(self, kind="SAME_VEHICLE", rid="identity", scopes=None, anchors=None):
        scopes = scopes or [self.scope(1, 0, 2), self.scope(2, 4, 5)]
        anchors = [0, 2, 4, 5] if anchors is None else anchors
        return {"review_id": rid, "type": kind, "claim_type": "ADJUDICATED_AI_PIXELS_REVIEW",
            "human_confirmation_status": "NOT_NEWLY_ADJUDICATED_BY_USER",
            "scopes": scopes, "confirmed_frames": anchors,
            "evidence": [{"path": self.receipt.name, "sha256": digest(self.receipt.read_bytes()),
                "frame_index": f, "source_frame_pixel_sha256": f"{f+1:064x}"} for f in anchors]}

    def overlay(self, reviews=None):
        return {"schema_version": "phase8_b_v4_review_overlay_v1",
            "donor_manifest_sha256": previous.donor.DONOR_MANIFEST_SHA256,
            "videos": [{"video_id": "weekday_siang", **self.source,
                        "reviews": [self.review()] if reviews is None else reviews}]}

    def run(self, overlay=None, **kwargs):
        return prepare_reviewed_frames(self.frames, self.overlay() if overlay is None else overlay,
            source_identity=self.source, repo_root=self.root, source_records_path=self.cache,
            frame_count=6, **kwargs)


class P1ReviewContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.f = ReviewFixture(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_same_unit_assignment_is_per_track_interval_not_cross_product(self):
        result = self.f.run()
        for row in result["frames"]:
            for item in row["observations"]:
                red = item["track_id"] == 1 or row["frame_index"] >= 4
                self.assertEqual(item["unit_id"], "reviewed:one" if red else "track:2")
                self.assertEqual(item["association_verified"], red)
        self.assertEqual(result["application_audit"]["applied_measurements"], {"identity": 5})

    def test_split_identity_produces_typed_distinct_proof_without_alias(self):
        split = self.f.review("SPLIT_IDENTITY", "split", [self.f.scope(2, 0, 2, unit="reviewed:two")], [0, 2])
        result = self.f.run(self.f.overlay([self.f.review(), split]))
        blue = result["frames"][0]["observations"][1]
        red = result["frames"][0]["observations"][0]
        self.assertFalse(blue["association_verified"])
        self.assertIsNone(blue["association_id"])
        self.assertTrue(identity._identity_review_proof(blue))
        self.assertTrue(identity._proven_distinct(red, blue, []))

    def test_raw_measurements_and_inputs_are_immutable(self):
        overlay = self.f.overlay()
        snapshot = deepcopy((self.f.frames, overlay))
        result = self.f.run(overlay)
        self.assertEqual((self.f.frames, overlay), snapshot)
        for original, revised in zip(self.f.frames, result["frames"]):
            for before, after in zip(original["observations"], revised["observations"]):
                for key in ("raw_bbox", "class_name", "track_id", "frame_index", "original_detection_index"):
                    self.assertEqual(before[key], after[key])

    def test_machine_branch_rejects_review(self):
        with self.assertRaisesRegex(ValueError, "Machine branch"):
            self.f.run(branch="machine")

    def test_foreign_input_video_is_rejected(self):
        data = self.f.overlay(); data["videos"][0]["video_sha256"] = "f"*64
        with self.assertRaisesRegex(ValueError, "source binding"):
            self.f.run(data)

    def test_cache_byte_change_is_rejected(self):
        self.f.cache.write_bytes(self.f.cache.read_bytes()+b"changed")
        with self.assertRaisesRegex(ValueError, "exact frozen source cache"):
            self.f.run()

    def test_receipt_file_change_is_rejected(self):
        data = self.f.overlay(); self.f.receipt.write_text("{}")
        with self.assertRaises(ValueError):
            self.f.run(data)

    def test_receipt_pixel_claim_must_match_actual_cache(self):
        receipt = json.loads(self.f.receipt.read_text())
        receipt["images"][0]["raw_bgr_pixel_sha256"] = "f"*64
        self.f.receipt.write_text(json.dumps(receipt))
        data = self.f.overlay()
        data["videos"][0]["reviews"][0]["evidence"][0]["source_frame_pixel_sha256"] = "f"*64
        with self.assertRaisesRegex(ValueError, "actual source cache frame"):
            self.f.run(data)

    def test_anchor_raw_box_must_match_cache(self):
        self.f.frames[0]["observations"][0]["raw_bbox"][0] += 1
        with self.assertRaisesRegex(ValueError, "actual source measurement"):
            self.f.run()

    def test_each_identity_scope_needs_own_anchor(self):
        review = self.f.review(anchors=[4, 5])
        with self.assertRaisesRegex(ValueError, "own reviewed source anchor"):
            self.f.run(self.f.overlay([review]))

    def test_anchor_without_actual_target_is_rejected(self):
        review = self.f.review(anchors=[0, 3, 4])
        review["scopes"][0]["end_frame"] = 3
        with self.assertRaisesRegex(ValueError, "no measured target"):
            self.f.run(self.f.overlay([review]))

    def test_overlapping_identity_reviews_rejected(self):
        data = self.f.overlay([self.f.review(), self.f.review("SPLIT_IDENTITY", "other")])
        with self.assertRaisesRegex(ValueError, "Overlapping identity"):
            self.f.run(data)

    def test_person_role_review_is_bounded_and_never_vehicle_anchor(self):
        for row in self.f.frames:
            row["observations"] = [observation(3, row["frame_index"], category="person")]
        self.f.write_cache_and_receipt()
        review = self.f.review("COMPONENT_OF", "rider", [self.f.scope(3, 1, 2, family="person")], [1, 2])
        review["component_of_unit_id"] = "reviewed:parent"
        result = self.f.run(self.f.overlay([review]))
        self.assertEqual([r["observations"][0]["role"] for r in result["frames"]],
                         ["unknown_person", "rider", "rider", "unknown_person", "unknown_person", "unknown_person"])
        self.assertEqual(result["frames"][1]["observations"][0]["class_name"], "person")
        self.assertFalse(identity._identity_review_proof(result["frames"][1]["observations"][0]))

    def test_positive_pedestrian_does_not_implicitly_count(self):
        for row in self.f.frames:
            row["observations"] = [observation(3, row["frame_index"], category="person")]
        self.f.write_cache_and_receipt()
        review = self.f.review("PEDESTRIAN_ROLE", "walk", [self.f.scope(3, 1, 2, family="person")], [1, 2])
        result = self.f.run(self.f.overlay([review]))
        item = result["frames"][1]["observations"][0]
        self.assertEqual(item["role"], "pedestrian")
        self.assertEqual(item["resolved_class_name"], "pedestrian")
        self.assertNotIn("events", result)

    def test_ai_review_is_never_claimed_as_new_human_confirmation(self):
        result = self.f.run()
        ref = result["frames"][0]["observations"][0]["review_refs"][-1]
        self.assertEqual(ref["decision_origin"], "AI_ASSISTED_REVIEW_NOT_NEW_HUMAN_CONFIRMATION")
        self.assertFalse(result["provenance"]["qc_used_as_machine_predictions"])

    def test_user_review_requires_authority(self):
        data = self.f.overlay(); data["videos"][0]["reviews"][0]["claim_type"] = "USER_REVIEW"
        with self.assertRaisesRegex(ValueError, "retained user instruction"):
            self.f.run(data)

    def test_user_review_retains_exact_authority_and_origin(self):
        path = self.f.root / "user_decision.txt"
        path.write_text("Explicit fixture instruction: one physical passage.")
        review = self.f.review(); review["claim_type"] = "USER_REVIEW"
        review["reviewed_decision_authority"] = {"kind": "EXPLICIT_USER_INSTRUCTION",
            "path": path.name, "sha256": digest(path.read_bytes()),
            "exact_supporting_excerpt": "one physical passage"}
        result = self.f.run(self.f.overlay([review]))
        ref = result["frames"][0]["observations"][0]["review_refs"][-1]
        self.assertEqual(ref["claim_type"], "USER_REVIEW")
        self.assertEqual(ref["decision_origin"], "HUMAN_REVIEW")

    def test_ai_mapping_also_guards_attached_user_decision_bytes(self):
        path = self.f.root / "user_decision.txt"
        path.write_text("Physical decision; raw mapping remains AI review.")
        review = self.f.review()
        review["reviewed_decision_authority"] = {"kind": "EXPLICIT_USER_INSTRUCTION",
            "path": path.name, "sha256": digest(path.read_bytes())}
        result = self.f.run(self.f.overlay([review]))
        self.assertTrue(any(row["path"] == str(path) for row in result["guarded_inputs"]))
        path.write_text("Changed authority")
        with self.assertRaisesRegex(ValueError, "authority is missing or differs"):
            self.f.run(self.f.overlay([review]))

    def test_unanchored_or_outside_scope_observation_is_not_applied(self):
        result = self.f.run()
        self.assertNotIn("review_refs", result["frames"][0]["observations"][1])

    def test_repeated_call_is_deterministic(self):
        self.assertEqual(self.f.run(), self.f.run())

    def test_duplicate_raw_track_in_frame_rejected(self):
        self.f.frames[0]["observations"].append(deepcopy(self.f.frames[0]["observations"][0]))
        with self.assertRaisesRegex(ValueError, "Repeated raw track"):
            self.f.run()


if __name__ == "__main__":
    unittest.main(verbosity=2)
