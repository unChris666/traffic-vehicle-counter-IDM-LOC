"""Audited frontage assumptions, mapped-barrier checks and source-edge splitting."""
from collections import defaultdict
from copy import deepcopy
import math


def barrier_index(feature_source, frozen):
    from pyproj import Transformer
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import polygonize, transform, unary_union
    from shapely import STRtree
    from location_intelligent_li3_graph import node_permission
    elements = feature_source['payload']['elements']
    nodes = {e['id']: e for e in elements if e['type'] == 'node'}
    ways = {e['id']: e for e in elements if e['type'] == 'way'}
    tx = Transformer.from_crs(4326, frozen['policy']['li3']['metric_crs'], always_xy=True).transform
    shapes, records, open_gates, unresolved = [], [], [], []
    def way_line(way):
        if any(i not in nodes for i in way.get('nodes', [])) or len(way.get('nodes', [])) < 2:
            return None
        return transform(tx, LineString([(nodes[i]['lon'], nodes[i]['lat']) for i in way['nodes']]))
    for node in nodes.values():
        tags = node.get('tags', {})
        if not tags.get('barrier'):
            continue
        allowed, reason = node_permission(tags)
        p = transform(tx, Point(node['lon'], node['lat']))
        if allowed is True:
            open_gates.append(p)
        else:
            shapes.append(p); records.append({'source': f'osm_node_{node["id"]}', 'kind': 'node_barrier', 'reason': reason, 'verified_denial': allowed is False})
    for way in ways.values():
        tags = way.get('tags', {})
        kind = 'water' if tags.get('natural') == 'water' or tags.get('waterway') else 'barrier' if tags.get('barrier') else None
        if not kind:
            continue
        if kind == 'water' and tags.get('tunnel') in {'yes', 'culvert'}:
            continue
        line = way_line(way)
        if line is None:
            unresolved.append({'source': f'osm_way_{way["id"]}', 'reason': 'MISSING_BARRIER_NODES'})
            continue
        geom = Polygon(line) if kind == 'water' and line.is_ring else line
        if not geom.is_valid:
            unresolved.append({'source': f'osm_way_{way["id"]}', 'reason': 'INVALID_BARRIER_GEOMETRY'})
            continue
        shapes.append(geom); records.append({'source': f'osm_way_{way["id"]}', 'kind': kind, 'verified_denial': False})
    for relation in elements:
        if relation['type'] != 'relation' or relation.get('tags', {}).get('natural') != 'water':
            continue
        outer, inner = [], []
        missing = False
        for member in relation.get('members', []):
            if member.get('type') != 'way':
                continue
            line = way_line(ways[member['ref']]) if member['ref'] in ways else None
            if line is None:
                missing = True
            else:
                (inner if member.get('role') == 'inner' else outer).append(line)
        polygons = list(polygonize(outer))
        if missing or not polygons:
            unresolved.append({'source': f'osm_relation_{relation["id"]}', 'reason': 'WATER_RELATION_UNRESOLVED'})
            continue
        geom = unary_union(polygons)
        if inner:
            geom = geom.difference(unary_union(list(polygonize(inner))))
        if not geom.is_valid:
            unresolved.append({'source': f'osm_relation_{relation["id"]}', 'reason': 'INVALID_WATER_RELATION'})
            continue
        shapes.append(geom); records.append({'source': f'osm_relation_{relation["id"]}', 'kind': 'water', 'verified_denial': False})
    return {'tree': STRtree(shapes), 'shapes': shapes, 'records': records, 'open_gates': open_gates, 'unresolved': unresolved}


def check_barriers(line, index, epsilon):
    """Water cannot be crossed by an off-road connector; bridges stay in network."""
    hits = []
    for i in index['tree'].query(line):
        i = int(i)
        shape, info = index['shapes'][i], index['records'][i]
        if not line.intersects(shape):
            continue
        intersection = line.intersection(shape)
        if info['kind'] != 'water' and not info.get('verified_denial') and index['open_gates']:
            from shapely.ops import unary_union
            openings = unary_union([p.buffer(epsilon) for p in index['open_gates']])
            if openings.covers(intersection):
                continue
        hits.append(info)
    if hits:
        return False, hits
    if index['unresolved']:
        return None, index['unresolved']
    return True, []


