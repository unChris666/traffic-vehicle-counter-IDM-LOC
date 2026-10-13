#!/usr/bin/env python3
"""Reproduce bounded, development-only Option B association calibration.

No detector, tracker, encoder, geometry state machine, counting pipeline, or
held-out target features are executed. Uses only retained emitted raw boxes.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import statistics
from pathlib import Path


RECORDS = "docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz"
PIXEL_REVIEW = "docs/evidence/phase_6/review_samples/TOR3-PAGI/pixel_review.json"
POSITIVE_COMPONENTS = [(880, 893, 4975, 4979), (923, 912, 5011, 5022), (964, 967, 5118, 5126)]
POSITIVE_DUPLICATES = [(964, 973, 5129, 5130)]
REVIEWED_SEPARATE = [(1, 3, 60, 60)]
VEHICLE_LABELS = {"motorcycle", "car", "truck", "bus"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def box_properties(box):
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    if width <= 0 or height <= 0:
        raise ValueError("Non-positive source bbox")
    return {"width": width, "height": height, "area": width * height,
            "diagonal": math.hypot(width, height),
            "center": [(x1 + x2) / 2, (y1 + y2) / 2],
            "bc": [(x1 + x2) / 2, y2]}


def features(first, second, *, kind):
    """COMPONENT_OF: first person, second motorcycle; SAME_VEHICLE symmetric.

    The motion residual is the change in *pixel* relative-centre offsets,
    divided by the mean relevant bbox diagonal at the two consecutive frames.
    It is not the change between separately normalized offsets.
    """
    a = {m["frame_index"]: m for m in first}
    b = {m["frame_index"]: m for m in second}
    frames = sorted(a.keys() & b.keys())
    rows, steps = [], []
    longest = streak = 0
    for frame in frames:
        ma, mb = a[frame], b[frame]
        pa, pb = box_properties(ma["raw_bbox"]), box_properties(mb["raw_bbox"])
        xa, ya, za, wa = ma["raw_bbox"]
        xb, yb, zb, wb = mb["raw_bbox"]
        intersection = max(0.0, min(za, zb) - max(xa, xb)) * max(0.0, min(wa, wb) - max(ya, yb))
        iou = intersection / (pa["area"] + pb["area"] - intersection)
        norm = pb["diagonal"] if kind == "COMPONENT_OF" else (pa["diagonal"] + pb["diagonal"]) / 2
        offset = [pa["center"][i] - pb["center"][i] for i in range(2)]
        inside = xb <= pa["bc"][0] <= zb and yb <= pa["bc"][1] <= wb
        row = {
            "frame_index": frame,
            "first": {k: ma[k] for k in ("track_id", "class_name", "original_detection_index", "raw_bbox", "confidence", "measurement_provenance")},
            "second": {k: mb[k] for k in ("track_id", "class_name", "original_detection_index", "raw_bbox", "confidence", "measurement_provenance")},
            "iou": iou, "first_bc_inside_second": inside,
            "first_bc_normalized_in_second_box": [(pa["bc"][0] - xb) / pb["width"], (pa["bc"][1] - yb) / pb["height"]],
            "relative_center_offset_pixels": offset, "normalization_diagonal_pixels": norm,
            "center_distance_norm": math.hypot(*offset) / norm,
            "first_second_area_ratio": pa["area"] / pb["area"],
            "first_second_width_ratio": pa["width"] / pb["width"],
            "first_second_height_ratio": pa["height"] / pb["height"],
        }
        previous = rows[-1] if rows else None
        streak = streak + 1 if previous and frame == previous["frame_index"] + 1 else 1
        longest = max(longest, streak)
        if previous and frame == previous["frame_index"] + 1:
            residual = math.dist(offset, previous["relative_center_offset_pixels"]) / ((norm + previous["normalization_diagonal_pixels"]) / 2)
            a_prev, b_prev = box_properties(a[previous["frame_index"]]["raw_bbox"]), box_properties(b[previous["frame_index"]]["raw_bbox"])
            bc_a = [pa["bc"][i] - a_prev["bc"][i] for i in range(2)]
            bc_b = [pb["bc"][i] - b_prev["bc"][i] for i in range(2)]
            denom = math.hypot(*bc_a) * math.hypot(*bc_b)
            cosine = sum(bc_a[i] * bc_b[i] for i in range(2)) / denom if denom else None
            steps.append({"frame_start": previous["frame_index"], "frame_end": frame,
                          "relative_motion_residual_norm": residual, "bc_motion_cosine": cosine})
        rows.append(row)
    if not rows:
        return {"common_frame_indices": [], "common_frames": 0, "consecutive_common_frames_max": 0,
                "first_bc_inside_second_fraction": None, "iou_min": None, "iou_max": None,
                "center_distance_norm_max": None, "relative_motion_residual_norm_max": None,
                "common_detections": [], "motion_steps": []}
    foot_x = [r["first_bc_normalized_in_second_box"][0] for r in rows]
    foot_y = [r["first_bc_normalized_in_second_box"][1] for r in rows]
    cosines = [s["bc_motion_cosine"] for s in steps if s["bc_motion_cosine"] is not None]
    return {
        "common_frame_indices": frames, "common_frames": len(frames), "consecutive_common_frames_max": longest,
        "first_bc_inside_second_fraction": sum(r["first_bc_inside_second"] for r in rows) / len(rows),
        "iou_min": min(r["iou"] for r in rows), "iou_max": max(r["iou"] for r in rows),
        "center_distance_norm_max": max(r["center_distance_norm"] for r in rows),
        "relative_motion_residual_norm_max": max((s["relative_motion_residual_norm"] for s in steps), default=None),
        "first_bc_normalized_in_second_box_x_span": max(foot_x) - min(foot_x),
        "first_bc_normalized_in_second_box_y_span": max(foot_y) - min(foot_y),
        "bc_motion_cosine_min": min(cosines, default=None), "bc_motion_cosine_median": statistics.median(cosines) if cosines else None,
        "first_second_area_ratio_min": min(r["first_second_area_ratio"] for r in rows),
        "first_second_area_ratio_max": max(r["first_second_area_ratio"] for r in rows),
        "common_detections": rows, "motion_steps": steps,
    }


def hundredth_up(value):
    return math.ceil(value * 100) / 100


def hundredth_down(value):
    return math.floor(value * 100) / 100


def run(repo, output):
    records_path, review_path = repo / RECORDS, repo / PIXEL_REVIEW
    pixel_review = json.loads(review_path.read_text())
    reviews = {r["track_id"]: r for r in pixel_review["reviews"]}
    windows = [(lo, hi) for _, _, lo, hi in POSITIVE_COMPONENTS + POSITIVE_DUPLICATES + REVIEWED_SEPARATE]
    observations = []
    with gzip.open(records_path, "rt") as stream:
        for line in stream:
            record = json.loads(line)
            if any(lo <= record["frame_index"] <= hi for lo, hi in windows):
                observations.extend(record["emitted_tracks"])
    # Target windows are deliberately absent from the loaded feature observations.
    assert not any(m["track_id"] in {1772, 1774} for m in observations)

    def select(track_id, lo, hi, labels):
        return [m for m in observations if m["track_id"] == track_id and lo <= m["frame_index"] <= hi and m["class_name"] in labels]

    def review_evidence(track_id):
        r = reviews[track_id]
        return {"review_track_id": track_id, "observations": r["observations"],
                "exact_frames_opened": r["exact_frames_opened"],
                "raw_contact": r["raw_contact"], "overlay_contact": r["overlay_contact"],
                "reviewer_type": "AI_ASSISTED_CODEX", "formal_ground_truth": False}

    pairs = []
    for vehicle, person, lo, hi in POSITIVE_COMPONENTS:
        evidence = review_evidence(person)
        pairs.append({"pair_id": f"component_{person}_{vehicle}_{lo}_{hi}", "relation": "COMPONENT_OF",
                      "first_track_id": person, "second_track_id": vehicle, "window_inclusive": [lo, hi],
                      "reference_label": "REVIEW_SUPPORTED_COMPONENT", "use": "DEVELOPMENT_CALIBRATION_ONLY",
                      "reference_evidence": evidence,
                      "features": features(select(person, lo, hi, {"person"}), select(vehicle, lo, hi, {"motorcycle"}), kind="COMPONENT_OF")})
        alternatives = sorted({m["track_id"] for m in observations if lo <= m["frame_index"] <= hi and m["class_name"] == "motorcycle" and m["track_id"] != vehicle})
        for alternative in alternatives:
            pair_features = features(select(person, lo, hi, {"person"}), select(alternative, lo, hi, {"motorcycle"}), kind="COMPONENT_OF")
            if pair_features["common_frames"]:
                pairs.append({"pair_id": f"alternative_{person}_{alternative}_{lo}_{hi}", "relation": "COMPONENT_OF",
                              "first_track_id": person, "second_track_id": alternative, "window_inclusive": [lo, hi],
                              "reference_label": "UNKNOWN", "use": "ALTERNATIVE_FEATURE_INSPECTION_NOT_NEGATIVE_LABEL",
                              "reference_evidence": None, "features": pair_features})
    for first, second, lo, hi in POSITIVE_DUPLICATES:
        pairs.append({"pair_id": f"duplicate_{first}_{second}_{lo}_{hi}", "relation": "SAME_VEHICLE",
                      "first_track_id": first, "second_track_id": second, "window_inclusive": [lo, hi],
                      "reference_label": "REVIEW_SUPPORTED_DUPLICATE", "use": "DEVELOPMENT_CALIBRATION_ONLY_NO_HELD_OUT_DUPLICATE",
                      "reference_evidence": review_evidence(second),
                      "features": features(select(first, lo, hi, {"motorcycle"}), select(second, lo, hi, {"motorcycle"}), kind="SAME_VEHICLE")})
        alternatives = sorted({m["track_id"] for m in observations if lo <= m["frame_index"] <= hi and m["class_name"] == "motorcycle" and m["track_id"] not in {first, second}})
        for alternative in alternatives:
            pair_features = features(select(first, lo, hi, {"motorcycle"}), select(alternative, lo, hi, {"motorcycle"}), kind="SAME_VEHICLE")
            if pair_features["common_frames"]:
                pairs.append({"pair_id": f"duplicate_alternative_{first}_{alternative}_{lo}_{hi}", "relation": "SAME_VEHICLE",
                              "first_track_id": first, "second_track_id": alternative, "window_inclusive": [lo, hi],
                              "reference_label": "UNKNOWN", "use": "ALTERNATIVE_FEATURE_INSPECTION_NOT_NEGATIVE_LABEL",
                              "reference_evidence": None, "features": pair_features})
    for first, second, lo, hi in REVIEWED_SEPARATE:
        pairs.append({"pair_id": f"separate_{first}_{second}_{lo}_{hi}", "relation": "SAME_VEHICLE",
                      "first_track_id": first, "second_track_id": second, "window_inclusive": [lo, hi],
                      "reference_label": "REVIEW_SUPPORTED_SEPARATE_VEHICLES", "use": "PIXEL_SUPPORTED_NEGATIVE_STRUCTURALLY_CROSS_CATEGORY",
                      "reference_evidence": review_evidence(first),
                      "features": features(select(first, lo, hi, {"car"}), select(second, lo, hi, {"motorcycle"}), kind="SAME_VEHICLE")})

    component = [p["features"] for p in pairs if p["reference_label"] == "REVIEW_SUPPORTED_COMPONENT"]
    duplicate = [p["features"] for p in pairs if p["reference_label"] == "REVIEW_SUPPORTED_DUPLICATE"]
    thresholds = {
        "component": {"min_common_frames": 3, "min_consecutive_common_frames": 3,
                      "min_first_bc_inside_second_fraction": min(p["first_bc_inside_second_fraction"] for p in component),
                      "max_center_distance_norm": hundredth_up(max(p["center_distance_norm_max"] for p in component)),
                      "max_relative_motion_residual_norm": hundredth_up(max(p["relative_motion_residual_norm_max"] for p in component))},
        "same_vehicle": {"min_common_frames": 2, "min_consecutive_common_frames": 2,
                         "min_iou": hundredth_down(min(p["iou_min"] for p in duplicate)),
                         "max_center_distance_norm": hundredth_up(max(p["center_distance_norm_max"] for p in duplicate)),
                         "max_relative_motion_residual_norm": hundredth_up(max(p["relative_motion_residual_norm_max"] for p in duplicate))},
    }
    rules = {
        "claim_type": "ENGINEERING_EXPERIMENT_FROZEN_DEVELOPMENT_ONLY_NOT_PRODUCT_DEFAULT",
        "thresholds": thresholds,
        "derivation": "Component spatial/motion upper bounds = ceil(100 * largest positive-window value)/100. Duplicate IoU lower bound = floor(100 * smallest positive-window value)/100; other bounds use same ceiling. Foot-inside minimum = smallest positive-window fraction. No target used. Rounding precision .01 is an explicit engineering control, not calibrated probability.",
        "minimum_support_controls": "Component common/consecutive frames >=3 is an explicit engineering control to require temporal support. Duplicate >=2 reuses the two actually pixel-reviewed coexistent calibration frames; its reliability/generalization are unestablished.",
        "excluded_from_bounds": {"held_out_component_pair": [1772, 1774], "unknown_alternative_pairs": True, "reviewed_separate_pair": [1, 3]},
        "missing_validation": "No held-out duplicate positive. Only one pixel-backed real negative, cross-category and one frame; same-category near-neighbour and walking-person negatives require additional actual review. Synthetic negatives do not substitute for those reviews.",
        "unique_assignment_policy": "If multiple distinct vehicle groups pass, keep unresolved; no numeric score margin was inferred from these samples.",
    }
    formulas = {
        "box_source": "emitted_tracks.raw_bbox, never bbox Kalman or lifecycle prediction",
        "class_filter": "Component first=person, second=motorcycle. Duplicate both=motorcycle. Family-changing observations are excluded rather than relabelled; candidate episode recovery is a separate method.",
        "center_distance_norm_max": "max Euclidean(center(first)-center(second))/normalization_diagonal; COMPONENT_OF denominator second bbox diagonal; SAME_VEHICLE denominator mean of both bbox diagonals, symmetric.",
        "relative_motion_residual_norm_max": "For consecutive common decoder frames only: Euclidean(relative_center_offset_t-relative_center_offset_prev)/mean(normalization_diagonal_t,normalization_diagonal_prev). Null if no consecutive common pair.",
        "first_bc_inside_second_fraction": "Fraction common frames with first raw-bbox BC inclusively inside second raw_bbox. Inclusive here is an association feature, not a change to neutral polygon boundaries.",
        "iou_min_max": "Positive intersection / union areas of raw xyxy boxes; not evidence of identity on its own.",
        "bc_motion_cosine": "Dot product of raw BC pixel displacement vectors / product of lengths, only consecutive common frames; null for a zero vector. Retained for investigation, not an acceptance threshold.",
    }
    output.mkdir(parents=True, exist_ok=True)
    provenance = {"source_records_path": RECORDS, "source_records_sha256": sha256(records_path),
                  "source_pixel_review_path": PIXEL_REVIEW, "source_pixel_review_sha256": sha256(review_path),
                  "method_path": str(Path(__file__).resolve().relative_to(repo)), "method_sha256": sha256(__file__)}
    data = {"claim_type": "EXPERIMENT_RESULT_RETAINED_FEATURE_EXTRACTION_NOT_MODEL_OR_COUNTING_RESULT",
            "provenance": provenance, "formulas": formulas, "pairs": pairs,
            "label_counts": {label: sum(p["reference_label"] == label for p in pairs) for label in sorted({p["reference_label"] for p in pairs})},
            "target_features_computed": False, "appearance_features_available": False,
            "formal_ground_truth": False, "detector_tracker_reid_geometry_counting_executed": False}
    write_json(output / "pair_features.json", data)
    rules["provenance"] = provenance | {"pair_features_path": str((output / "pair_features.json").relative_to(repo)), "pair_features_sha256": sha256(output / "pair_features.json")}
    write_json(output / "frozen_thresholds.json", rules)
    lines = ["# Opsi B — kalibrasi terbatas dari bukti tersimpan", "",
             "**EXPERIMENT RESULT:** feature dihitung dari raw bbox emitted-track yang terikat ke sumber. Tidak menjalankan model, geometry state machine, counting, atau fitur kasus held-out ID1772/1774. Ini pengembangan parameter eksperimen; bukan ground truth atau ukuran accuracy.", "",
             "| Relasi dan pasangan | Window | Common/consecutive max | Foot inside | Center distance max | Relative-motion residual max | IoU min |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for pair in pairs:
        if pair["reference_label"] == "UNKNOWN":
            continue
        f = pair["features"]
        lines.append(f"| {pair['relation']} {pair['first_track_id']}/{pair['second_track_id']} | {pair['window_inclusive']} | {f['common_frames']}/{f['consecutive_common_frames_max']} | {f['first_bc_inside_second_fraction']:.6f} | {f['center_distance_norm_max']:.9f} | {str(f['relative_motion_residual_norm_max'])} | {f['iou_min']:.9f} |")
    lines += ["", "**ENGINEERING EXPERIMENT — frozen thresholds:**", "", "```json", json.dumps(thresholds, indent=2), "```", "",
              rules["derivation"], "", rules["minimum_support_controls"], "",
              "Pasangan alternatif mempunyai label **UNKNOWN**. Nilainya membantu memeriksa ambiguity assignment, tetapi tidak diubah menjadi negative label tanpa pixel review. Pasangan ID1/3 memang kendaraan berbeda menurut review frame60; ia merupakan negative lintas kategori, bukan bukti kemampuan membedakan dua motorcycle berdekatan.", "",
              rules["missing_validation"], "", "Tidak ada embedding per observation dalam cache ini; feature appearance tidak digunakan. Label person dari rider tidak ikut menentukan kategori motorcycle. Source raw bbox/BC tetap disimpan apa adanya.", "",
              "Reproduksi dari root repository:", "", "```bash", "python docs/evidence/phase_6/option_b_calibration/calibrate_retained_pairs.py --repo .", "```", "",
              "Artefak `pair_features.json` mempertahankan setiap frame/detection index/raw bbox/class/confidence, formula, alternatif dan hash sumber; `frozen_thresholds.json` mengikat angka ke metode serta feature bytes. Tidak boleh mengubah angka memakai hasil target lalu mengklaim target held-out.", ""]
    (output / "README.md").write_text("\n".join(lines))
    manifest = {"claim_type": "REPRODUCIBILITY_MANIFEST", "provenance": provenance,
                "files": [{"path": str(p.relative_to(repo)), "sha256": sha256(p), "size_bytes": p.stat().st_size}
                          for p in [output / "pair_features.json", output / "frozen_thresholds.json", output / "README.md", Path(__file__)]]}
    write_json(output / "manifest.json", manifest)
    print(json.dumps({"thresholds": thresholds, "label_counts": data["label_counts"], "feature_artifact": str(output / "pair_features.json")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.repo.resolve()
    run(root, root / "docs/evidence/phase_6/option_b_calibration")
