import cv2,json,gzip,numpy as np,hashlib
from pathlib import Path
r=Path('/workspace/traffic-vehicle-counter-IDM-LOC');out=r/'results/phase_9/20261020_QC_BV4_SIANG/identity/evidence';seq={6:[1434,1460,1480,1500,1510,1511,1512,1520,1530,1540,1550,1560,1570],28:[7263,7264,7290,7310,7330,7340,7350,7353,7360,7370,7380,7390,7410],30:[7769,7790,7809,7820,7840,7860,7880,7890,7900,7907,7920,7930,7940,7960]};need=set(f for v in seq.values() for f in v);records={}
with gzip.open('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz','rt') as f:
 for line in f:
  d=json.loads(line)
  if d['frame_index'] in need:records[d['frame_index']]=d
cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');images={};checks=[];idx=0
while True:
 ok,img=cap.read()
 if not ok:break
 if idx in need:
  sha=hashlib.sha256(img.tobytes()).hexdigest();assert sha==records[idx]['detector_input_frame_pixel_sha256'];images[idx]=img;checks.append({'frame_index':idx,'source_bgr_sha256':sha,'match':True})
 idx+=1
cap.release()
for case,frames in seq.items():
 cells=[]
 for frame in frames:
  raw=images[frame];img=raw.copy()
  for o in records[frame]['emitted_tracks']:
   if o['class_name'] not in ['motorcycle','person','car','truck','bus']:continue
   if o['raw_bbox'][2]-o['raw_bbox'][0]>250:continue
   x1,y1,x2,y2=map(int,o['raw_bbox']);col=(0,255,255)if o['class_name']!='person' else(255,0,255);cv2.rectangle(img,(x1,y1),(x2,y2),col,1);cv2.putText(img,str(o['track_id']),(x1,max(y1,12)),cv2.FONT_HERSHEY_SIMPLEX,.40,col,1,cv2.LINE_AA)
  canvas=np.zeros((505,640,3),dtype=np.uint8);canvas[25:]=img;cv2.putText(canvas,f'case{case} f{frame}',(5,19),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1,cv2.LINE_AA);cells.append(canvas)
 sheet=np.zeros((((len(cells)+2)//3)*505,1920,3),dtype=np.uint8)
 for i,img in enumerate(cells):sheet[i//3*505:(i//3+1)*505,i%3*640:(i%3+1)*640]=img
 p=out/f'IDENTITY-{case:02d}-focus.jpg';cv2.imwrite(str(p),sheet,[cv2.IMWRITE_JPEG_QUALITY,97])
(r/'results/phase_9/20261020_QC_BV4_SIANG/identity/focus_pixel_checks.json').write_text(json.dumps({'checks':checks,'count':len(checks)},indent=2)+'\n')
