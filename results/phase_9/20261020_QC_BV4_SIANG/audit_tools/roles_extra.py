import json,gzip,hashlib,cv2,numpy as np
from pathlib import Path
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/roles';E=OUT/'evidence';cache=next(Path('/tmp/qc-donor').rglob('track_records.jsonl.gz'))
requests={2958:[4818,4840,4860,4880,4965,4970,4974,4980],3185:[5394,5400,5410,5420,5500,5579],4725:[7733,7750,7760,7780,7800,7885]};needed={x for frames in requests.values() for x in frames};records={}
with gzip.open(cache,'rt') as f:
 for line in f:
  r=json.loads(line)
  if r['frame_index'] in needed:records[r['frame_index']]=r
cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');images={};manifest=[]
for f in range(9128):
 ok,image=cap.read();assert ok
 if f in needed:
  assert hashlib.sha256(image.tobytes()).hexdigest()==records[f]['detector_input_frame_pixel_sha256'];p=E/'native'/f'frame-{f:06d}.png';cv2.imwrite(str(p),image);images[f]=image;manifest.append({'frame_index':f,'native_path':str(p.relative_to(ROOT)),'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pixel_sha256':hashlib.sha256(image.tobytes()).hexdigest(),'cache_pixel_match':True})
cap.release()
for tid,frames in requests.items():
 panels=[]
 for f in frames:
  image=images[f];o=next((t for t in records[f]['emitted_tracks'] if t['track_id']==tid),None);panel=np.full((510,640,3),35,np.uint8);panel[30:]=image
  if o:
   x1,y1,x2,y2=map(int,o['raw_bbox']);cv2.rectangle(panel,(x1,y1+30),(x2,y2+30),(255,0,255),2)
  cv2.putText(panel,f'raw{tid} f{f} {o["class_name"] if o else "NO TRACK"}',(8,20),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);panels.append(panel)
 while len(panels)%2:panels.append(np.full((510,640,3),35,np.uint8))
 sheet=np.vstack([np.hstack(panels[i:i+2]) for i in range(0,len(panels),2)]);cv2.imwrite(str(E/f'role-extra-raw{tid}.jpg'),sheet,[cv2.IMWRITE_JPEG_QUALITY,95])
(E/'extra_manifest.json').write_text(json.dumps({'frames':manifest,'requests':requests},indent=2)+'\n');print('extra prepared')
