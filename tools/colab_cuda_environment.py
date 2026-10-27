"""Prepare the loader before exec: CUDA wheels are outside the system ld cache.

Standard library only; embedded in the notebook and existing-session recovery.
Does not install packages, load CUDA into the host kernel, or alter os.environ.
"""
def cuda_child_environment(science_python, environment):
    import json
    import subprocess
    from pathlib import Path
    env = dict(environment)
    # Ask the application interpreter, never the notebook's Python/version.
    paths = json.loads(subprocess.check_output(
        [str(science_python), '-I', '-c',
         'import json,sysconfig;print(json.dumps(sysconfig.get_paths()))'],
        env=env, text=True, timeout=30))
    site = Path(paths['purelib'])
    required = (site/'nvidia/cuda_nvrtc/lib/libnvrtc.so.12',
                site/'nvidia/cuda_runtime/lib/libcudart.so.12')
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise RuntimeError('CUDA wheel library belum terpasang: '+', '.join(missing)+
                           '. Jalankan ulang cell setup terkunci; jangan upgrade paket kernel Colab.')
    libraries = sorted(p for p in (site/'nvidia').glob('*/lib') if p.is_dir())
    if (site/'torch/lib').is_dir():
        libraries.append(site/'torch/lib')
    # Set this BEFORE Popen: changing LD_LIBRARY_PATH inside a running Python
    # process does not reliably change glibc's dlopen search path.
    inherited = [p for p in env.get('LD_LIBRARY_PATH', '').split(':') if p]
    env['LD_LIBRARY_PATH'] = ':'.join(dict.fromkeys([str(p) for p in libraries]+inherited))
    return env
