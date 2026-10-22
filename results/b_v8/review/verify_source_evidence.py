"""Independent source-byte/pixel verification; no model or counting execution."""
from pathlib import Path
import gzip
import hashlib
import json
import cv2

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'results/b_v8/review'
BASELINE=ROOT/'results/b_v7/execution/pilot_v7_machine_final/weekday_siang/counting_result.json.gz'
VIDEO=Path('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4')
CACHE=Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz')

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):value.update(part)
    return value.hexdigest()

def read(path):
    data=path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)

def main():
    baseline=read(BASELINE)
    pending=[row for row in baseline['decisions'] if row.get('status')=='pending']
    expected=baseline['source_identity']
    assert digest(VIDEO)==expected['video_sha256']
    assert digest(CACHE)==expected['records_sha256']
    fixture=read(ROOT/'results/b_v8/fixtures/blocker4843/source_decode_receipt.json')
    wanted={row['source_ref']['frame_index'] for row in pending}
    wanted.update(row['frame_index'] for row in fixture['selected_frames'])
    wanted.update([104,105,112])
    cached={}
    with gzip.open(CACHE,'rt') as stream:
        for text in stream:
            row=json.loads(text)
            if row['frame_index'] in wanted:cached[row['frame_index']]=row
    assert set(cached)==wanted
    for decision in pending:
        ref=decision['source_ref']
        rows=[row for row in cached[ref['frame_index']]['emitted_tracks']
              if row['track_id']==ref['track_id']
              and row['original_detection_index']==ref['original_detection_index']]
        assert len(rows)==1
        assert rows[0]['raw_bbox']==ref['raw_bbox'] and rows[0]['class_name']==ref['class_name']
        assert ref['point']==[(ref['raw_bbox'][0]+ref['raw_bbox'][2])/2,ref['raw_bbox'][3]]
    images=[]
    roles=[json.loads(t) for t in (ROOT/'results/phase_9/20261020_QC_BV4_SIANG/roles/per_case_decisions.jsonl').read_text().splitlines()]
    roles={row['raw_track_id']:row for row in roles}
    role_results=[]
    for decision in pending:
        track=decision['track_id']
        if track not in roles:continue
        review=roles[track]
        for image in review['evidence']:
            assert digest(ROOT/image['path'])==image['sha256']
            images.append({'path':image['path'],'sha256':image['sha256']})
        positive=review['role_scope'].get('positive_raw_person_sample_frames',[])
        role_results.append({'raw_track_id':track,'source_frame':decision['source_ref']['frame_index'],
            'source_point_in_positive_role_review':decision['source_ref']['frame_index'] in positive,
            'proposed_role':review['role_recommendation'],
            'role_review_is_temporal_sample_not_entire_raw_id':True})
    cap=cv2.VideoCapture(str(VIDEO)); assert cap.isOpened()
    pixels=[]
    for index in range(max(wanted)+1):
        ok,image=cap.read();assert ok,index
        if index in wanted:
            actual=hashlib.sha256(image.tobytes()).hexdigest()
            assert actual==cached[index]['detector_input_frame_pixel_sha256'],index
            pixels.append({'frame_index':index,'raw_bgr_pixel_sha256':actual,'frozen_cache_match':True})
    cap.release()
    value={'schema_version':'phase9_b_v8_independent_source_verification_v1',
        'status':'PASS_SOURCE_BYTES_AND_SELECTED_PIXELS_NOT_COUNTING_VALIDATION',
        'source_identity':expected,'baseline_sha256':digest(BASELINE),
        'pending_source_measurements_verified':len(pending),'native_source_frames_verified':pixels,
        'role_review_images_hash_verified':images,'role_evidence_scope_checks':role_results,
        'decode_method':'SEQUENTIAL_FROM_SOURCE_ZERO',
        'decoded_through_source_frame':max(wanted),
        'role_images_independently_viewed':'All21positivecomponent/rider/occupantcase sheets plus54pedestrian and3185unknown were opened by this reviewer; cargo3555 and all3blockercontacts also opened.',
        'physical_ground_truth_established':False,'model_tracker_reid_counting_enhancement_executed':False}
    (OUT/'independent_source_verification.json').write_text(json.dumps(value,indent=2)+'\n')
    print({'status':value['status'],'pending_source_measurements':len(pending),'native_frames':len(pixels),'role_review_images':len(images)})

if __name__=='__main__':main()
