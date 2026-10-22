"""Bind an already reviewed physical passage to actual source measurements."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"notebooks"))
from phase_8_b_v7_batch import _read,_write
from phase_8_b_v8_batch import build_policy


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    out=ROOT/"results/b_v8/fixtures/reviewed_handoff_recovery"
    assert not out.exists();out.mkdir()
    source=_read(ROOT/"results/b_v8/fixtures/blocker4843/source_identity.json")
    cache=Path("/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz")
    assert sha(cache.read_bytes())==source["records_sha256"]
    wanted={1272,1300,1336,1340,1344,1349,1355,1376,1396,1424};records={}
    with gzip.open(cache,"rt") as handle:
        for line in handle:
            row=json.loads(line)
            if row["frame_index"]>1424:break
            if row["frame_index"] in wanted:records[row["frame_index"]]=row
    images=[];tiles=[];cap=cv2.VideoCapture("/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4")
    for frame in range(1425):
        ok,image=cap.read();assert ok
        if frame not in wanted:continue
        pixel=sha(image.tobytes());assert pixel==records[frame]["detector_input_frame_pixel_sha256"]
        obs=[o for o in records[frame]["emitted_tracks"] if o["track_id"] in {1049,1123,1101,1070}]
        images.append({"frame_index":frame,"verified_decode_pixel_sha256":True,
            "raw_bgr_pixel_sha256":pixel,"observations":obs})
        for item in obs:
            x1,y1,x2,y2=map(round,item["raw_bbox"]);color=(0,255,255) if item["track_id"] in {1049,1123} else (255,255,0)
            cv2.rectangle(image,(x1,y1),(x2,y2),color,1)
            cv2.putText(image,str(item["track_id"]),(x1,max(13,y1-3)),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1)
        tile=np.zeros((506,640,3),np.uint8);tile[26:]=image
        cv2.putText(tile,f"SOURCE {frame}: raw boxes; no gap observations",(5,18),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
        tiles.append(tile)
    cap.release()
    assert cv2.imwrite(str(out/"source_contact.jpg"),np.vstack([np.hstack(tiles[i:i+2]) for i in range(0,len(tiles),2)]))
    receipt={"schema_version":"p1_recovery_pixels_v1","video_sha256":source["video_sha256"],
        "source_records_sha256":source["records_sha256"],"images":images,
        "decode_method":"SEQUENTIAL_FROM_ZERO","new_model_execution":False}
    _write(out/"pixel_evidence.json",receipt)
    anchors=sorted(wanted-{1340,1344});proof=out/"pixel_evidence.json"
    review={"review_id":"p1-reviewed-same-passage-handoff-recovery",
        "type":"SAME_VEHICLE","claim_type":"ADJUDICATED_AI_PIXELS_REVIEW",
        "human_confirmation_status":"NOT_NEWLY_ADJUDICATED_BY_USER",
        "scopes":[{"track_id":1049,"start_frame":1272,"end_frame":1336,"raw_family":"vehicle",
            "physical_unit_id":"review:TGDI_SIANG:recovered_handoff_passage","episode_id":"reviewed-handoff-episode"},
            {"track_id":1123,"start_frame":1349,"end_frame":1424,"raw_family":"vehicle",
            "physical_unit_id":"review:TGDI_SIANG:recovered_handoff_passage","episode_id":"reviewed-handoff-episode"}],
        "confirmed_frames":anchors,
        "evidence":[{"path":proof.relative_to(ROOT).as_posix(),"sha256":sha(proof.read_bytes()),
            "frame_index":i["frame_index"],"source_frame_pixel_sha256":i["raw_bgr_pixel_sha256"]}
            for i in images if i["frame_index"] in anchors],
        "observation":"One red motorcycle is visible before occlusion as1049 and afterward as1123. Distinct following1101 and opposite1070 remain separate. This source review is already documented in immutableBv7QC and is reopened here.",
        "scope_extent_basis":"AI bounded source-pixel temporal identity review, not a globalrawID or automaticReIDprediction. Continuity between anchors is an explicitengineeringassumption; no source observation is created at1340/1344.",
        "required_evidence_grade":"INFERRED_NOT_MEASURED; gap after actualcrossing before confirmation remainsinferred",
        "reviewed_result_not_machine_prediction":True}
    _write(out/"review_entry.json",review)
    overlay=_read(ROOT/"results/b_v8/config/review_overlay_v3.json")
    overlay["videos"][0]["reviews"].append(review)
    op=ROOT/"results/b_v8/config/review_overlay_v4.json";assert not op.exists();_write(op,overlay)
    pp=ROOT/"results/b_v8/config/policy_v4.json";assert not pp.exists();_write(pp,build_policy(ROOT,overlay_path=op))
    print(json.dumps({"native_source_frames":len(images),"reviewed_anchors":len(anchors),
        "reviewed_raw_ids_are_data_not_runtime_rules":True,"core_code_or_thresholds_changed":False}))


if __name__=="__main__":main()