def generate_connectors(base, metrics, feature_source, frozen):
    import numpy as np
    from shapely import STRtree
    from shapely.geometry import LineString, Point, shape
    from shapely.ops import nearest_points
    from location_intelligent_li3_graph import apply_turns
    graph = base['graph']
    sources, rules = base['edge_sources'], base['edge_rules']
    policy = frozen['policy']
    epsilon = policy['li3']['projection_position_precision_m']
    inset = policy['li3']['entrance_inset_m']
    maximum = policy['connectors']['max_building_to_road_m']['value']
    ranking = {name: i for i, names in enumerate(policy['connectors']['road_class_hierarchy']) for name in names}
    groups = {}
    for edge in graph['edges']:
        key = edge['edge_id']; source = sources[key]
        group = f'w{source["osm_way_id"]}_s{source["segment_index"]}'
        if group not in groups:
            coords = edge['geometry']['coordinates']
            if source['direction'] == 'r':
                coords = list(reversed(coords))
            a, b = (edge['u'], edge['v']) if source['direction'] == 'f' else (edge['v'], edge['u'])
            groups[group] = {'line': LineString(coords), 'a': a, 'b': b, 'members': [], 'tags': source['raw_tags'], 'road_class': edge['highway']}
        groups[group]['members'].append(edge)
    group_ids = sorted(groups)
    geometries = [groups[g]['line'] for g in group_ids]
    tree = STRtree(geometries)
    barrier = barrier_index(feature_source, frozen)
    footprints = {b['building_id']: shape(b['metric_geometry']) for b in metrics['all_buildings']}
    footprint_ids = sorted(footprints)
    footprint_geoms = [footprints[k] for k in footprint_ids]
    footprint_tree = STRtree(footprint_geoms)
    cuts, candidates, rejected = defaultdict(dict), [], []
    target = Point(*metrics['target_xy'])
    diagnostics = {'barrier_features': len(barrier['shapes']), 'unresolved_barrier_geometries': barrier['unresolved'],
                   'entrance_claim': 'OWNER_ACCEPTED_ASSUMPTION_NOT_OBSERVED_ENTRANCE'}

    def candidate(kind, building_id, rep, footprint, index):
        group_id = group_ids[index]; group = groups[group_id]
        reason = None
        name = group['road_class']
        name = name[:-5] if name.endswith('_link') else name
        if name not in ranking:
            reason = 'UNRANKED_FRONTAGE_CLASS'
        elif not any(rules[e['edge_id']]['allowed'] is True for e in group['members']):
            reason = 'ACCESS_UNVERIFIED' if any(rules[e['edge_id']]['allowed'] is None for e in group['members']) else 'ACCESS_PROHIBITED'
        elif group['tags'].get('bridge') not in {None, 'no'} or group['tags'].get('tunnel') not in {None, 'no'} or group['tags'].get('layer', '0') not in {'0', '0.0'}:
            reason = 'GRADE_SEPARATED_DIRECT_ENTRY_UNVERIFIED'
        distance = rep.distance(group['line'])
        if kind == 'BUILDING' and distance > maximum:
            return None
        if reason:
            rejected.append({'kind': kind, 'building_id': building_id, 'source_segment': group_id, 'reason': reason, 'distance_m': distance})
            return None
        if kind == 'BUILDING':
            interior = footprint.buffer(-inset)
            interior = interior if not interior.is_empty else footprint.representative_point()
            entrance, access = nearest_points(interior, group['line'])
        else:
            entrance, access = target, nearest_points(target, group['line'])[1]
        position = group['line'].project(access)
        length = group['line'].length
        if position <= epsilon:
            node, access, position = group['a'], Point(group['line'].coords[0]), 0.0
        elif length-position <= epsilon:
            node, access, position = group['b'], Point(group['line'].coords[-1]), length
        else:
            q = round(position/epsilon)
            position = min(max(q*epsilon, epsilon), length-epsilon)
            access = group['line'].interpolate(position)
            node = group_id + f'_x{q}'
        coords = [[entrance.x, entrance.y], [access.x, access.y]] if kind == 'BUILDING' else [[access.x, access.y], [target.x, target.y]]
        line = LineString(coords)
        clear, hits = check_barriers(line, barrier, epsilon)
        if clear is True:
            for j in footprint_tree.query(line):
                j = int(j); fid = footprint_ids[j]
                if fid == building_id or (kind == 'TARGET' and footprint_geoms[j].covers(target)):
                    continue
                if line.intersection(footprint_geoms[j].buffer(-inset)).length > epsilon:
                    clear = False; hits.append({'source': fid, 'kind': 'other_building'})
        if clear is not True:
            rejected.append({'kind': kind, 'building_id': building_id, 'source_segment': group_id,
                             'reason': 'ACCESS_UNVERIFIED' if clear is None else 'MAPPED_BARRIER_OR_BUILDING',
                             'distance_m': distance, 'geometry': {'type': 'LineString', 'coordinates': coords}, 'barrier_hits': hits})
            return None
        cuts[group_id][node] = position
        value = {'connector_id': ('target' if kind == 'TARGET' else building_id) + '_' + group_id + '_' + node,
                 'kind': kind, 'building_id': building_id, 'node_id': node, 'source_segment': group_id,
                 'status': 'OWNER_ASSUMPTION', 'barrier_clear': True,
                 'evidence_refs': [group_id, 'OWNER_FRONTAGE_ASSUMPTION', 'OSM_MAPPED_BARRIER_CHECK'],
                 'geometry': {'type': 'LineString', 'coordinates': coords}, 'class_rank': ranking[name],
                 'candidate_distance_m': distance, 'connector_distance_m': line.length,
                 'warnings': ['NOT_A_VERIFIED_PHYSICAL_ENTRANCE', 'OSM_ABSENCE_IS_NOT_PROOF_OF_NO_BARRIER']}
        candidates.append(value)
        return value

    # No numerical target search cap. Nearest valid source geometry wins;
    # grade/barrier checks can reject it and proceed to the next road.
    if group_ids:
        distances = np.array([target.distance(g) for g in geometries])
        for i in sorted(range(len(group_ids)), key=lambda i: (distances[i], group_ids[i])):
            if candidate('TARGET', None, target, None, i) is not None:
                break
    for b in sorted(metrics['selected_buildings'], key=lambda b: b['building_id']):
        point, footprint = Point(*b['representative_point_m']), footprints[b['building_id']]
        seen = set()
        for i in sorted(map(int, tree.query(point.buffer(maximum))), key=lambda i: group_ids[i]):
            c = candidate('BUILDING', b['building_id'], point, footprint, i)
            if c:
                unique = (c['node_id'], c['class_rank'])
                if unique in seen:
                    candidates.remove(c)
                    rejected.append({'kind': 'BUILDING', 'building_id': b['building_id'], 'source_segment': c['source_segment'], 'reason': 'DUPLICATE_NODE_AND_CLASS'})
                else:
                    seen.add(unique)
    nodes = {n['node_id']: deepcopy(n) for n in graph['nodes']}
    new_edges, new_sources, new_rules, incidents = [], {}, {}, defaultdict(list)
    speed = policy['travel']['reference_constant_speed']['value']*1000/3600
    for group_id in group_ids:
        group = groups[group_id]; line = group['line']
        positions = {group['a']: 0.0, group['b']: line.length, **cuts.get(group_id, {})}
        ordered = sorted(positions, key=lambda n: (positions[n], n))
        for node in ordered:
            point = line.interpolate(positions[node])
            if node not in nodes:
                nodes[node] = {'node_id': node, 'x': point.x, 'y': point.y}
        for parent in group['members']:
            pkey = parent['edge_id']; forward = sources[pkey]['direction'] == 'f'
            path = ordered if forward else list(reversed(ordered))
            for i, (a, b) in enumerate(zip(path, path[1:])):
                start, end = nodes[a], nodes[b]
                coords = [[start['x'], start['y']], [end['x'], end['y']]]
                distance = math.dist(*coords)
                if distance <= 0:
                    continue
                key = pkey + f'_p{i}'
                edge = {**parent, 'edge_id': key, 'u': a, 'v': b, 'key': key, 'length_m': distance,
                        'travel_time_s': distance/speed, 'geometry': {'type': 'LineString', 'coordinates': coords}}
                new_edges.append(edge)
                new_sources[key] = {**deepcopy(sources[pkey]), 'parent_edge_id': pkey}
                new_rules[key] = deepcopy(rules[pkey])
                incidents[(group_id, a)].append(key); incidents[(group_id, b)].append(key)
    new_graph = {**graph, 'nodes': sorted(nodes.values(), key=lambda n: n['node_id']), 'edges': sorted(new_edges, key=lambda e: e['edge_id'])}
    for c in candidates:
        c['road_edge_id'] = min(k for k in incidents[(c['source_segment'], c['node_id'])] if new_rules[k]['allowed'] is True)
    blocked, turn_diagnostics = apply_turns(new_graph, new_sources, new_rules, feature_source)
    # Quarantine inherited by edge rules after split; connector usability is
    # checked again by the existing motor engine, not asserted by this generator.
    diagnostics.update(connectors=len(candidates), rejected_candidates=len(rejected),
                       target_connector_found=any(c['kind'] == 'TARGET' for c in candidates),
                       turn_relations=turn_diagnostics, grade_separation_policy='NO_DIRECT_ENTRY_TO_ELEVATED_OR_TUNNEL_EDGE')
    return {'graph': new_graph, 'edge_sources': new_sources, 'edge_rules': new_rules,
            'blocked_turns': blocked, 'connectors': sorted(candidates, key=lambda c: c['connector_id']),
            'rejected_candidates': rejected, 'diagnostics': diagnostics}
