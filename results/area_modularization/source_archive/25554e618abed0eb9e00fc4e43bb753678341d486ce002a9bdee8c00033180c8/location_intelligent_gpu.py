"""Exact integer GPU reachability; canonical distances/ties stay in CPU engine.

No business configuration here. No CUDA import at module import. Production
requires CuPy/CUDA; CPU traversal below is an explicitly named test oracle.
"""
from collections import defaultdict
from pathlib import Path
import json

PROFILE='GPU_REACHABILITY_CANONICAL_CPU_V1'

class StateTopology:
    """Node-entry + edge-arrival states preserve directed turn restrictions."""
    def __init__(self,graph,allowed,blocked,potential=False):
        self.nodes=sorted(n['node_id'] for n in graph['nodes'])
        self.node_index={n:i for i,n in enumerate(self.nodes)}
        self.edges={e['edge_id']:e for e in graph['edges'] if (allowed.get(e['edge_id']) is not False if potential else allowed.get(e['edge_id']) is True)}
        self.node_only=not blocked
        if self.node_only:
            self.edge_index={k:self.node_index[e['u']] for k,e in self.edges.items()}
            self.incoming=defaultdict(list)
            self.arcs=[(self.node_index[e['u']],self.node_index[e['v']]) for e in self.edges.values()]
            self.size=len(self.nodes)
            return
        self.edge_index={k:len(self.nodes)+i for i,k in enumerate(sorted(self.edges))}
        self.incoming=defaultdict(list);outgoing=defaultdict(list)
        for key,e in self.edges.items():
            if e['u'] not in self.node_index or e['v'] not in self.node_index:raise ValueError('GPU_TOPOLOGY_UNKNOWN_NODE')
            self.incoming[e['v']].append(key);outgoing[e['u']].append(key)
        arcs=[]
        for node in self.nodes:
            for key in sorted(outgoing[node]):arcs.append((self.node_index[node],self.edge_index[key]))
        for key,e in sorted(self.edges.items()):
            for following in sorted(outgoing[e['v']]):
                if (key,following) not in blocked:arcs.append((self.edge_index[key],self.edge_index[following]))
        self.arcs=arcs;self.size=len(self.nodes)+len(self.edges)
    def target_seeds(self,node):
        return [self.node_index[node]] if self.node_only else [self.node_index[node]]+[self.edge_index[k] for k in self.incoming[node]]
    def source_seeds(self,nodes):return [self.node_index[n] for n in sorted(set(nodes))]


def cpu_reachability_oracle(topology,seeds,reverse=False):
    """Tests only. Never a production fallback for absent CUDA."""
    adjacency=defaultdict(list)
    for a,b in topology.arcs:adjacency[b if reverse else a].append(a if reverse else b)
    reached=set(seeds);queue=list(seeds)
    while queue:
        for dest in adjacency[queue.pop()]:
            if dest not in reached:reached.add(dest);queue.append(dest)
    return [i in reached for i in range(topology.size)]


