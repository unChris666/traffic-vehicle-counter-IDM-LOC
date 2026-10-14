"""Phase 7 raw/DEV-shortlisted night experiment; exact frozen Phase 6B semantics.

Detection and the external ReID encoder receive the SAME transformed full frame.
No isolated ReID benefit is inferred. Old source/evidence files are read-only.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import resource
import time
import types
from urllib.request import urlopen

import phase_7_night_helpers as night

B_SOURCE_SHA256 = "18949e7a44b6d73b9d50269f9d4569fbda781ba48269046b982287376ec3f054"
GEOMETRY_SOURCE_SHA256 = "c344aa5b73b8b75fcdd567355b867e977a3d8e170feb512cdf0d15ac61b123c9"
CALIBRATION_SHA256 = "f907c70b97b8d3aa85e94eb65e3c0b51653fea41ae9e51f378588a8ccba32723"
ENCODER_SHA256 = "8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb"
ENCODER_BYTES = 9873245
ENCODER_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-reid.onnx"
TRACKER_CONTROL = {"tracker_type": "botsort", "track_high_thresh": .25, "track_low_thresh": .1,
                   "new_track_thresh": .25, "track_buffer": 30, "match_thresh": .8,
                   "fuse_score": True, "gmc_method": "none", "proximity_thresh": .5,
                   "appearance_thresh": .8, "with_reid": True, "device": "cuda:0"}
ASSOCIATION_CONTROL = {
    "component": {"min_common_frames": 3, "min_consecutive_common_frames": 3,
                  "min_first_bc_inside_second_fraction": 1.0, "max_center_distance_norm": .51,
                  "max_relative_motion_residual_norm": .15},
    "same_vehicle": {"min_common_frames": 2, "min_consecutive_common_frames": 2, "min_iou": .59,
                     "max_center_distance_norm": .10, "max_relative_motion_residual_norm": .01}}
PROVENANCE = "retained_phase_7_detection"
EXPECTED_PACKAGE_SOURCES = {
    "trackers/bot_sort.py": "b157cbc33f75f1132df530f04361824bc39a30d4051ce6df1cd5c388e49b3117",
    "trackers/byte_tracker.py": "fb45d70e952f99984085788bc09fc0c60a18b14bc4329b28e32bc2c70ac37401",
    "trackers/basetrack.py": "9ef094b9a54ff2f52c9118b5bd1a2f84ba331aa557277f54186de11728c2f7e8",
    "trackers/utils/matching.py": "318bf81030558863a4ec6effea3c9d063a297f299367e379a58b89c24e3f421f",
    "trackers/utils/gmc.py": "d797f701a22347001d780b0dc4d0f2f5cabdfefb895c36bbab084ceb2dfc4000",
    "trackers/utils/stracks.py": "9534294af850c3a6755c3a5a1ba9b2b068c5b79a11166c8547652944e2632f58",
    "trackers/utils/reid.py": "75c54a4f8fe9b1e6946d61b530fbb790fdfcc27df120fa71cc7759c11e9f0475",
    "cfg/trackers/botsort.yaml": "8cd88930d3be5557be0777f384eecff0a36a7011850fe613fc0a68178bfd5b01",
    "engine/results.py": "871e5b3eed1558c3c048d99058ddf28a7927c1317d020981e7c0836f18e00ee3",
    "nn/backends/onnx.py": "8a42c894bb34381ffa2636d2bf8704c5ea5f2f80db6de296b278c6c6528b6e5e",
    "nn/autobackend.py": "450d5d5301e441896f8422cd333ce35c414c2e7ac39a88af01fd5edbd2e552dd",
    "utils/plotting.py": "a21122beb75642c535ba5f20f81e51cf9fd9c22c097120d1e787a7286c468ff0"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def validate_selection(selection, variants):
    _require(isinstance(selection, dict), "Frozen DEV selection object required")
    _require(selection.get("status") == "FROZEN_DEV_SHORTLIST", "DEV shortlist must be frozen before temporal execution")
    _require(selection.get("selection_basis") == "DEVELOPMENT_ONLY" and selection.get("holdout_used") is False,
             "Holdout cannot select or tune the enhancement")
    checked = night.validate_variants(variants)
    selected = selection.get("selected_variant")
    _require(isinstance(selected, dict) and selected.get("method") != "raw" and selected in checked,
             "One exact nonraw DEV candidate required")
    _require(len(checked) == 2 and checked[0] == {"name": "raw", "method": "raw"}, "Exactly raw then selected enhancement")
    _require(checked[1] == selected, "Temporal enhancement must equal frozen selection")
    _require(isinstance(selection.get("source_detection_screen_run_id"), str) and bool(selection["source_detection_screen_run_id"]),
             "Actual DEV detection screen lineage required")
    night._hash(selection.get("source_detection_screen_report_sha256"), "source DEV report SHA")
    return deepcopy(selection)


def make_temporal_config(video_sha, sampling_sha, geometry_sha, selection_sha, *, repo_root=".",
                         selection_path="docs/evidence/phase_7/selection/TOR3-MALAM_DEV_shortlist_v1.json",
                         geometry_path="docs/evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json",
                         weights_path="/kaggle/working/phase_7_assets/yolo26m.pt",
                         encoder_path="/kaggle/working/phase_7_assets/yolo26n-reid.onnx"):
    return {
        "contract_version": "phase7_night_temporal_v1", "repo_root": str(repo_root),
        "video_path": "/kaggle/input/datasets/chrisbiran/traffic-tracker-videos/TOR3-MALAM.mp4",
        "output_root": "/kaggle/working/phase_7_night_temporal", "expected_video_sha256": video_sha,
        "sampling_path": "docs/evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json",
        "expected_sampling_sha256": sampling_sha, "expected_frame_count": 9590,
        "geometry_path": str(geometry_path), "expected_geometry_sha256": geometry_sha,
        "selection_path": str(selection_path), "expected_selection_sha256": selection_sha,
        "variants": None, "frame_scope": "FULL_VIDEO_FROM_FRAME_ZERO_NO_TRACKER_RESET_WITHIN_VARIANT",
        "counting_scope": "DECLARED_DEV_AND_HOLDOUT_SAMPLING_WINDOWS_DYNAMIC_OBSERVED_IDS_FULL_HISTORY",
        "detector": night.make_screen_config(video_sha, sampling_sha, weights_path=weights_path)["detector"],
        "tracker": deepcopy(TRACKER_CONTROL),
        "encoder": {"path": str(encoder_path), "url": ENCODER_URL, "sha256": ENCODER_SHA256,
                    "bytes": ENCODER_BYTES, "device": "cuda:0", "onnx_version": "1.20.1", "ort_version": "1.24.4",
                    "input_policy": "SAME_TRANSFORMED_FRAME_AS_DETECTOR", "final_vehicle_configuration": False},
        "counting": {"policy_version": "phase6_option_b_v1", "metric": "passage", "neutral_band_px": 0.0,
                     "confirmation_observations": 1, "association": deepcopy(ASSOCIATION_CONTROL), "grouping_enabled": True,
                     "source_path": "notebooks/phase_6_identity_resolution_helpers.py", "source_sha256": B_SOURCE_SHA256,
                     "calibration_path": "docs/evidence/phase_6/option_b_calibration/frozen_thresholds.json",
                     "calibration_sha256": CALIBRATION_SHA256,
                     "parameter_status": "FROZEN_PAGI_EXPERIMENT_CONTROLS_NOT_NIGHT_CALIBRATION",
                     "geometry_source_sha256": GEOMETRY_SOURCE_SHA256},
        "result_semantics": "MACHINE_CANDIDATES_SEPARATE_FROM_EXPLICIT_PHYSICAL_PASSAGE_REVIEW_OFFLINE",
        "holdout_policy": "FROZEN_DEV_SELECTION_BEFORE_ANY_HOLDOUT_MODEL_OUTCOME_REVIEW"}


def validate_temporal_config(config):
    _require(isinstance(config, dict) and config.get("contract_version") == "phase7_night_temporal_v1", "Explicit Phase7 temporal contract required")
    for key in ("expected_video_sha256", "expected_sampling_sha256", "expected_geometry_sha256", "expected_selection_sha256"):
        night._hash(config.get(key), key)
    _require(config.get("frame_scope") == "FULL_VIDEO_FROM_FRAME_ZERO_NO_TRACKER_RESET_WITHIN_VARIANT", "Full source history required")
    night._positive_integer(config.get("expected_frame_count"), "frame total")
    _require(config.get("counting_scope") == "DECLARED_DEV_AND_HOLDOUT_SAMPLING_WINDOWS_DYNAMIC_OBSERVED_IDS_FULL_HISTORY", "Targeted sampling-window counting scope required")
    _require(night._same_typed_value(config.get("tracker"), TRACKER_CONTROL), "Tracker controls frozen against Phase4; no GMC, threshold tuning or encoder substitution")
    detector = config.get("detector")
    night.validate_config({"expected_video_sha256": config["expected_video_sha256"], "expected_sampling_sha256": config["expected_sampling_sha256"],
                           "detector": detector, "variants": config.get("variants")}, "detection")
    _require(detector.get("device") == 0, "Detector uses GPU0; no CPU fallback")
    encoder = config.get("encoder", {})
    _require(isinstance(encoder, dict) and set(encoder) == {"path", "url", "sha256", "bytes", "device", "onnx_version", "ort_version", "input_policy", "final_vehicle_configuration"}
             and isinstance(encoder.get("path"), str) and bool(encoder["path"]), "Explicit supported encoder configuration only; no ignored encoder overrides")
    _require(encoder.get("url") == ENCODER_URL and encoder.get("sha256") == ENCODER_SHA256 and encoder.get("bytes") == ENCODER_BYTES,
             "Phase4 verified encoder asset required")
    _require(encoder.get("device") == "cuda:0" and encoder.get("onnx_version") == "1.20.1" and encoder.get("ort_version") == "1.24.4",
             "Exact encoder CUDA runtime controls required")
    _require(encoder.get("input_policy") == "SAME_TRANSFORMED_FRAME_AS_DETECTOR" and encoder.get("final_vehicle_configuration") is False,
             "Same enhanced/raw frame must feed detector and encoder; candidate is not final vehicle encoder")
    counting = config.get("counting", {})
    _require(isinstance(counting, dict) and set(counting) == {"policy_version", "metric", "neutral_band_px", "confirmation_observations", "association", "grouping_enabled", "source_path", "source_sha256", "calibration_path", "calibration_sha256", "parameter_status", "geometry_source_sha256"},
             "Explicit supported frozen counting fields; no ignored overrides")
    _require(counting.get("policy_version") == "phase6_option_b_v1" and counting.get("metric") == "passage"
             and night._same_typed_value(counting.get("neutral_band_px"), 0.0) and night._same_typed_value(counting.get("confirmation_observations"), 1)
             and night._same_typed_value(counting.get("association"), ASSOCIATION_CONTROL) and counting.get("grouping_enabled") is True,
             "Frozen counting geometry/association controls required")
    _require(counting.get("source_sha256") == B_SOURCE_SHA256 and counting.get("geometry_source_sha256") == GEOMETRY_SOURCE_SHA256
             and counting.get("calibration_sha256") == CALIBRATION_SHA256,
             "Frozen counting source/calibration lineage required")
    _require(config.get("holdout_policy") == "FROZEN_DEV_SELECTION_BEFORE_ANY_HOLDOUT_MODEL_OUTCOME_REVIEW", "Explicit holdout policy required")
    return deepcopy(config)


def validate_emitted_outputs(outputs, row):
    values = outputs.tolist() if hasattr(outputs, "tolist") else deepcopy(outputs)
    _require(isinstance(values, list), "Tracker output must be list/matrix")
    ids, indices = set(), set()
    for output in values:
        _require(isinstance(output, list) and len(output) == 8 and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in output),
                 "Expected finite BoT-SORT [xyxy,id,score,class,sourceindex]")
        x1, y1, x2, y2, track, score, cls, index = output
        _require(x2 > x1 and y2 > y1, "Positive tracker box required")
        _require(track == int(track) and track > 0 and track not in ids and index == int(index) and 0 <= index < len(row["detections"]) and index not in indices,
                 "Unique valid emitted ID/source index required")
        source = row["detections"][int(index)]
        _require(cls == source["class_id"] and math.isclose(score, source["confidence"], abs_tol=1e-6), "Emitted raw class/score linkage mismatch")
        ids.add(track); indices.add(index)
    return values


def build_track_record(row, outputs, *, variant, parent_run_id, fps, assigned_observations=None, lifecycle_snapshots=None):
    values = validate_emitted_outputs(outputs, row)
    _require(isinstance(fps, (int, float)) and not isinstance(fps, bool) and math.isfinite(fps) and fps > 0, "Observed positive FPS required")
    emitted = []
    for output in values:
        source_index = int(output[7]); det = row["detections"][source_index]; box = deepcopy(det["bbox_xyxy_pixels"])
        emitted.append({"track_id": int(output[4]), "frame_index": row["frame_index"], "original_detection_index": source_index,
                        "raw_bbox": box, "bbox": output[:4], "center": [(box[0]+box[2])/2, (box[1]+box[3])/2],
                        "class_id": det["class_id"], "class_name": det["class_name"], "confidence": det["confidence"],
                        "timestamp_estimate_from_index_fps_seconds": row["frame_index"]/fps, "emitted": True,
                        "is_activated": True, "measurement_provenance": PROVENANCE})
    return {"phase": 7, "video_sha256": row["video_sha256"], "variant": variant, "parent_run_id": parent_run_id,
            "frame_index": row["frame_index"], "width": row["width"], "height": row["height"],
            "timestamp_estimate_from_index_fps_seconds": row["frame_index"]/fps,
            "timestamp_decoder_backend_ms": row.get("timestamp_backend_ms"),
            "raw_detections": deepcopy(row["detections"]), "emitted_tracks": emitted,
            "assigned_observations_including_unconfirmed": deepcopy(emitted if assigned_observations is None else assigned_observations),
            "lifecycle_snapshots": deepcopy([] if lifecycle_snapshots is None else lifecycle_snapshots), "measurement_provenance": PROVENANCE}


def check_source_record(record, expected_frame, identity):
    _require(record.get("phase") == 7 and record.get("measurement_provenance") == PROVENANCE, "Truthful Phase7 measurement lineage required")
    _require(type(record.get("frame_index")) is int and record["frame_index"] == expected_frame, "Full-video source order mismatch")
    for key in ("video_sha256", "variant", "parent_run_id", "width", "height"):
        _require(record.get(key) == identity[key], "Source context mismatch: " + key)
    raw = record.get("raw_detections")
    _require(isinstance(raw, list), "Full raw detection context required")
    for detection in raw:
        box = detection.get("bbox_xyxy_pixels")
        _require(isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in box), "Finite raw bbox required")
        _require(0 <= box[0] < box[2] <= identity["width"] and 0 <= box[1] < box[3] <= identity["height"], "In-frame positive raw bbox required")
        _require(type(detection.get("class_id")) is int and detection["class_id"] >= 0 and isinstance(detection.get("class_name"), str) and detection["class_name"], "Raw class metadata required")
        score = detection.get("confidence")
        _require(isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score) and 0 <= score <= 1, "Raw confidence invalid")
    ids, indices = set(), set()
    _require(isinstance(record.get("emitted_tracks"), list), "Emitted measurements required")
    for item in record["emitted_tracks"]:
        track, index = item.get("track_id"), item.get("original_detection_index")
        _require(type(track) is int and track > 0 and track not in ids and type(index) is int and 0 <= index < len(raw) and index not in indices,
                 "Unique direct emitted source link required")
        _require(item.get("frame_index") == expected_frame and item.get("emitted") is True and item.get("measurement_provenance") == PROVENANCE,
                 "Measured/emitted Phase7 observation required")
        detection = raw[index]
        _require(item.get("raw_bbox") == detection["bbox_xyxy_pixels"] and all(item.get(k) == detection[k] for k in ("class_id", "class_name", "confidence")),
                 "Observation must exactly link one original Phase7 detection")
        ids.add(track); indices.add(index)
    return True


def load_phase7_counting_adapter(source_path, expected_sha=B_SOURCE_SHA256):
    """Exactly one truthful provenance literal substitution; no algorithm edits."""
    source_path = Path(source_path)
    _require(expected_sha == B_SOURCE_SHA256 and night.sha256_file(source_path) == B_SOURCE_SHA256, "Frozen Phase6 B v1 source mismatch")
    text = source_path.read_text(encoding="utf-8")
    old, new = '"retained_phase_2_detection"', '"retained_phase_7_detection"'
    _require(text.count(old) == 1 and new not in text, "Expected exactly one source-bound provenance literal")
    adapted = text.replace(old, new, 1)
    module = types.ModuleType("phase_7_source_bound_option_b_adapter")
    module.__file__ = str(source_path)
    exec(compile(adapted, str(source_path) + "::phase7_provenance_adapter", "exec"), module.__dict__)
    module.phase7_adapter_provenance = {"base_source_sha256": B_SOURCE_SHA256,
        "adapted_source_sha256": hashlib.sha256(adapted.encode()).hexdigest(), "literal_substitution_count": 1,
        "from": old, "to": new, "behavior_changes": "SOURCE_PROVENANCE_ENUM_ONLY_NO_ALGORITHM_OR_THRESHOLD_CHANGE"}
    module.phase7_adapted_source = adapted
    return module


def update_tracker_on_transformed_frame(tracker, row, transformed_frame):
    """Single explicit donor frame for actual upstream ReID crop extraction."""
    import numpy as np
    from ultralytics.engine.results import Boxes
    _require(isinstance(transformed_frame, np.ndarray) and transformed_frame.dtype == np.uint8 and transformed_frame.shape == (row["height"], row["width"], 3), "Native HxWx3 BGR uint8 transformed frame required")
    values = np.asarray([d["bbox_xyxy_pixels"] + [d["confidence"], d["class_id"]] for d in row["detections"]], dtype=np.float32).reshape(-1, 6)
    return tracker.update(Boxes(values, orig_shape=transformed_frame.shape[:2]), img=transformed_frame, feats=None)


def provider_profile_evidence(events, *, execution_kind="ACTUAL_MODEL_EXECUTION"):
    _require(execution_kind in ("ACTUAL_MODEL_EXECUTION", "SYNTHETIC_FIXTURE"), "Explicit provider execution kind required")
    _require(isinstance(events, list), "Actual ONNX profile list required")
    providers = Counter(e.get("args", {}).get("provider") for e in events if isinstance(e, dict)
                        and e.get("cat") == "Node" and e.get("args", {}).get("provider"))
    _require(providers.get("CUDAExecutionProvider", 0) > 0, "Provider names alone do not prove actual CUDA execution")
    return {"provider_kernel_event_counts": dict(providers), "execution_kind": execution_kind,
            "actual_cuda_execution_confirmed": execution_kind == "ACTUAL_MODEL_EXECUTION",
            "cpu_partition_note": "CPU graph partitions are reported; whole-session fallback forbidden"}


@contextmanager
def _profiled_ort_session(prefix):
    import onnxruntime as ort
    original = ort.InferenceSession
    def create(*args, **kwargs):
        positional = list(args)
        options = (positional[1] if len(positional) > 1 else kwargs.get("sess_options")) or ort.SessionOptions()
        options.enable_profiling = True; options.profile_file_prefix = str(prefix)
        if len(positional) > 1:
            positional[1] = options; kwargs.pop("sess_options", None)
        else:
            kwargs["sess_options"] = options
        session = original(*positional, **kwargs); session.disable_fallback()
        return session
    ort.InferenceSession = create
    try:
        yield
    finally:
        ort.InferenceSession = original


def _encoder_asset(config):
    path = Path(config["path"]); path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        partial = path.with_suffix(".onnx.part")
        try:
            with urlopen(config["url"], timeout=60) as source, partial.open("wb") as output:
                for block in iter(lambda: source.read(1024*1024), b""):
                    output.write(block)
            _require(partial.stat().st_size == ENCODER_BYTES and night.sha256_file(partial) == ENCODER_SHA256, "Downloaded encoder identity mismatch")
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
    _require(path.stat().st_size == ENCODER_BYTES and night.sha256_file(path) == ENCODER_SHA256, "Exact encoder bytes required; no substitution")
    return path


def _actual_tracker(config, variant_dir):
    import numpy as np
    import onnxruntime as ort
    import ultralytics
    from ultralytics.trackers.bot_sort import BOTSORT
    from ultralytics.trackers.utils import matching
    from ultralytics.utils import IterableSimpleNamespace
    from ultralytics.trackers.basetrack import BaseTrack
    package = Path(ultralytics.__file__).resolve().parent
    checks = []
    for name, expected in EXPECTED_PACKAGE_SOURCES.items():
        actual = night.sha256_file(package/name)
        _require(actual == expected, "Pinned tracker source mismatch: " + name)
        checks.append({"path": name, "sha256": actual})
    for package_name, expected in (("onnx", "1.20.1"), ("onnxruntime-gpu", "1.24.4"), ("lap", "0.5.13")):
        _require(importlib.metadata.version(package_name) == expected, "Exact runtime required: " + package_name)
    _require("CUDAExecutionProvider" in ort.get_available_providers(), "CUDA encoder provider required; no CPU fallback")
    encoder_path = _encoder_asset(config["encoder"])

    class EncoderEvidence:
        def __init__(self, encoder):
            self.encoder = encoder; self.calls = []; self.total_calls = 0; self.total_features = 0
        def __call__(self, image, detections):
            started = time.perf_counter(); features = self.encoder(image, detections)
            _require(len(features) == len(detections), "Appearance cardinality mismatch")
            norms, hashes = [], []
            for feature in features:
                _require(feature is not None, "Empty ReID crop/feature is not silent identity proof")
                feature = np.asarray(feature)
                _require(feature.shape == (512,) and np.isfinite(feature).all(), "Actual finite 512D features required")
                norm = float(np.linalg.norm(feature)); _require(norm > 1e-12, "Nonzero actual feature required")
                norms.append(norm); hashes.append(hashlib.sha256(feature.tobytes()).hexdigest())
            self.calls.append({"feature_count": len(features), "feature_dimension": 512,
                               "feature_l2_norms": norms, "feature_sha256": hashes,
                               "donor_frame_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                               "encoder_wall_seconds": time.perf_counter()-started})
            self.total_calls += 1; self.total_features += len(features)
            return features

    class Observer(BOTSORT):
        def __init__(self, args):
            self.cost_calls = []; self.cost_totals = Counter(); super().__init__(args)
            self.encoder_evidence = EncoderEvidence(self.encoder); self.encoder = self.encoder_evidence
        def update(self, results, img=None, feats=None, **kwargs):
            self.before_objects = list(self.tracked_stracks) + list(self.lost_stracks); self.created_objects = []
            return super().update(results, img=img, feats=feats, **kwargs)
        def _init_new_tracks(self, indices, detections, activated, refind=None):
            before = len(activated); super()._init_new_tracks(indices, detections, activated, refind)
            self.created_objects.extend(activated[before:])
        def get_dists(self, tracks, detections):
            actual = super().get_dists(tracks, detections)
            iou = matching.iou_distance(tracks, detections)
            motion = matching.fuse_score(iou.copy(), detections) if self.args.fuse_score else iou.copy()
            present = bool(tracks and detections)
            if present:
                _require(all(t.smooth_feat is not None and np.isfinite(t.smooth_feat).all() for t in tracks)
                         and all(d.curr_feat is not None and np.isfinite(d.curr_feat).all() for d in detections), "Appearance must reach actual association")
            appearance = matching.embedding_distance(tracks, detections)/2.0
            eligible = (appearance <= (1-self.appearance_thresh)) & (iou <= (1-self.proximity_thresh))
            gated = appearance.copy(); gated[gated > (1-self.appearance_thresh)] = 1.0; gated[iou > (1-self.proximity_thresh)] = 1.0
            _require(np.array_equal(actual, np.minimum(motion, gated)), "Read-only observer must preserve exact parent formula")
            changed = int(np.count_nonzero(np.abs(actual-motion) > 1e-12))
            item = {"frame_index": self.frame_id-1, "matrix_shape": list(actual.shape), "candidate_pairs": int(actual.size),
                    "track_ids": [t.track_id for t in tracks], "detection_indices": [int(d.idx) for d in detections],
                    "features_present_in_nonempty_association": present, "appearance_eligible_pairs": int(eligible.sum()),
                    "appearance_changed_cost_pairs": changed, "parent_formula_exact_match": True}
            self.cost_calls.append(item); self.cost_totals.update(calls=1, candidate_pairs=int(actual.size),
                nonempty_feature_association_calls=int(present), appearance_eligible_pairs=int(eligible.sum()), appearance_changed_cost_pairs=changed)
            return actual

    BaseTrack.reset_id()
    args = dict(config["tracker"], model=str(encoder_path))
    with _profiled_ort_session(variant_dir/"ort_encoder_profile"):
        tracker = Observer(IterableSimpleNamespace(**args))
    encoder = tracker.encoder_evidence.encoder; session = encoder.model.session
    _require(session.get_providers()[0] == "CUDAExecutionProvider" and encoder.device.type == "cuda"
             and encoder.model.device.type == "cuda" and not encoder.is_pt and encoder.imgsz == (224, 224)
             and not encoder.fp16 and encoder.batch_size is None, "Actual external CUDA encoder/crop/runtime mismatch")
    _require(tracker.gmc.method is None, "GMC/stabilization disabled in this isolated experiment")
    runtime = {"providers": session.get_providers(), "provider_options": session.get_provider_options(),
               "device": str(encoder.device), "backend_device": str(encoder.model.device), "imgsz": list(encoder.imgsz),
               "fp16": encoder.fp16, "static_batch_size": encoder.batch_size, "no_runtime_fallback": True,
               "tracker_source_checks": checks, "effective_configuration": args,
               "encoder_asset_sha256": ENCODER_SHA256, "encoder_input_policy": config["encoder"]["input_policy"],
               "documented_training_domain": "MSMT17-v1 person; vehicle transfer unknown", "final_vehicle_configuration": False}
    return tracker, session, runtime


def _assigned_evidence(tracker, row, emitted_outputs, registry):
    objects = {t.track_id: t for t in tracker.before_objects + tracker.created_objects + tracker.tracked_stracks + tracker.lost_stracks + getattr(tracker, "removed_stracks_frame", [])}
    emitted_ids = {int(o[4]) for o in emitted_outputs}; observations, snapshots = [], []
    for track_id, track in sorted(objects.items()):
        observed = track.frame_id == row["frame_index"]+1
        entry = registry.setdefault(track_id, {"track_id": track_id, "first_observed_frame": None, "last_observed_frame": None,
            "observed_count": 0, "emitted_count": 0, "class_histogram": {}, "gap_events": [], "class_changes": []})
        if observed:
            index = int(track.idx); _require(0 <= index < len(row["detections"]), "Assigned unconfirmed source index mismatch")
            detection = row["detections"][index]
            _require(int(track.cls) == detection["class_id"] and math.isclose(float(track.score), detection["confidence"], abs_tol=1e-6), "Assigned raw class/score mismatch")
            old = entry["last_observed_frame"]
            if old is not None and row["frame_index"] > old+1:
                entry["gap_events"].append({"previous_frame": old, "next_frame": row["frame_index"], "missing_frames": row["frame_index"]-old-1})
            if old is not None and entry["last_class_id"] != detection["class_id"]:
                entry["class_changes"].append({"frame_index": row["frame_index"], "old_class_id": entry["last_class_id"], "new_class_id": detection["class_id"]})
            entry["first_observed_frame"] = row["frame_index"] if entry["first_observed_frame"] is None else entry["first_observed_frame"]
            entry["last_observed_frame"] = row["frame_index"]; entry["last_class_id"] = detection["class_id"]
            entry["observed_count"] += 1; entry["emitted_count"] += int(track_id in emitted_ids)
            label = detection["class_name"]; entry["class_histogram"][label] = entry["class_histogram"].get(label, 0)+1
            observations.append({"track_id": track_id, "frame_index": row["frame_index"], "original_detection_index": index,
                "raw_bbox": deepcopy(detection["bbox_xyxy_pixels"]), "bbox": track.xyxy.tolist(), "class_id": detection["class_id"],
                "class_name": label, "confidence": detection["confidence"], "emitted": track_id in emitted_ids,
                "is_activated": bool(track.is_activated), "measurement_provenance": PROVENANCE})
        snapshots.append({"track_id": track_id, "library_state": int(track.state), "is_activated": bool(track.is_activated),
            "observed_this_frame": observed, "emitted": track_id in emitted_ids, "bbox_kalman_estimate": track.xyxy.tolist(),
            "bbox_provenance": "filtered_current_detection" if observed else "tracker_estimate_not_current_detection"})
    _require(emitted_ids <= {o["track_id"] for o in observations}, "Emitted track must have actual current source observation")
    return observations, snapshots


def verify_temporal_inputs(config):
    """File/decision gates complete before any model or GPU runtime is loaded."""
    config = validate_temporal_config(config); repo = Path(config["repo_root"])
    def bound(relative, expected):
        path = Path(relative); path = path if path.is_absolute() else repo/path
        _require(path.is_file() and night.sha256_file(path) == expected, "Input SHA mismatch: " + str(path))
        return path
    sampling_path = bound(config["sampling_path"], config["expected_sampling_sha256"])
    geometry_path = bound(config["geometry_path"], config["expected_geometry_sha256"])
    selection_path = bound(config["selection_path"], config["expected_selection_sha256"])
    plan = json.loads(sampling_path.read_text()); night.verify_sampling_plan(plan)
    _require(plan["input_identity"]["video_sha256"] == config["expected_video_sha256"]
             and plan["input_identity"]["decoded_frame_count"] == config["expected_frame_count"], "Sampling video/frame identity mismatch")
    selection = validate_selection(json.loads(selection_path.read_text()), config["variants"])
    screen_candidates = list((repo/"docs/evidence/phase_7/screening").glob(selection["source_detection_screen_run_id"] + "/report.json"))
    _require(len(screen_candidates) == 1, "One retained actual DEV screen report required")
    bound(screen_candidates[0].resolve(), selection["source_detection_screen_report_sha256"])
    screen = json.loads(screen_candidates[0].read_text())
    _require(screen.get("execution_kind") == "ACTUAL_MODEL_EXECUTION" and screen.get("status") == "completed_detection_screen_no_temporal_claims"
             and screen.get("holdout_enhancement_or_inference_executed") is False
             and screen.get("heldout_evaluation_executed") is False, "Actual DEV-only detector outcome required for shortlist")
    _require(screen.get("sample_indices") == plan["development"]["sample_frame_indices"], "DEV shortlist source must use development samples only")
    screen_identity = screen.get("input_identity", {})
    _require(all(screen_identity.get(k) == plan["input_identity"][k] for k in ("video_sha256", "width", "height")), "Shortlist source video/native identity mismatch")
    screen_config = screen.get("configuration", {})
    _require(selection["selected_variant"] in screen_config.get("variants", []) and {"name": "raw", "method": "raw"} in screen_config.get("variants", []), "Shortlist candidate must actually have been screened")
    screen_detector = screen_config.get("detector", {})
    for key in ("package_version", "device", "weights_url", "weights_sha256", "weights_bytes", "settings"):
        _require(night._same_typed_value(screen_detector.get(key), config["detector"].get(key)), "Screen/temporal detector control mismatch: " + key)
    _require(screen.get("sampling_sha256") == config["expected_sampling_sha256"], "DEV screen sampling lineage mismatch")
    geometry = json.loads(geometry_path.read_text())
    _require(geometry.get("status") == "ACCEPTED_PHASE7_INITIAL_GEOMETRY_BASELINE_NUMERIC_DEFAULTS_OPEN"
             and geometry["source_video"]["sha256"] == config["expected_video_sha256"], "Approved actual night geometry required")
    _require(geometry.get("geometry_contract_accepted") is True and geometry.get("counting_execution_allowed") is True,
             "Geometry/counting approval must be explicit")
    _require(geometry["source_video"].get("native_width") == plan["input_identity"]["width"]
             and geometry["source_video"].get("native_height") == plan["input_identity"]["height"], "Approved geometry native dimensions mismatch")
    feedback = geometry.get("approval_feedback", {})
    feedback_path = bound(feedback.get("path", ""), feedback.get("sha256", ""))
    feedback_data = json.loads(feedback_path.read_text())
    _require(feedback_data.get("confirmed_decisions", {}).get("direction_metadata", {}).get("A_TO_B") == "approaching camera"
             and feedback_data["confirmed_decisions"]["direction_metadata"].get("B_TO_A") == "moving away from camera", "Explicit night directions approved")
    counting = config["counting"]
    source_path = bound(counting["source_path"], B_SOURCE_SHA256)
    bound("notebooks/phase_5_geometry_helpers.py", GEOMETRY_SOURCE_SHA256)
    calibration_path = bound(counting["calibration_path"], CALIBRATION_SHA256)
    _require(json.loads(calibration_path.read_text()).get("thresholds") == config["counting"]["association"], "Frozen calibrated controls mismatch")
    video_path = bound(config["video_path"], config["expected_video_sha256"])
    return {"config": config, "plan": plan, "selection": selection, "geometry_path": geometry_path,
            "source_path": source_path, "video_path": video_path, "dev_screen_path": screen_candidates[0]}


def _write_gzip(path, value):
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as output:
        output.write((json.dumps(value, sort_keys=True, allow_nan=False)+"\n").encode())


def _counting_replay(variant_dir, config, run_id, width, height, bindings):
    source = load_phase7_counting_adapter(bindings["source_path"])
    identity = {"video_sha256": config["expected_video_sha256"], "records_sha256": night.sha256_file(variant_dir/"track_records.jsonl.gz"),
                "geometry_sha256": config["expected_geometry_sha256"], "variant": variant_dir.name, "width": width, "height": height,
                "parent_run_id": run_id}
    counting = {key: deepcopy(config["counting"][key]) for key in ("policy_version", "metric", "neutral_band_px", "confirmation_observations", "association", "grouping_enabled")}
    windows = sorted([[item["start_frame"], item["end_frame"]] for split in ("development", "holdout") for item in bindings["plan"][split]["segments"]])
    discovered = set()
    with gzip.open(variant_dir/"track_records.jsonl.gz", "rt") as records:
        for row in records:
            item = json.loads(row)
            if any(start <= item["frame_index"] <= end for start, end in windows):
                discovered.update(o["track_id"] for o in item["emitted_tracks"])
    counting.update(input_identity=identity, scope={"track_ids": sorted(discovered), "association_frame_windows": windows})
    _require(bool(discovered), "No measured track IDs in declared windows; do not substitute whole-video counting scope")
    _json(variant_dir/"counting_configuration.json", counting)
    (variant_dir/"counting_adapter.executed_source.py").write_text(source.phase7_adapted_source)
    _json(variant_dir/"counting_adapter_provenance.json", source.phase7_adapter_provenance)
    started = time.perf_counter()
    result = source.run_identity_resolution(variant_dir/"track_records.jsonl.gz", bindings["geometry_path"], config=counting)
    for key, filename in (("episodes", "episodes.json.gz"), ("relations", "relations.json.gz"), ("derived_diagnostics", "geometry_diagnostics.json.gz"),
                          ("machine_decisions", "machine_passage_decisions.json.gz"), ("accepted_events", "machine_count_events.json.gz"),
                          ("source_index", "source_index.json.gz")):
        if key in result:
            _write_gzip(variant_dir/filename, result[key])
    _json(variant_dir/"machine_aggregate.json", result["aggregate"])
    report = dict(result["report"], phase=7, phase7_source_adapter=source.phase7_adapter_provenance,
                  source_cache_created_by_phase7_new_inference=True, counting_scope=config["counting_scope"], counting_replay_wall_seconds=time.perf_counter()-started,
                  physical_passage_review_status="PENDING_SEPARATE_AUDIT_NO_CROSS_VARIANT_TRACK_ID_MATCHING")
    _json(variant_dir/"counting_report.json", report)
    return report


def run_night_temporal(config):
    """Actual GPU detector+encoder; independent fullvideo variants, offline B cache replay."""
    bindings = verify_temporal_inputs(config); config = bindings["config"]
    import cv2
    import numpy as np
    import torch
    import platform
    night.verify_gpu_device(0)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    run_dir = Path(config["output_root"])/run_id; run_dir.mkdir(parents=True, exist_ok=False)
    _json(run_dir/"configuration.json", config)
    report = {"phase": 7, "run_id": run_id, "execution_kind": "ACTUAL_MODEL_EXECUTION", "status": "initialized",
              "started_utc": datetime.now(timezone.utc).isoformat(), "configuration": config,
              "source_helper_sha256": night.sha256_file(__file__), "variants": {}, "selection_frozen_before_temporal_execution": True,
              "manual_review_status": "PENDING_PHYSICAL_PASSAGE_REVIEW", "holdout_selection_used": False,
              "environment": {"python": platform.python_version(), "opencv": cv2.__version__, "torch": str(torch.__version__),
                              "association_device": "cpu", "detector_and_encoder_device": "cuda:0"},
              "limits": ["No ground truth or accuracy/precision/recall/F1/MAPE claim", "Track IDs independent between variants",
                         "Person-domain encoder candidate remains unselected as final vehicle encoder",
                         "Frozen PAGI association controls are not night calibration", "Offline categories use whole vehicle episode",
                         "Machine accepted decisions are distinct from review overlay", "Full history crosses sampling windows; heldout family/category evidence may be offline",
                         "Only enhancement changes; its separate detector-vs-ReID contribution cannot be isolated",
                         "Sequential variants and detector/encoder warmup plus instrumentation limit timing comparisons",
                         "Inference is fullvideo; counting comparison is limited to declared five windows",
                         "No measuredIDs in declared windows is an explicit unsupported condition, not whole-video fallback"]}
    _json(run_dir/"report.json", report)
    predict, detector_resources, begin_variant, finish_variant = night._actual_detector(config["detector"])
    plan = bindings["plan"]; sample_indices = sorted(set(plan["development"]["sample_frame_indices"] + plan["holdout"]["sample_frame_indices"]))
    native_hashes = {}
    try:
        for variant in config["variants"]:
            name = variant["name"]; target = run_dir/name; target.mkdir(); (target/"samples").mkdir()
            stats = {"status": "initialized", "frames_processed": 0, "variant": variant, "native_sample_pixel_hashes": {},
                     "detector_input_policy": "NATIVE_FULL_FRAME_TRANSFORMED", "encoder_input_policy": "SAME_TRANSFORMED_FRAME_AS_DETECTOR"}
            report["variants"][name] = stats; _json(run_dir/"report.json", report)
            tracker, session, runtime = _actual_tracker(config, target); stats["encoder_runtime"] = runtime
            capture = cv2.VideoCapture(str(bindings["video_path"]))
            _require(capture.isOpened(), "Actual source video decoder failed")
            width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(capture.get(cv2.CAP_PROP_FPS)); _require(math.isfinite(fps) and fps > 0, "Observed FPS required")
            _require((width, height) == (plan["input_identity"]["width"], plan["input_identity"]["height"]), "Actual native dimensions mismatch")
            stats["decode_metadata"] = {"width": width, "height": height, "fps_backend": fps, "backend": capture.getBackendName(),
                "frame_count_backend": float(capture.get(cv2.CAP_PROP_FRAME_COUNT)), "timestamp_semantics": "index/FPS estimate; POS_MSEC unverified source PTS"}
            registry = {}; counts = Counter(); timing = Counter(); began = time.perf_counter(); begin_variant()
            try:
                with gzip.open(target/"track_records.jsonl.gz", "wt", encoding="utf-8") as records, gzip.open(target/"appearance_records.jsonl.gz", "wt", encoding="utf-8") as appearances:
                    for index in range(config["expected_frame_count"]):
                        started = time.perf_counter(); ok, raw_frame = capture.read(); timing["decode_wall_seconds"] += time.perf_counter()-started
                        _require(ok and raw_frame.shape == (height, width, 3), "Decoder failed native alignment at frame " + str(index))
                        started = time.perf_counter(); frame = night.apply_transform(raw_frame, variant); timing["transform_wall_seconds"] += time.perf_counter()-started
                        frame_hash = hashlib.sha256(frame.tobytes()).hexdigest()
                        started = time.perf_counter(); prediction = predict(frame, index, name); timing["detector_wall_seconds"] += time.perf_counter()-started
                        clean = night.validate_detection_rows(prediction["detections"], width, height, prediction["class_names"])
                        detections = [{"bbox_xyxy_pixels": d["bbox_xyxy"], "class_id": d["class_id"], "class_name": d["class_name"], "confidence": d["confidence"]} for d in clean]
                        row = {"phase": 7, "frame_index": index, "video_sha256": config["expected_video_sha256"], "width": width, "height": height,
                               "timestamp_backend_ms": float(capture.get(cv2.CAP_PROP_POS_MSEC)), "detections": detections}
                        tracker.encoder_evidence.calls = []; tracker.cost_calls = []
                        started = time.perf_counter(); outputs = update_tracker_on_transformed_frame(tracker, row, frame); timing["tracker_wall_seconds"] += time.perf_counter()-started
                        outputs = validate_emitted_outputs(outputs, row)
                        assigned, snapshots = _assigned_evidence(tracker, row, outputs, registry)
                        record = build_track_record(row, outputs, variant=name, parent_run_id=run_id, fps=fps,
                            assigned_observations=assigned, lifecycle_snapshots=snapshots)
                        record.update(detector_input_frame_pixel_sha256=frame_hash, encoder_input_frame_pixel_sha256=frame_hash,
                                      transform=variant, detector_library_speed_ms=prediction["speed_ms"])
                        check_source_record(record, index, {"video_sha256": config["expected_video_sha256"], "variant": name, "parent_run_id": run_id, "width": width, "height": height})
                        calls = tracker.encoder_evidence.calls
                        _require(all(c["donor_frame_pixel_sha256"] == frame_hash for c in calls), "Detector/encoder donor frame mismatch")
                        if calls and "cuda_execution_evidence" not in stats:
                            profile = Path(session.end_profiling()); proof = provider_profile_evidence(json.loads(profile.read_text()))
                            proof.update(profile=profile.name, profile_sha256=night.sha256_file(profile), profiled_source_frame=index)
                            _json(target/"encoder_provider_evidence.json", proof); stats["cuda_execution_evidence"] = proof
                        records.write(json.dumps(record, allow_nan=False)+"\n")
                        appearances.write(json.dumps({"phase": 7, "frame_index": index, "variant": name, "encoder_calls": calls,
                            "association_calls": tracker.cost_calls, "donor_frame_pixel_sha256": frame_hash}, allow_nan=False)+"\n")
                        counts.update(raw_detections=len(detections), emitted_observations=len(record["emitted_tracks"]),
                                      empty_detection_frames=int(not detections), no_emitted_track_frames=int(not record["emitted_tracks"]))
                        timing["encoder_wall_seconds_inside_tracker"] += sum(c["encoder_wall_seconds"] for c in calls)
                        if index in sample_indices:
                            raw_hash = hashlib.sha256(raw_frame.tobytes()).hexdigest(); stats["native_sample_pixel_hashes"][str(index)] = raw_hash
                            _require(index not in native_hashes or native_hashes[index] == raw_hash, "Independent variant native source pixels differ")
                            native_hashes[index] = raw_hash
                            _require(cv2.imwrite(str(target/"samples"/f"frame_{index:09d}_input.png"), frame), "Actual transformed PNG export failed")
                            stats.setdefault("samples", []).append({"frame_index": index, "input_png": f"samples/frame_{index:09d}_input.png",
                                "input_png_sha256": night.sha256_file(target/"samples"/f"frame_{index:09d}_input.png"), "pixel_sha256": frame_hash})
                        stats["frames_processed"] = index+1
                        if (index+1) % 1000 == 0:
                            records.flush(); appearances.flush(); _json(run_dir/"report.json", report)
                            print(f"{name}: {index+1}/{config['expected_frame_count']} native frames; tracker IDs are not traffic counts", flush=True)
                    extra, _ = capture.read(); _require(not extra, "Unexpected source frame beyond expected fullvideo scope")
            finally:
                capture.release(); stats["timing"] = dict(timing, loop_wall_seconds=time.perf_counter()-began)
                stats["resource"] = dict(finish_variant(), process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
                stats["observed_diagnostics"] = dict(counts, captured_ids_including_unconfirmed=len(registry),
                    within_id_gap_events=sum(len(r["gap_events"]) for r in registry.values()), within_id_raw_class_changes=sum(len(r["class_changes"]) for r in registry.values()))
                stats["appearance_diagnostics"] = dict(tracker.cost_totals, encoder_calls=tracker.encoder_evidence.total_calls,
                    finite_nonzero_features_produced=tracker.encoder_evidence.total_features, embedding_dimension=512)
                _json(target/"track_summary.json", {"semantics": "software lifecycle diagnostic, not physical object/traffic totals", "tracks": list(registry.values())})
            _require(stats.get("cuda_execution_evidence", {}).get("actual_cuda_execution_confirmed") is True
                     and tracker.encoder_evidence.total_features > 0 and tracker.cost_totals["nonempty_feature_association_calls"] > 0,
                     "Actual CUDA encoder kernels/features/association required")
            stats["detector_resources"] = deepcopy(detector_resources)
            stats["status"] = "completed_full_video_inference_counting_replay_pending"
            stats["track_records_sha256"] = night.sha256_file(target/"track_records.jsonl.gz")
            stats["appearance_records_sha256"] = night.sha256_file(target/"appearance_records.jsonl.gz")
            _json(run_dir/"report.json", report)
            del tracker, session
            stats["counting_report"] = _counting_replay(target, config, run_id, width, height, bindings)
            stats["status"] = "completed_full_video_inference_geometry_counting_review_pending"
            _json(run_dir/"report.json", report)
        report["status"] = "completed_raw_selected_temporal_machine_outputs_physical_review_pending"
        report["native_sample_pixel_equality"] = {"passed": True, "frame_indices": sorted(native_hashes)}
    except Exception as exc:
        report["status"] = "failed_partial_execution"
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat(); _json(run_dir/"report.json", report)
        artifacts = [{"path": str(p.relative_to(run_dir)), "sha256": night.sha256_file(p), "bytes": p.stat().st_size}
                     for p in sorted(run_dir.rglob("*")) if p.is_file() and p.name != "retention_manifest.json"]
        _json(run_dir/"retention_manifest.json", {"phase": 7, "run_id": run_id, "artifacts": artifacts})
    print("Actual Phase7 temporal artifacts:", run_dir, flush=True)
    return {"run_dir": str(run_dir), "report": report}
