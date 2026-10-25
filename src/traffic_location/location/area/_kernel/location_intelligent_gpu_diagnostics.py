"""GPU-only diagnostics. Never serialize generic BQ/auth exception messages."""
from pathlib import Path
import io, json, hashlib

def diagnostic(error, stage):
    compiler = getattr(error, 'gpu_compiler_diagnostic', None)
    if compiler is not None:
        return {'status': 'FAILED', 'stage': stage, **compiler}
    name = type(error).__name__
    result = {'status': 'FAILED', 'stage': stage, 'error_type': name}
    if name == 'CompileException':
        result.update(error_code='GPU_KERNEL_COMPILE_FAILED', compiler_log=str(error))
    elif isinstance(error, RuntimeError) and str(error).startswith('GPU_'):
        result['error_code'] = str(error).split(':', 1)[0]
    else:
        result['error_code'] = 'GPU_PREFLIGHT_FAILED'
    result['action'] = 'Inspect gpu_preflight.json / kernel_compilation.json; do not bypass failed dependencies'
    return result

def compile_cuda_kernels(report_dir, device=0):
    """Eager compilation of every kernel before any source acquisition."""
    import cupy as cp
    from traffic_location.location.area._kernel.location_intelligent_gpu import CupyReachability
    from traffic_location.location.area._kernel.location_intelligent_gpu_geometry import GpuGeometry
    from traffic_location.location.area._kernel.location_intelligent_gpu_weighted import CupyWeightedRouter
    definitions = [('propagate', CupyReachability.KERNEL), ('distances', GpuGeometry.DISTANCE), ('polygon_lengths', GpuGeometry.CLIP), ('primitive_hits', GpuGeometry.PRIMITIVES), ('relax', CupyWeightedRouter.KERNEL)]
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / 'kernel_compilation.json'
    rows = []
    report = {'scope': 'CUDA_COMPILATION_ONLY', 'actual_cuda_executed': False, 'status': 'RUNNING', 'kernels': rows}
    path.write_text(json.dumps(report, indent=2))
    with cp.cuda.Device(device):
        for name, source in definitions:
            stream = io.StringIO()
            row = {'kernel': name, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'status': 'RUNNING'}
            rows.append(row)
            print('GPU kernel compile: ' + name, flush=True)
            try:
                kernel = cp.RawKernel(source, name, options=('--std=c++11', '--fmad=false'))
                kernel.compile(log_stream=stream)
                row.update(status='PASS', compiler_log=stream.getvalue())
            except Exception as error:
                log = stream.getvalue() + '\n' + str(error)
                log_path = report_dir / (name + '_compile.log')
                log_path.write_text(log)
                row.update(status='FAIL', error_type=type(error).__name__, compiler_log=log, log_path=str(log_path))
                report['status'] = 'FAIL'
                path.write_text(json.dumps(report, indent=2))
                failure = RuntimeError('GPU_KERNEL_COMPILE_FAILED: ' + name)
                failure.gpu_compiler_diagnostic = {'error_type': type(error).__name__, 'error_code': 'GPU_KERNEL_COMPILE_FAILED', 'kernel': name, 'compiler_log': log, 'log_path': str(log_path), 'action': 'Load latest helper cells and Run All; inspect compiler line in ' + str(log_path)}
                raise failure from error
            finally:
                path.write_text(json.dumps(report, indent=2))
    report['status'] = 'PASS'
    path.write_text(json.dumps(report, indent=2))
    return report
