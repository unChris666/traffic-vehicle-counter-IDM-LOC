"""Index retained QC evidence; never run inference or alter a machine result."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def save(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main():
    source = json.loads((ROOT / "input_manifest.json").read_text())["source_identity"]
    pixels = json.loads((ROOT / "evidence/source_pixel_validation.json").read_text())
    native = {row["path"]: row for row in pixels["native_files"]}
    images = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        sha = digest(path)
        row = {"path": rel, "bytes": path.stat().st_size, "sha256": sha}
        if rel in native:
            original = native[rel]
            assert original["file_sha256"] == sha, rel
            row.update({
                "kind": "SOURCE_NATIVE_PIXEL_VERIFIED",
                "source_frame_index": original["frame_index"],
                "decoded_pixel_sha256": original["pixel_sha256"],
                "pixel_verification": "source_pixel_validation.json",
            })
        else:
            row.update({
                "kind": "DERIVED_DISPLAY_IMAGE",
                "derivation": "Contact sheet, focused crop, labels and/or JPEG re-encoding; not a native source-frame file.",
                "source_scope": "See adjacent per-group evidence receipts and case ledgers; no inferred pixel identity.",
            })
        images.append(row)
    assert len(native) == sum(row["kind"] == "SOURCE_NATIVE_PIXEL_VERIFIED" for row in images)
    save(ROOT / "evidence/manifest.json", {
        "audit_id": ROOT.name,
        "source_video_sha256": source["video_sha256"],
        "source_records_sha256": source["records_sha256"],
        "source_frame_indices": "zero-based, 0..9127",
        "source_video_included": False,
        "scope": "Selected retained evidence and sampled temporal review; not a continuous full-video audit or formal ground truth.",
        "native_png_files": len(native),
        "unique_native_source_frames": pixels["unique_native_source_frames"],
        "derived_display_images": sum(row["kind"] == "DERIVED_DISPLAY_IMAGE" for row in images),
        "files": images,
    })

    manifest_path = ROOT / "artifact_manifest.json"
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == manifest_path or "__pycache__" in path.parts:
            continue
        files.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
    recommendation = REPO / "docs/PHASE_9_QC_RECOMMENDATIONS.md"
    save(manifest_path, {
        "audit_id": ROOT.name,
        "audit_date": "2026-10-20",
        "report_timezone": "Asia/Bangkok",
        "scope": "QC recommendations for the TGDI-WEEKDAY-SIANG B v4 pilot; no pipeline or baseline changes.",
        "machine_result_modified": False,
        "new_detector_tracker_reid_counting_enhancement_run": False,
        "full_video_continuous_visual_review": False,
        "other_seven_videos_validated": False,
        "file_count": len(files),
        "total_bytes": sum(row["bytes"] for row in files),
        "related_document": {"path": recommendation.relative_to(REPO).as_posix(), "sha256": digest(recommendation)},
        "files": files,
        "self_excluded": True,
    })
    for row in files:
        assert digest(ROOT / row["path"]) == row["sha256"], row["path"]
    print(json.dumps({"artifact_files_verified": len(files), "native_png_files": len(native), "derived_display_images": len(images) - len(native), "bytes": sum(row["bytes"] for row in files)}))


if __name__ == "__main__":
    main()
