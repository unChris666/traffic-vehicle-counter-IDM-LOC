from pathlib import Path
import json,gzip,hashlib,sys
from collections import Counter
import cv2,numpy as np
sys.path.insert(0,'notebooks')
from phase_9_p0_qc_compare import SourceIndex,source_key
root=Path('results/b_v5/verification/pilot_v1_independent_qc');root.mkdir(parents=True,exist_ok=True);(root/'evidence').mkdir(exist_ok=True)
old=json.loads(gzip.decompress(Path('results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz').read_bytes()))
new=json.loads(gzip.decompress(Path('results/b_v5/execution/pilot_p0_v1/weekday_siang/counting_result.json.gz').read_bytes()))
idx=SourceIndex(new);lost=[];wanted=set()
for event in old['events']:
 if not event['evidence']['measured_crossing']:continue
 pairs=[{source_key(pair['first']),source_key(pair['second'])} for pair in event['evidence']['crossing_pairs']]
 matches=[n for n,refs in zip(new['events'],idx.event_refs) if any(pair<=refs for pair in pairs)]
 if matches:continue
 refs=event['evidence']['source_refs'];pair=event['evidence']['crossing_pairs'][-1]
 chosen=[refs[0],pair['first'],pair['second'],refs[-1]]
 for ref in chosen:wanted.add(ref['frame_index'])
 cancelled=[]
 for n in new['cancelled_events']:
  keys=set(source_key(r) for r in n['evidence']['source_refs'])
  if any(pair<=keys for pair in pairs):cancelled.append({'event_id':n['event_id'],'track_id':n['track_id'],'activation_frame':n['activation_frame'],'reason':n.get('cancellation_reason')})
 lost.append({'old_event_id':event['event_id'],'raw_track_id':event['track_id'],'old_category':event['category'],'old_direction':event['direction'],'old_activation_frame':event['activation_frame'],'old_measured_pairs':[[pair['first']['frame_index'],pair['second']['frame_index']] for pair in event['evidence']['crossing_pairs']],'new_cancelled_counterparts':cancelled,'new_active_partial_source_counterparts':idx.candidates(event['evidence']),'selected_refs':chosen,'physical_qc_status':'NOT_YET_ADJUDICATED_FROM_NEW_IMAGES'})
cache=next(Path('/tmp/qc-donor').rglob('track_records.jsonl.gz'))
proof={}
with gzip.open(cache,'rt') as stream:
 for line in stream:
  row=json.loads(line)
  if row['frame_index'] in wanted:proof[row['frame_index']]=row
cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');images={};receipts=[];frame=0
while True:
 ok,image=cap.read()
 if not ok:break
 if frame in wanted:
  sha=hashlib.sha256(image.tobytes()).hexdigest();assert sha==proof[frame]['detector_input_frame_pixel_sha256'],frame
  path=root/'evidence'/f'native-f{frame:06d}.png';cv2.imwrite(str(path),image);images[frame]=image
  receipts.append({'frame_index':frame,'raw_bgr_pixel_sha256':sha,'native_png_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'path':str(path)})
 frame+=1
cap.release();assert wanted==set(images)
for case in lost:
 panels=[]
 for ref in case['selected_refs']:
  image=images[ref['frame_index']].copy();x1,y1,x2,y2=map(round,ref['raw_bbox']);cv2.rectangle(image,(x1,y1),(x2,y2),(0,255,0),2);cv2.line(image,(2,430),(617,1),(0,255,255),1)
  cv2.rectangle(image,(0,0),(640,32),(0,0,0),-1);cv2.putText(image,f'raw{ref["track_id"]} f{ref["frame_index"]} {ref["class_name"]}',(8,23),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1)
  panels.append(image)
 sheet=np.vstack([np.hstack(panels[:2]),np.hstack(panels[2:])]);path=root/'evidence'/f'lost-raw{case["raw_track_id"]}-f{case["old_activation_frame"]}.jpg';cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,90]);case['evidence_image']=str(path);case['evidence_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
(root/'source_pixel_proofs.json').write_text(json.dumps({'video_sha256':old['source_identity']['video_sha256'],'cache_sha256':old['source_identity']['records_sha256'],'native_images':receipts,'source_frame_count_decoded':frame,'no_inference':True},indent=2))
(root/'lost_measured_source_pairs.json').write_text(json.dumps({'old_measured':121,'new_measured':97,'old_measured_events_with_no_exact_pair_in_new_active_event':len(lost),'rows':lost,'claim_type':'DOCUMENTARY_PAIR_COVERAGE_NOT_PHYSICAL_COUNT_ACCURACY'},indent=2))
print(json.dumps({'lost_old_exact_pairs':len(lost),'native_frames_verified':len(images),'output':str(root)}))
