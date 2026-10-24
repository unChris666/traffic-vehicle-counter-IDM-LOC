"""Eight source-bound machine snapshots; category x direction x evidence pivot."""
from collections import Counter
from ..artifacts import require,semantic_hash
from .results import validate_native
CATEGORIES=('motorcycle','car','truck','bus','pedestrian')
DIRECTIONS=('A_TO_B','B_TO_A')

def aggregate(expected,results,*,experiment_sha256):
 require(len(expected)==8 and len(set(expected))==8,'Eight unique source slots required')
 ids=[v['video_id'] for v in results];require(len(set(ids))==len(ids) and set(ids)<=set(expected),'Duplicate rerun or foreign video')
 pivot={c:{d:{'measured':0,'estimated':0} for d in DIRECTIONS} for c in CATEGORIES}
 ledger=[];sources=set();versions={};pending=invalid=0;complete=True
 for slot in expected:
  row=next((r for r in results if r['video_id']==slot),None)
  if not row or row.get('status')!='SUCCEEDED':complete=False;continue
  require(row['experiment_sha256']==experiment_sha256 and row['branch']=='machine','Mixed policy/model/branch batch forbidden')
  require(row.get('scope')=='FULL_VIDEO','Smoke/prefix cannot enter full-video totals')
  native=validate_native(row['native']);require(native['source_identity']['video_sha256']==expected[slot],'Wrong video source')
  require(expected[slot] not in sources,'Same source repeated across slots');sources.add(expected[slot]);versions[slot]=row['result_version']
  for event in native['events']:
   c,d=event['category'],event['direction'];require(c in CATEGORIES and d in DIRECTIONS,'Unsupported event category/direction')
   evidence='measured' if event['evidence']['measured_crossing'] is True else 'estimated'
   pivot[c][d][evidence]+=1;ledger.append({'video_id':slot,'source_sha256':expected[slot],'event_id':event['event_id'],'category':c,'direction':d,'evidence':evidence})
  pending+=native['aggregate']['pending'];invalid+=native['aggregate']['invalid']
 require(len({(v['source_sha256'],v['event_id']) for v in ledger})==len(ledger),'Duplicate batch passage')
 vehicles=sum(1 for e in ledger if e['category']!='pedestrian')
 require(sum(x for c in pivot.values() for d in c.values() for x in d.values())==len(ledger),'Pivot/ledger mismatch')
 return {'schema_version':'traffic_batch_v1','execution_status':'SUCCEEDED' if complete else 'PARTIAL','result_quality':'PARTIAL',
  'experiment_sha256':experiment_sha256,'result_version':semantic_hash({'experiment':experiment_sha256,'versions':versions,'pivot':pivot}),
  'videos_expected':8,'videos_completed':len(versions),'complete_vehicle_total':vehicles if complete else None,
  'observed_vehicle_subtotal':vehicles,'pedestrian_total':len(ledger)-vehicles,'pivot':pivot,'events':ledger,
  'pending':pending,'invalid':invalid,'missing_or_failed':[v for v in expected if v not in versions],
  'semantics':'PASSAGES_IN_RECORDED_SAMPLES_NOT_UNIQUE_VEHICLES_OR_DAILY_TRAFFIC','production_ready':False}
