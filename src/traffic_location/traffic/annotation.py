"""Fresh full-frame audit rendering. Consumes immutable decisions, never counts."""
from collections import defaultdict,Counter
from pathlib import Path
import hashlib,subprocess,math,json
from ..artifacts import read,sha,semantic_hash,require,write
from .results import validate_native
from ._kernel.geometry import Geometry
COLORS={'motorcycle':(70,210,70),'car':(220,100,40),'truck':(30,150,250),'bus':(190,60,180),'pedestrian':(220,210,30),'person':(140,140,140)}
CATS=('motorcycle','car','truck','bus','pedestrian')
def plan(native):
 validate_native(native);by_frame=defaultdict(dict);links=defaultdict(dict);candidates=defaultdict(lambda:defaultdict(set));events=[];display=defaultdict(list)
 for a in native.get('frame_assignments',[]):by_frame[a['frame_index']][a['track_id']]=a
 for r in native.get('component_links',[]):
  for f in r['support_frames']:candidates[f][r['component_track_id']].add(r['vehicle_track_id'])
 for f,children in candidates.items():
  for child,parents in children.items():
   if len(parents)==1:links[f][child]=next(iter(parents))
 for e in native['events']:
  frame=e.get('activation_frame',e['decision_frame']);require(type(frame) is int and 0<=frame<native['report']['frame_count'],'Accepted event activation outside source')
  events.append((frame,e))
  for ref in e['evidence'].get('source_refs',[]):
   ep=ref.get('physical_episode_id')
   if ep:display[ref['track_id'],ep].append((frame,e))
 return {'assignments':by_frame,'links':links,'events':sorted(events,key=lambda v:(v[0],v[1]['event_id'])),'display':display}
def snapshot(p,index):
 active=[e for f,e in p['events'] if f<=index];pivot={c:{d:{'measured':0,'estimated':0} for d in ['A_TO_B','B_TO_A']} for c in CATS}
 for e in active:pivot[e['category']][e['direction']]['measured' if e['evidence']['measured_crossing'] else 'estimated']+=1
 return {'accepted':len(active),'vehicles':sum(e['category']!='pedestrian' for e in active),'pedestrian':sum(e['category']=='pedestrian' for e in active),'measured':sum(e['evidence']['measured_crossing'] is True for e in active),'estimated':sum(e['evidence']['measured_crossing'] is not True for e in active),'pivot':pivot,'recent':active[-7:]}
