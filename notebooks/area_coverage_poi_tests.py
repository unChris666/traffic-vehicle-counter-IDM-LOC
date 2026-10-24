"""Explicit synthetic boundary fixtures; not claims about actual POI inventory."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyproj import Geod
from location_intelligent_map_poi import classify_poi, normalize_pois, load_osm_pois, build_poi_query
from location_intelligent_map_pilot import bq_credentials, interactive_map, load_bq_layers


CONFIG = {'latitude': -6.409737552410453, 'longitude': 106.82835008971841,
          'poi_radius_m': 2000.0, 'poi_overpass_endpoints': ['https://example.invalid']}


def payload():
    return {'osm3s': {'timestamp_osm_base': '2026-10-24T00:00:00Z'}, 'elements': [
        {'type': 'node', 'id': 1, 'lat': CONFIG['latitude'], 'lon': CONFIG['longitude'],
         'tags': {'amenity': 'school', 'name': 'SYNTHETIC TEST FIXTURE'}}]}


class FacilityTests(unittest.TestCase):
    def test_eight_categories_and_government_precedence(self):
        tags = [{'amenity': x} for x in ['hospital', 'clinic', 'marketplace', 'police', 'school', 'university']]
        tags += [{'office': 'government'}, {'office': 'company'}]
        self.assertEqual([classify_poi(t) for t in tags],
                         ['hospital', 'clinic', 'market', 'police', 'school', 'university', 'government', 'office'])
        self.assertEqual(classify_poi({'amenity': 'townhall', 'office': 'government'}), 'government')
        self.assertIsNone(classify_poi({'building': 'hospital'}))
        self.assertIsNone(classify_poi({'office': 'vacant'}))

    def test_geodesic_final_radius_and_missing_center(self):
        p = payload()
        for index, distance in enumerate([1999.99, 2000.01], start=2):
            lon, lat, _ = Geod(ellps='WGS84').fwd(CONFIG['longitude'], CONFIG['latitude'], 30, distance)
            p['elements'].append({'type': 'node', 'id': index, 'lat': lat, 'lon': lon, 'tags': {'amenity': 'clinic'}})
        p['elements'].append({'type': 'way', 'id': 4, 'tags': {'amenity': 'university'}})
        result = normalize_pois(CONFIG, p)
        self.assertEqual(result['count'], 2)
        self.assertEqual(len(result['excluded']), 2)
        self.assertEqual(sum(result['counts_by_category'].values()), result['count'])

    def test_incomplete_source_not_valid_empty_inventory(self):
        p = payload(); p['remark'] = 'timeout'
        with self.assertRaises(ValueError):
            normalize_pois(CONFIG, p)

    def test_failed_retrieval_preserves_unknown(self):
        with tempfile.TemporaryDirectory() as d, patch('location_intelligent_map_poi.acquire_overpass',
                return_value={'status': 'RETRIEVAL_FAILED', 'attempts': []}):
            layer = load_osm_pois(CONFIG, Path(d)/'cache.data', mode='ACQUIRE_ONCE')
            self.assertEqual(layer['status'], 'FAILED')
            self.assertIsNone(layer['count'])
            self.assertFalse((Path(d)/'cache.data').exists())

    def test_frozen_reopen_never_queries_and_rejects_other_target(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d)/'cache.data'
            with patch('location_intelligent_map_poi.acquire_overpass',
                       return_value={'status': 'SUCCEEDED', 'payload': payload(), 'attempts': []}):
                original = load_osm_pois(CONFIG, cache, mode='ACQUIRE_ONCE')
            with patch('location_intelligent_map_poi.acquire_overpass', side_effect=AssertionError('network forbidden')):
                self.assertEqual(load_osm_pois(CONFIG, cache), original)
                with self.assertRaises(ValueError):
                    load_osm_pois({**CONFIG, 'longitude': 107.0}, cache)

    def test_query_contains_requested_categories_and_not_arbitrary_building(self):
        query = build_poi_query(CONFIG)
        self.assertIn('around:2100.0', query)
        self.assertIn('nwr["office"]', query)
        self.assertIn('marketplace', query)
        self.assertNotIn('["building"]', query)

    def test_named_kaggle_secret_used_without_echo(self):
        client = SimpleNamespace(get_secret=lambda name: json.dumps({'type': 'service_account'}) if name == 'LocatioIntelligent' else '')
        with patch.dict('sys.modules', {'kaggle_secrets': SimpleNamespace(UserSecretsClient=lambda: client)}), \
                patch('google.oauth2.service_account.Credentials.from_service_account_info', return_value='TEST_CREDENTIALS'):
            self.assertEqual(bq_credentials(), 'TEST_CREDENTIALS')

    def test_wrapped_secret_http_error_preserves_status_without_secret_or_message(self):
        from urllib.error import HTTPError
        error = ConnectionError('SYNTHETIC_PRIVATE_VALUE_MUST_NOT_LEAK')
        error.__cause__ = HTTPError('https://example.invalid/secret', 403, 'PRIVATE_ERROR_BODY', {}, None)
        with tempfile.TemporaryDirectory() as d, patch('location_intelligent_map_pilot.bq_credentials', side_effect=error):
            layers = load_bq_layers(CONFIG, d)
        for layer in layers.values():
            self.assertEqual(layer['error_stage'], 'KAGGLE_SECRET_READ')
            self.assertEqual(layer['error_diagnostics']['chain'][1]['http_status'], 403)
        serialized = json.dumps(layers)
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE_MUST_NOT_LEAK', serialized)
        self.assertNotIn('PRIVATE_ERROR_BODY', serialized)
        self.assertNotIn('example.invalid', serialized)

    def test_one_400m_circle_per_store_and_separate_toggle_groups(self):
        from pyproj import Transformer
        from folium import Circle
        config = {**CONFIG, 'building_radius_m': 800.0, 'metric_crs': 'EPSG:32748', 'store_buffer_radius_m': 400.0}
        x, y = Transformer.from_crs(4326, config['metric_crs'], always_xy=True).transform(config['longitude'], config['latitude'])
        sources = {'decisions.json.gz': [], 'selection.json': {'selected': []},
                   'buildings.geojson': {'features': []}, 'graph.json.gz': {'edges': [
                       {'edge_id': 'SYNTHETIC_TEST_EDGE', 'highway': 'service',
                        'geometry': {'type': 'LineString', 'coordinates': [[x, y], [x+10, y]]}}]},
                   'report.json': {'source_records': 0, 'selected_buildings': 0, 'decision_counts_selected': {}},
                   'pilot.json': {'policy': {'li3': config}},
                   'context.json': {'config': {'area_coverage': {'parameters': {'building_radius_m': {'value': 800.0}}}}}}
        layers = {kind: {'status': 'SUCCEEDED', 'table': 'SYNTHETIC_TEST_FIXTURE',
                        'request_binding': {'latitude': config['latitude'], 'longitude': config['longitude'], 'radius_m': 2000.0},
                        'rows': [{'store_id': kind, 'store_name': 'SYNTHETIC', 'latitude': config['latitude'],
                                  'longitude': config['longitude'], 'distance_m': 0.0}]}
                  for kind in ['indomaret', 'competitor']}
        with tempfile.TemporaryDirectory() as d, patch('location_intelligent_map_pilot.read_json',
                side_effect=lambda p: sources[Path(p).name]):
            map_object = interactive_map(config, d, layers, Path(d)/'test.html')
            groups = [g for g in map_object._children.values() if 'radius 400 m per toko' in getattr(g, 'layer_name', '')]
            self.assertEqual(len(groups), 2)
            for group in groups:
                circles = [child for child in group._children.values() if isinstance(child, Circle)]
                self.assertEqual(len(circles), 1)
                self.assertEqual(circles[0].options['radius'], 400.0)
                self.assertEqual(circles[0].location, [config['latitude'], config['longitude']])


if __name__ == '__main__':
    unittest.main()
