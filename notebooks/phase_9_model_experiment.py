"""Paired confidence-retention experiment on a bounded, actual source clip.

This research helper never alters old detector caches, counters or model assets.
It runs two actual YOLO predictions, with fresh frozen BoT-SORT/ReID state per
variant. Outputs are observations, not a traffic benchmark or production config.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import platform
import time


SOURCE_SHA256 = "5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1"
WINDOW = {"context_start_frame": 7380, "evaluation_start_frame": 7440,
          "end_frame": 7979, "warmup_source_frames": 60}
VARIANTS = (("baseline_conf025", 0.25), ("candidate_conf010", 0.10))
SAMPLES = (7400, 7422, 7509, 7604, 7615, 7625, 7635, 7651, 7711, 7900, 7979)


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def validate_plan(plan):
    if plan.get("schema_version") != "phase9_detector_retention_experiment_v1":
        raise ValueError("Explicit experiment plan required")
    if plan.get("source_video_sha256") != SOURCE_SHA256 or plan.get("window") != WINDOW:
        raise ValueError("Frozen source/window differs; create a versioned experiment")
    if plan.get("variants") != [{"name": name, "conf": conf} for name, conf in VARIANTS]:
        raise ValueError("Only the two frozen confidence settings are permitted")
    if plan.get("preprocessing") != "raw" or plan.get("counting") != "NOT_EXECUTED_IN_MODEL_HELPER":
        raise ValueError("No simultaneous enhancement or implicit counting")
    gate = plan.get("p0_execution_gate", {})
    if gate.get("status") != "PASS" or not gate.get("evidence_sha256"):
        raise ValueError("Retained P0 execution/test gate required before new inference")
    if len(gate["evidence_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in gate["evidence_sha256"]):
        raise ValueError("Invalid gate evidence SHA")
    gate_path = Path(gate.get("evidence_path", ""))
    if not gate_path.is_file() or sha256(gate_path) != gate["evidence_sha256"]:
        raise ValueError("Retained P0 gate bytes differ or are unavailable")
    if json.loads(gate_path.read_text()).get("status") != "PASS":
        raise ValueError("Retained P0 gate is not PASS")
    if plan.get("processing_profile_sha256") != sha256(plan["processing_profile_path"]):
        raise ValueError("Frozen model profile bytes differ")
    return deepcopy(plan)


def make_plan(profile_path, *, p0_gate_sha256, p0_gate_path, video_path, output_path):
    return {"schema_version": "phase9_detector_retention_experiment_v1",
            "source_video_sha256": SOURCE_SHA256, "video_path": str(video_path),
            "output_path": str(output_path), "processing_profile_path": str(profile_path),
            "processing_profile_sha256": sha256(profile_path), "window": deepcopy(WINDOW),
            "variants": [{"name": name, "conf": conf} for name, conf in VARIANTS],
            "preprocessing": "raw", "counting": "NOT_EXECUTED_IN_MODEL_HELPER",
            "p0_execution_gate": {"status": "PASS", "evidence_sha256": p0_gate_sha256,
                                  "evidence_path": str(p0_gate_path)},
            "selection_basis": "QC development cases 4552/4480,4614,4709/4630 and parked-object negative controls; fixed before outcomes",
            "holdout": False, "full_video_history": False,
            "comparison": "TWO_ACTUAL_PREDICTIONS_PER_SOURCE_FRAME_NOT_FILTERED_BASELINE",
            "limits": ["600 contiguous context frames, last 540 evaluation frames",
                       "Clip reset has no source history before 7380; not a full-video traffic count",
                       "All previously viewed development source; not a blind benchmark",
                       "Lower confidence can introduce false tracks and wrong associations",
                       "Person-domain ReID is a fixed experimental control, not final vehicle-ReID",
                       "No ground truth or accuracy/precision/recall/F1/MAPE claim"]}


def _native_frames(video_path, window):
    import cv2
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Source decoder unavailable")
    metadata = {"width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps_backend": float(capture.get(cv2.CAP_PROP_FPS)),
                "frame_count_backend": int(capture.get(cv2.CAP_PROP_FRAME_COUNT))}
    frames = []
    try:
        for index in range(window["end_frame"] + 1):
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Source read failed at frame {index}")
            if index >= window["context_start_frame"]:
                if frame.shape != (480, 640, 3):
                    raise RuntimeError("Native source geometry changed")
                frames.append(frame)
    finally:
        capture.release()
    return frames, metadata


def _run_experiment(plan):
    plan = validate_plan(plan)
    source = Path(plan["video_path"])
    if sha256(source) != plan["source_video_sha256"]:
        raise ValueError("Actual source video SHA differs")
    output = Path(plan["output_path"])
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "plan.json", plan)
    import cv2
    import numpy as np
    import torch
    import phase_7_night_helpers as night
    import phase_7_temporal_helpers as temporal
    night.verify_gpu_device(0)  # Never silently fall back to CPU.
    profile = json.loads(Path(plan["processing_profile_path"]).read_text())
    if profile["detector"]["settings"] != night.DEFAULT_DETECTOR_SETTINGS:
        raise ValueError("Unexpected donor detector settings")
    if profile["tracker"] != temporal.TRACKER_CONTROL:
        raise ValueError("Unexpected donor tracker controls")
    profile["detector"]["weights_path"] = str(output / "assets/yolo26m.pt")
    profile["encoder"]["path"] = str(output / "assets/yolo26n-reid.onnx")
    started = time.perf_counter()
    frames, metadata = _native_frames(source, plan["window"])
    hashes = [hashlib.sha256(frame.tobytes()).hexdigest() for frame in frames]
    report = {"schema_version": "phase9_detector_retention_result_v1", "status": "running",
              "execution_kind": "REQUESTED_ACTUAL_CUDA_MODEL_EXPERIMENT", "source": metadata,
              "source_video_sha256": sha256(source), "source_frame_count_processed_per_variant": len(frames),
              "source_helper_sha256": sha256(__file__), "new_counting_execution": False,
              "new_enhancement_execution": False, "actual_detector_executed": False,
              "actual_encoder_cuda_execution_established": False, "plan": plan, "variants": {},
              "environment": {"python": platform.python_version(), "torch": str(torch.__version__),
                              "opencv": cv2.__version__, "cuda_name": torch.cuda.get_device_name(0)}}
    write_json(output / "report.json", report)
    for name, threshold in VARIANTS:
        target = output / name
        target.mkdir()
        detector = deepcopy(profile["detector"])
        detector["settings"]["conf"] = threshold
        predict, detector_resources, begin, finish = night._actual_detector(detector)
        tracker, session, runtime = temporal._actual_tracker(profile, target)
        registry, counts, timing, sample_rows = {}, Counter(), Counter(), []
        begin()
        with gzip.open(target / "detections.jsonl.gz", "wt") as detections_out, \
                gzip.open(target / "track_records.jsonl.gz", "wt") as records:
            for local_index, frame in enumerate(frames):
                global_index = WINDOW["context_start_frame"] + local_index
                actual_hash = hashlib.sha256(frame.tobytes()).hexdigest()
                if actual_hash != hashes[local_index]:
                    raise RuntimeError("Variant did not receive identical raw source pixels")
                before = time.perf_counter()
                prediction = predict(frame, global_index, name)
                timing["detector_wall_seconds"] += time.perf_counter() - before
                if not report["actual_detector_executed"]:
                    report["actual_detector_executed"] = True
                    write_json(output / "report.json", report)
                clean = night.validate_detection_rows(prediction["detections"], 640, 480, prediction["class_names"])
                detections = [{"bbox_xyxy_pixels": d["bbox_xyxy"], "confidence": d["confidence"],
                               "class_id": d["class_id"], "class_name": d["class_name"]} for d in clean]
                internal = {"frame_index": local_index, "width": 640, "height": 480, "detections": detections}
                before = time.perf_counter()
                tracker.encoder_evidence.calls = []
                outputs = temporal.update_tracker_on_transformed_frame(tracker, internal, frame)
                timing["tracker_wall_seconds_including_encoder"] += time.perf_counter() - before
                values = temporal.validate_emitted_outputs(outputs, internal)
                assigned, snapshots = temporal._assigned_evidence(tracker, internal, outputs, registry)
                for row in assigned:
                    row.update(frame_index=global_index, clip_local_frame_index=local_index,
                               measurement_provenance="retained_phase_9_new_detection")
                emitted = []
                for value in values:
                    source_index = int(value[7])
                    detection = detections[source_index]
                    emitted.append({"track_id": int(value[4]), "frame_index": global_index,
                                    "clip_local_frame_index": local_index, "original_detection_index": source_index,
                                    "raw_bbox": detection["bbox_xyxy_pixels"], "bbox": value[:4],
                                    "class_id": detection["class_id"], "class_name": detection["class_name"],
                                    "confidence": detection["confidence"], "observed": True, "emitted": True,
                                    "measurement_provenance": "retained_phase_9_new_detection"})
                evaluation = global_index >= WINDOW["evaluation_start_frame"]
                row = {"frame_index": global_index, "clip_local_frame_index": local_index,
                       "width": 640, "height": 480, "variant": name, "evaluation": evaluation,
                       "video_sha256": SOURCE_SHA256, "raw_frame_pixel_sha256": actual_hash,
                       "detections": detections, "emitted_tracks": emitted,
                       "assigned_observations": assigned, "track_lifecycle_snapshots": snapshots}
                records.write(json.dumps(row, allow_nan=False) + "\n")
                detections_out.write(json.dumps({key: row[key] for key in (
                    "frame_index", "clip_local_frame_index", "variant", "evaluation", "video_sha256",
                    "raw_frame_pixel_sha256", "detections")}, allow_nan=False) + "\n")
                counts.update(context_frames=1, detections=len(detections), emitted_observations=len(emitted),
                              low_conf_detections=sum(d["confidence"] < .25 for d in detections),
                              low_conf_emitted=sum(d["confidence"] < .25 for d in emitted))
                if evaluation:
                    counts.update(evaluation_frames=1, evaluation_detections=len(detections),
                                  evaluation_emitted_observations=len(emitted),
                                  evaluation_low_conf_emitted=sum(d["confidence"] < .25 for d in emitted))
                calls = tracker.encoder_evidence.calls
                if calls and not runtime.get("actual_cuda_execution_confirmed"):
                    path = Path(session.end_profiling())
                    proof = temporal.provider_profile_evidence(json.loads(path.read_text()))
                    proof.update(profile_sha256=sha256(path), source_frame_index=global_index)
                    write_json(target / "encoder_provider_evidence.json", proof)
                    runtime.update(proof)
                    report["actual_encoder_cuda_execution_established"] = True
                if global_index in SAMPLES:
                    native = output / "native_samples" / f"frame-{global_index:06d}.png"
                    native.parent.mkdir(exist_ok=True)
                    if not native.exists() and not cv2.imwrite(str(native), frame):
                        raise RuntimeError("Could not retain native sample")
                    sample_rows.append({"frame_index": global_index, "native_png": native.relative_to(output).as_posix(),
                                        "native_png_sha256": sha256(native), "pixel_sha256": actual_hash})
                if local_index % 100 == 0:
                    print(json.dumps({"variant": name, "source_frame": global_index}), flush=True)
        if not runtime.get("actual_cuda_execution_confirmed"):
            raise RuntimeError("Actual CUDA encoder kernels not established")
        result = {"status": "completed", "counts": dict(counts), "timing": dict(timing),
                  "detector_runtime": detector_resources, "encoder_runtime": runtime,
                  "cuda_resources": finish(), "samples": sample_rows,
                  "unique_tracker_ids": len(registry), "tracker_registry_local_frame_indices": registry,
                  "ids_are_not_physical_vehicle_counts": True}
        report["variants"][name] = result
        write_json(target / "report.json", result)
        write_json(output / "report.json", report)
        del tracker, session, predict
        torch.cuda.empty_cache()
    report.update(status="completed_development_confidence_experiment_pending_physical_review",
                  execution_kind="ACTUAL_CUDA_DETECTOR_AND_REID_EXECUTION",
                  wall_seconds=time.perf_counter() - started,
                  thresholds_are_not_selected_production_defaults=True,
                  physical_accuracy_established=False)
    write_json(output / "report.json", report)
    artifacts = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha256(p)}
                 for p in sorted(output.rglob("*")) if p.is_file() and p.name != "artifact_manifest.json"]
    write_json(output / "artifact_manifest.json", {"artifacts": artifacts, "self_excluded": True})
    return report


def run_experiment(plan):
    """Retain partial failures without rewriting output from any earlier run."""
    output = Path(plan.get("output_path", "/nonexistent-unconfigured-model-experiment"))
    was_absent = not output.exists()
    try:
        return _run_experiment(plan)
    except Exception as error:
        if was_absent and output.is_dir():
            report_path = output / "report.json"
            report = json.loads(report_path.read_text()) if report_path.is_file() else {
                "actual_detector_executed": False, "actual_encoder_cuda_execution_established": False}
            report.update(status="FAILED_OR_PARTIAL_NOT_A_COMPLETED_COMPARISON",
                          error_type=type(error).__name__, error=str(error))
            write_json(report_path, report)
        raise
