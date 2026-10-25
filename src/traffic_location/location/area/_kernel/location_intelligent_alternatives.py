"""Isolated store-alternative routing; no edits to the primary counting ledger."""
from pathlib import Path
import hashlib, json, math
from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json, write_json, canonical_bytes

def rank_alternatives(rows):

    def key(r):
        width = r.get('frontage_m')
        return (r['total_distance_m'], r['store_road_rank'], width is None, -width if width is not None else 0, r['store_key'])
    return sorted(rows, key=key)

def reachable_alternatives(package, stores, building_ids):
    """Same edge-state path index as motor engine, including prohibited turns."""
    from traffic_location.location.area._kernel.location_intelligent_motor_routing import _path_index
    graph = package['graph']
    rules = package['edge_rules']
    allowed = {k: v['allowed'] for k, v in rules.items()}
    blocked = {(t['from_edge'], t['to_edge']) for t in package['blocked_turns']}
    result = {bid: [] for bid in building_ids}
    sources = {bid: [] for bid in building_ids}
    for c in package['connectors']:
        if c['kind'] == 'BUILDING' and c.get('building_id') in sources:
            sources[c['building_id']].append(c)
    by_store = {s['store_key']: s for s in stores}
    edges = {e['edge_id']: e for e in graph['edges']}
    for target in package['connectors']:
        store_key = target.get('alternative_store_key')
        if store_key not in by_store or allowed.get(target['road_edge_id']) is not True:
            continue
        if target['barrier_clear'] is not True or target['status'] not in {'VERIFIED', 'OWNER_ASSUMPTION'}:
            continue
        lookup = _path_index(graph, allowed, blocked, target['node_id'])
        target_m = sum((math.dist(a, b) for a, b in zip(target['geometry']['coordinates'], target['geometry']['coordinates'][1:])))
        for bid, connectors in sources.items():
            options = []
            for c in connectors:
                if allowed.get(c['road_edge_id']) is not True or c['barrier_clear'] is not True:
                    continue
                if c['status'] not in {'VERIFIED', 'OWNER_ASSUMPTION'}:
                    continue
                path = lookup(c['node_id'])
                if path is None:
                    continue
                source_m = sum((math.dist(a, b) for a, b in zip(c['geometry']['coordinates'], c['geometry']['coordinates'][1:])))
                distance = source_m + path['distance_m'] + target_m
                options.append((c['class_rank'], distance, c['connector_id'], path))
            if options:
                _, distance, source_id, path = min(options, key=lambda x: (x[0], x[1], x[2]))
                store = by_store[store_key]
                result[bid].append({**store, 'total_distance_m': distance, 'store_road_rank': target['class_rank'], 'store_highway': edges[target['road_edge_id']]['highway'], 'building_connector_id': source_id, 'target_connector_id': target['connector_id'], 'path_sha256': hashlib.sha256(canonical_bytes(path['edges'])).hexdigest(), 'access_basis': 'REACHABLE_IN_CONFIGURED_MOTOR_GRAPH_NOT_PHYSICAL_VERIFICATION'})
    return {bid: rank_alternatives(rows) for bid, rows in result.items()}

