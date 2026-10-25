"""Execute real source/calculation cells against pre-single-entrance packets."""
import unittest,json,tempfile,hashlib,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from copy import deepcopy
from location_intelligent_market_runtime import source_request_config,verify_market_source_packet,SourcePacketError
from location_intelligent_li3_sources import read_json,write_json
from location_intelligent_map_pilot import sha
ROOT=Path(__file__).parent

class SourceCompatibilityTests(unittest.TestCase):
 def packet(self,root):
  root.mkdir();(root/'source.data').write_bytes(b'RETAINED SOURCE')
  config={'latitude':-6.19,'longitude':106.83,'network_radius_m':3000,'network_feature_mode':'ROADS_ONLY_EXPERIMENT','max_building_rows':50000}
  write_json(root/'source_manifest.json',{'config':config,'files':{'source.data':sha(root/'source.data')}})
  return config
 def env(self,root,config,mode):
  env={};exec((ROOT/'location_intelligent_notebook_runtime.py').read_text(),env)
  env['NOTEBOOK_REPORT_PATH']=root/'readiness.json'
  env.update(Path=Path,os=os,FROZEN_SOURCE_INPUT=None,SOURCE_MODE=mode,SOURCES=root/'sources',CONFIG=config,
   NETWORK_FOLDER=root/'sources/network_roads_only',read_json=read_json,write_json=write_json,sha=sha,
   PILOT=root/'pilot',display=lambda rows:None,pd=SimpleNamespace(DataFrame=lambda rows:rows))
  for stage in ['dependencies','configuration']:env['STAGES'][stage]={'status':'SUCCEEDED'}
  return env
 def notebook(self,index):return ''.join(json.loads((ROOT/'area_coverage_market_cpu_2km.ipynb').read_text())['cells'][index]['source'])
 def test_reproduce_legacy_full_config_assertion_then_reopen_unchanged(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);old=self.packet(root/'sources');new={**old,'building_entrance_profile':'SINGLE_HIGHEST_CLASS_NEAREST_V1','road_rule_profile':'BARRIER_ONEWAY_EXPERIMENT_V1'}
   before={p.name:p.read_bytes() for p in (root/'sources').iterdir()}
   with self.assertRaises(AssertionError):assert read_json(root/'sources/source_manifest.json')['config']==new
   self.assertEqual(verify_market_source_packet(root/'sources',new)['config'],old)
   self.assertEqual(before,{p.name:p.read_bytes() for p in (root/'sources').iterdir()})
   self.assertEqual(source_request_config(new),source_request_config(old))
 def test_actual_cells_accept_legacy_source_and_unblock_calculation_with_optional_poi_failure(self):
  for mode in ['ACQUIRE_ONCE','FROZEN']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d,patch.dict(os.environ):
    root=Path(d);old=self.packet(root/'sources');config={**old,'building_entrance_profile':'SINGLE_HIGHEST_CLASS_NEAREST_V1','road_rule_profile':'BARRIER_ONEWAY_EXPERIMENT_V1'}
    env=self.env(root,config,mode);before=(root/'sources/source_manifest.json').read_bytes()
    with patch('importlib.reload',side_effect=lambda m:m),patch('location_intelligent_market_runtime.acquire_market_network',side_effect=AssertionError('MUST NOT REFETCH')) as fetch,patch('location_intelligent_map_poi.load_optional_osm_pois',return_value={'status':'FAILED','count':None,'rows':None}):
     exec(self.notebook(54),env)
    fetch.assert_not_called();self.assertEqual(env['STAGES']['sources']['status'],'PARTIAL')
    self.assertIsNone(env['facilities']['count']);self.assertEqual((root/'sources/source_manifest.json').read_bytes(),before)
    # Exercise actual calculation cell in frozen mode, without an expensive replay.
    pilot=env['PILOT'];pilot.mkdir();write_json(pilot/'manifest.json',{})
    write_json(pilot/'report.json',{'all_source_rows_accounted':1,'source_records':1,'decision_counts_selected':{'ACCEPTED':1},'status':'PARTIAL'})
    env['verify_manifest']=lambda root:None
    exec(self.notebook(56),env)
    self.assertEqual(env['STAGES']['calculation']['status'],'PARTIAL')
 def test_coordinate_network_mode_extent_and_checksum_guards_remain(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'sources';old=self.packet(root)
   for key,value in [('latitude',-7),('network_radius_m',9000),('network_feature_mode','FULL')]:
    with self.subTest(key=key),self.assertRaises(SourcePacketError) as error:
     verify_market_source_packet(root,{**old,key:value})
    self.assertEqual(error.exception.code,'SOURCE_CONFIG_MISMATCH')
   (root/'source.data').write_bytes(b'CORRUPT')
   with self.assertRaises(SourcePacketError) as error:verify_market_source_packet(root,old)
   self.assertEqual(error.exception.code,'SOURCE_SNAPSHOT_CHANGED')
 def test_real_source_cell_reports_specific_code_and_blocks_invalid_input(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);old=self.packet(root/'sources');env=self.env(root,{**old,'longitude':100.0},'FROZEN')
   with patch('importlib.reload',side_effect=lambda m:m):exec(self.notebook(54),env)
   self.assertEqual(env['STAGES']['sources']['error_code'],'SOURCE_CONFIG_MISMATCH')
   exec(self.notebook(56),env);self.assertEqual(env['STAGES']['calculation']['status'],'BLOCKED')
   self.assertIsNone(read_json(root/'readiness.json')['candidate_buildings'])
if __name__=='__main__':unittest.main()
