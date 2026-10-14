"""Phase 7 development-only photometric and full-frame detector screening.

This prototype does not implement tracking, ReID, geometry replay or counting.
Sparse detection samples cannot establish temporal identity or traffic volume.
Optional image/model dependencies are imported only when their stage is used.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from urllib.request import urlopen


MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26m.pt"
MODEL_SHA256 = "401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7"
MODEL_BYTES = 44255705
PACKAGE_VERSION = "8.4.175"
DEFAULT_DETECTOR_SETTINGS = {
    "conf": 0.25, "imgsz": 640, "iou": 0.7, "max_det": 300,
    "quantize": None, "nms": None, "classes": None, "rect": True,
    "augment": False, "agnostic_nms": False, "batch": 1, "seed": 0,
}
DEFAULT_VARIANTS = [
    {"name": "raw", "method": "raw"},
    {"name": "gamma_070", "method": "gamma", "gamma": 0.7},
    {"name": "exposure_125", "method": "exposure", "gain": 1.25},
    {"name": "contrast_125", "method": "contrast", "factor": 1.25, "pivot": 128.0},
    {"name": "unsharp_s1_a05", "method": "unsharp", "sigma": 1.0, "amount": 0.5},
]
TRANSFORM_FORMULAE = {
    "raw": "output = input.copy()",
    "gamma": "output = round_clip_uint8(255 * (input / 255) ** gamma)",
    "exposure": "output = round_clip_uint8(gain * input)",
    "contrast": "output = round_clip_uint8(pivot + factor * (input - pivot))",
    "unsharp": "output = round_clip_uint8(input + amount * (input - GaussianBlur(input, sigma, BORDER_REFLECT_101)))",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _positive_integer(value, name, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if allow_zero else 1):
        raise ValueError(f"{name} must be {'nonnegative' if allow_zero else 'positive'} integer")
    return value


def _number(value, name, low=None, high=None, strict_low=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite number")
    if low is not None and (value <= low if strict_low else value < low):
        raise ValueError(f"{name} is below its valid range")
    if high is not None and value > high:
        raise ValueError(f"{name} is above its valid range")
    return value


def _hash(value, name):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _same_typed_value(first, second):
    if type(first) is not type(second):
        return False
    if isinstance(first, dict):
        return set(first) == set(second) and all(_same_typed_value(first[key], second[key]) for key in first)
    if isinstance(first, list):
        return len(first) == len(second) and all(_same_typed_value(a, b) for a, b in zip(first, second))
    return first == second


def validate_variants(variants):
    if not isinstance(variants, list) or not variants:
        raise ValueError("variants must be a nonempty explicit list")
    seen, raw_count = set(), 0
    keys = {
        "raw": set(), "gamma": {"gamma"}, "exposure": {"gain"},
        "contrast": {"factor", "pivot"}, "unsharp": {"sigma", "amount"},
    }
    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError("each variant must be object")
        name, method = variant.get("name"), variant.get("method")
        if not isinstance(name, str) or re.fullmatch(r"[a-zA-Z0-9_-]+", name) is None or name in seen:
            raise ValueError("variant names must be unique safe identifiers")
        if method not in keys or set(variant) != {"name", "method"} | keys[method]:
            raise ValueError("variant fields must exactly match the documented transformation")
        seen.add(name)
        raw_count += method == "raw"
        if method == "gamma":
            _number(variant["gamma"], "gamma", 0, strict_low=True)
        elif method == "exposure":
            _number(variant["gain"], "gain", 0, strict_low=True)
        elif method == "contrast":
            _number(variant["factor"], "factor", 0, strict_low=True)
            _number(variant["pivot"], "pivot", 0, 255)
        elif method == "unsharp":
            _number(variant["sigma"], "sigma", 0, strict_low=True)
            _number(variant["amount"], "amount", 0)
    if raw_count != 1:
        raise ValueError("exactly one raw baseline is mandatory")
    return copy.deepcopy(variants)


def apply_transform(frame_bgr, variant):
    import numpy as np
    if not isinstance(variant, dict):
        raise ValueError("variant must be object")
    validate_variants([variant] if variant.get("method") == "raw" else [DEFAULT_VARIANTS[0], variant])
    if not isinstance(frame_bgr, np.ndarray) or frame_bgr.dtype != np.uint8 or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3 or min(frame_bgr.shape[:2]) < 1:
        raise ValueError("input must be nonempty native HxWx3 BGR uint8")
    method = variant["method"]
    if method == "raw":
        return frame_bgr.copy()
    pixels = frame_bgr.astype(np.float64)
    if method == "gamma":
        pixels = 255.0 * np.power(pixels / 255.0, variant["gamma"])
    elif method == "exposure":
        pixels *= variant["gain"]
    elif method == "contrast":
        pixels = variant["pivot"] + variant["factor"] * (pixels - variant["pivot"])
    elif method == "unsharp":
        import cv2
        blurred = cv2.GaussianBlur(pixels, (0, 0), sigmaX=variant["sigma"], sigmaY=variant["sigma"], borderType=cv2.BORDER_REFLECT_101)
        pixels += variant["amount"] * (pixels - blurred)
    return np.clip(np.rint(pixels), 0, 255).astype(np.uint8)


def validate_stage_gate(config, stage):
    if stage not in {"photometric", "detection"}:
        raise ValueError("Only photometric/detection DEV screening is implemented; night temporal/geometry/counting needs separate approved task")
    return True


def validate_config(config, mode):
    validate_stage_gate(config, mode)
    if not isinstance(config, dict):
        raise ValueError("config must be object")
    _hash(config.get("expected_video_sha256"), "expected_video_sha256")
    _hash(config.get("expected_sampling_sha256"), "expected_sampling_sha256")
    variants = validate_variants(config.get("variants", copy.deepcopy(DEFAULT_VARIANTS)))
    maximum = _positive_integer(config.get("max_dev_samples", 50), "max_dev_samples")
    if maximum > 50:
        raise ValueError("Stage1 DEV engineering budget is at most 50 sparse samples")
    detector = config.get("detector")
    if mode == "detection" and detector is None:
        raise ValueError("detection requires explicit frozen detector config")
    if detector is not None:
        if not isinstance(detector, dict):
            raise ValueError("detection requires explicit frozen detector config")
        allowed = {"package_version", "device", "weights_path", "weights_url", "weights_sha256", "weights_bytes", "settings", "baseline_provenance"}
        if set(detector) - allowed:
            raise ValueError("unknown detector config fields; no ignored inference overrides")
        if detector.get("package_version") != PACKAGE_VERSION or detector.get("weights_url") != MODEL_URL or detector.get("weights_sha256") != MODEL_SHA256 or detector.get("weights_bytes") != MODEL_BYTES:
            raise ValueError("detector package/asset must match retained Phase2 baseline")
        if not _same_typed_value(detector.get("settings"), DEFAULT_DETECTOR_SETTINGS):
            raise ValueError("detector settings must exactly match frozen Phase2 screening control")
        _positive_integer(detector.get("device"), "CUDA device index", allow_zero=True)
        if not isinstance(detector.get("weights_path"), str) or not detector["weights_path"]:
            raise ValueError("detector weights_path required")
    return {**copy.deepcopy(config), "variants": variants, "max_dev_samples": maximum}


def make_screen_config(expected_video_sha256, expected_sampling_sha256, *, weights_path="/kaggle/working/phase_7_night/weights/yolo26m.pt", device=0):
    """Explicit untuned engineering controls shared by CPU/GPU screening modes."""
    config = {
        "contract_version": "phase7_dev_screen_v1",
        "expected_video_sha256": expected_video_sha256,
        "expected_sampling_sha256": expected_sampling_sha256,
        "variants": copy.deepcopy(DEFAULT_VARIANTS), "max_dev_samples": 50,
        "parameter_status": "ENGINEERING_TEST_POINTS_NOT_SELECTED_PRODUCTION_SETTINGS",
        "detector": {
            "package_version": PACKAGE_VERSION, "device": device,
            "weights_path": str(weights_path), "weights_url": MODEL_URL,
            "weights_sha256": MODEL_SHA256, "weights_bytes": MODEL_BYTES,
            "settings": copy.deepcopy(DEFAULT_DETECTOR_SETTINGS),
            "baseline_provenance": "docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/detection_report.json",
        },
        "night_geometry_status": "PROPOSED_NOT_APPROVED_NO_TEMPORAL_EXECUTION",
        "later_counting_profile": "phase6_option_b_v1_with_explicit_review_overlay_offline",
        "later_counting_parameters_status": "FROZEN_NO_TUNING_IN_ENHANCEMENT_COMPARISON",
    }
    return validate_config(config, "detection")


def verify_gpu_device(device):
    _positive_integer(device, "CUDA device index", allow_zero=True)
    import torch
    if not torch.cuda.is_available() or device >= torch.cuda.device_count():
        raise RuntimeError("Explicit selected CUDA device unavailable; CPU fallback is forbidden")
    return {"execution_device": f"cuda:{device}", "cuda_available": True, "visible_cuda_device_count": torch.cuda.device_count()}


def verify_sampling_plan(plan, video_identity=None):
    if not isinstance(plan, dict) or not isinstance(plan.get("input_identity"), dict):
        raise ValueError("sampling plan input_identity required")
    identity = plan["input_identity"]
    _hash(identity.get("video_sha256"), "sampling video_sha256")
    for key in ("width", "height", "decoded_frame_count"):
        _positive_integer(identity.get(key), key)
    if video_identity is not None:
        actual_sha = video_identity.get("video_sha256", video_identity.get("sha256"))
        if actual_sha != identity["video_sha256"]:
            raise ValueError("sampling/input video hash mismatch")
        for key in ("width", "height"):
            if video_identity.get(key) != identity[key]:
                raise ValueError("sampling/input native dimensions mismatch")
    all_segments, indices_by_split = {}, {}
    for split in ("development", "holdout"):
        selection = plan.get(split)
        if not isinstance(selection, dict) or not isinstance(selection.get("segments"), list) or not selection["segments"]:
            raise ValueError(f"{split} inclusive segments required")
        segments = []
        for segment in selection["segments"]:
            if not isinstance(segment, dict):
                raise ValueError("segment must be object")
            first = _positive_integer(segment.get("start_frame"), "start_frame", True)
            last = _positive_integer(segment.get("end_frame"), "end_frame", True)
            if first > last or last >= identity["decoded_frame_count"]:
                raise ValueError("invalid segment bounds")
            segments.append((first, last))
        for i, (first, last) in enumerate(segments):
            if any(max(first, other_first) <= min(last, other_last) for other_first, other_last in segments[:i]):
                raise ValueError("overlapping within-split segments")
        indices = selection.get("sample_frame_indices")
        if not isinstance(indices, list) or not indices:
            raise ValueError(f"{split} explicit sparse samples required")
        for index in indices:
            _positive_integer(index, "sample index", True)
            if not any(first <= index <= last for first, last in segments):
                raise ValueError("sample outside its split segments")
        if indices != sorted(set(indices)):
            raise ValueError("sample indices must be unique sorted")
        all_segments[split], indices_by_split[split] = segments, indices
    if any(max(first, other_first) <= min(last, other_last) for first, last in all_segments["development"] for other_first, other_last in all_segments["holdout"]):
        raise ValueError("development/holdout segments overlap")
    return indices_by_split["development"].copy()


def decode_dev_frames(video_path, indices):
    """Read sequentially from zero, retaining only requested native frames."""
    import cv2
    if not isinstance(indices, list) or not indices or indices != sorted(set(indices)):
        raise ValueError("indices must be nonempty unique sorted list")
    for index in indices:
        _positive_integer(index, "sample index", True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError("OpenCV cannot open actual video")
    metadata = {
        "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps_backend": capture.get(cv2.CAP_PROP_FPS),
        "frame_count_backend": capture.get(cv2.CAP_PROP_FRAME_COUNT),
        "backend": capture.getBackendName(),
        "timestamp_limits": "Backend POS_MSEC and index/FPS estimates are not verified source PTS",
        "decode_method": "sequential_from_frame_zero_no_seek",
        "decode_completeness": "prefix through last DEV sample; not full video integrity proof",
        "discarded_prefix_frames_may_include_holdout": True,
        "holdout_prefix_read_is_not_evaluation": True,
    }
    frames, positions, desired = {}, [], set(indices)
    started = time.perf_counter()
    try:
        for index in range(indices[-1] + 1):
            success, frame = capture.read()
            if not success:
                raise RuntimeError(f"Decoder read false before requested sample {index}; EOF/decode failure not distinguished")
            if frame.shape != (metadata["height"], metadata["width"], 3):
                raise ValueError("native dimensions changed during sequential decode")
            if index in desired:
                frames[index] = frame.copy()
                msec = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                fps = metadata["fps_backend"]
                positions.append({
                    "frame_index": index, "backend_pos_frames_after_read": float(capture.get(cv2.CAP_PROP_POS_FRAMES)),
                    "backend_timestamp_seconds": msec / 1000 if math.isfinite(msec) else None,
                    "estimated_seconds_index_over_fps": index / fps if math.isfinite(fps) and fps > 0 else None,
                })
    finally:
        capture.release()
    metadata.update({"sequential_decoded_frames": indices[-1] + 1, "sampled_indices": indices.copy(), "sample_positions": positions, "decode_wall_seconds": time.perf_counter() - started})
    return frames, metadata


def validate_detection_rows(detections, width, height, class_names):
    _positive_integer(width, "width")
    _positive_integer(height, "height")
    if not isinstance(detections, list) or not isinstance(class_names, dict):
        raise ValueError("detections list and class names mapping required")
    cleaned = []
    for detection in detections:
        if not isinstance(detection, dict):
            raise ValueError("each detection must be object")
        box = detection.get("bbox_xyxy")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            raise ValueError("native bbox_xyxy must contain four values")
        x1, y1, x2, y2 = [_number(value, "bbox coordinate") for value in box]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("bbox must be positive and inside native full-frame image")
        confidence = _number(detection.get("confidence"), "confidence", 0, 1)
        class_id = _positive_integer(detection.get("class_id"), "class_id", True)
        label = class_names.get(str(class_id), class_names.get(class_id))
        if not isinstance(label, str) or detection.get("class_name") != label:
            raise ValueError("class_id/class_name mismatch against model mapping")
        cleaned.append({"detection_index": len(cleaned), "bbox_xyxy": [float(x1), float(y1), float(x2), float(y2)], "confidence": float(confidence), "class_id": class_id, "class_name": label})
    return cleaned


def _download_weights(config):
    target = Path(config["weights_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(target.suffix + ".part")
        try:
            with urlopen(MODEL_URL, timeout=60) as source, temporary.open("wb") as output:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
            if temporary.stat().st_size != MODEL_BYTES or sha256_file(temporary) != MODEL_SHA256:
                raise ValueError("downloaded model asset identity mismatch")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    if target.stat().st_size != MODEL_BYTES or sha256_file(target) != MODEL_SHA256:
        raise ValueError("cached model asset identity mismatch; no fallback asset")
    return target


def _actual_detector(config):
    if importlib.metadata.version("ultralytics") != PACKAGE_VERSION:
        raise RuntimeError(f"Requires ultralytics=={PACKAGE_VERSION}; no automatic package replacement")
    import torch
    from ultralytics import YOLO
    device = config["device"]
    verify_gpu_device(device)
    torch.manual_seed(0)
    torch.cuda.manual_seed_all(0)
    torch.backends.cudnn.benchmark = False
    weights = _download_weights(config)
    model = YOLO(str(weights))
    if model.task != "detect":
        raise RuntimeError("verified asset did not load as detect task")
    class_names = {str(key): value for key, value in model.names.items()}
    resources = {
        "execution_device": f"cuda:{device}", "cuda_available": True,
        "visible_cuda_device_count": torch.cuda.device_count(),
        "cuda_device_name": torch.cuda.get_device_name(device),
        "cuda_total_memory_bytes": torch.cuda.get_device_properties(device).total_memory,
        "torch_version": str(torch.__version__), "torch_cuda_build": torch.version.cuda,
        "package_version": PACKAGE_VERSION, "weights_sha256": sha256_file(weights),
        "weights_bytes": weights.stat().st_size, "weights_url": MODEL_URL,
        "class_names": class_names, "exact_bitwise_repeatability_claimed": False,
    }

    def predict(frame, frame_index, variant_name):
        results = model.predict(source=frame, device=device, verbose=False, save=False, **config["settings"])
        if len(results) != 1 or tuple(results[0].orig_shape) != frame.shape[:2]:
            raise ValueError("detector result count/native dimensions mismatch")
        backend = model.predictor.model
        if str(backend.device) != f"cuda:{device}" or backend.fp16:
            raise RuntimeError("actual model backend differs from pinned CUDA FP32 baseline")
        rows = []
        result = results[0]
        for box, score, class_id in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
            if int(class_id) != class_id:
                raise ValueError("nonintegral model class id")
            rows.append({"bbox_xyxy": box, "confidence": score, "class_id": int(class_id), "class_name": class_names[str(int(class_id))]})
        resources["actual_predictor_arguments"] = {key: getattr(model.predictor.args, key, None) for key in config["settings"]}
        if resources["actual_predictor_arguments"] != config["settings"]:
            raise RuntimeError("effective predictor arguments differ from frozen settings")
        resources["actual_backend"] = {"device": str(backend.device), "fp16": bool(backend.fp16), "end2end": bool(backend.end2end), "imgsz": list(model.predictor.imgsz)}
        return {"detections": rows, "class_names": class_names, "speed_ms": {key: float(value) for key, value in result.speed.items()}}

    def begin_variant():
        torch.cuda.synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)

    def finish_variant():
        torch.cuda.synchronize(device)
        return {"cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(device), "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(device)}

    return predict, resources, begin_variant, finish_variant


def _save_frame(path, frame):
    import cv2
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise IOError(f"could not save PNG {path}")
    return {"path": str(path), "sha256": sha256_file(path)}


def _annotate(frame, detections):
    import cv2
    overlay = frame.copy()
    for row in detections:
        x1, y1, x2, y2 = row["bbox_xyxy"]
        first = (int(round(x1)), int(round(y1)))
        last = (min(frame.shape[1] - 1, int(round(x2))), min(frame.shape[0] - 1, int(round(y2))))
        cv2.rectangle(overlay, first, last, (0, 220, 0), 2)
        cv2.putText(overlay, f"d{row['detection_index']} {row['class_name']} {row['confidence']:.3f}", (first[0], max(12, first[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 0), 1, cv2.LINE_AA)
    return overlay


def _photometric_metrics(frame):
    import cv2
    import numpy as np
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return {
        "mean_grayscale_8bit": float(np.mean(gray)),
        "grayscale_percentiles_1_50_99": [float(value) for value in np.percentile(gray, [1, 50, 99])],
        "fraction_grayscale_zero": float(np.mean(gray == 0)),
        "fraction_grayscale_255": float(np.mean(gray == 255)),
        "claim_limits": "Pixel descriptors only; not visibility/detector/tracker/counting performance",
    }


def run_screen(video_path, sampling_path, output_root, *, config, mode="photometric", detector=None):
    """Execute one auditable DEV screening run; callbacks are synthetic fixtures."""
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = validate_config(config, mode)
    if mode == "photometric" and detector is not None:
        raise ValueError("photometric stage cannot receive detector")
    sampling_path, video_path = Path(sampling_path), Path(video_path)
    if sha256_file(sampling_path) != config["expected_sampling_sha256"]:
        raise ValueError("sampling plan SHA-256 differs from frozen config")
    input_sha = sha256_file(video_path)
    if input_sha != config["expected_video_sha256"]:
        raise ValueError("actual video SHA-256 differs from explicit config")
    plan = json.loads(sampling_path.read_text(encoding="utf-8"))
    indices = verify_sampling_plan(plan)
    if len(indices) > config["max_dev_samples"]:
        raise ValueError("DEV sample count exceeds explicit engineering budget")
    frames, metadata = decode_dev_frames(video_path, indices)
    import cv2
    import numpy as np
    video_identity = {"video_sha256": input_sha, "width": metadata["width"], "height": metadata["height"]}
    verify_sampling_plan(plan, video_identity)
    execution_kind = "SYNTHETIC_FIXTURE" if detector is not None else "ACTUAL_PHOTOMETRIC_EXECUTION" if mode == "photometric" else "ACTUAL_MODEL_EXECUTION"
    run_id = started.strftime("%Y%m%dT%H%M%S_%fZ")
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=False)
    _json(output / "config.json", config)
    _json(output / "sampling_plan.json", plan)
    _json(output / "sample_source_positions.json", metadata)
    resource = {"execution_device": "cpu", "model_inference_executed": False}
    begin_variant, finish_variant = lambda: None, lambda: {}
    report = {
        "run_id": run_id, "phase": 7, "stage": mode, "execution_kind": execution_kind,
        "status": "running", "started_utc": started.isoformat(), "output_directory": str(output),
        "scope": "DEV sparse native full-frame photometric/detection screening only",
        "input_identity": {**video_identity, "path": str(video_path), "filename": video_path.name, "size_bytes": video_path.stat().st_size},
        "sample_indices": indices, "sampling_sha256": sha256_file(sampling_path),
        "source_helper_sha256": sha256_file(__file__), "configuration": config,
        "formulae": TRANSFORM_FORMULAE, "rounding": "float64, numpy.rint ties-to-even, clip [0,255], uint8",
        "channel_order": "BGR; per-channel point operations, native shape preserved; no crop/resize/stabilization",
        "environment": {"python": sys.version, "platform": platform.platform(), "cpu_count": os.cpu_count(), "numpy_version": np.__version__, "opencv_version": cv2.__version__},
        "decode": metadata, "resource": resource, "variants": [],
        "temporal_pipeline_executed": False, "count_events_generated": False,
        "holdout_enhancement_or_inference_executed": False,
        "heldout_evaluation_executed": False,
        "decoder_holdout_prefix_read_possible": True,
        "selected_configuration": None, "selection_status": "OPEN_PENDING_ACTUAL_REVIEW_AND_HOLDOUT",
        "limitations": [
            "No ground truth or accuracy/precision/recall/F1/MAPE claims.",
            "No tracker, ReID encoder, geometry/crossing/counting execution in this stage.",
            "Sparse detector outputs are not unique vehicles, physical identity, passage totals or temporal quality.",
            "Engineering transformation points are not tuned or production defaults.",
            "Hold-out is excluded from enhancement/inference; prior Phase1 visual inspection means it is not blind.",
            "More brightness, confidence or detections do not by themselves demonstrate improvement.",
        ],
    }
    try:
        if mode == "detection":
            if detector is None:
                detector, resource, begin_variant, finish_variant = _actual_detector(config["detector"])
                resource["model_inference_executed"] = True
            else:
                resource = {"execution_device": "synthetic_fixture_callback", "model_inference_executed": False, "fixture_detection_outputs_not_model_evidence": True}
            report["resource"] = resource
        source_samples = []
        for index in indices:
            saved = _save_frame(output / "source_frames" / f"frame_{index:09d}.png", frames[index])
            source_samples.append({"frame_index": index, **saved})
        report["source_frames"] = source_samples
        frozen_class_names = None
        for variant in config["variants"]:
            variant_clock = time.perf_counter()
            directory = output / variant["name"]
            directory.mkdir()
            begin_variant()
            transform_seconds, prediction_seconds, samples, class_totals, confidences = [], [], [], {}, []
            warmup = None
            detection_path = directory / "frame_detections.jsonl.gz"
            stream = gzip.open(detection_path, "wt", encoding="utf-8") if mode == "detection" else None
            try:
                if mode == "detection":
                    before = time.perf_counter()
                    warm_frame = apply_transform(frames[indices[0]], variant)
                    warm_result = detector(warm_frame, indices[0], variant["name"])
                    validate_detection_rows(warm_result["detections"], metadata["width"], metadata["height"], warm_result["class_names"])
                    if frozen_class_names is None:
                        frozen_class_names = copy.deepcopy(warm_result["class_names"])
                    elif warm_result["class_names"] != frozen_class_names:
                        raise ValueError("class mapping changed across variant/frame calls")
                    warmup = {"frame_index": indices[0], "wall_seconds_including_transform": time.perf_counter() - before, "saved_as_measurement": False, "timing_excluded_from_prediction_statistics": True}
                for index in indices:
                    before = time.perf_counter()
                    transformed = apply_transform(frames[index], variant)
                    transform_seconds.append(time.perf_counter() - before)
                    sample = {"frame_index": index, "transformed": _save_frame(directory / f"frame_{index:09d}_transformed.png", transformed), "photometric_descriptors": _photometric_metrics(transformed)}
                    if mode == "detection":
                        before = time.perf_counter()
                        result = detector(transformed, index, variant["name"])
                        elapsed = time.perf_counter() - before
                        prediction_seconds.append(elapsed)
                        detections = validate_detection_rows(result["detections"], metadata["width"], metadata["height"], result["class_names"])
                        if result["class_names"] != frozen_class_names:
                            raise ValueError("class mapping changed across variant/frame calls")
                        speed = result.get("speed_ms", {})
                        if not isinstance(speed, dict):
                            raise ValueError("speed_ms must be object")
                        for value in speed.values():
                            _number(value, "library speed", 0)
                        for row in detections:
                            class_totals[row["class_name"]] = class_totals.get(row["class_name"], 0) + 1
                            confidences.append(row["confidence"])
                        record = {"frame_index": index, "variant": variant["name"], "input_video_sha256": input_sha, "width": metadata["width"], "height": metadata["height"], "coordinate_space": "native_full_frame_xyxy_pixels", "detections": detections, "prediction_wall_seconds": elapsed, "library_speed_ms": speed, "execution_kind": execution_kind, "accepted_count_event": False}
                        stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                        sample.update({"detection_count": len(detections), "annotated": _save_frame(directory / f"frame_{index:09d}_annotated.png", _annotate(transformed, detections))})
                    samples.append(sample)
            finally:
                if stream is not None:
                    stream.close()
            report["variants"].append({
                "variant": variant, "formula": TRANSFORM_FORMULAE[variant["method"]], "sample_indices": indices.copy(), "samples": samples,
                "transformation_wall_seconds": sum(transform_seconds), "variant_total_wall_seconds_including_io_and_warmup": time.perf_counter() - variant_clock,
                "warmup": warmup, "prediction_calls_measured": len(prediction_seconds),
                "prediction_wall_ms_mean": statistics.mean(prediction_seconds) * 1000 if prediction_seconds else None,
                "prediction_wall_ms_median": statistics.median(prediction_seconds) * 1000 if prediction_seconds else None,
                "prediction_wall_seconds_total_excluding_warmup": sum(prediction_seconds) if prediction_seconds else None,
                "detection_class_observation_totals": class_totals if mode == "detection" else None,
                "detection_confidence_mean": statistics.mean(confidences) if confidences else None,
                "observation_totals_limits": "Frame-level observations; not physical units/counts/quality metrics",
                "detections_path": str(detection_path) if mode == "detection" else None,
                "detections_sha256": sha256_file(detection_path) if mode == "detection" else None,
                "resource": finish_variant(),
            })
        report["status"] = "completed_synthetic_fixture" if execution_kind == "SYNTHETIC_FIXTURE" else "completed_photometric_screen" if mode == "photometric" else "completed_detection_screen_no_temporal_claims"
    except Exception as error:
        report.update({"status": "failed", "error": {"type": type(error).__name__, "message": str(error)}})
        _json(output / "report.json", report)
        raise
    report.update({"finished_utc": datetime.now(timezone.utc).isoformat(), "total_wall_seconds": time.perf_counter() - clock})
    with gzip.open(output / "phase_7_night_helpers.executed_source.py.gz", "wb") as stream:
        stream.write(Path(__file__).read_bytes())
    _json(output / "report.json", report)
    manifest = {"run_id": run_id, "artifacts": [{"path": str(path.relative_to(output)), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(output.rglob("*")) if path.is_file()]}
    _json(output / "manifest.json", manifest)
    return report


def run_photometric_screen(video_path, sampling_path, output_root, *, config):
    return run_screen(video_path, sampling_path, output_root, config=config, mode="photometric")


def run_detection_screen(video_path, sampling_path, output_root, *, config, detector=None):
    return run_screen(video_path, sampling_path, output_root, config=config, mode="detection", detector=detector)
