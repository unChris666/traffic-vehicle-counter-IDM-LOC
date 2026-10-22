"""Review the complete competing episode while preserving its valid passage."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks"))
from phase_8_b_v7_batch import _read, _write
from phase_8_b_v8_batch import build_policy


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    out = ROOT / "results/b_v8/fixtures/blocker4843_control4798_v3"
    assert not out.exists(); out.mkdir()
    previous = ROOT / "results/b_v8/fixtures/blocker4843_control4798_v2"
    receipt = _read(previous / "pixel_evidence.json")
    wanted = {7796,7820,7850}; records, episode = {}, []
    cache = Path("/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz")
    assert sha(cache.read_bytes()) == receipt["source_records_sha256"]
    with gzip.open(cache,"rt") as handle:
        for line in handle:
            row = json.loads(line); frame = row["frame_index"]
            if frame > 7903:break
            if frame in wanted:records[frame] = row
            episode += [{"frame_index":frame, **item} for item in row["emitted_tracks"] if item["track_id"] == 4798]
    assert [i["frame_index"] for i in episode] == list(range(7796,7904))
    assert {i["class_name"] for i in episode} == {"motorcycle"}
    cap = cv2.VideoCapture("/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4"); tiles=[]
    for frame in range(max(wanted)+1):
        ok,image=cap.read();assert ok
        if frame not in wanted:continue
        digest=sha(image.tobytes());assert digest==records[frame]["detector_input_frame_pixel_sha256"]
        items=[i for i in records[frame]["emitted_tracks"] if i["track_id"] == 4798]
        receipt["images"].append({"frame_index":frame,"verified_decode_pixel_sha256":True,
            "raw_bgr_pixel_sha256":digest,"observations":items})
        if frame==7796:assert cv2.imwrite(str(out/"native-7796.png"),image)
        for item in items:
            x1,y1,x2,y2=map(round,item["raw_bbox"]);cv2.rectangle(image,(x1,y1),(x2,y2),(0,255,255),2)
        tile=np.zeros((506,640,3),np.uint8);tile[26:]=image
        cv2.putText(tile,f"SOURCE {frame}: same continuous foreground episode",(5,18),
            cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1);tiles.append(tile)
    cap.release()
    assert cv2.imwrite(str(out/"early_episode_contact.jpg"),np.vstack(tiles))
    receipt["images"].sort(key=lambda x:x["frame_index"])
    receipt["additional_source_pixel_frames"] = sorted(wanted)
    _write(out/"pixel_evidence.json",receipt);_write(out/"continuous_measurements.json.gz",episode)
    overlay=_read(ROOT/"results/b_v8/config/review_overlay_v2.json")
    review=deepcopy(overlay["videos"][0]["reviews"][-1])
    review["review_id"]="p1-reviewed-distinct-foreground-episode-v3"
    review["scopes"][0].update(start_frame=7796,
        physical_unit_id="review:TGDI_SIANG:distinct_foreground_motorcycle",
        episode_id="reviewed-distinct-foreground-episode")
    review["confirmed_frames"]=[7796,7820,7850,7888,7899,7903]
    proof=out/"pixel_evidence.json"
    review["evidence"]=[{"path":proof.relative_to(ROOT).as_posix(),"sha256":sha(proof.read_bytes()),
        "frame_index":i["frame_index"],"source_frame_pixel_sha256":i["raw_bgr_pixel_sha256"]}
        for i in receipt["images"] if i["frame_index"] in review["confirmed_frames"]]
    review["scope_basis"]="Complete continuous108-observation vehicle context7796–7903, bounded AI source-pixel identity review; separate from red and blue in co-present7888/7899/7903. Keep the eligible observed history together rather than splitting midway through its existing crossing. Continuity between anchors is an explicit engineering assumption."
    overlay["videos"][0]["reviews"][-1]=review
    path=ROOT/"results/b_v8/config/review_overlay_v3.json";assert not path.exists();_write(path,overlay)
    policy=ROOT/"results/b_v8/config/policy_v3.json";assert not policy.exists();_write(policy,build_policy(ROOT,overlay_path=path))
    _write(out/"review_entry.json",review)
    print(json.dumps({"reviewed_continuous_measurements":len(episode),"first":7796,"last":7903,
        "new_thresholds":False,"new_model_inference":False,"overlay":str(path)}))


if __name__ == "__main__":main()
