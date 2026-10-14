#!/usr/bin/env python3
"""Read-only artifact checks for the raw sampling/N1 proposal; no inference."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import cv2
from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sample_dir = repo / "docs/evidence/phase_7/sampling"
    manifest = json.loads((sample_dir / "build_manifest.json").read_text())
    checks = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    def check_artifact(value: dict) -> None:
        path = repo / value["path"]
        check("artifact_exists:" + value["path"], path.is_file())
        check("artifact_hash:" + value["path"], sha256(path) == value["sha256"])

    for field in ("geometry_proposal", "geometry_preview", "geometry_alignment_sheet", "sampling_plan", "builder"):
        check_artifact(manifest[field])
    plan = json.loads((repo / manifest["sampling_plan"]["path"]).read_text())
    draft_path = repo / manifest["geometry_proposal"]["path"]
    draft = json.loads(draft_path.read_text())
    original = json.loads((repo / draft["template_source"]["path"]).read_text())
    check_artifact(draft["template_source"])
    check("new_source_identity", draft["source_video"]["sha256"] == "a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082")
    check("night_not_accepted", draft["geometry_contract_accepted"] is False and draft["approval_feedback"] is None)
    check("night_semantics_not_confirmed", draft["confirmed_direction_metadata"] is None)
    check("counting_execution_disallowed", draft["counting_execution_allowed"] is False)
    check("g3_relative_geometry_retained_exactly", draft["normalized"] == original["normalized"])
    check("g3_native_geometry_retained_exactly", draft["rendered_native_pixels"] == original["rendered_native_pixels"])
    check("endpoint_difference_not_snapped", draft["line_polygon_endpoint_difference_reference"] == original["line_polygon_endpoint_difference_reference"])
    check("geometry_gate_binds_proposal_hash", plan["geometry_gate"]["proposal_sha256"] == sha256(draft_path))
    check("geometry_gate_required", plan["geometry_gate"]["require_geometry_approval"] is True)
    check("all_native_source_frames_decoded", manifest["actual_decoded_frames"] == 9590)
    check("no_model_or_enhancement_execution", manifest["no_enhancement_or_model_execution"] is True)

    spec = importlib.util.spec_from_file_location("retained_geometry_verification", repo / "notebooks/phase_5_geometry_helpers.py")
    geometry_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = geometry_module
    spec.loader.exec_module(geometry_module)
    geometry = geometry_module.Geometry.from_draft(draft_path, 1280, 720)
    check("polygon_simple_finite_nonoverlap_validation", geometry.width == 1280 and geometry.height == 720)
    check("geometry_line_matches_native", list(geometry.p1) == draft["rendered_native_pixels"]["line"]["P1"] and list(geometry.p2) == draft["rendered_native_pixels"]["line"]["P2"])
    indices_by_split, ranges_by_split = {}, {}
    for split in ("development", "holdout"):
        indices = plan[split]["sample_frame_indices"]
        check(split + "_samples_unique_sorted", indices == sorted(set(indices)))
        ranges = set()
        for segment in plan[split]["segments"]:
            start, end = segment["start_frame"], segment["end_frame"]
            check(segment["segment_id"] + "_frame_bounds", 0 <= start <= end < 9590)
            check(segment["segment_id"] + "_continuous_budget", end-start+1 == segment["frame_count"] == 240)
            check(segment["segment_id"] + "_anchor_in_window", start <= segment["anchor_frame"] <= end)
            check(segment["segment_id"] + "_no_within_split_window_overlap", ranges.isdisjoint(range(start, end+1)))
            ranges.update(range(start, end+1))
        check(split + "_samples_within_windows", set(indices).issubset(ranges))
        indices_by_split[split], ranges_by_split[split] = set(indices), ranges
    check("development_holdout_window_disjoint", ranges_by_split["development"].isdisjoint(ranges_by_split["holdout"]))
    check("development_holdout_sample_disjoint", indices_by_split["development"].isdisjoint(indices_by_split["holdout"]))
    check("dev_fifteen_samples", len(indices_by_split["development"]) == 15)
    check("holdout_ten_samples", len(indices_by_split["holdout"]) == 10)
    retained_indices = set()
    for entry in manifest["native_sample_inventory"]:
        if "retained_native_png" not in entry:
            continue
        value = entry["retained_native_png"]
        check_artifact(value)
        with Image.open(repo / value["path"]) as image:
            check("native_dimensions:" + str(entry["frame_index"]), image.size == (1280, 720))
            check("native_pixels:" + str(entry["frame_index"]), hashlib.sha256(image.convert("RGB").tobytes()).hexdigest() == entry["native_pixel_sha256_rgb"])
        retained_indices.add(entry["frame_index"])
    check("native_samples_cover_plan", retained_indices == indices_by_split["development"] | indices_by_split["holdout"])
    for sheet in manifest["temporal_sheets"]:
        check_artifact(sheet)
        check("raw_temporal_sheet:" + sheet["path"], sheet["enhancement"] == "none")
    for clip in manifest["runtime_only_clips"]:
        path = Path(clip["runtime_path"])
        check("runtime_clip_hash:" + clip["segment_id"], sha256(path) == clip["sha256"])
        capture = cv2.VideoCapture(str(path))
        decoded = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            check("runtime_clip_dimensions:" + clip["segment_id"] + ":" + str(decoded), frame.shape[:2] == (360, 640))
            decoded += 1
        capture.release()
        check("runtime_clip_exact_frame_count:" + clip["segment_id"], decoded == clip["frame_count"] == 240)
        check("runtime_clip_not_source_or_model_input:" + clip["segment_id"], clip["retained_in_git"] is False)
    result = {"status": "PASS", "passed": len(checks), "failed": 0, "checks": checks, "scope": "raw native pixel/source/hash/sample-split/geometry-proposal checks; no model, enhancement or count performance", "checked_manifest_sha256": sha256(sample_dir / "build_manifest.json")}
    output = args.output or sample_dir / "artifact_validation.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "passed": result["passed"], "failed": result["failed"]}))


if __name__ == "__main__":
    main()
