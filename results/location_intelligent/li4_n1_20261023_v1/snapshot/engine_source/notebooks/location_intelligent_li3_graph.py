"""OSM raw topology -> existing directed graph/evidence, never geometric joins."""
from collections import Counter, defaultdict
from copy import deepcopy
import math

from location_intelligent_motor_routing import motor_access


def node_permission(tags):
    barrier = tags.get('barrier')
    if not barrier:
        return True, 'NO_MAPPED_NODE_BARRIER'
    if tags.get('access') == 'private' or tags.get('motorcycle') == 'no' or tags.get('locked') == 'yes' or tags.get('gate:status') == 'closed':
        return False, 'CLOSED_OR_PROHIBITED_BARRIER'
    if any(':conditional' in k for k in tags) or (tags.get('opening_hours') and tags['opening_hours'] != '24/7'):
        return None, 'BARRIER_CONDITION_UNEVALUATED'
    if barrier in {'gate', 'lift_gate', 'swing_gate', 'chain'}:
        value, _ = motor_access(tags, 'service')
        return value, 'OWNER_PORTAL_OPEN_ASSUMPTION' if value else 'PORTAL_PERMISSION'
    if tags.get('motorcycle') in {'yes', 'designated', 'permissive'}:
        return True, 'EXPLICIT_MOTOR_BARRIER_PASSAGE'
    return None, 'PHYSICAL_BARRIER_UNVERIFIED'


def way_direction(tags):
    if any(k.startswith('oneway') and ':conditional' in k for k in tags):
        return None
    value = next((tags[k] for k in ['oneway:motorcycle', 'oneway:motor_vehicle', 'oneway:vehicle', 'oneway'] if k in tags), None)
    if value is None:
        return 1 if tags.get('junction') == 'roundabout' or tags.get('highway') == 'motorway' else 0
    return {'yes': 1, 'true': 1, '1': 1, '-1': -1, 'reverse': -1, 'no': 0, 'false': 0, '0': 0}.get(value)


def merge_elements(roads, features):
    elements, conflicts = {}, []
    for entry in [*roads, *features]:
        key = (entry['type'], entry['id'])
        if key in elements and elements[key] != entry:
            conflicts.append({'type': key[0], 'id': key[1], 'reason': 'SOURCE_ELEMENT_CONFLICT'})
        else:
            elements[key] = entry
    if conflicts:
        raise ValueError('OSM snapshot element conflicts: ' + str(conflicts[:5]))
    return elements


