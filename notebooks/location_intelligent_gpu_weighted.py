"""FP64 CUDA weighted routing; exact CPU path extraction and audited ambiguity fallback."""
import math
from location_intelligent_motor_routing import _path_index as _CPU_PATH_INDEX
from collections import defaultdict

class WeightedLookup:
    """Host view of GPU labels; CPU search only for numerically ambiguous queries."""
    def __init__(self,graph,allowed,blocked,target,labels,audit):
        self.graph=graph;self.allowed=allowed;self.blocked=blocked;self.target=target;self.labels=labels;self.audit=audit
        self.edges={e['edge_id']:e for e in graph['edges']};self.keys=labels['keys'];self.index={k:i for i,k in enumerate(self.keys)}
        self.outgoing=defaultdict(list);self.memo={};self.reference=None
        for e in graph['edges']:
            if allowed.get(e['edge_id']) is True:self.outgoing[e['u']].append(e['edge_id'])
    def fallback(self,start,reason):
        self.audit['cpu_fallback_queries']=self.audit.get('cpu_fallback_queries',0)+1
        counts=self.audit.setdefault('fallback_reasons',{});counts[reason]=counts.get(reason,0)+1
        self.audit.setdefault('fallback_records',[]).append({'origin_node':start,'target_node':self.target,'reason':reason})
        if self.reference is None:self.reference=_CPU_PATH_INDEX(self.graph,self.allowed,self.blocked,self.target)
        return self.reference(start)
    def __call__(self,start):
        if start in self.memo:return self.memo[start]
        if start==self.target:return {'distance_m':0.0,'edges':[]}
        options=[]
        for key in self.outgoing[start]:
            i=self.index[key];cost=self.labels['distance'][i]
            if cost is not None and math.isfinite(cost):options.append((cost,self.labels['hops'][i],key,i))
        if not options:
            result=None;self.audit['gpu_weighted_queries']=self.audit.get('gpu_weighted_queries',0)+1
        else:
            options.sort();cost,hops,_,i=options[0]
            tolerance=256*math.ulp(max(1.0,abs(cost)))*max(1,hops)
            ambiguous=any(row[0]!=cost and abs(row[0]-cost)<=tolerance for row in options[1:])
            path=[];seen=set();cursor=i;reason='SOURCE_DISTANCE_TIE' if ambiguous else None
            while reason is None:
                if cursor in seen or not 0<=cursor<len(self.keys):reason='PATH_POINTER_INVALID';break
                seen.add(cursor);key=self.keys[cursor];path.append(key)
                if self.labels['ambiguous'][cursor]:reason='PATH_NUMERIC_AMBIGUITY';break
                following=self.labels['next'][cursor]
                if following<0:
                    if self.edges[key]['v']!=self.target:reason='PATH_TARGET_MISMATCH'
                    break
                if (key,self.keys[following]) in self.blocked or self.edges[key]['v']!=self.edges[self.keys[following]]['u']:
                    reason='PATH_TRANSITION_INVALID';break
                if self.labels['hops'][following]+1!=self.labels['hops'][cursor]:reason='PATH_HOPS_INVALID';break
                cursor=following
            if reason is None:
                reverse=0.0
                for key in reversed(path):reverse=self.edges[key]['length_m']+reverse
                if reverse!=cost:reason='REVERSE_SUM_DIFFERENCE'
            if reason:result=self.fallback(start,reason)
            else:
                result={'distance_m':sum(self.edges[k]['length_m'] for k in path),'edges':path}
                self.audit['gpu_weighted_queries']=self.audit.get('gpu_weighted_queries',0)+1
        self.memo[start]=result;return result


