#!/usr/bin/env python3
"""Create a fresh, explicit reviewed overlay of retained Option B outputs.

Uses standard-library IO and the existing geometry predicates/aggregation
helper. Never executes the identity resolver, geometry state machine, models,
video decoder or encoder. Original machine artifacts remain immutable.
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
import sys


POLICY = "phase6_option_b_review_overlay_v1"
REVIEWABLE_REASONS = frozenset({
    "NO_POSITIVE_PHYSICAL_IDENTITY_EVIDENCE", "RAW_UNRESOLVED_VEHICLE_COMPETITOR",
    "ALTERNATIVE_ASSIGNMENT_AMBIGUITY", "IDENTITY_RELATION_OUTSIDE_PASSAGE_WINDOW",
    "IDENTITY_SUPPORT_INSUFFICIENT_WITHIN_PASSAGE_WINDOW",
})
VEHICLE_CATEGORIES = frozenset({"car", "motorcycle", "truck"})
IDENTITY_FIELDS = ("video_sha256", "records_sha256", "geometry_sha256", "variant",
                   "width", "height", "parent_run_id")
SEMANTIC_POLICY_FIELDS = ("policy_version", "metric", "neutral_band_px",
    "confirmation_observations", "grouping_enabled", "scope", "association",
    "episode_policy", "category_policy", "identity_policy", "identity_support_policy")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def logical_id(prefix, value):
    return prefix + hashlib.sha256(canonical(value).encode()).hexdigest()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be nonnegative integer")
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric")
    return value


def point_equal(first, second):
    return (isinstance(first, (list, tuple)) and len(first) == 2
            and isinstance(second, (list, tuple)) and len(second) == 2
            and all(math.isclose(number(a, "point"), number(b, "point"), rel_tol=1e-12, abs_tol=1e-9)
                    for a, b in zip(first, second)))


def raw_bc(box):
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise ValueError("raw_bbox must be xyxy")
    values = [number(v, "bbox coordinate") for v in box]
    if values[0] >= values[2] or values[1] >= values[3]:
        raise ValueError("Non-positive measured bbox")
    return [(values[0] + values[2]) / 2, values[3]]


def geometry_imports(repo):
    notebooks = str((Path(repo) / "notebooks").resolve())
    if notebooks not in sys.path:
        sys.path.insert(0, notebooks)
    from phase_5_geometry_helpers import Geometry, segment_intersection, signed_distance
    from phase_6_counting_helpers import aggregate_events
    return Geometry, segment_intersection, signed_distance, aggregate_events


def evidence_validate(row, repo):
    evidence = row.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Review requires actual hash-bound evidence")
    covered = set()
    repo = Path(repo).resolve()
    for ref in evidence:
        if not isinstance(ref, dict):
            raise ValueError("Invalid evidence reference")
        path_text = text(ref.get("path"), "evidence path")
        path = (repo / path_text).resolve()
        if not path.is_relative_to(repo) or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Evidence must be a photograph artifact under repository")
        expected = text(ref.get("sha256"), "evidence sha256")
        if sha256(path) != expected:
            raise ValueError("Review evidence SHA-256 mismatch")
        signature = path.read_bytes()[:12]
        valid_photo = (signature.startswith(b"\x89PNG\r\n\x1a\n")
                       or signature.startswith(b"\xff\xd8")
                       or signature.startswith(b"RIFF") and signature[8:12] == b"WEBP")
        if not valid_photo:
            raise ValueError("Review photo artifact signature unsupported")
        text(ref.get("observation"), "evidence observation")
        frames = ref.get("frame_indices")
        if not isinstance(frames, list) or not frames or len(frames) != len(set(frames)):
            raise ValueError("Review photo requires explicit unique frame indices")
        covered.update(integer(f, "evidence frame") for f in frames)
    return covered


def validate_candidate(candidate, episodes, config, geometry, repo):
    """Validate source predicates without generating any new transition."""
    _, segment_intersection, signed_distance, _ = geometry_imports(repo)
    identity = config["input_identity"]
    diagnostic = candidate.get("diagnostic", {})
    if diagnostic.get("type") != "GEOMETRY_TRANSITION" or diagnostic.get("accepted_count_event") is not False:
        raise ValueError("Only retained measured geometry transitions are reviewable")
    track = integer(candidate.get("track_id"), "candidate track")
    episode_id = text(candidate.get("episode_id"), "candidate episode")
    episode = episodes.get(episode_id)
    if episode is None or episode.get("family") != "vehicle" or episode.get("track_id") != track:
        raise ValueError("Missing original vehicle measurement episode")
    if episode.get("source_identity") != identity:
        raise ValueError("Episode source identity mismatch")
    if diagnostic.get("episode_id") != episode_id or diagnostic.get("track_id") != track:
        raise ValueError("Diagnostic episode/track source mismatch")
    if diagnostic.get("geometry_id") != geometry.geometry_id:
        raise ValueError("Geometry identity mismatch")
    origin, start, end, confirm = (integer(diagnostic.get(k), k) for k in
        ("origin_frame", "crossing_frame_start", "crossing_frame_end", "confirmation_frame"))
    if not origin <= start < end <= confirm or diagnostic.get("frame_index") != confirm:
        raise ValueError("Invalid origin/crossing/confirmation order")
    support = candidate.get("measurement_support")
    if not isinstance(support, list) or [o.get("frame_index") for o in support] != list(range(origin, confirm + 1)):
        raise ValueError("Vehicle measurement support must be full and continuous")
    source_observations = {o["frame_index"]: o for o in episode["observations"]}
    if len(source_observations) != len(episode["observations"]):
        raise ValueError("Duplicate episode frame")
    for observation in support:
        frame = observation["frame_index"]
        if observation != source_observations.get(frame):
            raise ValueError("Candidate measurement does not match original episode")
        if (observation.get("track_id") != track or observation.get("emitted") is not True
                or observation.get("measurement_provenance") != "retained_phase_2_detection"
                or observation.get("class_name") not in VEHICLE_CATEGORIES):
            raise ValueError("Only raw emitted vehicle measurements support reviewed event")
        integer(observation.get("original_detection_index"), "source detection index")
        integer(observation.get("class_id"), "raw source class")
        number(observation.get("confidence"), "raw source confidence")
        if not point_equal(observation.get("point"), raw_bc(observation.get("raw_bbox"))):
            raise ValueError("Episode point is not original raw-bbox BC")
    category = candidate.get("category")
    members = candidate.get("vehicle_episode_ids", [episode_id])
    if not isinstance(members, list) or episode_id not in members or len(set(members)) != len(members):
        raise ValueError("Invalid vehicle episode group")
    histogram = Counter()
    for member in members:
        if member not in episodes or episodes[member].get("family") != "vehicle" or episodes[member].get("source_identity") != identity:
            raise ValueError("Broken grouped episode reference")
        histogram.update(o["class_name"] for o in episodes[member]["observations"])
    if (category not in VEHICLE_CATEGORIES or set(histogram) != {category}
            or dict(histogram) != candidate.get("vehicle_class_histogram")
            or {o["class_name"] for o in support} != {category}):
        raise ValueError("Full measured vehicle category conflict cannot be reviewed away")

    def source_observation(value, expected_frame=None):
        frame = integer(value.get("frame_index"), "geometry observation frame")
        if expected_frame is not None and frame != expected_frame:
            raise ValueError("Geometry observation frame mismatch")
        source = source_observations.get(frame)
        if source is None or not origin <= frame <= confirm:
            raise ValueError("Geometry measurement outside supported vehicle window")
        metadata = value.get("metadata", {})
        expected = {"track_id": track, "episode_id": episode_id,
                    **{k: identity[k] for k in ("video_sha256", "records_sha256", "variant", "parent_run_id")},
                    **{k: source[k] for k in ("original_detection_index", "raw_bbox", "class_id", "class_name", "confidence", "measurement_provenance")}}
        if any(metadata.get(k) != v for k, v in expected.items()) or not point_equal(value.get("point"), raw_bc(source["raw_bbox"])):
            raise ValueError("Geometry point/source box link mismatch")
        return source

    origin_observation = source_observation(diagnostic["origin_observation"], origin)
    crossing = diagnostic["crossing_evidence"]
    first, last = source_observation(crossing["start_observation"], start), source_observation(crossing["end_observation"], end)
    confirmations = diagnostic.get("confirmation_observations", [])
    c = config["confirmation_observations"]
    if len(confirmations) != c or [o.get("frame_index") for o in confirmations] != list(range(confirm - c + 1, confirm + 1)):
        raise ValueError("Confirmation measurements differ from explicit policy")
    confirmation_sources = [source_observation(o) for o in confirmations]
    if not confirmation_sources:
        raise ValueError("No opposite-side measured confirmation")
    if diagnostic.get("metadata") != confirmations[-1].get("metadata"):
        raise ValueError("Top-level diagnostic source differs from confirmation")
    if not point_equal(diagnostic.get("origin_point"), raw_bc(origin_observation["raw_bbox"])) or not point_equal(
            diagnostic.get("confirmation_point"), raw_bc(confirmation_sources[-1]["raw_bbox"])):
        raise ValueError("Diagnostic top-level raw BC mismatch")
    band = number(config["neutral_band_px"], "neutral band")

    def side(observation):
        point = raw_bc(observation["raw_bbox"])
        return geometry.side(point) if abs(signed_distance(point, geometry.p1, geometry.p2)) > max(band, 1e-9) else None

    initial_side, final_side = side(origin_observation), side(confirmation_sources[-1])
    if initial_side not in {"A", "B"} or final_side not in {"A", "B"} or initial_side == final_side:
        raise ValueError("Measured origin/opposite ROI evidence absent")
    if (diagnostic.get("origin_side"), diagnostic.get("destination_side"), diagnostic.get("direction")) != (
            initial_side, final_side, initial_side + "_TO_" + final_side):
        raise ValueError("Geometry direction metadata mismatch")
    if any(side(o) != final_side for o in confirmation_sources):
        raise ValueError("Opposite-side confirmation is not consecutive")
    required_frames = {origin, start, end, confirm}
    method = crossing.get("method")
    if method == "consecutive_measured_segment":
        if end != start + 1:
            raise ValueError("Crossing through gap forbidden")
        intersection = segment_intersection(raw_bc(first["raw_bbox"]), raw_bc(last["raw_bbox"]), geometry.p1, geometry.p2)
        if intersection["kind"] != "proper":
            raise ValueError("Endpoint/touch-only geometry cannot be reviewed away")
    elif method == "measured_touch_then_opposite_sign":
        touch_first = source_observation(crossing["first_touch_observation"], start + 1)
        source_observation(crossing["last_touch_observation"], end - 1)
        for frame in range(start + 1, end):
            touch_point = raw_bc(source_observations[frame]["raw_bbox"])
            if abs(signed_distance(touch_point, geometry.p1, geometry.p2)) > 1e-9 or segment_intersection(
                    raw_bc(first["raw_bbox"]), touch_point, geometry.p1, geometry.p2)["kind"] != "touch":
                raise ValueError("Invalid measured finite-line contact interval")
        intersection = segment_intersection(raw_bc(first["raw_bbox"]), raw_bc(touch_first["raw_bbox"]), geometry.p1, geometry.p2)
        if intersection["kind"] != "touch":
            raise ValueError("Invalid first measured contact")
        required_frames.update(range(start + 1, end))
    else:
        raise ValueError("Unsupported measured crossing method")
    recorded = crossing.get("intersection", {})
    if recorded.get("kind") != intersection["kind"] or not point_equal(recorded.get("point"), intersection.get("point")) or not point_equal(
            diagnostic.get("crossing_point"), intersection.get("point")):
        raise ValueError("Retained finite-segment crossing evidence inconsistent")
    for fraction in ("t", "u"):
        if not math.isclose(number(recorded.get(fraction), fraction), intersection[fraction], rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("Retained intersection fraction differs from source")
    entry = signed_distance(raw_bc(first["raw_bbox"]), geometry.p1, geometry.p2)
    exit_distance = signed_distance(raw_bc(last["raw_bbox"]), geometry.p1, geometry.p2)
    if entry * exit_distance >= 0 or (crossing.get("entry_sign"), crossing.get("exit_sign")) != (
            1 if entry > 0 else -1, 1 if exit_distance > 0 else -1):
        raise ValueError("No opposite measured crossing signs")
    return required_frames


def build_reviewed_snapshot(machine_decisions, episode_rows, machine_events, config, reviews, *, repo, geometry):
    """Pure reviewed overlay apart from reading hash-bound review photos."""
    _, _, _, aggregate_events = geometry_imports(repo)
    if config.get("policy_version") != "phase6_option_b_v1" or config.get("metric") != "passage":
        raise ValueError("Unsupported source counting policy")
    identity = config.get("input_identity")
    if reviews.get("source_identity") != identity or any(k not in identity for k in IDENTITY_FIELDS):
        raise ValueError("Review input source identity mismatch")
    original = deepcopy(machine_decisions)
    decisions = deepcopy(machine_decisions)
    by_id = {text(c.get("candidate_id"), "candidate_id"): c for c in decisions}
    if len(by_id) != len(decisions):
        raise ValueError("Duplicate original candidate ID")
    episodes = {text(e.get("episode_id"), "episode_id"): e for e in episode_rows}
    if len(episodes) != len(episode_rows):
        raise ValueError("Duplicate source episode ID")
    rows = reviews.get("decisions")
    if not isinstance(rows, list):
        raise ValueError("Review decisions must be explicit list")
    review_by_id = {}
    confirmed = []
    for row in rows:
        candidate_id = text(row.get("candidate_id"), "review candidate_id")
        if candidate_id not in by_id or candidate_id in review_by_id:
            raise ValueError("Review must bind exactly one existing candidate, without duplicate/conflicting rows")
        text(row.get("reason"), "review reason")
        text(row.get("reviewer"), "reviewer")
        disposition = row.get("disposition")
        if disposition not in {"CONFIRM_PASSAGE", "HOLD"}:
            raise ValueError("Unsupported review disposition")
        covered = evidence_validate(row, repo)
        candidate = by_id[candidate_id]
        review_id = logical_id("rv6br_", {"source_identity": identity, "candidate_id": candidate_id, "review": row})
        review_by_id[candidate_id] = row
        candidate["original_machine_decision"] = deepcopy(original[next(i for i, c in enumerate(original) if c["candidate_id"] == candidate_id)])
        candidate["review_id"] = review_id
        candidate["review_decision"] = deepcopy(row)
        candidate["review_policy"] = POLICY
        candidate["manual_review_applied"] = True
        if disposition == "HOLD":
            candidate.update({"status": "pending_review", "accepted_count_event": False, "event_id": None,
                              "review_recorded_category": row.get("category")})
            candidate["reasons"] = sorted(set(candidate.get("reasons", []) + ["EXPLICIT_REVIEW_HOLD"]))
            continue
        if any(row.get(k) is not True for k in ("unit_confirmed", "category_confirmed", "identity_confirmed")):
            raise ValueError("Positive unit/category/identity review required")
        remaining = (set(candidate.get("reasons", [])) | set(candidate.get("hard_block_reasons", []))) - REVIEWABLE_REASONS
        if remaining:
            raise ValueError("Review cannot promote non-association hard block: " + ",".join(sorted(remaining)))
        required = validate_candidate(candidate, episodes, config, geometry, repo)
        if not required <= covered:
            raise ValueError("Review photo evidence misses origin/contact/crossing/confirmation frame")
        if row.get("category") != candidate.get("category"):
            raise ValueError("Manual category differs from full measured vehicle class history")
        candidate["physical_unit_id"] = text(row.get("physical_unit_id"), "review physical unit")
        candidate["passage_id"] = text(row.get("passage_id"), "review passage")
        candidate["review_resolved_association_reasons"] = sorted((set(candidate.get("reasons", [])) | set(candidate.get("hard_block_reasons", []))) & REVIEWABLE_REASONS)
        candidate["reasons"], candidate["hard_block_reasons"] = [], []
        confirmed.append(candidate)

    # Reuse untouched machine accepted payloads verbatim; never append the old
    # full snapshot to a new reviewed snapshot.
    events = []
    seen_machine_candidates, seen_machine_event_ids = set(), set()
    for event in machine_events:
        candidate_id = text(event.get("candidate_id"), "machine event candidate")
        if candidate_id not in by_id or candidate_id in seen_machine_candidates or event.get("event_id") in seen_machine_event_ids:
            raise ValueError("Machine event source candidate/event identity invalid")
        seen_machine_candidates.add(candidate_id)
        seen_machine_event_ids.add(event.get("event_id"))
        source = next(c for c in original if c["candidate_id"] == candidate_id)
        if (event.get("type") != "CountEvent" or event.get("status") != "accepted" or event.get("accepted_count_event") is not True
                or source.get("status") != "accepted" or source.get("accepted_count_event") is not True
                or source.get("event_id") != event.get("event_id") or event.get("source_identity") != identity
                or source.get("category") != event.get("category") or source["diagnostic"]["direction"] != event.get("direction")
                or event.get("geometry_evidence") != source["diagnostic"] or event.get("measurement_support") != source.get("measurement_support")):
            raise ValueError("Machine accepted event does not match retained decision")
        if source.get("reasons") or source.get("hard_block_reasons"):
            raise ValueError("Machine event has unresolved reasons")
        validate_candidate(source, episodes, config, geometry, repo)
        if candidate_id not in review_by_id:
            events.append(deepcopy(event))
    if any(c.get("accepted_count_event") is True and c["candidate_id"] not in seen_machine_candidates for c in original):
        raise ValueError("Original accepted candidate lacks typed event")

    groups = defaultdict(list)
    for candidate in confirmed:
        groups[(candidate["physical_unit_id"], candidate["passage_id"])].append(candidate)
    per_unit_passages = defaultdict(set)
    for unit, passage in groups:
        per_unit_passages[unit].add(passage)
    if any(len(passages) > 1 for passages in per_unit_passages.values()):
        raise ValueError("This overlay cannot promote additional genuine-return episodes")
    semantic = {key: deepcopy(config[key]) for key in SEMANTIC_POLICY_FIELDS if key in config}
    policy_id = logical_id("cfg6br_", {"source_identity": identity, "source_policy": semantic, "review_overlay_policy": POLICY})
    for (unit, passage), members in sorted(groups.items()):
        if len({c["category"] for c in members}) != 1 or len({c["diagnostic"]["direction"] for c in members}) != 1:
            raise ValueError("Same physical passage members disagree on category/direction")
        if any(e.get("physical_unit_id") == unit for e in events):
            raise ValueError("Manual unit conflicts with unreviewed existing machine unit")
        representative = min(members, key=lambda c: tuple(c["diagnostic"][key] for key in (
            "crossing_frame_start", "crossing_frame_end", "confirmation_frame", "origin_frame")) + (c["track_id"], c["candidate_id"]))
        event_id = logical_id("ce6br_", {"source_identity": identity, "policy_identity": policy_id,
                                      "physical_unit_id": unit, "passage_id": passage})
        for candidate in members:
            candidate.update({"status": "accepted" if candidate is representative else "duplicate_suppressed",
                              "event_id": event_id, "accepted_count_event": candidate is representative,
                              "duplicate_role": "representative" if candidate is representative else "same_passage_support"})
        diagnostic = representative["diagnostic"]
        events.append({"type": "CountEvent", "accepted_count_event": True, "status": "accepted",
            "event_id": event_id, "candidate_id": representative["candidate_id"],
            "physical_unit_id": unit, "passage_id": passage, "category": representative["category"],
            "direction": diagnostic["direction"], "track_id": representative["track_id"],
            "vehicle_measurement_episode_id": representative["episode_id"],
            "source_identity": deepcopy(identity), "policy_identity": policy_id,
            "geometry_evidence": deepcopy(diagnostic), "measurement_support": deepcopy(representative["measurement_support"]),
            "vehicle_episode_ids": sorted({c["episode_id"] for c in members}),
            "component_episode_ids": sorted({e for c in members for e in c.get("component_episode_ids", [])}),
            "same_passage_candidate_ids": sorted(c["candidate_id"] for c in members),
            "source_episode_references": [{"candidate_id": c["candidate_id"], "episode_id": c["episode_id"], "track_id": c["track_id"],
                "origin_frame": c["diagnostic"]["origin_frame"], "crossing_frame_start": c["diagnostic"]["crossing_frame_start"],
                "crossing_frame_end": c["diagnostic"]["crossing_frame_end"], "confirmation_frame": c["diagnostic"]["confirmation_frame"]}
                for c in sorted(members, key=lambda c: c["candidate_id"])],
            "review_references": [{"candidate_id": c["candidate_id"], "review_id": c["review_id"],
                                   "review": deepcopy(c["review_decision"])} for c in sorted(members, key=lambda c: c["candidate_id"])],
            "original_automatic_identity_evidence": [{"candidate_id": c["candidate_id"],
                "machine_decision": deepcopy(c["original_machine_decision"])} for c in sorted(members, key=lambda c: c["candidate_id"])],
            "manual_review_applied": True, "automatic_acceptance": False,
            "claim_type": "EXPLICIT_REVIEWED_PASSAGE_OVERLAY_NOT_AUTOMATIC_B_SUCCESS_OR_GROUND_TRUTH",
            "appearance_features_used": False, "execution_semantics": "offline_review_of_retained_outputs",
            "is_causal_online_decision": False})
    events.sort(key=lambda e: e["event_id"])
    aggregate = aggregate_events(events)
    report = {"claim_type": "EXECUTED_REVIEWED_OUTPUT_OVERLAY_NOT_AUTOMATIC_RESOLVER_RESULT",
        "review_policy": POLICY, "source_identity": deepcopy(identity), "source_policy_identity": policy_id,
        "reviewed_candidates": len(rows), "manual_confirmation_candidates": len(confirmed),
        "manual_confirmed_physical_passages": len(groups), "preserved_machine_accepted_events": len(events) - len(groups),
        "accepted_events": aggregate["total"], "decision_status_counts": dict(sorted(Counter(c["status"] for c in decisions).items())),
        "original_machine_artifacts_modified": False, "model_geometry_resolver_rerun": False,
        "formal_ground_truth": False, "whole_video_traffic_result": False,
        "new_automatic_success_claimed": False}
    if sum(aggregate["by_category"].values()) != len(events) or sum(aggregate["by_direction"].values()) != len(events):
        raise AssertionError("Reviewed aggregate does not reconcile")
    if machine_decisions != original:
        raise AssertionError("Input machine decisions were mutated")
    return {"resolved_decisions": decisions, "accepted_events": events, "aggregate": aggregate, "report": report}


def read_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def write_jsonl(path, values):
    body = "".join(canonical(value) + "\n" for value in values).encode()
    Path(path).write_bytes(gzip.compress(body, mtime=0))


def execute(repo, run, review_path, output=None):
    repo, run, review_path = Path(repo).resolve(), Path(run).resolve(), Path(review_path).resolve()
    output = Path(output).resolve() if output else run / "reviewed"
    if output == run or output in run.parents or output == review_path.parent:
        raise ValueError("Output cannot overwrite source run or review directory")
    source_paths = {name: run / name for name in ("machine_decisions.jsonl.gz", "episodes.jsonl.gz", "accepted_events.jsonl.gz", "configuration_input.json", "report.json", "execution_manifest.json")}
    before = {name: sha256(path) for name, path in source_paths.items()}
    config, review = json.loads(source_paths["configuration_input.json"].read_text()), json.loads(review_path.read_text())
    source_report = json.loads(source_paths["report.json"].read_text())
    if review.get("source_run_id") != source_report.get("run_id") or review.get("source_run_id") != run.name:
        raise ValueError("Review binds another source run")
    if review.get("source_machine_decisions_sha256") != before["machine_decisions.jsonl.gz"]:
        raise ValueError("Review binds another machine decision artifact")
    manifest = json.loads(source_paths["execution_manifest.json"].read_text())
    entries = {item["path"]: item for item in manifest["artifacts"]}
    for name in ("machine_decisions.jsonl.gz", "episodes.jsonl.gz", "accepted_events.jsonl.gz", "configuration_input.json"):
        if name not in entries or entries[name]["sha256"] != before[name] or entries[name]["size_bytes"] != source_paths[name].stat().st_size:
            raise ValueError("Source artifact differs from retained execution manifest")
    identity = config["input_identity"]
    Geometry, _, _, _ = geometry_imports(repo)
    geometry_candidates = [path for path in (repo / "docs/evidence/phase_5/accepted_geometry").glob("*.json") if sha256(path) == identity["geometry_sha256"]]
    if len(geometry_candidates) != 1:
        raise ValueError("Exactly one retained accepted geometry must match source hash")
    geometry = Geometry.from_draft(geometry_candidates[0], identity["width"], identity["height"])
    result = build_reviewed_snapshot(read_jsonl(source_paths["machine_decisions.jsonl.gz"]), read_jsonl(source_paths["episodes.jsonl.gz"]),
        read_jsonl(source_paths["accepted_events.jsonl.gz"]), config, review, repo=repo, geometry=geometry)
    if any(sha256(source_paths[name]) != value for name, value in before.items()):
        raise AssertionError("Original machine source artifact changed during postprocessing")
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "resolved_decisions.jsonl.gz", result["resolved_decisions"])
    write_jsonl(output / "accepted_events.jsonl.gz", result["accepted_events"])
    write_json(output / "aggregate.json", result["aggregate"])
    result["report"].update({"source_run_id": run.name, "source_artifact_sha256": before,
        "review_input_path": str(review_path.relative_to(repo)) if review_path.is_relative_to(repo) else str(review_path),
        "review_input_sha256": sha256(review_path), "method_sha256": sha256(__file__)})
    write_json(output / "report.json", result["report"])
    (output / "review_input.json").write_bytes(review_path.read_bytes())
    artifacts = [output / name for name in ("resolved_decisions.jsonl.gz", "accepted_events.jsonl.gz", "aggregate.json", "report.json", "review_input.json")]
    write_json(output / "execution_manifest.json", {"claim_type": "REVIEWED_OVERLAY_REPRODUCIBILITY_MANIFEST",
        "source_run_id": run.name, "source_artifact_sha256": before, "method_sha256": sha256(__file__),
        "artifacts": [{"path": p.name, "sha256": sha256(p), "size_bytes": p.stat().st_size} for p in artifacts],
        "accepted_unique_event_subtotal": result["aggregate"]["total"], "automatic_acceptance_claimed": False})
    return result


def self_test(repo):
    """Small synthetic fixtures; they do not label or process any real video."""
    import base64
    import tempfile
    Geometry, segment_intersection, _, _ = geometry_imports(repo)
    geometry = Geometry((0, 50), (100, 50), ((0, 0), (100, 0), (100, 50), (0, 50)),
        ((0, 50), (100, 50), (100, 100), (0, 100)), 100, 100, "fixture_geometry")
    identity = {"video_sha256": "a" * 64, "records_sha256": "b" * 64, "geometry_sha256": "c" * 64,
        "variant": "reid_on", "width": 100, "height": 100, "parent_run_id": "synthetic_fixture_parent"}
    config = {"policy_version": "phase6_option_b_v1", "metric": "passage", "input_identity": identity,
        "neutral_band_px": 0, "confirmation_observations": 1, "grouping_enabled": True, "scope": {"synthetic_fixture": True}, "association": {}}

    def fixture(track=1, heights=(70, 60, 40), touch=False):
        episode_id, candidate_id = f"fixture_episode_{track}", f"fixture_candidate_{track}"
        observations = [{"frame_index": f, "track_id": track, "emitted": True,
            "measurement_provenance": "retained_phase_2_detection", "class_name": "motorcycle",
            "class_id": 3, "confidence": 0.9, "original_detection_index": track - 1,
            "raw_bbox": [45, y - 10, 55, y], "point": [50, y]} for f, y in enumerate(heights)]
        episode = {"episode_id": episode_id, "track_id": track, "family": "vehicle", "source_identity": deepcopy(identity),
            "observations": deepcopy(observations), "start_frame": 0, "end_frame": len(observations) - 1}

        def observed(source):
            metadata = {"track_id": track, "episode_id": episode_id,
                **{k: identity[k] for k in ("video_sha256", "records_sha256", "variant", "parent_run_id")},
                **{k: source[k] for k in ("original_detection_index", "raw_bbox", "class_id", "class_name", "confidence", "measurement_provenance")}}
            return {"frame_index": source["frame_index"], "point": source["point"], "metadata": metadata}
        origin, start, end = observed(observations[0]), observed(observations[0] if touch else observations[-2]), observed(observations[-1])
        intersection_end = observed(observations[1]) if touch else end
        crossing = {"start_observation": start, "end_observation": end,
            "method": "measured_touch_then_opposite_sign" if touch else "consecutive_measured_segment",
            "intersection": segment_intersection(start["point"], intersection_end["point"], geometry.p1, geometry.p2),
            "entry_sign": 1, "exit_sign": -1}
        if touch:
            crossing.update(first_touch_observation=observed(observations[1]), last_touch_observation=observed(observations[-2]))
        diagnostic = {"type": "GEOMETRY_TRANSITION", "accepted_count_event": False, "track_id": track,
            "episode_id": episode_id, "geometry_id": geometry.geometry_id, "origin_frame": 0,
            "crossing_frame_start": start["frame_index"], "crossing_frame_end": end["frame_index"],
            "confirmation_frame": end["frame_index"], "frame_index": end["frame_index"],
            "origin_observation": origin, "origin_point": origin["point"], "confirmation_point": end["point"],
            "origin_side": "B", "destination_side": "A", "direction": "B_TO_A",
            "confirmation_observations": [end], "metadata": end["metadata"],
            "crossing_point": crossing["intersection"]["point"], "crossing_evidence": crossing}
        candidate = {"candidate_id": candidate_id, "episode_id": episode_id, "track_id": track,
            "status": "pending_review", "reasons": ["NO_POSITIVE_PHYSICAL_IDENTITY_EVIDENCE"], "hard_block_reasons": [],
            "diagnostic": diagnostic, "measurement_support": deepcopy(observations), "category": "motorcycle",
            "vehicle_episode_ids": [episode_id], "vehicle_class_histogram": {"motorcycle": len(observations)},
            "component_episode_ids": [], "accepted_count_event": False, "event_id": None}
        return candidate, episode

    checks = []
    with tempfile.TemporaryDirectory(dir="/tmp") as temp:
        root = Path(temp)
        (root / "notebooks").symlink_to(Path(repo).resolve() / "notebooks", target_is_directory=True)
        photo = root / "fixture.png"
        photo.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jz1kAAAAASUVORK5CYII="))
        candidate, episode = fixture()
        row = {"candidate_id": candidate["candidate_id"], "disposition": "CONFIRM_PASSAGE",
            "physical_unit_id": "synthetic_unit", "passage_id": "synthetic_passage", "category": "motorcycle",
            "unit_confirmed": True, "category_confirmed": True, "identity_confirmed": True,
            "reason": "Synthetic software fixture only", "reviewer": "SYNTHETIC_FIXTURE",
            "evidence": [{"path": "fixture.png", "sha256": sha256(photo), "frame_indices": [0, 1, 2],
                          "observation": "Synthetic fixture, not real video evidence"}]}
        review = {"source_identity": deepcopy(identity), "decisions": [row]}

        def call(candidates=None, episodes=None, events=None, reviewed=None):
            return build_reviewed_snapshot(candidates if candidates is not None else [candidate],
                episodes if episodes is not None else [episode], events or [], config,
                reviewed if reviewed is not None else review, repo=root, geometry=geometry)

        accepted = call()
        checks += [("typed_event_acceptance", accepted["aggregate"]["total"] == 1 and accepted["accepted_events"][0]["type"] == "CountEvent"),
            ("original_input_immutable", candidate["status"] == "pending_review" and candidate["event_id"] is None),
            ("deterministic_idempotence", call() == accepted)]
        mutations = [
            ("hard_gap_not_promoted", lambda c, r: c["hard_block_reasons"].append("AMBIGUOUS_GAP")),
            ("wrong_category_not_promoted", lambda c, r: r["decisions"][0].update(category="car")),
            ("missing_frame_evidence", lambda c, r: r["decisions"][0]["evidence"][0].update(frame_indices=[1, 2])),
            ("wrong_photo_hash", lambda c, r: r["decisions"][0]["evidence"][0].update(sha256="f" * 64)),
            ("positive_identity_required", lambda c, r: r["decisions"][0].update(identity_confirmed=False)),
            ("invented_bottom_center", lambda c, r: c["measurement_support"][0].update(point=[0, 0])),
            ("unknown_candidate", lambda c, r: r["decisions"][0].update(candidate_id="absent")),
            ("duplicate_review_rows", lambda c, r: r["decisions"].append(deepcopy(r["decisions"][0]))),
            ("wrong_source_identity", lambda c, r: r["source_identity"].update(video_sha256="d" * 64)),
            ("return_hard_block_preserved", lambda c, r: c["reasons"].append("GENUINE_RETURN_REVIEW_REQUIRED")),
            ("unknown_context_hard_block", lambda c, r: c["hard_block_reasons"].append("UNKNOWN_RAW_COMPETITORS")),
            ("unsupported_disposition", lambda c, r: r["decisions"][0].update(disposition="FORCE")),
        ]
        for name, mutate in mutations:
            mutated, reviewed = deepcopy(candidate), deepcopy(review)
            mutate(mutated, reviewed)
            try:
                call([mutated], reviewed=reviewed)
                passed = False
            except ValueError:
                passed = True
            checks.append((name, passed))
        held = deepcopy(review)
        held["decisions"][0]["disposition"] = "HOLD"
        checks.append(("hold_excluded", call(reviewed=held)["aggregate"]["total"] == 0))
        candidate2, episode2 = fixture(track=2)
        two_reviews = deepcopy(review)
        two_row = deepcopy(row)
        two_row["candidate_id"] = candidate2["candidate_id"]
        two_reviews["decisions"].append(two_row)
        duplicate = call([candidate2, candidate], [episode2, episode], reviewed=two_reviews)
        checks += [("same_passage_deduplicated", duplicate["aggregate"]["total"] == 1),
                   ("deterministic_representative_order", duplicate["accepted_events"][0]["track_id"] == 1),
                   ("all_duplicate_sources_retained", len(duplicate["accepted_events"][0]["same_passage_candidate_ids"]) == 2)]
        two_reviews["decisions"][1]["passage_id"] = "synthetic_second_passage"
        try:
            call([candidate, candidate2], [episode, episode2], reviewed=two_reviews)
            return_rejected = False
        except ValueError:
            return_rejected = True
        checks.append(("manual_return_not_silently_added", return_rejected))
        machine_candidate = deepcopy(accepted["resolved_decisions"][0])
        machine_event = deepcopy(accepted["accepted_events"][0])
        machine_event["fixture_untouched_payload"] = "preserve this exact payload"
        empty_review = {"source_identity": deepcopy(identity), "decisions": []}
        reused = call([machine_candidate], events=[machine_event], reviewed=empty_review)
        checks.append(("untouched_machine_event_reused_verbatim", reused["accepted_events"] == [machine_event]))
        replaced = call([machine_candidate], events=[machine_event])
        checks.append(("explicit_review_replaces_not_appends", replaced["aggregate"]["total"] == 1))
        touched, touched_episode = fixture(heights=(70, 50, 50, 40), touch=True)
        touch_review = deepcopy(review)
        touch_review["decisions"][0]["evidence"][0]["frame_indices"] = [0, 1, 2, 3]
        checks.append(("full_measured_contact_interval_accepted", call([touched], [touched_episode], reviewed=touch_review)["aggregate"]["total"] == 1))
        touch_review["decisions"][0]["evidence"][0]["frame_indices"] = [0, 1, 3]
        try:
            call([touched], [touched_episode], reviewed=touch_review)
            contact_rejected = False
        except ValueError:
            contact_rejected = True
        checks.append(("missing_contact_frame_not_accepted", contact_rejected))
    result = {"claim_type": "SYNTHETIC_REVIEW_OVERLAY_SOFTWARE_CHECKS_NOT_VIDEO_EVIDENCE",
        "passed": sum(passed for _, passed in checks), "failed": sum(not passed for _, passed in checks),
        "checks": [{"check": name, "pass": passed} for name, passed in checks]}
    if result["failed"]:
        raise AssertionError(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(args.repo), indent=2))
    else:
        if args.run is None or args.reviews is None:
            parser.error("--run and --reviews are required without --self-test")
        result = execute(args.repo, args.run, args.reviews, args.output)
        print(json.dumps({"aggregate": result["aggregate"], "report": result["report"]}, indent=2))
