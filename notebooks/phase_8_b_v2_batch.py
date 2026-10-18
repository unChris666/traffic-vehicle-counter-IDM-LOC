"""CPU replay of frozen Phase 8 measurements under the user's B v2 policy.

The old model run, events, annotation tools and geometry remain immutable.
New geometry, accepted estimates and route logs use a separate output namespace.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time

import phase_8_annotation_batch as donor
import phase_8_annotation_helpers as retained
from phase_5_geometry_helpers import Geometry


CONFIG = "results/b_v2/config"
VEHICLES = {"motorcycle", "car", "truck", "bus"}
SOURCE_NAMES = ("phase_8_b_v2_batch.py", "phase_8_b_v2_counting.py", "phase_8_b_v2_annotation.py",
                "phase_5_geometry_helpers.py", "phase_8_annotation_batch.py", "phase_8_annotation_helpers.py")


def _json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def _bound(root, name, digest):
    path = donor._relative_path(root, name)
    donor._require(path.is_file() and donor.sha256_file(path) == digest,
                   "B v2 input bytes differ: " + name)
    return path


def prepare_b_v2_batch(*, repo_root, source_run_root=None, source_video_root=None,
                       input_root="/kaggle/input", video_ids=None):
    """Prove the exact original run before binding new, separate geometry."""
    prepared = donor.prepare_annotation_batch(repo_root=repo_root, source_run_root=source_run_root,
        source_video_root=source_video_root, input_root=input_root, video_ids=video_ids)
    root = Path(repo_root).resolve()
    manifest = donor._read(root / CONFIG / "geometry_manifest.json")
    policy = donor._read(root / CONFIG / "policy.json")
    donor._require(manifest.get("schema_version") == "phase8_b_v2_geometry_manifest_v1",
                   "Unknown B v2 geometry manifest")
    template = _bound(root, manifest["template_path"], manifest["template_sha256"])
    donor._require(policy.get("source_template_sha256") == manifest["template_sha256"],
                   "Policy/template binding mismatch")
    donor._require(policy.get("timeout_frames") == 60 and policy.get("timeout_clock") == "last_observed_origin"
        and policy.get("line_margin_half_width_px") == 25, "User's declared timeout/margin changed")
    donor._require(policy.get("category_policy") == "band_majority_ties_pending", "Undeclared category policy")
    geometries = {item["video_id"]: item for item in manifest["videos"]}
    donor._require(len(geometries) == len(manifest["videos"]) == 8 and set(geometries) == set(donor.VIDEO_IDS),
                   "B v2 needs eight explicit, unique source bindings")
    for job in prepared["jobs"]:
        entry = geometries[job["video_id"]]
        identity = deepcopy(job["source_identity"])
        donor._require(entry["video_sha256"] == identity["video_sha256"]
            and (entry["width"], entry["height"]) == (identity["width"], identity["height"]),
            "Shared template assigned to wrong source")
        path = _bound(root, entry["geometry_path"], entry["geometry_sha256"])
        geometry = donor._read(path)
        donor._require(geometry["user_template"]["sha256"] == manifest["template_sha256"]
            and geometry["source_video"]["sha256"] == identity["video_sha256"]
            and geometry["line_margin_half_width_px"] == policy["line_margin_half_width_px"],
            "Derived geometry/source/margin differs")
        Geometry.from_draft(path, identity["width"], identity["height"])
        identity.update(geometry_sha256=entry["geometry_sha256"])
        job.update(b_v2_geometry_path=path, b_v2_source_identity=identity)
    prepared.update(policy=policy, template_path=template,
        geometry_manifest_sha256=donor.sha256_file(root / CONFIG / "geometry_manifest.json"),
        policy_sha256=donor.sha256_file(root / CONFIG / "policy.json"))
    return prepared


def retained_relationships(path):
    """Reuse supported old relations; no new appearance/spatial association.

    Whole-ID grouping is explicitly experimental: supported raw-ID graph
    components must be cliques and must not have an unresolved internal pair.
    Ambiguous SAME_VEHICLE support is retained locally as a count conflict.
    """
    components, edges, ambiguous = [], set(), set()
    conflicts = defaultdict(set)
    for relation in retained.iter_json_array(path):
        kind, status = relation.get("type"), relation.get("status")
        if kind not in ("COMPONENT_OF", "SAME_VEHICLE") or status not in ("SUPPORTED", "UNRESOLVED"):
            continue
        first, second = relation["first_track_id"], relation["second_track_id"]
        frames = relation.get("features", {}).get("common_frame_indices", [])
        donor._require(type(first) is int and type(second) is int and first > 0 and second > 0
            and first != second and isinstance(frames, list) and frames
            and all(type(f) is int and f >= 0 for f in frames), "Invalid retained relation support")
        if kind == "COMPONENT_OF" and status == "SUPPORTED":
            components.append({"type": "COMPONENT_OF", "relation_id": relation["relation_id"],
                "vehicle_track_id": second, "component_track_id": first,
                "support_frames": sorted(set(frames))})
        elif kind == "SAME_VEHICLE":
            pair = frozenset((first, second))
            if status == "SUPPORTED":
                edges.add(pair)
            else:
                ambiguous.add(pair)
                for frame in frames:
                    conflicts[frame].update((first, second))
    graph = defaultdict(set)
    for pair in edges - ambiguous:
        first, second = sorted(pair)
        graph[first].add(second); graph[second].add(first)
    visited, units, groups = set(), {}, []
    for first in sorted(graph):
        if first in visited:
            continue
        todo, members = [first], set()
        while todo:
            current = todo.pop()
            if current in members:
                continue
            members.add(current); todo.extend(graph[current] - members)
        visited.update(members)
        if any(frozenset((a, b)) not in edges - ambiguous for a in members for b in members if a < b):
            continue
        group = sorted(members)
        unit = "retained-clique:" + ",".join(map(str, group))
        units.update({track: unit for track in group}); groups.append(group)
    return {"component_links": components, "unit_by_track": units,
            "unit_groups": groups, "identity_conflicts_by_frame": dict(conflicts)}


def adapted_frames(path, identity, frame_count, *, relationships=None):
    """Read actual source-linked emitted boxes, preserving every empty frame."""
    relations = relationships or {}
    units = relations.get("unit_by_track", {})
    conflicts = relations.get("identity_conflicts_by_frame", {})
    count = 0
    for record in retained._records(path):
        frame = record.get("frame_index")
        donor._require(type(frame) is int and frame == count, "B v2 source frames must start at zero and be continuous")
        for key in ("video_sha256", "parent_run_id", "variant", "width", "height"):
            donor._require(record.get(key) == identity.get(key), "Source cache identity differs: " + key)
        raw, tracks = record.get("raw_detections"), record.get("emitted_tracks")
        donor._require(isinstance(raw, list) and isinstance(tracks, list), "Missing raw/source tracks")
        seen, indices, observations = set(), set(), []
        for observation in tracks:
            track, index = observation.get("track_id"), observation.get("original_detection_index")
            donor._require(type(track) is int and track > 0 and track not in seen
                and type(index) is int and 0 <= index < len(raw) and index not in indices,
                "Repeated or invalid emitted source link")
            seen.add(track); indices.add(index)
            donor._require(observation.get("frame_index") == frame and observation.get("emitted") is True
                and observation.get("measurement_provenance") == "retained_phase_8_detection",
                "Only retained measured emitted track observations can count")
            box = retained._bbox(observation.get("raw_bbox")); detection = raw[index]
            donor._require(0 <= box[0] < box[2] <= identity["width"]
                and 0 <= box[1] < box[3] <= identity["height"], "BBox outside source image")
            donor._require(box == detection.get("bbox_xyxy_pixels")
                and all(observation.get(k) == detection.get(k) for k in ("class_name", "class_id", "confidence")),
                "Track measurement differs from original detection")
            confidence = observation.get("confidence")
            donor._require(isinstance(confidence, (float, int)) and not isinstance(confidence, bool)
                and math.isfinite(confidence), "Missing finite source confidence")
            if observation["class_name"] not in VEHICLES:
                continue
            item = deepcopy(observation)
            item.update(observed=True, identity_conflict=track in conflicts.get(frame, set()))
            if track in units:
                item["unit_id"] = units[track]
            observations.append(item)
        yield {"frame_index": frame, "observations": observations}
        count += 1
    donor._require(count == frame_count, "Full B v2 source cache frame count differs")


def _retention(directory):
    artifacts = []
    for path in sorted(Path(directory).rglob("*")):
        if path.is_file() and path.name != "retention_manifest.json":
            artifacts.append({"path": path.relative_to(directory).as_posix(),
                "sha256": donor.sha256_file(path), "size_bytes": path.stat().st_size})
    _json(Path(directory) / "retention_manifest.json", {"schema_version": "phase8_b_v2_retention_v1", "artifacts": artifacts})


def _source_snapshot(output):
    """Retain exact executable bytes, separately from scientific donor inputs."""
    directory = Path(__file__).resolve().parent
    result = {}
    for name in SOURCE_NAMES:
        path = directory / name
        data = path.read_bytes()
        archive = output / "source_snapshot" / (name + ".gz")
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(gzip.compress(data, mtime=0))
        result[str(path)] = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
            "retained_path": archive.relative_to(output).as_posix()}
    _json(output / "source_snapshot.json", result)
    return result


def run_b_v2_batch(*, repo_root, output_root="/kaggle/working/results/phase_8_b_v2",
                   source_run_root=None, source_video_root=None, input_root="/kaggle/input",
                   video_ids=None, render=True, progress=print, run_id=None):
    """Replay then optionally render each selected video; preserve partials."""
    import phase_8_b_v2_counting as counting
    prepared = prepare_b_v2_batch(repo_root=repo_root, source_run_root=source_run_root,
        source_video_root=source_video_root, input_root=input_root, video_ids=video_ids)
    identifier = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    donor._require(isinstance(identifier, str) and identifier and Path(identifier).name == identifier
        and identifier not in (".", "..") and "\\" not in identifier, "Unsafe run ID")
    output = Path(output_root).resolve() / identifier
    donor._require(not output.exists(), "Output run already exists; preserve prior results")
    donor._require(not output.is_relative_to(Path(prepared["source_run_root"]).resolve()),
                   "B v2 output cannot be placed inside original evidence")
    output.mkdir(parents=True)
    sources = _source_snapshot(output)
    report = {"schema_version": "phase8_b_v2_batch_v1", "run_id": identifier,
        "status": "running", "claim_type": "ACTUAL_RETAINED_CACHE_POLICY_REPLAY_NOT_MODEL_BENCHMARK",
        "output_directory": str(output), "selected_video_ids": prepared["selected_video_ids"],
        "all_eight_selected": prepared["all_eight_selected"], "videos": [],
        "policy": prepared["policy"], "policy_sha256": prepared["policy_sha256"],
        "geometry_manifest_sha256": prepared["geometry_manifest_sha256"],
        "baseline_run_id": donor.DONOR_RUN_ID, "baseline_accepted": donor.EXPECTED_ACCEPTED,
        "baseline_pending": donor.EXPECTED_PENDING, "original_model_caches_modified": False,
        "baseline_selected_accepted": sum(job["expected_pivot"]["accepted_total"] for job in prepared["jobs"]),
        "baseline_selected_pending": sum(job["expected_pending"] for job in prepared["jobs"]),
        "pending_semantics": "B_V2_UNIT_PASSAGE_DECISIONS_NOT_BASELINE_GEOMETRY_DIAGNOSTIC_ITEMS",
        "changed_factors": ["geometry", "eligibility", "category_window", "gap_routes", "automatic_timeout"],
        "executed_source_files": sources,
        "new_detector_tracker_reid_execution": False, "new_counting_policy_replay": True,
        "physical_identity_or_counting_accuracy_established": False,
        "python": platform.python_version(), "render_requested": bool(render)}
    _json(output / "batch_report.json", report)
    started = time.perf_counter()
    try:
        for job in prepared["jobs"]:
            video_id = job["video_id"]
            target = output / video_id; target.mkdir()
            row = {"video_id": video_id, "status": "running"}; report["videos"].append(row)
            geometry_data = donor._read(job["b_v2_geometry_path"])
            identity = job["b_v2_source_identity"]
            geometry = Geometry.from_draft(job["b_v2_geometry_path"], identity["width"], identity["height"])
            links = retained_relationships(job["paths"]["relations"])
            result = counting.replay_frames(adapted_frames(job["paths"]["records"], identity,
                job["metadata"]["frame_count"], relationships=links), geometry,
                source_identity=identity, policy=prepared["policy"])
            result.update(video_id=video_id, source_identity=identity,
                component_links=links["component_links"], unit_groups=links["unit_groups"])
            _json(target / "counting_result.json", result)
            _json(target / "geometry.json", geometry_data)
            row.update(status="counting_complete", frames=job["metadata"]["frame_count"],
                aggregate=result["aggregate"], pending=sum(str(d.get("status", "")).startswith("pending") for d in result["decisions"]),
                source_identity=identity, baseline_accepted=job["expected_pivot"]["accepted_total"],
                baseline_pending=job["expected_pending"], known_duplicate_groups=len(links["unit_groups"]))
            if progress:
                progress({"video_id": video_id, "stage": "counting_complete", "aggregate": result["aggregate"]})
            if render:
                import phase_8_b_v2_annotation as annotation
                annotation_report = annotation.render_video(job["video_path"], job["paths"]["records"],
                    result, geometry_data, target / (video_id + "-b-v2-annotated.mp4"),
                    fps=job["metadata"]["fps"], expected_frame_count=job["metadata"]["frame_count"],
                    source_identity=identity, component_relations=links["component_links"],
                    progress=(lambda value: progress(dict(value, video_id=video_id))) if progress else None)
                _json(target / "annotation_report.json", annotation_report)
                row["annotation"] = annotation_report
            row["status"] = "completed"
            _json(output / "batch_report.json", report)
        report.update(status="completed_research_policy_replay_pending_physical_audit",
            all_selected_completed=True,
            all_eight_completed=prepared["all_eight_selected"] and len(report["videos"]) == 8,
            frames_processed=sum(row["frames"] for row in report["videos"]),
            operational_total=sum(row["aggregate"]["total"] for row in report["videos"]),
            pending_total=sum(row["pending"] for row in report["videos"]))
    except Exception as error:
        report.update(status="failed_or_partial", all_selected_completed=False,
            all_eight_completed=False, error_type=type(error).__name__, error=str(error))
        raise
    finally:
        changed_sources = [path for path, value in sources.items()
            if not Path(path).is_file() or donor.sha256_file(path) != value["sha256"]]
        report["source_files_unchanged_during_execution"] = not changed_sources
        if changed_sources:
            report.update(status="failed_or_partial", all_selected_completed=False,
                all_eight_completed=False, error="Executable source changed during execution")
        report["wall_seconds"] = time.perf_counter() - started
        _json(output / "batch_report.json", report)
        _retention(output)
        if changed_sources:
            raise RuntimeError("B v2 executable source changed during execution")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-run-root")
    parser.add_argument("--source-video-root")
    parser.add_argument("--input-root", default="/kaggle/input")
    parser.add_argument("--output-root", default="/kaggle/working/results/phase_8_b_v2")
    parser.add_argument("--video-ids", nargs="+")
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    result = run_b_v2_batch(repo_root=args.repo_root, source_run_root=args.source_run_root,
        source_video_root=args.source_video_root, input_root=args.input_root,
        output_root=args.output_root, video_ids=args.video_ids, render=not args.no_render)
    print(json.dumps({key: result[key] for key in ("status", "output_directory", "frames_processed", "operational_total", "pending_total")}))


if __name__ == "__main__":
    main()
