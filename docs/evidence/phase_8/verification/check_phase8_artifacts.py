"""Independent Phase 8 preparation/source/history retention audit.

Reads retained artifacts and source text only. It never runs a detector, tracker,
encoder, identity resolver, geometry state machine, or full-video decoder.
``--capture`` must be used only after all Phase 8 source/evidence/docs are frozen.
The final manifest and validation report live at the Phase 8 evidence root.
"""
from __future__ import annotations

import argparse
import ast
import base64
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import cv2


PHASE8 = Path("docs/evidence/phase_8")
FINAL_MANIFEST = PHASE8 / "final_retention_manifest.json"
FINAL_VALIDATION = PHASE8 / "final_artifact_validation.json"
RECURSIVE_OUTPUTS = {FINAL_MANIFEST, FINAL_VALIDATION}
CONTEXT = ("AGENTS.md", "README.md", "docs/PROJECT_CONTEXT.md", "docs/OPEN_DECISIONS.md")
MODULES = ("manifest", "pipeline", "batch", "review")
SOURCE_FILES = tuple(f"notebooks/phase_8_{name}_{kind}.py" for name in MODULES for kind in ("helpers", "tests"))
NOTEBOOK = "notebooks/08_end_to_end_batch.ipynb"
DOCS = ("docs/PHASE_8_TASK.md", "docs/PHASE_8_REVIEW.md")
SLOTS = {(day, period) for day in ("weekday", "weekend") for period in ("pagi", "siang", "sore", "malam")}
OLD_MANIFESTS = (
    ("phase6A", Path("docs/evidence/phase_6/20261012T144625_030645Z/retention_manifest.json"), 103, None),
    ("phase6B", Path("docs/evidence/phase_6/20261013T104301_354775Z/retention_manifest.json"), 172,
     Path("docs/evidence/phase_7/baseline_retention/context_retention_mapping.json")),
    ("phase7", Path("docs/evidence/phase_7/final_retention_manifest.json"), 472,
     PHASE8 / "baseline_retention/context_retention_mapping.json"),
)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def read(path):
    def reject(value):
        raise ValueError("Nonfinite JSON: " + value)
    data = Path(path).read_bytes()
    if str(path).endswith(".gz"):
        data = gzip.decompress(data)
    return json.loads(data, parse_constant=reject)


def local_path(repo, value):
    """Resolve repo-relative source identities recorded by another workspace."""
    candidate = Path(value)
    if not candidate.is_absolute():
        return repo / candidate
    for prefix in ("notebooks", "docs"):
        if prefix in candidate.parts:
            return repo / Path(*candidate.parts[candidate.parts.index(prefix):])
    return candidate


