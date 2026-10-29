"""Regression for Shapely object-dtype failure on zero connector candidates."""
import unittest,importlib.util
from unittest.mock import Mock,patch
from traffic_location.location.area.backends.geometry_gpu import BatchSafeGpuGeometry,geometry_scope,FrozenGpuGeometry
class BatchTests(unittest.TestCase):
 def test_empty_batch_does_not_touch_cuda_index_or_inset(self):
  g=object.__new__(BatchSafeGpuGeometry);g.cp=Mock();tree=Mock();inset=Mock()
  self.assertEqual(g.footprint_clear_batch([],['b'],{},tree,inset),[])
  self.assertEqual(g.resident_footprint_batch([],['b'],{},tree,inset),[])
  self.assertEqual(g.cp.mock_calls,[]);tree.query.assert_not_called();inset.assert_not_called()
 def test_nonempty_gpu_batch_is_delegated_unchanged(self):
  g=object.__new__(BatchSafeGpuGeometry);items=[None];args=(items,['b'],{},Mock(),Mock())
  with patch.object(FrozenGpuGeometry,'resident_footprint_batch',return_value=[[]]) as original:
   self.assertEqual(g.resident_footprint_batch(*args),[[]]);original.assert_called_once_with(*args)
 def test_scoped_patch_is_restored_after_failure(self):
  from traffic_location.location.area._kernel import location_intelligent_gpu_geometry as kernel
  original=kernel.GpuGeometry
  with self.assertRaises(RuntimeError):
   with geometry_scope():
    self.assertIs(kernel.GpuGeometry,BatchSafeGpuGeometry);raise RuntimeError('fixture')
  self.assertIs(kernel.GpuGeometry,original)
 def test_both_source_and_market_runtimes_use_scope(self):
  from traffic_location.location.area.backends import runtime_gpu
  from traffic_location.location.area._kernel import location_intelligent_gpu_geometry as kernel
  def check(*a,**kw):self.assertIs(kernel.GpuGeometry,BatchSafeGpuGeometry);return 'ok'
  with patch.object(runtime_gpu,'_build',side_effect=check),patch.object(runtime_gpu,'_market',side_effect=check):
   self.assertEqual(runtime_gpu.build_gpu('pilot'),'ok');self.assertEqual(runtime_gpu.build_market_gpu('config'),'ok')
 @unittest.skipUnless(importlib.util.find_spec('shapely'),'Run GIS environment')
 def test_native_shapely_reproduces_error_and_adapter_avoids_it(self):
  from shapely import STRtree
  from shapely.geometry import box
  tree=STRtree([box(0,0,1,1)])
  with self.assertRaisesRegex(TypeError,'object dtype'):tree.query([])
  g=object.__new__(BatchSafeGpuGeometry);g.cp=Mock()
  self.assertEqual(g.footprint_clear_batch([],['b'],{'b':box(0,0,1,1)},tree,Mock()),[])
 @unittest.skipUnless(importlib.util.find_spec('shapely'),'Run GIS environment')
 def test_nonempty_cpu_geometry_parity_keeps_intersection_and_owner_rules(self):
  from shapely import STRtree
  from shapely.geometry import box,LineString,Point
  footprints={'own':box(0,0,1,1),'other':box(2,0,3,1)};ids=list(footprints)
  tree=STRtree(list(footprints.values()))
  items=[{'building_id':'own','kind':'BUILDING','target':Point(4,.5),'line':LineString([(.5,.5),(4,.5)]),'epsilon':.001},None]
  def make(cls):
   g=object.__new__(cls);g.polygon_lengths=lambda pairs:[(line.intersection(poly).length,False,0.) for line,poly in pairs];return g
  args=(items,ids,footprints,tree,lambda bid:footprints[bid])
  observed=make(BatchSafeGpuGeometry).footprint_clear_batch(*args)
  self.assertEqual(observed,make(FrozenGpuGeometry).footprint_clear_batch(*args));self.assertEqual(observed,[[{'source':'other','kind':'other_building'}],[]])
