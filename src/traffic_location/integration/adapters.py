"""Read-only adapters; source ledgers remain unchanged, counting stays upstream."""
from pathlib import Path
from ..artifacts import read, sha, semantic_hash
from ..persistence import verify_manifest, reopen_traffic
from .contracts import need, fields, load, resolve

def ref(path):
    return {'path':str(Path(path).resolve()), 'sha256':sha(Path(path)/'manifest.json')}

def inspect(engine, pointer, root):
    fields(pointer, {'path','sha256'})
    folder=resolve(pointer['path'],root)
    need(sha(folder/'manifest.json')==pointer['sha256'],'MANIFEST_CHANGED','Manifest SHA berbeda')
    m=verify_manifest(folder);r=read(folder/'result.json');n=read(folder/'native.json.gz')
    expected='area_execution_result_v1' if engine=='area' else 'traffic_result_v2'
    need(r.get('schema_version')==expected,'RESULT_SCHEMA_UNSUPPORTED','Handoff memerlukan '+expected)
    need(m['metadata'].get('engine')==engine and r.get('execution_status')=='SUCCEEDED',
         'ENGINE_NOT_SUCCEEDED','Hanya paket hasil engine yang berhasil dan finalized dapat dipakai')
    need(m['metadata'].get('result_version')==r['result_version'],'VERSION_MISMATCH','Versi manifest/result berbeda')
    if engine=='traffic':
        reopen_traffic(folder)
        request=read(folder/'request.json')
        need(r.get('counting_executed') is True and r['operation_executed']=='count_replay',
             'COUNTING_MISSING','Output inference saja belum merupakan hasil counting')
        need(r['source_identity']==n['source_identity']==request['source_identity'] and
             r['branch']==request['profile'] and r['scope']['source_frames']==request['frame_count'] and
             r['scope']['processed_frames']==n['report']['frame_count'], 'SOURCE_MISMATCH','Scope/source/branch berbeda')
        keys={'accepted_total':'total','accepted_measured':'measured_total','accepted_estimated':'inferred_total',
              'pending':'pending','invalid':'invalid'}
        need(all(r['summary'][k]==n['aggregate'][v] for k,v in keys.items()),'SUMMARY_MISMATCH','Summary berbeda dari ledger')
    else:
        need(semantic_hash({k:v for k,v in n.items() if k not in {'identity','fingerprint','output_path'}})
             ==r['native_domain_sha256'],'NATIVE_CHANGED','Domain Area berbeda dari envelope')
        from ..location.area.domain.aggregation import reconcile
        need(reconcile(n['rows'])==n['summary']==r['summary'],'SUMMARY_MISMATCH','Summary Area tidak cocok')
        need(semantic_hash(n['identity'])==n['fingerprint'],'SOURCE_MISMATCH','Identitas Area berbeda')
        need(n['status']==r['data_quality_status'],'QUALITY_MISMATCH','Status kualitas Area berbeda')
    return {'schema_version':'engine_handoff_v1','engine':engine,'execution_status':'SUCCEEDED',
            'result_version':r['result_version'],'result_ref':pointer,'quality':r.get('result_quality',r.get('data_quality_status')),
            'summary':r['summary'],'result':r,'native':n}

def execute(job, root, output):
    if job['action']=='reuse':
        return inspect(job['engine'],job['result_ref'],root)
    q=load(job['request_ref'],root);input_root=resolve(job['root'],root)
    if job['engine']=='area':
        from ..location.area.facade import execute as run
        key='input' if q['schema_version']=='area_execution_request_v2' else 'baseline'
        q[key]['path']=str(resolve(q[key]['path'],input_root))
        run(q,output)
    else:
        from ..traffic.application.runtime import execute_and_publish
        from ..traffic.artifact_store import LocalArtifactStore
        execute_and_publish(q,root=input_root,store=LocalArtifactStore(Path(output).parent),key=Path(output).name)
    return inspect(job['engine'],ref(output),root)
