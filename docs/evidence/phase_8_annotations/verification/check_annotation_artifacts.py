"""Independent annotation-only source/evidence retention validation.

Reads retained JSON, gzip bytes, notebook literals and PNG headers. Never runs
models, counting, rendering, or video decoding. MP4 re-decode claims refer only
to the actual executed renderer reports; this audit does not download/redecode
the eight videos. Delivery checks read source/derivative bytes and retained
FFprobe reports without decoding video. Final capture requires completed
actual Kaggle evidence and the authorized GitHub Release publication receipt.
"""
from __future__ import annotations

import argparse
import ast
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


BASE = Path("docs/evidence/phase_8_annotations")
FINAL_MANIFEST = BASE / "final_retention_manifest.json"
FINAL_VALIDATION = BASE / "final_artifact_validation.json"
SOURCE_FILES = (
    "notebooks/phase_8_annotation_helpers.py", "notebooks/phase_8_annotation_tests.py",
    "notebooks/phase_8_annotation_batch.py", "notebooks/phase_8_annotation_batch_tests.py",
    "notebooks/08a_annotation_review.ipynb",
)
CONTEXT_FILES = ("README.md", "docs/PHASE_8_REVIEW.md", "docs/ANNOTATED_VIDEO_REVIEW.md")
DONOR_SHA = "79e8cf19747c63b34f8389d8f525925fd0c69e966f3d12ffb89716a5c89bd0dc"
DONOR_RUN = "20261015T083731_664817Z"
VIDEO_IDS = tuple(f"{day}_{period}" for day in ("weekday", "weekend") for period in ("pagi", "siang", "sore", "malam"))
CATEGORIES = ("motorcycle", "car", "truck")
DIRECTIONS = ("A_TO_B", "B_TO_A")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read(path):
    data = Path(path).read_bytes()
    if str(path).endswith(".gz"):
        data = gzip.decompress(data)
    def reject(value):
        raise ValueError("Nonfinite JSON constant: " + value)
    return json.loads(data, parse_constant=reject)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def png_size(path):
    with Path(path).open("rb") as source:
        header = source.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("Invalid retained PNG header: " + str(path))
    return struct.unpack(">II", header[16:24])


