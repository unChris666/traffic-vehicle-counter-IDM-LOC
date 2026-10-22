import csv,json,re,shutil
from pathlib import Path
R=Path('/workspace/traffic-vehicle-counter-IDM-LOC');O=R/'results/phase_9/20261020_QC_BV4_SIANG'
rows=[json.loads(s) for s in (O/'review_decisions.jsonl').read_text().splitlines()]
def label(row):
 a=row['recommended_action']
 if row['qc_status']=='UNRESOLVED':return 'Kategori bisnis OPEN' if row['group']=='duplicates' else 'Bukti role/identitas belum cukup'
 if row['proposed_count_delta_vs_machine']==1:return 'Pedestrian54: gunakan adjudikasi yang sudah ada' if row['raw_track_id']==54 else 'SUV3582: satu CAR passage terukur'
 if a=='RIDER_COMPONENT_PLUS_ZERO':return 'Rider/passenger, +0'
 if a=='NON_INDEPENDENT_OCCUPANT_PLUS_ZERO':return 'Komponen occupant kendaraan, +0'
 if row['raw_track_id']==2560:return 'Fragmen passage2549/2561, +0 tambahan'
 if row['raw_track_id']==4820:return 'Duplikat cargo van4774, +0 tambahan'
 return 'Tidak eligible / tidak ada passage mandiri, +0'
text=['# Keputusan seluruh68kasus pending','',
 'Rekomendasi QC AI berbatas bukti, belum diterapkan pada machine. Frame0-based; rawID bukan identitas fisik global. Detail JSON tiapgroup menyimpan scope/parent/source SHA dan pengukuran. Unresolved tidak diganti nol.', '',
 '| Case | Kelompok | RawID | Frame keputusan baseline | Rekomendasi | Delta usulan | Bukti |',
 '|---|---|---:|---:|---|---:|---|']
for row in rows:
 p=R/row['evidence'][0]['path'];rel=p.relative_to(O);delta=row['proposed_count_delta_vs_machine'];v='unknown' if delta is None else f'{delta:+d}'
 text.append(f"|{row['case_id']}|{row['group']}|{row['raw_track_id']}|{row['baseline_decision_frame']}|{label(row)}|{v}|[buka]({rel.as_posix()})|")
(O/'PENDING_DECISIONS.md').write_text('\n'.join(text)+'\n')
with (O/'comparison.csv').open('w',newline='') as f:
 fields=['case_id','baseline_kind','baseline_reference','raw_track_id','qc_status','proposed_delta','future_machine_status','applied_to_machine']
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for row in rows:w.writerow(dict(case_id=row['case_id'],baseline_kind='PENDING',baseline_reference=row['baseline_passage_id'],raw_track_id=row['raw_track_id'],qc_status=row['qc_status'],proposed_delta=row['proposed_count_delta_vs_machine'],future_machine_status='NOT_RUN',applied_to_machine=False))
 for s in (O/'accepted_event_actions.jsonl').read_text().splitlines():
  a=json.loads(s);w.writerow(dict(case_id=a['case_id'],baseline_kind='ACCEPTED',baseline_reference=a['event_id'],raw_track_id=a['raw_track_id'],qc_status=a['action'],proposed_delta=-1,future_machine_status='NOT_RUN',applied_to_machine=False))
