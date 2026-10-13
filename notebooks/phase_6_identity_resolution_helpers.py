"""Inspectable Phase 6 Option B experiment on retained measured tracks.

This resolver is deliberately conservative. Relations are evidence, not a
trajectory repair. Every geometry point is the BC of one original vehicle
detection; no person point, merged box, interpolation or appearance feature is
invented. Numeric association controls are mandatory experimental inputs.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
import math
from numbers import Real
from pathlib import Path

from phase_5_geometry_helpers import Geometry, GeometryStateMachine, segment_intersection


POLICY_VERSION = "phase6_option_b_v1"
VEHICLE_LABELS = frozenset(("motorcycle", "car", "truck", "bus"))
CATEGORIES = ("pedestrian", "motorcycle", "car", "truck", "bus_angkot")
IDENTITY_FIELDS = ("video_sha256", "records_sha256", "geometry_sha256", "variant",
                   "width", "height", "parent_run_id")
COMPONENT_KEYS = ("min_common_frames", "min_consecutive_common_frames",
                  "min_first_bc_inside_second_fraction", "max_center_distance_norm",
                  "max_relative_motion_residual_norm")
DUPLICATE_KEYS = ("min_common_frames", "min_consecutive_common_frames", "min_iou",
                  "max_center_distance_norm", "max_relative_motion_residual_norm")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def _id(prefix, value):
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _int(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be integer >= {minimum}")
    return value


def _num(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric")
    return float(value)


def _box(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("raw_bbox must be four xyxy coordinates")
    box = [_num(v, "bbox coordinate") for v in value]
    if box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError("raw bbox must have positive width/height")
    return box


def _family(label):
    return "vehicle" if label in VEHICLE_LABELS else "person" if label == "person" else "other"


def _center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _bc(box):
    return [(box[0] + box[2]) / 2, box[3]]


def _diag(box):
    return math.hypot(box[2] - box[0], box[3] - box[1])


def _intersection_area(first, second):
    return max(0.0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0.0, min(first[3], second[3]) - max(first[1], second[1]))


def _validate_measurement(value):
    item = deepcopy(value)
    _int(item.get("track_id"), "track_id", 1)
    _int(item.get("frame_index"), "frame_index")
    _int(item.get("original_detection_index"), "original_detection_index")
    _int(item.get("class_id"), "class_id")
    if not isinstance(item.get("class_name"), str) or not item["class_name"].strip():
        raise ValueError("class_name must be nonempty")
    _num(item.get("confidence"), "confidence")
    if item.get("measurement_provenance") != "retained_phase_2_detection":
        raise ValueError("Only retained measured source detections are supported")
    item["raw_bbox"] = _box(item.get("raw_bbox"))
    # Input point/center is never trusted as the geometry anchor.
    item["point"] = _bc(item["raw_bbox"])
    timestamp = item.get("timestamp_estimate_from_index_fps_seconds")
    if timestamp is not None:
        _num(timestamp, "estimated timestamp")
    return item


def extract_episodes(measurements, *, source_identity):
    """Split EVERY track at a family change or missing measured frame.

    Vehicle-class changes remain in an episode and cause a category conflict.
    Every excluded earlier observation is retained as provenance. This is not
    choosing an origin retrospectively to obtain a desired crossing.
    """
    tracks = defaultdict(list)
    seen = set()
    for value in measurements:
        item = _validate_measurement(value)
        key = (item["track_id"], item["frame_index"])
        if key in seen:
            raise ValueError("Duplicate measured track/frame")
        seen.add(key)
        tracks[item["track_id"]].append(item)
    episodes = []
    for track_id in sorted(tracks):
        history = sorted(tracks[track_id], key=lambda o: o["frame_index"])
        chunks, chunk, reasons = [], [], []
        previous = None
        for item in history:
            changed = previous is not None and _family(item["class_name"]) != _family(previous["class_name"])
            gap = previous is not None and item["frame_index"] != previous["frame_index"] + 1
            if previous is None or changed or gap:
                if chunk:
                    chunks.append(chunk)
                chunk = []
                reasons.append("INITIAL_OBSERVATION" if previous is None else
                               "FAMILY_CHANGE_AND_GAP" if changed and gap else
                               "FAMILY_CHANGE" if changed else "MEASUREMENT_GAP")
            chunk.append(item)
            previous = item
        if chunk:
            chunks.append(chunk)
        preceding = []
        for index, observations in enumerate(chunks):
            family = _family(observations[0]["class_name"])
            episode_id = _id("ve6b_", {"source_identity": source_identity, "track_id": track_id,
                                     "first_frame": observations[0]["frame_index"],
                                     "last_frame": observations[-1]["frame_index"], "family": family})
            episodes.append({"episode_id": episode_id, "track_id": track_id, "family": family,
                             "start_frame": observations[0]["frame_index"],
                             "end_frame": observations[-1]["frame_index"],
                             "boundary_reason": reasons[index], "episode_sequence": index + 1,
                             "observations": deepcopy(observations),
                             "excluded_preceding_observations": deepcopy(preceding),
                             "source_identity": deepcopy(source_identity)})
            preceding.extend(observations)
    return sorted(episodes, key=lambda e: (e["track_id"], e["start_frame"], e["episode_id"]))


def pair_features(first_episode, second_episode, *, kind="COMPONENT_OF", frame_windows=None):
    """Expose raw-measurement spatial/temporal/motion evidence, with no defaults.

    COMPONENT_OF is ordered person -> motorcycle. SAME_VEHICLE normalizes by
    the mean of the two bbox diagonals and is symmetric. Relative motion is
    the change in unnormalized centre offset over consecutive common frames,
    divided by the mean corresponding normalization lengths. Nonconsecutive
    frames never supply motion evidence.
    """
    if kind not in ("COMPONENT_OF", "SAME_VEHICLE"):
        raise ValueError("Unsupported relation kind")
    first = {o["frame_index"]: o for o in first_episode["observations"]}
    second = {o["frame_index"]: o for o in second_episode["observations"]}
    frames = sorted(frame for frame in set(first) & set(second)
                    if frame_windows is None or any(start <= frame <= end for start, end in frame_windows))
    distances, ious, offsets, lengths, foot_inside = [], [], [], [], []
    run = longest = 0
    previous = None
    for frame in frames:
        a, b = _box(first[frame]["raw_bbox"]), _box(second[frame]["raw_bbox"])
        center_a, center_b = _center(a), _center(b)
        length = (_diag(a) + _diag(b)) / 2 if kind == "SAME_VEHICLE" else _diag(b)
        offset = (center_a[0] - center_b[0], center_a[1] - center_b[1])
        distances.append(math.hypot(*offset) / length)
        offsets.append(offset)
        lengths.append(length)
        intersection = _intersection_area(a, b)
        area_a, area_b = (a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])
        ious.append(intersection / (area_a + area_b - intersection))
        foot = _bc(a)
        foot_inside.append(b[0] <= foot[0] <= b[2] and b[1] <= foot[1] <= b[3])
        run = run + 1 if previous is not None and frame == previous + 1 else 1
        longest = max(longest, run)
        previous = frame
    residuals = [math.hypot(offsets[i][0] - offsets[i - 1][0], offsets[i][1] - offsets[i - 1][1]) /
                 ((lengths[i] + lengths[i - 1]) / 2)
                 for i in range(1, len(frames)) if frames[i] == frames[i - 1] + 1]
    return {"kind": kind, "common_frame_indices": frames, "common_frames": len(frames),
            "consecutive_common_frames_max": longest,
            "first_bc_inside_second_fraction": sum(foot_inside) / len(frames) if frames else None,
            "iou_min": min(ious) if ious else None, "iou_max": max(ious) if ious else None,
            "center_distance_norm_max": max(distances) if distances else None,
            "relative_motion_residual_norm_max": max(residuals) if residuals else None,
            "consecutive_motion_pairs": len(residuals),
            "association_frame_windows": deepcopy(frame_windows),
            "appearance_features_used": False}


def _validate_configuration(config):
    if not isinstance(config, dict) or config.get("policy_version") != POLICY_VERSION or config.get("metric") != "passage":
        raise ValueError("Explicit phase6_option_b_v1 passage policy is required")
    band = _num(config.get("neutral_band_px"), "neutral_band_px")
    if band < 0:
        raise ValueError("neutral_band_px must be nonnegative")
    _int(config.get("confirmation_observations"), "confirmation_observations", 1)
    association = config.get("association")
    if not isinstance(association, dict):
        raise ValueError("Association controls must be explicit")
    for kind, keys in (("component", COMPONENT_KEYS), ("same_vehicle", DUPLICATE_KEYS)):
        values = association.get(kind)
        if not isinstance(values, dict) or any(key not in values for key in keys):
            raise ValueError(f"Missing explicit {kind} threshold")
        for key in keys:
            number = (_int(values[key], key, 1) if key in ("min_common_frames", "min_consecutive_common_frames")
                      else _num(values[key], key))
            if number < 0 or (key in ("min_iou", "min_first_bc_inside_second_fraction") and number > 1):
                raise ValueError(f"Invalid threshold {key}")
    identity = config.get("input_identity")
    if not isinstance(identity, dict) or any(key not in identity for key in IDENTITY_FIELDS):
        raise ValueError("Explicit source identity is required")
    for key in ("video_sha256", "records_sha256", "geometry_sha256"):
        value = identity[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"Invalid SHA-256 {key}")
    for key in ("width", "height"):
        _int(identity[key], key, 1)
    for key in ("variant", "parent_run_id"):
        if not isinstance(identity[key], str) or not identity[key].strip():
            raise ValueError(f"Missing {key}")
    if "grouping_enabled" in config and not isinstance(config["grouping_enabled"], bool):
        raise ValueError("grouping_enabled must be boolean")
    scope = config.get("scope", {})
    if not isinstance(scope, dict):
        raise ValueError("scope must be an object")
    windows = scope.get("association_frame_windows")
    if windows is not None:
        if not isinstance(windows, list) or not windows:
            raise ValueError("association_frame_windows must be an explicit nonempty list")
        previous_end = None
        for window in windows:
            if not isinstance(window, list) or len(window) != 2:
                raise ValueError("Association window must contain start/end indices")
            start, end = (_int(v, "association frame") for v in window)
            if start > end or previous_end is not None and start <= previous_end:
                raise ValueError("Association windows must be ordered disjoint inclusive ranges")
            previous_end = end
    return deepcopy({key: identity[key] for key in IDENTITY_FIELDS})


def _supported(features, controls, kind):
    reasons = []
    if features["common_frames"] < controls["min_common_frames"]:
        reasons.append("INSUFFICIENT_COMMON_OBSERVATIONS")
    if features["consecutive_common_frames_max"] < controls["min_consecutive_common_frames"]:
        reasons.append("INSUFFICIENT_CONSECUTIVE_COMMON_OBSERVATIONS")
    if features["relative_motion_residual_norm_max"] is None:
        reasons.append("NO_CONSECUTIVE_MOTION_EVIDENCE")
    elif features["relative_motion_residual_norm_max"] > controls["max_relative_motion_residual_norm"]:
        reasons.append("RELATIVE_MOTION_CONTRADICTION")
    if features["center_distance_norm_max"] is None or features["center_distance_norm_max"] > controls["max_center_distance_norm"]:
        reasons.append("SPATIAL_SEPARATION")
    if kind == "COMPONENT_OF":
        if features["first_bc_inside_second_fraction"] is None or features["first_bc_inside_second_fraction"] < controls["min_first_bc_inside_second_fraction"]:
            reasons.append("PERSON_POSITION_NOT_SUPPORTED")
    elif features["iou_min"] is None or features["iou_min"] < controls["min_iou"]:
        reasons.append("DUPLICATE_BOX_AGREEMENT_NOT_SUPPORTED")
    return reasons


def _metadata(observation, identity, episode_id):
    return {"track_id": observation["track_id"], "episode_id": episode_id,
            "video_sha256": identity["video_sha256"], "records_sha256": identity["records_sha256"],
            "variant": identity["variant"], "parent_run_id": identity["parent_run_id"],
            "original_detection_index": observation["original_detection_index"],
            "raw_bbox": deepcopy(observation["raw_bbox"]), "class_id": observation["class_id"],
            "class_name": observation["class_name"], "confidence": observation["confidence"],
            "measurement_provenance": observation["measurement_provenance"],
            "timestamp_estimate_from_index_fps_seconds": observation.get("timestamp_estimate_from_index_fps_seconds"),
            "timestamp_is_verified_source_pts": False}


def _aggregate(events):
    unique = {}
    for event in events:
        if event.get("type") != "CountEvent" or event.get("accepted_count_event") is not True or event.get("status") != "accepted":
            raise ValueError("Only accepted typed CountEvents can be aggregated")
        key = event["event_id"]
        if key in unique and _canonical(unique[key]) != _canonical(event):
            raise ValueError("Conflicting event identity")
        unique[key] = event
    return {"total": len(unique), "by_category": {c: sum(e["category"] == c for e in unique.values()) for c in CATEGORIES},
            "by_direction": {d: sum(e["direction"] == d for e in unique.values()) for d in ("A_TO_B", "B_TO_A")},
            "event_ids": sorted(unique), "scope": "option_b_experimental_accepted_passage_subtotal_not_complete_traffic"}


def resolve_episodes(episodes, geometry, *, config, context_by_frame=None):
    """Resolve measured vehicle episodes; in-memory API for meaningful fixtures.

    All pairing alternatives are examined before any graph is built. Vehicle
    groups must be cliques: an inferred A=B=C chain without A=C evidence never
    merges. Multiple possible motorcycle groups hold the person and vehicles.
    Missing raw frame context holds acceptance, never substitutes proof.
    """
    identity = _validate_configuration(config)
    if not isinstance(geometry, Geometry):
        raise ValueError("Explicit validated Geometry is required")
    if geometry.width is not None and (geometry.width, geometry.height) != (identity["width"], identity["height"]):
        raise ValueError("Geometry dimensions do not match source identity")
    if geometry.video_sha256 is not None and geometry.video_sha256 != identity["video_sha256"]:
        raise ValueError("Geometry video does not match source identity")
    windows = config.get("scope", {}).get("association_frame_windows")
    grouping_enabled = config.get("grouping_enabled", True)
    episodes = sorted(deepcopy(episodes), key=lambda e: (e["track_id"], e["start_frame"], e["episode_id"]))
    by_id = {e["episode_id"]: e for e in episodes}
    if len(by_id) != len(episodes):
        raise ValueError("Duplicate episode_id")
    for episode in episodes:
        if episode.get("source_identity") != identity:
            raise ValueError("Episode source identity does not match configuration")
        observations = episode["observations"]
        if not observations or any(_family(o["class_name"]) != episode["family"] for o in observations):
            raise ValueError("Inconsistent measurement family episode")
        if observations[0]["frame_index"] != episode["start_frame"] or observations[-1]["frame_index"] != episode["end_frame"]:
            raise ValueError("Episode bounds do not match its measurements")
        if any(b["frame_index"] != a["frame_index"] + 1 for a, b in zip(observations, observations[1:])):
            raise ValueError("Episode cannot bridge missing measured observations")
        for observation in observations:
            validated = _validate_measurement(observation)
            if validated["track_id"] != episode["track_id"]:
                raise ValueError("One episode cannot mix raw track identities")
            if observation.get("point", validated["point"]) != validated["point"]:
                raise ValueError("Episode point differs from raw-bbox BC")
    vehicles = [e for e in episodes if e["family"] == "vehicle"]
    persons = [e for e in episodes if e["family"] == "person"]
    diagnostics, relations = [], []
    for episode in vehicles:
        machine = GeometryStateMachine(geometry, neutral_band_px=config["neutral_band_px"],
                                       confirmation_observations=config["confirmation_observations"])
        for observation in episode["observations"]:
            for diagnostic in machine.update(observation["frame_index"], _bc(observation["raw_bbox"]),
                                             metadata=_metadata(observation, identity, episode["episode_id"])):
                diagnostics.append({"episode_id": episode["episode_id"], "track_id": episode["track_id"],
                                    "frame_index": observation["frame_index"], **diagnostic})
        # Explicit gap audit survives the episode reset. It cannot become an event.
        preceding = episode.get("excluded_preceding_observations", [])
        if preceding and episode["boundary_reason"] in ("MEASUREMENT_GAP", "FAMILY_CHANGE_AND_GAP"):
            previous, current = preceding[-1], episode["observations"][0]
            if _family(previous["class_name"]) == "vehicle":
                intersection = segment_intersection(_bc(previous["raw_bbox"]), _bc(current["raw_bbox"]), geometry.p1, geometry.p2)
                if intersection["kind"] != "none" or geometry.side(_bc(previous["raw_bbox"])) != geometry.side(_bc(current["raw_bbox"])):
                    diagnostics.append({"type": "AMBIGUOUS_GAP", "episode_id": episode["episode_id"],
                                        "track_id": episode["track_id"], "frame_index": current["frame_index"],
                                        "geometry_id": geometry.geometry_id, "accepted_count_event": False,
                                        "previous_observation": deepcopy(previous), "current_observation": deepcopy(current),
                                        "interpolation_used": False})
    def relation(first, second, kind):
        features = pair_features(first, second, kind=kind, frame_windows=windows)
        if not features["common_frames"]:
            return None
        controls = config["association"]["component" if kind == "COMPONENT_OF" else "same_vehicle"]
        reasons = _supported(features, controls, kind)
        if not grouping_enabled:
            reasons.append("GROUPING_DISABLED_ABLATION")
        result = {"relation_id": _id("ur6b_", {"kind": kind, "first": first["episode_id"],
                                              "second": second["episode_id"], "controls": controls,
                                              "association_frame_windows": windows,
                                              "grouping_enabled": grouping_enabled}),
                  "type": kind, "first_episode_id": first["episode_id"], "second_episode_id": second["episode_id"],
                  "first_track_id": first["track_id"], "second_track_id": second["track_id"],
                  "status": "REJECTED" if reasons else "SUPPORTED", "reasons": reasons,
                  "features": features, "thresholds": deepcopy(controls),
                  "claim_type": "EXPERIMENTAL_MEASURED_RELATION_NOT_GROUND_TRUTH"}
        relations.append(result)
        return result
    duplicate_edges = set()
    neighbors = {e["episode_id"]: set() for e in vehicles}
    for index, first in enumerate(vehicles):
        for second in vehicles[index + 1:]:
            if first["track_id"] == second["track_id"]:
                continue
            item = relation(first, second, "SAME_VEHICLE")
            if item and item["status"] == "SUPPORTED":
                a, b = first["episode_id"], second["episode_id"]
                duplicate_edges.add(frozenset((a, b)))
                neighbors[a].add(b)
                neighbors[b].add(a)
    visited, groups, group_block = set(), {}, defaultdict(set)
    for first in sorted(neighbors):
        if first in visited:
            continue
        pending, members = [first], set()
        while pending:
            current = pending.pop()
            if current in members:
                continue
            members.add(current)
            pending.extend(neighbors[current] - members)
        visited.update(members)
        clique = all(frozenset((a, b)) in duplicate_edges for a in members for b in members if a < b)
        if not clique:
            for member in members:
                groups[member] = frozenset((member,))
                group_block[member].add("TRANSITIVE_IDENTITY_CONFLICT")
            for item in relations:
                if item["type"] == "SAME_VEHICLE" and {item["first_episode_id"], item["second_episode_id"]} <= members and item["status"] == "SUPPORTED":
                    item["status"] = "UNRESOLVED"
                    item["reasons"].append("TRANSITIVE_IDENTITY_CONFLICT")
        else:
            for member in members:
                groups[member] = frozenset(members)
    component_relations, components = [], defaultdict(set)
    for person in persons:
        alternatives = []
        for vehicle in vehicles:
            # A vehicle-class conflict cannot provide a motorcycle role decision.
            if {o["class_name"] for o in vehicle["observations"]} != {"motorcycle"}:
                continue
            item = relation(person, vehicle, "COMPONENT_OF")
            if item and item["status"] == "SUPPORTED":
                alternatives.append(item)
        alternative_groups = {groups[item["second_episode_id"]] for item in alternatives}
        if len(alternative_groups) > 1:
            for item in alternatives:
                item["status"] = "UNRESOLVED"
                item["reasons"].append("ALTERNATIVE_ASSIGNMENT_AMBIGUITY")
                for member in groups[item["second_episode_id"]]:
                    group_block[member].add("ALTERNATIVE_ASSIGNMENT_AMBIGUITY")
        else:
            for item in alternatives:
                component_relations.append(item)
                for member in groups[item["second_episode_id"]]:
                    components[member].add(person["episode_id"])
    def unit_id(member):
        return _id("pu6b_", {"source_identity": identity, "vehicle_episode_ids": sorted(groups[member])})
    for episode in episodes:
        episode["physical_unit_id"] = unit_id(episode["episode_id"]) if episode["family"] == "vehicle" else None
        episode["resolved_role"] = "vehicle" if episode["family"] == "vehicle" else (
            "rider_component" if any(episode["episode_id"] in c for c in components.values()) else "unresolved")
    decisions = []
    semantic = {key: deepcopy(config[key]) for key in ("policy_version", "metric", "neutral_band_px", "confirmation_observations", "association")}
    semantic["grouping_enabled"] = grouping_enabled
    semantic["association_frame_windows"] = deepcopy(windows)
    for diagnostic in sorted(diagnostics, key=lambda d: (d["frame_index"], d["track_id"], d["episode_id"], d["type"])):
        if diagnostic["type"] not in ("GEOMETRY_TRANSITION", "AMBIGUOUS_GAP", "AMBIGUOUS_ENDPOINT"):
            continue
        if windows is not None:
            selected_frames = ([diagnostic["crossing_frame_start"], diagnostic["crossing_frame_end"], diagnostic["confirmation_frame"]]
                               if diagnostic["type"] == "GEOMETRY_TRANSITION" else [diagnostic["frame_index"]])
            if not all(any(start <= frame <= end for start, end in windows) for frame in selected_frames):
                continue
        member = diagnostic["episode_id"]
        episode = by_id[member]
        selector = {key: diagnostic[key] for key in ("track_id", "episode_id", "frame_index", "type")}
        if diagnostic["type"] == "GEOMETRY_TRANSITION":
            selector.update({key: diagnostic[key] for key in ("origin_frame", "crossing_frame_start", "crossing_frame_end", "confirmation_frame", "direction")})
        candidate_id = _id("pc6b_", {"source_identity": identity, "selector": selector,
                                  "geometry_id": geometry.geometry_id, "policy": semantic})
        item = {"candidate_id": candidate_id, "episode_id": member, "track_id": episode["track_id"],
                "selector": selector, "status": "pending_review", "reasons": [], "hard_block_reasons": [],
                "category": None, "physical_unit_id": unit_id(member), "passage_id": None,
                "event_id": None, "accepted_count_event": False, "diagnostic": deepcopy(diagnostic),
                "component_episode_ids": sorted(components[member]), "vehicle_episode_ids": sorted(groups[member]),
                "identity_relation_ids": sorted(r["relation_id"] for r in relations if r["status"] == "SUPPORTED" and
                    ((r["type"] == "SAME_VEHICLE" and r["first_episode_id"] in groups[member] and r["second_episode_id"] in groups[member]) or
                     (r["type"] == "COMPONENT_OF" and r["second_episode_id"] in groups[member]))),
                "raw_competitor_evidence": []}
        labels = sorted({o["class_name"] for m in groups[member] for o in by_id[m]["observations"]})
        item["vehicle_class_histogram"] = dict(Counter(o["class_name"] for m in groups[member] for o in by_id[m]["observations"]))
        if len(labels) != 1:
            item["hard_block_reasons"].append("CATEGORY_CONFLICT")
        elif labels[0] == "bus":
            item["hard_block_reasons"].append("BUS_ANGKOT_MAPPING_OPEN")
        elif labels[0] in ("motorcycle", "car", "truck"):
            item["category"] = labels[0]
        else:
            item["hard_block_reasons"].append("UNSUPPORTED_VEHICLE_CATEGORY")
        if diagnostic["type"] != "GEOMETRY_TRANSITION":
            item["hard_block_reasons"].append(diagnostic["type"])
        item["hard_block_reasons"].extend(sorted(group_block[member]))
        if not item["identity_relation_ids"]:
            item["reasons"].append("NO_POSITIVE_PHYSICAL_IDENTITY_EVIDENCE")
        if diagnostic["type"] == "GEOMETRY_TRANSITION":
            start, end = diagnostic["origin_frame"], diagnostic["confirmation_frame"]
            # A relation observed elsewhere in a long raw track is not proof
            # that the same physical unit produced THIS passage. Preserve the
            # exploratory graph, but authorize counting only with sufficient
            # measured relation evidence inside origin -> confirmation.
            local_windows = [[start, end]] if windows is None else [
                [max(start, lower), min(end, upper)] for lower, upper in windows
                if max(start, lower) <= min(end, upper)]
            global_relation_ids = deepcopy(item["identity_relation_ids"])
            item["exploratory_global_identity_relation_ids"] = global_relation_ids
            item["exploratory_global_component_episode_ids"] = deepcopy(item["component_episode_ids"])
            local_ids, local_components, local_evidence = [], set(), []
            nonlocal_duplicate = False
            for relationship in relations:
                if relationship["relation_id"] not in global_relation_ids:
                    continue
                first = by_id[relationship["first_episode_id"]]
                second = by_id[relationship["second_episode_id"]]
                local_features = pair_features(first, second, kind=relationship["type"], frame_windows=local_windows)
                controls = config["association"]["component" if relationship["type"] == "COMPONENT_OF" else "same_vehicle"]
                local_reasons = _supported(local_features, controls, relationship["type"])
                local_evidence.append({"relation_id": relationship["relation_id"], "type": relationship["type"],
                    "passage_support_window": [start, end], "evaluated_frame_windows": deepcopy(local_windows),
                    "features": local_features, "thresholds": deepcopy(controls),
                    "status": "SUPPORTED" if not local_reasons else "INSUFFICIENT_PASSAGE_LOCAL_SUPPORT",
                    "reasons": local_reasons})
                if not local_reasons:
                    local_ids.append(relationship["relation_id"])
                    if relationship["type"] == "COMPONENT_OF":
                        local_components.add(relationship["first_episode_id"])
                elif relationship["type"] == "SAME_VEHICLE":
                    nonlocal_duplicate = True
            item["passage_identity_relation_evidence"] = local_evidence
            item["identity_relation_ids"] = sorted(local_ids)
            item["component_episode_ids"] = sorted(local_components)
            if global_relation_ids and (not local_ids or nonlocal_duplicate):
                item["hard_block_reasons"].append("IDENTITY_RELATION_OUTSIDE_PASSAGE_WINDOW")
            item["measurement_support"] = [deepcopy(o) for o in episode["observations"] if start <= o["frame_index"] <= end]
            if len(item["measurement_support"]) != end - start + 1:
                raise ValueError("Measured passage support is not complete")
            if context_by_frame is None or any(frame not in context_by_frame for frame in range(start, end + 1)):
                item["hard_block_reasons"].append("UNKNOWN_RAW_COMPETITORS")
            else:
                all_members = set(groups[member]) | local_components
                association_frames = {frame for evidence in local_evidence if evidence["status"] == "SUPPORTED"
                                      for frame in evidence["features"]["common_frame_indices"]}
                review_frames = sorted(set(range(start, end + 1)) | association_frames)
                item["identity_decision_evidence_frame_indices"] = sorted(association_frames)
                item["identity_decision_latest_evidence_frame"] = max(association_frames) if association_frames else None
                if any(frame not in context_by_frame for frame in review_frames):
                    item["hard_block_reasons"].append("UNKNOWN_RAW_COMPETITORS")
                for frame in review_frames:
                    if frame not in context_by_frame:
                        continue
                    linked = [o for ep in all_members for o in by_id[ep]["observations"] if o["frame_index"] == frame]
                    owned_indices = {o["original_detection_index"] for o in linked}
                    for observation in linked:
                        index = observation["original_detection_index"]
                        raw = context_by_frame[frame]["raw_detections"]
                        emitted = context_by_frame[frame]["emitted_tracks"]
                        if index >= len(raw) or observation["raw_bbox"] != raw[index]["bbox_xyxy_pixels"] or any(
                                observation[key] != raw[index][key] for key in ("class_name", "class_id", "confidence")):
                            raise ValueError("Episode measurement does not match raw frame context")
                        if not any(other["track_id"] == observation["track_id"] and other["original_detection_index"] == index
                                   and other.get("emitted") is True for other in emitted):
                            raise ValueError("Episode measurement lacks emitted frame-context source link")
                    for index, detection in enumerate(context_by_frame[frame]["raw_detections"]):
                        if index in owned_indices or detection["class_name"] not in VEHICLE_LABELS:
                            continue
                        box = detection["bbox_xyxy_pixels"]
                        if any(_intersection_area(o["raw_bbox"], box) > 0 or
                               o["class_name"] == "person" and box[0] <= _bc(o["raw_bbox"])[0] <= box[2]
                               and box[1] <= _bc(o["raw_bbox"])[1] <= box[3] for o in linked):
                            item["raw_competitor_evidence"].append({"frame_index": frame, "original_detection_index": index,
                                "class_name": detection["class_name"], "raw_bbox": deepcopy(box),
                                "emitted_track_ids": sorted(o["track_id"] for o in context_by_frame[frame]["emitted_tracks"] if o["original_detection_index"] == index)})
                if item["raw_competitor_evidence"]:
                    item["hard_block_reasons"].append("RAW_UNRESOLVED_VEHICLE_COMPETITOR")
        item["hard_block_reasons"] = sorted(set(item["hard_block_reasons"]))
        item["reasons"] = sorted(set(item["reasons"] + item["hard_block_reasons"]))
        if not item["reasons"]:
            item["status"] = "eligible"
        decisions.append(item)
    # One independently valid vehicle trajectory per same-unit passage. Never
    # concatenate measurements from members of the unit graph.
    unit_candidates = defaultdict(list)
    for item in decisions:
        if item["diagnostic"]["type"] == "GEOMETRY_TRANSITION":
            unit_candidates[item["physical_unit_id"]].append(item)
    events = []
    for physical_unit_id in sorted(unit_candidates):
        candidates = sorted(unit_candidates[physical_unit_id], key=lambda i: (
            i["diagnostic"]["crossing_frame_start"], i["diagnostic"]["confirmation_frame"], i["candidate_id"]))
        clusters = []
        for candidate in candidates:
            d = candidate["diagnostic"]
            matches = [cluster for cluster in clusters if cluster[0]["diagnostic"]["direction"] == d["direction"] and any(
                max(d["origin_frame"], other["diagnostic"]["origin_frame"]) <= min(d["confirmation_frame"], other["diagnostic"]["confirmation_frame"])
                for other in cluster)]
            if matches:
                matches[0].append(candidate)
            else:
                clusters.append([candidate])
        clusters.sort(key=lambda c: min(i["diagnostic"]["crossing_frame_start"] for i in c))
        for sequence, cluster in enumerate(clusters):
            passage_id = _id("ps6b_", {"physical_unit_id": physical_unit_id,
                "direction": cluster[0]["diagnostic"]["direction"], "candidate_ids": sorted(i["candidate_id"] for i in cluster)})
            for item in cluster:
                item["passage_id"] = passage_id
            if sequence > 0:
                for item in cluster:
                    item["status"] = "pending_review"
                    item["reasons"] = sorted(set(item["reasons"] + ["GENUINE_RETURN_REVIEW_REQUIRED"]))
                continue
            eligible = [i for i in cluster if i["status"] == "eligible"]
            if not eligible:
                continue
            representative = min(eligible, key=lambda i: (i["diagnostic"]["confirmation_frame"],
                                                          i["diagnostic"]["crossing_frame_start"], i["candidate_id"]))
            event_id = _id("ce6b_", {"source_identity": identity, "policy": semantic,
                                    "physical_unit_id": physical_unit_id, "passage_id": passage_id})
            for item in eligible:
                item["status"] = "accepted" if item is representative else "duplicate_suppressed"
                item["event_id"] = event_id
                item["accepted_count_event"] = item is representative
                item["duplicate_role"] = "representative" if item is representative else "same_passage_support"
            diagnostic = representative["diagnostic"]
            events.append({"type": "CountEvent", "accepted_count_event": True, "status": "accepted",
                "event_id": event_id, "candidate_id": representative["candidate_id"],
                "physical_unit_id": physical_unit_id, "passage_id": passage_id,
                "category": representative["category"], "direction": diagnostic["direction"],
                "track_id": representative["track_id"], "vehicle_measurement_episode_id": representative["episode_id"],
                "source_identity": deepcopy(identity), "policy_identity": _id("cfg6b_", semantic),
                "geometry_evidence": deepcopy(diagnostic), "measurement_support": deepcopy(representative["measurement_support"]),
                "vehicle_episode_ids": representative["vehicle_episode_ids"],
                "component_episode_ids": representative["component_episode_ids"],
                "identity_relation_ids": representative["identity_relation_ids"],
                "passage_identity_relation_evidence": deepcopy(representative["passage_identity_relation_evidence"]),
                "identity_decision_evidence_frame_indices": deepcopy(representative.get("identity_decision_evidence_frame_indices", [])),
                "identity_decision_latest_evidence_frame": representative.get("identity_decision_latest_evidence_frame"),
                "identity_evidence_policy": "measured_relation_support_inside_origin_to_confirmation_only",
                "execution_semantics": "offline_retained_source_experiment_not_online_latency_evidence",
                "is_causal_online_decision": False,
                "category_decision_latest_evidence_frame": max(by_id[episode_id]["end_frame"] for episode_id in representative["vehicle_episode_ids"]),
                "same_passage_candidate_ids": sorted(i["candidate_id"] for i in cluster),
                "claim_type": "EXPERIMENTAL_AUTOMATIC_PASSAGE_NOT_GROUND_TRUTH", "appearance_features_used": False})
    # Resetting a family/gap episode must not erase evidence of an earlier
    # passage on the same raw identity. A new physical-unit key is not proof
    # of genuine return or of a new physical vehicle.
    known_passages = defaultdict(list)
    for item in decisions:
        if item["diagnostic"]["type"] == "GEOMETRY_TRANSITION":
            known_passages[item["passage_id"]].append(item)
    seen_passage_tracks, held_event_ids = {}, set()
    for passage_id, items in sorted(known_passages.items(), key=lambda pair: (
            min(item["diagnostic"]["crossing_frame_start"] for item in pair[1]), pair[0])):
        source_tracks = {by_id[episode_id]["track_id"] for item in items for episode_id in item["vehicle_episode_ids"]}
        prior_unselected_passage = windows is not None and any(
            earlier["type"] == "GEOMETRY_TRANSITION" and earlier["track_id"] in source_tracks and
            earlier["confirmation_frame"] <= min(item["diagnostic"]["origin_frame"] for item in items) and
            not any(item["episode_id"] == earlier["episode_id"] and
                    item["diagnostic"]["crossing_frame_start"] == earlier["crossing_frame_start"] for item in items)
            for earlier in diagnostics)
        if prior_unselected_passage or any(track in seen_passage_tracks and seen_passage_tracks[track] != passage_id for track in source_tracks):
            for item in items:
                if item["event_id"] is not None:
                    held_event_ids.add(item["event_id"])
                item["status"] = "pending_review"
                item["reasons"] = sorted(set(item["reasons"] + ["GENUINE_RETURN_REVIEW_REQUIRED"]))
                item["accepted_count_event"] = False
                item["event_id"] = None
                item["duplicate_role"] = None
        for track in source_tracks:
            seen_passage_tracks.setdefault(track, passage_id)
    events = [event for event in events if event["event_id"] not in held_event_ids]
    return {"episodes": episodes, "relations": sorted(relations, key=lambda r: r["relation_id"]),
            "derived_diagnostics": diagnostics, "machine_decisions": decisions,
            "accepted_events": sorted(events, key=lambda e: e["event_id"]), "aggregate": _aggregate(events),
            "report": {"claim_type": "EXECUTED_OPTION_B_SOFTWARE_EXPERIMENT_NOT_A_BENCHMARK", "policy_version": POLICY_VERSION,
                "input_identity": identity, "episode_count": len(episodes),
                "episode_family_counts": dict(Counter(e["family"] for e in episodes)),
                "relation_status_counts": dict(Counter(r["status"] for r in relations)),
                "decision_status_counts": dict(Counter(d["status"] for d in decisions)),
                "geometry_diagnostic_counts": dict(Counter(d["type"] for d in diagnostics)),
                "accepted_events": len(events), "component_person_episodes": len({p for c in components.values() for p in c}),
                "association_frame_windows": deepcopy(windows), "grouping_enabled": grouping_enabled,
                "identity_support_policy": "PASSAGE_LOCAL_RELATION_EVIDENCE_REQUIRED_GLOBAL_GRAPH_EXPLORATORY",
                "detector_tracker_encoder_rerun": False, "appearance_features_used": False,
                "physical_identity_or_counting_accuracy_established": False}}


def _load_records(path, identity):
    measurements, context = [], {}
    opener = gzip.open if str(path).endswith(".gz") else open
    previous = None
    with opener(path, "rt", encoding="utf-8") as source:
        for row_number, line in enumerate(source, 1):
            if not line.strip():
                raise ValueError(f"Empty source record {row_number}")
            record = json.loads(line)
            frame = _int(record.get("frame_index"), "source frame")
            if previous is not None and frame != previous + 1:
                raise ValueError("Source frames must be continuous and ordered")
            previous = frame
            for key in ("video_sha256", "variant", "parent_run_id", "width", "height"):
                if record.get(key) != identity[key]:
                    raise ValueError(f"Source context mismatch: {key}")
            raw, tracks = record.get("raw_detections"), record.get("emitted_tracks")
            if not isinstance(raw, list) or not isinstance(tracks, list):
                raise ValueError("Source rows require raw detections and emitted tracks")
            for detection in raw:
                _box(detection.get("bbox_xyxy_pixels"))
                _int(detection.get("class_id"), "source class_id")
                _num(detection.get("confidence"), "source confidence")
                if not isinstance(detection.get("class_name"), str) or not detection["class_name"].strip():
                    raise ValueError("Invalid source class_name")
            frame_ids, indices = set(), set()
            for observation in tracks:
                item = _validate_measurement(observation)
                if item["frame_index"] != frame or observation.get("emitted") is not True:
                    raise ValueError("Emitted measurement frame/status mismatch")
                index = item["original_detection_index"]
                if item["track_id"] in frame_ids or index in indices or index >= len(raw):
                    raise ValueError("Duplicate or broken emitted source link")
                frame_ids.add(item["track_id"])
                indices.add(index)
                detection = raw[index]
                if item["raw_bbox"] != detection["bbox_xyxy_pixels"] or any(item[k] != detection[k] for k in ("class_id", "class_name", "confidence")):
                    raise ValueError("Measurement not value-linked to original source detection")
                item["timestamp_estimate_from_index_fps_seconds"] = record.get("timestamp_estimate_from_index_fps_seconds")
                measurements.append(item)
            context[frame] = {"raw_detections": deepcopy(raw), "emitted_tracks": deepcopy(tracks)}
    if not context:
        raise ValueError("No source records")
    return measurements, context


def run_identity_resolution(records_path, geometry_path, *, config):
    """Validate the entire retained cache, then execute only the declared scope."""
    identity = _validate_configuration(config)
    for path, field in ((records_path, "records_sha256"), (geometry_path, "geometry_sha256")):
        if _sha(path) != identity[field]:
            raise ValueError(f"Source hash mismatch: {field}")
    geometry = Geometry.from_draft(geometry_path, identity["width"], identity["height"])
    if geometry.video_sha256 != identity["video_sha256"]:
        raise ValueError("Geometry video identity mismatch")
    measurements, context = _load_records(records_path, identity)
    all_episodes = extract_episodes(measurements, source_identity=identity)
    scope = config.get("scope", {})
    if not isinstance(scope, dict):
        raise ValueError("scope must be an object")
    requested = scope.get("track_ids")
    if requested is None:
        episodes = all_episodes
    else:
        if not isinstance(requested, list) or not requested:
            raise ValueError("Explicit nonempty scope track_ids required")
        requested = {_int(i, "scope track_id", 1) for i in requested}
        present = {e["track_id"] for e in all_episodes}
        if requested - present:
            raise ValueError("Scope contains undiscovered track IDs")
        episodes = [e for e in all_episodes if e["track_id"] in requested]
    result = resolve_episodes(episodes, geometry, config=config, context_by_frame=context)
    result["source_index"] = {"input_identity": identity, "source_frame_count": len(context),
        "source_measured_observation_count": len(measurements), "all_source_episode_count": len(all_episodes),
        "selected_track_ids": sorted({e["track_id"] for e in episodes}),
        "selected_measured_observation_count": sum(len(e["observations"]) for e in episodes),
        "selected_source_links": [{"episode_id": e["episode_id"], "track_id": e["track_id"],
            "frame_index": o["frame_index"], "original_detection_index": o["original_detection_index"],
            "raw_bbox": deepcopy(o["raw_bbox"]), "class_name": o["class_name"]}
            for e in episodes for o in e["observations"]]}
    result["report"].update({"source_frame_count": len(context), "source_measured_observation_count": len(measurements),
                              "all_source_episode_count": len(all_episodes), "scope": deepcopy(scope),
                              "association_window_policy": "all_measured_common_frames_within_predeclared_generic_windows" if
                                  config.get("scope", {}).get("association_frame_windows") is not None else
                                  "all_measured_common_frames_of_complete_selected_episodes"})
    return result
