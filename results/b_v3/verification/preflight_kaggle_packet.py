#!/usr/bin/env python3
"""Verify/extract the actual packet and prepare all eight source inputs only.

Run in a fresh Python process. No counting, rendering, detector, tracker or ReID
entry point is called. Exact source snapshots and JSON dependencies must work
without access to the surrounding repository or retained PNG image files.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import time

from verify_submitted_packet import verify, builder


def preflight(*, repo_root, packet_dir, source_run_root, source_video_root, snapshot_parent):
    started = time.perf_counter()
    repo, packet = Path(repo_root).resolve(), Path(packet_dir).resolve()
    parent = Path(snapshot_parent).resolve()
    if parent.exists():
        raise ValueError("Preflight needs a new isolated snapshot parent")
    proof = verify(repo, packet)
    notebook = json.loads((packet / "phase8_tgdi_b_v3_review.ipynb").read_text())
    namespace = {"PHASE8_B_V3_SOURCE_PARENT": str(parent)}
    capture = io.StringIO()
    with redirect_stdout(capture):
        # verify() established that this is the exact allowlisted extraction
        # code and all embedded bytes equal trusted current repository files.
        exec(builder.cell_source(notebook["cells"][1]), namespace)
    snapshot = namespace["REPO_ROOT"]
    if not snapshot.is_relative_to(parent):
        raise ValueError("Extracted snapshot escapes its new parent")
    if any(name.startswith("phase_8_") or name == "phase_5_geometry_helpers" for name in sys.modules):
        raise ValueError("Use a fresh process: project source modules were already loaded")
    batch = importlib.import_module("phase_8_b_v3_batch")
    expected = snapshot / "notebooks/phase_8_b_v3_batch.py"
    if Path(batch.__file__).resolve() != expected:
        raise ValueError("Preflight imported a module outside the extracted snapshot")
    prepared = batch.prepare_b_v3_batch(repo_root=snapshot, source_run_root=source_run_root,
        source_video_root=source_video_root, input_root="/path-not-used-in-explicit-source-preflight", video_ids=None)
    jobs = prepared["jobs"]
    if len(jobs) != 8 or set(prepared["selected_video_ids"]) != set(builder.EXPECTED_VIDEO_IDS):
        raise ValueError("Preflight did not prepare all eight actual inputs")
    if sum(job["metadata"]["frame_count"] for job in jobs) != 72590:
        raise ValueError("Actual retained source frame coverage differs")
    if any(name.split(".")[0] in builder.FORBIDDEN_IMPORTS for name in sys.modules):
        raise ValueError("A forbidden model/network runtime was loaded")
    manifest = json.loads((packet / "source_bundle_manifest.json").read_text())
    for name, entry in manifest["source_files"].items():
        data = (snapshot / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Extracted dependency changed during preparation")
    return {"claim_type": "ACTUAL_ISOLATED_PACKET_DEPENDENCY_PREPARATION_NOT_COUNTING_OR_MODEL_EXECUTION",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS",
        "source_bundle_binding_sha256": proof["source_bundle_binding_sha256"],
        "submitted_notebook_sha256": proof["submitted_notebook_sha256"],
        "source_file_count": proof["source_file_count"], "packet_verification_check_count": proof["check_count"],
        "all_eight_prepared": True, "retained_frame_coverage": 72590,
        "source_snapshot_root": str(snapshot), "source_run_root": str(Path(source_run_root).resolve()),
        "source_video_root": str(Path(source_video_root).resolve()),
        "verified_original_video_sha256": True, "source_cache_and_original_manifest_sha256_verified": True,
        "review_manifest_sha256": prepared["reviews_sha256"],
        "revision_policy_sha256": prepared["policy_sha256"],
        "compact_baseline_sha256": prepared["b_v2_reference"]["sha256"],
        "native_png_files_bundled_or_required_by_prepare": False,
        "only_bootstrap_cell_executed": True, "canonical_notebook_code_cells_executed": False,
        "counting_rendering_detector_tracker_reid_executed": False,
        "review_source_anchor_replay_performed": False,
        "remote_submission_performed": False,
        "snapshot_unchanged_during_preparation": True,
        "videos": [{"video_id": job["video_id"], "frame_count": job["metadata"]["frame_count"],
            "video_sha256": job["b_v2_source_identity"]["video_sha256"],
            "records_sha256": job["b_v2_source_identity"]["records_sha256"],
            "geometry_sha256": job["b_v2_source_identity"]["geometry_sha256"]} for job in jobs],
        "wall_seconds": time.perf_counter() - started,
        "preflight_helper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--packet-dir", required=True)
    parser.add_argument("--source-run-root", required=True)
    parser.add_argument("--source-video-root", required=True)
    parser.add_argument("--snapshot-parent", required=True)
    parser.add_argument("--proof-path", required=True)
    args = parser.parse_args()
    target = Path(args.proof_path).resolve()
    if target.exists():
        raise ValueError("Refusing to overwrite an existing preparation proof")
    proof = preflight(repo_root=args.repo_root, packet_dir=args.packet_dir,
        source_run_root=args.source_run_root, source_video_root=args.source_video_root,
        snapshot_parent=args.snapshot_parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": proof["status"], "all_eight_prepared": proof["all_eight_prepared"],
        "source_file_count": proof["source_file_count"], "proof_path": str(target),
        "counting_rendering_detector_tracker_reid_executed": False}))
