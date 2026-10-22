import json,gzip,hashlib,collections,cv2,numpy as np
from pathlib import Path
root=Path('/workspace/traffic-vehicle-counter-IDM-LOC');out=root/'results/phase_9/20261020_QC_BV4_SIANG/identity';out.mkdir(parents=True,exist_ok=True);(out/'evidence').mkdir(exist_ok=True)
base=root/'results/b_v4/execution/pilot_machine_final/weekday_siang'
def load(name):return json.loads(gzip.decompress((base/(name+'.json.gz')).read_bytes()))
d=load('counting_result');handoffs=load('handoff_audit');episodes=load('episode_audit');assign=load('frame_assignments');rows=[v for v in d['decisions'] if v['status']=='pending' and 'IDENTITY_CONTINUITY_UNRESOLVED_FOR_TIMEOUT' in v['reasons']]
records=[];trackobs=collections.defaultdict(list);source=Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz')
with gzip.open(source,'rt') as f:
 for line in f:
  r=json.loads(line);records.append(r)
  for t in r['emitted_tracks']:trackobs[t['track_id']].append(t)
plans=[];needed=set()
for i,row in enumerate(rows):
 candidates=[a for a in assign if (a['physical_unit_id'],a['episode_id'])==(row['physical_unit_id'],row['episode_id']) and a['role']=='vehicle'];pids={a['physical_episode_id'] for a in candidates}; tids={a['track_id'] for a in candidates}
 links=[h for h in handoffs if h['first_episode_id'] in pids or h['second_episode_id'] in pids]
 first=min(a['frame_index'] for a in candidates);last=max(a['frame_index'] for a in candidates)
 frames={first,max(0,first-20),min(last,first+10),last,min(9127,last+30),row['frame_index']}
 for h in links:frames|={h['last_first_frame'],h['first_second_frame']}
 frames=sorted(f for f in frames if 0<=f<=9127);needed.update(frames)
 plan={'case_id':f'IDENTITY-{i+1:02d}','track_id':row['track_id'],'member_track_ids':sorted(tids),'physical_unit_id':row['physical_unit_id'],'episode_id':row['episode_id'],'passage_id':row['passage_id'],'decision_frame':row['frame_index'],'first_frame':first,'last_frame':last,'source_ref':row['source_ref'],'handoff_pairs':links,'planned_frames':frames,'physical_episode_ids':sorted(pids)};plans.append(plan)
video=Path('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');cap=cv2.VideoCapture(str(video));frames={};checks=[];index=0
while True:
 ok,img=cap.read()
 if not ok:break
 if index in needed:
  sha=hashlib.sha256(img.tobytes()).hexdigest();expected=records[index]['detector_input_frame_pixel_sha256'];assert sha==expected,(index,sha,expected);frames[index]=img
  checks.append({'frame_index':index,'source_bgr_sha256':sha,'retained_detector_input_pixel_sha256':expected,'match':True})
 index+=1
cap.release();assert index==9128
for plan in plans:
 cells=[];tids=set(plan['member_track_ids'])|{h[k] for h in plan['handoff_pairs'] for k in ['first_track_id','second_track_id']}
 for f in plan['planned_frames']:
  img=frames[f].copy();obs=[o for o in records[f]['emitted_tracks'] if o['track_id'] in tids]
  for t in obs:
   box=list(map(int,t['raw_bbox']));color=(0,255,255) if t['track_id'] in plan['member_track_ids'] else (0,100,255);cv2.rectangle(img,tuple(box[:2]),tuple(box[2:]),color,2);cv2.putText(img,f"{t['track_id']} {t['class_name']}",(max(0,box[0]),max(15,box[1]-3)),cv2.FONT_HERSHEY_SIMPLEX,.48,color,1,cv2.LINE_AA)
  if obs:
   boxes=[t['raw_bbox'] for t in obs];x1=max(0,int(min(b[0] for b in boxes))-25);y1=max(0,int(min(b[1] for b in boxes))-25);x2=min(640,int(max(b[2] for b in boxes))+25);y2=min(480,int(max(b[3] for b in boxes))+25);crop=img[y1:y2,x1:x2]
  else:crop=img
  cell=np.zeros((270,640,3),dtype=np.uint8);cell[30:270,:320]=cv2.resize(img,(320,240));h,w=crop.shape[:2];ratio=min(320/w,240/h);small=cv2.resize(crop,(max(1,int(w*ratio)),max(1,int(h*ratio))));cell[30:30+small.shape[0],320:320+small.shape[1]]=small;cv2.putText(cell,f"{plan['case_id']} raw{plan['track_id']} f{f}",(5,22),cv2.FONT_HERSHEY_SIMPLEX,.58,(255,255,255),1,cv2.LINE_AA);cells.append(cell)
 cols=3;count=len(cells);sheet=np.zeros((((count+cols-1)//cols)*270,cols*640,3),dtype=np.uint8)
 for n,cell in enumerate(cells):sheet[(n//cols)*270:(n//cols+1)*270,(n%cols)*640:(n%cols+1)*640]=cell
 path=out/'evidence'/(plan['case_id']+'.jpg');assert cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,95]);plan['contact_sheet']=str(path.relative_to(root));plan['contact_sheet_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
(out/'case_plans.json').write_text(json.dumps(plans,indent=2)+'\n');(out/'source_pixel_checks.json').write_text(json.dumps({'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'records_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'full_frames_decoded':index,'checked_frames':len(checks),'checks':checks},indent=2)+'\n')
print({'cases':len(plans),'source_frames_checked':len(checks),'output':str(out)})