def paint(image,record,native,geometry,p,*,fps,video_id):
 import cv2,numpy as np
 index=record['frame_index'];h,w=image.shape[:2];canvas=np.zeros((max(900,h),w+560,3),dtype=np.uint8);canvas[:h,:w]=image
 assignments=p['assignments'].get(index,{});names={int(k):v for k,v in geometry['_class_names'].items()};obs={v['track_id']:v for v in record['emitted_measurements'] if names[v['raw_detection']['class_id']] in {'person','motorcycle','car','truck','bus'}};children=defaultdict(list);occupied=[]
 for child,parent in p['links'].get(index,{}).items():
  if child in obs and parent in obs and assignments.get(child,{}).get('role')=='rider' and names[obs[parent]['raw_detection']['class_id']]=='motorcycle':children[parent].append(child)
 hidden={c for cs in children.values() for c in cs}
 overlay=canvas[:h,:w].copy()
 for key,color in [('side_a_polygon',(180,80,20)),('side_b_polygon',(30,100,220))]:
  pts=np.array([[round(x*w),round(y*h)] for x,y in geometry['normalized'][key]],dtype=np.int32);cv2.fillPoly(overlay,[pts],color)
 canvas[:h,:w]=cv2.addWeighted(overlay,.15,canvas[:h,:w],.85,0)
 a,b=[np.array(geometry['normalized']['line'][k])*[w,h] for k in ['P1','P2']];normal=np.array([-(b-a)[1],(b-a)[0]])/np.linalg.norm(b-a)
 cv2.line(canvas,tuple(a.astype(int)),tuple(b.astype(int)),(0,255,255),2)
 margin=native['report']['policy']['line_margin_half_width_px']
 for sign in [-1,1]:cv2.line(canvas,tuple((a+sign*margin*normal).astype(int)),tuple((b+sign*margin*normal).astype(int)),(0,150,160),1)
 for tid,o in obs.items():
  if tid in hidden:continue
  raw=o['raw_detection'];cat=names[raw['class_id']];assignment=assignments.get(tid,{});role=assignment.get('role','unknown_person' if cat=='person' else 'vehicle');category='pedestrian' if role=='pedestrian' else cat
  box=list(raw['bbox']);bc=((box[0]+box[2])/2,box[3])
  for child in children.get(tid,[]):
   cb=obs[child]['raw_detection']['bbox'];box=[min(box[0],cb[0]),min(box[1],cb[1]),max(box[2],cb[2]),max(box[3],cb[3])]
  color=COLORS.get(category,(130,130,130));x1,y1,x2,y2=[int(v) for v in box];cv2.rectangle(canvas,(x1,y1),(x2,y2),color,2);cv2.circle(canvas,tuple(int(v) for v in bc),4,(0,255,255),-1)
  label=f'RAW {tid} {category.upper()}'
  if cat=='person':label+=' '+role.upper()
  if children.get(tid):label+=' +R'+','.join(str(c) for c in children[tid])
  candidates=[e for frame,e in p['display'].get((tid,assignment.get('physical_episode_id')),[]) if frame<=index]
  if candidates:
   accepted=max(candidates,key=lambda e:e['decision_frame']);label+=' FINAL '+accepted['category'].upper()+' '+accepted['display_id']
  tw,th=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,.42,1)[0];lx=max(0,min(x1,w-tw-6));ly=max(th+5,y1-4)
  for candidate_y in [ly]+list(range(th+8,h-5,th+10)):
   rect=(lx,candidate_y-th-5,min(w,lx+tw+6),candidate_y+3)
   if not any(rect[0]<r[2] and r[0]<rect[2] and rect[1]<r[3] and r[1]<rect[3] for r in occupied):ly=candidate_y;break
  occupied.append((lx,ly-th-5,min(w,lx+tw+6),ly+3))
  cv2.rectangle(canvas,(lx,ly-th-5),(min(w,lx+tw+6),ly+3),color,-1);cv2.putText(canvas,label,(lx+3,ly),0,.42,(0,0,0) if category in ['motorcycle','truck','pedestrian'] else (255,255,255),1,cv2.LINE_AA)
 s=snapshot(p,index)
 def text(msg,y,color=(230,230,230),scale=.5,x=None):cv2.putText(canvas,str(msg),(w+12 if x is None else x,y),0,scale,color,1,cv2.LINE_AA)
 text(video_id,25,scale=.53);text(f'FRAME {index} / {native["report"]["frame_count"]-1} | t~{index/fps:.2f}s',49)
 text('OFFLINE FINALIZED REVIEW',74,(0,220,255));text('Uses full-video evidence; not live decisions',96,scale=.43)
 text('PASSAGE ACCEPTED (through this frame)',128,(100,240,100));text(f'Vehicles {s["vehicles"]} | Pedestrian {s["pedestrian"]}',151)
 text(f'Measured {s["measured"]} | Estimated {s["estimated"]}',174)
 text('CATEGORY        A>B M/E       B>A M/E',207,(0,220,255))
 for n,cat in enumerate(CATS):
  v=s['pivot'][cat];text(f'{cat:12} {v["A_TO_B"]["measured"]:4}/{v["A_TO_B"]["estimated"]:<4}    {v["B_TO_A"]["measured"]:4}/{v["B_TO_A"]["estimated"]:<4}',232+n*25,COLORS[cat],.48)
 text('PASSAGE LOG (accepted only)',380,(0,220,255))
 for n,e in enumerate(reversed(s['recent'])):
  text(f'{e["display_id"]} RAW{e["track_id"]} {e["category"]} {e["direction"]}',403+n*39,scale=.43)
  text(f'  f{e["decision_frame"]} {e["route"]} '+('MEASURED' if e['evidence']['measured_crossing'] else 'ESTIMATED'),419+n*39,scale=.39)
 text(f'PENDING FINAL: {native["aggregate"]["pending"]} (whole video)',702,(60,190,255))
 pending=[d for d in native['decisions'] if d.get('status')=='pending']
 for n,d in enumerate(pending[:3]):text(f'RAW{d.get("track_id")} '+','.join(d.get('reasons',[]))[:56],725+n*22,scale=.37)
 text(f'INVALID FINAL: {native["aggregate"]["invalid"]} | excluded',812,(80,130,255))
 text('Pending/invalid never enter accepted pivot',838,scale=.43)
 text('Geometry provisional | source BC: yellow dot',862,scale=.42)
 text('UNITS ON FRAME (raw IDs; rider parent exact-frame)',h+25,x=12,scale=.45)
 for n,(tid,o) in enumerate(list(obs.items())[:11]):
  row=assignments.get(tid,{});par=p['links'].get(index,{}).get(tid);line=f'RAW{tid}: {names[o["raw_detection"]["class_id"]]} | {row.get("role","unresolved")}'
  if par is not None:line+=f' | parent RAW{par}'
  text(line,h+48+n*23,x=12,scale=.42)
 return canvas,s

