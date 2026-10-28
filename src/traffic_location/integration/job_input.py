"""Reviewed immutable request metadata; source snapshots/artifacts live in GCS."""
from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid4
from ..artifacts import semantic_hash,canonical,write
from .contracts import need

def review(values):
    return {'schema_version':'input_review_v1','fingerprint':semantic_hash(values),
            'values':deepcopy(values),'reviewed_at':datetime.now(timezone.utc).isoformat()}

def checked_review(values,token,confirmed):
    need(confirmed is True and isinstance(token,dict) and token.get('fingerprint')==semantic_hash(values),
         'INPUT_REVIEW_REQUIRED','Input berubah/belum dikonfirmasi. Pratinjau lokasi dan input lagi, lalu konfirmasi sebelum Process.')
    return deepcopy(values)

def freeze(root,mode,context,parameters,inventory,identity=None):
    identity=identity or {}
    job_id=identity.get('job_id') or 'job_'+uuid4().hex
    import re
    need(re.fullmatch(r'job_[a-f0-9]{32}',job_id) is not None,'JOB_ID_INVALID','Identitas job tidak valid.')
    import math
    need(all(isinstance(context.get(k),str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',context[k]) for k in ('target_id','period_id')),'JOB_CONTEXT_INVALID','Identitas target/periode tidak valid.')
    need(all(type(context.get(k)) in (int,float) and math.isfinite(context[k]) for k in ('latitude','longitude')) and -80<=context['latitude']<=84 and -180<=context['longitude']<=180,'JOB_CONTEXT_INVALID','Koordinat tidak valid.')
    from .. import __version__
    value={'schema_version':'job_input_v1','job_id':job_id,'created_at':datetime.now(timezone.utc).isoformat(),
           'package_version':__version__,'mode':mode,'context':deepcopy(context),'parameters':deepcopy(parameters),
           'review_sha256':identity.get('review_sha256'),'review_confirmed':bool(identity.get('review_sha256')),
           'requested_video_ids':deepcopy(identity.get('requested_video_ids',[])),
           'skipped_videos':deepcopy(identity.get('skipped_videos',[])),
           'target_video_binding_confirmed':bool(identity.get('target_confirmed')),
           'video_source':identity.get('video_source','NOT_REQUESTED'),
           'videos':[{k:deepcopy(v[k]) for k in ('id','filename','status','slot','geometry_ref','inspection_ref') if k in v} for v in inventory]}
    # Geometry refs identify immutable files; no credentials or notebook environment.
    value['input_sha256']=semantic_hash(value)
    path=root/'job-input.json';need(not path.exists(),'JOB_INPUT_IMMUTABLE','Input job sudah dibekukan.')
    write(path,value)
    return value

def upload(snapshot,destination,storage):
    name='jobs/'+snapshot['context']['target_id']+'/'+snapshot['context']['period_id']+'/'+snapshot['job_id']+'/inputs/job-input.json'
    blob=storage.bucket(destination.bucket).blob(name)
    from ..artifacts import semantic_hash
    blob.metadata={'sha256':semantic_hash(snapshot)}
    blob.upload_from_string(canonical(snapshot),content_type='application/json',if_generation_match=0,checksum='crc32c',timeout=60)
    return 'gs://'+destination.bucket+'/'+name
