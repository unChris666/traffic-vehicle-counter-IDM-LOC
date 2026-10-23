"""Synthetic membership and offline-packet regressions. No external data requests."""
import copy,json,math,socket,tempfile,shutil
from pathlib import Path
from unittest import TestCase,main,mock
from shapely.geometry import Point,Polygon,MultiPolygon,box,mapping
import location_intelligent_recount as m
from location_intelligent_li3_sources import read_json,write_json
from location_intelligent_li4 import build as build_li4
from li4_package_tests import fixture,rehash


def record(i,xy,status='ACCEPTED',value=4,unit='UNRESOLVED'):
    return {'source_row_index':i,'building_key':'b'+str(i),'point_m':xy,'selection_status':'SELECTED',
        'decision_state':status,'capacity_unit':unit,'capacity_reference':value}


def fc(g,rev='test-r1'):
    return {'type':'FeatureCollection','schema_version':'li_recount_polygons_v1','crs':'EPSG:4326',
        'revision_id':rev,'claim_type':'SYNTHETIC_TEST','features':[{'type':'Feature','properties':{'polygon_id':'p'},'geometry':mapping(g)}]}


class MembershipTests(TestCase):
    def evaluate(self,rows,polys,**kw):return m.evaluate(rows,polys,center=(0,0),radius=10,**kw)
    def test_inside_outside(self):
        g,u=self.evaluate([record(0,(0,0)),record(1,(3,3))],{'p':box(-1,-1,1,1)})
        self.assertEqual(u,[0]);self.assertEqual(g['p']['decision_counts'],{'ACCEPTED':1})
    def test_boundary_covers(self):
        self.assertEqual(self.evaluate([record(0,(1,0))],{'p':box(-1,-1,1,1)})[1],[0])
    def test_explicit_contains_excludes_boundary(self):
        self.assertEqual(self.evaluate([record(0,(1,0))],{'p':box(-1,-1,1,1)},predicate='contains')[1],[])
    def test_hole_and_hole_boundary(self):
        p=Polygon([(-4,-4),(4,-4),(4,4),(-4,4)],holes=[[(-1,-1),(1,-1),(1,1),(-1,1)]])
        self.assertEqual(self.evaluate([record(0,(0,0)),record(1,(1,0)),record(2,(2,0))],{'p':p})[1],[1,2])
    def test_multipolygon(self):
        p=MultiPolygon([box(-3,-3,-2,-2),box(2,2,3,3)])
        self.assertEqual(self.evaluate([record(0,(2.5,2.5)),record(1,(0,0))],{'p':p})[1],[0])
    def test_overlap_union_unique(self):
        g,u=self.evaluate([record(0,(0,0)),record(1,(2,0))],{'a':box(-1,-1,1,1),'b':box(-1,-1,3,1)})
        self.assertEqual(sum(len(x['source_row_indices']) for x in g.values()),3);self.assertEqual(u,[0,1])
    def test_outside_scope_reported(self):
        g,u=self.evaluate([record(0,(0,0))],{'p':box(-20,-1,20,1)})
        self.assertEqual(g['p']['coverage_status'],'PARTIAL_OUTSIDE_ANALYSIS_DOMAIN');self.assertEqual(u,[0])
    def test_empty_polygons_explicit_empty_membership(self):self.assertEqual(self.evaluate([record(0,(0,0))],{}),({},[]))
    def test_empty_records_not_fabricated(self):self.assertEqual(self.evaluate([],{'p':box(-1,-1,1,1)})[1],[])
    def test_unknown_access_stays_unknown(self):
        g,_=self.evaluate([record(0,(0,0),'ACCESS_UNVERIFIED')],{'p':box(-1,-1,1,1)})
        self.assertEqual(g['p']['decision_counts'],{'ACCESS_UNVERIFIED':1})
    def test_mixed_units_and_null(self):
        g,_=self.evaluate([record(0,(0,0),value=None,unit='ROOM'),record(1,(0,0),unit='GUEST')],{'p':box(-1,-1,1,1)})
        groups=g['p']['capacity_by_decision_and_unit']['ACCEPTED']
        self.assertEqual(groups['ROOM']['unknown_buildings'],1);self.assertEqual(groups['GUEST']['known_subtotal'],4)
        self.assertIsNone(g['p']['mixed_unit_total'])
    def test_duplicate_key_fails(self):
        r=[record(0,(0,0)),record(1,(0,0))];r[1]['building_key']=r[0]['building_key']
        with self.assertRaises(ValueError):self.evaluate(r,{})
    def test_duplicate_row_fails(self):
        with self.assertRaises(ValueError):self.evaluate([record(0,(0,0)),record(0,(1,1))],{})
    def test_nan_point_fails(self):
        with self.assertRaises(ValueError):self.evaluate([record(0,(math.nan,0))],{})
    def test_invalid_polygon_not_repaired(self):
        with self.assertRaises(ValueError):self.evaluate([],{'p':Polygon([(0,0),(1,1),(1,0),(0,1)])})
    def test_footprint_intersection_not_point_membership(self):
        footprint=box(0,0,10,10);p=box(-1,-1,1,1)
        self.assertTrue(footprint.intersects(p));self.assertEqual(self.evaluate([record(0,(5,5))],{'p':p})[1],[])
    def test_invalid_lon_lat(self):
        with self.assertRaises(ValueError):m.validate_polygons(fc(box(200,0,201,1)))
    def test_duplicate_polygon_id(self):
        v=fc(box(0,0,1,1));v['features']*=2
        with self.assertRaises(ValueError):m.validate_polygons(v)
    def test_missing_revision(self):
        v=fc(box(0,0,1,1));v.pop('revision_id')
        with self.assertRaises(ValueError):m.validate_polygons(v)
    def test_policy_requires_explicit_supported_values(self):
        v=read_json(m.HERE/'fixtures/li5/policy.json');v['outside_coverage']='AUTO_FETCH'
        with self.assertRaises(ValueError):m.checked_policy(v)
    def test_order_determinism(self):
        rows=[record(2,(0,0)),record(1,(0,0))];p={'b':box(-1,-1,1,1),'a':box(-2,-2,2,2)}
        self.assertEqual(self.evaluate(rows,p),self.evaluate(list(reversed(rows)),dict(reversed(list(p.items())))))


class PacketTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.base=Path(cls.temp.name)
        raw=cls.base/'raw';fixture(raw)
        v=read_json(raw/'building_results/selection.json')
        for i,b in enumerate(v['selected']):
            b.update(source_row_index=i,representative_point={'type':'Point','coordinates':[106.00005+i*.001,-6.00005]},
                building_key={'provider':'SYNTHETIC','source_version':'test','snapshot_sha256':'a'*64,'building_id':b['building_id']})
        write_json(raw/'building_results/selection.json',v)
        c=read_json(raw/'normalized/context.json');c['config']={'area_coverage':{'parameters':{'building_radius_m':{'value':400,'unit':'m'}}}}
        write_json(raw/'normalized/context.json',c)
        write_json(raw/'config/pilot.json',{'policy':{'li3':{'metric_crs':'EPSG:32748','longitude':106.003,'latitude':-6}}})
        rehash(raw);cls.source=cls.base/'li4';build_li4(raw,cls.source)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.policy=read_json(m.HERE/'fixtures/li5/policy.json')
    def tearDown(self):self.temp.cleanup()
    def build(self,name='r1',revision='demo-r1',previous=None):
        out=self.root/name;m.build(self.source,out,m.demo(self.source,revision),self.policy,previous);return out
    def test_build_reopen_relocated_without_network(self):
        with mock.patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
            out=self.build();dest=self.root/'moved';out.rename(dest)
            self.assertEqual(m.verify(dest)['source_rows'],4)
    def test_all_rows_source_decisions_unchanged(self):
        out=self.build();ledger=read_json(out/'membership.json');original=read_json(self.source/'buildings.json')
        self.assertEqual(len(ledger),4)
        for a,b in zip(ledger,original):
            for k,v in b.items():self.assertEqual(a[k],v)
        self.assertFalse(ledger[3]['recount_evaluated'])
    def test_repeat_result_bytes_identical(self):
        a=self.build('a');b=self.build('b')
        for name in ['result.json','membership.json','membership.csv','review.html']:
            self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
    def test_delta_matches_set_difference(self):
        a=self.build();b=self.build('r2','demo-r2',a)
        old=read_json(a/'result.json');new=read_json(b/'result.json');delta=read_json(b/'delta.json')
        self.assertEqual(delta['union']['entered'],sorted(set(new['union_source_row_indices'])-set(old['union_source_row_indices'])))
        self.assertEqual(delta['union']['exited'],[])
    def test_changed_geometry_requires_revision(self):
        a=self.build();polys=m.demo(self.source,'demo-r2');polys['revision_id']='demo-r1'
        with self.assertRaisesRegex(ValueError,'new revision'):m.build(self.source,self.root/'bad',polys,self.policy,a)
    def test_policy_delta_mismatch(self):
        a=self.build();p=copy.deepcopy(self.policy);p.update(predicate='contains',policy_version='TEST_CONTAINS')
        with self.assertRaisesRegex(ValueError,'same source and policy'):m.build(self.source,self.root/'bad',m.demo(self.source,'demo-r2'),p,a)
    def test_immutable_output(self):
        self.build()
        with self.assertRaises(ValueError):self.build()
    def test_tampering_fails(self):
        a=self.build();(a/'result.json').write_text('{}')
        with self.assertRaises(ValueError):m.verify(a)
    def test_failure_partial_export_no_publish(self):
        original=Path.write_bytes
        def fail(p,data):
            if p.name=='membership.csv':raise OSError('disk full')
            return original(p,data)
        with mock.patch.object(Path,'write_bytes',fail):
            with self.assertRaises(OSError):self.build()
        self.assertFalse((self.root/'r1').exists());self.assertFalse(list(self.root.glob('.r1-*')))
    def test_parent_unchanged(self):
        before=m.digest(self.source/'manifest.json');self.build();self.assertEqual(m.digest(self.source/'manifest.json'),before)


if __name__=='__main__':main()
