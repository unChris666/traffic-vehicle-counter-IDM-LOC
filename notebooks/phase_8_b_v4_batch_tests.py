"""Source-bound B v4 transport/provenance safeguards; no model execution."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import phase_8_b_v4_batch as batch
from phase_8_b_v2_batch_tests import IDENTITY, POLICY


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        receipt = self.root / "results/phase_9/pilot/evidence/source_pixel_checks.json"
        image = receipt.parent / "frame-000001.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"bound image file; native receipt already records the pixel hash")
        batch._write(receipt, {"source_sha256": IDENTITY["video_sha256"],
            "retained_cache_file_sha256": IDENTITY["records_sha256"], "checks": [{
                "frame_index": 1, "status": "PASS", "actual_bgr_pixel_sha256": "a" * 64,
                "expected_retained_detector_input_pixel_sha256": "a" * 64,
                "retained_native_png_path": "evidence/frame-000001.png",
                "sequentially_decoded_native_png_sha256": batch.donor.sha256_file(image)}]})
        self.receipt = receipt
        self.review = {"review_id": "adjudicated:positive", "type": "PEDESTRIAN_ROLE",
            "claim_type": "ADJUDICATED_AI_PIXELS_REVIEW",
            "human_confirmation_status": "NOT_NEWLY_ADJUDICATED_BY_USER", "confirmed_frames": [1],
            "physical_unit_id": "bounded:person", "episode_id": "bounded:role", "scopes": [
                {"track_id": 54, "start_frame": 1, "end_frame": 2, "raw_family": "person"}],
            "evidence": [{"path": receipt.relative_to(self.root).as_posix(),
                "sha256": batch.donor.sha256_file(receipt), "frame_index": 1,
                "source_frame_pixel_sha256": "a" * 64}]}

    def tearDown(self):
        self.temp.cleanup()

    def value(self):
        return {"schema_version": "phase8_b_v4_review_overlay_v1",
            "donor_manifest_sha256": batch.donor.DONOR_MANIFEST_SHA256,
            "videos": [{"video_id": "weekday_siang", **{key: IDENTITY[key] for key in
                ("video_sha256", "records_sha256", "geometry_sha256")}, "reviews": [deepcopy(self.review)]}]}

    def jobs(self):
        return [{"video_id": "weekday_siang", "b_v2_source_identity": IDENTITY,
            "metadata": {"frame_count": 10}}]

    def validate(self, value=None):
        guard = []
        result = batch.validate_overlay(value or self.value(), self.jobs(), self.root, guard)
        return result, guard

    def test_bounded_adjudication_has_native_anchor_and_guarded_images(self):
        result, guard = self.validate()
        review = result["weekday_siang"]["reviews"][0]
        self.assertEqual(review["claim_type"], "ADJUDICATED_AI_PIXELS_REVIEW")
        self.assertEqual(review["_pixel_anchor_proofs"][1]["raw_bgr_pixel_sha256"], "a" * 64)
        self.assertEqual(len(guard), 2)
        self.assertEqual(review["scopes"][0]["end_frame"], 2)

    def test_changed_bound_receipt_rejected(self):
        value = self.value()
        self.receipt.write_text("{}")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            self.validate(value)

    def test_changed_native_image_rejected(self):
        (self.receipt.parent / "frame-000001.png").write_bytes(b"different image")
        with self.assertRaisesRegex(ValueError, "image bytes"):
            self.validate()

    def test_foreign_video_or_cache_rejected(self):
        for key in ("video_sha256", "records_sha256", "geometry_sha256"):
            value = self.value()
            value["videos"][0][key] = "f" * 64
            with self.assertRaisesRegex(ValueError, "source binding"):
                self.validate(value)

    def test_adjudication_cannot_masquerade_as_new_user_review(self):
        value = self.value()
        value["videos"][0]["reviews"][0]["claim_type"] = "USER_REVIEW"
        with self.assertRaisesRegex(ValueError, "AI adjudication provenance"):
            self.validate(value)

    def test_scope_and_anchor_must_be_bounded_and_source_valid(self):
        for change in ({"end_frame": 10}, {"start_frame": 2}, {"raw_family": "vehicle"}):
            value = self.value()
            value["videos"][0]["reviews"][0]["scopes"][0].update(change)
            with self.assertRaises(ValueError):
                self.validate(value)

    def test_pixel_receipt_source_or_anchor_mismatch_rejected(self):
        value = self.value()
        value["videos"][0]["reviews"][0]["evidence"][0]["source_frame_pixel_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "pixel evidence"):
            self.validate(value)

    def test_unknown_duplicate_video_and_duplicate_review_rejected(self):
        for field in ("videos", "reviews"):
            value = self.value()
            target = value["videos"] if field == "videos" else value["videos"][0]["reviews"]
            target.append(deepcopy(target[0]))
            with self.assertRaises(ValueError):
                self.validate(value)

    def test_overlay_provenance_distinct_from_unchanged_base_review(self):
        frame = {"frame_index": 1, "observations": [{"review_refs": [
            {"review_id": "old", "reviews_sha256": "base"},
            {"review_id": self.review["review_id"], "reviews_sha256": "base"}]}]}
        out = list(batch._attach_overlay_provenance([frame], [self.review], "overlay"))[0]
        refs = out["observations"][0]["review_refs"]
        self.assertEqual(refs[0]["reviews_sha256"], "base")
        self.assertEqual(refs[1]["reviews_sha256"], "overlay")
        self.assertTrue(refs[1]["not_automatic_model_role_prediction"])

    def test_pixel_anchor_requires_actual_scoped_raw_measurement_match(self):
        with self.assertRaisesRegex(ValueError, "did not match"):
            batch._validate_overlay_application({"matched_reviewed_anchors": []}, [self.review])
        batch._validate_overlay_application({"matched_reviewed_anchors": [{
            "review_id": self.review["review_id"], "frame_index": 1}]}, [self.review])


class PreparationTests(unittest.TestCase):
    def test_machine_branch_defaults_pilot_and_cannot_take_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "oldreviews.json"
            batch._write(old, {"retained": True})
            policy = {**POLICY, "schema_version": "phase8_b_v4_policy_v1",
                "base_b_v3_policy_sha256": "b" * 64, "supported_categories": ["car"],
                "passage_display_id": {"scope": "test"}}
            batch._write(root / batch.POLICY, policy)
            prepared = {"policy_sha256": "b" * 64, "policy": policy, "jobs": [],
                "reviews_path": old, "reviews_sha256": batch.donor.sha256_file(old),
                "reviews": {}, "selected_video_ids": ["weekday_siang"]}
            with patch.object(batch.previous, "prepare_b_v3_batch",
                    side_effect=lambda **_: deepcopy(prepared)) as prepare:
                out = batch.prepare_b_v4_batch(repo_root=root)
                self.assertEqual(prepare.call_args.kwargs["video_ids"], ["weekday_siang"])
                self.assertEqual(out["branch"], "machine")
                self.assertEqual(out["review_overlay"], {})
                self.assertIsNone(out["review_overlay_sha256"])
                with self.assertRaisesRegex(ValueError, "cannot silently"):
                    batch.prepare_b_v4_batch(repo_root=root, reviews_path="fakeoverlay.json")

    def test_frozen_timer_control_change_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = {**POLICY, "schema_version": "phase8_b_v4_policy_v1",
                "base_b_v3_policy_sha256": "b" * 64, "supported_categories": ["car"],
                "passage_display_id": {}, "timeout_frames": 61}
            batch._write(root / batch.POLICY, config)
            old = {**config, "timeout_frames": 60}
            with patch.object(batch.previous, "prepare_b_v3_batch", return_value={
                "policy_sha256": "b" * 64, "policy": old}):
                with self.assertRaisesRegex(ValueError, "frozen counting controls"):
                    batch.prepare_b_v4_batch(repo_root=root)


class RetentionComparisonTests(unittest.TestCase):
    def test_new_retention_manifest_has_versioned_namespace_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            batch._write(root / "policy.json", {"timeout_frames": 60})
            before = (root / "policy.json").read_bytes()
            batch._retention(root)
            manifest = json.loads((root / "retention_manifest.json").read_text())
            self.assertEqual(manifest["schema_version"], "phase8_b_v4_retention_v1")
            self.assertEqual(manifest["artifacts"][0]["sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual((root / "policy.json").read_bytes(), before)
            self.assertNotIn("retention_manifest.json", [r["path"] for r in manifest["artifacts"]])

    def test_actual_retained_pilot_baseline_is_read_not_replayed(self):
        root = Path(batch.__file__).resolve().parents[1]
        result, reference = batch._read_b_v3_result(root, "weekday_siang")
        self.assertEqual(result["aggregate"]["total"], 584)
        self.assertEqual(result["source_identity"]["records_sha256"],
            "bc484aff0372242925f8b87e6d91ffc2ac11ae696ed3f59201a73d44f98a145b")
        self.assertEqual(reference["decoded_sha256"],
            "3fbbcfe070e0f83094990238e2308ef9ac3b4544a5bfd5263cd5b9ea66be9f45")

    def test_exact_retained_v3_baseline_decoded_with_manifest_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = b'{"aggregate":{"total":2},"events":[]}'
            archive = root / "results/old.json.gz"
            archive.parent.mkdir(parents=True)
            archive.write_bytes(gzip.compress(raw, mtime=0))
            batch._write(root / batch.BASELINE_RETENTION, {"files": [{
                "source_relative_path": "weekday_siang/counting_result.json",
                "retained_path": archive.relative_to(root).as_posix(),
                "retained_sha256": batch.donor.sha256_file(archive),
                "source_bytes": len(raw), "source_sha256": hashlib.sha256(raw).hexdigest()}]})
            result, ref = batch._read_b_v3_result(root, "weekday_siang")
            self.assertEqual(result["aggregate"]["total"], 2)
            self.assertEqual(ref["decoded_sha256"], hashlib.sha256(raw).hexdigest())
            archive.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "bytes differ"):
                batch._read_b_v3_result(root, "weekday_siang")

    def test_comparison_uses_raw_frame_refs_not_version_event_hash_equality(self):
        event = {"event_id": "oldhash", "display_id": "M1000", "physical_unit_id": "u",
            "episode_id": "e", "passage_id": "p", "category": "motorcycle", "direction": "B_TO_A",
            "route": "LINE_MARGIN", "evidence": {"measured_crossing": True,
                "source_refs": [{"track_id": 185, "frame_index": 251}]}}
        old = {"aggregate": {"total": 1}, "events": [event]}
        new = deepcopy(old)
        new["events"][0]["event_id"] = "newhash"
        result = batch.compare_b_v3(old, new, {"sha256": "a" * 64})
        self.assertTrue(result["event_hashes_not_used_as_cross_version_identity"])
        self.assertEqual(result["b_v3_events"][0]["raw_frame_refs"], [(185, 251)])
        self.assertEqual(result["operational_total_delta"], 0)
        self.assertTrue(result["branch_totals_must_not_be_added"])

    def test_role_review_queue_keeps_distinct_episodes_not_global_raw_id(self):
        common = {"role": "unknown_person", "physical_unit_id": "person:1"}
        queue = batch._role_queue([{**common, "episode_id": "first", "frame_index": 1},
            {**common, "episode_id": "second", "frame_index": 10}])
        self.assertEqual(len(queue), 2)
        self.assertTrue(all(row["does_not_imply_pedestrian"] for row in queue))

    def test_notebook_contains_prepare_default_no_inference_and_explicit_scope(self):
        path = Path(batch.__file__).parent / "08d_episode_eligibility_role_replay.ipynb"
        notebook = json.loads(path.read_text())
        cells = ["".join(cell["source"]) for cell in notebook["cells"]]
        parameters = cells[1]
        namespace = {"REPO_ROOT": "/tmp/injected-checkout", "__name__": "test"}
        exec(compile(parameters, "parameters", "exec"), namespace)
        self.assertEqual(str(namespace["REPO_ROOT"]), "/tmp/injected-checkout")
        self.assertEqual(namespace["MODE"], "prepare")
        self.assertEqual(namespace["VIDEO_IDS"], ["weekday_siang"])
        self.assertFalse(namespace["RENDER_ANNOTATED_VIDEO"])
        self.assertNotIn("ultralytics", "\n".join(cells))


if __name__ == "__main__":
    unittest.main(verbosity=2)
