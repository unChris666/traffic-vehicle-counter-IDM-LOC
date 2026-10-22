from pathlib import Path
import cv2,json,hashlib
import numpy as np
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC/results/phase_9/20261020_QC_BV4_SIANG/unmatched')
video=Path('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4')
specs={'begin':list(range(0,360,15)), 'middle':list(range(4400,4760,15)),'late':list(range(8640,9000,15))}
wanted={i for v in specs.values() for i in v};cap=cv2.VideoCapture(str(video)); native={};idx=0
while idx<=max(wanted):
 ok,img=cap.read()
 if not ok:break
 if idx in wanted:native[idx]=img.copy()
 idx+=1
cap.release(); manifest=[]
for label,indices in specs.items():
 for batch in range(0,len(indices),12):
  subset=indices[batch:batch+12]; canvas=np.full((4*510,3*640,3),245,np.uint8)
  for pos,f in enumerate(subset):
   row,col=divmod(pos,3);img=native[f];canvas[row*510+30:row*510+510,col*640:(col+1)*640]=img
   cv2.putText(canvas,f'RAW SOURCE f{f} t={f/29.781214:.3f}s',(col*640+8,row*510+22),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,0),2)
   manifest.append({'frame_index':f,'bgr_sha256':hashlib.sha256(img.tobytes()).hexdigest(),'sheet':f'{label}-{batch//12+1}.jpg','review_status':'NOT_YET_VIEWED'})
  cv2.imwrite(str(ROOT/'evidence'/f'{label}-{batch//12+1}.jpg'),canvas,[cv2.IMWRITE_JPEG_QUALITY,94])
(ROOT/'evidence'/'source_frame_manifest.json').write_text(json.dumps({'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'decode':'SEQUENTIAL_FROM_ZERO','frames':manifest},indent=2)+'\n')
print(len(manifest))
