"""Nearest access ordering and exact-node reuse, no centroid approximations."""
import unittest,random,tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from shapely import STRtree
from shapely.geometry import Point,LineString
import li3_integration_tests as fixtures
from location_intelligent_li3_connectors import nearest_road_candidates,generate_connectors
from location_intelligent_market_runtime import _MarketRoutes,_market_store_routes
from location_intelligent_alternatives import reachable_alternatives

class NearestClusterTests(unittest.TestCase):
 def test_spatial_index_order_equals_full_scan_including_ties_and_far_targets(self):
  rng=random.Random(444)
  lines=[LineString([(rng.uniform(-500,500),rng.uniform(-500,500)),(rng.uniform(-500,500),rng.uniform(-500,500))]) for _ in range(300)]
  lines += [LineString([(0,0),(10,0)]),LineString([(0,0),(10,0)])]
  names=[str(i) for i in range(len(lines))];tree=STRtree(lines)
  for xy in [(0,0),(10,0),(10000,-20000),(-1000,800)]:
   point=Point(*xy);actual=list(nearest_road_candidates(point,tree,lines,names))
   expected=sorted([(point.distance(g),i) for i,g in enumerate(lines)],key=lambda x:(x[0],names[x[1]]))
   self.assertEqual(actual,expected)
  self.assertEqual(list(nearest_road_candidates(Point(0,0),STRtree([]),[],[])),[])
 def test_competitor_boundary_and_primary_secondary_classification(self):
  from location_intelligent_market_runtime import _market_store_in_scope
  from location_intelligent_market_config import get_market_config
  from location_intelligent_market import classify_store
  market=get_market_config()
  self.assertTrue(_market_store_in_scope('competitor',800.,market))
  self.assertFalse(_market_store_in_scope('competitor',800.01,market))
  self.assertTrue(_market_store_in_scope('indomaret',1500.,market))
  policy=market['allocation_requirements'];target=['name:jalan a']
  for tokens,tier in [(['name:jalan a'],'PRIMARY'),(['name:jalan b'],'SECONDARY'),([],'UNVERIFIED_CORRIDOR')]:
   store={'store_key':'test','kind':'competitor','distance_to_candidate_m':800.,'corridor_tokens':tokens}
   self.assertEqual(classify_store(store,target,policy)['tier'],tier)

 def test_nearest_entrance_beats_higher_class(self):
  import area_coverage_single_entrance_tests as tests
  f=tests.SingleEntranceTests();f.setUp();f.road(2,80)
  f.f['policy']['connectors']['building_entrance_profile']='SINGLE_NEAREST_VALID_V1'
  self.assertEqual(f.building(f.run_case())[0]['source_segment'],'w1_s0')
  # Nearest geometry rejected by known grade separation, so next valid wins.
  f.base['edge_sources']['w1_s0_f']['raw_tags']['bridge']='yes'
  self.assertEqual(f.building(f.run_case())[0]['source_segment'],'w2_s0')
 def test_shared_node_reuses_lookup_but_not_individual_connector_cost(self):
  f=fixtures.Fixtures();f.setUp();base=f.graph();x,y=f.x,f.y
  f.f['policy']['connectors']['building_entrance_profile']='SINGLE_NEAREST_VALID_V1'
  metrics={'target_xy':[x+80,y-10],'all_buildings':[],'selected_buildings':[]}
  for bid,dy in [('b0',20),('b1',-60)]:
   a=x-30;b=y+dy
   metrics['all_buildings'].append({'building_id':bid,'metric_geometry':{'type':'Polygon','coordinates':[[[a,b],[a+6,b],[a+6,b+6],[a,b+6],[a,b]]]}})
   metrics['selected_buildings'].append({'building_id':bid,'representative_point_m':[a+3,b+3]})
  package=generate_connectors(base,metrics,f.features,f.f)
  sources=[c for c in package['connectors'] if c['kind']=='BUILDING']
  self.assertEqual(len(sources),2);self.assertEqual(sources[0]['node_id'],sources[1]['node_id'])
  original=deepcopy(package)
  for c in original['connectors']:
   if c['kind']=='TARGET':c['alternative_store_key']='candidate'
  expected=reachable_alternatives(original,[{'store_key':'candidate'}],['b0','b1'])
  network=_MarketRoutes(package);calls=[];reverse=network.reverse
  def tracked(target):
   lookup=reverse(target)
   def one(node):calls.append(node);return lookup(node)
   return one
  with patch.object(network,'reverse',side_effect=tracked):
   actual=_market_store_routes(package,[{'store_key':'candidate'}],['b0','b1'],network,{})
  self.assertEqual(actual,expected);self.assertEqual(len(calls),1)
  self.assertNotEqual(actual['b0'][0]['total_distance_m'],actual['b1'][0]['total_distance_m'])

if __name__=='__main__':unittest.main()
