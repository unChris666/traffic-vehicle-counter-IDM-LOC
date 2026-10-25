"""Policy-aware offline motorcycle routing on explicit, hash-bound evidence.

No entrance/bridge/connector is invented. Connectors and resolved restrictions
must be supplied by a source adapter or review. N1 engine remains unchanged.
"""
from copy import deepcopy
import argparse
import heapq
import json
import math
from pathlib import Path

from location_intelligent_config import get_config
from location_intelligent_routing import _graph, _selection, _number, inside_bbox
from location_intelligent_validator import _Validator, canonical_hash, validate


def motor_access(tags, highway):
    """Conservative normalized tag resolver, not a conditional-expression parser."""
    if not isinstance(tags, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in tags.items()):
        return None, "MALFORMED_TAGS"
    if any(":conditional" in k for k in tags):
        return None, "CONDITIONAL_REQUIRES_RESOLVED_EVIDENCE"
    if highway in {"steps", "footway", "pedestrian", "cycleway"}:
        return False, "NON_MOTOR_PROFILE"
    values = [tags.get(k, "").lower() for k in ("access", "vehicle", "motor_vehicle", "motorcycle")]
    if "private" in values or tags.get("gate:status") == "closed":
        return False, "EXPLICIT_PROHIBITION"
    for value in reversed(values):
        if value == 'no':
            return False, 'EXPLICIT_PROHIBITION'
        if value in {'yes', 'designated', 'permissive'}:
            return True, 'POSITIVE_TAG_PERMISSION'
        if value:
            return None, 'ACCESS_VALUE_REQUIRES_REVIEW'
    if highway in {"service", "living_street", "residential", "unclassified"}:
        return True, "OWNER_ALLEY_ACCESS_ASSUMPTION"
    return None, "ACCESS_UNVERIFIED"


def _path(graph, allowed, blocked, start, target):
    """Edge-state Dijkstra enforces prohibited turns without reversing roads."""
    adjacency = {n["node_id"]: [] for n in graph["nodes"]}
    for edge in graph["edges"]:
        if allowed.get(edge["edge_id"]) is True:
            adjacency[edge["u"]].append(edge)
    queue, best = [(0.0, 0, (), start, "")], {(start, ""): (0.0, 0, ())}
    while queue:
        cost, hops, ids, node, previous = heapq.heappop(queue)
        if best.get((node, previous)) != (cost, hops, ids):
            continue
        if node == target:
            return {"distance_m": cost, "edges": list(ids)}
        for edge in sorted(adjacency[node], key=lambda e: e["edge_id"]):
            key = edge["edge_id"]
            if (previous, key) in blocked:
                continue
            label = (cost + edge["length_m"], hops + 1, (*ids, key))
            state = (edge["v"], key)
            if state not in best or label < best[state]:
                best[state] = label
                heapq.heappush(queue, (*label, *state))
    return None


def _path_index(graph, allowed, blocked, target):
    """Reverse edge-state index; same cost/hops/edge-ID tie-break as _path.

    Built once per target per invocation. It never crosses analysis/config
    boundaries and does not drop turn restrictions to optimize real graphs.
    """
    incoming, outgoing, edges = {}, {}, {}
    for edge in graph['edges']:
        key = edge['edge_id']
        if allowed.get(key) is True:
            edges[key] = edge
            incoming.setdefault(edge['v'], []).append(key)
            outgoing.setdefault(edge['u'], []).append(key)
    best, queue = {}, []
    for key in incoming.get(target, []):
        label = (edges[key]['length_m'], 1, (key,))
        best[key] = label
        heapq.heappush(queue, (*label, key))
    while queue:
        cost, hops, path, key = heapq.heappop(queue)
        if best.get(key) != (cost, hops, path):
            continue
        for previous in incoming.get(edges[key]['u'], []):
            if (previous, key) in blocked:
                continue
            label = (edges[previous]['length_m'] + cost, hops+1, (previous, *path))
            if previous not in best or label < best[previous]:
                best[previous] = label
                heapq.heappush(queue, (*label, previous))
    def lookup(start):
        if start == target:
            return {'distance_m': 0.0, 'edges': []}
        options = [best[k] for k in outgoing.get(start, []) if k in best]
        if not options:
            return None
        label = min(options)
        # Report forward-ordered summation, matching legacy _path arithmetic.
        return {'distance_m': sum(edges[k]['length_m'] for k in label[2]), 'edges': list(label[2])}
    return lookup


