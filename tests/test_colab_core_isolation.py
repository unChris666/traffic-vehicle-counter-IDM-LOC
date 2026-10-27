"""Reproduce installed-wheel PYTHONPATH leakage without GIS/GPU in CI."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('core_bootstrap',ROOT/'tools/colab_bootstrap.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)

class CoreIsolationTests(unittest.TestCase):
    def test_core_imports_application_without_scientific_dependency_leakage(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);site=base/'scientific-site';app=site/'traffic_location'
            app.mkdir(parents=True);(app/'__init__.py').write_text('fixture=True\n')
            (site/'scientific_dependency_sentinel.py').write_text('leaked=True\n')
            executable=base/'runtime/core/bin/python';executable.parent.mkdir(parents=True)
            executable.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' "$@"\n');executable.chmod(0o755)
            with patch('subprocess.check_output',return_value=str(site)+'\n'):
                wrapper=bootstrap.write_core_wrapper(base,'/science/python')
                self.assertEqual(bootstrap.write_core_wrapper(base,'/science/python'),wrapper)
            env={**os.environ,'PYTHONPATH':str(site),'PROJ_LIB':'wrong','PROJ_DATA':'wrong','GDAL_DATA':'wrong'}
            probe='import importlib.util;assert importlib.util.find_spec("scientific_dependency_sentinel") is not None'
            subprocess.run([sys.executable,'-c',probe],env=env,check=True)
            probe='''import importlib.util,os,traffic_location
assert traffic_location.fixture
assert importlib.util.find_spec('scientific_dependency_sentinel') is None
assert 'PROJ_LIB' not in os.environ
assert os.environ['PROJ_DATA'].endswith('/runtime/core/share/proj')
assert os.environ['GDAL_DATA'].endswith('/runtime/core/share/gdal')
assert os.environ['PYTHONNOUSERSITE']=='1'
'''
            subprocess.run([str(wrapper),'-c',probe],env=env,check=True)
            self.assertEqual(env['PYTHONPATH'],str(site))

    def test_recovery_embeds_same_wrapper_and_rejects_active_server_before_changes(self):
        source=(ROOT/'tools/colab_bootstrap.py').read_text()
        function=ast.get_source_segment(source,next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='write_core_wrapper'))
        recovery=(ROOT/'notebooks/active/colab_core_recovery.py').read_text()
        self.assertIn(function,recovery)
        from unittest.mock import Mock
        server=Mock();server.poll.return_value=None
        namespace=dict(BASE=Path('/unused'),SCIENCE='/science',CORE='/core',child_env=lambda:{},run_logged=Mock(),command=Mock(),SERVER=server)
        with self.assertRaisesRegex(RuntimeError,'Hentikan cell SERVER'):
            exec(compile(recovery,'core-recovery','exec'),namespace)
        namespace['run_logged'].assert_not_called()

    def test_notebook_checks_actual_core_with_worker_path_and_exports_diagnostic(self):
        notebook=json.loads((ROOT/'notebooks/active/15_colab_l4_area_first.ipynb').read_text())
        cells='\n'.join(c['source'] for c in notebook['cells'])
        fragment=(ROOT/'tools/colab_core_check.py').read_text()
        self.assertIn(fragment,cells)
        self.assertIn('core-runtime-isolation.json',cells)
        self.assertIn('core-isolation.log',cells)
        self.assertIn("'PYTHONPATH':sysconfig.get_path('purelib')",fragment)
        self.assertIn('assert clean==worker',fragment)

if __name__=='__main__':unittest.main()
