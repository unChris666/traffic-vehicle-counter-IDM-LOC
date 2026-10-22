"""Isolated B v4 replay of source-bound Phase 8 measurements.

This notebook helper does not import or execute a detector, tracker, ReID encoder
or enhancement model. The machine branch keeps the old reviewed inputs; a
separate review-assisted branch can add explicitly adjudicated bounded evidence.
Branch totals must never be added together.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import time

import phase_8_b_v3_batch as previous
from phase_5_geometry_helpers import Geometry


donor, baseline = previous.donor, previous.baseline
POLICY = "results/b_v4/config/policy.json"
OVERLAY = "results/b_v4/input/review_decisions.json"
BASELINE_RETENTION = "results/b_v3/execution/final_20261019T045405_106031Z/retained_bytes_manifest.json"
SOURCE_NAMES = tuple(dict.fromkeys(previous.SOURCE_NAMES + (
    "phase_8_b_v4_identity.py", "phase_8_b_v4_counting.py",
    "phase_8_b_v4_annotation.py", "phase_8_b_v4_batch.py",
    "08d_episode_eligibility_role_replay.ipynb")))
BRANCHES = ("machine", "review_assisted")


def _write(path, value):
    baseline._json(path, value)


def _digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()


def _bound_artifact(root, relative_path, sha256, guarded):
    path = baseline._bound(root, relative_path, sha256)
    guarded.append({"path": str(path), "sha256": sha256})
    return path


def validate_overlay(value, jobs, root, guarded):
    """Bind adjudications to exact input bytes and retained native-pixel anchors.

    The additional claims are research review inputs, never automatic model
    predictions or newly confirmed user labels. The immutable old adapter checks
    anchor pixels again against each actual retained frame during replay.
    """
    donor._require(value.get("schema_version") == "phase8_b_v4_review_overlay_v1"
        and value.get("donor_manifest_sha256") == donor.DONOR_MANIFEST_SHA256,
        "Unknown B v4 overlay schema or foreign donor")
    videos = {v["video_id"]: v for v in value.get("videos", [])}
    donor._require(len(videos) == len(value.get("videos", [])) and set(videos) <= set(donor.VIDEO_IDS),
        "Overlay has duplicate or unknown video IDs")
    seen = set()
    for job in jobs:
        vid = job["video_id"]
        if vid not in videos:
            continue
        video, source = videos[vid], job["b_v2_source_identity"]
        donor._require(all(video.get(key) == source[key] for key in
            ("video_sha256", "records_sha256", "geometry_sha256")), "Overlay source binding differs")
        for review in video.get("reviews", []):
            rid = review.get("review_id")
            donor._require(isinstance(rid, str) and rid and rid not in seen,
                "Missing or duplicate overlay review ID")
            seen.add(rid)
            donor._require(review.get("claim_type") == "ADJUDICATED_AI_PIXELS_REVIEW"
                and review.get("type") in previous.KINDS
                and review.get("human_confirmation_status") == "NOT_NEWLY_ADJUDICATED_BY_USER",
                "Overlay must retain explicit AI adjudication provenance")
            scopes, anchors = review.get("scopes", []), review.get("confirmed_frames", [])
            donor._require(scopes and anchors and all(type(f) is int for f in anchors),
                "Overlay needs bounded scopes and confirmed frames")
            for scope in scopes:
                start, end = scope.get("start_frame"), scope.get("end_frame")
                donor._require(type(scope.get("track_id")) is int and scope["track_id"] > 0
                    and type(start) is int and type(end) is int
                    and 0 <= start <= end < job["metadata"]["frame_count"]
                    and scope.get("raw_family") in ("person", "vehicle"), "Invalid overlay scope")
            if review["type"] in ("PEDESTRIAN_ROLE", "COMPONENT_OF"):
                donor._require(all(s["raw_family"] == "person" for s in scopes),
                    "Role review may only relabel raw person measurements")
            if review["type"] == "COMPONENT_OF":
                donor._require(bool(review.get("component_of_unit_id")), "Rider review needs parent")
            if review["type"] in ("SAME_VEHICLE", "SPLIT_IDENTITY"):
                donor._require(all(s.get("physical_unit_id", review.get("physical_unit_id"))
                    and s.get("episode_id", review.get("episode_id")) for s in scopes),
                    "Identity overlay needs unit and episode")
            evidence = review.get("evidence", [])
            donor._require(evidence, "Adjudication must bind retained evidence")
            proofs = {}
            for entry in evidence:
                path = _bound_artifact(root, entry["path"], entry["sha256"], guarded)
                proof = donor._read(path)
                frame = entry.get("frame_index")
                donor._require(frame in anchors, "Overlay evidence is not a confirmed frame")
                if "checks" in proof:
                    donor._require(proof.get("source_sha256") == source["video_sha256"]
                        and proof.get("retained_cache_file_sha256") == source["records_sha256"],
                        "Overlay pixel evidence belongs to another input")
                    found = [c for c in proof["checks"] if c["frame_index"] == frame]
                    donor._require(len(found) == 1 and found[0].get("status") == "PASS"
                        and found[0].get("actual_bgr_pixel_sha256") == entry.get("source_frame_pixel_sha256")
                        and found[0].get("expected_retained_detector_input_pixel_sha256")
                            == entry.get("source_frame_pixel_sha256"), "Overlay native pixel evidence differs")
                    check = found[0]
                    png = check.get("retained_native_png_path")
                    if png:
                        # The source-pixel receipt is inside evidence/; PNG paths
                        # are relative to the audit package, not repository root.
                        image = path.parent.parent / png
                        donor._require(image.is_file() and donor.sha256_file(image)
                            == check.get("sequentially_decoded_native_png_sha256"),
                            "Retained adjudication image bytes differ")
                        guarded.append({"path": str(image), "sha256": donor.sha256_file(image)})
                    proofs[frame] = {"raw_bgr_pixel_sha256": entry["source_frame_pixel_sha256"],
                        "observations": []}
                else:
                    donor._require(proof.get("video_sha256") == source["video_sha256"]
                        and proof.get("source_records_sha256") == source["records_sha256"],
                        "Overlay pixel evidence belongs to another input")
                    images = [image for image in proof.get("images", []) if image["frame_index"] == frame]
                    donor._require(len(images) == 1 and images[0].get("verified_decode_pixel_sha256") is True
                        and images[0].get("raw_bgr_pixel_sha256") == entry.get("source_frame_pixel_sha256"),
                        "Overlay native pixel evidence differs")
                    proofs[frame] = images[0]
            donor._require(set(anchors) <= set(proofs), "Every overlay anchor needs pixel evidence")
            donor._require(all(any(s["start_frame"] <= f <= s["end_frame"] for s in scopes)
                for f in anchors), "Overlay anchor outside its bounded scope")
            review["_pixel_anchor_proofs"] = proofs
    return videos


def prepare_b_v4_batch(*, repo_root, source_run_root=None, source_video_root=None,
                      input_root="/kaggle/input", video_ids=None, branch="machine",
                      policy_path=None, reviews_path=None):
    donor._require(branch in BRANCHES, "Unknown B v4 branch")
    root = Path(repo_root).resolve()
    selected = ["weekday_siang"] if video_ids is None else video_ids
    prepared = previous.prepare_b_v3_batch(repo_root=root, source_run_root=source_run_root,
        source_video_root=source_video_root, input_root=input_root, video_ids=selected)
    config_path = Path(policy_path).resolve() if policy_path else root / POLICY
    policy = donor._read(config_path)
    donor._require(policy.get("schema_version") == "phase8_b_v4_policy_v1"
        and policy.get("base_b_v3_policy_sha256") == prepared["policy_sha256"],
        "B v4 policy does not bind immutable B v3 policy")
    donor._require(all(policy.get(key) == prepared["policy"][key] for key in
        ("line_margin_half_width_px", "timeout_frames", "timeout_clock", "category_policy",
         "supported_categories", "passage_display_id")), "B v4 changed frozen counting controls")
    guarded = list(prepared.get("verified_input_files", [])) + [
        {"path": str(config_path), "sha256": donor.sha256_file(config_path)},
        {"path": str(prepared["reviews_path"]), "sha256": prepared["reviews_sha256"]}]
    old_reviews = deepcopy(prepared["reviews"])
    overlay_path, overlay_digest, overlay = None, None, {}
    if branch == "review_assisted":
        overlay_path = Path(reviews_path).resolve() if reviews_path else root / OVERLAY
        overlay_digest = donor.sha256_file(overlay_path)
        guarded.append({"path": str(overlay_path), "sha256": overlay_digest})
        overlay = validate_overlay(donor._read(overlay_path), prepared["jobs"], root, guarded)
    else:
        donor._require(reviews_path is None, "Machine branch cannot silently use review overlay")
    policy["review_manifest_sha256"] = prepared["reviews_sha256"]
    policy["review_overlay_sha256"] = overlay_digest
    policy["execution_branch"] = branch
    prepared.update(repo_root=root, policy=policy, policy_path=config_path,
        policy_sha256=donor.sha256_file(config_path), effective_policy_sha256=_digest_json(policy),
        base_reviews=old_reviews, review_overlay=overlay, review_overlay_path=overlay_path,
        review_overlay_sha256=overlay_digest, branch=branch, guarded_inputs=guarded)
    return prepared


def _read_b_v3_result(root, video_id):
    """Read exact retained B v3 result bytes, never recompute its counting."""
    manifest = donor._read(root / BASELINE_RETENTION)
    item = next(row for row in manifest["files"]
        if row["source_relative_path"] == video_id + "/counting_result.json")
    archive = baseline._bound(root, item["retained_path"], item["retained_sha256"])
    data = gzip.decompress(archive.read_bytes())
    donor._require(len(data) == item["source_bytes"]
        and hashlib.sha256(data).hexdigest() == item["source_sha256"], "B v3 retained result differs")
    return json.loads(data), {"path": item["retained_path"], "sha256": item["retained_sha256"],
        "decoded_sha256": item["source_sha256"]}


def _source_snapshot(output):
    directory, snapshots = Path(__file__).resolve().parent, {}
    for name in SOURCE_NAMES:
        path = directory / name
        data = path.read_bytes()
        archive = output / "source_snapshot" / (name + ".gz")
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(gzip.compress(data, mtime=0))
        snapshots[str(path)] = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
            "retained_path": archive.relative_to(output).as_posix()}
    _write(output / "source_snapshot.json", snapshots)
    return snapshots


def _retention(output):
    artifacts = [{"path": path.relative_to(output).as_posix(),
        "sha256": donor.sha256_file(path), "size_bytes": path.stat().st_size}
        for path in sorted(output.rglob("*")) if path.is_file() and path.name != "retention_manifest.json"]
    _write(output / "retention_manifest.json", {"schema_version": "phase8_b_v4_retention_v1",
        "artifacts": artifacts, "manifest_self_hash_excluded": True})


def _event_refs(event):
    refs = []
    def walk(value):
        if isinstance(value, dict):
            if type(value.get("track_id")) is int and type(value.get("frame_index")) is int:
                refs.append((value["track_id"], value["frame_index"]))
            for nested in value.values(): walk(nested)
        elif isinstance(value, list):
            for nested in value: walk(nested)
    walk(event)
    return sorted(set(refs))


def compare_b_v3(old, new, reference):
    """Versioned event IDs differ; retain raw/frame membership for case review."""
    def rows(result):
        return [{"event_id": e.get("event_id"), "display_id": e.get("display_id"),
            "physical_unit_id": e.get("physical_unit_id"), "episode_id": e.get("episode_id"),
            "passage_id": e.get("passage_id"), "category": e.get("category"),
            "direction": e.get("direction"), "route": e.get("route"),
            "measured_crossing": e.get("evidence", {}).get("measured_crossing"),
            "activation_frame": e.get("activation_frame"), "decision_frame": e.get("decision_frame"),
            "raw_frame_refs": _event_refs(e)}
            for e in result.get("events", [])]
    return {"claim_type": "LEDGER_DIFFERENCES_NOT_PHYSICAL_ACCURACY_OR_PENDING_IMPROVEMENT",
        "b_v3_reference": reference, "b_v3_aggregate": old["aggregate"], "b_v4_aggregate": new["aggregate"],
        "operational_total_delta": new["aggregate"]["total"] - old["aggregate"]["total"],
        "event_hashes_not_used_as_cross_version_identity": True,
        "raw_frame_membership_not_automatic_physical_identity": True,
        "branch_totals_must_not_be_added": True, "b_v3_events": rows(old), "b_v4_events": rows(new)}


def _attach_overlay_provenance(frames, overlay_reviews, overlay_sha256):
    """The old adapter accepts one manifest hash; preserve the separate overlay binding."""
    extra_ids = {review["review_id"] for review in overlay_reviews}
    for frame in frames:
        for item in frame["observations"]:
            for ref in item.get("review_refs", []):
                if ref["review_id"] in extra_ids:
                    ref["reviews_sha256"] = overlay_sha256
                    ref["review_branch"] = "review_assisted"
                    ref["not_automatic_model_role_prediction"] = True
        yield frame


def _validate_overlay_application(proof, overlay_reviews):
    matched = {(item["review_id"], item["frame_index"])
        for item in proof.get("matched_reviewed_anchors", [])}
    for review in overlay_reviews:
        donor._require(all((review["review_id"], frame) in matched for frame in review["confirmed_frames"]),
            "Adjudicated anchor did not match its scoped raw source measurement")


def _role_queue(assignments):
    groups = defaultdict(list)
    for row in assignments:
        if row["role"] == "unknown_person":
            groups[(row["physical_unit_id"], row["episode_id"])].append(row["frame_index"])
    return [{"physical_unit_id": unit, "episode_id": episode, "first_observed_frame": min(frames),
        "last_observed_frame": max(frames), "observed_measurements": len(frames),
        "status": "PERSON_ROLE_UNRESOLVED", "does_not_imply_pedestrian": True}
        for (unit, episode), frames in sorted(groups.items())]


def run_b_v4_batch(*, repo_root, output_root="/kaggle/working/results/phase_8_b_v4",
                  source_run_root=None, source_video_root=None, input_root="/kaggle/input",
                  video_ids=None, render=False, progress=print, run_id=None, branch="machine",
                  policy_path=None, reviews_path=None):
    import phase_8_b_v4_counting as counting
    import phase_8_b_v4_identity as identity_module
    prepared = prepare_b_v4_batch(repo_root=repo_root, source_run_root=source_run_root,
        source_video_root=source_video_root, input_root=input_root, video_ids=video_ids,
        branch=branch, policy_path=policy_path, reviews_path=reviews_path)
    identifier = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    donor._require(isinstance(identifier, str) and identifier and Path(identifier).name == identifier
        and identifier not in (".", "..") and "\\" not in identifier, "Unsafe run ID")
    output = Path(output_root).resolve() / identifier
    donor._require(not output.exists() and not output.is_relative_to(Path(prepared["source_run_root"]).resolve())
        and not output.is_relative_to(prepared["repo_root"] / "results/b_v3")
        and not output.is_relative_to(prepared["repo_root"] / "results/phase_9"),
        "Output must be new and outside immutable evidence")
    output.mkdir(parents=True)
    snapshots = _source_snapshot(output)
    _write(output / "policy.json", prepared["policy"])
    _write(output / "base_review_decisions.json", donor._read(prepared["reviews_path"]))
    if prepared["review_overlay_path"]:
        _write(output / "review_overlay.json", donor._read(prepared["review_overlay_path"]))
    report = {"schema_version": "phase8_b_v4_batch_v1", "run_id": identifier,
        "status": "running", "branch": branch, "output_directory": str(output),
        "claim_type": "ACTUAL_RETAINED_CACHE_EPISODE_ELIGIBILITY_REPLAY_NOT_ACCURACY",
        "selected_video_ids": prepared["selected_video_ids"], "all_eight_selected": prepared["all_eight_selected"],
        "selected_video_count": len(prepared["jobs"]), "videos": [], "policy": prepared["policy"],
        "policy_sha256": prepared["policy_sha256"], "effective_policy_sha256": prepared["effective_policy_sha256"],
        "geometry_manifest_sha256": prepared["geometry_manifest_sha256"],
        "base_reviews_sha256": prepared["reviews_sha256"], "review_overlay_sha256": prepared["review_overlay_sha256"],
        "executed_source_files": snapshots, "original_model_caches_modified": False,
        "new_detector_tracker_reid_execution": False, "new_enhancement_execution": False,
        "new_counting_policy_replay": True, "render_requested": bool(render),
        "physical_identity_or_counting_accuracy_established": False, "branch_totals_must_not_be_added": True,
        "machine_branch_keeps_preexisting_review_inputs": True,
        "python": platform.python_version(), "video_scope_is_full_selected_source_history": True}
    _write(output / "batch_report.json", report)
    started = time.perf_counter()
    try:
        for job in prepared["jobs"]:
            vid = job["video_id"]
            target = output / vid
            target.mkdir()
            row = {"video_id": vid, "status": "running"}
            report["videos"].append(row)
            source = job["b_v2_source_identity"]
            geo_data = donor._read(job["b_v2_geometry_path"])
            geometry = Geometry.from_draft(job["b_v2_geometry_path"], source["width"], source["height"])
            links = previous.relationship_evidence(job["paths"]["relations"])
            old_reviews = prepared["base_reviews"][vid].get("reviews", [])
            additional = prepared["review_overlay"].get(vid, {}).get("reviews", [])
            proof = {}
            frames = previous.adapted_frames(job["paths"]["records"], source, job["metadata"]["frame_count"],
                relationships=links, reviews=old_reviews + additional,
                reviews_sha256=prepared["reviews_sha256"], application_proof=proof)
            frames = _attach_overlay_provenance(frames, additional, prepared["review_overlay_sha256"])
            resolved = identity_module.prepare_identity_frames(frames, geometry,
                prepared["policy"], relationships=links)
            _validate_overlay_application(proof, additional)
            assignments = resolved["assignments"]
            result = counting.replay_frames(resolved["frames"], geometry, source_identity=source,
                policy=prepared["policy"])
            result.update(video_id=vid, source_identity=source, branch=branch,
                frame_assignments=assignments, review_application_proof=proof,
                component_links=resolved.get("component_links", links["component_links"]),
                unit_groups=links["unit_groups"], review_overlay_sha256=prepared["review_overlay_sha256"])
            groups, queue = previous.pending_groups(result), _role_queue(assignments)
            groups["schema_version"] = "phase8_b_v4_pending_groups_v1"
            _write(target / "counting_result.json", result)
            _write(target / "geometry.json", geo_data)
            _write(target / "pending_groups.json", groups)
            _write(target / "person_role_review_queue.json", queue)
            _write(target / "adapter_audit.json", proof)
            _write(target / "frame_assignments.json", assignments)
            for name in ("episode_audit", "role_audit", "handoff_audit", "alias_context_audit"):
                _write(target / (name + ".json"), resolved.get(name, []))
            _write(target / "eligibility_audit.json", result.get("eligibility_audit", []))
            old, ref = _read_b_v3_result(prepared["repo_root"], vid)
            comparison = compare_b_v3(old, result, ref)
            _write(target / "comparison_b_v3.json", comparison)
            row.update(status="counting_complete", frames=job["metadata"]["frame_count"],
                aggregate=result["aggregate"], source_identity=source,
                pending_unique_unit_episode_passages=groups["unique_unit_episode_passages"],
                pending_group_memberships=groups["case_group_memberships"], unknown_person_role_keys=len(queue),
                b_v3_operational_total=old["aggregate"]["total"],
                operational_total_delta=comparison["operational_total_delta"],
                review_overlay_applied=bool(additional))
            if progress: progress({"video_id": vid, "branch": branch, "stage": "counting_complete",
                "aggregate": result["aggregate"]})
            if render:
                import phase_8_b_v4_annotation as annotation
                annotation_report = annotation.render_video(job["video_path"], job["paths"]["records"], result,
                    geo_data, target / (vid + "-b-v4-annotated.mp4"), fps=job["metadata"]["fps"],
                    expected_frame_count=job["metadata"]["frame_count"], source_identity=source,
                    component_relations=result["component_links"], unit_assignments=assignments,
                    progress=(lambda value: progress(dict(value, video_id=vid))) if progress else None)
                _write(target / "annotation_report.json", annotation_report)
                row["annotation"] = annotation_report
            row["status"] = "completed"
            _write(output / "batch_report.json", report)
        report.update(status="completed_scoped_b_v4_replay_pending_physical_audit", all_selected_completed=True,
            all_eight_completed=prepared["all_eight_selected"] and len(report["videos"]) == 8,
            frames_processed=sum(v["frames"] for v in report["videos"]),
            operational_total=sum(v["aggregate"]["total"] for v in report["videos"]),
            pending_unique_unit_episode_passages=sum(v["pending_unique_unit_episode_passages"] for v in report["videos"]),
            unknown_person_role_keys=sum(v["unknown_person_role_keys"] for v in report["videos"]))
    except Exception as error:
        report.update(status="failed_or_partial", all_selected_completed=False, all_eight_completed=False,
            error_type=type(error).__name__, error=str(error))
        raise
    finally:
        changed_sources = [p for p, item in snapshots.items() if donor.sha256_file(p) != item["sha256"]]
        changed_inputs = [item["path"] for item in prepared["guarded_inputs"]
            if donor.sha256_file(item["path"]) != item["sha256"]]
        report.update(source_files_unchanged_during_execution=not changed_sources,
            original_inputs_and_reviews_unchanged_during_execution=not changed_inputs,
            wall_seconds=time.perf_counter() - started)
        if changed_sources or changed_inputs:
            report.update(status="failed_or_partial", all_selected_completed=False, all_eight_completed=False,
                error="Executable source or retained input changed during replay")
        _write(output / "batch_report.json", report)
        _retention(output)
        if changed_sources or changed_inputs:
            raise RuntimeError(report["error"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-run-root")
    parser.add_argument("--source-video-root")
    parser.add_argument("--input-root", default="/kaggle/input")
    parser.add_argument("--output-root", default="/kaggle/working/results/phase_8_b_v4")
    parser.add_argument("--video-ids", nargs="+")
    parser.add_argument("--branch", choices=BRANCHES, default="machine")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--policy-path")
    parser.add_argument("--reviews-path")
    result = run_b_v4_batch(**vars(parser.parse_args()))
    print(json.dumps({key: result[key] for key in
        ("status", "branch", "output_directory", "frames_processed", "operational_total")}))


if __name__ == "__main__":
    main()
