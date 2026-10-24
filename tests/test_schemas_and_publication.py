import copy,json,tempfile,unittest
from pathlib import Path
import jsonschema
from traffic_location.artifacts import read,sha
from traffic_location.persistence import publish,verify_manifest
ROOT=Path(__file__).resolve().parents[1]
SCHEMAS=ROOT/'src/traffic_location/schemas'
REQUESTS=ROOT/'results/engine_modularization/20261023/requests'

class SchemaTests(unittest.TestCase):
 def schema(self,name):return read(SCHEMAS/(name+'.json'))
 def test_every_schema_is_valid_draft202012(self):
  for p in SCHEMAS.glob('*.json'):
   with self.subTest(path=p.name):jsonschema.Draft202012Validator.check_schema(read(p))
 def test_real_requests_match_schema(self):
  for name in ['machine','review_assisted']:jsonschema.validate(read(REQUESTS/(name+'.json')),self.schema('traffic_request.v1'))
  for name,schema in [('location_selection','location_selection_request.v1'),('location_recount_r1','location_recount_request.v1'),('location_recount_r2','location_recount_request.v1')]:jsonschema.validate(read(REQUESTS/(name+'.json')),self.schema(schema))
 def test_actual_migration_result_v2_matches_schema(self):
  result=ROOT/'results/traffic_migration/20261024/parity/T7SL-WEEKDAY-MALAM/result.json'
  if not result.exists():self.skipTest('Migration receipt not retained')
  jsonschema.validate(read(result),self.schema('traffic_result.v2'))
 def test_machine_overlay_mixing_rejected_by_schema(self):
  r=read(REQUESTS/'review_assisted.json');r['profile']='machine'
  with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(r,self.schema('traffic_request.v1'))
 def test_replay_requires_explicit_branch(self):
  r=read(REQUESTS/'machine.json');r['profile']='replay'
  with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(r,self.schema('traffic_request.v1'))
 def test_atomic_export_failure_does_not_publish_success(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'result'
   with self.assertRaises((TypeError,ValueError)):publish(p,{'first.json':{'ok':True},'bad.json':{'not_serializable':object()}})
   self.assertFalse(p.exists());self.assertEqual(list(Path(d).iterdir()),[])
 def test_output_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):publish(Path(d)/'result',{'../escape.json':{}})
   self.assertFalse((Path(d)/'escape.json').exists())
 def test_manifest_detects_unlisted_artifacts(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'result';publish(p,{'result.json':{}});(p/'extra').write_text('x')
   with self.assertRaises(ValueError):verify_manifest(p)

if __name__=='__main__':unittest.main()
