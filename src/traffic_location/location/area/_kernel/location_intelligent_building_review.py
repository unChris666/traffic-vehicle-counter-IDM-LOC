"""Read-only case evidence for neighboring buildings; no status overrides."""
from pathlib import Path
from collections import Counter
import re
from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json, write_json

def osm_id(value):
    m = re.fullmatch('(way|relation)/?(\\d+)', value)
    return m.group(1) + '/' + m.group(2) if m else value

def building_case_review(pilot, requested):
    pilot = Path(pilot)
    from traffic_location.location.area._kernel.location_intelligent_li3 import verify_manifest
    verify_manifest(pilot)
    decisions = {osm_id(r['building_id']): r for r in read_json(pilot / 'building_results/decisions.json.gz') if r.get('building_id')}
    routes = {osm_id(r['building_id']): r for r in read_json(pilot / 'building_results/routing.json.gz')['routes']}
    connectors = read_json(pilot / 'connectors/connectors.json.gz')
    rejected = read_json(pilot / 'connectors/rejected.json.gz')
    uses = {osm_id(f['properties']['building_id']): {k: f['properties'].get(k) for k in ['osm_tags', 'class', 'subclass', 'use_review_reason', 'poi_use_evidence']} for f in read_json(pilot / 'normalized/buildings.geojson')['features']}
    edges = {r['edge_id']: r for r in read_json(pilot / 'graph/graph.json.gz')['edges']}
    records = []
    for source_id in requested:
        bid = osm_id(source_id)
        decision = decisions.get(bid)
        if decision is None:
            records.append({'requested_id': source_id, 'status': 'SOURCE_ID_NOT_FOUND'})
            continue
        own = [c for c in connectors if osm_id(c.get('building_id') or '') == bid]
        rejects = [c for c in rejected if osm_id(c.get('building_id') or '') == bid]
        route = routes.get(bid, {})
        records.append({'requested_id': source_id, 'status': 'EVIDENCE_LOADED', 'decision': decision, 'use_evidence': uses.get(bid), 'selected_candidate': route.get('selected_candidate'), 'route_found': route.get('route_found'), 'route_reason': route.get('reason'), 'route_candidates': route.get('candidates', []), 'connectors': [{'connector_id': c['connector_id'], 'node_id': c['node_id'], 'candidate_distance_m': c.get('candidate_distance_m'), 'source_segment': c['source_segment'], 'highway': edges[c['road_edge_id']]['highway'], 'edge_access_allowed': edges[c['road_edge_id']].get('access_allowed'), 'geometry': c['geometry']} for c in own], 'rejected_connector_reasons': dict(Counter((r['reason'] for r in rejects))), 'rejected_candidates': rejects, 'interpretation': 'Evidence only; neighbor proximity does not authorize a route'})
    import hashlib
    return {'schema': 'building_case_review_v1', 'primary_decisions_changed': False, 'pilot_manifest_sha256': hashlib.sha256((pilot / 'manifest.json').read_bytes()).hexdigest(), 'frozen_source_config': read_json(pilot / 'config/pilot.json'), 'cases': records}

def case_review_map(config, pilot, layers, facilities, review, output, alternatives=None):
    import folium
    from html import escape
    from pyproj import Transformer
    from traffic_location.location.area._kernel.location_intelligent_map_pilot import interactive_map
    pilot = Path(pilot)
    m = interactive_map(config, pilot, layers, output, facilities=facilities, alternatives=alternatives)
    features = {osm_id(f['properties']['building_id']): f for f in read_json(pilot / 'normalized/buildings.geojson')['features']}
    graph = read_json(pilot / 'graph/graph.json.gz')
    edges = {e['edge_id']: e for e in graph['edges']}
    inverse = Transformer.from_crs(config['metric_crs'], 4326, always_xy=True)

    def positions(geometry):
        return [[lat, lon] for lon, lat in [inverse.transform(x, y) for x, y in geometry['coordinates']]]
    for case in review['cases']:
        bid = osm_id(case['requested_id'])
        if case['status'] != 'EVIDENCE_LOADED' or bid not in features:
            continue
        group = folium.FeatureGroup(name='Audit ' + bid, show=True)
        folium.GeoJson(features[bid], style_function=lambda f: {'color': '#111827', 'weight': 4, 'fillOpacity': 0.05}, interactive=False).add_to(group)
        for c in case['connectors']:
            text = escape(bid + ' | ' + c['connector_id'] + ' | ' + str(c['highway']) + ' | candidate ' + str(c['candidate_distance_m']) + 'm')
            folium.PolyLine(positions(c['geometry']), color='#0284c7', weight=3, tooltip=text).add_to(group)
        for c in case['rejected_candidates']:
            if c.get('geometry'):
                folium.PolyLine(positions(c['geometry']), color='#dc2626', weight=2, dash_array='5,5', tooltip=escape(c['reason'])).add_to(group)
        route = case.get('selected_candidate') or {}
        for key in route.get('network_edges', []):
            if key in edges and edges[key].get('geometry'):
                folium.PolyLine(positions(edges[key]['geometry']), color='#7c3aed', weight=4, tooltip='Stored route ' + escape(bid)).add_to(group)
        group.add_to(m)
    for key, value in list(m._children.items()):
        if isinstance(value, folium.LayerControl):
            del m._children[key]
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(str(output))
    return m
