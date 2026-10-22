import cv2,json,hashlib,numpy as np
from pathlib import Path
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC/results/phase_9/20261020_QC_BV4_SIANG/unmatched');specs={'motor49':[24,26,28,29,30,31,32,33,34,36,40,44],'motor2643':[4250,4255,4260,4265,4270,4275,4280,4282,4283,4285,4290,4300],'motor3255':[5455,5460,5465,5470,5475,5478,5479,5480,5485,5490,5500,5510],'motor4552':[7600,7605,7610,7615,7620,7625,7630,7636,7637,7640,7650,7660]};ids={f for a in specs.values() for f in a};cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');images={};i=0
while i<=max(ids):
 ok,im=cap.read()
 if not ok:break
 if i in ids:images[i]=im.copy()
 i+=1
cap.release();metadata=[]
for name,fs in specs.items():
 canvas=np.full((2040,1920,3),250,np.uint8)
 for p,f in enumerate(fs):
  y,x=divmod(p,3);canvas[y*510+30:(y+1)*510,x*640:(x+1)*640]=images[f];cv2.putText(canvas,f'RAW f{f}',(x*640+5,y*510+22),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,0),2);cv2.imwrite(str(R/'evidence'/f'frame-{f:06d}.png'),images[f]);metadata.append({'frame_index':f,'bgr_sha256':hashlib.sha256(images[f].tobytes()).hexdigest(),'sheet':name+'.jpg'})
 cv2.imwrite(str(R/'evidence'/f'{name}.jpg'),canvas,[cv2.IMWRITE_JPEG_QUALITY,95])
(R/'evidence'/'dense_candidates_manifest.json').write_text(json.dumps({'not_a_counting_replay':True,'selection':'After raw-first global review, diagnostic source pairs used only to target additional pixel audit','frames':metadata},indent=2)+'\n')
