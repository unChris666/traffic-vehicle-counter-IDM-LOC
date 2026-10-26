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
        package=zipfile.ZipFile(io.BytesIO(z.read('package/traffic_location_engines-0.4.8rc1-py3-none-any.whl')))
        for name in package.namelist():
            if name.startswith('traffic_location/') and name.endswith('.py'):
                self.assertEqual(package.read(name),(ROOT/'src'/name).read_bytes(),name)
        all_code='\n'.join(sources)
        self.assertIn('share=True',all_code);self.assertIn('APP.block_thread()',all_code)
        self.assertNotIn('.execute(',all_code);self.assertNotIn('CUDA_VISIBLE_DEVICES',all_code)
if __name__=='__main__':unittest.main()
