"""Meaningful failure, reconciliation, and offline persistence regressions for LI-4."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import location_intelligent_li4 as li4
from location_intelligent_li3_sources import read_json, write_json


def rehash(root):
    root = Path(root)
    manifest = read_json(root/'manifest.json') if (root/'manifest.json').exists() else {'schema_version': 'li3_manifest_v1'}
    manifest['files'] = [{'path': str(p.relative_to(root)), 'bytes': p.stat().st_size,
        'sha256': li4.digest(p), 'dependencies': []}
        for p in sorted(root.rglob('*')) if p.is_file() and p != root/'manifest.json']
    write_json(root/'manifest.json', manifest)


def fixture(root):
    """Four synthetic source records, three units, missing capacity, and an over-time route."""
    features, selected, decisions, caps, routes, connectors = [], [], [], [], [], []
    outcomes = ['ACCEPTED', 'ACCESS_UNVERIFIED', 'OVER_TIME_LIMIT', 'EXCLUDED_BY_SELECTION']
    units = ['OCCUPIED_ROOMS_ESTIMATED', 'GUESTS_ESTIMATED', 'N1_STANDARD_VALUE_UNIT_UNRESOLVED']
    for i, state in enumerate(outcomes):
        bid = 'building-'+str(i)
        geometry = {'type': 'Polygon', 'coordinates': [[[106+i*.001,-6],[106.0001+i*.001,-6],
            [106.0001+i*.001,-6.0001],[106+i*.001,-6.0001],[106+i*.001,-6]]]}
        features.append({'type': 'Feature', 'properties': {'building_id': bid}, 'geometry': geometry})
        candidate = {'building_connector_id': 'b'+str(i), 'target_connector_id': 'target',
            'network_edges': ['e'], 'total_time_min': 5.25 if i==0 else 10.6,
            'threshold_time_min': 5 if i==0 else 11} if i in (0,2) else None
        decisions.append({'source_row_index': i, 'building_id': bid,
            'selection_status': 'SELECTED' if i<3 else 'EXCLUDED', 'decision_state': state,
            'reason': 'EVIDENCE_INCOMPLETE' if i==1 else 'SYNTHETIC', 'selected_candidate': candidate})
        if i>=3:
            continue
        selected.append({'building_id': bid, 'area_m2': 60})
        caps.append({'building_id': bid, 'unit': units[i], 'capacity_reference_rounded': None if i==1 else 4})
        routes.append({'building_id': bid, 'selected_candidate': candidate,
            'route_found': None if i==1 else True, 'scenario_accessible': None if i==1 else i==0})
        connectors.append({'connector_id': 'b'+str(i), 'building_id': bid, 'node_id': 'n1',
            'geometry': {'type': 'LineString', 'coordinates': [[106,-6],[106.001,-6]]}})
    connectors.append({'connector_id': 'target', 'kind': 'TARGET', 'node_id': 'n2',
        'geometry': {'type': 'LineString', 'coordinates': [[106.002,-6],[106.003,-6]]}})
    report = {'source_records': 4, 'selected_buildings': 3, 'all_source_rows_accounted': 4,
        'status': 'PARTIAL', 'analysis_run_id': 'SYNTHETIC_ONLY',
        'decision_counts_selected': {'ACCEPTED': 1, 'ACCESS_UNVERIFIED': 1, 'OVER_TIME_LIMIT': 1},
        'capacity_by_decision_state_and_unit': {
            'ACCEPTED': {units[0]: {'buildings': 1, 'known_subtotal': 4, 'unknown_buildings': 0}},
            'ACCESS_UNVERIFIED': {units[1]: {'buildings': 1, 'known_subtotal': 0, 'unknown_buildings': 1}},
            'OVER_TIME_LIMIT': {units[2]: {'buildings': 1, 'known_subtotal': 4, 'unknown_buildings': 0}}},
        'source_warnings': [{'code':'SYNTHETIC'}], 'limitations': ['Synthetic fixture; not real access']}
    files = {'report.json': report, 'normalized/buildings.geojson': {'features': features},
        'building_results/selection.json': {'selected': selected},
        'building_results/decisions.json.gz': decisions,
        'building_results/capacity.json': {'rows': caps},
        'building_results/routing.json.gz': {'routes': routes},
        'graph/graph.json.gz': {'crs':'EPSG:4326','edges':[{'edge_id':'e','u':'n1','v':'n2',
            'access_allowed':True,'geometry':{'type':'LineString','coordinates':[[106.001,-6],[106.002,-6]]}}]},
        'connectors/connectors.json.gz': connectors,
        'connectors/rejected.json.gz': [{'building_id':'building-1','reason':'UNKNOWN_BARRIER'}],
        'normalized/context.json': {'target':{'longitude':106.003,'latitude':-6}},
        'config/pilot.json': {'policy':{'synthetic':True}}}
    for name, value in files.items():
        write_json(root/name, value)
    rehash(root)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source, self.out = self.root/'source', self.root/'output'
        fixture(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def change(self, name, fn):
        value = read_json(self.source/name); fn(value); write_json(self.source/name, value); rehash(self.source)

    def test_offline_build_and_relocated_reopen(self):
        with mock.patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')):
            receipt = li4.build(self.source, self.out)
            moved = self.root/'relocated'; self.out.rename(moved)
            with mock.patch.object(li4, 'HERE', self.root/'no-working-code-needed'):
                self.assertEqual(li4.verify(moved)['status'], 'PASS')
        self.assertEqual(receipt['source_records'],4)
        self.assertEqual(receipt['routes'],2)

    def test_archived_cli_without_bytecode_environment_is_read_only(self):
        li4.build(self.source, self.out)
        result = subprocess.run([sys.executable, str(self.out/'engine_source/location_intelligent_li4.py'),
            'verify', '--root', str(self.out)], cwd=self.root, env={'PROJ_NETWORK':'OFF'},
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'PASS')
        self.assertFalse(list(self.out.rglob('__pycache__')))

    def test_all_rows_geojson_csv_and_view_reconcile(self):
        li4.build(self.source,self.out)
        rows=read_json(self.out/'buildings.json')
        self.assertEqual([r['source_row_index'] for r in rows],list(range(4)))
        features=read_json(self.out/'buildings.geojson')['features']
        self.assertEqual([f['properties'] for f in features],rows)
        self.assertEqual((self.out/'buildings.csv').read_bytes(),li4.csv_bytes(rows))
        self.assertIn(li4.CLAIM,(self.out/'review.html').read_text())

    def test_unknown_stays_null_and_no_route(self):
        data=li4.derive(self.source)
        row=data['rows'][1]
        self.assertIsNone(row['scenario_accessible'])
        self.assertIsNone(row['capacity_reference'])
        self.assertIsNone(row['total_time_min'])
        self.assertNotIn(1,[f['id'] for f in data['routes']['features']])

    def test_over_time_route_is_retained(self):
        data=li4.derive(self.source)
        self.assertEqual(data['routes']['features'][1]['properties']['decision_state'],'OVER_TIME_LIMIT')
        self.assertEqual(data['rows'][2]['total_time_min'],10.6)
        self.assertEqual(data['rows'][2]['threshold_time_min'],11)

    def test_units_never_merged_and_missing_is_counted(self):
        s=li4.derive(self.source)['summary']
        self.assertIsNone(s['mixed_unit_total'])
        self.assertIsNone(s['final_business_capacity'])
        g=s['capacity_by_decision_state_and_unit']['ACCESS_UNVERIFIED']['GUESTS_ESTIMATED']
        self.assertEqual(g,{'buildings':1,'known_subtotal':0,'unknown_buildings':1})

    def test_missing_row_fails(self):
        self.change('building_results/decisions.json.gz',lambda v:v.pop())
        with self.assertRaisesRegex(ValueError,'reconcile'):li4.build(self.source,self.out)
        self.assertFalse(self.out.exists())

    def test_duplicate_row_fails(self):
        self.change('building_results/decisions.json.gz',lambda v:v.append(v[0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):li4.derive(self.source)

    def test_wrong_source_identity_fails(self):
        self.change('building_results/decisions.json.gz',lambda v:v[0].update(building_id='different'))
        with self.assertRaisesRegex(ValueError,'identity'):li4.derive(self.source)

    def test_no_unknown_promotion(self):
        self.change('building_results/decisions.json.gz',lambda v:v[1].update(decision_state='ACCEPTED'))
        with self.assertRaisesRegex(ValueError,'Unproven'):li4.derive(self.source)

    def test_summary_drift_fails(self):
        self.change('report.json',lambda v:v['decision_counts_selected'].update(ACCEPTED=999))
        with self.assertRaisesRegex(ValueError,'Summary'):li4.derive(self.source)

    def test_capacity_missing_identity_fails(self):
        self.change('building_results/capacity.json',lambda v:v['rows'].pop())
        with self.assertRaisesRegex(ValueError,'identities'):li4.derive(self.source)

    def test_path_discontinuity_fails(self):
        self.change('graph/graph.json.gz',lambda v:v['edges'][0].update(u='wrong'))
        with self.assertRaisesRegex(ValueError,'continuity'):li4.derive(self.source)

    def test_unknown_edge_not_rendered_as_accepted(self):
        self.change('graph/graph.json.gz',lambda v:v['edges'][0].update(access_allowed=None))
        with self.assertRaisesRegex(ValueError,'permission'):li4.derive(self.source)

    def test_candidate_mismatch_fails(self):
        self.change('building_results/routing.json.gz',lambda v:v['routes'][0]['selected_candidate'].update(total_time_min=100))
        with self.assertRaisesRegex(ValueError,'candidate mismatch'):li4.derive(self.source)

    def test_export_failure_never_publishes(self):
        with mock.patch.object(li4,'exports',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):li4.build(self.source,self.out)
        self.assertFalse(self.out.exists())
        self.assertFalse(list(self.root.glob('.output-*')))

    def test_failure_after_partial_exports_removes_staging(self):
        original = Path.write_bytes
        written = []
        def fail_on_routes(path, data):
            if path.name == 'routes.geojson':
                raise OSError('simulated partial export failure')
            written.append(path.name)
            return original(path, data)
        with mock.patch.object(Path, 'write_bytes', fail_on_routes):
            with self.assertRaises(OSError):li4.build(self.source, self.out)
        self.assertIn('buildings.csv', written)
        self.assertFalse(self.out.exists())
        self.assertFalse(list(self.root.glob('.output-*')))

    def test_final_verification_failure_never_publishes(self):
        with mock.patch.object(li4,'verify',side_effect=ValueError('final verification failed')):
            with self.assertRaises(ValueError):li4.build(self.source,self.out)
        self.assertFalse(self.out.exists())
        self.assertFalse(list(self.root.glob('.output-*')))

    def test_source_checksum_failure(self):
        (self.source/'report.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'checksum'):li4.build(self.source,self.out)
        self.assertFalse(self.out.exists())

    def test_missing_export_fails_on_reopen(self):
        li4.build(self.source,self.out);(self.out/'routes.geojson').unlink()
        with self.assertRaises(ValueError):li4.verify(self.out)

    def test_tampered_csv_fails_even_if_rehashed(self):
        li4.build(self.source,self.out);(self.out/'buildings.csv').write_text('fake')
        rehash(self.out)
        with self.assertRaisesRegex(ValueError,'reconciliation'):li4.verify(self.out)

    def test_extra_file_fails_on_reopen(self):
        li4.build(self.source,self.out);(self.out/'unlisted.txt').write_text('extra')
        with self.assertRaises(ValueError):li4.verify(self.out)

    def test_source_symlink_fails(self):
        p=self.source/'report.json';data=p.read_bytes();p.unlink()
        outside=self.root/'outside.json';outside.write_bytes(data);p.symlink_to(outside)
        with self.assertRaises(ValueError):li4.build(self.source,self.out)

    def test_refuses_overwrite_and_nested_source(self):
        li4.build(self.source,self.out)
        with self.assertRaisesRegex(ValueError,'new output'):li4.build(self.source,self.out)
        with self.assertRaisesRegex(ValueError,'separate'):li4.build(self.source,self.source/'nested')

    def test_embedded_json_script_injection_is_escaped(self):
        result=li4.html_bytes({'value':'</script><script>alert(1)</script>&'},'__LI4_PAYLOAD__')
        self.assertNotIn(b'</script>',result)
        self.assertEqual(json.loads(result),{'value':'</script><script>alert(1)</script>&'})

    def test_csv_formula_and_null(self):
        self.assertEqual(li4.csv_value('=1+1'),"'=1+1")
        self.assertEqual(li4.csv_value(None),'')
        self.assertEqual(li4.csv_value(0),'0')
        self.assertEqual(li4.csv_value(False),'false')

    def test_negative_or_nan_capacity_fails(self):
        row=li4.derive(self.source)['rows'][0]
        for value in [-1,float('nan'),True]:
            with self.subTest(value=value):
                bad={**row,'capacity_reference':value}
                with self.assertRaises(ValueError):li4.capacity_groups([bad])


if __name__=='__main__':
    unittest.main()
