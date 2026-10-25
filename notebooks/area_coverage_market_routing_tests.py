"""Section8 reuse, store routing and gate direction tests. No remote API."""
import unittest,tempfile,random,math
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import li3_integration_tests as fixtures
from location_intelligent_li3_graph import build_graph
from location_intelligent_li3_connectors import generate_connectors
from location_intelligent_li3_sources import write_json
from location_intelligent_market_runtime import _reuse_calculation_connectors,_MarketRoutes,_market_store_routes,_poi_gate
from location_intelligent_motor_routing import _path_index,_potential_reachability
from location_intelligent_alternatives import reachable_alternatives
from location_intelligent_market_config import get_market_config

class MarketRoutingTests(unittest.TestCase):
 def setup_case(self,restriction=None,profile='SINGLE_HIGHEST_CLASS_NEAREST_V1'):
  f=fixtures.Fixtures();f.setUp()
  f.f['policy']['connectors']['building_entrance_profile']=profile
  if restriction=='conditional':f.relation('no_left_turn',**{'restriction:conditional':'no_left_turn @ (Mo-Fr)'})
  elif restriction:f.relation(restriction)
  base=f.graph();x,y=f.x,f.y
  metrics={'target_xy':[x+80,y-10], 'all_buildings':[], 'selected_buildings':[]}
  for i,offset in enumerate([20,60]):
   bid='b'+str(i);a=x+offset;b=y+20
   metrics['all_buildings'].append({'building_id':bid,'metric_geometry':{'type':'Polygon','coordinates':[[[a,b],[a+6,b],[a+6,b+6],[a,b+6],[a,b]]]}})
   metrics['selected_buildings'].append({'building_id':bid,'representative_point_m':[a+3,b+3]})
  targets=[{'store_key':'a','target_xy':[x+140,y-10]}, {'store_key':'b','target_xy':[x+140,y-10]}, {'store_key':'end','target_xy':[x,y-5]}]
  return f,base,metrics,targets
 def packages(self,root,restriction=None,profile='SINGLE_HIGHEST_CLASS_NEAREST_V1'):
  f,base,metrics,targets=self.setup_case(restriction,profile)
  retained=generate_connectors(base,metrics,f.features,f.f)
  write_json(root/'graph/base_graph.json.gz',base['graph']);write_json(root/'graph/base_edge_sources.json.gz',base['edge_sources'])
  write_json(root/'connectors/connectors.json.gz',retained['connectors'])
  original=generate_connectors(base,metrics,f.features,f.f,alternative_targets=targets)
  # Reuse path may ask generator for targets only, never for building entrances.
  original_generator=generate_connectors
  def targets_only(base,metrics,*args,**kwargs):
   self.assertEqual(metrics['selected_buildings'],[])
   return original_generator(base,metrics,*args,**kwargs)
  with patch('location_intelligent_li3_connectors.generate_connectors',side_effect=targets_only):
   reused=_reuse_calculation_connectors(root,metrics,f.features,f.f,targets)
  return original,reused
 def test_extended_graph_connectors_rules_and_turns_equal_rebuild(self):
  for profile,restriction in [(p,r) for p in ['MULTI_ACCESS_LEGACY','SINGLE_HIGHEST_CLASS_NEAREST_V1'] for r in [None,'no_left_turn','only_right_turn','conditional']]:
   with self.subTest(profile=profile,restriction=restriction),tempfile.TemporaryDirectory() as d:
    original,reused=self.packages(Path(d),restriction,profile)
    for name in ['graph','edge_sources','edge_rules','blocked_turns']:self.assertEqual(original[name],reused[name],name)
    self.assertEqual(sorted(original['connectors'],key=lambda c:c['connector_id']),sorted(reused['connectors'],key=lambda c:c['connector_id']))
 def test_store_matrix_matches_legacy_and_shares_target_node_search(self):
  with tempfile.TemporaryDirectory() as d:
   original,reused=self.packages(Path(d));stores=[{'store_key':k} for k in ['candidate','a','b','end']]
   old=deepcopy(original)
   for c in old['connectors']:
    if c['kind']=='TARGET' and not c.get('alternative_store_key'):c['alternative_store_key']='candidate'
   expected=reachable_alternatives(old,stores,['b0','b1']);network=_MarketRoutes(reused)
   with patch.object(network,'reverse',wraps=network.reverse) as calls:
    actual=_market_store_routes(reused,stores,['b0','b1'],network,{})
   self.assertEqual(expected,actual);self.assertEqual(calls.call_count,3) # a/b share target node
 def test_primary_routes_skip_redundant_candidate_search(self):
  with tempfile.TemporaryDirectory() as d:
   _,reused=self.packages(Path(d));network=_MarketRoutes(reused)
   with patch.object(network,'reverse',side_effect=AssertionError('must reuse primary')):
    r=_market_store_routes(reused,[{'store_key':'candidate'}],['b0'],network,{'b0':{'selected_candidate':{'total_distance_m':1}}})
   self.assertEqual(r,{'b0':[]})
 def test_forward_paths_match_reverse_and_unknown_reachability(self):
  rng=random.Random(38)
  for trial in range(12):
   edges=[];rules={}
   for i in range(8):
    for j in range(8):
     if i!=j and rng.random()<.25:
      key=f'{i}-{j}';edges.append({'edge_id':key,'u':str(i),'v':str(j),'length_m':rng.choice([1.,2.,3.,.1,.2])})
      rules[key]={'allowed':rng.choice([True,True,True,None,False])}
   turns=[{'from_edge':a['edge_id'],'to_edge':b['edge_id']} for a in edges for b in edges if a['v']==b['u'] and rng.random()<.08]
   p={'graph':{'nodes':[{'node_id':str(i)} for i in range(8)],'edges':edges},'edge_rules':rules,'blocked_turns':turns}
   n=_MarketRoutes(p);strict=n.forward('0');possible=n.potential_forward('0')
   for target in map(str,range(8)):
    old=_path_index(p['graph'],n.allowed,n.blocked,target)('0');new=strict(target)
    self.assertEqual(old is None,new is None)
    if old:self.assertAlmostEqual(old['distance_m'],new['distance_m'],places=12)
    self.assertEqual(possible(target),_potential_reachability(p['graph'],n.allowed,n.blocked,target)('0'))
 def test_gate_uses_one_forward_search_for_multiple_pois(self):
  with tempfile.TemporaryDirectory() as d:
   _,package=self.packages(Path(d));network=_MarketRoutes(package)
   pois=[{'source_id':'hospital-'+key,'store_key':key,'category':'hospital'} for key in ['a','b']]
   with patch.object(network,'forward',wraps=network.forward) as searches:
    gate=_poi_gate({'metric_crs':'EPSG:32748'},get_market_config()['allocation_requirements'],
                   {'status':'SUCCEEDED'},package,pois,{'features':[]},network=network)
   self.assertEqual(searches.call_count,1);self.assertEqual(gate['state'],'OPEN')
   self.assertEqual(gate['positive_attractors'],['hospital-a','hospital-b'])

 def test_gate_unavailable_remains_unknown_without_search(self):
  policy=get_market_config()['allocation_requirements']
  self.assertEqual(_poi_gate({},policy,{'status':'FAILED'},{},[],{})['state'],'UNKNOWN')

if __name__=='__main__':unittest.main()
