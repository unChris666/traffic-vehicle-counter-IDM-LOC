"""Execute notebook failure paths with mocked upstream errors, no live API."""
import unittest,tempfile,json,sys,hashlib
from pathlib import Path
from types import ModuleType,SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent

class NotebookTests(unittest.TestCase):
 def runtime(self,path):
  env={};exec((ROOT/'location_intelligent_notebook_runtime.py').read_text(),env)
  env['NOTEBOOK_REPORT_PATH']=path/'readiness.json';return env
 def test_stale_import_replaced_from_verified_written_files(self):
  original={k:v for k,v in sys.modules.items() if k.startswith('location_intelligent_')};paths=list(sys.path)
  try:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);env=self.runtime(root)
    sources={'location_intelligent_map_poi.py':'def load_optional_osm_pois():return "NEW"\n',
             'location_intelligent_market_runtime.py':'def acquire_market_network():pass\ndef build_market():pass\n'}
    for name,body in sources.items():(root/name).write_text(body)
    stale=ModuleType('location_intelligent_map_poi');sys.modules['location_intelligent_map_poi']=stale
    env['activate_notebook_sources'](root,{n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()})
    self.assertEqual(sys.modules['location_intelligent_map_poi'].load_optional_osm_pois(),'NEW')
    with self.assertRaisesRegex(RuntimeError,'SOURCE_INSTALL_INCOMPLETE'):env['activate_notebook_sources'](root,{'missing.py':'x'})
  finally:
   for name in list(sys.modules):
    if name.startswith('location_intelligent_'):del sys.modules[name]
   sys.modules.update(original);sys.path[:]=paths
 def test_actual_source_cell_handles_500_502_and_blocks_downstream_without_stale_counts(self):
  n=json.loads((ROOT/'area_coverage_market_cpu_2km.ipynb').read_text())
  for status in [500,502]:
   with self.subTest(status=status),tempfile.TemporaryDirectory() as d:
    root=Path(d);env=self.runtime(root)
    env.update(Path=Path,FROZEN_SOURCE_INPUT=None,SOURCE_MODE='ACQUIRE_ONCE',SOURCES=root/'sources',
               NETWORK_FOLDER=root/'sources/network_roads_only',CONFIG={},MARKET={'summary':{'candidate_whole_buildings':999}})
    for key in ['dependencies','configuration']:env['STAGES'][key]={'status':'SUCCEEDED'}
    with patch('importlib.reload',side_effect=lambda m:m),patch('location_intelligent_market_runtime.acquire_market_network',side_effect=RuntimeError('HTTP '+str(status))):
     exec(''.join(n['cells'][54]['source']),env)
    self.assertEqual(env['STAGES']['sources']['status'],'FAILED')
    exec(''.join(n['cells'][56]['source']),env)
    exec(''.join(n['cells'][60]['source']),env)
    self.assertEqual(env['STAGES']['allocation']['status'],'BLOCKED')
    with patch.dict('sys.modules',{'IPython.display':SimpleNamespace(display=lambda *a:None,HTML=lambda s:s,FileLink=lambda s:s)}):
     exec(''.join(n['cells'][62]['source']),env)
    r=json.loads((root/'readiness.json').read_text())
    self.assertEqual(r['status'],'NOT_READY');self.assertIsNone(r['candidate_buildings'])
    self.assertIsNone(env['MARKET'])
