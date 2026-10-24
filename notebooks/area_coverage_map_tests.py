"""Offline boundary tests; no provider calls or fabricated experiment results."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile,unittest,hashlib
from location_intelligent_map_pilot import resolve_bq_fields,build_bq_query,poi_locations,query_bbox,load_bq_layers,interactive_map
from location_intelligent_li3_sources import write_json,canonical_bytes
ROOT=Path(__file__).resolve().parents[1]
class QueryTests(unittest.TestCase):
 def field(self,name,kind):return SimpleNamespace(name=name,field_type=kind)
 def test_numeric_competitor_schema(self):
  fields=resolve_bq_fields(SimpleNamespace(schema=[self.field('LAT','STRING'),self.field('LONG','STRING'),self.field('KDTK','STRING')]),'competitor')
  q=build_bq_query('locdeproject.DWH_NS_LOC.COMPETITOR',fields)
  self.assertIn('SAFE_CAST(`LAT` AS FLOAT64)',q);self.assertIn('@radius_m',q);self.assertNotIn('SELECT * FROM `',q)
  self.assertIn('CASE WHEN latitude BETWEEN -90 AND 90',q)
 def test_geography_store_schema(self):
  f=resolve_bq_fields(SimpleNamespace(schema=[self.field('KOORDINAT','GEOGRAPHY')]),'indomaret')
  q=build_bq_query('locdeproject.DWH_NS_LOC.AREA_COVERAGE',f)
  self.assertIn('`KOORDINAT` AS p',q);self.assertIn('SAFE.ST_X',q)
 def test_wkt_store_schema(self):
  f=resolve_bq_fields(SimpleNamespace(schema=[self.field('KOORDINAT','STRING')]),'indomaret')
  self.assertIn('SAFE.ST_GEOGFROMTEXT',build_bq_query('locdeproject.DWH_NS_LOC.AREA_COVERAGE',f))
 def test_explicit_point_override_wins_over_numeric_fields(self):
  t=SimpleNamespace(schema=[self.field('LAT','FLOAT64'),self.field('LONG','FLOAT64'),self.field('KOORDINAT','GEOGRAPHY')])
  f=resolve_bq_fields(t,'competitor',{'point':'KOORDINAT'})
  self.assertIsNone(f['latitude']);self.assertIn('`KOORDINAT` AS p',build_bq_query('locdeproject.DWH_NS_LOC.COMPETITOR',f))
 def test_unknown_or_incomplete_override_not_ignored(self):
  t=SimpleNamespace(schema=[self.field('LAT','FLOAT64'),self.field('LONG','FLOAT64')])
  for overrides in [{'latitdue':'LAT'},{'latitude':'LAT'}]:
   with self.assertRaises(ValueError):resolve_bq_fields(t,'competitor',overrides)
 def test_unknown_schema_not_guessed(self):
  with self.assertRaises(ValueError):resolve_bq_fields(SimpleNamespace(schema=[]),'competitor')
 def test_sql_identifier_injection_rejected(self):
  f=resolve_bq_fields(SimpleNamespace(schema=[self.field('LAT','FLOAT64'),self.field('LONG','FLOAT64')]),'competitor')
  with self.assertRaises(ValueError):build_bq_query('locdeproject.DWH_NS_LOC.COMPETITOR` DROP TABLE',f)
class LayerTests(unittest.TestCase):
 def test_history_same_location_one_marker_aliases_retained(self):
  rows=[{'store_id':'001','store_name':name,'latitude':-6.4,'longitude':106.8,'distance_m':10.} for name in ['Old name','New name']]
  result=poi_locations({'rows':rows});self.assertEqual(len(result),1);self.assertEqual(result[0]['source_rows'],2);self.assertEqual(len(result[0]['names']),2)
 def test_conflicting_id_locations_not_arbitrarily_merged(self):
  rows=[{'store_id':'001','store_name':'X','latitude':-6.4+i*.001,'longitude':106.8,'distance_m':10.} for i in range(2)]
  result=poi_locations({'rows':rows});self.assertEqual(len(result),2);self.assertTrue(all(r['identity_location_conflict'] for r in result))
 def test_geodesic_query_bbox_contains_target(self):
  w,s,e,n=query_bbox(-6.409737552410453,106.82835008971841,2100)
  self.assertTrue(w<106.82835008971841<e and s<-6.409737552410453<n)
 def test_auth_failure_is_unknown_not_zero(self):
  config={'latitude':-6.4,'longitude':106.8,'poi_radius_m':2000.}
  with tempfile.TemporaryDirectory() as d,patch('location_intelligent_map_pilot.bq_credentials',side_effect=ValueError('unavailable')):
   r=load_bq_layers(config,d)
  for layer in r.values():self.assertEqual(layer['status'],'BLOCKED');self.assertIsNone(layer['rows']);self.assertIsNone(layer['count_source_rows_distinct'])
 def test_successful_frozen_cache_reopens_without_auth_or_query(self):
  c={'latitude':-6.4,'longitude':106.8,'poi_radius_m':2000.}
  with tempfile.TemporaryDirectory() as d:
   for k,t in [('indomaret','AREA_COVERAGE'),('competitor','COMPETITOR')]:
    binding={**c,'radius_m':c['poi_radius_m'],'table':'locdeproject.DWH_NS_LOC.'+t,'overrides':{}}
    binding.pop('poi_radius_m')
    write_json(Path(d)/(k+'.json'),{'status':'SUCCEEDED','rows':[],'request_fingerprint':hashlib.sha256(canonical_bytes(binding)).hexdigest()})
   with patch('location_intelligent_map_pilot.bq_credentials',side_effect=AssertionError('must not authenticate')):
    r=load_bq_layers(c,d);self.assertTrue(all(v['status']=='SUCCEEDED' for v in r.values()))
 def test_wrong_map_target_fails_before_drawing(self):
  c={'latitude':-6.409737552410453,'longitude':106.82835008971841,'building_radius_m':800.,'poi_radius_m':2000.,'metric_crs':'EPSG:32748'}
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Map target/CRS differs'):
    interactive_map(c,ROOT/'results/location_intelligent/li3_n1_20261022_v1',{},Path(d)/'map.html')
if __name__=='__main__':unittest.main()