def _potential_reachability(graph, allowed, blocked, target):
    """Unknown edges may explain a no-route result; never used for acceptance."""
    edges, incoming, outgoing = {}, {}, {}
    for edge in graph['edges']:
        if allowed.get(edge['edge_id']) is not False:
            key = edge['edge_id']; edges[key] = edge
            incoming.setdefault(edge['v'], []).append(key)
            outgoing.setdefault(edge['u'], []).append(key)
    reached = set(incoming.get(target, [])); queue = list(reached)
    while queue:
        key = queue.pop()
        for previous in incoming.get(edges[key]['u'], []):
            if previous not in reached and (previous, key) not in blocked:
                reached.add(previous); queue.append(previous)
    return lambda start: start == target or any(k in reached for k in outgoing.get(start, []))


def route_motor_buildings(context, manifest, buildings, graph, evidence, *, root, policy=None):
    """Integrate editable policy with verified local sources; no live fallback.

    Evidence schema li_motor_evidence_v1 binds hashes to context/selection/graph.
    edge_rules resolves all edge permissions with evidence_refs. blocked_turns
    lists explicit (from_edge,to_edge). connectors are metric LineStrings with
    kind BUILDING/TARGET, building_id, node_id, road_edge_id, status
    VERIFIED/OWNER_ASSUMPTION/BLOCKED/UNKNOWN, barrier_clear and evidence_refs.
    Incomplete restriction coverage keeps routing blocked rather than bypassed.
    """
    policy = get_config() if policy is None else deepcopy(policy)
    result = {"schema_version": "li_motor_routing_v1", "status": "BLOCKED", "routes": [],
              "summary": None, "diagnostics": [], "live_readiness": "NOT_VERIFIED",
              "physical_access_validated": False}
    def stop(code, status="BLOCKED"):
        result["status"] = status
        result["diagnostics"].append({"code": code})
        return result
    gate = validate(context, manifest, root=root)
    if gate["offline_readiness"] != "READY":
        return stop("LI0_INPUT_BLOCKED")
    if not isinstance(evidence, dict) or not isinstance(graph, dict):
        return stop("MOTOR_EVIDENCE_REQUIRED")
    v = _Validator(root)
    for name, value in [("graph", graph), ("buildings", buildings), ("policy", policy), ("evidence", evidence)]:
        v.json_values(value, name)
    if v.diagnostics:
        return stop("NONFINITE_OR_MALFORMED_INPUT", "FAILED")
    try:
        travel, conn = policy["travel"], policy["connectors"]
        road_profile=policy.get('li3',{}).get('road_rule_profile','STRICT_MOTOR_LEGACY')
        if road_profile not in {'STRICT_MOTOR_LEGACY','BARRIER_ONEWAY_EXPERIMENT_V1'}:return stop('UNSUPPORTED_ROAD_RULE_PROFILE','FAILED')
        simplified=road_profile=='BARRIER_ONEWAY_EXPERIMENT_V1'
        profile=conn.get('building_entrance_profile','MULTI_ACCESS_LEGACY')
        if profile not in {'MULTI_ACCESS_LEGACY','SINGLE_HIGHEST_CLASS_NEAREST_V1'}:
            return stop('UNSUPPORTED_ENTRANCE_PROFILE','FAILED')
        single=profile=='SINGLE_HIGHEST_CLASS_NEAREST_V1'
        expected_selection='HIGHEST_VALID_CLASS_THEN_NEAREST_REPRESENTATIVE_POINT_THEN_SEGMENT_ID' if single else 'HIGHEST_VALID_ACCESS_CLASS_THEN_MINIMUM_TOTAL_TIME'
        expected_fallback='NO_ROUTE_NO_ENTRANCE_FALLBACK' if single else 'TRY_NEXT_REACHABLE_CLASS'

        speed = travel["reference_constant_speed"]["value"] * 1000 / 3600
        limit = conn["max_building_to_road_m"]["value"]
        threshold = travel["max_travel_min"]["value"]
        if (not _number(travel["reference_constant_speed"]["value"]) or
            not all(_number(x) and x > 0 for x in (speed, limit, threshold)) or
            any(policy["motorcycle_access"].get(k) is not expected for k,expected in [("private_access_usable",simplified),("pedestrian_only_usable",simplified),("stairs_usable",simplified),("invent_u_turns_or_reverse_edges",False)]) or
            travel["reference_constant_speed"]["unit"] != "km/h" or
            conn["max_building_to_road_m"]["unit"] != "m" or travel["max_travel_min"]["unit"] != "min" or
            travel["mode"] != "motorcycle" or travel["threshold_comparison"] != "<=" or
            travel["threshold_rounding"] != "PYTHON_ROUND_HALF_EVEN_TOTAL_MINUTES_BEFORE_COMPARISON" or
            travel["segment_speed_model"] != "ALL_SEGMENTS_USE_REFERENCE_CONSTANT_SPEED" or
            conn["candidate_selection"] != expected_selection or
            conn["max_target_snap_m"] != {"value": None, "unit": "m", "limit_type": "UNBOUNDED"} or
            conn["unreachable_higher_class"] != expected_fallback):
            return stop("UNSUPPORTED_MOTOR_POLICY", "FAILED")
        rank = {name: i for i, group in enumerate(conn["road_class_hierarchy"]) for name in group}
        if not rank or len(rank) != sum(map(len, conn["road_class_hierarchy"])):
            return stop("INVALID_ROAD_HIERARCHY", "FAILED")
    except (KeyError, TypeError, ValueError):
        return stop("INVALID_MOTOR_POLICY", "FAILED")
    crs = context["config"]["area_coverage"]["metric_crs"]
    nodes = _graph(v, graph, crs)
    selected = _selection(v, buildings, context, manifest, crs)
    if v.diagnostics:
        result["diagnostics"] = v.diagnostics
        return stop("INPUT_CONTRACT_INVALID", "FAILED")
    hashes = {"graph_hash": canonical_hash(graph), "selection_hash": canonical_hash(buildings), "context_hash": context["context_hash"], "policy_hash": canonical_hash(policy)}
    result["provenance"] = {**hashes, "effective_policy": policy, "graph_id": graph["graph_id"]}
    if evidence.get("schema_version") != "li_motor_evidence_v1" or any(evidence.get(k) != val for k, val in hashes.items()):
        return stop("EVIDENCE_BINDING_MISMATCH", "FAILED")
    edges = {e["edge_id"]: e for e in graph["edges"]}
    rules = evidence.get("edge_rules")
    if not isinstance(rules, dict) or set(rules) != set(edges):
        return stop("EDGE_PERMISSION_COVERAGE_INCOMPLETE")
    allowed = {}
    for key, rule in rules.items():
        if (not isinstance(rule, dict) or type(rule.get("allowed")) not in (bool, type(None)) or
            not isinstance(rule.get("evidence_refs"), list) or not rule["evidence_refs"] or
            not all(isinstance(x, str) and x for x in rule["evidence_refs"])):
            return stop("INVALID_EDGE_EVIDENCE", "FAILED")
        tags = rule.get("raw_tags", {})
        derived, reason = motor_access(tags, edges[key]["highway"])
        # Positive review cannot override explicit motor/private restrictions.
        if not simplified and derived is False and rule["allowed"] is True:
            return stop("PERMISSION_OVERRIDES_PROHIBITION", "FAILED")
        if not isinstance(tags, dict) or any(not isinstance(k, str) or not isinstance(val, str) for k, val in tags.items()):
            return stop("MALFORMED_RAW_TAGS", "FAILED")
        if not simplified and any(":conditional" in k for k in tags) and rule.get("conditional_resolved") is not True and rule['allowed'] is True:
            return stop("CONDITIONAL_RESTRICTION_UNRESOLVED")
        allowed[key] = rule["allowed"]
    road_only=(policy.get('li3',{}).get('feature_source_mode')=='ROADS_ONLY_EXPERIMENT' and
               evidence.get('feature_scope')=='ROADS_ONLY_EXPERIMENT')
    if evidence.get("restrictions_complete") is not True and not road_only:
        return stop("TURN_OR_BARRIER_COVERAGE_UNRESOLVED")
    turns = evidence.get("blocked_turns")
    if not isinstance(turns, list):
        return stop("INVALID_TURNS", "FAILED")
    blocked = set()
    for turn in turns:
        if (not isinstance(turn, dict) or turn.get("from_edge") not in edges or turn.get("to_edge") not in edges or
            not turn.get("evidence_ref") or edges[turn["from_edge"]]["v"] != edges[turn["to_edge"]]["u"]):
            return stop("INVALID_TURN_REFERENCE", "FAILED")
        blocked.add((turn["from_edge"], turn["to_edge"]))
    try:
        from location_intelligent_buildings import _backend, _spatial
        _, ogr, osr = _backend()
        transform, target = _spatial(crs, context["target"], ogr, osr)
        target_xy = [target.GetX(), target.GetY()]
    except (ImportError, RuntimeError, ValueError):
        return stop("CRS_BACKEND_UNAVAILABLE")
    if not inside_bbox(target_xy, graph["coverage"]["bbox"]):
        return stop("TARGET_OUTSIDE_COVERAGE")
    by_id = {b["building_id"]: b for b in selected}
    sources, targets, ids, building_geometry_cache = [], [], set(), {}
    if not isinstance(evidence.get("connectors"), list):
        return stop("INVALID_CONNECTOR_COLLECTION", "FAILED")
    for c in evidence["connectors"]:
        if not isinstance(c, dict):
            return stop("INVALID_CONNECTOR", "FAILED")
        key, node, edge = c.get("connector_id"), c.get("node_id"), edges.get(c.get("road_edge_id"))
        geom = c.get("geometry") if isinstance(c.get("geometry"), dict) else {}
        coords = geom.get("coordinates")
        if (not isinstance(key, str) or not key or key in ids or node not in nodes or edge is None or
            node not in {edge["u"], edge["v"]} or c.get("kind") not in {"BUILDING", "TARGET"} or
            c.get("status") not in {"VERIFIED", "OWNER_ASSUMPTION", "BLOCKED", "UNKNOWN"} or
            type(c.get("barrier_clear")) not in (bool, type(None)) or
            geom.get("type") != "LineString" or not isinstance(coords, list) or len(coords) < 2 or
            not all(isinstance(p, list) and len(p) == 2 and all(_number(x) for x in p) for p in coords) or
            not isinstance(c.get("evidence_refs"), list) or not c["evidence_refs"]):
            return stop("INVALID_CONNECTOR", "FAILED")
        ids.add(key)
        if not all(inside_bbox(p, graph["coverage"]["bbox"]) for p in coords):
            return stop("CONNECTOR_OUTSIDE_COVERAGE")
        node_xy = [nodes[node]["x"], nodes[node]["y"]]
        length = sum(math.dist(a, b) for a, b in zip(coords, coords[1:]))
        if not math.isfinite(length):
            return stop("CONNECTOR_DISTANCE_INVALID", "FAILED")
        r = deepcopy(c)
        r["distance_m"] = length
        r['structural_usable'] = c['status'] in {'VERIFIED', 'OWNER_ASSUMPTION'} and c['barrier_clear'] is True
        r['permission'] = allowed[edge['edge_id']]
        r["usable"] = c["status"] in {"VERIFIED", "OWNER_ASSUMPTION"} and c["barrier_clear"] is True and allowed[edge["edge_id"]] is True
        if c["kind"] == "BUILDING":
            if c.get("building_id") not in by_id or coords[-1] != node_xy:
                return stop("CONNECTOR_SOURCE_MISMATCH", "FAILED")
            b = by_id[c["building_id"]]
            if b['building_id'] not in building_geometry_cache:
                g = ogr.CreateGeometryFromJson(json.dumps(b["geometry"]))
                g.Transform(transform)
                rep = transform.TransformPoint(*b["representative_point"]["coordinates"])[:2]
                building_geometry_cache[b['building_id']] = (g, rep)
            g, rep = building_geometry_cache[b['building_id']]
            p = ogr.Geometry(ogr.wkbPoint); p.AddPoint_2D(*coords[0])
            if not g.Intersects(p):
                return stop("ENTRANCE_OUTSIDE_BUILDING", "FAILED")
            offset = math.dist(rep, node_xy)
            # Candidate search measures point-to-road, not connector detour length.
            if edge["geometry"] is None:
                r["usable"] = False
            else:
                from location_intelligent_routing import _project_to_line
                offset = _project_to_line(rep, edge["geometry"]["coordinates"])[0]
            r["candidate_distance_m"] = offset
            h = edge["highway"] or ""
            h = h[:-5] if h.endswith('_link') else h
            r["class_rank"] = rank.get(h)
            r["usable"] &= offset <= limit and r["class_rank"] is not None
            r['structural_usable'] &= edge['geometry'] is not None and offset <= limit and r['class_rank'] is not None
            sources.append(r)
        else:
            if coords[0] != node_xy or coords[-1] != target_xy:
                return stop("TARGET_CONNECTOR_MISMATCH", "FAILED")
            targets.append(r)
    if single:
        counts={}
        for source in sources:counts[source['building_id']]=counts.get(source['building_id'],0)+1
        if any(count>1 for count in counts.values()):return stop('MULTIPLE_ENTRANCES_IN_SINGLE_PROFILE','FAILED')
    indexes = {c['node_id']: _path_index(graph, allowed, blocked, c['node_id']) for c in targets if c['usable']}
    potential = {c['node_id']: _potential_reachability(graph, allowed, blocked, c['node_id']) for c in targets
                 if c['structural_usable'] and c['permission'] is not False} if any(v is None for v in allowed.values()) else {}
    sources_by_building = {}
    for source in sources:
        sources_by_building.setdefault(source['building_id'], []).append(source)
    for b in selected:
        row = {"building_id": b["building_id"], "route_found": False, "scenario_accessible": False,
               "physical_access_validated": False, "candidates": [], "selected_candidate": None}
        result["routes"].append(row)
        for source in sources_by_building.get(b['building_id'], []):
            if not source["usable"]:
                continue
            for target_conn in targets:
                if not target_conn["usable"]:
                    continue
                path = indexes[target_conn['node_id']](source['node_id'])
                if path is None:
                    continue
                total = source["distance_m"] + path["distance_m"] + target_conn["distance_m"]
                if not math.isfinite(total):
                    return stop("TOTAL_DISTANCE_OVERFLOW", "FAILED")
                minutes = total / speed / 60
                row["candidates"].append({"building_connector_id": source["connector_id"], "target_connector_id": target_conn["connector_id"],
                    "class_rank": source["class_rank"], "network_edges": path["edges"],
                    "building_connector_m": source["distance_m"], "network_distance_m": path["distance_m"],
                    "target_connector_m": target_conn["distance_m"], "total_distance_m": total,
                    "total_time_min": minutes, "threshold_time_min": round(minutes), "within_time": round(minutes) <= threshold})
        if row["candidates"]:
            best = min(row["candidates"], key=lambda c: (c["class_rank"], c["total_time_min"], c["building_connector_id"], c["target_connector_id"], tuple(c["network_edges"])))
            row.update(route_found=True, selected_candidate=best, scenario_accessible=best["within_time"],
                       reason="SCENARIO_WITHIN_TIME" if best["within_time"] else "SCENARIO_TIME_LIMIT")
        else:
            source_rows = [s for s in sources if s["building_id"] == b["building_id"]]
            unresolved = (not source_rows or not targets or
                          any(c["status"] == "UNKNOWN" or c["barrier_clear"] is None for c in [*source_rows, *targets]))
            if not unresolved and potential:
                unresolved = any(source['structural_usable'] and source['permission'] is not False and lookup(source['node_id'])
                                 for source in source_rows for lookup in potential.values())
            row["reason"] = "EVIDENCE_INCOMPLETE" if unresolved else "NO_VALID_REACHABLE_CONNECTORS"
            if unresolved:
                row.update(route_found=None, scenario_accessible=None)
    unknown = any(v is None for v in allowed.values())
    result["status"] = "PARTIAL" if road_only or unknown or any(r["route_found"] is None for r in result["routes"]) or graph["coverage"]["completeness"] != "COMPLETE" or buildings["status"] == "PARTIAL" else "SUCCEEDED"
    if simplified:
        result['road_rule_profile']=road_profile
        result['access_tag_validation']='NOT_APPLIED_BY_OWNER_POLICY'
        result['turn_restriction_validation']='NOT_APPLIED_BY_OWNER_POLICY'
    result['external_feature_validation']='NOT_REQUESTED_ROAD_GRAPH_EXPERIMENT' if road_only else 'CONFIGURED_FEATURE_EVIDENCE'
    result["summary"] = {"input_selected": len(selected), "accounted": len(result["routes"]),
                         "scenario_accepted": sum(r["scenario_accessible"] is True for r in result["routes"]),
                         "no_route": sum(r["route_found"] is False for r in result["routes"]),
                         "not_evaluated": sum(r["route_found"] is None for r in result["routes"]),
                         "unknown_edge_permissions": sum(v is None for v in allowed.values())}
    result["limitations"] = ["Offline scenario on explicit evidence; not proof of real/legal access", "No automatic entrance/barrier/conditional parser or source retrieval", "Node-bound connectors only; adapters must split edges for interior access points"]
    return result


def main(argv=None):
    from location_intelligent_validator import _strict_pairs, _reject_constant
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('context', 'manifest', 'buildings', 'graph', 'evidence', 'root'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--policy', type=Path)
    args = parser.parse_args(argv)
    def read(p):
        if not p.is_file():
            raise ValueError('Use regular local input files')
        return json.loads(p.read_text(), object_pairs_hook=_strict_pairs, parse_constant=_reject_constant)
    try:
        r = route_motor_buildings(*(read(getattr(args, k)) for k in ('context', 'manifest', 'buildings', 'graph', 'evidence')),
                                  root=args.root, policy=read(args.policy) if args.policy else None)
    except (ValueError, OSError, UnicodeError) as e:
        r = {'schema_version': 'li_motor_routing_v1', 'status': 'FAILED', 'summary': None,
             'diagnostics': [{'code': 'INPUT_READ_FAILED', 'message': str(e)}]}
    print(json.dumps(r, sort_keys=True, indent=2, allow_nan=False))
    return {'SUCCEEDED': 0, 'PARTIAL': 3, 'BLOCKED': 2, 'FAILED': 1}[r['status']]


if __name__ == '__main__':
    raise SystemExit(main())
