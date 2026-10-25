"""GPU adapter logic via explicit CPU oracle; does not claim CUDA execution."""
import unittest,tempfile,random,json,sys
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from importlib.util import find_spec
from location_intelligent_gpu import StateTopology,cpu_reachability_oracle,prepare_scope,verify_scope_binding
from location_intelligent_gpu_worker import scoped_routing

class OracleEngine:
    def __init__(self,*args):self.stats={'actual_cuda_executed':False,'test_oracle':True}
    def reach(self,topology,seeds,reverse=False,sample_states=None):
        rows=[cpu_reachability_oracle(topology,s,reverse) for s in seeds]
        return [[row[i] for i in sample_states] for row in rows] if sample_states is not None else rows
    def close(self):pass

class TopologyTests(unittest.TestCase):
 def test_unknown_direction_and_turn_reachability_matches_canonical(self):
  from location_intelligent_motor_routing import _path_index,_potential_reachability
  rng=random.Random(72)
  for trial in range(30):
   nodes=[{'node_id':str(i)} for i in range(9)];edges=[];rules={}
   for i in range(9):
    for j in range(9):
     if i!=j and rng.random()<.2:
      key=f'{i}-{j}';edges.append({'edge_id':key,'u':str(i),'v':str(j),'length_m':rng.choice([.1,1.,2.])});rules[key]={'allowed':rng.choice([True,True,False,None])}
   turns=[{'from_edge':a['edge_id'],'to_edge':b['edge_id']} for a in edges for b in edges if a['v']==b['u'] and rng.random()<.12]
   graph={'nodes':nodes,'edges':edges};allowed={k:r['allowed'] for k,r in rules.items()};blocked={(r['from_edge'],r['to_edge']) for r in turns}
   package={'graph':graph,'edge_rules':rules,'blocked_turns':turns,'connectors':[
    {'kind':'BUILDING','node_id':'0'},{'kind':'BUILDING','node_id':'1'}]+[{'kind':'TARGET','node_id':str(i),'alternative_store_key':str(i)} for i in range(9)]}
   scope=prepare_scope(package,OracleEngine())
   strict=StateTopology(graph,allowed,blocked)
   for target in map(str,range(9)):
    for origin in ['0','1']:
     expected=_path_index(graph,allowed,blocked,target)(origin)
     self.assertEqual(origin in scope['reachable_nodes'][target],expected is not None)
   import location_intelligent_motor_routing as module
   before=module._path_index
   with scoped_routing(scope):
    for target in map(str,range(9)):
     lookup=module._path_index(graph,allowed,blocked,target)
     for origin in ['0','1']:
      self.assertEqual(lookup(origin),before(graph,allowed,blocked,target)(origin))
      self.assertEqual(module._potential_reachability(graph,allowed,blocked,target)(origin),_potential_reachability(graph,allowed,blocked,target)(origin))
   self.assertIs(module._path_index,before)
 def test_stale_scope_rejected_and_no_cupy_import_on_worker(self):
  from location_intelligent_validator import canonical_hash
  graph={'nodes':[],'edges':[]};evidence={}
  scope={'schema':'gpu_routing_scope_v1','profile':'GPU_REACHABILITY_CANONICAL_CPU_V1','edge_ids':[],
   'graph_hash':canonical_hash(graph),'evidence_hash':canonical_hash(evidence),'origin_nodes':[],'reachable_nodes':{}}
  verify_scope_binding(scope,graph,evidence)
  with self.assertRaisesRegex(ValueError,'MISMATCH'):verify_scope_binding(scope,{'nodes':[{}],'edges':[]},evidence)

@unittest.skipUnless(find_spec('shapely'),'Geometry worker required')
class MarketAdapterTests(unittest.TestCase):
 def test_market_matrix_gate_and_restore_match_canonical(self):
  import area_coverage_market_routing_tests as tests
  from location_intelligent_market_runtime import _MarketRoutes,_market_store_routes,_poi_gate
  from location_intelligent_gpu_runtime import weighted_market_routes_class
  from location_intelligent_market_config import get_market_config
  f=tests.MarketRoutingTests()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);_,package=f.packages(root)
   before=deepcopy(package);cpu=_MarketRoutes(package)
   from area_coverage_gpu_v2_tests import WeightedOracle
   cls=weighted_market_routes_class(router_factory=WeightedOracle);gpu=cls(package)
   stores=[{'store_key':key} for key in ['candidate','a','b','end']]
   self.assertEqual(_market_store_routes(package,stores,['b0','b1'],cpu,{}),_market_store_routes(package,stores,['b0','b1'],gpu,{}))
   policy=get_market_config()['allocation_requirements'];pois=[{'source_id':'a','store_key':'a','category':'hospital'}]
   args=({'metric_crs':'EPSG:32748'},policy,{'status':'SUCCEEDED'},package,pois,{'features':[]})
   self.assertEqual(_poi_gate(*args,network=cpu),_poi_gate(*args,network=gpu));self.assertEqual(package,before)
   self.assertFalse(gpu.router.audit['actual_cuda_executed'])
 def test_missing_gpu_never_calls_cpu_fallback(self):
  from location_intelligent_gpu import CupyReachability
  with patch.dict(sys.modules,{'cupy':None}):
   with self.assertRaises(ModuleNotFoundError):CupyReachability()