class CupyWeightedRouter:
    KERNEL=r'''extern "C" __global__ void relax(
      const long long* offsets,const int* successors,const double* weights,
      const unsigned char* terminals,int edges,int batch,
      const double* d,const int* hops,const int* next,
      double* nd,int* nh,int* nn,unsigned char* ambiguity,unsigned int* changed) {
      long long z=(long long)blockIdx.x*blockDim.x+threadIdx.x;
      if(z>=(long long)edges*batch)return;
      int e=z/batch,c=z%batch;double best=1.0/0.0;int bh=2147483647,bn=-1;
      if(terminals[z]){best=weights[e];bh=1;}
      for(long long p=offsets[e];p<offsets[e+1];p++){
        int f=successors[p];long long q=(long long)f*batch+c;
        if(!isfinite(d[q]))continue;
        double value=weights[e]+d[q];int h=hops[q]+1;
        if(value<best || (value==best && (h<bh || (h==bh && f<bn)))){best=value;bh=h;bn=f;}
      }
      unsigned char uncertain=0;
      if(isfinite(best)){
        double tolerance=256.0*2.2204460492503131e-16*fmax(1.0,fabs(best))*fmax(1,bh);
        for(long long p=offsets[e];p<offsets[e+1];p++){
          int f=successors[p];if(f==bn)continue;
          double value=weights[e]+d[(long long)f*batch+c];
          if(isfinite(value) && value!=best && fabs(value-best)<=tolerance)uncertain=1;
        }
      }
      nd[z]=best;nh[z]=bh;nn[z]=bn;ambiguity[z]=uncertain;
      if(best!=d[z] || bh!=hops[z] || bn!=next[z])atomicExch(changed,1u);
    }'''
    def __init__(self,graph,allowed,blocked,device=0,batch_size=8):
        import cupy as cp
        self.cp=cp;self.device=device;self.batch_size=batch_size;self.graph=graph;self.allowed=allowed;self.blocked=blocked
        self.keys=sorted(e['edge_id'] for e in graph['edges'] if allowed.get(e['edge_id']) is True)
        byid={e['edge_id']:e for e in graph['edges']};self.edges=[byid[k] for k in self.keys];index={k:i for i,k in enumerate(self.keys)}
        outgoing=defaultdict(list)
        for i,e in enumerate(self.edges):outgoing[e['u']].append(i)
        offsets=[0];successors=[]
        for e in self.edges:
            successors.extend(i for i in outgoing[e['v']] if (e['edge_id'],self.keys[i]) not in blocked);offsets.append(len(successors))
        self.offsets=offsets;self.successors=successors;self.labels={}
        self.audit={'backend':'CUDA_FP64_WEIGHTED_V2','gpu_weighted_queries':0,'cpu_fallback_queries':0,'fallback_reasons':{},'actual_cuda_executed':False}
        with cp.cuda.Device(device):self.kernel=cp.RawKernel(self.KERNEL,'relax',options=('--std=c++11','--fmad=false'))
    def compute(self,targets):
        import numpy as np
        cp=self.cp;targets=sorted(set(targets));n=len(self.edges)
        if not n:
            for target in targets:self.labels[target]={'keys':[],'distance':[],'hops':[],'next':[],'ambiguous':[]}
            return self.labels
        with cp.cuda.Device(self.device):
            offsets=cp.asarray(self.offsets,dtype=cp.int64);successors=cp.asarray(self.successors,dtype=cp.int32)
            weights=cp.asarray([e['length_m'] for e in self.edges],dtype=cp.float64)
            free,_=cp.cuda.runtime.memGetInfo();batch=min(self.batch_size,max(1,int(free*.2)//max(1,n*60)))
            for begin in range(0,len(targets),batch):
                chunk=targets[begin:begin+batch];b=len(chunk)
                print('GPU weighted routing: targets '+str(begin+1)+'-'+str(begin+b)+'/'+str(len(targets)),flush=True)
                terminals=cp.asarray([[e['v']==target for target in chunk] for e in self.edges],dtype=cp.uint8)
                distance=cp.full((n,b),cp.inf,dtype=cp.float64);hops=cp.full((n,b),2147483647,dtype=cp.int32);following=cp.full((n,b),-1,dtype=cp.int32)
                for iteration in range(n+1):
                    if iteration and iteration%100==0:print('GPU weighted iterations: '+str(iteration),flush=True)
                    nd=cp.empty_like(distance);nh=cp.empty_like(hops);nn=cp.empty_like(following);amb=cp.empty((n,b),dtype=cp.uint8);changed=cp.zeros(1,dtype=cp.uint32)
                    self.kernel((((n*b)+255)//256,),(256,),(offsets,successors,weights,terminals,np.int32(n),np.int32(b),distance,hops,following,nd,nh,nn,amb,changed))
                    distance,hops,following=nd,nh,nn
                    if not int(changed.get()[0]):break
                else:raise RuntimeError('GPU_WEIGHTED_DID_NOT_CONVERGE')
                dh,hh,fh,ah=distance.get(),hops.get(),following.get(),amb.get()
                for c,target in enumerate(chunk):
                    self.labels[target]={'keys':self.keys,'distance':dh[:,c].copy(),
                        'hops':hh[:,c].copy(),'next':fh[:,c].copy(),'ambiguous':ah[:,c].copy()}
                self.audit['gpu_relax_iterations']=self.audit.get('gpu_relax_iterations',0)+iteration+1
                self.audit['gpu_target_count']=self.audit.get('gpu_target_count',0)+b
                self.audit['actual_cuda_executed']=True
        return self.labels
    def lookup(self,target):return WeightedLookup(self.graph,self.allowed,self.blocked,target,self.labels[target],self.audit)

    def export_labels(self):
        return {target:{'keys':row['keys'],'distance':[float(v) if math.isfinite(v) else None for v in row['distance']],
            'hops':[int(v) for v in row['hops']],'next':[int(v) for v in row['next']],
            'ambiguous':[bool(v) for v in row['ambiguous']]} for target,row in self.labels.items()}
