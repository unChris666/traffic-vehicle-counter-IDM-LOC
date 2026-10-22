"""Apply source-bound P1 adjudications to a separate reviewed branch.

The immutable B v4 overlay validator checks retained pixel receipts. This
adapter adds exact cache-anchor checks and typed identity provenance while
preserving every raw measurement. Reviews never create missing observations.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re

import phase_8_b_v4_batch as previous
import phase_8_b_v6_identity as identity


IDENTITY_TYPES = {"SAME_VEHICLE", "SPLIT_IDENTITY"}
RAW_KEYS = ("frame_index", "track_id", "original_detection_index", "raw_bbox",
            "class_name", "class_id", "confidence", "measurement_provenance",
            "observed", "emitted")


def _require(value, message):
    if not value:
        raise ValueError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _file_hash(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _family(item):
    return previous.previous._family(item["class_name"])


def _matches(scope, item, frame):
    return (scope["track_id"] == item["track_id"]
            and scope["raw_family"] == _family(item)
            and scope["start_frame"] <= frame <= scope["end_frame"])


def _authority(review, root, guarded):
    authority = review.get("reviewed_decision_authority", {})
    if review.get("claim_type") != "USER_REVIEW" and not authority:
        return
    _require(authority.get("kind") == "EXPLICIT_USER_INSTRUCTION",
             "USER_REVIEW requires an explicit retained user instruction")
    path = (root / authority.get("path", "")).resolve()
    _require(path.is_relative_to(root) and path.is_file()
             and _file_hash(path) == authority.get("sha256"),
             "User decision authority is missing or differs")
    if review.get("claim_type") == "USER_REVIEW":
        excerpt = authority.get("exact_supporting_excerpt")
        _require(isinstance(excerpt, str) and bool(excerpt)
                 and excerpt in path.read_text(), "User review lacks its exact authority excerpt")
    guarded.append({"path": str(path), "sha256": _file_hash(path)})


def _validated_reviews(overlay, source_identity, video_id, frame_count, root, guarded):
    normalized = deepcopy(overlay)
    originals = {r["review_id"]: r for v in overlay.get("videos", [])
                 for r in v.get("reviews", [])}
    _require(len(originals) == sum(len(v.get("reviews", [])) for v in overlay.get("videos", [])),
             "Duplicate review IDs")
    occupied = defaultdict(list)
    for video in normalized.get("videos", []):
        for review in video.get("reviews", []):
            _authority(review, root, guarded)
            if review.get("claim_type") == "USER_REVIEW":
                # Reuse validation, never relabel the retained decision origin.
                review["claim_type"] = "ADJUDICATED_AI_PIXELS_REVIEW"
                review["human_confirmation_status"] = "NOT_NEWLY_ADJUDICATED_BY_USER"
            if review.get("type") in IDENTITY_TYPES:
                for scope in review.get("scopes", []):
                    key = scope.get("track_id"), scope.get("raw_family")
                    start, end = scope.get("start_frame"), scope.get("end_frame")
                    _require(type(start) is int and type(end) is int, "Explicit identity scope required")
                    _require(all(end < old[0] or start > old[1] for old in occupied[key]),
                             "Overlapping identity adjudications are forbidden")
                    occupied[key].append((start, end))
    jobs = [{"video_id": video_id, "b_v2_source_identity": source_identity,
             "metadata": {"frame_count": frame_count}}]
    validated = previous.validate_overlay(normalized, jobs, root, guarded)
    _require(set(validated) == {video_id}, "P1 overlay must name exactly the supplied source video")
    reviews = validated[video_id].get("reviews", [])
    for review in reviews:
        original = originals[review["review_id"]]
        review["claim_type"] = original["claim_type"]
        review["human_confirmation_status"] = original.get("human_confirmation_status")
        if "reviewed_decision_authority" in original:
            review["reviewed_decision_authority"] = deepcopy(original["reviewed_decision_authority"])
        _require(all(any(scope["start_frame"] <= frame <= scope["end_frame"]
                         for frame in review["confirmed_frames"])
                     for scope in review["scopes"]),
                 "Every bounded scope needs its own reviewed source anchor")
    return reviews


def _anchor_records(path, source_identity, anchors):
    _require(_file_hash(path) == source_identity["records_sha256"],
             "Review must use the exact frozen source cache")
    found = {}
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            frame = row.get("frame_index")
            if frame not in anchors:
                continue
            _require(frame not in found, "Repeated cache anchor frame")
            _require(all(row.get(k) == source_identity[k]
                         for k in ("video_sha256", "width", "height")),
                     "Anchor cache belongs to a different video")
            found[frame] = row
    _require(set(found) == anchors, "Reviewed source frame is missing from frozen cache")
    return found


def prepare_reviewed_frames(frames, overlay, *, source_identity, repo_root,
                            source_records_path, video_id="weekday_siang", frame_count=None,
                            overlay_sha256=None, branch="review_assisted"):
    """Return copied reviewed frames plus application proof; never machine data.

    ``frames`` must be the unchanged source adapter output before B v6 identity
    preparation. The caller retains/guards the manifest file if passing its
    file SHA; the semantic input digest is recorded independently here.
    """
    _require(branch == "review_assisted", "Machine branch cannot apply P1 adjudications")
    root, copied = Path(repo_root).resolve(), deepcopy(list(frames))
    _require(copied, "Review needs actual source frames")
    frame_ids = [row["frame_index"] for row in copied]
    _require(all(type(f) is int and f >= 0 for f in frame_ids)
             and frame_ids == sorted(set(frame_ids)), "Source frames must be unique and ordered")
    frame_count = max(frame_ids) + 1 if frame_count is None else frame_count
    _require(type(frame_count) is int and max(frame_ids) < frame_count, "Invalid source frame count")
    semantic = _digest(overlay)
    manifest_digest = semantic if overlay_sha256 is None else overlay_sha256
    _require(isinstance(manifest_digest, str) and re.fullmatch(r"[0-9a-f]{64}", manifest_digest),
             "Review manifest SHA must be explicit SHA256")
    guarded = []
    reviews = _validated_reviews(overlay, source_identity, video_id, frame_count, root, guarded)
    anchors = {f for review in reviews for f in review["confirmed_frames"]}
    records = _anchor_records(source_records_path, source_identity, anchors)
    guarded.append({"path": str(Path(source_records_path).resolve()),
                    "sha256": source_identity["records_sha256"]})
    source = {(row["frame_index"], item["track_id"]): item
              for row in copied for item in row.get("observations", [])}
    _require(len(source) == sum(len(row.get("observations", [])) for row in copied),
             "Repeated raw track within a source frame")
    counts, matched, assignments = Counter(), set(), []
    scope_counts = Counter()
    for review in reviews:
        rid = review["review_id"]
        for frame in review["confirmed_frames"]:
            proof = review["_pixel_anchor_proofs"][frame]
            record = records[frame]
            _require(record.get("detector_input_frame_pixel_sha256") == proof["raw_bgr_pixel_sha256"],
                     "Review pixel receipt differs from actual source cache frame")
            actual = {item["track_id"]: item for item in record["emitted_tracks"]}
            anchor_matches = 0
            for scope in review["scopes"]:
                item = source.get((frame, scope["track_id"]))
                if item is None or not _matches(scope, item, frame):
                    continue
                cached = actual.get(item["track_id"], {})
                _require(all(cached.get(k) == item.get(k) for k in
                             ("raw_bbox", "class_name", "original_detection_index")),
                         "Review anchor differs from actual source measurement")
                anchor_matches += 1
                matched.add((rid, item["track_id"], frame))
            _require(anchor_matches, "Confirmed review frame has no measured target in its own scope")
    for row in copied:
        frame = row["frame_index"]
        for item in row.get("observations", []):
            original = deepcopy(item)
            for review in reviews:
                for si, scope in enumerate(review["scopes"]):
                    if not _matches(scope, item, frame):
                        continue
                    rid, kind = review["review_id"], review["type"]
                    before = {k: deepcopy(item.get(k)) for k in
                              ("unit_id", "episode_id", "role", "resolved_class_name",
                               "association_verified", "association_id", "component_of_unit_id")}
                    if kind in IDENTITY_TYPES:
                        unit = scope.get("physical_unit_id", review.get("physical_unit_id"))
                        episode = scope.get("episode_id", review.get("episode_id"))
                        if identity._identity_review_proof(item):
                            _require((unit, episode) == (item["unit_id"], item.get("episode_id")),
                                     "Conflicting positive identity review requires explicit replacement")
                        item.update(unit_id=unit, episode_id=episode,
                                    association_verified=kind == "SAME_VEHICLE",
                                    association_id=rid if kind == "SAME_VEHICLE" else None)
                    elif kind == "COMPONENT_OF":
                        _require(item.get("role") != "pedestrian", "Contradictory positive role review")
                        item.update(role="rider", component_of_unit_id=review["component_of_unit_id"],
                                    role_scope_id=rid)
                    elif kind == "PEDESTRIAN_ROLE":
                        _require(item.get("role") != "rider", "Contradictory positive role review")
                        item.update(role="pedestrian", resolved_class_name="pedestrian",
                            unit_id=review.get("physical_unit_id", f"reviewed-pedestrian:{rid}"),
                            episode_id=review.get("episode_id", f"reviewed-role:{rid}"), role_scope_id=rid)
                    resolved = scope.get("resolved_class_name", review.get("resolved_class_name"))
                    if resolved:
                        item["resolved_class_name"] = resolved
                    item.setdefault("review_refs", []).append({"review_id": rid,
                        "reviews_sha256": manifest_digest, "source_frame": frame,
                        "track_id": item["track_id"], "review_type": kind,
                        "claim_type": review["claim_type"],
                        "decision_origin": "HUMAN_REVIEW" if review["claim_type"] == "USER_REVIEW"
                            else "AI_ASSISTED_REVIEW_NOT_NEW_HUMAN_CONFIRMATION",
                        "scope_extent_is_engineering_assumption": True})
                    counts[rid] += 1
                    scope_counts[(rid, si)] += 1
                    assignments.append({"frame_index": frame, "track_id": item["track_id"],
                        "original_detection_index": item["original_detection_index"],
                        "raw_bbox": deepcopy(item["raw_bbox"]), "review_id": rid, "review_type": kind,
                        "before": before, "after": {k: deepcopy(item.get(k)) for k in before},
                        "claim_type": review["claim_type"], "source_measurement_unchanged": True})
            _require(all(item.get(k) == original.get(k) for k in RAW_KEYS),
                     "A review cannot modify raw measurements")
    _require(all(scope_counts[(r["review_id"], i)] > 0
                 for r in reviews for i, _ in enumerate(r["scopes"])),
             "Review scope did not match a measured observation")
    audit = {"applied_measurements": dict(sorted(counts.items())),
        "matched_reviewed_anchors": [{"review_id": rid, "track_id": track, "frame_index": frame}
                                     for rid, track, frame in sorted(matched)],
        "source_links_checked": True, "raw_measurements_modified": False,
        "new_observations_created": 0, "review_assignments": assignments}
    return {"frames": copied, "application_audit": audit, "guarded_inputs": guarded,
        "provenance": {"schema_version": "phase8_b_v8_review_application_v1", "branch": branch,
            "review_manifest_sha256": manifest_digest, "review_semantic_sha256": semantic,
            "source_identity": deepcopy(source_identity), "qc_used_as_machine_predictions": False,
            "source_records_sha256_verified": True, "typed_identity_provenance": True,
            "decision_origin": "SOURCE_BOUND_REVIEW_ASSISTED_NOT_AUTOMATIC_MODEL_RESULT"}}
