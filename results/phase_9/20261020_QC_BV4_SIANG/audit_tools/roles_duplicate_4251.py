import cv2,json,gzip,hashlib,numpy as np
from pathlib import Path
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');E=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/roles/evidence';wanted=[7360,7363,7367,7369,7370,7371,7374,7379];cache=next(Path('/tmp/qc-donor').rglob('track_records.jsonl.gz'));records={}
with gzip.open(cache,'rt') as f:
 for line in f:
  r=json.loads(line)
  if r['frame_index'] in wanted:records[r['frame_index']]=r
cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');panels=[];manifest=[]
for f in range(7380):
 ok,image=cap.read();assert ok
 if f in wanted:
  assert hashlib.sha256(image.tobytes()).hexdigest()==records[f]['detector_input_frame_pixel_sha256'];p=E/'native'/f'frame-{f:06d}.png';cv2.imwrite(str(p),image);canvas=np.zeros((520,640,3),np.uint8);canvas[40:]=image;targets=[]
  for t in records[f]['emitted_tracks']:
   if t['track_id'] in [4251,4281,4244]:
    b=list(map(int,t['raw_bbox']));color=(255,0,255) if t['track_id']==4244 else (0,255,255) if t['track_id']==4251 else(255,255,0);cv2.rectangle(canvas,(b[0],b[1]+40),(b[2],b[3]+40),color,2);cv2.putText(canvas,str(t['track_id']),(b[0],b[1]+35),cv2.FONT_HERSHEY_SIMPLEX,.5,color,1);targets.append(t)
  cv2.putText(canvas,f'f{f} | 4251yellow/4281cyan/4244magenta',(8,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);panels.append(canvas);manifest.append({'frame_index':f,'path':str(p.relative_to(ROOT)),'pixel_sha256':hashlib.sha256(image.tobytes()).hexdigest(),'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_observations':targets})
cap.release();sheet=np.vstack([np.hstack(panels[i:i+2]) for i in range(0,len(panels),2)]);cv2.imwrite(str(E/'accepted-4251-4281-comparison.jpg'),sheet,[cv2.IMWRITE_JPEG_QUALITY,95]);(E/'accepted-4251-4281-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('saved')
