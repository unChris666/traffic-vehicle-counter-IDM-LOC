"""Allocation-only owner policy: radial POI gate400, store participants800.

Scoped adapters preserve frozen calculation, connector and Huff algorithms.
"""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import hashlib
import math


def configure_scope(config):
    result=deepcopy(config)
    result['policy_version']='owner_market_poi400_stores800_v5_2026_10_26'
    result['sources'].update(competitor_calculation_radius_m=800.0,indomaret_calculation_radius_m=800.0)
    result['allocation_requirements'].update(attractor_radius_m=400.0,
        attractor_gate='RADIAL_ATTRACTOR_400M_NO_POI_ROUTING')
    result['allocation_adapter_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def store_in_scope(kind,distance_m,config):
    if kind=='candidate':return True
    if kind not in {'competitor','indomaret'}:raise ValueError('UNKNOWN_STORE_KIND')
    return math.isfinite(distance_m) and 0<=distance_m<=800.0


def radial_poi_gate(config,policy,facilities,package,poi_targets,buildings,*,network=None):
    """No POI connectors or graph traversal. Restaurant criteria remain explicit."""
    from pyproj import Geod,Transformer
    from shapely.geometry import Point,shape
    from shapely.ops import transform
    from shapely import STRtree
    from location_intelligent_market import restaurant_cluster,corridor_tokens
    if not policy['outer_zone_requires_attractor']:
        return {'state':'OPEN','reason':'ATTRACTOR_REQUIREMENT_DISABLED_BY_BUSINESS_POLICY','evidence':[]}
    if facilities.get('status')!='SUCCEEDED':
        return {'state':'UNKNOWN','reason':'POI_INPUT_UNAVAILABLE','evidence':[]}
    geod=Geod(ellps='WGS84');radius=policy['attractor_radius_m']
    allowed=set(policy['attractor_kinds'])-{'restaurant_cluster'}
    evidence=[];restaurants=[];positive=[];incomplete=False
    tx=Transformer.from_crs(4326,config['metric_crs'],always_xy=True)
    shapes=None;index=None;by_id=None;road_tree=None;road_shapes=None;edges=None
    for p in sorted(poi_targets,key=lambda p:p['source_id']):
        distance=geod.inv(config['longitude'],config['latitude'],p['longitude'],p['latitude'])[2]
        row={'source_id':p['source_id'],'category':p['category'],'distance_to_candidate_m':distance,
             'eligible':False,'basis':'RADIAL_DISTANCE_NO_ROUTE_REQUIRED'}
        evidence.append(row)
        if distance>radius:
            row['reason']='OUTSIDE_ATTRACTOR_400M';continue
        if p['category'] in allowed:
            row.update(eligible=True,reason='QUALIFYING_ATTRACTOR_WITHIN_400M');positive.append(p['source_id']);continue
        if p['category']!='restaurant':
            row['reason']='NOT_A_QUALIFYING_ATTRACTOR';continue
        # Restaurant cluster requirements are unchanged; inspect only nearby sites.
        if shapes is None:
            shapes=[shape(f['geometry']) for f in buildings['features']];index=STRtree(shapes)
            by_id={f['properties']['building_id']:i for i,f in enumerate(buildings['features'])}
        ids=[by_id[p['source_id']]] if p['source_id'] in by_id else []
        if not ids and p.get('point_basis')=='OSM_NODE':
            pt=Point(p['longitude'],p['latitude']);ids=[int(i) for i in index.query(pt) if shapes[int(i)].contains(pt)]
        if len(ids)!=1:
            row['reason']='RESTAURANT_FOOTPRINT_UNVERIFIED';incomplete=True;continue
        i=ids[0];area=transform(tx.transform,shapes[i]).area;row['footprint_area_m2']=area
        if area<policy['restaurant_cluster']['minimum_footprint_m2']:
            row['reason']='RESTAURANT_FOOTPRINT_BELOW_40';continue
        if road_tree is None:
            from shapely.geometry import LineString
            edges=sorted(package['graph']['edges'],key=lambda e:e['edge_id'])
            road_shapes=[LineString(e['geometry']['coordinates']) for e in edges];road_tree=STRtree(road_shapes)
        xy=tx.transform(p['longitude'],p['latitude']);point=Point(*xy)
        nearest=sorted(map(int,road_tree.query_nearest(point,all_matches=True))) if edges else []
        token_sets=[set(corridor_tokens(package['edge_sources'][edges[j]['edge_id']]['raw_tags'])) for j in nearest]
        # Equidistant roads with different names cannot assert a common corridor.
        tokens=sorted(set.intersection(*token_sets)) if token_sets else []
        if not tokens:
            row['reason']='RESTAURANT_CORRIDOR_UNVERIFIED';incomplete=True;continue
        row.update(eligible=True,reason='RESTAURANT_CLUSTER_CANDIDATE',corridor_basis='NEAREST_ROAD_NAME_REF_ASSUMPTION',corridor_tokens=tokens)
        restaurants.append({'source_id':p['source_id'],'building_id':buildings['features'][i]['properties']['building_id'],
                            'xy':xy,'corridor_tokens':tokens})
    cluster=restaurant_cluster(restaurants,policy['restaurant_cluster']['maximum_pair_distance_m'],policy['restaurant_cluster']['minimum_sites'])
    return {'state':'OPEN' if positive or cluster else 'UNKNOWN' if incomplete else 'CLOSED',
            'reason':'OBSERVED_ATTRACTOR_WITHIN_400M' if positive else 'VERIFIED_RESTAURANT_CLUSTER_WITHIN_400M' if cluster else 'INSUFFICIENT_ATTRACTOR_EVIDENCE' if incomplete else 'NO_QUALIFYING_ATTRACTOR_WITHIN_400M',
            'positive_attractors':positive,'restaurant_cluster':cluster,'evidence':evidence,
            'radius_m':radius,'poi_routing_performed':False}


@contextmanager
def market_scope():
    """Apply to GPU and CPU comparison together; restore even on failure."""
    import location_intelligent_market_runtime as runtime
    from location_intelligent_gpu_runtime import _LOCK
    with _LOCK:
        original=(runtime._poi_gate,runtime._market_store_in_scope,runtime._reuse_calculation_connectors)
        def reuse(pilot,metrics,features,frozen,targets):
            stores=[p for p in targets if not p['store_key'].startswith('poi:')]
            print('Market scope: routing',len(stores),'store targets; POI routing disabled',flush=True)
            return original[2](pilot,metrics,features,frozen,stores)
        runtime._poi_gate=radial_poi_gate;runtime._market_store_in_scope=store_in_scope
        runtime._reuse_calculation_connectors=reuse
        try:yield
        finally:runtime._poi_gate,runtime._market_store_in_scope,runtime._reuse_calculation_connectors=original
