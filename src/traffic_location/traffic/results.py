"""Domain reconciliation and stable result identities, separate from native ledgers."""
from collections import Counter
from copy import deepcopy
import platform
from ..artifacts import require,semantic_hash

def validate_native(result):
 a=result['aggregate'];events=result['events']
 require(len(events)==a['total'],'Accepted total/event mismatch')
 require(len({e['event_id'] for e in events})==len(events),'Duplicate accepted event ID')
 measured=sum(e['evidence']['measured_crossing'] is True for e in events)
 require(measured==a['measured_total'] and len(events)-measured==a['inferred_total'],'Measured/estimated mismatch')
 require(dict(sorted(Counter(e['category'] for e in events).items()))==a['by_category'],'Category aggregation mismatch')
 require(dict(sorted(Counter(e['direction'] for e in events).items()))==a['by_direction'],'Direction aggregation mismatch')
 require(all(e.get('accepted_count_event') is True and e.get('status')=='accepted' for e in events),'Non-accepted event in accepted ledger')
 require(sum(d.get('status')=='pending' for d in result['decisions'])==a['pending'],'Pending decision aggregate mismatch')
 require(len(result['invalid_decisions'])==a['invalid'],'Invalid decision aggregate mismatch')
 return result

def wrap_native(result,*,request,branch,implementation_hash):
 validate_native(result);a=result['aggregate']
 runtime={'python':platform.python_version(),'implementation':platform.python_implementation()}
 fingerprint=semantic_hash({'source':request['source_identity'],'artifacts':{k:v['sha256'] for k,v in request['artifacts'].items()},
  'branch':branch,'video_id':request['video_id'],'frame_count':request['frame_count'],'implementation':implementation_hash,'runtime':runtime})
 return {'schema_version':'traffic_result_v1','execution_status':'SUCCEEDED',
  'result_quality':'PARTIAL','validation_level':'TECHNICAL_PILOT',
  'result_version':fingerprint,'branch':branch,'operation_profile':request['profile'],'runtime':runtime,
  'scope':{'video_id':request['video_id'],'source_frames':request['frame_count'],'processed_frames':result['report']['frame_count']},
  'summary':{'accepted_total':a['total'],'accepted_measured':a['measured_total'],'accepted_estimated':a['inferred_total'],
   'pending':a['pending'],'invalid':a['invalid'],'native_aggregate':deepcopy(a)},
  'source_identity':deepcopy(request['source_identity']),'native_semantic_sha256':semantic_hash(result),
  'legacy_baseline_review_context_present':'baseline_reviews' in request['artifacts'],
  'fresh_inference_executed':False,'production_ready':False,
  'limitations':['Counting correctness and identity/role generalization are not established by modular parity',
    'Machine native gate remains unresolved; review-assisted is not automatic model performance']}
