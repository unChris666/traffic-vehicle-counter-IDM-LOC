"""Resumable bounded source acquisition; no relaxation of motor/barrier rules."""
from pathlib import Path
import hashlib
from location_intelligent_li3_sources import canonical_bytes,read_json,write_json


def feature_part_queries(box,policy,stamp):
    """Same feature selectors as the original union, independently retrievable."""
    w,s,e,n=box;region=f'({s},{w},{n},{e})'
    li=policy['li3'];timeout=min(20,li['request_timeout_s'])
    header=f'[out:json][timeout:{timeout}][maxsize:{li["max_response_bytes"]}][date:"{stamp}"];'
    selectors={'node_barriers':'node["barrier"]','way_barriers':'way["barrier"]',
               'waterways':'way["waterway"]','water_polygons':'way["natural"="water"]',
               'water_relations':'relation["natural"="water"]','turn_restrictions':'relation["type"="restriction"]'}
    return {name:header+'('+selector+region+';);(._;>>;);out meta;' for name,selector in selectors.items()}


def _save(path,value):
    """Only draft acquisition files may be replaced; retain failed history."""
    if path.exists():
        previous=path.read_bytes()
        digest=hashlib.sha256(previous).hexdigest()
        archive=path.parent/'attempt_history'/(path.name+'.'+digest+'.gz')
        if not archive.exists():
            archive.parent.mkdir(parents=True,exist_ok=True);archive.write_bytes(previous)
    # Preserve gzip encoding based on the eventual canonical extension.
    tmp=path.with_name(path.stem+'.partial'+path.suffix)
    write_json(tmp,value);tmp.replace(path)


