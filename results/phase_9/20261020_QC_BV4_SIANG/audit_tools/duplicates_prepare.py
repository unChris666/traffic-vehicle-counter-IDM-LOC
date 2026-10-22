from pathlib import Path
import json,gzip,hashlib,sys,cv2,numpy as np
from collections import defaultdict
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC'); OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/duplicates'; (OUT/'evidence').mkdir(parents=True,exist_ok=True)
p=ROOT/'results/b_v4/execution/pilot_machine_final/weekday_siang'
load=lambda n:json.loads(gzip.decompress((p/(n+'.json.gz')).read_bytes()))
data=load('counting_result'); cases=[r for r in data['decisions'] if r['status']=='pending' and 'UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE' in r['reasons']]; wanted={r['track_id'] for r in cases}|{2561,3587}; obs=defaultdict(list); records={}
cache=Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz')
with gzip.open(cache,'rt') as f:
 for line in f:
  r=json.loads(line); records[r['frame_index']]=r
  for o in r['emitted_tracks']:
   if o['track_id'] in wanted:obs[o['track_id']].append(o)
frames=set(); summaries=[]
for c in cases:
 tid=c['track_id']; oo=obs[tid]; framesource=c['source_ref']['frame_index']; start=max(0,framesource-90); end=min(9127,framesource+60); selected=sorted(set([start,framesource-30,framesource-10,framesource,framesource+10,framesource+30,end]+[o['frame_index'] for o in oo if start<=o['frame_index']<=end][::15])); frames.update(selected); summaries.append({'track_id':tid,'decision':c,'selected_frames':selected,'first_raw_observation':oo[0]['frame_index'],'last_raw_observation':oo[-1]['frame_index'],'categories':dict(__import__('collections').Counter(o['class_name'] for o in oo)),'observations':oo})
images={}; evidence=[]; cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4'); i=0
while True:
 ok,image=cap.read()
 if not ok:break
 if i in frames:
  sha=hashlib.sha256(image.tobytes()).hexdigest(); assert sha==records[i]['detector_input_frame_pixel_sha256'];images[i]=image
 i+=1
cap.release(); assert i==9128
for s in summaries:
 tid=s['track_id']; selected=s['selected_frames']; columns=3; h,w=260,320; rows=(len(selected)+columns-1)//columns; sheet=np.full((rows*h,columns*w,3),32,np.uint8)
 for idx,f in enumerate(selected):
  image=images[f].copy(); targets=[]
  for o in records[f]['emitted_tracks']:
   if o['track_id'] in wanted:
    x1,y1,x2,y2=map(round,o['raw_bbox']); color=(0,255,255) if o['track_id']==tid else (255,0,255);cv2.rectangle(image,(x1,y1),(x2,y2),color,2);cv2.putText(image,f"{o['track_id']} {o['class_name']}",(x1,max(12,y1-3)),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1);targets.append(o)
  tile=cv2.resize(image,(320,240)); yy=(idx//columns)*h;xx=(idx%columns)*w;sheet[yy:yy+240,xx:xx+w]=tile;cv2.putText(sheet,f"source f{f} | target {tid}",(xx+4,yy+255),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1)
  if f in [s['decision']['source_ref']['frame_index'],s['decision']['source_ref']['frame_index']-10,s['decision']['source_ref']['frame_index']+10]:
   path=OUT/'evidence'/f'raw-{tid}-f{f}.png';cv2.imwrite(str(path),images[f]); evidence.append({'path':str(path.relative_to(OUT)),'frame_index':f,'target_raw_id':tid,'source_bgr_sha256':hashlib.sha256(images[f].tobytes()).hexdigest(),'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'native_dimensions':[640,480],'cache_pixel_match':True})
 path=OUT/'evidence'/f'sheet-{tid}.jpg';cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,95]);s['sheet']=str(path.relative_to(OUT))
(OUT/'prepared_cases.json').write_text(json.dumps(summaries,indent=2));(OUT/'evidence/manifest.json').write_text(json.dumps({'source_video_sha256':'5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1','records_sha256':'bc484aff0372242925f8b87e6d91ffc2ac11ae696ed3f59201a73d44f98a145b','decode_frames':i,'native_evidence':evidence,'sheets_are_resized_visual_aids':True},indent=2))
print([(s['track_id'],s['first_raw_observation'],s['last_raw_observation'],len(s['selected_frames'])) for s in summaries])
