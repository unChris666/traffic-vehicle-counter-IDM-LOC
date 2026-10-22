from pathlib import Path
import cv2,json,hashlib
import numpy as np
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC/results/phase_9/20261020_QC_BV4_SIANG/unmatched');ids=list(range(0,9128,60));cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');images={};f=0
while f<=max(ids):
 ok,img=cap.read()
 if not ok:break
 if f in ids:images[f]=img.copy()
 f+=1
cap.release();rows=[]
for n in range(0,len(ids),20):
 block=ids[n:n+20];canvas=np.full((4*265,5*320,3),250,np.uint8)
 for i,idx in enumerate(block):
  y,x=divmod(i,5);img=images[idx];canvas[y*265+25:(y+1)*265,x*320:(x+1)*320]=cv2.resize(img,(320,240));cv2.putText(canvas,f'f{idx} t{idx/29.781214:.1f}s',(x*320+3,y*265+18),cv2.FONT_HERSHEY_SIMPLEX,.52,(0,0,0),1);rows.append({'frame_index':idx,'bgr_sha256':hashlib.sha256(img.tobytes()).hexdigest(),'sheet':f'global-{n//20+1}.jpg','review_status':'NOT_YET_VIEWED'})
 cv2.imwrite(str(R/'evidence'/f'global-{n//20+1}.jpg'),canvas,[cv2.IMWRITE_JPEG_QUALITY,95])
(R/'evidence'/'global_raw_manifest.json').write_text(json.dumps({'decode':'SEQUENTIAL_FROM_ZERO','sampling_interval_source_frames':60,'frames':rows},indent=2)+'\n');print(len(ids))
