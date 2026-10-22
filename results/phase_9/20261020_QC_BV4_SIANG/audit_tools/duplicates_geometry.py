from pathlib import Path
from collections import defaultdict,Counter
import gzip,json,sys
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/duplicates';p=ROOT/'results/b_v4/execution/pilot_machine_final/weekday_siang';load=lambda n:json.loads(gzip.decompress((p/(n+'.json.gz')).read_bytes())); data=load('counting_result');g=load('geometry')['rendered_native_pixels'];sys.path.insert(0,str(ROOT/'notebooks'));from phase_5_geometry_helpers import Geometry,signed_distance,segment_intersection
G=Geometry(g['line']['P1'],g['line']['P2'],g['side_a_polygon'],g['side_b_polygon'],640,480)
relations=json.loads(gzip.decompress(Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/counting/relations.json.gz').read_bytes()));wanted={2549,2561,2615,3582,3587,3761,4115,4774,4820,4990};relevant=[r for r in relations if r.get('type')=='SAME_VEHICLE' and r['status']=='UNRESOLVED' and ({r['first_track_id'],r['second_track_id']}&wanted)];wanted|={t for r in relevant for t in [r['first_track_id'],r['second_track_id']]};obs=defaultdict(list)
with gzip.open('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz','rt') as f:
 for line in f:
  r=json.loads(line)
  for o in r['emitted_tracks']:
   if o['track_id'] in wanted:
    b=o['raw_bbox'];point=[(b[0]+b[2])/2,b[3]];v={'frame_index':r['frame_index'],'track_id':o['track_id'],'original_detection_index':o['original_detection_index'],'class_name':o['class_name'],'raw_bbox':b,'point':point,'signed_distance_px':signed_distance(point,G.p1,G.p2),'polygon':G.side(point)};obs[o['track_id']].append(v)
summary=[]
for tid,values in sorted(obs.items()):
 crossings=[]; band=[]
 for v in values:
  b=v['point']; dx,dy=G.p2[0]-G.p1[0],G.p2[1]-G.p1[1];projection=((b[0]-G.p1[0])*dx+(b[1]-G.p1[1])*dy)/(dx*dx+dy*dy)
  if 0<=projection<=1 and abs(v['signed_distance_px'])<=25:band.append(v)
 for a,b in zip(values,values[1:]):
  if b['frame_index']==a['frame_index']+1 and a['signed_distance_px']*b['signed_distance_px']<0:
   cross=segment_intersection(a['point'],b['point'],G.p1,G.p2)
   if cross['kind']=='proper':crossings.append({'first':a,'second':b,'intersection':cross})
 events=[]
 for event in data['events']:
  if tid in {ref['track_id'] for ref in event['evidence']['source_refs']}:events.append({k:event[k] for k in ['event_id','display_id','category','direction','route','activation_frame']})
 summary.append({'track_id':tid,'first':values[0],'last':values[-1],'observations':len(values),'polygons':dict(Counter(v['polygon'] for v in values)),'in_band_category_votes':dict(Counter(v['class_name'] for v in band)),'in_band_frames':[v['frame_index'] for v in band],'crossings':crossings,'existing_accepted_events':events})
(OUT/'source_geometry_diagnostics.json').write_text(json.dumps({'claim_type':'SOURCE_MEASUREMENT_AUDIT_DIAGNOSTICS_NO_COUNTING_REPLAY','tracks':summary},indent=2))
for v in summary:
 if v['track_id'] in {2549,2561,2615,3582,3587,3761,4115,4774,4820,4990}:print({k:v[k] for k in ['track_id','polygons','in_band_category_votes','existing_accepted_events']}|{'crossing_pairs':[(x['first']['frame_index'],x['second']['frame_index']) for x in v['crossings']]})
