"""Headless, independent engine jobs with strict PPAC admission and immutable receipts."""
from pathlib import Path
from copy import deepcopy
import fcntl
import os
from ..artifacts import read,sha,semantic_hash
from ..persistence import publish,verify_manifest
from .contracts import need,decode,load,GateError
from .adapters import execute,inspect
from .gate import features


def code_hash():
    root=Path(__file__).resolve().parents[1]
    paths=[p for name in ('integration','ppac') for p in sorted((root/name).glob('*.py'))]
    paths.extend(root/n for n in ('artifacts.py','persistence.py'))
    return semantic_hash({str(p.relative_to(root)):sha(p) for p in paths})

def reopen(output):
    root=Path(output)/'receipt';verify_manifest(root)
    r=read(root/'result.json')
    need(r.get('schema_version')=='gate2_result_v1','SCHEMA_UNSUPPORTED','Bukan receipt Gate 2')
    return r

def run(request,output,*,root='.',operation='run'):
    q=deepcopy(decode(request));root=Path(root).resolve();output=Path(output).resolve()
    need(operation in ('run','area','traffic','ppac'),'OPERATION_INVALID','Operasi tidak dikenal')
    jobs=[j for j in q['jobs'] if operation in ('run','ppac') or j['engine']==operation]
    need(bool(jobs),'JOBS_MISSING','Tidak ada job untuk operasi ini')
    need(operation!='ppac' or all(j['action']=='reuse' for j in jobs),'FINALIZED_INPUT_REQUIRED','ppac hanya menerima reuse; gunakan run untuk menjalankan engine')
    versions={}
    for engine in {j['engine'] for j in jobs if j['action']=='run'}:
        if engine=='area':
            from ..location.area.application.pipeline import implementation_hash
        else:
            from ..traffic.application.pipeline import implementation_hash
        versions[engine]=implementation_hash()
    identity={'request':q,'root':str(root),'operation':operation,'code':code_hash(),'engine_code':versions}
    output.mkdir(parents=True,exist_ok=True)
    fd=os.open(output/'.workflow.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise GateError('WORKFLOW_RUNNING','Output ini sedang dikerjakan') from None
        if (output/'receipt').exists():
            saved=reopen(output)
            need(read(output/'receipt/identity.json')==identity,'REVISION_CONFLICT','Request/kode berubah; gunakan revision output baru')
            for item in saved['jobs']:
                if item['execution_status']=='SUCCEEDED':inspect(item['engine'],item['result_ref'],root)
            if operation in ('run','ppac') and q['ppac'] is not None:
                for ref in q['ppac'].values():
                    if ref is not None:load(ref,root)
            for j in jobs:
                if j['action']=='run':load(j['request_ref'],root)
            return saved
        outcomes=[];handoffs={}
        for j in jobs:
            try:
                h=execute(j,root,output/'engines'/j['id']);h['action']=j['action'];handoffs[j['id']]=h
                outcomes.append({'id':j['id'],**{k:v for k,v in h.items() if k not in ('result','native')}})
            except Exception as exc:
                outcomes.append({'id':j['id'],'engine':j['engine'],'execution_status':'FAILED',
                                 'diagnostics':[diagnostic(exc,'ENGINE_FAILED')]})
        ppac={'execution_status':'NOT_RUN','std_total':None,'diagnostics':[]}
        if operation in ('run','ppac') and (q['ppac'] is not None or operation=='ppac'):
            ppac={'execution_status':'BLOCKED','std_total':None,'diagnostics':[]}
            try:
                need(len(handoffs)==len(jobs) and {'area','traffic'}<={h['engine'] for h in handoffs.values()},
                     'REQUIRED_ENGINE_UNAVAILABLE','Hasil Area dan Traffic yang berhasil wajib tersedia')
                need(q['ppac'] is not None and all(v is not None for v in q['ppac'].values()),
                     'PPAC_CONFIGURATION_MISSING','Binding dan parameter PPAC belum tersedia')
                binding=load(q['ppac']['binding_ref'],root);params=load(q['ppac']['parameters_ref'],root)
                f=features(binding,handoffs,params)
            except Exception as exc:
                ppac['diagnostics']=[diagnostic(exc,'INPUT_INVALID')]
            else:
                try:
                    from ..ppac import calculate
                    ppac=calculate(f,params);ppac.update(features=f,parameters=params,diagnostics=[])
                except Exception as exc:
                    ppac={'execution_status':'FAILED','std_total':None,'diagnostics':[diagnostic(exc,'PPAC_FAILED')]}
        status='FAILED' if any(o['execution_status']=='FAILED' for o in outcomes) or ppac['execution_status']=='FAILED' else 'BLOCKED' if ppac['execution_status']=='BLOCKED' else 'SUCCEEDED'
        result={'schema_version':'gate2_result_v1','execution_status':status,'jobs':outcomes,'ppac':ppac,
                'storage':'LOCAL','production_ready':False,'implementation_sha256':identity['code']}
        result['result_version']=semantic_hash({'identity':identity,'result':result})
        publish(output/'receipt',{'result.json':result,'identity.json':identity},metadata={'engine':'gate2','result_version':result['result_version']})
        return result
    finally:os.close(fd)

def diagnostic(exc,default):
    return {'code':exc.code if isinstance(exc,GateError) else default,'message':str(exc)}