def render(video,measurement,native_path,geometry_path,output,*,preview_limit=None):
 import cv2
 video,measurement,native_path,geometry_path,output=map(Path,[video,measurement,native_path,geometry_path,output]);require(not output.exists(),'Immutable annotated output exists')
 before={str(p):sha(p) for p in [video,measurement,native_path,geometry_path]};native=read(native_path);validate_native(native);native_hash=semantic_hash(native);fresh=read(measurement);geometry=read(geometry_path);identity=native['source_identity']
 require(before[str(video)]==identity['video_sha256'] and before[str(measurement)]==identity['records_sha256'] and before[str(geometry_path)]==identity['geometry_sha256'],'Renderer source binding differs')
 require(fresh['records_semantic_sha256']==semantic_hash(fresh['records']),'Measurement integrity failure')
 expected=native['report']['frame_count'];require(fresh['frames']==expected==len(fresh['records']),'Renderer coverage differs');count=expected if preview_limit is None else min(preview_limit,expected)
 geometry['_class_names']=fresh['class_names'];p=plan(native);cap=cv2.VideoCapture(str(video));require(cap.isOpened(),'Source cannot decode');fps=cap.get(cv2.CAP_PROP_FPS);require(math.isfinite(fps) and fps>0,'Invalid FPS')
 w,h=identity['width'],identity['height'];size=(w+560,max(900,h));require(size[0]%2==0 and size[1]%2==0,'H264 requires even output dimensions');output.parent.mkdir(parents=True,exist_ok=True)
 temp=output.with_name(output.stem+'.partial.mp4');log=output.with_suffix('.ffmpeg.log');command=['ffmpeg','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{size[0]}x{size[1]}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(temp)]
 encoded=0
 try:
  with log.open('w') as stderr:
   proc=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=stderr)
   try:
    for index,record in enumerate(fresh['records'][:count]):
     ok,image=cap.read();require(ok and record['frame_index']==index,'Decode/frame gap')
     require(hashlib.sha256(image.tobytes()).hexdigest()==record['source_pixel_sha256'],'Source pixel mismatch: sequential decode required')
     canvas,state=paint(image,record,native,geometry,p,fps=fps,video_id=native['video_id']);proc.stdin.write(canvas.tobytes());encoded+=1
     if index%300==0:print(json.dumps({'stage':'annotation','video':native['video_id'],'frame':index,'total':count}),flush=True)
   finally:proc.stdin.close()
   require(proc.wait(timeout=180)==0,'FFmpeg failed; see codec log')
  require(encoded==count,'Incomplete annotated video')
  if preview_limit is None:require(not cap.read()[0],'Unexpected extra source frames; not a full-video render')
  if preview_limit is None:require(state['accepted']==native['aggregate']['total'] and state['vehicles']==native['aggregate']['vehicle_total'],'Final panel/ledger mismatch')
  dec=cv2.VideoCapture(str(temp));decoded=0
  while True:
   ok,_=dec.read()
   if not ok:break
   decoded+=1
  dec.release();require(decoded==count,'Encoded frame coverage mismatch')
  require(semantic_hash(native)==native_hash and all(sha(Path(k))==v for k,v in before.items()),'Renderer changed inputs')
  temp.rename(output);report={'status':'SUCCEEDED','video_id':native['video_id'],'frames_encoded':encoded,'frames_redecoded':decoded,'measurement_frames':expected,'source_reported_frames':fresh['metadata']['reported_frame_count'],'scope':'FULL_VIDEO' if preview_limit is None else 'PREVIEW_ONLY','final_panel':{k:v for k,v in state.items() if k!='recent'},'output_sha256':sha(output),'input_sha256':before,'counting_rerun':False,'inference_rerun':False,'source_pixels_verified_every_frame':True,'audio_preserved':False,'timing':'CFR_REPORTED_FPS_NOT_ORIGINAL_VFR_PTS'};write(output.with_suffix('.json'),report);return report
 except BaseException:
  if 'proc' in locals() and proc.poll() is None:proc.kill();proc.wait()
  temp.unlink(missing_ok=True);raise
 finally:cap.release()
