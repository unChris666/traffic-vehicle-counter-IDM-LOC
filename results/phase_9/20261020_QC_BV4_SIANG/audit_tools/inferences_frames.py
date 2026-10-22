from pathlib import Path
import cv2,json,hashlib,math,numpy as np
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/removed_inferences';plan=json.loads((OUT/'visual_plan.json').read_text());records=json.loads((OUT/'selected_record_metadata.json').read_text());wanted={f for v in plan for f in v['frames_to_review']};source=Path('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4');assert hashlib.sha256(source.read_bytes()).hexdigest()=='5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1';cap=cv2.VideoCapture(str(source));images={};receipts=[];i=0
while True:
 ok,im=cap.read()
 if not ok:break
 if i in wanted:
  sha=hashlib.sha256(im.tobytes()).hexdigest();assert sha==records[str(i)]['detector_input_frame_pixel_sha256'];p=OUT/'evidence'/f'native-{i:06d}.png';assert cv2.imwrite(str(p),im);images[i]=im;receipts.append({'frame_index':i,'source_bgr_sha256':sha,'retained_path':str(p.relative_to(ROOT)),'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'cache_pixel_sha256_matches':True})
 i+=1
cap.release();assert i==9128 and set(images)==wanted
for case in plan:
 cells=[];t=case['raw_track_id']
 for f in case['frames_to_review']:
  im=images[f].copy();row=records[str(f)];obs=[q for q in row['emitted_tracks'] if q['track_id']==t];header=np.full((36,640,3),255,np.uint8);text=f"{case['case_id']} | source f{f}";cv2.putText(header,text,(6,23),cv2.FONT_HERSHEY_SIMPLEX,.49,(0,0,0),1,cv2.LINE_AA)
  for o in obs:
   x1,y1,x2,y2=[round(x) for x in o['raw_bbox']];cv2.rectangle(im,(x1,y1),(x2,y2),(255,0,0),2);cv2.putText(im,f"raw{t} {o['class_name']}",(max(0,min(x1,400)),max(15,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,0,0),2,cv2.LINE_AA)
  cells.append(np.vstack((header,im)))
 cols=3;rows=math.ceil(len(cells)/cols);canvas=np.full((516*rows,640*cols,3),230,np.uint8)
 for idx,c in enumerate(cells):canvas[(idx//cols)*516:(idx//cols+1)*516,(idx%cols)*640:(idx%cols+1)*640]=c
 p=OUT/'evidence'/(case['case_id']+'-sheet.jpg');assert cv2.imwrite(str(p),canvas,[cv2.IMWRITE_JPEG_QUALITY,92]);case['contact_sheet']=str(p.relative_to(ROOT));case['contact_sheet_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();case['status']='IMAGES_GENERATED_NOT_YET_VISUALLY_REVIEWED'
(OUT/'visual_plan.json').write_text(json.dumps(plan,indent=2)+'\n');(OUT/'evidence/frame_receipts.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_frames_decoded':i,'actual_source_frames_retained':len(images),'frames':receipts},indent=2)+'\n');print({'decoded':i,'native_frames':len(images),'contact_sheets':len(plan)})
