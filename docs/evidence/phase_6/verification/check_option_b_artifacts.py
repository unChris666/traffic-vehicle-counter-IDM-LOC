"""Independent read-only audit of retained Phase 6 Option B artifacts.

This script does not import or execute the counting/identity resolver, models,
tracker, encoder, geometry state machine, or video decoder. It independently
checks source values, episode partitions, association arithmetic, passage
evidence and snapshot reconciliation. Pixel checks read existing PNGs only.
It does not measure identity, tracking or counting accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess


VEHICLES = {"motorcycle", "car", "truck", "bus"}
SOURCE = "docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz"
GEOMETRY = "docs/evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json"
CALIBRATION = "docs/evidence/phase_6/option_b_calibration/frozen_thresholds.json"
A_ORIGINAL = "docs/evidence/phase_6/20261012T144625_030645Z"
A_UPDATED = "docs/evidence/phase_6/option_b_a_updated_20261013"
PIXELS = "docs/evidence/phase_6/option_b_temporal_review"
KEYS = ("track_id", "frame_index", "original_detection_index", "raw_bbox", "class_id", "class_name", "confidence", "measurement_provenance")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def hashed_id(prefix, value):
    return prefix + hashlib.sha256(canonical(value).encode()).hexdigest()


def read(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def bc(box):
    return [(box[0] + box[2]) / 2, box[3]]


def area_intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def family(label):
    return "vehicle" if label in VEHICLES else "person" if label == "person" else "other"


def cross(first, second):
    return first[0] * second[1] - first[1] * second[0]


def inside_polygon(point, polygon):
    """Independent ray predicate, excluding boundary contacts."""
    inside = False
    for first, second in zip(polygon, polygon[1:] + polygon[:1]):
        offset = [point[0] - first[0], point[1] - first[1]]
        edge = [second[0] - first[0], second[1] - first[1]]
        if abs(cross(offset, edge)) < 1e-9 and min(first[0], second[0]) <= point[0] <= max(first[0], second[0]) and min(first[1], second[1]) <= point[1] <= max(first[1], second[1]):
            return False
        if (first[1] > point[1]) != (second[1] > point[1]):
            intersection = first[0] + (point[1] - first[1]) * (second[0] - first[0]) / (second[1] - first[1])
            if point[0] < intersection: inside = not inside
    return inside


def proper_finite_intersection(first, second, line_first, line_second):
    trajectory = [second[0] - first[0], second[1] - first[1]]
    line = [line_second[0] - line_first[0], line_second[1] - line_first[1]]
    offset = [line_first[0] - first[0], line_first[1] - first[1]]
    determinant = cross(trajectory, line)
    if abs(determinant) < 1e-12: return None
    time = cross(offset, line) / determinant
    position = cross(offset, trajectory) / determinant
    if not (0 < time < 1 and 0 < position < 1): return None
    return [first[0] + time * trajectory[0], first[1] + time * trajectory[1]]


def feature_values(first, second, kind, windows):
    """Independent arithmetic, without calling the implementation helper."""
    a = {o["frame_index"]: o for o in first["observations"]}
    b = {o["frame_index"]: o for o in second["observations"]}
    common = sorted(frame for frame in a.keys() & b.keys() if windows is None or any(lo <= frame <= hi for lo, hi in windows))
    offsets, lengths, distances, ious, inside = [], [], [], [], []
    longest = streak = 0
    for index, frame in enumerate(common):
        x, y = a[frame]["raw_bbox"], b[frame]["raw_bbox"]
        cx, cy = [(x[0] + x[2]) / 2, (x[1] + x[3]) / 2], [(y[0] + y[2]) / 2, (y[1] + y[3]) / 2]
        diagonal_x, diagonal_y = math.hypot(x[2] - x[0], x[3] - x[1]), math.hypot(y[2] - y[0], y[3] - y[1])
        scale = diagonal_y if kind == "COMPONENT_OF" else (diagonal_x + diagonal_y) / 2
        offset = [cx[0] - cy[0], cx[1] - cy[1]]
        offsets.append(offset)
        lengths.append(scale)
        distances.append(math.hypot(*offset) / scale)
        intersection = area_intersection(x, y)
        ious.append(intersection / ((x[2] - x[0]) * (x[3] - x[1]) + (y[2] - y[0]) * (y[3] - y[1]) - intersection))
        point = bc(x)
        inside.append(y[0] <= point[0] <= y[2] and y[1] <= point[1] <= y[3])
        streak = streak + 1 if index and frame == common[index - 1] + 1 else 1
        longest = max(longest, streak)
    residuals = [math.dist(offsets[index], offsets[index - 1]) / ((lengths[index] + lengths[index - 1]) / 2)
                 for index in range(1, len(common)) if common[index] == common[index - 1] + 1]
    return {"kind": kind, "common_frame_indices": common, "common_frames": len(common),
            "consecutive_common_frames_max": longest, "first_bc_inside_second_fraction": sum(inside) / len(common) if common else None,
            "iou_min": min(ious) if common else None, "iou_max": max(ious) if common else None,
            "center_distance_norm_max": max(distances) if common else None,
            "relative_motion_residual_norm_max": max(residuals) if residuals else None,
            "consecutive_motion_pairs": len(residuals), "association_frame_windows": windows, "appearance_features_used": False}


def equal_value(actual, expected):
    if isinstance(actual, (float, int)) and not isinstance(actual, bool) and isinstance(expected, (float, int)) and not isinstance(expected, bool):
        return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(equal_value(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(equal_value(a, b) for a, b in zip(actual, expected))
    return actual == expected


def control_passes(features, controls, kind):
    common = features["common_frames"] >= controls["min_common_frames"]
    consecutive = features["consecutive_common_frames_max"] >= controls["min_consecutive_common_frames"]
    residual = features["relative_motion_residual_norm_max"]
    distance = features["center_distance_norm_max"]
    general = common and consecutive and residual is not None and residual <= controls["max_relative_motion_residual_norm"] and distance is not None and distance <= controls["max_center_distance_norm"]
    specific = (features["first_bc_inside_second_fraction"] is not None and features["first_bc_inside_second_fraction"] >= controls["min_first_bc_inside_second_fraction"]
                if kind == "COMPONENT_OF" else features["iou_min"] is not None and features["iou_min"] >= controls["min_iou"])
    return general and specific


def audit_reviewed(repo, run_dir, check, config, measured, episodes, decisions, machine_events, pixel_index):
    """Audit a fresh reviewed snapshot without executing its postprocessor."""
    directory = run_dir / "reviewed"
    if not directory.is_dir():
        return {"audited": False, "reason": "Reviewed overlay not retained at audit time."}, []
    review = read(directory / "review_input.json")
    report = read(directory / "report.json")
    manifest = read(directory / "execution_manifest.json")
    for artifact in manifest["artifacts"]:
        path = directory / artifact["path"]
        check("reviewed_manifest_bytes:" + artifact["path"], path.is_file() and path.stat().st_size == artifact["size_bytes"] and sha(path) == artifact["sha256"])
    identity = config["input_identity"]
    check("reviewed_input_run_and_source_binding", review["source_run_id"] == run_dir.name == report["source_run_id"] == manifest["source_run_id"] and review["source_identity"] == identity == report["source_identity"] and review["source_machine_decisions_sha256"] == sha(run_dir / "machine_decisions.jsonl.gz"))
    input_path = repo / report["review_input_path"]
    check("reviewed_original_input_exact_copy", input_path.is_file() and input_path.read_bytes() == (directory / "review_input.json").read_bytes() and report["review_input_sha256"] == sha(input_path))
    method = repo / "docs/evidence/phase_6/option_b_verification/build_reviewed_comparison.py"
    check("reviewed_executed_method_binding", report["method_sha256"] == manifest["method_sha256"] == sha(method))
    for name, digest in report["source_artifact_sha256"].items():
        check("reviewed_machine_source_immutable:" + name, sha(run_dir / name) == digest == manifest["source_artifact_sha256"][name])
    check("reviewed_explicit_nonautomatic_nontruth_semantics", report["original_machine_artifacts_modified"] is False and report["model_geometry_resolver_rerun"] is False and report["formal_ground_truth"] is False and report["whole_video_traffic_result"] is False and report["new_automatic_success_claimed"] is False and manifest["automatic_acceptance_claimed"] is False)
    reviewed = rows(directory / "resolved_decisions.jsonl.gz")
    events = rows(directory / "accepted_events.jsonl.gz")
    aggregate = read(directory / "aggregate.json")
    originals = {d["candidate_id"]: d for d in decisions}
    resolved = {d["candidate_id"]: d for d in reviewed}
    by_episode = {e["episode_id"]: e for e in episodes}
    review_rows = {r["candidate_id"]: r for r in review["decisions"]}
    check("reviewed_candidate_inventory_unchanged", len(resolved) == len(reviewed) == len(originals) and resolved.keys() == originals.keys())
    check("reviewed_input_exact_five_existing_rows", len(review_rows) == len(review["decisions"]) == 5 and set(review_rows) <= originals.keys() and {originals[c]["track_id"] for c in review_rows} == {1, 923, 964, 973, 1323})
    check("reviewed_typed_unique_accepted_only", all(e["type"] == "CountEvent" and e["status"] == "accepted" and e["accepted_count_event"] is True for e in events) and len({e["event_id"] for e in events}) == len(events))
    untouched = [e for e in machine_events if e["candidate_id"] not in review_rows]
    event_map = {e["event_id"]: e for e in events}
    check("reviewed_automatic1772_event_exact_payload_preserved", len(untouched) == 1 and untouched[0]["track_id"] == 1772 and all(event_map.get(e["event_id"]) == e for e in untouched))
    check("reviewed_unmodified_machine_decision1772", all(resolved[c] == originals[c] for c in originals.keys() - review_rows.keys()))
    check("reviewed_actual_four_physical_events", len(events) == aggregate["total"] == 4 and {e["track_id"] for e in events} == {1, 923, 964, 1772})
    check("reviewed_unique_physical_unit_passage", len({(e["physical_unit_id"], e["passage_id"]) for e in events}) == len(events))
    check("reviewed_aggregate_event_ids_exact", sorted(aggregate["event_ids"]) == sorted(event_map) and len(aggregate["event_ids"]) == len(events))
    for field, key in (("category", "by_category"), ("direction", "by_direction")):
        actual = Counter(e[field] for e in events)
        check("reviewed_aggregate_reconciles:" + field, sum(aggregate[key].values()) == len(events) and all(count == actual.get(label, 0) for label, count in aggregate[key].items()))
    check("reviewed_snapshot_decision_counts", Counter(d["status"] for d in reviewed) == {"accepted": 4, "duplicate_suppressed": 1, "pending_review": 1} and report["decision_status_counts"] == dict(Counter(d["status"] for d in reviewed)))
    check("reviewed_manual_auto_report_split", report["reviewed_candidates"] == 5 and report["manual_confirmation_candidates"] == 4 and report["manual_confirmed_physical_passages"] == 3 and report["preserved_machine_accepted_events"] == 1 and report["accepted_events"] == 4)

    # Derive actual photograph frame inventories from retained source indexes,
    # not from frame labels asserted in newly supplied review rows.
    photo_inventory = {}
    for case in pixel_index["cases"]:
        for kind, artifact in case["artifacts"].items():
            view = kind.rsplit("_", 1)[0]
            photo_inventory[artifact["path"]] = {"sha256": artifact["sha256"], "frames": {t["frame_index"] for t in case["views"][view]["tiles"]}}
    old_pixel_review = read(repo / "docs/evidence/phase_6/review_samples/TOR3-PAGI/pixel_review.json")
    old_index_path = repo / old_pixel_review["source_sample_index_path"]
    check("reviewed_original_photo_index_binding", sha(old_index_path) == old_pixel_review["source_sample_index_sha256"])
    old_index = read(old_index_path)
    check("reviewed_original_photo_source_identity", old_index["source_video_sha256"] == identity["video_sha256"] and old_index["records_sha256"] == identity["records_sha256"] and old_index["geometry_sha256"] == identity["geometry_sha256"])
    for case in old_index["cases"]:
        for artifact in case["artifacts"].values():
            photo_inventory[artifact["path"]] = {"sha256": artifact["sha256"], "frames": {t["frame_index"] for t in case["tiles"]}}
    allowed_reasons = {"NO_POSITIVE_PHYSICAL_IDENTITY_EVIDENCE", "RAW_UNRESOLVED_VEHICLE_COMPETITOR", "ALTERNATIVE_ASSIGNMENT_AMBIGUITY", "IDENTITY_RELATION_OUTSIDE_PASSAGE_WINDOW", "IDENTITY_SUPPORT_INSUFFICIENT_WITHIN_PASSAGE_WINDOW"}
    for candidate_id, row in review_rows.items():
        source, result = originals[candidate_id], resolved[candidate_id]
        check("reviewed_original_decision_preserved:" + candidate_id, result["original_machine_decision"] == source and result["review_decision"] == row and result["manual_review_applied"] is True and result["review_policy"] == "phase6_option_b_review_overlay_v1")
        check("reviewed_deterministic_review_id:" + candidate_id, result["review_id"] == hashed_id("rv6br_", {"source_identity": identity, "candidate_id": candidate_id, "review": row}))
        photo_frames = set()
        for ref in row["evidence"]:
            entry = photo_inventory.get(ref["path"])
            valid = entry is not None and sha(repo / ref["path"]) == ref["sha256"] == entry["sha256"] and set(ref["frame_indices"]) <= entry["frames"] and bool(ref["observation"])
            check("reviewed_photo_hash_and_actual_frame_inventory:" + candidate_id + ":" + ref["path"], valid)
            if valid: photo_frames.update(ref["frame_indices"])
        if row["disposition"] == "HOLD":
            check("reviewed_hold1323_categorycar_identity_unknown", source["track_id"] == 1323 and row["category"] == result["review_recorded_category"] == "car" and row["category_confirmed"] is True and row["identity_confirmed"] is False and result["status"] == "pending_review" and result["event_id"] is None and result["accepted_count_event"] is False and "EXPLICIT_REVIEW_HOLD" in result["reasons"] and not any(e["track_id"] == 1323 for e in events))
            continue
        diagnostic = source["diagnostic"]
        required = {diagnostic[k] for k in ("origin_frame", "crossing_frame_start", "crossing_frame_end", "confirmation_frame")}
        if diagnostic["crossing_evidence"]["method"] == "measured_touch_then_opposite_sign": required.update(range(diagnostic["crossing_frame_start"] + 1, diagnostic["crossing_frame_end"]))
        check("reviewed_positive_unit_category_identity:" + candidate_id, row["disposition"] == "CONFIRM_PASSAGE" and all(row[k] is True for k in ("unit_confirmed", "category_confirmed", "identity_confirmed")))
        check("reviewed_required_actual_photo_frames:" + candidate_id, required <= photo_frames, {"required_frames": sorted(required), "covered_actual_frames": sorted(photo_frames)})
        check("reviewed_association_only_blocks_resolved:" + candidate_id, (set(source["reasons"]) | set(source["hard_block_reasons"])) <= allowed_reasons and not result["reasons"] and not result["hard_block_reasons"] and source["status"] == "pending_review")
        check("reviewed_original_measurement_diagnostic_unchanged:" + candidate_id, result["diagnostic"] == source["diagnostic"] and result["measurement_support"] == source["measurement_support"] and result["category"] == source["category"] == row["category"] and result["episode_id"] == source["episode_id"])
        for track in row.get("manual_component_track_ids", []):
            check("reviewed_component_source_is_person_without_crossing_substitution:" + candidate_id + ":" + str(track), any((track, frame) in measured and measured[(track, frame)]["class_name"] == "person" for frame in range(diagnostic["origin_frame"], diagnostic["confirmation_frame"] + 1)) and all(o["track_id"] == source["track_id"] for o in result["measurement_support"]))

    native = read(repo / GEOMETRY)["rendered_native_pixels"]
    passage_audit = []
    manual = [e for e in events if e.get("manual_review_applied") is True]
    check("reviewed_three_explicit_manual_events", len(manual) == 3 and all(e["automatic_acceptance"] is False and e["event_id"].startswith("ce6br_") and e["is_causal_online_decision"] is False and e["appearance_features_used"] is False for e in manual))
    groups = defaultdict(list)
    for candidate_id, row in review_rows.items():
        if row["disposition"] == "CONFIRM_PASSAGE": groups[(row["physical_unit_id"], row["passage_id"])].append(originals[candidate_id])
    semantic_fields = ("policy_version", "metric", "neutral_band_px", "confirmation_observations", "grouping_enabled", "scope", "association", "episode_policy", "category_policy", "identity_policy", "identity_support_policy")
    policy_identity = hashed_id("cfg6br_", {"source_identity": identity, "source_policy": {k: config[k] for k in semantic_fields if k in config}, "review_overlay_policy": "phase6_option_b_review_overlay_v1"})
    check("reviewed_policy_identity_source_bound", report["source_policy_identity"] == policy_identity)
    for event in manual:
        members = groups[(event["physical_unit_id"], event["passage_id"])]
        expected_representative = min(members, key=lambda c: tuple(c["diagnostic"][k] for k in ("crossing_frame_start", "crossing_frame_end", "confirmation_frame", "origin_frame")) + (c["track_id"], c["candidate_id"]))
        source = originals[event["candidate_id"]]
        diagnostic = event["geometry_evidence"]
        check("reviewed_earliest_valid_vehicle_representative:" + event["event_id"], event["candidate_id"] == expected_representative["candidate_id"] and event["track_id"] == source["track_id"] and event["vehicle_measurement_episode_id"] == source["episode_id"] and diagnostic == source["diagnostic"] and event["measurement_support"] == source["measurement_support"])
        check("reviewed_all_same_passage_sources_retained:" + event["event_id"], set(event["same_passage_candidate_ids"]) == {c["candidate_id"] for c in members} and set(event["vehicle_episode_ids"]) == {c["episode_id"] for c in members} and len(event["source_episode_references"]) == len(members) and len(event["review_references"]) == len(members))
        expected_refs = [{"candidate_id": c["candidate_id"], "episode_id": c["episode_id"], "track_id": c["track_id"], **{k: c["diagnostic"][k] for k in ("origin_frame", "crossing_frame_start", "crossing_frame_end", "confirmation_frame")}} for c in sorted(members, key=lambda c: c["candidate_id"])]
        check("reviewed_source_episode_references_exact:" + event["event_id"], event["source_episode_references"] == expected_refs)
        check("reviewed_deterministic_manual_event_id:" + event["event_id"], event["policy_identity"] == policy_identity and event["event_id"] == hashed_id("ce6br_", {"source_identity": identity, "policy_identity": policy_identity, "physical_unit_id": event["physical_unit_id"], "passage_id": event["passage_id"]}))
        check("reviewed_group_members_share_one_count_authority:" + event["event_id"], all(resolved[c["candidate_id"]]["event_id"] == event["event_id"] and resolved[c["candidate_id"]]["accepted_count_event"] is (c["candidate_id"] == event["candidate_id"]) and resolved[c["candidate_id"]]["status"] == ("accepted" if c["candidate_id"] == event["candidate_id"] else "duplicate_suppressed") for c in members))
        diagnostic_points = [diagnostic["origin_observation"], diagnostic["crossing_evidence"]["start_observation"], diagnostic["crossing_evidence"]["end_observation"], *diagnostic["confirmation_observations"]]
        for value in diagnostic_points:
            observation = measured[(event["track_id"], value["frame_index"])]
            metadata = {"track_id": event["track_id"], "episode_id": event["vehicle_measurement_episode_id"], **{k: identity[k] for k in ("video_sha256", "records_sha256", "variant", "parent_run_id")}, **{k: observation[k] for k in ("original_detection_index", "raw_bbox", "class_id", "class_name", "confidence", "measurement_provenance")}}
            check("reviewed_geometry_observation_raw_source_metadata:" + event["event_id"] + ":" + str(value["frame_index"]), all(value["metadata"].get(k) == v for k, v in metadata.items()) and value["point"] == bc(observation["raw_bbox"]))
        check("reviewed_manual_source_identity_category_full_history:" + event["event_id"], event["source_identity"] == identity and {o["class_name"] for eid in event["vehicle_episode_ids"] for o in by_episode[eid]["observations"]} == {event["category"]} and event["direction"] == diagnostic["direction"])
        check("reviewed_full_raw_vehicle_only_support:" + event["event_id"], [o["frame_index"] for o in event["measurement_support"]] == list(range(diagnostic["origin_frame"], diagnostic["confirmation_frame"] + 1)) and all(o["class_name"] in VEHICLES and o["track_id"] == event["track_id"] and o["point"] == bc(o["raw_bbox"]) and all(o[k] == measured[(event["track_id"], o["frame_index"])][k] for k in KEYS) for o in event["measurement_support"]))
        first, second = (bc(measured[(event["track_id"], diagnostic[k])]["raw_bbox"]) for k in ("crossing_frame_start", "crossing_frame_end"))
        point = proper_finite_intersection(first, second, native["line"]["P1"], native["line"]["P2"])
        check("reviewed_independent_finite_measured_crossing:" + event["event_id"], point is not None and equal_value(point, diagnostic["crossing_point"]) and diagnostic["crossing_frame_end"] == diagnostic["crossing_frame_start"] + 1)
        first_roi = native["side_a_polygon"] if diagnostic["direction"] == "A_TO_B" else native["side_b_polygon"]
        second_roi = native["side_b_polygon"] if diagnostic["direction"] == "A_TO_B" else native["side_a_polygon"]
        origin = bc(measured[(event["track_id"], diagnostic["origin_frame"])]["raw_bbox"])
        confirm = bc(measured[(event["track_id"], diagnostic["confirmation_frame"])]["raw_bbox"])
        check("reviewed_independent_original_opposite_roi_interiors:" + event["event_id"], inside_polygon(origin, first_roi) and not inside_polygon(origin, second_roi) and inside_polygon(confirm, second_roi) and not inside_polygon(confirm, first_roi))
        for ref in event["review_references"]:
            check("reviewed_event_review_reference_exact:" + event["event_id"] + ":" + ref["candidate_id"], ref["review"] == review_rows[ref["candidate_id"]] and ref["review_id"] == resolved[ref["candidate_id"]]["review_id"])
        for ref in event["original_automatic_identity_evidence"]:
            check("reviewed_original_automatic_evidence_retained:" + event["event_id"] + ":" + ref["candidate_id"], ref["machine_decision"] == originals[ref["candidate_id"]])
        passage_audit.append({"event_id": event["event_id"], "vehicle_track_id": event["track_id"], "vehicle_member_track_ids": sorted(c["track_id"] for c in members), "manual_component_track_ids": sorted({t for c in members for t in review_rows[c["candidate_id"]].get("manual_component_track_ids", [])}), "origin_frame": diagnostic["origin_frame"], "crossing_frames": [diagnostic["crossing_frame_start"], diagnostic["crossing_frame_end"]], "confirmation_frame": diagnostic["confirmation_frame"], "raw_vehicle_only": True, "manual_review_applied": True, "automatic_acceptance": False, "claim_type": "INDEPENDENT_SOURCE_RECONCILIATION_OF_EXPLICIT_REVIEW_NOT_PHYSICAL_ACCURACY"})
    duplicate = [e for e in events if set(e.get("vehicle_episode_ids", [])) == {originals[c]["episode_id"] for c in originals if originals[c]["track_id"] in (964, 973)}]
    check("reviewed964973_one_motorcycle_count_correct_origin", len(duplicate) == 1 and duplicate[0]["track_id"] == 964 and duplicate[0]["category"] == "motorcycle" and duplicate[0]["geometry_evidence"]["origin_frame"] == 5122 and duplicate[0]["geometry_evidence"]["crossing_frame_start"] == 5128 and duplicate[0]["geometry_evidence"]["crossing_frame_end"] == duplicate[0]["geometry_evidence"]["confirmation_frame"] == 5129)
    suppressed = [d for d in reviewed if d["track_id"] == 973]
    check("reviewed973_source_suppressed_excluded_from_subtotal", len(suppressed) == 1 and suppressed[0]["status"] == "duplicate_suppressed" and suppressed[0]["accepted_count_event"] is False and suppressed[0]["event_id"] == duplicate[0]["event_id"] and not any(e["track_id"] == 973 for e in events))
    clean = by_episode[duplicate[0]["vehicle_measurement_episode_id"]]
    check("reviewed964_prior_person_not_inherited", clean["family"] == "vehicle" and all(o["class_name"] == "motorcycle" for o in clean["observations"]) and any(o["class_name"] == "person" and o["frame_index"] == 5116 for o in clean["excluded_preceding_observations"]))
    return {"audited": True, "accepted_events": len(events), "manual_events": len(manual), "preserved_automatic_events": len(untouched), "pending_items": sum(d["status"] == "pending_review" for d in reviewed), "duplicate_suppressed_items": sum(d["status"] == "duplicate_suppressed" for d in reviewed)}, passage_audit


def audit(repo, run_dir, require_reviewed=False):
    checks = []
    def check(name, passed, details=None):
        checks.append({"check": name, "passed": bool(passed), "details": details})
    def manifest(directory):
        document = read(directory / "execution_manifest.json")
        for artifact in document["artifacts"]:
            path = directory / artifact["path"]
            check("manifest_bytes:" + str(path.relative_to(repo)), path.is_file() and path.stat().st_size == artifact["size_bytes"] and sha(path) == artifact["sha256"])
        return document
    config = read(run_dir / "configuration_input.json")
    identity = config["input_identity"]
    expected_identity = {key: identity[key] for key in ("video_sha256", "records_sha256", "geometry_sha256", "variant", "width", "height", "parent_run_id")}
    check("actual_source_cache_sha256", sha(repo / SOURCE) == identity["records_sha256"])
    check("actual_geometry_sha256", sha(repo / GEOMETRY) == identity["geometry_sha256"])
    check("accepted_geometry_video_identity", read(repo / GEOMETRY)["source_video"]["sha256"] == identity["video_sha256"])
    calibration = read(repo / CALIBRATION)
    check("frozen_calibration_bytes", sha(repo / CALIBRATION) == config["calibration_evidence_sha256"])
    check("association_controls_not_retuned", config["association"] == calibration["thresholds"])
    check("held_out_excluded_numeric_bounds", calibration["excluded_from_bounds"]["held_out_component_pair"] == [1772, 1774])
    check("v1_explicit_policy", config["policy_version"] == "phase6_option_b_v1")
    check("geometry_experimental_control_unchanged", config["neutral_band_px"] == 0 and config["confirmation_observations"] == 1)
    report = read(run_dir / "report.json")
    manifest(run_dir)
    source_code = read(run_dir / "source_code_sha256.json")
    archived_sources = {"identity_resolution_helper": "phase_6_identity_resolution_helpers.executed_source.py.gz",
                        "identity_resolution_tests": "phase_6_identity_resolution_tests.executed_source.py.gz",
                        "repository_notebook_source": "06b_identity_resolution_comparison.original_source.ipynb.gz"}
    for name, filename in archived_sources.items():
        actual = hashlib.sha256(gzip.decompress((run_dir / filename).read_bytes())).hexdigest()
        check("executed_source_archive:" + name, actual == source_code[name])
    for name, filename in (("geometry_helper", "phase_5_geometry_helpers.py"), ("counting_validation_helper", "phase_6_counting_helpers.py"),
                           ("identity_resolution_helper", "phase_6_identity_resolution_helpers.py"), ("identity_resolution_tests", "phase_6_identity_resolution_tests.py")):
        check("current_source_matches_run:" + name, sha(repo / "notebooks" / filename) == source_code[name])
    tests = read(run_dir / "synthetic_test_results.json")
    check("actual_notebook_synthetic_guard", tests["successful"] and tests["tests_run"] == 63 and tests["tests_passed"] == 63 and not tests["failures"] and not tests["errors"])
    check("no_model_encoder_or_video_decoder", not report["runtime"]["detector_tracker_encoder_rerun"] and not report["runtime"]["video_decode_executed"] and not report["manual_feedback_applied_to_B_machine"])
    check("no_appearance_fabrication", not report["runtime"]["appearance_vectors_available_or_used"])
    check("no_ground_truth_or_accuracy_claim", report["formal_ground_truth_available"] is False and report["whole_video_physical_audit_complete"] is False and report["selected_suitable_product_parameters"] is None)
    episodes = rows(run_dir / "episodes.jsonl.gz")
    decisions = rows(run_dir / "machine_decisions.jsonl.gz")
    relations = rows(run_dir / "relations.jsonl.gz")
    events = rows(run_dir / "accepted_events.jsonl.gz")
    derived = rows(run_dir / "derived_diagnostics.jsonl.gz")
    by_id = {e["episode_id"]: e for e in episodes}
    needed_frames = {frame for lo, hi in config["scope"]["association_frame_windows"] for frame in range(lo, hi + 1)}
    for decision in decisions:
        d = decision["diagnostic"]
        if d["type"] == "GEOMETRY_TRANSITION":
            needed_frames.update(range(d["origin_frame"], d["confirmation_frame"] + 1))
    pixel_index = read(repo / PIXELS / "sample_index.json")
    needed_frames.update(frame for case in pixel_index["cases"] for frame in case["frames"])
    selected = set(config["scope"]["track_ids"])
    measured, context, source_rows = {}, {}, 0
    all_links_valid, source_context_valid, frame_order_valid, previous = True, True, True, None
    observation_count = 0
    with gzip.open(repo / SOURCE, "rt", encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            frame = record["frame_index"]
            source_rows += 1
            frame_order_valid &= previous is None or frame == previous + 1
            previous = frame
            source_context_valid &= all(record[key] == identity[key] for key in ("video_sha256", "variant", "parent_run_id", "width", "height"))
            seen_tracks, seen_indices = set(), set()
            for observation in record["emitted_tracks"]:
                observation_count += 1
                index = observation["original_detection_index"]
                track = observation["track_id"]
                valid = observation["frame_index"] == frame and observation.get("emitted") is True and observation.get("measurement_provenance") == "retained_phase_2_detection"
                valid &= track not in seen_tracks and index not in seen_indices and 0 <= index < len(record["raw_detections"])
                if 0 <= index < len(record["raw_detections"]):
                    raw = record["raw_detections"][index]
                    valid &= observation["raw_bbox"] == raw["bbox_xyxy_pixels"] and all(observation[k] == raw[k] for k in ("class_id", "class_name", "confidence"))
                all_links_valid &= valid
                seen_tracks.add(track); seen_indices.add(index)
                if track in selected:
                    measured[(track, frame)] = deepcopy(observation)
            if frame in needed_frames:
                context[frame] = record
    check("all_cache_frames_ordered_continuous", frame_order_valid and source_rows == 10282, {"frames": source_rows})
    check("all_cache_context_identity", source_context_valid)
    check("all_emitted_raw_source_links", all_links_valid, {"observations": observation_count})
    check("all_required_raw_frames_available", needed_frames <= context.keys())
    check("declared_scope_complete_source_partition", len({(e["track_id"], o["frame_index"]) for e in episodes for o in e["observations"]}) == len(measured))
    expected_chunks = defaultdict(list)
    histories = defaultdict(list)
    for (track, frame), observation in sorted(measured.items()):
        histories[track].append(observation)
    for track, observations in histories.items():
        chunks, chunk, previous = [], [], None
        for observation in observations:
            if previous and (family(observation["class_name"]) != family(previous["class_name"]) or observation["frame_index"] != previous["frame_index"] + 1):
                chunks.append(chunk); chunk = []
            chunk.append(observation); previous = observation
        if chunk: chunks.append(chunk)
        expected_chunks[track] = chunks
    for track, chunks in expected_chunks.items():
        actual = sorted([e for e in episodes if e["track_id"] == track], key=lambda e: e["start_frame"])
        check("full_family_gap_partition:" + str(track), [[o["frame_index"] for o in e["observations"]] for e in actual] == [[o["frame_index"] for o in chunk] for chunk in chunks])
        preceding = []
        for episode in actual:
            observations = episode["observations"]
            check("episode_raw_values:" + episode["episode_id"], all(all(o[k] == measured[(track, o["frame_index"])][k] for k in KEYS) and o["point"] == bc(o["raw_bbox"]) for o in observations))
            check("episode_unit_family:" + episode["episode_id"], all(family(o["class_name"]) == episode["family"] for o in observations))
            check("episode_preceding_provenance:" + episode["episode_id"], [{k: o[k] for k in KEYS} for o in episode["excluded_preceding_observations"]] == [{k: o[k] for k in KEYS} for o in preceding])
            expected = hashed_id("ve6b_", {"source_identity": expected_identity, "track_id": track, "first_frame": observations[0]["frame_index"], "last_frame": observations[-1]["frame_index"], "family": episode["family"]})
            check("episode_deterministic_id:" + episode["episode_id"], expected == episode["episode_id"])
            preceding.extend(observations)
    for relation in relations:
        expected = feature_values(by_id[relation["first_episode_id"]], by_id[relation["second_episode_id"]], relation["type"], config["scope"]["association_frame_windows"])
        check("independent_relation_arithmetic:" + relation["relation_id"], equal_value(relation["features"], expected))
        kind = "component" if relation["type"] == "COMPONENT_OF" else "same_vehicle"
        check("relation_frozen_controls:" + relation["relation_id"], relation["thresholds"] == config["association"][kind])
        if relation["status"] == "SUPPORTED":
            check("supported_relation_passes_controls:" + relation["relation_id"], control_passes(expected, relation["thresholds"], relation["type"]))
    relation_map = {r["relation_id"]: r for r in relations}
    for decision in decisions:
        d = decision["diagnostic"]
        if d["type"] != "GEOMETRY_TRANSITION":
            check("ambiguous_not_accepted:" + decision["candidate_id"], decision["status"] != "accepted")
            continue
        start, end = d["origin_frame"], d["confirmation_frame"]
        support = decision["measurement_support"]
        check("candidate_complete_raw_vehicle_support:" + decision["candidate_id"], [o["frame_index"] for o in support] == list(range(start, end + 1)) and all(o["class_name"] in VEHICLES and o["point"] == bc(o["raw_bbox"]) and all(o[k] == measured[(decision["track_id"], o["frame_index"])][k] for k in KEYS) for o in support))
        for evidence in decision["passage_identity_relation_evidence"]:
            relation = relation_map[evidence["relation_id"]]
            expected = feature_values(by_id[relation["first_episode_id"]], by_id[relation["second_episode_id"]], relation["type"], evidence["evaluated_frame_windows"])
            check("passage_local_identity_arithmetic:" + decision["candidate_id"] + ":" + evidence["relation_id"], equal_value(expected, evidence["features"]) and all(start <= frame <= end for frame in expected["common_frame_indices"]))
            if evidence["status"] == "SUPPORTED":
                check("local_identity_passes_frozen_controls:" + decision["candidate_id"] + ":" + evidence["relation_id"], control_passes(expected, evidence["thresholds"], evidence["type"]))
        owned_episodes = set(decision["vehicle_episode_ids"]) | set(decision["component_episode_ids"])
        expected_competitors = []
        for frame in range(start, end + 1):
            linked = [o for ep in owned_episodes for o in by_id[ep]["observations"] if o["frame_index"] == frame]
            owned_indices = {o["original_detection_index"] for o in linked}
            for index, raw in enumerate(context[frame]["raw_detections"]):
                if index in owned_indices or raw["class_name"] not in VEHICLES: continue
                box = raw["bbox_xyxy_pixels"]
                possible = any(area_intersection(o["raw_bbox"], box) > 0 or o["class_name"] == "person" and box[0] <= bc(o["raw_bbox"])[0] <= box[2] and box[1] <= bc(o["raw_bbox"])[1] <= box[3] for o in linked)
                if possible:
                    expected_competitors.append({"frame_index": frame, "original_detection_index": index, "class_name": raw["class_name"], "raw_bbox": box,
                        "emitted_track_ids": sorted(o["track_id"] for o in context[frame]["emitted_tracks"] if o["original_detection_index"] == index)})
        check("all_raw_competitors_including_unemitted:" + decision["candidate_id"], expected_competitors == decision["raw_competitor_evidence"], {"competitor_rows": len(expected_competitors), "unemitted_rows": sum(not x["emitted_track_ids"] for x in expected_competitors)})
        if decision["status"] == "accepted":
            check("accepted_candidate_has_no_unresolved_blocks:" + decision["candidate_id"], not decision["reasons"] and not decision["hard_block_reasons"] and not expected_competitors and bool(decision["identity_relation_ids"]))
    aggregate = read(run_dir / "aggregate.json")
    check("typed_unique_accepted_events", all(e["type"] == "CountEvent" and e["status"] == "accepted" and e["accepted_count_event"] is True for e in events) and len({e["event_id"] for e in events}) == len(events))
    check("machine_actual_one_held_out_motorcycle", len(events) == 1 and events[0]["track_id"] == 1772 and events[0]["category"] == "motorcycle")
    check("aggregate_event_total", aggregate["total"] == len(events) and sorted(aggregate["event_ids"]) == sorted(e["event_id"] for e in events))
    for field, key in (("category", "by_category"), ("direction", "by_direction")):
        actual = Counter(e[field] for e in events)
        check("aggregate_reconciles:" + field, all(count == actual.get(label, 0) for label, count in aggregate[key].items()) and sum(aggregate[key].values()) == len(events))
    decision_map = {d["candidate_id"]: d for d in decisions}
    passage_audit = []
    for event in events:
        decision = decision_map[event["candidate_id"]]
        d = event["geometry_evidence"]
        episode = by_id[event["vehicle_measurement_episode_id"]]
        check("event_exact_measured_candidate:" + event["event_id"], event["measurement_support"] == decision["measurement_support"] and d == decision["diagnostic"])
        check("event_no_person_bc:" + event["event_id"], all(o["class_name"] == "motorcycle" and o["point"] == bc(o["raw_bbox"]) for o in event["measurement_support"]))
        check("event_identity_inside_passage:" + event["event_id"], event["identity_decision_evidence_frame_indices"] == list(range(7716, 7723)) and event["identity_decision_latest_evidence_frame"] <= d["confirmation_frame"])
        check("event_reset_person_origin_excluded:" + event["event_id"], episode["start_frame"] == 7713 and d["origin_frame"] == 7716 and any(o["frame_index"] == 7712 and o["class_name"] == "person" for o in episode["excluded_preceding_observations"]))
        check("event_new_geometry_and_immutable_source_flag:" + event["event_id"], d["crossing_frame_start"] == 7721 and d["crossing_frame_end"] == d["confirmation_frame"] == 7722 and d["direction"] == "B_TO_A" and d["accepted_count_event"] is False)
        check("event_explicit_offline_category_evidence:" + event["event_id"], event["is_causal_online_decision"] is False and event["category_decision_latest_evidence_frame"] == episode["end_frame"])
        check("event_one_component_person:" + event["event_id"], len(event["component_episode_ids"]) == 1 and by_id[event["component_episode_ids"][0]]["track_id"] == 1774 and all(by_id[x]["family"] == "vehicle" for x in event["vehicle_episode_ids"]))
        check("event_whole_vehicle_episode_category_consistent:" + event["event_id"], {o["class_name"] for eid in event["vehicle_episode_ids"] for o in by_id[eid]["observations"]} == {event["category"]})
        native_geometry = read(repo / GEOMETRY)["rendered_native_pixels"]
        first_point = bc(measured[(event["track_id"], d["crossing_frame_start"])]["raw_bbox"])
        second_point = bc(measured[(event["track_id"], d["crossing_frame_end"])]["raw_bbox"])
        independent_intersection = proper_finite_intersection(first_point, second_point, native_geometry["line"]["P1"], native_geometry["line"]["P2"])
        check("independent_finite_measured_crossing:" + event["event_id"], independent_intersection is not None and equal_value(independent_intersection, d["crossing_point"]) and d["crossing_frame_end"] == d["crossing_frame_start"] + 1)
        origin_point = bc(measured[(event["track_id"], d["origin_frame"])]["raw_bbox"])
        confirmation_point = bc(measured[(event["track_id"], d["confirmation_frame"])]["raw_bbox"])
        check("independent_origin_arrival_roi_interiors:" + event["event_id"], inside_polygon(origin_point, native_geometry["side_b_polygon"]) and not inside_polygon(origin_point, native_geometry["side_a_polygon"]) and inside_polygon(confirmation_point, native_geometry["side_a_polygon"]) and not inside_polygon(confirmation_point, native_geometry["side_b_polygon"]))
        passage_audit.append({"event_id": event["event_id"], "vehicle_track_id": event["track_id"], "component_track_ids": [by_id[x]["track_id"] for x in event["component_episode_ids"]], "origin_frame": d["origin_frame"], "crossing_frames": [d["crossing_frame_start"], d["crossing_frame_end"]], "confirmation_frame": d["confirmation_frame"], "identity_evidence_frames": event["identity_decision_evidence_frame_indices"], "category_latest_evidence_frame": event["category_decision_latest_evidence_frame"], "raw_vehicle_only": True, "claim_type": "INDEPENDENT_SOURCE_AND_ARTIFACT_RECONCILIATION_NOT_PHYSICAL_ACCURACY"})
    negative = [r for r in relations if r["type"] == "SAME_VEHICLE" and {r["first_track_id"], r["second_track_id"]} == {880, 892}]
    check("pixel_reviewed_negative_880_892_not_merged", negative and all(r["status"] == "REJECTED" for r in negative))
    duplicate = [r for r in relations if r["type"] == "SAME_VEHICLE" and {r["first_track_id"], r["second_track_id"]} == {964, 973}]
    check("known_duplicate_not_auto_claimed_resolved", len(duplicate) == 1 and duplicate[0]["status"] == "REJECTED" and duplicate[0]["features"]["relative_motion_residual_norm_max"] > duplicate[0]["thresholds"]["max_relative_motion_residual_norm"])
    check("unresolved_duplicate_candidates_excluded", all(d["status"] == "pending_review" for d in decisions if d["track_id"] in (964, 973)) and not any(e["track_id"] in (964, 973) for e in events))
    check("923_future_only_identity_no_promotion", any(d["track_id"] == 923 and d["status"] == "pending_review" and "IDENTITY_RELATION_OUTSIDE_PASSAGE_WINDOW" in d["reasons"] for d in decisions) and not any(e["track_id"] == 923 for e in events))
    ablation = run_dir / "ablation"
    check("episode_only_ablation_no_events", not rows(ablation / "accepted_events.jsonl.gz") and read(ablation / "aggregate.json")["total"] == 0 and len(rows(ablation / "machine_decisions.jsonl.gz")) == 6)
    check("ablation_geometry_not_changed", rows(ablation / "derived_diagnostics.jsonl.gz") == derived)
    for label, directory in (("A_original", repo / A_ORIGINAL), ("A_updated", repo / A_UPDATED)):
        manifest(directory)
        a_events = rows(directory / "accepted_events.jsonl.gz")
        a_decisions = rows(directory / "resolved_decisions.jsonl.gz")
        a_aggregate = read(directory / "aggregate.json")
        check(label + "_actual_snapshot_18_141_7", len(a_events) == a_aggregate["total"] == 18 and Counter(d["status"] for d in a_decisions) == {"accepted": 18, "pending_review": 141, "rejected": 7})
        if label == "A_updated":
            check("A_updated_reviews_actual_28", len(read(directory / "review_input.json")["decisions"]) == 28)
            check("A_updated_1772_old_mixed_history_not_promoted", any(d["track_id"] == 1772 and d["status"] == "pending_review" and "UNIT_COMPONENT_CHANGE" in d["hard_block_reasons"] for d in a_decisions))
            check("A_updated_user_category1323_kept_pending_identity", any(d["track_id"] == 1323 and d["status"] == "pending_review" and d["review"]["category"] == "car" and d["review"]["category_confirmed"] is True and d["review"]["identity_confirmed"] is False for d in a_decisions))
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", A_ORIGINAL], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    check("historical_A_original_tracked_bytes_immutable", not changed, changed or None)
    check("pixel_review_source_identity", all(pixel_index[key] == identity[field] for key, field in (("source_video_sha256", "video_sha256"), ("records_sha256", "records_sha256"), ("geometry_sha256", "geometry_sha256"))))
    from PIL import Image
    import numpy as np
    for case in pixel_index["cases"]:
        for artifact in case["artifacts"].values():
            check("retained_pixel_artifact:" + artifact["path"], sha(repo / artifact["path"]) == artifact["sha256"] and (repo / artifact["path"]).stat().st_size == artifact["size_bytes"])
        for view, details in case["views"].items():
            artifact_key = view + "_raw"
            image = Image.open(repo / case["artifacts"][artifact_key]["path"]).convert("RGB")
            for tile in details["tiles"]:
                box = tile["native_crop_xyxy"]; origin = tile["sheet_image_origin_xy"]
                width, height = box[2] - box[0], box[3] - box[1]
                values = np.ascontiguousarray(np.array(image.crop((origin[0], origin[1], origin[0] + width, origin[1] + height)))[:, :, ::-1])
                check("raw_contact_tile_exact_pixels:" + case["case_id"] + ":" + view + ":" + str(tile["frame_index"]), hashlib.sha256(values.tobytes()).hexdigest() == tile["crop_bgr_uint8_sha256"])
                check("pixel_tile_source_measurements:" + case["case_id"] + ":" + view + ":" + str(tile["frame_index"]), all(all(o[k] == measured[(o["track_id"], o["frame_index"])][k] for k in KEYS) for o in tile["emitted_measurements"]))
    reviewed_result, reviewed_passages = audit_reviewed(repo, run_dir, check, config, measured, episodes, decisions, events, pixel_index)
    if require_reviewed:
        check("reviewed_overlay_required_and_present", reviewed_result["audited"])
    failed = [c for c in checks if not c["passed"]]
    output = {"claim_type": "ACTUALLY_EXECUTED_INDEPENDENT_READ_ONLY_ARTIFACT_SOURCE_AUDIT_NOT_ACCURACY", "run_id": run_dir.name,
              "auditor": "INDEPENDENT_CODEX_AGENT", "method_path": str(Path(__file__).resolve().relative_to(repo)), "method_sha256": sha(__file__),
              "pipeline_rerun": False, "video_decoder_executed": False, "source_cache_frames_read": source_rows,
              "source_cache_emitted_links_checked": observation_count, "selected_source_measurements_checked": len(measured),
              "checks_passed": len(checks) - len(failed), "checks_failed": len(failed), "successful": not failed,
              "machine_accepted_event_count": len(events), "reviewed_overlay": reviewed_result, "checks": checks,
              "limitations": ["Artifact consistency does not establish physical identity or counting accuracy.", "Pixel source hashes verify retained evidence; interpretation is separately recorded in bounded pixel review.", "No whole-video physical audit, held-out duplicate positive, or generalization claim.", "Reviewed acceptance is an explicit photo-supported manual overlay, not additional automatic resolver success." if reviewed_result["audited"] else "Manual B_reviewed overlay is not audited by this machine-artifact pass."]}
    return output, {"claim_type": "INDEPENDENT_MEASURED_SOURCE_PASSAGE_AUDIT_NOT_GROUND_TRUTH", "input_identity": expected_identity, "passages": passage_audit, "reviewed_overlay": reviewed_result, "manual_reviewed_passages": reviewed_passages}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--require-reviewed", action="store_true")
    args = parser.parse_args()
    root = args.repo.resolve()
    directory = args.run_dir.resolve()
    result, source_audit = audit(root, directory, args.require_reviewed)
    (directory / "independent_artifact_audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (directory / "source_identity_and_passage_audit.json").write_text(json.dumps(source_audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("successful", "checks_passed", "checks_failed", "source_cache_frames_read", "source_cache_emitted_links_checked", "machine_accepted_event_count")}, indent=2))
    if not result["successful"]:
        print(json.dumps([check for check in result["checks"] if not check["passed"]], indent=2))
    raise SystemExit(0 if result["successful"] else 1)
