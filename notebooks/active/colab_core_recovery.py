# Sesi Colab r4: hentikan cell SERVER setelah job gagal selesai dahulu.
# Salin seluruh kode ini ke CELL BARU. Tidak menginstal paket atau mengubah snapshot.
import json,os,shlex,subprocess
from pathlib import Path
if not all(k in globals() for k in ('BASE','SCIENCE','CORE','child_env','run_logged','command')):
    raise RuntimeError('Cell ini memerlukan sesi notebook yang sudah selesai setup.')
if 'SERVER' in globals() and SERVER.poll() is None:
    raise RuntimeError('Hentikan cell SERVER dahulu agar tidak mengubah runtime saat job aktif.')
def write_core_wrapper(base,science_python):
    """Expose application code to core without exposing scientific dependencies."""
    base=Path(base).resolve()
    site=Path(subprocess.check_output([str(science_python),'-I','-c',
        'import sysconfig;print(sysconfig.get_path("purelib"))'],text=True,timeout=30).strip())
    application=site/'traffic_location'
    if not application.is_dir():raise RuntimeError('Wheel aplikasi belum terpasang; jalankan setup dahulu.')
    bridge=base/'runtime/core-application';bridge.mkdir(parents=True,exist_ok=True)
    link=bridge/'traffic_location'
    if link.is_symlink():
        if link.resolve()!=application.resolve():raise RuntimeError('Core application bridge berbeda; gunakan workspace terpisah.')
    elif link.exists():raise RuntimeError('Core application bridge bukan symlink aplikasi.')
    else:link.symlink_to(application,target_is_directory=True)
    core=base/'runtime/core-python'
    core.write_text('#!/bin/sh\nunset PROJ_LIB\nunset PYTHONHOME\nexport PYTHONNOUSERSITE=1\nexport PYTHONPATH='+shlex.quote(str(bridge))+'\nexport PROJ_DATA='+shlex.quote(str(base/'runtime/core/share/proj'))+'\nexport GDAL_DATA='+shlex.quote(str(base/'runtime/core/share/gdal'))+'\nexec '+shlex.quote(str(base/'runtime/core/bin/python'))+' "$@"\n')
    core.chmod(0o755)
    return core
write_core_wrapper(BASE,SCIENCE)
# Notebook fragment: run after verify, before authentication or engine execution.
core_isolation_probe = r'''
import json,os,subprocess,sys,sysconfig
from pathlib import Path
base=Path(sys.argv[1]);core=sys.argv[2]
probe="""import json,platform,pyproj
from osgeo import gdal
import traffic_location.location.area._kernel.location_intelligent_li3_core
print(json.dumps({'python':platform.python_version(),'gdal':gdal.VersionInfo('RELEASE_NAME'),'pyproj':pyproj.__version__,'pyproj_file':pyproj.__file__,'gdal_file':gdal.__file__}))"""
# Exact PYTHONPATH shape set by the installed Area pipeline.
worker_env={**os.environ,'PYTHONPATH':sysconfig.get_path('purelib')+os.pathsep+os.environ.get('PYTHONPATH','')}
clean=json.loads(subprocess.check_output([core,'-c',probe],text=True,timeout=60))
worker=json.loads(subprocess.check_output([core,'-c',probe],env=worker_env,text=True,timeout=60))
assert clean==worker,('AREA_CORE_ISOLATION_FAILED',clean,worker)
core_root=(base/'runtime/core').resolve()
assert all(Path(worker[k]).resolve().is_relative_to(core_root) for k in ('pyproj_file','gdal_file')),worker
report={'status':'PASS','core':worker,'scope':'Core import and worker PYTHONPATH isolation; not Area execution.'}
(base/'core-runtime-isolation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
'''
run_logged([SCIENCE,'-u','-c',core_isolation_probe,str(BASE),CORE],'core-isolation',env=child_env())

run_logged(command('verify'),'runtime-check',env=child_env())
print('Core terisolasi dan runtime check lulus. Jalankan kembali cell server, lalu Process Area untuk membuat job baru. Jangan ulang setup lama.')
