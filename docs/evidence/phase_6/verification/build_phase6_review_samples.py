"""Extract bounded native pixel evidence; no model/track/geometry rerun.

Run with a Python environment containing OpenCV, numpy and Pillow. Full video
and decoded full frames remain outside the repository. A display crop margin
is an annotation choice, never a counting/association threshold.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


VIDEO_SHA = "606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c"
RECORDS = "docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz"
DIAGNOSTICS = "docs/evidence/phase_5/20261011T161440_100155Z_2e39a11c/b0_c1_diagnostics.jsonl.gz"
GEOMETRY = "docs/evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json"
OUTPUT = "docs/evidence/phase_6/review_samples/TOR3-PAGI"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def build(root, video, inventory):
    if digest(video) != VIDEO_SHA:
        raise ValueError("Source video SHA differs from the retained TOR3-PAGI input")
    inv = json.loads(inventory.read_text())
    chosen = [c for c in inv["candidates"] if c["strict_stable_proposal_mapped_class"] and not c["raw_vehicle_overlaps"]]
    extra_ids = {973, 967, 1774, 893, 912, 1, 1323}
    chosen += [c for c in inv["candidates"] if c["track_id"] in extra_ids]
    cases = {}
    for c in chosen:
        case = cases.setdefault(c["track_id"], {"track_id": c["track_id"], "candidate_inventory_indices": [], "frames": set(), "source_diagnostic_selectors": []})
        case["candidate_inventory_indices"].append(c["candidate_inventory_index"])
        case["frames"].update([c["origin_frame"], c["crossing_frame_start"], c["crossing_frame_end"], c["confirmation_frame"]])
        case["source_diagnostic_selectors"].append({k: c[k] for k in ["track_id", "origin_frame", "crossing_frame_start", "crossing_frame_end", "confirmation_frame", "direction"]})
        # One earlier measured/pixel frame adds context without pretending it
        # is necessary evidence or changing the origin/crossing diagnostics.
        if len(case["frames"]) < 4:
            case["frames"].add(max(0, c["crossing_frame_start"] - 1))
        # Inspect actual overlap evidence before claiming clearance for a car
        # candidate. These indices come from positive-area source screening,
        # without an invented IoU threshold. Other cases retain bounded unit
        # snapshots and receive no automatic clearance from this method.
        if c["track_id"] in {1, 1323} and c["raw_vehicle_overlaps"]:
            overlap_rows = c["raw_vehicle_overlaps"]
            case["frames"].update([min(o["frame_index"] for o in overlap_rows), max(o["frame_index"] for o in overlap_rows), max(overlap_rows,key=lambda o:o["positive_intersection_area_px2"])["frame_index"]])
    for case in cases.values():
        case["frames"] = sorted(case["frames"])
    targets = {f for c in cases.values() for f in c["frames"]} | {5140}
    source_rows = {}
    with gzip.open(root / RECORDS, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["frame_index"] in targets:
                source_rows[row["frame_index"]] = row
    pixels = {}
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Source video cannot be opened")
    frame_count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame.shape != (720, 1280, 3):
            raise ValueError("Unexpected native dimensions")
        if frame_count in targets:
            pixels[frame_count] = frame
        frame_count += 1
    cap.release()
    if frame_count != 10282 or set(pixels) != targets:
        raise ValueError("Unexpected decoded frame count or missing target pixels")
    retained = cv2.imread(str(root / "docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/samples/frame_000005140_raw.png"))
    if retained is None or not np.array_equal(retained, pixels[5140]):
        raise ValueError("Frame5140 differs from the retained exact native PNG")
    out = root / OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    frame_hashes = {f: hashlib.sha256(np.ascontiguousarray(pixels[f]).tobytes()).hexdigest() for f in targets}
    # Accepted coordinates: explicit 960x540 -> native1280x720 mapping.
    p1 = (4.5 * 1280 / 960, 516.5 * 720 / 540)
    p2 = (936.4 * 1280 / 960, 305.4 * 720 / 540)
    prepared = []
    for tid, case in sorted(cases.items()):
        bounds = []
        observations = {}
        for f in case["frames"]:
            row = source_rows[f]
            focus = next((o for o in row["emitted_tracks"] if o["track_id"] == tid), None)
            observations[f] = focus
            if focus:
                bounds.append(focus["raw_bbox"])
                # Include visibly associated/occluding people in the display
                # crop. This is not an identity-association decision.
                bounds.extend(d["bbox_xyxy_pixels"] for d in row["raw_detections"] if d["class_name"] == "person" and overlap(focus["raw_bbox"], d["bbox_xyxy_pixels"]))
        if not bounds:
            raise ValueError(f"Missing emitted source measurements for track{tid}")
        crop = [max(0, math.floor(min(b[0] for b in bounds)) - 24), max(0, math.floor(min(b[1] for b in bounds)) - 24), min(1280, math.ceil(max(b[2] for b in bounds)) + 24), min(720, math.ceil(max(b[3] for b in bounds)) + 24)]
        x1, y1, x2, y2 = crop
        width, height = x2 - x1, y2 - y1
        columns = 2
        rows = math.ceil(len(case["frames"]) / columns)
        sheets = {kind: Image.new("RGB", (columns * width, rows * (height + 26)), "#eeeeee") for kind in ["raw", "overlay"]}
        tiles = []
        for i, f in enumerate(case["frames"]):
            image = Image.fromarray(cv2.cvtColor(pixels[f][y1:y2, x1:x2], cv2.COLOR_BGR2RGB))
            annotate = image.copy()
            draw = ImageDraw.Draw(annotate)
            draw.line([(p1[0]-x1, p1[1]-y1), (p2[0]-x1, p2[1]-y1)], fill="#fff200", width=2)
            row = source_rows[f]
            focus = observations[f]
            links = []
            if focus:
                b = focus["raw_bbox"]
                for j, d in enumerate(row["raw_detections"]):
                    if j == focus["original_detection_index"] or d["class_name"] not in {"car", "motorcycle", "truck", "bus"} or not overlap(b, d["bbox_xyxy_pixels"]):
                        continue
                    bb = d["bbox_xyxy_pixels"]
                    other_id = next((o["track_id"] for o in row["emitted_tracks"] if o["original_detection_index"] == j), None)
                    draw.rectangle([bb[0]-x1,bb[1]-y1,bb[2]-x1,bb[3]-y1], outline="#ff7f00", width=2)
                    draw.text((bb[0]-x1+2,bb[1]-y1+2), f"raw {d['class_name']} ID{other_id} d{j}", fill="#ff7f00")
                    links.append({"raw_detection_index": j, "other_emitted_track_id": other_id, "raw_class_name": d["class_name"], "raw_bbox": bb})
                draw.rectangle([b[0]-x1,b[1]-y1,b[2]-x1,b[3]-y1], outline="#00ffb0", width=2)
                bc = ((b[0]+b[2])/2,b[3])
                draw.ellipse([bc[0]-x1-4,bc[1]-y1-4,bc[0]-x1+4,bc[1]-y1+4], fill="#00ffb0")
                draw.text((b[0]-x1+2,b[1]-y1+2), f"ID{tid} {focus['class_name']} d{focus['original_detection_index']}", fill="#00ffb0")
            col, rr = i % columns, i // columns
            origin = (col * width, rr * (height + 26))
            for kind, img in [("raw", image), ("overlay", annotate)]:
                sheets[kind].paste(img, (origin[0], origin[1]+26))
                ImageDraw.Draw(sheets[kind]).text((origin[0]+4, origin[1]+5), f"Native frame{f} ID{tid} ({'emitted' if focus else 'not emitted'})", fill="black")
            tiles.append({"frame_index": f, "native_crop_xyxy": crop, "contact_sheet_image_origin_xy": [origin[0], origin[1]+26], "native_bgr_uint8_sha256": frame_hashes[f], "focus_measurement": focus, "auxiliary_competitor_detections": links})
        artifacts = {}
        for kind, sheet in sheets.items():
            name = f"id{tid}_{kind}_contact.png"
            sheet.save(out/name)
            artifacts[kind] = {"path": f"{OUTPUT}/{name}", "sha256": digest(out/name), "size_bytes": (out/name).stat().st_size, "shape_width_height": list(sheet.size)}
        prepared.append({**case, "scope": "only listed frames visually available; full support windows scanned numerically, not all visually reviewed", "crop_xyxy": crop, "coordinate_mapping": "tile_x=native_x-crop_x1+sheet_image_origin_x; tile_y=native_y-crop_y1+sheet_image_origin_y; no resize", "artifacts": artifacts, "tiles": tiles})
    report = {"claim_type": "EXPERIMENT_RESULT_PIXEL_EXTRACTION_NOT_VISUAL_VERDICT", "source_video_sha256": VIDEO_SHA, "source_video_size_bytes": video.stat().st_size, "records_sha256": digest(root/RECORDS), "diagnostics_sha256": digest(root/DIAGNOSTICS), "geometry_sha256": digest(root/GEOMETRY), "method_sha256": digest(Path(__file__)), "inventory_sha256": digest(inventory), "python_opencv_version": cv2.__version__, "decoded_frame_count": frame_count, "native_dimensions": [1280,720], "target_frames_excluding_alignment_count": len(targets-{5140}), "alignment_frame5140_equals_retained_phase2_png": True, "pixel_hash_encoding": "SHA256 contiguous native uint8 BGR bytes", "reviewer": None, "decoder_indices_not_authoritative_pts": True, "no_models_or_geometry_replayed": True, "display_margin_px":24, "display_margin_is_not_model_or_association_threshold": True, "cases": prepared}
    (out/"sample_index.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"case_count": len(prepared), "target_frames":len(targets-{5140}), "decoded_frame_count":frame_count, "sample_index":str(out/"sample_index.json")},indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    build(args.root,args.video,args.inventory)
