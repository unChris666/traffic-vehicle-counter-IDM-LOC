"""Notebook16 packaging and explicit opt-in; no cloud/engine execution."""
import ast,base64,hashlib,io,json,unittest,zipfile
from pathlib import Path
from traffic_location import __version__
ROOT=Path(__file__).resolve().parents[1]

class FlowNotebookTests(unittest.TestCase):
    def test_new_notebook_embeds_exact_package_and_explicit_independent_mode(self):
        n=json.loads((ROOT/'notebooks/active/16_colab_l4_independent_flow.ipynb').read_text())
        code=[]
        for c in n['cells']:
            if c['cell_type']=='code':
                compile(c['source'],'flow-cell','exec');code.append(c['source'])
                self.assertEqual(c['outputs'],[]);self.assertIsNone(c['execution_count'])
        setup=next(s for s in code if 'PAYLOAD=' in s)
        self.assertIn("'LI_COMPONENT_FLOW':'1'",setup)
        old=json.loads((ROOT/'notebooks/active/15_colab_l4_area_first.ipynb').read_text())
        old_setup=next(c['source'] for c in old['cells'] if c['cell_type']=='code' and 'PAYLOAD=' in c['source'])
        self.assertNotIn("'LI_COMPONENT_FLOW':'1'",old_setup)
        node=next(x for x in ast.walk(ast.parse(setup)) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in x.targets))
        data=base64.b64decode(ast.literal_eval(node.value.args[0]));self.assertIn(hashlib.sha256(data).hexdigest(),setup)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            with zipfile.ZipFile(io.BytesIO(z.read('package/traffic_location_engines-'+__version__+'-py3-none-any.whl'))) as wheel:
                for name in wheel.namelist():
                    if name.startswith('traffic_location/') and name.endswith('.py'):self.assertEqual(wheel.read(name),(ROOT/'src'/name).read_bytes(),name)
        self.assertNotIn('.execute(','\n'.join(code))
        self.assertEqual(n['metadata']['colab']['name'],'16_colab_l4_independent_flow.ipynb')
