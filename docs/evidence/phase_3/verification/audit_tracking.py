"""Independent read-only audit of Phase 3 artifacts; no tracker/model execution.

Writes audit outputs only under --output-dir, never mutates retained input artifacts.
Checks software/provenance consistency; diagnostics are not identity-quality metrics.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_VIDEO_SHA256 = '606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c'
EXPECTED_DETECTIONS_SHA256 = '033a2815d3abbd23327936a1b9d948b2b9b7d312796516e5ee46aec5685be345'
EXPECTED_SOURCE_RUN_ID = '20261011T052950_360560Z_ed399fb8'
EXPECTED_FRAME_COUNT = 10282
EXPECTED_ULTRALYTICS = '8.4.175'


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def iter_jsonl(path: Path):
    with path.open(encoding='utf-8') as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f'{path.name}: blank line {line_no}')
            row=json.loads(line)
            if not isinstance(row,dict):
                raise ValueError(f'{path.name}: line {line_no} is not object')
            yield row


def require_int(value, context):
    if isinstance(value, bool) or not isinstance(value,int):
        raise ValueError(f'{context}: expected integer, got {value!r}')
    return value


def finite_number(value, context):
    if isinstance(value, bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(f'{context}: not finite number {value!r}')
    return float(value)


def finite_box(box, context):
    if not isinstance(box,list) or len(box)!=4:
        raise ValueError(f'{context}: expected xyxy list of length 4')
    vals=[finite_number(v,context) for v in box]
    if not vals[2]>vals[0] or not vals[3]>vals[1]:
        raise ValueError(f'{context}: nonpositive box area')
    return vals


def equal_float(left, right, context, tolerance=1e-7):
    left=finite_number(left,context);right=finite_number(right,context)
    if not math.isclose(left,right,rel_tol=tolerance,abs_tol=tolerance):
        raise ValueError(f'{context}: mismatch {left!r} vs {right!r}')


def pixel_digest(path:Path):
    from PIL import Image
    with Image.open(path) as im:
        im=im.convert('RGB')
        return {'width':im.width,'height':im.height,'rgb_sha256':hashlib.sha256(im.tobytes()).hexdigest()}


class Audit:
    def __init__(self):
        self.checks=[]
        self.errors=[]
        self.diagnostics={}
    def record(self,name,passed,details=None):
        entry={'check':name,'passed':bool(passed)}
        if details is not None:entry['details']=compact_check_details(name, details)
        self.checks.append(entry)
        if not passed:self.errors.append(entry)
    def check(self,name,fn):
        try:
            result=fn()
            self.record(name,True,result)
            return result
        except Exception as exc:
            self.record(name,False,{'error_type':type(exc).__name__,'message':str(exc)})
            return None


def compact_check_details(name, details):
    """Keep diagnostics in the audit, not copies of input/output sequences.

    Audit.check still returns the complete in-memory result for dependent checks.
    Only its persisted check details are summarized here.
    """
    if not isinstance(details, (dict, list, tuple)):
        return details
    if isinstance(details, dict) and 'error_type' in details:
        return details
    if name in {'phase3_report_json_read', 'run_manifest_json_read'}:
        return {key: details[key] for key in
                ['phase', 'run_id', 'status', 'frames_processed', 'manual_review_status']
                if key in details}
    if name == 'retained_detection_cache_identity_schema_contiguity':
        return details[1]
    if name == 'full_frame_records_links_measurement_and_lifecycle_consistency':
        return {**details['diagnostics'],
                'measurement_provenance': 'raw detections preserved; estimated Kalman boxes distinguished',
                'per_frame_id_and_source_detection_uniqueness': 'passed',
                'lifecycle_last_observed_missing_counts_and_pool_semantics': 'passed'}
    if name == 'focused_trace_7711_7718_complete':
        return {'scope': details['scope'], 'frame_indices': [r['frame_index'] for r in details['frames']],
                'trace_artifact': 'focused_track_trace_7711_7718.json'}
    return details

# Artifact-specific audit follows after schema confirmation from notebook author.


def check_detection_cache(cache_path:Path):
    if file_sha256(cache_path)!=EXPECTED_DETECTIONS_SHA256:
        raise ValueError("Detection cache SHA256 mismatch")
    rows=list(iter_jsonl(cache_path))
    if len(rows)!=EXPECTED_FRAME_COUNT:
        raise ValueError(f"Expected {EXPECTED_FRAME_COUNT} cache rows, got {len(rows)}")
    raw_classes=Counter()
    for index,row in enumerate(rows):
        if require_int(row.get("frame_index"),"cached frame_index")!=index:
            raise ValueError(f"Cache not contiguous at row {index}")
        if row.get("video_sha256")!=EXPECTED_VIDEO_SHA256:
            raise ValueError(f"Cache video hash mismatch at row {index}")
        width=require_int(row.get("width"),"cached width")
        height=require_int(row.get("height"),"cached height")
        if width<=0 or height<=0:raise ValueError("Invalid cache frame dimensions")
        if not isinstance(row.get("detections"),list):raise ValueError("Cached detections not a list")
        for det_index,det in enumerate(row["detections"]):
            context=f"cache frame {index} detection {det_index}"
            require_int(det.get("class_id"),context+" class_id")
            if not isinstance(det.get("class_name"),str):raise ValueError(context+": missing class_name")
            confidence=finite_number(det.get("confidence"),context+" confidence")
            if not 0<=confidence<=1:raise ValueError(context+": confidence outside [0,1]")
            box=finite_box(det.get("bbox_xyxy_pixels"),context+" bbox")
            # Source detections were clipped by Phase2; tracker Kalman boxes are assessed separately.
            if box[0]<0 or box[1]<0 or box[2]>width or box[3]>height:
                raise ValueError(context+": raw detection outside image bounds")
            raw_classes[det["class_name"]]+=1
    return rows, {"frame_count":len(rows),"raw_detection_count":sum(len(x["detections"]) for x in rows),
                  "zero_detection_frame_count":sum(not x["detections"] for x in rows),
                  "raw_detection_observations_by_class":dict(raw_classes),
                  "interpretation":"Detection observations, not physical-object or traffic totals"}

def reject_identity_metrics(value,path="root"):
    forbidden={"accuracy","precision","recall","f1","mape","idf1","mota","tracking_accuracy","counting_accuracy"}
    if isinstance(value,dict):
        for key,item in value.items():
            if key.lower() in forbidden and isinstance(item,(int,float)) and not isinstance(item,bool):
                raise ValueError(f"Ground-truth-free report contains numeric identity/quality metric {path}.{key}")
            reject_identity_metrics(item,f"{path}.{key}")
    elif isinstance(value,list):
        for index,item in enumerate(value):reject_identity_metrics(item,f"{path}[{index}]")


def audit_frame_records(record_path:Path,cache_rows,fps):
    histories=defaultdict(list)
    last_snapshots={}
    lifecycle=defaultdict(list)
    records=[]
    emitted_ids=set()
    emitted_count=0
    empty_input=0
    empty_emitted=0
    for index,row in enumerate(iter_jsonl(record_path)):
        if index>=len(cache_rows):raise ValueError('Extra output frame beyond cached sequence')
        parent=cache_rows[index]
        if require_int(row.get('frame_index'),'output frame_index')!=index:raise ValueError('Output rows not contiguous')
        if row.get('video_sha256')!=EXPECTED_VIDEO_SHA256:raise ValueError(f'Wrong output video SHA at {index}')
        if row.get('parent_run_id')!=EXPECTED_SOURCE_RUN_ID:raise ValueError(f'Wrong parent run at {index}')
        if (row.get('width'),row.get('height'))!=(parent['width'],parent['height']):raise ValueError('Output dimensions mismatch')
        if row.get('raw_detections')!=parent['detections']:raise ValueError(f'Raw detections changed at {index}')
        if row.get('timestamp_parent_backend_ms')!=parent.get('timestamp_backend_ms'):raise ValueError('Parent backend timestamp changed')
        equal_float(row.get('timestamp_estimate_from_index_fps_seconds'),index/fps,'Output approximate timestamp')
        emitted=row['emitted_tracks'];assigned=row['assigned_observations_including_unconfirmed']
        snapshots=row['lifecycle_snapshots'];transitions=row['lifecycle_transitions']
        emitted_map={o['track_id']:o for o in emitted}
        assigned_map={o['track_id']:o for o in assigned}
        snapshot_map={o['track_id']:o for o in snapshots}
        if len(emitted_map)!=len(emitted):raise ValueError(f'Duplicate emitted ID at {index}')
        if len(assigned_map)!=len(assigned):raise ValueError(f'Duplicate assigned ID at {index}')
        if len(snapshot_map)!=len(snapshots):raise ValueError(f'Duplicate lifecycle ID at {index}')
        if not set(emitted_map)<=set(assigned_map):raise ValueError('Emitted ID lacks assigned detection')
        if not set(assigned_map)<=set(snapshot_map):raise ValueError('Assigned ID lacks lifecycle snapshot')
        input_indices=[]
        for track_id,obs in assigned_map.items():
            require_int(track_id,'assigned track ID')
            if track_id<=0:raise ValueError('Nonpositive track ID')
            if obs['frame_index']!=index:raise ValueError('Observation frame mismatch')
            source_index=require_int(obs['original_detection_index'],'original_detection_index')
            if not 0<=source_index<len(parent['detections']):raise ValueError('Invalid source detection index')
            input_indices.append(source_index)
            det=parent['detections'][source_index]
            if obs['raw_bbox']!=det['bbox_xyxy_pixels']:raise ValueError(f'Raw bbox mismatch {index}/{track_id}')
            if obs['class_id']!=det['class_id'] or obs['class_name']!=det['class_name']:raise ValueError('Raw class changed')
            if obs['confidence']!=det['confidence']:raise ValueError('Raw confidence changed')
            if obs['measurement_provenance']!='retained_phase_2_detection':raise ValueError('Incorrect measurement provenance')
            finite_box(obs['bbox'],'Assigned Kalman bbox')
            box=det['bbox_xyxy_pixels']
            equal_float(obs['center'][0],(box[0]+box[2])/2,'Raw center x',1e-9)
            equal_float(obs['center'][1],(box[1]+box[3])/2,'Raw center y',1e-9)
            if obs['emitted']!=(track_id in emitted_map):raise ValueError('Observation emitted flag mismatch')
            if obs['is_activated']!=snapshot_map[track_id]['is_activated']:raise ValueError('Activation flag mismatch')
            if obs['timestamp_parent_backend_ms']!=parent.get('timestamp_backend_ms'):raise ValueError('Observation timestamp mismatch')
            equal_float(obs['timestamp_estimate_from_index_fps_seconds'],index/fps,'Observation approximate timestamp')
            if histories[track_id] and histories[track_id][-1]['frame_index']>=index:raise ValueError('Nonmonotonic history')
            histories[track_id].append(obs)
        if len(input_indices)!=len(set(input_indices)):raise ValueError('One raw detection assigned to multiple IDs')
        for track_id,obs in emitted_map.items():
            if obs.get('emitted') is not True or obs.get('is_activated') is not True:raise ValueError('Emitted inactive observation')
            box=finite_box(obs['bbox'],'Emitted Kalman box')
            for key,value in assigned_map[track_id].items():
                if key!='bbox' and obs.get(key)!=value:raise ValueError(f'Emitted/assigned field mismatch: {key}')
            for left,right in zip(box,assigned_map[track_id]['bbox']):equal_float(left,right,'Output float32 Kalman serialization',1e-6)
            snapshot=snapshot_map[track_id]
            if snapshot.get('emitted') is not True or snapshot.get('observed_this_frame') is not True:raise ValueError('Emitted snapshot is not a measurement')
            if snapshot['state']!='tracked' or 'tracked' not in snapshot['pool_membership']:raise ValueError('Emitted ID not in tracked state')
        for track_id,snapshot in snapshot_map.items():
            history=histories.get(track_id,[])
            if not history:raise ValueError(f'Snapshot ID {track_id} has no captured assignment')
            last_frame=history[-1]['frame_index']
            missing=index-last_frame
            if snapshot['latest_observed_frame']!=last_frame or snapshot['missing_frame_count']!=missing:raise ValueError(f'Snapshot last/missing incoherent {index}/{track_id}')
            if snapshot['observed_this_frame']!=(track_id in assigned_map):raise ValueError('Snapshot observed flag incoherent')
            if snapshot['emitted']!=(track_id in emitted_map):raise ValueError('Snapshot emitted flag incoherent')
            finite_box(snapshot['bbox_kalman_estimate'],'Lifecycle estimated Kalman bbox')
            expected_provenance='filtered_current_detection' if track_id in assigned_map else 'tracker_estimate_not_current_detection'
            if snapshot['bbox_provenance']!=expected_provenance:raise ValueError('Predicted snapshot incorrectly presented as measured')
            membership=snapshot['pool_membership']
            if len(membership)!=len(set(membership)) or not set(membership)<={'tracked','lost','removed_this_frame'}:raise ValueError('Invalid pool membership')
            if snapshot['state'] not in {'tracked','lost','removed','not_retained','new'}:raise ValueError('Invalid lifecycle state')
            if not membership and snapshot['state']!='not_retained':raise ValueError('No-pool snapshot not marked not_retained')
            if membership and snapshot['state']!=snapshot['library_state']:raise ValueError('Retained state differs from library state')
            # Removed+lost overlap for the removal update is allowed by the authoritative implementation.
            last_snapshots[track_id]={'frame_index':index,**snapshot}
        for event in transitions:
            if event['frame_index']!=index:raise ValueError('Transition frame mismatch')
            lifecycle[event['track_id']].append(event)
        records.append(row)
        emitted_ids.update(emitted_map)
        emitted_count+=len(emitted_map)
        empty_input+=not parent['detections']
        empty_emitted+=not emitted_map
    if len(records)!=len(cache_rows):raise ValueError(f'Expected {len(cache_rows)} output rows, got {len(records)}')
    return {'records':records,'histories':dict(histories),'last_snapshots':last_snapshots,'lifecycle':dict(lifecycle),
            'diagnostics':{'serialized_rows_verified':len(records),'captured_tracker_ids_including_unconfirmed':len(histories),
             'unique_emitted_tracker_ids':len(emitted_ids),'emitted_track_observations':emitted_count,
             'frames_with_zero_cached_detections':empty_input,'frames_with_no_emitted_tracks':empty_emitted}}


def audit_track_summary(path:Path,frame_audit,run_id):
    data=load_json(path)
    if data['video_sha256']!=EXPECTED_VIDEO_SHA256 or data['run_id']!=run_id:raise ValueError('Track summary provenance mismatch')
    tracks=data['tracks']
    lookup={t['track_id']:t for t in tracks}
    if len(lookup)!=len(tracks):raise ValueError('Duplicate summary IDs')
    if set(lookup)!=set(frame_audit['histories']):raise ValueError('Frame/history track-ID sets differ')
    gaps_total=changes_total=never_emitted=0
    for track_id,entry in lookup.items():
        history=frame_audit['histories'][track_id]
        if entry['trajectory']!=history:raise ValueError(f'Summary history differs from frame assignments for ID {track_id}')
        if entry['detection_count']!=len(history):raise ValueError('History/detection counter mismatch')
        emitted_count=sum(obs['emitted'] for obs in history)
        if entry['emitted_observation_count']!=emitted_count:raise ValueError('History/emitted counter mismatch')
        never_emitted+=not emitted_count
        if entry['first_seen_frame']!=history[0]['frame_index'] or entry['last_seen_frame']!=history[-1]['frame_index']:raise ValueError('Track boundaries mismatch')
        for field in ['class_id','class_name','confidence','bbox','center']:
            if entry[field]!=history[-1][field]:raise ValueError(f'Latest track field mismatch: {field}')
        if entry.get('direction') is not None or entry.get('counting_state') is not None:raise ValueError('Later-phase computed state present')
        snapshot=frame_audit['last_snapshots'][track_id]
        if entry['last_lifecycle_frame']!=snapshot['frame_index']:raise ValueError('Last lifecycle frame mismatch')
        if entry['missing_frame_count']!=snapshot['missing_frame_count']:raise ValueError('Final missing count mismatch')
        if entry['final_recorded_state']!=snapshot['state']:
            # A subsequent disappearance transition may be recorded without a new pool snapshot.
            events=frame_audit['lifecycle'].get(track_id,[])
            if not events or events[-1]['state']!=entry['final_recorded_state']:raise ValueError('Final lifecycle state mismatch')
        events=frame_audit['lifecycle'].get(track_id,[])
        if entry['lifecycle']!=events:raise ValueError('Summary/frame lifecycle transition lists differ')
        indices=[o['frame_index'] for o in history]
        if indices!=sorted(set(indices)):raise ValueError('History not strictly increasing')
        gaps=[];changes=[]
        for previous,current in zip(history,history[1:]):
            gap=current['frame_index']-previous['frame_index']-1
            if gap:gaps.append({'previous_observed_frame':previous['frame_index'],'next_observed_frame':current['frame_index'],'missing_frames':gap})
            if current['class_id']!=previous['class_id']:
                changes.append({'frame_index':current['frame_index'],'previous_class_id':previous['class_id'],
                                'new_class_id':current['class_id'],'detection_index':current['original_detection_index']})
        if entry['gap_events']!=gaps:raise ValueError('Gap diagnostic does not match ordered observed frames')
        if entry['class_changes']!=changes:raise ValueError('Class-change diagnostic does not match raw class sequence')
        gaps_total+=len(gaps);changes_total+=len(changes)
    return {'within_id_gap_events':gaps_total,'within_id_raw_class_changes':changes_total,'ids_never_emitted':never_emitted,
            'lifecycle_transition_events':sum(len(v) for v in frame_audit['lifecycle'].values()),
            'interpretation':'Algorithm bookkeeping/diagnostic events, not physical identity errors or traffic totals'}


def audit_provenance(report,source_report_path:Path,cache_path:Path,video_path:Path|None):
    parent=load_json(source_report_path)
    if parent['run_id']!=EXPECTED_SOURCE_RUN_ID or parent['input']['sha256']!=EXPECTED_VIDEO_SHA256:raise ValueError('Wrong retained Phase 2 parent report')
    if report['phase']!=3 or report['input']['parent_run_id']!=EXPECTED_SOURCE_RUN_ID:raise ValueError('Phase3 report/source run mismatch')
    if report['input']['video_sha256']!=EXPECTED_VIDEO_SHA256:raise ValueError('Report input video SHA mismatch')
    if report['input']['frame_detections_sha256']!=EXPECTED_DETECTIONS_SHA256:raise ValueError('Report input cache SHA mismatch')
    if report['input']['detection_report_sha256']!=file_sha256(source_report_path):raise ValueError('Retained Phase2 report file changed/provenance mismatch')
    if file_sha256(cache_path)!=EXPECTED_DETECTIONS_SHA256:raise ValueError('Retained detection cache file changed')
    if report['input']['expected_and_validated_rows']!=EXPECTED_FRAME_COUNT:raise ValueError('Report validated input row count mismatch')
    for key,parentkey in [('parent_input_metadata','input'),('parent_detector_configuration','configuration'),('parent_detector_environment','environment'),('parent_detector_weights','weights')]:
        if report['input'][key]!=parent[parentkey]:raise ValueError(f'Retained parent provenance changed: {key}')
    if report['input']['video_size_bytes']!=parent['input']['file_size_bytes']:raise ValueError('Report source size mismatch')
    if video_path is not None:
        if file_sha256(video_path)!=EXPECTED_VIDEO_SHA256 or video_path.stat().st_size!=parent['input']['file_size_bytes']:raise ValueError('Provided source video identity mismatch')
    return {'parent_report_sha256':file_sha256(source_report_path),'cache_sha256':EXPECTED_DETECTIONS_SHA256,
            'video_sha256':EXPECTED_VIDEO_SHA256,'source_video_bytes_rehashed':video_path is not None}


def audit_runtime_configuration(report,verification_path:Path):
    verified=load_json(verification_path)
    env=report['environment'];tracker=report['tracker']
    if env['package_versions']['ultralytics']!=EXPECTED_ULTRALYTICS or env['package_versions']['lap']!='0.5.13':raise ValueError('Pinned runtime package mismatch')
    if env['association_device']!='cpu' or tracker['association_device']!='cpu':raise ValueError('Actual association device not declared CPU')
    if env['detector_inference_executed'] is not False or env['reid_inference_executed'] is not False:raise ValueError('Later/unrequested inference declared')
    if tracker['class']!='ultralytics.trackers.bot_sort.BOTSORT':raise ValueError('Tracker substituted')
    if tracker['effective_configuration']!=verified['contracts']['experiment_config']:raise ValueError('Baseline configuration differs from verified settings')
    if tracker['published_defaults']!=verified['contracts']['published_defaults']:raise ValueError('Published defaults provenance differs')
    if tracker['explicit_overrides']!={'with_reid':False,'gmc_method':'none'}:raise ValueError('Isolation overrides mismatch')
    if tracker['published_yaml_sha256']!=verified['contracts']['yaml_default_sha256']:raise ValueError('Published YAML identity mismatch')
    if tracker['max_frames_lost']!=30:raise ValueError('Literal pinned frame buffer differs')
    if tracker['class_gate_in_verified_source'] is not False:raise ValueError('Incorrect class-agnostic association description')
    expected={x['path'].removeprefix('ultralytics/'):x['official_sha256'] for x in verified['files']}
    actual={x['path']:x['sha256'] for x in report['tracker_source_verification']}
    if actual!=expected or not all(x['verified'] is True for x in report['tracker_source_verification']):raise ValueError('Runtime tracker source digests mismatch official verification')
    return {'tracker_source_files_verified':len(actual),'association_device':'cpu','with_reid':False,'gmc_method':'none',
            'package_versions':env['package_versions']}


def audit_report_statistics(report,frame_audit,summary_diagnostics):
    expected={**frame_audit['diagnostics'],**{k:v for k,v in summary_diagnostics.items() if k!='interpretation'}}
    for key,value in expected.items():
        if report['diagnostics'][key]!=value:raise ValueError(f'Reported software diagnostic mismatch: {key}')
    if report['diagnostics']['id_switch_count'] is not None or report['diagnostics']['traffic_count'] is not None:raise ValueError('Unsubstantiated identity/traffic totals')
    times=[finite_number(row['tracker_update_wall_seconds'],'tracker update time') for row in frame_audit['records']]
    if any(t<0 for t in times):raise ValueError('Negative observed timing')
    execution=report['execution']
    if execution['frames_processed']!=EXPECTED_FRAME_COUNT or execution['tracker_update_calls']!=EXPECTED_FRAME_COUNT:raise ValueError('Actual call/frame counter mismatch')
    if execution['decoder_read_calls_including_final_probe']!=EXPECTED_FRAME_COUNT+1:raise ValueError('Decode read call total mismatch')
    equal_float(execution['tracker_update_wall_seconds'],sum(times),'Reported tracker time',1e-9)
    equal_float(execution['tracker_update_wall_ms_mean'],sum(times)/len(times)*1000,'Reported mean tracker time',1e-9)
    import statistics
    equal_float(execution['tracker_update_wall_ms_median'],statistics.median(times)*1000,'Reported median tracker time',1e-9)
    if execution['loop_wall_seconds']<execution['tracker_update_wall_seconds']:raise ValueError('Loop timing below contained tracker timing')
    if report['frames_processed']!=EXPECTED_FRAME_COUNT:raise ValueError('Top-level processed count mismatch')
    if report['status']!='completed_cached_sequence_manual_review_pending':raise ValueError('Actual original execution status not completed/pending visual review')
    reject_identity_metrics(report)
    return {**expected,'tracker_update_wall_seconds':sum(times),'interpretation':'Software/association diagnostics, not identity-quality or counting metrics'}


def audit_artifact_hashes(run_dir:Path,report):
    artifacts=report['artifacts'];checks=[]
    for path_key,hash_key in [('track_records','track_records_sha256'),('track_summary','track_summary_sha256'),
                               ('focused_scooter_contact_sheet','focused_scooter_contact_sheet_sha256')]:
        path=run_dir/artifacts[path_key]
        if not path.is_file() or file_sha256(path)!=artifacts[hash_key]:raise ValueError(f'Output artifact hash mismatch: {path_key}')
        checks.append(str(path.relative_to(run_dir)))
    for frame in artifacts['sample_frames']:
        for path_key,hash_key in [('raw','raw_sha256'),('annotated','annotated_sha256')]:
            path=run_dir/frame[path_key]
            if not path.is_file() or file_sha256(path)!=frame[hash_key]:raise ValueError(f'Sample PNG artifact hash mismatch: {frame["frame_index"]}/{path_key}')
            dims=pixel_digest(path)
            if (dims['width'],dims['height'])!=(report['input']['width'],report['input']['height']):raise ValueError('Sample PNG not native dimensions')
            checks.append(str(path.relative_to(run_dir)))
    for burst in artifacts['temporal_bursts']:
        for path_key,hash_key in [('clip','clip_sha256'),('contact_sheet','contact_sheet_sha256')]:
            path=run_dir/burst[path_key]
            if not path.is_file() or file_sha256(path)!=burst[hash_key]:raise ValueError('Temporal artifact hash mismatch')
            checks.append(str(path.relative_to(run_dir)))
    return {'hashed_output_files':len(checks),'paths':checks}


def audit_temporal_and_raw_pixels(run_dir:Path,report,frame_audit,phase2_report_path:Path):
    parent=load_json(phase2_report_path)
    phase2_dir=phase2_report_path.parent
    lookup={item['frame_index']:item for item in report['artifacts']['sample_frames']}
    required=set([0,2570,5140,7711,10281]+list(range(7711,7719)))
    if set(lookup)!=required:raise ValueError('Native representative/focused frame set mismatch')
    raw_matches=[]
    for sample in parent['sample_frames']:
        index=sample['frame_index'];left=run_dir/lookup[index]['raw'];right=phase2_dir/sample['raw']
        if not right.is_file():raise ValueError(f'Phase2 retained raw sample unavailable at {index}')
        left_pixels=pixel_digest(left);right_pixels=pixel_digest(right)
        if left_pixels!=right_pixels:raise ValueError(f'Phase3 raw pixels differ from Phase2 sample at {index}')
        raw_matches.append({'frame_index':index,'raw_rgb_pixels_identical':True,'png_bytes_identical':file_sha256(left)==file_sha256(right)})
    bursts=report['artifacts']['temporal_bursts']
    expected_bursts=[(0,29),(2555,2584),(5125,5154),(7696,7725),(10252,10281)]
    if [(b['start_frame'],b['end_frame']) for b in bursts]!=expected_bursts:raise ValueError('Retained burst boundaries mismatch')
    temporal_records=load_json(run_dir/report['artifacts']['representative_temporal_track_records'])
    expected_records=[row for row in frame_audit['records'] if any(start<=row['frame_index']<=end for start,end in expected_bursts)]
    if temporal_records!=expected_records:raise ValueError('Temporal record subset differs from actual full inherited-state sequence')
    # Decode only rendered MP4 artifacts; this is no source video/model/tracker rerun.
    import cv2
    clips=[]
    for burst in bursts:
        cap=cv2.VideoCapture(str(run_dir/burst['clip']));count=0
        try:
            if not cap.isOpened():raise ValueError('Retained temporal MP4 cannot open')
            while True:
                ok,image=cap.read()
                if not ok:break
                if image.shape[:2]!=(report['input']['height'],report['input']['width']):raise ValueError('Clip not native dimensions')
                count+=1
        finally:cap.release()
        if count!=30 or count!=burst['frame_count']:raise ValueError('Temporal rendered clip frame count mismatch')
        clips.append({'start_frame':burst['start_frame'],'end_frame':burst['end_frame'],'decoded_rendered_frames':count})
    return {'matched_phase2_native_raw_samples':raw_matches,'temporal_subset_records':len(temporal_records),
            'rendered_clips':clips,'scope':'Pixel preservation and rendered artifact completeness only; not physical identity correctness'}


def focused_trace(frame_audit):
    rows=[]
    for row in frame_audit['records']:
        if not 7711<=row['frame_index']<=7718:continue
        rows.append({'frame_index':row['frame_index'],'raw_detections':[{'original_detection_index':i,**d} for i,d in enumerate(row['raw_detections'])],
                     'emitted_tracks':row['emitted_tracks'],'assigned_observations_including_unconfirmed':row['assigned_observations_including_unconfirmed'],
                     'lifecycle_snapshots':row['lifecycle_snapshots'],'lifecycle_transitions':row['lifecycle_transitions']})
    if [r['frame_index'] for r in rows]!=list(range(7711,7719)):raise ValueError('Focused trace not complete')
    return {'scope':'Exact algorithm/detector-link trace for temporal visual review; no physical identity classification inferred','frames':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--phase2-report',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--video',type=Path)
    parser.add_argument('--source-verification',type=Path,default=Path('/tmp/phase3-tracker-verification/source_verification.json'))
    parser.add_argument('--output-dir',type=Path,default=Path('/tmp/phase3-artifact-audit/results'))
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    audit=Audit()
    report=audit.check('phase3_report_json_read',lambda:load_json(args.run_dir/'tracking_report.json'))
    cache_result=audit.check('retained_detection_cache_identity_schema_contiguity',lambda:check_detection_cache(args.cache))
    if report is not None and cache_result is not None:
        cache_rows,cache_diagnostics=cache_result
        audit.diagnostics['retained_input']=cache_diagnostics
        audit.check('input_and_parent_provenance',lambda:audit_provenance(report,args.phase2_report,args.cache,args.video))
        audit.check('pinned_runtime_sources_and_isolated_cpu_configuration',lambda:audit_runtime_configuration(report,args.source_verification))
        artifact_audit=audit.check('all_declared_output_artifact_hashes_and_native_sample_dimensions',lambda:audit_artifact_hashes(args.run_dir,report))
        manifest=audit.check('run_manifest_json_read',lambda:load_json(args.run_dir/'run_manifest.json'))
        if manifest is not None:audit.record('run_manifest_matches_original_tracking_report',manifest==report)
        frame_audit=audit.check('full_frame_records_links_measurement_and_lifecycle_consistency',lambda:audit_frame_records(args.run_dir/report['artifacts']['track_records'],cache_rows,report['input']['fps_from_parent_opencv']))
        if frame_audit is not None:
            summary=audit.check('per_id_histories_counters_gaps_classes_and_lifecycle',lambda:audit_track_summary(args.run_dir/report['artifacts']['track_summary'],frame_audit,report['run_id']))
            if summary is not None:
                statistics=audit.check('reported_diagnostics_and_measured_timing_reconcile',lambda:audit_report_statistics(report,frame_audit,summary))
                audit.diagnostics['tracking_software_diagnostics']=statistics
            audit.check('native_raw_pixel_preservation_and_full_history_temporal_exports',lambda:audit_temporal_and_raw_pixels(args.run_dir,report,frame_audit,args.phase2_report))
            trace=audit.check('focused_trace_7711_7718_complete',lambda:focused_trace(frame_audit))
            if trace is not None:
                (args.output_dir/'focused_track_trace_7711_7718.json').write_text(json.dumps(trace,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    result={'claim_type':'EXPERIMENT_RESULT','scope':'Independent read-only retained-artifact audit. No detector/tracker execution, physical identity labeling or ground-truth evaluation.',
            'created_at_utc':datetime.now(timezone.utc).isoformat(),'run_dir':str(args.run_dir),'run_id':report.get('run_id') if report else None,
            'status':'passed' if not audit.errors else 'failed','checks_passed':sum(c['passed'] for c in audit.checks),'checks_total':len(audit.checks),
            'checks':audit.checks,'errors':audit.errors,'diagnostics':audit.diagnostics,
            'limitations':['Checks establish serialization/provenance/lifecycle consistency, not tracking accuracy or physical identity correctness.',
                           'Source video is only hashed when supplied; only already-rendered temporal MP4 artifacts are decoded.',
                           'No Phase 2 rerun, detector prediction, ReID/GMC inference, geometry, crossing or counting is performed.']}
    output=args.output_dir/'artifact_audit.json'
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'checks_passed':result['checks_passed'],'checks_total':result['checks_total'],'errors':result['errors'],'audit_path':str(output)},indent=2))
    raise SystemExit(0 if not audit.errors else 1)

if __name__=='__main__':main()
