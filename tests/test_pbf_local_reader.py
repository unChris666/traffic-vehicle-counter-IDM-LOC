"""Source geometry and diagnostics; native tests use synthetic PBF, never owner data."""
import importlib.util,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from traffic_location.location.area.sources import pbf_local
from traffic_location.artifacts import read,sha
from traffic_location.integration.kaggle_runtime import area_config

class BboxSelectionTests(unittest.TestCase):
    def test_crossing_segment_is_selected_without_inside_vertex(self):
        nodes={1:{'lon':-2.,'lat':0.},2:{'lon':2.,'lat':0.}}
        self.assertTrue(pbf_local.way_intersects_bbox({'id':7,'nodes':[1,2]},nodes,[-1,-1,1,1]))
    def test_non_crossing_parallel_corner_and_reverse(self):
        def p(x,y):return {'lon':x,'lat':y}
        box=[-1,-1,1,1]
        for a,b,expected in ((p(-2,2),p(2,2),False),(p(-2,0),p(0,2),True),
                             (p(-2,1.5),p(.1,3),False),(p(0,0),p(0,0),True)):
            self.assertEqual(pbf_local.segment_intersects_bbox(a,b,box),expected)
            self.assertEqual(pbf_local.segment_intersects_bbox(b,a,box),expected)
    def test_missing_nodes_are_not_bridged(self):
        with self.assertRaisesRegex(RuntimeError,'PBF_MISSING_WAY_NODE'):
            pbf_local.way_intersects_bbox({'id':7,'nodes':[1,2,3]},
                {1:{'lon':-2,'lat':0},3:{'lon':2,'lat':0}},[-1,-1,1,1])

@unittest.skipUnless(all(importlib.util.find_spec(p) for p in ('osmium','osmnx','pyproj')),'Run PBF native environment separately')
class NativePbfTests(unittest.TestCase):
    def make_pbf(self,root,tags):
        import osmium
        path=root/'fixture.osm.pbf';header=osmium.io.Header()
        header.add_box(osmium.osm.Box(109.,-9.,112.,-6.))
        header.set('osmosis_replication_timestamp','2026-10-20T00:00:00Z')
        with osmium.SimpleWriter(path,header=header) as writer:
            writer.add_node(osmium.osm.mutable.Node(id=1,location=(110.45,-7.33058110387148)))
            writer.add_node(osmium.osm.mutable.Node(id=2,location=(110.56,-7.33058110387148)))
            writer.add_way(osmium.osm.mutable.Way(id=7,nodes=[1,2],tags=tags))
        return path
    def run_reader(self,reader,root,tags):
        path=self.make_pbf(root,tags);config=area_config(-7.33058110387148,110.50486365193136)['CONFIG']
        def extract(args,**kwargs):shutil.copyfile(path,args[args.index('--output')+1])
        with patch('subprocess.run',side_effect=extract):
            return reader.materialize(config,root/'sources',path,'fixture-osmium',{'sha256':sha(path),'generation':1,'object':'synthetic'})
    def test_native_pbf_crossing_road_false_empty_is_fixed_and_manifests_verify(self):
        from traffic_location.location.area._kernel import location_intelligent_pbf_sources as old
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(RuntimeError,'PBF_NO_ROADS_IN_REQUESTED_EXTENT'):
                self.run_reader(old,root,{'highway':'residential'})
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=self.run_reader(pbf_local,root,{'highway':'residential'})
            self.assertTrue((source/'source_manifest.json').exists())
            report=read(source/'pbf-source-diagnostics.json')
            self.assertEqual(report['selected_road_ways'],1);self.assertEqual(report['metric_crs'],'EPSG:32749')
            self.assertEqual(read(source/'pbf_source.json')['reader_version'],pbf_local.READER_VERSION)
    def test_no_highways_has_precise_diagnostic_without_success_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(pbf_local.PbfSourceError,'NO_HIGHWAY_WAYS'):
                self.run_reader(pbf_local,root,{'building':'yes'})
            self.assertFalse((root/'sources/source_manifest.json').exists())
            self.assertEqual(read(root/'sources/pbf-source-diagnostics.json')['nodes'],2)
    def test_access_rules_remain_strict_no_fake_roads(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(pbf_local.PbfSourceError,'ACCESS_FILTER_EXCLUDED_ALL'):
                self.run_reader(pbf_local,root,{'highway':'residential','access':'private'})
            self.assertFalse((root/'sources/source_manifest.json').exists())

if __name__=='__main__':unittest.main()
