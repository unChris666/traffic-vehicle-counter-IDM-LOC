from pathlib import Path
import cv2,json,gzip,hashlib,math
from collections import defaultdict
root=Path('/workspace/traffic-vehicle-counter-IDM-LOC');out=root/'results/phase_9/20261020_QC_BV4_SIANG/accepted_timeout_control';out.mkdir(parents=True,exist_ok=True);ev=out/'evidence';ev.mkdir(exist_ok=True)
video=Path('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');cache=Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz');data=json.loads(gzip.decompress((root/'results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz').read_bytes())); events=[e for e in data['events'] if e['route']=='ESTIMATED_TIMEOUT'];tracks={e['track_id'] for e in events};by=defaultdict(list);pixel={}
with gzip.open(cache,'rt') as f:
 for line in f:
  row=json.loads(line);pixel[row['frame_index']]=row['detector_input_frame_pixel_sha256']
  for obs in row['emitted_tracks']:
   if obs['track_id'] in tracks:by[obs['track_id']].append(obs)
plans=[];wanted=set()
for i,e in enumerate(events,1):
 track=e['track_id'];start=e['evidence']['source_frames'][0];last=max(e['evidence']['source_frames']);obs=[o for o in by[track] if start<=o['frame_index']<=last];choices=[max(0,start-30),start,obs[len(obs)//3]['frame_index'],obs[(2*len(obs))//3]['frame_index'],last,min(9127,last+20),min(9127,last+40),min(9127,last+80)];boxes=[o['raw_bbox'] for o in obs];x1=min(b[0] for b in boxes);y1=min(b[1] for b in boxes);x2=max(b[2] for b in boxes);y2=max(b[3] for b in boxes);w=max(150,x2-x1+80);h=max(112.5,y2-y1+60);w=max(w,h*4/3);h=w*3/4;cx=(x1+x2)/2;cy=(y1+y2)/2;w=min(640,w);h=min(480,h);lx=max(0,min(640-w,cx-w/2));ly=max(0,min(480-h,cy-h/2));crop=[int(lx),int(ly),int(lx+w),int(ly+h)];p={'case_id':f'TIMEOUT-{i:02d}','event_id':e['event_id'],'display_id':e['display_id'],'track_id':track,'category':e['category'],'direction':e['direction'],'activation_frame':e['activation_frame'],'first_source_frame':start,'last_source_frame':last,'frames_review_planned':choices,'crop_xyxy':crop,'event':e,'observations':obs};plans.append(p);wanted.update(choices)
frames={};checks=[];capture=cv2.VideoCapture(str(video));idx=0
while True:
 ok,img=capture.read()
 if not ok:break
 if idx in wanted:
  actual=hashlib.sha256(img.tobytes()).hexdigest();assert actual==pixel[idx],(idx,actual,pixel[idx]);frames[idx]=img;checks.append({'frame_index':idx,'bgr_pixel_sha256':actual,'retained_detector_input_pixel_sha256':pixel[idx],'status':'PASS'})
 idx+=1
capture.release();assert idx==9128
artifacts=[]
for p in plans:
 header=55;sheet=__import__('numpy').full((header+960,1280,3),24,dtype='uint8');cv2.putText(sheet,f"{p['case_id']} {p['display_id']} raw{p['track_id']} {p['category']} {p['direction']} timeout@{p['activation_frame']}",(8,24),cv2.FONT_HERSHEY_SIMPLEX,.62,(255,255,255),1,cv2.LINE_AA);cv2.putText(sheet,'Crops same source region. First/last source full frame below. Orange bbox=raw target',(8,46),cv2.FONT_HERSHEY_SIMPLEX,.52,(255,255,255),1,cv2.LINE_AA);lookup={o['frame_index']:o for o in by[p['track_id']]};a,b,c,d=p['crop_xyxy']
 for j,f in enumerate(p['frames_review_planned']):
  im=frames[f].copy();o=lookup.get(f)
  if o:
   box=[round(q) for q in o['raw_bbox']];cv2.rectangle(im,(box[0],box[1]),(box[2],box[3]),(0,165,255),2)
  crop=cv2.resize(im[b:d,a:c],(320,240));cv2.rectangle(crop,(0,0),(320,23),(0,0,0),-1);cv2.putText(crop,f"f{f} "+(o['class_name'] if o else 'target not emitted'),(4,17),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1,cv2.LINE_AA);y=header+(j//4)*240;x=(j%4)*320;sheet[y:y+240,x:x+320]=crop
 for j,f in enumerate([p['first_source_frame'],p['last_source_frame']]):
  im=frames[f].copy();o=lookup.get(f)
  if o:
   box=[round(q) for q in o['raw_bbox']];cv2.rectangle(im,(box[0],box[1]),(box[2],box[3]),(0,165,255),2)
  sheet[header+480:header+960,j*640:j*640+640]=im
 path=ev/f"{p['case_id']}-raw{p['track_id']}.jpg";assert cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,94]);artifacts.append({'path':str(path.relative_to(out)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_frames':p['frames_review_planned'],'crop_xyxy':p['crop_xyxy'],'resize':'320x240 crop cells; 640x480 full first/last','derivation':'SOURCE_DECODE_WITH_RAW_TARGET_BBOX_CONTEXT_JPEG_CONTACT_SHEET_NOT_MODEL_RUN'})
(out/'selected_events.json').write_text(json.dumps(plans,indent=2)+'\n');(ev/'manifest.json').write_text(json.dumps({'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'records_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),'frames_decoded':idx,'pixel_checks':checks,'artifacts':artifacts},indent=2)+'\n');print({'events':len(plans),'unique_source_frames':len(frames),'decoded':idx,'output':str(out)})
