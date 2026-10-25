"""LI-2: offline directed multigraph diagnostics; final accessibility is blocked.

D02/D03/D05/D10 are OPEN in the audited decision register. Numeric N1 reference
results are explicitly separate from approved business/physical accessibility.
No live retrieval, OSMnx, implicit reverse edges, repair or framework imports.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import heapq
import json
import math
from pathlib import Path
from typing import Any
from traffic_location.location.area._kernel.location_intelligent_validator import _Validator, _strict_pairs, _reject_constant, canonical_hash, validate
GRAPH_SCHEMA = 'li_directed_graph_v1'
CONFIG_SCHEMA = 'li_routing_config_v1'
RESULT_SCHEMA = 'location_intelligent_routing_v1'
OPEN_DECISIONS = ('D02', 'D03', 'D05', 'D10')

def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False

def inside_bbox(point, bbox):
    """Closed boundary, no hidden tolerance."""
    return bbox[0] <= point[0] <= bbox[2] and bbox[1] <= point[1] <= bbox[3]

def within_snap_limit(distance, maximum):
    return distance <= maximum

def reference_time_pass(total_min, maximum=10.0):
    """N1 compares its already-rounded three-decimal time strictly below limit."""
    return round(total_min, 3) < maximum

def classify_road(highway, service):
    h, s = ((highway or '').strip().lower(), (service or '').strip().lower())
    if h in {'service', 'track', 'path', 'footway', 'pedestrian', 'steps', 'cycleway', 'bridleway'} or s in {'driveway', 'alley', 'parking_aisle'}:
        return 'gang'
    if h in {'residential', 'unclassified', 'living_street', 'road'}:
        return 'street'
    if h in {'tertiary', 'tertiary_link', 'secondary', 'secondary_link'}:
        return 'main street'
    if h in {'primary', 'primary_link', 'trunk', 'trunk_link', 'motorway', 'motorway_link'}:
        return 'highway'
    return None

def shortest_route(graph, start, target, weight='travel_time_s'):
    """Dijkstra: cost, then fewest hops, then lexicographic edge-ID sequence.

    Nonnegative weights and validated node/edge references are prerequisites.
    Hops before lexicographic IDs also terminates equal-cost zero-edge cycles.
    Every stored directed parallel edge is considered; nothing is reversed.
    """
    adjacency = {row['node_id']: [] for row in graph['nodes']}
    edges = {row['edge_id']: row for row in graph['edges']}
    if start not in adjacency or target not in adjacency:
        return None
    for edge in graph['edges']:
        adjacency[edge['u']].append(edge)
    best = {start: (0.0, 0, ())}
    queue = [(0.0, 0, (), start)]
    while queue:
        cost, hops, path, node = heapq.heappop(queue)
        if best.get(node) != (cost, hops, path):
            continue
        if node == target:
            records = [edges[key] for key in path]
            return {'nodes': [start, *[edge['v'] for edge in records]], 'edges': list(path), 'weight': weight, 'weight_value': cost, 'distance_m': sum((edge['length_m'] for edge in records)), 'time_s': sum((edge['travel_time_s'] for edge in records))}
        for edge in sorted(adjacency[node], key=lambda row: row['edge_id']):
            label = (cost + edge[weight], hops + 1, (*path, edge['edge_id']))
            if edge['v'] not in best or label < best[edge['v']]:
                best[edge['v']] = label
                heapq.heappush(queue, (*label, edge['v']))
    return None

def _project_to_line(point, coords):
    lengths = [math.dist(a, b) for a, b in zip(coords, coords[1:])]
    total, walked, best = (sum(lengths), 0.0, None)
    for i, (a, b, length) in enumerate(zip(coords, coords[1:], lengths)):
        if length == 0:
            continue
        fraction = max(0.0, min(1.0, ((point[0] - a[0]) * ((b[0] - a[0]) / length) + (point[1] - a[1]) * ((b[1] - a[1]) / length)) / length))
        access = [a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1])]
        position = walked + fraction * length
        candidate = (math.dist(point, access), position, i, access)
        if best is None or candidate[:3] < best[:3]:
            best = candidate
        walked += length
    return (best[0], best[1] / total, best[3], [best[3], *coords[best[2] + 1:]])

def _configuration(v, config, context, selection, graph):
    c = v.obj(config, 'routing_config', 'schema_version version analysis_run_id context_hash selection_hash graph_hash profile path_weight parameters policy_refs connector_policy target_connector_policy')
    if c.get('schema_version') != CONFIG_SCHEMA:
        v.issue('ROUTING_SCHEMA_UNSUPPORTED', 'routing_config.schema_version', f'Use {CONFIG_SCHEMA}.')
    for key in ('version',):
        v.text(c.get(key), 'routing_config.' + key)
    for key in ('analysis_run_id', 'context_hash'):
        if c.get(key) != context.get(key):
            v.issue('ROUTING_CONTEXT_MISMATCH', 'routing_config.' + key, 'Bind routing configuration to the validated current context.')
    for key, value in (('selection_hash', selection), ('graph_hash', graph)):
        if v.digest(c.get(key), 'routing_config.' + key) and c[key] != canonical_hash(value):
            v.issue('ROUTING_HASH_MISMATCH', 'routing_config.' + key, "Verify the canonical JSON input hash; do not use another run's result.")
    v.enum(c.get('profile'), {'N1_REFERENCE_ONLY'}, 'routing_config.profile')
    v.enum(c.get('path_weight'), {'length_m', 'travel_time_s'}, 'routing_config.path_weight')
    v.enum(c.get('connector_policy'), {'EXPLICIT_FIXTURE_ACCESS_AND_N1_ROAD_CLASS'}, 'routing_config.connector_policy')
    v.enum(c.get('target_connector_policy'), {'OMIT_N1_REFERENCE_REPORT_OFFSET'}, 'routing_config.target_connector_policy')
    refs = v.obj(c.get('policy_refs'), 'routing_config.policy_refs', ' '.join(OPEN_DECISIONS))
    for key in OPEN_DECISIONS:
        v.text(refs.get(key), 'routing_config.policy_refs.' + key)
    params = v.obj(c.get('parameters'), 'routing_config.parameters', 'max_building_to_road_m max_travel_min motorcycle_speed_kmh max_target_snap_m')
    expected = {'max_building_to_road_m': ('m', 125.0), 'max_travel_min': ('min', 10.0), 'motorcycle_speed_kmh': ('km/h', 7.0), 'max_target_snap_m': ('m', None)}
    values = {}
    for key, (unit, reference) in expected.items():
        path = 'routing_config.parameters.' + key
        q = v.obj(params.get(key), path, 'value unit', 'unknown_reason')
        if q.get('unit') != unit:
            v.issue('ROUTING_UNIT_INVALID', path, f'Declare {unit} explicitly.')
        value = q.get('value')
        if key == 'max_target_snap_m' and value is None:
            v.text(q.get('unknown_reason'), path + '.unknown_reason')
            values[key] = None
        elif not _number(value) or value < 0 or (key != 'max_target_snap_m' and value == 0):
            v.issue('ROUTING_PARAMETER_INVALID', path, 'Supply a finite positive reference quantity, or a nonnegative snap diagnostic limit.')
        elif reference is not None and value != reference:
            v.issue('REFERENCE_CONTROL_CHANGED', path, 'This profile preserves N1 controls125m/10min/7kmh; no business policy change is approved.')
        else:
            values[key] = value
        if 'unknown_reason' in q:
            v.text(q['unknown_reason'], path + '.unknown_reason')
    return values

def _graph(v, graph, metric_crs):
    g = v.obj(graph, 'graph', 'schema_version graph_id directed crs units coverage provenance nodes edges')
    if g.get('schema_version') != GRAPH_SCHEMA:
        v.issue('GRAPH_SCHEMA_UNSUPPORTED', 'graph.schema_version', f'Use {GRAPH_SCHEMA}.')
    v.identifier(g.get('graph_id'), 'graph.graph_id')
    if g.get('directed') is not True:
        v.issue('GRAPH_NOT_DIRECTED', 'graph.directed', 'Supply explicit directed edges; undirected data is not expanded.')
    if g.get('crs') != metric_crs:
        v.issue('GRAPH_CRS_MISMATCH', 'graph.crs', 'Graph must use the current explicit metric CRS.')
    if g.get('units') != {'coordinates': 'm', 'distance': 'm', 'travel_time': 's'}:
        v.issue('GRAPH_UNITS_INVALID', 'graph.units', 'Graph coordinates/distances must be meters and travel time seconds.')
    cov = v.obj(g.get('coverage'), 'graph.coverage', 'bbox completeness scope')
    bbox = cov.get('bbox')
    valid_bbox = isinstance(bbox, list) and len(bbox) == 4 and all((_number(x) for x in bbox)) and (bbox[0] < bbox[2]) and (bbox[1] < bbox[3])
    if not valid_bbox:
        v.issue('GRAPH_COVERAGE_INVALID', 'graph.coverage.bbox', 'Declare a finite [xmin,ymin,xmax,ymax] metric coverage rectangle.')
    elif not math.isfinite(math.dist(bbox[:2], bbox[2:])):
        v.issue('GRAPH_COVERAGE_UNUSABLE', 'graph.coverage.bbox', 'Coverage span must support finite metric calculations.')
    v.enum(cov.get('completeness'), {'COMPLETE', 'PARTIAL', 'UNKNOWN'}, 'graph.coverage.completeness')
    v.text(cov.get('scope'), 'graph.coverage.scope')
    prov = v.obj(g.get('provenance'), 'graph.provenance', 'origin source_version source_as_of description')
    v.enum(prov.get('origin'), {'SYNTHETIC_FIXTURE', 'OFFLINE_SNAPSHOT'}, 'graph.provenance.origin')
    v.text(prov.get('source_version'), 'graph.provenance.source_version')
    v.text(prov.get('description'), 'graph.provenance.description')
    if prov.get('source_as_of') is not None:
        v.stamp(prov['source_as_of'], 'graph.provenance.source_as_of')
    nodes, edge_ids, triples = ({}, set(), set())
    for index, row in enumerate(v.array(g.get('nodes'), 'graph.nodes')):
        path = f'graph.nodes[{index}]'
        n = v.obj(row, path, 'node_id x y')
        key = n.get('node_id')
        if not v.identifier(key, path + '.node_id'):
            continue
        if key in nodes:
            v.issue('GRAPH_NODE_DUPLICATE', path, 'Keep unique node identifiers.')
        if not all((_number(n.get(k)) for k in ('x', 'y'))):
            v.issue('GRAPH_NODE_COORDINATES', path, 'Supply finite projected XY coordinates.')
        elif valid_bbox and (not inside_bbox([n['x'], n['y']], bbox)):
            v.issue('GRAPH_NODE_OUTSIDE_COVERAGE', path, 'Nodes must lie inside the declared graph extent.')
        nodes[key] = n
    for index, row in enumerate(v.array(g.get('edges'), 'graph.edges')):
        path = f'graph.edges[{index}]'
        e = v.obj(row, path, 'edge_id u v key length_m travel_time_s highway service access_allowed geometry')
        key = e.get('edge_id')
        if not v.identifier(key, path + '.edge_id'):
            continue
        if key in edge_ids:
            v.issue('GRAPH_EDGE_DUPLICATE', path, 'Keep unique edge identifiers.')
        edge_ids.add(key)
        endpoints = True
        for name in ('u', 'v'):
            if not isinstance(e.get(name), str) or e[name] not in nodes:
                v.issue('GRAPH_NODE_REF_INVALID', path + '.' + name, 'Reference an existing node.')
                endpoints = False
        if v.text(e.get('key'), path + '.key') and endpoints:
            triple = (e['u'], e['v'], e['key'])
            if triple in triples:
                v.issue('GRAPH_PARALLEL_KEY_DUPLICATE', path, 'Use unique (u,v,key) identities for parallel edges.')
            triples.add(triple)
        for name in ('length_m', 'travel_time_s'):
            if not _number(e.get(name)) or e[name] < 0:
                v.issue('GRAPH_COST_INVALID', path + '.' + name, 'Supply explicit finite nonnegative costs; missing is not zero.')
        for name in ('highway', 'service'):
            if e.get(name) is not None:
                v.text(e[name], path + '.' + name)
        if e.get('access_allowed') is not None and type(e['access_allowed']) is not bool:
            v.issue('CONNECTOR_PERMISSION_INVALID', path + '.access_allowed', 'Declare a fixture permission bool or explicit unknown null.')
        geom = e.get('geometry')
        if geom is None:
            continue
        coords = geom.get('coordinates') if isinstance(geom, dict) else None
        valid = isinstance(geom, dict) and geom.get('type') == 'LineString' and isinstance(coords, list) and (len(coords) >= 2) and all((isinstance(x, list) and len(x) == 2 and all((_number(v) for v in x)) for x in coords))
        if not valid:
            v.issue('GRAPH_GEOMETRY_INVALID', path + '.geometry', 'Supply an explicit 2D metric LineString or null; do not infer road geometry.')
            continue
        if valid_bbox and (not all((inside_bbox(x, bbox) for x in coords))):
            v.issue('GRAPH_EDGE_OUTSIDE_COVERAGE', path, 'Stored road geometry leaves the declared extent.')
        geom_length = sum((math.dist(a, b) for a, b in zip(coords, coords[1:])))
        if not math.isfinite(geom_length):
            v.issue('GRAPH_GEOMETRY_UNUSABLE', path, 'Road length must support finite metric calculations.')
        elif geom_length <= 0:
            v.issue('GRAPH_GEOMETRY_EMPTY', path, 'Access road geometry must have positive length.')
        if endpoints and all((_number(nodes[e[k]].get(axis)) for k in ('u', 'v') for axis in ('x', 'y'))):
            if coords[0] != [nodes[e['u']]['x'], nodes[e['u']]['y']] or coords[-1] != [nodes[e['v']]['x'], nodes[e['v']]['y']]:
                v.issue('GRAPH_EDGE_ORIENTATION', path, 'Geometry endpoints must match stored u→v; it is never auto-reversed.')
        if _number(e.get('length_m')) and e['length_m'] == 0:
            v.issue('GRAPH_COST_GEOMETRY_CONFLICT', path, 'A positive road geometry cannot declare zero physical length.')
    for key in ('length_m', 'travel_time_s'):
        edge_rows = g.get('edges') if isinstance(g.get('edges'), list) else []
        vals = [e[key] for e in edge_rows if isinstance(e, dict) and _number(e.get(key))]
        if not math.isfinite(sum(vals)):
            v.issue('GRAPH_COST_UNUSABLE', 'graph.edges', 'Aggregated nonnegative route costs must remain finite.')
    return nodes

def _selection(v, selection, context, manifest, metric_crs):
    if not isinstance(selection, dict) or selection.get('schema_version') != 'location_intelligent_building_selection_v1':
        v.issue('BUILDING_RESULT_INVALID', 'buildings', 'Supply the selected LI-1 result envelope.')
        return []
    if selection.get('status') not in ('SUCCEEDED', 'PARTIAL'):
        v.issue('BUILDING_RESULT_UNAVAILABLE', 'buildings.status', 'Only available LI-1 selections can be routed.', 'BLOCKER')
    snap = selection.get('snapshot')
    if not isinstance(snap, dict):
        v.issue('BUILDING_PROVENANCE_INVALID', 'buildings.snapshot', 'Supply source/config/context provenance.')
        return []
    if not isinstance(snap.get('fingerprint'), dict):
        v.issue('BUILDING_PROVENANCE_INVALID', 'buildings.snapshot.fingerprint', 'Supply the verified snapshot fingerprint object.')
        return []
    if selection.get('analysis_run_id') != context['analysis_run_id'] or snap.get('context_hash') != context['context_hash'] or snap.get('config_hash') != canonical_hash(context['config']):
        v.issue('BUILDING_CONTEXT_MISMATCH', 'buildings', 'Select the LI-1 output for this immutable target/config.')
    source = next((x for x in manifest['sources'] if x['source_ref_id'] == snap.get('source_ref_id')), None)
    required = {ref for r in manifest['modules'] if r['module'] == 'area_coverage' for ref in r['required_inputs']}
    if source is None or source['source_ref_id'] not in required or source['inventory_id'] != 'SRC04' or (source.get('fingerprint') != snap.get('fingerprint')) or (snap.get('crs') != 'EPSG:4326') or (source.get('crs') != snap.get('crs')) or (source.get('schema_version') != snap.get('schema_version')):
        v.issue('BUILDING_SOURCE_MISMATCH', 'buildings.snapshot', 'Bind selected records to their verified current source snapshot.')
    rows = v.array(selection.get('selected'), 'buildings.selected')
    seen = set()
    summary = selection.get('summary')
    ledger = selection.get('reject_ledger')
    valid_counts = isinstance(summary, dict) and all((type(summary.get(k)) is int and summary[k] >= 0 for k in ('selected', 'excluded', 'rejected', 'source_records', 'accounted_records')))
    if not valid_counts or summary.get('selected') != len(rows) or (not isinstance(ledger, list)) or (summary['excluded'] + summary['rejected'] != len(ledger)) or (summary['accounted_records'] != len(rows) + len(ledger)) or (summary['source_records'] != summary['accounted_records']) or (source is not None and source.get('row_count') != summary['source_records']):
        v.issue('BUILDING_COUNT_MISMATCH', 'buildings.summary', 'Selected count must match actual records.')
    indices = []
    for item in [*rows, *(ledger if isinstance(ledger, list) else [])]:
        if not isinstance(item, dict) or type(item.get('source_row_index')) is not int:
            v.issue('BUILDING_ROW_IDENTITY_INVALID', 'buildings', 'Every disposition needs an explicit integer source row.')
        else:
            indices.append(item['source_row_index'])
    if valid_counts and sorted(indices) != list(range(summary['source_records'])):
        v.issue('BUILDING_ROW_RECONCILIATION', 'buildings', 'Source rows must appear exactly once across selected and ledger.')
    for index, row in enumerate(rows):
        p = f'buildings.selected[{index}]'
        if not isinstance(row, dict):
            v.issue('BUILDING_RECORD_INVALID', p, 'Supply a selected BuildingRecord.')
            continue
        key = row.get('building_id')
        if v.text(key, p + '.building_id'):
            if key in seen:
                v.issue('BUILDING_ID_DUPLICATE', p, 'Route each selected source identity once.')
            seen.add(key)
        if row.get('metric_crs') != metric_crs or row.get('analysis_run_id') != context['analysis_run_id'] or row.get('source_ref_id') != snap.get('source_ref_id') or (row.get('snapshot_sha256') != (snap.get('fingerprint') or {}).get('value')):
            v.issue('BUILDING_RECORD_BINDING', p, 'Record source/CRS/context must match the selected snapshot.')
        point = row.get('representative_point')
        coords = point.get('coordinates') if isinstance(point, dict) else None
        if not isinstance(point, dict) or point.get('type') != 'Point' or (not isinstance(coords, list)) or (len(coords) != 2) or (not all((_number(x) for x in coords))) or (not (-180 <= coords[0] <= 180 and -90 <= coords[1] <= 90)):
            v.issue('BUILDING_POINT_INVALID', p, 'Supply explicit WGS84 [lon,lat] representative point from LI-1.')
        else:
            zone, south = (int(metric_crs[-2:]), metric_crs.startswith('EPSG:327'))
            if not (-80 <= coords[1] <= 84 and (coords[1] <= 0 if south else coords[1] >= 0) and (-180 + 6 * (zone - 1) <= coords[0] <= -180 + 6 * zone)):
                v.issue('BUILDING_POINT_CRS_DOMAIN', p, "Selected point must retain LI-1's declared UTM domain.")
    return rows

def _edge_ref(edge):
    return {key: edge[key] for key in ('edge_id', 'u', 'v', 'key')}

def _route_geometry(tail, path, edges):
    coords = deepcopy(tail)
    for key in path['edges']:
        geom = edges[key]['geometry']
        if geom is None:
            return (None, 'MISSING_NETWORK_EDGE_GEOMETRY')
        coords.extend(deepcopy(geom['coordinates'][1:]))
    compact = []
    for xy in coords:
        if not compact or xy != compact[-1]:
            compact.append(xy)
    return ({'type': 'LineString', 'coordinates': compact}, 'AVAILABLE_ROAD_GEOMETRY') if len(compact) >= 2 else (None, 'ZERO_ROAD_LENGTH')

def route_buildings(context: Any, manifest: Any, buildings: Any, graph: Any, config: Any, *, root: Path | str) -> dict:
    result = {'schema_version': RESULT_SCHEMA, 'status': 'BLOCKED', 'routing_gate': 'BLOCKED', 'accessibility_gate': 'BLOCKED', 'unresolved_decisions': list(OPEN_DECISIONS), 'live_readiness': 'NOT_VERIFIED', 'routes': [], 'summary': None, 'diagnostics': [], 'limitations': ['N1 reference/fixture diagnostics only; no approved business accessibility.', 'Declared graph coverage and access permission are not real-world/legal access proof.']}

    def stop(code, message, status='FAILED'):
        result['status'] = status
        result['diagnostics'].append({'code': code, 'message': message})
        return result
    gate = validate(context, manifest, root=root)
    result['li0'] = gate
    if gate['offline_readiness'] != 'READY':
        return stop('LI0_INPUT_BLOCKED', 'Supply valid, available current context/source inputs.', 'BLOCKED')
    if graph is None:
        return stop('GRAPH_UNAVAILABLE', 'Supply a local graph; it is not retrieved automatically.', 'BLOCKED')
    if not isinstance(config, dict) or not isinstance(graph, dict):
        return stop('ROUTING_INPUT_INVALID', 'Supply graph and routing-config JSON objects.')
    v = _Validator(Path(root))
    for name, value in (('buildings', buildings), ('graph', graph), ('routing_config', config)):
        v.json_values(value, name)
    if v.diagnostics:
        result['diagnostics'] = v.diagnostics
        return stop('ROUTING_JSON_INVALID', 'Correct malformed/nonfinite routing input.')
    params = _configuration(v, config, context, buildings, graph)
    metric_crs = context['config']['area_coverage']['metric_crs']
    nodes = _graph(v, graph, metric_crs)
    selected = _selection(v, buildings, context, manifest, metric_crs)
    if v.diagnostics:
        result['diagnostics'] = sorted(v.diagnostics, key=lambda x: (x['path'], x['code']))
        return stop('ROUTING_INPUT_INVALID', 'Correct graph/config/selected-result contract violations.', 'FAILED' if any((x['severity'] == 'ERROR' for x in v.diagnostics)) else 'BLOCKED')
    result['provenance'] = {'analysis_run_id': context['analysis_run_id'], 'target': deepcopy(context['target']), 'context_hash': context['context_hash'], 'routing_config_hash': canonical_hash(config), 'selection_hash': canonical_hash(buildings), 'graph_hash': canonical_hash(graph), 'graph_id': graph['graph_id'], 'graph_provenance': deepcopy(graph['provenance']), 'policy_refs': deepcopy(config['policy_refs']), 'metric_crs': metric_crs, 'profile': config['profile'], 'path_weight': config['path_weight']}
    try:
        from traffic_location.location.area._kernel.location_intelligent_buildings import _backend, _spatial
        _, ogr, osr = _backend()
        with osr.ExceptionMgr(useExceptions=True):
            transform, target = _spatial(metric_crs, context['target'], ogr, osr)
            inverse = transform.GetInverse()
        target_xy = [target.GetX(), target.GetY()]
    except (ImportError, OSError, RuntimeError, ValueError):
        return stop('ROUTING_TRANSFORM_UNAVAILABLE', 'Provide the offline CRS backend validated for LI-1.', 'BLOCKED')
    bbox = graph['coverage']['bbox']
    edges = {e['edge_id']: e for e in graph['edges']}
    speed = params['motorcycle_speed_kmh'] * 1000 / 3600
    result['provenance']['constant_speed_mps'] = speed
    parity = config['path_weight'] == 'travel_time_s' and all((e['travel_time_s'] == e['length_m'] / speed for e in graph['edges']))
    result['provenance']['n1_network_cost_model_matches'] = parity
    if not parity:
        result['diagnostics'].append({'code': 'WEIGHTED_GRAPH_DIAGNOSTIC_VARIANT', 'message': "Explicit path weight/edge costs differ from N1's constant-speed network; reference distance/time formula is reported separately."})
    if nodes:
        snap_key = min(nodes, key=lambda key: (math.dist(target_xy, [nodes[key]['x'], nodes[key]['y']]), key))
        snap_distance = math.dist(target_xy, [nodes[snap_key]['x'], nodes[snap_key]['y']])
    else:
        snap_key, snap_distance = (None, None)
    for building in selected:
        row = {'analysis_run_id': context['analysis_run_id'], 'building_id': building['building_id'], 'source_row_index': building.get('source_row_index'), 'route_found': None, 'accessible': None, 'reference_accessible': None, 'accessibility_reason': 'POLICY_UNRESOLVED', 'unresolved_decisions': list(OPEN_DECISIONS), 'selected_candidate': None, 'candidates': [], 'candidate_diagnostics': [], 'route_geometry': None, 'route_geometry_crs': 'EPSG:4326', 'route_geometry_status': 'NOT_EVALUATED', 'coverage_status': graph['coverage']['completeness'], 'target_connection': {'node_id': snap_key, 'snap_distance_m': snap_distance, 'snap_status': 'NOT_EVALUATED', 'connector_included_in_reference': False, 'omitted_connector_distance_m': snap_distance, 'omitted_connector_time_s': snap_distance / speed if snap_distance is not None else None}}
        result['routes'].append(row)
        if not inside_bbox(target_xy, bbox):
            row.update(reason='TARGET_OUTSIDE_COVERAGE', coverage_status='TARGET_OUTSIDE')
            continue
        try:
            lon, lat = building['representative_point']['coordinates']
            with osr.ExceptionMgr(useExceptions=True):
                xy = list(transform.TransformPoint(lon, lat)[:2])
        except (RuntimeError, ValueError):
            row['reason'] = 'BUILDING_TRANSFORM_FAILED'
            continue
        if not all((_number(x) for x in xy)):
            row['reason'] = 'BUILDING_TRANSFORM_FAILED'
            continue
        row['building_point_m'] = xy
        if not inside_bbox(xy, bbox):
            row.update(reason='BUILDING_OUTSIDE_COVERAGE', coverage_status='BUILDING_OUTSIDE')
            continue
        if not nodes:
            row.update(reason='EMPTY_GRAPH', route_found=False)
            continue
        limit = params['max_target_snap_m']
        if limit is None:
            row['target_connection']['snap_status'] = 'UNRESOLVED'
            row['reason'] = 'TARGET_SNAP_POLICY_UNRESOLVED'
            continue
        if not within_snap_limit(snap_distance, limit):
            row['target_connection']['snap_status'] = 'LIMIT_EXCEEDED'
            row['reason'] = 'TARGET_SNAP_LIMIT_EXCEEDED'
            continue
        row['target_connection']['snap_status'] = 'WITHIN_DECLARED_FIXTURE_LIMIT'
        for edge in sorted(graph['edges'], key=lambda x: x['edge_id']):
            rejection = None
            road = classify_road(edge['highway'], edge['service'])
            if road not in ('street', 'main street', 'highway'):
                rejection = 'ROAD_CLASS_INELIGIBLE'
            elif edge['geometry'] is None:
                rejection = 'ACCESS_GEOMETRY_MISSING'
            if rejection:
                row['candidate_diagnostics'].append({'edge': _edge_ref(edge), 'reason': rejection})
                continue
            offset, fraction, access, tail = _project_to_line(xy, edge['geometry']['coordinates'])
            if offset > params['max_building_to_road_m']:
                row['candidate_diagnostics'].append({'edge': _edge_ref(edge), 'reason': 'ACCESS_DISTANCE_EXCEEDED', 'distance_m': offset})
                continue
            if edge['access_allowed'] is not True:
                row['candidate_diagnostics'].append({'edge': _edge_ref(edge), 'reason': 'CONNECTOR_REJECTED' if edge['access_allowed'] is False else 'CONNECTOR_PERMISSION_UNKNOWN', 'distance_m': offset})
                continue
            path = shortest_route(graph, edge['v'], snap_key, config['path_weight'])
            candidate = {'edge': _edge_ref(edge), 'road_type': road, 'connector_status': 'EXPLICIT_FIXTURE_PERMISSION_NOT_PHYSICAL_PROOF', 'building_connector_distance_m': offset, 'building_connector_time_s': offset / speed, 'access_point_m': access, 'partial_edge_fraction': 1 - fraction, 'partial_edge_distance_m': (1 - fraction) * edge['length_m'], 'route_found': path is not None, 'network': path, 'reason': 'NO_DIRECTED_PATH' if path is None else 'DIRECTED_PATH_FOUND'}
            row['candidates'].append(candidate)
            if path is None:
                continue
            total = offset + candidate['partial_edge_distance_m'] + path['distance_m']
            total_min = total / speed / 60
            candidate.update(partial_edge_reference_time_s=candidate['partial_edge_distance_m'] / speed, network_reference_time_s=path['distance_m'] / speed, total_road_distance_m=total, total_reference_time_min=total_min, threshold_time_min=round(total_min, 3), reference_accessible=reference_time_pass(total_min, params['max_travel_min']), diagnostic_distance_including_target_m=total + snap_distance, diagnostic_time_including_target_min=(total + snap_distance) / speed / 60, graph_cost_time_s=offset / speed + (1 - fraction) * edge['travel_time_s'] + path['time_s'])
            metric_geometry, candidate['geometry_status'] = _route_geometry(tail, path, edges)
            candidate['road_coordinates_m'] = metric_geometry['coordinates'] if metric_geometry is not None else None
            candidate['road_geometry'] = None
            if metric_geometry is not None:
                try:
                    with osr.ExceptionMgr(useExceptions=True):
                        geo = [list(inverse.TransformPoint(*xy)[:2]) for xy in metric_geometry['coordinates']]
                    if not all((all((_number(x) for x in xy)) for xy in geo)):
                        raise ValueError('Nonfinite inverse transform')
                    candidate['road_geometry'] = {'type': 'LineString', 'coordinates': geo}
                except (RuntimeError, ValueError):
                    candidate['geometry_status'] = 'ROUTE_GEOMETRY_TRANSFORM_FAILED'
        reachable = [c for c in row['candidates'] if c['route_found']]
        if not reachable:
            reason = 'NO_DIRECTED_PATH' if row['candidates'] else 'NO_ELIGIBLE_ACCESS'
            if not row['candidates'] and any((d['reason'] in ('CONNECTOR_REJECTED', 'CONNECTOR_PERMISSION_UNKNOWN') for d in row['candidate_diagnostics'])):
                reason = 'CONNECTOR_VALIDATION_FAILED'
            row.update(reason=reason, route_found=False)
            continue
        best = min(reachable, key=lambda c: (round(c['building_connector_distance_m'], 2), c['threshold_time_min'], c['edge']['u'], c['edge']['v'], c['edge']['key'], c['edge']['edge_id']))
        row.update(route_found=True, selected_candidate=deepcopy(best), reference_accessible=best['reference_accessible'], route_geometry=best['road_geometry'], route_geometry_status=best['geometry_status'], reason='REFERENCE_WITHIN_TIME' if best['reference_accessible'] else 'REFERENCE_TIME_LIMIT')
    counts = Counter((row['reason'] for row in result['routes']))
    result['summary'] = {'input_selected_buildings': len(selected), 'accounted_routes': len(result['routes']), 'route_found': sum((r['route_found'] is True for r in result['routes'])), 'no_route': sum((r['route_found'] is False for r in result['routes'])), 'not_evaluated': sum((r['route_found'] is None for r in result['routes'])), 'reference_within_time': sum((r['reference_accessible'] is True for r in result['routes'])), 'reference_time_limit': sum((r['reference_accessible'] is False for r in result['routes'])), 'accepted_accessible': None, 'policy_unresolved': len(selected), 'reason_counts': dict(sorted(counts.items()))}
    assert result['summary']['accounted_routes'] == len(selected)
    result['routing_gate'] = 'PASS'
    result['status'] = 'PARTIAL'
    result['diagnostics'].append({'code': 'POLICY_UNRESOLVED', 'message': 'D02/D03/D05/D10 remain OPEN; reference counts are not approved accessibility.'})
    return result

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('context', 'manifest', 'buildings', 'graph', 'config', 'root'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args(argv)
    loaded = []
    file_hashes = {}
    try:
        for key in ('context', 'manifest', 'buildings', 'graph', 'config'):
            path = getattr(args, key)
            if not path.is_file():
                raise OSError('Regular local inputs required')
            raw = path.read_bytes()
            file_hashes[key] = hashlib.sha256(raw).hexdigest()
            loaded.append(json.loads(raw.decode('utf-8'), object_pairs_hook=_strict_pairs, parse_constant=_reject_constant))
        result = route_buildings(*loaded, root=args.root)
        result['input_file_sha256'] = file_hashes
    except OSError:
        result = {'schema_version': RESULT_SCHEMA, 'status': 'BLOCKED', 'summary': None, 'diagnostics': [{'code': 'INPUT_UNAVAILABLE', 'message': 'Supply readable regular local inputs; no network fallback.'}], 'live_readiness': 'NOT_VERIFIED'}
    except (ValueError, UnicodeError, RecursionError):
        result = {'schema_version': RESULT_SCHEMA, 'status': 'FAILED', 'summary': None, 'diagnostics': [{'code': 'INPUT_JSON_INVALID', 'message': 'Supply strict UTF-8 JSON inputs.'}], 'live_readiness': 'NOT_VERIFIED'}
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))
    return {'PARTIAL': 3, 'BLOCKED': 2, 'FAILED': 1}.get(result['status'], 0)
if __name__ == '__main__':
    raise SystemExit(main())