def build_graph(road_source, feature_source, frozen):
    from pyproj import Transformer
    if road_source.get('status') != 'SUCCEEDED':
        return {'status': 'SOURCE_MISSING' if road_source.get('status') == 'SOURCE_MISSING' else 'RETRIEVAL_FAILED', 'graph': None, 'diagnostics': {'reason': 'ROAD_SOURCE_UNAVAILABLE'}}
    if feature_source.get('status') != 'SUCCEEDED':
        return {'status': 'SOURCE_MISSING' if feature_source.get('status') == 'SOURCE_MISSING' else 'RETRIEVAL_FAILED', 'graph': None, 'diagnostics': {'reason': 'RESTRICTION_OR_BARRIER_SOURCE_UNAVAILABLE'}}
    raw = road_source['payload']
    features = feature_source['payload']
    elements = merge_elements(raw['elements'], features['elements'])
    road_way_ids = {e['id'] for e in raw['elements'] if e['type'] == 'way'}
    transform = Transformer.from_crs(4326, frozen['policy']['li3']['metric_crs'], always_xy=True)
    source_nodes = {i: e for (kind, i), e in elements.items() if kind == 'node'}
    nodes, edges, sources, rules, rejects = {}, [], {}, {}, []
    speed = frozen['policy']['travel']['reference_constant_speed']['value'] * 1000 / 3600
    for way_id in sorted(road_way_ids):
        way = elements[('way', way_id)]
        tags = way.get('tags', {})
        if not tags.get('highway') or not isinstance(way.get('nodes'), list) or len(way['nodes']) < 2:
            rejects.append({'way_id': way_id, 'reason': 'INVALID_ROAD_WAY'})
            continue
        if any(i not in source_nodes for i in way['nodes']):
            rejects.append({'way_id': way_id, 'reason': 'MISSING_SOURCE_NODE'})
            continue
        direction = way_direction(tags)
        permission, permission_reason = motor_access(tags, tags['highway'])
        if direction is None:
            permission, permission_reason = None, 'DIRECTION_UNVERIFIED'
        for index, (a, b) in enumerate(zip(way['nodes'], way['nodes'][1:])):
            if a == b:
                rejects.append({'way_id': way_id, 'segment_index': index, 'reason': 'ZERO_SOURCE_SEGMENT'})
                continue
            for i in (a, b):
                n = source_nodes[i]
                x, y = transform.transform(n['lon'], n['lat'])
                if not all(math.isfinite(v) for v in (x, y)):
                    raise ValueError('Invalid projected OSM coordinates')
                nodes[f'n{i}'] = {'node_id': f'n{i}', 'x': x, 'y': y}
            for u, v, label in ([(a, b, 'f')] if direction == 1 else [(b, a, 'r')] if direction == -1 else [(a, b, 'f'), (b, a, 'r')]):
                start, end = nodes[f'n{u}'], nodes[f'n{v}']
                distance = math.hypot(end['x']-start['x'], end['y']-start['y'])
                if distance == 0:
                    rejects.append({'way_id': way_id, 'segment_index': index, 'reason': 'COINCIDENT_DISTINCT_NODES'})
                    continue
                allowed, reason = permission, permission_reason
                barriers = []
                for i in (u, v):
                    status, why = node_permission(source_nodes[i].get('tags', {}))
                    if source_nodes[i].get('tags', {}).get('barrier'):
                        barriers.append({'node_id': i, 'allowed': status, 'reason': why})
                    if status is False:
                        allowed, reason = False, why
                    elif status is None and allowed is not False:
                        allowed, reason = None, why
                key = f'w{way_id}_s{index}_{label}'
                effective_tags = deepcopy(tags)
                for access_key in ('access', 'vehicle', 'motor_vehicle', 'motorcycle'):
                    directional = access_key + (':forward' if label == 'f' else ':backward')
                    if directional in tags:
                        effective_tags[access_key] = tags[directional]
                directional_allowed, directional_reason = motor_access(effective_tags, tags['highway'])
                if directional_allowed is False:
                    allowed, reason = False, directional_reason
                elif directional_allowed is None and allowed is True:
                    allowed, reason = None, directional_reason
                elif directional_allowed is True and permission is not True and direction is not None and not any(b['allowed'] is not True for b in barriers):
                    allowed, reason = True, directional_reason
                edges.append({'edge_id': key, 'u': start['node_id'], 'v': end['node_id'], 'key': key,
                              'length_m': distance, 'travel_time_s': distance/speed, 'highway': tags['highway'],
                              'service': tags.get('service'), 'access_allowed': allowed,
                              'geometry': {'type': 'LineString', 'coordinates': [[start['x'], start['y']], [end['x'], end['y']]]}})
                sources[key] = {'osm_way_id': way_id, 'segment_index': index, 'direction': label,
                                'raw_tags': deepcopy(tags), 'source_node_barriers': barriers,
                                'permission_reason': reason, 'source_version': way.get('version')}
                rules[key] = {'allowed': allowed, 'evidence_refs': [f'osm_way_{way_id}'], 'raw_tags': effective_tags, 'reason': reason}
    bbox = deepcopy(frozen['reference_metric_bbox'])
    if nodes:
        bbox = [min(bbox[0], min(n['x'] for n in nodes.values())), min(bbox[1], min(n['y'] for n in nodes.values())),
                max(bbox[2], max(n['x'] for n in nodes.values())), max(bbox[3], max(n['y'] for n in nodes.values()))]
    asof = raw.get('osm3s', {}).get('timestamp_osm_base')
    graph = {'schema_version': 'li_directed_graph_v1', 'graph_id': frozen['analysis_run_id'] + '-osm',
             'directed': True, 'crs': frozen['policy']['li3']['metric_crs'],
             'units': {'coordinates': 'm', 'distance': 'm', 'travel_time': 's'},
             'coverage': {'bbox': bbox, 'completeness': 'PARTIAL', 'scope': 'Bounded raw OSM extraction; no global connectivity/completeness claim'},
             'provenance': {'origin': 'OFFLINE_SNAPSHOT', 'source_version': 'OSM-' + (asof or 'unknown'),
                            'source_as_of': asof, 'description': 'Actual OSM nodes/ways; no geometry-crossing joins; fixed7kmh assumption'},
             'nodes': sorted(nodes.values(), key=lambda n: n['node_id']), 'edges': sorted(edges, key=lambda e: e['edge_id'])}
    return {'status': 'PARTIAL' if rejects else 'SUCCEEDED', 'graph': graph, 'edge_sources': sources,
            'edge_rules': rules, 'diagnostics': {'rejected_source_segments': rejects,
              'permissions': dict(Counter(str(r['allowed']) for r in rules.values())),
              'way_count': len(road_way_ids), 'source_as_of': asof}}


