"""Source-bound CPU market orchestration. Cache keys bind data, code and policy."""
from pathlib import Path
from copy import deepcopy
import hashlib
import math
from location_intelligent_li3_sources import read_json, write_json, canonical_bytes
from location_intelligent_market import (classify_store, corridor_tokens, restaurant_cluster,
                                         allocate_building, reconcile)


def acquire_market_network(config, root):
    """New-location roads/barriers only; never relabel the old network seed."""
    from pyproj import Transformer
    from location_intelligent_config import get_config
    from location_intelligent_validator import canonical_hash
    from location_intelligent_li3_sources import build_queries, acquire_overpass, utc
    from location_intelligent_map_pilot import sha
    root = Path(root)
    if (root/'network_manifest.json').exists():
        m = read_json(root/'network_manifest.json')
        if m['config'] != config:
            raise ValueError('Network cache config changed; choose new revision')
        for name, digest in m['files'].items():
            if sha(root/name) != digest:
                raise ValueError('Network cache corrupted')
        return root
    if root.exists():
        raise ValueError('Incomplete network acquisition; inspect failure then use a new source revision')
    root.mkdir(parents=True)
    p = get_config()
    p['li3'].update(latitude=config['latitude'], longitude=config['longitude'],
                    metric_crs=config['metric_crs'], network_bbox_radius_m=config['network_radius_m'])
    forward = Transformer.from_crs(4326, config['metric_crs'], always_xy=True)
    inverse = Transformer.from_crs(config['metric_crs'], 4326, always_xy=True)
    x, y = forward.transform(config['longitude'], config['latitude']); r = config['network_radius_m']
    corners = [inverse.transform(a, b) for a in (x-r, x+r) for b in (y-r, y+r)]
    frozen = {'schema_version':'li3_pilot_config_v1','algorithm_version':'LI3_V1',
              'analysis_run_id':root.name,'frozen_at':utc(),'policy':p,'target_xy':[x,y],
              'reference_metric_bbox':[x-r,y-r,x+r,y+r],
              'extraction_bbox_wgs84':[min(a for a,b in corners),min(b for a,b in corners),max(a for a,b in corners),max(b for a,b in corners)],
              'diagnostic_gap_m':10.0,'building_cache_files':{},'source_scope':'NEW_TARGET_OSM_MOTOR_NETWORK'}
    frozen['config_hash'] = canonical_hash(frozen)
    write_json(root/'config/pilot.json', frozen, exclusive=True)
    q = build_queries(frozen['extraction_bbox_wgs84'], p)
    write_json(root/'config/queries.json', q, exclusive=True)
    stamp = None
    for name in ('roads','features'):
        query = q[name]
        if name == 'features' and stamp:
            query = query.replace(';', '[date:"'+stamp+'"];', 1)
        result = acquire_overpass(query, config['poi_overpass_endpoints'], p['li3']['request_timeout_s'], p['li3']['max_response_bytes'])
        result['actual_query'] = query
        if name == 'features':
            result['requested_snapshot_as_of'] = stamp
        path = root/('raw/osm_roads.json.gz' if name == 'roads' else 'raw/osm_features_pinned.json.gz')
        write_json(path, result, exclusive=True)
        if result['status'] != 'SUCCEEDED':
            if name != 'features' or not stamp:
                raise RuntimeError('OSM '+name+' unavailable; no valid empty graph; inspect '+str(path))
            # The full request can exceed Overpass capacity in dense Jakarta.
            # Retain the failure and require all four exact-as-of tiles.
            west,south,east,north=frozen['extraction_bbox_wgs84']
            mx,my=(west+east)/2,(south+north)/2
            boxes=[(west,south,mx,my),(mx,south,east,my),
                   (west,my,mx,north),(mx,my,east,north)]
            for i,box in enumerate(boxes):
                tile_query=build_queries(box,p)['features'].replace(';','[date:"'+stamp+'"];',1)
                tile=acquire_overpass(tile_query,config['poi_overpass_endpoints'],p['li3']['request_timeout_s'],p['li3']['max_response_bytes'])
                tile.update(actual_query=tile_query,requested_snapshot_as_of=stamp)
                tile_path=root/f'raw/osm_features_tile_{i}.json.gz'
                write_json(tile_path,tile,exclusive=True)
                if tile['status']!='SUCCEEDED':
                    raise RuntimeError('Barrier tile unavailable; partial extraction cannot authorize routing: '+str(tile_path))
            from location_intelligent_li3 import select_feature_source
            selected,_=select_feature_source(root)
            if read_json(selected)['status']!='SUCCEEDED':
                raise RuntimeError('Tiled barrier source not complete')
        stamp = result['payload']['osm3s'].get('timestamp_osm_base') if name == 'roads' else stamp
    files = {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
    write_json(root/'network_manifest.json', {'config':config,'files':files}, exclusive=True)
    return root


def _connector_tokens(package, connector):
    return corridor_tokens(package['edge_sources'][connector['road_edge_id']]['raw_tags'])


def _poi_gate(config, policy, facilities, package, poi_targets, buildings):
    """Assess actual observed attractors and complete-link restaurant groups."""
    from location_intelligent_motor_routing import _path_index, _potential_reachability
    from pyproj import Transformer
    from shapely.geometry import shape, Point
    from shapely.ops import transform
    from shapely.strtree import STRtree
    if facilities.get('status') != 'SUCCEEDED':
        return {'state':'UNKNOWN','reason':'POI_INPUT_UNAVAILABLE','evidence':[]}
    graph = package['graph']; allowed = {k:r['allowed'] for k,r in package['edge_rules'].items()}
    blocked = {(r['from_edge'],r['to_edge']) for r in package['blocked_turns']}
    targets = {c.get('alternative_store_key'):c for c in package['connectors'] if c.get('alternative_store_key')}
    candidate = next((c for c in package['connectors'] if c['kind']=='TARGET' and 'alternative_store_key' not in c), None)
    if candidate is None:
        return {'state':'UNKNOWN','reason':'CANDIDATE_CONNECTOR_UNAVAILABLE','evidence':[]}
    tx = Transformer.from_crs(4326,config['metric_crs'],always_xy=True)
    shapes = [shape(f['geometry']) for f in buildings['features']]
    index = STRtree(shapes); by_id={f['properties']['building_id']:i for i,f in enumerate(buildings['features'])}
    evidence=[]; restaurants=[]; incomplete=False
    for p in poi_targets:
        conn = targets.get(p['store_key'])
        record={'source_id':p['source_id'],'category':p['category'],'eligible':False}
        evidence.append(record)
        if conn is None or allowed.get(conn['road_edge_id']) is not True:
            record['reason']='POI_CONNECTOR_UNAVAILABLE';incomplete=True;continue
        path = _path_index(graph,allowed,blocked,conn['node_id'])(candidate['node_id'])
        if path is None:
            unknown = _potential_reachability(graph,allowed,blocked,conn['node_id'])(candidate['node_id'])
            record['reason']='ROUTE_UNVERIFIED' if unknown else 'NO_OBSERVED_ROUTE'
            incomplete |= unknown;continue
        record.update(route_distance_m=path['distance_m'] + _connector_length(candidate) + _connector_length(conn),
                      eligible=True,reason='REACHABLE_IN_CONFIGURED_GRAPH')
        if p['category'] != 'restaurant':
            continue
        ids=[by_id[p['source_id']]] if p['source_id'] in by_id else []
        if not ids and p['point_basis']=='OSM_NODE':
            pt=Point(p['longitude'],p['latitude'])
            ids=[int(i) for i in index.query(pt) if shapes[int(i)].contains(pt)]
        if len(ids)!=1:
            record.update(eligible=False,reason='RESTAURANT_FOOTPRINT_UNVERIFIED');incomplete=True;continue
        i=ids[0];area=transform(tx.transform,shapes[i]).area
        record['footprint_area_m2']=area
        if area < policy['restaurant_cluster']['minimum_footprint_m2']:
            record.update(eligible=False,reason='RESTAURANT_FOOTPRINT_BELOW_40');continue
        tokens=_connector_tokens(package,conn)
        if not tokens:
            record.update(eligible=False,reason='RESTAURANT_CORRIDOR_UNVERIFIED');incomplete=True;continue
        restaurants.append({'source_id':p['source_id'],'building_id':buildings['features'][i]['properties']['building_id'],
                            'xy':p['target_xy'],'corridor_tokens':tokens})
    cluster=restaurant_cluster(restaurants,policy['restaurant_cluster']['maximum_pair_distance_m'],policy['restaurant_cluster']['minimum_sites'])
    positive=[r['source_id'] for r in evidence if r['eligible'] and r['category']!='restaurant']
    if positive or cluster:
        return {'state':'OPEN','reason':'OBSERVED_REACHABLE_ATTRACTOR' if positive else 'VERIFIED_RESTAURANT_CLUSTER',
                'positive_attractors':positive,'restaurant_cluster':cluster,'evidence':evidence}
    return {'state':'UNKNOWN' if incomplete else 'CLOSED',
            'reason':'INSUFFICIENT_ATTRACTOR_EVIDENCE' if incomplete else 'NO_QUALIFYING_ATTRACTOR_IN_OBSERVED_SNAPSHOT',
            'restaurant_cluster':None,'evidence':evidence}


def _connector_length(c):
    xy=c['geometry']['coordinates']
    return sum(math.dist(a,b) for a,b in zip(xy,xy[1:]))


def build_market(config, market_config, pilot, layers, facilities, output):
    from pyproj import Transformer, Geod
    from location_intelligent_li3 import verify_manifest,select_feature_source
    from location_intelligent_map_pilot import sha,poi_locations
    from location_intelligent_li3_graph import build_graph
    from location_intelligent_li3_connectors import generate_connectors
    from location_intelligent_alternatives import reachable_alternatives
    from location_intelligent_market_config import require_market_decisions
    import location_intelligent_market as domain
    import location_intelligent_alternatives as alternatives
    import location_intelligent_li3_graph as graph_code
    import location_intelligent_li3_connectors as connector_code
    import location_intelligent_motor_routing as motor_code
    policy=require_market_decisions(market_config)['allocation_requirements']
    if any(config[k]!=market_config['target'][k] for k in ('latitude','longitude')):
        raise ValueError('Market target differs from job')
    if config['building_radius_m']!=policy['zones_m'][-1] or config['min_area_m2']!=policy['residential_min_area_m2'] or config['max_area_m2']!=policy['residential_max_area_m2_exclusive'] or config.get('selection_profile')!='area-market-ge36-v1':
        raise ValueError('Market selection profile differs')
    pilot=Path(pilot);verify_manifest(pilot)
    frozen=read_json(pilot/'config/pilot.json')
    if any(frozen['policy']['li3'][k]!=config[k] for k in ('latitude','longitude','metric_crs')):
        raise ValueError('Pilot target differs from job')
    if frozen['policy']['travel']['reference_constant_speed']['value']!=policy['speed_kmh'] or frozen['policy']['travel']['max_travel_min']['value']!=policy['max_travel_minutes']:
        raise ValueError('Market time policy differs from frozen motor routing')
    if facilities.get('request_binding',{}).get('rules')!='osm_market_attractors_v2':
        raise ValueError('Market requires expanded POI inventory; legacy eight-category cache not sufficient')
    identity={'schema':'area_market_v1','config':config,'market_config':market_config,'pilot':sha(pilot/'manifest.json'),
              'stores':hashlib.sha256(canonical_bytes(layers)).hexdigest(),
              'facilities':hashlib.sha256(canonical_bytes(facilities)).hexdigest(),
              'code':{m.__name__:sha(m.__file__) for m in [domain,alternatives,graph_code,connector_code,motor_code]},'runtime':sha(__file__)}
    fingerprint=hashlib.sha256(canonical_bytes(identity)).hexdigest()
    root=Path(output)/fingerprint
    if (root/'manifest.json').exists():
        manifest=read_json(root/'manifest.json')
        if manifest['identity']!=identity:raise ValueError('Market cache binding changed')
        for name,digest in manifest['files'].items():
            if sha(root/name)!=digest:raise ValueError('Market result cache corrupted')
        return read_json(root/'result.json')
    if root.exists():raise ValueError('Incomplete market result; inspect rather than overwrite')
    for layer in layers.values():
        if layer['status']=='SUCCEEDED':
            b=layer['request_binding']
            if any(b[k]!=v for k,v in {'latitude':config['latitude'],'longitude':config['longitude'],'radius_m':2000}.items()):
                raise ValueError('BQ snapshot belongs to another location')
    binding=facilities.get('request_binding',{})
    if any(binding.get(k)!=v for k,v in {'latitude':config['latitude'],'longitude':config['longitude'],'radius_m':2000}.items()):
        raise ValueError('POI snapshot belongs to another location')
    tx=Transformer.from_crs(4326,config['metric_crs'],always_xy=True); geod=Geod(ellps='WGS84')
    metrics=read_json(pilot/'normalized/metric_buildings.json')
    selected=read_json(pilot/'building_results/selection.json')['selected']
    decisions=read_json(pilot/'building_results/decisions.json.gz')
    normalized=read_json(pilot/'normalized/buildings.geojson')
    features=read_json(select_feature_source(pilot)[0])
    base=build_graph(read_json(pilot/'raw/osm_roads.json.gz'),features,frozen)
    if base['graph'] is None:raise ValueError('Motor graph unavailable; market allocation blocked')
    stores=[];source_complete=all(l['status']=='SUCCEEDED' for l in layers.values());excluded=[]
    for kind,layer in sorted(layers.items()):
        for r in poi_locations(layer) if layer['status']=='SUCCEEDED' else []:
            if r['identity_location_conflict']:
                source_complete=False;excluded.append({'kind':kind,'store_id':r['store_id'],'reason':'IDENTITY_LOCATION_CONFLICT'});continue
            key=hashlib.sha256(canonical_bytes([kind,r['store_id'],r['latitude'],r['longitude']])).hexdigest()[:20]
            stores.append({'store_key':key,'name':' / '.join(r['names']) or str(r['store_id']),'kind':kind,
                           'latitude':r['latitude'],'longitude':r['longitude'],'distance_to_candidate_m':r['distance_m'],
                           'target_xy':list(tx.transform(r['longitude'],r['latitude']))})
    pois=[]
    for p in facilities.get('rows') or []:
        if p['category'] in {'market','hospital','station','recreation','police','bank','mall','restaurant'}:
            pois.append({**p,'store_key':'poi:'+p['source_id'],'target_xy':list(tx.transform(p['longitude'],p['latitude']))})
    package=generate_connectors(base,metrics,features,frozen,alternative_targets=[*stores,*pois])
    own_target=next((c for c in package['connectors'] if c['kind']=='TARGET' and not c.get('alternative_store_key')),None)
    candidate={'store_key':'candidate','kind':'candidate','name':'Calon toko','latitude':config['latitude'],
               'longitude':config['longitude'],'distance_to_candidate_m':0.0,'corridor_tokens':_connector_tokens(package,own_target) if own_target else []}
    conn_by_key={c.get('alternative_store_key'):c for c in package['connectors'] if c.get('alternative_store_key')}
    for s in stores:
        c=conn_by_key.get(s['store_key']);s['corridor_tokens']=_connector_tokens(package,c) if c else []
        if c is None:
            source_complete=False;excluded.append({'store_key':s['store_key'],'reason':'STORE_CONNECTOR_UNAVAILABLE'})
    stores=[classify_store(s,candidate['corridor_tokens'],policy) for s in [candidate,*stores]]
    route_package=deepcopy(package)
    for c in route_package['connectors']:
        if c['kind']=='TARGET' and not c.get('alternative_store_key'):c['alternative_store_key']='candidate'
    matrix=reachable_alternatives(route_package,stores,[b['building_id'] for b in selected])
    gate=_poi_gate(config,policy,facilities,package,pois,normalized)
    gate['snapshot_inventory_complete']=False
    property_by_id={f['properties']['building_id']:f['properties'] for f in normalized['features']}
    building_by_id={b['building_id']:b for b in selected}
    # Preserve primary per-building candidate route: extra graph split points
    # must not alter a validated baseline route or its origin policy.
    primary_routes={r['building_id']:r for r in read_json(pilot/'building_results/routing.json.gz')['routes']}
    rows=[]
    for d in decisions:
        bid=d.get('building_id')
        if not bid:continue
        b=building_by_id.get(bid);props=property_by_id[bid]
        if b:
            lon,lat=b['representative_point']['coordinates'];area=b['area_m2']
            distances={s['store_key']:geod.inv(lon,lat,s['longitude'],s['latitude'])[2] for s in stores}
            records={r['store_key']:r for r in matrix.get(bid,[])}
            primary=primary_routes.get(bid,{}).get('selected_candidate')
            if primary is not None:records['candidate']={'total_distance_m':primary['total_distance_m']}
            building={'building_id':bid,'residential':b['building_type']=='standard_residential',
                      'area_m2':area,'access_status':d['decision_state'],
                      'distance_to_candidate_m':distances['candidate'],'store_distances_m':distances}
            row=allocate_building(building,stores,records,gate,policy,inputs_complete=source_complete)
        else:
            row={'building_id':bid,'access_status':d['decision_state'],'market_status':'OTHERS',
                 'reason':d['reason'],'winner_store_key':None,'count_candidate':0,'scores':[],'estimated':True}
        row['area_m2']=b['area_m2'] if b else None
        row['use_review_reason']=props.get('use_review_reason')
        rows.append(row)
    if len(rows)!=len(decisions):raise ValueError('Missing building identity; cannot reconcile market ledger')
    result={'schema_version':'area_market_result_v1','status':'PARTIAL','fingerprint':fingerprint,'identity':identity,
            'output_path':str(root),'rows':rows,'summary':reconcile(rows),'stores':stores,'excluded_stores':excluded,
            'attractor_gate':gate,'market_inputs_complete':source_complete,'primary_routing_changed':False,
            'claim':'EXPERIMENTAL_HUFF_ESTIMATES_NOT_CALIBRATED_CUSTOMER_PROBABILITIES',
            'limitations':['Bounded OSM motor graph; source gaps and unobserved barriers remain',
                           'Equal store attractiveness, beta=2; whole footprint winner, no random draw',
                           'Residential fallback remains an assumption where source use is generic']}
    write_json(root/'result.json',result,exclusive=True)
    import csv,json
    with (root/'market_buildings.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['building_id','area_m2','access_status','market_status','reason','winner_store_key','count_candidate','scores'])
        writer.writeheader()
        for row in rows:writer.writerow({**{k:row.get(k) for k in writer.fieldnames},'scores':json.dumps(row['scores'],sort_keys=True)})
    write_json(root/'manifest.json',{'identity':identity,'files':{n:sha(root/n) for n in ['result.json','market_buildings.csv']}},exclusive=True)
    return result
