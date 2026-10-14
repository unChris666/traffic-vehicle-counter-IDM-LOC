"""Independent synthetic contract checks for the Phase 7 night screen.

All arrays, sample plans, identities, and injected detector responses in this
file are software fixtures. They are not TOR3-MALAM observations, YOLO outputs,
ground truth, or measurements of detector/tracker/counting performance.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import cv2
import numpy as np

import phase_7_night_helpers as engine


FIXTURE_VIDEO_SHA = "f" * 64


def _raw():
    return {"name": "raw", "method": "raw"}


def _gamma(value=0.7):
    return {"name": "gamma_fixture", "method": "gamma", "gamma": value}


def _exposure(value=1.25):
    return {"name": "exposure_fixture", "method": "exposure", "gain": value}


def _contrast(value=1.25, pivot=128.0):
    return {"name": "contrast_fixture", "method": "contrast", "factor": value, "pivot": pivot}


def _unsharp(amount=0.5, sigma=1.0):
    return {"name": "unsharp_fixture", "method": "unsharp", "sigma": sigma, "amount": amount}


def _plan():
    return {
        "schema_version": "phase7_sampling_v1",
        "status": "SYNTHETIC_SOFTWARE_FIXTURE_NOT_ACTUAL_VIDEO",
        "input_identity": {"video_sha256": FIXTURE_VIDEO_SHA, "width": 16,
                           "height": 12, "decoded_frame_count": 30},
        "development": {
            "segments": [{"segment_id": "dev_synthetic", "start_frame": 2, "end_frame": 5}],
            "sample_frame_indices": [2, 3, 5],
        },
        "holdout": {
            "segments": [{"segment_id": "holdout_synthetic", "start_frame": 20, "end_frame": 24}],
            "sample_frame_indices": [20, 22, 24],
        },
    }


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TransformTests(unittest.TestCase):
    def setUp(self):
        # Unequal channels deliberately exercise BGR preservation.
        self.frame = np.arange(6 * 9 * 3, dtype=np.uint8).reshape(6, 9, 3)

    def test_raw_is_bit_identical_separate_copy(self):
        output = engine.apply_transform(self.frame, _raw())
        np.testing.assert_array_equal(output, self.frame)
        self.assertFalse(np.shares_memory(output, self.frame))
        output[0, 0, 0] = 250
        self.assertEqual(int(self.frame[0, 0, 0]), 0)

    def test_every_transform_keeps_input_immutable_shape_uint8_and_native_channels(self):
        for variant in [_raw(), _gamma(), _exposure(), _contrast(), _unsharp()]:
            with self.subTest(method=variant["method"]):
                before = self.frame.copy()
                output = engine.apply_transform(self.frame, variant)
                np.testing.assert_array_equal(self.frame, before)
                self.assertEqual(output.shape, self.frame.shape)
                self.assertEqual(output.dtype, np.uint8)
                self.assertFalse(np.shares_memory(output, self.frame))

    def test_gamma_matches_documented_exponent_and_rounding(self):
        output = engine.apply_transform(self.frame, _gamma(0.7))
        reference = np.rint(255 * (self.frame.astype(np.float64) / 255) ** 0.7).astype(np.uint8)
        np.testing.assert_array_equal(output, reference)

    def test_gamma_identity_and_black_white_endpoints(self):
        ramp = np.repeat(np.arange(256, dtype=np.uint8).reshape(1, 256, 1), 3, axis=2)
        np.testing.assert_array_equal(engine.apply_transform(ramp, _gamma(1.0)), ramp)
        output = engine.apply_transform(ramp, _gamma(0.7))
        self.assertEqual(int(output[0, 0, 0]), 0)
        self.assertEqual(int(output[0, 255, 0]), 255)

    def test_gamma_is_monotonic_and_subunit_exponent_brightens_midtones(self):
        ramp = np.repeat(np.arange(256, dtype=np.uint8).reshape(1, 256, 1), 3, axis=2)
        output = engine.apply_transform(ramp, _gamma(0.7))
        self.assertTrue(np.all(np.diff(output[0, :, 0].astype(int)) >= 0))
        self.assertGreater(int(output[0, 64, 0]), 64)

    def test_exposure_clips_without_uint8_overflow(self):
        frame = np.array([[[0, 100, 250], [10, 128, 255]]], dtype=np.uint8)
        output = engine.apply_transform(frame, _exposure(2.0))
        np.testing.assert_array_equal(output, [[[0, 200, 255], [20, 255, 255]]])

    def test_exposure_identity_preserves_bgr_order(self):
        frame = np.array([[[17, 80, 203]]], dtype=np.uint8)
        np.testing.assert_array_equal(engine.apply_transform(frame, _exposure(1.0)), frame)

    def test_contrast_uses_explicit_fixed_pivot(self):
        frame = np.array([[[64, 128, 192], [0, 100, 255]]], dtype=np.uint8)
        np.testing.assert_array_equal(engine.apply_transform(frame, _contrast(2.0)),
                                      [[[0, 128, 255], [0, 72, 255]]])

    def test_contrast_identity_is_not_scene_dependent(self):
        np.testing.assert_array_equal(engine.apply_transform(self.frame, _contrast(1.0)), self.frame)

    def test_unsharp_uniform_frame_is_unchanged(self):
        frame = np.tile(np.array([17, 128, 240], dtype=np.uint8), (11, 13, 1))
        np.testing.assert_array_equal(engine.apply_transform(frame, _unsharp(2.0)), frame)

    def test_unsharp_matches_float_reference_with_reflect_border(self):
        frame = np.zeros((9, 9, 3), dtype=np.uint8)
        frame[4, 4] = [255, 180, 90]
        floating = frame.astype(np.float64)
        blurred = cv2.GaussianBlur(floating, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
        reference = np.clip(np.rint(floating + 1.5 * (floating - blurred)), 0, 255).astype(np.uint8)
        np.testing.assert_array_equal(engine.apply_transform(frame, _unsharp(1.5)), reference)

    def test_unsharp_no_wrapping_at_negative_or_saturated_edges(self):
        frame = np.zeros((11, 11, 3), dtype=np.uint8)
        frame[:, 5:] = 255
        output = engine.apply_transform(frame, _unsharp(4.0))
        self.assertTrue(np.all(output[:, 4] == 0))
        self.assertTrue(np.all(output[:, 5] == 255))

    def test_transforms_reject_invalid_frame_dtype_and_shape(self):
        for frame in [np.zeros((2, 3), np.uint8), np.zeros((2, 3, 4), np.uint8),
                      np.zeros((2, 3, 3), np.float32), np.zeros((0, 3, 3), np.uint8)]:
            with self.subTest(shape=frame.shape, dtype=str(frame.dtype)):
                with self.assertRaises(ValueError):
                    engine.apply_transform(frame, _raw())


class VariantValidationTests(unittest.TestCase):
    def test_one_explicit_raw_and_distinct_single_operation_variants_are_valid(self):
        engine.validate_variants([_raw(), _gamma(), _exposure(), _contrast(), _unsharp()])

    def test_raw_required_and_duplicate_names_rejected(self):
        for variants in [[_gamma()], [_raw(), _raw()], [_raw(), {"name": "raw", "method": "gamma", "gamma": 0.7}]]:
            with self.subTest(variants=variants):
                with self.assertRaises(ValueError):
                    engine.validate_variants(variants)

    def test_unsupported_combination_and_hidden_operation_rejected(self):
        for variant in [{"name": "clahe", "method": "clahe", "clip": 2},
                        {"name": "combo", "method": "gamma_exposure", "gamma": 0.7, "gain": 1.2},
                        {"name": "hidden", "method": "raw", "gamma": 0.7}]:
            with self.subTest(variant=variant):
                with self.assertRaises(ValueError):
                    engine.validate_variants([_raw(), variant])

    def test_missing_parameter_is_not_silently_defaulted(self):
        for method in ["gamma", "exposure", "contrast", "unsharp"]:
            with self.subTest(method=method):
                with self.assertRaises(ValueError):
                    engine.validate_variants([_raw(), {"name": "missing", "method": method}])

    def test_nan_infinity_boolean_and_nonpositive_parameters_rejected(self):
        for factory in [_gamma, _exposure, _contrast]:
            for value in [float("nan"), float("inf"), -1.0, 0.0, True, "0.7"]:
                with self.subTest(factory=factory.__name__, value=value):
                    with self.assertRaises(ValueError):
                        engine.validate_variants([_raw(), factory(value)])

    def test_sharpen_requires_positive_sigma_and_nonnegative_amount(self):
        for variant in [_unsharp(sigma=0), _unsharp(sigma=float("nan")), _unsharp(amount=-0.1),
                        _unsharp(amount=float("inf")), _unsharp(amount=True)]:
            with self.subTest(variant=variant):
                with self.assertRaises(ValueError):
                    engine.validate_variants([_raw(), variant])

    def test_pivot_is_explicit_finite_in_intensity_range(self):
        for pivot in [float("nan"), float("inf"), -1, 256, True]:
            with self.subTest(pivot=pivot):
                with self.assertRaises(ValueError):
                    engine.validate_variants([_raw(), _contrast(pivot=pivot)])


class SamplingPlanTests(unittest.TestCase):
    def test_development_indices_returned_only_not_holdout(self):
        self.assertEqual(engine.verify_sampling_plan(_plan()), [2, 3, 5])

    def test_sampling_indices_are_original_native_indices_not_rebased(self):
        plan = _plan()
        plan["development"]["segments"] = [{"segment_id": "late_dev", "start_frame": 10, "end_frame": 14}]
        plan["development"]["sample_frame_indices"] = [10, 12, 14]
        self.assertEqual(engine.verify_sampling_plan(plan), [10, 12, 14])

    def test_inclusive_touching_segment_boundary_is_leakage(self):
        plan = _plan()
        plan["holdout"]["segments"][0]["start_frame"] = 5
        with self.assertRaises(ValueError):
            engine.verify_sampling_plan(plan)

    def test_overlap_is_rejected_even_without_overlapping_sampled_indices(self):
        plan = _plan()
        plan["holdout"]["segments"][0].update(start_frame=4, end_frame=24)
        with self.assertRaises(ValueError):
            engine.verify_sampling_plan(plan)

    def test_samples_outside_own_segment_are_rejected(self):
        for section, value in [("development", 6), ("holdout", 25)]:
            plan = _plan()
            plan[section]["sample_frame_indices"].append(value)
            with self.subTest(section=section):
                with self.assertRaises(ValueError):
                    engine.verify_sampling_plan(plan)

    def test_duplicate_unsorted_or_boolean_frame_indices_are_rejected(self):
        for indices in [[2, 2, 3], [3, 2, 5], [True, 2, 3], [2.0, 3, 5]]:
            plan = _plan()
            plan["development"]["sample_frame_indices"] = indices
            with self.subTest(indices=indices):
                with self.assertRaises(ValueError):
                    engine.verify_sampling_plan(plan)

    def test_segment_bounds_require_valid_native_integer_frames(self):
        for updates in [{"start_frame": -1}, {"start_frame": True}, {"end_frame": 30},
                        {"start_frame": 7, "end_frame": 5}, {"end_frame": 5.5}]:
            plan = _plan()
            plan["development"]["segments"][0].update(updates)
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    engine.verify_sampling_plan(plan)

    def test_plan_does_not_mutate_input(self):
        plan = _plan()
        before = copy.deepcopy(plan)
        engine.verify_sampling_plan(plan)
        self.assertEqual(plan, before)

    def test_plan_identity_hash_or_native_dimensions_mismatch_is_rejected(self):
        matching = {"video_sha256": FIXTURE_VIDEO_SHA, "width": 16, "height": 12}
        for update in [{"video_sha256": "e" * 64}, {"width": 17}, {"height": 13}]:
            identity = {**matching, **update}
            with self.subTest(update=update):
                with self.assertRaises(ValueError):
                    engine.verify_sampling_plan(_plan(), identity)

    def test_within_split_overlap_is_rejected(self):
        plan = _plan()
        plan["development"]["segments"].append({"segment_id": "other", "start_frame": 4, "end_frame": 8})
        with self.assertRaises(ValueError):
            engine.verify_sampling_plan(plan)


def _detector_config():
    return {
        "package_version": "8.4.175", "device": 0,
        "weights_path": "/tmp/synthetic_tests_do_not_load_yolo26m.pt",
        "weights_url": engine.MODEL_URL, "weights_sha256": engine.MODEL_SHA256,
        "weights_bytes": engine.MODEL_BYTES,
        "settings": copy.deepcopy(engine.DEFAULT_DETECTOR_SETTINGS),
    }


def _config():
    return {
        "expected_video_sha256": FIXTURE_VIDEO_SHA,
        "expected_sampling_sha256": "a" * 64,
        "variants": [_raw(), _gamma()], "max_dev_samples": 10,
        "detector": _detector_config(),
    }


class ConfigurationTests(unittest.TestCase):
    def test_explicit_frozen_detection_control_is_accepted_without_mutation(self):
        config = _config()
        before = copy.deepcopy(config)
        validated = engine.validate_config(config, "detection")
        self.assertEqual(config, before)
        self.assertEqual(validated["detector"]["settings"], before["detector"]["settings"])

    def test_changed_detector_settings_rejected_before_model_execution(self):
        for update in [{"conf": 0.4}, {"imgsz": 320}, {"classes": [3]}, {"rect": False},
                       {"batch": 2}, {"seed": 1}, {"quantize": "int8"}]:
            config = _config()
            config["detector"]["settings"].update(update)
            with self.subTest(update=update):
                with self.assertRaises(ValueError):
                    engine.validate_config(config, "detection")

    def test_boolean_or_different_numeric_type_cannot_masquerade_as_frozen_setting(self):
        for update in [{"batch": True}, {"max_det": 300.0}, {"imgsz": 640.0}, {"rect": 1}]:
            config = _config()
            config["detector"]["settings"].update(update)
            with self.subTest(update=update):
                with self.assertRaises(ValueError):
                    engine.validate_config(config, "detection")

    def test_detector_asset_package_and_explicit_device_are_not_silently_replaced(self):
        for update in [{"package_version": "8.4.174"}, {"weights_sha256": "0" * 64},
                       {"weights_bytes": 1}, {"weights_url": "https://example.invalid/other.pt"},
                       {"device": "cpu"}, {"device": True}, {"device": -1}, {"weights_path": ""}]:
            config = _config()
            config["detector"].update(update)
            with self.subTest(update=update):
                with self.assertRaises(ValueError):
                    engine.validate_config(config, "detection")

    def test_missing_detector_in_detection_mode_is_rejected(self):
        config = _config()
        del config["detector"]
        with self.assertRaises(ValueError):
            engine.validate_config(config, "detection")

    def test_invalid_input_hash_and_nonpositive_or_oversized_budget_rejected(self):
        for update in [{"expected_video_sha256": None}, {"expected_sampling_sha256": "not-a-hash"},
                       {"max_dev_samples": True}, {"max_dev_samples": 0}, {"max_dev_samples": 51}]:
            with self.subTest(update=update):
                with self.assertRaises(ValueError):
                    engine.validate_config({**_config(), **update}, "photometric")

    def test_unknown_screen_mode_cannot_silently_run_later_phase(self):
        with self.assertRaises(ValueError):
            engine.validate_config(_config(), "full_pipeline")


class SyntheticScreenTests(unittest.TestCase):
    """A tiny FFV1 software video plus explicitly injected synthetic detections."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phase7-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.video = self.root / "software_fixture_not_TOR3.avi"
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"FFV1"), 10, (16, 12))
        if not writer.isOpened():
            writer.release()
            self.fail("FFV1 encoder unavailable: synthetic video fixture cannot execute")
        self.frames = {}
        try:
            for index in range(30):
                frame = np.tile(np.array([index, 2 * index, 100 + index], dtype=np.uint8), (12, 16, 1))
                self.frames[index] = frame
                writer.write(frame)
        finally:
            writer.release()
        self.plan = _plan()
        self.plan["input_identity"]["video_sha256"] = _sha(self.video)
        self.sampling = self.root / "software_sampling.json"
        self.sampling.write_text(json.dumps(self.plan), encoding="utf-8")
        self.config = _config()
        self.config.update(expected_video_sha256=_sha(self.video), expected_sampling_sha256=_sha(self.sampling))
        self.calls = []

    def detector(self, frame, index, variant_name):
        self.calls.append({"frame_index": index, "variant": variant_name, "pixels": frame.copy()})
        return {"detections": [{"bbox_xyxy": [1, 2, 8, 10], "confidence": 0.8,
                                "class_id": 3, "class_name": "motorcycle"}],
                "class_names": {3: "motorcycle"}, "speed_ms": {}}

    def execute(self):
        return engine.run_screen(self.video, self.sampling, self.root / "outputs",
                                 config=self.config, mode="detection", detector=self.detector)

    def test_decoder_keeps_native_frame_numbers_and_pixels(self):
        frames, metadata = engine.decode_dev_frames(self.video, [2, 3, 5])
        self.assertEqual(list(frames), [2, 3, 5])
        self.assertEqual((metadata["width"], metadata["height"]), (16, 12))
        self.assertEqual(metadata["sequential_decoded_frames"], 6)
        for index in frames:
            np.testing.assert_array_equal(frames[index], self.frames[index])

    def test_all_variants_use_identical_dev_indices_not_holdout_and_record_warmup_separately(self):
        report = self.execute()
        self.assertEqual(report["sample_indices"], [2, 3, 5])
        for item in report["variants"]:
            name = item["variant"]["name"]
            calls = [entry for entry in self.calls if entry["variant"] == name]
            self.assertEqual([entry["frame_index"] for entry in calls], [2, 2, 3, 5])
            self.assertEqual(item["sample_indices"], [2, 3, 5])
            self.assertEqual(item["prediction_calls_measured"], 3)
            self.assertFalse(item["warmup"]["saved_as_measurement"])
            self.assertTrue(item["warmup"]["timing_excluded_from_prediction_statistics"])
        self.assertFalse(report["holdout_enhancement_or_inference_executed"])

    def test_callback_receives_documented_transform_of_same_native_source(self):
        self.execute()
        variants = {item["name"]: item for item in self.config["variants"]}
        for call in self.calls:
            reference = engine.apply_transform(self.frames[call["frame_index"]], variants[call["variant"]])
            np.testing.assert_array_equal(call["pixels"], reference)

    def test_fixture_results_cannot_claim_actual_inference_temporal_pipeline_or_counting(self):
        report = self.execute()
        self.assertEqual(report["execution_kind"], "SYNTHETIC_FIXTURE")
        self.assertEqual(report["status"], "completed_synthetic_fixture")
        self.assertFalse(report["resource"]["model_inference_executed"])
        self.assertTrue(report["resource"]["fixture_detection_outputs_not_model_evidence"])
        self.assertFalse(report["temporal_pipeline_executed"])
        self.assertFalse(report["count_events_generated"])
        self.assertIsNone(report["selected_configuration"])
        for item in report["variants"]:
            self.assertEqual(item["detection_class_observation_totals"], {"motorcycle": 3})
            self.assertIn("not physical units/counts/quality", item["observation_totals_limits"])
            self.assertEqual(item["resource"], {})

    def test_serialized_native_records_have_input_provenance_and_no_count_authorization(self):
        report = self.execute()
        for item in report["variants"]:
            with gzip.open(item["detections_path"], "rt", encoding="utf-8") as stream:
                rows = [json.loads(line) for line in stream]
            self.assertEqual([row["frame_index"] for row in rows], [2, 3, 5])
            for row in rows:
                self.assertEqual(row["input_video_sha256"], _sha(self.video))
                self.assertEqual(row["coordinate_space"], "native_full_frame_xyxy_pixels")
                self.assertEqual(row["execution_kind"], "SYNTHETIC_FIXTURE")
                self.assertFalse(row["accepted_count_event"])

    def test_retained_manifest_hashes_match_actual_written_artifacts(self):
        report = self.execute()
        output = Path(report["output_directory"])
        manifest = json.loads((output / "manifest.json").read_text())
        for artifact in manifest["artifacts"]:
            target = output / artifact["path"]
            self.assertEqual(artifact["bytes"], target.stat().st_size)
            self.assertEqual(artifact["sha256"], _sha(target))

    def test_exact_helper_source_is_retained_with_bound_hash(self):
        report = self.execute()
        source = Path(report["output_directory"]) / "phase_7_night_helpers.executed_source.py.gz"
        with gzip.open(source, "rb") as stream:
            executed = stream.read()
        self.assertEqual(hashlib.sha256(executed).hexdigest(), report["source_helper_sha256"])
        self.assertEqual(executed, Path(engine.__file__).read_bytes())

    def test_video_hash_mismatch_fails_before_decode_or_any_detector_call(self):
        self.config["expected_video_sha256"] = "0" * 64
        with mock.patch.object(engine, "decode_dev_frames", side_effect=AssertionError("must not decode")):
            with self.assertRaises(ValueError):
                self.execute()
        self.assertEqual(self.calls, [])

    def test_sampling_hash_mismatch_fails_before_decode_or_any_detector_call(self):
        self.config["expected_sampling_sha256"] = "0" * 64
        with mock.patch.object(engine, "decode_dev_frames", side_effect=AssertionError("must not decode")):
            with self.assertRaises(ValueError):
                self.execute()
        self.assertEqual(self.calls, [])

    def test_sample_budget_guard_fails_before_decode_or_any_detector_call(self):
        self.config["max_dev_samples"] = 2
        with mock.patch.object(engine, "decode_dev_frames", side_effect=AssertionError("must not decode")):
            with self.assertRaises(ValueError):
                self.execute()
        self.assertEqual(self.calls, [])

    def test_photometric_mode_cannot_hide_detector_execution(self):
        with self.assertRaises(ValueError):
            engine.run_screen(self.video, self.sampling, self.root / "outputs", config=self.config,
                              mode="photometric", detector=self.detector)
        self.assertEqual(self.calls, [])

    def test_invalid_callback_bbox_fails_without_generating_count_evidence(self):
        def invalid(frame, index, variant):
            result = self.detector(frame, index, variant)
            result["detections"][0]["bbox_xyxy"][2] = 17
            return result
        with self.assertRaises(ValueError):
            engine.run_screen(self.video, self.sampling, self.root / "outputs", config=self.config,
                              mode="detection", detector=invalid)
        failed = list((self.root / "outputs").glob("*/report.json"))
        self.assertEqual(len(failed), 1)
        report = json.loads(failed[0].read_text())
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["count_events_generated"])

    def test_callback_cannot_change_raw_class_mapping_between_variants(self):
        def changed(frame, index, variant):
            result = self.detector(frame, index, variant)
            if variant != "raw":
                result["class_names"][99] = "synthetic_added_label"
            return result
        with self.assertRaises(ValueError):
            engine.run_screen(self.video, self.sampling, self.root / "outputs", config=self.config,
                              mode="detection", detector=changed)

    def test_callback_speed_descriptor_must_be_finite_not_fabricated_nan(self):
        def invalid(frame, index, variant):
            result = self.detector(frame, index, variant)
            result["speed_ms"] = {"inference": float("nan")}
            return result
        with self.assertRaises(ValueError):
            engine.run_screen(self.video, self.sampling, self.root / "outputs", config=self.config,
                              mode="detection", detector=invalid)

    def test_model_setup_failure_is_retained_as_failure_never_cpu_fallback(self):
        with mock.patch.object(engine, "_actual_detector", side_effect=RuntimeError("synthetic unavailable CUDA guard")):
            with self.assertRaises(RuntimeError):
                engine.run_screen(self.video, self.sampling, self.root / "outputs", config=self.config,
                                  mode="detection")
        reports = list((self.root / "outputs").glob("*/report.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["resource"]["model_inference_executed"])
        self.assertFalse(report["count_events_generated"])
        self.assertEqual(report["variants"], [])


class ExplicitGpuGuardTests(unittest.TestCase):
    def test_explicit_cuda_probe_records_selected_device_without_inference(self):
        torch_stub = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True,
                                                                      device_count=lambda: 2))
        with mock.patch.dict("sys.modules", {"torch": torch_stub}):
            resource = engine.verify_gpu_device(1)
        self.assertEqual(resource["execution_device"], "cuda:1")
        self.assertEqual(resource["visible_cuda_device_count"], 2)

    def test_unavailable_selected_cuda_never_loads_weights_or_constructs_yolo(self):
        for available, count, selected in [(False, 0, 0), (True, 1, 1)]:
            cuda = types.SimpleNamespace(is_available=lambda: available, device_count=lambda: count)
            torch_stub = types.SimpleNamespace(cuda=cuda)
            yolo = mock.Mock(side_effect=AssertionError("YOLO must not be constructed"))
            config = _detector_config()
            config["device"] = selected
            with self.subTest(available=available, count=count, selected=selected):
                with mock.patch.dict("sys.modules", {"torch": torch_stub, "ultralytics": types.SimpleNamespace(YOLO=yolo)}):
                    with mock.patch.object(engine.importlib.metadata, "version", return_value="8.4.175"):
                        with mock.patch.object(engine, "_download_weights", side_effect=AssertionError("must not download")):
                            with self.assertRaises(RuntimeError):
                                engine._actual_detector(config)
                yolo.assert_not_called()


