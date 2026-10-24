"""Per-video process isolation and immutable publication; failures retain logs."""
from pathlib import Path
import shutil
import tempfile
from ...artifacts import read, require, semantic_hash, write, artifact
from ..adapters.detector import execute_worker
from ..adapters.tracker_reid import require_reid
from ..artifact_store import ArtifactStore
from .pipeline import run, implementation_hash


def fresh_inference(request_path, output, *, python_executable, timeout_seconds=3600):
    require(type(timeout_seconds) in (int, float) and timeout_seconds > 0, 'Positive worker timeout required')
    request = read(request_path)
    require_reid(request)
    output = Path(output).resolve()
    require(not output.exists(), 'Immutable inference output required')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.inference-', dir=output.parent))
    try:
        code = execute_worker(request_path, stage / 'worker', python_executable=python_executable,
                              log_path=stage / 'worker.log', timeout_seconds=timeout_seconds)
        require(code == 0, 'Inference worker failed; inspect retained failure log')
        value = read(stage / 'worker/result.json.gz')
        require(value['status'] == 'SUCCEEDED' and value['request_fingerprint'] == semantic_hash(request), 'Worker request/result mismatch')
        require(value['records_semantic_sha256'] == semantic_hash(value['records']), 'Worker records integrity mismatch')
        shutil.move(stage / 'worker/result.json.gz', stage / 'result.json.gz')
        (stage / 'worker').rmdir()
        require(not output.exists(), 'Output appeared during inference')
        stage.rename(output)
        return value
    except BaseException as exc:
        write(stage / 'failure.json', {'status': 'FAILED', 'error_type': type(exc).__name__, 'error': str(exc),
                                      'request_sha256': semantic_hash(request), 'published_success': False})
        # Keep the unique failed stage for inspection; never publish it as success.
        raise


def execute_and_publish(request, *, root, store: ArtifactStore, key):
    code_hash = implementation_hash()
    if store.exists(key):
        result = store.reopen(key)
        metadata = store.read_document(key, 'manifest.json')['metadata']
        require(metadata.get('counting_implementation_sha256') == code_hash, 'Code changed; use a new revision')
        require(store.read_document(key, 'request.json') == request, 'Request changed; use a new revision')
        for ref in request['artifacts'].values():
            artifact(ref, root)
        return result
    value = run(request, root=root)
    store.publish_result(key, {'result.json': value['result'], 'native.json.gz': value['native'],
        'adapter_audit.json': value['adapter_audit'], 'request.json': request},
        metadata={'engine': 'traffic', 'operation': 'count_replay', 'result_version': value['result']['result_version'],
                  'counting_implementation_sha256': code_hash})
    return store.reopen(key)
