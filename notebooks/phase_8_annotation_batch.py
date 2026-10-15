"""CPU-only annotation replay of the immutable, completed TGDI Phase 8 run.

This controller never imports a detector, tracker, encoder or counting resolver.
It selects one retained machine snapshot per video and writes new review outputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import gzip
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import time


DONOR_RUN_ID = "20261015T083731_664817Z"
DONOR_MANIFEST_SHA256 = "79e8cf19747c63b34f8389d8f525925fd0c69e966f3d12ffb89716a5c89bd0dc"
DONOR_SOURCE_BUNDLE_PREFIX = "c08bc7b3cdded8ec"
EXPECTED_ACCEPTED = 58
EXPECTED_PENDING = 1825
EXPECTED_FRAMES = 72590
VIDEO_IDS = tuple(f"{day}_{period}" for day in ("weekday", "weekend")
                  for period in ("pagi", "siang", "sore", "malam"))
SUPPORTED_CATEGORIES = ("motorcycle", "car", "truck")
DIRECTIONS = ("A_TO_B", "B_TO_A")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class AnnotationBatchError(RuntimeError):
    """Partial output is retained, but the requested render did not complete."""


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_file(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _read(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _inside(path, parent):
    return path == parent or parent in path.parents


def _relative_path(root, relative):
    relative = Path(relative)
    _require(not relative.is_absolute() and ".." not in relative.parts,
             "Retained artifact path must be relative and cannot escape the donor root")
    resolved = (root / relative).resolve()
    _require(_inside(resolved, root), "Retained artifact symlink escapes the donor root")
    return resolved


def _index_manifest(manifest):
    _require(manifest.get("schema_version") == "phase8_batch_v1", "Unexpected donor retention schema")
    result = {}
    for row in manifest.get("artifacts", []):
        path, digest, size = row.get("path"), row.get("sha256"), row.get("size_bytes")
        _require(isinstance(path, str) and path not in result, "Missing or duplicate retained artifact path")
        _require(isinstance(digest, str) and _HASH.fullmatch(digest), "Invalid retained artifact SHA")
        _require(type(size) is int and size >= 0, "Invalid retained artifact byte size")
        _relative_path(Path("/donor"), path)
        result[path] = row
    _require(bool(result), "Empty donor retention manifest")
    return result


def locate_source_run(source_run_root=None, *, input_root="/kaggle/input"):
    """Locate the exact completed kernel output, rather than choosing the latest run."""
    if source_run_root is not None:
        candidates = [Path(source_run_root).resolve() / "batch_retention_manifest.json"]
    else:
        base = Path(input_root).resolve()
        _require(base.is_dir(), "Kaggle input root unavailable; set SOURCE_RUN_ROOT explicitly")
        candidates = sorted(base.rglob("batch_retention_manifest.json"))
    matching = {path.resolve().parent for path in candidates
                if path.is_file() and sha256_file(path) == DONOR_MANIFEST_SHA256}
    _require(len(matching) == 1,
             "Expected one Phase 8 Version 2 donor with the exact retained manifest SHA; "
             "attach chrisbiran/phase-8-tgdi-full-video-research as a notebook input, or set SOURCE_RUN_ROOT")
    return matching.pop()


def _verify_artifact(root, index, relative, retained_inputs):
    _require(relative in index, "Artifact absent from the immutable donor manifest: " + relative)
    row = index[relative]
    path = _relative_path(root, relative)
    _require(path.is_file(), "Required retained artifact is unavailable: " + str(path))
    _require(path.stat().st_size == row["size_bytes"] and sha256_file(path) == row["sha256"],
             "Retained artifact bytes differ: " + relative)
    retained_inputs[str(path)] = {"path": str(path), "sha256": row["sha256"], "size_bytes": row["size_bytes"]}
    return path


def _selected_ids(video_ids):
    selected = list(VIDEO_IDS if video_ids is None else video_ids)
    _require(bool(selected) and all(isinstance(v, str) and v in VIDEO_IDS for v in selected),
             "VIDEO_IDS must contain known TGDI video IDs")
    _require(len(set(selected)) == len(selected), "Duplicate VIDEO_IDS would render the same snapshot twice")
    return selected


def _source_video(video, source_video_root, input_root):
    filename = video.get("metadata_confirmation", {}).get("source_filename")
    _require(isinstance(filename, str) and Path(filename).name == filename,
             "Actual source filename is missing or invalid")
    if source_video_root is not None:
        base = Path(source_video_root).resolve()
        candidates = [base / filename]
    else:
        base = Path(input_root).resolve()
        _require(base.is_dir(), "Input root unavailable; set SOURCE_VIDEO_ROOT")
        candidates = list(base.rglob(filename))
    paths = set()
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            _require(_inside(resolved, base), "Source video symlink escapes the selected dataset root")
            paths.add(resolved)
    _require(len(paths) == 1, "Expected exactly one actual source video named " + filename)
    path = paths.pop()
    _require(sha256_file(path) == video["source_sha256"], "Actual source video bytes differ: " + filename)
    return path


def _event_totals(events):
    event_ids, passages = set(), set()
    pivot = {category: {direction: 0 for direction in DIRECTIONS} for category in SUPPORTED_CATEGORIES}
    for event in events:
        _require(event.get("type") == "CountEvent" and event.get("status") == "accepted"
                 and event.get("accepted_count_event") is True, "Only typed accepted CountEvent may enter the pivot")
        category, direction = event.get("category"), event.get("direction")
        _require(category in pivot and direction in DIRECTIONS, "Unsupported accepted category or direction")
        event_id = event.get("event_id")
        passage = (event.get("physical_unit_id"), event.get("passage_id"))
        _require(isinstance(event_id, str) and event_id and event_id not in event_ids, "Duplicate accepted event")
        _require(all(isinstance(v, str) and v for v in passage) and passage not in passages,
                 "Duplicate physical-unit passage")
        _require(event.get("manual_review_applied") is not True, "This render selects the original machine snapshot only")
        event_ids.add(event_id); passages.add(passage)
        pivot[category][direction] += 1
    return {"accepted_total": len(events), "by_category_direction": pivot,
            "by_category": {c: sum(values.values()) for c, values in pivot.items()},
            "by_direction": {d: sum(values[d] for values in pivot.values()) for d in DIRECTIONS},
            "event_ids": sorted(event_ids)}


def _decision_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def prepare_annotation_batch(*, repo_root, source_run_root=None, source_video_root=None,
                             input_root="/kaggle/input", video_ids=None):
    """Verify original bytes and source identities before creating any output."""
    selected = _selected_ids(video_ids)
    repo_root = Path(repo_root).resolve()
    root = locate_source_run(source_run_root, input_root=input_root)
    manifest_path = root / "batch_retention_manifest.json"
    retained_inputs = {str(manifest_path): {"path": str(manifest_path), "sha256": DONOR_MANIFEST_SHA256,
                                           "size_bytes": manifest_path.stat().st_size}}
    index = _index_manifest(_read(manifest_path))
    def bound(relative):
        return _verify_artifact(root, index, relative, retained_inputs)
    manifest = _read(bound("input_manifest.json"))
    results = _read(bound("per_video_results.json"))
    ledger_path = bound("accepted_event_ledger.json")
    ledger = _read(ledger_path)
    queue = _read(bound("audit_queue.json"))
    report = _read(bound("batch_report.json"))
    _require(report.get("run_id") == DONOR_RUN_ID and report.get("all_eight_videos_processed") is True
             and report.get("status") == "completed_research_snapshots_pending_audit", "Donor is not the completed Phase 8 research run")
    original_path = report.get("source_mount_resolution", {}).get("original_manifest_path", "")
    _require("phase8_source_snapshot_" + DONOR_SOURCE_BUNDLE_PREFIX in original_path,
             "Donor is not the retained Phase 8 source-bundle snapshot")
    _require(report.get("accepted_observed_event_count") == EXPECTED_ACCEPTED
             and report.get("pending_observed_count") == EXPECTED_PENDING
             and len(ledger) == EXPECTED_ACCEPTED and len(queue) == EXPECTED_PENDING,
             "Donor accepted/pending totals changed")
    _require(report.get("accepted_event_ledger") == ledger and report.get("audit_queue") == queue,
             "Batch report, accepted ledger and audit queue disagree")
    _require(report.get("input_manifest_sha256") == index["input_manifest.json"]["sha256"],
             "Donor input-manifest binding differs")
    del report
    video_map = {video["video_id"]: video for video in manifest["videos"]}
    result_map = {result["video_id"]: result for result in results}
    _require(len(video_map) == len(manifest["videos"]) == 8 and set(video_map) == set(VIDEO_IDS)
             and len(result_map) == len(results) == 8 and set(result_map) == set(VIDEO_IDS),
             "Expected exactly eight unique original TGDI input/result slots")
    _require(sum(result["frames_processed"] for result in results) == EXPECTED_FRAMES,
             "Original eight-video frame coverage differs")
    ledger_by_video = {video_id: [] for video_id in VIDEO_IDS}
    queue_by_video = {video_id: {} for video_id in VIDEO_IDS}
    for row in ledger:
        _require(row.get("video_id") in ledger_by_video and row.get("snapshot_kind") == "machine",
                 "Ledger contains an unknown video or mixed reviewed snapshot")
        ledger_by_video[row["video_id"]].append(row)
    for row in queue:
        video_id, candidate_id = row.get("video_id"), row.get("candidate_id")
        _require(video_id in queue_by_video and row.get("snapshot_kind") == "machine"
                 and candidate_id not in queue_by_video[video_id]
                 and str(row.get("status", "")).startswith("pending"), "Invalid or duplicate original pending candidate")
        queue_by_video[video_id][candidate_id] = _decision_digest(row["decision"])
    del queue
    gc.collect()
    jobs = []
    for video_id in selected:
        video, result = video_map[video_id], result_map[video_id]
        _require(result.get("status") == "completed_full_video_pipeline_machine_snapshot_review_pending"
                 and result.get("snapshot", {}).get("kind") == "machine"
                 and result.get("scope") == "full_video", "Selected donor snapshot is not completed full-video machine output")
        metadata, identity = video["observed_metadata"], result["source_identity"]
        _require(result["snapshot"]["source_identity"] == identity and result["report"]["source_identity"] == identity
                 and identity["video_sha256"] == video["source_sha256"]
                 and identity["geometry_sha256"] == video["geometry_sha256"]
                 and (identity["width"], identity["height"]) == (metadata["width"], metadata["height"])
                 and result["frames_processed"] == metadata["frame_count"] and identity["variant"] == "raw",
                 "Selected source, geometry, frame scope or identity differs")
        paths = {name: bound(f"{video_id}/{relative}") for name, relative in {
            "records": "track_records.jsonl.gz", "decisions": "counting/machine_passage_decisions.json.gz",
            "events": "counting/machine_count_events.json.gz", "relations": "counting/relations.json.gz",
            "configuration": "counting/counting_configuration.json", "aggregate": "counting/machine_aggregate.json",
            "counting_report": "counting/counting_report.json", "report": "report.json"}.items()}
        source_report = _read(paths["report"])
        _require(source_report == result["report"], "Per-video report changed relative to the selected original result")
        _require(index[f"{video_id}/track_records.jsonl.gz"]["sha256"] == identity["records_sha256"],
                 "Original measurement cache SHA differs from selected identity")
        configuration = _read(paths["configuration"])
        _require(configuration.get("input_identity") == identity, "Counting configuration has a different source identity")
        for name in ("events", "decisions", "configuration"):
            _require(result["snapshot"][name + "_sha256"] == sha256_file(paths[name]),
                     "Selected snapshot binding differs: " + name)
        events, decisions = _read(paths["events"]), _read(paths["decisions"])
        _require(sorted(events, key=lambda e: e["event_id"]) ==
                 sorted((row["event"] for row in ledger_by_video[video_id]), key=lambda e: e["event_id"]),
                 "Selected machine events differ from the original accepted ledger")
        for row in ledger_by_video[video_id]:
            _require(row["source_identity"] == identity
                     and row["snapshot_events_sha256"] == result["snapshot"]["events_sha256"]
                     and row["counting_configuration_sha256"] == result["snapshot"]["configuration_sha256"],
                     "Accepted ledger selected another namespace/configuration")
        totals = _event_totals(events)
        aggregate = _read(paths["aggregate"])
        _require(aggregate == result["aggregate"] and aggregate.get("total") == totals["accepted_total"]
                 and sorted(aggregate.get("event_ids", [])) == totals["event_ids"]
                 and all(aggregate["by_category"].get(c) == n for c, n in totals["by_category"].items())
                 and aggregate.get("by_direction") == totals["by_direction"], "Original event aggregate does not reconcile")
        pending = {d["candidate_id"]: _decision_digest(d) for d in decisions if str(d.get("status", "")).startswith("pending")}
        _require(pending == queue_by_video[video_id], "Pending decisions differ from the retained audit queue")
        _require(len({d["candidate_id"] for d in decisions}) == len(decisions), "Duplicate original candidate decision")
        accepted_decisions = {d["event_id"] for d in decisions if d.get("accepted_count_event") is True}
        _require(accepted_decisions == set(totals["event_ids"]), "Accepted decisions and events disagree")
        geometry_path = _relative_path(repo_root, video["geometry_path"])
        _require(geometry_path.is_file() and sha256_file(geometry_path) == identity["geometry_sha256"],
                 "Accepted geometry bytes changed")
        geometry = _read(geometry_path)
        _require(geometry.get("geometry_contract_accepted") is True
                 and geometry.get("source_video", {}).get("sha256") == identity["video_sha256"],
                 "Geometry is unapproved or belongs to another actual source")
        video_path = _source_video(video, source_video_root, input_root)
        for path, digest in ((geometry_path, identity["geometry_sha256"]), (video_path, identity["video_sha256"])):
            retained_inputs[str(path)] = {"path": str(path), "sha256": digest, "size_bytes": path.stat().st_size}
        jobs.append({"video_id": video_id, "video_path": video_path, "geometry_path": geometry_path,
                     "paths": paths, "source_identity": identity, "metadata": metadata,
                     "expected_pivot": totals, "expected_pending": len(pending),
                     "category_uses_future_evidence_count": sum(
                         e.get("category_decision_latest_evidence_frame", -1) > e["geometry_evidence"]["confirmation_frame"] for e in events)})
        del decisions, events, source_report
        gc.collect()
    return {"source_run_root": root, "repo_root": repo_root, "jobs": jobs,
            "ledger_path": ledger_path, "verified_input_files": list(retained_inputs.values()),
            "selected_video_ids": selected, "all_eight_selected": set(selected) == set(VIDEO_IDS),
            "baseline_accepted": EXPECTED_ACCEPTED, "baseline_pending": EXPECTED_PENDING,
            "selected_accepted": sum(job["expected_pivot"]["accepted_total"] for job in jobs),
            "selected_pending": sum(job["expected_pending"] for job in jobs)}


def _retention(directory):
    files = [{"path": str(path.relative_to(directory)), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
             for path in sorted(directory.rglob("*")) if path.is_file() and path.name != "annotation_retention_manifest.json"]
    _write(directory / "annotation_retention_manifest.json", {"schema_version": "phase8_annotation_retention_v1", "artifacts": files})


def run_annotation_batch(*, repo_root, output_root="/kaggle/working/phase_8_annotated_review_v1",
                         source_run_root=None, source_video_root=None, input_root="/kaggle/input",
                         video_ids=None, preview_frames=(), progress=print):
    """Render selected original snapshots sequentially; reject partial execution."""
    began = time.perf_counter()
    prepared = prepare_annotation_batch(repo_root=repo_root, source_run_root=source_run_root,
        source_video_root=source_video_root, input_root=input_root, video_ids=video_ids)
    base = Path(output_root).resolve()
    _require(not _inside(base, prepared["source_run_root"]), "Output must not overwrite the original Phase 8 donor")
    for job in prepared["jobs"]:
        _require(not _inside(base, job["video_path"].parent), "Output must not be inside the raw dataset")
    destination = base / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    destination.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": "phase8_annotation_batch_v1", "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
        "donor_run_id": DONOR_RUN_ID, "donor_manifest_sha256": DONOR_MANIFEST_SHA256,
        "source_bundle_prefix": DONOR_SOURCE_BUNDLE_PREFIX, "source_run_root": str(prepared["source_run_root"]),
        "output_directory": str(destination), "selected_video_ids": prepared["selected_video_ids"],
        "all_eight_selected": prepared["all_eight_selected"], "baseline_accepted": EXPECTED_ACCEPTED,
        "baseline_pending": EXPECTED_PENDING, "selected_expected_accepted": prepared["selected_accepted"],
        "selected_expected_pending": prepared["selected_pending"], "detector_tracker_encoder_counting_rerun": False,
        "snapshot_kind": "machine", "original_aggregates_changed": False,
        "timeline_semantics": "FINAL_OFFLINE_ACCEPTED_SNAPSHOT_REPLAY_AT_STORED_GEOMETRY_CONFIRMATION_FRAME_NOT_CAUSAL_DECISION_AVAILABILITY",
        "pending_semantics": "CANDIDATES_NOT_UNIQUE_PHYSICAL_VEHICLES_AND_EXCLUDED_FROM_ACCEPTED_PIVOT",
        "identity_gap_semantics": "NO_NEW_ID_STITCHING_OR_COMPONENT_INFERENCE", "runtime": {"python": platform.python_version()},
        "controller_sha256": sha256_file(__file__), "videos": [], "errors": []}
    _write(destination / "input_hashes.json", prepared["verified_input_files"])
    _write(destination / "annotation_batch_report.json", report)
    module_directory = str(Path(__file__).resolve().parent)
    if module_directory not in sys.path:
        sys.path.insert(0, module_directory)
    try:
        from phase_8_annotation_helpers import render_review_video
        import cv2
        import numpy
        report["runtime"].update(opencv=cv2.__version__, numpy=numpy.__version__)
        for job in prepared["jobs"]:
            video_id, paths = job["video_id"], job["paths"]
            try:
                if progress:
                    progress(f"{video_id}: render cache asli; tidak menjalankan model/counting ulang")
                expected_hashes = {key: sha256_file(paths[key]) for key in ("records", "decisions", "events", "relations")}
                expected_hashes.update(video=job["source_identity"]["video_sha256"],
                    geometry=job["source_identity"]["geometry_sha256"], ledger=sha256_file(prepared["ledger_path"]))
                result = render_review_video(job["video_path"], paths["records"], job["geometry_path"],
                    paths["decisions"], paths["events"], paths["relations"], destination / video_id,
                    source_identity=job["source_identity"], fps=job["metadata"]["fps"],
                    expected_frame_count=job["metadata"]["frame_count"], video_id=video_id,
                    ledger_path=prepared["ledger_path"], expected_input_sha256=expected_hashes,
                    preview_frames=preview_frames, progress=progress)
                # Renderer performs full MP4 re-decode and its own event-level reconciliation.
                _require(result.get("final_accepted") == job["expected_pivot"]["accepted_total"]
                         and result.get("final_pending_candidates") == job["expected_pending"]
                         and all(result.get("final_pivot", {}).get(c) == values for c, values in job["expected_pivot"]["by_category_direction"].items()),
                         "Rendered final pivot/pending differs from the original snapshot")
                _require(result.get("output_video", {}).get("frames_written") == job["metadata"]["frame_count"]
                         and result["output_video"].get("frames_redecoded") == job["metadata"]["frame_count"]
                         and result.get("inputs_unchanged_after_render") is True
                         and result.get("source_pixel_hash_verified_every_frame") is True,
                         "Full-frame source/render/decode verification is incomplete")
                row = {"video_id": video_id, "status": "completed", "expected_frame_count": job["metadata"]["frame_count"],
                       "accepted_total": job["expected_pivot"]["accepted_total"], "pending_count": job["expected_pending"],
                       "expected_pivot": job["expected_pivot"], "category_uses_future_evidence_count": job["category_uses_future_evidence_count"],
                       "render_report": result}
                report["videos"].append(row)
            except Exception as exc:
                error = {"video_id": video_id, "status": "failed", "exception_type": type(exc).__name__, "message": str(exc)}
                report["videos"].append(error); report["errors"].append(error)
            _write(destination / "annotation_batch_report.json", report)
            gc.collect()
        for original in prepared["verified_input_files"]:
            path = Path(original["path"])
            _require(path.is_file() and path.stat().st_size == original["size_bytes"] and sha256_file(path) == original["sha256"],
                     "Original input changed during annotation: " + str(path))
        report["all_verified_input_bytes_preserved"] = True
        completed = [row for row in report["videos"] if row["status"] == "completed"]
        report["completed_video_count"] = len(completed)
        report["all_eight_annotation_videos_completed"] = prepared["all_eight_selected"] and len(completed) == 8 and not report["errors"]
        report["selected_accepted_replayed"] = sum(row["accepted_total"] for row in completed)
        report["selected_pending_retained"] = sum(row["pending_count"] for row in completed)
        _require(not report["errors"] and len(completed) == len(prepared["jobs"]), "One or more requested annotation renders failed")
        _require(report["selected_accepted_replayed"] == prepared["selected_accepted"]
                 and report["selected_pending_retained"] == prepared["selected_pending"], "Selected final counters do not reconcile")
        report["status"] = "completed_all_eight_render_only" if prepared["all_eight_selected"] else "completed_selected_subset_not_full_batch"
    except BaseException as exc:
        report["status"] = "failed_or_partial_annotation_batch"
        report["terminal_error"] = {"exception_type": type(exc).__name__, "message": str(exc)}
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["wall_seconds"] = time.perf_counter() - began
        _write(destination / "annotation_batch_report.json", report); _retention(destination)
        raise AnnotationBatchError(f"Annotation incomplete; actual output/error retained at {destination}") from exc
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    report["wall_seconds"] = time.perf_counter() - began
    _write(destination / "annotation_batch_report.json", report); _retention(destination)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--source-run-root")
    parser.add_argument("--source-video-root")
    parser.add_argument("--input-root", default="/kaggle/input")
    parser.add_argument("--output-root", default="/kaggle/working/phase_8_annotated_review_v1")
    parser.add_argument("--video-ids", nargs="+", choices=VIDEO_IDS)
    parser.add_argument("--preview-frames", nargs="*", type=int, default=[])
    args = parser.parse_args()
    report = run_annotation_batch(**vars(args))
    print(json.dumps({key: report[key] for key in ("status", "output_directory", "selected_video_ids", "selected_accepted_replayed", "selected_pending_retained")}, indent=2))


if __name__ == "__main__":
    main()