class DetectionRowsAndStageTests(unittest.TestCase):
    def setUp(self):
        self.names = {0: "person", 2: "car", 3: "motorcycle"}
        self.rows = [{"bbox_xyxy": [1, 2, 8, 10], "confidence": 0.8,
                      "class_id": 3, "class_name": "motorcycle"}]

    def test_valid_native_bbox_and_raw_class_mapping(self):
        rows = engine.validate_detection_rows(copy.deepcopy(self.rows), 16, 12, self.names)
        self.assertEqual(rows[0]["class_name"], "motorcycle")
        self.assertEqual(rows[0]["bbox_xyxy"], [1, 2, 8, 10])

    def test_invalid_bbox_nan_outside_or_reversed_rejected(self):
        for box in [[float("nan"), 2, 8, 10], [-1, 2, 8, 10], [1, 2, 17, 10],
                    [1, 2, 8, 13], [8, 2, 1, 10], [1, 2, 1, 10]]:
            rows = copy.deepcopy(self.rows)
            rows[0]["bbox_xyxy"] = box
            with self.subTest(box=box):
                with self.assertRaises(ValueError):
                    engine.validate_detection_rows(rows, 16, 12, self.names)

    def test_confidence_must_be_finite_probability(self):
        for confidence in [float("nan"), float("inf"), -0.1, 1.1, True]:
            rows = copy.deepcopy(self.rows)
            rows[0]["confidence"] = confidence
            with self.subTest(confidence=confidence):
                with self.assertRaises(ValueError):
                    engine.validate_detection_rows(rows, 16, 12, self.names)

    def test_unknown_class_or_inconsistent_label_not_silently_mapped(self):
        for updates in [{"class_id": 99}, {"class_name": "pedestrian"}, {"class_id": True}]:
            rows = copy.deepcopy(self.rows)
            rows[0].update(updates)
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    engine.validate_detection_rows(rows, 16, 12, self.names)

    def test_no_geometry_or_counting_from_detection_even_claimed_approval(self):
        for stage in ["tracking", "reid", "geometry", "counting", "aggregation"]:
            with self.subTest(stage=stage):
                with self.assertRaises(ValueError):
                    engine.validate_stage_gate({"night_geometry_approved": True}, stage)

    def test_only_implemented_screen_stages_pass_stage_gate(self):
        for stage in ["photometric", "detection"]:
            engine.validate_stage_gate({}, stage)


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
        "scope": "Phase 7 transformations, controlled DEV sampling and detector-output gates; no actual-video/model results",
        "fixture_controls_are_product_defaults": False,
        "successful": result.wasSuccessful(), "tests_run": result.testsRun,
        "tests_passed": sum(item["status"] == "passed" for item in result.records),
        "failures": [{"id": test.id(), "traceback": trace} for test, trace in result.failures],
        "errors": [{"id": test.id(), "traceback": trace} for test, trace in result.errors],
        "skipped": [{"id": test.id(), "reason": reason} for test, reason in result.skipped],
        "tests": result.records, "output": output.getvalue(),
    }


if __name__ == "__main__":
    summary = run_tests()
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["successful"] else 1)