class GpuNotebookTests(unittest.TestCase):
 def notebooks(self):
  root=Path(__file__).parent
  return json.loads((root/'area_coverage_market_cpu_2km.ipynb').read_text()),json.loads((root/'area_coverage_market_gpu_2km.ipynb').read_text())
 def test_visible_helpers_ast_baseline_and_policy_unchanged(self):
  import ast,hashlib
  cpu,gpu=self.notebooks()
  def bodies(n):return {''.join(c['source']).split('\n',1)[0].rsplit('/',1)[1]:''.join(c['source']).split('\n',1)[1] for c in n['cells'] if ''.join(c['source']).startswith('%%writefile ')}
  a,b=bodies(cpu),bodies(gpu)
  for name,source in a.items():self.assertEqual(source,b[name],name)
  self.assertIn('location_intelligent_gpu.py',b)
  configuration=next(''.join(c['source']) for c in gpu['cells'] if "begin_notebook_stage('configuration'" in ''.join(c['source']))
  for name,source in b.items():self.assertIn(repr(name)+': '+repr(hashlib.sha256(source.encode()).hexdigest()),configuration)
  def configs(n):
   code=next(''.join(c['source']) for c in n['cells'] if "begin_notebook_stage('configuration'" in ''.join(c['source']))
   return {node.targets[0].id:ast.dump(node.value) for node in ast.walk(ast.parse(code)) if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ['CONFIG','MARKET_CONFIG','SOURCE_REVISION','SOURCE_MODE','BQ_MODE']}
  old,new=configs(cpu),configs(gpu)
  self.assertEqual(old['MARKET_CONFIG'],new['MARKET_CONFIG']);self.assertEqual(old['BQ_MODE'],new['BQ_MODE'])
  self.assertNotEqual(old['SOURCE_MODE'],new['SOURCE_MODE'])
  self.assertIn('FROZEN_GCS_PBF',new['SOURCE_MODE'])
  # Only the core runtime locator changes inside CONFIG; domain fields stay exact.
  def config_fields(n):
   code=next(''.join(c['source']) for c in n['cells'] if "begin_notebook_stage('configuration'" in ''.join(c['source']))
   node=next(x for x in ast.walk(ast.parse(code)) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONFIG' for t in x.targets))
   return {ast.literal_eval(k):ast.dump(v) for k,v in zip(node.value.keys,node.value.values)}
  a,b=config_fields(cpu),config_fields(gpu)
  transport={'core_python','poi_overpass_endpoints'}
  self.assertEqual({k:v for k,v in a.items() if k not in transport},{k:v for k,v in b.items() if k not in transport})
  self.assertEqual(b['core_python'],"Name(id='CORE_PYTHON', ctx=Load())")
  self.assertEqual(b['poi_overpass_endpoints'],'List(elts=[], ctx=Load())')
  for c in gpu['cells']:
   if c['cell_type']=='code':
    code=''.join(c['source']);ast.parse(code.split('\n',1)[1] if code.startswith('%%writefile ') else code)
    self.assertIsNone(c['execution_count']);self.assertEqual(c['outputs'],[])
 def test_failed_output_cannot_authorize_traffic_and_cleans_up(self):
  _,gpu=self.notebooks();code=''.join(gpu['cells'][-1]['source'])
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);env={'Path':Path,'json':json,'NOTEBOOK_REPORT_PATH':root/'readiness.json','STAGES':{'output':{'status':'FAILED'}},'GPU_DEVICE':0}
   with patch('location_intelligent_gpu.release_gpu',return_value={'status':'RELEASED'}) as release:exec(code,env)
   saved=json.loads((root/'engine_handoff.json').read_text())
   self.assertEqual(saved['status'],'NOT_READY');self.assertFalse(saved['traffic_started']);release.assert_called_once()

if __name__=='__main__':unittest.main()
