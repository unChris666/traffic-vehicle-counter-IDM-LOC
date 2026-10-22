"""Offline LI-3 unit/integration fixtures; run in the isolated source env."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest

from pyproj import Transformer
from shapely.geometry import LineString

from location_intelligent_config import get_config
from location_intelligent_li3_sources import acquire_overpass, build_queries, canonical_bytes, read_json, write_json
from location_intelligent_li3_graph import build_graph, apply_turns, node_permission, way_direction, merge_elements, graph_diagnostics
from location_intelligent_li3_connectors import barrier_index, check_barriers, generate_connectors
from location_intelligent_motor_routing import _path, _path_index
from location_intelligent_li3 import verify_manifest, map_decisions


def element(kind, key, **kwargs):
    return {'type': kind, 'id': key, 'version': 1, **kwargs}


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.p = get_config()
        tx = Transformer.from_crs(4326, 'EPSG:32748', always_xy=True)
        self.x, self.y = tx.transform(106.81, -6.43)
        self.f = {'policy': self.p, 'analysis_run_id': 'li3-synthetic',
                  'reference_metric_bbox': [self.x-2000,self.y-2000,self.x+2000,self.y+2000]}
        self.nodes = [element('node',1,lon=106.81,lat=-6.43), element('node',2,lon=106.811,lat=-6.43),
                      element('node',3,lon=106.812,lat=-6.43), element('node',4,lon=106.811,lat=-6.429)]
        self.ways = [element('way',10,nodes=[1,2,3],tags={'highway':'residential'}),
                     element('way',20,nodes=[2,4],tags={'highway':'service'})]
        self.roads = {'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':'2026-10-22T00:00:00Z'},'elements':self.nodes+self.ways}}
        self.features = {'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':'2026-10-22T00:00:00Z'},'elements':[]}}

    def graph(self):
        return build_graph(self.roads,self.features,self.f)

    def relation(self, restriction, via=None, **tags):
        self.features['payload']['elements'] = [element('relation',99,tags={'type':'restriction','restriction':restriction,**tags},
            members=[{'type':'way','ref':10,'role':'from'}, {'type':'node','ref':2,'role':'via'} if via is None else via,
                     {'type':'way','ref':20,'role':'to'}])]

    def test_directionality_without_reverse_invention(self):
        self.ways[0]['tags']['oneway']='yes'
        b=self.graph(); keys=b['edge_sources']
        self.assertEqual(sum(s['osm_way_id']==10 for s in keys.values()),2)
        self.assertTrue(all(e['u']!='n3' for e in b['graph']['edges'] if keys[e['edge_id']]['osm_way_id']==10))

    def test_motorcycle_oneway_exception(self):
        self.ways[0]['tags'].update(oneway='yes',**{'oneway:motorcycle':'no'})
        self.assertEqual(sum(s['osm_way_id']==10 for s in self.graph()['edge_sources'].values()),4)

    def test_reverse_oneway(self):
        self.assertEqual(way_direction({'oneway':'-1'}),-1)
        self.assertEqual(way_direction({'junction':'roundabout'}),1)

    def test_circular_junction_not_implicitly_oneway(self):
        self.assertEqual(way_direction({'junction':'circular'}),0)

    def test_private_prohibition(self):
        self.ways[0]['tags'].update(access='private',motorcycle='yes')
        b=self.graph()
        self.assertTrue(all(b['edge_rules'][k]['allowed'] is False for k,s in b['edge_sources'].items() if s['osm_way_id']==10))

    def test_directional_access_tags(self):
        self.ways[0]['tags']['motorcycle:forward']='no'
        b=self.graph()
        self.assertTrue(all(b['edge_rules'][k]['allowed'] is False for k,s in b['edge_sources'].items() if s['osm_way_id']==10 and s['direction']=='f'))
        self.assertTrue(all(b['edge_rules'][k]['allowed'] is True for k,s in b['edge_sources'].items() if s['osm_way_id']==10 and s['direction']=='r'))

    def test_unknown_primary_not_assumed_from_car_filter(self):
        self.ways[0]['tags']['highway']='primary'
        b=self.graph()
        self.assertTrue(all(b['edge_rules'][k]['allowed'] is None for k,s in b['edge_sources'].items() if s['osm_way_id']==10))

    def test_mapped_gate_assumption_and_locked_gate(self):
        self.assertTrue(node_permission({'barrier':'gate'})[0])
        self.assertFalse(node_permission({'barrier':'gate','locked':'yes'})[0])
        self.assertIsNone(node_permission({'barrier':'bollard'})[0])

    def test_gate_hours_unknown(self):
        self.assertIsNone(node_permission({'barrier':'gate','opening_hours':'Mo-Fr 08:00-18:00'})[0])

    def test_source_missing_different_from_empty(self):
        failed=build_graph({'status':'RETRIEVAL_FAILED'},self.features,self.f)
        self.assertIsNone(failed['graph'])
        self.roads['payload']['elements']=[]
        empty=self.graph()
        self.assertEqual(empty['graph']['edges'],[])
        self.assertEqual(empty['status'],'SUCCEEDED')

    def test_missing_source_keeps_missing_state(self):
        r=build_graph({'status':'SOURCE_MISSING'},self.features,self.f)
        self.assertEqual(r['status'],'SOURCE_MISSING')

    def test_missing_node_is_rejected_not_connected_straight(self):
        self.ways[0]['nodes']=[1,999]
        b=self.graph()
        self.assertEqual(b['status'],'PARTIAL')
        self.assertEqual(b['diagnostics']['rejected_source_segments'][0]['reason'],'MISSING_SOURCE_NODE')

    def test_source_conflict_rejected(self):
        with self.assertRaises(ValueError):
            merge_elements([self.nodes[0]],[{**self.nodes[0],'lon':107.0}])

    def test_numerical_crossing_does_not_connect_grade_separated_roads(self):
        self.nodes += [element('node',5,lon=106.8105,lat=-6.4305),element('node',6,lon=106.8105,lat=-6.4295)]
        self.ways += [element('way',30,nodes=[5,6],tags={'highway':'service','bridge':'yes','layer':'1'})]
        self.roads['payload']['elements']=self.nodes+self.ways
        b=self.graph()
        self.assertEqual(len(b['graph']['nodes']),6)
        self.assertFalse(any(e['u'] in {'n5','n6'} and e['v'] in {'n1','n2','n3','n4'} for e in b['graph']['edges']))

    def test_no_turn_mapping(self):
        self.relation('no_left_turn'); b=self.graph()
        turns,d=apply_turns(b['graph'],b['edge_sources'],b['edge_rules'],self.features)
        self.assertTrue(any(t['from_edge']=='w10_s0_f' and t['to_edge']=='w20_s0_f' for t in turns))
        self.assertEqual(d[0]['reason'],'NORMALIZED_VIA_NODE')

    def test_only_turn_mapping(self):
        self.relation('only_right_turn');b=self.graph()
        turns,_=apply_turns(b['graph'],b['edge_sources'],b['edge_rules'],self.features)
        self.assertTrue(any(t['from_edge']=='w10_s0_f' and t['to_edge']=='w10_s1_f' for t in turns))
        self.assertFalse(any(t['from_edge']=='w10_s0_f' and t['to_edge']=='w20_s0_f' for t in turns))

    def test_turn_exception(self):
        self.relation('no_left_turn',**{'except':'motorcycle'});b=self.graph()
        turns,d=apply_turns(b['graph'],b['edge_sources'],b['edge_rules'],self.features)
        self.assertEqual(turns,[]);self.assertEqual(d[0]['reason'],'MOTORCYCLE_EXEMPT')

    def test_via_way_quarantined_not_ignored(self):
        self.relation('no_left_turn',via={'type':'way','ref':20,'role':'via'});b=self.graph()
        turns,d=apply_turns(b['graph'],b['edge_sources'],b['edge_rules'],self.features)
        self.assertEqual(turns,[])
        self.assertEqual(d[0]['reason'],'UNRESOLVED_TURN_QUARANTINE')
        self.assertTrue(all(r['allowed'] is None for r in b['edge_rules'].values()))

    def test_conditional_turn_quarantined(self):
        self.relation('no_left_turn',**{'restriction:conditional':'no_left_turn @ (Mo-Fr)'});b=self.graph()
        _,d=apply_turns(b['graph'],b['edge_sources'],b['edge_rules'],self.features)
        self.assertTrue(d[0]['conditional'])

    def test_no_u_turn_does_not_block_forward_continuation(self):
        self.relation('no_u_turn')
        self.features['payload']['elements'][0]['members'][-1]['ref']=10
        b=self.graph();turns,_=apply_turns(b['graph'],b['edge_sources'],b['edge_rules'],self.features)
        pairs={(t['from_edge'],t['to_edge']) for t in turns}
        self.assertIn(('w10_s0_f','w10_s0_r'),pairs)
        self.assertNotIn(('w10_s0_f','w10_s1_f'),pairs)

    def test_graph_diagnostics_do_not_repair_gaps(self):
        b=self.graph();before=deepcopy(b['graph'])
        d=graph_diagnostics(b['graph'],b['edge_rules'],10)
        self.assertEqual(before,b['graph']);self.assertEqual(d['weak_components'],1)

    def test_supplement_filter_retains_motorcar_exception_and_paths(self):
        q=build_queries([106,-7,107,-6],self.p)
        self.assertIn('motorcar',q['roads']);self.assertIn('track|path',q['roads'])
        self.assertIn('restriction',q['features']);self.assertIn('barrier',q['features'])


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.p=get_config();self.f={'policy':self.p,'analysis_run_id':'synthetic','reference_metric_bbox':[-2000,-2000,2000,2000]}
        self.features={'status':'SUCCEEDED','payload':{'elements':[]}}
        e={'edge_id':'w1_s0_f','u':'a','v':'b','key':'0','length_m':100.0,'travel_time_s':100/(7*1000/3600),
           'highway':'residential','service':None,'access_allowed':True,'geometry':{'type':'LineString','coordinates':[[0,0],[100,0]]}}
        self.base={'graph':{'schema_version':'li_directed_graph_v1','graph_id':'synthetic','directed':True,'crs':'EPSG:32748',
            'units':{'coordinates':'m','distance':'m','travel_time':'s'},'coverage':{'bbox':[-2000,-2000,2000,2000],'completeness':'COMPLETE','scope':'fixture'},
            'provenance':{'origin':'SYNTHETIC_FIXTURE','source_version':'1','source_as_of':None,'description':'fixture'},
            'nodes':[{'node_id':'a','x':0.0,'y':0.0},{'node_id':'b','x':100.0,'y':0.0}], 'edges':[e]},
            'edge_sources':{'w1_s0_f':{'osm_way_id':1,'segment_index':0,'direction':'f','raw_tags':{'highway':'residential'}}},
            'edge_rules':{'w1_s0_f':{'allowed':True,'raw_tags':{},'evidence_refs':['fixture']}}}
        self.metrics={'target_xy':[90,10],'all_buildings':[{'building_id':'b1','metric_geometry':{'type':'Polygon','coordinates':[[[40,20],[50,20],[50,30],[40,30],[40,20]]]}}],
                      'selected_buildings':[{'building_id':'b1','representative_point_m':[45,25]}]}

    def test_projection_splits_edge_and_counts_partial_road_in_network(self):
        r=generate_connectors(self.base,self.metrics,self.features,self.f)
        self.assertEqual(len(r['connectors']),2)
        self.assertGreater(len(r['graph']['edges']),1)
        self.assertAlmostEqual(sum(e['length_m'] for e in r['graph']['edges']),100)
        self.assertTrue(all(c['status']=='OWNER_ASSUMPTION' for c in r['connectors']))

    def test_candidate_distance_boundary(self):
        self.metrics['selected_buildings'][0]['representative_point_m']=[45,125]
        r=generate_connectors(self.base,self.metrics,self.features,self.f)
        self.assertTrue(any(c['kind']=='BUILDING' for c in r['connectors']))
        self.metrics['selected_buildings'][0]['representative_point_m']=[45,125.0001]
        r=generate_connectors(self.base,self.metrics,self.features,self.f)
        self.assertFalse(any(c['kind']=='BUILDING' for c in r['connectors']))

    def test_unbounded_target_snap_not_capped_at125(self):
        self.metrics['target_xy']=[1000,50]
        r=generate_connectors(self.base,self.metrics,self.features,self.f)
        self.assertGreater(next(c['connector_distance_m'] for c in r['connectors'] if c['kind']=='TARGET'),125)

    def test_bridge_cannot_be_direct_entrance(self):
        self.base['edge_sources']['w1_s0_f']['raw_tags']['bridge']='yes'
        r=generate_connectors(self.base,self.metrics,self.features,self.f)
        self.assertEqual(r['connectors'],[])
        self.assertTrue(any('GRADE' in c['reason'] for c in r['rejected_candidates']))

    def test_determinism_and_no_input_mutation(self):
        before=deepcopy(self.base)
        a=generate_connectors(self.base,self.metrics,self.features,self.f)
        b=generate_connectors(self.base,self.metrics,self.features,self.f)
        self.assertEqual(a,b);self.assertEqual(before,self.base)


class BarrierTests(unittest.TestCase):
    def test_water_blocks_offroad_connector(self):
        from shapely import STRtree
        water=LineString([(0,-1),(0,1)])
        index={'tree':STRtree([water]),'shapes':[water],'records':[{'kind':'water','source':'fixture'}],'open_gates':[],'unresolved':[]}
        self.assertFalse(check_barriers(LineString([(-1,0),(1,0)]),index,1e-6)[0])

    def test_open_gate_does_not_cancel_water(self):
        from shapely import STRtree
        from shapely.geometry import Point
        wall=LineString([(0,-1),(0,1)])
        index={'tree':STRtree([wall]),'shapes':[wall],'records':[{'kind':'barrier','source':'fixture'}],'open_gates':[Point(0,0)],'unresolved':[]}
        self.assertTrue(check_barriers(LineString([(-1,0),(1,0)]),index,1e-6)[0])
        index['records'][0]['kind']='water'
        self.assertFalse(check_barriers(LineString([(-1,0),(1,0)]),index,1e-6)[0])

    def test_unresolved_barrier_stays_unknown(self):
        from shapely import STRtree
        index={'tree':STRtree([]),'shapes':[],'records':[],'open_gates':[],'unresolved':[{'source':'missing'}]}
        self.assertIsNone(check_barriers(LineString([(-1,0),(1,0)]),index,1e-6)[0])


class HTTPTests(unittest.TestCase):
    class Response:
        def __init__(self,status,value):self.status_code=status;self.data=canonical_bytes(value)
        def iter_content(self,n):yield self.data
        def close(self):pass
    class Session:
        def __init__(self,response):self.response=response
        def post(self,*a,**kw):return self.response
    def test_successful_empty_not_failure(self):
        r=acquire_overpass('query',['https://fixture'],1,10000,self.Session(self.Response(200,{'elements':[],'osm3s':{}})))
        self.assertEqual(r['status'],'SUCCEEDED');self.assertEqual(r['payload']['elements'],[])
    def test_failure_not_successful_zero(self):
        r=acquire_overpass('query',['https://fixture'],1,10000,self.Session(self.Response(503,{})))
        self.assertEqual(r['status'],'RETRIEVAL_FAILED');self.assertIsNone(r['payload'])
    def test_server_partial_remark_not_empty_success(self):
        r=acquire_overpass('q',['https://fixture'],1,10000,self.Session(self.Response(200,{'elements':[],'osm3s':{},'remark':'timeout'})))
        self.assertEqual(r['status'],'RETRIEVAL_FAILED')
    def test_byte_budget_failure_explicit(self):
        r=acquire_overpass('q',['https://fixture'],1,1,self.Session(self.Response(200,{'elements':[],'osm3s':{}})))
        self.assertEqual(r['status'],'RETRIEVAL_FAILED')


class RoutingIndexTests(unittest.TestCase):
    def test_index_matches_forward_search_with_turns_and_ties(self):
        for seed in range(8):
            rng=random.Random(seed);edges=[]
            for a in range(6):
                for b in range(6):
                    if a!=b and rng.random()<.4:
                        edges.append({'edge_id':f'e{a}_{b}','u':str(a),'v':str(b),'length_m':float(rng.randrange(4))})
            graph={'nodes':[{'node_id':str(i)} for i in range(6)],'edges':edges};allowed={e['edge_id']:True for e in edges}
            blocked={(a['edge_id'],b['edge_id']) for a in edges for b in edges if a['v']==b['u'] and rng.random()<.2}
            for target in map(str,range(6)):
                index=_path_index(graph,allowed,blocked,target)
                for start in map(str,range(6)):
                    self.assertEqual(index(start),_path(graph,allowed,blocked,start,target))

    def test_unrelated_unknown_does_not_make_known_disconnect_uncertain(self):
        from location_intelligent_motor_routing import _potential_reachability
        g={'edges':[{'edge_id':'a','u':'A','v':'B','length_m':1}, {'edge_id':'x','u':'X','v':'Y','length_m':1}]}
        can_reach=_potential_reachability(g,{'a':True,'x':None},set(),'B')
        self.assertTrue(can_reach('A'));self.assertFalse(can_reach('X'))


class ManifestTests(unittest.TestCase):
    def test_checksum_change_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=b'{}';(root/'a.json').write_bytes(data)
            write_json(root/'manifest.json',{'files':[{'path':'a.json','bytes':2,'sha256':hashlib.sha256(data).hexdigest()}]})
            verify_manifest(root)
            (root/'a.json').write_bytes(b'[]')
            with self.assertRaises(ValueError):verify_manifest(root)


class DecisionStateTests(unittest.TestCase):
    def test_connector_unknown_no_route_and_measured_outcomes_separate(self):
        selection={'selected':[{'building_id':x,'source_row_index':i} for i,x in enumerate(['a','b','c','d','e'])],'reject_ledger':[]}
        routing={'status':'PARTIAL','routes':[
            {'building_id':'a','route_found':True,'scenario_accessible':True,'reason':'WITHIN'},
            {'building_id':'b','route_found':True,'scenario_accessible':False,'reason':'OVER'},
            {'building_id':'c','route_found':False,'scenario_accessible':False,'reason':'NO_PATH'},
            {'building_id':'d','route_found':None,'scenario_accessible':None,'reason':'UNKNOWN'},
            {'building_id':'e','route_found':None,'scenario_accessible':None,'reason':'NO_CONNECTOR'}]}
        package={'connectors':[{'building_id':x} for x in ['a','b','c','d']],'rejected_candidates':[]}
        rows=map_decisions(selection,routing,package)
        self.assertEqual([r['decision_state'] for r in rows],['ACCEPTED','OVER_TIME_LIMIT','NO_ROUTE','ACCESS_UNVERIFIED','NO_VALID_CONNECTOR'])

    def test_invalid_data_not_selection_exclusion(self):
        selection={'selected':[],'reject_ledger':[
            {'building_id':'a','source_row_index':0,'disposition':'REJECTED','stage':'GEOMETRY','code':'INVALID'},
            {'building_id':'b','source_row_index':1,'disposition':'REJECTED','stage':'PAYLOAD','code':'INVALID'},
            {'building_id':'c','source_row_index':2,'disposition':'EXCLUDED','stage':'SELECTION','code':'OUTSIDE'}]}
        rows=map_decisions(selection,{'status':'SUCCEEDED','routes':[]},{})
        self.assertEqual([r['decision_state'] for r in rows],['INVALID_GEOMETRY','PROCESSING_ERROR','EXCLUDED_BY_SELECTION'])
    def test_missing_file_not_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_json(root/'manifest.json',{'files':[{'path':'missing','bytes':0,'sha256':'0'*64}]})
            with self.assertRaises(ValueError):verify_manifest(root)
    def test_round_boundary_explicit(self):
        self.assertEqual([round(x)<=10 for x in [9.8,10.49,10.5,10.51]],[True,True,True,False])
    def test_unlisted_artifact_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'a').write_text('x');write_json(root/'manifest.json',{'files':[]})
            with self.assertRaises(ValueError):verify_manifest(root)
    def test_dependency_cycle_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rows=[]
            for name,other in [('a','b'),('b','a')]:
                (root/name).write_text('x');rows.append({'path':name,'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest(),'dependencies':[other]})
            write_json(root/'manifest.json',{'files':rows})
            with self.assertRaises(ValueError):verify_manifest(root)


if __name__=='__main__':unittest.main()
