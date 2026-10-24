import unittest
from pathlib import Path
from traffic_location.artifacts import read,semantic_hash
from traffic_location.traffic.annotation import plan,snapshot
ROOT=Path(__file__).resolve().parents[1]
class AnnotationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.native=read(ROOT/'results/b_v8/execution/pilot_p1_reviewed_v3/weekday_siang/counting_result.json.gz')
 def test_final_pivot_matches_saved_events(self):
  n=self.native;s=snapshot(plan(n),n['report']['frame_count']-1)
  self.assertEqual(s['accepted'],n['aggregate']['total']);self.assertEqual(s['vehicles'],n['aggregate']['vehicle_total']);self.assertEqual(s['measured'],n['aggregate']['measured_total']);self.assertEqual(s['estimated'],n['aggregate']['inferred_total'])
 def test_planning_does_not_modify_decisions(self):
  before=semantic_hash(self.native);snapshot(plan(self.native),2000);self.assertEqual(before,semantic_hash(self.native))
 def test_future_events_not_activated_early(self):
  p=plan(self.native);first=p['events'][0][0]
  if first>0:self.assertEqual(snapshot(p,first-1)['accepted'],0)
  self.assertGreaterEqual(snapshot(p,first)['accepted'],1)
 def test_role_links_exact_frame_only(self):
  n=self.native;p=plan(n)
  for r in n['component_links']:
   for frame in r['support_frames']:
    parents={v['vehicle_track_id'] for v in n['component_links'] if v['component_track_id']==r['component_track_id'] and frame in v['support_frames']}
    if len(parents)==1:self.assertEqual(p['links'][frame][r['component_track_id']],r['vehicle_track_id'])
    else:self.assertNotIn(r['component_track_id'],p['links'][frame])
if __name__=='__main__':unittest.main()
