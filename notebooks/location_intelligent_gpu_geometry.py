"""Batched CUDA point/segment distances and line/polygon lengths, with audited GEOS fallback."""
import math
from collections import Counter

class GpuGeometry:
    DISTANCE=r'''extern "C" __global__ void distances(const double* p,const double* s,const long long* pi,const long long* si,long long n,double* out){
      long long i=(long long)blockDim.x*blockIdx.x+threadIdx.x;if(i>=n)return;
      long long a=pi[i]*2,b=si[i]*4;double x=p[a]-s[b],y=p[a+1]-s[b+1],dx=s[b+2]-s[b],dy=s[b+3]-s[b+1];
      double den=dx*dx+dy*dy,t=den>0?fmin(1.0,fmax(0.0,(x*dx+y*dy)/den)):0.0;
      out[i]=hypot(x-t*dx,y-t*dy);
    }'''
    CLIP=r'''extern "C" __global__ void polygon_lengths(const double* q,const double* edges,const long long* offsets,const long long* line_ids,const long long* polygon_ids,int count,double* lengths,unsigned char* uncertain,double* errors){
      int i=blockDim.x*blockIdx.x+threadIdx.x;if(i>=count)return;
      long long li=line_ids[i],poly=polygon_ids[i];
      double px=q[li*4],py=q[li*4+1],dx=q[li*4+2]-px,dy=q[li*4+3]-py,L=hypot(dx,dy),integral=0;
      int winding=0,events=0;unsigned char bad=0;double scale=1;
      for(long long k=offsets[poly];k<offsets[poly+1];k++){
        double ax=edges[k*4]-px,ay=edges[k*4+1]-py,bx=edges[k*4+2]-px,by=edges[k*4+3]-py;
        double ex=bx-ax,ey=by-ay,cross0=ex*(-ay)-ey*(-ax);
        double tol=128.0*2.2204460492503131e-16*(fabs(ex*ay)+fabs(ey*ax)+fabs(dx*ey)+fabs(dy*ex)+1.0);
        scale=fmax(scale,fmax(fabs(ax),fmax(fabs(ay),fmax(fabs(bx),fabs(by)))));
        if(fabs(cross0)<=tol && fmin(ax,bx)<=0 && fmax(ax,bx)>=0 && fmin(ay,by)<=0 && fmax(ay,by)>=0)bad=1;
        if(ay<=0 && by>0 && cross0>0)winding++;
        if(ay>0 && by<=0 && cross0<0)winding--;
        double den=dx*ey-dy*ex;
        if(fabs(den)<=tol){
          if(fabs(ax*dy-ay*dx)<=tol)bad=1;
          continue;
        }
        double t=(ax*ey-ay*ex)/den,u=(ax*dy-ay*dx)/den;
        double param_tol=512.0*2.2204460492503131e-16*(scale+L+1.0);
        if(t>=-param_tol && t<=1+param_tol && u>=-param_tol && u<=1+param_tol){
          if(t<=param_tol || t>=1-param_tol || u<=param_tol || u>=1-param_tol)bad=1;
          if(t>0 && t<1 && u>0 && u<1){integral+=(den<0?1.0:-1.0)*(1.0-t);events++;}
        }
      }
      if(winding<0 || winding>1)bad=1;
      integral+=winding;
      double err=1024.0*2.2204460492503131e-16*(offsets[poly+1]-offsets[poly]+1)*(scale+1)*(L+1);
      if(integral < -err || integral>1+err || L==0 || (events>0 && fabs(integral*L)<=err))bad=1;
      lengths[i]=integral*L;uncertain[i]=bad;errors[i]=err;
    }'''
    PRIMITIVES=r'''extern "C" __global__ void primitive_hits(const double* q,const double* edges,const long long* offsets,int count,unsigned char* hits,unsigned char* uncertain){
      int i=blockDim.x*blockIdx.x+threadIdx.x;if(i>=count)return;
      double px=q[i*4],py=q[i*4+1],dx=q[i*4+2]-px,dy=q[i*4+3]-py;unsigned char hit=0,bad=0;
      for(long long k=offsets[i];k<offsets[i+1];k++){
        double ax=edges[k*4]-px,ay=edges[k*4+1]-py,bx=edges[k*4+2]-px,by=edges[k*4+3]-py,ex=bx-ax,ey=by-ay;
        if(fmax(ax,bx)<fmin(0.0,dx) || fmin(ax,bx)>fmax(0.0,dx) || fmax(ay,by)<fmin(0.0,dy) || fmin(ay,by)>fmax(0.0,dy))continue;
        double c1=dx*ay-dy*ax,c2=dx*by-dy*bx,c3=ex*(-ay)-ey*(-ax),c4=ex*(dy-ay)-ey*(dx-ax);
        double tol=128.0*2.2204460492503131e-16*(fabs(dx*ay)+fabs(dy*ax)+fabs(ex*dy)+fabs(ey*dx)+1.0);
        if(ex==0.0 && ey==0.0){if(fabs(c1)<=tol)bad=1;continue;}
        if(fabs(c1)<=tol || fabs(c2)<=tol || fabs(c3)<=tol || fabs(c4)<=tol){bad=1;continue;}
        if(((c1<0)!=(c2<0)) && ((c3<0)!=(c4<0)))hit=1;
      }
      hits[i]=hit;uncertain[i]=bad;
    }'''
    def __init__(self,device=0):
        import cupy as cp
        self.cp=cp;self.device=device;self.audit={'backend':'CUDA_FP64_GEOMETRY_V2','gpu_distance_pairs':0,'gpu_polygon_queries':0,
            'cpu_fallback_queries':0,'fallback_reasons':{},'canonical_scalar_distances':0,'actual_cuda_executed':False}
        with cp.cuda.Device(device):
            self.dist_kernel=cp.RawKernel(self.DISTANCE,'distances',options=('--std=c++11','--fmad=false'))
            self.primitive_kernel=cp.RawKernel(self.PRIMITIVES,'primitive_hits',options=('--std=c++11','--fmad=false'))
            self.clip_kernel=cp.RawKernel(self.CLIP,'polygon_lengths',options=('--std=c++11','--fmad=false'))
        self.polygon_cache={};self.footprint_store=None
    def fallback(self,reason,context=None):
        self.audit['cpu_fallback_queries']+=1;counts=self.audit['fallback_reasons'];counts[reason]=counts.get(reason,0)+1
        self.audit.setdefault('fallback_records',[]).append({'reason':reason,**(context or {})})
    def distances(self,points,segments,pairs,limits=None):
        import numpy as np
        cp=self.cp;result=[]
        with cp.cuda.Device(self.device):
            ps=cp.asarray(points,dtype=cp.float64);ss=cp.asarray(segments,dtype=cp.float64)
            for begin in range(0,len(pairs),262144):
                chunk=pairs[begin:begin+262144];pi=cp.asarray([x[0] for x in chunk],dtype=cp.int64);si=cp.asarray([x[1] for x in chunk],dtype=cp.int64);out=cp.empty(len(chunk),dtype=cp.float64)
                self.dist_kernel((((len(chunk))+255)//256,),(256,),(ps,ss,pi,si,np.int64(len(chunk)),out))
                if not bool(cp.all(cp.isfinite(out)).get()):raise RuntimeError('GPU_DISTANCE_NONFINITE')
                if limits is not None:
                    accepted=out<=cp.asarray(limits[begin:begin+len(chunk)],dtype=cp.float64)
                    self.audit['gpu_filtered_pairs']=self.audit.get('gpu_filtered_pairs',0)+int(cp.count_nonzero(~accepted).get())
                    out=cp.where(accepted,out,cp.inf)
                result.extend(float(v) for v in out.get())
        self.audit['gpu_distance_pairs']+=len(pairs);self.audit['actual_cuda_executed']|=bool(pairs)
        return result
    def polygon_edges(self,geometry):
        key=geometry.wkb
        if key in self.polygon_cache:return self.polygon_cache[key]
        if geometry.is_empty:result=[]
        elif geometry.geom_type in {'Polygon','MultiPolygon'}:
            result=[]
            for poly in ([geometry] if geometry.geom_type=='Polygon' else geometry.geoms):
                for ring,outer in [(poly.exterior,True)]+[(r,False) for r in poly.interiors]:
                    coords=list(ring.coords);area=sum((b[0]-a[0])*(b[1]+a[1]) for a,b in zip(coords,coords[1:]))
                    ccw=area<0
                    if ccw!=outer:coords=list(reversed(coords))
                    result.extend([a[0],a[1],b[0],b[1]] for a,b in zip(coords,coords[1:]))
        else:result=None
        self.polygon_cache[key]=result;return result
    def polygon_lengths(self,queries):
        """Return (length, uncertain, conservative error) per line/valid polygon."""
        import numpy as np
        cp=self.cp;lines=[];edges=[];offsets=[0];valid=[];answers=[None]*len(queries)
        for i,(line,polygon) in enumerate(queries):
            rings=self.polygon_edges(polygon)
            if rings is None or len(line.coords)!=2:
                self.fallback('UNSUPPORTED_GEOMETRY');answers[i]=(line.intersection(polygon).length,False,0.0);continue
            valid.append(i);a,b=list(line.coords);lines.append([a[0],a[1],b[0],b[1]]);edges.extend(rings);offsets.append(len(edges))
        if valid:
            with cp.cuda.Device(self.device):
                q=cp.asarray(lines,dtype=cp.float64);es=cp.asarray(edges,dtype=cp.float64);off=cp.asarray(offsets,dtype=cp.int64)
                lengths=cp.empty(len(valid),dtype=cp.float64);uncertain=cp.empty(len(valid),dtype=cp.uint8)
                ids=cp.arange(len(valid),dtype=cp.int64);errors=cp.empty(len(valid),dtype=cp.float64)
                self.clip_kernel((((len(valid))+255)//256,),(256,),(q,es,off,ids,ids,np.int32(len(valid)),lengths,uncertain,errors))
                lh,uh=lengths.get(),uncertain.get()
            for j,i in enumerate(valid):
                line,polygon=queries[i];px,py=line.coords[0];extent=max(1.0,abs(polygon.bounds[0]-px),abs(polygon.bounds[2]-px),abs(polygon.bounds[1]-py),abs(polygon.bounds[3]-py)) if not polygon.is_empty else 1.0
                error=1024*math.ulp(1.0)*(offsets[j+1]-offsets[j]+1)*(extent+1)*(line.length+1)
                answers[i]=(float(lh[j]),bool(uh[j]),error)
            self.audit['gpu_polygon_queries']+=len(valid);self.audit['actual_cuda_executed']=True
        return answers
    def footprint_clear_batch(self,prepared,footprint_ids,footprints,tree,inset_geometry):
        # CPU-oracle subclasses override polygon_lengths and have no CUDA device.
        if hasattr(self,'cp'):
            return self.resident_footprint_batch(prepared,footprint_ids,footprints,tree,inset_geometry)
        queries=[];owners=[];hits=[[] for _ in prepared]
        for i,item in enumerate(prepared):
            if item is None:continue
            line=item['line'];bid=item['building_id'];target=item['target']
            for index in map(int,tree.query(line)):
                fid=footprint_ids[index];geom=footprints[fid]
                if fid==bid or (item['kind']=='TARGET' and geom.covers(target)):continue
                queries.append((line,inset_geometry(fid)));owners.append((i,fid))
        values=self.polygon_lengths(queries)
        for (line,poly),(i,fid),(length,uncertain,error) in zip(queries,owners,values):
            epsilon=prepared[i]['epsilon']
            if uncertain or not math.isfinite(length) or abs(length-epsilon)<=error:
                self.fallback('POLYGON_BOUNDARY_OR_THRESHOLD',{'building_id':prepared[i]['building_id'],'obstacle_id':fid,'line':list(line.coords)});length=line.intersection(poly).length
            if length>epsilon:hits[i].append({'source':fid,'kind':'other_building'})
        return hits

    def resident_footprint_batch(self,prepared,footprint_ids,footprints,tree,inset_geometry):
        """Upload inset polygons once; GPU queries reference resident edge ranges.

        STRtree is a CPU broadphase only. GPU performs the polygon intersections
        and threshold decisions. GEOS is used for explicit numerical ambiguity.
        """
        import numpy as np
        from time import perf_counter
        cp=self.cp;started=perf_counter();hits=[[] for _ in prepared]
        if self.footprint_store is None:
            polygons=[inset_geometry(fid) for fid in footprint_ids];edges=[];offsets=[0];unsupported=set()
            for j,polygon in enumerate(polygons):
                rings=self.polygon_edges(polygon)
                if rings is None:unsupported.add(j)
                else:edges.extend(rings)
                offsets.append(len(edges))
            with cp.cuda.Device(self.device):
                es=cp.asarray(np.asarray(edges,dtype=np.float64).reshape(-1,4));off=cp.asarray(offsets,dtype=cp.int64)
            self.footprint_store={'ids':footprint_ids,'polygons':polygons,'edges':es,'offsets':off,
                                  'unsupported':unsupported,'target_covers':{}}
            self.audit.update(resident_footprint_count=len(polygons),resident_polygon_edges=len(edges),
                              resident_polygon_uploads=1,resident_polygon_prepare_s=perf_counter()-started)
        store=self.footprint_store
        if footprint_ids!=store['ids']:raise RuntimeError('GPU_FOOTPRINT_SCOPE_CHANGED')
        lines=[item['line'] if item else None for item in prepared]
        # Vectorized broadphase, rather than a Python STRtree query per candidate.
        pairs=tree.query(lines)
        if not pairs.size:return hits
        li,pi=pairs;keep=np.ones(len(li),dtype=bool)
        own={fid:j for j,fid in enumerate(footprint_ids)}
        owners=np.asarray([own.get(item['building_id'],-1) if item else -1 for item in prepared])
        keep &= pi!=owners[li]
        targets={}
        for i,item in enumerate(prepared):
            if item and item['kind']=='TARGET':targets.setdefault(tuple(item['target'].coords[0]),[]).append(i)
        for xy,indexes in targets.items():
            if xy not in store['target_covers']:
                point=prepared[indexes[0]]['target']
                store['target_covers'][xy]=[j for j in map(int,tree.query(point)) if footprints[footprint_ids[j]].covers(point)]
            covered=store['target_covers'][xy]
            if covered:keep &= ~(np.isin(li,indexes)&np.isin(pi,covered))
        li,pi=li[keep],pi[keep]
        if not len(li):return hits
        q=np.asarray([list(line.coords[0])+list(line.coords[-1]) if line is not None else [0.]*4 for line in lines],dtype=np.float64)
        epsilon=np.asarray([item['epsilon'] if item else 0. for item in prepared],dtype=np.float64)
        with cp.cuda.Device(self.device):q_gpu=cp.asarray(q)
        # Bound transient output memory; the polygon edge store stays on device.
        for begin in range(0,len(li),262144):
            a,b=li[begin:begin+262144],pi[begin:begin+262144];n=len(a)
            with cp.cuda.Device(self.device):
                lengths=cp.empty(n,dtype=cp.float64);uncertain=cp.empty(n,dtype=cp.uint8);errors=cp.empty(n,dtype=cp.float64)
                self.clip_kernel(((n+255)//256,),(256,),
                    (q_gpu,store['edges'],store['offsets'],cp.asarray(a),cp.asarray(b),np.int32(n),lengths,uncertain,errors))
                eps=cp.asarray(epsilon[a]);amb=(uncertain!=0)|~cp.isfinite(lengths)|(cp.abs(lengths-eps)<=errors)
                # Only transfer positive intersections / ambiguous cases.
                indexes=cp.flatnonzero(amb|(lengths>eps)).get();ambiguous=amb[indexes].get()
            for j,ambiguous_value in zip(indexes,ambiguous):
                i=int(a[j]);p=int(b[j]);fid=footprint_ids[p];line=lines[i]
                if ambiguous_value or p in store['unsupported']:
                    self.fallback('POLYGON_BOUNDARY_OR_THRESHOLD',{'building_id':prepared[i]['building_id'],'obstacle_id':fid,'line':list(line.coords)})
                    if line.intersection(store['polygons'][p]).length<=epsilon[i]:continue
                hits[i].append({'source':fid,'kind':'other_building'})
            # Unsupported polygons must never be silently considered empty.
            for j in np.flatnonzero(np.isin(b,list(store['unsupported']))):
                if j in indexes:continue
                i=int(a[j]);p=int(b[j]);fid=footprint_ids[p]
                self.fallback('UNSUPPORTED_FOOTPRINT',{'obstacle_id':fid})
                if lines[i].intersection(store['polygons'][p]).length>epsilon[i]:hits[i].append({'source':fid,'kind':'other_building'})
        self.audit['gpu_polygon_queries']+=len(li);self.audit['actual_cuda_executed']=True
        self.audit['resident_footprint_batch_s']=self.audit.get('resident_footprint_batch_s',0.)+perf_counter()-started
        return hits
    def primitive_intersections(self,queries):
        import numpy as np
        cp=self.cp;lines=[];edges=[];offsets=[0];answers=[None]*len(queries);valid=[]
        for i,(line,geom) in enumerate(queries):
            if geom.geom_type=='Point':pieces=[[geom.coords[0],geom.coords[0]]]
            elif geom.geom_type in {'LineString','MultiLineString'}:
                pieces=[]
                for g in ([geom] if geom.geom_type=='LineString' else geom.geoms):pieces.extend(zip(list(g.coords),list(g.coords)[1:]))
            else:
                self.fallback('UNSUPPORTED_BARRIER');answers[i]=(line.intersects(geom),False);continue
            valid.append(i);a,b=list(line.coords);lines.append([a[0],a[1],b[0],b[1]])
            edges.extend([a[0],a[1],b[0],b[1]] for a,b in pieces);offsets.append(len(edges))
        if valid:
            with cp.cuda.Device(self.device):
                q=cp.asarray(lines,dtype=cp.float64);es=cp.asarray(edges,dtype=cp.float64);off=cp.asarray(offsets,dtype=cp.int64)
                hits=cp.empty(len(valid),dtype=cp.uint8);uncertain=cp.empty(len(valid),dtype=cp.uint8)
                self.primitive_kernel((((len(valid))+255)//256,),(256,),(q,es,off,np.int32(len(valid)),hits,uncertain))
                hh,uh=hits.get(),uncertain.get()
            for j,i in enumerate(valid):answers[i]=(bool(hh[j]),bool(uh[j]))
            self.audit['gpu_primitive_queries']=self.audit.get('gpu_primitive_queries',0)+len(valid);self.audit['actual_cuda_executed']=True
        return answers

    def barrier_batch(self,prepared,index,epsilon):
        # Polygon barriers run on CUDA; boundary/open-gate/point/line ambiguity
        # uses the unchanged GEOS predicate with explicit counters.
        from location_intelligent_li3_connectors import check_barriers
        result=[(True,[]) for _ in prepared];queries=[];owners=[];primitives=[];primitive_owners=[];fallback=set()
        for i,item in enumerate(prepared):
            if item is None:continue
            if index['unresolved']:
                fallback.add(i);continue
            for j in map(int,index['tree'].query(item['line'])):
                geom=index['shapes'][j]
                if geom.geom_type not in {'Polygon','MultiPolygon'}:
                    primitives.append((item['line'],geom));primitive_owners.append((i,j));continue
                queries.append((item['line'],geom));owners.append((i,j))
        for (line,poly),(i,j),(length,uncertain,error) in zip(queries,owners,self.polygon_lengths(queries)):
            if uncertain or not math.isfinite(length):fallback.add(i)
            elif length>0:result[i][1].append(index['records'][j])
        for (i,j),(hit,uncertain) in zip(primitive_owners,self.primitive_intersections(primitives)):
            if uncertain:fallback.add(i)
            elif hit:result[i][1].append(index['records'][j])
        for i,item in enumerate(prepared):
            if item is None:continue
            if i in fallback:
                self.fallback('BARRIER_BOUNDARY_OR_UNSUPPORTED',{'building_id':item['building_id'],'line':list(item['line'].coords)});result[i]=check_barriers(item['line'],index,epsilon)
            elif result[i][1]:
                if index['open_gates']:
                    self.fallback('BARRIER_GATE_OPENING');result[i]=check_barriers(item['line'],index,epsilon)
                else:result[i]=(False,result[i][1])
        return result


class GpuCandidatePlanner:
    def __init__(self,geometry,geometries,group_ids,tree,metrics,alternatives,maximum):
        from shapely.geometry import Point
        self.geometry=geometry;self.geometries=geometries;self.ids=group_ids;self.rows={}
        requests={tuple(metrics['target_xy']):None}
        for row in alternatives or []:requests[tuple(row['target_xy'])]=None
        for row in metrics['selected_buildings']:requests.setdefault(tuple(row['representative_point_m']),maximum)
        points=list(requests);segments=[list(g.coords[0])+list(g.coords[-1]) for g in geometries];pairs=[];members=[];limits=[]
        scale=max([1.0]+[abs(v) for row in segments for v in row]);self.error=512*math.ulp(1.0)*scale
        for i,xy in enumerate(points):
            point=Point(*xy);cap=requests[xy]
            indexes=range(len(geometries)) if cap is None else sorted(map(int,tree.query(point.buffer(cap))))
            for j in indexes:
                pairs.append((i,j));members.append((xy,j));limits.append(math.inf if cap is None else cap+self.error)
        values=geometry.distances(points,segments,pairs,limits=limits) if pairs else []
        for (xy,j),distance in zip(members,values):
            if math.isfinite(distance):self.rows.setdefault(xy,[]).append((distance,group_ids[j],j))
        for xy in self.rows:self.rows[xy].sort()
    def ordered(self,point,maximum=None):
        """GPU ranking; canonically resolve only overlapping numeric intervals."""
        rows=self.rows.get((point.x,point.y),[]);position=0
        while position<len(rows):
            end=position+1;upper=rows[position][0]+self.error
            while end<len(rows) and rows[end][0]-self.error<=upper:
                upper=max(upper,rows[end][0]+self.error);end+=1
            candidates=[]
            for _,name,j in rows[position:end]:
                distance=point.distance(self.geometries[j]);self.geometry.audit['canonical_scalar_distances']+=1
                if maximum is None or distance<=maximum:candidates.append((distance,name,j))
            for distance,_,j in sorted(candidates):yield distance,j
            position=end
            if maximum is not None and position<len(rows) and rows[position][0]-self.error>maximum:return
