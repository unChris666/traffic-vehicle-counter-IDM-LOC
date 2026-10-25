"""GPU notebook facade. No policy changes and no automatic CPU-only fallback."""
from pathlib import Path
from threading import RLock
import json,os,subprocess
from location_intelligent_gpu import CupyReachability,prepare_scope,PROFILE
_LOCK=RLock()


def _report(path,report):
    from location_intelligent_li3_sources import write_json,read_json
    path=Path(path);rows=read_json(path) if path.exists() else []
    rows.append(report);tmp=path.with_suffix('.partial');write_json(tmp,rows);tmp.replace(path)


def build_gpu(root,report_path,device=0):
    """Reuse build unchanged; replace only its route worker for this invocation."""
    import location_intelligent_li3 as canonical
    from location_intelligent_li3_sources import read_json,write_json
    from location_intelligent_validator import canonical_hash
    root=Path(root);original=canonical.run_core
    def runner(pilot,stage):
        if stage!='route':return original(pilot,stage)
        graph=read_json(pilot/'graph/graph.json.gz');evidence=read_json(pilot/'connectors/evidence.json.gz')
        engine=CupyReachability(device)
        try:
            scope=prepare_scope({'graph':graph,**{k:evidence[k] for k in ['connectors','edge_rules','blocked_turns']}},engine)
        finally:engine.close()
        scope.update(graph_hash=canonical_hash(graph),evidence_hash=canonical_hash(evidence))
        path=Path(report_path).parent/(pilot.name+'-gpu-scope.json.gz');write_json(path,scope)
        _report(report_path,{'stage':'calculation','profile':PROFILE,'stats':scope['stats'],
                'original_edges':scope['original_edges'],'retained_edges':scope['retained_edges']})
        completed=subprocess.run(['/usr/bin/python3','-B',str(Path(__file__).with_name('location_intelligent_gpu_worker.py')),
            '--root',str(pilot),'--scope',str(path)],capture_output=True,text=True,
            env={**os.environ,'PROJ_NETWORK':'OFF','PYTHONDONTWRITEBYTECODE':'1'})
        if completed.returncode:raise RuntimeError('GPU_CANONICAL_WORKER_FAILED: '+completed.stderr[-1200:])
        return json.loads(completed.stdout)
    with _LOCK:
        canonical.run_core=runner
        try:return canonical.build(root)
        finally:canonical.run_core=original


def market_routes_class(report_path,device=0,engine_factory=None):
    from location_intelligent_market_runtime import _MarketRoutes as CanonicalRoutes
    class GpuCanonicalRoutes(CanonicalRoutes):
        def __init__(self,package):
            engine=engine_factory() if engine_factory else CupyReachability(device)
            try:scope=prepare_scope(package,engine)
            finally:engine.close()
            keep=set(scope['edge_ids']);self.origins=set(scope['origin_nodes']);self.scope=scope
            filtered={**package,'graph':{**package['graph'],'edges':[e for e in package['graph']['edges'] if e['edge_id'] in keep]}}
            # Keep all original rule entries for connector eligibility checks.
            super().__init__(filtered)
            self.edges={e['edge_id']:e for e in package['graph']['edges']}
            self.filtered_graph=filtered['graph']
            _report(report_path,{'stage':'market','profile':PROFILE,'stats':scope['stats'],
                     'original_edges':scope['original_edges'],'retained_edges':scope['retained_edges']})
        def reverse(self,target):
            if target not in self.scope['reachable_nodes']:raise ValueError('GPU_SCOPE_TARGET_MISSING')
            reached=set(self.scope['reachable_nodes'][target])
            canonical=super().reverse(target) if reached & self.origins else None
            def lookup(start):
                if start not in self.origins:raise ValueError('GPU_SCOPE_ORIGIN_MISSING')
                return canonical(start) if canonical and start in reached else None
            return lookup
        def forward(self,start):
            if start not in self.origins:raise ValueError('GPU_SCOPE_ORIGIN_MISSING')
            return super().forward(start)
        def potential_forward(self,start):
            if start not in self.origins:raise ValueError('GPU_SCOPE_ORIGIN_MISSING')
            # Canonical forward already uses all non-False edges in filtered graph.
            return super().potential_forward(start)
    return GpuCanonicalRoutes


def build_market_gpu(config,market_config,pilot,layers,facilities,output,*,report_path,device=0):
    import location_intelligent_market_runtime as canonical
    with _LOCK:
        original=canonical._MarketRoutes
        adapter=market_routes_class(report_path,device)
        canonical._MarketRoutes=adapter
        try:return canonical.build_market(config,market_config,pilot,layers,facilities,output)
        finally:canonical._MarketRoutes=original
