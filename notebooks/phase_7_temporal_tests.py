"""Independent software-fixture checks for Phase 7 temporal integration.

All constructed boxes, class labels, identity hashes and relation cases are
synthetic. These checks never load detector/ReID weights, execute a tracker,
or prove CUDA inference/physical-vehicle/counting quality on TOR3-MALAM.
Historical Phase 6 source/evidence stays unchanged.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

import phase_7_temporal_helpers as temporal
from phase_5_geometry_helpers import Geometry


BASE_RESOLVER_SHA = "18949e7a44b6d73b9d50269f9d4569fbda781ba48269046b982287376ec3f054"
FIXTURE_VIDEO_SHA = "7" * 64
FIXTURE_ASSOCIATION = {
    "component": {
        "min_common_frames": 3, "min_consecutive_common_frames": 3,
        "min_first_bc_inside_second_fraction": 1.0,
        "max_center_distance_norm": 0.51,
        "max_relative_motion_residual_norm": 0.15,
    },
    "same_vehicle": {
        "min_common_frames": 2, "min_consecutive_common_frames": 2,
        "min_iou": 0.59, "max_center_distance_norm": 0.10,
        "max_relative_motion_residual_norm": 0.01,
    },
}
VARIANTS = [{"name": "raw", "method": "raw"},
            {"name": "gamma_070", "method": "gamma", "gamma": 0.7}]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _selection():
    return {
        "status": "FROZEN_DEV_SHORTLIST", "selection_basis": "DEVELOPMENT_ONLY",
        "holdout_used": False, "selected_variant": copy.deepcopy(VARIANTS[1]),
        "source_detection_screen_run_id": "synthetic_development_screen_not_actual_model",
        "source_detection_screen_report_sha256": "a" * 64,
        "claim_type": "SYNTHETIC_SOFTWARE_FIXTURE_NOT_ACTUAL_SHORTLIST",
    }


def _measurement(track, frame, box, label, index):
    return {
        "track_id": track, "frame_index": frame, "raw_bbox": list(box),
        "class_id": {"motorcycle": 3, "person": 0, "car": 2}[label],
        "class_name": label, "confidence": 0.8, "original_detection_index": index,
        "measurement_provenance": "retained_phase_7_detection",
        "timestamp_estimate_from_index_fps_seconds": frame / 30,
        "emitted": True,
    }


def _config():
    config = temporal.make_temporal_config(FIXTURE_VIDEO_SHA, "1" * 64, "2" * 64, "3" * 64)
    config["variants"] = copy.deepcopy(VARIANTS)
    return config


def _row(frame=0):
    return {
        "video_sha256": FIXTURE_VIDEO_SHA, "frame_index": frame, "width": 100, "height": 100,
        "detections": [
            {"bbox_xyxy_pixels": [20, 30, 50, 60], "confidence": 0.8, "class_id": 3, "class_name": "motorcycle"},
            {"bbox_xyxy_pixels": [30, 24, 40, 50], "confidence": 0.7, "class_id": 0, "class_name": "person"},
        ],
    }


def _outputs():
    # Filtered tracker bbox differs deliberately from raw source coordinates.
    return [[18, 28, 48, 58, 17, 0.8, 3, 0], [29, 23, 39, 49, 19, 0.7, 0, 1]]


def _identity():
    return {"video_sha256": FIXTURE_VIDEO_SHA, "variant": "raw", "parent_run_id": "synthetic_parent",
            "width": 100, "height": 100}


class _SourceFixture:
    def __init__(self, directory, positions, *, rider_start=0):
        self.root = Path(directory)
        self.geometry_path = self.root / "synthetic_geometry.json"
        geometry = {
            "draft_id": "phase7_synthetic_geometry_not_TOR3",
            "status": "SYNTHETIC_SOFTWARE_FIXTURE_NOT_ACTUAL_GEOMETRY_APPROVAL",
            "source_video": {"sha256": FIXTURE_VIDEO_SHA},
            "normalized": {
                "line": {"P1": [0.5, 0.2], "P2": [0.5, 0.8]},
                "side_a_polygon": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
                "side_b_polygon": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]],
            },
        }
        self.geometry_path.write_text(json.dumps(geometry), encoding="utf-8")
        self.records_path = self.root / "synthetic_phase7_measurements.jsonl"
        self.records = []
        for frame, x in enumerate(positions):
            observations = [_measurement(17, frame, [x - 15, 30, x + 15, 60], "motorcycle", 0)]
            if frame >= rider_start:
                observations.append(_measurement(19, frame, [x - 5, 24, x + 5, 50], "person", 1))
            record = {
                "video_sha256": FIXTURE_VIDEO_SHA, "parent_run_id": "synthetic_phase7",
                "variant": "raw", "frame_index": frame, "width": 100, "height": 100,
                "timestamp_estimate_from_index_fps_seconds": frame / 30,
                "raw_detections": [{
                    "bbox_xyxy_pixels": copy.deepcopy(observation["raw_bbox"]),
                    "class_id": observation["class_id"], "class_name": observation["class_name"],
                    "confidence": observation["confidence"],
                } for observation in observations],
                "emitted_tracks": observations,
            }
            self.records.append(record)
        self.write()

    def write(self):
        self.records_path.write_text("".join(json.dumps(row) + "\n" for row in self.records), encoding="utf-8")
        self.identity = {
            "video_sha256": FIXTURE_VIDEO_SHA, "parent_run_id": "synthetic_phase7", "variant": "raw",
            "width": 100, "height": 100, "records_sha256": _sha(self.records_path),
            "geometry_sha256": _sha(self.geometry_path),
        }
        self.config = {
            "policy_version": "phase6_option_b_v1", "metric": "passage",
            "parameter_claim_type": "SYNTHETIC_FIXTURE_USING_FROZEN_EXPERIMENT_CONTROLS_NOT_PRODUCT_DEFAULTS",
            "neutral_band_px": 0.0, "confirmation_observations": 1,
            "input_identity": copy.deepcopy(self.identity),
            "association": copy.deepcopy(FIXTURE_ASSOCIATION),
        }


class SelectionTests(unittest.TestCase):
    def test_explicit_development_only_nonraw_variant_can_be_shortlisted(self):
        before = _selection()
        temporal.validate_selection(before, VARIANTS)
        self.assertEqual(before, _selection())

    def test_holdout_cannot_be_used_to_select_transform(self):
        for updates in [{"holdout_used": True}, {"selection_basis": "HOLDOUT"},
                        {"holdout_used": "false"}, {"holdout_used": 0}]:
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    temporal.validate_selection({**_selection(), **updates}, VARIANTS)

    def test_missing_source_development_report_identity_is_rejected(self):
        for field in ["source_detection_screen_run_id", "source_detection_screen_report_sha256"]:
            selection = _selection()
            del selection[field]
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    temporal.validate_selection(selection, VARIANTS)

    def test_not_frozen_unknown_or_raw_candidate_is_rejected(self):
        for updates in [{"status": "DRAFT"}, {"selected_variant": VARIANTS[0]},
                        {"selected_variant": {"name": "gamma_090", "method": "gamma", "gamma": 0.9}},
                        {"selected_variant": {"name": "gamma_070", "method": "gamma", "gamma": 0.8}}]:
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    temporal.validate_selection({**_selection(), **updates}, VARIANTS)


class FrozenConfigurationTests(unittest.TestCase):
    def test_frozen_controls_have_same_semantics_as_phase6b_baseline(self):
        config = _config()
        validated = temporal.validate_temporal_config(config)
        self.assertEqual(validated["counting"]["association"], FIXTURE_ASSOCIATION)
        self.assertEqual(validated["counting"]["source_sha256"], BASE_RESOLVER_SHA)
        self.assertEqual(validated["counting"]["neutral_band_px"], 0.0)
        self.assertEqual(validated["counting"]["confirmation_observations"], 1)
        self.assertTrue(validated["tracker"]["with_reid"])
        self.assertEqual(config, _config())

    def test_changed_counting_association_or_geometry_controls_rejected(self):
        for section, name, value in [("component", "max_center_distance_norm", 0.60),
                                     ("same_vehicle", "max_relative_motion_residual_norm", 0.10)]:
            config = _config()
            config["counting"]["association"][section][name] = value
            with self.subTest(section=section):
                with self.assertRaises(ValueError):
                    temporal.validate_temporal_config(config)
        for updates in [{"neutral_band_px": 2.0}, {"confirmation_observations": 2},
                        {"grouping_enabled": False}, {"policy_version": "phase6_option_b_v0"},
                        {"source_sha256": "0" * 64}]:
            config = _config()
            config["counting"].update(updates)
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    temporal.validate_temporal_config(config)

    def test_configuration_types_cannot_masquerade_as_frozen_controls(self):
        for section, updates in [("tracker", {"with_reid": 1}),
                                 ("counting", {"confirmation_observations": True}),
                                 ("counting", {"neutral_band_px": False})]:
            config = _config()
            config[section].update(updates)
            with self.subTest(section=section, updates=updates):
                with self.assertRaises(ValueError):
                    temporal.validate_temporal_config(config)
        config = _config()
        config["counting"]["association"]["component"]["min_common_frames"] = 3.0
        with self.assertRaises(ValueError):
            temporal.validate_temporal_config(config)

    def test_reid_cannot_be_disabled_or_silently_use_auto_or_cpu(self):
        for updates in [{"with_reid": False}, {"device": "cpu"}, {"gmc_method": "sparseOptFlow"}]:
            config = _config()
            config["tracker"].update(updates)
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    temporal.validate_temporal_config(config)
        for updates in [{"device": "cpu"}, {"input_policy": "RAW_FRAME_FOR_REID_ENHANCED_FOR_DETECTOR"},
                        {"final_vehicle_configuration": True}, {"sha256": "0" * 64},
                        {"ort_version": "1.20.0"}]:
            config = _config()
            config["encoder"].update(updates)
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    temporal.validate_temporal_config(config)

    def test_nonfullvideo_scope_and_unfrozen_holdout_policy_are_rejected(self):
        for updates in [{"frame_scope": "ONLY_SELECTED_CROSSING_FRAMES"},
                        {"holdout_policy": "TUNE_USING_ALL_VIDEO"},
                        {"expected_frame_count": True}, {"expected_selection_sha256": "unknown"}]:
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    temporal.validate_temporal_config({**_config(), **updates})

    def test_ignored_encoder_or_counting_override_fields_are_rejected(self):
        for section, update in [("encoder", {"crop_policy": "RAW_UNENHANCED_CROPS"}),
                                ("counting", {"category_policy": "LAST_FRAME_ONLY"}),
                                ("counting", {"auto_review": True})]:
            config = _config()
            config[section].update(update)
            with self.subTest(section=section, update=update):
                with self.assertRaises(ValueError):
                    temporal.validate_temporal_config(config)


class RawMeasurementBoundaryTests(unittest.TestCase):
    def make_record(self):
        return temporal.build_track_record(_row(), _outputs(), variant="raw", parent_run_id="synthetic_parent", fps=30)

    def test_measurement_uses_exact_raw_bbox_and_never_filtered_tracker_box(self):
        row = _row()
        record = temporal.build_track_record(row, _outputs(), variant="raw", parent_run_id="synthetic_parent", fps=30)
        motor = record["emitted_tracks"][0]
        self.assertEqual(motor["raw_bbox"], [20, 30, 50, 60])
        self.assertEqual(motor["bbox"], [18, 28, 48, 58])
        self.assertEqual(motor["confidence"], row["detections"][0]["confidence"])
        self.assertEqual(motor["measurement_provenance"], "retained_phase_7_detection")
        self.assertTrue(temporal.check_source_record(record, 0, _identity()))

    def test_explicit_empty_assigned_observation_metadata_is_not_fabricated(self):
        record = temporal.build_track_record(_row(), _outputs(), variant="raw", parent_run_id="synthetic_parent", fps=30,
                                             assigned_observations=[], lifecycle_snapshots=[])
        self.assertEqual(record["assigned_observations_including_unconfirmed"], [])

    def test_raw_person_label_preserved_not_automatically_mapped_to_pedestrian(self):
        record = self.make_record()
        self.assertEqual(record["raw_detections"][1]["class_name"], "person")
        self.assertEqual(record["emitted_tracks"][1]["class_name"], "person")
        self.assertNotIn("pedestrian", json.dumps(record))

    def test_builder_is_immutable_and_native_frame_index_is_not_rebased(self):
        row, outputs = _row(747), _outputs()
        before_row, before_outputs = copy.deepcopy(row), copy.deepcopy(outputs)
        record = temporal.build_track_record(row, outputs, variant="raw", parent_run_id="synthetic_parent", fps=30)
        self.assertEqual(row, before_row)
        self.assertEqual(outputs, before_outputs)
        self.assertEqual(record["frame_index"], 747)
        self.assertEqual(record["emitted_tracks"][0]["frame_index"], 747)
        self.assertEqual(record["timestamp_estimate_from_index_fps_seconds"], 747 / 30)

    def test_duplicate_track_or_source_index_and_fractional_identity_rejected(self):
        for change in [(1, 4, 17), (1, 7, 0), (0, 4, 17.5), (0, 7, 0.5), (0, 4, True)]:
            outputs = _outputs()
            outputs[change[0]][change[1]] = change[2]
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    temporal.validate_emitted_outputs(outputs, _row())

    def test_tracker_class_or_score_mismatch_and_nonfinite_output_rejected(self):
        for column, value in [(6, 2), (5, 0.4), (0, float("nan")), (1, float("inf")), (7, 99)]:
            outputs = _outputs()
            outputs[0][column] = value
            with self.subTest(column=column, value=value):
                with self.assertRaises(ValueError):
                    temporal.validate_emitted_outputs(outputs, _row())

    def test_source_tampering_of_each_linked_value_is_rejected(self):
        for updates in [{"raw_bbox": [21, 30, 50, 60]}, {"class_id": 2}, {"class_name": "car"},
                        {"confidence": 0.9}, {"measurement_provenance": "retained_phase_2_detection"},
                        {"emitted": False}, {"original_detection_index": 1}]:
            record = self.make_record()
            record["emitted_tracks"][0].update(updates)
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    temporal.check_source_record(record, 0, _identity())

    def test_fullvideo_order_rejects_frame_one_as_first_and_unknown_input_identity(self):
        record = self.make_record()
        record["frame_index"] = 1
        with self.assertRaises(ValueError):
            temporal.check_source_record(record, 0, _identity())
        for update in [{"video_sha256": "0" * 64}, {"variant": "gamma_070"}, {"width": 1280}]:
            with self.subTest(update=update):
                with self.assertRaises(ValueError):
                    temporal.check_source_record(self.make_record(), 0, {**_identity(), **update})

    def test_raw_invalid_native_bbox_or_confidence_or_class_does_not_enter_cache(self):
        for updates in [{"bbox_xyxy_pixels": [-1, 30, 50, 60]}, {"bbox_xyxy_pixels": [20, 30, 101, 60]},
                        {"confidence": float("nan")}, {"class_id": True}, {"class_name": ""}]:
            record = self.make_record()
            record["raw_detections"][0].update(updates)
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    temporal.check_source_record(record, 0, _identity())

    def test_empty_detections_and_no_emitted_track_still_preserve_source_frame(self):
        row = _row()
        row["detections"] = []
        record = temporal.build_track_record(row, [], variant="raw", parent_run_id="synthetic_parent", fps=30)
        self.assertEqual(record["raw_detections"], [])
        self.assertEqual(record["emitted_tracks"], [])
        self.assertEqual(record["frame_index"], 0)
        self.assertTrue(temporal.check_source_record(record, 0, _identity()))

class Phase7ResolverAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phase7-temporal-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = Path(__file__).with_name("phase_6_identity_resolution_helpers.py")
        self.source_before = self.source.read_bytes()
        self.adapter = temporal.load_phase7_counting_adapter(self.source)

    def test_frozen_source_matches_binding_and_adapter_never_modifies_it(self):
        self.assertEqual(hashlib.sha256(self.source_before).hexdigest(), BASE_RESOLVER_SHA)
        self.assertEqual(self.source.read_bytes(), self.source_before)

    def test_wrong_base_source_hash_cannot_be_silently_adapted(self):
        with self.assertRaises(ValueError):
            temporal.load_phase7_counting_adapter(self.source, expected_sha="0" * 64)

    def test_new_measurement_provenance_is_preserved_without_fabricating_phase2(self):
        observation = _measurement(17, 0, [20, 30, 50, 60], "motorcycle", 0)
        normalized = self.adapter._validate_measurement(observation)
        self.assertEqual(normalized["measurement_provenance"], "retained_phase_7_detection")
        self.assertNotEqual(normalized["measurement_provenance"], "retained_phase_2_detection")

    def test_phase2_or_predicted_observation_cannot_enter_new_source_adapter(self):
        for provenance in ["retained_phase_2_detection", "kalman_prediction", None]:
            observation = _measurement(17, 0, [20, 30, 50, 60], "motorcycle", 0)
            observation["measurement_provenance"] = provenance
            with self.subTest(provenance=provenance):
                with self.assertRaises(ValueError):
                    self.adapter._validate_measurement(observation)

    def test_synthetic_motorcycle_rider_yields_one_vehicle_bc_event(self):
        fixture = _SourceFixture(self.root, [30, 35, 40, 48, 52, 60])
        outcome = self.adapter.run_identity_resolution(fixture.records_path, fixture.geometry_path, config=fixture.config)
        self.assertEqual(len(outcome["accepted_events"]), 1)
        event = outcome["accepted_events"][0]
        self.assertEqual(event["category"], "motorcycle")
        self.assertEqual(event["direction"], "A_TO_B")
        self.assertEqual(event["geometry_evidence"]["crossing_frame_start"], 3)
        self.assertEqual(event["geometry_evidence"]["crossing_frame_end"], 4)
        self.assertEqual(event["track_id"], 17)
        crossing_start = next(item for item in event["measurement_support"] if item["frame_index"] == 3)
        self.assertEqual(crossing_start["point"], [48.0, 60.0])
        self.assertTrue(event["accepted_count_event"])

    def test_future_rider_support_does_not_accept_earlier_crossing(self):
        fixture = _SourceFixture(self.root, [30, 35, 40, 48, 52, 60, 62, 65, 68], rider_start=5)
        outcome = self.adapter.run_identity_resolution(fixture.records_path, fixture.geometry_path, config=fixture.config)
        self.assertEqual(outcome["accepted_events"], [])
        self.assertTrue(all(item["status"] == "pending_review" for item in outcome["machine_decisions"]))
        self.assertIn("IDENTITY_RELATION_OUTSIDE_PASSAGE_WINDOW", outcome["machine_decisions"][0]["reasons"])

    def test_raw_bbox_link_tampering_fails_before_event_generation(self):
        fixture = _SourceFixture(self.root, [30, 35, 40, 48, 52, 60])
        fixture.records[3]["emitted_tracks"][0]["raw_bbox"][2] += 1
        fixture.write()
        with self.assertRaises(ValueError):
            self.adapter.run_identity_resolution(fixture.records_path, fixture.geometry_path, config=fixture.config)

    def test_gap_in_source_frame_records_cannot_be_silently_interpolated(self):
        fixture = _SourceFixture(self.root, [30, 35, 40, 48, 52, 60])
        fixture.records.pop(2)
        fixture.write()
        with self.assertRaises(ValueError):
            self.adapter.run_identity_resolution(fixture.records_path, fixture.geometry_path, config=fixture.config)


class EncoderBoundaryAndProviderTests(unittest.TestCase):
    def test_tracker_receives_same_transformed_donor_image_without_overlay_or_raw_fallback(self):
        frame = np.tile(np.array([40, 80, 120], np.uint8), (100, 100, 1))
        received = []

        class BoxesFixture:
            def __init__(self, values, orig_shape):
                self.values, self.orig_shape = values.copy(), orig_shape

        class TrackerFixture:
            def update(self, boxes, *, img, feats):
                received.append((boxes, img, feats))
                return _outputs()

        module = type("ResultsFixture", (), {"Boxes": BoxesFixture})
        with mock.patch.dict(sys.modules, {"ultralytics.engine.results": module}):
            output = temporal.update_tracker_on_transformed_frame(TrackerFixture(), _row(), frame)
        self.assertEqual(output, _outputs())
        self.assertIs(received[0][1], frame)
        self.assertIsNone(received[0][2])
        self.assertEqual(received[0][0].orig_shape, (100, 100))
        np.testing.assert_allclose(received[0][0].values[:, :4], [d["bbox_xyxy_pixels"] for d in _row()["detections"]])

    def test_encoder_donor_frame_requires_native_uint8_three_channels(self):
        tracker = mock.Mock()
        for frame in [np.zeros((100, 100), np.uint8), np.zeros((100, 100, 3), np.float32),
                      np.zeros((101, 100, 3), np.uint8), np.zeros((100, 100, 4), np.uint8)]:
            with self.subTest(shape=frame.shape, dtype=str(frame.dtype)):
                with mock.patch.dict(sys.modules, {"ultralytics.engine.results": type("ResultsFixture", (), {"Boxes": mock.Mock()})}):
                    with self.assertRaises(ValueError):
                        temporal.update_tracker_on_transformed_frame(tracker, _row(), frame)
        tracker.update.assert_not_called()

    def test_provider_configuration_names_or_cpu_nodes_never_establish_cuda_execution(self):
        for events in [[], [{"cat": "Session", "args": {"provider": "CUDAExecutionProvider"}}],
                       [{"cat": "Node", "args": {"provider": "CPUExecutionProvider"}}]]:
            with self.subTest(events=events):
                with self.assertRaises(ValueError):
                    temporal.provider_profile_evidence(events, execution_kind="SYNTHETIC_FIXTURE")

    def test_synthetic_cuda_profile_fixture_cannot_claim_actual_gpu_execution(self):
        events = [{"cat": "Node", "name": "SYNTHETIC_TEST_NODE", "args": {"provider": "CUDAExecutionProvider"}},
                  {"cat": "Node", "name": "SYNTHETIC_TEST_NODE", "args": {"provider": "CPUExecutionProvider"}}]
        evidence = temporal.provider_profile_evidence(events, execution_kind="SYNTHETIC_FIXTURE")
        self.assertFalse(evidence["actual_cuda_execution_confirmed"])
        self.assertEqual(evidence["execution_kind"], "SYNTHETIC_FIXTURE")
        self.assertEqual(evidence["provider_kernel_event_counts"], {"CUDAExecutionProvider": 1, "CPUExecutionProvider": 1})


class InputDecisionGateTests(unittest.TestCase):
    """Use unmodified retained DEV evidence as lineage, never invent GPU results."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phase7-input-decision-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        repository = Path(__file__).resolve().parent.parent
        self.plan_path = self.root / "sampling.json"
        original_plan = repository / "docs/evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json"
        shutil.copyfile(original_plan, self.plan_path)
        self.plan = json.loads(self.plan_path.read_text())
        screen_path = repository / "docs/evidence/phase_7/screening/20261014T060849_366767Z/report.json"
        retained_screen = json.loads(screen_path.read_text())
        self.assertEqual(retained_screen["execution_kind"], "ACTUAL_MODEL_EXECUTION")
        self.assertEqual(retained_screen["status"], "completed_detection_screen_no_temporal_claims")
        self.screen_run = retained_screen["run_id"]
        self.screen_copy = self.root / "docs/evidence/phase_7/screening" / self.screen_run / "report.json"
        self.screen_copy.parent.mkdir(parents=True)
        shutil.copyfile(screen_path, self.screen_copy)
        self.geometry_path = self.root / "geometry.json"
        approved_geometry = repository / "docs/evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json"
        shutil.copyfile(approved_geometry, self.geometry_path)
        self.geometry = json.loads(self.geometry_path.read_text())
        self.selection_path = self.root / "selection_SOFTWARE_FIXTURE_NOT_ACTUAL_SHORTLIST.json"
        selection = _selection()
        selection["source_detection_screen_run_id"] = self.screen_run
        selection["source_detection_screen_report_sha256"] = _sha(self.screen_copy)
        self.selection_path.write_text(json.dumps(selection))
        self.config = temporal.make_temporal_config(
            self.plan["input_identity"]["video_sha256"], _sha(self.plan_path), _sha(self.geometry_path), _sha(self.selection_path),
            repo_root=self.root, geometry_path=self.geometry_path, selection_path=self.selection_path)
        self.config.update(sampling_path=str(self.plan_path), variants=copy.deepcopy(VARIANTS),
                           video_path=str(self.root / "not_present_actual_video_no_model_execution.mp4"))

    def test_selection_file_sha_mismatch_stops_before_detector_or_encoder_setup(self):
        self.config["expected_selection_sha256"] = "0" * 64
        with mock.patch.object(temporal.night, "_actual_detector", side_effect=AssertionError("must not load detector")):
            with mock.patch.object(temporal, "_actual_tracker", side_effect=AssertionError("must not load encoder/tracker")):
                with self.assertRaisesRegex(ValueError, "Input SHA mismatch"):
                    temporal.run_night_temporal(self.config)

    def test_unapproved_geometry_stops_even_when_its_file_hash_matches_supplied_config(self):
        self.geometry["status"] = "PROPOSAL_NOT_HUMAN_APPROVED"
        self.geometry_path.write_text(json.dumps(self.geometry))
        self.config["expected_geometry_sha256"] = _sha(self.geometry_path)
        with self.assertRaisesRegex(ValueError, "Approved actual night geometry required"):
            temporal.verify_temporal_inputs(self.config)

    def test_other_video_geometry_stops_even_when_its_file_hash_matches(self):
        self.geometry["source_video"]["sha256"] = "0" * 64
        self.geometry_path.write_text(json.dumps(self.geometry))
        self.config["expected_geometry_sha256"] = _sha(self.geometry_path)
        with self.assertRaisesRegex(ValueError, "Approved actual night geometry required"):
            temporal.verify_temporal_inputs(self.config)

    def test_synthetic_screen_record_cannot_supply_actual_dev_model_proof(self):
        screen = json.loads(self.screen_copy.read_text())
        screen["execution_kind"] = "SYNTHETIC_FIXTURE"
        self.screen_copy.write_text(json.dumps(screen))
        selection = json.loads(self.selection_path.read_text())
        selection["source_detection_screen_report_sha256"] = _sha(self.screen_copy)
        self.selection_path.write_text(json.dumps(selection))
        self.config["expected_selection_sha256"] = _sha(self.selection_path)
        with self.assertRaisesRegex(ValueError, "Actual DEV-only detector outcome required"):
            temporal.verify_temporal_inputs(self.config)

    def rewrite_screen_fixture(self, mutate):
        # Every mutation below creates a negative software fixture from a copy.
        # The retained actual report in the repository is never edited.
        screen = json.loads(self.screen_copy.read_text())
        mutate(screen)
        self.screen_copy.write_text(json.dumps(screen))
        selection = json.loads(self.selection_path.read_text())
        selection["source_detection_screen_report_sha256"] = _sha(self.screen_copy)
        self.selection_path.write_text(json.dumps(selection))
        self.config["expected_selection_sha256"] = _sha(self.selection_path)

    def test_other_video_development_screen_cannot_supply_shortlist_evidence(self):
        self.rewrite_screen_fixture(lambda screen: screen["input_identity"].update(video_sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "Shortlist source video/native identity mismatch"):
            temporal.verify_temporal_inputs(self.config)

    def test_candidate_not_actually_screened_cannot_be_shortlisted(self):
        self.rewrite_screen_fixture(lambda screen: screen["configuration"].update(variants=[VARIANTS[0]]))
        with self.assertRaisesRegex(ValueError, "Shortlist candidate must actually have been screened"):
            temporal.verify_temporal_inputs(self.config)

    def test_changed_detector_between_development_and_temporal_run_is_rejected(self):
        self.rewrite_screen_fixture(lambda screen: screen["configuration"]["detector"]["settings"].update(conf=0.4))
        with self.assertRaisesRegex(ValueError, "Screen/temporal detector control mismatch"):
            temporal.verify_temporal_inputs(self.config)

    def test_holdout_used_in_screen_cannot_supply_development_selection(self):
        self.rewrite_screen_fixture(lambda screen: screen.update(holdout_enhancement_or_inference_executed=True))
        with self.assertRaisesRegex(ValueError, "Actual DEV-only detector outcome required"):
            temporal.verify_temporal_inputs(self.config)

    def test_geometry_approval_flags_must_be_explicit_true(self):
        self.geometry["geometry_contract_accepted"] = False
        self.geometry_path.write_text(json.dumps(self.geometry))
        self.config["expected_geometry_sha256"] = _sha(self.geometry_path)
        with self.assertRaisesRegex(ValueError, "Geometry/counting approval must be explicit"):
            temporal.verify_temporal_inputs(self.config)

class _RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"id": test.id(), "status": "passed"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({"id": test.id(), "status": "failed"})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({"id": test.id(), "status": "error"})


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2, resultclass=_RecordingResult).run(suite)
    return {
        "claim_type": "ACTUALLY_EXECUTED_SYNTHETIC_SOFTWARE_CONTRACT_TESTS",
        "scope": "Phase7 temporal lineage/control/source adaptation; no model/provider or real-video performance evidence",
        "fixture_controls_are_product_defaults": False,
        "successful": result.wasSuccessful(), "tests_run": result.testsRun,
        "tests_passed": sum(item["status"] == "passed" for item in result.records),
        "failures": [{"id": test.id(), "traceback": trace} for test, trace in result.failures],
        "errors": [{"id": test.id(), "traceback": trace} for test, trace in result.errors],
        "tests": result.records, "output": output.getvalue(),
    }


if __name__ == "__main__":
    summary = run_tests()
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["successful"] else 1)
