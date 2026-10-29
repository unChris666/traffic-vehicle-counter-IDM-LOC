import ast,base64,io,json,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class NotebookTests(unittest.TestCase):
    def test_exact_source_wheel_and_only_explicit_server_launch(self):
        n=json.loads((ROOT/'notebooks/14_gate2_sorong_t7sl_gradio.ipynb').read_text())
        sources=[c['source'] if isinstance(c['source'],str) else ''.join(c['source']) for c in n['cells']]
        for c,s in zip(n['cells'],sources):
            if c['cell_type']=='code':compile(s,'notebook','exec');self.assertEqual(c['outputs'],[])
        s=next(s for s in sources if 'PAYLOAD=' in s)
        a=next(x for x in ast.walk(ast.parse(s)) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in x.targets))
        z=zipfile.ZipFile(io.BytesIO(base64.b64decode(ast.literal_eval(a.value.args[0]))))
        package=zipfile.ZipFile(io.BytesIO(z.read('package/traffic_location_engines-0.7.3rc3-py3-none-any.whl')))
        for name in package.namelist():
            if name.startswith('traffic_location/') and name.endswith('.py'):
                self.assertEqual(package.read(name),(ROOT/'src'/name).read_bytes(),name)
        all_code='\n'.join(sources)
        self.assertIn('share=True',all_code);self.assertIn('APP.block_thread()',all_code)
        self.assertNotIn('.execute(',all_code);self.assertNotIn('CUDA_VISIBLE_DEVICES',all_code)
if __name__=='__main__':unittest.main()

class NotebookCleanupTests(unittest.TestCase):
    def test_interrupt_closes_the_share_server(self):
        import tempfile
        from unittest.mock import Mock,patch
        n=json.loads((ROOT/'notebooks/14_gate2_sorong_t7sl_gradio.ipynb').read_text())
        code=next((c['source'] if isinstance(c['source'],str) else ''.join(c['source'])) for c in n['cells'] if c['cell_type']=='code' and 'APP.block_thread()' in ''.join(c['source']))
        app=Mock();app.block_thread.side_effect=KeyboardInterrupt
        old=Mock()
        with tempfile.TemporaryDirectory() as d,patch('traffic_location.integration.gradio_app.launch',return_value=(app,'https://software-fixture.invalid')):
            with self.assertRaises(KeyboardInterrupt):
                exec(compile(code,'launch-cell','exec'),{'BASE':Path(d),'APP':old})
        old.close.assert_called_once();app.close.assert_called_once()

class ReleaseVersionTests(unittest.TestCase):
    def test_package_notebook_and_build_metadata_share_one_version(self):
        import tomllib
        from traffic_location import __version__
        declared=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
        self.assertEqual(declared,__version__)
        notebook=json.loads((ROOT/'notebooks/14_gate2_sorong_t7sl_gradio.ipynb').read_text())
        code=next(c['source'] if isinstance(c['source'],str) else ''.join(c['source']) for c in notebook['cells'] if 'PAYLOAD=' in ''.join(c['source']))
        assignment=next(x for x in ast.walk(ast.parse(code)) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in x.targets))
        bundle=zipfile.ZipFile(io.BytesIO(base64.b64decode(ast.literal_eval(assignment.value.args[0]))))
        wheel=zipfile.ZipFile(io.BytesIO(bundle.read('package/traffic_location_engines-'+declared+'-py3-none-any.whl')))
        metadata=wheel.read('traffic_location_engines-'+declared+'.dist-info/METADATA').decode()
        self.assertIn('\nVersion: '+declared+'\n',metadata)
