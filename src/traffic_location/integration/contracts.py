"""Small strict JSON interface and stable error codes for Gate 2."""
from pathlib import Path
from ..artifacts import artifact, read

class GateError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

def need(condition, code, message):
    if not condition:
        raise GateError(code, message)

def fields(value, required, optional=()):
    need(isinstance(value, dict) and set(required) <= set(value) and
         set(value) <= set(required) | set(optional), 'SCHEMA_INVALID', 'Field wajib hilang atau field tidak dikenal: '+str(required))

def load(ref, root):
    fields(ref, {'path','sha256'})
    return read(artifact(ref, root))

def resolve(path, root):
    return (Path(root) / path).resolve()

def decode(q):
    fields(q, {'schema_version','jobs','ppac'})
    need(q['schema_version']=='gate2_workflow_v1', 'SCHEMA_UNSUPPORTED', 'Gunakan gate2_workflow_v1')
    need(isinstance(q['jobs'],list) and bool(q['jobs']), 'JOBS_MISSING','jobs wajib list non-kosong')
    ids=set()
    for job in q['jobs']:
        fields(job, {'id','engine','action'}, {'request_ref','root','result_ref'})
        import re
        need(isinstance(job['id'],str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', job['id']) is not None
             and job['id'] not in ids, 'JOB_ID_INVALID','ID job wajib unik dan aman')
        ids.add(job['id'])
        need(job['engine'] in ('area','traffic'), 'ENGINE_UNSUPPORTED','engine harus area/traffic')
        need(job['action'] in ('run','reuse'), 'ACTION_UNSUPPORTED','action harus run/reuse')
        fields(job, {'id','engine','action','request_ref','root'} if job['action']=='run'
               else {'id','engine','action','result_ref'})
    if q['ppac'] is not None:
        fields(q['ppac'], {'binding_ref','parameters_ref'})
    return q
