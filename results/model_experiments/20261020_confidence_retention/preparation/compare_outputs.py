"""Read-only comparison of newly retained model outputs; no model/count replay."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path


def read(path):
    with gzip.open(path, "rt") as stream:
        return [json.loads(line) for line in stream]


def stable_detection(d):
    return (d["class_id"], *(round(x, 4) for x in d["bbox_xyxy_pixels"]), round(d["confidence"], 5))


def annotate(image, row, heading):
    import cv2
    result = image.copy()
    cv2.rectangle(result, (0, 0), (639, 32), (15, 15, 15), -1)
    cv2.putText(result, heading, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .58, (255, 255, 255), 1, cv2.LINE_AA)
    for obj in row["emitted_tracks"]:
        if obj["class_name"] not in {"person", "car", "truck", "motorcycle", "bus"}:
            continue
        x1, y1, x2, y2 = [round(x) for x in obj["raw_bbox"]]
        color = (40, 180, 250) if obj["confidence"] < .25 else (60, 220, 70)
        cv2.rectangle(result, (x1, y1), (x2, y2), color, 1)
        label = f'{obj["track_id"]} {obj["class_name"]} {obj["confidence"]:.2f}'
        width = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .33, 1)[0][0]
        y = max(42, y1)
        cv2.rectangle(result, (max(0,x1), y-12), (min(639,x1+width+3), y+2), (15,15,15), -1)
        cv2.putText(result, label, (max(0,x1), y), cv2.FONT_HERSHEY_SIMPLEX, .33, color, 1, cv2.LINE_AA)
        cv2.circle(result, ((x1+x2)//2, y2), 2, color, -1)
    return cv2.resize(result, (1280,960), interpolation=cv2.INTER_NEAREST)


def compare(root, output):
    import cv2
    import numpy as np
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    a = read(root / "baseline_conf025/track_records.jsonl.gz")
    b = read(root / "candidate_conf010/track_records.jsonl.gz")
    assert len(a) == len(b) == 600
    frames, low_tracks = [], defaultdict(list)
    for baseline, candidate in zip(a,b):
        assert baseline["frame_index"] == candidate["frame_index"]
        assert baseline["raw_frame_pixel_sha256"] == candidate["raw_frame_pixel_sha256"]
        ah = Counter(stable_detection(d) for d in baseline["detections"])
        bh = Counter(stable_detection(d) for d in candidate["detections"] if d["confidence"] >= .25)
        low = [d for d in candidate["emitted_tracks"] if d["confidence"] < .25]
        for obj in low:
            low_tracks[obj["track_id"]].append({"frame_index":candidate["frame_index"],
                "class_name":obj["class_name"], "confidence":obj["confidence"], "raw_bbox":obj["raw_bbox"]})
        frames.append({"frame_index":baseline["frame_index"], "evaluation":baseline["evaluation"],
            "baseline_detections":len(baseline["detections"]), "candidate_detections":len(candidate["detections"]),
            "baseline_emitted":len(baseline["emitted_tracks"]), "candidate_emitted":len(candidate["emitted_tracks"]),
            "candidate_low_emitted":len(low), "rounded_high_detection_sets_equal":ah == bh})
    with (output / "paired_frames.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(frames[0]));writer.writeheader();writer.writerows(frames)
    details = [{"track_id":track, "first_low_source_frame":min(o["frame_index"] for o in observations),
                "last_low_source_frame":max(o["frame_index"] for o in observations),
                "low_emitted_observations":len(observations),
                "class_histogram_low_only":dict(Counter(o["class_name"] for o in observations)),
                "observations":observations} for track, observations in sorted(low_tracks.items())]
    (output / "candidate_low_track_details.json").write_text(json.dumps(details,indent=2)+'\n')
    sheets = []
    by_frame_a = {row["frame_index"]:row for row in a}
    by_frame_b = {row["frame_index"]:row for row in b}
    for path in sorted((root / "native_samples").glob("*.png")):
        index = int(path.stem.split("-")[-1]);image = cv2.imread(str(path))
        assert hashlib.sha256(image.tobytes()).hexdigest() == by_frame_a[index]["raw_frame_pixel_sha256"]
        joined = np.concatenate((annotate(image,by_frame_a[index],f"source {index} baseline conf0.25"),
                                 annotate(image,by_frame_b[index],f"source {index} candidate conf0.10")),axis=1)
        target = output / f"pair-{index:06d}.jpg"
        assert cv2.imwrite(str(target),joined,[cv2.IMWRITE_JPEG_QUALITY,93])
        sheets.append({"source_frame_index":index,"path":target.name,
                       "sha256":hashlib.sha256(target.read_bytes()).hexdigest()})
    report = {"status":"ACTUAL_MODEL_ARTIFACT_COMPARISON_NOT_PHYSICAL_ACCURACY",
              "paired_context_frames":len(frames), "paired_evaluation_frames":sum(r["evaluation"] for r in frames),
              "identical_source_pixels_confirmed":True,
              "high_detection_rounded_set_equal_frames":sum(r["rounded_high_detection_sets_equal"] for r in frames),
              "rounding":"bbox4 decimals, confidence5 decimals; not a bitwise identity assertion",
              "candidate_low_emitted_observations":sum(r["candidate_low_emitted"] for r in frames),
              "candidate_low_track_ids":len(details),
              "extra_observations_not_extra_physical_vehicles":True,
              "contact_sheets":sheets, "physical_review_status":"PENDING_EXPLICIT_SOURCE_REVIEW"}
    (output / "comparison.json").write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--execution-root",required=True);parser.add_argument("--output",required=True)
    args=parser.parse_args();print(json.dumps(compare(args.execution_root,args.output)))
