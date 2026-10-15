"""Phase 8 notebook prototype: full-video raw processing and source-bound replay.

The frozen Phase 6 B algorithm is reused without threshold/algorithm changes.
Old runs are never appended to this snapshot. Machine accepted passages remain
experimental; unresolved categories, returns and identities require audit.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import time
import types

import phase_7_night_helpers as night
import phase_7_temporal_helpers as temporal
import phase_8_manifest_helpers as manifest
from phase_5_geometry_helpers import Geometry


PROVENANCE = "retained_phase_8_detection"
PROFILE_VERSION = "phase8_full_video_raw_b_v1"
PHASE7_ACTUAL_REPORT_SHA256 = "1bbb6bd1c392f24eb9fd74e8462aeb2e88385a798c4b6876f2585c59c99f3304"
FROZEN_SOURCES = {
    "notebooks/phase_7_night_helpers.py": "6a31794bad0c5cd346575ad4602adb5d10f17bd14cc1094dd5f2b207b0935889",
    "notebooks/phase_7_temporal_helpers.py": "2ef8de2d0d309b86bae6a75a2135c59d8dd09e203610fc444c6023c0614d9c74",
    "notebooks/phase_5_geometry_helpers.py": temporal.GEOMETRY_SOURCE_SHA256,
    "notebooks/phase_6_identity_resolution_helpers.py": temporal.B_SOURCE_SHA256,
    "docs/evidence/phase_6/option_b_calibration/frozen_thresholds.json": temporal.CALIBRATION_SHA256,
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _gz(path, value):
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as output:
        output.write((json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode())


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _bound(root, path, sha):
    path = Path(path) if Path(path).is_absolute() else Path(root) / path
    _require(path.is_file() and night.sha256_file(path) == sha, "Source SHA mismatch: " + str(path))
    return path


def make_processing_profile(repo_root="."):
    """Explicit experimental controls; final vehicle-ReID/thresholds remain OPEN."""
    root = Path(repo_root).resolve()
    for path, sha in FROZEN_SOURCES.items():
        _bound(root, path, sha)
    detector = night.make_screen_config("0" * 64, "0" * 64,
        weights_path="/kaggle/working/phase_8_assets/yolo26m.pt")["detector"]
    return {"profile_version": PROFILE_VERSION, "phase": 8, "variant": {"name": "raw", "method": "raw"},
        "device": "cuda:0", "execution_policy": "SEQUENTIAL_ONE_FULL_VIDEO_ON_CUDA0",
        "frame_scope": "FRAME_ZERO_TO_DECODER_END", "counting_scope": "ALL_MEASURED_TRACK_EPISODES_FULL_VIDEO",
        "detector": detector, "tracker": deepcopy(temporal.TRACKER_CONTROL),
        "encoder": {"path": "/kaggle/working/phase_8_assets/yolo26n-reid.onnx", "url": temporal.ENCODER_URL,
            "sha256": temporal.ENCODER_SHA256, "bytes": temporal.ENCODER_BYTES, "device": "cuda:0",
            "onnx_version": "1.20.1", "ort_version": "1.24.4", "input_policy": "SAME_TRANSFORMED_FRAME_AS_DETECTOR",
            "final_vehicle_configuration": False, "documented_training_domain": "MSMT17-v1 person; vehicle transfer unknown"},
        "counting": {"policy_version": "phase6_option_b_v1", "metric": "passage", "neutral_band_px": 0.0,
            "confirmation_observations": 1, "association": deepcopy(temporal.ASSOCIATION_CONTROL), "grouping_enabled": True},
        "source_bindings": deepcopy(FROZEN_SOURCES),
        "category_coverage": {"motorcycle": "experimental_vehicle_passage", "car": "experimental_vehicle_passage",
            "truck": "experimental_vehicle_passage", "pedestrian": "NOT_IMPLEMENTED_BY_FROZEN_B_V1",
            "bus_angkot": "BUS_ANGKOT_MAPPING_OPEN"},
        "result_semantics": "OFFLINE_MACHINE_SUBTOTAL_SEPARATE_FROM_REVIEW_NOT_COMPLETE_TRAFFIC_GROUND_TRUTH"}


def validate_processing_profile(profile, repo_root="."):
    expected = make_processing_profile(repo_root)
    candidate = deepcopy(profile)
    # Asset locations are configurable, but asset bytes and every behavior control are fixed.
    for section, field in (("detector", "weights_path"), ("encoder", "path")):
        value = candidate.get(section, {}).get(field)
        _require(isinstance(value, str) and bool(value), "Explicit model asset path required")
        candidate[section][field] = expected[section][field]
    _require(night._same_typed_value(candidate, expected), "Phase8 profile differs from frozen raw controls")
    return deepcopy(profile)


def validate_geometry(path, identity, *, repo_root=".", allow_synthetic=False):
    path = _bound(repo_root, path, identity["geometry_sha256"])
    data = _read_json(path)
    _require(data.get("geometry_contract_accepted") is True, "Per-video geometry has not been accepted")
    _require(str(data.get("status", "")).startswith("ACCEPTED_"), "Accepted geometry status required")
    _require(data.get("selected_anchor") == "bottom_center", "Raw measured vehicle BC is required")
    directions = data.get("confirmed_direction_metadata", {})
    _require(all(isinstance(directions.get(k), str) and directions[k].strip() for k in ("A_TO_B", "B_TO_A")),
        "Per-video direction confirmation required")
    _require(data.get("source_video", {}).get("sha256") == identity["video_sha256"], "Geometry belongs to another video")
    evidence_root = path.parent if allow_synthetic else Path(repo_root).resolve()
    _, geometry, _ = manifest._reviewed_geometry(evidence_root, path, identity["geometry_sha256"],
        identity["video_sha256"], identity["width"], identity["height"], allow_synthetic)
    return path, geometry


def load_counting_adapter(repo_root, provenance):
    """One source-provenance literal substitution, never changed old source."""
    _require(provenance in ("retained_phase_2_detection", "retained_phase_7_detection", PROVENANCE), "Unsupported donor provenance")
    path = _bound(repo_root, "notebooks/phase_6_identity_resolution_helpers.py", temporal.B_SOURCE_SHA256)
    text = path.read_text(encoding="utf-8")
    old, new = '"retained_phase_2_detection"', json.dumps(provenance)
    _require(text.count(old) == 1, "Expected one frozen B source-provenance literal")
    adapted = text.replace(old, new, 1)
    module = types.ModuleType("phase_8_source_bound_b_adapter")
    module.__file__ = str(path)
    exec(compile(adapted, str(path) + "::phase8_provenance_adapter", "exec"), module.__dict__)
    proof = {"base_source_sha256": temporal.B_SOURCE_SHA256,
        "adapted_source_sha256": hashlib.sha256(adapted.encode()).hexdigest(),
        "literal_substitution_count": int(new != old), "from": old, "to": new,
        "behavior_changes": "SOURCE_PROVENANCE_ENUM_ONLY_NO_ALGORITHM_OR_THRESHOLD_CHANGE"}
    return module, proof, adapted


def _records(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as source:
        for line in source:
            _require(bool(line.strip()), "Blank cache record")
            yield json.loads(line)


def _validate_full_cache(path, identity, provenance, frame_count):
    _require(night.sha256_file(path) == identity["records_sha256"], "Cache SHA mismatch")
    night._positive_integer(frame_count, "observed frame count")
    expected_phase = {"retained_phase_2_detection": None, "retained_phase_7_detection": 7, PROVENANCE: 8}[provenance]
    count = 0
    for record in _records(path):
        _require(type(record.get("frame_index")) is int and record["frame_index"] == count, "Cache must contain every frame from zero in order")
        for key in ("video_sha256", "variant", "parent_run_id", "width", "height"):
            _require(record.get(key) == identity[key], "Source cache identity mismatch: " + key)
        if expected_phase is not None:
            _require(record.get("phase") == expected_phase and record.get("measurement_provenance") == provenance, "Truthful source phase/provenance required")
        raw, observations = record.get("raw_detections"), record.get("emitted_tracks")
        _require(isinstance(raw, list) and isinstance(observations, list), "Raw source measurements and emitted tracks required")
        for det in raw:
            box = det.get("bbox_xyxy_pixels", [])
            _require(len(box) == 4 and all(isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) for v in box), "Finite source bbox required")
            _require(0 <= box[0] < box[2] <= identity["width"] and 0 <= box[1] < box[3] <= identity["height"], "Raw bbox exceeds native image")
        ids, indices = set(), set()
        for observation in observations:
            idx, track = observation.get("original_detection_index"), observation.get("track_id")
            _require(type(idx) is int and 0 <= idx < len(raw) and idx not in indices and type(track) is int and track > 0 and track not in ids,
                "Unique direct source-detection linkage required")
            _require(observation.get("frame_index") == count and observation.get("emitted") is True and observation.get("measurement_provenance") == provenance,
                "Predicted/nonemitted observation cannot be counting evidence")
            det = raw[idx]
            _require(observation.get("raw_bbox") == det["bbox_xyxy_pixels"] and all(observation.get(k) == det[k] for k in ("class_id", "class_name", "confidence")),
                "Observation is not linked to its actual raw detector measurement")
            ids.add(track); indices.add(idx)
        count += 1
    _require(count == frame_count, "Full decoded-frame count differs from complete cache")
    return count


def _match_model_controls(config, profile):
    detector = deepcopy(config.get("detector", {})); expected = deepcopy(profile["detector"])
    detector.pop("weights_path", None); expected.pop("weights_path", None)
    _require(night._same_typed_value(detector, expected), "Donor detector controls/asset differ")
    _require(night._same_typed_value(config.get("tracker"), profile["tracker"]), "Donor tracker controls differ")
    encoder = config.get("encoder", {})
    for key in ("sha256", "bytes", "device", "onnx_version", "ort_version", "input_policy", "final_vehicle_configuration"):
        _require(encoder.get(key) == profile["encoder"][key], "Donor encoder differs: " + key)


def validate_appearance_execution(branch):
    """Empty videos are valid; missing expected encoder evidence is an error."""
    diagnostics = branch.get("appearance_diagnostics", {})
    raw_count = branch.get("observed_diagnostics", {}).get("raw_detections")
    features = diagnostics.get("finite_nonzero_features_produced")
    calls = diagnostics.get("encoder_calls")
    proof = branch.get("cuda_execution_evidence", {})
    if raw_count == 0:
        _require(type(raw_count) is int and type(features) is int and features == 0 and type(calls) is int and calls == 0,
            "Empty source has inconsistent appearance counters")
        _require(proof.get("actual_cuda_execution_confirmed") is not True,
            "Zero-crop source must not claim executed CUDA encoder kernels")
        status = {"status": "not_executed_no_eligible_crops", "actual_cuda_execution_confirmed": False,
            "encoder_calls": 0, "finite_nonzero_features_produced": 0,
            "association_status": "not_executed_no_nonempty_candidate_pairs"}
    else:
        _require(type(raw_count) is int and raw_count > 0 and type(features) is int and features > 0 and type(calls) is int and calls > 0,
            "Detected eligible crops require actual finite appearance features")
        _require(proof.get("actual_cuda_execution_confirmed") is True, "Actual CUDA encoder proof absent for eligible crops")
        status = {"status": "executed_actual_cuda", "actual_cuda_execution_confirmed": True,
            "encoder_calls": calls, "finite_nonzero_features_produced": features,
            "association_status": "executed_nonempty_feature_pairs" if diagnostics.get("nonempty_feature_association_calls", 0) > 0
                else "not_executed_no_nonempty_candidate_pairs"}
    if "appearance_execution" in branch:
        _require(branch["appearance_execution"] == status, "Retained appearance execution status differs from measured counters")
    return status


def validate_cache_provenance(provenance, identity, profile, *, repo_root="."):
    """Read retained execution proof rather than trusting a caller's source label."""
    _require(isinstance(provenance, dict), "Explicit donor execution proof required")
    path = _bound(repo_root, provenance["source_report_path"], provenance["source_report_sha256"])
    report = _read_json(path)
    _require(report.get("execution_kind") == "ACTUAL_MODEL_EXECUTION", "Actual retained GPU source execution required")
    phase = report.get("phase")
    _require(phase in (7, 8), "This donor report format supports verified Phase7/8 GPU sources only; Phase2 cache alone lacks ReID proof")
    _require(report.get("run_id") == identity["parent_run_id"], "Donor run identity mismatch")
    _match_model_controls(report.get("configuration", {}), profile)
    if phase == 7:
        _require(night.sha256_file(path) == PHASE7_ACTUAL_REPORT_SHA256, "Phase7 donor must be the immutable retained actual execution report")
        _require(report.get("source_helper_sha256") == FROZEN_SOURCES["notebooks/phase_7_temporal_helpers.py"], "Donor executed helper differs")
        _require(report.get("configuration", {}).get("expected_video_sha256") == identity["video_sha256"], "Donor report video identity mismatch")
        branch = report.get("variants", {}).get(identity["variant"], {})
        _require(branch.get("variant") == {"name": "raw", "method": "raw"}, "Only raw donor frames permitted")
        _require(str(branch.get("status", "")).startswith("completed_full_video_inference_geometry_counting"), "Donor inference incomplete")
    else:
        _require(report.get("source_helper_sha256") == night.sha256_file(__file__), "Donor Phase8 executed source differs")
        _require(report.get("source_identity", {}).get("video_sha256") == identity["video_sha256"], "Donor report video identity mismatch")
        branch = report
        _require(report.get("inference_status") == "completed", "Donor Phase8 inference incomplete")
    _require(branch.get("track_records_sha256") == identity["records_sha256"], "Retained donor report does not bind cache bytes")
    appearance_execution = validate_appearance_execution(branch)
    frames = branch.get("frames_processed")
    _require((branch.get("decode_metadata", {}).get("width"), branch.get("decode_metadata", {}).get("height")) == (identity["width"], identity["height"]), "Donor actual native dimensions differ")
    appearance_path = _bound(repo_root, provenance["appearance_records_path"], provenance["appearance_records_sha256"])
    _require(branch.get("appearance_records_sha256") == night.sha256_file(appearance_path), "Appearance stream not bound by actual donor report")
    actual = "retained_phase_7_detection" if phase == 7 else PROVENANCE
    _require(provenance.get("measurement_provenance", actual) == actual, "Caller donor provenance differs from retained execution")
    return {"source_report_path": str(path), "source_report_sha256": night.sha256_file(path),
        "source_phase": phase, "measurement_provenance": actual, "frame_count": frames,
        "appearance_records_path": str(appearance_path), "appearance_records_sha256": night.sha256_file(appearance_path),
        "appearance_execution": appearance_execution,
        "new_detector_tracker_encoder_inference": False,
        "appearance_limits": "Feature hashes/norms and observer assertions retained; full embedding/cost matrices are not independent numeric proof"}


