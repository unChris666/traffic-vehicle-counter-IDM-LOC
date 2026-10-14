#!/usr/bin/env python3
"""Build source-bound night geometry PROPOSAL and raw temporal sample evidence.

No inference, enhancement, stabilization, track IDs or count events are created.
Run with the repository inspection environment (OpenCV + Pillow required).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

EXPECTED_SHA256 = "a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082"
EXPECTED_WIDTH, EXPECTED_HEIGHT, EXPECTED_FRAMES = 1280, 720, 9590
FPS_ESTIMATE = 29.419969502218617
SEGMENTS = [
    ("dev_beginning", "development", 0, 239, 0),
    ("dev_quarter", "development", 2277, 2516, 2397),
    ("holdout_middle", "holdout", 4674, 4913, 4794),
    ("dev_three_quarters", "development", 7072, 7311, 7192),
    ("holdout_end", "holdout", 9350, 9589, 9589),
]
NATIVE_SAMPLES = {
    "dev_beginning": [0, 7, 14, 29, 239],
    "dev_quarter": [2277, 2337, 2397, 2457, 2516],
    "holdout_middle": [4674, 4734, 4794, 4854, 4913],
    "dev_three_quarters": [7072, 7132, 7192, 7252, 7311],
    "holdout_end": [9350, 9410, 9470, 9530, 9589],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)


def artifact(path: Path, repo: Path, **extra: object) -> dict:
    return {"path": str(path.relative_to(repo)), "sha256": sha256(path), **extra}


def geometry_preview(raw: Image.Image, geometry: dict, frame_index: int) -> Image.Image:
    width, height = raw.size
    canvas = Image.new("RGB", (width, height + 180), (16, 20, 27))
    canvas.paste(raw, (0, 70))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    native = geometry["rendered_native_pixels"]
    for name, colour in (("side_a_polygon", (35, 155, 255)),
                         ("side_b_polygon", (255, 151, 44))):
        points = [tuple(point) for point in native[name]]
        draw.polygon(points, fill=colour + (24,))
        draw.line(points + [points[0]], fill=colour + (255,), width=3)
    p1, p2 = tuple(native["line"]["P1"]), tuple(native["line"]["P2"])
    draw.line([p1, p2], fill=(255, 239, 42, 255), width=4)
    for point in (p1, p2):
        x, y = point
        draw.ellipse((x-7, y-7, x+7, y+7), fill=(255, 239, 42, 255))
    composed = Image.alpha_composite(raw.convert("RGBA"), overlay).convert("RGB")
    canvas.paste(composed, (0, 70))
    draw = ImageDraw.Draw(canvas)
    draw.text((18, 12), "TOR3-MALAM / N1: relative G3 transfer / PROPOSAL", font=font(27), fill="white")
    draw.text((18, 43), f"Raw native {width} x {height}; frame {frame_index}; no crop; geometry/directions need review", font=font(16), fill=(210, 215, 220))

    def tag(x: float, y: float, text: str, colour: tuple) -> None:
        box = draw.textbbox((x, y), text, font=font(23))
        draw.rectangle((box[0]-7, box[1]-5, box[2]+7, box[3]+5), fill=(10, 12, 15))
        draw.text((x, y), text, font=font(23), fill=colour)

    tag(390, 405, "A / far-region proposal", (90, 185, 255))
    tag(470, 70+640, "B / near-region proposal", (255, 170, 75))
    tag(p1[0]+20, 70+p1[1]-46, "P1", (255, 239, 42))
    tag(p2[0]-75, 70+p2[1]-40, "P2", (255, 239, 42))
    bottom = height+86
    draw.text((18, bottom), "P1=(6.0,688.7)  P2=(1248.5,407.2) | B cap x=1166.7 | native pixel coordinates", font=font(18), fill="white")
    draw.text((18, bottom+29), "Proposed A_TO_B: approaching; B_TO_A: away. These night semantics are NOT approved.", font=font(18), fill=(255, 239, 155))
    draw.text((18, bottom+58), "BC uses raw measured vehicle box after tracking. No model boxes or crossing evidence are shown here.", font=font(17), fill=(210, 215, 220))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--runtime-clips", type=Path, default=Path("/tmp/traffic-phase7-source/raw_sampling_clips"))
    args = parser.parse_args()
    repo, video = args.repo.resolve(), args.video.resolve()
    if sha256(video) != EXPECTED_SHA256:
        raise ValueError("Input bytes differ from retained TOR3-MALAM evidence")
    g3_path = repo / "docs/evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json"
    g3 = json.loads(g3_path.read_text())
    sampling = repo / "docs/evidence/phase_7/sampling"
    proposals = repo / "docs/evidence/phase_7/geometry_proposals"
    frames_path = sampling / "frames"
    for directory in (sampling, proposals, frames_path, args.runtime_clips):
        directory.mkdir(parents=True, exist_ok=True)
    source = {
        "filename": video.name, "sha256": EXPECTED_SHA256,
        "size_bytes": video.stat().st_size, "native_width": EXPECTED_WIDTH,
        "native_height": EXPECTED_HEIGHT, "decoded_frame_count": EXPECTED_FRAMES,
        "average_fps": FPS_ESTIMATE,
        "average_fps_provenance": "retained Phase1 ffprobe; not authoritative source PTS",
        "kaggle_path": "/kaggle/input/datasets/chrisbiran/traffic-tracker-videos/TOR3-MALAM.mp4",
    }
    geometry = {
        "draft_id": "TOR3-MALAM-N1-v1", "status": "PROPOSAL_NOT_HUMAN_APPROVED",
        "claim_type": "PROPOSAL", "source_video": source,
        "template_source": artifact(g3_path, repo),
        "transfer_policy": "Full-frame u=x/960,v=y/540 -> x=u*1280,y=v*720. No crop, rotation or inferred transform.",
        "template_reference": g3["template_reference"],
        "normalization_convention": g3["normalization_convention"],
        "normalized": g3["normalized"],
        "line_endpoints_reference": g3["line_endpoints_reference"],
        "side_a_polygon_reference": g3["side_a_polygon_reference"],
        "side_b_polygon_reference": g3["side_b_polygon_reference"],
        "rendered_native_pixels": g3["rendered_native_pixels"],
        "line_polygon_endpoint_difference_reference": g3["line_polygon_endpoint_difference_reference"],
        "selected_anchor": "bottom_center",
        "anchor_status": "USER_ACCEPTED_MEASUREMENT_CONTROL_NIGHT_SUITABILITY_REQUIRES_REVIEW",
        "anchor_source": "raw detector-linked measured vehicle bbox after emitted-track association; never rider BC/prediction",
        "proposed_direction_metadata": {"A_TO_B": "approaching camera", "B_TO_A": "moving away from camera", "scope": "TOR3-MALAM", "claim_type": "PROPOSAL_NOT_CONFIRMED"},
        "confirmed_direction_metadata": None,
        "geometry_contract_accepted": False,
        "counting_execution_allowed": False,
        "thresholds": {"neutral_band_px": 0.0, "confirmation_observations": 1, "status": "FROZEN_B0_C1_EXPERIMENT_CONTROL_NOT_PRODUCTION_DEFAULT"},
        "approval_feedback": None,
        "review_questions": ["Does N1 cross the intended vehicle corridor with observable before/after regions?", "Are A/B polygons and B right cap appropriate in the night scene?", "Confirm or revise approaching/away semantics for this video.", "Should embedded text, glare, cropped vehicles or unlit road require a geometry revision?"],
        "source_frame": {"frame_index": 7192, "width": EXPECTED_WIDTH, "height": EXPECTED_HEIGHT, "coordinate_space": "native full-frame pixel coordinates; origin upper-left; x right; y down"},
    }
    geometry_path = proposals / "TOR3-MALAM-N1.json"
    write_json(geometry_path, geometry)
    plan = {
        "schema_version": "phase7_sampling_plan_v1",
        "status": "PROPOSAL_NOT_HUMAN_APPROVED",
        "source_video": source,
        "input_identity": {"video_sha256": EXPECTED_SHA256, "width": EXPECTED_WIDTH, "height": EXPECTED_HEIGHT, "decoded_frame_count": EXPECTED_FRAMES},
        "frame_index_convention": "zero based; start_frame and end_frame inclusive; decode native full-frame images",
        "development": {"segments": [], "sample_frame_indices": []},
        "holdout": {"segments": [], "sample_frame_indices": []},
        "sampling_budget": {"frames_per_continuous_segment": 240, "claim_type": "ENGINEERING_EXPERIMENT_BUDGET_NOT_ELIGIBILITY_THRESHOLD"},
        "split_policy": "Three nonoverlapping development windows; two separately reserved holdout windows. No candidate selection/tuning on holdout model/enhancement outcomes.",
        "holdout_blindness": "NOT_BLIND: anchor pixels and short bursts were already inspected in Phase1; current raw temporal preview is sample planning only, not enhancement/model evaluation.",
        "geometry_gate": {"require_geometry_approval": True, "proposal_path": str(geometry_path.relative_to(repo)), "proposal_sha256": sha256(geometry_path), "tracking_counting_stage": "WAIT_FOR_NIGHT_GEOMETRY_REVIEW", "photometric_detection_screen_stage": "DEVELOPMENT_ONLY_NO_COUNTING"},
        "limitations": ["Window lengths are experiment budgets; no complete physical passage is asserted by these ranges.", "Beginning is left-censored and end is right-censored by file boundaries.", "A vehicle identity across split boundaries cannot be established without temporal/manual evidence; do not label windows ground truth.", "Index/FPS timing is estimated; authoritative source PTS and variable-frame-rate status remain unknown.", "Sparse development samples support photometric/detection screening only; tracking/counting requires actual continuous frames plus approved geometry."],
    }
    sample_set = set()
    display_by_segment = {}
    for segment_id, split, start, end, anchor in SEGMENTS:
        indices = sorted(set(round(start + (end-start)*i/23) for i in range(24)) | {anchor} | set(NATIVE_SAMPLES[segment_id]))
        display_by_segment[segment_id] = indices
        sample_set.update(indices)
        sample_set.update(NATIVE_SAMPLES[segment_id])
        context_limits = []
        if start == 0:
            context_limits.append("LEFT_CENSORED_AT_VIDEO_START: earlier vehicle history unavailable")
        if end == EXPECTED_FRAMES-1:
            context_limits.append("RIGHT_CENSORED_AT_VIDEO_END: later vehicle history unavailable")
        plan[split]["segments"].append({
            "segment_id": segment_id, "start_frame": start, "end_frame": end,
            "anchor_frame": anchor, "frame_count": end-start+1,
            "reason": "Around historical Phase1 anchor; raw temporal context inspected, not a model performance selection",
            "context_limits": context_limits,
        })
        plan[split]["sample_frame_indices"].extend(NATIVE_SAMPLES[segment_id])
    native_samples = {index for values in NATIVE_SAMPLES.values() for index in values}
    thumbs, inventory, runtime_clips = {}, [], []
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open the actual night source")
    capture_props = {"width": capture.get(cv2.CAP_PROP_FRAME_WIDTH), "height": capture.get(cv2.CAP_PROP_FRAME_HEIGHT), "frame_count": capture.get(cv2.CAP_PROP_FRAME_COUNT), "fps": capture.get(cv2.CAP_PROP_FPS)}
    writers = {}
    for segment_id, _, start, end, _ in SEGMENTS:
        path = args.runtime_clips / f"{segment_id}_raw_640x360.mp4"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS_ESTIMATE, (640, 360))
        if not writer.isOpened():
            raise RuntimeError("Could not open runtime-only temporal clip writer")
        writers[segment_id] = writer
        runtime_clips.append({"segment_id": segment_id, "runtime_path": str(path), "retained_in_git": False, "frame_start": start, "frame_end": end, "frame_count": end-start+1, "purpose": "raw temporal review aid only; resized and reencoded, not model input", "timing": "CFR playback from average FPS estimate, source PTS not preserved"})
    decoded = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        index = decoded
        decoded += 1
        if frame.shape[:2] != (EXPECTED_HEIGHT, EXPECTED_WIDTH):
            raise ValueError(f"Unexpected native dimensions at frame {index}")
        rgb = None
        if index in sample_set:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            thumb = image.resize((640, 360), Image.Resampling.LANCZOS)
            thumbs[index] = thumb
            entry = {"frame_index": index, "native_pixel_sha256_rgb": hashlib.sha256(rgb.tobytes()).hexdigest(), "width": EXPECTED_WIDTH, "height": EXPECTED_HEIGHT, "backend_position_msec": capture.get(cv2.CAP_PROP_POS_MSEC), "index_fps_estimate_seconds": index/FPS_ESTIMATE}
            if index in native_samples:
                path = frames_path / f"frame_{index:09d}.png"
                image.save(path)
                entry["retained_native_png"] = artifact(path, repo, lossless=True)
            inventory.append(entry)
        for segment_id, _, start, end, _ in SEGMENTS:
            if start <= index <= end:
                writers[segment_id].write(cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA))
    capture.release()
    for writer in writers.values():
        writer.release()
    if decoded != EXPECTED_FRAMES:
        raise ValueError(f"Decoded {decoded} != retained expected {EXPECTED_FRAMES}; no automatic EOF/corruption diagnosis")
    for clip in runtime_clips:
        clip["sha256"] = sha256(Path(clip["runtime_path"]))
    sheets = []
    for segment_id, split, start, end, anchor in SEGMENTS:
        indices = display_by_segment[segment_id]
        rows = (len(indices)+3)//4
        sheet = Image.new("RGB", (2560, 65+rows*397), (15, 18, 23))
        draw = ImageDraw.Draw(sheet)
        draw.text((20, 14), f"RAW TOR3-MALAM | {segment_id} | {split.upper()} | {start}..{end} inclusive | sampled temporal display", font=font(25), fill="white")
        for pos, index in enumerate(indices):
            x, y = (pos%4)*640, 65+(pos//4)*397
            sheet.paste(thumbs[index], (x, y))
            draw.text((x+10, y+363), f"frame {index} | ~{index/FPS_ESTIMATE:.3f}s (index / avgFPS)", font=font(19), fill=(215, 220, 225))
        path = sampling / f"{segment_id}_raw_temporal.png"
        sheet.save(path)
        sheets.append(artifact(path, repo, frame_indices=indices, source_space="full native frame ->640x360 display thumbnail", enhancement="none"))
    source_frame_path = frames_path / "frame_000007192.png"
    geometry["source_frame"].update(artifact(source_frame_path, repo, lossless=True))
    write_json(geometry_path, geometry)
    plan["geometry_gate"]["proposal_sha256"] = sha256(geometry_path)
    plan_path = sampling / "TOR3-MALAM_sampling_plan_v1.json"
    write_json(plan_path, plan)
    preview = geometry_preview(Image.open(source_frame_path).convert("RGB"), geometry, 7192)
    preview_path = proposals / "TOR3-MALAM-N1.png"
    preview.save(preview_path)
    comparison = Image.new("RGB", (1280, 150+3*720), (15, 18, 23))
    draw = ImageDraw.Draw(comparison)
    draw.text((20, 15), "N1 transferred G3 | raw temporal alignment review | NOT APPROVED", font=font(25), fill="white")
    for row, index in enumerate((0, 2397, 7192)):
        raw = Image.open(frames_path / f"frame_{index:09d}.png").convert("RGB")
        image = geometry_preview(raw, geometry, index)
        comparison.paste(image.crop((0, 70, 1280, 790)), (0, 60+row*750))
        draw.text((20, 62+row*750), f"frame {index}: full native1280x720; transferred polygon/line preview", font=font(18), fill="white", stroke_width=2, stroke_fill="black")
    alignment_path = proposals / "TOR3-MALAM-N1_alignment.png"
    comparison.save(alignment_path)
    result = {
        "status": "ACTUAL_RAW_DECODE_AND_PROPOSAL_RENDER_EXECUTED_NO_MODELS",
        "source_video": source, "source_local_path": str(video),
        "environment": {"python": platform.python_version(), "opencv": cv2.__version__, "pillow": Image.__version__},
        "capture_properties": capture_props, "actual_decoded_frames": decoded,
        "decode_integrity_limit": "Exact emitted count matches prior decoder evidence; read failure alone cannot establish source integrity or absence of unsupported/corrupt frames",
        "native_sample_inventory": inventory, "temporal_sheets": sheets,
        "runtime_only_clips": runtime_clips,
        "geometry_proposal": artifact(geometry_path, repo),
        "geometry_preview": artifact(preview_path, repo),
        "geometry_alignment_sheet": artifact(alignment_path, repo),
        "sampling_plan": artifact(plan_path, repo),
        "builder": artifact(Path(__file__).resolve(), repo),
        "no_enhancement_or_model_execution": True,
    }
    write_json(sampling / "build_manifest.json", result)
    print(json.dumps({"decoded_frames": decoded, "retained_native_frames": len(native_samples), "sampled_temporal_frames": len(inventory), "geometry_preview": str(preview_path.relative_to(repo)), "sampling_plan": str(plan_path.relative_to(repo))}))


if __name__ == "__main__":
    main()
