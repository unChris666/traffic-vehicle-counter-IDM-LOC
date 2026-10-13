"""Extract exact source pixels for bounded Option B temporal audit only.

No detector, tracker, encoder, resolver, or geometry state machine executes.
Geometry overlays are drawings of accepted G3, never generated crossings.
Full decoded frames remain in /tmp; GitHub contains bounded lossless crops.
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
GEOMETRY = "docs/evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json"
OUTPUT = "docs/evidence/phase_6/option_b_temporal_review"
CASES = [
    {"case_id": "motorcycle1772_rider1774", "track_ids": [1772, 1774], "frames": list(range(7712, 7723)), "partition": "HELD_OUT_TARGET", "full_overview": False},
    {"case_id": "car1323", "track_ids": [1323], "frames": [6256, 6257, 6258], "partition": "USER_REVIEW_CATEGORY_REFERENCE", "full_overview": True},
    {"case_id": "duplicate964_973", "track_ids": [964, 973], "frames": [5116, 5117, 5118, 5122, 5128, 5129, 5130], "partition": "DEVELOPMENT", "full_overview": False},
    {"case_id": "motorcycle923_rider912", "track_ids": [923, 912], "frames": [5011, 5017, 5018, 5020, 5028, 5029], "partition": "DEVELOPMENT", "full_overview": False},
    {"case_id": "motorcycle880_rider893", "track_ids": [880, 893], "frames": list(range(4975, 4980)), "partition": "DEVELOPMENT", "full_overview": False},
    {"case_id": "negative_motorcycles880_892", "track_ids": [880, 892], "frames": list(range(4975, 4980)), "partition": "DEVELOPMENT_NEGATIVE_ACTUAL_PIXELS", "full_overview": False},
    {"case_id": "late_motorcycle923_person912", "track_ids": [923, 912], "frames": [5116, 5128], "partition": "POST_LOCK_TEMPORAL_AUDIT_NOT_CALIBRATION", "full_overview": True},
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def dump(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def build(root, video, decoded_dir):
    if digest(video) != VIDEO_SHA:
        raise ValueError("Source video SHA mismatch")
    out = root / OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    decoded_dir.mkdir(parents=True, exist_ok=True)
    targets = {frame for case in CASES for frame in case["frames"]} | {5140}
    rows = {}
    with gzip.open(root / RECORDS, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["frame_index"] in targets:
                rows[row["frame_index"]] = row
    pixels = {}
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Cannot open video")
    frame_count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame.shape != (720, 1280, 3):
            raise ValueError("Unexpected native shape")
        if frame_count in targets:
            pixels[frame_count] = frame
            cv2.imwrite(str(decoded_dir / f"frame_{frame_count:09d}.png"), frame)
        frame_count += 1
    cap.release()
    if frame_count != 10282 or set(pixels) != targets or set(rows) != targets:
        raise ValueError("Decode/input frame coverage mismatch")
    alignment_path = root / "docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/samples/frame_000005140_raw.png"
    alignment = cv2.imread(str(alignment_path))
    if not np.array_equal(alignment, pixels[5140]):
        raise ValueError("Frame5140 differs from retained Phase2 source")
    geometry = json.loads((root / GEOMETRY).read_text())["rendered_native_pixels"]
    line = [tuple(geometry["line"][key]) for key in ["P1", "P2"]]
    frame_hashes = {f: hashlib.sha256(np.ascontiguousarray(p).tobytes()).hexdigest() for f, p in pixels.items()}
    colors = ["#00ffb0", "#ff70fa"]
    case_outputs = []
    checks = [{"name": "source_video_sha", "passed": True}, {"name": "decoded_frame_count10282", "passed": True}, {"name": "frame5140_matches_retained_png", "passed": True}]
    for case in CASES:
        focus_rows = {f: [obs for obs in rows[f]["emitted_tracks"] if obs["track_id"] in case["track_ids"]] for f in case["frames"]}
        bounds = [obs["raw_bbox"] for observations in focus_rows.values() for obs in observations]
        if not bounds:
            raise ValueError("Missing focus observations")
        crop = [max(0, math.floor(min(b[0] for b in bounds)) - 32), max(0, math.floor(min(b[1] for b in bounds)) - 32), min(1280, math.ceil(max(b[2] for b in bounds)) + 32), min(720, math.ceil(max(b[3] for b in bounds)) + 32)]
        # Include ALL raw car measurements at the left edge in case1323;
        # crop is a display decision, never an association threshold.
        if case["case_id"] == "car1323":
            crop[0] = 0
        views = {"crop": crop}
        if case["full_overview"]:
            views["overview"] = [0, 0, 1280, 720]
        if case["case_id"] == "car1323":
            views["left_edge_detail"] = [170, 400, 245, 490]
        artifact_map = {}
        view_maps = {}
        for view, rectangle in views.items():
            x1, y1, x2, y2 = rectangle
            width, height = x2 - x1, y2 - y1
            # One overview column; all crops use two columns. No resize.
            columns = 1 if view == "overview" else 2
            row_count = math.ceil(len(case["frames"]) / columns)
            sheets = {kind: Image.new("RGB", (columns * width, row_count * (height + 28)), "#eeeeee") for kind in ["raw", "overlay"]}
            tiles = []
            for index, frame in enumerate(case["frames"]):
                raw = Image.fromarray(cv2.cvtColor(pixels[frame][y1:y2, x1:x2], cv2.COLOR_BGR2RGB))
                overlay = raw.copy()
                draw = ImageDraw.Draw(overlay)
                for polykey, color in [("side_a_polygon", "#5b9bff"), ("side_b_polygon", "#ff9d50")]:
                    points = [(p[0] - x1, p[1] - y1) for p in geometry[polykey]]
                    draw.line(points + points[:1], fill=color, width=2)
                draw.line([(x - x1, y - y1) for x, y in line], fill="#fff200", width=3)
                aux = []
                for detection_index, detection in enumerate(rows[frame]["raw_detections"]):
                    bbox = detection["bbox_xyxy_pixels"]
                    focus_indices = {obs["original_detection_index"] for obs in focus_rows[frame]}
                    nearby = any(intersects(bbox, obs["raw_bbox"]) for obs in focus_rows[frame])
                    include = detection["class_name"] in {"car", "motorcycle", "truck", "bus", "person"} and detection_index not in focus_indices and (nearby or case["case_id"] == "car1323")
                    if not include:
                        continue
                    emitted_id = next((obs["track_id"] for obs in rows[frame]["emitted_tracks"] if obs["original_detection_index"] == detection_index), None)
                    draw.rectangle([bbox[0]-x1, bbox[1]-y1, bbox[2]-x1, bbox[3]-y1], outline="#ffa500", width=2)
                    draw.text((bbox[0]-x1+2, bbox[1]-y1+2), f"raw d{detection_index} {detection['class_name']} ID{emitted_id}", fill="#ffa500")
                    aux.append({"original_detection_index": detection_index, "emitted_track_id": emitted_id, "raw_detection": detection})
                for obs in focus_rows[frame]:
                    detection = rows[frame]["raw_detections"][obs["original_detection_index"]]
                    linked = detection["bbox_xyxy_pixels"] == obs["raw_bbox"] and detection["class_name"] == obs["class_name"]
                    checks.append({"name": f"source_link_{case['case_id']}_{frame}_{obs['track_id']}", "passed": linked})
                    if not linked:
                        raise ValueError("Raw measurement/source mismatch")
                    bbox = obs["raw_bbox"]
                    color = colors[case["track_ids"].index(obs["track_id"]) % len(colors)]
                    draw.rectangle([bbox[0]-x1,bbox[1]-y1,bbox[2]-x1,bbox[3]-y1], outline=color,width=3)
                    bc = ((bbox[0]+bbox[2])/2, bbox[3])
                    draw.ellipse([bc[0]-x1-4,bc[1]-y1-4,bc[0]-x1+4,bc[1]-y1+4],fill=color)
                    draw.text((bbox[0]-x1+2,bbox[1]-y1+16),f"ID{obs['track_id']} {obs['class_name']} d{obs['original_detection_index']}",fill=color)
                col, sheet_row = index % columns, index // columns
                origin = [col * width, sheet_row * (height + 28) + 28]
                for kind, tile in [("raw", raw), ("overlay", overlay)]:
                    sheets[kind].paste(tile, tuple(origin))
                    ImageDraw.Draw(sheets[kind]).text((origin[0]+4,origin[1]-22),f"native frame{frame} - {view} - {','.join('ID'+str(t) for t in case['track_ids'])}",fill="black")
                crop_pixel_hash = hashlib.sha256(np.ascontiguousarray(pixels[frame][y1:y2,x1:x2]).tobytes()).hexdigest()
                tiles.append({"frame_index": frame, "native_bgr_uint8_sha256": frame_hashes[frame], "crop_bgr_uint8_sha256": crop_pixel_hash, "native_crop_xyxy": rectangle, "sheet_image_origin_xy": origin, "emitted_measurements": focus_rows[frame], "auxiliary_raw_detections": aux})
            view_maps[view] = {"native_crop_xyxy": rectangle, "columns":columns, "tiles":tiles}
            for kind, sheet in sheets.items():
                name = f"{case['case_id']}_{view}_{kind}.png"
                path = out / name
                sheet.save(path)
                artifact_map[f"{view}_{kind}"] = {"path":f"{OUTPUT}/{name}","sha256":digest(path),"size_bytes":path.stat().st_size,"shape_width_height":list(sheet.size)}
                # Verify raw sheet crop pixels round-trip against source.
                if kind == "raw":
                    reopened = np.array(Image.open(path).convert("RGB"))
                    for tile in tiles:
                        ox,oy = tile["sheet_image_origin_xy"]
                        actual = reopened[oy:oy+height,ox:ox+width]
                        expected = cv2.cvtColor(pixels[tile["frame_index"]][y1:y2,x1:x2],cv2.COLOR_BGR2RGB)
                        checks.append({"name":f"lossless_crop_{case['case_id']}_{view}_{tile['frame_index']}","passed":np.array_equal(actual,expected)})
        case_outputs.append({**case,"coordinate_mapping":"sheet_x=native_x-crop_x1+sheet_image_origin_x; sheet_y=native_y-crop_y1+sheet_image_origin_y; no resize", "artifacts":artifact_map,"views":view_maps})
    report = {"claim_type":"EXECUTED_PIXEL_EXTRACTION_NOT_RESOLVER_RESULT", "source_video_sha256":VIDEO_SHA,"source_video_size_bytes":video.stat().st_size,"records_path":RECORDS,"records_sha256":digest(root/RECORDS),"geometry_path":GEOMETRY,"geometry_sha256":digest(root/GEOMETRY),"method_path":"docs/evidence/phase_6/verification/build_option_b_temporal_review.py","method_sha256":digest(Path(__file__)),"decoder":"OpenCV sequential VideoCapture","opencv_version":cv2.__version__,"decoded_frame_count":frame_count,"native_dimensions":[1280,720],"unique_review_frames":len(targets-{5140}),"alignment_frame5140_matches_retained_phase2":True,"pixel_hash_encoding":"SHA256 contiguous native/crop uint8 BGR bytes","source_pts_authoritative":False,"no_model_tracker_reid_resolver_or_geometry_state_machine_rerun":True,"display_margin_px":32,"display_margin_is_not_association_threshold":True,"cases":case_outputs}
    dump(out/"sample_index.json",report)
    dump(out/"artifact_validation.json",{"claim_type":"EXECUTED_HASH_AND_PIXEL_SOURCE_LINK_CHECKS_NOT_VISUAL_TRUTH", "checks":checks,"passed":sum(c["passed"] for c in checks),"failed":sum(not c["passed"] for c in checks),"total":len(checks)})
    entries = [{"path":str(p.relative_to(root)),"sha256":digest(p),"size_bytes":p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"]
    dump(out/"manifest.json",{"source_video_sha256":VIDEO_SHA,"method_sha256":digest(Path(__file__)),"entries":entries,"total_bytes":sum(e["size_bytes"] for e in entries),"original_video_or_standalone_decoded_frame_files_retained":False,"native_full_frame_tiles_present_in_car1323_overview_contacts":True})
    print(json.dumps({"case_count":len(case_outputs),"review_frames":len(targets-{5140}),"validation_passed":sum(c["passed"] for c in checks),"validation_failed":sum(not c["passed"] for c in checks),"artifact_bytes":sum(e["size_bytes"] for e in entries)},indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",required=True,type=Path)
    parser.add_argument("--video",required=True,type=Path)
    parser.add_argument("--decoded-dir",default="/tmp/option_b_native_review_frames",type=Path)
    arguments=parser.parse_args()
    build(arguments.root,arguments.video,arguments.decoded_dir)