def _manifest(directory):
    directory = Path(directory)
    files = [{"path": str(p.relative_to(directory)), "sha256": night.sha256_file(p), "bytes": p.stat().st_size}
        for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "retention_manifest.json"]
    _json(directory / "retention_manifest.json", {"phase": 8, "artifacts": files})


def _execute_replay(records_path, geometry_path, profile, output_dir, *, repo_root, identity, proof, synthetic=False):
    target = Path(output_dir); target.mkdir(parents=True, exist_ok=False)
    config = deepcopy(profile["counting"])
    proof = dict(proof, records_path=str(Path(records_path).resolve()), records_sha256=identity["records_sha256"],
        geometry_path=str(Path(geometry_path).resolve()), geometry_sha256=identity["geometry_sha256"])
    config.update(input_identity=deepcopy(identity), scope={"track_ids": None, "association_frame_windows": None})
    source, adaptation, adapted = load_counting_adapter(repo_root, proof["measurement_provenance"])
    _json(target / "counting_configuration.json", config)
    _json(target / "counting_adapter_provenance.json", adaptation)
    (target / "counting_adapter.executed_source.py").write_text(adapted, encoding="utf-8")
    started = time.perf_counter()
    try:
        result = source.run_identity_resolution(records_path, geometry_path, config=config)
        for key, filename in (("episodes", "episodes.json.gz"), ("relations", "relations.json.gz"),
            ("derived_diagnostics", "geometry_diagnostics.json.gz"), ("machine_decisions", "machine_passage_decisions.json.gz"),
            ("accepted_events", "machine_count_events.json.gz"), ("source_index", "source_index.json.gz")):
            _gz(target / filename, result[key])
        _json(target / "machine_aggregate.json", result["aggregate"])
        snapshot = hashlib.sha256(json.dumps({"source_identity": identity, "profile": profile}, sort_keys=True).encode()).hexdigest()
        report = dict(result["report"], phase=8, run_id="p8_" + snapshot, snapshot_id="p8_" + snapshot,
            source_identity=deepcopy(identity), cache_provenance=proof, configuration=profile,
            records_path=str(Path(records_path).resolve()), geometry_path=str(Path(geometry_path).resolve()),
            counting_scope="ALL_MEASURED_TRACK_EPISODES_FULL_VIDEO", source_adapter=adaptation,
            execution_kind="SYNTHETIC_FIXTURE" if synthetic else "ACTUAL_RETAINED_SOURCE_COUNTING_REPLAY",
            status="completed_full_video_machine_snapshot_review_pending", counting_replay_wall_seconds=time.perf_counter()-started,
            category_coverage=profile["category_coverage"], aggregate_semantics="ACCEPTED_MACHINE_PASSAGE_SUBTOTAL_NOT_ALL_TRAFFIC",
            manual_review_status="PENDING_NEW_FULL_SCOPE_AUDIT_NO_OLD_OVERLAY_REUSE", old_events_or_review_overlays_copied=False,
            complete_eight_video_batch=False, appearance_used_by_b_resolver=False)
        _json(target / "counting_report.json", report)
        _json(target / "report.json", report)
        _json(target / "phase_8_snapshot.json", {"phase": 8, "snapshot_id": report["snapshot_id"], "source_identity": identity,
            "source_event_ids": [e["event_id"] for e in result["accepted_events"]],
            "source_candidate_ids": [d["candidate_id"] for d in result["machine_decisions"]], "old_machine_ids_preserved_as_source_references": True})
    except Exception as exc:
        _json(target / "error.json", {"phase": 8, "status": "failed_partial_replay", "type": type(exc).__name__, "message": str(exc)})
        _manifest(target)
        raise
    except BaseException:
        _manifest(target)
        raise
    snapshot = {"kind": "machine", "run_id": report["run_id"], "scope": "full_video", "frames_processed": proof["frame_count"],
        "source_identity": deepcopy(identity)}
    for name, filename in (("events", "machine_count_events.json.gz"), ("decisions", "machine_passage_decisions.json.gz"), ("configuration", "counting_configuration.json")):
        path = (target / filename).resolve()
        snapshot[name + "_path"] = str(path); snapshot[name + "_sha256"] = night.sha256_file(path)
    descriptor = _read_json(target / "phase_8_snapshot.json")
    descriptor.update(snapshot, snapshot_kind="machine", profile_name=PROFILE_VERSION,
        config_path=snapshot["configuration_path"], config_sha256=snapshot["configuration_sha256"])
    _json(target / "phase_8_snapshot.json", descriptor)
    _manifest(target)
    return {"report": report, "run_dir": str(target), "status": report["status"], "aggregate": result["aggregate"],
        "snapshot": snapshot, "run_id": snapshot["run_id"], "source_identity": deepcopy(identity), "frames_processed": proof["frame_count"], "scope": "full_video"}


