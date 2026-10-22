"""Evidence/readiness checks only. No detector, tracker, ReID or counting replay."""
import csv,gzip,hashlib,json,re
from collections import Counter
from pathlib import Path
import cv2
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC');O=R/'results/phase_9/20261020_QC_BV4_SIANG'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def save(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+'\n')
base=json.loads(gzip.decompress((R/'results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz').read_bytes()))
pending={d['passage_id'] for d in base['decisions'] if d['status']=='pending'};q=rows(O/'review_decisions.jsonl')
assert len(q)==68 and len({x['case_id'] for x in q})==68 and {x['baseline_passage_id'] for x in q}==pending
assert Counter(x['group'] for x in q)=={'roles':29,'identity':31,'duplicates':8}
refs=0
for record in q+rows(O/'accepted_event_actions.jsonl')+rows(O/'unmatched/unmatched_passages.jsonl'):
 assert record['evidence'],record.get('case_id')
 for proof in record['evidence']:
  p=R/proof['path'];assert p.is_file() and sha(p)==proof['sha256'],str(p);refs+=1
control=rows(O/'accepted_timeout_control/per_event_decisions.jsonl');expected={e['event_id'] for e in base['events'] if e['route']=='ESTIMATED_TIMEOUT'}
assert len(control)==34 and {x['event_id'] for x in control}==expected
actions=rows(O/'accepted_event_actions.jsonl');assert len(actions)==16 and len({a['event_id'] for a in actions})==16
all_events={e['event_id']:e for e in base['events']}
for a in actions:
 assert a['event_id'] in all_events and a['proposed_count_delta']==-1
 assert all_events[a['event_id']]['evidence']['measured_crossing']==a['measured_crossing']
assert not ({a['event_id'] for a in actions}&{a['keep_event_id'] for a in actions if a['keep_event_id']})
with (O/'removed_inferences/exhaustive_mapping.csv').open() as f:mapping=list(csv.DictReader(f))
assert len(mapping)==463
mapping_summary=json.loads((O/'removed_inferences/mapping_summary.json').read_text());assert mapping_summary['same_source_candidates']==44 and mapping_summary['old_without_accepted_source_counterpart']==419 and len(mapping_summary['new_without_old_counterpart'])==7
assert 463-419+7==51
old=json.loads((R/'results/b_v4/artifact_manifest.json').read_text());old_checks=[]
for item in old['files']:
 p=R/'results/b_v4'/item['path'];assert p.is_file() and sha(p)==item['sha256'];old_checks.append(item['path'])
software=json.loads((R/'results/b_v4/verification/software_validation.json').read_text())
for key in ['new_source_sha256','b_v3_executables_unchanged']:
 for name,digest in software[key].items():assert sha(R/'notebooks'/name)==digest,name
cache=next(Path('/tmp/qc-donor').rglob('track_records.jsonl.gz'));frame_hashes={}
with gzip.open(cache,'rt') as f:
 for line in f:
  item=json.loads(line);frame_hashes[item['frame_index']]=item['detector_input_frame_pixel_sha256']
assert len(frame_hashes)==9128 and sha(cache)==base['source_identity']['records_sha256']
assert sha(Path('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4'))==base['source_identity']['video_sha256']
native,derived=[],[]
for p in O.rglob('*.png'):
 match=re.search(r'(?:frame-|native-f|native-|raw-?\d+-f|accepted-confirm-f|initial-|^f)(\d{1,6})',p.name)
 if not match:continue
 image=cv2.imread(str(p));assert image is not None
 if image.shape!=(480,640,3):continue
 frame=int(match.group(1));digest=hashlib.sha256(image.tobytes()).hexdigest();row={'path':str(p.relative_to(O)),'frame_index':frame,'pixel_sha256':digest,'file_sha256':sha(p)}
 if digest==frame_hashes[frame]:native.append(row)
 else:
  # The raw-... PNGs produced by challenge helpers may contain drawn boxes;
  # primary frame-/native-f files must be genuine source images.
  assert any(tag in p.name for tag in ['raw-','accepted-challenge','accepted-confirm']),str(p)
  row['kind']='DERIVED_BBOX_OVERLAY_NOT_NATIVE_PIXEL_PROOF';derived.append(row)
assert native
save(O/'evidence/source_pixel_validation.json',{'verified_native_png_files':len(native),'unique_native_source_frames':len({x['frame_index'] for x in native}),'derived_overlay_files':len(derived),'native_files':native,'derived_files':derived})
save(O/'baseline_guard_after.json',{'checked':len(old_checks),'all_pass':True,'source_executables_unchanged':True,'machine_policy_and_results_unchanged':True,'files':old_checks})
result={'pending_coverage':'PASS_ALL68_UNIQUE_BASELINE_KEYS','group_counts':dict(Counter(x['group'] for x in q)),
 'pending_recommendation_counts':dict(Counter(x['qc_status'] for x in q)),
 'accepted_timeout_control':'PASS_ALL34_UNIQUE_EVENT_IDS','accepted_cancel_unique':16,
 'mapping_records':len(mapping),'mapping_equation':'463-419+7=51', 'new_only_inferences':7,
 'evidence_reference_hash_checks':refs,'baseline_artifact_hash_checks':len(old_checks),
 'source_executable_hashes_unchanged':True,'source_cache_frames':len(frame_hashes),
 'native_png_files_checked':len(native),'unique_source_frames_from_native_pngs':len({x['frame_index'] for x in native}),
 'derived_pngs_identified':len(derived),'status':'PASS_SCOPED_QC_ARTIFACT_INTEGRITY',
 'continuous_visual_full_video_review':False,'physical_ground_truth_accuracy_established':False,
 'new_detector_tracker_reid_counting_enhancement_run':False,'machine_ledger_modified':False}
save(O/'validation.json',result);print(json.dumps(result,indent=2))