def apply_turns(graph, edge_sources, edge_rules, feature_source):
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for edge in graph['edges']:
        incoming[edge['v']].append(edge)
        outgoing[edge['u']].append(edge)
    blocked, diagnostics = [], []
    for relation in sorted((e for e in feature_source['payload']['elements'] if e['type'] == 'relation' and e.get('tags', {}).get('type') == 'restriction'), key=lambda e: e['id']):
        tags, members = relation.get('tags', {}), relation.get('members', [])
        rid = relation['id']
        if set(tags.get('except', '').split(';')) & {'motorcycle', 'motor_vehicle', 'vehicle'}:
            diagnostics.append({'relation_id': rid, 'reason': 'MOTORCYCLE_EXEMPT'})
            continue
        restriction = tags.get('restriction:motorcycle', tags.get('restriction:motor_vehicle', tags.get('restriction')))
        if not restriction and not any('conditional' in k and k.startswith('restriction') for k in tags):
            diagnostics.append({'relation_id': rid, 'reason': 'NOT_MOTOR_RESTRICTION'})
            continue
        from_ids = [m['ref'] for m in members if m.get('role') == 'from' and m.get('type') == 'way']
        to_ids = [m['ref'] for m in members if m.get('role') == 'to' and m.get('type') == 'way']
        via = [m for m in members if m.get('role') == 'via']
        simple = len(from_ids) == len(to_ids) == len(via) == 1 and via[0]['type'] == 'node'
        conditional = any('conditional' in k for k in tags)
        supported = simple and not conditional and restriction and (restriction.startswith('no_') or restriction.startswith('only_'))
        if supported:
            node = 'n' + str(via[0]['ref'])
            ins = [e for e in incoming[node] if edge_sources[e['edge_id']]['osm_way_id'] == from_ids[0]]
            outs = [e for e in outgoing[node] if edge_sources[e['edge_id']]['osm_way_id'] == to_ids[0]]
            if from_ids[0] == to_ids[0] and restriction != 'no_u_turn':
                supported = False
            else:
                for a in ins:
                    targets = [b for b in outs if restriction != 'no_u_turn' or b['v'] == a['u']]
                    forbidden = targets if restriction.startswith('no_') else [b for b in outgoing[node] if b not in targets]
                    for b in forbidden:
                        blocked.append({'from_edge': a['edge_id'], 'to_edge': b['edge_id'], 'evidence_ref': f'osm_relation_{rid}'})
                diagnostics.append({'relation_id': rid, 'reason': 'NORMALIZED_VIA_NODE', 'restriction': restriction,
                                    'incoming_matched': len(ins), 'target_outgoing_matched': len(outs)})
        if not supported:
            affected = set(from_ids + to_ids + [m['ref'] for m in via if m['type'] == 'way'])
            count = 0
            for key, source in edge_sources.items():
                if source['osm_way_id'] in affected:
                    if edge_rules[key]['allowed'] is not False:
                        edge_rules[key]['allowed'] = None
                        edge_rules[key]['reason'] = 'UNRESOLVED_TURN_QUARANTINE'
                    count += 1
            diagnostics.append({'relation_id': rid, 'reason': 'UNRESOLVED_TURN_QUARANTINE', 'affected_edges': count,
                                'restriction': restriction, 'conditional': conditional})
    unique = {(b['from_edge'], b['to_edge'], b['evidence_ref']): b for b in blocked}
    return sorted(unique.values(), key=lambda b: (b['from_edge'], b['to_edge'], b['evidence_ref'])), diagnostics


def graph_diagnostics(graph, rules, gap_m):
    import networkx as nx
    from shapely import STRtree
    from shapely.geometry import Point
    g = nx.DiGraph()
    g.add_nodes_from(n['node_id'] for n in graph['nodes'])
    g.add_edges_from((e['u'], e['v']) for e in graph['edges'] if rules[e['edge_id']]['allowed'] is True)
    components = sorted((sorted(c) for c in nx.weakly_connected_components(g)), key=lambda c: (-len(c), c[0]))
    membership = {key: index for index, component in enumerate(components) for key in component}
    nodes = {n['node_id']: n for n in graph['nodes']}
    ends = sorted(n for n in g if g.degree(n) in {1, 2})
    points = [Point(nodes[n]['x'], nodes[n]['y']) for n in ends]
    tree = STRtree(points)
    gaps = []
    for i, point in enumerate(points):
        for j in tree.query(point.buffer(gap_m)):
            j = int(j)
            if j > i and membership[ends[i]] != membership[ends[j]] and point.distance(points[j]) <= gap_m:
                gaps.append({'node_a': ends[i], 'node_b': ends[j], 'distance_m': point.distance(points[j])})
    return {'nodes': len(nodes), 'directed_edges': len(graph['edges']), 'allowed_edges': sum(r['allowed'] is True for r in rules.values()),
            'denied_edges': sum(r['allowed'] is False for r in rules.values()), 'unknown_edges': sum(r['allowed'] is None for r in rules.values()),
            'weak_components': len(components), 'largest_weak_component_nodes': len(components[0]) if components else 0,
            'isolated_nodes': len(list(nx.isolates(g))), 'strong_components': nx.number_strongly_connected_components(g),
            'suspicious_gap_threshold_m': gap_m, 'suspicious_gap_count': len(gaps), 'suspicious_gap_examples': sorted(gaps, key=lambda x: (x['distance_m'], x['node_a'], x['node_b']))[:50],
            'gap_warning': 'Diagnostic only; no edge inserted to repair gaps'}
