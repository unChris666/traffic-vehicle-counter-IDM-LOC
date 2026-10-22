from pathlib import Path
import cv2,json,hashlib,gzip,numpy as np,math
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC');O=R/'results/phase_9/20261020_QC_BV4_SIANG/removed_inferences';plan=json.loads((O/'visual_plan.json').read_text());cases=[p for p in plan if p['stratum']=='ALL_NEW_ONLY_INFERRED'];selected={}
for p in cases:
 end=max(p['source_frames']);p['followup_frames']=[end+d for d in [0,15,30,45,60,75,90,120,150,180,210,240]]
 for f in p['followup_frames']:selected[f]=None
records={}
with gzip.open('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz','rt') as h:
 for line in h:
  d=json.loads(line)
  if d['frame_index'] in selected:records[d['frame_index']]=d
c=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');frame=0;images={};receipts=[]
while True:
 ok,im=c.read()
 if not ok:break
 if frame in selected:
  sha=hashlib.sha256(im.tobytes()).hexdigest();assert sha==records[frame]['detector_input_frame_pixel_sha256'];images[frame]=im;p=O/'evidence'/f'native-{frame:06d}.png';assert cv2.imwrite(str(p),im);receipts.append({'frame_index':frame,'source_bgr_sha256':sha,'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'retained_path':str(p.relative_to(R))})
 frame+=1
c.release();assert frame==9128
for p in cases:
 cells=[]
 for f in p['followup_frames']:
  im=images[f].copy();head=np.full((32,640,3),255,np.uint8);cv2.putText(head,f"{p['case_id']} FOLLOWUP source f{f}",(4,22),cv2.FONT_HERSHEY_SIMPLEX,.46,(0,0,0),1,cv2.LINE_AA)
  for t in records[f]['emitted_tracks']:
   if t['class_name'] not in {'car','truck','motorcycle','bus'}:continue
   x,y,x2,y2=[round(v) for v in t['raw_bbox']];cv2.rectangle(im,(x,y),(x2,y2),(255,0,0),1);cv2.putText(im,f"{t['track_id']} {t['class_name']}",(max(0,min(570,x)),max(12,y-3)),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,0,0),1,cv2.LINE_AA)
  cells.append(np.vstack((head,im)))
 canvas=np.vstack([np.hstack(cells[i:i+3]) for i in range(0,len(cells),3)]);path=O/'evidence'/(p['case_id']+'-followup.jpg');assert cv2.imwrite(str(path),canvas,[cv2.IMWRITE_JPEG_QUALITY,94]);p['followup_contact_sheet']=str(path.relative_to(R));p['followup_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
(O/'followup_plan.json').write_text(json.dumps(cases,indent=2)+'\n');(O/'evidence/followup_frame_receipts.json').write_text(json.dumps({'source_frames_decoded':frame,'source_frames_retained':len(receipts),'frames':receipts},indent=2)+'\n');print(len(receipts),len(cases))
