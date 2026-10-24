"""Strict explicit profiles; replay is an operation over one declared branch."""
from copy import deepcopy
from ..artifacts import require
PROFILES={'machine','review_assisted','replay'}
def valid_hash(value):return isinstance(value,str) and len(value)==64 and all(x in '0123456789abcdef' for x in value)
REQUIRED={'schema_version','profile','video_id','frame_count','source_identity','artifacts','source_manifest_sha256'}
OPTIONAL={'replay_branch','request_id','measurement_format'}
ALLOWED_ARTIFACTS={'measurements','geometry','policy','relationships','baseline_reviews','review_overlay','adjudications','baseline_result','historical_baseline'}

def validate_request(request):
 r=deepcopy(request)
 require(isinstance(r,dict) and REQUIRED<=set(r) and set(r)<=REQUIRED|OPTIONAL,'Missing/unknown traffic request fields')
 require(r['schema_version']=='traffic_request_v1' and isinstance(r['profile'],str) and r['profile'] in PROFILES,'Unsupported traffic profile/schema')
 require(isinstance(r['video_id'],str) and r['video_id'].strip() and '/' not in r['video_id'] and '\\' not in r['video_id'],'Explicit video ID required')
 require(type(r['frame_count']) is int and r['frame_count']>0,'Positive actual frame_count required')
 branch=r.get('replay_branch') if r['profile']=='replay' else r['profile']
 require(isinstance(branch,str) and branch in {'machine','review_assisted'},'Replay requires an explicit replay_branch')
 require(r['profile']=='replay' or 'replay_branch' not in r,'replay_branch only allowed on replay')
 a=r['artifacts'];require(isinstance(a,dict) and {'measurements','geometry','policy'}<=set(a) and set(a)<=ALLOWED_ARTIFACTS,'Invalid artifact set')
 require(r.get('measurement_format','notebook_native') in {'notebook_native','fresh_v1'},'Unsupported measurement format')
 if r.get('measurement_format')=='fresh_v1':
  require(branch=='machine' and not {'baseline_reviews','historical_baseline','review_overlay','adjudications','baseline_result','relationships'}&set(a),'Fresh machine input cannot inherit legacy review or relations')
 require(isinstance(r['source_identity'],dict),'Explicit source identity required')
 for ref in a.values():require(isinstance(ref,dict) and set(ref)=={'path','sha256'} and isinstance(ref['path'],str) and bool(ref['path']) and valid_hash(ref['sha256']),'Invalid artifact reference')
 require('baseline_reviews' not in a or 'historical_baseline' in a,'Historical review context needs an explicit frozen baseline')
 review_keys={'review_overlay','adjudications','baseline_result'}
 require(review_keys<=set(a) if branch=='review_assisted' else not review_keys&set(a),'Machine/review overlay mixing forbidden')
 for key in ['video_sha256','geometry_sha256','records_sha256']:
  require(valid_hash(r['source_identity'].get(key)),'Missing source hash '+key)
 for key in ['width','height']:require(type(r['source_identity'].get(key)) is int and r['source_identity'][key]>0,'Explicit native dimensions required')
 require(a['measurements']['sha256']==r['source_identity']['records_sha256'] and a['geometry']['sha256']==r['source_identity']['geometry_sha256'],'Source/artifact hash mismatch')
 require(valid_hash(r['source_manifest_sha256']),'Source manifest SHA required')
 return r,branch
