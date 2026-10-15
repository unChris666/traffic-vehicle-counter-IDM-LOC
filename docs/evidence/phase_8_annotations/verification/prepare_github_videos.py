#!/usr/bin/env python3
"""Prepare browser-playable copies of the exact completed Kaggle annotations.

This delivery-only script does not import project inference/counting code. It
binds each input to the completed annotation retention manifest and report,
transcodes every frame with libx264, and records independent full decode/PTS,
FPS, dimensions, SHA, and MP4 faststart evidence. MP4 files stay outside Git.
"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading
import time


SCHEMA = "phase8_github_browser_delivery_v1"
VIDEO_IDS = tuple(f"{day}_{period}" for day in ("weekday", "weekend")
                  for period in ("pagi", "siang", "sore", "malam"))
CODEC_PARAMETERS = {"encoder": "libx264", "codec": "h264", "crf": 18,
    "preset": "fast", "pixel_format": "yuv420p", "encoder_threads": 2,
    "decoder_threads": 1, "maximum_parallel_encoders": 2,
    "fps_mode": "passthrough", "encoder_time_base": "demux",
    "movflags": "+faststart", "audio": "none", "cuts_or_filters": False,
    "resize_or_crop": False}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".writing")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def file_reference(path, *, relative_to=None):
    path = Path(path)
    name = str(path.relative_to(relative_to)) if relative_to is not None else str(path)
    return {"path": name, "sha256": sha256(path), "size_bytes": path.stat().st_size}


def mp4_atoms(path):
    """Inspect top-level box offsets, including extended-size MP4 boxes."""
    result, size = [], Path(path).stat().st_size
    with Path(path).open("rb") as handle:
        position = 0
        while position < size:
            handle.seek(position)
            header = handle.read(8)
            require(len(header) == 8, "Truncated MP4 box header")
            box_size, kind = struct.unpack(">I4s", header)
            header_size = 8
            if box_size == 1:
                extended = handle.read(8)
                require(len(extended) == 8, "Truncated extended MP4 box header")
                box_size, header_size = struct.unpack(">Q", extended)[0], 16
            elif box_size == 0:
                box_size = size - position
            require(box_size >= header_size and position + box_size <= size, "Invalid MP4 box bounds")
            result.append({"type": kind.decode("ascii", errors="replace"),
                           "offset": position, "size_bytes": box_size})
            position += box_size
        require(position == size, "MP4 top-level boxes do not cover file")
    return result


def full_probe(path, output_path):
    """FFprobe decodes every frame, retaining integer presentation timestamps."""
    command = ["ffprobe", "-v", "error", "-threads", "1", "-count_frames", "-show_frames",
        "-show_entries", "stream=index,codec_type,codec_name,codec_tag_string,width,height,pix_fmt,"
        "r_frame_rate,avg_frame_rate,time_base,nb_frames,nb_read_frames,duration,start_time:"
        "format=format_name,duration,start_time,size:frame=media_type,best_effort_timestamp",
        "-of", "json", str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    require(completed.returncode == 0 and not completed.stderr.strip(),
            "Full ffprobe decode failed: " + completed.stderr[-3000:])
    result = json.loads(completed.stdout)
    require(len(result.get("streams", [])) == 1 and result["streams"][0].get("codec_type") == "video",
            "Expected one annotated video stream without audio")
    stream = result["streams"][0]
    frames = result.get("frames", [])
    require(frames and all(frame.get("media_type") == "video" for frame in frames), "Missing full frame probe")
    pts = [int(frame["best_effort_timestamp"]) for frame in frames]
    require(len(pts) == int(stream["nb_read_frames"]), "FFprobe read-frame counter differs from timestamps")
    require(all(first < second for first, second in zip(pts, pts[1:])), "Presentation timestamps are not increasing")
    time_base = Fraction(stream["time_base"])
    times = [value * time_base for value in pts]
    canonical = "\n".join(f"{value.numerator}/{value.denominator}" for value in times) + "\n"
    proof = {"command": command, "returncode": completed.returncode, "stderr": completed.stderr,
        "stream": stream, "format": result.get("format", {}), "full_decoded_frame_count": len(pts),
        "frame_pts_ticks": pts, "frame_pts_seconds_exact_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "first_frame_pts_seconds_exact": str(times[0]), "last_frame_pts_seconds_exact": str(times[-1])}
    write_json(output_path, proof)
    return proof, times


def build_plan(evidence_root):
    evidence_root = Path(evidence_root)
    retention_path = evidence_root / "annotation_retention_manifest.json"
    manifest = read_json(retention_path)
    artifacts = {entry["path"]: entry for entry in manifest["artifacts"]}
    require(len(artifacts) == len(manifest["artifacts"]), "Repeated original retention path")
    batch_path = evidence_root / "annotation_batch_report.json"
    batch_entry = artifacts.get("annotation_batch_report.json", {})
    require(sha256(batch_path) == batch_entry.get("sha256") and
            batch_path.stat().st_size == batch_entry.get("size_bytes"), "Original annotation batch SHA/size differs")
    batch = read_json(batch_path)
    require(batch.get("status") == "completed_all_eight_render_only" and batch.get("all_eight_selected") is True,
            "Original annotation batch is not complete")
    require(set(batch["selected_video_ids"]) == set(VIDEO_IDS), "Original batch does not contain exact eight TGDI slots")
    plan = []
    for video_id in VIDEO_IDS:
        report_path = evidence_root / video_id / "annotation_report.json"
        entry = artifacts.get(f"{video_id}/annotation_report.json", {})
        require(sha256(report_path) == entry.get("sha256") and report_path.stat().st_size == entry.get("size_bytes"),
                "Original annotation report SHA/size differs: " + video_id)
        report = read_json(report_path)
        video = report["output_video"]
        video_entry = artifacts.get(f"{video_id}/annotated_review.mp4", {})
        require(video_entry.get("sha256") == video.get("sha256") and
                video_entry.get("size_bytes") == video.get("size_bytes"), "Original video retention/report differs")
        require(report.get("video_id") == video_id and report["canvas"]["width"] == 1160
                and report["canvas"]["height"] == 720, "Unexpected annotation native canvas")
        require(video["frames_written"] == video["frames_redecoded"], "Original frame count was not validated")
        day, period = video_id.split("_")
        plan.append({"video_id": video_id,
            "filename": f"TGDI-{day.upper()}-{period.upper()}-annotated-review.mp4",
            "source_annotation": {"retention_path": f"{video_id}/annotated_review.mp4",
                "sha256": video["sha256"], "size_bytes": video["size_bytes"]},
            "original_report": file_reference(report_path),
            "frame_count": video["frames_written"], "documented_original_fps": video["fps"],
            "width": 1160, "height": 720, "accepted": report["final_accepted"],
            "pending": report["final_pending_candidates"], "final_pivot": report["final_pivot"]})
    require(sum(item["frame_count"] for item in plan) == 72590, "Original full frame total differs")
    require(sum(item["accepted"] for item in plan) == 58 and sum(item["pending"] for item in plan) == 1825,
            "Original scientific subtotal differs; delivery must not modify it")
    return plan, file_reference(retention_path), file_reference(batch_path)


def transcode(item, original_root, browser_root, proof_root):
    video_id = item["video_id"]
    source = Path(original_root) / (video_id + ".mp4")
    expected = item["source_annotation"]
    require(source.is_file() and source.stat().st_size == expected["size_bytes"] and sha256(source) == expected["sha256"],
            "Original downloaded annotation SHA/size differs: " + video_id)
    output = Path(browser_root) / item["filename"]
    require(not output.exists(), "Refusing to overwrite a browser delivery asset: " + str(output))
    temporary = output.with_name(output.stem + ".encoding.mp4")
    require(not temporary.exists(), "Incomplete encoder output exists; inspect before retry: " + str(temporary))
    proof_root = Path(proof_root)
    probe_in = proof_root / "probes" / (video_id + "_source.json")
    probe_out = proof_root / "probes" / (video_id + "_browser.json")
    log_path = proof_root / "codec_logs" / (video_id + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    original_probe, original_times = full_probe(source, probe_in)
    source_stream = original_probe["stream"]
    require(original_probe["full_decoded_frame_count"] == item["frame_count"] and
            (source_stream["width"], source_stream["height"]) == (item["width"], item["height"]),
            "Original source full decode dimensions/frame count differs")
    require(source_stream["codec_name"] == "mpeg4", "Expected actual OpenCV mp4v annotation source")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info", "-n", "-threads", "1",
        "-i", str(source), "-map", "0:v:0", "-an", "-sn", "-dn", "-map_metadata", "-1",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-threads", "2", "-filter_threads", "1", "-filter_complex_threads", "1",
        "-fps_mode", "passthrough", "-enc_time_base", "demux", "-movflags", "+faststart", str(temporary)]
    began = utc_now(); start = time.perf_counter()
    with log_path.open("wb") as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    require(completed.returncode == 0, "libx264 encoder failed; inspect " + str(log_path))
    encoded_probe, encoded_times = full_probe(temporary, probe_out)
    stream = encoded_probe["stream"]
    require(encoded_probe["full_decoded_frame_count"] == item["frame_count"] and
            (stream["width"], stream["height"]) == (item["width"], item["height"]),
            "Browser output frame count/dimensions differ")
    require(stream["codec_name"] == "h264" and stream["pix_fmt"] == "yuv420p", "Browser output codec/pixel format differs")
    require(Fraction(source_stream["avg_frame_rate"]) == Fraction(stream["avg_frame_rate"]),
            "Encoded average rational FPS differs")
    require(Fraction(source_stream["r_frame_rate"]) == Fraction(stream["r_frame_rate"]),
            "Encoded nominal rational FPS differs")
    require(original_times == encoded_times, "Encoded frame presentation timeline differs")
    atoms = mp4_atoms(temporary)
    moov = [atom["offset"] for atom in atoms if atom["type"] == "moov"]
    mdat = [atom["offset"] for atom in atoms if atom["type"] == "mdat"]
    require(len(moov) == 1 and mdat and moov[0] < min(mdat), "Browser MP4 lacks faststart moov before mdat")
    require(sha256(source) == expected["sha256"], "Original annotation changed during transcode")
    require(temporary.stat().st_size < 2_000_000_000, "Browser asset exceeds GitHub per-file limit")
    os.replace(temporary, output)
    item = dict(item)
    item.update({"status": "completed_verified", "path": str(output), "sha256": sha256(output),
        "size_bytes": output.stat().st_size, "started_utc": began, "finished_utc": utc_now(),
        "transcode_and_probe_wall_seconds": time.perf_counter() - start,
        "command": command, "encoder_returncode": completed.returncode,
        "source_codec": source_stream["codec_name"], "output_codec": stream["codec_name"],
        "pixel_format": stream["pix_fmt"], "source_full_decoded_frame_count": len(original_times),
        "output_full_decoded_frame_count": len(encoded_times), "presentation_timestamps_preserved_exactly": True,
        "presentation_timestamps_exact_sha256": encoded_probe["frame_pts_seconds_exact_sha256"],
        "source_rational_fps": source_stream["avg_frame_rate"], "output_rational_fps": stream["avg_frame_rate"],
        "fps_documentary_float_minus_stored_rational": item["documented_original_fps"] - float(Fraction(source_stream["avg_frame_rate"])),
        "faststart_moov_before_mdat": True, "top_level_mp4_atoms": atoms,
        "proofs": {"source_probe": file_reference(probe_in, relative_to=proof_root),
                   "browser_probe": file_reference(probe_out, relative_to=proof_root),
                   "codec_log": file_reference(log_path, relative_to=proof_root)},
        "original_annotation_unchanged_after_encoding": True,
        "lossless_copy": False, "delivery_conversion": "LOSSY_H264_VISUAL_COPY_OF_ORIGINAL_MP4V_ANNOTATED_RESULT",
        "new_detector_tracker_encoder_counting_execution": False})
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--browser-root", type=Path, required=True)
    parser.add_argument("--proof-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--wait-timeout-seconds", type=float, default=3600)
    arguments = parser.parse_args()
    require(arguments.wait_timeout_seconds > 0, "Positive input wait timeout required")
    plan, retention, batch = build_plan(arguments.evidence_root)
    arguments.browser_root.mkdir(parents=True, exist_ok=True)
    arguments.proof_root.mkdir(parents=True, exist_ok=True)
    manifest_path = arguments.proof_root / "delivery_manifest.json"
    require(not manifest_path.exists(), "Existing delivery manifest: preserve it and use a new proof root for a retry")
    versions = {}
    for program in ("ffmpeg", "ffprobe"):
        result = subprocess.run([program, "-version"], capture_output=True, text=True, check=True)
        versions[program] = result.stdout
    encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, check=True).stdout
    require("libx264" in encoders, "FFmpeg lacks libx264; no silent encoder substitution")
    versions_path = arguments.proof_root / "tool_versions.json"
    write_json(versions_path, {"versions": versions, "libx264_available": True})
    manifest = {"schema_version": SCHEMA, "status": "waiting_for_verified_originals",
        "claim_type": "ACTUAL_ANNOTATED_VIDEO_DELIVERY_TRANSCODE_NOT_NEW_SCIENTIFIC_RUN",
        "started_utc": utc_now(), "original_retention_manifest": retention,
        "original_annotation_batch_report": batch, "codec_parameters": CODEC_PARAMETERS,
        "actual_parallel_encoder_limit": arguments.workers,
        "original_video_root": str(arguments.original_root), "browser_video_root": str(arguments.browser_root),
        "tool_versions": file_reference(versions_path, relative_to=arguments.proof_root),
        "delivery_helper": file_reference(Path(__file__).resolve()),
        "models_tracker_reid_counting_rerun": False, "original_aggregates_changed": False,
        "expected_full_frame_count": sum(item["frame_count"] for item in plan),
        "unchanged_accepted": 58, "unchanged_pending": 1825, "assets": []}
    write_json(manifest_path, manifest)
    queued, active, deadline = list(plan), {}, time.monotonic() + arguments.wait_timeout_seconds
    try:
        with ThreadPoolExecutor(max_workers=arguments.workers) as executor:
            while queued or active:
                require(time.monotonic() < deadline, "Timed out waiting for actual downloaded originals")
                for item in list(queued):
                    if len(active) >= arguments.workers:
                        break
                    source = arguments.original_root / (item["video_id"] + ".mp4")
                    # Downloader creates the final name only after SHA/size
                    # verification; this script verifies those bytes again.
                    if source.is_file():
                        future = executor.submit(transcode, item, arguments.original_root,
                                                 arguments.browser_root, arguments.proof_root)
                        active[future] = item["video_id"]
                        queued.remove(item)
                        manifest["status"] = "transcoding_actual_originals"
                        write_json(manifest_path, manifest)
                        print(json.dumps({"event": "transcode_started", "video_id": item["video_id"], "utc": utc_now()}), flush=True)
                if not active:
                    time.sleep(2)
                    continue
                completed, _ = wait(active, timeout=2, return_when=FIRST_COMPLETED)
                for future in completed:
                    video_id = active.pop(future)
                    asset = future.result()
                    manifest["assets"].append(asset)
                    manifest["assets"].sort(key=lambda entry: VIDEO_IDS.index(entry["video_id"]))
                    manifest["completed_video_count"] = len(manifest["assets"])
                    manifest["completed_frame_count"] = sum(entry["output_full_decoded_frame_count"] for entry in manifest["assets"])
                    write_json(manifest_path, manifest)
                    print(json.dumps({"event": "transcode_completed_verified", "video_id": video_id,
                        "path": asset["path"], "sha256": asset["sha256"], "size_bytes": asset["size_bytes"],
                        "frames": asset["output_full_decoded_frame_count"], "utc": utc_now()}), flush=True)
        require(len(manifest["assets"]) == 8 and manifest["completed_frame_count"] == 72590,
                "Incomplete browser delivery set")
        manifest.update(status="completed_all_eight_verified", finished_utc=utc_now(),
            all_source_sha_verified=True, all_output_full_frame_counts_preserved=True,
            all_presentation_timestamps_preserved_exactly=True, all_outputs_h264_yuv420p_faststart=True,
            total_source_annotation_bytes=sum(entry["source_annotation"]["size_bytes"] for entry in manifest["assets"]),
            total_browser_delivery_bytes=sum(entry["size_bytes"] for entry in manifest["assets"]))
        write_json(manifest_path, manifest)
        print(json.dumps({"event": "delivery_preparation_completed", "manifest": str(manifest_path),
                          "videos": 8, "frames": 72590}), flush=True)
    except BaseException as error:
        manifest.update(status="failed_preserve_partial_evidence", finished_utc=utc_now(),
                        error={"type": type(error).__name__, "message": str(error)})
        write_json(manifest_path, manifest)
        raise


if __name__ == "__main__":
    main()