def replay_full_video_cache(records_path, geometry_path, profile, output_dir, *, repo_root=".", cache_identity, cache_provenance):
    """Full scope replay only; no detector/tracker/encoder rerun, no old review reuse."""
    profile = validate_processing_profile(profile, repo_root)
    identity = deepcopy(cache_identity)
    _require(identity.get("variant") == "raw", "Phase8 baseline is raw")
    for key in ("video_sha256", "records_sha256", "geometry_sha256"):
        night._hash(identity.get(key), key)
    for key in ("width", "height"):
        night._positive_integer(identity.get(key), key)
    records_path = Path(records_path) if Path(records_path).is_absolute() else Path(repo_root) / records_path
    geometry_path, _ = validate_geometry(geometry_path, identity, repo_root=repo_root)
    proof = validate_cache_provenance(cache_provenance, identity, profile, repo_root=repo_root)
    _validate_full_cache(records_path, identity, proof["measurement_provenance"], proof["frame_count"])
    return _execute_replay(records_path, geometry_path, profile, output_dir, repo_root=repo_root, identity=identity, proof=proof)


def _phase8_record(row, outputs, *, run_id, fps, assigned, snapshots):
    record = temporal.build_track_record(row, outputs, variant="raw", parent_run_id=run_id, fps=fps,
        assigned_observations=assigned, lifecycle_snapshots=snapshots)
    record["phase"] = 8; record["measurement_provenance"] = PROVENANCE
    for key in ("emitted_tracks", "assigned_observations_including_unconfirmed"):
        for observation in record[key]:
            observation["measurement_provenance"] = PROVENANCE
    record["record_serialization_adaptation"] = "PHASE_AND_MEASUREMENT_NAMESPACE_ONLY_NO_COORDINATE_OR_ASSOCIATION_CHANGE"
    return record


