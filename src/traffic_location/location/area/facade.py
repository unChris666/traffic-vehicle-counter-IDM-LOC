"""Artifact freeze/reopen facade; never computes or changes native decisions."""
from pathlib import Path
from shutil import copyfile
import tempfile
from .input_contracts import AreaArtifactRequest
from .artifact_refs import checked
from .sources.snapshots import MarketSnapshot
from ...artifacts import read,write,sha,semantic_hash

def freeze(request,output):
    q=AreaArtifactRequest.parse(request)
    if q.operation!='freeze':raise ValueError('AREA_EXPECTED_FREEZE')
    source=checked(q.path,q.sha256);snapshot=MarketSnapshot(source)
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        value=reopen({'schema_version':q.schema_version,'operation':'reopen',
                      'path':str(output/'baseline.zip'),'sha256':q.sha256})
        if read(output/'freeze_receipt.json')['source_zip_sha256']!=q.sha256:
            raise ValueError('AREA_FREEZE_CONFLICT')
        return value
    with tempfile.TemporaryDirectory(prefix='.area-freeze-',dir=output.parent) as d:
        stage=Path(d)/'packet';stage.mkdir();copyfile(source,stage/'baseline.zip')
        if sha(stage/'baseline.zip')!=q.sha256:raise ValueError('AREA_FREEZE_COPY_CHANGED')
        receipt={'schema_version':'area_baseline_freeze_v1','status':'VERIFIED',
            'source_zip_sha256':q.sha256,'native_result_fingerprint':snapshot.native['fingerprint'],
            'file_count':snapshot.file_count,'code_hashes':snapshot.code_hashes,
            'source_rows':len(snapshot.native['rows']),'summary':snapshot.native['summary']}
        write(stage/'freeze_receipt.json',receipt);stage.rename(output)
    return reopen({'schema_version':q.schema_version,'operation':'reopen','path':str(output/'baseline.zip'),'sha256':q.sha256})

def reopen(request):
    q=AreaArtifactRequest.parse(request)
    if q.operation!='reopen':raise ValueError('AREA_EXPECTED_REOPEN')
    snapshot=MarketSnapshot(checked(q.path,q.sha256));native=snapshot.native
    equivalence=snapshot.equivalence
    states=[equivalence.get(k,{}).get('status') for k in ['calculation','market']]
    status='FAIL' if 'FAIL' in states else 'PASS' if states==['PASS','PASS'] else 'NOT_VERIFIED'
    adapter=semantic_hash({str(p.relative_to(Path(__file__).parent)):sha(p) for p in sorted(Path(__file__).parent.rglob('*.py'))})
    return {'schema_version':'area_artifact_result_v1','execution_status':'SUCCEEDED',
        'operation':'REOPEN_RETAINED_RESULT_NO_COMPUTE','data_quality_status':native['status'],
        'result_version':semantic_hash({'schema':'area_artifact_result_v1','zip':q.sha256,'native':native['fingerprint'],'adapter':adapter}),
        'claim_type':'EXPERIMENTAL_SCENARIO','adapter_sha256':adapter,'source_zip_sha256':q.sha256,
        'native_result_fingerprint':native['fingerprint'],'equivalence_status':status,
        'reproducibility_status':'NOT_VERIFIED','publication_status':'LOCAL_VERIFIED_ARTIFACT',
        'rows':native['rows'],'summary':native['summary'],'capacity':snapshot.capacity}


def execute(request,output):
    """Execute a typed frozen-input job; worker/backend selection stays explicit."""
    from .application.pipeline import execute as run
    return run(request,output)


def reopen_result(root):
    """Read a finalized modular result without source downloads or computation."""
    from .validation import reopen_execution
    return reopen_execution(root)
