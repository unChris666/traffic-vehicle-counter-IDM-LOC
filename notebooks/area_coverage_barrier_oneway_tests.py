"""Owner simplified road-rule scenario, isolated from historical strict policy."""
import unittest,tempfile
from importlib.util import find_spec
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from location_intelligent_li3_graph import barrier_only_permission,apply_turns
from location_intelligent_market_runtime import source_request_config

class BarrierPermissionTests(unittest.TestCase):
 def test_unclear_vs_known_closed(self):
  self.assertTrue(barrier_only_permission({'barrier':'gate','access':'private','opening_hours':'09:00-10:00'})[0])
  self.assertTrue(barrier_only_permission({'barrier':'bollard'})[0])
  self.assertFalse(barrier_only_permission({'barrier':'gate','locked':'yes'})[0])
  self.assertFalse(barrier_only_permission({'barrier':'wall'})[0])
 def test_unresolved_turn_is_ignored_only_under_explicit_profile(self):
  self.assertEqual(apply_turns({}, {}, {}, {},profile='BARRIER_ONEWAY_EXPERIMENT_V1')[0],[])
 def test_rule_profile_is_calculation_only_for_source_identity(self):
  old={'latitude':-6.19,'longitude':106.83,'network_radius_m':3000}
  self.assertEqual(source_request_config(old),source_request_config({**old,'road_rule_profile':'BARRIER_ONEWAY_EXPERIMENT_V1'}))

@unittest.skipUnless(find_spec('shapely'),'Graph worker required')
class RoadGraphTests(unittest.TestCase):
 def fixture(self):
  import li3_integration_tests as tests
  f=tests.Fixtures();f.setUp();f.f['policy']['li3']['road_rule_profile']='BARRIER_ONEWAY_EXPERIMENT_V1';return f
 def test_unknown_access_class_private_and_conditions_are_assumptions(self):
  f=self.fixture();f.ways[0]['tags'].update(highway='primary',access='private',motorcycle='no',**{'access:conditional':'no @ (Mo-Fr)'})
  self.assertTrue(all(r['allowed'] is True for r in f.graph()['edge_rules'].values()))
  del f.f['policy']['li3']['road_rule_profile']
  self.assertFalse(all(r['allowed'] is True for r in f.graph()['edge_rules'].values()))
 def test_oneway_is_not_reversed_and_unknown_direction_is_not_usable(self):
  f=self.fixture();f.ways[0]['tags']['oneway']='yes';base=f.graph()
  self.assertEqual(sum(s['osm_way_id']==10 for s in base['edge_sources'].values()),2)
  self.assertTrue(all(s['direction']=='f' for s in base['edge_sources'].values() if s['osm_way_id']==10))
  f.ways[0]['tags']['oneway']='reversible';base=f.graph()
  self.assertTrue(all(base['edge_rules'][k]['allowed'] is None for k,s in base['edge_sources'].items() if s['osm_way_id']==10))
 def test_unknown_barrier_passes_but_known_closed_blocks(self):
  f=self.fixture();f.nodes[1]['tags']={'barrier':'gate','opening_hours':'09:00-10:00'}
  self.assertTrue(all(r['allowed'] is True for r in f.graph()['edge_rules'].values()))
  f.nodes[1]['tags']['locked']='yes'
  self.assertTrue(all(r['allowed'] is False for r in f.graph()['edge_rules'].values()))
 def test_unclear_barrier_way_ignored_known_wall_kept(self):
  from location_intelligent_li3_connectors import barrier_index
  f=self.fixture();way={'type':'way','id':99,'nodes':[1,2],'tags':{'barrier':'unknown'}}
  features={'payload':{'elements':[deepcopy(n) for n in f.nodes]+[way]}}
  self.assertEqual(len(barrier_index(features,f.f)['shapes']),0)
  way['tags']['barrier']='wall'
  self.assertEqual(len(barrier_index(features,f.f)['shapes']),1)

 def test_conditional_oneway_ignored_static_oneway_retained(self):
  f=self.fixture();f.ways[0]['tags'].update(oneway='yes',**{'oneway:conditional':'no @ (Su)'})
  base=f.graph();self.assertEqual(sum(s['osm_way_id']==10 for s in base['edge_sources'].values()),2)

@unittest.skipUnless(find_spec('osgeo'),'GDAL worker required')
class SimplifiedMotorTests(unittest.TestCase):
 def fixture(self):
  import location_intelligent_motor_routing_tests as tests
  f=tests.MotorRoutingTests();f.setUp();f.p['li3']['road_rule_profile']='BARRIER_ONEWAY_EXPERIMENT_V1'
  f.p['motorcycle_access'].update(private_access_usable=True,pedestrian_only_usable=True,stairs_usable=True)
  return f
 def test_tag_restrictions_bypassed_only_for_profile_and_unknown_still_not_accepted(self):
  f=self.fixture()
  for rule in f.e['edge_rules'].values():rule['raw_tags']={'access':'private','access:conditional':'no @ (Mo-Fr)'}
  r=f.run_motor();self.assertEqual(r['status'],'SUCCEEDED',r);self.assertGreater(r['summary']['scenario_accepted'],0)
  for rule in f.e['edge_rules'].values():rule['allowed']=None
  r=f.run_motor();self.assertEqual(r['summary']['scenario_accepted'],0,r)
  self.assertTrue(all(row['scenario_accessible'] is not True for row in r['routes']))

if __name__=='__main__':unittest.main()
