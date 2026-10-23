"""Scoped boundary/behavior tests, independent from any fresh model execution."""
import ast,copy,gzip,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from traffic_location.artifacts import read,write,sha,semantic_hash
from traffic_location.traffic.contracts import validate_request
from traffic_location.traffic.pipeline import run
from traffic_location.traffic import render
from traffic_location.traffic._kernel import publication
from traffic_location.traffic._kernel.geometry import Geometry
from traffic_location.persistence import publish,reopen_traffic
ROOT=Path(__file__).resolve().parents[1]
CASE=ROOT/'results/b_v8/verification/actual_fixture_probes_v2'
REQUEST=ROOT/'results/engine_modularization/20261023/requests/machine.json'

class ProfileTests(unittest.TestCase):
 def setUp(self):self.r=read(REQUEST)
 def test_machine_valid(self):self.assertEqual(validate_request(self.r)[1],'machine')
 def test_new_review_overlay_forbidden_on_machine(self):
  self.r['artifacts']['review_overlay']=self.r['artifacts']['baseline_reviews']
  with self.assertRaises(ValueError):validate_request(self.r)
 def test_machine_adjudications_forbidden(self):
  self.r['artifacts']['adjudications']=self.r['artifacts']['baseline_reviews']
  with self.assertRaises(ValueError):validate_request(self.r)
 def test_review_branch_requires_all_proofs(self):
  self.r['profile']='review_assisted'
  with self.assertRaises(ValueError):validate_request(self.r)
 def test_replay_must_name_branch(self):
  self.r['profile']='replay'
  with self.assertRaises(ValueError):validate_request(self.r)
 def test_replay_explicit_branch(self):
  self.r.update(profile='replay',replay_branch='machine');self.assertEqual(validate_request(self.r)[1],'machine')
 def test_foreign_source_hash_rejected(self):
  self.r['source_identity']['records_sha256']='a'*64
  with self.assertRaises(ValueError):validate_request(self.r)
 def test_arbitrary_video_id_not_pilot_constant(self):
  self.r['video_id']='another_store_clip';self.assertEqual(validate_request(self.r)[0]['video_id'],'another_store_clip')
 def test_actual_frame_count_parameter(self):
  self.r['frame_count']=17;self.assertEqual(validate_request(self.r)[0]['frame_count'],17)
 def test_bool_frame_count_rejected(self):
  self.r['frame_count']=True
  with self.assertRaises(ValueError):validate_request(self.r)
 def test_unknown_fields_rejected(self):
  self.r['magic_override']=True
  with self.assertRaises(ValueError):validate_request(self.r)
 def test_historical_context_needs_bound_baseline(self):
  del self.r['artifacts']['historical_baseline']
  with self.assertRaises(ValueError):validate_request(self.r)

class CountingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.geometry=Geometry.from_draft(ROOT/'results/b_v8/fixtures/blocker4843/geometry.json',640,480)
  cls.cases={}
  for name in ['blocker4843','pedestrian54']:
   old=read(CASE/name/'reviewed_result.json.gz');frames=read(CASE/name/'reviewed_resolved_frames.json.gz')
   cls.cases[name]=(frames,old['source_identity'],old['report']['policy'])
 def count(self,name):
  f,s,p=self.cases[name];return publication.replay_frames(f,self.geometry,source_identity=s,policy=p)
 def test_original_kernel_parity(self):
  sys.path.insert(0,str(ROOT/'notebooks'))
  import phase_8_b_v7_counting as old
  from phase_5_geometry_helpers import Geometry as OriginalGeometry
  original_geometry=OriginalGeometry.from_draft(ROOT/'results/b_v8/fixtures/blocker4843/geometry.json',640,480)
  for name,(f,s,p) in self.cases.items():
   with self.subTest(name=name):self.assertEqual(self.count(name),old.replay_frames(f,original_geometry,source_identity=s,policy=p))
 def test_three_independent_counts(self):
  first=self.count('blocker4843')
  for _ in range(2):self.assertEqual(self.count('blocker4843'),first)
 def test_job_order_does_not_leak_state(self):
  a=self.count('blocker4843');b=self.count('pedestrian54')
  self.assertEqual(self.count('pedestrian54'),b);self.assertEqual(self.count('blocker4843'),a)
 def test_frames_not_mutated(self):
  before=copy.deepcopy(self.cases);self.count('blocker4843');self.assertEqual(before,self.cases)
 def test_inferred_never_promoted(self):
  self.assertFalse(self.count('blocker4843')['events'][0]['evidence']['measured_crossing'])
 def test_positive_pedestrian_measured(self):
  self.assertTrue(self.count('pedestrian54')['events'][0]['evidence']['measured_crossing'])
 def test_raw_bc_unchanged(self):
  for event in self.count('blocker4843')['events']:
   for ref in event['evidence']['source_refs']:
    box=ref['raw_bbox'];self.assertEqual(ref['point'],[(box[0]+box[2])/2,box[3]])
 def test_bad_prediction_input_rejected(self):
  f,s,p=copy.deepcopy(self.cases['pedestrian54']);next(v for v in f if v['observations'])['observations'][0]['observed']=False
  with self.assertRaises(ValueError):publication.replay_frames(f,self.geometry,source_identity=s,policy=p)

class IsolationTests(unittest.TestCase):
 def test_import_without_notebook_modules_or_cwd(self):
  code="import sys;from traffic_location.traffic.pipeline import run;from traffic_location.traffic import render;assert not any(k.startswith('phase_') for k in sys.modules)"
  with tempfile.TemporaryDirectory() as d:
   result=subprocess.run([sys.executable,'-B','-c',code],cwd=d,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_renderer_has_no_counting_dependency(self):
  p=ROOT/'src/traffic_location/traffic/render.py'
  for node in ast.walk(ast.parse(p.read_text())):
   if isinstance(node,ast.ImportFrom):self.assertNotIn(node.module,{'publication','pipeline','identity'})
 def test_all_generated_imports_are_local_or_stdlib(self):
  for p in (ROOT/'src/traffic_location/traffic').rglob('*.py'):
   for n in ast.walk(ast.parse(p.read_text())):
    if isinstance(n,ast.Import):self.assertFalse(any(a.name.startswith('phase_') for a in n.names),str(p))
    if isinstance(n,ast.ImportFrom):self.assertFalse((n.module or '').startswith('phase_'),str(p))
 def test_extraction_registry_matches_original_and_generated_sources(self):
  for registry in ['source_extraction.json','location_source_extraction.json']:
   for row in read(ROOT/'results/engine_modularization'/registry):
    self.assertEqual(sha(ROOT/row['source']),row['source_sha256'])
    self.assertEqual(sha(ROOT/row['module']),row['module_sha256'])
 def test_golden_registry_matches_retained_bytes(self):
  for branch,row in read(ROOT/'results/engine_modularization/20261023/goldens/baselines.json').items():
   p=Path(row['native_ref']['path']);self.assertEqual(sha(p),row['native_ref']['sha256']);self.assertEqual(semantic_hash(read(p)),row['canonical_native_sha256'])
 def test_atomic_publication_and_reopen(self):
  golden=read(ROOT/'results/engine_modularization/20261023/goldens/baselines.json')['machine']
  native=read(golden['native_ref']['path']);result={'native_semantic_sha256':semantic_hash(native)}
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'result';publish(out,{'native.json.gz':native,'result.json':result})
   self.assertEqual(reopen_traffic(out),result)
   with self.assertRaises(ValueError):publish(out,{})
 def test_tampered_result_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'result';publish(out,{'result.json':{'x':1}});(out/'result.json').write_text('{}')
   from traffic_location.persistence import verify_manifest
   with self.assertRaises(ValueError):verify_manifest(out)

if __name__=='__main__':unittest.main()