def capture_files(repo):
    files = {Path(name) for name in SOURCE_FILES + CONTEXT_FILES}
    files.update(path.relative_to(repo) for path in (repo / BASE).rglob("*") if path.is_file())
    return sorted(path for path in files if path not in (FINAL_MANIFEST, FINAL_VALIDATION)
                  and "__pycache__" not in path.parts and path.suffix != ".pyc")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--preliminary", action="store_true", help="Audit available evidence; never capture or claim remote completion")
    args = parser.parse_args()
    if args.capture and args.preliminary:
        parser.error("A final capture cannot use preliminary mode")
    repo = args.repo.resolve()
    base = repo / BASE
    totals, passed, failures = Counter(), Counter(), []
    diagnostics = {"model_counting_rendering_video_decode_executed_by_audit": False,
                   "MP4_download_or_independent_redecode_performed_by_audit": False,
                   "physical_passage_accuracy_or_ground_truth_established": False}

    def check(group, condition, detail=None):
        totals[group] += 1
        if bool(condition):
            passed[group] += 1
        elif sum(item["check"] == group for item in failures) < 25:
            failures.append({"check": group, "detail": detail})
        return bool(condition)

    def bound(path, expected, size=None, group="artifact"):
        path = Path(path)
        exists = check(group + ":exists", path.is_file(), str(path))
        return exists and check(group + ":exact_SHA_and_bytes", sha(path) == expected
                                and (size is None or path.stat().st_size == size), str(path))

    # Only these two explicitly archived mutable context documents may replace
    # their former bytes in the immutable prior 367-artifact delivery.
    mapping = read(base / "baseline/context_retention_mapping.json")
    old_manifest_path = repo / mapping["prior_delivery_manifest"]
    bound(old_manifest_path, mapping["prior_delivery_manifest_sha256"], group="prior367:manifest_unchanged")
    archived_context = {}
    check("prior367:only_two_explicit_context_archives", {item["original_path"] for item in mapping["artifacts"]}
          == {"README.md", "docs/PHASE_8_REVIEW.md"})
    for item in mapping["artifacts"]:
        path = repo / item["retained_path"]
        if bound(path, item["retained_sha256"], item["retained_size_bytes"], group="prior367:compressed_context"):
            original = gzip.decompress(path.read_bytes())
            if check("prior367:logical_original_context", digest(original) == item["original_sha256"]
                     and len(original) == item["original_size_bytes"], item["original_path"]):
                archived_context[item["original_path"]] = (item["original_sha256"], len(original))
    old_manifest = read(old_manifest_path)
    check("prior367:original_cardinality", old_manifest["artifact_count"] == len(old_manifest["artifacts"]) == 367)
    for item in old_manifest["artifacts"]:
        path = repo / item["path"]
        direct = path.is_file() and sha(path) == item["sha256"] and path.stat().st_size == item["size_bytes"]
        check("prior367:unchanged_artifact_or_explicit_context_only", direct or
              archived_context.get(item["path"]) == (item["sha256"], item["size_bytes"]), item["path"])

    # The actual original batch is retained as exact logical bytes. None of the
    # output comparisons below use the former context-document fallback.
    baseline = read(base / "baseline/baseline_retention.json")
    check("baseline:actual_version2_identity", baseline["source_kernel_version"] == 2
          and baseline["source_run_id"] == DONOR_RUN and baseline["source_batch_retention_manifest_sha256"] == DONOR_SHA
          and baseline["new_model_inference_executed"] is False
          and baseline["visual_review_of_original_full_videos_performed"] is False and len(baseline["artifacts"]) == 13)
    donor_manifest = read(base / "baseline/batch_retention_manifest.json.gz")
    donor_index = {item["path"]: item for item in donor_manifest["artifacts"]}
    check("baseline:unique_original_manifest_entries", len(donor_index) == len(donor_manifest["artifacts"]))
    original_objects = {}
    for item in baseline["artifacts"]:
        path = repo / item["retained_path"]
        if bound(path, item["retained_sha256"], item["retained_size_bytes"], group="baseline:compressed_original"):
            logical = gzip.decompress(path.read_bytes())
            relative = item["original_kaggle_output_path"].split(DONOR_RUN + "/", 1)[1]
            check("baseline:original_exact_logical_bytes", digest(logical) == item["original_sha256"]
                  and len(logical) == item["original_size_bytes"], relative)
            if relative == "batch_retention_manifest.json":
                check("baseline:original_manifest_exact_SHA", digest(logical) == DONOR_SHA)
            else:
                expected = donor_index.get(relative)
                check("baseline:original_payload_bound_by_donor_manifest", expected is not None
                      and expected["sha256"] == digest(logical) and expected["size_bytes"] == len(logical), relative)
            original_objects[relative] = json.loads(logical)
    original_report = original_objects["batch_report.json"]
    original_results = {row["video_id"]: row for row in original_objects["per_video_results.json"]}
    ledger = original_objects["accepted_event_ledger.json"]
    queue = original_report["audit_queue"]
    check("baseline:original_batch_complete_research_only", original_report["run_id"] == DONOR_RUN
          and original_report["all_eight_videos_processed"] is True
          and original_report["accepted_observed_event_count"] == len(ledger) == 58
          and original_report["pending_observed_count"] == len(queue) == 1825
          and original_report["accepted_event_ledger"] == ledger and set(original_results) == set(VIDEO_IDS)
          and sum(row["frames_processed"] for row in original_results.values()) == 72590)
    ledger_by_video, queue_by_video = defaultdict(list), defaultdict(list)
    for row in ledger:
        ledger_by_video[row["video_id"]].append(row)
    for row in queue:
        queue_by_video[row["video_id"]].append(row)
        check("baseline:pending_not_accepted_count", row["snapshot_kind"] == "machine"
              and str(row["status"]).startswith("pending") and row["decision"]["accepted_count_event"] is False, row["candidate_id"])
    check("baseline:unique_accepted_batch_ids", len({row["batch_event_id"] for row in ledger}) == 58)
    future_categories = 0
    expected_pivots = {}
    for video_id in VIDEO_IDS:
        result = original_results[video_id]
        identity = result["source_identity"]
        check("baseline:selected_machine_source_and_reports", result["snapshot"]["kind"] == "machine"
              and result["snapshot"]["source_identity"] == identity and result["scope"] == "full_video"
              and original_objects[video_id + "/report.json"] == result["report"], video_id)
        pivot = {category: {direction: 0 for direction in DIRECTIONS} for category in CATEGORIES}
        event_ids, passages = set(), set()
        for row in ledger_by_video[video_id]:
            event = row["event"]
            physical = (event["physical_unit_id"], event["passage_id"])
            check("baseline:unique_typed_machine_event_source", row["snapshot_kind"] == "machine" and row["source_identity"] == identity
                  and event["source_identity"] == identity and event["type"] == "CountEvent" and event["status"] == "accepted"
                  and event["accepted_count_event"] is True and event["event_id"] not in event_ids and physical not in passages
                  and event["category"] in CATEGORIES and event["direction"] in DIRECTIONS, event["event_id"])
            event_ids.add(event["event_id"]); passages.add(physical)
            pivot[event["category"]][event["direction"]] += 1
            future_categories += event["category_decision_latest_evidence_frame"] > event["geometry_evidence"]["confirmation_frame"]
            for name in ("events", "decisions", "configuration"):
                check("baseline:original_selected_snapshot_hash", result["snapshot"][name + "_sha256"] ==
                      donor_index[video_id + "/counting/" + {"events": "machine_count_events.json.gz", "decisions": "machine_passage_decisions.json.gz",
                                                          "configuration": "counting_configuration.json"}[name]]["sha256"], [video_id, name])
        expected_pivots[video_id] = pivot
        check("baseline:accepted_and_pending_totals_reconcile", result["aggregate"]["total"] == len(event_ids)
              and set(result["aggregate"]["event_ids"]) == event_ids, video_id)
    check("baseline:all_58_categories_use_future_evidence_not_online", future_categories == 58)

    preflight = read(base / "verification/all_eight_original_input_preflight.json")
    check("input_preflight:all_eight_readonly_original_inputs", preflight["ready"] is True and preflight["all_eight_selected"] is True
          and set(preflight["selected_video_ids"]) == set(VIDEO_IDS) and preflight["verified_input_count"] == len(preflight["inputs"]) == 86
          and preflight["baseline_accepted"] == preflight["selected_accepted"] == 58
          and preflight["baseline_pending"] == preflight["selected_pending"] == 1825
          and preflight["controller_sha256"] == sha(repo / SOURCE_FILES[2]))
    for row in preflight["videos"]:
        video_id = row["video_id"]
        check("input_preflight:original_counts_and_offline_timeline", row["expected_pivot"]["by_category_direction"] == expected_pivots[video_id]
              and row["expected_pivot"]["accepted_total"] == len(ledger_by_video[video_id])
              and row["expected_pending"] == len(queue_by_video[video_id])
              and row["frame_count"] == original_results[video_id]["frames_processed"]
              and row["future_category_events"] == len(ledger_by_video[video_id]), video_id)
    source_hashes = {row["source_identity"]["video_sha256"] for row in original_results.values()}
    geometry_hashes = {row["source_identity"]["geometry_sha256"] for row in original_results.values()}
    for item in preflight["inputs"]:
        if DONOR_RUN + "/" in item["path"]:
            relative = item["path"].split(DONOR_RUN + "/", 1)[1]
            expected = donor_index.get(relative)
            valid = item["sha256"] == DONOR_SHA if relative == "batch_retention_manifest.json" else (
                expected is not None and expected["sha256"] == item["sha256"] and expected["size_bytes"] == item["size_bytes"])
        else:
            valid = item["sha256"] in source_hashes | geometry_hashes
        check("input_preflight:every_record_binds_original_source_or_geometry", valid, item["path"])

    # Current canonical source and test evidence; syntax-only parsing executes
    # neither software tests nor any notebook cell in this audit.
    software = read(base / "verification/annotation_software_tests.json")
    check("software:52_passed_no_skip_no_model", software["tests_registered"] == software["tests_passed"] == 52
          and software["tests_skipped"] == 0 and software["successful"] is True
          and not software["failures"] and not software["errors"] and software["new_model_inference"] is False)
    for item in software["sources"]:
        bound(repo / item["path"], item["sha256"], group="software:executed_source")
    bound(repo / software["log"]["path"], software["log"]["sha256"], group="software:actual_execution_log")
    for name in SOURCE_FILES:
        if name.endswith(".py"):
            ast.parse((repo / name).read_text()); check("software:source_AST_valid", True, name)
    canonical_notebook = read(repo / SOURCE_FILES[-1])
    check("software:canonical_notebook_source_no_execution_claim", canonical_notebook["nbformat"] == 4 and all(
        cell.get("execution_count") is None and not cell.get("outputs") for cell in canonical_notebook["cells"] if cell["cell_type"] == "code"))

    # Exact 14-source CPU-only package, preserving canonical notebook cells.
    package = read(base / "kaggle_submission/source_bundle_manifest.json")
    submission = read(base / "kaggle_submission/submission.json")
    archive = repo / submission["submitted_archive_path"]
    bound(archive, submission["submitted_archive_sha256"], group="package:submitted_archive")
    notebook_bytes = gzip.decompress(archive.read_bytes())
    check("package:exact_submitted_source_SHA_size", digest(notebook_bytes) == submission["submitted_notebook_sha256"]
          == package["submitted_notebook"]["sha256"] and len(notebook_bytes) == submission["submitted_notebook_bytes"]
          == package["submitted_notebook"]["bytes"] < 1_000_000)
    submitted_notebook = json.loads(notebook_bytes)
    bundles = []
    for cell in submitted_notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        for node in ast.parse("".join(cell["source"])).body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            call = node.value
            if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "json" and call.func.attr == "loads" and len(call.args) == 1:
                try:
                    value = json.loads(ast.literal_eval(call.args[0]))
                except (ValueError, TypeError, SyntaxError):
                    continue
                if isinstance(value, dict) and value and all(isinstance(item, dict) and "gzip_base64" in item for item in value.values()):
                    bundles.append(value)
    check("package:exact_one_14_source_bundle", len(bundles) == 1 and len(bundles[0]) == package["source_file_count"] == 14)
    bundle = bundles[0]
    source_manifest = {name: {key: item[key] for key in ("sha256", "bytes")} for name, item in bundle.items()}
    check("package:source_binding_exact", source_manifest == package["source_files"] and digest(canonical(source_manifest).encode()) ==
          package["source_bundle_binding_sha256"] == submission["source_bundle_binding_sha256"])
    for name, item in bundle.items():
        data = gzip.decompress(base64.b64decode(item["gzip_base64"], validate=True))
        check("package:original_canonical_logical_source_bytes", digest(data) == item["sha256"] and len(data) == item["bytes"]
              and (repo / name).read_bytes() == data, name)
    check("package:canonical_cells_preserved_after_bootstrap", submitted_notebook["cells"][2:] == canonical_notebook["cells"])
    bound(base / "verification/build_render_bundle.py", package["builder"]["sha256"], group="package:builder_source")
    metadata_path = base / "kaggle_submission/kernel-metadata.json"
    bound(metadata_path, package["kernel_metadata"]["sha256"], group="package:metadata")
    metadata = read(metadata_path)
    check("package:private_cpu_no_internet_readonly_original_parent", metadata["is_private"] is True and metadata["enable_gpu"] is False
          and metadata["enable_tpu"] is False and metadata["enable_internet"] is False
          and metadata["kernel_sources"] == ["chrisbiran/phase-8-tgdi-full-video-research"]
          and metadata["dataset_sources"] == ["chrisbiran/tgdi-traffic-videos"]
          and package["original_input_mounts_read_only"] is True and package["original_parent_kernel_version"] == 2
          and package["original_batch_manifest_sha256"] == DONOR_SHA and package["new_model_execution"] is False
          and package["counting_decisions_modified"] is False and package["retained_model_caches_bundled"] is False
          and package["videos_bundled"] is False and package["model_weights_bundled"] is False)
    bootstrap = read(base / "kaggle_submission/bootstrap_and_guard_validation.json")
    check("package:actual_bootstrap_52_guards_no_actual_render", bootstrap["passed"] is True
          and bootstrap["tests_run"] == bootstrap["tests_passed"] == 52 and bootstrap["tests_failed"] == bootstrap["tests_errors"] == bootstrap["tests_skipped"] == 0
          and bootstrap["source_files_verified"] == 14 and bootstrap["source_bundle_binding_sha256"] == submission["source_bundle_binding_sha256"]
          and bootstrap["actual_source_video_rendering_executed"] is False and bootstrap["new_detector_tracker_reid_execution"] is False)

    def validate_render_report(report, video_id, group):
        original = original_results[video_id]
        check(group + ":source_identity_and_renderer", report["video_id"] == video_id and report["source_identity"] == original["source_identity"]
              and report["software_source_sha256"] == sha(repo / SOURCE_FILES[0]))
        check(group + ":full_native_source_and_output_redecode_report", report["output_video"]["frames_written"] ==
              report["output_video"]["frames_redecoded"] == original["frames_processed"]
              and report["source_image_region"] == {"x": 0, "y": 0, "width": 640, "height": 480, "resized": False,
                                                   "coordinate_transform": "IDENTITY_NATIVE_TOP_LEFT"}
              and report["source_pixel_hash_verified_every_frame"] is True and report["inputs_unchanged_after_render"] is True)
        check(group + ":unchanged_accepted_pending_pivot", report["final_accepted"] == len(ledger_by_video[video_id])
              and report["final_pending_candidates"] == len(queue_by_video[video_id])
              and all(report["final_pivot"][category] == pivot for category, pivot in expected_pivots[video_id].items())
              and all(value is None for category in ("bus_angkot", "pedestrian") for value in report["final_pivot"][category].values()))
        check(group + ":render_only_offline_measured_BC_no_identity_repair", report["new_detector_tracker_encoder_inference"] is False
              and report["counting_or_identity_resolver_rerun"] is False and report["occlusion_identity_recovery_modified"] is False
              and report["pending_excluded_from_pivot"] is True and report["category_color_basis"] == "CURRENT_RAW_MEASURED_CLASS"
              and "OFFLINE_FINAL_SNAPSHOT" in report["timeline_semantics"]
              and report["component_connector_policy"] == "ACCEPTED_EVENT_SUPPORTED_PASSAGE_LOCAL_MEASURED_COMMON_FRAMES_ONLY")
        for key, relative in {"records": video_id + "/track_records.jsonl.gz", "decisions": video_id + "/counting/machine_passage_decisions.json.gz",
                              "events": video_id + "/counting/machine_count_events.json.gz", "relations": video_id + "/counting/relations.json.gz",
                              "ledger": "accepted_event_ledger.json"}.items():
            expected = donor_index[relative]
            check(group + ":exact_original_donor_input_bytes", report["inputs"][key]["sha256"] == expected["sha256"]
                  and report["inputs"][key]["size_bytes"] == expected["size_bytes"], [video_id, key])
        check(group + ":raw_video_geometry_input_identity", report["inputs"]["video"]["sha256"] == original["source_identity"]["video_sha256"]
              and report["inputs"]["geometry"]["sha256"] == original["source_identity"]["geometry_sha256"])

    # One actual local render and a bounded photographic review, not eight
    # independently inspected physical-passage results.
    local_root = base / "local_review/weekday_pagi"
    local_report = read(local_root / "annotation_report.json")
    validate_render_report(local_report, "weekday_pagi", "local_render")
    display = read(local_root / "passage_display_index.json")
    bound(local_root / "passage_display_index.json", local_report["passage_display_index"]["sha256"], group="local_render:display_index")
    check("local_render:index_replays_exact_original_events", {item["event_id"] for item in display["events"]}
          == {item["event"]["event_id"] for item in ledger_by_video["weekday_pagi"]}
          and display["final_accepted"] == 6 and display["final_pending"] == 263
          and all(item["component_additional_increment"] == 0 and item["accepted_increment"] == 1
                  and item["replay_is_causal"] is False for item in display["events"]))
    visual_review = read(base / "local_review/bounded_visual_review.json")
    check("local_render:bounded_visual_review_no_ground_truth_claim", visual_review["frames_rendered_and_redecoded"] == 9052
          and visual_review["accepted"] == 6 and visual_review["pending"] == 263 and visual_review["new_model_or_counting_execution"] is False
          and visual_review["external_video"]["committed_to_git"] is False and "not physical validation" in visual_review["review_scope"])
    for item in visual_review["files"]:
        bound(repo / item["path"], item["sha256"], item["size_bytes"], group="local_render:retained_photographic_evidence")
        if item["path"].endswith(".png"):
            check("local_render:expanded_native_canvas_PNG_header", png_size(repo / item["path"]) == (1160, 720), item["path"])

    # Actual all-eight Kaggle reports are required for the final capture. The
    # report reader will be bound to the execution record when it is retained.
    remote_runs = []
    for path in base.rglob("annotation_batch_report.json"):
        report = read(path)
        if report.get("all_eight_annotation_videos_completed") is not True:
            continue
        remote_runs.append(path)
        check("remote_render:actual_complete_eight_render_only", report["status"] == "completed_all_eight_render_only"
              and report["donor_run_id"] == DONOR_RUN and report["donor_manifest_sha256"] == DONOR_SHA
              and report["controller_sha256"] == sha(repo / SOURCE_FILES[2]) and report["detector_tracker_encoder_counting_rerun"] is False
              and report["original_aggregates_changed"] is False and report["all_verified_input_bytes_preserved"] is True
              and report["selected_accepted_replayed"] == 58 and report["selected_pending_retained"] == 1825
              and report["completed_video_count"] == len(report["videos"]) == 8 and report["errors"] == [])
        check("remote_render:exact_eight_unique_slots", {row["video_id"] for row in report["videos"]} == set(VIDEO_IDS))
        frames = 0
        remote_index_path = path.parent / "annotation_retention_manifest.json"
        remote_index = {item["path"]: item for item in read(remote_index_path)["artifacts"]}
        for relative, item in remote_index.items():
            artifact = path.parent / relative
            check("remote_render:safe_original_output_manifest_path", not Path(relative).is_absolute()
                  and ".." not in Path(relative).parts and artifact.resolve().is_relative_to(path.parent.resolve()), relative)
            if artifact.is_file():
                bound(artifact, item["sha256"], item["size_bytes"], group="remote_render:exact_retained_output_bytes")
                if artifact.suffix == ".png":
                    check("remote_render:retained_canvas_PNG_header", png_size(artifact) == (1160, 720), relative)
        for row in report["videos"]:
            video_id, rendered = row["video_id"], row["render_report"]
            validate_render_report(rendered, video_id, "remote_render")
            check("remote_render:per_video_status_complete", row["status"] == "completed"
                  and row["accepted_total"] == len(ledger_by_video[video_id]) and row["pending_count"] == len(queue_by_video[video_id]))
            frames += rendered["output_video"]["frames_redecoded"]
            child_report_path = path.parent / video_id / "annotation_report.json"
            display_path = path.parent / video_id / "passage_display_index.json"
            check("remote_render:actual_child_report_equals_executed_batch_row", read(child_report_path) == rendered, video_id)
            bound(display_path, rendered["passage_display_index"]["sha256"], group="remote_render:actual_display_index")
            display = read(display_path)
            event_map = {item["event"]["event_id"]: item["event"] for item in ledger_by_video[video_id]}
            check("remote_render:display_maps_exact_original_event_and_pending_ids", len(display["events"]) == len(event_map)
                  and {item["event_id"] for item in display["events"]} == set(event_map)
                  and len(display["pending_candidates"]) == len(queue_by_video[video_id])
                  and {item["candidate_id"] for item in display["pending_candidates"]}
                  == {item["candidate_id"] for item in queue_by_video[video_id]}, video_id)
            for card in display["events"]:
                event = event_map[card["event_id"]]
                check("remote_render:original_offline_confirmation_and_component_zero", card["activation_frame"] == event["geometry_evidence"]["confirmation_frame"]
                      and card["category_latest_evidence_frame"] == event["category_decision_latest_evidence_frame"]
                      and card["source_vehicle_track_id"] == event["track_id"]
                      and card["physical_unit_id"] == event["physical_unit_id"] and card["passage_id"] == event["passage_id"]
                      and card["category"] == event["category"] and card["direction"] == event["direction"]
                      and card["accepted_increment"] == 1 and card["component_additional_increment"] == 0
                      and card["replay_is_causal"] is False, card["event_id"])
            video_relative = video_id + "/" + rendered["output_video"]["path"]
            original_video_entry = remote_index.get(video_relative)
            check("remote_render:MP4_metadata_bound_without_download_or_independent_decode", original_video_entry is not None
                  and original_video_entry["sha256"] == rendered["output_video"]["sha256"]
                  and original_video_entry["size_bytes"] == rendered["output_video"]["size_bytes"] > 0, video_id)
        check("remote_render:actual_72590_full_redecode_reported", frames == 72590)
    check("remote_render:actual_complete_evidence_required_for_final", len(remote_runs) == 1 or args.preliminary)
    terminal_path = base / "kaggle_submission/execution_terminal_record.json"
    check("remote_execution:terminal_evidence_required_for_final", terminal_path.is_file() or args.preliminary)
    if terminal_path.is_file():
        terminal = read(terminal_path)
        terminal_status = terminal.get("execution_status", terminal.get("status"))
        check("remote_execution:actual_complete_source_and_original_identity", terminal_status in ("COMPLETE", "KernelWorkerStatus.COMPLETE")
              and terminal["source_bundle_matches_submitted"] is True
              and terminal["expected_source_bundle_binding_sha256"] == submission["source_bundle_binding_sha256"])
        bound(repo / terminal["execution_log_path"], terminal["execution_log_sha256"], group="remote_execution:actual_execution_log")
        log_data = gzip.decompress((repo / terminal["execution_log_path"]).read_bytes())
        check("remote_execution:source_bundle_present_in_actual_log", submission["source_bundle_binding_sha256"] in log_data.decode("utf-8"))
        check("remote_execution:exact_logical_log_and_completed_counters", digest(log_data) == terminal["execution_log_logical_sha256"]
              and terminal["all_eight_completed"] is True and terminal["rendered_frames"] == 72590
              and terminal["accepted_unchanged"] == 58 and terminal["pending_unchanged"] == 1825
              and terminal["all_verified_input_bytes_preserved"] is True
              and terminal["original_machine_aggregate_changed"] is False
              and terminal["new_detector_tracker_reid_or_counting_execution"] is False)
        remote_run = repo / terminal["retained_run_path"]
        bound(remote_run / "annotation_batch_report.json", terminal["retained_batch_report_sha256"], group="remote_execution:actual_batch_report")
        check("remote_execution:retained_execution_is_audited_run", remote_run / "annotation_batch_report.json" in remote_runs)
        terminal_downloads = terminal["download_checks"]
        check("remote_execution:unique_retained_original_payloads", len(terminal_downloads) == terminal["verified_original_payloads"] == 24
              and len({row["path"] for row in terminal_downloads}) == 24)
        terminal_index = {row["path"]: row for row in read(remote_run / "annotation_retention_manifest.json")["artifacts"]}
        for item in terminal_downloads:
            expected = terminal_index.get(item["path"])
            check("remote_execution:original_download_checked_against_original_manifest", item["http_status"] == 200
                  and item["status"] == "PASS" and (item["path"] == "annotation_retention_manifest.json" or
                      expected is not None and expected["sha256"] == item["sha256"] and expected["size_bytes"] == item["size_bytes"]), item["path"])
            bound(remote_run / item["path"], item["sha256"], item["size_bytes"], group="remote_execution:exact_original_download")
        check("remote_execution:complete_CPU_submission_not_new_counting", submission["execution_status"] == "COMPLETE"
              and submission["all_eight_rendered_videos_verified"] is True and submission["gpu_requested"] is False
              and submission["internet_requested"] is False and submission["new_model_inference_requested"] is False
              and submission["original_machine_events_or_decisions_modified"] is False)
    diagnostics["retained_completed_all_eight_annotation_runs"] = len(remote_runs)
    diagnostics["original_accepted_machine_passages_unchanged"] = 58
    diagnostics["original_pending_candidates_excluded_from_pivot"] = 1825
    diagnostics["local_full_video_frame_count_from_actual_renderer_report"] = 9052

    # Delivery is an explicitly lossy H264 visual copy of the original MP4v
    # annotation, not another model/counting experiment. Read retained full
    # FFprobe timestamp sequences and external file bytes; do not decode them.
    publication_root = base / "github_publication"
    delivery_path = publication_root / "delivery_manifest.json"
    check("browser_delivery:manifest_required_for_final", delivery_path.is_file() or args.preliminary)
    delivery_assets = {}
    if delivery_path.is_file():
        delivery = read(delivery_path)
        delivery_complete = delivery.get("status") == "completed_all_eight_verified"
        check("browser_delivery:all_eight_completed_required_for_final", delivery_complete or args.preliminary)
        expected_codec = {"encoder": "libx264", "codec": "h264", "crf": 18, "preset": "fast",
                          "pixel_format": "yuv420p", "encoder_threads": 2, "decoder_threads": 1,
                          "maximum_parallel_encoders": 2, "fps_mode": "passthrough", "encoder_time_base": "demux",
                          "movflags": "+faststart", "audio": "none", "cuts_or_filters": False, "resize_or_crop": False}
        check("browser_delivery:explicit_codec_unchanged_scientific_run", delivery["schema_version"] == "phase8_github_browser_delivery_v1"
              and delivery["codec_parameters"] == expected_codec and delivery["actual_parallel_encoder_limit"] in (1, 2)
              and delivery["models_tracker_reid_counting_rerun"] is False and delivery["original_aggregates_changed"] is False
              and delivery["expected_full_frame_count"] == 72590 and delivery["unchanged_accepted"] == 58
              and delivery["unchanged_pending"] == 1825)
        for key, name in (("original_retention_manifest", "annotation_retention_manifest.json"),
                          ("original_annotation_batch_report", "annotation_batch_report.json")):
            reference = delivery[key]
            bound(repo / reference["path"], reference["sha256"], reference["size_bytes"], group="browser_delivery:original_executed_evidence")
            check("browser_delivery:original_run_path_binding", any(repo / reference["path"] == item.parent / name for item in remote_runs), key)
        for key, expected_name in (("tool_versions", "tool_versions.json"), ("delivery_helper", "verification/prepare_github_videos.py")):
            reference = delivery[key]
            actual = publication_root / reference["path"] if key == "tool_versions" else base / expected_name
            bound(actual, reference["sha256"], reference["size_bytes"], group="browser_delivery:actual_delivery_source_and_tools")
        versions = read(publication_root / delivery["tool_versions"]["path"])
        check("browser_delivery:actual_ffmpeg_libx264_present", versions["libx264_available"] is True
              and "ffmpeg version" in versions["versions"]["ffmpeg"] and "ffprobe version" in versions["versions"]["ffprobe"])
        delivery_assets = {row["video_id"]: row for row in delivery["assets"]}
        check("browser_delivery:unique_known_completed_asset_slots", len(delivery_assets) == len(delivery["assets"])
              and set(delivery_assets).issubset(VIDEO_IDS))
        if delivery_complete:
            check("browser_delivery:all_eight_frames_bytes_and_summary", set(delivery_assets) == set(VIDEO_IDS)
                  and delivery["completed_video_count"] == 8 and delivery["completed_frame_count"] == 72590
                  and delivery["all_source_sha_verified"] is True and delivery["all_output_full_frame_counts_preserved"] is True
                  and delivery["all_presentation_timestamps_preserved_exactly"] is True
                  and delivery["all_outputs_h264_yuv420p_faststart"] is True
                  and delivery["total_source_annotation_bytes"] == sum(row["source_annotation"]["size_bytes"] for row in delivery_assets.values())
                  and delivery["total_browser_delivery_bytes"] == sum(row["size_bytes"] for row in delivery_assets.values()))
        for video_id, item in delivery_assets.items():
            day, period = video_id.split("_")
            source_relative = video_id + "/annotated_review.mp4"
            source_entry = terminal_index[source_relative]
            expected_frames = original_results[video_id]["frames_processed"]
            check("browser_delivery:exact_original_MP4v_source_binding", item["source_annotation"] == {
                      "retention_path": source_relative, "sha256": source_entry["sha256"], "size_bytes": source_entry["size_bytes"]}
                  and item["frame_count"] == item["source_full_decoded_frame_count"] == item["output_full_decoded_frame_count"] == expected_frames
                  and item["accepted"] == len(ledger_by_video[video_id]) and item["pending"] == len(queue_by_video[video_id])
                  and all(item["final_pivot"][category] == values for category, values in expected_pivots[video_id].items()), video_id)
            source_path = Path(delivery["original_video_root"]) / (video_id + ".mp4")
            browser_path = Path(item["path"])
            check("browser_delivery:external_original_and_derivative_paths", source_path.is_absolute() and browser_path.is_absolute()
                  and not source_path.resolve().is_relative_to(repo) and not browser_path.resolve().is_relative_to(repo)
                  and browser_path.parent == Path(delivery["browser_video_root"])
                  and browser_path.name == item["filename"] == f"TGDI-{day.upper()}-{period.upper()}-annotated-review.mp4", video_id)
            bound(source_path, source_entry["sha256"], source_entry["size_bytes"], group="browser_delivery:actual_original_MP4_bytes")
            bound(browser_path, item["sha256"], item["size_bytes"], group="browser_delivery:actual_H264_derivative_bytes")
            check("browser_delivery:browser_codec_native_canvas_lossy_not_new_counting", item["status"] == "completed_verified"
                  and item["source_codec"] == "mpeg4" and item["output_codec"] == "h264" and item["pixel_format"] == "yuv420p"
                  and (item["width"], item["height"]) == (1160, 720) and item["size_bytes"] < 2_000_000_000
                  and item["lossless_copy"] is False and item["delivery_conversion"] == "LOSSY_H264_VISUAL_COPY_OF_ORIGINAL_MP4V_ANNOTATED_RESULT"
                  and item["original_annotation_unchanged_after_encoding"] is True
                  and item["new_detector_tracker_encoder_counting_execution"] is False, video_id)
            probes = {}
            for key, reference in item["proofs"].items():
                proof_path = publication_root / reference["path"]
                check("browser_delivery:safe_retained_proof_path", proof_path.resolve().is_relative_to(publication_root.resolve()), reference["path"])
                bound(proof_path, reference["sha256"], reference["size_bytes"], group="browser_delivery:exact_full_decode_and_codec_proof")
                if key.endswith("_probe"):
                    probe = read(proof_path)
                    ticks = probe["frame_pts_ticks"]
                    stream = probe["stream"]
                    times = [value * Fraction(stream["time_base"]) for value in ticks]
                    normalized = "\n".join(f"{value.numerator}/{value.denominator}" for value in times) + "\n"
                    check("browser_delivery:full_retained_probe_timestamps", probe["returncode"] == 0 and probe["stderr"] == ""
                          and len(ticks) == probe["full_decoded_frame_count"] == int(stream["nb_read_frames"]) == expected_frames
                          and all(isinstance(value, int) and not isinstance(value, bool) for value in ticks)
                          and all(left < right for left, right in zip(times, times[1:]))
                          and digest(normalized.encode()) == probe["frame_pts_seconds_exact_sha256"]
                          and str(times[0]) == probe["first_frame_pts_seconds_exact"]
                          and str(times[-1]) == probe["last_frame_pts_seconds_exact"]
                          and (stream["width"], stream["height"]) == (1160, 720), [video_id, key])
                    probes[key] = (probe, times)
            source_probe, source_times = probes["source_probe"]
            browser_probe, browser_times = probes["browser_probe"]
            check("browser_delivery:every_original_presentation_time_preserved", source_times == browser_times
                  and source_probe["stream"]["codec_name"] == "mpeg4" and browser_probe["stream"]["codec_name"] == "h264"
                  and browser_probe["stream"]["pix_fmt"] == "yuv420p"
                  and Fraction(source_probe["stream"]["avg_frame_rate"]) == Fraction(browser_probe["stream"]["avg_frame_rate"])
                      == Fraction(item["source_rational_fps"]) == Fraction(item["output_rational_fps"])
                  and Fraction(source_probe["stream"]["r_frame_rate"]) == Fraction(browser_probe["stream"]["r_frame_rate"])
                  and source_probe["frame_pts_seconds_exact_sha256"] == browser_probe["frame_pts_seconds_exact_sha256"]
                      == item["presentation_timestamps_exact_sha256"]
                  and item["presentation_timestamps_preserved_exactly"] is True, video_id)
            atoms = item["top_level_mp4_atoms"]
            offsets = [row["offset"] for row in atoms if row["type"] == "moov"]
            mdat = [row["offset"] for row in atoms if row["type"] == "mdat"]
            check("browser_delivery:retained_faststart_box_layout", item["faststart_moov_before_mdat"] is True
                  and len(offsets) == 1 and mdat and offsets[0] < min(mdat) and atoms[0]["offset"] == 0
                  and all(first["offset"] + first["size_bytes"] == second["offset"] for first, second in zip(atoms, atoms[1:]))
                  and atoms[-1]["offset"] + atoms[-1]["size_bytes"] == item["size_bytes"], video_id)
            command = item["command"]
            check("browser_delivery:actual_encoding_command_no_resize_cut_or_fps_rewrite", item["encoder_returncode"] == 0
                  and all(flag not in command for flag in ("-r", "-vf", "-af", "-filter_complex", "-s", "-ss", "-t", "-to", "-frames:v"))
                  and command[command.index("-i") + 1] == str(source_path)
                  and all(command[command.index(flag) + 1] == value for flag, value in
                          (("-c:v", "libx264"), ("-crf", "18"), ("-pix_fmt", "yuv420p"), ("-fps_mode", "passthrough"),
                           ("-enc_time_base", "demux"), ("-movflags", "+faststart"))), video_id)
        diagnostics["retained_completed_H264_browser_derivatives"] = len(delivery_assets)
        diagnostics["delivery_actual_video_decode_performed_by_separate_recorded_process"] = bool(delivery_assets)

    download_path = publication_root / "original_download_manifest.json"
    check("browser_delivery:actual_original_transport_required_for_final", download_path.is_file() or args.preliminary)
    if download_path.is_file():
        downloads = read(download_path)
        check("browser_delivery:actual_original_transport_completed", downloads["schema_version"] == "phase8_annotation_original_download_v1"
              and downloads["status"] == "COMPLETE" and downloads["kernel_ref"] == "chrisbiran/phase-8-tgdi-annotation-review"
              and downloads["kernel_version"] == 1 and downloads["observed_terminal_status"] == "KernelWorkerStatus.COMPLETE"
              and downloads["parent_retention_manifest_sha256"] == sha(remote_run / "annotation_retention_manifest.json")
              and downloads["parent_batch_report_sha256"] == sha(remote_run / "annotation_batch_report.json")
              and downloads["source_bundle_sha256"] == package["source_bundle_binding_sha256"]
              and downloads["signed_urls_retained"] is False and downloads["model_or_render_rerun"] is False
              and downloads["verified_video_count"] == len(downloads["videos"]) == 8
              and downloads["errors"] == [] and downloads["frames"] == 72590
              and downloads["accepted"] == 58 and downloads["pending"] == 1825)
        check("browser_delivery:actual_original_transport_unique_slots", {row["video_id"] for row in downloads["videos"]} == set(VIDEO_IDS))
        downloaded_bytes = 0
        expected_original_checksums = []
        for item in downloads["videos"]:
            video_id = item["video_id"]
            expected = terminal_index[video_id + "/annotated_review.mp4"]
            downloaded_bytes += item["size_bytes"]
            check("browser_delivery:original_download_matches_actual_Kaggle_output", item["remote_relative_path"] == video_id + "/annotated_review.mp4"
                  and item["sha256"] == item["expected_sha256"] == expected["sha256"]
                  and item["bytes_received"] == item["size_bytes"] == item["expected_size_bytes"] == expected["size_bytes"]
                  and item["status"] == "VERIFIED" and item["http_status"] == 200
                  and item["frames"] == original_results[video_id]["frames_processed"]
                  and item["accepted"] == len(ledger_by_video[video_id]) and item["pending"] == len(queue_by_video[video_id]), video_id)
            expected_original_checksums.append(item["sha256"] + "  " + Path(item["path"]).name)
            # Delivery assets additionally hash the same original bytes above.
            if video_id not in delivery_assets:
                bound(item["path"], item["sha256"], item["size_bytes"], group="browser_delivery:actual_original_MP4_bytes")
        check("browser_delivery:exact_original_transport_byte_total", downloaded_bytes == downloads["verified_bytes"] == downloads["total_expected_bytes"])
        checksum_path = publication_root / "original_SHA256SUMS.txt"
        check("browser_delivery:original_download_checksum_file", checksum_path.is_file() and
              set(checksum_path.read_text().splitlines()) == set(expected_original_checksums))

    browser_visual_path = publication_root / "bounded_visual_review.json"
    check("browser_delivery:bounded_derivative_visual_evidence_required_for_final", browser_visual_path.is_file() or args.preliminary)
    if browser_visual_path.is_file():
        browser_visual = read(browser_visual_path)
        extracted = read(publication_root / "visual_extraction_index.json")
        extraction_index = {(row["video_id"], row["frame_index"]): row for row in extracted["entries"]}
        check("browser_delivery:bounded_actual_pair_review_no_physical_accuracy_claim", browser_visual["schema_version"] ==
                  "phase8_browser_delivery_bounded_visual_review_v1" and browser_visual["reviewed_frame_pairs"] == len(browser_visual["entries"]) == 4
              and set(browser_visual["reviewed_video_ids"]) == {"weekday_pagi", "weekday_malam"}
              and browser_visual["new_model_or_counting_run"] is False and len(extraction_index) == len(extracted["entries"]) == 4
              and any("Not a whole-video physical passage audit" in value for value in browser_visual["limitations"])
              and any("Lossy H264" in value for value in browser_visual["limitations"]))
        for item in browser_visual["entries"]:
            video_id, frame = item["video_id"], item["frame_index"]
            original_extraction = extraction_index[(video_id, frame)]
            expected = delivery_assets[video_id]
            check("browser_delivery:visual_pair_exact_extraction_and_MP4_identity", all(item[key] == value for key, value in original_extraction.items())
                  and item["source_mp4_sha256"] == expected["source_annotation"]["sha256"]
                  and item["browser_mp4_sha256"] == expected["sha256"] and 0 <= frame < expected["frame_count"]
                  and item["comparison_layout"] == {"source_region": [0, 40, 1160, 720], "browser_region": [1160, 40, 1160, 720]})
            image_path = publication_root / item["pair_path"]
            bound(image_path, item["pair_sha256"], item["pair_size_bytes"], group="browser_delivery:actual_retained_source_H264_pair_image")
            check("browser_delivery:pair_PNG_native_two_canvas_layout", image_path.resolve().is_relative_to(publication_root.resolve())
                  and png_size(image_path) == (2320, 760), item["pair_path"])
            decoded = item["decoding"]
            check("browser_delivery:bounded_extraction_same_frame_original_and_derivative", len(decoded) == 2
                  and decoded[0]["path"] == str(Path(delivery["original_video_root"]) / (video_id + ".mp4"))
                  and decoded[1]["path"] == expected["path"]
                  and all(row["decoded_frame_index"] == frame and re.fullmatch(r"[0-9a-f]{64}", row["bgr_sha256"]) for row in decoded))
            observations = item["visual_observations"]
            display = read(remote_run / video_id / "passage_display_index.json")
            active = [row for row in display["events"] if row["activation_frame"] <= frame]
            active_pending = sum(row["frame"] <= frame for row in display["pending_candidates"])
            direction_counts = {direction: sum(row["category"] == "motorcycle" and row["direction"] == direction for row in active)
                                for direction in DIRECTIONS}
            check("browser_delivery:observed_counters_agree_with_original_passage_timeline", observations["accepted_display"] ==
                      f"{len(active)} / {len(display['events'])}" and observations["pending_display"] ==
                      f"{active_pending} / {len(display['pending_candidates'])}"
                  and observations["motorcycle_direction_counts"] == direction_counts)
            check("browser_delivery:actual_bounded_readability_observation_only", all(observations[key] is True for key in
                      ("panel_labels_and_numbers_legible_at_native_canvas", "category_colors_distinguishable", "frame_counter_matches_pair_index",
                       "no_observed_new_panel_cropping", "source_and_browser_counter_display_match"))
                  and "Only this retained frame pair" in observations["scope"])
        diagnostics["H264_visual_review_frame_pairs"] = 4
        diagnostics["H264_visual_review_video_count_not_all_eight"] = 2

    receipt_path = publication_root / "publication_receipt.json"
    check("github_release:actual_publication_receipt_required_for_final", receipt_path.is_file() or args.preliminary)
    if receipt_path.is_file():
        receipt = read(receipt_path)
        release = receipt["release"]
        repository = "unChris666/traffic-vehicle-counter-IDM-LOC"
        tag = "phase8-annotation-review-v1"
        source_commit = receipt["source_commit"]
        release_url = f"https://github.com/{repository}/releases/tag/{tag}"
        check("github_release:actual_published_release_exact_source_commit", receipt["claim_type"] == "ACTUAL_GITHUB_RELEASE_PUBLICATION_NOT_MODEL_EVALUATION"
              and receipt["repository"] == repository and receipt["tag_name"] == release["tag_name"] == tag
              and receipt["release_id"] == release["id"] and isinstance(release["id"], int) and release["id"] > 0
              and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None
              and receipt["target_commitish"] == release["target_commitish"] == receipt["resolved_tag_commit_sha"] == source_commit
              and receipt["html_url"] == release["html_url"] == release_url
              and receipt["draft"] is release["draft"] is False and release["prerelease"] is False
              and bool(receipt["published_at"]) and receipt["large_videos_committed_to_git"] is False
              and receipt["new_detector_tracker_reid_or_counting_execution"] is False
              and receipt["delivery_manifest_sha256"] == sha(delivery_path))
        release_assets = receipt["assets"]
        check("github_release:eight_unique_actual_video_assets", receipt["video_asset_count"] == len(release_assets) == len(delivery_assets) == 8
              and {row["video_id"] for row in release_assets} == set(VIDEO_IDS)
              and len({row["id"] for row in release_assets}) == len({row["name"] for row in release_assets}) == 8)
        for asset in release_assets:
            expected = delivery_assets[asset["video_id"]]
            actual_remote_bytes_verified = (
                asset["verification_method"] == "GITHUB_SERVER_SHA256" and asset["digest"] == "sha256:" + expected["sha256"]
                or asset["verification_method"] == "ACTUAL_GITHUB_ASSET_DOWNLOAD_SHA256" and asset["digest"] is None)
            check("github_release:server_digest_exact_H264_bytes_not_only_URL", asset["name"] == asset["filename"] == expected["filename"]
                  and asset["id"] == asset["asset_id"] and isinstance(asset["id"], int) and asset["id"] > 0
                  and asset["size"] == asset["size_bytes"] == expected["size_bytes"]
                  and asset["uploaded_file_sha256"] == expected["sha256"]
                  and asset["verified_remote_sha256"] == expected["sha256"]
                  and asset["digest"] == asset["github_digest"] and actual_remote_bytes_verified
                  and asset["state"] == "uploaded" and asset["browser_download_url"] ==
                      f"https://github.com/{repository}/releases/download/{tag}/{expected['filename']}", asset["video_id"])
        supplemental = receipt["supplemental_assets"]
        check("github_release:exact_manifest_and_checksum_supplementals", len(supplemental) == 2
              and {row["name"] for row in supplemental} == {"delivery_manifest.json", "SHA256SUMS"})
        checksum_lines = {item["sha256"] + "  " + item["filename"] for item in delivery_assets.values()}
        check("github_release:published_checksum_payload_exact", set((publication_root / "SHA256SUMS").read_text().splitlines()) == checksum_lines)
        for asset in supplemental:
            local_path = publication_root / asset["name"]
            expected_sha = sha(local_path)
            actual_remote_bytes_verified = (
                asset["verification_method"] == "GITHUB_SERVER_SHA256" and asset["digest"] == "sha256:" + expected_sha
                or asset["verification_method"] == "ACTUAL_GITHUB_ASSET_DOWNLOAD_SHA256" and asset["digest"] is None)
            check("github_release:supplemental_exact_remote_byte_binding", asset["size"] == local_path.stat().st_size
                  and asset["uploaded_file_sha256"] == asset["verified_remote_sha256"] == expected_sha and actual_remote_bytes_verified
                  and isinstance(asset["id"], int) and asset["id"] > 0 and asset["browser_download_url"] ==
                      f"https://github.com/{repository}/releases/download/{tag}/{asset['name']}", asset["name"])
        # Read-only local Git object checks bind the release target to the exact
        # delivered renderer/geometry source and its completed delivery manifest.
        committed_paths = set(package["source_files"]) | {
            str(BASE / "verification/prepare_github_videos.py"),
            str(BASE / "verification/publish_github_release.py"), str(delivery_path.relative_to(repo))}
        for name in sorted(committed_paths):
            blob = subprocess.run(["git", "show", source_commit + ":" + name], cwd=repo, capture_output=True, check=False)
            check("github_release:source_commit_contains_exact_delivered_source", blob.returncode == 0
                  and digest(blob.stdout) == sha(repo / name), name)
        diagnostics["github_release_published_browser_video_count"] = len(release_assets)
        diagnostics["github_release_source_commit"] = source_commit

    files = capture_files(repo)
    for path in files:
        artifact = repo / path
        check("retention:no_MP4_source_video_model_weights_or_100MB_file", artifact.is_file()
              and path.suffix.lower() not in {".mp4", ".avi", ".mkv", ".mov", ".pt", ".onnx", ".engine", ".pyc"}
              and artifact.stat().st_size < 100_000_000, str(path))
    for name in CONTEXT_FILES:
        document = repo / name
        for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", document.read_text(encoding="utf-8")):
            if target.startswith(("https:", "http:", "mailto:", "#", "app:")):
                continue
            clean = target.split("#", 1)[0].strip("<>")
            candidate = document.parent / clean
            if candidate.resolve() not in {repo / FINAL_MANIFEST, repo / FINAL_VALIDATION}:
                check("documentation:local_link_exists", candidate.exists(), [name, target])
    if args.capture and not failures:
        manifest = {"claim_type": "ANNOTATION_ONLY_FINAL_RETENTION_NOT_NEW_COUNTING_OR_PHYSICAL_GROUND_TRUTH",
                    "captured_utc": datetime.now(timezone.utc).isoformat(), "source_videos_included": False,
                    "rendered_MP4s_included": False, "model_weights_included": False,
                    "excluded_recursive_outputs": [str(FINAL_MANIFEST), str(FINAL_VALIDATION)],
                    "artifacts": [{"path": str(path), "sha256": sha(repo / path), "size_bytes": (repo / path).stat().st_size} for path in files]}
        manifest.update(artifact_count=len(manifest["artifacts"]), total_bytes=sum(item["size_bytes"] for item in manifest["artifacts"]))
        (repo / FINAL_MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if (repo / FINAL_MANIFEST).is_file() and not args.preliminary:
        retained = read(repo / FINAL_MANIFEST)
        check("final:exact_artifact_set", {item["path"] for item in retained["artifacts"]} == {str(path) for path in files})
        for item in retained["artifacts"]:
            bound(repo / item["path"], item["sha256"], item["size_bytes"], group="final:retained_artifact")
    elif not args.preliminary:
        check("final:manifest_captured_after_freeze", False)
    result = {"status": "PASS" if not failures else "FAIL", "claim_type": "INDEPENDENT_RETAINED_ANNOTATION_ARTIFACT_AUDIT_NOT_MODEL_OR_COUNTING_QUALITY",
              "created_utc": datetime.now(timezone.utc).isoformat(), "preliminary_only": args.preliminary,
              "checks_passed": sum(passed.values()), "checks_total": sum(totals.values()),
              "groups": {group: {"passed": passed[group], "total": totals[group]} for group in sorted(totals)},
              "failures": failures, "diagnostics": diagnostics, "checker_source_sha256": sha(__file__)}
    output = Path("/tmp/phase8_annotation_preliminary_validation.json") if args.preliminary else repo / FINAL_VALIDATION
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "checks_passed", "checks_total", "failures")}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
