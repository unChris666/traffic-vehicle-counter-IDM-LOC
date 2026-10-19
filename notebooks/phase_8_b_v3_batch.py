"""Source-bound reviewed-identity replay of immutable Phase 8 measurements.

No detector, tracker or ReID model is loaded. Original B v2 sources/results are
inputs, never overwritten. Human-reviewed identity is scoped by video, raw ID,
source frames and raw measurement family; unknown people are not pedestrians.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import phase_8_annotation_batch as donor
import phase_8_annotation_helpers as retained
import phase_8_b_v2_batch as baseline
from phase_5_geometry_helpers import Geometry


REVIEWS = "results/b_v3/input/review_decisions.json"
SOURCE_NAMES = baseline.SOURCE_NAMES + ("phase_8_b_v3_counting.py", "phase_8_b_v3_annotation.py",
    "phase_8_b_v3_batch.py")
KINDS = {"SAME_VEHICLE", "SPLIT_IDENTITY", "COMPONENT_OF", "PEDESTRIAN_ROLE"}
VEHICLES = baseline.VEHICLES
PENDING_GROUPS = {
    "IDENTITY_DUPLICATE": {"UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE"},
    "IDENTITY_HANDOFF": {"RAW_TRACK_CHANGED_DURING_PASSAGE", "TIMEOUT_RAW_TRACK_HANDOFF_UNRESOLVED"},
    "CATEGORY_CONFLICT": {"CATEGORY_ENDPOINT_CONFLICT", "CATEGORY_TIE_IN_BAND"},
    "CROSSING_EVIDENCE": {"DESTINATION_REACHED_WITHOUT_ACCEPTED_CROSSING_ROUTE", "DESTINATION_WITHOUT_ELIGIBLE_CROSSING",
        "NO_VALID_FINITE_LINE_OR_OCCLUSION_EVIDENCE"},
    "TAXONOMY_OPEN": {"UNSUPPORTED_CATEGORY_TAXONOMY_OPEN"},
    "PERSON_ROLE_UNRESOLVED": {"PERSON_ROLE_UNRESOLVED"},
}


def _write(path, value):
    baseline._json(path, value)


def validate_reviews(value, jobs):
    """Reject foreign sources, global aliases, implicit taxonomy and overlaps."""
    donor._require(value.get("schema_version") == "phase8_b_v3_review_decisions_v1"
        and value.get("donor_manifest_sha256") == donor.DONOR_MANIFEST_SHA256,
        "Unknown review schema or foreign donor")
    videos = {row["video_id"]: row for row in value.get("videos", [])}
    donor._require(len(videos) == len(value.get("videos", [])) == 8
        and set(videos) == set(donor.VIDEO_IDS), "Reviews must explicitly bind all eight inputs")
    seen = set()
    for job in jobs:
        video = videos[job["video_id"]]
        identity = job["b_v2_source_identity"]
        donor._require(all(video.get(k) == identity[k] for k in
            ("video_sha256", "records_sha256", "geometry_sha256")), "Review source binding differs")
        occupied = defaultdict(list)
        for review in video.get("reviews", []):
            rid, kind = review.get("review_id"), review.get("type")
            donor._require(isinstance(rid, str) and rid and rid not in seen and kind in KINDS,
                "Review ID missing/duplicate or unsupported type")
            seen.add(rid)
            claim = review.get("claim_type")
            donor._require((claim == "USER_REVIEW" or
                (claim == "AI_ASSISTED_PIXELS_REVIEW" and kind == "PEDESTRIAN_ROLE"))
                and isinstance(review.get("confirmed_frames"), list) and review["confirmed_frames"],
                "Review must retain explicit user-reviewed anchors")
            if claim == "AI_ASSISTED_PIXELS_REVIEW":
                evidence = review.get("evidence", [])
                donor._require(evidence and all(isinstance(item.get("path"), str)
                    and isinstance(item.get("sha256"), str) and donor._HASH.fullmatch(item["sha256"])
                    and item.get("frame_index") in review["confirmed_frames"] for item in evidence),
                    "AI pedestrian review requires retained pixel evidence bindings")
            scopes = review.get("scopes", [])
            donor._require(scopes, "Global unbounded review is forbidden")
            for scope in scopes:
                track, start, end = (scope.get(k) for k in ("track_id", "start_frame", "end_frame"))
                donor._require(type(track) is int and track > 0 and type(start) is int and type(end) is int
                    and 0 <= start <= end < job["metadata"]["frame_count"], "Invalid bounded review scope")
                donor._require(scope.get("raw_family") in ("vehicle", "person"), "Review needs raw measurement family")
                if kind in ("SAME_VEHICLE", "SPLIT_IDENTITY"):
                    unit = scope.get("physical_unit_id", review.get("physical_unit_id"))
                    episode = scope.get("episode_id", review.get("episode_id"))
                    donor._require(isinstance(unit, str) and unit and isinstance(episode, str) and episode,
                        "Identity review needs explicit physical unit and episode")
                    for old in occupied[(track, scope["raw_family"])]:
                        donor._require(end < old[0] or start > old[1], "Overlapping identity review scopes")
                    occupied[(track, scope["raw_family"])].append((start, end))
                if kind == "COMPONENT_OF":
                    donor._require(scope["raw_family"] == "person" and review.get("component_of_unit_id"),
                        "Rider review must target measured person and explicit parent")
                if kind == "PEDESTRIAN_ROLE":
                    donor._require(scope["raw_family"] == "person", "Pedestrian review needs raw person")
    return videos


def prepare_b_v3_batch(*, repo_root, source_run_root=None, source_video_root=None,
                       input_root="/kaggle/input", video_ids=None, reviews_path=None):
    """Reuse the original full donor/source SHA guard, then bind new reviews."""
    root = Path(repo_root).resolve()
    prepared = baseline.prepare_b_v2_batch(repo_root=root, source_run_root=source_run_root,
        source_video_root=source_video_root, input_root=input_root, video_ids=video_ids)
    path = Path(reviews_path).resolve() if reviews_path else root / REVIEWS
    value = donor._read(path)
    for video in value.get("videos", []):
        for review in video.get("reviews", []):
            if review.get("claim_type") == "AI_ASSISTED_PIXELS_REVIEW":
                pixel_proofs = {}
                for evidence in review.get("evidence", []):
                    evidence_path = baseline._bound(root, evidence["path"], evidence["sha256"])
                    if evidence_path.suffix == ".json":
                        proof = donor._read(evidence_path)
                        donor._require(proof.get("video_sha256") == video["video_sha256"]
                            and proof.get("source_records_sha256") == video["records_sha256"],
                            "AI role evidence belongs to another input")
                        images = [image for image in proof.get("images", [])
                            if image["frame_index"] == evidence["frame_index"]]
                        donor._require(len(images) == 1 and images[0].get("verified_decode_pixel_sha256") is True
                            and images[0]["raw_bgr_pixel_sha256"] == evidence.get("source_frame_pixel_sha256"),
                            "AI role evidence pixel/source frame binding differs")
                        pixel_proofs[evidence["frame_index"]] = images[0]
                review["_pixel_anchor_proofs"] = pixel_proofs
    policy_path = root / "results/b_v3/config/policy.json"
    policy = donor._read(policy_path)
    donor._require(policy.get("base_b_v2_policy_sha256") == prepared["policy_sha256"]
        and all(policy.get(key) == prepared["policy"][key] for key in
            ("line_margin_half_width_px", "timeout_frames", "timeout_clock", "category_policy")),
        "B v3 changed frozen geometry/counting parameters")
    policy["review_manifest_sha256"] = donor.sha256_file(path)
    reference = value.get("b_v2_baseline_reference")
    donor._require(isinstance(reference, dict), "Missing retained B v2 baseline reference")
    baseline_path = baseline._bound(root, reference["path"], reference["sha256"])
    old_summary = donor._read(baseline_path)
    donor._require(old_summary.get("frames_processed") == 72590 and old_summary.get("operational_total") == 3717,
        "Retained B v2 baseline summary differs")
    prepared.update(reviews=validate_reviews(value, prepared["jobs"]), reviews_path=path,
        reviews_sha256=donor.sha256_file(path), original_videos_sha_verified=True,
        original_videos_redecoded_during_prepare=False, policy=policy,
        policy_sha256=donor.sha256_file(policy_path), effective_policy_sha256=hashlib.sha256(
            json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        b_v2_reference=reference, b_v2_by_video={row["video_id"]: row for row in old_summary["per_video"]})
    return prepared


def relationship_evidence(path):
    result = baseline.retained_relationships(path)
    pairs, supported, relation_ids = defaultdict(list), defaultdict(list), defaultdict(dict)
    for row in retained.iter_json_array(path):
        if row.get("type") != "SAME_VEHICLE" or row.get("status") not in ("SUPPORTED", "UNRESOLVED"):
            continue
        pair = tuple(sorted((row["first_track_id"], row["second_track_id"])))
        target = pairs if row["status"] == "UNRESOLVED" else supported
        for frame in row.get("features", {}).get("common_frame_indices", []):
            target[frame].append(pair)
            if row["status"] == "SUPPORTED":
                relation_ids[frame].setdefault(pair, []).append(row["relation_id"])
    result.update(identity_pairs_by_frame=dict(pairs), supported_pairs_by_frame=dict(supported),
        supported_relation_ids_by_frame=dict(relation_ids))
    return result


def _family(category):
    return "vehicle" if category in VEHICLES else "person" if category == "person" else "other"


def _scope_matches(scope, track, frame, category):
    return (scope["track_id"] == track and scope["start_frame"] <= frame <= scope["end_frame"]
        and scope["raw_family"] == _family(category))


def _review_at(reviews, track, frame, category):
    return [(review, scope) for review in reviews for scope in review["scopes"]
        if _scope_matches(scope, track, frame, category)]


def _same_reviewed_pair(reviews, pair, frame):
    for review in reviews:
        if review["type"] != "SAME_VEHICLE":
            continue
        active = {s["track_id"] for s in review["scopes"] if s["raw_family"] == "vehicle"
            and s["start_frame"] <= frame <= s["end_frame"]}
        if set(pair) <= active:
            return True
    return False


def _local_retained_associations(links, present, frame, identity):
    """Verify only an exact-frame complete positive co-observation clique.

    The retained whole-ID unit name is an operational grouping assumption. It
    does not verify every observation, fill support gaps, or authorize a chain
    merge. A future/earlier positive relation cannot verify this source frame.
    """
    units = links.get("unit_by_track", {})
    groups = defaultdict(list)
    for track, observation in present.items():
        if observation.get("class_name") in VEHICLES and track in units:
            groups[units[track]].append(track)
    positive = {tuple(sorted(pair)) for pair in links.get("supported_pairs_by_frame", {}).get(frame, [])}
    unresolved = {tuple(sorted(pair)) for pair in links.get("identity_pairs_by_frame", {}).get(frame, [])}
    verified = {}
    for unit, members in groups.items():
        members = sorted(members)
        if len(members) < 2:
            continue
        required = {(first, second) for index, first in enumerate(members) for second in members[index + 1:]}
        if not required <= positive - unresolved:
            continue
        relation_ids = sorted({rid for pair in required for rid in
            links.get("supported_relation_ids_by_frame", {}).get(frame, {}).get(pair, [])})
        for track in members:
            verified[track] = {"association_id": "retained-local:" + identity["records_sha256"] + ":" + unit,
                "association_evidence": {"claim_type": "RETAINED_SUPPORTED_SAME_VEHICLE_EXACT_SOURCE_FRAME",
                    "frame_index": frame, "track_ids": members, "relation_ids": relation_ids,
                    "records_sha256": identity["records_sha256"], "whole_id_support_implied": False}}
    return verified


def adapted_frames(path, identity, frame_count, *, relationships=None, reviews=None,
                   reviews_sha256=None, assignments=None, application_proof=None):
    """Validate every emitted/raw link; attach explicit roles without editing it."""
    links, reviews = relationships or {}, reviews or []
    units = links.get("unit_by_track", {})
    components = defaultdict(dict)
    for link in links.get("component_links", []):
        for frame in link["support_frames"]:
            components[frame][link["component_track_id"]] = link
    proof = application_proof if application_proof is not None else {}
    counts, anchors, coexistence, count = Counter(), set(), [], 0
    for record in retained._records(path):
        frame = record.get("frame_index")
        donor._require(type(frame) is int and frame == count, "B v3 frames must start at zero and be continuous")
        donor._require(all(record.get(key) == identity.get(key) for key in
            ("video_sha256", "parent_run_id", "variant", "width", "height")), "Source cache identity differs")
        raw, tracks = record.get("raw_detections"), record.get("emitted_tracks")
        donor._require(isinstance(raw, list) and isinstance(tracks, list), "Missing retained source links")
        seen, indices, observations = set(), set(), []
        present = {o["track_id"]: o for o in tracks}
        local_associations = _local_retained_associations(links, present, frame, identity)
        for review in reviews:
            anchor = review.get("_pixel_anchor_proofs", {}).get(frame)
            if not anchor: continue
            donor._require(record.get("detector_input_frame_pixel_sha256") == anchor["raw_bgr_pixel_sha256"],
                "Reviewed pedestrian frame differs from actual retained detector input")
            targets = {s["track_id"] for s in review["scopes"]}
            for source in anchor["observations"]:
                if source["track_id"] not in targets: continue
                actual = present.get(source["track_id"], {})
                donor._require(all(actual.get(key) == source[key] for key in
                    ("class_name", "raw_bbox", "original_detection_index")),
                    "Reviewed pedestrian source measurement differs")
        for original in tracks:
            track, index = original.get("track_id"), original.get("original_detection_index")
            donor._require(type(track) is int and track > 0 and track not in seen
                and type(index) is int and 0 <= index < len(raw) and index not in indices,
                "Repeated or invalid emitted source link")
            seen.add(track); indices.add(index)
            donor._require(original.get("frame_index") == frame and original.get("emitted") is True
                and original.get("measurement_provenance") == "retained_phase_8_detection",
                "Only raw measured emitted source observations may enter replay")
            box, detection = retained._bbox(original.get("raw_bbox")), raw[index]
            donor._require(0 <= box[0] < box[2] <= identity["width"] and 0 <= box[1] < box[3] <= identity["height"],
                "BBox outside source image")
            donor._require(box == detection.get("bbox_xyxy_pixels") and all(original.get(key) == detection.get(key)
                for key in ("class_name", "class_id", "confidence")), "Measurement differs from original detection")
            confidence = original.get("confidence")
            donor._require(isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
                and math.isfinite(confidence), "Missing finite source confidence")
            category = original["class_name"]
            if _family(category) == "other":
                continue
            item = deepcopy(original)
            item.update(observed=True, role="unknown_person" if category == "person" else "vehicle",
                unit_id=f"person-track:{track}" if category == "person" else units.get(track, f"track:{track}"),
                episode_id="unreviewed-person" if category == "person" else "unreviewed-vehicle",
                association_verified=False)
            association = local_associations.get(track)
            if association is not None:
                item.update(association_verified=True, association_id=association["association_id"])
                original_ref = deepcopy(item.get("source_ref"))
                item["source_ref"] = {"retained_same_vehicle_association": association["association_evidence"]}
                if original_ref is not None:
                    item["source_ref"]["original_source_ref"] = original_ref
            pairs = [pair for pair in links.get("identity_pairs_by_frame", {}).get(frame, []) if track in pair]
            item["identity_conflict"] = any(not _same_reviewed_pair(reviews, pair, frame) for pair in pairs)
            if not links.get("identity_pairs_by_frame"):
                item["identity_conflict"] = track in links.get("identity_conflicts_by_frame", {}).get(frame, set())
            local = components.get(frame, {}).get(track)
            if category == "person" and local and local["vehicle_track_id"] in present:
                parent = present[local["vehicle_track_id"]]
                if parent["class_name"] == "motorcycle":
                    item.update(role="rider", component_of_unit_id=units.get(local["vehicle_track_id"],
                        f"track:{local['vehicle_track_id']}"), retained_component_relation_id=local["relation_id"])
            applied = _review_at(reviews, track, frame, category)
            for review, scope in applied:
                rid, kind = review["review_id"], review["type"]
                counts[rid] += 1
                if frame in review["confirmed_frames"]:
                    anchors.add((rid, track, frame))
                item.setdefault("review_refs", []).append({"review_id": rid, "reviews_sha256": reviews_sha256,
                    "source_frame": frame, "track_id": track,
                    "claim_type": review.get("claim_type", "USER_REVIEW"),
                    "scope_extent_is_engineering_assumption": True})
                if kind in ("SAME_VEHICLE", "SPLIT_IDENTITY"):
                    item.update(unit_id=scope.get("physical_unit_id", review.get("physical_unit_id")),
                        episode_id=scope.get("episode_id", review.get("episode_id")))
                    if kind == "SAME_VEHICLE":
                        item.update(association_verified=True, association_id=rid)
                elif kind == "COMPONENT_OF":
                    item.update(role="rider", component_of_unit_id=review["component_of_unit_id"])
                elif kind == "PEDESTRIAN_ROLE":
                    item.update(role="pedestrian", resolved_class_name="pedestrian",
                        unit_id=review.get("physical_unit_id", f"reviewed-pedestrian:{track}"),
                        episode_id=review.get("episode_id", f"reviewed-role:{rid}"))
                resolved = scope.get("resolved_class_name", review.get("resolved_class_name"))
                if resolved:
                    item["resolved_class_name"] = resolved
            observations.append(item)
            if assignments is not None:
                assignments.append({"frame_index": frame, "track_id": track,
                    "physical_unit_id": item["unit_id"], "episode_id": item["episode_id"],
                    "role": item["role"], "category": item.get("resolved_class_name", category),
                    "raw_category": category, "review_refs": deepcopy(item.get("review_refs", [])),
                    "association_verified": item["association_verified"],
                    "association_id": item.get("association_id"),
                    **({"component_of_unit_id": item["component_of_unit_id"]} if "component_of_unit_id" in item else {})})
        simultaneous = defaultdict(list)
        for item in observations:
            if item["role"] == "vehicle" and item.get("association_verified"):
                simultaneous[(item["unit_id"], item["episode_id"])].append(item)
        for (unit, episode), items in simultaneous.items():
            if len(items) < 2: continue
            for index, first in enumerate(items):
                for second in items[index + 1:]:
                    a, b = first["raw_bbox"], second["raw_bbox"]
                    overlap = max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])
                    coexistence.append({"frame_index": frame, "physical_unit_id": unit, "episode_id": episode,
                        "track_ids": [first["track_id"], second["track_id"]], "raw_bboxes": [a, b],
                        "boxes_overlap_with_positive_area": overlap,
                        "association_basis": ("SOURCE_FRAME_BOUND_REVIEWED_CLAIM_NOT_AUTOMATIC_IDENTITY_PROOF"
                            if first.get("review_refs") or second.get("review_refs") else
                            "RETAINED_SUPPORTED_SAME_VEHICLE_EXACT_SOURCE_FRAME")})
        yield {"frame_index": frame, "observations": observations}
        count += 1
    donor._require(count == frame_count, "Full B v3 source cache frame count differs")
    donor._require(all(counts[r["review_id"]] > 0 for r in reviews), "Review did not match any measured source")
    proof.update(applied_measurements=dict(counts), matched_reviewed_anchors=[{"review_id": r, "track_id": t,
        "frame_index": f} for r, t, f in sorted(anchors)], source_links_checked=True,
        no_source_observations_modified=True, all_source_frames_retained=count,
        simultaneous_reviewed_vehicle_measurements=coexistence)


def pending_groups(result):
    """One decision per unit/episode/passage, multiple reasons retained."""
    merged = {}
    for decision in result.get("decisions", []):
        if not str(decision.get("status", "")).startswith("pending"):
            continue
        key = (decision.get("physical_unit_id"), decision.get("episode_id"), decision.get("passage_id"))
        row = merged.setdefault(key, {"physical_unit_id": key[0], "episode_id": key[1], "passage_id": key[2],
            "role": decision.get("role"), "reasons": set(), "decision_frames": set(), "track_ids": set()})
        row["reasons"].update(decision.get("reasons", []))
        if isinstance(decision.get("frame_index"), int): row["decision_frames"].add(decision["frame_index"])
        ref = decision.get("source_ref", {})
        if ref.get("track_id") is not None: row["track_ids"].add(ref["track_id"])
    rows, counts = [], Counter()
    for row in merged.values():
        row = {key: sorted(value) if isinstance(value, set) else value for key, value in row.items()}
        groups = sorted({name for name, reasons in PENDING_GROUPS.items() if set(row["reasons"]) & reasons})
        if not groups: groups = ["OTHER_REQUIRES_REVIEW"]
        row["case_groups"] = groups; counts.update(groups); rows.append(row)
    return {"schema_version": "phase8_b_v3_pending_groups_v1", "unique_unit_episode_passages": len(rows),
        "case_group_memberships": dict(sorted(counts.items())), "groups_not_mutually_exclusive": True,
        "unknown_person_candidate_keys": sum(row["role"] == "unknown_person" for row in rows),
        "vehicle_or_reviewed_pedestrian_pending_keys": sum(row["role"] != "unknown_person" for row in rows),
        "cases": rows}


def _source_snapshot(output):
    directory, result = Path(__file__).resolve().parent, {}
    for name in SOURCE_NAMES:
        path = directory / name; data = path.read_bytes()
        archive = output / "source_snapshot" / (name + ".gz"); archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(gzip.compress(data, mtime=0))
        result[str(path)] = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
            "retained_path": archive.relative_to(output).as_posix()}
    _write(output / "source_snapshot.json", result)
    return result


def run_b_v3_batch(*, repo_root, output_root="/kaggle/working/results/phase_8_b_v3", source_run_root=None,
                   source_video_root=None, input_root="/kaggle/input", video_ids=None, render=True,
                   progress=print, run_id=None, reviews_path=None):
    import phase_8_b_v3_counting as counting
    prepared = prepare_b_v3_batch(repo_root=repo_root, source_run_root=source_run_root,
        source_video_root=source_video_root, input_root=input_root, video_ids=video_ids, reviews_path=reviews_path)
    identifier = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    donor._require(isinstance(identifier, str) and identifier and Path(identifier).name == identifier
        and identifier not in (".", "..") and "\\" not in identifier, "Unsafe run ID")
    output = Path(output_root).resolve() / identifier
    donor._require(not output.exists() and not output.is_relative_to(Path(prepared["source_run_root"]).resolve()),
        "Output must be new and outside original evidence")
    output.mkdir(parents=True)
    snapshots = _source_snapshot(output)
    guarded = list(prepared.get("verified_input_files", [])) + [{"path": str(prepared["reviews_path"]),
        "sha256": prepared["reviews_sha256"]}, {"path": str(Path(repo_root) / "results/b_v3/config/policy.json"),
        "sha256": prepared["policy_sha256"]}]
    _write(output / "review_decisions.json", donor._read(prepared["reviews_path"]))
    report = {"schema_version": "phase8_b_v3_batch_v1", "run_id": identifier, "status": "running",
        "claim_type": "ACTUAL_RETAINED_CACHE_REVIEWED_IDENTITY_REPLAY_NOT_ACCURACY",
        "output_directory": str(output), "selected_video_ids": prepared["selected_video_ids"],
        "all_eight_selected": prepared["all_eight_selected"], "videos": [],
        "policy": prepared["policy"], "policy_sha256": prepared["policy_sha256"],
        "effective_policy_sha256": prepared.get("effective_policy_sha256"),
        "geometry_manifest_sha256": prepared["geometry_manifest_sha256"],
        "reviews_sha256": prepared["reviews_sha256"], "executed_source_files": snapshots,
        "original_model_caches_modified": False, "original_videos_sha_verified": True,
        "new_detector_tracker_reid_execution": False, "render_requested": bool(render),
        "physical_identity_or_counting_accuracy_established": False, "python": platform.python_version(),
        "pending_semantics": "UNIT_EPISODE_PASSAGE_KEYS_WITH_MULTI_REASON_GROUPS; PERSON_ROLE_QUEUE_SEPARATE",
        "unchanged_clique_grouping_assumption": "retained whole-ID clique is operational; handoff verification remains local",
        "unknown_person_policy": "not automatically pedestrian; unresolved role stays outside pedestrian subtotal"}
    _write(output / "batch_report.json", report)
    started = time.perf_counter()
    try:
        for job in prepared["jobs"]:
            video_id = job["video_id"]; target = output / video_id; target.mkdir()
            row = {"video_id": video_id, "status": "running"}; report["videos"].append(row)
            identity = job["b_v2_source_identity"]
            geometry_data = donor._read(job["b_v2_geometry_path"])
            geometry = Geometry.from_draft(job["b_v2_geometry_path"], identity["width"], identity["height"])
            links = relationship_evidence(job["paths"]["relations"])
            assignments, proof = [], {}
            result = counting.replay_frames(adapted_frames(job["paths"]["records"], identity,
                job["metadata"]["frame_count"], relationships=links,
                reviews=prepared["reviews"][video_id].get("reviews", []), reviews_sha256=prepared["reviews_sha256"],
                assignments=assignments, application_proof=proof), geometry, source_identity=identity, policy=prepared["policy"])
            result.update(video_id=video_id, source_identity=identity, component_links=links["component_links"],
                unit_groups=links["unit_groups"], frame_assignments=assignments, review_application_proof=proof)
            groups = pending_groups(result)
            role_rows = [row for row in assignments if row["role"] == "unknown_person"]
            role_tracks = defaultdict(list)
            for role in role_rows: role_tracks[(role["physical_unit_id"], role["episode_id"])].append(role["frame_index"])
            role_queue = [{"physical_unit_id": unit, "episode_id": episode, "first_observed_frame": min(frames),
                "last_observed_frame": max(frames), "observed_measurements": len(frames), "status": "PERSON_ROLE_UNRESOLVED",
                "does_not_imply_pedestrian": True} for (unit, episode), frames in sorted(role_tracks.items())]
            _write(target / "counting_result.json", result); _write(target / "geometry.json", geometry_data)
            _write(target / "pending_groups.json", groups); _write(target / "person_role_review_queue.json", role_queue)
            row.update(status="counting_complete", frames=job["metadata"]["frame_count"], aggregate=result["aggregate"],
                pending_unique_unit_episode_passages=groups["unique_unit_episode_passages"],
                pending_group_memberships=groups["case_group_memberships"], unknown_person_role_keys=len(role_queue),
                source_identity=identity, review_application_proof=proof)
            previous = prepared["b_v2_by_video"][video_id]
            comparison = {"claim_type": "SNAPSHOT_LEDGER_DIFFERENCES_NOT_ACCURACY_OR_PENDING_IMPROVEMENT",
                "b_v2_reference": prepared["b_v2_reference"], "b_v2_aggregate": previous["aggregate"],
                "b_v3_aggregate": result["aggregate"],
                "operational_total_delta": result["aggregate"]["total"] - previous["aggregate"]["total"],
                "b_v2_pending_decision_rows": previous["pending_decision_rows"],
                "b_v3_pending_unique_unit_episode_passages": groups["unique_unit_episode_passages"],
                "pending_denominators_differ": True, "person_role_queue_is_separate": True}
            _write(target / "comparison_b_v2.json", comparison); row["comparison_b_v2"] = comparison
            if progress: progress({"video_id": video_id, "stage": "counting_complete", "aggregate": result["aggregate"]})
            if render:
                import phase_8_b_v3_annotation as annotation
                annotation_report = annotation.render_video(job["video_path"], job["paths"]["records"], result,
                    geometry_data, target / (video_id + "-b-v3-annotated.mp4"), fps=job["metadata"]["fps"],
                    expected_frame_count=job["metadata"]["frame_count"], source_identity=identity,
                    component_relations=links["component_links"], unit_assignments=assignments,
                    progress=(lambda value: progress(dict(value, video_id=video_id))) if progress else None)
                _write(target / "annotation_report.json", annotation_report); row["annotation"] = annotation_report
            row["status"] = "completed"; _write(output / "batch_report.json", report)
        report.update(status="completed_reviewed_identity_replay_pending_physical_audit", all_selected_completed=True,
            all_eight_completed=prepared["all_eight_selected"] and len(report["videos"]) == 8,
            frames_processed=sum(row["frames"] for row in report["videos"]),
            operational_total=sum(row["aggregate"]["total"] for row in report["videos"]),
            pending_unique_unit_episode_passages=sum(row["pending_unique_unit_episode_passages"] for row in report["videos"]),
            unknown_person_role_keys=sum(row["unknown_person_role_keys"] for row in report["videos"]))
    except Exception as error:
        report.update(status="failed_or_partial", all_selected_completed=False, all_eight_completed=False,
            error_type=type(error).__name__, error=str(error)); raise
    finally:
        changed = [path for path, item in snapshots.items() if donor.sha256_file(path) != item["sha256"]]
        changed_inputs = [item["path"] for item in guarded if donor.sha256_file(item["path"]) != item["sha256"]]
        report["source_files_unchanged_during_execution"] = not changed
        report["original_inputs_and_reviews_unchanged_during_execution"] = not changed_inputs
        report["wall_seconds"] = time.perf_counter() - started
        if changed or changed_inputs: report.update(status="failed_or_partial", all_selected_completed=False,
            all_eight_completed=False, error="Executable source changed during replay")
        _write(output / "batch_report.json", report); baseline._retention(output)
        if changed or changed_inputs: raise RuntimeError("Executable source or retained input changed during replay")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default="."); parser.add_argument("--source-run-root")
    parser.add_argument("--source-video-root"); parser.add_argument("--input-root", default="/kaggle/input")
    parser.add_argument("--output-root", default="/kaggle/working/results/phase_8_b_v3")
    parser.add_argument("--video-ids", nargs="+"); parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--reviews-path")
    args = vars(parser.parse_args()); args["render"] = not args.pop("no_render")
    result = run_b_v3_batch(**args)
    print(json.dumps({key: result[key] for key in ("status", "output_directory", "frames_processed", "operational_total")}))


if __name__ == "__main__":
    main()
