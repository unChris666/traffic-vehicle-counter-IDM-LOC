"""Phase 6 Option A notebook prototype: reviewed passage events, not a benchmark.

The v0 experiment accepts no unreviewed candidate.  Geometry is consumed from
retained Phase 5 diagnostics, never replayed or repaired here.  Raw detections
only screen conflicts and verify source links; they never create events.
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
from typing import Any

from phase_5_geometry_helpers import Geometry, point_in_polygon, signed_distance, segment_intersection


CONTRACT_VERSION = "phase6_option_a_v0"
CATEGORIES = ("pedestrian", "motorcycle", "car", "bus_angkot", "truck")
VEHICLE_LABELS = frozenset(("car", "motorcycle", "truck", "bus"))
IDENTITY_FIELDS = ("video_sha256", "records_sha256", "diagnostics_sha256", "geometry_sha256",
                   "variant", "width", "height", "parent_run_id")
HARD_REASONS = frozenset(("AMBIGUOUS_GAP", "AMBIGUOUS_ENDPOINT", "UNIT_COMPONENT_CHANGE",
                          "BUS_ANGKOT_MAPPING_OPEN"))


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _id(prefix, value):
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _bbox(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("raw bbox must contain four xyxy coordinates")
    result = [_number(v, "bbox coordinate") for v in value]
    if result[0] >= result[2] or result[1] >= result[3]:
        raise ValueError("raw bbox must have positive width and height")
    return result


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("point must contain two coordinates")
    return [_number(v, "point coordinate") for v in value]


def _equal_point(left, right):
    # Only numerical representation tolerance; this is not a jitter threshold.
    return all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)
               for a, b in zip(_point(left), _point(right)))


def _read_jsonl(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"Empty JSONL source row at line {number}")
            try:
                value = json.loads(line)
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid JSON source row {number}") from error
            if not isinstance(value, dict):
                raise ValueError("JSONL rows must be objects")
            yield value


def candidate_selector(diagnostic) -> dict[str, Any]:
    """Exact, human-reviewable selector; no nearest-frame fallback is allowed."""
    track_id = _integer(diagnostic.get("track_id"), "track_id", 1)
    kind = diagnostic.get("type")
    if kind == "GEOMETRY_TRANSITION":
        direction = diagnostic.get("direction")
        if direction not in ("A_TO_B", "B_TO_A"):
            raise ValueError("Unknown candidate direction")
        return {"track_id": track_id,
                "crossing_frame_start": _integer(diagnostic.get("crossing_frame_start"), "crossing start"),
                "crossing_frame_end": _integer(diagnostic.get("crossing_frame_end"), "crossing end"),
                "direction": direction}
    if kind in ("AMBIGUOUS_GAP", "AMBIGUOUS_ENDPOINT"):
        return {"track_id": track_id, "frame_index": _integer(diagnostic.get("frame_index"), "frame_index"),
                "type": kind}
    raise ValueError("Only complete or explicitly ambiguous geometry diagnostics have counting selectors")


def candidate_key(diagnostic, input_identity) -> str:
    """Candidate identity is stable across human review/status changes."""
    return _id("pc6_", {"input_identity": {k: input_identity[k] for k in IDENTITY_FIELDS},
                        "selector": candidate_selector(diagnostic), "geometry_id": diagnostic.get("geometry_id")})


def aggregate_events(events) -> dict[str, Any]:
    """Build one accepted snapshot; identical event IDs are idempotent."""
    unique = {}
    for event in events:
        event_id = _text(event.get("event_id"), "event_id")
        if (event.get("type") != "CountEvent" or event.get("accepted_count_event") is not True
                or event.get("status") != "accepted"):
            raise ValueError("Aggregation requires accepted CountEvent objects only")
        if event.get("category") not in CATEGORIES or event.get("direction") not in ("A_TO_B", "B_TO_A"):
            raise ValueError("Unsupported event category or direction")
        if event_id in unique and _canonical(unique[event_id]) != _canonical(event):
            raise ValueError("Conflicting payloads for one event_id")
        unique[event_id] = event
    category = Counter(e["category"] for e in unique.values())
    direction = Counter(e["direction"] for e in unique.values())
    return {"total": len(unique), "by_category": {c: category[c] for c in CATEGORIES},
            "by_direction": {d: direction[d] for d in ("A_TO_B", "B_TO_A")},
            "event_ids": sorted(unique), "scope": "reviewed_accepted_passage_subtotal_not_complete_traffic"}


def _configuration(config, diagnostics_path, records_path, geometry_path):
    if not isinstance(config, dict):
        raise ValueError("config must be explicit")
    if (config.get("contract_version"), config.get("metric"), config.get("review_policy")) != (
            CONTRACT_VERSION, "passage", "audit_gated"):
        raise ValueError("Only explicit phase6_option_a_v0 passage/audit_gated contract is supported")
    band = _number(config.get("neutral_band_px"), "neutral_band_px")
    if band < 0:
        raise ValueError("neutral_band_px must be nonnegative")
    confirmations = _integer(config.get("confirmation_observations"), "confirmation_observations", 1)
    identity = config.get("input_identity")
    if not isinstance(identity, dict) or any(k not in identity for k in IDENTITY_FIELDS):
        raise ValueError("config.input_identity must explicitly bind hashes, dimensions, variant and parent")
    identity = {k: identity[k] for k in IDENTITY_FIELDS}
    for key in ("video_sha256", "records_sha256", "diagnostics_sha256", "geometry_sha256"):
        if not isinstance(identity[key], str) or len(identity[key]) != 64 or any(c not in "0123456789abcdef" for c in identity[key]):
            raise ValueError(f"Invalid SHA-256 identity field {key}")
    for name in ("width", "height"):
        _integer(identity[name], name, 1)
    for name in ("variant", "parent_run_id"):
        _text(identity[name], name)
    for path, name in ((diagnostics_path, "diagnostics_sha256"), (records_path, "records_sha256"),
                       (geometry_path, "geometry_sha256")):
        if _sha(path) != identity[name]:
            raise ValueError(f"Source hash mismatch: {name}")
    geometry = Geometry.from_draft(geometry_path, identity["width"], identity["height"])
    if geometry.video_sha256 != identity["video_sha256"]:
        raise ValueError("Geometry video identity mismatch")
    # Bind the recorded geometry experiment too, when the retained report exists.
    report_path = Path(str(diagnostics_path).replace("_diagnostics.jsonl.gz", "_report.json"))
    if report_path != Path(diagnostics_path) and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        software = report.get("software_report", {})
        if software.get("neutral_band_px") != band or software.get("confirmation_observations") != confirmations:
            raise ValueError("Counting config differs from retained Phase 5 experiment parameters")
        for key, expected in (("source_records_file_sha256", identity["records_sha256"]),
                              ("source_variant", identity["variant"]), ("video_sha256", identity["video_sha256"]),
                              ("source_parent_run_id", identity["parent_run_id"])):
            if software.get(key) != expected:
                raise ValueError(f"Retained geometry report source identity mismatch: {key}")
        if report.get("diagnostics_file_sha256") != identity["diagnostics_sha256"]:
            raise ValueError("Retained geometry report diagnostics hash mismatch")
    return identity, geometry, band, confirmations


def _measurement_metadata(record, observation):
    return {"track_id": observation["track_id"], "video_sha256": record["video_sha256"],
            "parent_run_id": record["parent_run_id"], "variant": record["variant"],
            "original_detection_index": observation["original_detection_index"],
            "raw_bbox": observation["raw_bbox"], "class_id": observation["class_id"],
            "class_name": observation["class_name"], "confidence": observation["confidence"],
            "measurement_provenance": observation["measurement_provenance"],
            "timestamp_estimate_from_index_fps_seconds": record.get("timestamp_estimate_from_index_fps_seconds"),
            "timestamp_is_verified_source_pts": False}


def _overlap(a, b):
    return (min(a[2], b[2]) - max(a[0], b[0]) > 0 and
            min(a[3], b[3]) - max(a[1], b[1]) > 0)


def _load_sources(records_path, identity, diagnostics):
    windows = defaultdict(list)
    for diagnostic in diagnostics:
        if diagnostic["type"] == "GEOMETRY_TRANSITION":
            first = _integer(diagnostic.get("origin_frame"), "origin_frame")
            last = _integer(diagnostic.get("confirmation_frame"), "confirmation_frame")
        else:
            first = _integer(diagnostic["previous_observation"]["frame_index"], "previous_observation frame")
            last = _integer(diagnostic["current_observation"]["frame_index"], "current_observation frame")
        if first > last:
            raise ValueError("Diagnostic source window is reversed")
        windows[diagnostic["track_id"]].append((first, last))
    sources, overlaps, frames, emitted = {}, defaultdict(list), 0, 0
    previous = None
    for record in _read_jsonl(records_path):
        frame = _integer(record.get("frame_index"), "source frame")
        if previous is not None and frame != previous + 1:
            raise ValueError("Source frame records must be continuous and ordered")
        previous = frame
        frames += 1
        for key in ("video_sha256", "variant", "parent_run_id", "width", "height"):
            if record.get(key) != identity[key]:
                raise ValueError(f"Cached source context mismatch: {key}")
        _integer(record["width"], "source width", 1)
        _integer(record["height"], "source height", 1)
        timestamp = record.get("timestamp_estimate_from_index_fps_seconds")
        if timestamp is not None:
            _number(timestamp, "estimated timestamp")
        raw = record.get("raw_detections")
        tracks = record.get("emitted_tracks")
        if not isinstance(raw, list) or not isinstance(tracks, list):
            raise ValueError("Source row must carry raw_detections and emitted_tracks")
        for detection in raw:
            _bbox(detection.get("bbox_xyxy_pixels"))
            _integer(detection.get("class_id"), "class_id")
            _text(detection.get("class_name"), "class_name")
            _number(detection.get("confidence"), "confidence")
        frame_ids, indices = set(), set()
        for observation in tracks:
            track_id = _integer(observation.get("track_id"), "track_id", 1)
            index = _integer(observation.get("original_detection_index"), "detection index")
            if track_id in frame_ids or index in indices or index >= len(raw):
                raise ValueError("Duplicate track/detection link or broken detection index")
            frame_ids.add(track_id)
            indices.add(index)
            if observation.get("frame_index") != frame or observation.get("emitted") is not True:
                raise ValueError("Emitted measurement/frame contract mismatch")
            if observation.get("measurement_provenance") != "retained_phase_2_detection":
                raise ValueError("Counting requires raw measured detection provenance")
            box = _bbox(observation.get("raw_bbox"))
            _integer(observation.get("class_id"), "measurement class_id")
            _text(observation.get("class_name"), "measurement class_name")
            _number(observation.get("confidence"), "measurement confidence")
            detection = raw[index]
            if box != detection["bbox_xyxy_pixels"] or any(
                    observation.get(k) != detection[k] for k in ("class_id", "class_name", "confidence")):
                raise ValueError("Measurement not value-linked to original detection")
            emitted += 1
            if not any(start <= frame <= end for start, end in windows.get(track_id, [])):
                continue
            sources[(track_id, frame)] = {"frame_index": frame, "point": [(box[0] + box[2]) / 2, box[3]],
                                         "metadata": _measurement_metadata(record, observation)}
            for other_index, other in enumerate(raw):
                if other_index != index and other["class_name"] in VEHICLE_LABELS and _overlap(box, other["bbox_xyxy_pixels"]):
                    overlaps[(track_id, frame)].append({"frame_index": frame,
                        "candidate_original_detection_index": index, "other_original_detection_index": other_index,
                        "other_class_name": other["class_name"], "other_raw_bbox": other["bbox_xyxy_pixels"],
                        "other_emitted_track_ids": sorted(o["track_id"] for o in tracks
                                                         if o["original_detection_index"] == other_index)})
    if not frames:
        raise ValueError("No cached source frames")
    return sources, overlaps, frames, emitted


def _check_observation(observation, track_id, sources):
    frame = _integer(observation.get("frame_index"), "diagnostic observation frame")
    source = sources.get((track_id, frame))
    if source is None:
        raise ValueError("Diagnostic refers to absent emitted measurement")
    if not _equal_point(observation.get("point"), source["point"]):
        raise ValueError("Diagnostic point is not raw-bbox BC")
    metadata = observation.get("metadata", {})
    for key, value in source["metadata"].items():
        if metadata.get(key) != value:
            raise ValueError(f"Diagnostic measurement provenance mismatch: {key}")
    return source


def _stable_side(source, geometry, band):
    distance = signed_distance(source["point"], geometry.p1, geometry.p2)
    if abs(distance) <= max(band, 1e-9):
        return None
    return geometry.side(source["point"])


def _candidate_decision(diagnostic, identity, geometry, band, confirmations, sources, overlaps):
    decision = {"candidate_id": candidate_key(diagnostic, identity), "selector": candidate_selector(diagnostic),
                "track_id": diagnostic["track_id"], "diagnostic_type": diagnostic["type"],
                "status": "pending_review", "reasons": [], "hard_block_reasons": [],
                "diagnostic": deepcopy(diagnostic), "accepted_count_event": False,
                "event_id": None, "review_id": None, "category": None, "physical_unit_id": None,
                "passage_id": None, "duplicate_role": None}
    track_id = diagnostic["track_id"]
    if diagnostic.get("geometry_id") != geometry.geometry_id or diagnostic.get("accepted_count_event") is not False:
        raise ValueError("Diagnostic geometry identity/status is not retained Phase 5 evidence")
    if diagnostic["type"] != "GEOMETRY_TRANSITION":
        _check_observation(diagnostic["previous_observation"], track_id, sources)
        _check_observation(diagnostic["current_observation"], track_id, sources)
        decision["hard_block_reasons"] = [diagnostic["type"]]
        decision["reasons"] = [diagnostic["type"]]
        decision["support_window"] = None
        decision["raw_class_histogram"] = {}
        decision["identity_conflicts"] = []
        return decision
    origin, start, end, confirm = (diagnostic[k] for k in ("origin_frame", "crossing_frame_start",
                                                         "crossing_frame_end", "confirmation_frame"))
    for frame in (origin, start, end, confirm):
        _integer(frame, "diagnostic support frame")
    if not (origin <= start < end <= confirm) or diagnostic.get("frame_index") != confirm:
        raise ValueError("Invalid origin/passage/confirmation ordering")
    origin_source = _check_observation(diagnostic["origin_observation"], track_id, sources)
    crossing = diagnostic["crossing_evidence"]
    start_source = _check_observation(crossing["start_observation"], track_id, sources)
    end_source = _check_observation(crossing["end_observation"], track_id, sources)
    if (origin_source["frame_index"], start_source["frame_index"], end_source["frame_index"]) != (origin, start, end):
        raise ValueError("Diagnostic observation frames do not match passage fields")
    if not _equal_point(diagnostic["origin_point"], origin_source["point"]):
        raise ValueError("Diagnostic origin point mismatch")
    confirmation_sources = [_check_observation(o, track_id, sources)
                            for o in diagnostic.get("confirmation_observations", [])]
    if len(confirmation_sources) != confirmations or [o["frame_index"] for o in confirmation_sources] != list(
            range(confirm - confirmations + 1, confirm + 1)):
        raise ValueError("Diagnostic confirmation window differs from explicit parameters")
    confirmation = confirmation_sources[-1]
    if not _equal_point(diagnostic["confirmation_point"], confirmation["point"]):
        raise ValueError("Diagnostic confirmation point mismatch")
    if diagnostic.get("metadata") != confirmation["metadata"]:
        raise ValueError("Diagnostic top-level measurement provenance mismatch")
    window = []
    for frame in range(origin, confirm + 1):
        source = sources.get((track_id, frame))
        if source is None:
            raise ValueError("Incomplete measured origin-to-confirmation support window")
        window.append(source)
    origin_side = _stable_side(origin_source, geometry, band)
    destination = _stable_side(confirmation, geometry, band)
    if origin_side not in ("A", "B") or destination == origin_side or destination not in ("A", "B"):
        raise ValueError("Diagnostic origin/destination is not supported by measured polygons")
    if (diagnostic.get("origin_side"), diagnostic.get("destination_side"), diagnostic.get("direction")) != (
            origin_side, destination, f"{origin_side}_TO_{destination}"):
        raise ValueError("Diagnostic direction metadata mismatch")
    if any(_stable_side(s, geometry, band) != destination for s in confirmation_sources):
        raise ValueError("Consecutive opposite-ROI confirmation unsupported")
    method = crossing.get("method")
    if method == "consecutive_measured_segment":
        if end != start + 1:
            raise ValueError("Passage crosses missing observations")
        intersection = segment_intersection(start_source["point"], end_source["point"], geometry.p1, geometry.p2)
        if intersection["kind"] != "proper":
            raise ValueError("Retained passage is not a proper interior finite-segment crossing")
    elif method == "measured_touch_then_opposite_sign":
        first = _check_observation(crossing["first_touch_observation"], track_id, sources)
        last = _check_observation(crossing["last_touch_observation"], track_id, sources)
        if first["frame_index"] != start + 1 or last["frame_index"] != end - 1:
            raise ValueError("Invalid contiguous measured contact interval")
        for frame in range(start + 1, end):
            point = sources[(track_id, frame)]["point"]
            if abs(signed_distance(point, geometry.p1, geometry.p2)) > 1e-9:
                raise ValueError("Contact interval includes off-line measurements")
            hit = segment_intersection(start_source["point"], point, geometry.p1, geometry.p2)
            if hit["kind"] != "touch":
                raise ValueError("Contact interval does not stay on finite-line interior")
        # Derive the retained first contact from measured BCs.  Comparing two
        # copies of the diagnostic point would let source rebinding hide an
        # invented intersection even though the measurements stayed unchanged.
        intersection = segment_intersection(start_source["point"], first["point"], geometry.p1, geometry.p2)
        if intersection["kind"] != "touch":
            raise ValueError("First measured contact is not finite-line interior")
    else:
        raise ValueError("Unsupported measured passage method")
    if not _equal_point(diagnostic["crossing_point"], intersection.get("point")) or not _equal_point(
            crossing["intersection"].get("point"), intersection.get("point")):
        raise ValueError("Retained intersection point mismatch")
    if crossing["intersection"].get("kind") != intersection["kind"]:
        raise ValueError("Retained intersection kind mismatch")
    for fraction in ("t", "u"):
        value = _number(crossing["intersection"].get(fraction), f"intersection {fraction}")
        if not math.isclose(value, intersection[fraction], rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError(f"Retained intersection fraction mismatch: {fraction}")
    entry_distance = signed_distance(start_source["point"], geometry.p1, geometry.p2)
    exit_distance = signed_distance(end_source["point"], geometry.p1, geometry.p2)
    if entry_distance * exit_distance >= 0:
        raise ValueError("Passage lacks opposite measured signs")
    if crossing.get("entry_sign") != (1 if entry_distance > 0 else -1) or crossing.get("exit_sign") != (1 if exit_distance > 0 else -1):
        raise ValueError("Retained crossing sign mismatch")
    sequence = _integer(diagnostic.get("software_transition_sequence"), "software_transition_sequence", 1)
    labels = Counter(s["metadata"]["class_name"] for s in window)
    families = {"vehicle" if label in VEHICLE_LABELS else "person" if label == "person" else "unrelated"
                for label in labels}
    if len(families) > 1:
        decision["hard_block_reasons"].append("UNIT_COMPONENT_CHANGE")
    if "bus" in labels:
        decision["hard_block_reasons"].append("BUS_ANGKOT_MAPPING_OPEN")
    if set(labels) == {"person"}:
        decision["reasons"].append("ROLE_UNRESOLVED")
    elif set(labels).issubset(VEHICLE_LABELS):
        if len(labels) == 1 and "bus" not in labels:
            decision["experimental_category_interpretation"] = next(iter(labels))
        elif len(labels) > 1:
            decision["reasons"].append("CATEGORY_CONFLICT")
    elif families == {"unrelated"}:
        decision["status"] = "rejected"
        decision["reasons"].append("UNSUPPORTED_COUNTABLE_UNIT")
    conflicts = [entry for source in window for entry in overlaps.get((track_id, source["frame_index"]), [])]
    if conflicts:
        decision["reasons"].append("VEHICLE_OVERLAP_IDENTITY_CONFLICT")
    if sequence > 1:
        decision["reasons"].append("RETURN_EPISODE_REVIEW_REQUIRED")
    decision["reasons"].extend(decision["hard_block_reasons"])
    if decision["status"] != "rejected":
        decision["reasons"].extend(("UNIT_REVIEW_REQUIRED", "CATEGORY_REVIEW_REQUIRED", "IDENTITY_REVIEW_REQUIRED"))
    decision["support_window"] = {"first_frame": origin, "last_frame": confirm,
                                   "measured_observation_count": len(window)}
    required_frames = {origin, start, end, confirm}
    if method == "measured_touch_then_opposite_sign":
        required_frames.update(range(start + 1, end))
    decision["required_review_frames"] = sorted(required_frames)
    decision["raw_class_histogram"] = dict(sorted(labels.items()))
    decision["class_history"] = [{"frame_index": s["frame_index"], "class_id": s["metadata"]["class_id"],
                                   "class_name": s["metadata"]["class_name"]} for s in window]
    decision["measurement_support"] = window
    decision["identity_conflicts"] = conflicts
    return decision


def _review_evidence(review, evidence_root):
    evidence = review.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Review requires actual hash-bound evidence references")
    root = Path(evidence_root).resolve()
    covered = set()
    for reference in evidence:
        if not isinstance(reference, dict):
            raise ValueError("Evidence reference must be an object")
        path_value = _text(reference.get("path"), "evidence path")
        path = (root / path_value).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Evidence path must be an existing file under evidence_root")
        if reference.get("sha256") != _sha(path):
            raise ValueError("Review evidence hash mismatch")
        frame_indices = reference.get("frame_indices")
        if not isinstance(frame_indices, list) or not frame_indices:
            raise ValueError("Evidence must declare actual supporting frame_indices")
        covered.update(_integer(frame, "evidence frame") for frame in frame_indices)
        _text(reference.get("observation"), "evidence observation")
    return covered


def _review_mapping(reviews, identity, decisions, evidence_root):
    if reviews is None:
        return {}, None
    if isinstance(reviews, (str, Path)):
        reviews = json.loads(Path(reviews).read_text(encoding="utf-8"))
    if evidence_root is None:
        raise ValueError("Explicit evidence_root is required for review validation")
    if not isinstance(reviews, dict) or not isinstance(reviews.get("input_identity"), dict):
        raise ValueError("Review file must bind input_identity")
    if any(reviews["input_identity"].get(k) != identity[k] for k in IDENTITY_FIELDS):
        raise ValueError("Review input identity mismatch")
    entries = reviews.get("decisions")
    if not isinstance(entries, list):
        raise ValueError("Review decisions must be a list")
    selectors = {_canonical(d["selector"]): d for d in decisions}
    mapping = {}
    for review in entries:
        selector = review.get("selector")
        if not isinstance(selector, dict) or _canonical(selector) not in selectors:
            raise ValueError("Review selector does not exactly match retained candidate")
        key = _canonical(selector)
        if key in mapping:
            if _canonical(mapping[key]["review"]) == _canonical(review):
                continue
            raise ValueError("Conflicting repeated review selector")
        _text(review.get("reviewer"), "reviewer")
        _text(review.get("reason"), "review reason")
        if review.get("decision") not in ("CONFIRM_PASSAGE", "REJECT_COMPONENT", "REJECT", "HOLD"):
            raise ValueError("Unsupported review disposition")
        covered = _review_evidence(review, evidence_root)
        mapping[key] = {"review": deepcopy(review), "covered_frames": covered,
                        "review_id": _id("pr6_", {"input_identity": identity, "review": review})}
    return mapping, deepcopy(reviews)


def _apply_review(machine, mapped):
    result = deepcopy(machine)
    if mapped is None:
        return result
    review = mapped["review"]
    result["review_id"] = mapped["review_id"]
    result["review"] = deepcopy(review)
    result["physical_unit_id"] = review.get("physical_unit_id")
    result["passage_id"] = review.get("passage_id")
    if review["decision"] == "HOLD":
        result["status"] = "pending_review"
        result["reasons"] = sorted(set(result["reasons"] + ["REVIEW_HOLD"]))
        return result
    if review["decision"] in ("REJECT_COMPONENT", "REJECT"):
        if review["decision"] == "REJECT_COMPONENT" and review.get("role") not in ("rider", "passenger"):
            raise ValueError("REJECT_COMPONENT requires rider/passenger role")
        result["status"] = "rejected"
        result["reasons"] = sorted(set(result["hard_block_reasons"] +
                                         ["REVIEW_REJECTED_COMPONENT" if review["decision"] == "REJECT_COMPONENT" else "REVIEW_REJECTED"]))
        return result
    for key in ("physical_unit_id", "passage_id"):
        _text(review.get(key), key)
    if review.get("category") not in CATEGORIES or review.get("role") not in ("vehicle", "pedestrian"):
        raise ValueError("CONFIRM_PASSAGE requires explicit countable role and category")
    category, role = review["category"], review["role"]
    if (category == "pedestrian") != (role == "pedestrian"):
        raise ValueError("Review category/role contradiction")
    labels = set(result["raw_class_histogram"])
    pending = list(result["hard_block_reasons"])
    if machine["status"] == "rejected":
        pending.append("UNSUPPORTED_COUNTABLE_UNIT")
    if role == "pedestrian" and labels != {"person"}:
        pending.append("PEDESTRIAN_MEASUREMENT_SUPPORT_REQUIRED")
    if role == "vehicle" and not labels.issubset(VEHICLE_LABELS):
        pending.append("VEHICLE_MEASUREMENT_SUPPORT_REQUIRED")
    if role == "vehicle" and category not in labels:
        pending.append("CATEGORY_WITHOUT_CLASS_SUPPORT")
    if category == "bus_angkot":
        pending.append("BUS_ANGKOT_MAPPING_OPEN")
    for flag, reason in (("unit_confirmed", "UNIT_REVIEW_REQUIRED"),
                         ("category_confirmed", "CATEGORY_REVIEW_REQUIRED"),
                         ("identity_confirmed", "IDENTITY_REVIEW_REQUIRED")):
        if review.get(flag) is not True:
            pending.append(reason)
    required = set(result.get("required_review_frames", []))
    if not required.issubset(mapped["covered_frames"]):
        pending.append("EVIDENCE_FRAME_COVERAGE_INCOMPLETE")
    if "RETURN_EPISODE_REVIEW_REQUIRED" in machine["reasons"] and review.get("independent_return_confirmed") is not True:
        pending.append("RETURN_EPISODE_REVIEW_REQUIRED")
    result["category"] = category
    result["reasons"] = sorted(set(pending))
    result["status"] = "pending_review" if pending else "accepted"
    result["accepted_count_event"] = not pending
    return result


def _representative_key(decision):
    d = decision["diagnostic"]
    return (d["crossing_frame_start"], d["crossing_frame_end"], d["confirmation_frame"],
            d["origin_frame"], d["track_id"], decision["candidate_id"])


def _events(resolved, identity, config_id, recording_metadata):
    # The same physical unit with distinct passage IDs requires positive return
    # evidence for every later reviewed episode, even across software IDs.
    physical = defaultdict(list)
    for decision in resolved:
        if decision["physical_unit_id"] and decision["passage_id"] and decision["diagnostic_type"] == "GEOMETRY_TRANSITION":
            physical[decision["physical_unit_id"]].append(decision)
    for members in physical.values():
        episodes = defaultdict(list)
        for member in members:
            episodes[member["passage_id"]].append(member)
        ordered = sorted(episodes.values(), key=lambda group: min(_representative_key(m) for m in group))
        conflicting_episodes = set()
        for index, first_episode in enumerate(ordered):
            for other_index, second_episode in enumerate(ordered[index + 1:], index + 1):
                if any(max(a["diagnostic"]["crossing_frame_start"], b["diagnostic"]["crossing_frame_start"])
                       < min(a["diagnostic"]["crossing_frame_end"], b["diagnostic"]["crossing_frame_end"])
                       for a in first_episode for b in second_episode):
                    conflicting_episodes.update((index, other_index))
        # Distinct passage labels plus an affirmative return flag cannot resolve
        # simultaneous measured passages assigned to one physical unit.  Hold
        # both episodes; choosing an arbitrary earliest one hides the conflict.
        # Adjacent intervals may share a measurement boundary, and opposite
        # directions are not required by the business passage metric.
        for index in conflicting_episodes:
            for member in ordered[index]:
                if member["status"] != "rejected":
                    member["status"] = "pending_review"
                    member["accepted_count_event"] = False
                    member["reasons"] = sorted(set(member["reasons"] + ["OVERLAPPING_PASSAGE_EPISODES"]))
        for later in ordered[1:]:
            for member in later:
                if member["status"] == "accepted" and member["review"].get("independent_return_confirmed") is not True:
                    member["status"] = "pending_review"
                    member["accepted_count_event"] = False
                    member["reasons"] = ["RETURN_EPISODE_REVIEW_REQUIRED"]
    groups = defaultdict(list)
    for decision in resolved:
        if decision["status"] == "accepted":
            groups[(decision["physical_unit_id"], decision["passage_id"])].append(decision)
    events = []
    for (physical_id, passage_id), members in groups.items():
        members.sort(key=_representative_key)
        categories = {m["category"] for m in members}
        directions = {m["diagnostic"]["direction"] for m in members}
        if len(categories) != 1 or len(directions) != 1:
            raise ValueError("One reviewed physical passage has contradictory category/direction")
        representative = members[0]
        diagnostic = representative["diagnostic"]
        event_id = _id("pe6_", {"input_identity": identity, "counting_config_id": config_id,
                               "physical_unit_id": physical_id, "passage_id": passage_id})
        related = [m for m in resolved if m["physical_unit_id"] == physical_id and m["passage_id"] == passage_id
                   and m["status"] != "accepted"]
        event = {"event_id": event_id, "type": "CountEvent", "accepted_count_event": True,
                 "status": "accepted", "metric": "passage",
                 "physical_unit_id": physical_id, "passage_id": passage_id,
                 "representative_candidate_id": representative["candidate_id"],
                 "representative_track_id": representative["track_id"],
                 "source_candidate_ids": sorted(m["candidate_id"] for m in members),
                 "source_track_ids": sorted({m["track_id"] for m in members}),
                 "related_nonaccepted_candidate_ids": sorted(m["candidate_id"] for m in related),
                 "category": representative["category"], "direction": diagnostic["direction"],
                 "origin_side": diagnostic["origin_side"], "destination_side": diagnostic["destination_side"],
                 "input_identity": deepcopy(identity), "counting_config_id": config_id,
                 "geometry_id": diagnostic["geometry_id"], "recording_metadata": deepcopy(recording_metadata),
                 "review_ids": sorted(m["review_id"] for m in members),
                 "review_evidence": [deepcopy(m["review"]["evidence"]) for m in members],
                 "raw_class_histogram": deepcopy(representative["raw_class_histogram"]),
                 "class_history": deepcopy(representative["class_history"]),
                 "identity_resolution": "explicit_review_same_physical_unit_and_passage_no_trajectory_merge",
                 "duplicate_resolution": "earliest_hard_eligible_measured_candidate",
                 "independent_return_confirmed": representative["review"].get("independent_return_confirmed") is True,
                 "geometry_evidence": deepcopy(diagnostic),
                 "measurement_support": deepcopy(representative["measurement_support"]),
                 "time": {"origin_frame": diagnostic["origin_frame"],
                          "passage_frame_start": diagnostic["crossing_frame_start"],
                          "passage_frame_end": diagnostic["crossing_frame_end"],
                          "confirmation_frame": diagnostic["confirmation_frame"],
                          "origin_index_fps_estimate_seconds": diagnostic["origin_observation"]["metadata"].get("timestamp_estimate_from_index_fps_seconds"),
                          "passage_start_index_fps_estimate_seconds": diagnostic["crossing_evidence"]["start_observation"]["metadata"].get("timestamp_estimate_from_index_fps_seconds"),
                          "passage_end_index_fps_estimate_seconds": diagnostic["crossing_evidence"]["end_observation"]["metadata"].get("timestamp_estimate_from_index_fps_seconds"),
                          "confirmation_index_fps_estimate_seconds": diagnostic["metadata"].get("timestamp_estimate_from_index_fps_seconds"),
                          "timestamp_is_verified_source_pts": False,
                          "authoritative_source_pts": None},
                 "limitations": ["bounded_visual_review_not_ground_truth", "not_complete_video_traffic_total"]}
        for member in members:
            member["event_id"] = event_id
            member["duplicate_role"] = "representative" if member is representative else "duplicate_member"
            member["accepted_count_event"] = member is representative
            member["reasons"] = ["REVIEW_CONFIRMED_PASSAGE" if member is representative else "REVIEW_CONFIRMED_DUPLICATE_MEMBER"]
        events.append(event)
    events.sort(key=lambda e: (e["time"]["passage_frame_start"], e["event_id"]))
    return events


def run_counting(diagnostics_path, records_path, geometry_path, *, config, reviews=None, evidence_root=None):
    """Consume retained measurements after the external synthetic-test gate.

    This pure-stdlib helper does not load or run models, track association,
    geometry state machines, video enhancement, or UI.  Review interpretations
    remain human/AI audit observations, not formal ground truth.
    """
    identity, geometry, band, confirmations = _configuration(config, diagnostics_path, records_path, geometry_path)
    frequencies = Counter()
    diagnostics, seen = [], {}
    ignored_duplicates = 0
    for diagnostic in _read_jsonl(diagnostics_path):
        kind = _text(diagnostic.get("type"), "diagnostic type")
        frequencies[kind] += 1
        if kind not in ("GEOMETRY_TRANSITION", "AMBIGUOUS_GAP", "AMBIGUOUS_ENDPOINT"):
            continue
        key = candidate_key(diagnostic, identity)
        if key in seen:
            if _canonical(seen[key]) != _canonical(diagnostic):
                raise ValueError("Conflicting duplicate candidate diagnostic payload")
            ignored_duplicates += 1
            continue
        seen[key] = diagnostic
        diagnostics.append(diagnostic)
    sources, overlaps, frames, emitted = _load_sources(records_path, identity, diagnostics)
    machine = [_candidate_decision(d, identity, geometry, band, confirmations, sources, overlaps)
               for d in diagnostics]
    mapping, retained_reviews = _review_mapping(reviews, identity, machine, evidence_root)
    resolved = [_apply_review(m, mapping.get(_canonical(m["selector"]))) for m in machine]
    # Context metadata is included in reproducibility identity; unlike category
    # review it can change the interpretation/snapshot aggregation namespace.
    recording_metadata = {"store_code": None, "store_name": None, "latitude": None, "longitude": None,
                          "day_type": None, "recording_period": None}
    supplied_metadata = config.get("recording_metadata", {})
    if not isinstance(supplied_metadata, dict):
        raise ValueError("recording_metadata must be an object with unknown fields null")
    recording_metadata.update(supplied_metadata)
    # Execution timestamps/random run labels are provenance, not semantics.
    # Hash the explicitly supported policy fields and declared context only.
    semantic_config = {key: config[key] for key in (
        "contract_version", "metric", "review_policy", "neutral_band_px",
        "confirmation_observations", "input_identity")}
    semantic_config["recording_metadata"] = recording_metadata
    config_id = _id("cc6_", semantic_config)
    accepted = _events(resolved, identity, config_id, recording_metadata)
    machine_aggregate, aggregate = aggregate_events([]), aggregate_events(accepted)
    report = {"claim_type": "EXECUTED_SOFTWARE_AUDIT_GATED_PASSAGE_SUBTOTAL_NOT_ACCURACY",
              "contract_version": CONTRACT_VERSION, "input_identity": deepcopy(identity),
              "counting_config_id": config_id, "effective_config": deepcopy(config),
              "frames_processed": frames, "emitted_measured_observations_processed": emitted,
              "source_diagnostic_frequencies": dict(sorted(frequencies.items())),
              "complete_geometry_candidates": sum(d["diagnostic_type"] == "GEOMETRY_TRANSITION" for d in machine),
              "ambiguous_geometry_audit_items": sum(d["diagnostic_type"] != "GEOMETRY_TRANSITION" for d in machine),
              "ignored_identical_duplicate_diagnostics": ignored_duplicates,
              "machine_decision_statuses": dict(Counter(d["status"] for d in machine)),
              "resolved_decision_statuses": dict(Counter(d["status"] for d in resolved)),
              "resolved_pending_reason_frequencies": dict(Counter(reason for d in resolved
                       if d["status"] == "pending_review" for reason in d["reasons"])),
              "reviewed_candidates": len(mapping), "accepted_event_count": len(accepted),
              "accepted_candidate_members": sum(d["status"] == "accepted" for d in resolved),
              "accepted_duplicate_members": sum(d["duplicate_role"] == "duplicate_member" for d in resolved),
              "machine_events_accepted": 0, "aggregate_reconciles": aggregate["total"] == len(accepted),
              "geometry_detector_tracker_encoder_rerun": False, "numeric_product_defaults_selected": False,
              "complete_video_traffic_count_established": False, "ground_truth_available": False,
              "helper_sha256": _sha(__file__), "review_input_sha256": _id("", retained_reviews) if retained_reviews is not None else None,
              "representative_order": ["crossing_frame_start", "crossing_frame_end", "confirmation_frame", "origin_frame", "track_id", "candidate_id"]}
    return {"machine_decisions": machine, "resolved_decisions": resolved, "machine_events": [],
            "accepted_events": accepted, "machine_aggregate": machine_aggregate, "aggregate": aggregate,
            "report": report, "review_input": retained_reviews}
