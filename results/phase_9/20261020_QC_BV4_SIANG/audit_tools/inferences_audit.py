from pathlib import Path
from collections import defaultdict,Counter
import json,gzip,sys,hashlib,csv,math
ROOT=Path('/workspace/traffic-vehicle-counter-IDM-LOC');sys.path.insert(0,str(ROOT/'notebooks'))
from phase_8_b_v4_batch import _read_b_v3_result
OUT=ROOT/'results/phase_9/20261020_QC_BV4_SIANG/removed_inferences'
OUT.mkdir(parents=True,exist_ok=True)
old,base_ref=_read_b_v3_result(ROOT,'weekday_siang')
new=json.loads(gzip.decompress((ROOT/'results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz').read_bytes()))
a=[e for e in old['events'] if not e['evidence']['measured_crossing']];b=[e for e in new['events'] if not e['evidence']['measured_crossing']]
def origin_key(e):
 f=e['evidence']['last_observed_origin_frame'];r=[v for v in e['evidence']['source_refs'] if v['frame_index']==f]
 return e['category'],e['direction'],tuple(sorted((v['track_id'],tuple(v['raw_bbox']),v['original_detection_index']) for v in r)),f
def refs(e):return set((v['track_id'],v['frame_index'],v['original_detection_index'],tuple(v['raw_bbox'])) for v in e['evidence']['source_refs'])
newkeys=defaultdict(list)
for e in b:newkeys[origin_key(e)].append(e)
diag=defaultdict(list);audit=defaultdict(list);epi=defaultdict(list)
for x in new['open_passage_diagnostics']:diag[x['track_id']].append(x)
for x in new['eligibility_audit']:audit[x['track_id']].append(x)
for x in json.loads(gzip.decompress((ROOT/'results/b_v4/execution/pilot_machine_final/weekday_siang/episode_audit.json.gz').read_bytes())):epi[x['track_id']].append(x)
records=[];bytrack=defaultdict(list);bysource={}
cache=Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz')
with gzip.open(cache,'rt') as f:
 for line in f:
  row=json.loads(line);bysource[row['frame_index']]=row
  for o in row['emitted_tracks']:bytrack[o['track_id']].append(o)
# Geometric measurement summaries are descriptive; no state/counting replay.
g=json.loads(gzip.decompress((ROOT/'results/b_v4/execution/pilot_machine_final/weekday_siang/geometry.json.gz').read_bytes()))
(OUT/'geometry_copy.json').write_text(json.dumps(g,indent=2)+'\n')
from phase_5_geometry_helpers import Geometry,signed_distance
geometry=Geometry.from_draft(OUT/'geometry_copy.json',640,480)
signA=1 if sum(signed_distance(p,geometry.p1,geometry.p2) for p in geometry.side_a)>0 else -1
mapping=[];matched=set()
for e in a:
 matches=newkeys.get(origin_key(e),[])
 matches=[n for n in matches if len(refs(e)&refs(n))>=2]
 if len(matches)>1:raise RuntimeError('Ambiguous candidate mapping')
 n=matches[0] if matches else None
 if n:matched.add(n['event_id'])
 source=e['evidence']['source_frames'];first,last=min(source),max(source);t=e['track_id'];origin=e['evidence']['last_observed_origin_frame']
 local=[d for d in diag[t] if d.get('last_origin_frame')==origin]
 if not local:local=sorted(diag[t],key=lambda d:abs((d.get('last_origin_frame') or d['last_observed_frame'])-origin))[:1]
 d=local[0] if local else {}
 overlapping=[x for x in epi[t] if x['start_frame']<=last and x['end_frame']>=first]
 local_audit=[x for x in audit[t] if first<=x['source_ref']['frame_index']<=last]
 raw=[o for o in bytrack[t] if first<=o['frame_index']<=last and o['class_name'] in {'car','truck','motorcycle','bus'}]
 sign=signA if e['direction']=='A_TO_B' else -signA
 distance=lambda o:signed_distance(((o['raw_bbox'][0]+o['raw_bbox'][2])/2,o['raw_bbox'][3]),geometry.p1,geometry.p2)*sign
 net=distance(raw[0])-distance(raw[-1]) if raw else None
 maxrun=0;maxprogress=0.;run=[]
 for o in raw:
  if run and o['frame_index']!=run[-1]['frame_index']+1:run=[]
  run.append(o);maxrun=max(maxrun,len(run));maxprogress=max(maxprogress,max(distance(q) for q in run)-distance(o))
 disposition=d.get('disposition','NO_ASSOCIATED_DIAGNOSTIC')
 if n:mechanism='RETAINED_SOURCE_CANDIDATE' if e['route']==n['route'] else 'RETAINED_CANDIDATE_ROUTE_CHANGED'
 elif 'PENDING'==disposition:mechanism='IDENTITY_OR_ROLE_PENDING'
 elif len(overlapping)>1:mechanism='EPISODE_CONTEXT_SPLIT'
 elif disposition=='TURNED_AWAY_WITHOUT_CONFIRMED_PASSAGE':mechanism='MEASURED_RETREAT_OR_TURN'
 elif net is not None and net < 0:mechanism='SOURCE_ENDPOINTS_MOVING_AWAY'
 elif maxrun<3:mechanism='FEWER_THAN_THREE_CONTIGUOUS_MEASUREMENTS'
 elif maxprogress<25:mechanism='APPROACH_DISPLACEMENT_UNDER_25PX'
 elif disposition=='PHYSICAL_EPISODE_ENDED_NO_TIMER_INHERITANCE':mechanism='EPISODE_CLOSED_NO_TIMER_INHERITANCE'
 else:mechanism='OTHER_ELIGIBILITY_OR_OBSERVATION_GUARD'
 mapping.append({'old_event_id':e['event_id'],'old_display_id':e['display_id'],'raw_track_id':t,'category':e['category'],'direction':e['direction'],'old_route':e['route'],'old_activation_frame':e['activation_frame'],'old_decision_frame':e['decision_frame'],'source_first_frame':first,'last_origin_frame':origin,'source_last_frame':last,'source_frames':json.dumps(source),'new_event_id':n['event_id'] if n else '', 'new_route':n['route'] if n else '', 'mapping_status':'SAME_SOURCE_CANDIDATE' if n else 'NO_ACCEPTED_SOURCE_COUNTERPART','mechanism_documentary':mechanism,'new_diagnostic':disposition,'diagnostic_passage_id':d.get('passage_id'),'overlapping_raw_contexts':len(overlapping),'max_contiguous_vehicle_frames':maxrun,'max_contiguous_toward_progress_px':maxprogress,'endpoint_toward_progress_px':net,'physical_passage_adjudication':'NOT_VISUALLY_REVIEWED_YET'})
