"""GDAL worker: original CPU arithmetic, GPU-certified topology scope only."""
from contextlib import contextmanager
from pathlib import Path
from traffic_location.location.area._kernel.location_intelligent_gpu import verify_scope_binding

@contextmanager
def scoped_routing(scope):
    import traffic_location.location.area._kernel.location_intelligent_motor_routing as motor
    original_path = motor._path_index
    original_potential = motor._potential_reachability
    keep = set(scope['edge_ids'])
    origins = set(scope['origin_nodes'])

    def restricted(graph):
        return {**graph, 'edges': [e for e in graph['edges'] if e['edge_id'] in keep]}

    def path_index(graph, allowed, blocked, target):
        if target not in scope['reachable_nodes']:
            raise ValueError('GPU_SCOPE_TARGET_MISSING')
        reached = set(scope['reachable_nodes'][target])
        lookup = original_path(restricted(graph), allowed, blocked, target) if reached & origins else None

        def path(start):
            if start not in origins:
                raise ValueError('GPU_SCOPE_ORIGIN_MISSING')
            return lookup(start) if start in reached and lookup else None
        return path

    def potential(graph, allowed, blocked, target):
        return original_potential(restricted(graph), allowed, blocked, target)
    motor._path_index = path_index
    motor._potential_reachability = potential
    try:
        yield
    finally:
        motor._path_index = original_path
        motor._potential_reachability = original_potential

def route(root, scope_path):
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json
    from traffic_location.location.area._kernel.location_intelligent_li3_core import route as canonical_route
    graph = read_json(root / 'graph/graph.json.gz')
    evidence = read_json(root / 'connectors/evidence.json.gz')
    scope = read_json(scope_path)
    verify_scope_binding(scope, graph, evidence)
    with scoped_routing(scope):
        return canonical_route(root)

def route_weighted(root, scope_path, audit_path):
    import traffic_location.location.area._kernel.location_intelligent_motor_routing as motor
    from traffic_location.location.area._kernel.location_intelligent_gpu_weighted import WeightedLookup
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json
    from traffic_location.location.area._kernel.location_intelligent_li3_core import route as canonical_route
    from traffic_location.location.area._kernel.location_intelligent_validator import canonical_hash
    from traffic_location.location.area._kernel.location_intelligent_gpu_runtime import _report
    graph = read_json(root / 'graph/graph.json.gz')
    evidence = read_json(root / 'connectors/evidence.json.gz')
    cache = read_json(scope_path)
    if cache.get('schema') != 'gpu_weighted_cache_v2' or cache['graph_hash'] != canonical_hash(graph) or cache['evidence_hash'] != canonical_hash(evidence):
        raise ValueError('GPU_WEIGHTED_CACHE_BINDING_MISMATCH')
    original = motor._path_index
    hosts = {}
    audit = cache['audit']

    def index(g, allowed, blocked, target):
        if target not in hosts:
            hosts[target] = WeightedLookup(g, allowed, blocked, target, cache['labels'][target], audit)
        return hosts[target]
    motor._path_index = index
    try:
        return canonical_route(root)
    finally:
        motor._path_index = original
        _report(audit_path, {'stage': 'calculation_weighted', 'routing': audit})
if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--scope', required=True, type=Path)
    parser.add_argument('--weighted', action='store_true')
    parser.add_argument('--audit-path', type=Path)
    args = parser.parse_args()
    result = route_weighted(args.root, args.scope, args.audit_path) if args.weighted else route(args.root, args.scope)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
