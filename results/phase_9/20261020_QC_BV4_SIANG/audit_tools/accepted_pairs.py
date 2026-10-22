from pathlib import Path
import json,gzip,hashlib,cv2,numpy as np
root=Path('/workspace/traffic-vehicle-counter-IDM-LOC');out=root/'results/phase_9/20261020_QC_BV4_SIANG/accepted_timeout_control';cache=Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz');plans=[('pickup927_988',[927,988,1107],[1141,1157,1172,1187,1190,1195,1200,1206,1220,1257,1293,1328]),('mpv2697_2706',[2697,2706],[4384,4390,4396,4400,4401,4402,4404,4410,4420,4434,4441,4450]),('blue4149_4367',[4149,4367],[7380,7402,7422,7430,7440,7449,7450,7454,7459,7463,7466,7480]),('gojek4934_4946_4953',[4934,4946,4953],[7990,7994,7998,8000,8001,8005,8010,8015,8018,8021,8041,8081]),('honda4541_4567',[4541,4567,4569,4627],[7535,7570,7600,7609,7618,7621,7625,7630,7639,7651,7663,7680]),('first156_car192',[156,192,20,218],[174,190,206,218,220,222,223,224,225,241,259,283])];wanted={f for _,_,fs in plans for f in fs};records={}
with gzip.open(cache,'rt') as f:
 for line in f:
  d=json.loads(line)
  if d['frame_index'] in wanted:records[d['frame_index']]=d
images={};cap=cv2.VideoCapture('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');i=0
while True:
 ok,img=cap.read()
 if not ok:break
 if i in wanted:
  assert hashlib.sha256(img.tobytes()).hexdigest()==records[i]['detector_input_frame_pixel_sha256'];images[i]=img
 i+=1
cap.release();manifest=[];proofs=[]
for name,tracks,fs in plans:
 sheet=np.full((50+3*480,4*640,3),24,dtype=np.uint8);cv2.putText(sheet,name+' raw source pair/context evidence; sampled native frames',(10,32),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),1,cv2.LINE_AA);measure=[]
 for k,f in enumerate(fs):
  image=images[f].copy();cv2.rectangle(image,(0,0),(640,28),(0,0,0),-1);cv2.putText(image,f'f{f}',(6,22),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1,cv2.LINE_AA)
  for j,t in enumerate(tracks):
   obs=[o for o in records[f]['emitted_tracks'] if o['track_id']==t]
   for o in obs:
    col=[(0,165,255),(255,255,0),(0,255,255),(255,0,255)][j%4];b=[round(v) for v in o['raw_bbox']];cv2.rectangle(image,(b[0],b[1]),(b[2],b[3]),col,2);cv2.putText(image,f'{t}:{o["class_name"]}',(b[0],max(42,b[1]-4)),cv2.FONT_HERSHEY_SIMPLEX,.43,col,1,cv2.LINE_AA);measure.append({key:o[key] for key in ['frame_index','track_id','raw_bbox','class_name','original_detection_index','confidence']})
  y=50+(k//4)*480;x=(k%4)*640;sheet[y:y+480,x:x+640]=image
 path=out/'evidence'/f'pair-{name}.jpg';cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,94]);manifest.append({'path':str(path.relative_to(out)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_frames':fs,'raw_track_ids':tracks,'derivation':'NATIVE640X480_SAMPLED_CONTACT_SHEET_RAW_MEASUREMENT_BOXES_ONLY'});proofs.append({'case':name,'frames':fs,'tracks':tracks,'source_measurements':measure})
(out/'pair_proofs.json').write_text(json.dumps(proofs,indent=2)+'\n');(out/'evidence/pair_manifest.json').write_text(json.dumps({'artifacts':manifest,'source_pixel_checks':[{'frame_index':f,'sha256':hashlib.sha256(images[f].tobytes()).hexdigest(),'cache_sha256':records[f]['detector_input_frame_pixel_sha256'],'status':'PASS'} for f in sorted(wanted)]},indent=2)+'\n');print({'pair_proofs':len(plans),'frames':len(wanted)})
