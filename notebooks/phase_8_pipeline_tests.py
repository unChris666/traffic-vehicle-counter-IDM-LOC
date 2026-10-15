"""Phase 8 synthetic software tests; no model inference or performance claims."""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import cv2
import numpy as np

import phase_8_pipeline_helpers as pipeline


ROOT = Path(__file__).resolve().parents[1]


class Fixture:
    """Constructed boxes/IDs/categories; not a real traffic-video experiment."""
    def __init__(self, root, positions=(20, 30, 40, 60, 70, 20, 30, 40, 60, 70)):
        self.root = Path(root)
        self.geometry = self.root / "geometry.json"
        self.cache = self.root / "records.jsonl.gz"
        self.video_sha = "8" * 64
        self.records = []
        for frame, x in enumerate(positions):
            vehicle, rider = (1, 2) if frame < 5 else (3, 4)
            boxes = [(vehicle, "motorcycle", 3, [x - 15, 30, x + 15, 60]), (rider, "person", 0, [x - 5, 24, x + 5, 50])]
            raw, observations = [], []
            for index, (track, label, cls, box) in enumerate(boxes):
                raw.append({"bbox_xyxy_pixels": box, "class_id": cls, "class_name": label, "confidence": .8})
                observations.append({"track_id": track, "frame_index": frame, "original_detection_index": index,
                    "raw_bbox": box, "bbox": [0, 0, 1, 1], "class_id": cls, "class_name": label,
                    "confidence": .8, "emitted": True, "measurement_provenance": pipeline.PROVENANCE})
            self.records.append({"phase": 8, "measurement_provenance": pipeline.PROVENANCE,
                "video_sha256": self.video_sha, "variant": "raw", "parent_run_id": "SYNTHETIC_PHASE8_NOT_GPU",
                "frame_index": frame, "width": 100, "height": 100, "raw_detections": raw, "emitted_tracks": observations,
                "timestamp_estimate_from_index_fps_seconds": frame / 10})
        self.geometry_data = {"draft_id": "SYNTHETIC_GEOMETRY_NOT_USER_APPROVAL", "status": "ACCEPTED_SYNTHETIC_FIXTURE",
            "claim_type": "SYNTHETIC_SOFTWARE_FIXTURE", "source_video": {"sha256": self.video_sha},
            "geometry_contract_accepted": True, "selected_anchor": "bottom_center",
            "confirmed_direction_metadata": {"A_TO_B": "approaching camera", "B_TO_A": "moving away from camera"},
            "rendered_native_pixels": {"width": 100, "height": 100,
                "line": {"P1": [50, 20], "P2": [50, 80]},
                "side_a_polygon": [[0, 0], [50, 0], [50, 100], [0, 100]],
                "side_b_polygon": [[50, 0], [100, 0], [100, 100], [50, 100]]},
            "normalized": {"line": {"P1": [.5, .2], "P2": [.5, .8]},
                "side_a_polygon": [[0, 0], [.5, 0], [.5, 1], [0, 1]],
                "side_b_polygon": [[.5, 0], [1, 0], [1, 1], [.5, 1]]}}
        self.save()

    def save(self):
        image_path = self.root / "frame.png"
        cv2.imwrite(str(image_path), np.zeros((100, 100, 3), dtype=np.uint8))
        self.geometry_data["source_frame"] = {"path": "frame.png", "sha256": pipeline.night.sha256_file(image_path),
            "frame_index": 0, "width": 100, "height": 100, "coordinate_space": "native_full_frame_pixels"}
        approval = {"schema_version": "phase8_geometry_review_v1", "approved": True,
            "claim_type": "SYNTHETIC_TEST_FIXTURE_NOT_REAL_DATASET", "source_video_sha256": self.video_sha,
            "geometry_coordinates_sha256": pipeline.manifest.geometry_coordinates_sha256(self.geometry_data),
            "reviewer": "synthetic test", "reviewed_at": "2026-10-14T00:00:00Z", "observation": "constructed geometry",
            "evidence_frames": [{"path": "frame.png", "sha256": pipeline.night.sha256_file(image_path), "frame_index": 0}],
            "confirmed_direction_metadata": self.geometry_data["confirmed_direction_metadata"]}
        approval_path = self.root / "approval.json"; approval_path.write_text(json.dumps(approval))
        self.geometry_data["approval_feedback"] = {"path": "approval.json", "sha256": pipeline.night.sha256_file(approval_path)}
        self.geometry.write_text(json.dumps(self.geometry_data))
        with gzip.open(self.cache, "wt", encoding="utf-8") as handle:
            for record in self.records:
                handle.write(json.dumps(record) + "\n")
        self.identity = {"video_sha256": self.video_sha, "geometry_sha256": pipeline.night.sha256_file(self.geometry),
            "records_sha256": pipeline.night.sha256_file(self.cache), "variant": "raw", "width": 100, "height": 100,
            "parent_run_id": "SYNTHETIC_PHASE8_NOT_GPU"}

    def replay(self, target):
        profile = pipeline.make_processing_profile(ROOT)
        pipeline.validate_geometry(self.geometry, self.identity, repo_root=ROOT, allow_synthetic=True)
        pipeline._validate_full_cache(self.cache, self.identity, pipeline.PROVENANCE, len(self.records))
        return pipeline._execute_replay(self.cache, self.geometry, profile, target, repo_root=ROOT, identity=self.identity,
            proof={"measurement_provenance": pipeline.PROVENANCE, "frame_count": len(self.records), "source_phase": 8,
                "execution_kind": "SYNTHETIC_FIXTURE", "new_detector_tracker_encoder_inference": False}, synthetic=True)


