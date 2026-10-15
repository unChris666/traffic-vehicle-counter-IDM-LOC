"""Readiness guards on explicitly synthetic video/geometry fixtures only.

No fixture output is actual dataset evidence, a detector result or a benchmark.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from phase_8_manifest_helpers import (
    SLOT_IDS, describe_issues, discover_videos, geometry_coordinates_sha256,
    make_batch_manifest, make_manifest_from_discovery, parse_confirmed_video_filename,
    sha256_file, validate_manifest,
)


FIXTURE_LABEL = "SYNTHETIC_TEST_FIXTURE_NOT_REAL_DATASET"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def synthetic_batch(root):
    """Eight real small decodable files; business values explicitly fictitious."""
    import cv2
    import numpy as np
    manifest = make_batch_manifest()
    manifest["claim_type"] = FIXTURE_LABEL
    manifest["evidence_kind"] = "SYNTHETIC_TEST_FIXTURE"
    manifest["location"] = {"store_code": "SYNTHETIC", "store_name": "SYNTHETIC TEST LOCATION",
                            "latitude": 0.0, "longitude": 0.0}
    for number, video in enumerate(manifest["videos"]):
        # Deliberately unrelated filenames: explicit slots establish grouping.
        source = root / f"fixture_{number}.avi"
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 5, (32, 24))
        if not writer.isOpened():
            raise RuntimeError("Synthetic OpenCV MJPG writer is unavailable")
        try:
            for frame in range(4):
                image = np.full((24, 32, 3), 10 + number * 20 + frame, dtype=np.uint8)
                image[8:16, 4:12] = (20 + number, 30 + frame, 200 - number)
                writer.write(image)
        finally:
            writer.release()
        capture = cv2.VideoCapture(str(source))
        okay, image = capture.read()
        capture.release()
        if not okay:
            raise RuntimeError("Synthetic fixture failed actual decode")
        picture = root / f"source_{number}.png"
        if not cv2.imwrite(str(picture), image):
            raise RuntimeError("Synthetic PNG write failed")
        digest = sha256_file(source)
        directions = {"A_TO_B": "approaching camera", "B_TO_A": "moving away from camera",
                      "scope": video["slot_id"]}
        geometry = {
            "draft_id": f"SYNTHETIC-{number}", "claim_type": FIXTURE_LABEL,
            "status": "ACCEPTED_PHASE8_SYNTHETIC_TEST_GEOMETRY",
            "geometry_contract_accepted": True, "selected_anchor": "bottom_center",
            "source_video": {"sha256": digest, "filename": source.name},
            "source_frame": {"path": picture.name, "sha256": sha256_file(picture), "frame_index": 0,
                             "width": 32, "height": 24, "coordinate_space": "native_full_frame_pixels"},
            "normalized": {"line": {"P1": [0, .5], "P2": [1, .5]},
                           "side_a_polygon": [[0, 0], [1, 0], [1, .5], [0, .5]],
                           "side_b_polygon": [[0, .5], [1, .5], [1, 1], [0, 1]]},
            "rendered_native_pixels": {"width": 32, "height": 24,
                "line": {"P1": [0, 12], "P2": [32, 12]},
                "side_a_polygon": [[0, 0], [32, 0], [32, 12], [0, 12]],
                "side_b_polygon": [[0, 12], [32, 12], [32, 24], [0, 24]]},
            "confirmed_direction_metadata": directions,
        }
        feedback = {
            "schema_version": "phase8_geometry_review_v1", "claim_type": FIXTURE_LABEL,
            "approved": True, "reviewer": "SYNTHETIC TEST REVIEWER",
            "reviewed_at": "SYNTHETIC TEST TIME (not actual review)",
            "observation": "Synthetic fixture only; no actual road or vehicle observation",
            "source_video_sha256": digest,
            "geometry_coordinates_sha256": geometry_coordinates_sha256(geometry),
            "confirmed_direction_metadata": directions,
            "evidence_frames": [{"path": picture.name, "sha256": sha256_file(picture), "frame_index": 0}],
        }
        review_path = root / f"review_{number}.json"
        write_json(review_path, feedback)
        geometry["approval_feedback"] = {"path": review_path.name, "sha256": sha256_file(review_path)}
        geometry_path = root / f"geometry_{number}.json"
        write_json(geometry_path, geometry)
        video.update(source_path=str(source), source_sha256=digest,
                     observed_metadata={"width": 32, "height": 24, "fps": 5.0, "frame_count": 4},
                     metadata_confirmed=True, geometry_path=geometry_path.name,
                     geometry_sha256=sha256_file(geometry_path), geometry_review_confirmed=True)
    return manifest


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="phase8_synthetic_manifest_")
        cls.root = Path(cls.directory.name)
        cls.base = synthetic_batch(cls.root)
        cls.named_root = cls.root / "SYNTHETIC_confirmed_filename_inputs"
        cls.named_root.mkdir()
        for video in cls.base["videos"]:
            filename = f"TGDI-{video['day_type'].upper()}-{video['recording_period'].upper()}.avi"
            shutil.copyfile(video["source_path"], cls.named_root / filename)
        cls.named_inventory = discover_videos(cls.named_root)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.manifest = copy.deepcopy(self.base)

    def check(self, *, files=True):
        return validate_manifest(self.manifest, self.root, check_files=files)

    def codes(self, result):
        return {row["code"] for row in result["issues"]}

    def geometry_mutation(self, mutation, *, update_review=False):
        # Own copy keeps class-wide immutable fixture inputs intact.
        video = self.manifest["videos"][0]
        geometry = json.loads((self.root / video["geometry_path"]).read_text())
        mutation(geometry)
        geometry_path = self.root / f"mutated_{self.id().split('.')[-1]}.json"
        if update_review:
            feedback = json.loads((self.root / geometry["approval_feedback"]["path"]).read_text())
            feedback["geometry_coordinates_sha256"] = geometry_coordinates_sha256(geometry)
            feedback_path = geometry_path.with_suffix(".review.json")
            write_json(feedback_path, feedback)
            geometry["approval_feedback"] = {"path": feedback_path.name, "sha256": sha256_file(feedback_path)}
        write_json(geometry_path, geometry)
        video["geometry_path"] = geometry_path.name
        video["geometry_sha256"] = sha256_file(geometry_path)

    def location_waiver(self, mutation=None):
        self.manifest["location"].update(store_name=None, latitude=None, longitude=None)
        self.manifest["execution_purpose"] = "RESEARCH_WITH_DECLARED_UNKNOWN_LOCATION"
        review = {
            "schema_version": "phase8_location_metadata_review_v1",
            "claim_type": FIXTURE_LABEL,
            "reviewer": "SYNTHETIC TEST REVIEWER (not an actual user acknowledgement)",
            "reviewed_at": "2026-01-01T00:00:00+00:00",
            "store_code": self.manifest["location"]["store_code"],
            "unknown_fields": ["store_name", "latitude", "longitude"],
            "user_reply": "belum diketahui",
            "authorization": "CONTINUE_RESEARCH_WITH_UNKNOWN_LOCATION_METADATA",
            "source_video_sha256_by_slot": {video["slot_id"]: video["source_sha256"]
                                            for video in self.manifest["videos"]},
        }
        if mutation:
            mutation(review)
        path = self.root / f"{self.id().split('.')[-1]}_SYNTHETIC_location_review.json"
        write_json(path, review)
        self.manifest["location_metadata_review"] = {"path": path.name, "sha256": sha256_file(path)}
        return path

    def test_empty_scaffold_is_honestly_blocked(self):
        result = validate_manifest(make_batch_manifest(), self.root, check_files=False)
        self.assertFalse(result["ready"])
        self.assertEqual(len(result["effective_videos"]), 8)
        self.assertIn("missing_location_latitude", self.codes(result))
        self.assertIn("missing_source_sha256", self.codes(result))

    def test_scaffold_exact_business_grid(self):
        self.assertEqual(tuple(v["slot_id"] for v in make_batch_manifest()["videos"]), SLOT_IDS)

    def test_scaffolds_are_independent(self):
        first, second = make_batch_manifest(), make_batch_manifest()
        first["videos"][0]["observed_metadata"]["width"] = 3
        self.assertIsNone(second["videos"][0]["observed_metadata"]["width"])

    def test_actual_decode_synthetic_fixture_is_ready_but_labelled(self):
        result = self.check()
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["ready"])
        self.assertEqual(result["evidence_kind"], "SYNTHETIC_TEST_FIXTURE")
        self.assertTrue(all(v["verified_source"]["decoded_frame_count"] == 4 for v in result["effective_videos"]))

    def test_check_files_false_never_authorizes_execution(self):
        result = self.check(files=False)
        self.assertFalse(result["ready"])
        self.assertEqual(self.codes(result), {"source_files_not_verified"})

    def test_require_ready_false_preserves_blockers(self):
        result = validate_manifest(make_batch_manifest(), self.root, check_files=False, require_ready=False)
        self.assertFalse(result["ready"])
        self.assertFalse(result["execution_requested"])

    def test_discovery_does_not_infer_filename_metadata(self):
        found = discover_videos(self.named_root)
        self.assertEqual(len(found), 8)
        self.assertTrue(all(v["day_type"] is None and v["recording_period"] is None and v["store_code"] is None for v in found))
        self.assertTrue(all(v["fully_decoded"] is False for v in found))
        self.assertEqual(found[0]["observed_metadata"], {"width": 32, "height": 24, "fps": 5.0, "frame_count": 4})

    def test_confirmed_filename_parser_maps_only_approved_tokens(self):
        self.assertEqual(parse_confirmed_video_filename("TGDI-WEEKEND-MALAM.mp4"),
            {"store_code": "TGDI", "day_type": "weekend", "recording_period": "malam",
             "slot_id": "weekend_malam", "video_id": "weekend_malam"})

    def test_confirmed_filename_parser_token_case_has_no_semantic_effect(self):
        self.assertEqual(parse_confirmed_video_filename("TGDI-weekday-pagi.MP4")["slot_id"], "weekday_pagi")

    def test_confirmed_filename_parser_rejects_legacy_unconfirmed_naming(self):
        for name in ("TOR3-PAGI.mp4", "TGDI-HOLIDAY-PAGI.mp4", "TGDI-WEEKEND-NIGHT.mp4",
                     "TGDI-WEEKEND-MALAM-extra.mp4", "/tmp/TGDI-WEEKEND-MALAM.mp4"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_confirmed_video_filename(name)

    def test_confirmed_filename_builder_positive_is_still_incomplete(self):
        manifest = make_manifest_from_discovery(self.named_inventory)
        manifest["claim_type"] = FIXTURE_LABEL
        manifest["evidence_kind"] = "SYNTHETIC_TEST_FIXTURE"
        self.assertEqual(manifest["location"], {"store_code": "TGDI", "store_name": None,
                                              "latitude": None, "longitude": None})
        self.assertTrue(all(video["metadata_confirmed"] for video in manifest["videos"]))
        self.assertTrue(all(video["geometry_path"] is None and not video["geometry_review_confirmed"] for video in manifest["videos"]))
        self.assertEqual(manifest["filename_mapping_contract"]["claim_type"], "USER_CONFIRMED_FILENAME_CONVENTION")
        self.assertFalse(validate_manifest(manifest, self.root, check_files=False)["ready"])

    def test_confirmed_filename_builder_does_not_modify_discovery(self):
        inventory = copy.deepcopy(self.named_inventory)
        make_manifest_from_discovery(inventory)
        self.assertEqual(inventory, self.named_inventory)

    def test_confirmed_filename_builder_rebases_only_explicit_mount(self):
        manifest = make_manifest_from_discovery(self.named_inventory,
            dataset_root="/kaggle/input/datasets/chrisbiran/tgdi-traffic-videos")
        for video in manifest["videos"]:
            self.assertTrue(video["source_path"].startswith("/kaggle/input/datasets/chrisbiran/tgdi-traffic-videos/TGDI-"))
            self.assertEqual(video["source_sha256"], next(entry["source_sha256"] for entry in self.named_inventory
                if entry["filename"] == Path(video["source_path"]).name))

    def test_confirmed_filename_builder_preserves_explicit_location(self):
        manifest = make_manifest_from_discovery(self.named_inventory,
            location={"store_code": "TGDI", "store_name": "SYNTHETIC LOCATION", "latitude": 0.0, "longitude": 0.0})
        self.assertEqual(manifest["location"]["store_name"], "SYNTHETIC LOCATION")
        self.assertEqual(manifest["location"]["latitude"], 0.0)

    def test_confirmed_filename_builder_rejects_conflicting_location(self):
        with self.assertRaises(ValueError):
            make_manifest_from_discovery(self.named_inventory, location={"store_code": "OTHER"})

    def test_confirmed_filename_builder_rejects_incomplete_batch(self):
        with self.assertRaises(ValueError):
            make_manifest_from_discovery(self.named_inventory[:7])

    def test_confirmed_filename_builder_rejects_duplicate_slot(self):
        inventory = copy.deepcopy(self.named_inventory)
        inventory[1] = inventory[0]
        with self.assertRaises(ValueError):
            make_manifest_from_discovery(inventory)

    def test_confirmed_filename_builder_rejects_duplicate_input_bytes(self):
        inventory = copy.deepcopy(self.named_inventory)
        inventory[1]["source_sha256"] = inventory[0]["source_sha256"]
        with self.assertRaises(ValueError):
            make_manifest_from_discovery(inventory)

    def test_confirmed_filename_builder_rejects_multiple_store_codes(self):
        inventory = copy.deepcopy(self.named_inventory)
        inventory[0]["filename"] = inventory[0]["filename"].replace("TGDI-", "OTHER-")
        inventory[0]["source_path"] = str(self.named_root / inventory[0]["filename"])
        with self.assertRaises(ValueError):
            make_manifest_from_discovery(inventory)

    def test_confirmed_filename_builder_keeps_unavailable_metadata_unknown(self):
        inventory = copy.deepcopy(self.named_inventory)
        inventory[0]["observed_metadata"]["fps"] = None
        manifest = make_manifest_from_discovery(inventory)
        self.assertIsNone(next(video for video in manifest["videos"]
            if video["source_sha256"] == inventory[0]["source_sha256"])["observed_metadata"]["fps"])

    def test_confirmed_filename_builder_requires_measured_source_identity(self):
        inventory = copy.deepcopy(self.named_inventory)
        inventory[0]["source_sha256"] = None
        with self.assertRaises(ValueError):
            make_manifest_from_discovery(inventory)

    def test_confirmed_filename_builder_rejects_relative_path_escape(self):
        inventory = copy.deepcopy(self.named_inventory)
        inventory[0]["relative_path"] = "../" + inventory[0]["filename"]
        with self.assertRaises(ValueError):
            make_manifest_from_discovery(inventory, dataset_root="/kaggle/input/explicit")

    def test_discovery_unavailable_root_raises(self):
        with self.assertRaises(FileNotFoundError):
            discover_videos(self.root / "not_present")

    def test_discovery_invalid_video_keeps_unknown_properties(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "weekday-PAGI.mp4"
            path.write_bytes(b"SYNTHETIC deliberately undecodable file")
            result = discover_videos(temporary)
            self.assertEqual(len(result), 1)
            self.assertTrue(all(v is None for v in result[0]["observed_metadata"].values()))
            self.assertIsNone(result[0]["day_type"])
            self.assertIn("opencv_cannot_open_video", result[0]["metadata_issues"])

    def test_missing_one_video_rejected(self):
        self.manifest["videos"].pop()
        with self.assertRaises(ValueError):
            self.check()

    def test_duplicate_slot_rejected(self):
        self.manifest["videos"][1] = self.manifest["videos"][0]
        with self.assertRaises(ValueError):
            self.check()

    def test_unknown_slot_rejected(self):
        self.manifest["videos"][0]["slot_id"] = "holiday_pagi"
        with self.assertRaises(ValueError):
            self.check()

    def test_malformed_unhashable_slot_raises_valueerror(self):
        self.manifest["videos"][0]["slot_id"] = []
        with self.assertRaises(ValueError):
            self.check()

    def test_grid_metadata_disagreement_rejected(self):
        self.manifest["videos"][0]["day_type"] = "weekend"
        with self.assertRaises(ValueError):
            self.check()

    def test_video_id_disagreement_rejected(self):
        self.manifest["videos"][0]["video_id"] = "invented"
        with self.assertRaises(ValueError):
            self.check()

    def test_second_location_rejected(self):
        self.manifest["videos"][0]["store_code"] = "OTHER"
        with self.assertRaises(ValueError):
            self.check()

    def test_unconfirmed_input_metadata_blocked(self):
        self.manifest["videos"][0]["metadata_confirmed"] = False
        self.assertIn("metadata_confirmed_required", self.codes(self.check()))

    def test_unconfirmed_geometry_blocked(self):
        self.manifest["videos"][0]["geometry_review_confirmed"] = False
        self.assertIn("geometry_review_confirmed_required", self.codes(self.check()))

    def test_empty_metadata_blocked(self):
        self.manifest["videos"][0]["observed_metadata"] = {}
        self.assertIn("missing_observed_frame_count", self.codes(self.check()))

    def test_fake_metadata_count_detected_by_full_decode(self):
        self.manifest["videos"][0]["observed_metadata"]["frame_count"] = 9
        self.assertIn("source_verification_failed", self.codes(self.check()))

    def test_fake_metadata_dimensions_blocked(self):
        self.manifest["videos"][0]["observed_metadata"]["width"] = 33
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))
        self.assertIn("source_verification_failed", self.codes(self.check()))

    def test_fake_metadata_fps_detected(self):
        self.manifest["videos"][0]["observed_metadata"]["fps"] = 25
        self.assertIn("source_verification_failed", self.codes(self.check()))

    def test_duplicate_source_identity_blocked(self):
        self.manifest["videos"][1]["source_sha256"] = self.manifest["videos"][0]["source_sha256"]
        self.assertIn("duplicate_source_sha256", self.codes(self.check()))

    def test_changed_source_sha_blocked(self):
        self.manifest["videos"][0]["source_sha256"] = "0" * 64
        self.assertIn("source_verification_failed", self.codes(self.check()))

    def test_missing_source_file_blocked(self):
        self.manifest["videos"][0]["source_path"] = str(self.root / "missing.avi")
        self.assertIn("source_verification_failed", self.codes(self.check()))

    def test_geometry_source_mismatch_blocked(self):
        self.geometry_mutation(lambda geometry: geometry["source_video"].update(sha256="0" * 64))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_unapproved_despite_manifest_flag_blocked(self):
        self.geometry_mutation(lambda geometry: geometry.update(geometry_contract_accepted=False))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_proposal_status_blocked(self):
        self.geometry_mutation(lambda geometry: geometry.update(status="PROPOSAL"))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_shape_mismatch_blocked(self):
        self.geometry_mutation(lambda geometry: geometry["rendered_native_pixels"].update(width=640))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_source_declared_native_shape_mismatch_blocked(self):
        self.geometry_mutation(lambda geometry: geometry["source_video"].update(native_width=1280))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_new_geometry_cropped_coordinate_space_blocked(self):
        self.geometry_mutation(lambda geometry: geometry["source_frame"].update(coordinate_space="cropped_pixels"),
                               update_review=True)
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_native_coordinate_drift_blocked(self):
        self.geometry_mutation(lambda geometry: geometry["rendered_native_pixels"]["line"]["P1"].__setitem__(1, 13))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_changed_after_review_blocked(self):
        self.geometry_mutation(lambda geometry: geometry.update(draft_id="OTHER"))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_no_traceable_review_blocked(self):
        self.geometry_mutation(lambda geometry: geometry.pop("approval_feedback"))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_wrong_review_hash_blocked(self):
        self.geometry_mutation(lambda geometry: geometry["approval_feedback"].update(sha256="0" * 64))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_direction_mapping_requires_opposite_metadata(self):
        self.geometry_mutation(lambda geometry: geometry["confirmed_direction_metadata"].update(B_TO_A="approaching camera"))
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_geometry_source_png_must_match_video_pixels(self):
        import cv2
        import numpy as np
        fake_path = self.root / "SYNTHETIC_fake_source.png"
        cv2.imwrite(str(fake_path), np.full((24, 32, 3), 244, dtype=np.uint8))
        def mutation(geometry):
            geometry["source_frame"].update(path=fake_path.name, sha256=sha256_file(fake_path))
        self.geometry_mutation(mutation)
        video = self.manifest["videos"][0]
        geometry_path = self.root / video["geometry_path"]
        geometry = json.loads(geometry_path.read_text())
        feedback = json.loads((self.root / geometry["approval_feedback"]["path"]).read_text())
        feedback["geometry_coordinates_sha256"] = geometry_coordinates_sha256(geometry)
        feedback["evidence_frames"] = [{"path": fake_path.name, "sha256": sha256_file(fake_path), "frame_index": 0}]
        feedback_path = geometry_path.with_suffix(".review.json")
        write_json(feedback_path, feedback)
        geometry["approval_feedback"] = {"path": feedback_path.name, "sha256": sha256_file(feedback_path)}
        write_json(geometry_path, geometry)
        video["geometry_sha256"] = sha256_file(geometry_path)
        result = self.check()
        self.assertIn("source_verification_failed", self.codes(result))
        self.assertFalse(result["ready"])

    def test_extra_review_frame_must_also_match_source_pixels(self):
        import cv2
        import numpy as np
        video = self.manifest["videos"][0]
        geometry = json.loads((self.root / video["geometry_path"]).read_text())
        feedback = json.loads((self.root / geometry["approval_feedback"]["path"]).read_text())
        fake_path = self.root / "SYNTHETIC_fake_extra.png"
        cv2.imwrite(str(fake_path), np.full((24, 32, 3), 244, dtype=np.uint8))
        feedback["evidence_frames"].append({"path": fake_path.name, "sha256": sha256_file(fake_path), "frame_index": 1})
        review_path = self.root / "synthetic_wrong_extra_review.json"
        write_json(review_path, feedback)
        geometry["approval_feedback"] = {"path": review_path.name, "sha256": sha256_file(review_path)}
        geometry_path = self.root / "synthetic_wrong_extra_geometry.json"
        write_json(geometry_path, geometry)
        video.update(geometry_path=geometry_path.name, geometry_sha256=sha256_file(geometry_path))
        self.assertIn("source_verification_failed", self.codes(self.check()))

    def test_synthetic_evidence_cannot_be_claimed_actual(self):
        self.manifest["claim_type"] = "ACTUAL_DATASET"
        self.manifest["evidence_kind"] = "ACTUAL_DATASET"
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_evidence_kind_conflict_is_rejected(self):
        self.manifest["evidence_kind"] = "ACTUAL_DATASET"
        with self.assertRaises(ValueError):
            self.check()

    def test_builder_declares_intended_actual_input_kind_without_ready_claim(self):
        manifest = make_manifest_from_discovery(self.named_inventory)
        self.assertEqual(manifest["evidence_kind"], "ACTUAL_DATASET")
        self.assertFalse(validate_manifest(manifest, self.root, check_files=False)["ready"])

    def test_invalid_location_geography_rejected(self):
        self.manifest["location"]["latitude"] = 91
        with self.assertRaises(ValueError):
            self.check()

    def test_no_default_location_when_unknown(self):
        self.manifest["location"]["longitude"] = None
        self.assertIn("missing_location_longitude", self.codes(self.check()))

    def test_research_location_acknowledgement_retains_unknown_facts(self):
        self.location_waiver()
        result = self.check()
        self.assertTrue(result["ready"], result["issues"])
        self.assertFalse(result["business_metadata_complete"])
        self.assertEqual(result["unknown_location_fields"], ["store_name", "latitude", "longitude"])
        self.assertEqual(result["location_metadata_status"], "UNKNOWN_DECLARED_RESEARCH_ONLY")
        self.assertTrue(result["research_only"])
        self.assertTrue(result["research_unknown_location_authorized"])
        for video in result["effective_videos"]:
            self.assertTrue(video["research_only"])
            self.assertFalse(video["business_metadata_complete"])
            self.assertIsNone(video["location"]["store_name"])
            self.assertIsNone(video["location"]["latitude"])
            self.assertIsNone(video["location"]["longitude"])

    def test_research_acknowledgement_does_not_waive_geometry(self):
        self.location_waiver()
        self.manifest["videos"][0]["geometry_review_confirmed"] = False
        self.assertIn("geometry_review_confirmed_required", self.codes(self.check()))

    def test_research_acknowledgement_does_not_waive_source_bytes(self):
        self.location_waiver()
        self.manifest["videos"][0]["source_path"] = str(self.root / "missing.avi")
        self.assertIn("source_verification_failed", self.codes(self.check()))

    def test_unknown_location_without_acknowledgement_stays_blocked(self):
        self.manifest["location"].update(store_name=None, latitude=None, longitude=None)
        result = self.check()
        self.assertFalse(result["ready"])
        self.assertFalse(result["research_only"])
        self.assertIn("missing_location_latitude", self.codes(result))

    def test_research_purpose_alone_does_not_waive_unknown_location(self):
        self.manifest["location"].update(store_name=None, latitude=None, longitude=None)
        self.manifest["execution_purpose"] = "RESEARCH_WITH_DECLARED_UNKNOWN_LOCATION"
        result = self.check()
        self.assertIn("invalid_location_metadata_review", self.codes(result))
        self.assertIn("missing_location_store_name", self.codes(result))

    def test_location_review_without_research_purpose_stays_blocked(self):
        self.location_waiver()
        self.manifest.pop("execution_purpose")
        result = self.check()
        self.assertIn("research_location_waiver_not_authorized", self.codes(result))
        self.assertIn("missing_location_longitude", self.codes(result))

    def test_research_location_review_hash_tamper_is_blocked(self):
        self.location_waiver()
        self.manifest["location_metadata_review"]["sha256"] = "0" * 64
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_changed_bytes_are_blocked(self):
        path = self.location_waiver()
        review = json.loads(path.read_text())
        review["reviewer"] = "CHANGED AFTER BINDING"
        write_json(path, review)
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_store_code_mismatch_is_blocked(self):
        self.location_waiver(lambda review: review.update(store_code="OTHER"))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_cannot_waive_missing_store_code(self):
        self.location_waiver()
        self.manifest["location"]["store_code"] = None
        result = self.check()
        self.assertIn("invalid_location_metadata_review", self.codes(result))
        self.assertIn("missing_location_store_code", self.codes(result))

    def test_research_location_review_unknown_field_subset_is_blocked(self):
        self.location_waiver(lambda review: review.update(unknown_fields=["store_name"]))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_duplicate_unknown_fields_is_blocked(self):
        self.location_waiver(lambda review: review["unknown_fields"].append("latitude"))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_stale_unknown_fields_are_blocked(self):
        self.location_waiver()
        self.manifest["location"]["latitude"] = 0.0
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_invalid_coordinate_is_not_waived(self):
        self.location_waiver()
        self.manifest["location"]["latitude"] = 91
        with self.assertRaises(ValueError):
            self.check()

    def test_research_location_review_missing_authorization_is_blocked(self):
        self.location_waiver(lambda review: review.pop("authorization"))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_unknown_reply_is_retained_exactly(self):
        self.location_waiver(lambda review: review.update(user_reply="unknown guess"))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_source_binding_mismatch_is_blocked(self):
        def mutation(review):
            review["source_video_sha256_by_slot"]["weekday_pagi"] = "0" * 64
        self.location_waiver(mutation)
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_missing_source_binding_is_blocked(self):
        self.location_waiver(lambda review: review.pop("source_video_sha256_by_slot"))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_swapped_slots_are_blocked(self):
        def mutation(review):
            bindings = review["source_video_sha256_by_slot"]
            bindings["weekday_pagi"], bindings["weekend_pagi"] = bindings["weekend_pagi"], bindings["weekday_pagi"]
        self.location_waiver(mutation)
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_actual_location_review_cannot_use_synthetic_claim(self):
        self.location_waiver()
        self.manifest["claim_type"] = "ACTUAL_DATASET"
        self.manifest["evidence_kind"] = "ACTUAL_DATASET"
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_location_review_requires_truthful_claim_for_fixture(self):
        self.location_waiver(lambda review: review.update(claim_type="USER_CONFIRMED_UNKNOWN_LOCATION_METADATA_FOR_RESEARCH"))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_requires_timezone(self):
        self.location_waiver(lambda review: review.update(reviewed_at="2026-01-01T00:00:00"))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_checks_referenced_user_confirmation(self):
        self.location_waiver(lambda review: review.update(source_user_confirmation={
            "path": "missing_SYNTHETIC_user_confirmation.json", "sha256": "0" * 64}))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_research_location_review_referenced_confirmation_wrong_scope_is_blocked(self):
        path = self.root / "SYNTHETIC_wrong_scope_confirmation.json"
        write_json(path, {"claim_type": FIXTURE_LABEL, "store_metadata_reply": "belum diketahui",
                          "source_video_sha256_by_slot": {}})
        self.location_waiver(lambda review: review.update(source_user_confirmation={
            "path": path.name, "sha256": sha256_file(path)}))
        self.assertIn("invalid_location_metadata_review", self.codes(self.check()))

    def test_complete_business_metadata_remains_explicitly_complete(self):
        result = self.check()
        self.assertTrue(result["business_metadata_complete"])
        self.assertEqual(result["unknown_location_fields"], [])
        self.assertFalse(result["research_only"])
        self.assertEqual(result["location_metadata_status"], "COMPLETE")

    def test_nonfinite_metadata_rejected(self):
        self.manifest["videos"][0]["observed_metadata"]["fps"] = float("nan")
        with self.assertRaises(ValueError):
            self.check()

    def test_fractional_frame_count_rejected(self):
        self.manifest["videos"][0]["observed_metadata"]["frame_count"] = 4.1
        with self.assertRaises(ValueError):
            self.check()

    def test_boolean_metadata_rejected(self):
        self.manifest["videos"][0]["observed_metadata"]["width"] = True
        with self.assertRaises(ValueError):
            self.check()

    def test_hash_string_format_rejected(self):
        self.manifest["videos"][0]["source_sha256"] = "not-a-real-sha"
        with self.assertRaises(ValueError):
            self.check()

    def test_path_escape_blocked(self):
        self.manifest["videos"][0]["geometry_path"] = "../external.json"
        self.assertIn("invalid_or_unreviewed_geometry", self.codes(self.check()))

    def test_describe_issues_is_deterministic_and_honest(self):
        result = validate_manifest(make_batch_manifest(), self.root, check_files=False)
        first = describe_issues(result)
        self.assertEqual(first, describe_issues(result))
        self.assertTrue(any("weekday_pagi: missing_source_path" in line for line in first))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ManifestTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"claim_type": "SYNTHETIC_SOFTWARE_VERIFICATION_NOT_REAL_DATASET_RESULT",
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "passed": result.wasSuccessful()}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.report, report)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
