from copy import deepcopy
import json
from pathlib import Path
import unittest

from location_intelligent_config import get_config
from location_intelligent_motor_routing import motor_access, route_motor_buildings
from location_intelligent_validator import canonical_hash

try:
    from pyproj import Transformer
    GEO = True
except ImportError:
    GEO = False

REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(GEO, 'Use system Python with PyProj/GDAL')
class MotorRoutingTests(unittest.TestCase):
    def setUp(self):
        self.root = REPO / 'notebooks/fixtures/li1'
        self.c = json.loads((self.root / 'context.json').read_text())
        self.m = json.loads((self.root / 'manifest.json').read_text())
        self.b = json.loads((REPO / 'docs/evidence/location_intelligent/li01_20261022/li1_fixture_result.json').read_text())
        self.g = json.loads((REPO / 'notebooks/fixtures/li2/graph.json').read_text())
        self.p = get_config()
        self.g['edges'][0]['highway'] = 'primary'
        self.g['edges'][1]['highway'] = 'service'
        self.g['edges'][2]['highway'] = 'service'
        nodes = {n['node_id']: [n['x'], n['y']] for n in self.g['nodes']}
        t = Transformer.from_crs(4326, self.g['crs'], always_xy=True)
        tx = list(t.transform(self.c['target']['longitude'], self.c['target']['latitude']))
        self.e = {'schema_version': 'li_motor_evidence_v1', 'restrictions_complete': True,
                  'edge_rules': {e['edge_id']: {'allowed': True, 'evidence_refs': ['SYNTHETIC_FIXTURE_ONLY'], 'raw_tags': {'motorcycle': 'yes'}} for e in self.g['edges']},
                  'blocked_turns': [], 'connectors': []}
        for b in self.b['selected']:
            start = list(t.transform(*b['representative_point']['coordinates']))
            for suffix, node, edge in [('high', 'A', 'access-AB'), ('low', 'B', 'network-BT-fast')]:
                self.e['connectors'].append({'connector_id': b['building_id'] + suffix, 'building_id': b['building_id'],
                    'kind': 'BUILDING', 'node_id': node, 'road_edge_id': edge,
                    'status': 'VERIFIED', 'barrier_clear': True, 'evidence_refs': ['SYNTHETIC_FIXTURE_ONLY'],
                    'geometry': {'type': 'LineString', 'coordinates': [start, nodes[node]]}})
        self.e['connectors'].append({'connector_id': 'target', 'kind': 'TARGET', 'node_id': 'T',
            'road_edge_id': 'network-BT-fast', 'status': 'OWNER_ASSUMPTION', 'barrier_clear': True,
            'evidence_refs': ['SYNTHETIC_FIXTURE_ONLY'], 'geometry': {'type': 'LineString', 'coordinates': [nodes['T'], tx]}})

    def run_motor(self, bind=True):
        if bind:
            self.e.update(graph_hash=canonical_hash(self.g), selection_hash=canonical_hash(self.b),
                          context_hash=self.c['context_hash'], policy_hash=canonical_hash(self.p))
        return route_motor_buildings(self.c, self.m, self.b, self.g, self.e, root=self.root, policy=self.p)

    def test_high_class_beats_faster_low_class_and_reconciles(self):
        r = self.run_motor()
        self.assertEqual(r['status'], 'SUCCEEDED', r)
        self.assertEqual(r['summary']['accounted'], 5)
        first = r['routes'][0]
        self.assertEqual(first['selected_candidate']['class_rank'], 0)
        self.assertGreater(first['selected_candidate']['total_time_min'], min(c['total_time_min'] for c in first['candidates']))
        self.assertEqual(r['provenance']['effective_policy'], self.p)

    def test_unreachable_higher_class_falls_back(self):
        edge = self.g['edges'][0]
        edge['u'], edge['v'] = edge['v'], edge['u']
        edge['geometry']['coordinates'].reverse()
        r = self.run_motor()
        self.assertEqual(r['routes'][0]['selected_candidate']['class_rank'], 4, r)

    def test_network_permission_is_enforced(self):
        for key in self.e['edge_rules']:
            self.e['edge_rules'][key]['allowed'] = False
        r = self.run_motor()
        self.assertEqual(r['summary']['scenario_accepted'], 0)
        self.assertFalse(r['routes'][0]['route_found'])

    def test_turn_restrictions_apply(self):
        self.e['blocked_turns'] = [{'from_edge': 'access-AB', 'to_edge': 'network-BT-fast', 'evidence_ref': 'FIXTURE_NO_TURN'}]
        r = self.run_motor()
        self.assertEqual(r['routes'][0]['selected_candidate']['network_edges'], ['access-AB', 'network-BT-slow'])

    def test_unknown_barrier_does_not_fabricate_connector(self):
        for c in self.e['connectors']:
            c['barrier_clear'] = None
        r = self.run_motor()
        self.assertEqual(r['status'], 'PARTIAL')
        self.assertIsNone(r['routes'][0]['scenario_accessible'])
        self.assertEqual(r['summary']['not_evaluated'], 5)

    def test_target_connector_included_without_snap_limit(self):
        c = self.e['connectors'][-1]
        point = c['geometry']['coordinates'][0]
        end = c['geometry']['coordinates'][-1]
        c['geometry']['coordinates'] = [point, [point[0]+100, point[1]], end]
        r = self.run_motor()
        self.assertGreater(r['routes'][0]['selected_candidate']['target_connector_m'], 100)

    def test_incomplete_turn_coverage_blocks(self):
        self.e['restrictions_complete'] = False
        r = self.run_motor()
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertIsNone(r['summary'])

    def test_conditional_requires_resolution(self):
        self.e['edge_rules']['access-AB']['raw_tags']['motorcycle:conditional'] = 'no @ (22:00-05:00)'
        self.assertEqual(self.run_motor()['status'], 'BLOCKED')

    def test_private_prohibition_cannot_be_overridden(self):
        self.e['edge_rules']['access-AB']['raw_tags']['access'] = 'private'
        self.assertEqual(self.run_motor()['status'], 'FAILED')

    def test_evidence_stale_after_config_edit(self):
        self.run_motor()
        self.p['travel']['max_travel_min']['value'] = 9
        self.assertEqual(self.run_motor(bind=False)['status'], 'FAILED')

    def test_input_immutability_and_determinism(self):
        first = self.run_motor()
        before = deepcopy([self.c, self.m, self.b, self.g, self.e, self.p])
        self.assertEqual(first, self.run_motor())
        self.assertEqual(before, [self.c, self.m, self.b, self.g, self.e, self.p])

    def test_link_inherits_parent_rank(self):
        self.g['edges'][0]['highway'] = 'primary_link'
        self.assertEqual(self.run_motor()['routes'][0]['selected_candidate']['class_rank'], 0)

    def test_round_threshold_uses_editable_speed_and_limit(self):
        r = self.run_motor()
        distance = r['routes'][0]['selected_candidate']['total_distance_m']
        # Choose a speed yielding exactly10.5 minutes for this fixture.
        self.p['travel']['reference_constant_speed']['value'] = distance / 10.5 * 60 / 1000
        r = self.run_motor()
        value = r['routes'][0]['selected_candidate']['total_time_min']
        self.assertAlmostEqual(value, 10.5)
        self.assertEqual(r['routes'][0]['scenario_accessible'], round(value) <= 10)


class AccessTagTests(unittest.TestCase):
    def test_mode_specific_permission_overrides_general_ban(self):
        self.assertTrue(motor_access({'motor_vehicle': 'no', 'motorcycle': 'yes'}, 'path')[0])
        self.assertFalse(motor_access({'access': 'private', 'motorcycle': 'yes'}, 'service')[0])
    def test_explicit_deny_beats_alley_assumption(self):
        self.assertFalse(motor_access({'motorcycle': 'no'}, 'service')[0])

    def test_alley_assumed_but_path_requires_evidence(self):
        self.assertTrue(motor_access({}, 'service')[0])
        self.assertIsNone(motor_access({}, 'path')[0])
        self.assertTrue(motor_access({'motorcycle': 'yes'}, 'path')[0])


if __name__ == '__main__':
    unittest.main()