with (OUT/'exhaustive_mapping.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(mapping[0]));w.writeheader();w.writerows(mapping)
newonly=[e for e in b if e['event_id'] not in matched]
summary={'old_inferred':len(a),'new_inferred':len(b),'same_source_candidates':len(matched),'old_without_accepted_source_counterpart':len(a)-len(matched),'new_without_old_accepted_source_counterpart':len(newonly),'net_delta':len(b)-len(a),'mechanism_counts':dict(Counter(v['mechanism_documentary'] for v in mapping)),'new_without_old_counterpart':[{k:e[k] for k in ['event_id','track_id','category','direction','route','activation_frame']}|{'source_frames':e['evidence']['source_frames']} for e in newonly],'matching_basis':'same category/direction + last observed origin source frame and detector-linked raw bbox/index + >=2 exact raw measurement refs; event ID not compared','classification_limit':'mechanisms are descriptive artifact classifications, not physical ground truth'}
(OUT/'mapping_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
# Predeclare visual strata: all nine old OCCLUSION, every mechanism,
# all new-only inferred candidates. This is targeted development review.
selected={e['event_id']:('ALL_OLD_OCCLUSION',e) for e in a if e['route']=='OCCLUSION_DIFF_POLYGON'}
for mech in sorted(set(v['mechanism_documentary'] for v in mapping)):
 candidates=[v for v in mapping if v['mechanism_documentary']==mech]
 x=candidates[0];e=next(e for e in a if e['event_id']==x['old_event_id']);selected.setdefault(e['event_id'],('FIRST_BY_FROZEN_EVENT_ORDER_PER_MECHANISM:'+mech,e))
for e in newonly:selected[e['event_id']]=('ALL_NEW_ONLY_INFERRED',e)
# Specific outgoing fragment856 user/audit knowncase.
for e in a:
 if e['track_id']==856:selected[e['event_id']]=('KNOWN_UNRESOLVED_WHITE_SCOOTER',e)
visual=[]
for event_id,(stratum,e) in selected.items():
 samples=e['evidence']['source_frames'];start,end=min(samples),max(samples)
 chosen=set([start,end,max(0,start-12),min(9127,end+12)])
 chosen.update(round(start+(end-start)*f/7) for f in range(8))
 # Add actual nearest measurements; long gaps remain explicit source views.
 obs=[o['frame_index'] for o in bytrack[e['track_id']] if start<=o['frame_index']<=end]
 if obs:
  chosen.update([obs[len(obs)//4],obs[len(obs)//2],obs[3*len(obs)//4]])
 visual.append({'case_id':('NEW' if event_id.startswith('b_v4') else 'OLD')+'-raw'+str(e['track_id'])+'-f'+str(e['activation_frame']),'stratum':stratum,'event_id':event_id,'raw_track_id':e['track_id'],'direction':e['direction'],'route':e['route'],'category':e['category'],'source_frames':samples,'frames_to_review':sorted(chosen),'status':'PLANNED'})
(OUT/'visual_plan.json').write_text(json.dumps(visual,indent=2)+'\n')
# Save target record metadata so image receipts can bind exact source pixels.
(OUT/'selected_record_metadata.json').write_text(json.dumps({str(f):{'frame_index':f,'detector_input_frame_pixel_sha256':bysource[f]['detector_input_frame_pixel_sha256'],'emitted_tracks':bysource[f]['emitted_tracks']} for f in sorted({f for v in visual for f in v['frames_to_review']})},indent=2)+'\n')
