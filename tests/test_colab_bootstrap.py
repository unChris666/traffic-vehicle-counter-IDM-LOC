"""Short local subprocess tests for visible setup failures; no package installation."""
import ast,contextlib,hashlib,importlib.util,io,json,os,signal,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('colab_bootstrap_under_test',ROOT/'tools/colab_bootstrap.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)

class BootstrapTests(unittest.TestCase):
    def test_bootstrap_child_uses_agg_without_changing_notebook_backend(self):
        inherited='module://matplotlib_inline.backend_inline'
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'MPLBACKEND':inherited}):
            progress=bootstrap.Progress(d)
            progress.run('scientific_imports',[sys.executable,'-c','import os;assert os.environ["MPLBACKEND"]=="Agg"'])
            self.assertEqual(os.environ['MPLBACKEND'],inherited)
    def test_explicit_subprocess_environment_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as d:
            original={'MPLBACKEND':'module://matplotlib_inline.backend_inline','TEST_SENTINEL':'keep'}
            progress=bootstrap.Progress(d)
            progress.run('probe',[sys.executable,'-c','import os;assert os.environ["MPLBACKEND"]=="Agg";assert os.environ["TEST_SENTINEL"]=="keep"'],env=original)
            self.assertEqual(original['MPLBACKEND'],'module://matplotlib_inline.backend_inline')
    def test_notebook_runner_and_server_env_use_agg_without_mutating_host(self):
        inherited='module://matplotlib_inline.backend_inline'
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'MPLBACKEND':inherited}),contextlib.redirect_stdout(io.StringIO()):
            self.runner(Path(d))([sys.executable,'-c','import os;assert os.environ["MPLBACKEND"]=="Agg"'],'setup')
            notebook=json.loads((ROOT/'notebooks/active/15_colab_l4_area_first.ipynb').read_text())
            code=next(c['source'] for c in notebook['cells'] if c['cell_type']=='code' and 'def child_env(' in c['source'])
            fn=next(x for x in ast.parse(code).body if isinstance(x,ast.FunctionDef) and x.name=='child_env')
            env={'os':os,'CORE':'fixture-core','BASE':Path(d),'SCIENCE':sys.executable,
                 'cuda_child_environment':lambda science,env:env}
            exec(compile(ast.Module(body=[fn],type_ignores=[]),'child-env','exec'),env)
            self.assertEqual(env['child_env']()['MPLBACKEND'],'Agg')
            self.assertEqual(os.environ['MPLBACKEND'],inherited)

    def test_retry_installs_into_existing_conda_prefix_without_reset(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);prefix=root/'runtime/science';(prefix/'conda-meta').mkdir(parents=True);(prefix/'conda-meta/history').touch()
            retained=prefix/'retained-data';retained.write_text('keep')
            progress=bootstrap.Progress(root)
            with patch.object(bootstrap.subprocess,'run') as run:
                bootstrap.ensure_environment('micromamba',prefix,'lock',{},progress,'science')
            self.assertEqual(run.call_args.args[0][2],'install');self.assertEqual(retained.read_text(),'keep')
    def test_new_prefix_uses_create_and_foreign_prefix_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);progress=bootstrap.Progress(root)
            with patch.object(bootstrap.subprocess,'run') as run:
                bootstrap.ensure_environment('micromamba',root/'new','lock',{},progress,'core')
                self.assertEqual(run.call_args.args[0][2],'create')
                foreign=root/'foreign';foreign.mkdir();(foreign/'owner.txt').write_text('keep')
                with self.assertRaisesRegex(RuntimeError,'non-conda'):bootstrap.ensure_environment('micromamba',foreign,'lock',{},progress,'core')
                self.assertTrue((foreign/'owner.txt').exists())
    def test_explicit_wheel_does_not_select_old_wheel(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'package').mkdir()
            for n in ('old.whl','current.whl'):(root/'package'/n).touch()
            self.assertEqual(bootstrap.select_wheel(root,'current.whl').name,'current.whl')
            with self.assertRaises(ValueError):bootstrap.select_wheel(root)
            with self.assertRaises(ValueError):bootstrap.select_wheel(root,'../current.whl')
    def test_cli_persists_failure_stage_and_python_version(self):
        with tempfile.TemporaryDirectory() as d:
            run=subprocess.run([sys.executable,str(ROOT/'tools/colab_bootstrap.py'),d],capture_output=True,text=True)
            self.assertEqual(run.returncode,1)
            status=json.loads((Path(d)/'setup-status.json').read_text())
            self.assertEqual(status['stage'],'input_validation');self.assertEqual(status['status'],'FAILED')
            self.assertIn('host_python',status);self.assertIn('BOOTSTRAP_FAILED',run.stderr)
    def runner(self,base):
        n=json.loads((ROOT/'notebooks/active/15_colab_l4_area_first.ipynb').read_text())
        cell=next(c['source'] for c in n['cells'] if c['cell_type']=='code' and 'def run_logged(' in c['source'])
        fn=next(node for node in ast.parse(cell).body if isinstance(node,ast.FunctionDef) and node.name=='run_logged')
        env={'BASE':base,'subprocess':subprocess,'json':json,'os':os,'signal':signal}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'notebook-log-runner','exec'),env)
        return env['run_logged']
    def test_notebook_shows_actual_stderr_and_stage_instead_of_only_process_error(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'setup-status.json').write_text(json.dumps({'stage':'pip_locked_dependencies','status':'FAILED'}))
            run=self.runner(root);output=io.StringIO()
            with contextlib.redirect_stdout(output),self.assertRaisesRegex(RuntimeError,'pip_locked_dependencies') as caught:
                run([sys.executable,'-c','import sys;print("ERROR: fixture dependency unavailable",file=sys.stderr);sys.exit(7)'],'setup')
            self.assertIn('fixture dependency unavailable',str(caught.exception));self.assertIn('exit=7',str(caught.exception))
            self.assertIn('fixture dependency unavailable',output.getvalue());self.assertIn('fixture dependency unavailable',(root/'setup.log').read_text())
    def test_notebook_streams_success_and_redacts_bearer_tokens(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(self.runner(root)([sys.executable,'-c','print("Authorization: Bearer fixture-secret")'],'setup'),0)
            self.assertNotIn('fixture-secret',out.getvalue());self.assertNotIn('fixture-secret',(root/'setup.log').read_text())



class BootstrapExportTests(unittest.TestCase):
    def test_diagnostic_download_works_before_science_python_exists(self):
        import types,zipfile
        from unittest.mock import Mock
        n=json.loads((ROOT/'notebooks/active/15_colab_l4_area_first.ipynb').read_text())
        code=next(c['source'] for c in n['cells'] if c['cell_type']=='code' and 'Setup/startup diagnosis only' in c['source'])
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);(base/'setup-status.json').write_text(json.dumps({'stage':'disk_preflight','status':'FAILED'}))
            (base/'setup.log').write_text('ERROR: storage fixture\nAuthorization: Bearer fixture-secret\n')
            (base/'server.log').write_text('x'*70000+'\nServer fixture stopped\nAuthorization: Bearer server-secret\n')
            (base/'server-status.json').write_text(json.dumps({'status':'STOPPED','exit_code':0}))
            files=Mock();module=types.ModuleType('google.colab');module.files=files
            with patch.dict(sys.modules,{'google.colab':module}):exec(compile(code,'diagnostic-cell','exec'),{'BASE':base,'Path':Path})
            files.download.assert_called_once_with(str(base/'colab-diagnostics.zip'))
            with zipfile.ZipFile(base/'colab-diagnostics.zip') as z:
                self.assertIn('setup-status.json',z.namelist());self.assertIn('storage fixture',z.read('setup.log').decode())
                self.assertNotIn('fixture-secret',z.read('setup.log').decode())
                self.assertIn('Server fixture stopped',z.read('server.log').decode())
                self.assertNotIn('server-secret',z.read('server.log').decode())
                self.assertLessEqual(len(z.read('server.log')),65536)
                self.assertEqual(json.loads(z.read('server-status.json'))['status'],'STOPPED')
                self.assertEqual(len(z.namelist()),len(set(z.namelist())))

if __name__=='__main__':unittest.main()
