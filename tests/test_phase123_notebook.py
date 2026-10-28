"""Notebook17 enables reviewed requests without executing engines on import."""
import ast,base64,io,json,unittest,zipfile
from pathlib import Path
from traffic_location import __version__
ROOT=Path(__file__).resolve().parents[1]

class PhaseNotebookTests(unittest.TestCase):
    def test_exact_package_opt_in_and_clean_cells(self):
        n=json.loads((ROOT/'notebooks/active/17_colab_l4_phase123_user_testing.ipynb').read_text())
        code=[]
        for c in n['cells']:
            if c['cell_type']=='code':
                compile(c['source'],'phase123-cell','exec');code.append(c['source'])
                self.assertEqual(c['outputs'],[]);self.assertIsNone(c['execution_count'])
        setup=next(s for s in code if 'PAYLOAD=' in s)
        self.assertIn("'LI_PHASE123':'1'",setup);self.assertIn("'LI_COMPONENT_FLOW':'1'",setup)
        node=next(x for x in ast.walk(ast.parse(setup)) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in x.targets))
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(ast.literal_eval(node.value.args[0])))) as z:
            with zipfile.ZipFile(io.BytesIO(z.read('package/traffic_location_engines-'+__version__+'-py3-none-any.whl'))) as wheel:
                for name in wheel.namelist():
                    if name.startswith('traffic_location/') and name.endswith('.py'):self.assertEqual(wheel.read(name),(ROOT/'src'/name).read_bytes(),name)
        self.assertNotIn('.execute(','\n'.join(code))
        self.assertEqual(n['metadata']['colab']['name'],'17_colab_l4_phase123_user_testing.ipynb')
