"""Read-only retained-night comparison media; never runs inference or counting.

Decode sequentially at native resolution, reproduce only the frozen photometric
transform, verify saved input pixel hashes, and draw measured linked raw boxes.
Case windows are a bounded audit inventory, not traffic ground truth.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RUN_ID = "20261014T062858_002323Z"
VIDEO_SHA = "a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082"
CASES = [
    {"case_id": "dev_beginning_motorcycle_27", "split": "development", "segment_id": "dev_beginning", "crossing_end": 27, "frames": [13,14,20,24,26,27,30], "crop": [180,245,860,710]},
    {"case_id": "dev_beginning_motorcycle_113", "split": "development", "segment_id": "dev_beginning", "crossing_end": 113, "frames": [104,105,106,107,108,109,110,111,112,113,114,119], "crop": [250,280,820,680]},
    {"case_id": "dev_quarter_motorcycle_2297", "split": "development", "segment_id": "dev_quarter", "crossing_end": 2297, "frames": [2277,2280,2285,2290,2296,2297,2300], "crop": [190,205,1170,715]},
    {"case_id": "holdout_middle_motorcycle_4869", "split": "holdout", "segment_id": "holdout_middle", "crossing_end": 4869, "frames": [4855,4856,4857,4860,4868,4869,4887], "crop": [220,240,820,710]},
    {"case_id": "dev_three_quarters_truck_7114", "split": "development", "segment_id": "dev_three_quarters", "crossing_end": 7114, "frames": [7071,7072,7073,7080,7113,7114,7126,7147], "crop": [170,0,1280,715]},
    {"case_id": "dev_three_quarters_motorcycle_7170", "split": "development", "segment_id": "dev_three_quarters", "crossing_end": 7170, "frames": [7150,7154,7157,7166,7169,7170,7171,7172], "crop": [200,190,820,715]},
    {"case_id": "dev_three_quarters_car_conflict_7244", "split": "development", "segment_id": "dev_three_quarters", "crossing_end": 7244, "frames": [7210,7224,7240,7243,7244,7337,7358,7360], "crop": [140,100,1280,715]},
    {"case_id": "holdout_end_motorcycle_9356", "split": "holdout", "segment_id": "holdout_end", "crossing_end": 9356, "frames": [9345,9346,9350,9355,9356,9363], "crop": [380,315,1080,700]},
    {"case_id": "dev_quarter_car_detection_control", "split": "development", "segment_id": "dev_quarter", "crossing_end": None, "frames": [2277,2280,2285,2297,2300,2310], "crop": [0,170,1280,715]},
    {"case_id": "holdout_middle_headlight_control", "split": "holdout", "segment_id": "holdout_middle", "crossing_end": None, "frames": [4674,4734,4794,4854,4913], "crop": [0,190,1280,715]},
    {"case_id": "holdout_end_censored_control", "split": "holdout", "segment_id": "holdout_end", "crossing_end": None, "frames": [9350,9410,9470,9530,9589], "crop": [0,190,1280,715]},
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as stream:
        return json.load(stream)


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--video", type=Path, default=Path("/tmp/traffic-phase7-source/TOR3-MALAM.mp4"))
    args = parser.parse_args()
    repo, run = args.repo.resolve(), args.run.resolve()
    output = repo / "docs/evidence/phase_7/temporal" / RUN_ID / "temporal_review"
    output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("frozen_phase7_transform", repo / "notebooks/phase_7_night_helpers.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    config = read(run / "configuration.json")
    assert config["expected_video_sha256"] == VIDEO_SHA and sha(args.video) == VIDEO_SHA
    geometry = read(repo / config["geometry_path"])["rendered_native_pixels"]
    variants = config["variants"]
    wanted = set(f for case in CASES for f in case["frames"])
    records, decisions = {}, {}
    source_bindings = {}
    checks = []

    def check(name, passed, detail=None):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise AssertionError(f"{name}: {detail}")

    for variant in variants:
        name = variant["name"]
        records[name] = {}
        cache = run / name / "track_records.jsonl.gz"
        with gzip.open(cache, "rt") as stream:
            for line in stream:
                record = json.loads(line)
                if record["frame_index"] in wanted:
                    records[name][record["frame_index"]] = record
        check(name + " all requested retained source frames", set(records[name]) == wanted)
        decisions[name] = read(run / name / "machine_passage_decisions.json.gz")
        source_bindings[name] = {"track_records_sha256": sha(cache), "machine_decisions_sha256": sha(run / name / "machine_passage_decisions.json.gz")}
        for frame in records[name].values():
            raw = frame["raw_detections"]
            for track in frame["emitted_tracks"]:
                donor = raw[track["original_detection_index"]]
                check(name + " linked measured raw bbox/class/source", track["raw_bbox"] == donor["bbox_xyxy_pixels"] and track["class_name"] == donor["class_name"] and track["confidence"] == donor["confidence"] and track["measurement_provenance"] == "retained_phase_7_detection", [frame["frame_index"], track["track_id"]])
    native = {}
    capture = cv2.VideoCapture(str(args.video))
    index = 0
    while index <= max(wanted):
        okay, pixels = capture.read()
        if not okay:
            break
        if index in wanted:
            check("native decoded shape", pixels.shape == (720, 1280, 3), index)
            native[index] = pixels
            for variant in variants:
                name = variant["name"]
                donor = helper.apply_transform(pixels, variant)
                pixel_sha = hashlib.sha256(donor.tobytes()).hexdigest()
                record = records[name][index]
                check(name + " exact actual detector and encoder input pixels", pixel_sha == record["detector_input_frame_pixel_sha256"] == record["encoder_input_frame_pixel_sha256"], index)
        index += 1
    capture.release()
    check("all native source frames decoded", set(native) == wanted)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 19) if Path(font_path).exists() else ImageFont.load_default()
    small = ImageFont.truetype(font_path, 15) if Path(font_path).exists() else ImageFont.load_default()
    entries = []
    palette = {"motorcycle": (255, 80, 50), "car": (60, 180, 255), "truck": (255, 170, 40), "bus": (255, 170, 40), "person": (240, 100, 250)}
    for case in CASES:
        entry = dict(case, artifacts={}, views={}, source_decisions={})
        for name in records:
            found = [d for d in decisions[name] if d["diagnostic"].get("crossing_frame_end") == case["crossing_end"]] if case["crossing_end"] is not None else []
            check(name + " unambiguous candidate by declared crossing frame", len(found) == 1 if case["crossing_end"] is not None else len(found) == 0, case["case_id"])
            entry["source_decisions"][name] = [{"candidate_id": d["candidate_id"], "track_id": d["track_id"], "status": d["status"], "category": d["category"], "reasons": d["reasons"], "selector": d["selector"]} for d in found]
        for mode in ("pixels", "measured_overlay"):
            x0, y0, x1, y1 = case["crop"]
            width, height = x1 - x0, y1 - y0
            columns = 3
            rows_per_variant = (len(case["frames"]) + columns - 1) // columns
            tile_height = height + 30
            header = 78
            contact = Image.new("RGB", (width * columns, header + tile_height * rows_per_variant * len(variants)), (18, 18, 18))
            draw = ImageDraw.Draw(contact)
            draw.text((12, 8), case["case_id"] + " | " + case["split"], fill="white", font=font)
            draw.text((12, 35), mode + " | original frame indices | crop at native pixel scale", fill="white", font=small)
            tiles = []
            for variant_index, variant in enumerate(variants):
                name = variant["name"]
                for position, frame_index in enumerate(case["frames"]):
                    pixels = helper.apply_transform(native[frame_index], variant)
                    picture = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
                    if mode == "measured_overlay":
                        layer = Image.new("RGBA", picture.size, (0, 0, 0, 0))
                        tint = ImageDraw.Draw(layer)
                        tint.polygon([tuple(p) for p in geometry["side_a_polygon"]], fill=(40, 120, 255, 20), outline=(40, 120, 255, 160))
                        tint.polygon([tuple(p) for p in geometry["side_b_polygon"]], fill=(255, 140, 30, 20), outline=(255, 140, 30, 160))
                        picture = Image.alpha_composite(picture.convert("RGBA"), layer).convert("RGB")
                        pd = ImageDraw.Draw(picture)
                        pd.line([tuple(geometry["line"]["P1"]), tuple(geometry["line"]["P2"])], fill=(255, 240, 0), width=3)
                        record = records[name][frame_index]
                        linked = {item["original_detection_index"] for item in record["emitted_tracks"]}
                        for raw_index, detection in enumerate(record["raw_detections"]):
                            if raw_index not in linked and detection["class_name"] in {"motorcycle", "car", "truck", "bus"}:
                                box = detection["bbox_xyxy_pixels"]
                                pd.rectangle(tuple(box), outline=(180, 180, 180), width=2)
                                pd.text((box[0], max(0, box[1] - 18)), f"d{raw_index} unlinked {detection['class_name']}", fill=(220, 220, 220), font=small)
                        for item in record["emitted_tracks"]:
                            box = item["raw_bbox"]
                            color = palette.get(item["class_name"], (180, 220, 180))
                            pd.rectangle(tuple(box), outline=color, width=3)
                            label = f"ID{item['track_id']} {item['class_name']} d{item['original_detection_index']}"
                            pd.text((box[0], max(0, box[1] - 19)), label, fill=color, font=small)
                            if item["class_name"] in {"motorcycle", "car", "truck", "bus"}:
                                xx, yy = (box[0] + box[2]) / 2, box[3]
                                pd.ellipse((xx-5, yy-5, xx+5, yy+5), fill=color, outline=(255,255,255), width=1)
                    crop = picture.crop(tuple(case["crop"]))
                    col, row = position % columns, variant_index * rows_per_variant + position // columns
                    left, top = col * width, header + row * tile_height
                    contact.paste(crop, (left, top + 30))
                    draw.text((left + 8, top + 5), f"{name} frame {frame_index}", fill="white", font=small)
                    record = records[name][frame_index]
                    tiles.append({"variant": name, "frame_index": frame_index, "crop_native": case["crop"], "contact_tile_xywh": [left, top + 30, width, height], "source_input_pixel_sha256": record["detector_input_frame_pixel_sha256"], "emitted_measured_tracks": record["emitted_tracks"], "raw_vehicle_detection_indices": [i for i,d in enumerate(record["raw_detections"]) if d["class_name"] in {"motorcycle","car","truck","bus"}]})
            destination = output / f"{case['case_id']}_{mode}.png"
            contact.save(destination)
            entry["artifacts"][mode] = {"path": destination.relative_to(repo).as_posix(), "sha256": sha(destination), "bytes": destination.stat().st_size, "width": contact.width, "height": contact.height, "contact_lossless": True, "native_crop_scale": 1.0, "geometry_tint_applied": mode == "measured_overlay"}
            entry["views"][mode] = {"tiles": tiles}
        entries.append(entry)
    result = {"schema_version": "phase7_temporal_contact_index_v1", "run_id": RUN_ID, "source_video_sha256": VIDEO_SHA, "source_run_directory": run.as_posix(), "source_bindings": source_bindings, "source_method_sha256": sha(Path(__file__)), "frozen_transform_helper_sha256": sha(repo / "notebooks/phase_7_night_helpers.py"), "cases": entries, "actual_unique_native_frames_decoded": len(native), "contact_artifacts_generated": len(entries) * 2, "model_tracker_encoder_counting_rerun": False, "limitations": ["Visual audit samples, not exhaustive traffic ground truth", "Same-frame candidate inventory does not itself prove physical matching; actual pixel review is separate", "Controls without a machine crossing candidate are inspected, not promoted into counts", "Category-conflict frames beyond declared counting windows are explicit offline evidence"]}
    write(output / "contact_index.json", result)
    validation = {"schema_version": "phase7_temporal_contacts_validation_v1", "checks_total": len(checks), "checks_passed": sum(c["passed"] for c in checks), "successful": all(c["passed"] for c in checks), "checks": checks, "source_index_sha256": sha(output / "contact_index.json")}
    write(output / "artifact_validation.json", validation)
    print(json.dumps({"cases": len(entries), "images": len(entries) * 2, "unique_frames": len(native), "checks_passed": validation["checks_passed"], "checks_total": len(checks), "output": str(output)}))


if __name__ == "__main__":
    main()
