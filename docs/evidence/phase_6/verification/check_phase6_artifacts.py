from pathlib import Path
from collections import Counter
import gzip,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[4]
RUN=Path(sys.argv[1])
OUT=Path(sys.argv[2])
checks=[]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def ident(pre,x):return pre+hashlib.sha256(canon(x).encode()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def check(name,condition,context=None):
 checks.append({'check':name,'passed':bool(condition),'context':context})
def strict(name,condition,context=None):
 check(name,condition,context)
 if not condition: raise AssertionError(name)
report=load(RUN/'report.json');software=report['software_report'];config=load(RUN/'configuration_input.json');reviews=load(RUN/'review_input.json')
machine=rows(RUN/'machine_decisions.jsonl.gz');resolved=rows(RUN/'resolved_decisions.jsonl.gz');events=rows(RUN/'accepted_events.jsonl.gz');aggregate=load(RUN/'aggregate.json');queue=rows(RUN/'audit_queue.jsonl.gz');rejected=rows(RUN/'rejected_decisions.jsonl.gz');manifest=load(RUN/'execution_manifest.json')
for item in manifest['artifacts']:
 p=RUN/item['path'];strict('output artifact '+item['path'],p.is_file() and p.stat().st_size==item['size_bytes'] and sha(p)==item['sha256'])
strict('unique accepted event IDs',len({e['event_id'] for e in events})==len(events))
strict('aggregate accepted event list',aggregate['total']==len(events) and aggregate['event_ids']==sorted(e['event_id'] for e in events))
for field,key in [('by_category','category'),('by_direction','direction')]:
 c=Counter(e[key] for e in events);strict('aggregate '+field,all(v==c.get(k,0) for k,v in aggregate[field].items()) and not(set(c)-set(aggregate[field])))
strict('machine events zero',not rows(RUN/'machine_events.jsonl.gz') and load(RUN/'machine_aggregate.json')['total']==0)
strict('machine decisions not silently changed',all(d['status']!='accepted' and d['accepted_count_event'] is False for d in machine))
strict('queue equals resolved pending',queue==[d for d in resolved if d['status']=='pending_review'])
strict('rejected equals resolved rejected',rejected==[d for d in resolved if d['status']=='rejected'])
strict('machine/resolved same candidate identities',len(machine)==len(resolved) and {d['candidate_id'] for d in machine}=={d['candidate_id'] for d in resolved})
identity=config['input_identity'];review_mapping={canon(r['selector']):r for r in reviews['decisions']};machine_mapping={d['candidate_id']:d for d in machine};decision_mapping={d['candidate_id']:d for d in resolved}
semantic={k:config[k] for k in ['contract_version','metric','review_policy','neutral_band_px','confirmation_observations','input_identity']}
metadata={k:None for k in ['store_code','store_name','latitude','longitude','day_type','recording_period']};metadata.update(config.get('recording_metadata',{}));semantic['recording_metadata']=metadata
config_id=ident('cc6_',semantic);strict('semantic config identity',config_id==software['counting_config_id'])
strict('source review namespace',reviews['input_identity']==identity)
source_paths={
 'diagnostics':ROOT/'docs/evidence/phase_5/20261011T161440_100155Z_2e39a11c/b0_c1_diagnostics.jsonl.gz',
 'records':ROOT/'docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz',
 'geometry':ROOT/'docs/evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json',
}
for key,path in source_paths.items():
 strict('actual input hash '+key,sha(path)==identity[key+'_sha256']==report['input_sha256'][key])
source_diagnostics={}
for diagnostic in rows(source_paths['diagnostics']):
 if diagnostic['type'] not in ('GEOMETRY_TRANSITION','AMBIGUOUS_GAP','AMBIGUOUS_ENDPOINT'):continue
 if diagnostic['type']=='GEOMETRY_TRANSITION':
  selector={k:diagnostic[k] for k in ['track_id','crossing_frame_start','crossing_frame_end','direction']}
 else:selector={k:diagnostic[k] for k in ['track_id','frame_index','type']}
 key=ident('pc6_',{'input_identity':identity,'selector':selector,'geometry_id':diagnostic.get('geometry_id')})
 source_diagnostics[key]=diagnostic
strict('all retained counting selectors covered',set(source_diagnostics)==set(machine_mapping))
for cid,decision in machine_mapping.items():
 strict('original diagnostic unchanged '+cid,decision['diagnostic']==source_diagnostics[cid])
 strict('resolved diagnostic unchanged '+cid,decision_mapping[cid]['diagnostic']==decision['diagnostic'])
 if decision['diagnostic_type']=='GEOMETRY_TRANSITION':
  diag=decision['diagnostic'];support=decision['measurement_support']
  strict('full measured support window '+cid,[r['frame_index'] for r in support]==list(range(diag['origin_frame'],diag['confirmation_frame']+1)))
  strict('full raw class histogram '+cid,dict(Counter(r['metadata']['class_name'] for r in support))==decision['raw_class_histogram'])
  families={'vehicle' if k in {'car','motorcycle','truck','bus'} else 'person' if k=='person' else 'unrelated' for k in decision['raw_class_histogram']}
  strict('hard unit change flag '+cid,('UNIT_COMPONENT_CHANGE' in decision['hard_block_reasons'])==(len(families)>1))

review_index=load(ROOT/'docs/evidence/phase_6/review_samples/TOR3-PAGI/sample_index.json')
artifact_frames={a['path']:set(case['frames']) for case in review_index['cases'] for a in case['artifacts'].values()}
for key in ('source_video_sha256','records_sha256','diagnostics_sha256','geometry_sha256'):
 expected=identity['video_sha256'] if key=='source_video_sha256' else identity[key]
 strict('sample index source '+key,review_index[key]==expected)
pixel_review=load(ROOT/'docs/evidence/phase_6/review_samples/TOR3-PAGI/pixel_review.json')
strict('pixel review index binding',pixel_review['source_sample_index_sha256']==sha(ROOT/'docs/evidence/phase_6/review_samples/TOR3-PAGI/sample_index.json'))
strict('pixel review case/frame scope',pixel_review['actual_reviewed_cases']==len(review_index['cases'])==len(pixel_review['reviews']) and pixel_review['exact_unique_sample_frames']==len({f for case in review_index['cases'] for f in case['frames']}))
for visual in pixel_review['reviews']:
 for key in ('raw_contact','overlay_contact'):
  ref=visual[key];strict('pixel declaration hash '+ref['path'],sha(ROOT/ref['path'])==ref['sha256'])
  strict('pixel declaration indexed frames '+ref['path'],set(visual['exact_frames_opened']).issubset(artifact_frames[ref['path']]))
strict('pixel review limitations explicit',pixel_review['human_review'] is False and pixel_review['formal_ground_truth'] is False and pixel_review['geometry_or_models_replayed'] is False)

all_source_pairs={}
for d in resolved:
 for s in d.get('measurement_support',[]):all_source_pairs[(d['track_id'],s['frame_index'])]=s
source_path=ROOT/'docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz'
strict('retained source hash',sha(source_path)==identity['records_sha256'])
found={};frame_count=0
with gzip.open(source_path,'rt') as f:
 for line in f:
  r=json.loads(line);frame_count+=1
  for o in r['emitted_tracks']:
   key=(o['track_id'],r['frame_index'])
   if key not in all_source_pairs:continue
   ref=all_source_pairs[key];box=o['raw_bbox'];raw=r['raw_detections'][o['original_detection_index']]
   strict('raw source '+str(key),ref['point']==[(box[0]+box[2])/2,box[3]] and box==raw['bbox_xyxy_pixels'] and all(ref['metadata'][k]==o[k]==raw[k] for k in ['class_id','class_name','confidence']) and ref['metadata']['original_detection_index']==o['original_detection_index'] and ref['metadata']['measurement_provenance']=='retained_phase_2_detection')
   found[key]=True
strict('all measurement references found',len(found)==len(all_source_pairs),{'requested':len(all_source_pairs),'found':len(found)})
strict('frame count report',frame_count==software['frames_processed'])
for e in events:
 strict('event accepted boundary '+e['event_id'],e['type']=='CountEvent' and e['accepted_count_event'] is True and e['status']=='accepted')
 strict('event stable ID '+e['event_id'],e['event_id']==ident('pe6_',{'input_identity':identity,'counting_config_id':config_id,'physical_unit_id':e['physical_unit_id'],'passage_id':e['passage_id']}))
 members=[decision_mapping[k] for k in e['source_candidate_ids']]
 strict('event member links '+e['event_id'],all(d['status']=='accepted' and d['event_id']==e['event_id'] and d['physical_unit_id']==e['physical_unit_id'] and d['passage_id']==e['passage_id'] for d in members))
 strict('one representative marker '+e['event_id'],sum(d['accepted_count_event'] is True for d in members)==1 and e['representative_candidate_id'] in e['source_candidate_ids'])
 rep=decision_mapping[e['representative_candidate_id']]
 strict('event supporting data '+e['event_id'],e['geometry_evidence']==rep['diagnostic'] and e['measurement_support']==rep['measurement_support'] and e['class_history']==rep['class_history'] and e['raw_class_histogram']==rep['raw_class_histogram'])
 strict('event class/unit hard blocks '+e['event_id'],all(not d['hard_block_reasons'] for d in members))
 for d in members:
  review=review_mapping[canon(d['selector'])];covered=set()
  strict('positive review '+d['candidate_id'],review['decision']=='CONFIRM_PASSAGE' and all(review[k] is True for k in ['unit_confirmed','category_confirmed','identity_confirmed']))
  strict('review deterministic ID '+d['candidate_id'],d['review_id']==ident('pr6_',{'input_identity':identity,'review':review}))
  for ev in review['evidence']:
   p=ROOT/ev['path'];strict('review evidence hash '+ev['path'],p.is_file() and sha(p)==ev['sha256'])
   if ev['path'] in artifact_frames:strict('review evidence actual indexed frames '+ev['path'],set(ev['frame_indices']).issubset(artifact_frames[ev['path']]))
   covered.update(ev['frame_indices'])
  strict('review scope '+d['candidate_id'],set(d['required_review_frames']).issubset(covered))
strict('software report accepted counts',software['accepted_event_count']==len(events) and software['accepted_candidate_members']==sum(d['status']=='accepted' for d in resolved) and software['resolved_decision_statuses']==dict(Counter(d['status'] for d in resolved)))
strict('not model rerun/GT',software['geometry_detector_tracker_encoder_rerun'] is False and software['complete_video_traffic_count_established'] is False and software['ground_truth_available'] is False)
result={'claim_type':'EXECUTED_INDEPENDENT_ARTIFACT_AND_SOURCE_AUDIT_NOT_GROUND_TRUTH','run_dir':str(RUN),'checks':checks,'checks_run':len(checks),'checks_passed':sum(c['passed'] for c in checks),'successful':all(c['passed'] for c in checks),'frames_scanned_for_source_validation':frame_count,'measurement_references_verified':len(found),'unique_accepted_event_subtotal':len(events),'by_category':aggregate['by_category'],'by_direction':aggregate['by_direction'],'resolved_statuses':dict(Counter(d['status'] for d in resolved)),'method_sha256':sha(__file__),'scope':'No counting or geometry rerun; retained outputs reconciled with source measurements and evidence hashes. Pixel truth interpretation is not established by hashes.'}
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