def render_annotated_video(video_path, records_path, geometry_path, identity, decisions_path, output_path, *, fps, expected_frame_count):
    """Second decoder pass; raw vehicle BC never replaced by a rider/filtered box."""
    import cv2
    import numpy as np
    _require(night.sha256_file(video_path) == identity["video_sha256"], "Annotation source video SHA differs from counting input")
    geometry = Geometry.from_draft(geometry_path, identity["width"], identity["height"])
    with gzip.open(decisions_path, "rt", encoding="utf-8") as handle:
        decisions = json.load(handle)
    by_track = {}
    for decision in decisions:
        by_track.setdefault(decision["track_id"], []).append(decision)
    output_path = Path(output_path); output_path.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path)); _require(capture.isOpened(), "Annotation source decoder unavailable")
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (identity["width"], identity["height"]))
    _require(writer.isOpened(), "MP4 writer unavailable; no silent codec substitution")
    count = 0
    try:
        for record in _records(records_path):
            ok, frame = capture.read()
            _require(ok and record["frame_index"] == count and frame.shape[:2] == (identity["height"], identity["width"]), "Annotation/cache native frame alignment failed")
            donor = record.get("detector_input_frame_pixel_sha256")
            if donor is not None:
                _require(hashlib.sha256(frame.tobytes()).hexdigest() == donor, "Annotation source pixels differ from actual raw donor")
            for polygon, colour in ((geometry.side_a, (255, 160, 0)), (geometry.side_b, (0, 130, 255))):
                cv2.polylines(frame, [np.rint(polygon).astype(np.int32)], True, colour, 2)
            cv2.line(frame, tuple(round(v) for v in geometry.p1), tuple(round(v) for v in geometry.p2), (0, 255, 255), 2)
            for det in record["raw_detections"]:
                box = [round(v) for v in det["bbox_xyxy_pixels"]]
                cv2.rectangle(frame, tuple(box[:2]), tuple(box[2:]), (90, 90, 90), 1)
            for obs in record["emitted_tracks"]:
                box = obs["raw_bbox"]; centre = (round((box[0] + box[2]) / 2), round(box[3]))
                relevant = [d for d in by_track.get(obs["track_id"], []) if d["diagnostic"].get("origin_frame", d["diagnostic"]["frame_index"]) <= count <= d["diagnostic"].get("confirmation_frame", d["diagnostic"]["frame_index"])]
                status = "/".join(sorted({d["status"] for d in relevant})) or "track"
                colour = (0, 220, 0) if any(d["accepted_count_event"] for d in relevant) else (0, 200, 255)
                cv2.rectangle(frame, (round(box[0]), round(box[1])), (round(box[2]), round(box[3])), colour, 2)
                if obs["class_name"] in ("motorcycle", "car", "truck", "bus"):
                    cv2.circle(frame, centre, 4, colour, -1)
                cv2.putText(frame, f"ID{obs['track_id']} {obs['class_name']} {status}", (round(box[0]), max(14, round(box[1]) - 5)), cv2.FONT_HERSHEY_SIMPLEX, .42, colour, 1, cv2.LINE_AA)
            cv2.putText(frame, f"frame {count} | offline B v1 machine decisions | raw vehicle BC", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1, cv2.LINE_AA)
            writer.write(frame); count += 1
        extra, _ = capture.read(); _require(not extra and count == expected_frame_count, "Annotated/cache/source full-frame count differs")
    finally:
        capture.release(); writer.release()
    verify = cv2.VideoCapture(str(output_path)); actual = 0
    try:
        _require(verify.isOpened(), "Written annotated video cannot be reopened")
        while True:
            ok, frame = verify.read()
            if not ok:
                break
            _require(frame.shape[:2] == (identity["height"], identity["width"]), "Written annotation native dimensions differ")
            actual += 1
    finally:
        verify.release()
    _require(actual == count, "Written MP4 decode count differs")
    return {"path": str(output_path), "sha256": night.sha256_file(output_path), "frames_written_and_redecoded": count,
        "width": identity["width"], "height": identity["height"], "fps": fps, "codec": "mp4v",
        "timestamp_semantics": "presentation index/FPS; not preserved authoritative source PTS", "source_audio_preserved": False,
        "annotation_semantics": "OFFLINE_MACHINE_DECISIONS_NOT_MANUAL_AUDIT_OR_MODEL_ACCURACY"}


