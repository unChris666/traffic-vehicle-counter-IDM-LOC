"""Synthetic LI-2 graph/connector/policy tests. No live/physical-access claims."""
from copy import deepcopy
import contextlib
import io
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from location_intelligent_routing import (
    route_buildings, shortest_route, reference_time_pass, inside_bbox,
    within_snap_limit, classify_road, main,
)
from location_intelligent_validator import canonical_hash

try:
    from pyproj import Transformer
    from osgeo import ogr
    GEOMETRY_AVAILABLE=True
except ImportError:
    GEOMETRY_AVAILABLE=False

REPO=Path(__file__).resolve().parents[1]
FIXTURES=REPO/'notebooks/fixtures/li2'
LI1=REPO/'notebooks/fixtures/li1'
SELECTED=REPO/'docs/evidence/location_intelligent/li01_20261022/li1_fixture_result.json'


@unittest.skipUnless(GEOMETRY_AVAILABLE,'Use /usr/bin/python3 with the validated LI-1 CRS backend')
class DirectedRoutingTests(unittest.TestCase):
    def setUp(self):
        self.c=json.loads((LI1/'context.json').read_text())
        self.m=json.loads((LI1/'manifest.json').read_text())
        self.b=json.loads(SELECTED.read_text())
        self.g=json.loads((FIXTURES/'graph.json').read_text())
        self.cfg=json.loads((FIXTURES/'config.json').read_text())
        self.x,self.y=Transformer.from_crs(4326,self.g['crs'],always_xy=True).transform(self.c['target']['longitude'],self.c['target']['latitude'])

    def run_routing(self,rebind=True):
        if rebind:
            self.cfg.update(selection_hash=canonical_hash(self.b),graph_hash=canonical_hash(self.g))
        return route_buildings(self.c,self.m,self.b,self.g,self.cfg,root=LI1)

    def codes(self,r):
        return {x['code'] for x in r['diagnostics']}

    def node(self,key,x,y):
        return {'node_id':key,'x':self.x+x,'y':self.y+y}

    def edge(self,key,u,v,*,allowed=False,length=None,time=None,geometry=True,parallel='0'):
        nodes={x['node_id']:x for x in self.g['nodes']}
        coords=[[nodes[u]['x'],nodes[u]['y']],[nodes[v]['x'],nodes[v]['y']]]
        d=math.dist(*coords) if length is None else length
        return {'edge_id':key,'u':u,'v':v,'key':parallel,'length_m':d,'travel_time_s':d/(7*1000/3600) if time is None else time,
                'highway':'residential','service':None,'access_allowed':allowed,
                'geometry':{'type':'LineString','coordinates':coords} if geometry else None}

    def access_graph(self,reverse=False):
        self.g['nodes']=[self.node('T',0,0),self.node('P',0,20),self.node('U',100,20)]
        self.g['edges']=[self.edge('access','P','U',allowed=True)]
        self.g['edges'].append(self.edge('network','T','U') if reverse else self.edge('network','U','T'))

    def test_retained_reachable_fixture_with_open_policy_gate(self):
        r=self.run_routing(rebind=False)
        self.assertEqual(r['routing_gate'],'PASS',r)
        self.assertEqual(r['status'],'PARTIAL')
        self.assertEqual(r['accessibility_gate'],'BLOCKED')
        self.assertEqual(r['summary']['route_found'],5)
        self.assertTrue(all(x['accessible'] is None for x in r['routes']))
        self.assertEqual(r['routes'][1]['selected_candidate']['network']['edges'],['network-BT-fast'])

    def test_one_way_forward_exists_reverse_does_not(self):
        self.access_graph()
        yes=self.run_routing()['routes'][0]
        self.assertTrue(yes['route_found'])
        self.access_graph(reverse=True)
        no=self.run_routing()['routes'][0]
        self.assertFalse(no['route_found'])
        self.assertEqual(no['reason'],'NO_DIRECTED_PATH')

    def test_disconnected_component_is_not_bypassed(self):
        self.access_graph();self.g['edges']=self.g['edges'][:1]
        r=self.run_routing()
        self.assertFalse(r['routes'][0]['route_found'])
        self.assertEqual(r['routing_gate'],'PASS')
        self.assertIsNotNone(r['summary'])

    def test_parallel_edge_identity_is_preserved(self):
        r=self.run_routing()['routes'][2]['selected_candidate']['network']
        self.assertEqual(r['edges'],['network-BT-fast'])
        self.assertAlmostEqual(r['distance_m'],20)

    def test_weight_can_select_fast_or_short_route_explicitly(self):
        self.access_graph()
        self.g['edges']=[self.g['edges'][0],self.edge('long-fast','U','T',length=200,time=1),
                         self.edge('short-slow','U','T',length=110,time=100,parallel='1')]
        self.cfg['path_weight']='travel_time_s'
        self.assertEqual(self.run_routing()['routes'][0]['selected_candidate']['network']['edges'],['long-fast'])
        self.cfg['path_weight']='length_m'
        self.assertEqual(self.run_routing()['routes'][0]['selected_candidate']['network']['edges'],['short-slow'])

    def test_nearest_disconnected_access_does_not_hide_reachable_alternative(self):
        self.g['nodes']=[self.node('T',0,0),self.node('A',0,10),self.node('B',100,10),self.node('C',0,20),self.node('D',100,20)]
        self.g['edges']=[self.edge('near','A','B',allowed=True),self.edge('far','C','D',allowed=True),self.edge('network','D','T')]
        row=self.run_routing()['routes'][0]
        self.assertEqual(row['selected_candidate']['edge']['edge_id'],'far')
        self.assertTrue(any(not x['route_found'] for x in row['candidates']))

    def test_nearest_reachable_is_not_minimum_total_time(self):
        self.g['coverage']['bbox']=[self.x-2000,self.y-2000,self.x+2000,self.y+2000]
        self.g['nodes']=[self.node('T',0,0),self.node('A',0,10),self.node('B',100,10),self.node('C',0,20),self.node('D',100,20)]
        self.g['edges']=[self.edge('near','A','B',allowed=True),self.edge('far','C','D',allowed=True),
                         self.edge('slow','B','T',length=2000),self.edge('fast','D','T')]
        row=self.run_routing()['routes'][0]
        self.assertEqual(row['selected_candidate']['edge']['edge_id'],'near')
        self.assertFalse(row['reference_accessible'])
        self.assertTrue(next(c for c in row['candidates'] if c['edge']['edge_id']=='far')['reference_accessible'])

    def test_connector_cost_components_and_target_offset_are_explicit(self):
        self.access_graph()
        # Move T10m away; nearest node remains T, the actual target is unchanged.
        for n in self.g['nodes']:
            if n['node_id']=='T':n['y']+=10
        self.g['edges']=[self.edge('access','P','U',allowed=True),self.edge('network','U','T')]
        row=self.run_routing()['routes'][0];c=row['selected_candidate'];t=row['target_connection']
        self.assertAlmostEqual(t['snap_distance_m'],10,places=5)
        self.assertFalse(t['connector_included_in_reference'])
        self.assertAlmostEqual(c['total_road_distance_m'],c['building_connector_distance_m']+c['partial_edge_distance_m']+c['network']['distance_m'])
        self.assertAlmostEqual(c['diagnostic_distance_including_target_m']-c['total_road_distance_m'],10,places=5)
        self.assertAlmostEqual(c['total_reference_time_min'],c['total_road_distance_m']/(7*1000/3600)/60)

    def test_forbidden_or_unknown_connectors_are_not_accepted(self):
        for value in [False,None]:
            with self.subTest(value=value):
                for e in self.g['edges']:e['access_allowed']=value
                row=self.run_routing()['routes'][0]
                self.assertEqual(row['reason'],'CONNECTOR_VALIDATION_FAILED')
                self.assertFalse(row['route_found'])

    def test_road_class_filters_only_access_not_network_topology(self):
        self.access_graph();self.g['edges'][1]['highway']='service'
        self.assertTrue(self.run_routing()['routes'][0]['route_found'])
        self.g['edges'][0]['highway']='footway'
        row=self.run_routing()['routes'][0]
        self.assertEqual(row['reason'],'NO_ELIGIBLE_ACCESS')

    def test_missing_network_geometry_is_not_invented(self):
        self.access_graph();self.g['edges'][1]['geometry']=None
        row=self.run_routing()['routes'][0]
        self.assertTrue(row['route_found'])
        self.assertIsNone(row['route_geometry'])
        self.assertEqual(row['route_geometry_status'],'MISSING_NETWORK_EDGE_GEOMETRY')

    def test_access_road_geometry_missing_is_a_diagnostic(self):
        for e in self.g['edges']:e['geometry']=None;e['access_allowed']=True
        row=self.run_routing()['routes'][0]
        self.assertEqual(row['reason'],'NO_ELIGIBLE_ACCESS')
        self.assertTrue(all(d['reason']=='ACCESS_GEOMETRY_MISSING' for d in row['candidate_diagnostics']))

    def test_reversed_geometry_does_not_create_a_reverse_road(self):
        self.g['edges'][0]['geometry']['coordinates'].reverse()
        r=self.run_routing();self.assertEqual(r['status'],'FAILED')
        self.assertIn('GRAPH_EDGE_ORIENTATION',self.codes(r))

    def test_missing_or_duplicate_node_and_edge_references(self):
        for mutate,code in [(lambda:self.g['edges'][0].update(v='missing'),'GRAPH_NODE_REF_INVALID'),
            (lambda:self.g['nodes'].append(deepcopy(self.g['nodes'][0])),'GRAPH_NODE_DUPLICATE'),
            (lambda:self.g['edges'].append(deepcopy(self.g['edges'][0])),'GRAPH_EDGE_DUPLICATE')]:
            with self.subTest(code=code):
                original=deepcopy(self.g);mutate();r=self.run_routing();self.g=original
                self.assertIn(code,self.codes(r));self.assertIsNone(r['summary'])

    def test_missing_negative_nonfinite_and_bool_costs_fail_closed(self):
        for val in [None,-1,True,'100']:
            with self.subTest(cost=val):
                self.g['edges'][0]['length_m']=val
                r=self.run_routing();self.assertIn('GRAPH_COST_INVALID',self.codes(r))
        self.g['edges'][0]['length_m']=float('nan')
        self.assertEqual(self.run_routing(rebind=False)['status'],'FAILED')

    def test_units_crs_schema_and_directed_flags(self):
        for key,value,code in [('directed',False,'GRAPH_NOT_DIRECTED'),('crs','EPSG:4326','GRAPH_CRS_MISMATCH'),
                               ('units',{'distance':'km'},'GRAPH_UNITS_INVALID'),('schema_version','other','GRAPH_SCHEMA_UNSUPPORTED')]:
            original=self.g[key];self.g[key]=value
            self.assertIn(code,self.codes(self.run_routing()));self.g[key]=original

    def test_invalid_coverage_or_geometry_is_not_a_no_path_result(self):
        self.g['coverage']['bbox']=[0,0,0,0]
        r=self.run_routing();self.assertEqual(r['status'],'FAILED');self.assertIsNone(r['summary'])

    def test_building_outside_coverage_is_not_snapped_into_graph(self):
        self.g['nodes']=[self.node('T',0,0)]
        self.g['edges']=[];self.g['coverage']['bbox']=[self.x-25,self.y-25,self.x+25,self.y+25]
        row=self.run_routing()['routes'][1]
        self.assertEqual(row['reason'],'BUILDING_OUTSIDE_COVERAGE');self.assertIsNone(row['route_found'])

    def test_target_outside_coverage_is_not_snapped_into_graph(self):
        self.g['nodes']=[self.node('T',200,0)];self.g['edges']=[]
        self.g['coverage']['bbox']=[self.x+100,self.y-50,self.x+300,self.y+50]
        row=self.run_routing()['routes'][0]
        self.assertEqual(row['reason'],'TARGET_OUTSIDE_COVERAGE');self.assertIsNone(row['route_found'])

    def test_snap_limit_and_unknown_snap_policy_are_explicit(self):
        self.g['nodes']=[self.node('T',51,0)];self.g['edges']=[]
        row=self.run_routing()['routes'][0]
        self.assertEqual(row['reason'],'TARGET_SNAP_LIMIT_EXCEEDED')
        self.cfg['parameters']['max_target_snap_m'].update(value=None,unknown_reason='D05 unresolved')
        row=self.run_routing()['routes'][0]
        self.assertEqual(row['reason'],'TARGET_SNAP_POLICY_UNRESOLVED')

    def test_no_nearby_road_is_distinct_from_nearby_connector_denial(self):
        self.g['nodes']=[self.node('T',0,0),self.node('A',200,200),self.node('B',300,200)]
        self.g['edges']=[self.edge('far','A','B',allowed=False)]
        row=self.run_routing()['routes'][0]
        self.assertEqual(row['reason'],'NO_ELIGIBLE_ACCESS')
        self.assertEqual(row['candidate_diagnostics'][0]['reason'],'ACCESS_DISTANCE_EXCEEDED')

    def test_route_found_and_reference_time_gate_are_separate(self):
        for time,want in [(9.999,True),(10,False),(10.001,False)]:
            with self.subTest(time=time):
                self.access_graph()
                edge=self.g['edges'][1]
                edge['length_m']=time*60*(7*1000/3600)-120
                edge['travel_time_s']=edge['length_m']/(7*1000/3600)
                row=self.run_routing()['routes'][0]
                self.assertTrue(row['route_found'])
                self.assertEqual(row['reference_accessible'],want)
                self.assertIsNone(row['accessible'])

    def test_finite_costs_whose_sum_overflows_are_invalid(self):
        for edge in self.g['edges']:edge['length_m']=1e308;edge['travel_time_s']=1e308
        r=self.run_routing()
        self.assertEqual(r['status'],'FAILED');self.assertIn('GRAPH_COST_UNUSABLE',self.codes(r))

    def test_wrong_nested_input_types_return_diagnostics_not_exceptions(self):
        mutations=[('g','nodes'),('g','edges'),('g','coverage'),('g','provenance'),('g','units'),
                   ('g','nodes.0'),('g','nodes.0.node_id'),('g','edges.0'),('g','edges.0.u'),
                   ('g','edges.0.geometry'),('g','edges.0.geometry.coordinates'),
                   ('cfg','parameters'),('cfg','policy_refs'),('cfg','parameters.max_travel_min'),
                   ('b','selected'),('b','selected.0'),('b','selected.0.representative_point'),
                   ('b','snapshot'),('b','snapshot.fingerprint'),('b','summary'),('b','reject_ledger')]
        before=deepcopy((self.g,self.cfg,self.b))
        for attr,path in mutations:
            for bad in [None,True,[],{},'bad']:
                with self.subTest(attr=attr,path=path,bad=bad):
                    self.g,self.cfg,self.b=deepcopy(before)
                    obj=getattr(self,attr);parts=path.split('.')
                    for part in parts[:-1]:obj=obj[int(part)] if isinstance(obj,list) else obj[part]
                    obj[int(parts[-1]) if isinstance(obj,list) else parts[-1]]=bad
                    r=self.run_routing()
                    # Both are explicitly valid contract states, rather than
                    # malformed types: an empty edge array and unknown geometry.
                    if (attr=='g' and path=='edges' and bad==[]) or (attr=='g' and path=='edges.0.geometry' and bad is None):
                        self.assertEqual(r['routing_gate'],'PASS')
                    else:
                        self.assertIn(r['status'],{'FAILED','BLOCKED'})
                    json.dumps(r,allow_nan=False)

    def test_empty_graph_is_available_not_missing_or_failed(self):
        self.g['nodes']=[];self.g['edges']=[]
        r=self.run_routing();self.assertEqual(r['routing_gate'],'PASS')
        self.assertEqual(r['summary']['no_route'],5)
        self.assertTrue(all(x['reason']=='EMPTY_GRAPH' for x in r['routes']))
        self.g=None
        r=route_buildings(self.c,self.m,self.b,None,self.cfg,root=LI1)
        self.assertEqual(r['status'],'BLOCKED');self.assertIsNone(r['summary'])

    def test_hashes_context_and_selection_are_bound(self):
        self.cfg['graph_hash']='0'*64
        self.assertIn('ROUTING_HASH_MISMATCH',self.codes(self.run_routing(rebind=False)))
        self.cfg['analysis_run_id']='different'
        self.assertIn('ROUTING_CONTEXT_MISMATCH',self.codes(self.run_routing()))

    def test_changed_n1_threshold_or_forged_approval_is_not_silently_applied(self):
        self.cfg['parameters']['max_travel_min']['value']=7
        self.assertIn('REFERENCE_CONTROL_CHANGED',self.codes(self.run_routing()))
        self.cfg['parameters']['max_travel_min']['value']=10
        self.cfg['approved']=True
        r=self.run_routing();self.assertIn('FIELD_UNKNOWN',self.codes(r))
        self.assertNotEqual(r['accessibility_gate'],'PASS')

    def test_selected_record_must_match_its_context_and_source(self):
        self.b['selected'][0]['source_ref_id']='another'
        self.assertIn('BUILDING_RECORD_BINDING',self.codes(self.run_routing()))

    def test_route_geometry_comes_from_stored_forward_edges(self):
        row=self.run_routing()['routes'][1]
        self.assertEqual(row['route_geometry_status'],'AVAILABLE_ROAD_GEOMETRY')
        self.assertEqual(row['route_geometry_crs'],'EPSG:4326')
        lon,lat=row['route_geometry']['coordinates'][-1]
        self.assertAlmostEqual(lon,self.c['target']['longitude'],places=9)
        self.assertAlmostEqual(lat,self.c['target']['latitude'],places=9)
        self.assertEqual(row['selected_candidate']['road_coordinates_m'][-1],[self.x,self.y])
        self.assertEqual(row['selected_candidate']['network']['nodes'],['B','T'])

    def test_determinism_input_nonmutation_and_count_reconciliation(self):
        old=deepcopy((self.c,self.m,self.b,self.g,self.cfg))
        a=self.run_routing(rebind=False);b=self.run_routing(rebind=False)
        self.assertEqual(a,b);self.assertEqual(old,(self.c,self.m,self.b,self.g,self.cfg))
        s=a['summary'];self.assertEqual(s['route_found']+s['no_route']+s['not_evaluated'],s['input_selected_buildings'])
        self.assertEqual(sum(s['reason_counts'].values()),len(a['routes']))
        self.assertIsNone(s['accepted_accessible'])

    def test_node_and_edge_array_order_do_not_choose_another_route(self):
        before=self.run_routing()['routes']
        self.g['nodes'].reverse();self.g['edges'].reverse()
        self.assertEqual(before,self.run_routing()['routes'])

    def test_no_network_no_writes_and_no_dataset_open(self):
        with patch.object(socket,'socket',side_effect=AssertionError('No network')),patch.object(ogr,'Open',side_effect=AssertionError('No dataset driver')),patch.object(Path,'write_text',side_effect=AssertionError('No write')):
            self.assertEqual(self.run_routing()['routing_gate'],'PASS')

    def test_cli_without_inherited_credentials(self):
        cmd=[sys.executable,'-B',str(REPO/'notebooks/location_intelligent_routing.py'),
             '--context',str(LI1/'context.json'),'--manifest',str(LI1/'manifest.json'),
             '--buildings',str(SELECTED),'--graph',str(FIXTURES/'graph.json'),
             '--config',str(FIXTURES/'config.json'),'--root',str(LI1)]
        r=subprocess.run(cmd,capture_output=True,text=True,env={'PROJ_NETWORK':'OFF','PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(r.returncode,3,r.stderr)
        self.assertEqual(json.loads(r.stdout)['routing_gate'],'PASS')

    def test_cli_reports_missing_graph_as_unavailable(self):
        with tempfile.TemporaryDirectory() as root:
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                code=main(['--context',str(LI1/'context.json'),'--manifest',str(LI1/'manifest.json'),
                           '--buildings',str(SELECTED),'--graph',str(Path(root)/'absent.json'),
                           '--config',str(FIXTURES/'config.json'),'--root',str(LI1)])
            self.assertEqual(code,2)
            r=json.loads(output.getvalue());self.assertIsNone(r['summary'])
            self.assertEqual(r['diagnostics'][0]['code'],'INPUT_UNAVAILABLE')

    def test_partial_coverage_is_explicit_not_real_world_approval(self):
        self.g['coverage']['completeness']='PARTIAL'
        r=self.run_routing()
        self.assertEqual(r['routing_gate'],'PASS')
        self.assertTrue(all(x['coverage_status']=='PARTIAL' for x in r['routes']))
        self.assertIsNone(r['summary']['accepted_accessible'])


class PureDirectedGraphTests(unittest.TestCase):
    def graph(self,edges):
        ids=sorted({n for _,u,v,_,_ in edges for n in (u,v)})
        return {'nodes':[{'node_id':x} for x in ids], 'edges':[{'edge_id':key,'u':u,'v':v,'length_m':d,'travel_time_s':t} for key,u,v,d,t in edges]}

    def test_forward_only_and_unreachable(self):
        g=self.graph([('a','A','B',10,5)])
        self.assertEqual(shortest_route(g,'A','B')['edges'],['a'])
        self.assertIsNone(shortest_route(g,'B','A'))

    def test_equal_cost_tie_is_fewest_hops_then_lexicographic_edge_ids(self):
        g=self.graph([('b','A','B',1,1),('c','B','T',1,1),('a','A','C',1,1),('d','C','T',1,1)])
        self.assertEqual(shortest_route(g,'A','T')['edges'],['a','d'])
        g['edges'].reverse()
        self.assertEqual(shortest_route(g,'A','T')['edges'],['a','d'])
        g['edges'].append({'edge_id':'z','u':'A','v':'T','length_m':2,'travel_time_s':2})
        self.assertEqual(shortest_route(g,'A','T')['edges'],['z'])

    def test_parallel_edges_and_zero_cycles(self):
        g=self.graph([('slow','A','T',10,10),('fast','A','T',20,1),('zero','A','B',0,0),('back','B','A',0,0)])
        self.assertEqual(shortest_route(g,'A','T')['edges'],['fast'])
        self.assertEqual(shortest_route(g,'A','T','length_m')['edges'],['slow'])

    def test_exact_closed_coverage_and_snap_boundaries(self):
        for p,want in [([0,0],True),([10,10],True),([10.0001,5],False)]:self.assertEqual(inside_bbox(p,[0,0,10,10]),want)
        self.assertTrue(within_snap_limit(50,50));self.assertFalse(within_snap_limit(50.0001,50))

    def test_time_threshold_rounding_and_strictness(self):
        for val,want in [(9.9989,True),(9.999,True),(9.9996,False),(10,False),(10.0001,False)]:
            with self.subTest(value=val):self.assertEqual(reference_time_pass(val,10),want)

    def test_road_taxonomy_matches_reference_access_filter(self):
        for h,s,want in [('residential',None,'street'),('secondary',None,'main street'),('trunk',None,'highway'),('service',None,'gang'),('residential','driveway','gang')]:self.assertEqual(classify_road(h,s),want)


if __name__=='__main__':unittest.main()
