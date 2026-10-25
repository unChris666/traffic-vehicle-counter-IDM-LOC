"""Source-bound CPU market orchestration. Cache keys bind data, code and policy."""
from pathlib import Path
from copy import deepcopy
import hashlib
import math
from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json, write_json, canonical_bytes
from traffic_location.location.area._kernel.location_intelligent_market import classify_store, corridor_tokens, restaurant_cluster, allocate_building, reconcile

class SourcePacketError(ValueError):
    """Public diagnostic code only; never contains credentials or raw responses."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)

def source_request_config(config):
    """Drop only calculation-only entrance selection from source identity.

    Compare both sides this way so legacy packets need no mutation/re-fetch.
    Target, extent, network mode and all other existing safeguards remain bound.
    """
    return {k: v for k, v in config.items() if k not in {'building_entrance_profile', 'road_rule_profile'}}

def verify_market_source_packet(root, config):
    from traffic_location.location.area._kernel.location_intelligent_map_pilot import sha
    root = Path(root)
    if not (root / 'source_manifest.json').is_file():
        raise SourcePacketError('FROZEN_SOURCE_PACKET_MISSING')
    manifest = read_json(root / 'source_manifest.json')
    if source_request_config(manifest['config']) != source_request_config(config):
        raise SourcePacketError('SOURCE_CONFIG_MISMATCH')
    for name, digest in manifest['files'].items():
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise SourcePacketError('SOURCE_PATH_INVALID')
        if not path.is_file() or sha(path) != digest:
            raise SourcePacketError('SOURCE_SNAPSHOT_CHANGED')
    return manifest

def acquire_market_network(config, root):
    """New-location roads/barriers only; never relabel the old network seed."""
    from pyproj import Transformer
    from traffic_location.location.area._kernel.location_intelligent_config import get_config
    from traffic_location.location.area._kernel.location_intelligent_validator import canonical_hash
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import build_queries, acquire_overpass, utc
    from traffic_location.location.area._kernel.location_intelligent_map_pilot import sha
    config = source_request_config(config)
    root = Path(root)
    mode = config.get('network_feature_mode', 'FULL')
    if mode not in {'FULL', 'ROADS_ONLY_EXPERIMENT'}:
        raise ValueError('Unknown network feature mode')
    if mode == 'ROADS_ONLY_EXPERIMENT' and (not root.exists()):
        old = root.with_name('network')
        if old != root and (old / 'config/pilot.json').exists() and (old / 'raw/osm_roads.json.gz').exists():
            previous = read_json(old / 'config/pilot.json')['policy']['li3']
            if any((previous[k] != config[k] for k in ['latitude', 'longitude', 'metric_crs'])):
                raise ValueError('Previous road extract belongs to another location')
            import shutil
            shutil.copytree(old, root, ignore=shutil.ignore_patterns('network_manifest.json', 'osm_features_roads_only.json.gz'))
    if (root / 'network_manifest.json').exists():
        m = read_json(root / 'network_manifest.json')
        if m['config'] != config:
            raise ValueError('Network cache config changed; choose new revision')
        for name, digest in m['files'].items():
            if sha(root / name) != digest:
                raise ValueError('Network cache corrupted')
        return root
    p = get_config()
    p['li3'].update(latitude=config['latitude'], longitude=config['longitude'], metric_crs=config['metric_crs'], network_bbox_radius_m=config['network_radius_m'])
    forward = Transformer.from_crs(4326, config['metric_crs'], always_xy=True)
    inverse = Transformer.from_crs(config['metric_crs'], 4326, always_xy=True)
    x, y = forward.transform(config['longitude'], config['latitude'])
    r = config['network_radius_m']
    corners = [inverse.transform(a, b) for a in (x - r, x + r) for b in (y - r, y + r)]
    frozen = {'schema_version': 'li3_pilot_config_v1', 'algorithm_version': 'LI3_V1', 'analysis_run_id': root.name, 'frozen_at': utc(), 'policy': p, 'target_xy': [x, y], 'reference_metric_bbox': [x - r, y - r, x + r, y + r], 'extraction_bbox_wgs84': [min((a for a, b in corners)), min((b for a, b in corners)), max((a for a, b in corners)), max((b for a, b in corners))], 'diagnostic_gap_m': 10.0, 'building_cache_files': {}, 'source_scope': 'NEW_TARGET_OSM_MOTOR_NETWORK'}
    frozen['config_hash'] = canonical_hash(frozen)
    q = build_queries(frozen['extraction_bbox_wgs84'], p)
    if root.exists():
        previous = read_json(root / 'config/pilot.json')
        check = deepcopy(previous)
        digest = check.pop('config_hash')
        if canonical_hash(check) != digest or previous['policy'] != p or previous['extraction_bbox_wgs84'] != frozen['extraction_bbox_wgs84']:
            raise ValueError('Network configuration changed; cannot resume')
        frozen = previous
    else:
        root.mkdir(parents=True)
        write_json(root / 'config/pilot.json', frozen, exclusive=True)
    if (root / 'config/queries.json').exists():
        if read_json(root / 'config/queries.json') != q:
            raise ValueError('Network query changed; use new source revision')
    else:
        write_json(root / 'config/queries.json', q, exclusive=True)
    from traffic_location.location.area._kernel.location_intelligent_network_acquisition import acquire_network_sources
    acquire_network_sources(root, frozen, q, config, build_queries, acquire_overpass)
    files = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}
    write_json(root / 'network_manifest.json', {'config': config, 'files': files}, exclusive=True)
    return root

def _connector_tokens(package, connector):
    return corridor_tokens(package['edge_sources'][connector['road_edge_id']]['raw_tags'])

def _reuse_calculation_connectors(pilot, metrics, features, frozen, alternative_targets):
    """Extend section-6 access points; never select building entrances again."""
    from collections import defaultdict
    from shapely.geometry import LineString, Point
    from traffic_location.location.area._kernel.location_intelligent_li3_connectors import generate_connectors
    from traffic_location.location.area._kernel.location_intelligent_li3_graph import apply_turns
    base_graph = read_json(pilot / 'graph/base_graph.json.gz')
    base_sources = read_json(pilot / 'graph/base_edge_sources.json.gz')
    retained = read_json(pilot / 'connectors/connectors.json.gz')
    base_rules = {}
    for edge in base_graph['edges']:
        key = edge['edge_id']
        source = base_sources[key]
        tags = deepcopy(source['raw_tags'])
        for access_key in ('access', 'vehicle', 'motor_vehicle', 'motorcycle'):
            directional = access_key + (':forward' if source['direction'] == 'f' else ':backward')
            if directional in tags:
                tags[access_key] = tags[directional]
        base_rules[key] = {'allowed': edge['access_allowed'], 'evidence_refs': ['osm_way_' + str(source['osm_way_id'])], 'raw_tags': tags, 'reason': source['permission_reason']}
    base = {'graph': base_graph, 'edge_sources': base_sources, 'edge_rules': base_rules}
    print('Market: building entrances from section 6; locating ' + str(len(alternative_targets)) + ' extra store/POI targets', flush=True)
    targets = generate_connectors(base, {**metrics, 'selected_buildings': []}, features, frozen, alternative_targets=alternative_targets)
    expected = next((c for c in retained if c['kind'] == 'TARGET' and (not c.get('alternative_store_key'))), None)
    generated = next((c for c in targets['connectors'] if c['kind'] == 'TARGET' and (not c.get('alternative_store_key'))), None)

    def entrance(c):
        return {k: v for k, v in c.items() if k != 'road_edge_id'} if c else None
    if entrance(expected) != entrance(generated):
        raise ValueError('Retained candidate entrance differs from frozen base graph')
    connectors = deepcopy(retained) + [deepcopy(c) for c in targets['connectors'] if c.get('alternative_store_key')]
    cuts = defaultdict(dict)
    groups = {}
    epsilon = frozen['policy']['li3']['projection_position_precision_m']
    for edge in base_graph['edges']:
        source = base_sources[edge['edge_id']]
        gid = f"w{source['osm_way_id']}_s{source['segment_index']}"
        if gid not in groups:
            forward = source['direction'] == 'f'
            coords = edge['geometry']['coordinates']
            groups[gid] = {'line': LineString(coords if forward else list(reversed(coords))), 'a': edge['u'] if forward else edge['v'], 'b': edge['v'] if forward else edge['u'], 'members': []}
        groups[gid]['members'].append(edge)
    for c in connectors:
        gid = c['source_segment']
        group = groups[gid]
        node = c['node_id']
        if node == group['a']:
            position = 0.0
        elif node == group['b']:
            position = group['line'].length
        elif node.startswith(gid + '_x'):
            position = min(max(int(node[len(gid) + 2:]) * epsilon, epsilon), group['line'].length - epsilon)
        else:
            raise ValueError('Unsupported retained access node')
        cuts[gid][node] = position
    nodes = {n['node_id']: deepcopy(n) for n in base_graph['nodes']}
    edges = []
    sources = {}
    rules = {}
    incidents = defaultdict(list)
    speed = frozen['policy']['travel']['reference_constant_speed']['value'] * 1000 / 3600
    for gid in sorted(groups):
        group = groups[gid]
        line = group['line']
        positions = {group['a']: 0.0, group['b']: line.length, **cuts.get(gid, {})}
        ordered = sorted(positions, key=lambda n: (positions[n], n))
        for node in ordered:
            point = line.interpolate(positions[node])
            if node not in nodes:
                nodes[node] = {'node_id': node, 'x': point.x, 'y': point.y}
        for parent in group['members']:
            pkey = parent['edge_id']
            path = ordered if base_sources[pkey]['direction'] == 'f' else list(reversed(ordered))
            for i, (a, b) in enumerate(zip(path, path[1:])):
                coords = [[nodes[a]['x'], nodes[a]['y']], [nodes[b]['x'], nodes[b]['y']]]
                distance = math.dist(*coords)
                if distance <= 0:
                    continue
                key = pkey + '_p' + str(i)
                edges.append({**parent, 'edge_id': key, 'u': a, 'v': b, 'key': key, 'length_m': distance, 'travel_time_s': distance / speed, 'geometry': {'type': 'LineString', 'coordinates': coords}})
                sources[key] = {**deepcopy(base_sources[pkey]), 'parent_edge_id': pkey}
                rules[key] = deepcopy(base_rules[pkey])
                incidents[gid, a].append(key)
                incidents[gid, b].append(key)
    graph = {**base_graph, 'nodes': sorted(nodes.values(), key=lambda n: n['node_id']), 'edges': sorted(edges, key=lambda e: e['edge_id'])}
    for c in connectors:
        c['road_edge_id'] = min((k for k in incidents[c['source_segment'], c['node_id']] if rules[k]['allowed'] is True))
    blocked, turn_diagnostics = apply_turns(graph, sources, rules, features, profile=frozen['policy']['li3'].get('road_rule_profile'))
    print('Market: reused ' + str(sum((c['kind'] == 'BUILDING' for c in retained))) + ' building connectors; added ' + str(len(alternative_targets)) + ' target requests', flush=True)
    return {'graph': graph, 'edge_sources': sources, 'edge_rules': rules, 'blocked_turns': blocked, 'connectors': connectors, 'diagnostics': {'building_connectors_reused': True, 'turn_relations': turn_diagnostics}}

class _MarketRoutes:
    """One immutable adjacency per market invocation, with directed turn states."""

    def __init__(self, package):
        self.edges = {e['edge_id']: e for e in package['graph']['edges']}
        self.allowed = {k: r['allowed'] for k, r in package['edge_rules'].items()}
        self.blocked = {(r['from_edge'], r['to_edge']) for r in package['blocked_turns']}
        self.incoming = {}
        self.outgoing = {}
        for key, e in self.edges.items():
            if self.allowed.get(key) is True:
                self.incoming.setdefault(e['v'], []).append(key)
                self.outgoing.setdefault(e['u'], []).append(key)

    def reverse(self, target):
        import heapq
        best = {}
        queue = []
        for key in self.incoming.get(target, []):
            label = (self.edges[key]['length_m'], 1, (key,))
            best[key] = label
            heapq.heappush(queue, (*label, key))
        while queue:
            cost, hops, path, key = heapq.heappop(queue)
            if best.get(key) != (cost, hops, path):
                continue
            for previous in self.incoming.get(self.edges[key]['u'], []):
                if (previous, key) in self.blocked:
                    continue
                label = (self.edges[previous]['length_m'] + cost, hops + 1, (previous, *path))
                if previous not in best or label < best[previous]:
                    best[previous] = label
                    heapq.heappush(queue, (*label, previous))
        memo = {}

        def lookup(start):
            if start == target:
                return {'distance_m': 0.0, 'path_sha256': hashlib.sha256(canonical_bytes([])).hexdigest()}
            if start not in memo:
                options = [best[k] for k in self.outgoing.get(start, []) if k in best]
                label = min(options) if options else None
                memo[start] = None if label is None else {'distance_m': sum((self.edges[k]['length_m'] for k in label[2])), 'path_sha256': hashlib.sha256(canonical_bytes(list(label[2]))).hexdigest()}
            return memo[start]
        return lookup

    def forward(self, start):
        import heapq
        queue = [(0.0, 0, (), start, '')]
        best = {(start, ''): (0.0, 0, ())}
        nodes = {}
        while queue:
            cost, hops, path, node, previous = heapq.heappop(queue)
            if best.get((node, previous)) != (cost, hops, path):
                continue
            if node not in nodes:
                nodes[node] = {'distance_m': cost}
            for key in sorted(self.outgoing.get(node, [])):
                if (previous, key) in self.blocked:
                    continue
                edge = self.edges[key]
                label = (cost + edge['length_m'], hops + 1, (*path, key))
                state = (edge['v'], key)
                if state not in best or label < best[state]:
                    best[state] = label
                    heapq.heappush(queue, (*label, *state))
        return lambda target: nodes.get(target)

    def potential_forward(self, start):
        outgoing = {}
        for key, e in self.edges.items():
            if self.allowed.get(key) is not False:
                outgoing.setdefault(e['u'], []).append(key)
        nodes = {start}
        seen = set()
        queue = [(start, '')]
        while queue:
            node, previous = queue.pop()
            for key in outgoing.get(node, []):
                if key in seen or (previous, key) in self.blocked:
                    continue
                seen.add(key)
                dest = self.edges[key]['v']
                nodes.add(dest)
                queue.append((dest, key))
        return lambda target: target in nodes

def _market_store_routes(package, stores, building_ids, network, primary_routes):
    """Reuse source validation/lengths and one reverse search per store node."""
    from traffic_location.location.area._kernel.location_intelligent_alternatives import rank_alternatives
    by_store = {s['store_key']: s for s in stores}
    sources = {bid: [] for bid in building_ids}
    result = {bid: [] for bid in building_ids}
    if not building_ids:
        print('Market routing: no eligible building/store pairs; rows remain in allocation ledger', flush=True)
        return result
    for c in package['connectors']:
        if c['kind'] == 'BUILDING' and c.get('building_id') in sources and (network.allowed.get(c['road_edge_id']) is True) and (c['barrier_clear'] is True) and (c['status'] in {'VERIFIED', 'OWNER_ASSUMPTION'}):
            sources[c['building_id']].append((c, _connector_length(c)))
    targets = []
    for c in package['connectors']:
        key = c.get('alternative_store_key') or ('candidate' if c['kind'] == 'TARGET' else None)
        if key in by_store and network.allowed.get(c['road_edge_id']) is True and (c['barrier_clear'] is True) and (c['status'] in {'VERIFIED', 'OWNER_ASSUMPTION'}):
            targets.append((key, c))
    source_groups = {}
    for bid, connectors in sources.items():
        for c, length in connectors:
            source_groups.setdefault(c['node_id'], []).append((bid, c, length))
    print('Market routing clusters: ' + str(len(source_groups)) + ' source access nodes for ' + str(len(building_ids)) + ' buildings', flush=True)
    grouped = {}
    for key, target in targets:
        grouped.setdefault(target['node_id'], []).append((key, target))
    for i, (node, targets_here) in enumerate(grouped.items(), 1):
        needed = any((key != 'candidate' or any((primary_routes.get(bid, {}).get('selected_candidate') is None for bid in sources)) for key, _ in targets_here))
        print('Market routing: target node ' + str(i) + '/' + str(len(grouped)) + (' — reuse primary' if not needed else ''), flush=True)
        if not needed:
            continue
        lookup = network.reverse(node)
        for key, target in targets_here:
            target_m = _connector_length(target)
            options_by_building = {bid: [] for bid in building_ids}
            for source_node, members in source_groups.items():
                path = lookup(source_node)
                if path is None:
                    continue
                for bid, c, source_m in members:
                    if key == 'candidate' and primary_routes.get(bid, {}).get('selected_candidate') is not None:
                        continue
                    options_by_building[bid].append((c['class_rank'], source_m + path['distance_m'] + target_m, c['connector_id'], path))
            for bid, options in options_by_building.items():
                if options:
                    _, distance, source_id, path = min(options, key=lambda x: (x[0], x[1], x[2]))
                    result[bid].append({**by_store[key], 'total_distance_m': distance, 'store_road_rank': target['class_rank'], 'store_highway': network.edges[target['road_edge_id']]['highway'], 'building_connector_id': source_id, 'target_connector_id': target['connector_id'], 'path_sha256': path['path_sha256'], 'access_basis': 'REACHABLE_IN_CONFIGURED_MOTOR_GRAPH_NOT_PHYSICAL_VERIFICATION'})
        del lookup
    return {bid: rank_alternatives(rows) for bid, rows in result.items()}

def _poi_gate(config, policy, facilities, package, poi_targets, buildings, *, network=None):
    """Assess actual observed attractors and complete-link restaurant groups."""
    from pyproj import Transformer
    from shapely.geometry import shape, Point
    from shapely.ops import transform
    from shapely.strtree import STRtree
    if not policy['outer_zone_requires_attractor']:
        return {'state': 'OPEN', 'reason': 'ATTRACTOR_REQUIREMENT_DISABLED_BY_BUSINESS_POLICY', 'evidence': []}
    if facilities.get('status') != 'SUCCEEDED':
        return {'state': 'UNKNOWN', 'reason': 'POI_INPUT_UNAVAILABLE', 'evidence': []}
    graph = package['graph']
    allowed = {k: r['allowed'] for k, r in package['edge_rules'].items()}
    blocked = {(r['from_edge'], r['to_edge']) for r in package['blocked_turns']}
    targets = {c.get('alternative_store_key'): c for c in package['connectors'] if c.get('alternative_store_key')}
    candidate = next((c for c in package['connectors'] if c['kind'] == 'TARGET' and 'alternative_store_key' not in c), None)
    if candidate is None:
        return {'state': 'UNKNOWN', 'reason': 'CANDIDATE_CONNECTOR_UNAVAILABLE', 'evidence': []}
    tx = Transformer.from_crs(4326, config['metric_crs'], always_xy=True)
    shapes = [shape(f['geometry']) for f in buildings['features']]
    index = STRtree(shapes)
    by_id = {f['properties']['building_id']: i for i, f in enumerate(buildings['features'])}
    network = network or _MarketRoutes(package)
    paths = network.forward(candidate['node_id']) if poi_targets else lambda node: None
    potential = network.potential_forward(candidate['node_id']) if any((v is None for v in allowed.values())) else lambda node: False
    evidence = []
    restaurants = []
    incomplete = False
    for i, p in enumerate(poi_targets, 1):
        if i == 1 or i % 25 == 0 or i == len(poi_targets):
            print('Market POI gate: ' + str(i) + '/' + str(len(poi_targets)), flush=True)
        conn = targets.get(p['store_key'])
        record = {'source_id': p['source_id'], 'category': p['category'], 'eligible': False}
        evidence.append(record)
        if conn is None or allowed.get(conn['road_edge_id']) is not True:
            record['reason'] = 'POI_CONNECTOR_UNAVAILABLE'
            incomplete = True
            continue
        path = paths(conn['node_id'])
        if path is None:
            unknown = potential(conn['node_id'])
            record['reason'] = 'ROUTE_UNVERIFIED' if unknown else 'NO_OBSERVED_ROUTE'
            incomplete |= unknown
            continue
        record.update(route_distance_m=path['distance_m'] + _connector_length(candidate) + _connector_length(conn), eligible=True, reason='REACHABLE_IN_CONFIGURED_GRAPH')
        if p['category'] != 'restaurant':
            continue
        ids = [by_id[p['source_id']]] if p['source_id'] in by_id else []
        if not ids and p['point_basis'] == 'OSM_NODE':
            pt = Point(p['longitude'], p['latitude'])
            ids = [int(i) for i in index.query(pt) if shapes[int(i)].contains(pt)]
        if len(ids) != 1:
            record.update(eligible=False, reason='RESTAURANT_FOOTPRINT_UNVERIFIED')
            incomplete = True
            continue
        i = ids[0]
        area = transform(tx.transform, shapes[i]).area
        record['footprint_area_m2'] = area
        if area < policy['restaurant_cluster']['minimum_footprint_m2']:
            record.update(eligible=False, reason='RESTAURANT_FOOTPRINT_BELOW_40')
            continue
        tokens = _connector_tokens(package, conn)
        if not tokens:
            record.update(eligible=False, reason='RESTAURANT_CORRIDOR_UNVERIFIED')
            incomplete = True
            continue
        restaurants.append({'source_id': p['source_id'], 'building_id': buildings['features'][i]['properties']['building_id'], 'xy': p['target_xy'], 'corridor_tokens': tokens})
    cluster = restaurant_cluster(restaurants, policy['restaurant_cluster']['maximum_pair_distance_m'], policy['restaurant_cluster']['minimum_sites'])
    positive = [r['source_id'] for r in evidence if r['eligible'] and r['category'] != 'restaurant']
    if positive or cluster:
        return {'state': 'OPEN', 'reason': 'OBSERVED_REACHABLE_ATTRACTOR' if positive else 'VERIFIED_RESTAURANT_CLUSTER', 'positive_attractors': positive, 'restaurant_cluster': cluster, 'evidence': evidence}
    return {'state': 'UNKNOWN' if incomplete else 'CLOSED', 'reason': 'INSUFFICIENT_ATTRACTOR_EVIDENCE' if incomplete else 'NO_QUALIFYING_ATTRACTOR_IN_OBSERVED_SNAPSHOT', 'restaurant_cluster': None, 'evidence': evidence}

def _connector_length(c):
    xy = c['geometry']['coordinates']
    return sum((math.dist(a, b) for a, b in zip(xy, xy[1:])))

def _market_store_in_scope(kind, distance_m, market_config):
    return kind != 'competitor' or distance_m <= market_config['sources'].get('competitor_calculation_radius_m', 2000.0)

def build_market(config, market_config, pilot, layers, facilities, output):
    from pyproj import Transformer, Geod
    from traffic_location.location.area._kernel.location_intelligent_li3 import verify_manifest, select_feature_source
    from traffic_location.location.area._kernel.location_intelligent_map_pilot import sha, poi_locations
    from traffic_location.location.area._kernel.location_intelligent_market_config import require_market_decisions
    import traffic_location.location.area._kernel.location_intelligent_market as domain
    import traffic_location.location.area._kernel.location_intelligent_alternatives as alternatives
    import traffic_location.location.area._kernel.location_intelligent_li3_graph as graph_code
    import traffic_location.location.area._kernel.location_intelligent_li3_connectors as connector_code
    import traffic_location.location.area._kernel.location_intelligent_motor_routing as motor_code
    policy = require_market_decisions(market_config)['allocation_requirements']
    if config.get('network_feature_mode', 'FULL') != market_config['sources'].get('network_feature_mode', 'FULL'):
        raise ValueError('Market source mode differs from job configuration')
    if any((config[k] != market_config['target'][k] for k in ('latitude', 'longitude'))):
        raise ValueError('Market target differs from job')
    if config['building_radius_m'] != policy['zones_m'][-1] or config['min_area_m2'] != policy['residential_min_area_m2'] or config['max_area_m2'] != policy['residential_max_area_m2_exclusive'] or (config.get('selection_profile') != 'area-market-ge36-v1'):
        raise ValueError('Market selection profile differs')
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import timed_call
    pilot = Path(pilot)
    timed_call('market_verify_calculation', verify_manifest, pilot)
    frozen = read_json(pilot / 'config/pilot.json')
    if frozen['policy']['li3'].get('road_rule_profile', 'STRICT_MOTOR_LEGACY') != config.get('road_rule_profile', 'STRICT_MOTOR_LEGACY'):
        raise ValueError('Frozen road rule profile differs from request')
    if frozen['policy']['connectors'].get('building_entrance_profile', 'MULTI_ACCESS_LEGACY') != config.get('building_entrance_profile', 'MULTI_ACCESS_LEGACY'):
        raise ValueError('Frozen entrance profile differs from requested calculation')
    if frozen['policy']['li3'].get('feature_source_mode', 'FULL') != config.get('network_feature_mode', 'FULL'):
        raise ValueError('Frozen network mode differs from market job')
    if any((frozen['policy']['li3'][k] != config[k] for k in ('latitude', 'longitude', 'metric_crs'))):
        raise ValueError('Pilot target differs from job')
    if frozen['policy']['travel']['reference_constant_speed']['value'] != policy['speed_kmh'] or frozen['policy']['travel']['max_travel_min']['value'] != policy['max_travel_minutes']:
        raise ValueError('Market time policy differs from frozen motor routing')
    if facilities.get('request_binding', {}).get('rules') != 'osm_market_attractors_v2':
        raise ValueError('Market requires expanded POI inventory; legacy eight-category cache not sufficient')
    identity = {'schema': 'area_market_v1', 'config': config, 'market_config': market_config, 'pilot': sha(pilot / 'manifest.json'), 'stores': hashlib.sha256(canonical_bytes(layers)).hexdigest(), 'facilities': hashlib.sha256(canonical_bytes(facilities)).hexdigest(), 'code': {m.__name__: sha(m.__file__) for m in [domain, alternatives, graph_code, connector_code, motor_code]}, 'runtime': sha(__file__)}
    fingerprint = hashlib.sha256(canonical_bytes(identity)).hexdigest()
    root = Path(output) / fingerprint
    if (root / 'manifest.json').exists():
        manifest = read_json(root / 'manifest.json')
        if manifest['identity'] != identity:
            raise ValueError('Market cache binding changed')
        for name, digest in manifest['files'].items():
            if sha(root / name) != digest:
                raise ValueError('Market result cache corrupted')
        print('Market: verified result cache HIT', flush=True)
        return read_json(root / 'result.json')
    if root.exists():
        raise ValueError('Incomplete market result; inspect rather than overwrite')
    for layer in layers.values():
        if layer['status'] == 'SUCCEEDED':
            b = layer['request_binding']
            if any((b[k] != v for k, v in {'latitude': config['latitude'], 'longitude': config['longitude'], 'radius_m': 2000}.items())):
                raise ValueError('BQ snapshot belongs to another location')
    binding = facilities.get('request_binding', {})
    if any((binding.get(k) != v for k, v in {'latitude': config['latitude'], 'longitude': config['longitude'], 'radius_m': 2000}.items())):
        raise ValueError('POI snapshot belongs to another location')
    tx = Transformer.from_crs(4326, config['metric_crs'], always_xy=True)
    geod = Geod(ellps='WGS84')
    metrics = read_json(pilot / 'normalized/metric_buildings.json')
    selected = read_json(pilot / 'building_results/selection.json')['selected']
    decisions = read_json(pilot / 'building_results/decisions.json.gz')
    normalized = read_json(pilot / 'normalized/buildings.geojson')
    features = read_json(select_feature_source(pilot)[0])
    stores = []
    source_complete = all((l['status'] == 'SUCCEEDED' for l in layers.values()))
    excluded = []
    for kind, layer in sorted(layers.items()):
        for r in poi_locations(layer) if layer['status'] == 'SUCCEEDED' else []:
            if not _market_store_in_scope(kind, r['distance_m'], market_config):
                excluded.append({'kind': kind, 'store_id': r['store_id'], 'reason': 'OUTSIDE_COMPETITOR_CALCULATION_RADIUS', 'distance_m': r['distance_m']})
                continue
            if r['identity_location_conflict']:
                source_complete = False
                excluded.append({'kind': kind, 'store_id': r['store_id'], 'reason': 'IDENTITY_LOCATION_CONFLICT'})
                continue
            key = hashlib.sha256(canonical_bytes([kind, r['store_id'], r['latitude'], r['longitude']])).hexdigest()[:20]
            stores.append({'store_key': key, 'name': ' / '.join(r['names']) or str(r['store_id']), 'kind': kind, 'latitude': r['latitude'], 'longitude': r['longitude'], 'distance_to_candidate_m': r['distance_m'], 'target_xy': list(tx.transform(r['longitude'], r['latitude']))})
    pois = []
    for p in facilities.get('rows') or []:
        if p['category'] in {'market', 'hospital', 'station', 'recreation', 'police', 'bank', 'mall', 'restaurant'}:
            pois.append({**p, 'store_key': 'poi:' + p['source_id'], 'target_xy': list(tx.transform(p['longitude'], p['latitude']))})
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import timed_call
    package = timed_call('market_reuse_connectors_add_targets', _reuse_calculation_connectors, pilot, metrics, features, frozen, [*stores, *pois])
    own_target = next((c for c in package['connectors'] if c['kind'] == 'TARGET' and (not c.get('alternative_store_key'))), None)
    candidate = {'store_key': 'candidate', 'kind': 'candidate', 'name': 'Calon toko', 'latitude': config['latitude'], 'longitude': config['longitude'], 'distance_to_candidate_m': 0.0, 'corridor_tokens': _connector_tokens(package, own_target) if own_target else []}
    conn_by_key = {c.get('alternative_store_key'): c for c in package['connectors'] if c.get('alternative_store_key')}
    for s in stores:
        c = conn_by_key.get(s['store_key'])
        s['corridor_tokens'] = _connector_tokens(package, c) if c else []
        if c is None:
            source_complete = False
            excluded.append({'store_key': s['store_key'], 'reason': 'STORE_CONNECTOR_UNAVAILABLE'})
    stores = [classify_store(s, candidate['corridor_tokens'], policy) for s in [candidate, *stores]]
    primary_routes = {r['building_id']: r for r in read_json(pilot / 'building_results/routing.json.gz')['routes']}
    network = timed_call('market_shared_routing_adjacency', _MarketRoutes, package)
    accepted_ids = {d['building_id'] for d in decisions if d['decision_state'] == 'ACCEPTED'}
    eligible_ids = [b['building_id'] for b in selected if b['building_id'] in accepted_ids and b['building_type'] == 'standard_residential'] if source_complete else []
    matrix = timed_call('market_store_routing', _market_store_routes, package, stores, eligible_ids, network, primary_routes)
    gate = timed_call('market_poi_gate', _poi_gate, config, policy, facilities, package, pois, normalized, network=network)
    gate['snapshot_inventory_complete'] = False
    property_by_id = {f['properties']['building_id']: f['properties'] for f in normalized['features']}
    building_by_id = {b['building_id']: b for b in selected}
    rows = []
    for d in decisions:
        bid = d.get('building_id')
        if not bid:
            continue
        b = building_by_id.get(bid)
        props = property_by_id[bid]
        if b:
            lon, lat = b['representative_point']['coordinates']
            area = b['area_m2']
            distances = {s['store_key']: geod.inv(lon, lat, s['longitude'], s['latitude'])[2] for s in stores}
            records = {r['store_key']: r for r in matrix.get(bid, [])}
            primary = primary_routes.get(bid, {}).get('selected_candidate')
            if primary is not None:
                records['candidate'] = {'total_distance_m': primary['total_distance_m']}
            building = {'building_id': bid, 'residential': b['building_type'] == 'standard_residential', 'area_m2': area, 'access_status': d['decision_state'], 'distance_to_candidate_m': distances['candidate'], 'store_distances_m': distances}
            row = allocate_building(building, stores, records, gate, policy, inputs_complete=source_complete)
        else:
            row = {'building_id': bid, 'access_status': d['decision_state'], 'market_status': 'OTHERS', 'reason': d['reason'], 'winner_store_key': None, 'count_candidate': 0, 'scores': [], 'estimated': True}
        row['area_m2'] = b['area_m2'] if b else None
        row['use_review_reason'] = props.get('use_review_reason')
        rows.append(row)
    if len(rows) != len(decisions):
        raise ValueError('Missing building identity; cannot reconcile market ledger')
    eligible_set = set(eligible_ids)
    result = {'schema_version': 'area_market_result_v1', 'status': 'PARTIAL', 'fingerprint': fingerprint, 'identity': identity, 'road_rule_profile': frozen['policy']['li3'].get('road_rule_profile', 'STRICT_MOTOR_LEGACY'), 'network_feature_mode': frozen['policy']['li3'].get('feature_source_mode', 'FULL'), 'building_entrance_profile': frozen['policy']['connectors'].get('building_entrance_profile', 'MULTI_ACCESS_LEGACY'), 'competitor_groups': {tier: [s['store_key'] for s in stores if s['kind'] == 'competitor' and s['tier'] == tier] for tier in ['PRIMARY', 'SECONDARY', 'UNVERIFIED_CORRIDOR']}, 'routing_clusters': {'basis': 'EXACT_SOURCE_ACCESS_NODE', 'source_nodes': len({c['node_id'] for c in package['connectors'] if c['kind'] == 'BUILDING' and c['building_id'] in eligible_set}), 'eligible_buildings': len(eligible_ids)}, 'output_path': str(root), 'rows': rows, 'summary': reconcile(rows), 'stores': stores, 'excluded_stores': excluded, 'attractor_gate': gate, 'market_inputs_complete': source_complete, 'primary_routing_changed': False, 'poi_input_status': facilities['status'], 'poi_required_for_pipeline': False, 'claim': 'EXPERIMENTAL_HUFF_ESTIMATES_NOT_CALIBRATED_CUSTOMER_PROBABILITIES', 'limitations': ['Bounded OSM motor graph; source gaps and unobserved barriers remain', 'Equal store attractiveness, beta=2; whole footprint winner, no random draw', 'Residential fallback remains an assumption where source use is generic']}
    write_json(root / 'result.json', result, exclusive=True)
    import csv, json
    with (root / 'market_buildings.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['building_id', 'area_m2', 'access_status', 'market_status', 'reason', 'winner_store_key', 'count_candidate', 'scores'])
        writer.writeheader()
        for row in rows:
            writer.writerow({**{k: row.get(k) for k in writer.fieldnames}, 'scores': json.dumps(row['scores'], sort_keys=True)})
    write_json(root / 'manifest.json', {'identity': identity, 'files': {n: sha(root / n) for n in ['result.json', 'market_buildings.csv']}}, exclusive=True)
    return result
