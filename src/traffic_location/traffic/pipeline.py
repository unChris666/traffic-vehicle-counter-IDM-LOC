"""Fresh per-call state over explicit source/config inputs. No pilot constants."""
from copy import deepcopy
from pathlib import Path
from .contracts import validate_request
from .measurements import read_measurements,relationship_evidence
from ._kernel import identity,publication,reviews,review_finalizer,review_metadata
from ._kernel.geometry import Geometry
from .results import wrap_native
from ..artifacts import artifact,read,require,sha,semantic_hash


def implementation_hash():
 root=Path(__file__).resolve().parent
 return semantic_hash({str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*.py'))
   if not p.name.startswith('render') and p.name!='inference_worker.py'})


def run(request,*,root):
 request,branch=validate_request(request);root=Path(root).resolve()
 refs=request['artifacts'];paths={k:artifact(v,root) for k,v in refs.items()}
 before={k:sha(p) for k,p in paths.items()}
 source=deepcopy(request['source_identity']);policy=read(paths['policy']);audit={}
 require(policy.get('execution_branch')==branch,'Effective policy branch differs from request')
 geometry_data=read(paths['geometry'])
 if geometry_data.get('source_video',{}).get('sha256'):
  require(geometry_data['source_video']['sha256']==source['video_sha256'],'Geometry belongs to a different source video')
 geometry=Geometry.from_draft(paths['geometry'],source['width'],source['height'])
 links=relationship_evidence(paths['relationships']) if 'relationships' in paths else {}
 base_reviews=[]
 if 'baseline_reviews' in paths:
  historical=read(paths['historical_baseline'])
  require(historical['source_identity']==source and historical['report']['policy']['review_manifest_sha256']==refs['baseline_reviews']['sha256'],'Historical baseline/review binding differs')
  manifest=read(paths['baseline_reviews'])
  require(manifest.get('donor_manifest_sha256')==request['source_manifest_sha256'],'Historical review source manifest differs')
  entries=[v for v in manifest['videos'] if v['video_id']==request['video_id']]
  require(len(entries)==1,'Historical review video missing/duplicate')
  require(all(entries[0][k]==source[k] for k in ['video_sha256','records_sha256','geometry_sha256']),'Historical review source differs')
  base_reviews=entries[0].get('reviews',[])
  # Baseline source-context reviews remain bounded, explicit, and source-linked.
  for review in base_reviews:
   require(review.get('confirmed_frames') and review.get('scopes'),'Unbounded historical review')
   for scope in review['scopes']:
    require(type(scope.get('start_frame')) is int and type(scope.get('end_frame')) is int and
      0<=scope['start_frame']<=scope['end_frame']<request['frame_count'],'Historical review scope outside video')
 if request.get('measurement_format')=='fresh_v1':
  from .fresh_bridge import frames as fresh_frames
  frames=fresh_frames(paths['measurements'],source,request['frame_count'],audit=audit)
 else:
  frames=read_measurements(paths['measurements'],source,request['frame_count'],relationships=links,
    baseline_reviews=base_reviews,baseline_reviews_sha256=refs.get('baseline_reviews',{}).get('sha256'),audit=audit)
 if branch=='review_assisted':
  overlay=read(paths['review_overlay'])
  require(overlay.get('donor_manifest_sha256')==request['source_manifest_sha256'],'Overlay parent manifest differs')
  reviewed=reviews.prepare_reviewed_frames(frames,overlay,source_identity=source,repo_root=root,
    source_records_path=paths['measurements'],video_id=request['video_id'],frame_count=request['frame_count'],
    overlay_sha256=refs['review_overlay']['sha256'],branch=branch)
  frames=reviewed['frames']
 resolved=identity.prepare_identity_frames(frames,geometry,policy,relationships=links)
 require([r['frame_index'] for r in resolved['frames']]==list(range(request['frame_count'])),'Missing/extra source frames')
 effective=deepcopy(policy);effective['episode_relations']=resolved.get('unit_relations',[])
 result=publication.replay_frames(resolved['frames'],geometry,source_identity=source,policy=effective)
 if branch=='review_assisted':
  adjudications=read(paths['adjudications'])
  require(adjudications['baseline_result_sha256']==refs['baseline_result']['sha256'],'Review baseline bytes mismatch')
  result=review_finalizer.finalize_reviewed_pending(result,adjudications,baseline_result=read(paths['baseline_result']),
    source_identity=source,finalization_frame=request['frame_count']-1,repo_root=root)
 result.update(video_id=request['video_id'],source_identity=source,branch=branch,
   frame_assignments=resolved['assignments'],component_links=resolved.get('component_links',[]))
 if branch=='review_assisted':
  review_metadata._decision_provenance(result,overlay,finalization_frame=request['frame_count']-1,overlay_sha256=refs['review_overlay']['sha256'])
  result=review_metadata._rename_event_ids(result)
  result['report'].update(version='b_v8_p1_review_assisted_v1',reviewed_branch_not_machine_model_improvement=True)
 require(all(sha(paths[k])==h for k,h in before.items()),'Input mutated during execution')
 return {'result':wrap_native(result,request=request,branch=branch,implementation_hash=implementation_hash()),
   'native':result,'adapter_audit':audit}
