import copy,tempfile,unittest
from pathlib import Path
from traffic_location.artifacts import read,write,semantic_hash
from traffic_location.traffic.fresh_bridge import frames
from traffic_location.traffic.batch import aggregate
ROOT=Path(__file__).resolve().parents[1]
class FreshTests(unittest.TestCase):
 def setUp(self):
  self.v=read(ROOT/'results/engine_modularization/20261023/verification/fresh_cpu_measurements.json.gz')
  # Actual retained CPU observations; only attach explicit COCO metadata for these tests.
  self.v['class_names']={0:'person',1:'bicycle',2:'car',3:'motorcycle',5:'bus',7:'truck',9:'traffic light',11:'stop sign'}
  self.s={'video_sha256':self.v['source_sha256'],'width':640,'height':480,'records_sha256':'a'*64}
 def adapt(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.json';write(p,self.v);return list(frames(p,self.s,32))
 def test_actual_measurements_preserve_raw_bc_source(self):
  rows=self.adapt();self.assertEqual(len(rows),32)
  for row in rows:
   for o in row['observations']:
    self.assertEqual(o['measurement_provenance'],'fresh_modular_detection_v1')
    self.assertEqual(o['raw_bbox'],self.v['records'][row['frame_index']]['detections'][o['original_detection_index']]['bbox'])
 def test_altered_raw_link_rejected(self):
  row=next(r for r in self.v['records'] if r['emitted_measurements']);row['emitted_measurements'][0]['observed']=False
  self.v['records_semantic_sha256']=semantic_hash(self.v['records'])
  with self.assertRaises(ValueError):self.adapt()
 def test_source_mismatch_rejected(self):
  self.s['video_sha256']='f'*64
  with self.assertRaises(ValueError):self.adapt()
 def test_integrity_failure_rejected(self):
  self.v['records'][0]['frame_index']=1
  with self.assertRaises(ValueError):self.adapt()
class BatchTests(unittest.TestCase):
 def setUp(self):
  self.expected={str(i):f'{i:064x}' for i in range(8)};self.rows=[]
  for i in range(8):
   measured=i%2==0;e={'event_id':'e','category':'car','direction':'A_TO_B','evidence':{'measured_crossing':measured},'accepted_count_event':True,'status':'accepted'}
   native={'events':[e],'source_identity':{'video_sha256':self.expected[str(i)]},'decisions':[],'invalid_decisions':[],
    'aggregate':{'total':1,'measured_total':int(measured),'inferred_total':int(not measured),'pending':0,'invalid':0,'by_category':{'car':1},'by_direction':{'A_TO_B':1}}}
   self.rows.append({'status':'SUCCEEDED','video_id':str(i),'branch':'machine','scope':'FULL_VIDEO','experiment_sha256':'x','result_version':'v','native':native})
 def call(self):return aggregate(self.expected,self.rows,experiment_sha256='x')
 def test_eight_pivot_reconciles(self):
  r=self.call();self.assertEqual(r['complete_vehicle_total'],8);self.assertEqual(r['pivot']['car']['A_TO_B'],{'measured':4,'estimated':4})
 def test_missing_is_partial_not_zero(self):
  self.rows.pop();r=self.call();self.assertIsNone(r['complete_vehicle_total']);self.assertEqual(r['observed_vehicle_subtotal'],7)
 def test_duplicate_rerun_rejected(self):
  self.rows.append(self.rows[0])
  with self.assertRaises(ValueError):self.call()
 def test_smoke_cannot_be_counted(self):
  self.rows[0]['scope']='SMOKE'
  with self.assertRaises(ValueError):self.call()
 def test_policy_mix_rejected(self):
  self.rows[0]['experiment_sha256']='different'
  with self.assertRaises(ValueError):self.call()
 def test_reviewed_not_added(self):
  self.rows[0]['branch']='review_assisted'
  with self.assertRaises(ValueError):self.call()
 def test_pending_invalid_do_not_enter_accepted(self):
  for row in self.rows:
   row['native']['decisions']=[{'status':'pending'}];row['native']['invalid_decisions']=[{'status':'invalid'}]
   row['native']['aggregate'].update(pending=1,invalid=1)
  result=self.call();self.assertEqual(result['complete_vehicle_total'],8);self.assertEqual(result['pending'],8);self.assertEqual(result['invalid'],8)
 def test_pedestrian_separate_from_vehicle(self):
  n=self.rows[0]['native'];n['events'][0]['category']='pedestrian';n['aggregate']['by_category']={'pedestrian':1}
  result=self.call();self.assertEqual(result['complete_vehicle_total'],7);self.assertEqual(result['pedestrian_total'],1)
 def test_stable_repeated_and_order_independent(self):
  r=self.call();self.rows.reverse();self.assertEqual(self.call(),r);self.assertEqual(self.call(),r)
if __name__=='__main__':unittest.main()
