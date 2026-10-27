"""Isolated worker execution and idempotent local publication; no live acquisition."""
from pathlib import Path
import os,shutil,subprocess,sys,tempfile,signal,time,fcntl
from ..artifact_refs import checked
from ..runtime.environment import fingerprint
from ..outputs.export import finalize
from .checkpoints import record
from ....artifacts import read,write,sha,semantic_hash
from ....persistence import verify_manifest


def implementation_hash():
    root=Path(__file__).resolve().parents[1]
    return semantic_hash({str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*.py'))})


def execute(request,output):
    source_request=request.get('schema_version')=='area_execution_request_v2'
    if source_request:
        if set(request)!={'schema_version','operation','input','core_python','render','timeout_seconds'} or request['operation']!='compute_gpu_sources':
            raise ValueError('AREA_EXECUTION_V2_SCHEMA_INVALID')
        request={'schema_version':'area_execution_request_v1','operation':'compute_gpu_sources',
                 'baseline':request['input'],'core_python':request['core_python'],
                 'render':request['render'],'timeout_seconds':request['timeout_seconds']}
    fields={'schema_version','operation','baseline','core_python','render','timeout_seconds'}
    if set(request)!=fields or request['schema_version']!='area_execution_request_v1':raise ValueError('AREA_EXECUTION_SCHEMA_INVALID')
    if not isinstance(request['operation'],str) or request['operation'] not in {'replay_recorded','compute_gpu_frozen','compute_gpu_sources'}:raise ValueError('AREA_EXECUTION_PROFILE_INVALID')
    if request['operation']=='compute_gpu_sources' and not source_request:raise ValueError('AREA_SOURCE_COMPUTE_REQUIRES_V2')
    if type(request['render']) is not bool or type(request['timeout_seconds']) not in {int,float} or not 0<request['timeout_seconds']<=86400:raise ValueError('AREA_EXECUTION_OPTIONS_INVALID')
    if not isinstance(request['core_python'],str) or not Path(request['core_python']).is_file():raise ValueError('AREA_CORE_PYTHON_MISSING')
    if not isinstance(request['baseline'],dict) or set(request['baseline'])!={'path','sha256'}:raise ValueError('AREA_BASELINE_REF_INVALID')
    from ..input_contracts import AreaArtifactRequest
    AreaArtifactRequest.parse({'schema_version':'area_artifact_request_v1','operation':'reopen',**request['baseline']})
    checked(request['baseline']['path'],request['baseline']['sha256'])
    version=semantic_hash({'operation':request['operation'],'baseline':request['baseline']['sha256'],
                           'render':request['render'],'code':implementation_hash(),'environment':fingerprint(),
                           'core_python':request['core_python']})
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        manifest=verify_manifest(output)
        if manifest['metadata'].get('result_version')!=version:raise ValueError('AREA_JOB_REVISION_CONFLICT')
        return read(output/'result.json')
    lock=output.with_name('.'+output.name+'.lock')
    # Keep the inode stable. The OS releases flock after exit/SIGKILL; a
    # leftover filename therefore cannot prevent a retry after a crash. The
    # worker inherits this descriptor so a live orphan still owns the lock.
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException as error:
        os.close(fd)
        if isinstance(error,BlockingIOError):
            raise RuntimeError('AREA_JOB_ALREADY_RUNNING: inspect '+str(lock)) from None
        raise
    stage=None
    try:
        if output.exists():
            manifest=verify_manifest(output)
            if manifest['metadata'].get('result_version')!=version:raise ValueError('AREA_JOB_REVISION_CONFLICT')
            return read(output/'result.json')
        stage=Path(tempfile.mkdtemp(prefix='.area-job-',dir=output.parent))
        write(stage/'request.json',request);record(stage,'worker','RUNNING')
        source_root=Path(__file__).resolve().parents[4]
        env={**os.environ,'PROJ_NETWORK':'OFF','PYTHONPATH':str(source_root)+os.pathsep+os.environ.get('PYTHONPATH','')}
        with (stage/'worker.log').open('w') as log:
            process=subprocess.Popen([sys.executable,'-m','traffic_location.location.area.application.worker',
                str(stage/'request.json'),str(stage)],stdout=log,stderr=subprocess.STDOUT,env=env,
                start_new_session=True,pass_fds=(fd,))
            deadline=time.monotonic()+request['timeout_seconds']
            try:
                while True:
                    try:
                        process.wait(timeout=max(.01,min(30,deadline-time.monotonic())));break
                    except subprocess.TimeoutExpired:
                        if time.monotonic()>=deadline:raise
                        checkpoint=read(stage/'checkpoint.json')
                        print('Area worker active:',checkpoint['stage'],checkpoint['status'],flush=True)
            except BaseException:
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait()
                raise
        if process.returncode:raise RuntimeError('AREA_WORKER_FAILED: inspect '+str(stage/'worker.log'))
        result=read(stage/'result.json');result['result_version']=version;write(stage/'result.json',result)
        # Inputs already exist in the verified baseline ZIP; avoid duplicating national/local sources per result.
        shutil.rmtree(stage/'work')
        finalize(stage,output,{'engine':'area','result_version':version,'operation':request['operation']})
        return result
    except BaseException as error:
        if stage is not None:record(stage,'worker','FAILED',error_type=type(error).__name__,published_success=False)
        raise
    finally:
        # Never unlink a lock: another process may already hold this inode.
        os.close(fd)
