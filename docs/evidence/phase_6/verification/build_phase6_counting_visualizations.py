"""Render case-level retained counting outcomes above unchanged contact sheets.

This reads accepted/resolved snapshots and existing PNG evidence only. It
never decodes video, runs models, replays geometry, or recomputes counting.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, __version__ as pillow_version


SAMPLES = Path("docs/evidence/phase_6/review_samples/TOR3-PAGI")
TRACKS = (1, 973, 1520, 1772, 1774, 1323)
CONTEXT_TRACK = {1772: 1774}
EXPECTED_STATUS = {1: "accepted", 973: "accepted", 1520: "accepted", 1772: "pending_review", 1774: "rejected", 1323: "pending_review"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    with gzip.open(path, "rt") as stream:
        return [json.loads(line) for line in stream]


def wrap_text(draw, line, font, width):
    words = line.split()
    lines = []
    current = ""
    for word in words:
        trial = current + (" " if current else "") + word
        if current and draw.textlength(trial, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]


def build(root, run):
    resolved_path = run / "resolved_decisions.jsonl.gz"
    accepted_path = run / "accepted_events.jsonl.gz"
    resolved = read_jsonl(resolved_path)
    accepted = {e["event_id"]: e for e in read_jsonl(accepted_path)}
    samples = json.loads((root/SAMPLES/"sample_index.json").read_text())
    cases = {c["track_id"]: c for c in samples["cases"]}
    out = run/"crossing_visualizations"
    out.mkdir(exist_ok=True)
    font = ImageFont.load_default(size=16)
    checks = []
    artifacts = []
    for tid in TRACKS:
        matches = [r for r in resolved if r["track_id"] == tid]
        if len(matches) != 1:
            raise ValueError(f"Need exactly one resolved candidate for track{tid}")
        row = matches[0]
        if row["status"] != EXPECTED_STATUS[tid]:
            raise ValueError(f"Resolved status changed for track{tid}; review before rendering")
        diag = row["diagnostic"]
        photo_tid = CONTEXT_TRACK.get(tid,tid)
        case = cases[photo_tid]
        event = accepted.get(row.get("event_id"))
        if (row["status"] == "accepted") != bool(event):
            raise ValueError("Accepted row/event identity mismatch")
        if event and event["representative_candidate_id"] != row["candidate_id"]:
            raise ValueError("Event representative does not match resolved candidate")
        confirmation_time = diag["metadata"].get("timestamp_estimate_from_index_fps_seconds")
        reason = ", ".join(row["reasons"])
        lines = [
            f"KEPUTUSAN AKHIR KASUS: {row['status'].upper()} | target track{tid}",
            "CASE-LEVEL FINAL OUTCOME; BUKAN counter/status pada tiap frame foto.",
            f"Kategori event: {row.get('category') or 'UNKNOWN / belum disahkan'} | arah geometri: {diag['direction']}",
            f"Origin frame{diag['origin_frame']}; passage terukur frame{diag['crossing_frame_start']}..{diag['crossing_frame_end']}; konfirmasi geometri frame{diag['confirmation_frame']}",
            f"Waktu konfirmasi geometri: {confirmation_time:.6f}s (estimasi indeks/FPS; bukan authoritative source PTS)",
            f"Candidate: {row['candidate_id']}",
            f"Event: {row.get('event_id') or 'NONE; tidak masuk subtotal accepted'}",
            f"Alasan snapshot: {reason}",
            f"Frame pada foto sumber track{photo_tid}: {','.join(map(str,case['frames']))}",
        ]
        if tid == 973:
            lines.append("Satu unit skuter merah; representative973. Kandidat964 tetap pending, bukan kendaraan tambahan.")
        if tid == 1772:
            lines += ["CONTEXT PHOTO: track1774 pada kendaraan yang sama; bukan crop atau bukti passage lengkap track1772.", "Frame7712/7721/7722 tidak ditampilkan oleh foto konteks ini. UNIT_COMPONENT_CHANGE tetap pending."]
        if tid == 1323:
            lines.append("Minivan/minibus: mapping kategori produk/angkot belum diputuskan; raw car bukan kategori event final.")
        if tid == 1774:
            lines.append("Komponen orang yang duduk pada skuter; bukan pedestrian independen dalam scope review ini.")
        color = {"accepted":"#126136","pending_review":"#835300","rejected":"#9d2424"}[row["status"]]
        for kind, src in case["artifacts"].items():
            source = root/src["path"]
            if digest(source) != src["sha256"]:
                raise ValueError(f"Source artifact changed: {source}")
            photo = Image.open(source).convert("RGB")
            width = max(photo.width, 1024)
            scratch = ImageDraw.Draw(Image.new("RGB",(width,1)))
            wrapped = [part for line in lines for part in wrap_text(scratch,line,font,width-32)]
            height = 28 + 23*len(wrapped)
            composed = Image.new("RGB",(width,height+photo.height),"#ffffff")
            composed.paste(photo,(0,height))
            draw = ImageDraw.Draw(composed)
            draw.rectangle((0,0,width-1,height-1),fill="#f4f6f8")
            draw.rectangle((0,0,8,height-1),fill=color)
            for i,line in enumerate(wrapped):
                draw.text((16,14+i*23),line,font=font,fill=color if i==0 else "#101820")
            name=f"id{tid}_{row['status']}_{kind}_case.png"
            target=out/name
            composed.save(target)
            # This checks every displayed source pixel, not just a hash link.
            saved=Image.open(target).convert("RGB")
            unchanged=ImageChops.difference(photo,saved.crop((0,height,photo.width,height+photo.height))).getbbox() is None
            if not unchanged:
                raise AssertionError("Photograph/contact pixels changed during composition")
            checks += [{"check":f"id{tid}_{kind}_source_sha256","passed":True},{"check":f"id{tid}_{kind}_all_source_pixels_unchanged","passed":unchanged},{"check":f"id{tid}_{kind}_resolved_status_event_binding","passed":True}]
            artifacts.append({"track_id":tid,"status":row["status"],"category":row.get("category"),"direction":diag["direction"],"candidate_id":row["candidate_id"],"event_id":row.get("event_id"),"reasons":row["reasons"],"hard_block_reasons":row["hard_block_reasons"],"origin_frame":diag["origin_frame"],"passage_frame_interval":[diag["crossing_frame_start"],diag["crossing_frame_end"]],"confirmation_frame":diag["confirmation_frame"],"confirmation_index_fps_estimate_seconds":confirmation_time,"authoritative_source_pts":None,"photo_context_track_id":photo_tid,"photo_exact_frames":case["frames"],"photo_complete_passage_evidence_for_target":tid!=1772,"source_path":src["path"],"source_sha256":src["sha256"],"source_kind":kind,"source_paste_origin_xy":[0,height],"source_pixels_unchanged":unchanged,"output_path":str(target.relative_to(root)),"output_sha256":digest(target),"output_size_bytes":target.stat().st_size,"dimensions_width_height":list(saved.size),"header_text":lines,"case_level_outcome_not_frame_counter":True})
    index={"claim_type":"EXPERIMENT_RESULT_RETAINED_CASE_OUTCOME_VISUALIZATION","run_id":run.name,"resolved_decisions_path":str(resolved_path.relative_to(root)),"resolved_decisions_sha256":digest(resolved_path),"accepted_events_path":str(accepted_path.relative_to(root)),"accepted_events_sha256":digest(accepted_path),"source_sample_index_sha256":digest(root/SAMPLES/"sample_index.json"),"method_sha256":digest(Path(__file__)),"pillow_version":pillow_version,"counting_models_video_or_geometry_rerun":False,"new_reviews_or_events_created":False,"case_count":len(TRACKS),"artifact_count":len(artifacts),"artifacts":artifacts}
    (out/"visualization_index.json").write_text(json.dumps(index,ensure_ascii=False,indent=2)+"\n")
    validation={"claim_type":"EXPERIMENT_RESULT_COMPOSITION_INTEGRITY_ONLY","checks_passed":len(checks),"checks_failed":0,"checks":checks,"photograph_pixels_unchanged":True,"outcomes_from_retained_snapshot_only":True,"not_ground_truth_performance":True}
    (out/"validation.json").write_text(json.dumps(validation,indent=2)+"\n")
    print(json.dumps({"case_count":len(TRACKS),"image_count":len(artifacts),"checks_passed":len(checks),"output":str(out)},indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--run",type=Path,required=True)
    args=parser.parse_args()
    build(args.root,args.run)
