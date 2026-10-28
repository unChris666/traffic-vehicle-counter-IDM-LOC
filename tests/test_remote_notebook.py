import ast,base64,io,json,zipfile,unittest,importlib.util,tempfile,os,socket
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('remote_probe',ROOT/'tools/colab_remote_probe.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
class RemoteTests(unittest.TestCase):
 def test_remote_notebook_compiles_and_embeds_exact_wheel(self):
  from traffic_location import __version__
  n=json.loads((ROOT/'notebooks/active/18_colab_l4_gradio_remote.ipynb').read_text());code=[]
  for c in n['cells']:
   if c['cell_type']=='code':
    compile(c['source'],'remote-cell','exec');self.assertEqual(c['outputs'],[]);self.assertIsNone(c['execution_count']);code.append(c['source'])
  server=next(s for s in code if 'SERVER=subprocess.Popen' in s)
  self.assertIn("UI_ACCESS='gradio'",server);self.assertIn("remote['status']=='READY'",server);self.assertIn('LINK PUBLIK BELUM SIAP',server)
  self.assertIn('remote-access-check.json','\n'.join(code))
  setup=next(s for s in code if 'PAYLOAD=' in s)
  node=next(x for x in ast.walk(ast.parse(setup)) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in x.targets))
  with zipfile.ZipFile(io.BytesIO(base64.b64decode(ast.literal_eval(node.value.args[0])))) as z:
   with zipfile.ZipFile(io.BytesIO(z.read('package/traffic_location_engines-'+__version__+'-py3-none-any.whl'))) as wheel:
    for name in wheel.namelist():
     if name.startswith('traffic_location/') and name.endswith('.py'):self.assertEqual(wheel.read(name),(ROOT/'src'/name).read_bytes())
 def test_real_get_and_post_probe_does_not_start_engine(self):
  from traffic_location.artifacts import write
  from traffic_location.integration.gradio_app import launch
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LI_PHASE123':'1','LI_COMPONENT_FLOW':'1'}):
   p=Path(d);write(p/'config/experiment.json',{'videos':[]})
   def forbidden(*a,**kw):raise AssertionError('Probe must not create runtime')
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   app,url=launch(p/'system',p/'config',share=False,server_port=port,runtime_factory=forbidden)
   try:
    report=probe.probe_remote('http://127.0.0.1:'+str(port),allow_loopback=True)
    self.assertEqual(report['status'],'READY',report);self.assertEqual(len(report['checks']),3)
   finally:app.close()
 def test_502_never_claims_public_ready(self):
  import urllib.error
  with patch('urllib.request.build_opener') as opener:
   opener.return_value.open.side_effect=urllib.error.HTTPError('https://fixture.gradio.live',502,'bad gateway',{},None)
   report=probe.probe_remote('https://fixture.gradio.live')
  self.assertEqual(report['status'],'NOT_READY');self.assertTrue(all(c['code']==502 for c in report['checks']))
 def test_unrelated_url_not_probed(self):
  with patch('urllib.request.build_opener') as opener:
   self.assertEqual(probe.probe_remote('https://example.invalid')['status'],'NOT_READY')
  opener.assert_not_called()