def acquire_network_sources(root,frozen,queries,config,build_queries,fetch):
    """Try full scope once, then four tiles. Rerun fetches failed tiles only.

    All successful pieces bind their exact query and bytes; failed pieces never
    produce a network manifest. A common road snapshot date pins remaining tiles.
    """
    root=Path(root);p=frozen['policy'];li=p['li3'];endpoints=config['poi_overpass_endpoints']
    def status(stage,state,**extra):
        write_json(root/'acquisition_status.json',{'stage':stage,'status':state,
                   'retry_action':'Rerun this acquisition cell; successful pieces are reused',**extra})
    fresh_requests=0
    def request(path,query,stage,retry_failed,timeout=None):
        nonlocal fresh_requests
        digest=hashlib.sha256(query.encode()).hexdigest()
        receipt=path.with_name(path.name+'.receipt.json')
        if path.exists():
            old=read_json(path)
            if old.get('actual_query')!=query:
                raise ValueError('Cached query differs at '+str(path))
            if old['status']=='SUCCEEDED':
                if receipt.exists() and read_json(receipt)['sha256']!=hashlib.sha256(path.read_bytes()).hexdigest():
                    raise ValueError('Cached successful source changed: '+str(path))
                if not receipt.exists():write_json(receipt,{'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'query_sha256':digest},exclusive=True)
                for name,digest in old.get('tile_sha256',{}).items():
                    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Cached feature piece changed')
                return old
            if not retry_failed:return old
        print('OSM acquisition:',stage,flush=True);status(stage,'RUNNING',query_sha256=digest)
        if fresh_requests>=64:
            status(stage,'PAUSED_REQUEST_BUDGET')
            raise RuntimeError('Acquisition checkpoint: 64 request chains reached. Rerun cell5 to continue cached progress.')
        fresh_requests+=1
        result=fetch(query,endpoints,timeout or li['request_timeout_s'],li['max_response_bytes'])
        result['actual_query']=query
        _save(path,result)
        if result['status']=='SUCCEEDED':
            write_json(receipt,{'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'query_sha256':digest},exclusive=True)
        return result
    def merge_pieces(pieces,query):
        from location_intelligent_li3_graph import merge_elements
        merged=[]
        for path,piece in pieces:merged=list(merge_elements(merged,piece['payload']['elements']).values())
        return {'status':'SUCCEEDED','payload':{'elements':sorted(merged,key=lambda r:(r['type'],r['id'])),
                    'osm3s':{'timestamp_osm_base':stamp},'generator':pieces[0][1]['payload'].get('generator')},
                'actual_query':query,'requested_snapshot_as_of':stamp,
                'tile_sources':[str(path.relative_to(root)) for path,r in pieces],
                'tile_sha256':{str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path,r in pieces}}
    def parts(box,base,depth=0,selected=None):
        pieces=[]
        for name,query in feature_part_queries(box,p,stamp).items():
            if selected is not None and name!=selected:continue
            path=base/(name+'.json.gz')
            piece=request(path,query,'features/'+str(base.relative_to(root))+'/'+name,not (base/(name+'_children')).exists(),min(20,li['request_timeout_s']))
            if piece['status']!='SUCCEEDED':
                # Spatial subdivision helps server-reported resource exhaustion;
                # it cannot repair an unavailable endpoint or denied request.
                remarks=' '.join(str(a.get('remark','')).lower() for a in piece.get('attempts',[]))
                resource=any(word in remarks for word in ['timed out','timeout','out of memory','memory limit','maxsize'])
                if depth<2 and resource:
                    w,s,e,n=box;mx,my=(w+e)/2,(s+n)/2
                    children=[]
                    for j,child in enumerate([(w,s,mx,my),(mx,s,e,my),(w,my,mx,n),(mx,my,e,n)]):
                        # Only subdivide the failed category, not successful ones.
                        children.extend(parts(child,base/(name+'_children')/str(j),depth+1,selected=name))
                    piece=merge_pieces(children,query);_save(path,piece)
                    write_json(path.with_name(path.name+'.receipt.json'),{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
                else:
                    safe=[{k:a.get(k) for k in ['endpoint','status','http_status','error_type','remark','failure_reason']} for a in piece.get('attempts',[])]
                    status('features/'+name,'BLOCKED_SOURCE_UNAVAILABLE',attempts=safe,source_path=str(path))
                    raise RuntimeError('OSM feature category '+name+' unavailable: '+str(safe)+'. Successful categories retained; inspect '+str(root/'acquisition_status.json'))
            pieces.append((path,piece))
        return pieces
    west,south,east,north=frozen['extraction_bbox_wgs84'];mx,my=(west+east)/2,(south+north)/2
    boxes=[(west,south,mx,my),(mx,south,east,my),(west,my,mx,north),(mx,my,east,north)]
    stamp=None
    for kind,filename in [('roads','osm_roads.json.gz'),('features','osm_features_pinned.json.gz')]:
        if kind=='features' and config.get('network_feature_mode')=='ROADS_ONLY_EXPERIMENT':
            roads=read_json(root/'raw/osm_roads.json.gz')
            derived={'status':'SUCCEEDED','provider':'DERIVED_FROM_ACTUAL_OSM_ROAD_EXTRACT',
                     'coverage':'ROAD_EXTRACT_ONLY_EXTERNAL_FEATURES_NOT_REQUESTED',
                     'external_features_requested':False,'restrictions_complete':False,
                     'source_roads_sha256':hashlib.sha256((root/'raw/osm_roads.json.gz').read_bytes()).hexdigest(),
                     'payload':roads['payload']}
            path=root/'raw/osm_features_roads_only.json.gz'
            if path.exists():
                if read_json(path)!=derived:raise ValueError('Road-derived feature snapshot changed')
            else:write_json(path,derived,exclusive=True)
            break
        query=queries[kind]
        if stamp:query=query.replace(';','[date:"'+stamp+'"];',1)
        canonical=root/'raw'/filename
        # Assembled roads are consumed using their own retained tile identities.
        if canonical.exists() and read_json(canonical).get('tile_sources'):
            assembled=read_json(canonical)
            receipt=canonical.with_name(canonical.name+'.receipt.json')
            if not receipt.exists() or read_json(receipt)['sha256']!=hashlib.sha256(canonical.read_bytes()).hexdigest():
                raise ValueError('Assembled source checksum differs')
            for name,digest in assembled['tile_sha256'].items():
                if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Assembled tile changed')
            result=assembled
        else:result=request(canonical,query,kind+'_full',False)
        if result['status']!='SUCCEEDED':
            codes=[a.get('http_status') for a in result.get('attempts',[])]
            if codes and all(code in {400,401,403} for code in codes):
                status(kind,'BLOCKED_REQUEST_REJECTED',http_statuses=codes)
                raise RuntimeError('OSM request rejected '+str(codes)+': inspect query/network access; tiles cannot fix this. '+str(root/'acquisition_status.json'))
            tiles=[]
            for i,box in enumerate(boxes):
                tq=build_queries(box,p)[kind]
                if stamp:tq=tq.replace(';','[date:"'+stamp+'"];',1)
                path=root/f'raw/osm_{kind}_tile_{i}.json.gz'
                tile=request(path,tq,f'{kind}_tile_{i+1}/4',kind=='roads')
                if tile['status']!='SUCCEEDED' and kind=='features':
                    pieces=parts(box,root/'raw/feature_parts'/str(i))
                    tile=merge_pieces(pieces,tq);_save(path,tile)
                    write_json(path.with_name(path.name+'.receipt.json'),{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
                if tile['status']!='SUCCEEDED':
                    safe=[{k:a.get(k) for k in ['endpoint','status','http_status','error_type']} for a in tile.get('attempts',[])]
                    status(kind,'BLOCKED_SOURCE_UNAVAILABLE',failed_tile=i,attempts=safe)
                    raise RuntimeError('OSM '+kind+' tile '+str(i+1)+'/4 unavailable: '+str(safe)+
                                       '. Rerun the same cell to resume; successful data retained. Details: '+str(root/'acquisition_status.json'))
                if stamp is None:
                    stamp=tile['payload']['osm3s'].get('timestamp_osm_base')
                    if not stamp:raise ValueError('Road tile has no snapshot timestamp')
                tiles.append((path,tile))
            from location_intelligent_li3_graph import merge_elements
            merged=[]
            for path,tile in tiles:merged=list(merge_elements(merged,tile['payload']['elements']).values())
            result={'status':'SUCCEEDED','payload':{'elements':sorted(merged,key=lambda r:(r['type'],r['id'])),
                       'osm3s':{'timestamp_osm_base':stamp},'generator':tiles[0][1]['payload'].get('generator')},
                    'actual_query':query,'requested_snapshot_as_of':stamp,
                    'tile_sources':[str(path.relative_to(root)) for path,t in tiles],
                    'tile_sha256':{str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path,t in tiles}}
            _save(canonical,result)
            # Canonical receipt belongs to the newly assembled successful bytes.
            write_json(canonical.with_name(canonical.name+'.receipt.json'),{'sha256':hashlib.sha256(canonical.read_bytes()).hexdigest(),
                         'query_sha256':hashlib.sha256(query.encode()).hexdigest()})
        if kind=='roads':
            stamp=result['payload']['osm3s'].get('timestamp_osm_base')
            if not stamp:raise ValueError('Road snapshot timestamp unavailable')
    status('network','SUCCEEDED',snapshot_as_of=stamp,
           feature_mode=config.get('network_feature_mode','FULL'),
           external_features_requested=config.get('network_feature_mode')!='ROADS_ONLY_EXPERIMENT')
