"""Decode real video once; retain bounded raw/overlay crops for Phase 5 audit.

This method runs no detector, tracker, encoder, preprocessing, or traffic counter.
OpenCV drawing is a deterministic audit visualization; raw contact sheets retain
unmodified, unscaled crop pixels. Full video and all decoded source frames stay
outside Git. Geometry measurements come only from cached linked raw_bbox.
"""
import argparse
import gzip
import hashlib
import json
import math
import pathlib
import platform
import sys

import cv2
import numpy as np


CASES = [
    {"name": "id893_return", "ids": [893], "range": [4975, 4984],
     "retain": [4977, 4978, 4979, 4980]},
    {"name": "id912_return", "ids": [912], "range": [5016, 5026],
     "retain": [5019, 5020, 5021, 5022]},
    {"name": "id1217_class_gap", "ids": [1217], "range": [6015, 6022],
     "retain": [6015, 6017, 6018, 6019]},
    {"name": "id1712_five_missing", "ids": [1712], "range": [7555, 7570],
     "retain": [7559, 7560, 7564, 7565]},
    {"name": "red_scooter_components", "ids": [964, 973, 967],
     "range": [5125, 5132], "retain": [5128, 5129, 5130, 5132]},
]


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pixel_sha(array):
    """SHA of contiguous BGR uint8 bytes; shape/type recorded separately."""
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sheet(frames, case, rows, crop, line, polygons, annotate):
    x1, y1, x2, y2 = crop
    width, height = x2 - x1, y2 - y1
    header = 72
    canvas = np.full((2 * (height + header), 2 * width, 3), 24, np.uint8)
    mapping = []
    colors = {893: (200, 20, 250), 912: (200, 20, 250),
              1217: (200, 20, 250), 1712: (200, 20, 250),
              964: (200, 20, 250), 973: (0, 255, 0), 967: (255, 160, 50)}
    for index, frame_index in enumerate(case["retain"]):
        image = frames[frame_index][y1:y2, x1:x2].copy()
        observations = [o for o in rows[frame_index]["emitted_tracks"]
                        if o["track_id"] in case["ids"]]
        if annotate:
            for name, polygon in polygons.items():
                points = np.array([[round(x - x1), round(y - y1)]
                                   for x, y in polygon], np.int32)
                cv2.polylines(image, [points], True,
                              (255, 160, 40) if name == "A" else (20, 145, 245), 1)
            points = [(round(p[0] - x1), round(p[1] - y1)) for p in line]
            cv2.line(image, points[0], points[1], (0, 245, 255), 2)
            for observation in observations:
                bbox = observation["raw_bbox"]
                color = colors[observation["track_id"]]
                a, b = ((round(bbox[0] - x1), round(bbox[1] - y1)),
                        (round(bbox[2] - x1), round(bbox[3] - y1)))
                cv2.rectangle(image, a, b, color, 2)
                bc = (round((bbox[0] + bbox[2]) / 2 - x1), round(bbox[3] - y1))
                cv2.circle(image, bc, 4, color, -1)
        column, row = index % 2, index // 2
        left, top = column * width, row * (height + header)
        canvas[top + header:top + header + height, left:left + width] = image
        label = f"frame {frame_index} | {'RAW + geometry/raw_bbox BC' if annotate else 'RAW pixels (no overlay)'}"
        cv2.putText(canvas, label, (left + 8, top + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, .43, (245, 245, 245), 1, cv2.LINE_AA)
        summaries = [f"ID{o['track_id']}:{o['class_name']}" for o in observations]
        cv2.putText(canvas, " | ".join(summaries) if summaries else "target ID: not emitted",
                    (left + 8, top + 41), cv2.FONT_HERSHEY_SIMPLEX,
                    .42, (245, 245, 245), 1, cv2.LINE_AA)
        cv2.putText(canvas, f"native crop x[{x1},{x2}) y[{y1},{y2}); no resize",
                    (left + 8, top + 61), cv2.FONT_HERSHEY_SIMPLEX,
                    .38, (215, 215, 215), 1, cv2.LINE_AA)
        mapping.append({"frame_index": frame_index,
                        "tile_image_top_left": [left, top + header],
                        "tile_image_size": [width, height],
                        "native_crop_xyxy": crop,
                        "raw_crop_bgr_uint8_sha256": pixel_sha(frames[frame_index][y1:y2, x1:x2]),
                        "overlay": annotate})
    return canvas, mapping


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/workspace/traffic-vehicle-counter-IDM-LOC")
    parser.add_argument("--video", default="/tmp/traffic-phase5-source/TOR3-PAGI.mp4")
    parser.add_argument("--output", default="docs/evidence/phase_5/20261012_temporal_review")
    parser.add_argument("--scratch", default="/tmp/traffic-phase5-targeted-pixels")
    args = parser.parse_args()
    root, video = pathlib.Path(args.root), pathlib.Path(args.video)
    output = pathlib.Path(args.output)
    if not output.is_absolute():
        output = root / output
    output.mkdir(parents=True, exist_ok=True)
    scratch = pathlib.Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    expected_video_sha = "606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c"
    video_sha = file_sha(video)
    if video_sha != expected_video_sha:
        raise ValueError("source video SHA does not match retained Phase2 input")
    records_path = root / "docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz"
    geometry_path = root / "docs/evidence/phase_5/review_drafts/G3/candidate_geometry.json"
    source_path = root / "docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/samples/frame_000005140_raw.png"
    geometry = json.loads(geometry_path.read_text())["rendered_native_pixels"]
    line = [geometry["line"]["P1"], geometry["line"]["P2"]]
    polygons = {"A": geometry["side_a_polygon"], "B": geometry["side_b_polygon"]}
    target_indices = {i for c in CASES for i in range(c["range"][0], c["range"][1] + 1)}
    target_indices.add(5140)
    rows = {}
    expected_index = 0
    frame_sizes = set()
    record_video_shas = set()
    with gzip.open(records_path, "rt") as stream:
        for text in stream:
            record = json.loads(text)
            if record["frame_index"] != expected_index:
                raise ValueError("retained cache is not contiguous from frame zero")
            frame_sizes.add((record["width"], record["height"]))
            record_video_shas.add(record["video_sha256"])
            if expected_index in target_indices:
                rows[expected_index] = record
                for o in record["emitted_tracks"]:
                    if o["measurement_provenance"] != "retained_phase_2_detection":
                        raise ValueError("unexpected measurement provenance")
                    if o["frame_index"] != record["frame_index"]:
                        raise ValueError("observation frame mismatch")
                    source = record["raw_detections"][o["original_detection_index"]]
                    if source["bbox_xyxy_pixels"] != o["raw_bbox"]:
                        raise ValueError("raw bbox does not match its linked detection")
            expected_index += 1
    if record_video_shas != {expected_video_sha} or frame_sizes != {(1280, 720)}:
        raise ValueError("cache video/native geometry provenance mismatch")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError("OpenCV cannot open verified source video")
    decoder_metadata = {"backend": cap.getBackendName(),
                        "reported_width": cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                        "reported_height": cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                        "reported_fps": cap.get(cv2.CAP_PROP_FPS),
                        "reported_frame_count": cap.get(cv2.CAP_PROP_FRAME_COUNT)}
    frames, decoded_sizes = {}, set()
    decoded_count = 0
    while True:
        success, frame = cap.read()
        if not success:
            break
        decoded_sizes.add((frame.shape[1], frame.shape[0]))
        if decoded_count in target_indices:
            frames[decoded_count] = frame
            cv2.imwrite(str(scratch / f"frame_{decoded_count:010d}_raw.png"), frame)
        decoded_count += 1
        if decoded_count % 2000 == 0:
            print(f"Successfully decoded {decoded_count} frames", flush=True)
    cap.release()
    retained_source = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    matched_5140 = 5140 in frames and retained_source is not None and np.array_equal(frames[5140], retained_source)
    alignment = {
        "claim_type": "EXPERIMENT_RESULT_DECODE_AND_CACHE_ALIGNMENT_ONLY",
        "source_video_sha256": video_sha,
        "source_video_bytes": video.stat().st_size,
        "cache_sha256": file_sha(records_path),
        "cache_successful_frame_rows": expected_index,
        "decoded_successful_frames": decoded_count,
        "decoded_native_sizes": [list(s) for s in sorted(decoded_sizes)],
        "frame_5140_pixel_array_identical_to_retained_raw_png": bool(matched_5140),
        "retained_png_file_sha256": file_sha(source_path),
        "retained_png_decoded_pixel_sha256": pixel_sha(retained_source) if retained_source is not None else None,
        "new_decoded_5140_pixel_sha256": pixel_sha(frames[5140]) if 5140 in frames else None,
        "decoder_reported_metadata": decoder_metadata,
        "python_version": platform.python_version(),
        "opencv_version": cv2.__version__, "numpy_version": np.__version__,
        "method_sha256": file_sha(pathlib.Path(__file__)),
        "alignment_pass": bool(matched_5140 and decoded_count == expected_index and decoded_sizes == frame_sizes),
        "limits": ["Sequential decoder index alignment checked by identical source file, successful frame count/native size, and exact pixel equality at frame5140; no authoritative source PTS or independent all-frame cache-pixel hash is available.",
                   "Metadata-reported frame count is not used as the successful decode count.",
                   "Decode/pixel checks do not establish model or counting performance."]}
    dump(output / "decode_alignment.json", alignment)
    print(json.dumps(alignment, indent=2), flush=True)
    if not alignment["alignment_pass"]:
        raise RuntimeError("alignment failed; no track/pixel overlay claims produced")
    dx, dy = line[1][0] - line[0][0], line[1][1] - line[0][1]
    length = math.hypot(dx, dy)
    manifest = {"claim_type": "EXPERIMENT_RESULT_BOUNDED_TARGETED_PIXEL_EVIDENCE",
                "source_video_sha256": video_sha,
                "records_sha256": file_sha(records_path),
                "geometry_sha256": file_sha(geometry_path),
                "method_sha256": file_sha(pathlib.Path(__file__)),
                "pixel_digest_encoding": "SHA256 of contiguous native uint8 BGR bytes; shape recorded separately",
                "coordinate_mapping": "crop_x=native_x-x1; crop_y=native_y-y1; sheet image origin listed per tile; no resizing",
                "all_target_native_frames": [], "cases": [], "retained_image_files": []}
    for index in sorted(target_indices):
        frame = frames[index]
        manifest["all_target_native_frames"].append({
            "frame_index": index, "shape_hwc": list(frame.shape),
            "bgr_uint8_sha256": pixel_sha(frame),
            "decoder_index_not_authoritative_pts": True})
    for case in CASES:
        all_obs = [o for i in range(case["range"][0], case["range"][1] + 1)
                   for o in rows[i]["emitted_tracks"] if o["track_id"] in case["ids"]]
        crop = [max(0, math.floor(min(o["raw_bbox"][0] for o in all_obs) - 35)),
                max(0, math.floor(min(o["raw_bbox"][1] for o in all_obs) - 35)),
                min(1280, math.ceil(max(o["raw_bbox"][2] for o in all_obs) + 35)),
                min(720, math.ceil(max(o["raw_bbox"][3] for o in all_obs) + 35))]
        measurements = []
        for i in range(case["range"][0], case["range"][1] + 1):
            obs = [o for o in rows[i]["emitted_tracks"] if o["track_id"] in case["ids"]]
            evidence = []
            for o in obs:
                bb = o["raw_bbox"]
                bc = [(bb[0] + bb[2]) / 2, bb[3]]
                evidence.append({"track_id": o["track_id"], "class_name": o["class_name"],
                                 "class_id": o["class_id"], "confidence": o["confidence"],
                                 "original_detection_index": o["original_detection_index"],
                                 "measurement_provenance": o["measurement_provenance"],
                                 "raw_bbox": bb, "raw_bbox_bc_native": bc,
                                 "signed_distance_px": (dx * (bc[1] - line[0][1]) - dy * (bc[0] - line[0][0])) / length})
            measurements.append({"frame_index": i, "target_emitted": bool(obs),
                                 "observations": evidence})
            raw_crop = frames[i][crop[1]:crop[3], crop[0]:crop[2]]
            cv2.imwrite(str(scratch / f"{case['name']}_{i:010d}_crop.png"), raw_crop)
        case_result = dict(case, native_crop_xyxy=crop, measurements=measurements, contact_sheets=[])
        for annotate in (False, True):
            name = f"{case['name']}_{'overlay' if annotate else 'raw'}_contact.png"
            image, mappings = sheet(frames, case, rows, crop, line, polygons, annotate)
            path = output / name
            if not cv2.imwrite(str(path), image):
                raise RuntimeError("contact sheet write failed")
            entry = {"path": name, "sha256": file_sha(path), "bytes": path.stat().st_size,
                     "shape_hwc": list(image.shape), "tiles": mappings}
            manifest["retained_image_files"].append(entry)
            case_result["contact_sheets"].append(name)
        manifest["cases"].append(case_result)
    dump(output / "targeted_pixel_manifest.json", manifest)
    print(json.dumps({"target_frames_decoded": len(target_indices),
                      "retained_images": len(manifest["retained_image_files"]),
                      "retained_image_bytes": sum(e["bytes"] for e in manifest["retained_image_files"]),
                      "output": str(output)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
