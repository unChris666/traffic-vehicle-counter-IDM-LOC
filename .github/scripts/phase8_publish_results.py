#!/usr/bin/env python3
"""Publish existing, hash-bound Phase 8 outputs using the Actions job token.

The dispatch payload contains expiring Kaggle download capabilities, never a
Kaggle or GitHub credential. Their values are masked and are not retained in
logs, manifests or the publication audit archive. This script runs only the
frozen delivery codec and release publisher; it never imports the model,
tracker, ReID, geometry or counting implementation.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = "unChris666/traffic-vehicle-counter-IDM-LOC"
EVENT_TYPE = "phase8-publish-results-v1"
DOWNLOAD_HOST = "www.kaggleusercontent.com"
TAG = "phase8-annotation-review-v1"
EVIDENCE = Path("docs/evidence/phase_8_annotations/kaggle_execution/20261015T150218_945772Z")
HELPERS = Path("docs/evidence/phase_8_annotations/verification")
FROZEN_HASHES = {
    EVIDENCE / "annotation_retention_manifest.json": "b9a84af72706ffa594465cc71e67064a08fdc91d4e932a06775b119deddf531a",
    HELPERS / "prepare_github_videos.py": "9e2d00a31f41ac28faa873565660bb2c198953c298ad7adca839bd18e3868d73",
    HELPERS / "publish_github_release.py": "f9664b316ce0f807af0c6003707c28537b3c59cc8a3fc3d4bfcd6014501007e3",
}
VIDEO_IDS = tuple(f"{day}_{period}" for day in ("weekday", "weekend")
                  for period in ("pagi", "siang", "sore", "malam"))


class PublicationError(Exception):
    """Safe diagnostic: retain stage and numerical status, never signed URLs."""


def require(condition, message):
    if not condition:
        raise PublicationError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def command(arguments, *, json_input=None, expect_json=False, safe_output=False):
    if safe_output:
        # Only frozen local-path codec/publisher commands may replay output.
        # Probe, download and dispatch-capability commands never use this mode.
        require(json_input is None and not expect_json, "Invalid safe-output command mode")
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = []
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            lines.append(line)
        if process.wait():
            raise PublicationError(f"Command failed: {Path(arguments[0]).name}, exit={process.returncode}")
        return "".join(lines)
    result = subprocess.run(arguments,
        input=None if json_input is None else json.dumps(json_input),
        capture_output=True, text=True, check=False)
    if result.returncode:
        raise PublicationError(f"Command failed: {Path(arguments[0]).name}, exit={result.returncode}")
    return json.loads(result.stdout) if expect_json else result.stdout


def api(endpoint, *, method="GET", body=None):
    arguments = ["gh", "api", "--method", method, endpoint]
    if body is not None:
        arguments.extend(["--input", "-"])
    return command(arguments, json_input=body, expect_json=method != "DELETE")


def validate_url(value, *, mask=False):
    require(isinstance(value, str) and value and not any(ord(char) < 32 or ord(char) == 127 for char in value),
            "Invalid download URL value or control character")
    if mask:
        # Workflow commands require percent escaping even for one-line values.
        print("::add-mask::" + value.replace("%", "%25"), flush=True)
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname == DOWNLOAD_HOST and
            parsed.netloc == DOWNLOAD_HOST and parsed.username is None and parsed.password is None and
            not parsed.fragment, "Download URL must use the exact approved HTTPS host")
    return value


class RestrictedRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        validate_url(new_url, mask=True)
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def build_download_plan(payload, root):
    require(isinstance(payload, dict), "Dispatch payload must be an object")
    source_commit = payload.get("source_commit")
    require(isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit),
            "A full lowercase source commit SHA is required")
    for relative, expected in FROZEN_HASHES.items():
        require(sha256(root / relative) == expected, "Frozen publication input SHA differs")
    retention = json.loads((root / EVIDENCE / "annotation_retention_manifest.json").read_text())
    entries = {entry["path"]: entry for entry in retention["artifacts"]}
    require(len(entries) == len(retention["artifacts"]), "Duplicate authoritative retention path")
    batch_entry = entries["annotation_batch_report.json"]
    batch_path = root / EVIDENCE / "annotation_batch_report.json"
    require(batch_path.stat().st_size == batch_entry["size_bytes"] and sha256(batch_path) == batch_entry["sha256"],
            "Original completed batch identity differs")
    batch = json.loads(batch_path.read_text())
    require(batch["status"] == "completed_all_eight_render_only" and batch["all_eight_selected"] is True,
            "Original annotation batch is not complete")
    rows = payload.get("downloads")
    require(isinstance(rows, list) and len(rows) == 8 and
            all(isinstance(row, dict) for row in rows), "Exactly eight download objects are required")
    require({row.get("video_id") for row in rows} == set(VIDEO_IDS), "Dispatch video IDs differ")
    urls = {row["video_id"]: validate_url(row.get("url"), mask=True) for row in rows}
    plan = []
    for video_id in VIDEO_IDS:
        report_path = root / EVIDENCE / video_id / "annotation_report.json"
        report_entry = entries[f"{video_id}/annotation_report.json"]
        require(report_path.stat().st_size == report_entry["size_bytes"] and
                sha256(report_path) == report_entry["sha256"], "Original annotation report identity differs")
        report = json.loads(report_path.read_text())
        original = entries[f"{video_id}/annotated_review.mp4"]
        output = report["output_video"]
        require(output["sha256"] == original["sha256"] and output["size_bytes"] == original["size_bytes"] and
                output["frames_written"] == output["frames_redecoded"], "Original video retention differs")
        plan.append({"video_id": video_id, "url": urls[video_id], "sha256": original["sha256"],
            "size_bytes": original["size_bytes"], "frames": output["frames_written"]})
    require(sum(item["frames"] for item in plan) == 72590, "Unexpected original frame total")
    return source_commit, plan


def verify_remote_asset(asset, path):
    expected_sha, expected_size = sha256(path), path.stat().st_size
    require(asset["state"] == "uploaded" and asset["size"] == expected_size, "Uploaded asset size/state differs")
    if asset.get("digest") is not None:
        require(asset["digest"] == "sha256:" + expected_sha, "Uploaded asset GitHub SHA differs")
    else:
        result = subprocess.run(["gh", "api", f"repos/{REPOSITORY}/releases/assets/{asset['id']}",
            "-H", "Accept: application/octet-stream"], capture_output=True, check=False)
        require(result.returncode == 0 and len(result.stdout) == expected_size and
                hashlib.sha256(result.stdout).hexdigest() == expected_sha, "Uploaded asset download SHA differs")
    return {"id": asset["id"], "name": asset["name"], "size": asset["size"], "digest": asset.get("digest"),
        "uploaded_file_sha256": expected_sha, "browser_download_url": asset["browser_download_url"]}


def upload_probe(source_commit, work, proof):
    run_id = os.environ["GITHUB_RUN_ID"]
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    require(re.fullmatch(r"[0-9]+", run_id) and re.fullmatch(r"[0-9]+", attempt), "Invalid Actions run identity")
    tag = f"phase8-actions-upload-check-{run_id}-{attempt}"
    probe_file = work / "probe" / "SHA256SUMS"
    probe_file.parent.mkdir(parents=True)
    probe_file.write_text(hashlib.sha256(f"Phase8 upload probe {run_id}/{attempt}".encode()).hexdigest() + "  probe\n")
    # A unique tag plus a response-bound draft ID prevents deleting unrelated releases.
    existing = api(f"repos/{REPOSITORY}/releases?per_page=100")
    require(not any(release["tag_name"] == tag for release in existing), "Probe release already exists")
    created = api(f"repos/{REPOSITORY}/releases", method="POST", body={"tag_name": tag,
        "target_commitish": source_commit, "name": "Temporary Phase 8 upload authorization check",
        "body": "Temporary checksum-only authorization probe; no model execution.", "draft": True})
    release_id = created["id"]
    require(created["tag_name"] == tag and created["draft"] is True, "Unexpected probe draft identity")
    record = {"claim_type": "ACTUAL_ACTIONS_GITHUB_TOKEN_CHECKSUM_UPLOAD_PROBE", "recorded_at_utc": now(),
        "repository": REPOSITORY, "source_commit": source_commit, "temporary_tag": tag,
        "temporary_draft_release_id": release_id, "secret_value_retained": False,
        "models_tracker_reid_counting_rerun": False, "bulk_download_started": False}
    try:
        command(["gh", "release", "upload", tag, str(probe_file), "--repo", REPOSITORY])
        current = api(f"repos/{REPOSITORY}/releases/{release_id}")
        require(len(current["assets"]) == 1 and current["assets"][0]["name"] == probe_file.name,
                "Unexpected probe draft assets")
        record["verified_uploaded_checksum"] = verify_remote_asset(current["assets"][0], probe_file)
        record["status"] = "UPLOAD_AUTHORIZATION_VERIFIED"
    except Exception:
        record["status"] = "UPLOAD_AUTHORIZATION_FAILED_NO_BULK_DOWNLOAD"
        raise
    finally:
        current = api(f"repos/{REPOSITORY}/releases/{release_id}")
        owned = current["id"] == release_id and current["tag_name"] == tag and current["draft"] is True
        assets_owned = all(asset["name"] == probe_file.name and asset["size"] == probe_file.stat().st_size
                           for asset in current["assets"]) and len(current["assets"]) <= 1
        require(owned and assets_owned, "Refusing to delete a draft with unexpected identity or assets")
        api(f"repos/{REPOSITORY}/releases/{release_id}", method="DELETE")
        remaining = api(f"repos/{REPOSITORY}/releases?per_page=100")
        record["temporary_owned_draft_cleanup_verified"] = not any(item["id"] == release_id for item in remaining)
        write_json(proof / "credential_verification.json", record)
        require(record["temporary_owned_draft_cleanup_verified"], "Probe draft cleanup could not be verified")


def download_one(item, destination):
    path = destination / (item["video_id"] + ".mp4")
    temporary = path.with_suffix(".mp4.downloading")
    require(not path.exists() and not temporary.exists(), "Refusing to overwrite an original download")
    started, count, checksum = time.perf_counter(), 0, hashlib.sha256()
    opener = build_opener(RestrictedRedirects())
    request = Request(item["url"], headers={"User-Agent": "phase8-result-publication/1", "Accept-Encoding": "identity"})
    try:
        with opener.open(request, timeout=180) as response, temporary.open("xb") as output:
            require(response.status == 200, "Original video request did not return HTTP 200")
            validate_url(response.geturl(), mask=True)
            for block in iter(lambda: response.read(1024 * 1024), b""):
                count += len(block)
                require(count <= item["size_bytes"], "Original video exceeds authoritative size")
                checksum.update(block)
                output.write(block)
    except HTTPError as error:
        raise PublicationError(f"Original download HTTP status={error.code}") from None
    except URLError:
        raise PublicationError("Original download network failure") from None
    require(count == item["size_bytes"] and checksum.hexdigest() == item["sha256"],
            "Original video SHA or size differs from the completed Kaggle output")
    temporary.replace(path)
    return {"video_id": item["video_id"], "path": str(path), "sha256": checksum.hexdigest(),
        "size_bytes": count, "source_kernel": "chrisbiran/phase-8-tgdi-annotation-review",
        "source_annotation_run": "20261015T150218_945772Z", "http_status": 200,
        "verified_original_manifest_identity": True, "wall_seconds": time.perf_counter() - started,
        "download_url_or_secret_retained": False}


def main():
    root = Path.cwd().resolve()
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY,
            "This publisher only runs in the expected repository's GitHub Actions environment")
    require(bool(os.environ.get("GH_TOKEN")), "Native workflow token missing")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    require(event.get("action") == EVENT_TYPE, "Unexpected repository_dispatch event type")
    source_commit, plan = build_download_plan(event.get("client_payload"), root)
    require(command(["git", "rev-parse", "HEAD"]).strip() == source_commit, "Checked-out source commit differs")
    work = Path(os.environ["RUNNER_TEMP"]) / f"phase8-publication-{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    require(not work.exists(), "Publication working directory already exists")
    work.mkdir()
    proof, original, browser = work / "audit", work / "original", work / "browser"
    proof.mkdir(); original.mkdir(); browser.mkdir()
    print(json.dumps({"stage": "checksum_upload_authorization_probe"}), flush=True)
    upload_probe(source_commit, work, proof)
    print(json.dumps({"stage": "upload_probe_verified"}), flush=True)
    # Bulk transport starts only after the actual small upload is verified.
    transport = {"status": "downloading", "recorded_at_utc": now(), "repository": REPOSITORY,
        "source_commit": source_commit, "new_detector_tracker_reid_counting_execution": False,
        "signed_download_urls_retained": False, "assets": []}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(download_one, item, original): item["video_id"] for item in plan}
        for future in as_completed(futures):
            record = future.result()
            transport["assets"].append(record)
            write_json(proof / "original_download_manifest.json", transport)
            print(json.dumps({"stage": "original_verified", "video_id": record["video_id"]}), flush=True)
    transport["status"] = "completed_all_eight_original_SHA_and_size_verified"
    transport["total_source_annotation_bytes"] = sum(item["size_bytes"] for item in transport["assets"])
    write_json(proof / "original_download_manifest.json", transport)
    print(json.dumps({"stage": "original_downloads_complete"}), flush=True)
    print(json.dumps({"stage": "browser_encoding_started"}), flush=True)
    command([sys.executable, str(root / HELPERS / "prepare_github_videos.py"),
        "--evidence-root", str(root / EVIDENCE), "--original-root", str(original),
        "--browser-root", str(browser), "--proof-root", str(proof), "--workers", "2"], safe_output=True)
    receipt_path = proof / "publication_receipt.json"
    print(json.dumps({"stage": "release_upload_started"}), flush=True)
    command([sys.executable, str(root / HELPERS / "publish_github_release.py"),
        "--manifest", str(proof / "delivery_manifest.json"), "--video-root", str(browser),
        "--repo", REPOSITORY, "--tag", TAG, "--source-commit", source_commit,
        "--notes-file", str(root / "docs/evidence/phase_8_annotations/github_publication/release_notes.md"),
        "--receipt", str(receipt_path), "--publish"], safe_output=True)
    receipt = json.loads(receipt_path.read_text())
    write_json(proof / "workflow_execution.json", {"claim_type": "ACTUAL_ACTIONS_DELIVERY_ONLY_EXECUTION",
        "repository": REPOSITORY, "source_commit": source_commit, "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"), "recorded_at_utc": now(),
        "signed_urls_or_user_tokens_retained": False, "token_source": "NATIVE_JOB_SCOPED_GITHUB_TOKEN",
        "new_detector_tracker_reid_counting_execution": False, "published_video_count": receipt["video_asset_count"]})
    archive = work / "phase8-publication-audit.tar.gz"
    # An explicit proof directory prevents event JSON, URL capabilities, videos,
    # and credentials from entering the release's small reproducibility archive.
    with tarfile.open(archive, "w:gz") as output:
        for path in sorted(proof.rglob("*")):
            require(not path.is_symlink(), "Audit proof must not contain symlinks")
            if path.is_file():
                require(path.suffix.lower() not in (".mp4", ".pt", ".onnx"), "Unexpected media or model in audit proof")
                output.add(path, arcname=str(Path("phase8-publication-audit") / path.relative_to(proof)), recursive=False)
    command(["gh", "release", "upload", TAG, str(archive), "--repo", REPOSITORY])
    release = api(f"repos/{REPOSITORY}/releases/{receipt['release_id']}")
    matches = [asset for asset in release["assets"] if asset["name"] == archive.name]
    require(len(matches) == 1, "Publication audit asset missing or duplicated")
    archive_receipt = verify_remote_asset(matches[0], archive)
    require(len(release["assets"]) == 11 and release["draft"] is False,
            "Expected eight videos, two checksum/manifest files, and one audit archive")
    print(json.dumps({"status": "PUBLISHED_ALL_EIGHT_WITH_AUDIT", "release_url": release["html_url"],
        "source_commit": source_commit, "video_asset_count": 8, "audit_asset": archive_receipt,
        "new_detector_tracker_reid_counting_execution": False}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except PublicationError as error:
        print(json.dumps({"status": "PUBLICATION_FAILED", "safe_error": str(error)}), flush=True)
        sys.exit(1)
    except Exception as error:
        # Some stdlib network exceptions contain the entire capability URL.
        print(json.dumps({"status": "PUBLICATION_FAILED", "error_type": type(error).__name__}), flush=True)
        sys.exit(1)
