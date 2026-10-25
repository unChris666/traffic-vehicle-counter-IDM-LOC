"""Resilient OSM transport for the GPU notebook; frozen domain helpers unchanged.

Successful source bytes are immutable. Retry and spatial subdivision preserve
selectors, exact source date, node recursion, extent and version-conflict checks.
"""
from pathlib import Path
from threading import RLock
import hashlib,re,time
from location_intelligent_li3_sources import read_json,write_json

_LOCK=RLock()
_BOX=re.compile(r'\((-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)\)')
_DATE=re.compile(r'\[date:"([^"]+)"\]')


class OsmAcquisitionError(RuntimeError):
    def __init__(self,code):self.code=code;super().__init__(code)


def safe_attempts(result):
    # Never publish response bodies or arbitrary exception messages.
    from urllib.parse import urlsplit
    rows=[]
    for attempt in result.get('attempts',[]):
        url=urlsplit(attempt.get('endpoint') or '')
        rows.append({**{k:attempt.get(k) for k in ['status','http_status','error_type','failure_reason']},
                     'endpoint':url.scheme+'://'+(url.hostname or '')+url.path})
    return rows


class RoadTransport:
    def __init__(self,root,frozen,queries,build_queries,fetch,*,sleep=time.sleep,retries=1,max_depth=2,max_calls=16,max_seconds=240):
        self.root=Path(root);self.policy=frozen['policy'];self.queries=queries;self.build_queries=build_queries;self.fetch=fetch
        self.sleep=sleep;self.retries=retries;self.max_depth=max_depth;self.max_calls=max_calls;self.max_seconds=max_seconds
        self.calls=0;self.started=time.monotonic();self.journal=self.root.parent/(self.root.name+'_transport_status.json')

    def record(self,state,**extra):
        write_json(self.journal,{'schema':'osm_transport_v1','status':state,'request_chains':self.calls,
            'elapsed_seconds':time.monotonic()-self.started,**extra})

    def call(self,query,endpoints,timeout,maximum):
        if self.calls>=self.max_calls or time.monotonic()-self.started>=self.max_seconds:
            self.record('PAUSED',error_code='OSM_RETRIEVAL_BUDGET_REACHED',action='Rerun sources; successful tiles retained')
            raise OsmAcquisitionError('OSM_RETRIEVAL_BUDGET_REACHED')
        self.calls+=1
        result=self.fetch(query,endpoints,timeout,maximum)
        self.record(result['status'],query_sha256=hashlib.sha256(query.encode()).hexdigest(),attempts=safe_attempts(result))
        return result

    @staticmethod
    def transient(result):
        attempts=result.get('attempts',[])
        return bool(attempts) and all(a.get('http_status') in {429,500,502,503,504} or
            a.get('status') in {'REQUEST_ERROR','PARTIAL_OR_INVALID'} for a in attempts)

    @staticmethod
    def subdividable(result):
        return any(a.get('http_status') in {500,502,504} or a.get('error_type')=='ReadTimeout' or
            any(word in str(a.get('remark','')).lower() for word in ['timeout','timed out','memory','maxsize'])
            for a in result.get('attempts',[]))

    def cached(self,path,query):
        if not path.exists():return None
        value=read_json(path)
        if value.get('actual_query')!=query:raise OsmAcquisitionError('OSM_SOURCE_QUERY_CHANGED')
        if value.get('status')!='SUCCEEDED':return None
        receipt=path.with_name(path.name+'.receipt.json')
        if not receipt.exists() or read_json(receipt)['sha256']!=hashlib.sha256(path.read_bytes()).hexdigest():
            raise OsmAcquisitionError('OSM_SOURCE_CHECKSUM_CHANGED')
        for name,digest in value.get('subtile_sha256',{}).items():
            child=self.root/name
            if not child.resolve().is_relative_to(self.root.resolve()) or not child.is_file() or hashlib.sha256(child.read_bytes()).hexdigest()!=digest:
                raise OsmAcquisitionError('OSM_SOURCE_CHECKSUM_CHANGED')
        return value

    def save(self,path,result,query):
        from location_intelligent_network_acquisition import _save
        value={**result,'actual_query':query};_save(path,value)
        if value['status']=='SUCCEEDED':write_json(path.with_name(path.name+'.receipt.json'),{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        return value

    def tile(self,query,endpoints,timeout,maximum,depth=0):
        key=hashlib.sha256(query.encode()).hexdigest()
        path=self.root/'raw/adaptive_roads'/(key+'.json.gz')
        cached=self.cached(path,query)
        if cached is not None:
            print('OSM road subtile: cached '+key[:10],flush=True);return cached
        # If a prior run started children, resume them without repeating parent.
        split_marker=path.with_name(path.name+'.split.json')
        result=read_json(path) if split_marker.exists() and path.exists() else self.call(query,endpoints,timeout,maximum)
        if result['status']=='SUCCEEDED':return self.save(path,result,query)
        self.save(path,result,query)
        if not split_marker.exists() and self.transient(result):
            # Resource exhaustion / read timeout: use smaller tiles immediately.
            if not self.subdividable(result):
                for retry in range(self.retries):
                    print('OSM road retry '+str(retry+1)+'/'+str(self.retries),flush=True);self.sleep(2*(retry+1))
                    result=self.call(query,endpoints,timeout,maximum)
                    self.save(path,result,query)
                    if result['status']=='SUCCEEDED':return {**result,'actual_query':query}
                    if not self.transient(result):break
            if depth>=self.max_depth or not self.subdividable(result):return result
        elif not split_marker.exists():return result
        matches=_BOX.findall(query)
        if not matches or len(set(matches))!=1:return result
        s,w,n,e=map(float,matches[0]);mx,my=(w+e)/2,(s+n)/2
        date=_DATE.search(query);stamp=date.group(1) if date else None
        if not split_marker.exists() and any(a.get('http_status') in {500,502,504} for a in result.get('attempts',[])):
            self.sleep(2)
        write_json(split_marker,{'query_sha256':key,'depth':depth})
        print('OSM road tile: subdivide depth='+str(depth+1)+'; successful children reused',flush=True)
        children=[]
        for box in [(w,s,mx,my),(mx,s,e,my),(w,my,mx,n),(mx,my,e,n)]:
            child_query=self.build_queries(box,self.policy)['roads']
            if stamp:child_query=child_query.replace(';','[date:"'+stamp+'"];',1)
            value=self.tile(child_query,endpoints,timeout,maximum,depth+1)
            if value['status']!='SUCCEEDED':return value
            if stamp is None:
                stamp=value.get('requested_snapshot_as_of') or value['payload']['osm3s'].get('timestamp_osm_base')
                if not stamp:raise OsmAcquisitionError('OSM_SNAPSHOT_TIMESTAMP_MISSING')
            children.append((child_query,value))
        from location_intelligent_li3_graph import merge_elements
        merged={};files={}
        for child_query,value in children:
            merged=merge_elements(list(merged.values()),value['payload']['elements'])
            child=self.root/'raw/adaptive_roads'/(hashlib.sha256(child_query.encode()).hexdigest()+'.json.gz')
            files[str(child.relative_to(self.root))]=hashlib.sha256(child.read_bytes()).hexdigest()
            files.update(value.get('subtile_sha256',{}))
        combined={'status':'SUCCEEDED','payload':{'elements':sorted(merged.values(),key=lambda r:(r['type'],r['id'])),
            'osm3s':{'timestamp_osm_base':stamp}},'requested_snapshot_as_of':stamp,'subtile_sha256':files,
            'attempts':result.get('attempts',[]),'retrieval':'EXACT_AS_OF_ADAPTIVE_ROAD_TILES'}
        return self.save(path,combined,query)

    def __call__(self,query,endpoints,timeout,maximum):
        # Keep full-scope failure cheap: canonical code already falls back to4tiles.
        # Feature categories retain their existing behavior and remain optional
        # by the notebook's ROADS_ONLY_EXPERIMENT profile.
        if query==self.queries['roads'] or 'way' not in query or '["highway"' not in query:
            return self.call(query,endpoints,timeout,maximum)
        result=self.tile(query,endpoints,timeout,maximum)
        if result['status']!='SUCCEEDED':
            self.record('UNAVAILABLE',error_code='OSM_ROAD_TILE_UNAVAILABLE',attempts=safe_attempts(result),
                        action='Rerun sources; completed source tiles remain unchanged')
            raise OsmAcquisitionError('OSM_ROAD_TILE_UNAVAILABLE')
        return result


def acquire_market_network_gpu(config,root):
    import location_intelligent_market_runtime as canonical
    import location_intelligent_network_acquisition as network
    with _LOCK:
        original=network.acquire_network_sources
        def wrapped(root,frozen,queries,config,build_queries,fetch):
            transport=RoadTransport(root,frozen,queries,build_queries,fetch)
            result=original(root,frozen,queries,config,build_queries,transport)
            transport.record('SUCCEEDED');return result
        network.acquire_network_sources=wrapped
        try:return canonical.acquire_market_network(config,root)
        finally:network.acquire_network_sources=original


def explain_source_failure(error,network_root,stages,readiness_path):
    """Public diagnostic from OSM receipts; never print a generic auth exception."""
    root=Path(network_root);paths=[root/'acquisition_status.json',root.parent/(root.name+'_transport_status.json')]
    details={'error_code':getattr(error,'code',None) or 'SOURCE_RUNTIME_ERROR','files':[]}
    print('Source failure code:',details['error_code'],flush=True)
    for path in paths:
        if not path.exists():continue
        details['files'].append(str(path))
        print('OSM diagnostic:',path,flush=True)
        try:value=read_json(path)
        except (OSError,ValueError):
            print('Diagnostic file unreadable; original failure retained',flush=True);continue
        print({k:value[k] for k in ['stage','status','error_code','failed_tile','request_chains','attempts','action'] if k in value},flush=True)
    stages['sources'].update(source_diagnostic=details)
    try:
        path=Path(readiness_path);report=read_json(path);report['stages']=stages;write_json(path,report)
    except (OSError,ValueError):print('Readiness diagnostic update unavailable; original failure retained',flush=True)
    print('Rerun sources in the same session to reuse successful tiles; calculation needs complete roads.',flush=True)
