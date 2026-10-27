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
