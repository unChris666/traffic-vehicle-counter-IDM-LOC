import json,gzip,hashlib,cv2,numpy as np
from pathlib import Path
from collections import defaultdict
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/roles';E=OUT/'evidence';E.mkdir(exist_ok=True);N=E/'native';N.mkdir(exist_ok=True)
BASE=ROOT/'results/b_v4/execution/pilot_machine_final/weekday_siang';load=lambda name:json.loads(gzip.decompress((BASE/(name+'.json.gz')).read_bytes()))
cases=json.loads((OUT/'selected_cases.json').read_text()); assignments=load('frame_assignments'); by_track=defaultdict(list)
for a in assignments:by_track[a['track_id']].append(a)
records={};rawbytrack=defaultdict(list)
cache=next(Path('/tmp/qc-donor').rglob('track_records.jsonl.gz'))
with gzip.open(cache,'rt') as f:
 for line in f:
  row=json.loads(line);records[row['frame_index']]=row
  for obs in row['emitted_tracks']:rawbytrack[obs['track_id']].append(obs)
manifest=[];needed=set();selections=[]
for i,case in enumerate(cases):
 tid=case['track_id'];at=case['source_ref']['frame_index'];allobs=[o for o in rawbytrack[tid] if abs(o['frame_index']-at)<=70 and o['class_name']=='person'];indices=sorted(set(o['frame_index'] for o in allobs))
 chosen=sorted(set([indices[int(round(k*(len(indices)-1)/4))] for k in range(5)]+[at])) if indices else [at]
 while len(chosen)<6:
  alternatives=[max(0,at-25),min(9127,at+25),max(0,at-50),min(9127,at+50)]
  c=next((x for x in alternatives if x not in chosen),None)
  if c is None:break
  chosen.append(c);chosen.sort()
 chosen=chosen[:6];needed.update(chosen);selections.append({'case_index':i+1,'track_id':tid,'decision_frame':case['frame_index'],'source_frame':at,'frames':chosen,'passage_id':case['passage_id'],'episode_id':case['episode_id']})
cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');images={}
for f in range(9128):
 ok,image=cap.read();assert ok
 if f in needed:
  sha=hashlib.sha256(image.tobytes()).hexdigest();assert sha==records[f]['detector_input_frame_pixel_sha256'],f
  path=N/f'frame-{f:06d}.png';assert cv2.imwrite(str(path),image);images[f]=image
  manifest.append({'frame_index':f,'native_path':str(path.relative_to(ROOT)),'pixel_sha256':sha,'png_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cache_pixel_match':True})
cap.release()
for selected in selections:
 tid=selected['track_id'];panels=[]
 for f in selected['frames']:
  image=images[f];obs=next((o for o in records[f]['emitted_tracks'] if o['track_id']==tid),None)
  if obs is None:
   available=rawbytrack[tid];near=min(available,key=lambda o:abs(o['frame_index']-f));bbox=near['raw_bbox'];label=f'NO CURRENT raw{tid}; nearest bbox frame{near["frame_index"]}'
  else:bbox=obs['raw_bbox'];label=f'raw{tid} {obs["class_name"]}'
  x1,y1,x2,y2=map(int,bbox);cx=(x1+x2)//2;cy=(y1+y2)//2;w=max(180,(x2-x1)*2+40);h=max(170,(y2-y1)+130);left=max(0,cx-w//2);right=min(640,left+w);top=max(0,cy-h//2);bottom=min(480,top+h)
  crop=image[top:bottom,left:right].copy()
  if obs is not None:cv2.rectangle(crop,(x1-left,y1-top),(x2-left,y2-top),(255,0,255),2)
  for o in records[f]['emitted_tracks']:
   if o['class_name']=='motorcycle':
    a,b,c,d=map(int,o['raw_bbox'])
    if c>=left and a<=right and d>=top and b<=bottom:
     cv2.rectangle(crop,(a-left,b-top),(c-left,d-top),(0,220,255),1);cv2.putText(crop,str(o['track_id']),(max(0,a-left),max(15,b-top)),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,200,255),1)
  scale=min(500/crop.shape[1],300/crop.shape[0]);res=cv2.resize(crop,None,fx=scale,fy=scale);panel=np.full((350,520,3),30,np.uint8);panel[45:45+res.shape[0],10:10+res.shape[1]]=res
  cv2.putText(panel,f'f{f} | {label}',(8,19),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1)
  cv2.putText(panel,f'crop native [{left},{top},{right},{bottom}]',(8,38),cv2.FONT_HERSHEY_SIMPLEX,.4,(180,180,180),1);panels.append(panel)
 while len(panels)<6:panels.append(np.full((350,520,3),30,np.uint8))
 sheet=np.vstack([np.hstack(panels[:3]),np.hstack(panels[3:6])]);path=E/f'role-{selected["case_index"]:02d}-raw{tid}.jpg';assert cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,95]);selected['sheet_path']=str(path.relative_to(ROOT));selected['sheet_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
(OUT/'review_selections.json').write_text(json.dumps(selections,indent=2)+'\n');(E/'native_manifest.json').write_text(json.dumps({'video_sha256':hashlib.sha256(Path('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4').read_bytes()).hexdigest(),'records_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),'native_frames':manifest,'all_pixel_hashes_match':True},indent=2)+'\n')
print({'cases':len(selections),'native_frames':len(manifest),'sheets':len(selections)})
