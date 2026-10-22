import gzip,json,math
from pathlib import Path
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC');out=R/'results/phase_9/20261020_QC_BV4_SIANG/unmatched';baseline=json.loads(gzip.decompress((R/'results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz').read_bytes()));matched={r['track_id'] for e in baseline['events'] for r in e['evidence']['source_refs']}|{d['track_id'] for d in baseline['decisions']};last={};pairs=[]
p1=(1.6843836743,429.9945169426);p2=(617.3266166341,1.3159337647);dx=p2[0]-p1[0];dy=p2[1]-p1[1];length=math.hypot(dx,dy)
def point(o):b=o['raw_bbox'];return((b[0]+b[2])/2,b[3])
def sd(p):return(dx*(p[1]-p1[1])-dy*(p[0]-p1[0]))/length
def proj(p):return((p[0]-p1[0])*dx+(p[1]-p1[1])*dy)/(length*length)
with gzip.open(next(Path('/tmp/qc-donor').rglob('track_records.jsonl.gz')),'rt') as f:
 for line in f:
  row=json.loads(line);fr=row['frame_index']
  for o in row['emitted_tracks']:
   t=o['track_id'];before=last.get(t);last[t]=o
   if t in matched or o['class_name'] not in ('motorcycle','car','truck') or before is None or before['class_name']!=o['class_name'] or before['frame_index']!=fr-1:continue
   a,b=point(before),point(o);sa,sb=sd(a),sd(b)
   if sa*sb>=0:continue
   k=sa/(sa-sb);intersection=(a[0]+k*(b[0]-a[0]),a[1]+k*(b[1]-a[1]));u=proj(intersection)
   if not 0<u<1:continue
   pairs.append({'track_id':t,'first_frame':fr-1,'second_frame':fr,'class_name':o['class_name'],'first_bc':a,'second_bc':b,'first_distance':sa,'second_distance':sb,'observed_intersection':intersection,'first_bbox':before['raw_bbox'],'second_bbox':o['raw_bbox'],'displacement':math.dist(a,b),'max_abs_distance':max(abs(sa),abs(sb)),'claim_type':'AUDIT_DIAGNOSTIC_PAIR_NOT_COUNT_EVENT_NOT_PHYSICAL_GT'})
(out/'geometry_pair_search.json').write_text(json.dumps({'not_a_counting_replay':True,'pairs':pairs},indent=2)+'\n')
print('pairs',len(pairs))
for p in pairs:print(p)
