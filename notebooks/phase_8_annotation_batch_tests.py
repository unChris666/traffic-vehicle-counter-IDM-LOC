"""Negative transport/selection guards; fixtures are not real video findings."""
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import phase_8_annotation_batch as batch


def event(identifier="event1", unit="unit1", passage="passage1"):
    return {"type": "CountEvent", "status": "accepted", "accepted_count_event": True,
            "event_id": identifier, "physical_unit_id": unit, "passage_id": passage,
            "category": "motorcycle", "direction": "A_TO_B"}


class SelectionGuards(unittest.TestCase):
    def test_default_selects_eight_once(self):
        self.assertEqual(batch._selected_ids(None), list(batch.VIDEO_IDS))

    def test_empty_selection_rejected(self):
        with self.assertRaisesRegex(ValueError, "VIDEO_IDS"):
            batch._selected_ids([])

    def test_duplicate_selection_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            batch._selected_ids(["weekday_pagi", "weekday_pagi"])

    def test_unknown_video_rejected(self):
        with self.assertRaisesRegex(ValueError, "VIDEO_IDS"):
            batch._selected_ids(["made_up_video"])

    def test_pending_never_accepted(self):
        value = event(); value["status"] = "pending_review"; value["accepted_count_event"] = False
        with self.assertRaisesRegex(ValueError, "accepted CountEvent"):
            batch._event_totals([value])

    def test_duplicate_event_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate accepted event"):
            batch._event_totals([event(), event()])

    def test_two_event_ids_cannot_duplicate_same_passage(self):
        with self.assertRaisesRegex(ValueError, "Duplicate physical-unit passage"):
            batch._event_totals([event(), event("event2")])

    def test_original_machine_and_reviewed_cannot_mix(self):
        value = event(); value["manual_review_applied"] = True
        with self.assertRaisesRegex(ValueError, "machine snapshot"):
            batch._event_totals([value])

    def test_component_and_unsupported_category_cannot_increment(self):
        for category in ("person", "bus_angkot", None):
            value = event(); value["category"] = category
            with self.subTest(category=category), self.assertRaisesRegex(ValueError, "Unsupported"):
                batch._event_totals([value])

    def test_category_direction_pivot_reconciles(self):
        second = event("event2", "unit2", "passage2"); second.update(category="car", direction="B_TO_A")
        result = batch._event_totals([event(), second])
        self.assertEqual(result["accepted_total"], 2)
        self.assertEqual(result["by_direction"], {"A_TO_B": 1, "B_TO_A": 1})
        self.assertEqual(sum(result["by_category"].values()), 2)


class RetainedBytesGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / "original.json"
        self.path.write_text('{"actual":1}', encoding="utf-8")
        self.row = {"path": self.path.name, "sha256": batch.sha256_file(self.path), "size_bytes": self.path.stat().st_size}

    def tearDown(self):
        self.temp.cleanup()

    def test_changed_bytes_same_length_rejected(self):
        self.path.write_text('{"actual":2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            batch._verify_artifact(self.root, {self.path.name: self.row}, self.path.name, {})

    def test_missing_retained_artifact_rejected(self):
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            batch._verify_artifact(self.root, {self.path.name: self.row}, self.path.name, {})

    def test_unlisted_file_rejected(self):
        with self.assertRaisesRegex(ValueError, "absent"):
            batch._verify_artifact(self.root, {}, self.path.name, {})

    def test_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, "escape"):
            batch._relative_path(self.root, "../other.json")

    def test_absolute_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "relative"):
            batch._relative_path(self.root, "/another/input.json")

    def test_duplicate_manifest_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            batch._index_manifest({"schema_version": "phase8_batch_v1", "artifacts": [self.row, self.row]})

    def test_exact_manifest_required_and_ambiguous_mount_rejected(self):
        digest = batch.sha256_file(self.path)
        with patch.object(batch, "DONOR_MANIFEST_SHA256", digest):
            for name in ("kernel_a", "kernel_b"):
                folder = self.root / name; folder.mkdir()
                (folder / "batch_retention_manifest.json").write_bytes(self.path.read_bytes())
            with self.assertRaisesRegex(ValueError, "Expected one"):
                batch.locate_source_run(input_root=self.root)

    def test_wrong_donor_rejected_even_with_plausible_filename(self):
        (self.root / "batch_retention_manifest.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "exact retained manifest"):
            batch.locate_source_run(self.root)

    def test_source_video_changed_bytes_rejected(self):
        video = {"metadata_confirmation": {"source_filename": self.path.name}, "source_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "source video bytes differ"):
            batch._source_video(video, self.root, self.root)

    def test_duplicate_raw_source_mount_rejected(self):
        for name in ("dataset_a", "dataset_b"):
            folder = self.root / name; folder.mkdir()
            (folder / "sample.mp4").write_bytes(b"fixture-not-a-real-video")
        video = {"metadata_confirmation": {"source_filename": "sample.mp4"}, "source_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "exactly one"):
            batch._source_video(video, None, self.root)

    def test_input_size_and_hash_preserved_in_proof(self):
        proof = {}
        result = batch._verify_artifact(self.root, {self.path.name: self.row}, self.path.name, proof)
        self.assertEqual(result, self.path)
        self.assertEqual(proof[str(self.path)]["sha256"], self.row["sha256"])


class PartialExecutionGuards(unittest.TestCase):
    def test_failed_render_retains_error_and_cannot_claim_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            donor = root / "donor"; donor.mkdir()
            dataset = root / "dataset"; dataset.mkdir()
            payload = dataset / "fixture.bin"; payload.write_bytes(b"not-an-actual-video")
            job = {"video_id": "weekday_pagi", "video_path": payload, "geometry_path": payload,
                   "paths": {key: payload for key in ("records", "decisions", "events", "relations")},
                   "source_identity": {"video_sha256": batch.sha256_file(payload), "geometry_sha256": batch.sha256_file(payload)},
                   "metadata": {"fps": 30.0, "frame_count": 1}, "expected_pivot": {"accepted_total": 0},
                   "expected_pending": 0, "category_uses_future_evidence_count": 0}
            prepared = {"source_run_root": donor, "jobs": [job], "selected_video_ids": ["weekday_pagi"],
                        "all_eight_selected": False, "selected_accepted": 0, "selected_pending": 0,
                        "verified_input_files": [], "ledger_path": payload}
            def failed_renderer(*args, **kwargs):
                raise ValueError("synthetic renderer failure")
            fake_helper = types.SimpleNamespace(render_review_video=failed_renderer)
            fake_library = types.SimpleNamespace(__version__="synthetic-guard-only")
            with patch.object(batch, "prepare_annotation_batch", return_value=prepared), \
                    patch.dict("sys.modules", {"phase_8_annotation_helpers": fake_helper, "cv2": fake_library, "numpy": fake_library}):
                with self.assertRaisesRegex(batch.AnnotationBatchError, "incomplete"):
                    batch.run_annotation_batch(repo_root=root, output_root=root / "outputs", progress=None)
            reports = list((root / "outputs").glob("*/annotation_batch_report.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text())
            self.assertEqual(report["status"], "failed_or_partial_annotation_batch")
            self.assertFalse(report["all_eight_annotation_videos_completed"])
            self.assertEqual(report["completed_video_count"], 0)
            self.assertEqual(report["videos"][0]["status"], "failed")
            self.assertIn("synthetic renderer failure", report["videos"][0]["message"])
            self.assertTrue((reports[0].parent / "annotation_retention_manifest.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
