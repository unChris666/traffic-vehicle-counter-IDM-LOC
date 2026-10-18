#!/usr/bin/env python3
"""Publish eight completed B v2 MP4s unchanged using the native Actions token.

The dispatched commit contains the retained delivery manifest. The separately
bound executed commit produced the Kaggle outputs and becomes the release tag
target. No encoding, model, identity resolution, or counting occurs here.
Signed Kaggle download capabilities are masked immediately and never retained.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


REPOSITORY = "unChris666/traffic-vehicle-counter-IDM-LOC"
EVENT_TYPE = "phase8-publish-b-v2-v1"
TAG = "phase8-b-v2-tgdi-review-v1"
DOWNLOAD_HOST = "www.kaggleusercontent.com"
MANIFEST_PATH = Path("results/b_v2/delivery_manifest.json")
VIDEO_IDS = tuple(f"{day}_{period}" for day in ("weekday", "weekend")
                  for period in ("pagi", "siang", "sore", "malam"))
REQUIRED_SOURCE_FILES = frozenset((
    "notebooks/phase_8_b_v2_counting.py", "notebooks/phase_8_b_v2_annotation.py",
    "notebooks/phase_8_b_v2_batch.py", "notebooks/phase_5_geometry_helpers.py",
    "notebooks/phase_8_annotation_helpers.py", "notebooks/phase_8_annotation_batch.py"))


class PublicationError(Exception):
    """Diagnostics must contain no credential, response body, or signed URL."""


def require(condition, message):
    if not condition:
        raise PublicationError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def command(arguments, *, body=None, expect_json=False):
    result = subprocess.run(arguments, input=None if body is None else json.dumps(body),
                            text=True, capture_output=True, check=False)
    require(result.returncode == 0, f"Command failed: {Path(arguments[0]).name}, exit={result.returncode}")
    return json.loads(result.stdout) if expect_json else result.stdout


def api(endpoint, *, method="GET", body=None, allow_missing=False):
    arguments = ["gh", "api", "--method", method, endpoint]
    if body is not None:
        arguments.extend(["--input", "-"])
    if not allow_missing:
        return command(arguments, body=body, expect_json=method != "DELETE")
    require(method == "GET" and body is None, "Missing-resource allowance only supports GET")
    result = subprocess.run(arguments, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return json.loads(result.stdout)
    require(re.search(r"\bHTTP 404\b", result.stderr) is not None,
            "Could not verify absence of a GitHub resource")
    return None


def _hex(value, length, label):
    require(isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None,
            label + " requires a full lowercase hexadecimal SHA")
    return value


def _integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, label + " must be an integer")
    return value


def validate_url(value, *, mask=False):
    require(isinstance(value, str) and value and not any(ord(char) < 32 or ord(char) == 127 for char in value),
            "Invalid signed-download URL value")
    if mask:
        print("::add-mask::" + value.replace("%", "%25"), flush=True)
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.netloc == DOWNLOAD_HOST and parsed.hostname == DOWNLOAD_HOST
            and parsed.username is None and parsed.password is None and not parsed.fragment,
            "Download URL requires the exact approved HTTPS host")
    return value


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def validate_payload_manifest(payload, manifest, *, mask_urls=False):
    require(isinstance(payload, dict) and isinstance(manifest, dict), "Payload and manifest must be objects")
    delivery_commit = _hex(payload.get("source_commit"), 40, "Delivery commit")
    require(manifest.get("schema_version") == "phase8_b_v2_delivery_v1", "Unexpected delivery schema")
    require(manifest.get("repository") == REPOSITORY, "Unexpected delivery repository")
    executed_commit = _hex(manifest.get("source_commit"), 40, "Executed code commit")
    if "executed_source_commit" in manifest:
        require(manifest["executed_source_commit"] == executed_commit, "Executed source aliases differ")
    # A capability must never be copied into retained manifest fields.
    require(DOWNLOAD_HOST not in json.dumps(manifest).lower(), "Retained manifest contains a signed-download host")
    rows, assets = payload.get("downloads"), manifest.get("assets")
    require(isinstance(rows, list) and len(rows) == 8 and all(isinstance(row, dict) for row in rows),
            "Exactly eight download objects are required")
    require({row.get("video_id") for row in rows} == set(VIDEO_IDS), "Download video IDs differ")
    urls = {row["video_id"]: validate_url(row.get("url"), mask=mask_urls) for row in rows}
    require(isinstance(assets, list) and len(assets) == 8 and all(isinstance(asset, dict) for asset in assets),
            "Exactly eight retained video assets are required")
    require({asset.get("video_id") for asset in assets} == set(VIDEO_IDS), "Manifest video IDs differ")
    by_id, plan = {asset["video_id"]: asset for asset in assets}, []
    for video_id in VIDEO_IDS:
        asset = by_id[video_id]
        day, period = video_id.split("_")
        expected_name = f"TGDI-{day.upper()}-{period.upper()}-b-v2-annotated.mp4"
        require(asset.get("filename") == expected_name, "Unexpected or unsafe MP4 filename")
        _hex(asset.get("sha256"), 64, "MP4 SHA")
        size = _integer(asset.get("size_bytes"), "MP4 size", 1)
        require(size < 2 * 1024 ** 3, "MP4 exceeds the per-asset delivery bound")
        _integer(asset.get("frame_count"), "MP4 frame count", 1)
        total = _integer(asset.get("operational_total"), "Operational total")
        measured = _integer(asset.get("measured_total"), "Measured total")
        inferred = _integer(asset.get("inferred_total"), "Inferred total")
        require(measured + inferred == total, "Measured/inferred counts do not reconcile")
        source_path = asset.get("source_output_path")
        require(isinstance(source_path, str) and source_path.endswith(".mp4")
                and ".." not in PurePosixPath(source_path).parts
                and not any(ord(char) < 32 for char in source_path) and "://" not in source_path
                and "?" not in source_path and "#" not in source_path, "Invalid retained output path")
        plan.append(dict(asset, url=urls[video_id]))
    require(sum(asset["frame_count"] for asset in plan) == 72590, "Unexpected full TGDI frame total")
    files = manifest.get("executed_source_files")
    require(isinstance(files, list) and len(files) == 6 and all(isinstance(item, dict) for item in files),
            "Six executed source bindings are required")
    require({item.get("path") for item in files} == REQUIRED_SOURCE_FILES, "Executed source file set differs")
    for item in files:
        _hex(item.get("sha256"), 64, "Executed source file SHA")
    return delivery_commit, executed_commit, plan


def verify_source_binding(root, delivery_commit, executed_commit, manifest):
    require(command(["git", "-C", str(root), "rev-parse", "HEAD"]).strip() == delivery_commit,
            "Checked-out delivery commit differs")
    ancestor = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", executed_commit,
                               delivery_commit], capture_output=True, check=False)
    require(ancestor.returncode == 0, "Executed source is not retained in delivery history")
    for item in manifest["executed_source_files"]:
        require(sha256(root / item["path"]) == item["sha256"], "Checked-out executed source SHA differs")
        original = subprocess.run(["git", "-C", str(root), "show", f"{executed_commit}:{item['path']}"],
                                  capture_output=True, check=False)
        require(original.returncode == 0 and hashlib.sha256(original.stdout).hexdigest() == item["sha256"],
                "Executed-commit source SHA differs")
    remote = api(f"repos/{REPOSITORY}/commits/{executed_commit}")
    require(remote.get("sha") == executed_commit, "Executed commit unavailable in expected repository")


def require_unused_tag(tag):
    # Authenticated release listing includes drafts, while /releases/tags can
    # return 404 for a draft whose tag has not been created yet.
    page = 1
    while True:
        releases = api(f"repos/{REPOSITORY}/releases?per_page=100&page={page}")
        require(isinstance(releases, list), "Invalid release listing")
        require(not any(release.get("tag_name") == tag for release in releases),
                "A release or draft already exists; refusing to replace it")
        if len(releases) < 100:
            break
        page += 1
    require(api(f"repos/{REPOSITORY}/releases/tags/{tag}", allow_missing=True) is None,
            "Release already exists; refusing to replace it")
    require(api(f"repos/{REPOSITORY}/git/ref/tags/{tag}", allow_missing=True) is None,
            "Tag already exists; refusing to replace it")


def verify_remote_asset(asset, path):
    expected_sha, expected_size = sha256(path), path.stat().st_size
    require(asset.get("name") == path.name and asset.get("state") == "uploaded"
            and asset.get("size") == expected_size, "Uploaded asset size, name, or state differs")
    if asset.get("digest") is not None:
        require(asset["digest"] == "sha256:" + expected_sha, "GitHub asset SHA differs")
        method = "GITHUB_SERVER_SHA256"
    else:
        process = subprocess.Popen(["gh", "api", f"repos/{REPOSITORY}/releases/assets/{asset['id']}",
                                    "-H", "Accept: application/octet-stream"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        digest, count = hashlib.sha256(), 0
        assert process.stdout is not None
        for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
            digest.update(block)
            count += len(block)
        require(process.wait() == 0 and count == expected_size and digest.hexdigest() == expected_sha,
                "Downloaded GitHub asset SHA differs")
        method = "ACTUAL_GITHUB_ASSET_DOWNLOAD_SHA256"
    return {"id": asset["id"], "name": asset["name"], "size_bytes": expected_size,
            "sha256": expected_sha, "github_digest": asset.get("digest"), "state": asset["state"],
            "verification_method": method, "browser_download_url": asset["browser_download_url"]}


def upload_probe(executed_commit, work, run_id, attempt):
    tag = f"phase8-b-v2-upload-check-{run_id}-{attempt}"
    require_unused_tag(tag)
    probe_dir = work / "probe"
    probe_dir.mkdir()
    path = probe_dir / "SHA256SUMS"
    path.write_text(hashlib.sha256(f"B v2 upload probe {run_id}/{attempt}".encode()).hexdigest() + "  probe\n")
    created = api(f"repos/{REPOSITORY}/releases", method="POST", body={
        "tag_name": tag, "target_commitish": executed_commit, "name": "Temporary B v2 upload authorization probe",
        "body": "Checksum-only owned draft; no video or inference execution.", "draft": True})
    release_id = created["id"]
    require(created.get("tag_name") == tag and created.get("draft") is True, "Unexpected probe identity")
    proof = {"claim_type": "ACTUAL_NATIVE_ACTIONS_TOKEN_CHECKSUM_UPLOAD_PROBE", "recorded_at_utc": now(),
             "temporary_draft_id": release_id, "temporary_tag": tag, "bulk_download_started": False,
             "token_value_retained": False}
    try:
        command(["gh", "release", "upload", tag, str(path), "--repo", REPOSITORY])
        current = api(f"repos/{REPOSITORY}/releases/{release_id}")
        require(len(current["assets"]) == 1, "Unexpected probe assets")
        proof["verified_checksum_upload"] = verify_remote_asset(current["assets"][0], path)
        proof["status"] = "UPLOAD_AUTHORIZATION_VERIFIED"
    finally:
        current = api(f"repos/{REPOSITORY}/releases/{release_id}")
        require(current.get("id") == release_id and current.get("tag_name") == tag and current.get("draft") is True
                and len(current["assets"]) <= 1 and all(asset["name"] == path.name for asset in current["assets"]),
                "Refusing to delete a draft with unexpected probe identity")
        api(f"repos/{REPOSITORY}/releases/{release_id}", method="DELETE")
        require(api(f"repos/{REPOSITORY}/releases/{release_id}", allow_missing=True) is None,
                "Owned probe draft cleanup not verified")
        proof["temporary_owned_draft_deleted"] = True
        write_json(work / "credential_verification.json", proof)
    return proof


def download_one(item, destination):
    path = destination / item["filename"]
    partial = path.with_suffix(".mp4.downloading")
    require(not path.exists() and not partial.exists(), "Download destination already exists")
    started, count, digest = time.perf_counter(), 0, hashlib.sha256()
    request = Request(item["url"], headers={"User-Agent": "phase8-b-v2-publication/1", "Accept-Encoding": "identity"})
    try:
        with build_opener(NoRedirects()).open(request, timeout=180) as response, partial.open("xb") as output:
            require(response.status == 200 and response.geturl() == item["url"], "Download HTTP status or origin differs")
            length = response.headers.get("Content-Length")
            if length is not None:
                require(length.isdecimal() and int(length) == item["size_bytes"], "Download content length differs")
            for block in iter(lambda: response.read(1024 * 1024), b""):
                count += len(block)
                require(count <= item["size_bytes"], "MP4 exceeds retained byte size")
                digest.update(block)
                output.write(block)
    except HTTPError as error:
        raise PublicationError(f"Completed Kaggle output download HTTP status={error.code}") from None
    except URLError:
        raise PublicationError("Completed Kaggle output download network failure") from None
    require(count == item["size_bytes"] and digest.hexdigest() == item["sha256"], "Kaggle output SHA or size differs")
    partial.replace(path)
    return {"video_id": item["video_id"], "filename": path.name, "sha256": digest.hexdigest(),
            "size_bytes": count, "http_status": 200, "wall_seconds": time.perf_counter() - started,
            "download_url_or_secret_retained": False}


def publish(root, manifest_path, manifest, plan, delivery_commit, executed_commit, work, probe_proof):
    require_unused_tag(TAG)
    video_dir = work / "videos"
    video_dir.mkdir()
    downloaded = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(download_one, item, video_dir): item["video_id"] for item in plan}
        for future in as_completed(futures):
            record = future.result()
            downloaded.append(record)
            print(json.dumps({"stage": "retained_mp4_verified", "video_id": record["video_id"]}), flush=True)
    delivered_manifest = work / "delivery_manifest.json"
    shutil.copyfile(manifest_path, delivered_manifest)
    checksums = work / "SHA256SUMS"
    checksums.write_text("".join(f"{item['sha256']}  {item['filename']}\n" for item in plan)
                         + f"{sha256(delivered_manifest)}  delivery_manifest.json\n", encoding="utf-8")
    notes = ("Eight completed TGDI B v2 annotated MP4 outputs from Kaggle, unchanged.\n\n"
             "Operational totals include measured and inferred passages, explicitly separated in the videos and manifest. "
             "Timeout counts are estimates and do not prove an ID change. No accuracy claim.\n\n"
             "Publication performs only SHA-bound transport; detector, tracker, ReID, counting and encoding are not rerun.\n\n"
             f"Executed code: `{executed_commit}`. Delivery manifest/publisher: `{delivery_commit}`.\n")
    created = api(f"repos/{REPOSITORY}/releases", method="POST", body={"tag_name": TAG,
        "target_commitish": executed_commit, "name": "Phase 8 B v2 — TGDI annotated review v1",
        "body": notes, "draft": True, "prerelease": True})
    release_id = created["id"]
    require(created.get("tag_name") == TAG and created.get("draft") is True, "Unexpected delivery draft")
    files = [video_dir / item["filename"] for item in plan] + [delivered_manifest, checksums]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(command, ["gh", "release", "upload", TAG, str(path), "--repo", REPOSITORY])
                   for path in files]
        for future in as_completed(futures):
            future.result()
    draft = api(f"repos/{REPOSITORY}/releases/{release_id}")
    draft_assets = {asset["name"]: asset for asset in draft["assets"]}
    require(len(draft_assets) == 10 and set(draft_assets) == {path.name for path in files}, "Unexpected draft asset set")
    for path in files:
        verify_remote_asset(draft_assets[path.name], path)
    api(f"repos/{REPOSITORY}/releases/{release_id}", method="PATCH", body={"draft": False})
    # Only the final API snapshot supplies links. Draft download URLs can use a
    # temporary untagged prefix and must never become the retained public index.
    final = api(f"repos/{REPOSITORY}/releases/{release_id}")
    require(final.get("draft") is False and final.get("tag_name") == TAG
            and final.get("target_commitish") == executed_commit, "Published release/source differs")
    resolved = api(f"repos/{REPOSITORY}/commits/{TAG}")
    require(resolved.get("sha") == executed_commit, "Published tag resolves to another executed commit")
    final_assets = {asset["name"]: asset for asset in final["assets"]}
    verified = []
    for path in files:
        record = verify_remote_asset(final_assets[path.name], path)
        expected_url = f"https://github.com/{REPOSITORY}/releases/download/{TAG}/{path.name}"
        require(record["browser_download_url"] == expected_url, "Final asset URL does not use the published tag")
        verified.append(record)
    receipt = {"schema_version": "phase8_b_v2_publication_receipt_v1",
        "claim_type": "ACTUAL_FINAL_GITHUB_RELEASE_PUBLICATION_NOT_MODEL_EVALUATION", "recorded_at_utc": now(),
        "repository": REPOSITORY, "release_id": release_id, "tag_name": TAG, "html_url": final["html_url"],
        "draft": False, "published_at": final["published_at"], "executed_source_commit": executed_commit,
        "delivery_source_commit": delivery_commit, "resolved_tag_commit_sha": resolved["sha"],
        "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "workflow_url": f"https://github.com/{REPOSITORY}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        "delivery_manifest_sha256": sha256(delivered_manifest), "video_asset_count": 8,
        "assets": [dict(record, video_id=next(item["video_id"] for item in plan if item["filename"] == record["name"]))
                   for record in verified if record["name"].endswith(".mp4")],
        "supplemental_assets": [record for record in verified if not record["name"].endswith(".mp4")],
        "expected_final_release_asset_count": 11, "receipt_self_digest_excluded": True,
        "credential_verification": probe_proof, "verified_kaggle_downloads": sorted(downloaded, key=lambda item: item["video_id"]),
        "executed_source_files": manifest["executed_source_files"], "frame_total": sum(item["frame_count"] for item in plan),
        "operational_total": sum(item["operational_total"] for item in plan),
        "measured_total": sum(item["measured_total"] for item in plan), "inferred_total": sum(item["inferred_total"] for item in plan),
        "new_detector_tracker_reid_counting_or_encoding_execution": False, "signed_download_urls_retained": False,
        "videos_committed_to_git": False}
    receipt_path = work / "publication_receipt.json"
    write_json(receipt_path, receipt)
    command(["gh", "release", "upload", TAG, str(receipt_path), "--repo", REPOSITORY])
    last = api(f"repos/{REPOSITORY}/releases/{release_id}")
    require(len(last["assets"]) == 11 and {asset["name"] for asset in last["assets"]}
            == {path.name for path in files} | {receipt_path.name}, "Final release asset count differs")
    receipt_asset = next(asset for asset in last["assets"] if asset["name"] == receipt_path.name)
    verified_receipt = verify_remote_asset(receipt_asset, receipt_path)
    require(verified_receipt["browser_download_url"]
            == f"https://github.com/{REPOSITORY}/releases/download/{TAG}/{receipt_path.name}",
            "Receipt URL does not use the published tag")
    print(json.dumps({"status": "PUBLISHED", "release_url": final["html_url"], "verified_videos": 8,
                      "receipt_sha256": sha256(receipt_path), "executed_source_commit": executed_commit,
                      "delivery_source_commit": delivery_commit}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true", help="Validate retained manifest/payload without network or mutation")
    parser.add_argument("--payload", type=Path, help="Local validation payload; only accepted with --validate-only")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if args.validate_only:
        require(args.payload is not None, "Local validation needs --payload")
        payload = json.loads(args.payload.read_text())
        manifest = json.loads((root / MANIFEST_PATH).read_text())
        delivery, executed, plan = validate_payload_manifest(payload, manifest)
        print(json.dumps({"status": "LOCAL_VALIDATION_PASS_NO_NETWORK_OR_MUTATION", "videos": len(plan),
                          "delivery_source_commit": delivery, "executed_source_commit": executed}))
        return
    require(args.payload is None, "Local payload paths are only allowed in validate-only mode")
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY,
            "Publisher requires the expected repository's GitHub Actions runtime")
    require(bool(os.environ.get("GH_TOKEN")), "Native Actions token missing")
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    require(re.fullmatch(r"[0-9]+", run_id) and re.fullmatch(r"[0-9]+", attempt), "Invalid workflow run identity")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    require(event.get("action") == EVENT_TYPE, "Unexpected dispatch event type")
    payload = event.get("client_payload")
    # Mask capabilities before any manifest/source/network validation can fail.
    if isinstance(payload, dict) and isinstance(payload.get("downloads"), list):
        for row in payload["downloads"]:
            if isinstance(row, dict):
                validate_url(row.get("url"), mask=True)
    manifest_path = root / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text())
    delivery, executed, plan = validate_payload_manifest(payload, manifest)
    verify_source_binding(root, delivery, executed, manifest)
    require_unused_tag(TAG)
    work = Path(os.environ["RUNNER_TEMP"]) / f"phase8-b-v2-publication-{run_id}-{attempt}"
    require(not work.exists(), "Publication working directory already exists")
    work.mkdir()
    print(json.dumps({"stage": "checksum_upload_authorization_probe"}), flush=True)
    proof = upload_probe(executed, work, run_id, attempt)
    print(json.dumps({"stage": "upload_authorization_verified_before_bulk_download"}), flush=True)
    publish(root, manifest_path, manifest, plan, delivery, executed, work, proof)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        message = str(error) if isinstance(error, PublicationError) else "Unexpected failure; signed URLs and response bodies withheld"
        print(json.dumps({"status": "FAILED", "error_type": type(error).__name__, "safe_message": message}), file=sys.stderr)
        sys.exit(1)