def literal_assignment(tree, name):
    matches = [node.value for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    return ast.literal_eval(matches[0]) if len(matches) == 1 else None


def final_files(repo):
    candidates = {Path(path) for path in (*CONTEXT, *SOURCE_FILES, NOTEBOOK, *DOCS)}
    candidates.update(path.relative_to(repo) for path in (repo / PHASE8).rglob("*") if path.is_file())
    return sorted(path for path in candidates if path not in RECURSIVE_OUTPUTS
                  and "__pycache__" not in path.parts and path.suffix != ".pyc")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--capture", action="store_true", help="Capture final files after explicit source/evidence/doc freeze")
    parser.add_argument("--allow-incomplete-preparation", action="store_true", help="Preliminary audit only; cannot capture a final manifest")
    args = parser.parse_args()
    if args.capture and args.allow_incomplete_preparation:
        parser.error("Final capture requires retained actual Kaggle preparation")
    repo = args.repo.resolve()
    base = repo / PHASE8
    totals, successes, failures = Counter(), Counter(), []
    diagnostics = {"model_tracker_encoder_resolver_execution": False,
                   "full_video_decode_execution": False,
                   "scope": "Phase8 code, actual eight-input preparation, source-bound geometry/user decisions and immutable historical evidence"}
    source_archives = {}

    def check(group, condition, detail=None):
        totals[group] += 1
        if bool(condition):
            successes[group] += 1
        elif sum(item["check"] == group for item in failures) < 30:
            failures.append({"check": group, "detail": detail})
        return bool(condition)

    def file_binding(path, digest, size=None, group="file_binding", allow_source_archive=False):
        path = Path(path)
        relative = str(path.relative_to(repo)) if path.is_relative_to(repo) else None
        archived = source_archives.get((relative, digest)) if allow_source_archive else None
        direct = path.is_file() and sha(path) == digest and (size is None or path.stat().st_size == size)
        logical = archived is not None and (size is None or len(archived) == size)
        exists = check(group + ":exists", path.is_file() or archived is not None, str(path))
        if logical and not direct:
            diagnostics.setdefault("historical_source_logical_archive_uses", []).append({"path": relative, "original_sha256": digest})
        return exists and check(group + ":sha_and_bytes", direct or logical, str(path))

    def exact_source_bytes(name, data):
        path = repo / name
        return (path.is_file() and path.read_bytes() == data) or source_archives.get((name, sha_bytes(data))) == data

    # Executed prepare-v1 is immutable even as newly authorized research-mode
    # source evolves. Only explicit, byte-validated source archives may satisfy
    # old source references; this fallback never applies to run/result payloads.
    for archive_manifest in sorted((base / "source_retention").glob("*manifest.json")):
        mapping = read(archive_manifest)
        items = mapping["artifacts"]
        check("source_history:unique_original_bindings", len({(item["original_path"], item["original_sha256"]) for item in items}) == len(items))
        for item in items:
            archive = repo / item["retained_path"]
            if file_binding(archive, item["retained_sha256"], group="source_history:compressed_archive"):
                logical = gzip.decompress(archive.read_bytes())
                valid = check("source_history:exact_original_logical_bytes", sha_bytes(logical) == item["original_sha256"]
                              and len(logical) == item["original_size_bytes"], item["original_path"])
                if valid:
                    source_archives[(item["original_path"], item["original_sha256"])] = logical

    # Historical manifests are immutable. Changed context documents are checked
    # against explicitly retained compressed original logical bytes, never a
    # re-written old manifest or an unbound fallback.
    for label, relative, expected_count, context_map in OLD_MANIFESTS:
        original = read(repo / relative)
        check(label + ":manifest_cardinality", original["artifact_count"] == len(original["artifacts"]) == expected_count)
        archived = {}
        if context_map is not None:
            mapping = read(repo / context_map)
            check(label + ":old_manifest_itself_unchanged", mapping["original_manifest_path"] == str(relative)
                  and mapping["original_manifest_sha256"] == sha(repo / relative))
            archived = {item["original_path"]: item for item in mapping["artifacts"]}
            check(label + ":context_mapping_unique", len(archived) == len(mapping["artifacts"]))
            for path, item in archived.items():
                artifact = repo / item["retained_path"]
                if file_binding(artifact, item["retained_sha256"], group=label + ":archive"):
                    logical = gzip.decompress(artifact.read_bytes())
                    check(label + ":archive_logical_original_bytes", sha_bytes(logical) == item["original_sha256"]
                          and len(logical) == item["original_size_bytes"] and item["logical_bytes_preserved"] is True, path)
        for item in original["artifacts"]:
            path, size = repo / item["path"], item.get("size_bytes", item.get("bytes"))
            if path.is_file() and sha(path) == item["sha256"] and path.stat().st_size == size:
                check(label + ":artifact_original_or_archived", True, item["path"])
            else:
                saved = archived.get(item["path"])
                check(label + ":artifact_original_or_archived", saved is not None and
                      saved["original_sha256"] == item["sha256"] and saved["original_size_bytes"] == size, item["path"])

    prior_delivery_mapping = base / "source_retention/delivery_a97f6d6_context_source_manifest.json"
    if prior_delivery_mapping.is_file():
        mapping = read(prior_delivery_mapping)
        original_path = repo / mapping["original_manifest_path"]
        file_binding(original_path, mapping["original_manifest_sha256"], group="prior_phase8_delivery:immutable_original_manifest")
        original = read(original_path)
        check("prior_phase8_delivery:original_267_artifacts", mapping["source_commit"] == "a97f6d638e32fdd8311ea46614244c66899f1cfc"
              and original["artifact_count"] == len(original["artifacts"]) == 267)
        for item in original["artifacts"]:
            path, expected_size = repo / item["path"], item["size_bytes"]
            direct = path.is_file() and sha(path) == item["sha256"] and path.stat().st_size == expected_size
            archived = source_archives.get((item["path"], item["sha256"]))
            check("prior_phase8_delivery:original_or_exact_archived_bytes", direct or
                  archived is not None and len(archived) == expected_size, item["path"])

    # Actual TGDI source discovery is a separate artifact from source inference.
    discovery_path = base / "inventory/TGDI_actual_discovery.json"
    discovery = read(discovery_path)
    original_manifest_path = base / "config/batch_manifest_v1.json"
    research_manifest_path = base / "config/batch_manifest_TGDI_G3_T1_v2.json"
    manifest_path = research_manifest_path if research_manifest_path.is_file() else original_manifest_path
    manifest = read(manifest_path)
    research_approved = manifest_path == research_manifest_path
    profile = read(base / "config/processing_profile_v1.json")
    check("inventory:actual_eight_decoded_inputs", discovery["status"] == "ACTUAL_8_VIDEO_SOURCE_DECODE_COMPLETED"
          and discovery["video_count"] == len(discovery["videos"]) == len(manifest["videos"]) == 8)
    file_binding(repo / discovery["listing_path"], discovery["listing_sha256"], group="inventory:listing")
    check("inventory:confirmed_dataset_not_old_13", discovery["dataset_path"] == manifest["dataset_root"]
          == "/kaggle/input/datasets/chrisbiran/tgdi-traffic-videos")
    file_binding(repo / manifest["input_authorization_path"], manifest["input_authorization_sha256"], group="inventory:user_convention")
    check("inventory:explicit_filename_mapping", manifest["filename_mapping_contract"]["claim_type"] == "USER_CONFIRMED_FILENAME_CONVENTION")
    check("inventory:location_unknown_not_inferred", manifest["location"] ==
          {"store_code": "TGDI", "store_name": None, "latitude": None, "longitude": None})
    by_source = {item["source_sha256"]: item for item in manifest["videos"]}
    check("inventory:unique_sources_and_slots", len(by_source) == 8 and
          {(item["day_type"], item["recording_period"]) for item in manifest["videos"]} == SLOTS)
    if research_approved:
        check("research:unknown_metadata_explicit_not_product_complete", manifest["execution_purpose"] == "RESEARCH_WITH_DECLARED_UNKNOWN_LOCATION"
              and manifest["business_metadata_complete"] is False and manifest["research_only"] is True)
        for key in ("location_metadata_review", "source_user_confirmation", "supersedes_input_configuration"):
            item = manifest[key]
            file_binding(repo / item["path"], item["sha256"], group="research:" + key)
        metadata_review = read(repo / manifest["location_metadata_review"]["path"])
        user_confirmation = read(repo / manifest["source_user_confirmation"]["path"])
        expected_sources = {item["slot_id"]: item["source_sha256"] for item in manifest["videos"]}
        check("research:user_unknown_location_review_bound_to_all_eight", metadata_review["schema_version"] == "phase8_location_metadata_review_v1"
              and metadata_review["authorization"] == "CONTINUE_RESEARCH_WITH_UNKNOWN_LOCATION_METADATA"
              and metadata_review["store_code"] == "TGDI"
              and set(metadata_review["unknown_fields"]) == {"store_name", "latitude", "longitude"}
              and metadata_review["source_video_sha256_by_slot"] == user_confirmation["source_video_sha256_by_slot"] == expected_sources
              and metadata_review["source_user_confirmation"] == manifest["source_user_confirmation"]
              and user_confirmation["geometry_reply"] == "Setuju untuk uji awal pada semua delapan video"
              and user_confirmation["direction_reply"] == "Ya, benar untuk semua delapan video")
    total_frames, retained_images = 0, 0
    for source in discovery["videos"]:
        name, digest = source["filename"], source["sha256"]
        slot = by_source[digest]
        expected_name = f"TGDI-{slot['day_type'].upper()}-{slot['recording_period'].upper()}.mp4"
        check("inventory:source_slot_filename_identity", name == expected_name and Path(slot["source_path"]).name == name
              and source["kaggle_path"] == slot["source_path"], name)
        check("inventory:actual_native_and_all_frames", source["width"] == source["height"] * 4 / 3 == 640
              and source["height"] == 480 and type(source["decoded_frame_count"]) is int
              and source["decoded_frame_count"] > 0 and source["decoded_frame_count"] == source["reported_frame_count"], name)
        total_frames += source["decoded_frame_count"]
        check("inventory:no_inference_or_counting_fabricated", source["model_inference_executed"] is False
              and source["counting_executed"] is False, name)
        for key in ("source_inspection", "geometry_proposal"):
            binding = source[key]
            file_binding(repo / binding["path"], binding["sha256"], group="inventory:" + key)
            check("inventory:manifest_matches_source_report", slot[key] == binding, [name, key])
        inspection = read(repo / source["source_inspection"]["path"])
        check("inventory:full_source_report_consistency", inspection["status"] == "ACTUAL_SEQUENTIAL_DECODE_COMPLETE"
              and inspection["source_video"]["sha256"] == digest and inspection["metadata"]["decoded_frame_count"] == source["decoded_frame_count"]
              and inspection["model_inference_executed"] is False and inspection["counting_executed"] is False, name)
        metadata = slot["observed_metadata"]
        check("inventory:manifest_observed_metadata", metadata["width"] == source["width"] and metadata["height"] == source["height"]
              and metadata["fps"] == source["opencv_fps"] and metadata["frame_count"] == source["decoded_frame_count"], name)
        sample_frames = set()
        for sample in inspection["retained_samples"]:
            sample_frames.add(sample["frame_index"])
            image_path = repo / sample["path"]
            file_binding(image_path, sample["sha256"], group="inventory:native_png")
            frame = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            check("inventory:native_png_shape_pixels", frame is not None and frame.shape == (480, 640, 3)
                  and sha_bytes(frame.tobytes()) == sample["bgr_uint8_pixel_sha256"], [name, sample["frame_index"]])
            retained_images += 1
        check("inventory:beginning_middle_end_retained", {0, source["decoded_frame_count"] // 2,
              source["decoded_frame_count"] - 1}.issubset(sample_frames), name)
        proposal = read(repo / source["geometry_proposal"]["path"])
        check("geometry:source_specific_unapproved_no_inferred_direction", proposal["source_video"]["sha256"] == digest
              and proposal["status"] == "PROPOSAL_NOT_HUMAN_APPROVED" and proposal["claim_type"] == "PROPOSAL"
              and all(proposal[key] is False for key in ("geometry_review_confirmed", "geometry_contract_accepted", "counting_execution_allowed"))
              and proposal["confirmed_direction_metadata"] is None and proposal["approval_feedback"] is None
              and proposal["direction_review"]["A_TO_B"] is None and proposal["direction_review"]["B_TO_A"] is None, name)
        if research_approved:
            file_binding(repo / slot["geometry_path"], slot["geometry_sha256"], group="geometry:accepted_source_geometry")
            accepted = read(repo / slot["geometry_path"])
            check("geometry:approved_initial_trial_same_proposal_coordinates", slot["geometry_review_confirmed"] is True
                  and accepted["status"] == "ACCEPTED_INITIAL_RESEARCH_G3_T1"
                  and all(accepted[key] is True for key in ("geometry_review_confirmed", "geometry_contract_accepted", "counting_execution_allowed"))
                  and accepted["source_video"] == dict(proposal["source_video"], native_width=640, native_height=480)
                  and accepted["source_frame"] == proposal["source_frame"], name)
            # source[geometry_proposal] includes its historical status, whereas
            # accepted.source_proposal deliberately contains only path and SHA.
            check("geometry:accepted_exact_original_source_and_coordinates", accepted["source_proposal"] ==
                  {key: source["geometry_proposal"][key] for key in ("path", "sha256")}
                  and accepted["normalized"] == proposal["normalized"]
                  and accepted["rendered_native_pixels"] == proposal["rendered_native_pixels"]
                  and accepted["selected_anchor"] == "bottom_center"
                  and accepted["confirmed_direction_metadata"] == {"A_TO_B": "approaching camera", "B_TO_A": "moving away from camera"}, name)
            feedback_ref = accepted["approval_feedback"]
            file_binding(repo / feedback_ref["path"], feedback_ref["sha256"], group="geometry:source_bound_user_feedback")
            feedback = read(repo / feedback_ref["path"])
            payload = {key: accepted.get(key) for key in ("draft_id", "source_video", "source_frame", "normalized",
                       "rendered_native_pixels", "selected_anchor", "confirmed_direction_metadata")}
            coordinate_digest = sha_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode())
            check("geometry:user_feedback_exact_native_coordinates_and_direction", feedback["schema_version"] == "phase8_geometry_review_v1"
                  and feedback["claim_type"] == "ACTUAL_USER_GEOMETRY_REVIEW" and feedback["approved"] is True
                  and feedback["source_video_sha256"] == digest and feedback["geometry_coordinates_sha256"] == coordinate_digest
                  and feedback["confirmed_direction_metadata"] == accepted["confirmed_direction_metadata"]
                  and feedback["source_proposal"] == accepted["source_proposal"]
                  and feedback["source_user_confirmation"] == manifest["source_user_confirmation"], name)
            for image in feedback["evidence_frames"]:
                file_binding(repo / image["path"], image["sha256"], group="geometry:feedback_native_evidence")
                check("geometry:feedback_uses_exact_actual_source_frame", image["frame_index"] == accepted["source_frame"]["frame_index"]
                      and image["path"] == accepted["source_frame"]["path"] and image["sha256"] == accepted["source_frame"]["sha256"], name)
        else:
            check("geometry:manifest_blocks_actual_execution", slot["geometry_path"] is None and slot["geometry_sha256"] is None
                  and slot["geometry_review_confirmed"] is False, name)
        native, normalized = proposal["rendered_native_pixels"], proposal["normalized"]
        pairs = [(native["line"][key], normalized["line"][key]) for key in ("P1", "P2")]
        for key in ("side_a_polygon", "side_b_polygon"):
            check("geometry:polygon_projection_cardinality", len(native[key]) == len(normalized[key]) >= 3, [name, key])
            pairs.extend(zip(native[key], normalized[key]))
        for pixel, relative in pairs:
            check("geometry:explicit_projection_only", all(math.isclose(pixel[i], relative[i] * (640, 480)[i], abs_tol=1e-10)
                  for i in range(2)) and all(math.isfinite(value) for value in pixel), name)
        for binding in (proposal["source_frame"], proposal["template_source"], proposal["preview"]):
            file_binding(repo / binding["path"], binding["sha256"], group="geometry:source_bound_preview")
    diagnostics.update(actual_source_frame_count_from_retained_full_decode_reports=total_frames,
                       native_pngs_independently_read=retained_images)
    check("inventory:declared_total_frames", total_frames == 72590 and retained_images == 56)
    preparation_validation = read(base / "input_preparation/preparation_artifact_validation.json")
    check("inventory:actual_preparation_validation_passed", preparation_validation["status"] == "PASS"
          and preparation_validation["checks_passed"] == preparation_validation["checks_total"] == 355
          and preparation_validation["inventory_sha256"] == sha(discovery_path)
          and preparation_validation["actual_full_decode_total_from_reports"] == total_frames)
    research_preflight = base / "verification/TGDI_research_v2_full_source_preflight.json"
    if research_preflight.is_file():
        preflight = read(research_preflight)
        validation = preflight["validation"]
        check("research:actual_full_source_preflight_no_model_execution", research_approved
              and preflight["canonical_manifest_sha256"] == sha(manifest_path)
              and preflight["new_model_inference_executed"] is False and preflight["traffic_result_created"] is False
              and validation["ready"] is True and validation["issues"] == []
              and len(validation["effective_videos"]) == 8)
        for effective in validation["effective_videos"]:
            configured = by_source[effective["source_sha256"]]
            accepted = read(repo / configured["geometry_path"])
            verified = effective["verified_source"]
            frame = accepted["source_frame"]
            check("research:effective_approved_source_and_unknown_business_status", effective["slot_id"] == configured["slot_id"]
                  and effective["geometry_sha256"] == configured["geometry_sha256"]
                  and effective["observed_metadata"] == configured["observed_metadata"]
                  and effective["business_metadata_complete"] is False and effective["research_only"] is True
                  and effective["research_unknown_location_authorized"] is True
                  and effective["location"] == manifest["location"]
                  and verified["decoded_frame_count"] == configured["observed_metadata"]["frame_count"]
                  and verified["review_frame_bgr_sha256_by_index"][str(frame["frame_index"])] == frame["bgr_uint8_pixel_sha256"],
                  effective["slot_id"])

    # Fixed experimental controls are compared independently with the historical
    # retained Phase7 configuration. New file locations may differ; semantics may not.
    old_config = read(repo / "docs/evidence/phase_7/config/TOR3-MALAM_temporal_v1.json")
    check("profile:full_video_raw_explicit_cuda0", profile["variant"] == {"name": "raw", "method": "raw"}
          and profile["device"] == "cuda:0" and profile["execution_policy"] == "SEQUENTIAL_ONE_FULL_VIDEO_ON_CUDA0"
          and profile["frame_scope"] == "FRAME_ZERO_TO_DECODER_END"
          and profile["counting_scope"] == "ALL_MEASURED_TRACK_EPISODES_FULL_VIDEO")
    check("profile:unchanged_detector_model_settings", profile["detector"]["settings"] == old_config["detector"]["settings"]
          and profile["detector"]["weights_sha256"] == old_config["detector"]["weights_sha256"]
          and profile["detector"]["package_version"] == old_config["detector"]["package_version"])
    check("profile:unchanged_tracker_reid_controls", profile["tracker"] == old_config["tracker"]
          and profile["encoder"]["sha256"] == old_config["encoder"]["sha256"]
          and profile["encoder"]["final_vehicle_configuration"] is False)
    check("profile:unchanged_counting_controls", all(profile["counting"][key] == old_config["counting"][key]
          for key in ("association", "neutral_band_px", "confirmation_observations")))
    for path, digest in profile["source_bindings"].items():
        file_binding(repo / path, digest, group="profile:frozen_source")

    trees = {}
    for relative in SOURCE_FILES:
        path = repo / relative
        trees[relative] = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        check("source:valid_python_ast", True, relative)
    pipeline_tree = trees["notebooks/phase_8_pipeline_helpers.py"]
    replay_function = next(node for node in pipeline_tree.body if isinstance(node, ast.FunctionDef) and node.name == "_execute_replay")
    scope_values = []
    for call in ast.walk(replay_function):
        if isinstance(call, ast.Call):
            for keyword in call.keywords:
                if keyword.arg == "scope":
                    scope_values.append(ast.literal_eval(keyword.value))
    check("source:unfiltered_full_counting_scope", scope_values == [{"track_ids": None, "association_frame_windows": None}])
    batch_source = (repo / "notebooks/phase_8_batch_helpers.py").read_text()
    check("source:aggregation_validates_selected_machine_or_review_source", "_verify_selected_source(snapshot, configuration, events, decisions, repo_root, evidence_kind)" in batch_source
          and "_reconcile_event(event, decisions, configuration, source, snapshot[\"kind\"])" in batch_source
          and "physical_key not in passages" in batch_source)
    review_tree = trees["notebooks/phase_8_review_helpers.py"]
    old_review_path = literal_assignment(review_tree, "BASE_PATH")
    old_review_sha = literal_assignment(review_tree, "BASE_SHA256")
    file_binding(repo / old_review_path, old_review_sha, group="source:frozen_review_algorithm")
    notebook = read(repo / NOTEBOOK)
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    check("notebook:unexecuted_canonical_source", notebook["nbformat"] == 4 and all(cell.get("execution_count") is None
          and not cell.get("outputs") for cell in code_cells))
    for index, cell in enumerate(code_cells):
        ast.parse("".join(cell["source"])); check("notebook:valid_code_ast", True, index)
    check("notebook:default_prepare_no_inference", any("MODE = globals().get('MODE', 'prepare')" in "".join(cell["source"]) for cell in code_cells))

    # Retained actual Kaggle preparation is not an eight-video model result.
    preparation_runs = []
    for report_path in base.rglob("report.json"):
        report = read(report_path)
        if report.get("phase") != 8 or report.get("mode") != "prepare":
            continue
        preparation_runs.append(report_path)
        run = report_path.parent
        check("preparation:actual_preparation_only", report["execution_kind"] == "ACTUAL_INPUT_DISCOVERY_AND_SOFTWARE_GUARDS_NO_MODEL_EXECUTION"
              and report["discovered_video_count"] == 8 and report["source_media_available_for_discovery"] is True
              and all(report[key] is False for key in ("counting_execution_authorized_by_prepare", "new_model_inference_executed",
                                                       "traffic_result_created", "complete_eight_video_processing")), str(report_path))
        input_manifest_sha = sha(run / "input_manifest.json")
        check("preparation:input_source_configuration_matches", report["input_manifest_sha256"] == input_manifest_sha
              and input_manifest_sha in {sha(original_manifest_path), sha(manifest_path)}
              and report["processing_profile_sha256"] == sha(base / "config/processing_profile_v1.json"))
        guards = read(run / "software_guards.json")
        check("preparation:all_four_actual_guard_suites", set(guards) == {f"phase_8_{name}_tests" for name in MODULES})
        for name, guard in guards.items():
            check("preparation:guard_passed", guard["successful"] is True and guard["tests_run"] > 0
                  and not guard.get("failures") and not guard.get("errors"), [name, guard.get("tests_run")])
            check("preparation:guard_passed_skipped_counts_explicit", type(guard.get("tests_passed")) is int
                  and type(guard.get("tests_skipped")) is int and guard["tests_skipped"] >= 0
                  and guard["tests_passed"] + guard["tests_skipped"] == guard["tests_run"], name)
        diagnostics.setdefault("preparation_software_test_counts", []).append({
            "run": str(report_path.relative_to(repo)),
            "loaded": sum(guard["tests_run"] for guard in guards.values()),
            "passed": sum(guard["tests_passed"] for guard in guards.values()),
            "skipped": sum(guard["tests_skipped"] for guard in guards.values()),
        })
        source_methods = read(run / "source_provenance.json")["source_methods"]
        for item in source_methods:
            file_binding(local_path(repo, item["path"]), item["sha256"], item.get("size_bytes"), group="preparation:executed_source_methods", allow_source_archive=True)
        run_manifest = read(run / "retention_manifest.json")
        for item in run_manifest["artifacts"]:
            artifact = run / item["path"]
            check("preparation:artifact_path_stays_in_run", artifact.resolve().is_relative_to(run.resolve()), item["path"])
            file_binding(artifact, item["sha256"], item.get("size_bytes", item.get("bytes")), group="preparation:retained_actual_output")
        observed = read(run / "discovered_videos.json")
        check("preparation:eight_sources_match_actual_input_bytes", {item["source_sha256"] for item in observed} == set(by_source))
        readiness = read(run / "readiness.json")
        check("preparation:execution_remains_blocked", readiness["ready"] is False and bool(readiness["issues"]))
    check("preparation:actual_preparation_retained", bool(preparation_runs) or args.allow_incomplete_preparation)
    diagnostics["retained_actual_preparation_run_count"] = len(preparation_runs)

    # A local canonical-notebook preparation is useful evidence, but cannot
    # substitute for the independently retained completed Kaggle execution.
    submission_path = base / "kaggle_submission/submission.json"
    submission = read(submission_path) if submission_path.is_file() else {}
    remote_fields = {"retained_preparation_run_path", "retained_preparation_report_sha256",
                     "execution_log_path", "execution_log_sha256"}
    remote_bound = submission.get("execution_status") == "COMPLETE" and remote_fields.issubset(submission)
    check("kaggle:completed_execution_binding_present", remote_bound or args.allow_incomplete_preparation)
    if remote_bound:
        remote_run = repo / submission["retained_preparation_run_path"]
        remote_report_path = remote_run / "report.json"
        file_binding(remote_report_path, submission["retained_preparation_report_sha256"], group="kaggle:actual_completed_report")
        file_binding(repo / submission["execution_log_path"], submission["execution_log_sha256"], group="kaggle:actual_completed_log")
        check("kaggle:remote_report_audited_separately_from_local", remote_report_path in preparation_runs
              and not remote_run.name.startswith("codex_") and remote_run.resolve().is_relative_to(base.resolve()))
        file_binding(base / "kaggle_submission/prepare_submitted.ipynb.gz", submission["submitted_archive_sha256"], group="kaggle:exact_submitted_archive")
        check("kaggle:actual_submitted_notebook_identity", sha_bytes(gzip.decompress((base / "kaggle_submission/prepare_submitted.ipynb.gz").read_bytes()))
              == submission["submitted_notebook_sha256"] and submission["actual_model_inference_requested"] is False
              and submission["counting_requested"] is False and submission["dataset"] == "chrisbiran/tgdi-traffic-videos")
        diagnostics["completed_kaggle_preparation_run"] = submission["retained_preparation_run_path"]

    # Every embedded submitted notebook bundle must reproduce canonical bytes;
    # read literals with AST, never execute notebook/bootstrap code in the audit.
    asset_manifest_path = base / "kaggle_geometry_assets/geometry_frames_manifest.json"
    asset_rows = {}
    if asset_manifest_path.is_file():
        assets = read(asset_manifest_path)
        creation = read(asset_manifest_path.parent / "dataset_creation_record.json")
        file_binding(repo / creation["actual_listing_path"], creation["actual_listing_sha256"], group="transport:actual_private_dataset_listing")
        file_binding(asset_manifest_path, creation["geometry_frames_manifest_sha256"], group="transport:exact_private_asset_manifest")
        check("transport:private_original_eight_pngs_only", creation["private_creation_response_observed"] is True
              and creation["source_videos_uploaded"] is False and creation["model_weights_uploaded"] is False
              and creation["png_reencoding_performed"] is False and assets["native_png_bytes_reencoded"] is False
              and assets["source_manifest_sha256"] == sha(manifest_path)
              and assets["dataset_ref"] == creation["dataset_ref"] == "chrisbiran/tgdi-phase8-geometry-evidence-v1"
              and len(assets["files"]) == 8)
        asset_rows = {item["repository_path"]: item for item in assets["files"]}
        with (repo / creation["actual_listing_path"]).open(newline="") as stream:
            listing = {row["name"]: int(row["size"]) for row in csv.DictReader(stream)}
        check("transport:actual_dataset_has_exact_nine_expanded_files", listing ==
              {**{row["relative_asset_path"]: row["size_bytes"] for row in assets["files"]},
               asset_manifest_path.name: asset_manifest_path.stat().st_size})
        for name, row in asset_rows.items():
            file_binding(repo / name, row["sha256"], row["size_bytes"], group="transport:byte_identical_native_png")
            video = by_source[row["source_video_sha256"]]
            accepted = read(repo / video["geometry_path"])
            check("transport:png_bound_to_exact_approved_source_frame", row["repository_path"] == accepted["source_frame"]["path"]
                  and row["sha256"] == accepted["source_frame"]["sha256"] and row["frame_index"] == 0
                  and row["width"] == 640 and row["height"] == 480, name)
    bundled_notebooks = 0
    submitted_archives = []
    for path in base.rglob("*.ipynb.gz"):
        submitted_archives.append((path, sha_bytes(gzip.decompress(path.read_bytes()))))
        submitted = read(path)
        contains_bundle = False
        bundled_canonical = None
        for cell in submitted.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            for node in ast.parse("".join(cell["source"])).body:
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                    continue
                call = node.value
                if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == "json" and call.func.attr == "loads" and len(call.args) == 1):
                    continue
                try:
                    bundle = json.loads(ast.literal_eval(call.args[0]))
                except (ValueError, TypeError, SyntaxError):
                    continue
                if not isinstance(bundle, dict) or not bundle or not all(isinstance(value, dict) and
                        {"sha256", "bytes"}.issubset(value) and (("gzip_base64" in value) != ("external_native_png" in value))
                        for value in bundle.values()):
                    continue
                bundled_notebooks += 1
                contains_bundle = True
                if NOTEBOOK in bundle:
                    bundled_canonical = json.loads(gzip.decompress(base64.b64decode(bundle[NOTEBOOK]["gzip_base64"], validate=True)))
                source_manifest = {name: {key: artifact[key] for key in ("sha256", "bytes")} for name, artifact in bundle.items()}
                binding = sha_bytes(json.dumps(source_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                               allow_nan=False).encode())
                declared_binding = literal_assignment(ast.parse("".join(cell["source"])), "SOURCE_BUNDLE_BINDING_SHA256")
                check("submission:bundle_binding_hash", declared_binding == binding, str(path))
                for name, artifact in bundle.items():
                    if "external_native_png" in artifact:
                        check("submission:external_transport_exact_approved_asset_row", artifact["external_native_png"] == asset_rows.get(name), name)
                        data = (repo / name).read_bytes()
                    else:
                        data = gzip.decompress(base64.b64decode(artifact["gzip_base64"], validate=True))
                    check("submission:bundle_actual_logical_bytes", sha_bytes(data) == artifact["sha256"]
                          and len(data) == artifact.get("bytes", artifact.get("size_bytes")), name)
                    check("submission:bundle_matches_canonical_or_retained_source", exact_source_bytes(name, data), name)
        if contains_bundle:
            check("submission:canonical_cells_preserved_after_bootstrap", bundled_canonical is not None
                  and submitted["cells"][2:] == bundled_canonical["cells"], str(path))
            check("submission:submitted_archive_not_claimed_executed_notebook", all(cell.get("execution_count") is None
                  and not cell.get("outputs") for cell in submitted["cells"] if cell["cell_type"] == "code"), str(path))
    for path in base.rglob("*source_bundle_manifest.json"):
        proof = read(path)
        check("submission:actual_packaging_claims", proof["claim_type"] in ("SOURCE_PACKAGING_NOT_EXECUTION", "SOURCE_PACKAGING_NOT_MODEL_EXECUTION")
              and proof["source_file_count"] == len(proof["source_files"])
              and proof["source_bundle_binding_sha256"] == sha_bytes(json.dumps(proof["source_files"], sort_keys=True,
                  separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode())
              and ((repo / NOTEBOOK).is_file() and proof["canonical_notebook_sha256"] == sha(repo / NOTEBOOK)
                   or (NOTEBOOK, proof["canonical_notebook_sha256"]) in source_archives)
              and proof["canonical_code_cells_modified"] is False
              and proof["videos_bundled"] is False and proof["model_weights_bundled"] is False
              and proof["actual_model_inference_executed"] is False, str(path))
        for name, item in proof["source_files"].items():
            file_binding(repo / name, item["sha256"], item["bytes"], group="submission:packaging_source_proof", allow_source_archive=True)
        check("submission:submitted_archive_matches_packaging_proof", any(digest == proof["submitted_notebook"]["sha256"]
              for _, digest in submitted_archives), str(path))
        if "builder" in proof:
            file_binding(local_path(repo, proof["builder"]["path"]), proof["builder"]["sha256"], group="submission:builder_proof", allow_source_archive=True)
        else:
            file_binding(base / "verification/build_phase8_research_bundle.py", proof["builder_sha256"], group="submission:builder_proof", allow_source_archive=True)
            file_binding(base / "verification/build_phase8_kaggle_bundle.py", proof["base_builder_sha256"], group="submission:base_builder_proof", allow_source_archive=True)
        file_binding(path.parent / "kernel-metadata.json", proof["kernel_metadata"]["sha256"], group="submission:exact_kernel_metadata")
        if "external_native_frame_transport" in proof:
            transport = proof["external_native_frame_transport"]
            check("transport:explicit_v3_source_binding", transport["manifest_sha256"] == sha(asset_manifest_path)
                  and transport["source_manifest_sha256"] == sha(manifest_path) and transport["external_frame_count"] == 8
                  and transport["native_png_bytes_changed"] is False and proof["embedded_source_file_count"] == 55
                  and proof["source_file_count"] == 63 and transport["dataset_ref"] == assets["dataset_ref"])
            check("transport:logical_source_plus_transport_binding", proof["source_bundle_transport_binding_sha256"] ==
                  sha_bytes(json.dumps({"logical_source_files": proof["source_files"], "transport": transport}, sort_keys=True,
                                      separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()))
    check("submission:retained_hash_bound_source_bundle", bundled_notebooks > 0 or args.allow_incomplete_preparation)
    diagnostics["hash_bound_submitted_bundles"] = bundled_notebooks

    # Scope of this delivery is development plus a verified remote job start.
    # RUNNING is scheduler evidence; zero exposed files is not zero traffic and
    # does not prove a detector frame or an encoder CUDA kernel has executed.
    accepted_submission_path = base / "kaggle_research_submission_v3/submission.json"
    if accepted_submission_path.is_file():
        accepted_submission = read(accepted_submission_path)
        rejected_submission = read(base / "kaggle_research_submission/submission.json")
        accepted_proof = read(accepted_submission_path.parent / "source_bundle_manifest.json")
        rejected_proof = read(base / "kaggle_research_submission/source_bundle_manifest.json")
        check("research_job:rejected_packet_retained_not_executed", rejected_submission["accepted_submission_confirmed"] is False
              and rejected_submission["kernel_version"] is None and rejected_submission["execution_status"] == "SUBMISSION_REJECTED_HTTP400"
              and rejected_submission["attempt_status"] == "REJECTED_SOURCE_SIZE_LIMIT" and rejected_submission["push_error"]["http_status"] == 400
              and rejected_proof["submitted_notebook"]["bytes"] >= 1_000_000)
        check("research_job:accepted_transport_only_preserves_all_logical_sources", accepted_proof["source_files"] == rejected_proof["source_files"]
              and accepted_proof["source_bundle_binding_sha256"] == rejected_proof["source_bundle_binding_sha256"]
              == accepted_submission["source_bundle_binding_sha256"]
              and accepted_submission["submitted_notebook_size_bytes"] == accepted_proof["submitted_notebook"]["bytes"] < 1_000_000)
        for submission_record in (accepted_submission, rejected_submission):
            archive = repo / submission_record["submitted_archive_path"]
            file_binding(archive, submission_record["submitted_archive_sha256"], group="research_job:exact_attempt_source_archive")
            check("research_job:exact_attempt_uncompressed_notebook", sha_bytes(gzip.decompress(archive.read_bytes())) == submission_record["submitted_notebook_sha256"])
        check("research_job:historical_v1_submission_not_completed_results", accepted_submission["accepted_submission_confirmed"] is True
              and accepted_submission["kernel_version"] == 1 and accepted_submission["execution_status"] in ("RUNNING", "ERROR")
              and accepted_submission["research_only"] is True and accepted_submission["business_metadata_complete"] is False
              and accepted_submission["all_eight_video_processing_complete"] is False
              and accepted_submission["completed_video_count"] is None and accepted_submission["accepted_event_total"] is None
              and accepted_submission["active_manifest_sha256"] == sha(manifest_path))
        metadata = read(accepted_submission_path.parent / "kernel-metadata.json")
        check("research_job:source_and_native_asset_dataset_attached_private", metadata["is_private"] is True
              and set(metadata["dataset_sources"]) == set(accepted_submission["dataset_sources"])
              == {"chrisbiran/tgdi-traffic-videos", "chrisbiran/tgdi-phase8-geometry-evidence-v1"})
        startup = read(base / "verification/research_v3_startup_summary.json")
        check("research_job:bounded_scheduler_status_not_cuda_proof", startup["observations"] == len(startup["observation_artifacts"]) == 5
              and startup["last_status"] == "KernelWorkerStatus.RUNNING" and startup["startup_failure_visible"] is False
              and startup["partial_log_available"] is False and startup["output_files_available"] is False
              and startup["complete_eight_video_processing"] is False)
        for item in startup["observation_artifacts"]:
            file_binding(repo / item["path"], item["sha256"], item["bytes"], group="research_job:actual_startup_probe")
            probe = read(repo / item["path"])
            check("research_job:probe_discloses_unknown_frame_and_cuda_progress", probe["kernel_ref"] == accepted_submission["kernel_ref"]
                  and probe["kernel_version"] == 1 and probe["status"] == "KernelWorkerStatus.RUNNING"
                  and probe["actual_detector_frame_progress"] is None and probe["actual_reid_cuda_execution"] is None
                  and probe["output_file_count_this_page"] == 0 and probe["log_available"] is False)
        diagnostics["delivery_scope"] = "FROZEN_DEVELOPMENT_AND_ACCEPTED_REMOTE_JOB_START_NOT_COMPLETED_EIGHT_VIDEO_RESULTS"
        diagnostics["actual_TGDI_frame_progress"] = "UNKNOWN_NO_RETAINED_MODEL_OUTPUTS"
        diagnostics["actual_TGDI_CUDA_inference_proof"] = "UNKNOWN_NO_RETAINED_MODEL_OUTPUTS"

    v1_failure_path = base / "kaggle_research_run_v1_failure/execution_failure.json"
    if v1_failure_path.is_file():
        failure = read(v1_failure_path)
        file_binding(repo / failure["log_path"], failure["log_sha256"], group="research_job:v1_actual_terminal_error_log")
        log_bytes = gzip.decompress((repo / failure["log_path"]).read_bytes())
        check("research_job:v1_exact_logical_error_log", sha_bytes(log_bytes) == failure["logical_log_sha256"]
              and len(log_bytes) == failure["logical_log_bytes"] and failure["execution_status"] == "ERROR"
              and failure["kernel_version"] == 1 and failure["no_completed_eight_video_results_claimed"] is True)
        log_events = json.loads(log_bytes)
        actual_log = "".join(event.get("data", "") for event in log_events)
        readiness_objects = []
        decoder = json.JSONDecoder()
        for match in re.finditer(r'\{\s*"ready"\s*:', actual_log):
            try:
                value, _ = decoder.raw_decode(actual_log[match.start():])
                if isinstance(value, dict) and isinstance(value.get("issues"), list):
                    readiness_objects.append(value)
            except json.JSONDecodeError:
                continue
        failed_source_checks = [item for value in readiness_objects for item in value["issues"]
                                if item.get("code") == "source_verification_failed"]
        check("research_job:v1_failed_at_full_input_gate_before_models", len(failed_source_checks) == 8
              and {item.get("slot_id") for item in failed_source_checks} == {video["slot_id"] for video in manifest["videos"]}
              and "if MODE == 'run_batch' and not READINESS['ready']" in actual_log
              and "RuntimeError: Batch belum boleh dijalankan" in actual_log)
        failure_review_path = v1_failure_path.parent / "failure_review.json"
        if failure_review_path.is_file():
            review = read(failure_review_path)
            file_binding(repo / review["full_readiness_path"], review["full_readiness_sha256"], group="research_job:v1_original_full_readiness")
            full_readiness = read(repo / review["full_readiness_path"])
            check("research_job:v1_readiness_matches_actual_log_and_no_count_claim", full_readiness in readiness_objects
                  and full_readiness["ready"] is False and len(full_readiness["issues"]) == 8
                  and review["new_detector_tracker_encoder_execution"] is False and review["completed_eight_video_results"] is False
                  and review["accepted_TGDI_passages_reported"] is None and review["source_video_integrity_failure_proven"] is False)
        diagnostics["research_kernel_version_1_terminal_status"] = "ERROR_INPUT_SOURCE_PATH_GATE_BEFORE_MODEL_EXECUTION"
        diagnostics["delivery_scope"] = "V1_TERMINAL_FAILURE_RETAINED_SOURCE_PATH_FIX_AND_RETRY_REQUIRE_SEPARATE_PROOF"

    mount_validation_path = base / "verification/research_v4_source_mount_bootstrap_validation.json"
    if mount_validation_path.is_file():
        mount_validation = read(mount_validation_path)
        resolution = mount_validation["source_resolution"]
        check("mount_fix:actual_local_source_transport_proof_not_gpu_execution", mount_validation["actual_model_inference_executed"] is False
              and mount_validation["full_source_decode_repeated"] is False and mount_validation["logical_source_files_verified"] == 63
              and mount_validation["canonical_code_cells_identical"] is True and mount_validation["canonical_mode"] == "run_batch"
              and mount_validation["readiness_and_run_manifest_is_effective"] is True)
        check("mount_fix:only_source_paths_may_change", resolution["schema_version"] == "phase8_source_mount_resolution_v1"
              and resolution["original_manifest_sha256"] == sha(manifest_path)
              and resolution["manifest_change_scope"] == "videos[*].source_path_ONLY"
              and resolution["scientific_fields_changed"] is False and resolution["actual_model_inference_executed"] is False
              and resolution["resolved_source_count"] == len(resolution["source_mapping"]) == 8)
        effective = json.loads(json.dumps(manifest))
        configured_by_id = {video["video_id"]: video for video in manifest["videos"]}
        mapping_by_id = {row["video_id"]: row for row in resolution["source_mapping"]}
        check("mount_fix:exact_eight_source_ids_no_reassignment", set(mapping_by_id) == set(configured_by_id) and len(mapping_by_id) == 8)
        for video in effective["videos"]:
            row, original = mapping_by_id[video["video_id"]], configured_by_id[video["video_id"]]
            check("mount_fix:source_identity_and_filename_trace_preserved", row["source_sha256"] == original["source_sha256"]
                  and row["original_source_path"] == original["source_path"] and row["filename_trace_verified"] is True
                  and Path(row["effective_source_path"]).name == Path(original["source_path"]).name
                  and Path(row["effective_source_path"]).is_relative_to(Path(resolution["input_root"])), video["video_id"])
            video["source_path"] = row["effective_source_path"]
        reconstructed_bytes = manifest_path.read_bytes() if effective == manifest else (
            json.dumps(effective, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
        check("mount_fix:effective_manifest_exact_path_only_hash", sha_bytes(reconstructed_bytes) == resolution["effective_manifest_sha256"])
        diagnostics["mount_fix_local_proof"] = "EIGHT_SOURCE_SHA_PATH_RELOCATION_ONLY_NO_REMOTE_GPU_EXECUTION_CLAIM"

    retry_preflight_path = base / "verification/research_v4_actual_full_source_preflight.json"
    if retry_preflight_path.is_file():
        retry_preflight = read(retry_preflight_path)
        full_validation, resolution = retry_preflight["validation"], retry_preflight["source_resolution"]
        check("mount_fix:actual_full_retry_preflight_no_inference", retry_preflight["actual_model_inference_executed"] is False
              and retry_preflight["total_decoded_frames"] == 72590 and full_validation["ready"] is True
              and full_validation["issues"] == [] and full_validation["business_metadata_complete"] is False
              and full_validation["research_only"] is True and resolution["scientific_fields_changed"] is False
              and resolution["manifest_change_scope"] == "videos[*].source_path_ONLY"
              and resolution["original_manifest_sha256"] == sha(manifest_path))
        resolved_by_id = {row["video_id"]: row for row in resolution["source_mapping"]}
        effective = json.loads(json.dumps(manifest))
        for video in effective["videos"]:
            row = resolved_by_id[video["video_id"]]
            check("mount_fix:retry_full_preflight_identity_mapping", row["source_sha256"] == video["source_sha256"]
                  and row["original_source_path"] == video["source_path"] and row["filename_trace_verified"] is True, video["video_id"])
            video["source_path"] = row["effective_source_path"]
        reconstructed = manifest_path.read_bytes() if effective == manifest else (
            json.dumps(effective, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
        check("mount_fix:full_preflight_effective_hash_changes_paths_only", sha_bytes(reconstructed) == resolution["effective_manifest_sha256"])
        decoded_total = 0
        for video in full_validation["effective_videos"]:
            original = by_source[video["source_sha256"]]
            geometry = read(repo / original["geometry_path"])
            frame = geometry["source_frame"]
            verified = video["verified_source"]
            decoded_total += verified["decoded_frame_count"]
            check("mount_fix:retry_all_native_frames_and_approved_geometry_verified", video["video_id"] == original["video_id"]
                  and video["source_path"] == resolved_by_id[video["video_id"]]["effective_source_path"]
                  and video["geometry_sha256"] == original["geometry_sha256"]
                  and verified["decoded_frame_count"] == original["observed_metadata"]["frame_count"]
                  and verified["review_frame_bgr_sha256_by_index"][str(frame["frame_index"])] == frame["bgr_uint8_pixel_sha256"], video["video_id"])
        check("mount_fix:retry_exact_eight_decoded_sources_total", len(full_validation["effective_videos"]) == len(resolved_by_id) == 8
              and decoded_total == 72590)

    retry_submission_path = base / "kaggle_research_submission_v4/submission.json"
    if retry_submission_path.is_file():
        retry = read(retry_submission_path)
        retry_proof = read(retry_submission_path.parent / "source_bundle_manifest.json")
        retry_archive = repo / retry["submitted_archive_path"]
        file_binding(retry_archive, retry["submitted_archive_sha256"], group="research_retry:exact_version2_submitted_archive")
        check("research_retry:version2_exact_source_and_unchanged_canonical_inputs", retry["accepted_submission_confirmed"] is True
              and retry["kernel_version"] == 2 and retry["execution_status"] == "RUNNING"
              and retry["active_manifest_sha256"] == sha(manifest_path)
              and sha_bytes(gzip.decompress(retry_archive.read_bytes())) == retry["submitted_notebook_sha256"]
              == retry_proof["submitted_notebook"]["sha256"]
              and retry["source_bundle_binding_sha256"] == retry_proof["source_bundle_binding_sha256"])
        check("research_retry:incomplete_research_not_traffic_results", retry["research_only"] is True
              and retry["business_metadata_complete"] is False and retry["all_eight_video_processing_complete"] is False
              and retry["completed_video_count"] is None and retry["accepted_event_total"] is None)
        probe = read(repo / retry["startup_status_evidence_path"])
        check("research_retry:actual_version2_startup_status_distinct_from_failed_v1", probe["kernel_ref"] == retry["kernel_ref"]
              and probe["kernel_version"] == 2 and probe["status"] == "KernelWorkerStatus.RUNNING"
              and probe["actual_detector_frame_progress"] is None and probe["actual_reid_cuda_execution"] is None)
        retry_startup = read(base / "verification/research_v4_startup_summary.json")
        check("research_retry:seven_bounded_version2_scheduler_observations", retry_startup["kernel_version"] == 2
              and retry_startup["observations"] == len(retry_startup["observation_artifacts"]) == 7
              and retry_startup["expected_source_bundle_binding_sha256"] == retry["source_bundle_binding_sha256"]
              and retry_startup["last_status"] == "KernelWorkerStatus.RUNNING" and retry_startup["error_status_observed"] is False
              and retry_startup["matching_version2_log_available"] is False and retry_startup["returned_output_files_available"] is False
              and retry_startup["complete_eight_video_processing"] is False)
        for item in retry_startup["observation_artifacts"]:
            file_binding(repo / item["path"], item["sha256"], item["bytes"], group="research_retry:actual_version2_probe")
            observed = read(repo / item["path"])
            check("research_retry:no_old_version1_outputs_or_model_progress_claim", observed["kernel_ref"] == retry["kernel_ref"]
                  and observed["kernel_version"] == 2 and observed["status"] == "KernelWorkerStatus.RUNNING"
                  and observed["actual_detector_frame_progress"] is None and observed["actual_reid_cuda_execution"] is None)
        diagnostics["research_kernel_version_2_observed_status"] = "RUNNING_SCHEDULER_STATUS_NOT_MODEL_EXECUTION_PROOF"
        diagnostics["delivery_scope"] = "FROZEN_SOURCE_PATH_FIX_AND_ACCEPTED_VERSION2_RETRY_START_NOT_COMPLETED_EIGHT_VIDEO_RESULTS"

    current_guards_path = base / "verification/current_software_validation.json"
    if current_guards_path.is_file():
        current_guards = read(current_guards_path)
        check("current_source:all_registered_software_checks_passed", current_guards["successful"] is True
              and current_guards["tests_registered"] == current_guards["tests_passed"] > 0
              and current_guards["tests_skipped"] == 0 and not current_guards["failures"] and not current_guards["errors"]
              and current_guards["new_detector_tracker_encoder_inference_executed"] is False
              and current_guards["actual_TGDI_traffic_result_created"] is False)
        for item in current_guards["method_sources"]:
            file_binding(repo / item["path"], item["sha256"], group="current_source:actual_software_test_source")
        file_binding(repo / current_guards["execution_log"]["path"], current_guards["execution_log"]["sha256"], group="current_source:actual_software_test_log")

    # Optional TOR3 CPU pilot: inspect its complete existing detector-linked cache
    # and saved resolver outputs directly. Never run the resolver in this audit.
    pilot_runs = []
    observation_fields = ("track_id", "frame_index", "original_detection_index", "raw_bbox", "class_id",
                          "class_name", "confidence", "measurement_provenance", "emitted")
    for report_path in base.rglob("counting_report.json"):
        report = read(report_path)
        if report.get("phase") != 8 or report.get("execution_kind") != "ACTUAL_RETAINED_SOURCE_COUNTING_REPLAY":
            continue
        pilot_runs.append(report_path)
        run, identity = report_path.parent, report["source_identity"]
        config = read(run / "counting_configuration.json")
        check("pilot:truthful_full_scope_replay_only", report["counting_scope"] == "ALL_MEASURED_TRACK_EPISODES_FULL_VIDEO"
              and config["scope"] == {"track_ids": None, "association_frame_windows": None}
              and report["complete_eight_video_batch"] is False and report["old_events_or_review_overlays_copied"] is False
              and config["input_identity"] == identity and report["configuration"] == profile, str(report_path))
        records_path = local_path(repo, report["records_path"])
        file_binding(records_path, identity["records_sha256"], group="pilot:actual_retained_cache")
        observations, count = {}, 0
        with gzip.open(records_path, "rt", encoding="utf-8") as records:
            for line in records:
                frame = json.loads(line)
                check("pilot:all_frames_contiguous_source_identity", frame["frame_index"] == count
                      and all(frame[key] == identity[key] for key in ("video_sha256", "parent_run_id", "variant", "width", "height")), count)
                raw = frame["raw_detections"]
                frame_ids = set()
                for observed in frame["emitted_tracks"]:
                    index = observed["original_detection_index"]
                    key = (count, observed["track_id"], index)
                    valid = type(index) is int and 0 <= index < len(raw) and key not in observations
                    check("pilot:emitted_observation_direct_raw_index", valid, key)
                    if not valid:
                        continue
                    detection = raw[index]
                    check("pilot:emitted_raw_bbox_class_provenance", observed["emitted"] is True
                          and observed["frame_index"] == count and observed["raw_bbox"] == detection["bbox_xyxy_pixels"]
                          and all(observed[field] == detection[field] for field in ("class_id", "class_name", "confidence"))
                          and observed["measurement_provenance"] == report["cache_provenance"]["measurement_provenance"]
                          and observed["track_id"] not in frame_ids, key)
                    frame_ids.add(observed["track_id"])
                    observations[key] = observed
                count += 1
        check("pilot:full_frame_count_not_five_windows", count == report["source_frame_count"] == report["cache_provenance"]["frame_count"])
        episodes = read(run / "episodes.json.gz")
        for episode in episodes:
            check("pilot:episode_identity", episode["source_identity"] == identity, episode["episode_id"])
            for observed in episode["observations"]:
                key = (observed["frame_index"], observed["track_id"], observed["original_detection_index"])
                donor = observations.get(key)
                box = observed["raw_bbox"]
                check("pilot:episode_preserves_actual_source_raw_BC", donor is not None
                      and all(observed[field] == donor[field] for field in observation_fields)
                      and observed["point"] == [(box[0] + box[2]) / 2, box[3]], key)
        decisions = read(run / "machine_passage_decisions.json.gz")
        events = read(run / "machine_count_events.json.gz")
        by_candidate = {item["candidate_id"]: item for item in decisions}
        check("pilot:unique_candidates_events", len(by_candidate) == len(decisions)
              and len({item["event_id"] for item in events}) == len(events))
        for decision in decisions:
            diagnostic = decision["diagnostic"]
            diagnostic_observations = [diagnostic.get("origin_observation")]
            diagnostic_observations.extend(diagnostic.get("confirmation_observations", []))
            crossing = diagnostic.get("crossing_evidence") or {}
            diagnostic_observations.extend(crossing.get(key) for key in ("start_observation", "end_observation"))
            for observed in filter(None, diagnostic_observations):
                metadata = observed["metadata"]
                key = (observed["frame_index"], metadata["track_id"], metadata["original_detection_index"])
                donor, box = observations.get(key), metadata["raw_bbox"]
                check("pilot:crossing_uses_vehicle_source_raw_BC", donor is not None
                      and metadata["class_name"] in {"motorcycle", "car", "truck", "bus"}
                      and all(metadata[field] == donor[field] for field in observation_fields
                              if field not in ("frame_index", "emitted"))
                      and observed["point"] == [(box[0] + box[2]) / 2, box[3]], key)
        for event in events:
            decision = by_candidate.get(event["candidate_id"])
            check("pilot:accepted_only_typed_event_reconciliation", event["type"] == "CountEvent"
                  and event["status"] == "accepted" and event["accepted_count_event"] is True
                  and decision is not None and decision["status"] == "accepted" and decision["accepted_count_event"] is True
                  and decision["event_id"] == event["event_id"] and not decision["reasons"] and not decision["hard_block_reasons"]
                  and event["source_identity"] == identity and event["geometry_evidence"] == decision["diagnostic"]
                  and event["measurement_support"] == decision["measurement_support"], event["event_id"])
        check("pilot:machine_event_set_not_review_or_rerun_sum", {event["event_id"] for event in events}
              == {item["event_id"] for item in decisions if item["accepted_count_event"] is True})
        for item in read(run / "retention_manifest.json")["artifacts"]:
            file_binding(run / item["path"], item["sha256"], item.get("bytes", item.get("size_bytes")), group="pilot:retained_outputs")
    diagnostics["actual_full_scope_CPU_pilot_count"] = len(pilot_runs)

    annotation_path = base / "pilot_annotation/annotation_report.json"
    if annotation_path.is_file():
        annotation = read(annotation_path)
        check("annotation:actual_technical_scope_no_new_model_claim", annotation["claim_type"] ==
              "ACTUAL_TOR3_RETAINED_CACHE_TECHNICAL_REGRESSION_NOT_TGDI_BATCH_RESULT"
              and annotation["new_detector_tracker_encoder_inference"] is False
              and annotation["frames_written_and_redecoded"] == annotation["independent_decoded_frame_count"] == 9590
              and annotation["output_retention"] == "EXTERNAL_TEMPORARY_MP4_NOT_COMMITTED_TO_GITHUB")
        sample = annotation["retained_native_annotated_sample"]
        file_binding(repo / sample["path"], sample["sha256"], group="annotation:native_retained_sample")
        pixels = cv2.imread(str(repo / sample["path"]), cv2.IMREAD_COLOR)
        check("annotation:actual_native_sample_pixels", pixels is not None
              and pixels.shape == (sample["height"], sample["width"], 3)
              and sha_bytes(pixels.tobytes()) == sample["decoded_pixel_sha256"])
        for path, digest in annotation["software_sources"].items():
            file_binding(repo / path, digest, group="annotation:executed_source", allow_source_archive=True)
        source_link = annotation["sample_source_binding"]
        check("annotation:measured_donor_binding_not_identity_review", source_link["source_cache_match"] is True
              and source_link["source_decoded_pixel_sha256"] == source_link["cache_detector_input_frame_pixel_sha256"]
              and annotation["visual_overlay_check"]["claim_limit"] ==
              "Annotation/source-linkage check only; physical passage correctness not established")
        for item in read(annotation_path.parent / "retention_manifest.json")["artifacts"]:
            file_binding(annotation_path.parent / item["path"], item["sha256"], item.get("bytes", item.get("size_bytes")),
                         group="annotation:retained_artifact")

    bridge_path = base / "verification/review_bridge_actual_validation.json"
    if bridge_path.is_file():
        bridge = read(bridge_path)
        file_binding(repo / bridge["helper_path"], bridge["helper_sha256"], group="review_bridge:executed_helper", allow_source_archive=True)
        file_binding(repo / bridge["tests_path"], bridge["tests_sha256"], group="review_bridge:executed_tests", allow_source_archive=True)
        check("review_bridge:technical_not_new_manual_evidence", bridge["actual_eight_video_batch_executed"] is False
              and bridge["detector_tracker_encoder_video_decoder_rerun"] is False
              and bridge["manual_confirmation_candidates"] == 0 and bridge["manual_pixel_review_performed"] is False
              and bridge["machine_payloads_preserved_verbatim"] is True)
        review_input = read(repo / bridge["review_input_path"])
        reviewed_run = repo / bridge["reviewed_output_path"]
        reviewed_report = read(reviewed_run / "report.json")
        source_run = next((path.parent for path in pilot_runs if read(path)["run_id"] == bridge["source_run_id"]), None)
        check("review_bridge:actual_machine_pilot_present", source_run is not None)
        if source_run is not None:
            check("review_bridge:empty_overlay_preserves_machine_payloads", review_input["decisions"] == []
                  and read(reviewed_run / "accepted_events.json.gz") == read(source_run / "machine_count_events.json.gz")
                  and read(reviewed_run / "resolved_decisions.json.gz") == read(source_run / "machine_passage_decisions.json.gz")
                  and reviewed_report["manual_confirmation_candidates"] == reviewed_report["manual_confirmed_physical_passages"] == 0)
        for item in read(reviewed_run / "execution_manifest.json")["artifacts"]:
            file_binding(reviewed_run / item["path"], item["sha256"], item.get("bytes", item.get("size_bytes")),
                         group="review_bridge:retained_empty_overlay")

    # No source videos, model weights or stale Python bytecode enter new evidence.
    selected_files = final_files(repo)
    forbidden = {".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm", ".pt", ".onnx", ".engine", ".pyc"}
    for relative in selected_files:
        path = repo / relative
        check("retention:no_video_weights_or_100MB_artifact", path.is_file() and relative.suffix.lower() not in forbidden
              and path.stat().st_size < 100_000_000, str(relative))
    for relative in (Path(path) for path in (*CONTEXT, *DOCS)):
        if not (repo / relative).is_file():
            check("documentation:required_file_exists", args.allow_incomplete_preparation, str(relative))
            continue
        text = (repo / relative).read_text(encoding="utf-8")
        for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", text):
            if target.startswith(("http:", "https:", "mailto:", "#", "app:")):
                continue
            clean = target.split("#", 1)[0].strip("<>")
            candidate = (repo / relative).parent / clean
            if candidate.resolve() in {repo / FINAL_MANIFEST, repo / FINAL_VALIDATION}:
                continue  # Captured below; avoids circular report existence.
            check("documentation:local_link_exists", candidate.exists(), [str(relative), target])

    if args.capture and not failures:
        captured = {"claim_type": "FINAL_PHASE8_RESEARCH_SOURCE_AND_EVIDENCE_RETENTION_NOT_MODEL_QUALITY_OR_GROUND_TRUTH",
                    "captured_utc": datetime.now(timezone.utc).isoformat(),
                    "scope": diagnostics["scope"], "source_video_included": False, "model_weights_included": False,
                    "excluded_recursive_outputs": [str(path) for path in sorted(RECURSIVE_OUTPUTS)],
                    "excluded_caches": ["__pycache__", "*.pyc"],
                    "artifacts": [{"path": str(relative), "sha256": sha(repo / relative),
                                   "size_bytes": (repo / relative).stat().st_size} for relative in selected_files]}
        captured.update(artifact_count=len(captured["artifacts"]), total_bytes=sum(item["size_bytes"] for item in captured["artifacts"]))
        (repo / FINAL_MANIFEST).write_text(json.dumps(captured, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if (repo / FINAL_MANIFEST).is_file():
        captured = read(repo / FINAL_MANIFEST)
        check("final:exact_file_set", {item["path"] for item in captured["artifacts"]} == {str(path) for path in selected_files})
        check("final:artifact_count_size", captured["artifact_count"] == len(captured["artifacts"])
              and captured["total_bytes"] == sum(item["size_bytes"] for item in captured["artifacts"]))
        for item in captured["artifacts"]:
            file_binding(repo / item["path"], item["sha256"], item["size_bytes"], group="final:retained_artifact")
    elif not args.allow_incomplete_preparation:
        check("final:retention_manifest_present", False, "Run --capture after all artifacts are frozen")
    report = {"status": "PASS" if not failures else "FAIL", "claim_type": "INDEPENDENT_SOFTWARE_SOURCE_AND_RETAINED_ARTIFACT_VALIDATION_NOT_MODEL_QUALITY",
              "created_utc": datetime.now(timezone.utc).isoformat(), "checks_passed": sum(successes.values()),
              "checks_total": sum(totals.values()), "check_groups": {key: {"passed": successes[key], "total": totals[key]} for key in sorted(totals)},
              "failures": failures, "diagnostics": diagnostics, "preliminary_only": args.allow_incomplete_preparation,
              "checker_source_sha256": sha(__file__)}
    output = repo / FINAL_VALIDATION if not args.allow_incomplete_preparation else Path("/tmp/phase8_preliminary_artifact_validation.json")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "checks_passed", "checks_total", "failures")}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
