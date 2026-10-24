"""Synthetic regression cases; not actual store/customer observations."""
import unittest
import tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
from location_intelligent_li3_sources import write_json
from copy import deepcopy
from location_intelligent_alternatives import rank_alternatives,reachable_alternatives
from location_intelligent_li3_connectors import generate_connectors
from location_intelligent_config import get_config
class AlternativeTests(unittest.TestCase):
 def test_alternative_cache_reopens_without_graph_rebuild(self):
  from location_intelligent_alternatives import build_alternatives
  from pyproj import Transformer
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pilot=root/'pilot';pilot.mkdir();(pilot/'manifest.json').write_text('{}')
   config={'latitude':-6.409737552410453,'longitude':106.82835008971841,'poi_radius_m':2000.0}
   x,y=Transformer.from_crs(4326,32748,always_xy=True).transform(config['longitude'],config['latitude'])
   write_json(pilot/'config/pilot.json',{'policy':{'li3':{'metric_crs':'EPSG:32748'}}})
   write_json(pilot/'normalized/metric_buildings.json',{'selected_buildings':[{'building_id':'b'}]})
   write_json(pilot/'raw/osm_roads.json.gz',{})
   write_json(pilot/'raw/features.json',{})
   binding={'latitude':config['latitude'],'longitude':config['longitude'],'radius_m':2000.0}
   layers={k:{'status':'SUCCEEDED','request_binding':binding,'rows':[]} for k in ['indomaret','competitor']}
   layers['competitor']['rows']=[{'store_id':'SYNTHETIC','store_name':'SYNTHETIC','latitude':config['latitude'],'longitude':config['longitude'],'distance_m':0.0}]
   def generated(*args,**kw):
    result=self.package();result['connectors'][1]['alternative_store_key']=kw['alternative_targets'][0]['store_key'];return result
   with patch('location_intelligent_li3.verify_manifest'),patch('location_intelligent_li3.select_feature_source',return_value=(pilot/'raw/features.json',[])),patch('location_intelligent_li3_graph.build_graph',return_value={'graph':{'coverage':{'bbox':[x-100,y-100,x+100,y+100]}}}),patch('location_intelligent_li3_connectors.generate_connectors',side_effect=generated):
    first=build_alternatives(config,pilot,layers,root/'alternatives.json')
   with patch('location_intelligent_li3.verify_manifest'),patch('location_intelligent_li3_graph.build_graph',side_effect=AssertionError('cached; no rebuild')):
    second=build_alternatives(config,pilot,layers,root/'alternatives.json')
   self.assertEqual(first,second);self.assertEqual(first['by_building']['b'][0]['name'],'SYNTHETIC')
 def test_renderer_rejects_alternatives_from_other_snapshot(self):
  from location_intelligent_map_pilot import interactive_map
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'manifest.json').write_text('{}')
   alt={'status':'SUCCEEDED','identity':{'pilot':'OTHER_SNAPSHOT'}}
   with self.assertRaisesRegex(ValueError,'another calculation snapshot'):
    interactive_map({},p,{},p/'map.html',alternatives=alt)
   alt['identity']={'pilot':hashlib.sha256(b'{}').hexdigest(),'attributes':{},'layer_hashes':{'wrong':'store snapshot'}}
   with self.assertRaisesRegex(ValueError,'Store snapshot changed'):
    interactive_map({},p,{},p/'map.html',alternatives=alt)
 def test_distance_then_road_then_width_unknown_last(self):
  def row(k,d,r,w):return {'store_key':k,'total_distance_m':d,'store_road_rank':r,'frontage_m':w}
  rows=[row('near',1,4,None),row('wide',2,0,8),row('narrow',2,0,4),row('unknown',2,0,None),row('lowerroad',2,3,100)]
  self.assertEqual([r['store_key'] for r in rank_alternatives(rows)],['near','wide','narrow','unknown','lowerroad'])
 def package(self):
  return {'graph':{'nodes':[{'node_id':n} for n in ['A','B','T']],
    'edges':[{'edge_id':'ab','u':'A','v':'B','length_m':1,'highway':'service'}, {'edge_id':'bt','u':'B','v':'T','length_m':1,'highway':'service'}]},
    'edge_rules':{'ab':{'allowed':True},'bt':{'allowed':True}},'blocked_turns':[],
    'connectors':[{'kind':'BUILDING','building_id':'b','connector_id':'bc','node_id':'A','road_edge_id':'ab','geometry':{'coordinates':[[0,0],[0,0]]},'status':'OWNER_ASSUMPTION','barrier_clear':True,'class_rank':3},
     {'kind':'TARGET','alternative_store_key':'s','connector_id':'tc','node_id':'T','road_edge_id':'bt','geometry':{'coordinates':[[2,0],[2,0]]},'status':'OWNER_ASSUMPTION','barrier_clear':True,'class_rank':4}]}
 def test_reachable_turn_block_and_unknown_permission(self):
  p=self.package();stores=[{'store_key':'s','name':'SYNTHETIC','frontage_m':None}]
  self.assertEqual(reachable_alternatives(p,stores,['b'])['b'][0]['total_distance_m'],2)
  p['blocked_turns']=[{'from_edge':'ab','to_edge':'bt'}];self.assertEqual(reachable_alternatives(p,stores,['b'])['b'],[])
  p=self.package();p['edge_rules']['bt']['allowed']=None;self.assertEqual(reachable_alternatives(p,stores,['b'])['b'],[])
  p=self.package();p['connectors'][0].update(node_id='T',road_edge_id='bt');p['connectors'][1].update(node_id='A',road_edge_id='ab')
  self.assertEqual(reachable_alternatives(p,stores,['b'])['b'],[]) # No reverse travel invented on one-way edges.
 def test_multitarget_split_keeps_baseline_input_immutable(self):
  edges=[{'edge_id':'f','u':'u','v':'v','key':'f','highway':'residential','length_m':10,'geometry':{'type':'LineString','coordinates':[[0,0],[10,0]]}},
         {'edge_id':'r','u':'v','v':'u','key':'r','highway':'residential','length_m':10,'geometry':{'type':'LineString','coordinates':[[10,0],[0,0]]}}]
  base={'graph':{'nodes':[{'node_id':'u','x':0,'y':0},{'node_id':'v','x':10,'y':0}],'edges':edges},
    'edge_sources':{k:{'osm_way_id':9,'segment_index':0,'direction':d,'raw_tags':{'highway':'residential'}} for k,d in [('f','f'),('r','r')]},
    'edge_rules':{k:{'allowed':True,'raw_tags':{'highway':'residential'},'evidence_refs':['FIXTURE']} for k in ['f','r']}}
  metrics={'target_xy':[5,1],'all_buildings':[],'selected_buildings':[]};frozen={'policy':get_config()};old=deepcopy(base)
  result=generate_connectors(base,metrics,{'payload':{'elements':[]}},frozen,alternative_targets=[{'store_key':'one','target_xy':[7,1]},{'store_key':'two','target_xy':[9,1]}])
  self.assertEqual(base,old);self.assertEqual(len(result['connectors']),3)
  self.assertEqual({c['alternative_store_key'] for c in result['connectors'] if 'alternative_store_key' in c},{'one','two'})
if __name__=='__main__':unittest.main()
