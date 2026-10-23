"""Source adapters reject fabricated links; rendering cannot change decisions."""
import copy,gzip,json,tempfile,unittest
from pathlib import Path
from traffic_location.artifacts import read,sha,semantic_hash
from traffic_location.traffic.measurements import read_measurements
from traffic_location.traffic.pipeline import run
from traffic_location.traffic._kernel.support import records
ROOT=Path(__file__).resolve().parents[1]
REQUEST=ROOT/'results/engine_modularization/20261023/requests/machine.json'

class MeasurementTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.request=read(REQUEST);p=Path(cls.request['artifacts']['measurements']['path'])
  if not p.exists():raise unittest.SkipTest('Download the exact measurement cache first; see results README')
  cls.rows=[]
  for row in records(p):
   cls.rows.append(row)
   if len(cls.rows)==32:break
 def execute(self,rows,fn):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'records.jsonl.gz'
   with gzip.open(p,'wt') as f:
    for row in rows:f.write(json.dumps(row)+'\n')
   return fn(p)
 def adapt(self,rows):
  return self.execute(rows,lambda p:list(read_measurements(p,self.request['source_identity'],32)))
 def test_actual_native_measurement_adapter(self):
  out=self.adapt(self.rows);self.assertEqual(len(out),32)
 def test_missing_source_frame_rejected(self):
  with self.assertRaises(ValueError):self.adapt(self.rows[:10]+self.rows[11:])
 def test_wrong_source_video_rejected(self):
  rows=copy.deepcopy(self.rows);rows[0]['video_sha256']='0'*64
  with self.assertRaises(ValueError):self.adapt(rows)
 def test_measured_bbox_cannot_be_replaced(self):
  rows=copy.deepcopy(self.rows);row=next(r for r in rows if r['emitted_tracks']);row['emitted_tracks'][0]['raw_bbox'][0]+=1
  with self.assertRaises(ValueError):self.adapt(rows)
 def test_new_video_job_has_no_hardcoded_pilot_id_or_length(self):
  def execute(path):
   request=copy.deepcopy(self.request);request.update(video_id='technical_prefix32',frame_count=32)
   for key in ['historical_baseline','baseline_reviews','relationships']:request['artifacts'].pop(key,None)
   request['artifacts']['measurements']={'path':str(path),'sha256':sha(path)};request['source_identity']['records_sha256']=sha(path)
   result=run(request,root=ROOT)
   self.assertEqual(result['native']['report']['frame_count'],32);self.assertEqual(result['native']['video_id'],'technical_prefix32')
  self.execute(self.rows,execute)

class RenderingTests(unittest.TestCase):
 def test_actual_frame_matches_original_renderer_and_preserves_events(self):
  import sys
  try:import cv2,numpy as np
  except ImportError:raise unittest.SkipTest('Run recorded Traffic CPU runtime for pixel test')
  sys.path.insert(0,str(ROOT/'notebooks'))
  import phase_8_b_v6_annotation as old
  from traffic_location.traffic import render
  q=read(REQUEST);video=ROOT.parent/'scratch/modularization/assets/TGDI-WEEKDAY-SIANG.mp4'
  if not video.exists():raise unittest.SkipTest('Actual source video not downloaded')
  native=read(ROOT/'results/b_v8/execution/pilot_p1_reviewed_v3/weekday_siang/counting_result.json.gz')
  geometry=read(q['artifacts']['geometry']['path']);record=None
  for row in records(q['artifacts']['measurements']['path']):
   if row['frame_index']==1089:record=row;break
  # This codec can return different pixels after random seeking. Preserve the
  # sequential decoder history used by the measurement producer.
  cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS)
  for _ in range(1090):ok,image=cap.read()
  cap.release();self.assertTrue(ok)
  import hashlib
  self.assertEqual(hashlib.sha256(image.tobytes()).hexdigest(),record['detector_input_frame_pixel_sha256'])
  before=semantic_hash(native)
  canvas,state=render.frame(image,record,native,geometry,fps=fps,video_id='weekday_siang')
  original,expected=old.render_b_v6_frame(image,record,native,geometry,fps=fps,video_id='weekday_siang',
   unit_assignments=native['frame_assignments'],component_relations=native['component_links'])
  self.assertTrue(np.array_equal(canvas,original));self.assertEqual(state,expected);self.assertEqual(semantic_hash(native),before)

if __name__=='__main__':unittest.main()