def run_full_video(video, profile, output_dir, *, repo_root="."):
    """Actual fresh GPU inference for one approved video; no CPU fallback/sampling."""
    profile = validate_processing_profile(profile, repo_root)
    metadata = video["observed_metadata"]
    for key in ("width", "height", "frame_count"):
        night._positive_integer(metadata.get(key), key)
    night._number(metadata.get("fps"), "observed FPS", 0, strict_low=True)
    source_path = _bound(repo_root, video["source_path"], video["source_sha256"])
    identity = {"video_sha256": video["source_sha256"], "geometry_sha256": video["geometry_sha256"],
        "width": metadata["width"], "height": metadata["height"], "variant": "raw"}
    geometry_path, _ = validate_geometry(video["geometry_path"], identity, repo_root=repo_root)
    # All source/geometry/profile gates above complete before models/runtime load.
    import cv2
    import torch
    night.verify_gpu_device(0)
    run_id = datetime.now(timezone.utc).strftime("phase8_%Y%m%dT%H%M%S_%fZ")
    target = Path(output_dir); target.mkdir(parents=True, exist_ok=False)
    identity["parent_run_id"] = run_id
    report = {"phase": 8, "run_id": run_id, "video_id": video["video_id"], "execution_kind": "ACTUAL_MODEL_EXECUTION",
        "configuration": profile, "source_identity": identity, "status": "initialized", "inference_status": "pending", "frames_processed": 0,
        "source_helper_sha256": night.sha256_file(__file__), "counting_scope": profile["counting_scope"],
        "new_detector_tracker_encoder_inference": True, "complete_eight_video_batch": False,
        "record_adapter": "FROZEN_PHASE7_SERIALIZER_PHASE_NAMESPACE_ONLY_NO_VALUES_CHANGED",
        "category_coverage": profile["category_coverage"], "started_utc": datetime.now(timezone.utc).isoformat()}
    _json(target / "configuration.json", profile); _json(target / "report.json", report)
    capture = tracker = session = None
    began = time.perf_counter(); timing = Counter(); registry = {}; counts = Counter()
    try:
        predict, resources, begin, finish = night._actual_detector(profile["detector"])
        tracker, session, runtime = temporal._actual_tracker(profile, target)
        report["encoder_runtime"] = runtime
        capture = cv2.VideoCapture(str(source_path)); _require(capture.isOpened(), "Source decoder failed")
        _require((int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))) == (metadata["width"], metadata["height"]), "Actual native dimensions differ")
        decoder_fps = float(capture.get(cv2.CAP_PROP_FPS)); _require(math.isfinite(decoder_fps) and decoder_fps > 0, "Actual decoder FPS unavailable")
        report["decode_metadata"] = dict(metadata, decoder_fps=decoder_fps, fps_semantics="observed average/index estimate; authoritative PTS unknown")
        begin()
        with gzip.open(target / "track_records.jsonl.gz", "wt", encoding="utf-8") as records, gzip.open(target / "appearance_records.jsonl.gz", "wt", encoding="utf-8") as appearances:
            for index in range(metadata["frame_count"]):
                started = time.perf_counter(); ok, frame = capture.read(); timing["decode_wall_seconds"] += time.perf_counter()-started
                _require(ok and frame.shape == (metadata["height"], metadata["width"], 3), "Fullvideo decode/alignment failed at " + str(index))
                donor = hashlib.sha256(frame.tobytes()).hexdigest()
                started = time.perf_counter(); prediction = predict(frame, index, "raw"); timing["detector_wall_seconds"] += time.perf_counter()-started
                clean = night.validate_detection_rows(prediction["detections"], metadata["width"], metadata["height"], prediction["class_names"])
                detections = [{"bbox_xyxy_pixels": d["bbox_xyxy"], "class_id": d["class_id"], "class_name": d["class_name"], "confidence": d["confidence"]} for d in clean]
                row = dict(identity, frame_index=index, timestamp_backend_ms=float(capture.get(cv2.CAP_PROP_POS_MSEC)), detections=detections)
                tracker.encoder_evidence.calls = []; tracker.cost_calls = []
                started = time.perf_counter(); outputs = temporal.update_tracker_on_transformed_frame(tracker, row, frame); timing["tracker_wall_seconds"] += time.perf_counter()-started
                outputs = temporal.validate_emitted_outputs(outputs, row)
                assigned, snapshots = temporal._assigned_evidence(tracker, row, outputs, registry)
                record = _phase8_record(row, outputs, run_id=run_id, fps=metadata["fps"], assigned=assigned, snapshots=snapshots)
                record.update(detector_input_frame_pixel_sha256=donor, encoder_input_frame_pixel_sha256=donor,
                    transform=profile["variant"], detector_library_speed_ms=prediction["speed_ms"])
                calls = tracker.encoder_evidence.calls
                _require(all(call["donor_frame_pixel_sha256"] == donor for call in calls), "Detector/ReID donor mismatch")
                if calls and "cuda_execution_evidence" not in report:
                    actual_profile = Path(session.end_profiling())
                    proof = temporal.provider_profile_evidence(_read_json(actual_profile))
                    proof.update(profile=actual_profile.name, profile_sha256=night.sha256_file(actual_profile), profiled_source_frame=index)
                    report["cuda_execution_evidence"] = proof; _json(target / "encoder_provider_evidence.json", proof)
                records.write(json.dumps(record, allow_nan=False) + "\n")
                appearances.write(json.dumps({"phase": 8, "frame_index": index, "variant": "raw", "encoder_calls": calls,
                    "association_calls": tracker.cost_calls, "donor_frame_pixel_sha256": donor}, allow_nan=False) + "\n")
                counts.update(raw_detections=len(detections), emitted_observations=len(record["emitted_tracks"]))
                timing["encoder_wall_seconds_inside_tracker"] += sum(call["encoder_wall_seconds"] for call in calls)
                report["frames_processed"] = index + 1
                if (index + 1) % 1000 == 0:
                    records.flush(); appearances.flush(); _json(target / "report.json", report)
                    print(f"{video['video_id']}: {index+1}/{metadata['frame_count']} frames; IDs are not traffic counts", flush=True)
            extra, _ = capture.read(); _require(not extra, "Video contains frames beyond observed metadata")
        report["resource"] = dict(finish(), process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        report["detector_resources"] = deepcopy(resources)
        report["appearance_diagnostics"] = dict(tracker.cost_totals, encoder_calls=tracker.encoder_evidence.total_calls,
            finite_nonzero_features_produced=tracker.encoder_evidence.total_features, embedding_dimension=512)
        report["timing"] = dict(timing, inference_loop_wall_seconds=time.perf_counter()-began)
        report["observed_diagnostics"] = dict(counts)
        report["appearance_execution"] = validate_appearance_execution(report)
        _json(target / "track_summary.json", {"semantics": "software track lifecycle, not physical traffic totals", "tracks": list(registry.values())})
        identity["records_sha256"] = night.sha256_file(target / "track_records.jsonl.gz")
        report.update(track_records_sha256=identity["records_sha256"], appearance_records_sha256=night.sha256_file(target / "appearance_records.jsonl.gz"), inference_status="completed")
        _validate_full_cache(target / "track_records.jsonl.gz", identity, PROVENANCE, metadata["frame_count"])
        _json(target / "report.json", report)
        proof = {"measurement_provenance": PROVENANCE, "source_phase": 8, "frame_count": metadata["frame_count"], "new_detector_tracker_encoder_inference": True,
            "source_report_path": str(target / "report.json"), "appearance_records_sha256": report["appearance_records_sha256"]}
        replay = _execute_replay(target / "track_records.jsonl.gz", geometry_path, profile, target / "counting", repo_root=repo_root, identity=identity, proof=proof)
        report["counting_report"] = replay["report"]
        report["annotated_video"] = render_annotated_video(source_path, target / "track_records.jsonl.gz", geometry_path, identity,
            target / "counting" / "machine_passage_decisions.json.gz", target / "annotated.mp4", fps=metadata["fps"], expected_frame_count=metadata["frame_count"])
        report["status"] = "completed_full_video_pipeline_machine_snapshot_review_pending"
    except Exception as exc:
        report["status"] = "failed_partial_execution"; report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        if capture is not None:
            capture.release()
        report["finished_utc"] = datetime.now(timezone.utc).isoformat(); report["total_wall_seconds"] = time.perf_counter()-began
        _json(target / "report.json", report); _manifest(target)
        if torch.cuda.is_available():
            del tracker, session
            torch.cuda.empty_cache()
    return {"report": report, "run_dir": str(target), "status": report["status"], "aggregate": replay["aggregate"],
        "snapshot": replay["snapshot"], "run_id": replay["snapshot"]["run_id"], "video_id": video["video_id"],
        "source_identity": deepcopy(identity), "frames_processed": metadata["frame_count"], "scope": "full_video"}