class ProfileTests(unittest.TestCase):
    def test_empty_source_encoder_truthfully_not_executed(self):
        status = pipeline.validate_appearance_execution({"observed_diagnostics": {"raw_detections": 0},
            "appearance_diagnostics": {"finite_nonzero_features_produced": 0, "encoder_calls": 0}})
        self.assertEqual(status["status"], "not_executed_no_eligible_crops")
        self.assertFalse(status["actual_cuda_execution_confirmed"])

    def test_single_crop_encoder_executed_no_association_is_valid(self):
        status = pipeline.validate_appearance_execution({"observed_diagnostics": {"raw_detections": 1},
            "appearance_diagnostics": {"finite_nonzero_features_produced": 1, "encoder_calls": 1, "nonempty_feature_association_calls": 0},
            "cuda_execution_evidence": {"actual_cuda_execution_confirmed": True}})
        self.assertEqual(status["status"], "executed_actual_cuda")
        self.assertEqual(status["association_status"], "not_executed_no_nonempty_candidate_pairs")

    def test_empty_source_cannot_claim_cuda_execution(self):
        with self.assertRaisesRegex(ValueError, "must not claim"):
            pipeline.validate_appearance_execution({"observed_diagnostics": {"raw_detections": 0},
                "appearance_diagnostics": {"finite_nonzero_features_produced": 0, "encoder_calls": 0},
                "cuda_execution_evidence": {"actual_cuda_execution_confirmed": True}})

    def test_expected_crop_missing_features_is_failure(self):
        with self.assertRaisesRegex(ValueError, "require actual finite"):
            pipeline.validate_appearance_execution({"observed_diagnostics": {"raw_detections": 2},
                "appearance_diagnostics": {"finite_nonzero_features_produced": 0, "encoder_calls": 0}})

    def test_expected_crop_missing_cuda_is_failure(self):
        with self.assertRaisesRegex(ValueError, "CUDA encoder proof absent"):
            pipeline.validate_appearance_execution({"observed_diagnostics": {"raw_detections": 2},
                "appearance_diagnostics": {"finite_nonzero_features_produced": 2, "encoder_calls": 1}})

    def test_inconsistent_empty_execution_status_rejected(self):
        with self.assertRaisesRegex(ValueError, "status differs"):
            pipeline.validate_appearance_execution({"observed_diagnostics": {"raw_detections": 0},
                "appearance_diagnostics": {"finite_nonzero_features_produced": 0, "encoder_calls": 0},
                "appearance_execution": {"status": "executed_actual_cuda"}})

    def test_frozen_profile(self):
        profile = pipeline.make_processing_profile(ROOT)
        self.assertEqual(pipeline.validate_processing_profile(profile, ROOT), profile)
        self.assertEqual(profile["tracker"]["with_reid"], True)
        self.assertEqual(profile["tracker"]["gmc_method"], "none")
        self.assertEqual(profile["category_coverage"]["pedestrian"], "NOT_IMPLEMENTED_BY_FROZEN_B_V1")

    def test_cpu_rejected(self):
        profile = pipeline.make_processing_profile(ROOT); profile["detector"]["device"] = "cpu"
        with self.assertRaises(ValueError):
            pipeline.validate_processing_profile(profile, ROOT)

    def test_gamma_rejected(self):
        profile = pipeline.make_processing_profile(ROOT); profile["variant"] = {"name": "gamma", "method": "gamma", "gamma": .7}
        with self.assertRaises(ValueError):
            pipeline.validate_processing_profile(profile, ROOT)

    def test_tuned_tracker_rejected(self):
        profile = pipeline.make_processing_profile(ROOT); profile["tracker"]["track_buffer"] = 31
        with self.assertRaises(ValueError):
            pipeline.validate_processing_profile(profile, ROOT)

    def test_tuned_counting_rejected(self):
        profile = pipeline.make_processing_profile(ROOT); profile["counting"]["association"]["component"]["max_center_distance_norm"] = .52
        with self.assertRaises(ValueError):
            pipeline.validate_processing_profile(profile, ROOT)

    def test_frozen_old_sources_unchanged(self):
        for path, sha in pipeline.FROZEN_SOURCES.items():
            self.assertEqual(pipeline.night.sha256_file(ROOT / path), sha)

    def test_adapter_only_one_literal(self):
        _, proof, source = pipeline.load_counting_adapter(ROOT, pipeline.PROVENANCE)
        original = (ROOT / "notebooks/phase_6_identity_resolution_helpers.py").read_text()
        self.assertEqual(source, original.replace('"retained_phase_2_detection"', '"retained_phase_8_detection"', 1))
        self.assertEqual(proof["literal_substitution_count"], 1)

    def test_unknown_provenance_rejected(self):
        with self.assertRaises(ValueError):
            pipeline.load_counting_adapter(ROOT, "invented_detection")

    def test_namespace_serialization_preserves_raw_bc(self):
        row = {"frame_index": 0, "video_sha256": "8" * 64, "width": 100, "height": 100,
            "detections": [{"bbox_xyxy_pixels": [10, 20, 50, 60], "class_id": 3, "class_name": "motorcycle", "confidence": .8}]}
        record = pipeline._phase8_record(row, [[0, 0, 1, 1, 7, .8, 3, 0]], run_id="SYNTHETIC", fps=10, assigned=[], snapshots=[])
        self.assertEqual(record["phase"], 8)
        self.assertEqual(record["emitted_tracks"][0]["raw_bbox"], [10, 20, 50, 60])
        self.assertEqual(record["emitted_tracks"][0]["bbox"], [0, 0, 1, 1])
        self.assertEqual(record["emitted_tracks"][0]["measurement_provenance"], pipeline.PROVENANCE)


class FullScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.fixture = Fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_scope_includes_later_passage_and_rider_is_one_vehicle(self):
        result = self.fixture.replay(Path(self.tmp.name) / "result")
        self.assertEqual(result["aggregate"]["total"], 2)
        self.assertEqual(result["aggregate"]["by_category"]["motorcycle"], 2)
        report = result["report"]
        self.assertEqual(report["scope"], {"track_ids": None, "association_frame_windows": None})
        self.assertEqual(report["source_frame_count"], 10)
        self.assertEqual(report["execution_kind"], "SYNTHETIC_FIXTURE")
        self.assertFalse(report["old_events_or_review_overlays_copied"])
        self.assertEqual(result["snapshot"]["scope"], "full_video")
        with gzip.open(Path(result["run_dir"]) / "machine_count_events.json.gz", "rt") as handle:
            events = json.load(handle)
        self.assertEqual({e["track_id"] for e in events}, {1, 3})
        for event in events:
            self.assertEqual(event["source_identity"], self.fixture.identity)
            self.assertEqual(event["geometry_evidence"]["crossing_point"][0], 50)
            self.assertTrue(event["component_episode_ids"])

    def test_frame_one_start_rejected(self):
        self.fixture.records.pop(0); self.fixture.save()
        with self.assertRaisesRegex(ValueError, "every frame from zero"):
            pipeline._validate_full_cache(self.fixture.cache, self.fixture.identity, pipeline.PROVENANCE, 9)

    def test_missing_middle_frame_rejected(self):
        self.fixture.records.pop(4); self.fixture.save()
        with self.assertRaises(ValueError):
            pipeline._validate_full_cache(self.fixture.cache, self.fixture.identity, pipeline.PROVENANCE, 9)

    def test_count_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "frame count"):
            pipeline._validate_full_cache(self.fixture.cache, self.fixture.identity, pipeline.PROVENANCE, 11)

    def test_false_link_rejected(self):
        self.fixture.records[3]["emitted_tracks"][0]["raw_bbox"] = [1, 1, 2, 2]; self.fixture.save()
        with self.assertRaisesRegex(ValueError, "raw detector measurement"):
            pipeline._validate_full_cache(self.fixture.cache, self.fixture.identity, pipeline.PROVENANCE, 10)

    def test_predicted_observation_rejected(self):
        self.fixture.records[3]["emitted_tracks"][0]["emitted"] = False; self.fixture.save()
        with self.assertRaises(ValueError):
            pipeline._validate_full_cache(self.fixture.cache, self.fixture.identity, pipeline.PROVENANCE, 10)

    def test_out_of_frame_bbox_rejected(self):
        self.fixture.records[3]["raw_detections"][0]["bbox_xyxy_pixels"][2] = 101; self.fixture.save()
        with self.assertRaisesRegex(ValueError, "native image"):
            pipeline._validate_full_cache(self.fixture.cache, self.fixture.identity, pipeline.PROVENANCE, 10)

    def test_cache_sha_changed_rejected(self):
        identity = deepcopy(self.fixture.identity); identity["records_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Cache SHA"):
            pipeline._validate_full_cache(self.fixture.cache, identity, pipeline.PROVENANCE, 10)

    def test_wrong_geometry_video_rejected(self):
        self.fixture.geometry_data["source_video"]["sha256"] = "9" * 64; self.fixture.save()
        with self.assertRaisesRegex(ValueError, "another video"):
            pipeline.validate_geometry(self.fixture.geometry, self.fixture.identity, repo_root=ROOT, allow_synthetic=True)

    def test_unreviewed_geometry_rejected_before_model_load(self):
        self.fixture.geometry_data["geometry_contract_accepted"] = False; self.fixture.save()
        with self.assertRaisesRegex(ValueError, "not been accepted"):
            pipeline.validate_geometry(self.fixture.geometry, self.fixture.identity, repo_root=ROOT, allow_synthetic=True)

    def test_missing_direction_rejected(self):
        self.fixture.geometry_data["confirmed_direction_metadata"]["B_TO_A"] = None; self.fixture.save()
        with self.assertRaisesRegex(ValueError, "direction confirmation"):
            pipeline.validate_geometry(self.fixture.geometry, self.fixture.identity, repo_root=ROOT, allow_synthetic=True)

    def test_template_native_transfer_rejected(self):
        self.fixture.geometry_data["rendered_native_pixels"]["width"] = 200; self.fixture.save()
        with self.assertRaisesRegex(ValueError, "native dimensions"):
            pipeline.validate_geometry(self.fixture.geometry, self.fixture.identity, repo_root=ROOT, allow_synthetic=True)

    def test_changed_coordinates_with_copied_feedback_rejected(self):
        self.fixture.geometry_data["normalized"]["line"]["P1"] = [.5, .1]
        self.fixture.geometry_data["rendered_native_pixels"]["line"]["P1"] = [50, 10]
        # Rehashing a modified geometry does not create a new review approval.
        self.fixture.geometry.write_text(json.dumps(self.fixture.geometry_data))
        self.fixture.identity["geometry_sha256"] = pipeline.night.sha256_file(self.fixture.geometry)
        with self.assertRaisesRegex(ValueError, "changed after review"):
            pipeline.validate_geometry(self.fixture.geometry, self.fixture.identity, repo_root=ROOT, allow_synthetic=True)

    def test_category_conflict_remains_pending(self):
        self.fixture.records[1]["raw_detections"][0].update(class_name="car", class_id=2)
        self.fixture.records[1]["emitted_tracks"][0].update(class_name="car", class_id=2)
        self.fixture.save()
        result = self.fixture.replay(Path(self.tmp.name) / "conflict")
        self.assertEqual(result["aggregate"]["total"], 1)
        with gzip.open(Path(result["run_dir"]) / "machine_passage_decisions.json.gz", "rt") as handle:
            decisions = json.load(handle)
        first = [d for d in decisions if d["track_id"] == 1]
        self.assertTrue(any("CATEGORY_CONFLICT" in d["hard_block_reasons"] for d in first))

    def test_valid_empty_full_cache_produces_empty_machine_snapshot(self):
        for record in self.fixture.records:
            record["raw_detections"] = []; record["emitted_tracks"] = []
        self.fixture.save()
        result = self.fixture.replay(Path(self.tmp.name) / "empty")
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["frames_processed"], 10)
        self.assertEqual(result["report"]["execution_kind"], "SYNTHETIC_FIXTURE")

    def test_bus_taxonomy_is_open(self):
        for record in self.fixture.records[:5]:
            record["raw_detections"][0].update(class_name="bus", class_id=5)
            record["emitted_tracks"][0].update(class_name="bus", class_id=5)
        self.fixture.save()
        result = self.fixture.replay(Path(self.tmp.name) / "bus")
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["report"]["category_coverage"]["bus_angkot"], "BUS_ANGKOT_MAPPING_OPEN")

    def test_synthetic_report_not_actual_gpu_evidence(self):
        report = self.fixture.root / "synthetic_report.json"; report.write_text(json.dumps({"execution_kind": "SYNTHETIC_FIXTURE"}))
        with self.assertRaisesRegex(ValueError, "Actual retained GPU"):
            pipeline.validate_cache_provenance({"source_report_path": str(report), "source_report_sha256": pipeline.night.sha256_file(report)},
                self.fixture.identity, pipeline.make_processing_profile(ROOT), repo_root=ROOT)

    def test_fabricated_actual_phase7_report_not_retained_evidence(self):
        report = self.fixture.root / "fabricated_report.json"
        report.write_text(json.dumps({"phase": 7, "run_id": self.fixture.identity["parent_run_id"],
            "execution_kind": "ACTUAL_MODEL_EXECUTION", "configuration": pipeline.make_processing_profile(ROOT),
            "fixture_label": "SYNTHETIC_TEST_ONLY_INVENTED_ACTUAL_LABEL_MUST_BE_REJECTED"}))
        with self.assertRaisesRegex(ValueError, "immutable retained actual execution report"):
            pipeline.validate_cache_provenance({"source_report_path": str(report), "source_report_sha256": pipeline.night.sha256_file(report)},
                self.fixture.identity, pipeline.make_processing_profile(ROOT), repo_root=ROOT)

    def test_incompatible_donor_detector_rejected(self):
        profile = pipeline.make_processing_profile(ROOT); other = deepcopy(profile); other["detector"]["settings"]["conf"] = .3
        with self.assertRaisesRegex(ValueError, "detector controls"):
            pipeline._match_model_controls(other, profile)

    def test_failed_replay_keeps_error_config_and_manifest(self):
        module, proof, source = pipeline.load_counting_adapter(ROOT, pipeline.PROVENANCE)
        module.run_identity_resolution = mock.Mock(side_effect=RuntimeError("SYNTHETIC_REPLAY_FAILURE"))
        target = self.fixture.root / "failed_replay"
        with mock.patch.object(pipeline, "load_counting_adapter", return_value=(module, proof, source)):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_REPLAY_FAILURE"):
                self.fixture.replay(target)
        error = json.loads((target / "error.json").read_text())
        self.assertEqual(error["status"], "failed_partial_replay")
        manifest = json.loads((target / "retention_manifest.json").read_text())
        paths = {entry["path"] for entry in manifest["artifacts"]}
        self.assertIn("error.json", paths)
        self.assertIn("counting_configuration.json", paths)
        for entry in manifest["artifacts"]:
            self.assertEqual(entry["sha256"], pipeline.night.sha256_file(target / entry["path"]))

    def test_real_mp4_fixture_write_decode_and_overlay(self):
        path = self.fixture.root / "synthetic_source.mp4"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (100, 100))
        self.assertTrue(writer.isOpened())
        for index in range(10):
            frame = np.full((100, 100, 3), (index * 10, 50, 90), dtype=np.uint8)
            cv2.rectangle(frame, (20, 20), (50, 60), (180, 180, 180), -1); writer.write(frame)
        writer.release()
        self.fixture.video_sha = pipeline.night.sha256_file(path)
        self.fixture.geometry_data["source_video"]["sha256"] = self.fixture.video_sha
        for record in self.fixture.records:
            record["video_sha256"] = self.fixture.video_sha
        self.fixture.save()
        result = self.fixture.replay(self.fixture.root / "annotated_replay")
        output = self.fixture.root / "annotated.mp4"
        proof = pipeline.render_annotated_video(path, self.fixture.cache, self.fixture.geometry, self.fixture.identity,
            Path(result["run_dir"]) / "machine_passage_decisions.json.gz", output, fps=10, expected_frame_count=10)
        self.assertEqual(proof["frames_written_and_redecoded"], 10)
        self.assertEqual(proof["width"], 100)
        self.assertFalse(proof["source_audio_preserved"])
        self.assertIn("presentation", proof["timestamp_semantics"])
        capture = cv2.VideoCapture(str(output)); ok, image = capture.read(); capture.release()
        self.assertTrue(ok)
        self.assertGreater(np.count_nonzero(image[:, 49:52, 1] > 150), 15)

    def test_annotation_wrong_source_sha_rejected_before_decode(self):
        source = self.fixture.root / "wrong_video.mp4"; source.write_bytes(b"synthetic_wrong_source")
        with self.assertRaisesRegex(ValueError, "source video SHA differs"):
            pipeline.render_annotated_video(source, self.fixture.cache, self.fixture.geometry, self.fixture.identity,
                self.fixture.root / "not_needed.json.gz", self.fixture.root / "not_written.mp4", fps=10, expected_frame_count=10)


def run_tests(output_json=None):
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"phase": 8, "execution_kind": "SYNTHETIC_SOFTWARE_TESTS_REAL_CODEC_FIXTURE",
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "passed": result.wasSuccessful(), "actual_gpu_inference_executed": False,
        "limits": "Constructed trajectories/IDs/classes; no vehicle-counting accuracy or eight-video processing claim"}
    if output_json:
        pipeline._json(output_json, report)
    if not result.wasSuccessful():
        raise AssertionError("Phase8 pipeline software guard failed")
    return report


if __name__ == "__main__":
    run_tests(sys.argv[1] if len(sys.argv) > 1 else None)