class CupyReachability:
    KERNEL=r'''extern "C" __global__ void propagate(
      const long long* src, const long long* dst, long long arcs, int batch,
      const unsigned int* current, unsigned int* next, unsigned int* changed) {
        long long i=(long long)blockDim.x*blockIdx.x+threadIdx.x;
        if(i>=arcs*batch)return;
        long long a=i/batch;int c=i%batch;
        if(current[src[a]*batch+c]) {
          unsigned int old=atomicOr(&next[dst[a]*batch+c],1u);
          if(old==0u)atomicExch(changed,1u);
        }
      }'''
    def __init__(self,device=0,batch_size=16):
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount()<=device:raise RuntimeError('GPU_REQUIRED_NO_VISIBLE_DEVICE')
        self.cp=cp;self.device=device;self.batch_size=batch_size
        self.stats={'execution_profile':PROFILE,'actual_cuda_executed':False,'calls':0,'iterations':0,'columns':0}
        with cp.cuda.Device(device):self.kernel=cp.RawKernel(self.KERNEL,'propagate',options=('--std=c++11',))
    def reach(self,topology,seed_columns,reverse=False,sample_states=None):
        import numpy as np
        cp=self.cp;answers=[]
        with cp.cuda.Device(self.device):
            free,_=cp.cuda.runtime.memGetInfo()
            batch=min(self.batch_size,max(1,int(free*.2)//max(1,topology.size*8)))
            pairs=topology.arcs
            a=cp.asarray([p[1] if reverse else p[0] for p in pairs],dtype=cp.int64)
            b=cp.asarray([p[0] if reverse else p[1] for p in pairs],dtype=cp.int64)
            for start in range(0,len(seed_columns),batch):
                seeds=seed_columns[start:start+batch];width=len(seeds)
                print('GPU integer reachability: columns '+str(start+1)+'-'+str(start+width)+'/'+str(len(seed_columns))+'; states='+str(topology.size)+'; arcs='+str(len(pairs)),flush=True)
                current=cp.zeros((topology.size,width),dtype=cp.uint32)
                for col,states in enumerate(seeds):
                    if states:current[cp.asarray(states,dtype=cp.int64),col]=1
                iterations=0
                while pairs:
                    following=current.copy();changed=cp.zeros(1,dtype=cp.uint32)
                    work=len(pairs)*width
                    self.kernel(((work+255)//256,),(256,),
                        (a,b,np.int64(len(pairs)),np.int32(width),current,following,changed))
                    iterations+=1;current=following
                    if iterations%100==0:print('GPU reachability iterations: '+str(iterations),flush=True)
                    if int(changed.get()[0])==0:break
                    if iterations>topology.size:raise RuntimeError('GPU_REACHABILITY_DID_NOT_CONVERGE')
                host=(current[cp.asarray(sample_states,dtype=cp.int64)] if sample_states is not None else current).get()
                answers.extend([host[:,col].astype(bool) for col in range(width)])
                self.stats['calls']+=1;self.stats['columns']+=width;self.stats['iterations']+=iterations
                self.stats['actual_cuda_executed']=True
            cp.cuda.runtime.deviceSynchronize()
        return answers
    def close(self):
        with self.cp.cuda.Device(self.device):
            self.cp.cuda.runtime.deviceSynchronize()
            self.cp.get_default_memory_pool().free_all_blocks()
            self.cp.get_default_pinned_memory_pool().free_all_blocks()


def prepare_scope(package,engine):
    """All routes from a connector origin remain in the exact retained subgraph."""
    graph=package['graph'];allowed={k:r['allowed'] for k,r in package['edge_rules'].items()}
    blocked={(t['from_edge'],t['to_edge']) for t in package['blocked_turns']}
    origins=sorted({c['node_id'] for c in package['connectors'] if c['kind']=='BUILDING' or
                    (c['kind']=='TARGET' and not c.get('alternative_store_key'))})
    possible=StateTopology(graph,allowed,blocked,potential=True)
    visited=engine.reach(possible,[possible.source_seeds(origins)])[0]
    keep={key for key,index in possible.edge_index.items() if visited[index]}
    restricted={**graph,'edges':[e for e in graph['edges'] if e['edge_id'] in keep]}
    strict=StateTopology(restricted,allowed,blocked)
    targets=sorted({c['node_id'] for c in package['connectors'] if c['kind']=='TARGET'})
    masks=engine.reach(strict,[strict.target_seeds(t) for t in targets],reverse=True,sample_states=list(range(len(strict.nodes))))
    print('GPU routing scope: '+str(len(graph['edges']))+' -> '+str(len(keep))+' relevant edges; targets='+str(len(targets)),flush=True)
    reachable={t:[node for node in strict.nodes if mask[strict.node_index[node]]] for t,mask in zip(targets,masks)}
    return {'schema':'gpu_routing_scope_v1','profile':PROFILE,'origin_nodes':origins,
            'edge_ids':sorted(keep),'reachable_nodes':reachable,'stats':dict(engine.stats),
            'original_edges':len(graph['edges']),'retained_edges':len(keep)}


def verify_scope_binding(scope,graph,evidence):
    from location_intelligent_validator import canonical_hash
    if scope.get('schema')!='gpu_routing_scope_v1' or scope.get('profile')!=PROFILE:raise ValueError('GPU_SCOPE_PROFILE_MISMATCH')
    if scope.get('graph_hash')!=canonical_hash(graph) or scope.get('evidence_hash')!=canonical_hash(evidence):
        raise ValueError('GPU_SCOPE_INPUT_MISMATCH')
    if not set(scope['edge_ids'])<={e['edge_id'] for e in graph['edges']}:raise ValueError('GPU_SCOPE_INVALID_EDGES')
    nodes={n['node_id'] for n in graph['nodes']}
    if not set(scope['origin_nodes'])<=nodes or any(not set(row)<=nodes for row in scope['reachable_nodes'].values()):raise ValueError('GPU_SCOPE_INVALID_NODES')


def gpu_preflight(device=0):
    import platform
    engine=CupyReachability(device);cp=engine.cp
    try:
        # Includes prohibited transition, directionality, isolated node and target=self.
        graph={'nodes':[{'node_id':n} for n in 'abcx'],'edges':[
            {'edge_id':'ab','u':'a','v':'b'},{'edge_id':'bc','u':'b','v':'c'},
            {'edge_id':'ca','u':'c','v':'a'}]}
        for blocked in [set(),{('ab','bc')}]:
            topology=StateTopology(graph,{k:True for k in ['ab','bc','ca']},blocked)
            seeds=[topology.source_seeds(['a']),topology.target_seeds('c')]
            for reverse in [False,True]:
                actual=engine.reach(topology,seeds,reverse)
                expected=[cpu_reachability_oracle(topology,s,reverse) for s in seeds]
                if [list(row) for row in actual]!=expected:raise RuntimeError('GPU_PREFLIGHT_EQUIVALENCE_FAILED')
        with cp.cuda.Device(device):props=cp.cuda.runtime.getDeviceProperties(device)
        return {'status':'SUCCEEDED','profile':PROFILE,'python':platform.python_version(),'cupy':cp.__version__,
            'cuda_runtime':cp.cuda.runtime.runtimeGetVersion(),'cuda_driver':cp.cuda.runtime.driverGetVersion(),
            'device_index':device,'device_name':props['name'].decode() if isinstance(props['name'],bytes) else props['name'],
            'visible_devices':cp.cuda.runtime.getDeviceCount(),'actual_cuda_executed':True,'self_test':'INTEGER_REACHABILITY_EQUIVALENT'}
    finally:engine.close()


def release_gpu(device=0):
    import cupy as cp
    with cp.cuda.Device(device):
        cp.cuda.runtime.deviceSynchronize();cp.get_default_memory_pool().free_all_blocks();cp.get_default_pinned_memory_pool().free_all_blocks()
    return {'status':'AREA_GPU_POOLS_RELEASED','device':device,'traffic_started':False}
