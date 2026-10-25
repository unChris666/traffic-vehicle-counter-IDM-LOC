"""Exact equivalence/cache invalidation tests. No source acquisition."""
import unittest,tempfile,json,random,os
from pathlib import Path
from unittest.mock import patch
from importlib.util import find_spec
import location_intelligent_osm_buildings as module
from location_intelligent_li3_sources import timed_call

class IndexTests(unittest.TestCase):
 def test_candidates_equal_envelope_scan_including_edges(self):
  rng=random.Random(81);records=[]
  for i in range(500):
   x,y=rng.uniform(-100,100),rng.uniform(-100,100)
   records.append((str(i),(x,x+rng.uniform(0,20),y,y+rng.uniform(0,20))))
  index=module.EnvelopePointIndex(records)
  points=[(rng.uniform(-120,120),rng.uniform(-120,120)) for _ in range(500)]
  points += [(e[0],e[2]) for _,e in records]
  for x,y in points:
   self.assertEqual(index.query(x,y),[k for k,e in records if e[0]<=x<=e[1] and e[2]<=y<=e[3]])
  self.assertEqual(module.EnvelopePointIndex([]).query(0,0),[])
 def test_timing_records_success_and_failure(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LI_PERFORMANCE_REPORT':str(Path(d)/'timing.json')}):
   self.assertEqual(timed_call('ok',lambda:7),7)
   with self.assertRaises(ZeroDivisionError):timed_call('bad',lambda:1/0)
   rows=json.loads((Path(d)/'timing.json').read_text())
   self.assertEqual([r['status'] for r in rows],['SUCCEEDED','FAILED'])
   self.assertTrue(all(r['duration_seconds']>=0 for r in rows))

 def test_timing_journal_failure_does_not_change_domain_result(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LI_PERFORMANCE_REPORT':str(Path(d)/'timing.json')}):
   with patch('location_intelligent_li3_sources.write_json',side_effect=OSError('disk unavailable')):
    self.assertEqual(timed_call('ok',lambda:7),7)
    with self.assertRaises(ZeroDivisionError):timed_call('bad',lambda:1/0)

@unittest.skipUnless(find_spec('osgeo'),'GDAL worker required')
class NormalizationTests(unittest.TestCase):
 def raw(self):
  def way(i,x,y,coords=None):
   return {'type':'way','id':i,'tags':{'building':'house'},'geometry':[{'lon':a,'lat':b} for a,b in (coords or [(x,y),(x+1,y),(x+1,y+1),(x,y+1),(x,y)])]}
  return {'provider':'OPENSTREETMAP','schema_version':module.SCHEMA,'use_policy_version':'osm_poi_use_v2',
    'payload':{'elements':[way(1,0,0),way(2,1,0),way(3,0,0),way(4,10,10)]},
    'use_poi_nodes':[{'type':'node','id':i,'lon':x,'lat':y,'tags':{'shop':'convenience'}}
      for i,(x,y) in enumerate([(0.5,0.5),(1,0.5),(11.1,11.1),(10.5,10.5)])]}
 def test_index_equals_legacy_ogr_scan(self):
  raw=self.raw();indexed=module.normalize_osm(raw,True)
  class Brute:
   def __init__(self,records):self.keys=[k for k,_ in records]
   def query(self,x,y):return self.keys
  with patch.object(module,'EnvelopePointIndex',Brute):legacy=module.normalize_osm(raw,True)
  self.assertEqual(indexed,legacy)
 def test_cache_hit_invalidation_corruption_and_legacy_readonly(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'cache.json';raw=self.raw()
   expected=module.cached_normalization(raw,path)
   with patch.object(module,'normalize_osm',side_effect=AssertionError('must not recompute')):
    self.assertEqual(module.cached_normalization(raw,path),expected)
   # New POI/use policy and changed code/runtime bindings invalidate cache.
   raw['use_poi_nodes']=[]
   with patch.object(module,'normalize_osm',wraps=module.normalize_osm) as work:
    module.cached_normalization(raw,path);self.assertEqual(work.call_count,1)
   data=json.loads(path.read_text());data['binding']['python']='old';path.write_text(json.dumps(data))
   with patch.object(module,'normalize_osm',wraps=module.normalize_osm) as work:
    module.cached_normalization(raw,path);self.assertEqual(work.call_count,1)
   data=json.loads(path.read_text());data['payload']['features']['features']=[];path.write_text(json.dumps(data))
   with self.assertRaisesRegex(ValueError,'Corrupt'):module.cached_normalization(raw,path)
   old=Path(d)/'historical.json';module.cached_normalization(raw,old,write=False);self.assertFalse(old.exists())
if __name__=='__main__':unittest.main()
