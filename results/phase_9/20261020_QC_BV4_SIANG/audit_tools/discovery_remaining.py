import cv2,gzip,hashlib,json,math
from pathlib import Path
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC');O=R/'results/phase_9/20261020_QC_BV4_SIANG/unmatched';out=O/'evidence';video='/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4'
cases={2771:4509,4614:7651,4709:7711}
samples={t:[f+v for v in [-20,-10,-5,-2,-1,0,1,2,5,10,20,30]] for t,f in cases.items()}
needed={v for s in samples.values() for v in s};records={}
with gzip.open(next(Path('/tmp/qc-donor').rglob('track_records.jsonl.gz')),'rt') as f:
 for line in f:
  row=json.loads(line)
  if row['frame_index'] in needed:records[row['frame_index']]=row
def iou(a,b):
 w=max(0,min(a[2],b[2])-max(a[0],b[0]));h=max(0,min(a[3],b[3])-max(a[1],b[1]));i=w*h;return i/max(1,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i)
cap=cv2.VideoCapture(video);images={};proof=[];frame=0
while frame<=max(needed):
 ok,img=cap.read()
 if not ok:raise RuntimeError(frame)
 if frame in needed:
  digest=hashlib.sha256(img.tobytes()).hexdigest();assert digest==records[frame]['detector_input_frame_pixel_sha256'];images[frame]=img.copy();path=out/f'root-frame-{frame:06d}.png';cv2.imwrite(str(path),img);proof.append({'frame_index':frame,'source_bgr_sha256':digest,'native_png_path':str(path.relative_to(R)),'native_png_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cache_pixel_match':True})
 frame+=1
cap.release();summaries=[]
for t,fs in samples.items():
 cells=[]
 for f in fs:
  img=images[f].copy();obs=records[f]['emitted_tracks'];target=next((o for o in obs if o['track_id']==t),None);rows=[]
  if target:
   for o in obs:
    if o['track_id']==t or (o['class_name'] in ['motorcycle','car','truck','bus'] and iou(target['raw_bbox'],o['raw_bbox'])>.3):
     box=list(map(round,o['raw_bbox']));color=(0,180,255) if o['track_id']==t else(255,255,0);cv2.rectangle(img,tuple(box[:2]),tuple(box[2:]),color,2);cv2.putText(img,f"{o['track_id']} {o['class_name']}",(max(0,box[0]),max(14,box[1]-4)),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1);rows.append({k:o[k] for k in ['track_id','class_name','raw_bbox']})
  cell=cv2.copyMakeBorder(img,32,0,0,0,cv2.BORDER_CONSTANT,value=(20,20,20));cv2.putText(cell,f'raw{t} | source f{f}'+(' TARGET ABSENT' if target is None else''),(6,22),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);cells.append(cell);summaries.append({'target':t,'frame_index':f,'observations':rows})
 import numpy as np
 sheet=np.vstack([np.hstack(cells[i:i+3]) for i in range(0,len(cells),3)]);cv2.imwrite(str(out/f'root-diagnostic-{t}.jpg'),sheet,[cv2.IMWRITE_JPEG_QUALITY,90])
(out/'root_remaining_pixel_checks.json').write_text(json.dumps({'frames':proof,'observations':summaries},indent=2)+'\n');print({'source_frames':len(proof),'sheets':len(cases)})
