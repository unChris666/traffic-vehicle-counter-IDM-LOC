"""Retain source proof for a distinct competing motorcycle; no inference."""
from copy import deepcopy
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
    out = ROOT / "results/b_v8/fixtures/blocker4843_control4798_v2"
    if out.exists():
        raise ValueError("Preserve previous evidence")
    out.mkdir()
    old = ROOT / "results/b_v8/fixtures/blocker4843"
    source = _read(old / "source_identity.json")
    video = Path("/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4")
    assert sha(video.read_bytes()) == source["video_sha256"]
    records = {r["frame_index"]: r for r in _read(old / "source_records_7800_8010.json.gz")}
    wanted = {7888, 7899, 7903, 7928, 7935}
    tracks = {4798, 4808, 4843, 4874}
    cap = cv2.VideoCapture(str(video)); images, tiles = [], []
    for frame in range(max(wanted) + 1):
        ok, image = cap.read(); assert ok
        if frame not in wanted:
            continue
        digest = sha(image.tobytes())
        assert digest == records[frame]["detector_input_frame_pixel_sha256"]
        obs = [o for o in records[frame]["emitted_tracks"] if o["track_id"] in tracks]
        images.append({"frame_index": frame, "verified_decode_pixel_sha256": True,
            "raw_bgr_pixel_sha256": digest, "observations": deepcopy(obs)})
        if frame == 7903:
            assert cv2.imwrite(str(out / "native-7903.png"), image)
        annotated = image.copy()
        for item in obs:
            x1, y1, x2, y2 = [round(x) for x in item["raw_bbox"]]
            color = (0, 255, 255) if item["track_id"] == 4798 else (255, 255, 0)
            cv2.rectangle(annotated, (x1,y1), (x2,y2), color, 2)
            cv2.putText(annotated, str(item["track_id"]), (x1,max(15,y1-4)),
                cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1)
        tile = np.zeros((506,640,3),np.uint8); tile[26:] = annotated
        cv2.putText(tile, f"SOURCE {frame}: exact retained vehicle boxes", (5,18),
            cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1); tiles.append(tile)
    cap.release()
    tiles.append(np.zeros_like(tiles[0]))
    assert cv2.imwrite(str(out / "distinct_source_contact.jpg"),
        np.vstack([np.hstack(tiles[i:i+2]) for i in range(0,6,2)]))
    receipt = {"schema_version":"p1_distinct_competitor_pixels_v1", **{
        "video_sha256":source["video_sha256"], "source_records_sha256":source["records_sha256"]},
        "images":images, "decode_method":"SEQUENTIAL_FROM_ZERO",
        "new_model_execution":False, "source_observations_created":False}
    _write(out / "pixel_evidence.json", receipt)
    overlay = _read(ROOT / "results/b_v8/config/review_overlay.json")
    proof = out / "pixel_evidence.json"
    review = {"review_id":"p1-distinct-foreground-unit-source-proof-v2",
        "type":"SPLIT_IDENTITY", "claim_type":"ADJUDICATED_AI_PIXELS_REVIEW",
        "human_confirmation_status":"NOT_NEWLY_ADJUDICATED_BY_USER",
        "scopes":[{"track_id":4798,"start_frame":7888,"end_frame":7903,
            "raw_family":"vehicle","physical_unit_id":"track:4798","episode_id":"unreviewed-vehicle"}],
        "confirmed_frames":[7888,7899,7903],
        "evidence":[{"path":proof.relative_to(ROOT).as_posix(),"sha256":sha(proof.read_bytes()),
            "frame_index":i["frame_index"],"source_frame_pixel_sha256":i["raw_bgr_pixel_sha256"]}
            for i in images if i["frame_index"] <= 7903],
        "observation":"The foreground dark motorcycle4798 coexists with the red4808 and blue4843 before SUV occlusion; it is a separate physical unit from the reviewed red passage.",
        "scope_basis":"Positive source-scoped distinct identity proof; keep its existing counting unit and episode to avoid splitting an already valid passage.",
        "not_a_post_occlusion_alias_to_4874":True,
        "no_global_raw_id_label":True}
    overlay["videos"][0]["reviews"].append(review)
    path = ROOT / "results/b_v8/config/review_overlay_v2.json"
    assert not path.exists(); _write(path,overlay)
    policy_path = ROOT / "results/b_v8/config/policy_v2.json"
    assert not policy_path.exists(); _write(policy_path,build_policy(ROOT,overlay_path=path))
    _write(out / "review_entry.json", review)
    print(json.dumps({"source_pixel_frames":len(images),"overlay":str(path),
        "policy":str(policy_path),"existing_counting_unit_preserved":True}))


if __name__ == "__main__":
    main()
