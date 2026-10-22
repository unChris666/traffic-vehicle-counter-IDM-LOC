import cv2,gzip,json,hashlib,numpy as np
from pathlib import Path
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/duplicates';fs=[4273,4401,4428,4434,4461,6296];wanted={2584,2615,2697,2706,3512,3582};recs={}
with gzip.open('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz','rt') as f:
 for l in f:
  r=json.loads(l)
  if r['frame_index'] in fs:recs[r['frame_index']]=r
ims={};cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');i=0;manifest=[]
while True:
 ok,im=cap.read()
 if not ok:break
 if i in fs:
  sha=hashlib.sha256(im.tobytes()).hexdigest();assert sha==recs[i]['detector_input_frame_pixel_sha256'];ims[i]=im;path=OUT/'evidence'/f'accepted-confirm-f{i:06d}.png';cv2.imwrite(str(path),im);manifest.append({'frame_index':i,'path':str(path.relative_to(OUT)),'source_bgr_sha256':sha,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cache_pixel_match':True})
 i+=1
cap.release();sheet=np.full((3*500,1280,3),30,np.uint8)
for ix,f in enumerate(fs):
 im=ims[f].copy();labels=[]
 for o in recs[f]['emitted_tracks']:
  if o['track_id'] in wanted:
   b=list(map(round,o['raw_bbox']));c=(0,255,255) if o['track_id'] in {2697,2584,3512} else (255,0,255);cv2.rectangle(im,tuple(b[:2]),tuple(b[2:]),c,2);labels.append(f"{o['track_id']}:{o['class_name']}")
 yy=(ix//2)*500;xx=(ix%2)*640;sheet[yy:yy+480,xx:xx+640]=im;cv2.putText(sheet,f"f{f} "+','.join(labels),(xx+4,yy+496),cv2.FONT_HERSHEY_SIMPLEX,.43,(255,255,255),1)
cv2.imwrite(str(OUT/'evidence/accepted-confirm-sheet.jpg'),sheet,[cv2.IMWRITE_JPEG_QUALITY,96]);(OUT/'evidence/accepted_confirm_manifest.json').write_text(json.dumps(manifest,indent=2));print('confirmedsourceframes',len(manifest))
