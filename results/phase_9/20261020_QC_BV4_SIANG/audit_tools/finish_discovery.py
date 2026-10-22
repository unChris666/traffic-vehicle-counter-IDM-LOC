import csv,gzip,hashlib,json
from pathlib import Path
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC');O=R/'results/phase_9/20261020_QC_BV4_SIANG';U=O/'unmatched'
d=json.loads(gzip.decompress((R/'results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz').read_bytes()))
def proof(name):
 p=U/'evidence'/name
 assert p.is_file()
 return {'path':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
pairs=json.loads((U/'geometry_pair_search.json').read_text())['pairs']
def pp(track):return [x for x in pairs if x['track_id']==track]
cases=[
 {'case_id':'NO-CANDIDATE-49','raw_track_ids':[49], 'source_frames':[24,26,28,29,30,31,32,33,34,36,40,44],
  'observation':'Motor berbeda dari11 terlihat bergerak B_TO_A, pertama terukur dalam band. Pair BC31→32 proper finite crossing, tetapi tidak membentuk origin/state sebelum crossing.',
  'status':'VISIBLE_PASSAGE_POLICY_COVERAGE_GAP','action':'PROPOSE_BAND_BORN_MEASURED_CROSSING_EXPERIMENT_NOT_TIMEOUT_RELAXATION','count_delta':None,
  'evidence':[proof('motor49.jpg')], 'geometry_pairs':pp(49),'machine_candidate_status':'NO_EVENT_NO_PENDING_FOR_RAW49'},
 {'case_id':'NO-CANDIDATE-4552','raw_track_ids':[4480,4552], 'source_frames':[7600,7605,7610,7615,7620,7625,7630,7636,7637,7640,7650,7660],
  'observation':'Motor pengendara hoodie merah4552 dan SUV4480 adalah dua objek berbeda yang koeksis. Namespace retained-clique4480,4552 yang belum terverifikasi membuat observasi motor tersupresi. Kemudian4552 berganti ke mobil Honda; konteks itu tidak boleh berlaku mundur.',
  'status':'CONFIRMED_WRONG_UNIT_GROUP_COVERAGE_HOLE_PASSAGE_GATE_OPEN','action':'SPLIT_MOTOR_EPISODE_4552_FROM_CAR4480_AND_LATER_CAR4552_NO_GLOBAL_ALIAS','count_delta':None,
  'evidence':[proof('motor4552.jpg')], 'geometry_pairs':pp(4552),'machine_candidate_status':'NO_INDEPENDENT_MOTOR_EVENT_OR_PENDING'},
 {'case_id':'NO-CANDIDATE-13-24','raw_track_ids':[13,24], 'source_scope':{'start_frame':0,'end_frame':12,'continuous_visual_review':False},
  'observation':'Fragmen motor datang sangat awal video; origin/crossing lengkap sebelum fragmen tidak tersedia. Kehadiran objek bukan otomatis passage valid.',
  'status':'UNRESOLVED_CLIP_START_OR_BAND_BORN','action':'NO_AUTOMATIC_PLUS_ONE_WITHOUT_PASSAGE_EVIDENCE','count_delta':None,'evidence':[]},
 {'case_id':'NO-CANDIDATE-2643','raw_track_ids':[2643,2632], 'status':'ALREADY_REPRESENTED_BY_ACCEPTED_TIMEOUT','action':'POSSIBLE_EVIDENCE_UPGRADE_PLUS_ZERO_NOT_NEW_PASSAGE','count_delta':0,
  'observation':'Subreview sumber mengaitkan diagnostic2643 dengan physical passage2632 yang sudah diterima timeout4337; perlu pertahankan identity scope saat upgrade.', 'geometry_pairs':pp(2643),'evidence':[proof('motor2643.jpg')]},
 {'case_id':'NO-CANDIDATE-3255','raw_track_ids':[3255,3224], 'status':'ALREADY_REPRESENTED_BY_ACCEPTED_TIMEOUT','action':'POSSIBLE_EVIDENCE_UPGRADE_PLUS_ZERO_NOT_NEW_PASSAGE','count_delta':0,
  'observation':'Subreview sumber mengaitkan diagnostic3255 dengan physical passage3224 yang sudah diterima timeout5533; jangan menambah+1 dari ID lain.', 'geometry_pairs':pp(3255),'evidence':[proof('motor3255.jpg')]},
 {'case_id':'NO-CANDIDATE-5298','raw_track_ids':[5298], 'status':'EOF_CONFIRMATION_INCOMPLETE','action':'KEEP_UNRESOLVED_NO_POST_EOF_FRAMES','count_delta':None,
  'observation':'Pair9125→9126 berada tepat sebelum EOF9127; observasi pasca-crossing/konfirmasi belum lengkap. Jangan menambah frame atau timeout setelah EOF.', 'geometry_pairs':pp(5298),'evidence':[]},
 {'case_id':'NO-CANDIDATE-763','raw_track_ids':[763,816,856], 'status':'KNOWN_WHITE_SCOOTER_HISTORY_UNRESOLVED','action':'TRACE_BOUNDED_PHYSICAL_EPISODES_WITHOUT_GLOBAL_ALIAS','count_delta':None,
  'observation':'Kasus riwayat skuter putih yang sudah diketahui; pasangan BC bukan bukti bahwa tiga rawID otomatis satu passage yang belum dihitung.', 'geometry_pairs':pp(763),'evidence':[]},
]
for track in [2771,4614,4709]:
 cases.append({'case_id':f'DIAGNOSTIC-ONLY-{track}','raw_track_ids':[track], 'status':'DIAGNOSTIC_PAIR_NOT_PHYSICALLY_ADJUDICATED','action':'NEEDS_SOURCE_ROLE_IDENTITY_AND_JITTER_CHECK','count_delta':None,'geometry_pairs':pp(track),
   'observation':'Pencarian pengukuran sumber menemukan sign change, tetapi bukan inventaris passage fisik yang sudah diputuskan. Tidak dipromosikan menjadi hitungan.','evidence':[]})
for c in cases:
 if c['case_id']=='DIAGNOSTIC-ONLY-2771':
  c.update(status='SOURCE_REVIEW_DUPLICATE_OF_ACCEPTED2750',action='NO_ADDITIONAL_PASSAGE_PLUS_ZERO',count_delta=0,
   raw_track_ids=[2771,2750],observation='Root meninjau12frame4489–4539: bbox2771 menutup bagian belakang motor berpenumpang kuning yang juga dibox2750 pada4507–4511. Event2750/M1038 sudah diterima4516; diagnostic2771 bukan passage kedua.',evidence=[proof('root-diagnostic-2771.jpg')])
 if c['case_id']=='DIAGNOSTIC-ONLY-4614':
  c.update(status='SOURCE_REVIEW_MOVING_APPROACH_BAND_BORN_POLICY_OPEN',action='NO_AUTOMATIC_COUNT_FROM_TINY_NEAR_LINE_PAIR',count_delta=None,
   observation='Root meninjau12frame7631–7681: motor datang bergerak ke kanan mendekati kamera. Pair7651→7652 hanya berpindah BC1.57px di sekitargaris(−0.926→+0.361px); observasi awal berada di band. Ada gap cakupan eligibility, tetapi bukti arah/konfirmasi harus dinilai sebelum menerima hitungan.',evidence=[proof('root-diagnostic-4614.jpg')])
 if c['case_id']=='DIAGNOSTIC-ONLY-4709':
  c.update(status='SOURCE_REVIEW_DUPLICATE_CANDIDATE_AND_BAND_BORN_POLICY_OPEN',action='ONE_PHYSICAL_CANDIDATE4630_4709_NOT_PLUS_TWO',count_delta=None,
   raw_track_ids=[4709,4630],observation='Root meninjau12frame7691–7741: dua bbox4630/4709 pada7711 mencakup motor datang yang sama. Pair7711→7712 sangat dekatgaris(−0.162→+2.723px). Tidak ada event accepted4630/4709; normalisasi unit dan aturan band-born perlu diuji, bukan menghitung setiap ID.',evidence=[proof('root-diagnostic-4709.jpg')])
diagnostic=U/'geometry_pair_search.json'
for c in cases:
 c.update(claim_type='AI_QC_SOURCE_OR_DIAGNOSTIC_REVIEW_NOT_GT',machine_ledger_changed=False,source_video_sha256=d['source_identity']['video_sha256'])
 if not c['evidence']:
  c['evidence']=[{'path':str(diagnostic.relative_to(R)),'sha256':hashlib.sha256(diagnostic.read_bytes()).hexdigest(),'basis':'MEASUREMENT_DIAGNOSTIC_NOT_PHYSICAL_PIXEL_ADJUDICATION'}]
(U/'unmatched_passages.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases))

# Finish documentary matching of raw-first seeds without inventing an exact match.
inventory=json.loads((U/'source_inventory_raw_first.json').read_text())
for row in inventory:
 candidates=[e for e in d['events'] if row['start_frame']-30<=e['activation_frame']<=row['end_frame']+60]
 row['candidate_event_ids']=[e['event_id'] for e in candidates]
 row['machine_matching_status']='TIME_WINDOW_CANDIDATES_IDENTITY_NOT_ADJUDICATED'
 row['matching_limit']='Temporal shortlist only; physical equality not implied.'
 if row['source_inventory_id']=='RAW-B01':row['machine_matching_status']='CLIP_START_PARTIAL_PHYSICAL_PASSAGE_UNRESOLVED'
 if row['source_inventory_id']=='RAW-B02':row['machine_matching_status']='PERSON54_LINKED_TO_ROLE_QC_AND_EXISTING_REVIEW_ASSISTED_ADJUDICATION'
 if row['source_inventory_id']=='RAW-M01':row['machine_matching_status']='CONFIRMED_PHYSICAL_GROUP2706_2697_DUPLICATE_ACCEPTED'
 if row['source_inventory_id']=='RAW-B03':row['machine_matching_status']='PHYSICAL_CAR192_REPRESENTED_OTHER_FRAGMENT156_UNRESOLVED'
keys=list(inventory[0])
with (U/'source_inventory.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
 for row in inventory:w.writerow({**row,'candidate_event_ids':'|'.join(row['candidate_event_ids'])})

# Extraction manifests were initialized before review. Record completed review as reported,
# retaining the raw-first seed and separating it from pixel integrity.
p=U/'evidence/global_raw_manifest.json';m=json.loads(p.read_text())
for row in m['frames']:row['review_status']='REVIEWED_BY_AI_SUBREVIEWER_REPORTED_NOT_BLIND'
m['coverage_limit']='153 sampled frames at60source-frame spacing, not continuous review of9128frames.'
p.write_text(json.dumps(m,indent=2)+'\n')
print({'discovery_rows':len(cases),'raw_first_inventory_rows':len(inventory),'global_sampled_frames':len(m['frames'])})