backlog=[
 ('P0','3/4/6','HYPOTHESIS_CLIQUE_SUPPRESSES_DISTINCT_OBJECT','4552/4480 at7615–7637','Retained whole-ID unit names plus exact-frame links and source negative coexistence','Keep unverified clique as hypothesis; separate state until positive episode-scoped proof','Preserve both physical objects; no retroactive future alias','4552motor must not disappear into4480car; verify true duplicates still one'),
 ('P0','5/6','BBOX_JITTER_ON_STATIONARY_OBJECT','IDENTITY28+0;2536,2584,2680,3512,4569,4627','Source body/road context, rawbbox quality, geometry and occlusion','Test stationary/moving eligibility and anchor-quality guards; optional reviewed road mask','Parked/occluded candidates+0; clocks unchanged','A vehicle parked then genuinely departing can re-arm; camera shake not false movement'),
 ('P0','3/4/6','CROSS_CATEGORY_PHYSICAL_DUPLICATE','2697/2706;3555/3563','Temporal duplicate/component candidates across vehicle classes','Resolve physical unit before category; positive scoped links and negative constraints','One passage for MPV or loaded motorcycle','Adjacent realvehicles stay separate even when sameclass/nearby'),
 ('P0','3/6','SAME_CLASS_RAW_ID_REUSE','2445;2583;4567;1107','Rawtrack episodes plus source spatial/object context','Cut contaminated origin/timer history; do not rely only on class switch or one center jump','No event assembled from different objects','Preserve continuous object despite harmless class jitter'),
 ('P0','6/8','FINALIZE_PASSAGE_BEFORE_AGGREGATION','4934/4946/4953;4251/4281;4149/4367','All candidateevents, scoped alias/components, measured/inferred evidence','Offline canonical passage reconciliation, cancel duplicate estimates, upgrade+0','At most one active event per physical passage; no false return','A genuine measured return still gets one new passage'),
 ('P1','3/6','BOUNDED_ROLE_AND_OCCUPANT','ROLE29;2531;3434/3593;2958/3185','Positive person-parent scope and contradictory source evidence','Carry/reconfirm role only within evidenced physical context; generic vehicle component proposal','Rider/occupant+0; unknown never automatic pedestrian','Pedestrian near motor and person gettingoff motor remain distinct'),
 ('P1','5/6','BAND_BORN_COVERAGE','49;4552;4614;4709/4630','Source-linked measured BC pairs, fullsource and jitter counterexamples','Experiment explicit band-born measured route after unit/role gates','Recover valid visible crossings without relaxing alltimeouts','Touch/oscillation/endpoints/gaps still not automatically accepted'),
 ('P1','2/6','BUSINESS_TAXONOMY','2549,3761,4115,4774','Physical body/usage categories and business decision','Document mapping passenger/goods/minibus/BUS and display/schema consequences','Stable category per physical passage','Do not map rawbus/car/truck only to force pendingdown'),
 ('P1','7','NIGHT_GENERALIZATION','Other TGDI malam sources, not audited here','Raw/night baseline and frozen newcounting profile','Prospective QC on samephysicalpassages; enhancement separateexperiment','Report benefits/regressions/cost','Do not infer gamma production reliability from daylightQC'),
 ('P1','1/8','BIDIRECTIONAL_QC_COVERAGE','All8videos; sourcefirst seed and noncandidate discovery','Verified source/timebase/config, case/passageinventory, event/pending','Run sameQCpacket pervideo with explicit sampled/full coverage','Report unknowns and missed/noncandidate cases','Pending zero alone is never acceptance')]
with (O/'improvement_backlog.csv').open('w',newline='') as f:
 fields=['priority','phases','mechanism','evidence_cases','input','proposed_process','expected_output','regression_guard'];w=csv.writer(f);w.writerow(fields);w.writerows(backlog)
with (O/'unresolved_decisions.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['case_id','raw_track_id','group','baseline_decision_frame','recommended_action','detail_ledger'])
 for row in rows:
  if row['qc_status']=='UNRESOLVED':w.writerow([row[k] for k in ['case_id','raw_track_id','group','baseline_decision_frame','recommended_action','detail_ledger']])
for p in Path('/tmp/qc-tools').glob('*.py'):shutil.copyfile(p,O/'audit_tools'/p.name)
# Formatting only, for newly authored audit prose. Avoid changing machine ledgers/hashes.
units='accepted|pending|kasus|frame|row|tes|observasi|event|rekomendasi|measured|inferred|kandidat|counterpart|hilang|baru|progress|guard|retreat|parkir|motor|role|rider|person|occupant|unit|pasangan|source|seed|OCCLUSION|endpoint|count|false|QC_DECIDED|UNRESOLVED|sample|van|pickup|minivan|cargo|car|truck|identity|selesai|geometry|LINE_MARGIN|px|detik|berkas|hilang|park|row|rekomendasi|diagnostic'
for p in list(O.rglob('*.md'))+[R/'docs/PHASE_9_QC_RECOMMENDATIONS.md']:
 s=p.read_text();s=re.sub(r'(?<=\d)(?=(?:'+units+r')\b)',' ',s)
 s=re.sub(r'\b(seluruh|semua|sebanyak|terdapat|dari|ada|hanya|total|sekitar|Tanggal|Oktober|Phase|timeout)(?=\d)',r'\1 ',s,flags=re.I)
 s=re.sub(r'^-(?=\d)','- ',s,flags=re.M);s=s.replace('zona waktuAsia','zona waktu Asia').replace('25kandidat','25 kandidat').replace('satuMPV','satu MPV').replace('satumotor','satu motor').replace('duaunit','dua unit').replace('empatkendaraan','empat kendaraan').replace('117artefak','117 artefak').replace('8konflik','8 konflik')
 p.write_text(s)
print({'pending_markdown_rows':len(rows),'comparison_rows':len(rows)+16,'backlog_items':len(backlog),'unresolved_csv_rows':sum(r['qc_status']=='UNRESOLVED' for r in rows)})
