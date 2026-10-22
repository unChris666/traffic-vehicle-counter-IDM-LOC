"""Replay frozen P0 on newly inferred clip tracks with explicit frame mapping.

No legacy raw-ID review or donor relation can enter this adapter. Global source
indices are mapped to local contiguous counting indices without synthesizing
prehistory, observations, or frames after the actual clip.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

from phase_9_model_experiment import SOURCE_SHA256, WINDOW, VARIANTS, sha256, write_json


SUPPORTED_RAW = frozenset(("person", "motorcycle", "car", "truck", "bus"))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def adapt_records(rows, *, source_sha256=SOURCE_SHA256, start_frame=7380, end_frame=7979,
                  namespace="isolated-phase9-clip"):
    _require(start_frame <= end_frame, "Invalid source clip window")
    rows = list(rows)
    _require(len(rows) == end_frame-start_frame+1, "Incomplete clip or synthesized frame count")
    result, discarded = [], Counter()
    for local, row in enumerate(rows):
        global_frame = start_frame + local
        _require(row.get("frame_index") == global_frame and row.get("clip_local_frame_index") == local,
                 "Actual/global/local source indices differ")
        _require(row.get("video_sha256") == source_sha256, "Foreign source video")
        _require((row.get("width"), row.get("height")) == (640,480), "Foreign source dimensions")
        detections = row.get("detections")
        _require(isinstance(detections,list), "Actual per-frame detections required")
        observations, seen, indices = [], set(), set()
        for emitted in row.get("emitted_tracks", []):
            track, index = emitted.get("track_id"), emitted.get("original_detection_index")
            _require(type(track) is int and track > 0 and track not in seen, "Invalid/repeated emitted raw ID")
            _require(type(index) is int and 0 <= index < len(detections) and index not in indices,
                     "Invalid/repeated source detection index")
            seen.add(track);indices.add(index)
            detection = detections[index]
            _require(emitted.get("observed") is True and emitted.get("emitted") is True,
                     "Predictions/non-emitted tracks cannot enter counting")
            _require(emitted.get("frame_index") == global_frame,
                     "Emitted observation belongs to another frame")
            _require(emitted.get("raw_bbox") == detection.get("bbox_xyxy_pixels")
                     and emitted.get("class_id") == detection.get("class_id")
                     and emitted.get("class_name") == detection.get("class_name")
                     and math.isclose(emitted.get("confidence",-1),detection.get("confidence",-2),abs_tol=1e-6),
                     "Raw emitted bbox/class/score differs from linked detector measurement")
            box = detection["bbox_xyxy_pixels"]
            _require(len(box) == 4 and all(type(x) in (int,float) and math.isfinite(x) for x in box)
                     and 0 <= box[0] < box[2] <= 640 and 0 <= box[1] < box[3] <= 480,
                     "Invalid raw bbox")
            label = detection["class_name"]
            if label not in SUPPORTED_RAW:
                discarded[label] += 1
                continue
            unit = f"{namespace}:raw:{track}"
            observations.append({"frame_index":local, "source_global_frame_index":global_frame,
                "track_id":track, "unit_id":unit, "episode_id":unit,
                "raw_bbox":deepcopy(box), "class_id":detection["class_id"], "class_name":label,
                "confidence":detection["confidence"], "observed":True, "emitted":True,
                "original_detection_index":index,
                "role":"unknown_person" if label == "person" else "vehicle",
                "association_verified":False, "identity_conflict":False,
                "measurement_provenance":"retained_phase_9_new_detection",
                "source_ref":{"global_frame_index":global_frame,"clip_local_frame_index":local,
                    "original_detection_index":index,"source_video_sha256":source_sha256,
                    "raw_frame_pixel_sha256":row.get("raw_frame_pixel_sha256")}})
        result.append({"frame_index":local, "source_global_frame_index":global_frame,
                       "observations":observations})
    return result, {"source_start_frame":start_frame,"source_end_frame":end_frame,
        "local_start_frame":0,"local_end_frame":len(rows)-1,"source_global_frame_equals_local_plus":start_frame,
        "synthetic_prehistory_frames":0,"synthetic_post_clip_frames":0,
        "legacy_raw_id_reviews_applied":False,"legacy_donor_relations_applied":False,
        "discarded_unsupported_raw_observations":dict(discarded)}


def _refs(value):
    found=[]
    if isinstance(value,dict):
        if type(value.get("frame_index")) is int and type(value.get("track_id")) is int:
            found.append((value["track_id"],value["frame_index"]))
        for child in value.values():found.extend(_refs(child))
    elif isinstance(value,list):
        for child in value:found.extend(_refs(child))
    return sorted(set(found))


def _global_event(event,offset):
    return {"event_id":event["event_id"],"display_id":event.get("display_id"),
            "category":event["category"],"direction":event["direction"],"route":event["route"],
            "measured_crossing":event.get("evidence",{}).get("measured_crossing"),
            "activation_frame_local":event["activation_frame"],
            "activation_source_frame":offset+event["activation_frame"],
            "decision_frame_local":event["decision_frame"],
            "decision_source_frame":offset+event["decision_frame"],
            "evaluation_activation":event["activation_frame"]>=WINDOW["warmup_source_frames"],
            "raw_source_refs":[{"track_id":track,"local_frame_index":frame,"source_global_frame_index":offset+frame}
                               for track,frame in _refs(event)]}


def _gzip_json(path,value):
    Path(path).write_bytes(gzip.compress((json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode(),mtime=0))


def replay_experiment(execution_root, *, geometry_path, policy_path, output_path):
    import phase_8_b_v5_identity as identity
    import phase_8_b_v5_counting as counting
    from phase_5_geometry_helpers import Geometry
    root,output=Path(execution_root),Path(output_path)
    model_report=json.loads((root/'report.json').read_text())
    _require(model_report.get('status')=='completed_development_confidence_experiment_pending_physical_review'
             and model_report.get('actual_detector_executed') is True
             and model_report.get('actual_encoder_cuda_execution_established') is True,
             'Completed actual detector/ReID execution evidence required')
    output.mkdir(parents=True,exist_ok=False)
    geometry_path,policy_path=Path(geometry_path),Path(policy_path)
    data=geometry_path.read_bytes()
    if geometry_path.suffix=='.gz':data=gzip.decompress(data)
    geometry_data=json.loads(data)
    _require(geometry_data["source_video"]["sha256"]==SOURCE_SHA256,"Geometry belongs to another video")
    native=output/'geometry.json';native.write_bytes(data)
    geometry=Geometry.from_draft(native,640,480)
    policy_input_sha256=sha256(policy_path)
    policy=json.loads(policy_path.read_text())
    _require(not policy.get("episode_relations"),"Foreign precomputed episode relations cannot enter the new clip")
    write_json(output/'frozen_policy.json',policy)
    sources={name:{"path":str(Path(module.__file__).resolve()),"sha256":sha256(module.__file__)}
             for name,module in (("identity",identity),("counting",counting))}
    comparisons=[]
    for name,threshold in VARIANTS:
        records=root/name/'track_records.jsonl.gz'
        with gzip.open(records,'rt') as stream:rows=[json.loads(line) for line in stream]
        _require(all(row.get("variant")==name for row in rows),"Variant provenance differs")
        frames,mapping=adapt_records(rows,namespace=f"phase9-{name}")
        source={"video_sha256":SOURCE_SHA256,"records_sha256":sha256(records),
            "geometry_sha256":hashlib.sha256(data).hexdigest(),"width":640,"height":480,
            "parent_run_id":"phase9_confidence_retention_clip_v1","variant":name,
            "source_frame_mapping":mapping,"clip_reset_not_full_video_history":True}
        target=output/name;target.mkdir()
        resolved=identity.prepare_identity_frames(frames,geometry,policy,relationships=None)
        effective=deepcopy(policy);effective["episode_relations"]=resolved.get("unit_relations",[])
        result=counting.replay_frames(resolved["frames"],geometry,source_identity=source,policy=effective)
        _gzip_json(target/'counting_result_local_indices.json.gz',result)
        _gzip_json(target/'frame_assignments_local_indices.json.gz',resolved["assignments"])
        _gzip_json(target/'unit_relations_local_indices.json.gz',resolved.get("unit_relations",[]))
        _gzip_json(target/'identity_audits_local_indices.json.gz',{key:resolved.get(key,[]) for key in
            ("episode_audit","role_audit","cross_category_audit","historical_hypothesis_audit","handoff_audit")})
        events=[_global_event(event,WINDOW["context_start_frame"]) for event in result["events"]]
        write_json(target/'events_global_source_export.json',events)
        write_json(target/'source_frame_mapping.json',mapping)
        eval_events=[event for event in events if event["evaluation_activation"]]
        row={"variant":name,"detector_conf":threshold,"context_aggregate":result["aggregate"],
             "evaluation_activation_events":len(eval_events),
             "evaluation_by_category":dict(Counter(event["category"] for event in eval_events)),
             "evaluation_measured":sum(bool(event["measured_crossing"]) for event in eval_events),
             "source_identity":source,"physical_passage_review":"PENDING_SEPARATE_SOURCE_REVIEW"}
        comparisons.append(row);write_json(target/'report.json',row)
    _require(sha256(policy_path)==policy_input_sha256,"Policy changed during paired replay")
    for item in sources.values():_require(sha256(item["path"])==item["sha256"],"P0 code changed during paired replay")
    report={"status":"COMPLETED_SCOPED_P0_REPLAY_ON_NEW_MODEL_CLIPS_PENDING_PHYSICAL_REVIEW",
        "variants":comparisons,"shared_policy_sha256":sha256(output/'frozen_policy.json'),
        "input_policy_sha256":sha256(policy_path),"executed_p0_sources":sources,
        "new_model_inference_by_this_replay":False,"synthetic_prehistory_or_post_clip_frames":False,
        "legacy_reviews_or_relations_applied":False,"full_video_traffic_count":False,
        "scope":"600 actual context frames per variant,540 evaluation frames; global=local+7380",
        "physical_accuracy_established":False}
    write_json(output/'report.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execution-root',required=True)
    parser.add_argument('--geometry-path',required=True);parser.add_argument('--policy-path',required=True)
    parser.add_argument('--output-path',required=True)
    print(json.dumps(replay_experiment(**vars(parser.parse_args()))))
