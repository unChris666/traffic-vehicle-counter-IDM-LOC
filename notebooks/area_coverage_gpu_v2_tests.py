"""CPU oracles for GPU V2 control/math; actual CUDA remains a separate gate."""
import unittest,random,math,tempfile
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
from collections import defaultdict
from shapely.geometry import Point,LineString,Polygon
from location_intelligent_gpu_geometry import GpuGeometry
from location_intelligent_gpu_weighted import WeightedLookup
from location_intelligent_motor_routing import _path_index

class GeometryOracle(GpuGeometry):
 def __init__(self,device=0):
  self.polygon_cache={};self.audit={'backend':'CPU_ORACLE_TEST_ONLY','actual_cuda_executed':False,'gpu_distance_pairs':0,'gpu_polygon_queries':0,'cpu_fallback_queries':0,'fallback_reasons':{},'canonical_scalar_distances':0}
 def distances(self,points,segments,pairs,limits=None):
  out=[]
  for i,(p,s) in enumerate(pairs):
   d=Point(*points[p]).distance(LineString([segments[s][:2],segments[s][2:]]));out.append(d if limits is None or d<=limits[i] else math.inf)
  return out
 def polygon_lengths(self,queries):return [(line.intersection(poly).length,False,0.0) for line,poly in queries]
 def primitive_intersections(self,queries):return [(line.intersects(shape),False) for line,shape in queries]

class WeightedOracle:
 def __init__(self,graph,allowed,blocked,device=0):
  self.graph=graph;self.allowed=allowed;self.blocked=blocked;self.labels={}
  self.keys=sorted(e['edge_id'] for e in graph['edges'] if allowed.get(e['edge_id']) is True)
  byid={e['edge_id']:e for e in graph['edges']};self.edges=[byid[k] for k in self.keys]
  self.audit={'backend':'CPU_ORACLE_TEST_ONLY','actual_cuda_executed':False,'gpu_weighted_queries':0,'cpu_fallback_queries':0,'fallback_reasons':{}}
 def compute(self,targets):
  outgoing=defaultdict(list)
  for i,e in enumerate(self.edges):outgoing[e['u']].append(i)
  n=len(self.edges)
  for target in sorted(set(targets)):
   d=[math.inf]*n;h=[2147483647]*n;nxt=[-1]*n
   for iteration in range(n+1):
    nd=[];nh=[];nn=[];amb=[]
    for i,e in enumerate(self.edges):
     opts=[(e['length_m'],1,-1)] if e['v']==target else []
     opts += [(e['length_m']+d[j],h[j]+1,j) for j in outgoing[e['v']] if math.isfinite(d[j]) and (e['edge_id'],self.keys[j]) not in self.blocked]
     best=min(opts) if opts else (math.inf,2147483647,-1);nd.append(best[0]);nh.append(best[1]);nn.append(best[2])
     tol=256*math.ulp(1.0)*max(1.,abs(best[0]))*max(1,best[1]) if math.isfinite(best[0]) else 0
     amb.append(any(v[2]!=best[2] and v[0]!=best[0] and abs(v[0]-best[0])<=tol for v in opts))
    stable=(nd,nh,nn)==(d,h,nxt);d,h,nxt=nd,nh,nn
    if stable:break
   self.labels[target]={'keys':self.keys,'distance':[v if math.isfinite(v) else None for v in d],'hops':h,'next':nxt,'ambiguous':amb}
  return self.labels
 def lookup(self,target):return WeightedLookup(self.graph,self.allowed,self.blocked,target,self.labels[target],self.audit)
 def export_labels(self):return self.labels

class WeightedTests(unittest.TestCase):
 def test_gpu_recurrence_and_host_paths_against_canonical_random_graphs(self):
  rng=random.Random(881)
  for trial in range(35):
   edges=[]
   for i in range(7):
    for j in range(7):
     if i!=j and rng.random()<.24:edges.append({'edge_id':f'{i}-{j}','u':str(i),'v':str(j),'length_m':rng.choice([.1,.2,1.,2.,5.])})
   graph={'nodes':[{'node_id':str(i)} for i in range(7)],'edges':edges};allowed={e['edge_id']:rng.choice([True,True,False,None]) for e in edges}
   blocked={(e['edge_id'],f['edge_id']) for e in edges for f in edges if e['v']==f['u'] and rng.random()<.1}
   router=WeightedOracle(graph,allowed,blocked);router.compute(map(str,range(7)))
   for target in map(str,range(7)):
    actual=router.lookup(target);expected=_path_index(graph,allowed,blocked,target)
    for start in map(str,range(7)):self.assertEqual(actual(start),expected(start))
 def test_tie_fallback_audited_unique_path_stays_on_weighted_labels(self):
  graph={'nodes':[{'node_id':n} for n in 'abcd'],'edges':[
   {'edge_id':'ab','u':'a','v':'b','length_m':1.},{'edge_id':'ac','u':'a','v':'c','length_m':1.},
   {'edge_id':'bd','u':'b','v':'d','length_m':1.},{'edge_id':'cd','u':'c','v':'d','length_m':1.}]}
  allowed={e['edge_id']:True for e in graph['edges']};router=WeightedOracle(graph,allowed,set());router.compute(['d']);lookup=router.lookup('d')
  self.assertEqual(lookup('a'),_path_index(graph,allowed,set(),'d')('a'));self.assertEqual(router.audit['cpu_fallback_queries'],0)
  graph['edges'][1]['length_m']+=1e-15
  router=WeightedOracle(graph,allowed,set());router.compute(['d']);router.lookup('d')('a')
  self.assertEqual(router.audit['cpu_fallback_queries'],1)
  router.lookup('d')('b');self.assertGreater(router.audit['gpu_weighted_queries'],0)

