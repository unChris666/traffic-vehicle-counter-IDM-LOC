from pathlib import Path
import cv2,json,hashlib,numpy as np
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC/results/phase_9/20261020_QC_BV4_SIANG/unmatched');specs={'grey-mpv':[4384,4390,4395,4400,4401,4402,4408,4415,4420,4430,4434,4445], 'box-motor':list(range(6200,6360,10)), 'yellow-ped':list(range(7290,7430,10)), 'white-car':list(range(2440,2600,10)),'end-car':list(range(9040,9128,10))}
wanted={i for v in specs.values() for i in v};cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');f=0;imgs={}
while f<=max(wanted):
 ok,img=cap.read()
 if not ok:break
 if f in wanted:imgs[f]=img.copy()
 f+=1
cap.release();meta=[]
for name,ids in specs.items():
 for start in range(0,len(ids),12):
  subset=ids[start:start+12];canvas=np.full((4*510,3*640,3),250,np.uint8)
  for n,f in enumerate(subset):
   row,col=divmod(n,3);canvas[row*510+30:(row+1)*510,col*640:(col+1)*640]=imgs[f];cv2.putText(canvas,f'RAW f{f} ({f/29.781214:.3f}s)',(col*640+5,row*510+22),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,0),2);meta.append({'frame_index':f,'bgr_sha256':hashlib.sha256(imgs[f].tobytes()).hexdigest(),'sheet':f'{name}-{start//12+1}.jpg'})
   cv2.imwrite(str(R/'evidence'/f'frame-{f:06d}.png'),imgs[f])
  cv2.imwrite(str(R/'evidence'/f'{name}-{start//12+1}.jpg'),canvas,[cv2.IMWRITE_JPEG_QUALITY,95])
(R/'evidence'/'adaptive_manifest.json').write_text(json.dumps({'decode':'SEQUENTIAL_FROM_ZERO','frames':meta},indent=2)+'\n')
print(len(meta))
