"""Run under each recorded geometry runtime; unavailable backend tests skip."""
import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from traffic_location.artifacts import read,sha,semantic_hash,write
from traffic_location.location.engine import run_selection,run_recount
from traffic_location.location.snapshot import SnapshotAdapter
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/location_intelligent'
SOURCE=BASE/'li4_n1_20261023_v1'

class SnapshotTests(unittest.TestCase):
 def test_reconciles_all_source_rows(self):
  a=SnapshotAdapter(SOURCE,sha(SOURCE/'manifest.json'));self.assertEqual(len(a.rows),2623)
 def test_wrong_manifest_binding_rejected(self):
  with self.assertRaises(ValueError):SnapshotAdapter(SOURCE,'0'*64)
 def test_not_another_packet_type(self):
  p=BASE/'li5_n1_20261023_r2'
  with self.assertRaises(ValueError):SnapshotAdapter(p,sha(p/'manifest.json'))

@unittest.skipUnless(importlib.util.find_spec('osgeo'),'Run GDAL runtime separately')
class SelectionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.request={'schema_version':'location_selection_request_v1','snapshot':str(SOURCE.relative_to(ROOT)),'manifest_sha256':sha(SOURCE/'manifest.json')}
 def test_actual_snapshot_selection_capacity_exact(self):
  value=run_selection(self.request,root=ROOT)
  self.assertEqual(value['result_quality'],'PARTIAL');self.assertEqual(value['source_analysis_status'],'PARTIAL')
  self.assertEqual(value['selection'],read(SOURCE/'snapshot/building_results/selection.json'))
  self.assertEqual(value['capacity'],read(SOURCE/'snapshot/building_results/capacity.json'))
 def test_three_replays_and_no_input_mutation(self):
  request=copy.deepcopy(self.request);a=run_selection(request,root=ROOT)
  for _ in range(2):self.assertEqual(run_selection(request,root=ROOT),a)
  self.assertEqual(request,self.request)
 def test_blocked_source_not_false_zero(self):
  from traffic_location.location.selection import select_buildings
  a=SnapshotAdapter(SOURCE,sha(SOURCE/'manifest.json'));m=copy.deepcopy(a.source_manifest);m['sources'][0]['availability']='UNAVAILABLE'
  r=select_buildings(a.context,m,root=SOURCE/'snapshot',source_ref_id=a.source_id())
  self.assertEqual(r['status'],'BLOCKED');self.assertIsNone(r['summary'])

@unittest.skipUnless(importlib.util.find_spec('shapely'),'Run Shapely runtime separately')
class RecountTests(unittest.TestCase):
 def request(self,rev):
  p=BASE/('li5_n1_20261023_'+rev)
  return {'schema_version':'location_recount_request_v1','packet':str(p.relative_to(ROOT)),'manifest_sha256':sha(p/'manifest.json')}
 def test_actual_membership_domain_equality_and_explicit_new_code_version(self):
  for rev in ['r1','r2']:
   value=run_recount(self.request(rev),root=ROOT);old=read(BASE/('li5_n1_20261023_'+rev)/'result.json')
   allowed={'engine_sha256','result_version'}
   self.assertEqual({k:v for k,v in value['result'].items() if k not in allowed},{k:v for k,v in old.items() if k not in allowed})
   self.assertEqual(value['membership'],read(BASE/('li5_n1_20261023_'+rev)/'membership.json'))
   self.assertNotEqual(value['result']['result_version'],old['result_version'])
 def test_three_replays_and_order_isolation(self):
  a=run_recount(self.request('r1'),root=ROOT);b=run_recount(self.request('r2'),root=ROOT)
  for rev,expected in [('r2',b),('r1',a),('r2',b),('r1',a)]:self.assertEqual(run_recount(self.request(rev),root=ROOT),expected)
 def test_delta_only_from_same_new_engine(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r1.json';first=run_recount(self.request('r1'),root=ROOT);write(p,first)
   r=self.request('r2');r['previous']={'path':str(p),'sha256':sha(p)}
   result=run_recount(r,root=ROOT);old=read(BASE/'li5_n1_20261023_r2/delta.json')
   self.assertEqual(result['delta']['union'],old['union']);self.assertEqual(result['delta']['polygons'],old['polygons'])
 def test_old_engine_previous_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'old.json';write(p,{'result':read(BASE/'li5_n1_20261023_r1/result.json')})
   r=self.request('r2');r['previous']={'path':str(p),'sha256':sha(p)}
   with self.assertRaises(ValueError):run_recount(r,root=ROOT)
 def test_unknown_stays_unknown_and_units_separate(self):
  value=run_recount(self.request('r2'),root=ROOT)
  self.assertTrue(any(r['decision_state']=='ACCESS_UNVERIFIED' for r in value['membership']))
  self.assertIsNone(value['result']['mixed_unit_total']);self.assertIsNone(value['result']['final_business_capacity'])

if __name__=='__main__':unittest.main()
