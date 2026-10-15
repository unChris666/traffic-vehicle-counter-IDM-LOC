"""Decode the eight actual TGDI sources and render unapproved G3 proposals.

This preparation tool performs no model inference, counting, or enhancement.
Source videos remain outside Git. The CSV is the retained Kaggle API listing,
and its expected byte sizes gate decoding; filename fields use the grammar
explicitly supplied by the user, not guessed recording dates or GPS text.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


KAGGLE_ROOT = "/kaggle/input/datasets/chrisbiran/tgdi-traffic-videos"
PERIODS = ("PAGI", "SIANG", "SORE", "MALAM")
DAYS = ("WEEKDAY", "WEEKEND")
BURST_INDICES = (0, 15, 30, 45, 59)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)


def ffprobe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
         "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return {"status": "unavailable", "returncode": result.returncode,
                "stderr": result.stderr[:2000]}
    result_json = json.loads(result.stdout)
    # The local path is execution context, not a rebasable dataset identifier.
    result_json.get("format", {}).pop("filename", None)
    return {"status": "observed_ffprobe_metadata", "metadata": result_json}


def save_frame(frame: np.ndarray, index: int, directory: Path, root: Path) -> dict:
    path = directory / f"frame_{index:09d}.png"
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"Could not write {path}")
    return {"frame_index": index, "path": relative(path, root), "sha256": sha256(path),
            "bgr_uint8_pixel_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
            "width": int(frame.shape[1]), "height": int(frame.shape[0]),
            "lossless": True, "source": "actual_sequential_OpenCV_decode"}


def annotated_proposal(raw: np.ndarray, geometry: dict, video_id: str) -> Image.Image:
    image = Image.fromarray(cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(overlay)
    a = [tuple(p) for p in geometry["side_a_polygon"]]
    b = [tuple(p) for p in geometry["side_b_polygon"]]
    blue, orange, yellow = (35, 145, 255), (255, 137, 35), (255, 244, 0)
    draw.polygon(a, fill=(*blue, 48), outline=(*blue, 255), width=2)
    draw.polygon(b, fill=(*orange, 50), outline=(*orange, 255), width=2)
    endpoints = geometry["line"]
    draw.line([tuple(endpoints["P1"]), tuple(endpoints["P2"])], fill=(*yellow, 255), width=3)
    for label, point in endpoints.items():
        x, y = point
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(*yellow, 255))
        tx = min(max(x + 6, 3), image.width - 35)
        ty = min(max(y - 23, 3), image.height - 24)
        draw.text((tx, ty), label, font=font(17), fill=(*yellow, 255),
                  stroke_width=2, stroke_fill=(0, 0, 0, 255))
    for label, poly, color in (("A", a, blue), ("B", b, orange)):
        xy = np.mean(np.asarray(poly), axis=0)
        draw.text(tuple(xy), label, font=font(28), fill=(*color, 255),
                  stroke_width=2, stroke_fill=(0, 0, 0, 255))
    draw.rectangle((0, 0, image.width, 63), fill=(0, 0, 0, 210))
    draw.text((8, 4), video_id, font=font(17), fill="white")
    draw.text((8, 27), "PROPOSED G3 / direction UNCONFIRMED", font=font(16), fill="yellow")
    draw.text((8, 47), "Native frame 0; no detector, bbox or track BC", font=font(11), fill="white")
    return Image.alpha_composite(image, overlay).convert("RGB")


def contact_sheet(samples: list[dict], root: Path, title: str, out: Path) -> None:
    thumb_width, thumb_height = 480, 360
    canvas = Image.new("RGB", (thumb_width * 3, (thumb_height + 36) * 2 + 55), "#161616")
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 8), title, font=font(20), fill="white")
    for position, sample in enumerate(samples):
        x = (position % 3) * thumb_width
        y = 55 + (position // 3) * (thumb_height + 36)
        image = Image.open(root / sample["path"]).convert("RGB")
        image.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        canvas.paste(image, (x + (thumb_width - image.width) // 2, y))
        draw.text((x + 8, y + thumb_height + 5), f"actual decoded frame {sample['frame_index']}",
                  font=font(15), fill="white")
    canvas.save(out)


def inspect_video(row: dict, args: argparse.Namespace, template: dict) -> dict:
    root, source_root = args.repository_root, args.source_root
    name = row["name"]
    source = source_root / name
    expected_size = int(row["size"])
    if not source.is_file() or source.stat().st_size != expected_size:
        raise RuntimeError(f"Incomplete/unavailable source {name}: expected {expected_size} bytes")
    source_stat = source.stat()
    source_hash = sha256(source)
    video_id = Path(name).stem
    code, day_type, period = video_id.split("-")
    if code != "TGDI" or day_type not in DAYS or period not in PERIODS:
        raise ValueError(f"Filename does not match the user-confirmed grammar: {name}")
    prepared = root / "docs/evidence/phase_8/input_preparation" / video_id
    prepared.mkdir(parents=True, exist_ok=True)
    report_path = prepared / "source_inspection.json"
    # Checkpoint reuse is content-bound; never trust an output from a partial source.
    if args.reuse_complete and report_path.exists():
        previous = json.loads(report_path.read_text())
        if previous.get("source_video", {}).get("sha256") == source_hash:
            sample_ok = all(sha256(root / item["path"]) == item["sha256"]
                            for item in previous["retained_samples"])
            if sample_ok and previous.get("status") == "ACTUAL_SEQUENTIAL_DECODE_COMPLETE":
                print(f"REUSE verified {name}", flush=True)
                return previous
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV could not open {name}")
    reported_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = capture.get(cv2.CAP_PROP_FPS)
    reported_width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
    reported_height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fourcc_number = int(capture.get(cv2.CAP_PROP_FOURCC))
    fourcc = "".join(chr((fourcc_number >> (8 * shift)) & 255) for shift in range(4))
    target_middle = int(reported_count) // 2 if reported_count > 0 else -1
    samples, dimensions, count, started = {}, set(), 0, time.perf_counter()
    first = last = None
    print(f"DECODE {name} ({expected_size} bytes)", flush=True)
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise RuntimeError(f"Unexpected decoded image format at {name}:{count}")
        dimensions.add((int(frame.shape[1]), int(frame.shape[0])))
        if count == 0:
            first = frame.copy()
        if count in BURST_INDICES or count == target_middle:
            samples[count] = save_frame(frame, count, prepared, root)
        last = frame
        count += 1
        if count % 3000 == 0:
            print(f"  {name}: decoded {count} frames", flush=True)
    capture.release()
    elapsed = time.perf_counter() - started
    if count < 1 or first is None or last is None:
        raise RuntimeError(f"No decodable frames in {name}")
    if len(dimensions) != 1:
        raise RuntimeError(f"Variable native dimensions require explicit handling: {name}:{dimensions}")
    actual_middle = count // 2
    if actual_middle not in samples:
        # Actual counts, not metadata, determine the retained middle frame.
        retry = cv2.VideoCapture(str(source))
        for index in range(actual_middle + 1):
            ok, frame = retry.read()
            if not ok:
                raise RuntimeError(f"Repeat sequential sample failed at {name}:{index}")
        retry.release()
        samples[actual_middle] = save_frame(frame, actual_middle, prepared, root)
    samples[count - 1] = save_frame(last, count - 1, prepared, root)
    final_stat = source.stat()
    if (source_stat.st_size, source_stat.st_mtime_ns) != (final_stat.st_size, final_stat.st_mtime_ns):
        raise RuntimeError(f"Source changed while decoding: {name}")
    width, height = next(iter(dimensions))
    native = {"width": width, "height": height,
              "line": {key: [point[0] * width, point[1] * height]
                       for key, point in template["normalized"]["line"].items()},
              "side_a_polygon": [[u * width, v * height]
                                 for u, v in template["normalized"]["side_a_polygon"]],
              "side_b_polygon": [[u * width, v * height]
                                 for u, v in template["normalized"]["side_b_polygon"]],
              "side_b_max_x": template["normalized"]["side_b_max_u"] * width}
    proposal_dir = root / "docs/evidence/phase_8/geometry_proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    preview = proposal_dir / f"{video_id}-G3-T1.png"
    annotated_proposal(first, native, video_id).save(preview)
    proposal_path = proposal_dir / f"{video_id}-G3-T1.json"
    proposal = {
        "draft_id": f"{video_id}-G3-T1", "status": "PROPOSAL_NOT_HUMAN_APPROVED",
        "claim_type": "PROPOSAL", "source_video": {"filename": name, "sha256": source_hash,
        "size_bytes": expected_size, "kaggle_path": f"{KAGGLE_ROOT}/{name}"},
        "source_frame": {**samples[0], "coordinate_space": "native_full_frame_pixels",
                         "origin": "upper_left", "x_axis": "right", "y_axis": "down"},
        "template_source": {"path": args.template_relative_path,
                            "sha256": sha256(root / args.template_relative_path)},
        "template_reference": template["template_reference"],
        "normalization_convention": template["normalization_convention"],
        "normalized": template["normalized"],
        "line_endpoints_reference": template["line_endpoints_reference"],
        "side_a_polygon_reference": template["side_a_polygon_reference"],
        "side_b_polygon_reference": template["side_b_polygon_reference"],
        "perimeter_labels": ["P1A", "P1B", "P1D", "P1C"],
        "rendered_native_pixels": native,
        "line_polygon_endpoint_difference_reference": template["line_polygon_endpoint_difference_reference"],
        "transfer_policy": "Explicit full-frame normalized G3 projection only; no crop, rotation, snapping, stabilization or road alignment inferred. Aspect ratio/viewpoint may differ; per-video review required.",
        "selected_anchor": "bottom_center",
        "anchor_source": "future raw detector-linked measured emitted vehicle bbox; no model, bbox or track BC produced by this preparation",
        "confirmed_direction_metadata": None,
        "direction_review": {"A_TO_B": None, "B_TO_A": None, "status": "UNKNOWN_REQUIRES_PER_VIDEO_USER_REVIEW"},
        "geometry_review_confirmed": False, "geometry_contract_accepted": False,
        "counting_execution_allowed": False, "approval_feedback": None,
        "preview": {"path": relative(preview, root), "sha256": sha256(preview),
                    "native_width": width, "native_height": height},
        "review_questions": ["Does the yellow finite line cross both intended traffic corridors?",
            "Do A and B contain visible measured trajectory context before and after crossing?",
            "Does the B right cap, burned-in map/text, parked objects or occlusion require a revision?",
            "Confirm or revise A_TO_B and B_TO_A camera-approach semantics for this particular video."]}
    write_json(proposal_path, proposal)
    ordered_samples = [samples[index] for index in sorted(samples)]
    burst_sheet = prepared / "beginning_temporal_contact_sheet.png"
    contact_sheet([samples[i] for i in BURST_INDICES if i in samples], root,
                  f"{video_id} | sequential frames 0/15/30/45/59", burst_sheet)
    representative = prepared / "beginning_middle_end_contact_sheet.png"
    contact_sheet([samples[i] for i in (0, actual_middle, count - 1)], root,
                  f"{video_id} | actual beginning/middle/end", representative)
    issues = []
    if int(reported_count) != count:
        issues.append("OpenCV metadata frame count differs from sequential decode count; reason unresolved")
    report = {"schema_version": "phase8_tgdi_input_preparation_v1",
        "status": "ACTUAL_SEQUENTIAL_DECODE_COMPLETE", "claim_type": "EXPERIMENT_RESULT",
        "source_video": {"filename": name, "video_id": video_id, "sha256": source_hash,
            "size_bytes": expected_size, "kaggle_path": f"{KAGGLE_ROOT}/{name}"},
        "filename_metadata": {"store_code": code, "day_type": day_type.lower(),
            "recording_period": period.lower(), "provenance": "user-confirmed KODETOKO-KATEGORI-KEADAAN filename grammar; not derived from video creation date or embedded text"},
        "metadata": {"width": width, "height": height, "aspect_ratio": f"{width}:{height}",
            "opencv_reported_width": reported_width, "opencv_reported_height": reported_height,
            "opencv_reported_fps": fps if fps > 0 else None,
            "opencv_reported_frame_count": reported_count,
            "decoded_frame_count": count,
            "duration_estimate_seconds": count / fps if fps > 0 else None,
            "duration_estimate_method": "actual decoded frame count divided by OpenCV reported average FPS; source PTS/CFR/VFR status not validated",
            "fourcc": fourcc, "ffprobe": ffprobe(source)},
        "decode": {"method": "full sequential cv2.VideoCapture.read from frame zero; no seek",
            "first_frame_index": 0, "last_frame_index": count - 1,
            "successful_frames": count, "first_false_read_at_index": count,
            "terminal_false_read_reason": "not distinguished by OpenCV; metadata comparison retained",
            "native_dimensions_consistent_over_all_decoded_frames": True,
            "decode_loop_elapsed_seconds": elapsed},
        "retained_samples": ordered_samples,
        "beginning_temporal_contact_sheet": {"path": relative(burst_sheet, root), "sha256": sha256(burst_sheet)},
        "beginning_middle_end_contact_sheet": {"path": relative(representative, root), "sha256": sha256(representative)},
        "geometry_proposal": {"path": relative(proposal_path, root), "sha256": sha256(proposal_path),
                              "status": "PROPOSAL_NOT_HUMAN_APPROVED"},
        "camera_stability": {"category": None, "status": "NOT_ASSESSED_AUTOMATICALLY",
            "limitation": "The five-frame beginning burst is retained for bounded qualitative review only, not full-video camera-stability proof."},
        "technical_issues": issues, "model_inference_executed": False,
        "counting_executed": False, "night_enhancement_executed": False,
        "environment": {"python": platform.python_version(), "opencv": cv2.__version__, "numpy": np.__version__},
        "source_inspection_path": relative(report_path, root)}
    write_json(report_path, report)
    print(f"DONE {name}: {width}x{height}, decoded={count}, reported={reported_count}, sha256={source_hash}", flush=True)
    return report


def validate_outputs(root: Path, source_root: Path, inventory: dict, reports: list[dict]) -> dict:
    """Check retained evidence and independently re-decode the beginning samples.

    This validates preparation artifacts, not detection/counting performance.
    The full sequential decode count is supported by each source report; the
    independent second pass below checks only frames 0..59 for sample identity.
    """
    sys.path.insert(0, str(root / "notebooks"))
    from phase_5_geometry_helpers import Geometry
    checks = []

    def check(name: str, condition: bool) -> None:
        checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise RuntimeError(f"Preparation artifact validation failed: {name}")

    check("exactly_eight_actual_inputs", len(inventory["videos"]) == len(reports) == 8)
    check("eight_unique_source_sha256", len({v["sha256"] for v in inventory["videos"]}) == 8)
    for video, report in zip(inventory["videos"], reports):
        label = video["video_id"]
        source = source_root / video["filename"]
        check(f"{label}:complete_actual_source_size", source.stat().st_size == video["size_bytes"])
        check(f"{label}:actual_source_sha256", sha256(source) == video["sha256"])
        check(f"{label}:retained_report_sha256", sha256(root / video["source_inspection"]["path"]) == video["source_inspection"]["sha256"])
        check(f"{label}:decoded_count_matches_reported_metadata", video["decoded_frame_count"] == video["reported_frame_count"])
        check(f"{label}:no_inference_or_counting", not report["model_inference_executed"] and not report["counting_executed"])
        samples = {sample["frame_index"]: sample for sample in report["retained_samples"]}
        check(f"{label}:beginning_actual_middle_actual_end_retained",
              {0, video["decoded_frame_count"] // 2, video["decoded_frame_count"] - 1}.issubset(samples))
        for index, sample in samples.items():
            path = root / sample["path"]
            decoded = cv2.imread(str(path), cv2.IMREAD_COLOR)
            check(f"{label}:{index}:native_png_file_sha256", sha256(path) == sample["sha256"])
            check(f"{label}:{index}:native_png_dimensions", decoded is not None and decoded.shape == (video["height"], video["width"], 3))
            check(f"{label}:{index}:native_png_bgr_pixel_sha256",
                  hashlib.sha256(decoded.tobytes()).hexdigest() == sample["bgr_uint8_pixel_sha256"])
        capture = cv2.VideoCapture(str(source))
        for index in range(max(BURST_INDICES) + 1):
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Independent beginning decode failed: {label}:{index}")
            if index in BURST_INDICES:
                check(f"{label}:{index}:independent_source_decode_matches_sample",
                      hashlib.sha256(frame.tobytes()).hexdigest() == samples[index]["bgr_uint8_pixel_sha256"])
        capture.release()
        proposal_reference = video["geometry_proposal"]
        path = root / proposal_reference["path"]
        proposal = json.loads(path.read_text())
        check(f"{label}:proposal_file_sha256", sha256(path) == proposal_reference["sha256"])
        check(f"{label}:proposal_source_video_bound", proposal["source_video"]["sha256"] == video["sha256"])
        check(f"{label}:proposal_source_frame_bound", proposal["source_frame"] == {**samples[0],
              "coordinate_space": "native_full_frame_pixels", "origin": "upper_left", "x_axis": "right", "y_axis": "down"})
        geometry = Geometry.from_draft(path, video["width"], video["height"])
        rendered = proposal["rendered_native_pixels"]
        check(f"{label}:finite_simple_nonoverlapping_geometry", geometry.width == video["width"] and geometry.height == video["height"])
        check(f"{label}:normalized_projection_line_exact",
              list(geometry.p1) == rendered["line"]["P1"] and list(geometry.p2) == rendered["line"]["P2"])
        check(f"{label}:normalized_projection_side_a_exact", [list(p) for p in geometry.side_a] == rendered["side_a_polygon"])
        check(f"{label}:normalized_projection_side_b_exact", [list(p) for p in geometry.side_b] == rendered["side_b_polygon"])
        check(f"{label}:unapproved_proposal_cannot_enable_counting", not proposal["geometry_review_confirmed"]
              and not proposal["geometry_contract_accepted"] and not proposal["counting_execution_allowed"]
              and proposal["approval_feedback"] is None)
        check(f"{label}:direction_not_inferred", proposal["confirmed_direction_metadata"] is None
              and proposal["direction_review"]["A_TO_B"] is None and proposal["direction_review"]["B_TO_A"] is None)
        check(f"{label}:native_preview_sha256", sha256(root / proposal["preview"]["path"]) == proposal["preview"]["sha256"])
        for key in ("beginning_temporal_contact_sheet", "beginning_middle_end_contact_sheet"):
            check(f"{label}:{key}:sha256", sha256(root / report[key]["path"]) == report[key]["sha256"])
    check("eight_video_overview_sha256", sha256(root / inventory["geometry_overview"]["path"]) == inventory["geometry_overview"]["sha256"])
    return {"status": "PASS", "claim_type": "EXPERIMENT_RESULT",
        "validation_scope": "Retained source-preparation artifact integrity, geometry validity, source identity, independently re-decoded beginning samples; no model-quality or traffic-count metric",
        "checks_passed": sum(c["passed"] for c in checks), "checks_total": len(checks),
        "native_source_images_validated": sum(len(r["retained_samples"]) for r in reports),
        "independent_beginning_source_samples_validated": len(BURST_INDICES) * len(reports),
        "actual_full_decode_total_from_reports": sum(v["decoded_frame_count"] for v in inventory["videos"]),
        "independent_second_pass_full_video_decode_performed": False,
        "model_inference_executed": False, "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--reuse-complete", action="store_true")
    args = parser.parse_args()
    args.repository_root = args.repository_root.resolve()
    args.template_relative_path = "docs/evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json"
    root = args.repository_root
    listing_path = root / "docs/evidence/phase_8/inventory/tgdi_kaggle_file_listing_20261015.csv"
    rows = list(csv.DictReader(listing_path.open()))
    expected_names = {f"TGDI-{day}-{period}.mp4" for day in DAYS for period in PERIODS}
    if {row["name"] for row in rows} != expected_names or len(rows) != 8:
        raise ValueError("Expected exactly the eight actually listed user-identified TGDI files")
    rows.sort(key=lambda row: (DAYS.index(Path(row["name"]).stem.split("-")[1]),
                               PERIODS.index(Path(row["name"]).stem.split("-")[2])))
    template = json.loads((root / args.template_relative_path).read_text())
    reports = []
    for row in rows:
        reports.append(inspect_video(row, args, template))
    videos = []
    for report in reports:
        videos.append({**report["source_video"], **report["filename_metadata"],
            "width": report["metadata"]["width"], "height": report["metadata"]["height"],
            "opencv_fps": report["metadata"]["opencv_reported_fps"],
            "reported_frame_count": report["metadata"]["opencv_reported_frame_count"],
            "decoded_frame_count": report["metadata"]["decoded_frame_count"],
            "duration_estimate_seconds": report["metadata"]["duration_estimate_seconds"],
            "codec_fourcc": report["metadata"]["fourcc"],
            "source_inspection": {"path": report["source_inspection_path"],
                "sha256": sha256(root / report["source_inspection_path"])},
            "geometry_proposal": report["geometry_proposal"],
            "model_inference_executed": False, "counting_executed": False})
    overview = root / "docs/evidence/phase_8/geometry_proposals/TGDI_eight_video_G3_T1_overview.png"
    canvas = Image.new("RGB", (1280, 4 * 520 + 65), "#181818")
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 8), "TGDI: 8 PROPOSED G3 placements / none approved", font=font(24), fill="white")
    draw.text((12, 39), "Native source 640x480. A/B are regions; approaching/away directions require separate review.", font=font(16), fill="yellow")
    for position, report in enumerate(reports):
        proposal = json.loads((root / report["geometry_proposal"]["path"]).read_text())
        image = Image.open(root / proposal["preview"]["path"]).convert("RGB")
        image.thumbnail((640, 480), Image.Resampling.LANCZOS)
        # Columns are weekday/weekend; rows are pagi/siang/sore/malam.
        column = DAYS.index(report["filename_metadata"]["day_type"].upper())
        row = PERIODS.index(report["filename_metadata"]["recording_period"].upper())
        canvas.paste(image, (column * 640, 65 + row * 520))
    canvas.save(overview)
    inventory = {"schema_version": "phase8_tgdi_actual_discovery_v1",
        "status": "ACTUAL_8_VIDEO_SOURCE_DECODE_COMPLETED", "claim_type": "EXPERIMENT_RESULT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": KAGGLE_ROOT, "listing_path": relative(listing_path, root),
        "listing_sha256": sha256(listing_path), "video_count": len(videos),
        "store_code": "TGDI", "store_name": None, "latitude": None, "longitude": None,
        "unprovided_store_metadata_policy": "Do not infer business name or location from burned-in video text",
        "filename_grammar_provenance": "docs/evidence/phase_8/authorization/dataset_clarification_20261015.json",
        "videos": videos,
        "geometry_overview": {"path": relative(overview, root), "sha256": sha256(overview)},
        "builder": {"path": relative(Path(__file__).resolve(), root), "sha256": sha256(Path(__file__))},
        "limitations": ["No detector/tracker/ReID inference or counting ran during source preparation.",
            "All eight geometries are source-bound proposals requiring per-video review; none is accepted.",
            "Approaching/away semantics are unknown for all eight until per-video direction review.",
            "Samples support bounded review only; camera shake and full-video geometry alignment have not been quantified.",
            "Frame index/FPS is an estimated timeline; source PTS and CFR/VFR status remain unvalidated."]}
    write_json(root / "docs/evidence/phase_8/inventory/TGDI_actual_discovery.json", inventory)
    validation = validate_outputs(root, args.source_root, inventory, reports)
    validation["inventory_path"] = "docs/evidence/phase_8/inventory/TGDI_actual_discovery.json"
    validation["inventory_sha256"] = sha256(root / validation["inventory_path"])
    write_json(root / "docs/evidence/phase_8/input_preparation/preparation_artifact_validation.json", validation)
    print(f"VALIDATION: {validation['checks_passed']}/{validation['checks_total']} preparation artifact checks", flush=True)
    print(f"COMPLETE: {len(videos)} actual source inspections; no accepted geometries or counts", flush=True)


if __name__ == "__main__":
    main()
