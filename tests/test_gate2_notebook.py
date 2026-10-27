"""Static/publish-off notebook checks; never execute setup, cloud or inference."""
import ast,base64,hashlib,io,json,unittest,zipfile,contextlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class NotebookRouteTests(unittest.TestCase):
    def setUp(self):
        self.notebook=json.loads((ROOT/'notebooks/11_gate2_t7sl_sorong_quiz.ipynb').read_text())
        self.code=[''.join(c['source']) for c in self.notebook['cells'] if c['cell_type']=='code']
    def test_all_cells_compile_and_publication_off_runs_no_setup(self):
        env={}
        with contextlib.redirect_stdout(io.StringIO()):
            for i,s in enumerate(self.code):
                exec(compile(s,str(i),'exec'),env)
        self.assertFalse(env['ENABLE_NOTEBOOK_SETUP'])
        self.assertNotIn('RUNTIME',env);self.assertNotIn('subprocess',env)
        for c in self.notebook['cells']:
            if c['cell_type']=='code':self.assertEqual(c['outputs'],[]);self.assertIsNone(c['execution_count'])
    def test_embedded_wheel_exact_no_old_glob_and_force_install(self):
        bootstrap=next(s for s in self.code if 'PAYLOAD=' in s)
        tree=ast.parse(bootstrap)
        assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in n.targets))
        raw=base64.b64decode(ast.literal_eval(assignment.value.args[0]));z=zipfile.ZipFile(io.BytesIO(raw))
        names=[n for n in z.namelist() if n.startswith('package/')]
        self.assertEqual(names,['package/traffic_location_engines-0.5.0rc1-py3-none-any.whl'])
        wheel=z.read(names[0]);self.assertIn(hashlib.sha256(wheel).hexdigest(),bootstrap)
        self.assertIn('--force-reinstall',bootstrap)
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='glob' for n in ast.walk(tree)))
        package=zipfile.ZipFile(io.BytesIO(wheel))
        source=package.read('traffic_location/integration/kaggle_runtime.py')
        self.assertEqual(source,(ROOT/'src/traffic_location/integration/kaggle_runtime.py').read_bytes())
        for name in package.namelist():
            if name.startswith('traffic_location/') and name.endswith('.py'):
                path=ROOT/'src'/name
                self.assertTrue(path.is_file(), 'Stale Python module in embedded wheel: '+name)
                self.assertEqual(package.read(name),path.read_bytes(),name)
    def test_user_quiz_has_no_technical_paths_or_manual_runtime_switch(self):
        quiz=next(s for s in self.code if 'import ipywidgets' in s)
        for token in ('area_path','core_path','assets_path','model_folder','provenance=W.Text'):
            self.assertNotIn(token,quiz)
        self.assertIn('RUNTIME.probe()',quiz);self.assertIn('RUNTIME.execute(',quiz)
        self.assertNotIn('INSTALL_TRAFFIC_RUNTIME',''.join(self.code))
    def test_eighteen_hours_does_not_silently_change_business_rule(self):
        text=''.join(''.join(c['source']) for c in self.notebook['cells'])
        self.assertIn('jam>15',text);self.assertIn('sesi tambahan',text)
        quiz=next(s for s in self.code if 'import ipywidgets' in s)
        self.assertIn('ppac_parameters_mvp_v2',quiz)

if __name__=='__main__':unittest.main()
