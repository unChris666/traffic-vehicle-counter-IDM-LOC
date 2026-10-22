import json,gzip,cv2,hashlib,numpy as np
from pathlib import Path
from collections import defaultdict
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/duplicates';E=OUT/'evidence';groups={2549:[4081,4082,4088,4092,4095,4099,4117,4118],2615:[4236,4265,4270,4282,4287,4303,4307,4311,4313,4352,4357,4390],3582:[6312,6322,6323,6324,6346,6347],3761:[6682,6684,6696,6700,6770,6771,6810,6811,6812,6813,6814,6815],4115:[7113,7121,7127,7132,7135,7152,7194,7199,7205,7209,7214,7215],4774:[7810,7819,7830,7835,7843,7853,7854],4990:[8098,8368,8369,8378,8386,8433,8434,8447,8448,8582]};wanted=set(f for fs in groups.values() for f in fs);rec={};cache=Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz');unresolved=json.loads((OUT/'unresolved_relations.json').read_text());related=defaultdict(set)
for r in unresolved:
 a,b=r['pair']; related[a].add(b);related[b].add(a)
related[3582].add(3587);related[2549].add(2561)
with gzip.open(cache,'rt') as f:
 for l in f:
  r=json.loads(l)
  if r['frame_index'] in wanted:rec[r['frame_index']]=r
images={};manifest=[];cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');i=0
while True:
 ok,im=cap.read()
 if not ok:break
 if i in wanted:
  sha=hashlib.sha256(im.tobytes()).hexdigest();assert sha==rec[i]['detector_input_frame_pixel_sha256'];images[i]=im;path=E/f'native-f{i:06d}.png';assert cv2.imwrite(str(path),im);manifest.append({'frame_index':i,'path':str(path.relative_to(OUT)),'source_bgr_pixel_sha256':sha,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cache_pixel_match':True,'dimensions':[640,480]})
 i+=1
cap.release();assert i==9128
for tid,fs in groups.items():
 cols=3;tw,th=420,335;rows=(len(fs)+cols-1)//cols;sheet=np.full((rows*th,cols*tw,3),32,np.uint8)
 for ix,f in enumerate(fs):
  im=images[f].copy();present=[]
  for o in rec[f]['emitted_tracks']:
   if o['track_id'] in related[tid]|{tid}:
    b=list(map(round,o['raw_bbox']));color=(0,255,255) if o['track_id']==tid else (255,0,255);cv2.rectangle(im,tuple(b[:2]),tuple(b[2:]),color,2);present.append(f"{o['track_id']}:{o['class_name']}")
  tile=cv2.resize(im,(420,315));yy=(ix//cols)*th;xx=(ix%cols)*tw;sheet[yy:yy+315,xx:xx+tw]=tile;cv2.putText(sheet,f"f{f} "+','.join(present),(xx+3,yy+330),cv2.FONT_HERSHEY_SIMPLEX,.37,(255,255,255),1)
 path=E/f'detail-{tid}.jpg';cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,96])
(E/'detailed_manifest.json').write_text(json.dumps({'claim_type':'ACTUAL_SEQUENTIALLY_DECODED_NATIVE_SOURCE_PIXELS','source_video_sha256':'5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1','cache_sha256':'bc484aff0372242925f8b87e6d91ffc2ac11ae696ed3f59201a73d44f98a145b','sequential_frames_decoded':i,'native_frames':manifest,'detail_sheets':[{ 'track_id':tid,'frames':fs,'path':f'evidence/detail-{tid}.jpg'} for tid,fs in groups.items()]},indent=2))
print('Nativeverified',len(manifest),'sheets',len(groups))
