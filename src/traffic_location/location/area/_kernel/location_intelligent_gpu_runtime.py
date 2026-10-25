"""GPU notebook facade. No policy changes and no automatic CPU-only fallback."""
from pathlib import Path
from threading import RLock
import json, os, subprocess
from traffic_location.location.area._kernel.location_intelligent_gpu import CupyReachability
PROFILE = 'GPU_WEIGHTED_GEOMETRY_V2'
_LOCK = RLock()

def run_core_with_python(root, stage):
    from traffic_location.location.area._kernel.location_intelligent_li3 import CORE
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json
    config = Path(root) / 'requested_config.json'
    python = read_json(config).get('core_python', '/usr/bin/python3') if config.exists() else '/usr/bin/python3'
    result = subprocess.run([python, '-B', str(CORE), stage, '--root', str(root)], capture_output=True, text=True, env={**os.environ, 'PROJ_NETWORK': 'OFF', 'PYTHONDONTWRITEBYTECODE': '1'})
    if result.returncode:
        raise RuntimeError('Core stage failed: ' + stage + ' ' + result.stderr[-1800:] + result.stdout[-1800:])
    for line in result.stderr.splitlines():
        if line.startswith('Normalization cache:'):
            print(line, flush=True)
    return json.loads(result.stdout)

def _report(path, report):
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import write_json, read_json
    path = Path(path)
    rows = read_json(path) if path.exists() else []
    rows.append(report)
    tmp = path.with_suffix('.partial')
    write_json(tmp, rows)
    tmp.replace(path)

def build_gpu(root, report_path, device=0):
    """GPU candidates/intersections + GPU weighted labels; CPU validates contracts."""
    import traffic_location.location.area._kernel.location_intelligent_li3 as canonical
    import traffic_location.location.area._kernel.location_intelligent_li3_connectors as connectors
    from traffic_location.location.area._kernel.location_intelligent_gpu_connectors import generate_connectors_gpu
    from traffic_location.location.area._kernel.location_intelligent_gpu_weighted import CupyWeightedRouter
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json, write_json
    from traffic_location.location.area._kernel.location_intelligent_validator import canonical_hash
    root = Path(root)
    original = canonical.run_core
    original_connectors = connectors.generate_connectors

    def connector_adapter(*args, **kwargs):
        return generate_connectors_gpu(*args, **kwargs, device=device, audit_path=report_path)

    def runner(pilot, stage):
        if stage != 'route':
            return run_core_with_python(pilot, stage)
        graph = read_json(pilot / 'graph/graph.json.gz')
        evidence = read_json(pilot / 'connectors/evidence.json.gz')
        allowed = {k: r['allowed'] for k, r in evidence['edge_rules'].items()}
        blocked = {(r['from_edge'], r['to_edge']) for r in evidence['blocked_turns']}
        router = CupyWeightedRouter(graph, allowed, blocked, device)
        router.compute([c['node_id'] for c in evidence['connectors'] if c['kind'] == 'TARGET'])
        cache = {'schema': 'gpu_weighted_cache_v2', 'graph_hash': canonical_hash(graph), 'evidence_hash': canonical_hash(evidence), 'labels': router.export_labels(), 'audit': router.audit}
        path = Path(report_path).parent / (pilot.name + '-gpu-weighted.json.gz')
        write_json(path, cache)
        core = read_json(pilot / 'requested_config.json').get('core_python', '/usr/bin/python3')
        completed = subprocess.run([core, '-B', str(Path(__file__).with_name('location_intelligent_gpu_worker.py')), '--root', str(pilot), '--scope', str(path), '--weighted', '--audit-path', str(report_path)], capture_output=True, text=True, env={**os.environ, 'PROJ_NETWORK': 'OFF', 'PYTHONDONTWRITEBYTECODE': '1'})
        if completed.returncode:
            raise RuntimeError('GPU_WEIGHTED_WORKER_FAILED: ' + completed.stderr[-1200:])
        return json.loads(completed.stdout)
    with _LOCK:
        canonical.run_core = runner
        connectors.generate_connectors = connector_adapter
        try:
            return canonical.build(root)
        finally:
            canonical.run_core = original
            connectors.generate_connectors = original_connectors

def build_market_gpu(config, market_config, pilot, layers, facilities, output, *, report_path, device=0):
    import traffic_location.location.area._kernel.location_intelligent_market_runtime as canonical
    import traffic_location.location.area._kernel.location_intelligent_li3_connectors as connectors
    from traffic_location.location.area._kernel.location_intelligent_gpu_connectors import generate_connectors_gpu
    with _LOCK:
        original = canonical._MarketRoutes
        original_connectors = connectors.generate_connectors
        instances = []
        adapter = weighted_market_routes_class(device, instances)
        canonical._MarketRoutes = adapter
        connectors.generate_connectors = lambda *a, **kw: generate_connectors_gpu(*a, **kw, device=device, audit_path=report_path)
        try:
            return canonical.build_market(config, market_config, pilot, layers, facilities, output)
        finally:
            canonical._MarketRoutes = original
            connectors.generate_connectors = original_connectors
            for instance in instances:
                _report(report_path, {'stage': 'market_weighted', 'routing': dict(instance.router.audit)})

def weighted_market_routes_class(device=0, instances=None, router_factory=None):
    from traffic_location.location.area._kernel.location_intelligent_market_runtime import _MarketRoutes as CanonicalRoutes
    from traffic_location.location.area._kernel.location_intelligent_gpu_weighted import CupyWeightedRouter
    from traffic_location.location.area._kernel.location_intelligent_gpu import StateTopology
    import hashlib
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import canonical_bytes

    class WeightedGpuRoutes(CanonicalRoutes):

        def __init__(self, package):
            super().__init__(package)
            self.package = package
            self.hosts = {}
            self.potential_cache = {}
            self.router = (router_factory or CupyWeightedRouter)(package['graph'], self.allowed, self.blocked, device)
            self.router.compute([c['node_id'] for c in package['connectors'] if c['kind'] == 'TARGET'])
            if instances is not None:
                instances.append(self)

        def reverse(self, target):
            if target not in self.hosts:
                self.hosts[target] = self.router.lookup(target)
            host = self.hosts[target]

            def lookup(start):
                path = host(start)
                return None if path is None else {'distance_m': path['distance_m'], 'path_sha256': hashlib.sha256(canonical_bytes(path['edges'])).hexdigest()}
            return lookup

        def forward(self, start):

            def lookup(target):
                if target not in self.hosts:
                    self.hosts[target] = self.router.lookup(target)
                path = self.hosts[target](start)
                return None if path is None else {'distance_m': path['distance_m']}
            return lookup

        def potential_forward(self, start):
            if start not in self.potential_cache:
                topology = StateTopology(self.package['graph'], self.allowed, self.blocked, potential=True)
                engine = CupyReachability(device)
                try:
                    visited = engine.reach(topology, [topology.source_seeds([start])])[0]
                finally:
                    engine.close()
                self.potential_cache[start] = {node for node in topology.nodes if any((visited[i] for i in topology.target_seeds(node)))}
            return lambda target: target in self.potential_cache[start]
    return WeightedGpuRoutes
