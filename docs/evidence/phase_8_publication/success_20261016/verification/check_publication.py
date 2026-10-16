#!/usr/bin/env python3
"""Verify retained Phase 8 GitHub publication evidence without model/video runs.

The original annotation delivery remains immutable. This checker accepts three
explicit historical Markdown archives, verifies the new codec proofs and GitHub
asset digests, and optionally captures only the publication update's retained
files. It does not execute inference, tracking, ReID, counting, rendering,
transcoding, video decoding or any network request.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPOSITORY = "unChris666/traffic-vehicle-counter-IDM-LOC"
ORIGINAL_MANIFEST_SHA = "05e3c3a4acd3250c04e94f23ff931257cbab39fc4990a27f40ae87a01c49b118"
SOURCE_HELPER_SHA = "9e2d00a31f41ac28faa873565660bb2c198953c298ad7adca839bd18e3868d73"
VIDEO_IDS = {f"{day}_{period}" for day in ("weekday", "weekend")
             for period in ("pagi", "siang", "sore", "malam")}
CONTEXT_FILES = ("README.md", "docs/PHASE_8_REVIEW.md", "docs/ANNOTATED_VIDEO_REVIEW.md")
FROZEN_SOURCES = ("notebooks/phase_8_annotation_helpers.py", "notebooks/phase_8_annotation_tests.py",
    "notebooks/phase_8_annotation_batch.py", "notebooks/phase_8_annotation_batch_tests.py",
    "notebooks/08a_annotation_review.ipynb",
    "docs/evidence/phase_8_annotations/verification/prepare_github_videos.py",
    "docs/evidence/phase_8_annotations/verification/publish_github_release.py",
    ".github/scripts/phase8_publish_results.py", ".github/workflows/phase8-publish-results.yml")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class Audit:
    def __init__(self):
        self.rows = []

    def check(self, condition, label, detail=""):
        self.rows.append({"check": label, "passed": bool(condition), "detail": str(detail)})
        return bool(condition)

    def reference(self, root, row, label):
        path = Path(row["path"])
        safe = not path.is_absolute() and ".." not in path.parts
        self.check(safe, label + ":safe_path", path)
        if not safe:
            return None
        path = root / path
        if not self.check(path.is_file(), label + ":exists", path):
            return None
        data = path.read_bytes()
        self.check(digest(data) == row["sha256"] and len(data) == row["size_bytes"],
                   label + ":SHA_and_size", path)
        return data


def ref(path, root):
    data = path.read_bytes()
    return {"path": str(path.relative_to(root)), "sha256": digest(data), "size_bytes": len(data)}


def verify(root, success):
    audit = Audit()
    prior_path = root / "docs/evidence/phase_8_annotations/final_retention_manifest.json"
    prior_bytes = prior_path.read_bytes()
    audit.check(digest(prior_bytes) == ORIGINAL_MANIFEST_SHA, "prior:manifest_exact_original")
    prior = json.loads(prior_bytes)
    mapping = read_json(root / "docs/evidence/phase_8_publication/baseline/context_retention_mapping.json")
    audit.check(mapping["prior_manifest_sha256"] == ORIGINAL_MANIFEST_SHA,
                "prior:explicit_context_mapping_binds_original_manifest")
    archives = {entry["original_path"]: entry for entry in mapping["archives"]}
    audit.check(set(archives) == set(CONTEXT_FILES), "prior:only_three_explicit_context_archives")
    archive_bytes = {}
    for name, entry in archives.items():
        archived = audit.reference(root, {"path": entry["archive_path"],
            "sha256": entry["archive_sha256"], "size_bytes": entry["archive_size_bytes"]}, "prior:archive")
        if archived is not None:
            original = gzip.decompress(archived)
            audit.check(digest(original) == entry["original_sha256"] and
                        len(original) == entry["original_size_bytes"], "prior:decompressed_context_exact", name)
            archive_bytes[name] = original
    historical_commit = "42c4ced5ae8ad7e495239b0f5abd66cd0586b30e"
    historical_publication_paths = ("credential_verification.json", "verification.json",
        "baseline/context_retention_mapping.json", "baseline/context/README.md.gz",
        "baseline/context/docs__PHASE_8_REVIEW.md.gz", "baseline/context/docs__ANNOTATED_VIDEO_REVIEW.md.gz")
    for suffix in historical_publication_paths:
        name = "docs/evidence/phase_8_publication/" + suffix
        previous = subprocess.run(["git", "cat-file", "blob", f"{historical_commit}:{name}"],
            cwd=root, capture_output=True, check=False)
        audit.check(previous.returncode == 0 and previous.stdout == (root / name).read_bytes(),
                    "prior:historical_403_publication_evidence_unchanged", name)
    audit.check(len(prior["artifacts"]) == 178, "prior:exact_178_artifacts")
    for entry in prior["artifacts"]:
        data = archive_bytes.get(entry["path"])
        if data is None:
            data = (root / entry["path"]).read_bytes()
        audit.check(digest(data) == entry["sha256"] and len(data) == entry["size_bytes"],
                    "prior:every_original_artifact_preserved", entry["path"])

    delivery_path = success / "delivery_manifest.json"
    delivery = read_json(delivery_path)
    audit.check(delivery["schema_version"] == "phase8_github_browser_delivery_v1" and
                delivery["status"] == "completed_all_eight_verified", "delivery:actual_complete_schema")
    audit.check(delivery["models_tracker_reid_counting_rerun"] is False and
                delivery["original_aggregates_changed"] is False and
                delivery["unchanged_accepted"] == 58 and delivery["unchanged_pending"] == 1825,
                "delivery:scientific_results_unchanged_no_model_rerun")
    audit.check(delivery["completed_video_count"] == 8 and delivery["completed_frame_count"] == 72590,
                "delivery:all_eight_72590_frames")
    audit.check(all(delivery[name] is True for name in ("all_source_sha_verified",
                "all_output_full_frame_counts_preserved", "all_presentation_timestamps_preserved_exactly",
                "all_outputs_h264_yuv420p_faststart")), "delivery:completion_guards")
    helper_path = root / "docs/evidence/phase_8_annotations/verification/prepare_github_videos.py"
    audit.check(digest(helper_path.read_bytes()) == SOURCE_HELPER_SHA and
                delivery["delivery_helper"]["sha256"] == SOURCE_HELPER_SHA,
                "delivery:frozen_codec_helper_source")
    def trusted_original_reference(entry, expected_path, label):
        # The actual job retained absolute runner paths. Map only this explicit
        # canonical repository source, retaining the original manifest bytes.
        path = Path(entry["path"])
        audit.check(".." not in path.parts and (str(path) == expected_path or
                    path.is_absolute() and str(path).endswith("/" + expected_path)),
                    label + ":explicit_runner_path_binding", path)
        return audit.reference(root, {**entry, "path": expected_path}, label)
    original_root = "docs/evidence/phase_8_annotations/kaggle_execution/20261015T150218_945772Z"
    for name, filename in (("original_retention_manifest", "annotation_retention_manifest.json"),
                           ("original_annotation_batch_report", "annotation_batch_report.json")):
        trusted_original_reference(delivery[name], original_root + "/" + filename,
                                   "delivery:original_executed_source")
    tools = audit.reference(success, delivery["tool_versions"], "delivery:actual_codec_versions")
    audit.check(tools is not None and json.loads(tools)["libx264_available"] is True,
                "delivery:explicit_libx264_available")
    original_manifest = read_json(root / original_root / "annotation_retention_manifest.json")
    original_entries = {entry["path"]: entry for entry in original_manifest["artifacts"]}
    assets = delivery["assets"]
    audit.check(len(assets) == 8 and {entry["video_id"] for entry in assets} == VIDEO_IDS,
                "delivery:exact_unique_eight_slots")
    for asset in assets:
        video_id = asset["video_id"]
        day, period = video_id.split("_")
        audit.check(asset["filename"] == f"TGDI-{day.upper()}-{period.upper()}-annotated-review.mp4",
                    "delivery:explicit_asset_filename", video_id)
        original = original_entries[f"{video_id}/annotated_review.mp4"]
        audit.check(asset["source_annotation"]["sha256"] == original["sha256"] and
                    asset["source_annotation"]["size_bytes"] == original["size_bytes"],
                    "delivery:original_kaggle_MP4_identity", video_id)
        report_bytes = trusted_original_reference(asset["original_report"],
            original_root + f"/{video_id}/annotation_report.json", "delivery:actual_original_report")
        report = json.loads(report_bytes)
        audit.check(report["final_accepted"] == asset["accepted"] and
                    report["final_pending_candidates"] == asset["pending"] and
                    report["final_pivot"] == asset["final_pivot"],
                    "delivery:original_accepted_pending_and_pivot", video_id)
        audit.check(asset["status"] == "completed_verified" and asset["output_codec"] == "h264" and
                    asset["pixel_format"] == "yuv420p" and asset["width"] == 1160 and
                    asset["height"] == 720 and asset["faststart_moov_before_mdat"] is True and
                    asset["lossless_copy"] is False and
                    asset["new_detector_tracker_encoder_counting_execution"] is False,
                    "delivery:browser_derivative_not_new_scientific_result", video_id)
        audit.check(asset["frame_count"] == asset["source_full_decoded_frame_count"] ==
                    asset["output_full_decoded_frame_count"] == report["output_video"]["frames_written"] and
                    asset["presentation_timestamps_preserved_exactly"] is True,
                    "delivery:every_original_frame_and_presentation_time_preserved", video_id)
        probes = {}
        for name, entry in asset["proofs"].items():
            data = audit.reference(success, entry, "delivery:retained_full_decode_or_codec_log")
            if name.endswith("probe") and data is not None:
                probes[name] = json.loads(data)
        source = probes["source_probe"]
        browser = probes["browser_probe"]
        audit.check(source["full_decoded_frame_count"] == browser["full_decoded_frame_count"] == asset["frame_count"]
                    and source["frame_pts_seconds_exact_sha256"] == browser["frame_pts_seconds_exact_sha256"] ==
                    asset["presentation_timestamps_exact_sha256"] and
                    Fraction(source["stream"]["avg_frame_rate"]) == Fraction(browser["stream"]["avg_frame_rate"]),
                    "delivery:independent_retained_full_decode_proofs", video_id)
        for proof_name, proof in (("source", source), ("browser", browser)):
            ticks = proof["frame_pts_ticks"]
            base = Fraction(proof["stream"]["time_base"])
            times = [int(tick) * base for tick in ticks]
            canonical_times = "\n".join(f"{value.numerator}/{value.denominator}" for value in times) + "\n"
            audit.check(len(ticks) == proof["full_decoded_frame_count"] == asset["frame_count"] and
                        all(isinstance(tick, int) for tick in ticks) and
                        all(first < second for first, second in zip(ticks, ticks[1:])) and
                        digest(canonical_times.encode()) == proof["frame_pts_seconds_exact_sha256"] and
                        proof["first_frame_pts_seconds_exact"] == str(times[0]) and
                        proof["last_frame_pts_seconds_exact"] == str(times[-1]) and
                        proof["returncode"] == 0 and proof["stderr"] == "" and
                        "-count_frames" in proof["command"] and "-show_frames" in proof["command"],
                        "delivery:recomputed_every_retained_integer_PTS_and_full_decode", video_id + ":" + proof_name)
        audit.check(source["stream"]["codec_name"] == "mpeg4" and browser["stream"]["codec_name"] == "h264" and
                    browser["stream"]["pix_fmt"] == "yuv420p" and
                    source["stream"]["width"] == browser["stream"]["width"] == 1160 and
                    source["stream"]["height"] == browser["stream"]["height"] == 720,
                    "delivery:retained_native_canvas_and_browser_codec", video_id)
        atoms = asset["top_level_mp4_atoms"]
        audit.check(next(entry["offset"] for entry in atoms if entry["type"] == "moov") <
                    min(entry["offset"] for entry in atoms if entry["type"] == "mdat"),
                    "delivery:recorded_faststart_atom_order", video_id)
    audit.check(sum(entry["frame_count"] for entry in assets) == 72590 and
                sum(entry["accepted"] for entry in assets) == 58 and
                sum(entry["pending"] for entry in assets) == 1825 and
                sum(entry["size_bytes"] for entry in assets) == delivery["total_browser_delivery_bytes"],
                "delivery:all_eight_reconciled_totals")

    receipt_path = success / "publication_receipt.json"
    receipt = read_json(receipt_path)
    audit.check(receipt["claim_type"] == "ACTUAL_GITHUB_RELEASE_PUBLICATION_NOT_MODEL_EVALUATION" and
                receipt["repository"] == REPOSITORY and receipt["video_asset_count"] == 8 and
                receipt["new_detector_tracker_reid_or_counting_execution"] is False and
                receipt["large_videos_committed_to_git"] is False,
                "github:actual_successful_canonical_publication_not_model_execution")
    source_commit = receipt["source_commit"]
    audit.check(re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None, "github:full_source_commit")
    for source_name in FROZEN_SOURCES:
        completed = subprocess.run(["git", "cat-file", "blob", f"{source_commit}:{source_name}"],
            cwd=root, capture_output=True, check=False)
        audit.check(completed.returncode == 0 and completed.stdout == (root / source_name).read_bytes(),
                    "github:tagged_source_contains_exact_frozen_implementation", source_name)
    audit.check(receipt["delivery_manifest_sha256"] == digest(delivery_path.read_bytes()),
                "github:receipt_binds_actual_codec_manifest")
    release = receipt["release"]
    audit.check(release["draft"] is False and release["prerelease"] is False and
                receipt["draft"] is False and receipt["published_at"] is not None and
                release["target_commitish"] == source_commit == receipt["target_commitish"] ==
                receipt["resolved_tag_commit_sha"] and
                release["html_url"] == f"https://github.com/{REPOSITORY}/releases/tag/{release['tag_name']}" and
                release["html_url"] == receipt["html_url"] and release["id"] == receipt["release_id"],
                "github:published_release_exact_source_binding")
    published = receipt["assets"] + receipt["supplemental_assets"]
    expected = {entry["filename"]: {"sha256": entry["sha256"], "size_bytes": entry["size_bytes"]} for entry in assets}
    expected.update({path.name: ref(path, root) for path in (delivery_path, success / "SHA256SUMS")})
    audit.check(len(receipt["assets"]) == 8 and len(receipt["supplemental_assets"]) == 2 and
                {entry["name"] for entry in published} == set(expected),
                "github:exact_eight_MP4_plus_two_audit_assets")
    for entry in published:
        original = expected[entry["name"]]
        audit.check(entry["size"] == original["size_bytes"] and
                    entry["uploaded_file_sha256"] == entry["verified_remote_sha256"] == original["sha256"] and
                    entry["digest"] == "sha256:" + original["sha256"] and
                    entry["verification_method"] == "GITHUB_SERVER_SHA256" and
                    (entry["browser_download_url"] == f"https://github.com/{REPOSITORY}/releases/download/"
                     f"{release['tag_name']}/{entry['name']}" or
                     re.fullmatch(re.escape(f"https://github.com/{REPOSITORY}/releases/download/") +
                                  r"untagged-[0-9a-f]+/" + re.escape(entry["name"]), entry["browser_download_url"])),
                    "github:actual_uploaded_digest_size_and_URL", entry["name"])
    sums = (success / "SHA256SUMS").read_text().splitlines()
    expected_sums = {f"{entry['sha256']}  {entry['filename']}" for entry in assets}
    audit.check(set(sums) == expected_sums and len(sums) == 8, "github:published_eight_video_checksums_exact")
    workflow = read_json(success / "workflow_execution.json")
    audit.check(workflow["claim_type"] == "ACTUAL_ACTIONS_DELIVERY_ONLY_EXECUTION" and
                workflow["repository"] == REPOSITORY and workflow["source_commit"] == source_commit and
                workflow["published_video_count"] == 8 and workflow["signed_urls_or_user_tokens_retained"] is False and
                workflow["token_source"] == "NATIVE_JOB_SCOPED_GITHUB_TOKEN" and
                workflow["new_detector_tracker_reid_counting_execution"] is False,
                "actions:actual_native_token_delivery_without_user_credentials_or_model_run")
    run = read_json(success / "workflow_run.json")
    jobs = read_json(success / "workflow_jobs.json")
    dispatch = read_json(success / "dispatch_record.json")
    audit.check(str(run["id"]) == str(workflow["run_id"]) and run["head_sha"] == source_commit and
                run["status"] == "completed" and run["conclusion"] == "success" and
                run["event"] == "repository_dispatch" and run["run_attempt"] == 1 and
                run["html_url"] == f"https://github.com/{REPOSITORY}/actions/runs/{run['id']}",
                "actions:actual_completed_success_bound_to_published_source")
    audit.check(jobs["total_count"] == 1 and len(jobs["jobs"]) == 1 and
                all(job["run_id"] == run["id"] and job["head_sha"] == source_commit and
                    job["status"] == "completed" and job["conclusion"] == "success" and
                    all(step["status"] == "completed" and step["conclusion"] == "success"
                        for step in job["steps"]) for job in jobs["jobs"]),
                "actions:actual_successful_job_and_all_delivery_steps")
    audit.check(dispatch["repository"] == REPOSITORY and dispatch["source_commit"] == source_commit and
                dispatch["event_type"] == "phase8-publish-results-v1" and dispatch["dispatch_accepted"] is True and
                dispatch["video_count"] == 8 and dispatch["signed_urls_logged_or_retained_in_evidence"] is False,
                "actions:actual_authorized_dispatch_without_retained_capability_URLs")
    static = read_json(success / "static_publication_guards.json")
    audit.check(static["status"] == "PASS_STATIC_PUBLICATION_GUARDS" and static["unsafe_url_cases_rejected"] == 6 and
                static["bound_original_videos"] == 8 and static["bound_frames"] == 72590 and
                static["download_or_codec_or_model_execution"] is False and
                static["uploader_sha256"] == digest((root / ".github/scripts/phase8_publish_results.py").read_bytes()),
                "actions:actual_static_security_guards_bound_to_published_wrapper")
    upload_probe = read_json(success / "credential_verification.json")
    audit.check(upload_probe["claim_type"] == "ACTUAL_ACTIONS_GITHUB_TOKEN_CHECKSUM_UPLOAD_PROBE" and
                upload_probe["status"] == "UPLOAD_AUTHORIZATION_VERIFIED" and
                upload_probe["temporary_owned_draft_cleanup_verified"] is True and
                upload_probe["source_commit"] == source_commit and upload_probe["secret_value_retained"] is False and
                upload_probe["bulk_download_started"] is False,
                "actions:actual_small_upload_probe_and_owned_cleanup_before_bulk_download")
    transport = read_json(success / "original_download_manifest.json")
    audit.check(transport["status"] == "completed_all_eight_original_SHA_and_size_verified" and
                transport["source_commit"] == source_commit and
                transport["signed_download_urls_retained"] is False and
                transport["new_detector_tracker_reid_counting_execution"] is False and
                len(transport["assets"]) == 8 and
                {item["video_id"] for item in transport["assets"]} == VIDEO_IDS,
                "actions:actual_eight_verified_original_transports_without_capability_retention")
    transport_entries = {item["video_id"]: item for item in transport["assets"]}
    for asset in assets:
        item = transport_entries[asset["video_id"]]
        audit.check(item["sha256"] == asset["source_annotation"]["sha256"] and
                    item["size_bytes"] == asset["source_annotation"]["size_bytes"] and
                    item["verified_original_manifest_identity"] is True and item["http_status"] == 200 and
                    item["download_url_or_secret_retained"] is False,
                    "actions:transport_matches_exact_original_not_new_render", asset["video_id"])
    server = read_json(success / "release_api_snapshot.json")
    audit.check(server["id"] == release["id"] and server["draft"] is False and
                server["tag_name"] == release["tag_name"] and server["target_commitish"] == source_commit and
                len(server["assets"]) == 11,
                "github:actual_final_eleven_asset_release_snapshot")
    server_assets = {item["name"]: item for item in server["assets"]}
    audit.check(set(server_assets) == set(expected) | {"phase8-publication-audit.tar.gz"},
                "github:only_eight_MP4_two_manifests_and_one_audit_archive")
    for item in published:
        remote = server_assets[item["name"]]
        audit.check(remote["state"] == "uploaded" and remote["id"] == item["id"] and
                    remote["size"] == item["size"] and remote["digest"] == item["digest"] and
                    remote["browser_download_url"] == f"https://github.com/{REPOSITORY}/releases/download/"
                    f"{release['tag_name']}/{item['name']}",
                    "github:canonical_receipt_agrees_with_final_server_asset", item["name"])
    archive_proof = read_json(success / "audit_archive_verification.json")
    archive = server_assets["phase8-publication-audit.tar.gz"]
    audit.check(archive_proof["id"] == archive["id"] and archive_proof["size"] == archive["size"] and
                archive_proof["sha256"] == archive_proof["downloaded_sha256"] and
                archive["digest"] == "sha256:" + archive_proof["sha256"] and
                archive_proof["browser_download_url"] == archive["browser_download_url"] and
                archive_proof["download_http_status"] == 200 and archive_proof["extracted_file_count"] == 31,
                "github:actual_audit_archive_full_download_verified_against_server_SHA")
    final_receipt = read_json(success / "final_publication_receipt.json")
    audit.check(final_receipt["original_runtime_receipt_sha256"] == digest(receipt_path.read_bytes()) and
                final_receipt["release_api_snapshot_sha256"] == digest((success / "release_api_snapshot.json").read_bytes()),
                "github:stable_final_receipt_binds_exact_runtime_receipt_and_server_snapshot")
    audit.check(all(final_receipt[key] == receipt[key] for key in ("repository", "source_commit", "release_id",
                "tag_name", "html_url", "target_commitish", "resolved_tag_commit_sha", "release", "draft",
                "published_at", "delivery_manifest_sha256", "video_asset_count", "large_videos_committed_to_git",
                "new_detector_tracker_reid_or_counting_execution")),
                "github:stable_final_receipt_preserves_actual_publication_semantics")
    final_assets = final_receipt["assets"] + final_receipt["supplemental_assets"]
    final_asset_map = {item["name"]: item for item in final_assets}
    audit.check(len(final_receipt["assets"]) == 8 and len(final_receipt["supplemental_assets"]) == 2 and
                len(final_asset_map) == 10 and set(final_asset_map) == set(expected),
                "github:stable_final_receipt_exact_eight_video_and_two_auxiliary_assets")
    for old in published:
        item = final_asset_map[old["name"]]
        remote = server_assets[old["name"]]
        audit.check(all(item[key] == value for key, value in old.items() if key != "browser_download_url") and
                    item["browser_download_url"] == remote["browser_download_url"] and
                    item["id"] == remote["id"] and item["size"] == remote["size"] and
                    item["digest"] == remote["digest"],
                    "github:stable_final_receipt_changes_only_provisional_URLs_to_verified_tagged_URLs", old["name"])
    final_archive = final_receipt["audit_archive_asset"]
    audit.check(all(final_archive[key] == archive[key] for key in ("id", "name", "size", "digest", "browser_download_url")),
                "github:stable_final_receipt_binds_eleventh_audit_archive_asset")
    public = read_json(success / "public_access_verification.json")
    checks = public["assets"]
    published_ids = {entry["id"]: entry for entry in server["assets"]}
    audit.check(public["release_id"] == release["id"] and public["repository"] == REPOSITORY and
                public["tag_name"] == release["tag_name"] and public["source_commit"] == source_commit and
                public["status"] == "ALL_ELEVEN_ASSET_URLS_VERIFIED" and
                public["client_authorization_header_sent"] is False and
                public["anonymous_access_proven"] is False and
                public["anonymous_control_user_endpoint_http_status"] == 200 and
                len(checks) == 11 and {entry["asset_id"] for entry in checks} == set(published_ids),
                "github:all_eleven_actual_range_access_checks_anonymity_explicitly_unproven")
    for entry in checks:
        asset = published_ids[entry["asset_id"]]
        audit.check(entry["name"] == asset["name"] and entry["url"] == asset["browser_download_url"] and
                    entry["http_status"] == 206 and entry["authenticated"] is None and
                    entry["client_authorization_header_sent"] is False and
                    entry["response_bytes"] == 64 and entry["asset_size"] == asset["size"] and
                    entry["content_range"] == f"bytes 0-63/{asset['size']}",
                    "github:actual_release_URL_range_and_file_size_authentication_unknown", entry["name"])
    for name in CONTEXT_FILES:
        text = (root / name).read_text()
        audit.check(release["html_url"] in text, "documentation:persistent_actual_release_link", name)
    audit.check(any(entry["name"].endswith(".mp4") for entry in published), "github:MP4_assets_present")
    return audit, receipt


def capture_paths(root, success):
    excluded = {success / "final_retention_manifest.json", success / "verification.json"}
    paths = {root / name for name in CONTEXT_FILES}
    paths.update(root / name for name in FROZEN_SOURCES[-2:])
    paths.update(path for path in (root / "docs/evidence/phase_8_publication").rglob("*")
                 if path.is_file() and path not in excluded and "__pycache__" not in path.parts)
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--success-dir", type=Path, default=Path("docs/evidence/phase_8_publication/success_20261016"))
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    success = args.success_dir if args.success_dir.is_absolute() else root / args.success_dir
    audit, receipt = verify(root, success)
    paths = capture_paths(root, success)
    capability_pattern = re.compile(rb"https://www\.kaggleusercontent\.com/[^\s\"']+|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}")
    for path in paths:
        audit.check(capability_pattern.search(path.read_bytes()) is None,
                    "retention:no_Kaggle_capability_URL_or_credential_value", path.relative_to(root))
        audit.check(path.suffix.lower() not in (".mp4", ".avi", ".pt", ".onnx") and path.stat().st_size < 100_000_000,
                    "retention:no_video_weights_or_100MB_git_payload", path.relative_to(root))
    failures = [row for row in audit.rows if not row["passed"]]
    status = "PASS" if not failures else "FAIL"
    if args.capture and not failures:
        manifest = {"claim_type": "GITHUB_ANNOTATED_VIDEO_PUBLICATION_RETENTION_NOT_NEW_SCIENTIFIC_RUN",
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "original_annotation_manifest_sha256": ORIGINAL_MANIFEST_SHA,
            "github_video_publication_complete": True, "release_url": receipt["release"]["html_url"],
            "excluded_recursive_outputs": [str((success / name).relative_to(root)) for name in
                                            ("final_retention_manifest.json", "verification.json")],
            "artifacts": [ref(path, root) for path in paths]}
        (success / "final_retention_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    manifest_path = success / "final_retention_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        audit.check({entry["path"] for entry in manifest["artifacts"]} ==
                    {str(path.relative_to(root)) for path in paths}, "retention:exact_new_artifact_set")
        for entry in manifest["artifacts"]:
            audit.reference(root, entry, "retention:new_captured_artifact")
    elif not args.capture:
        audit.check(False, "retention:capture_required_before_final_delivery")
    failures = [row for row in audit.rows if not row["passed"]]
    status = "PASS" if not failures else "FAIL"
    counts = Counter(row["check"] for row in audit.rows)
    report = {"status": status, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks_passed": len(audit.rows) - len(failures), "checks_total": len(audit.rows),
        "groups": dict(sorted(counts.items())), "failures": failures,
        "prior_178_artifacts_preserved_direct_or_three_archives": True if status == "PASS" else None,
        "github_video_publication_complete": status == "PASS", "published_video_count": 8,
        "release_url": receipt["release"]["html_url"], "new_model_tracker_reid_counting_execution": False,
        "model_or_codec_or_video_decode_or_network_execution_by_checker": False,
        "anonymous_download_access_proven": False,
        "release_range_requests_status": "ELEVEN_ACTUAL_HTTP206_WITH_CLIENT_AUTH_HEADER_ABSENT_PROXY_AUTH_UNKNOWN",
        "canonical_receipt_draft_asset_URLs_preserved": True,
        "final_download_URLs_verified_from_published_server_snapshot": True,
        "checker_source_sha256": digest(Path(__file__).read_bytes())}
    if args.capture and status == "PASS":
        (success / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
