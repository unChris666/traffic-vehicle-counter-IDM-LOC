"""Single entrance decisions; synthetic metric fixtures, no live source access."""
from copy import deepcopy
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from importlib.util import find_spec
from location_intelligent_li3_connectors import generate_connectors
from location_intelligent_alternatives import reachable_alternatives

@unittest.skipUnless(find_spec('shapely'),'Shapely geometry worker required')
class SingleEntranceTests(unittest.TestCase):
 def setUp(self):
  import li3_integration_tests as fixtures
  f=fixtures.ConnectorTests();f.setUp();self.f=f.f;self.base=f.base;self.metrics=f.metrics;self.features=f.features
  self.f['policy']['connectors']['building_entrance_profile']='SINGLE_HIGHEST_CLASS_NEAREST_V1'
 def road(self,i,y,highway='primary',allowed=True):
  edge=deepcopy(self.base['graph']['edges'][0]);key=f'w{i}_s0_f'
  edge.update(edge_id=key,key=key,u=f'a{i}',v=f'b{i}',highway=highway,
   geometry={'type':'LineString','coordinates':[[0,y],[100,y]]})
  self.base['graph']['nodes'] += [{'node_id':f'a{i}','x':0.,'y':float(y)},{'node_id':f'b{i}','x':100.,'y':float(y)}]
  self.base['graph']['edges'].append(edge)
  self.base['edge_sources'][key]={'osm_way_id':i,'segment_index':0,'direction':'f','raw_tags':{'highway':highway}}
  self.base['edge_rules'][key]={'allowed':allowed,'raw_tags':{},'evidence_refs':['SYNTHETIC']}
 def run_case(self):return generate_connectors(self.base,self.metrics,self.features,self.f)
 def building(self,r):return [c for c in r['connectors'] if c['kind']=='BUILDING']
 def test_high_class_before_nearest_and_single_connector(self):
  self.road(2,80);r=self.run_case();rows=self.building(r)
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['source_segment'],'w2_s0')
  self.assertEqual(r['diagnostics']['building_candidates_checked'],1)
 def test_same_class_nearest_then_stable_segment_id(self):
  self.road(2,80);self.road(3,60);self.road(4,60)
  a=self.run_case();self.assertEqual(self.building(a)[0]['source_segment'],'w3_s0')
  self.base['graph']['edges'].reverse();self.metrics['all_buildings'].reverse()
  self.assertEqual(a,self.run_case())
 def test_invalid_high_class_can_try_next_geometry_before_routing(self):
  self.road(2,80,allowed=False)
  self.assertEqual(self.building(self.run_case())[0]['source_segment'],'w1_s0')
 def test_footprint_obstruction_rejects_high_class(self):
  self.road(2,80)
  self.metrics['all_buildings'].append({'building_id':'obstacle','metric_geometry':{'type':'Polygon','coordinates':[[[40,45],[50,45],[50,55],[40,55],[40,45]]]}})
  r=self.run_case();self.assertEqual(self.building(r)[0]['source_segment'],'w1_s0')
  self.assertTrue(any(c['reason']=='MAPPED_BARRIER_OR_BUILDING' for c in r['rejected_candidates']))
  self.assertLessEqual(r['diagnostics']['footprint_buffers_calculated'],len(self.metrics['all_buildings']))
 def test_disconnected_selected_entrance_does_not_try_local_route(self):
  self.road(2,80);r=self.run_case()
  for c in r['connectors']:
   if c['kind']=='TARGET':c['alternative_store_key']='candidate'
  self.assertEqual(reachable_alternatives(r,[{'store_key':'candidate'}],['b1'])['b1'],[])
  legacy=deepcopy(self.f);legacy['policy']['connectors'].pop('building_entrance_profile')
  r=generate_connectors(self.base,self.metrics,self.features,legacy)
  for c in r['connectors']:
   if c['kind']=='TARGET':c['alternative_store_key']='candidate'
  self.assertEqual(len(reachable_alternatives(r,[{'store_key':'candidate'}],['b1'])['b1']),1)
 def test_entrance_change_reuses_source_snapshot_without_refetch(self):
  from location_intelligent_market_runtime import acquire_market_network
  cfg={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748','network_radius_m':3000.,'poi_overpass_endpoints':['https://example.invalid']}
  success={'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':'2026-10-25T00:00:00Z'},'elements':[]}}
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'network'
   with patch('location_intelligent_li3_sources.acquire_overpass',return_value=success):acquire_market_network(cfg,root)
   cfg['building_entrance_profile']='SINGLE_HIGHEST_CLASS_NEAREST_V1'
   with patch('location_intelligent_li3_sources.acquire_overpass',side_effect=AssertionError('No refetch')):
    acquire_market_network(cfg,root)

 def test_boundary125_and_input_immutability(self):
  before=deepcopy((self.base,self.metrics,self.features,self.f))
  self.run_case();self.assertEqual(before,(self.base,self.metrics,self.features,self.f))
  self.metrics['selected_buildings'][0]['representative_point_m']=[45,125]
  self.assertEqual(len(self.building(self.run_case())),1)
  self.metrics['selected_buildings'][0]['representative_point_m']=[45,125.0001]
  self.assertEqual(self.building(self.run_case()),[])

@unittest.skipUnless(find_spec('osgeo'),'GDAL worker required')
class SingleMotorTests(unittest.TestCase):
 def fixture(self):
  import location_intelligent_motor_routing_tests as tests
  f=tests.MotorRoutingTests();f.setUp()
  f.p['connectors'].update(building_entrance_profile='SINGLE_HIGHEST_CLASS_NEAREST_V1',
   candidate_selection='HIGHEST_VALID_CLASS_THEN_NEAREST_REPRESENTATIVE_POINT_THEN_SEGMENT_ID',
   unreachable_higher_class='NO_ROUTE_NO_ENTRANCE_FALLBACK')
  return f
 def test_route_failure_is_not_recovered_by_second_entrance(self):
  f=self.fixture()
  f.e['connectors']=[c for c in f.e['connectors'] if c['kind']=='TARGET' or c['connector_id'].endswith('high')]
  edge=f.g['edges'][0];edge['u'],edge['v']=edge['v'],edge['u'];edge['geometry']['coordinates'].reverse()
  r=f.run_motor();self.assertEqual(r['status'],'SUCCEEDED',r)
  self.assertTrue(all(row['route_found'] is False and row['selected_candidate'] is None for row in r['routes']))
 def test_multiple_entrances_rejected_in_single_profile(self):
  f=self.fixture();r=f.run_motor()
  self.assertEqual(r['status'],'FAILED',r)
  self.assertIn({'code':'MULTIPLE_ENTRANCES_IN_SINGLE_PROFILE'},r['diagnostics'])

if __name__=='__main__':unittest.main()