def build_alternatives(config, pilot, layers, output):
    from pyproj import Transformer
    from traffic_location.location.area._kernel.location_intelligent_li3 import verify_manifest, select_feature_source
    from traffic_location.location.area._kernel.location_intelligent_li3_graph import build_graph
    from traffic_location.location.area._kernel.location_intelligent_li3_connectors import generate_connectors
    from traffic_location.location.area._kernel.location_intelligent_map_pilot import poi_locations, sha
    import traffic_location.location.area._kernel.location_intelligent_li3_connectors as connector_code
    import traffic_location.location.area._kernel.location_intelligent_motor_routing as motor_code
    import traffic_location.location.area._kernel.location_intelligent_li3_graph as graph_code
    pilot = Path(pilot)
    output = Path(output)
    verify_manifest(pilot)
    identity = {'schema': 'store_alternatives_v1', 'pilot': sha(pilot / 'manifest.json'), 'layer_hashes': {k: hashlib.sha256(canonical_bytes(v)).hexdigest() for k, v in layers.items()}, 'attributes': config.get('store_attributes', {}), 'code': sha(__file__), 'dependencies': {m.__name__: sha(m.__file__) for m in [connector_code, motor_code, graph_code]}}
    fingerprint = hashlib.sha256(canonical_bytes(identity)).hexdigest()
    output = output.parent / output.stem / fingerprint / 'result.json'
    if output.exists():
        saved = read_json(output)
        if saved['fingerprint'] != fingerprint:
            raise ValueError('Alternative inputs changed; use new output revision')
        return saved
    if any((v['status'] != 'SUCCEEDED' for v in layers.values())):
        return {'status': 'BLOCKED', 'reason': 'STORE_INPUT_UNAVAILABLE', 'by_building': {}, 'fingerprint': fingerprint}
    frozen = read_json(pilot / 'config/pilot.json')
    metrics = read_json(pilot / 'normalized/metric_buildings.json')
    tx = Transformer.from_crs(4326, frozen['policy']['li3']['metric_crs'], always_xy=True)
    stores = []
    excluded_stores = []
    for kind, layer in sorted(layers.items()):
        binding = layer.get('request_binding', {})
        if any((binding.get(k) != v for k, v in {'latitude': config['latitude'], 'longitude': config['longitude'], 'radius_m': config['poi_radius_m']}.items())):
            raise ValueError('Store snapshot belongs to another target/radius')
        for r in poi_locations(layer):
            if not all((math.isfinite(r[k]) for k in ['latitude', 'longitude', 'distance_m'])) or not (-90 <= r['latitude'] <= 90 and -180 <= r['longitude'] <= 180 and (0 <= r['distance_m'] <= config['poi_radius_m'])):
                raise ValueError('Invalid store coordinate/distance evidence')
            if r['identity_location_conflict']:
                excluded_stores.append({'kind': kind, 'store_id': r['store_id'], 'reason': 'UNRESOLVED_STORE_IDENTITY_LOCATION'})
                continue
            store_key = hashlib.sha256(canonical_bytes([kind, r['store_id'], r['latitude'], r['longitude']])).hexdigest()[:20]
            attr = config.get('store_attributes', {}).get(store_key, {})
            width = attr.get('frontage_m') if attr.get('source_ref') else None
            if width is not None and (type(width) not in (float, int) or not math.isfinite(width) or width <= 0):
                raise ValueError('Invalid documented frontage')
            point = list(tx.transform(r['longitude'], r['latitude']))
            if not all((math.isfinite(v) for v in point)):
                raise ValueError('Store projection failed')
            stores.append({'store_key': store_key, 'name': ' / '.join(r['names']) or str(r['store_id']), 'kind': kind, 'store_id': r['store_id'], 'target_xy': point, 'frontage_m': width, 'frontage_source_ref': attr.get('source_ref')})
    features_path, _ = select_feature_source(pilot)
    features = read_json(features_path)
    base = build_graph(read_json(pilot / 'raw/osm_roads.json.gz'), features, frozen)
    if base['graph'] is None:
        return {'status': 'BLOCKED', 'reason': 'MOTOR_GRAPH_UNAVAILABLE', 'by_building': {}, 'fingerprint': fingerprint}
    from traffic_location.location.area._kernel.location_intelligent_routing import inside_bbox
    in_scope = []
    for store in stores:
        if inside_bbox(store['target_xy'], base['graph']['coverage']['bbox']):
            in_scope.append(store)
        else:
            excluded_stores.append({'store_key': store['store_key'], 'reason': 'TARGET_OUTSIDE_GRAPH_COVERAGE'})
    stores = in_scope
    package = generate_connectors(base, metrics, features, frozen, alternative_targets=stores)
    result = reachable_alternatives(package, stores, [b['building_id'] for b in metrics['selected_buildings']])
    saved = {'status': 'SUCCEEDED', 'fingerprint': fingerprint, 'identity': identity, 'by_building': result, 'stores': stores, 'excluded_stores': excluded_stores, 'artifact_path': str(output), 'ranking': 'total route distance asc; store road class rank asc; known frontage desc; unknown last on exact ties', 'primary_counting_changed': False, 'physical_access_validated': False}
    write_json(output, saved, exclusive=True)
    return saved
