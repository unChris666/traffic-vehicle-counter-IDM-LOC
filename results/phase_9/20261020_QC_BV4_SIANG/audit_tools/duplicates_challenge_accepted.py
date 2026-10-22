import cv2,gzip,json,hashlib,numpy as np
from pathlib import Path
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/duplicates'; groups={2584:[4143,4213],2697:[4384,4401],3512:[6190,6236],3761:[6604]}; wanted=set(f for fs in groups.values() for f in fs);rec={}
with gzip.open('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz','rt') as f:
 for l in f:
  r=json.loads(l)
  if r['frame_index'] in wanted:rec[r['frame_index']]=r
ims={};cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');i=0
while True:
 ok,im=cap.read()
 if not ok:break
 if i in wanted:assert hashlib.sha256(im.tobytes()).hexdigest()==rec[i]['detector_input_frame_pixel_sha256'];ims[i]=im
 i+=1
cap.release();m=[]
for t,fs in groups.items():
 sh=np.full((520,640*len(fs),3),30,np.uint8)
 for idx,f in enumerate(fs):
  raw=ims[f];im=raw.copy();name=f'accepted-challenge-raw{t}-f{f}.png';p=OUT/'evidence'/name;cv2.imwrite(str(p),raw)
  for o in rec[f]['emitted_tracks']:
   if o['track_id'] in {t,3738}:
    b=list(map(round,o['raw_bbox']));cv2.rectangle(im,tuple(b[:2]),tuple(b[2:]),(0,255,255),2);cv2.putText(im,f"{o['track_id']} {o['class_name']}",(b[0],max(16,b[1]-3)),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,255),1)
  sh[:480,idx*640:(idx+1)*640]=im;cv2.putText(sh,f'f{f} target raw{t}',(idx*640+4,507),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);m.append({'frame_index':f,'target_raw_id':t,'source_bgr_sha256':hashlib.sha256(raw.tobytes()).hexdigest(),'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'path':str(p.relative_to(OUT)),'cache_pixel_match':True})
 cv2.imwrite(str(OUT/'evidence'/f'accepted-challenge-{t}.jpg'),sh,[cv2.IMWRITE_JPEG_QUALITY,96])
(OUT/'evidence/accepted_challenge_manifest.json').write_text(json.dumps(m,indent=2))
print('challengeimages',len(m))