class GeometryControlTests(unittest.TestCase):
 def test_ring_orientation_and_hole_preserved(self):
  geom=GeometryOracle();poly=Polygon([(0,0),(10,0),(10,10),(0,10)],holes=[[(3,3),(7,3),(7,7),(3,7)]])
  edges=geom.polygon_edges(poly);self.assertEqual(len(edges),8)
  line=LineString([(-1,5),(11,5)]);integral=0;winding=0
  px,py=line.coords[0];qx,qy=line.coords[1];dx,dy=qx-px,qy-py
  for ax,ay,bx,by in edges:
   ax-=px;ay-=py;bx-=px;by-=py;ex,ey=bx-ax,by-ay;cross=ex*(-ay)-ey*(-ax)
   if ay<=0<by and cross>0:winding+=1
   if by<=0<ay and cross<0:winding-=1
   den=dx*ey-dy*ex
   if den:
    t=(ax*ey-ay*ex)/den;u=(ax*dy-ay*dx)/den
    if 0<t<1 and 0<u<1:integral+=(1 if den<0 else -1)*(1-t)
  self.assertAlmostEqual((integral+winding)*line.length,line.intersection(poly).length)
 def test_batched_connector_control_matches_cpu_with_holes_and_obstructions(self):
  import li3_integration_tests as fixtures
  from location_intelligent_li3_connectors import generate_connectors
  from location_intelligent_gpu_connectors import generate_connectors_gpu
  f=fixtures.ConnectorTests();f.setUp();f.f['policy']['connectors']['building_entrance_profile']='SINGLE_NEAREST_VALID_V1'
  before=deepcopy((f.base,f.metrics,f.features,f.f));expected=generate_connectors(f.base,f.metrics,f.features,f.f)
  with patch('location_intelligent_gpu_geometry.GpuGeometry',GeometryOracle):actual=generate_connectors_gpu(f.base,f.metrics,f.features,f.f)
  for field in ['graph','connectors','edge_sources','edge_rules','blocked_turns']:self.assertEqual(actual[field],expected[field])
  self.assertEqual(before,(f.base,f.metrics,f.features,f.f))


class EquivalenceGateTests(unittest.TestCase):
 def test_mismatched_market_blocks_equivalence(self):
  from location_intelligent_gpu_validation import validate_market
  fields=['rows','summary','stores','excluded_stores','attractor_gate','market_inputs_complete','competitor_groups','routing_clusters']
  expected={name:[] for name in fields};actual=deepcopy(expected);actual['rows']=[{'different':True}]
  with tempfile.TemporaryDirectory() as d,patch('location_intelligent_market_runtime.build_market',return_value=expected):
   path=Path(d)/'equivalence.json'
   with self.assertRaisesRegex(RuntimeError,'EQUIVALENCE_FAILED'):validate_market({}, {},Path(d),{}, {},actual,Path(d)/'market',path)
   import json
   self.assertEqual(json.loads(path.read_text())['market']['status'],'FAIL')
 def test_multiple_target_geometry_not_collapsed_to_candidate(self):
  import area_coverage_market_routing_tests as fixtures
  from location_intelligent_li3_connectors import generate_connectors
  from location_intelligent_gpu_connectors import generate_connectors_gpu
  f=fixtures.MarketRoutingTests();case,base,metrics,targets=f.setup_case(profile='SINGLE_NEAREST_VALID_V1')
  expected=generate_connectors(base,metrics,case.features,case.f,alternative_targets=targets)
  with patch('location_intelligent_gpu_geometry.GpuGeometry',GeometryOracle):actual=generate_connectors_gpu(base,metrics,case.features,case.f,alternative_targets=targets)
  self.assertEqual(actual['graph'],expected['graph']);self.assertEqual(actual['connectors'],expected['connectors'])

if __name__=='__main__':unittest.main()
