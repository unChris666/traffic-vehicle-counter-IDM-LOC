"""Synthetic OSM topology/provenance tests, run under system Python/GDAL."""
import unittest
from importlib.util import find_spec
from location_intelligent_osm_buildings import normalize_osm,join_rings,SCHEMA

def geom(coords):return [{'lon':x,'lat':y} for x,y in coords]
def raw(elements):return {'provider':'OPENSTREETMAP','schema_version':SCHEMA,'payload':{'elements':elements}}
@unittest.skipUnless(find_spec('osgeo'), 'OSM geometry normalization requires system Python/GDAL')
class OSMTests(unittest.TestCase):
 def test_closed_way_and_unknown_use_not_invented(self):
  r=normalize_osm(raw([{'type':'way','id':1,'tags':{'building':'yes'},'geometry':geom([(0,0),(1,0),(1,1),(0,0)])}]))
  p=r['features'][0]['properties'];self.assertEqual(p['building_id'],'way/1');self.assertIsNone(p['class']);self.assertIsNone(p['subclass'])
 def test_split_outer_hole_and_member_suppression(self):
  a=[(0,0),(10,0),(10,10)];b=[(0,0),(0,10),(10,10)];hole=[(2,2),(3,2),(3,3),(2,2)]
  relation={'type':'relation','id':9,'tags':{'type':'multipolygon','building':'apartments'},'members':[
   {'type':'way','ref':1,'role':'outer','geometry':geom(a)}, {'type':'way','ref':2,'role':'outer','geometry':geom(b)},
   {'type':'way','ref':3,'role':'inner','geometry':geom(hole)}]}
  r,d=normalize_osm(raw([relation,{'type':'way','id':1,'tags':{'building':'yes'},'geometry':geom(a)}]),True)
  self.assertEqual(len(r['features']),1);self.assertEqual(len(r['features'][0]['geometry']['coordinates'][0]),2)
  self.assertEqual(d['excluded'][0]['reason'],'RELATION_MEMBER_COMPONENT')
 def test_open_way_not_repaired(self):
  r,d=normalize_osm(raw([{'type':'way','id':1,'tags':{'building':'yes'},'geometry':geom([(0,0),(1,0),(1,1)])}]),True)
  self.assertEqual(r['features'],[]);self.assertEqual(d['excluded'][0]['reason'],'OPEN_WAY')
 def test_unsupported_use_not_residential_and_floor_unknown(self):
  r=normalize_osm(raw([{'type':'way','id':2,'tags':{'building':'industrial','height':'10 m','building:levels':'unknown'},'geometry':geom([(0,0),(1,0),(1,1),(0,0)])}]))
  p=r['features'][0]['properties'];self.assertEqual(p['subclass'],'industrial');self.assertIsNone(p['height']);self.assertIsNone(p['num_floors'])
 def test_duplicate_id_and_incomplete_ring_fail(self):
  e={'type':'way','id':1}
  with self.assertRaises(ValueError):normalize_osm(raw([e,e]))
  with self.assertRaises(ValueError):join_rings([[(0,0),(1,0)]])
 def test_explicit_facility_precedes_generic_residential_fallback(self):
  r=raw([{'type':'way','id':1,'tags':{'building':'yes','amenity':'school'},'geometry':geom([(0,0),(10,0),(10,10),(0,10),(0,0)])}]);r['use_policy_version']='osm_poi_use_v2'
  p=normalize_osm(r)['features'][0]['properties']
  self.assertEqual(p['subclass'],'non_residential_poi');self.assertIn('amenity=school',p['use_review_reason'])
 def test_contained_shop_is_review_not_whole_building_relabel(self):
  r=raw([{'type':'way','id':1,'tags':{'building':'house'},'geometry':geom([(0,0),(10,0),(10,10),(0,10),(0,0)])}]);r['use_policy_version']='osm_poi_use_v2'
  r['use_poi_nodes']=[{'type':'node','id':5,'lat':5,'lon':5,'tags':{'shop':'convenience'}}]
  p=normalize_osm(r)['features'][0]['properties'];self.assertEqual(p['subclass'],'poi_use_review');self.assertIn('NO_FLOOR_ALLOCATION',p['use_review_reason'])
 def test_nearby_poi_outside_does_not_change_house(self):
  r=raw([{'type':'way','id':1,'tags':{'building':'house'},'geometry':geom([(0,0),(10,0),(10,10),(0,10),(0,0)])}]);r['use_policy_version']='osm_poi_use_v2'
  r['use_poi_nodes']=[{'type':'node','id':5,'lat':11,'lon':11,'tags':{'amenity':'school'}}]
  p=normalize_osm(r)['features'][0]['properties'];self.assertEqual(p['subclass'],'residential')
 def test_bench_inside_not_evidence_of_nonresidential_building(self):
  r=raw([{'type':'way','id':1,'tags':{'building':'house'},'geometry':geom([(0,0),(10,0),(10,10),(0,10),(0,0)])}]);r['use_policy_version']='osm_poi_use_v2'
  r['use_poi_nodes']=[{'type':'node','id':5,'lat':5,'lon':5,'tags':{'amenity':'bench'}}]
  p=normalize_osm(r)['features'][0]['properties'];self.assertEqual(p['subclass'],'residential')
if __name__=='__main__':unittest.main()
