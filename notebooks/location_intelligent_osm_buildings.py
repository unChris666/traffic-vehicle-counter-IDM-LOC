"""OSM building adapter. Retain raw topology/tags; never repair invalid polygons."""
import math
from copy import deepcopy
from pathlib import Path
from location_intelligent_li3_sources import read_json,write_json,acquire_overpass,utc

SCHEMA='osm_buildings_adapter_v1'
FACILITY_AMENITIES={'hospital','clinic','doctors','dentist','pharmacy','marketplace','police','school',
 'kindergarten','college','university','townhall','courthouse','place_of_worship','library','bank',
 'restaurant','cafe','fast_food','bar','pub','cinema','theatre','fire_station','post_office','community_centre'}

def use_tags(tags):
    """Positive building-use hints, not every amenity such as a bench/bin."""
    return [k+'='+tags[k] for k in ['amenity','healthcare','shop','office','tourism']
            if tags.get(k) not in {None,'','no'} and (k!='amenity' or tags[k] in FACILITY_AMENITIES)]

def join_rings(parts):
    parts=[list(p) for p in parts]
    rings=[]
    while parts:
        ring=parts.pop(0)
        while ring[0]!=ring[-1]:
            matches=[(i,p) for i,p in enumerate(parts) if p[0]==ring[-1] or p[-1]==ring[-1]]
            if len(matches)!=1:raise ValueError('OPEN_OR_AMBIGUOUS_RING')
            i,p=matches[0];parts.pop(i)
            if p[-1]==ring[-1]:p=p[::-1]
            ring.extend(p[1:])
        if len(ring)<4:raise ValueError('SHORT_RING')
        rings.append(ring)
    return rings

def normalize_osm(raw,with_diagnostics=False):
    from osgeo import ogr,gdal
    if raw.get('schema_version')!=SCHEMA or raw.get('provider')!='OPENSTREETMAP':raise ValueError('Wrong OSM adapter schema')
    elements=raw['payload']['elements'];features=[];excluded=[]
    if len({(e['type'],e['id']) for e in elements})!=len(elements):raise ValueError('Duplicate OSM identities')
    members={m['ref'] for e in elements if e['type']=='relation' for m in e.get('members',[]) if m['type']=='way'}
    def polygon(coords):
        ring=ogr.Geometry(ogr.wkbLinearRing)
        for lon,lat in coords:ring.AddPoint_2D(lon,lat)
        p=ogr.Geometry(ogr.wkbPolygon);p.AddGeometry(ring);return p
    def coords(member):
        return [(v['lon'],v['lat']) for v in member.get('geometry',[])]
    def positive(value):
        try:
            x=float(value);return x if math.isfinite(x) and x>0 else None
        except (ValueError,TypeError):return None
    for e in sorted(elements,key=lambda e:(e['type'],e['id'])):
        bid=f"{e['type']}/{e['id']}";tags=e.get('tags',{});kind=tags.get('building')
        if e['type']=='way' and e['id'] in members:
            excluded.append({'source_id':bid,'reason':'RELATION_MEMBER_COMPONENT'});continue
        try:
            if not kind or kind=='no':raise ValueError('NO_ACTIVE_BUILDING_TAG')
            if e['type']=='way':
                c=coords(e)
                if len(c)<4 or c[0]!=c[-1]:raise ValueError('OPEN_WAY')
                geometry=polygon(c)
            elif e['type']=='relation' and tags.get('type')=='multipolygon':
                outer=[];inner=[]
                for m in e.get('members',[]):
                    if m['type']!='way' or m.get('role','') not in {'','outer','inner'}:raise ValueError('UNSUPPORTED_MEMBER')
                    c=coords(m)
                    if len(c)<2:raise ValueError('MISSING_MEMBER_GEOMETRY')
                    (inner if m.get('role')=='inner' else outer).append(c)
                polygons=[polygon(c) for c in join_rings(outer)]
                if not polygons:raise ValueError('MISSING_OUTER')
                for hole in join_rings(inner):
                    hp=polygon(hole);owners=[p for p in polygons if p.Contains(hp)]
                    if len(owners)!=1:raise ValueError('AMBIGUOUS_INNER')
                    owners[0].AddGeometry(hp.GetGeometryRef(0))
                geometry=ogr.Geometry(ogr.wkbMultiPolygon)
                for p in polygons:geometry.AddGeometry(p)
            else:raise ValueError('UNSUPPORTED_OSM_OBJECT')
            with gdal.quiet_errors():
                if geometry.IsEmpty() or not geometry.IsValid():raise ValueError('INVALID_TOPOLOGY')
            import json
            residential={'house','detached','semidetached_house','terrace','residential','bungalow'}
            cls=None if kind=='yes' else kind
            subclass=None if kind=='yes' else 'residential' if kind in residential else kind
            if kind in {'apartments','dormitory','hotel'}:subclass=None
            features.append({'type':'Feature','id':bid,'geometry':json.loads(geometry.ExportToJson()),
                'properties':{'building_id':bid,'class':cls,'subclass':subclass,
                 'height':positive(tags.get('height')),'num_floors':positive(tags.get('building:levels')),
                 'source_feature_version':e.get('version'),'sources':[{'dataset':'OpenStreetMap','record_id':bid}],
                 'osm_tags':deepcopy(tags),'osm_timestamp':e.get('timestamp')}})
        except (ValueError,RuntimeError,KeyError) as error:
            excluded.append({'source_id':bid,'reason':str(error)[:100]})
    if raw.get('use_policy_version')=='osm_poi_use_v2':
        external=raw.get('facility_evidence')
        available=bool(external and external.get('status')=='SUCCEEDED')
        evidence=deepcopy(external) if available else {'status':'SUCCEEDED','rows':[]}
        known={r['source_id'] for r in evidence['rows']}
        for node in raw.get('use_poi_nodes',[]):
            tags=node.get('tags',{})
            active=use_tags(tags)
            sid='node/'+str(node['id'])
            if active and sid not in known:
                evidence['rows'].append({'source_id':sid,'latitude':node['lat'],'longitude':node['lon'],'point_basis':'OSM_NODE'})
        apply_poi_use_review(features,evidence if available or 'use_poi_nodes' in raw else None)
    result={'type':'FeatureCollection','features':features}
    if with_diagnostics:return result,{'raw_elements':len(elements),'canonical_features':len(features),'excluded':excluded,
        'class_policy':raw.get('use_policy_version','explicit_OSM_tags_v1; building=yes keeps null legacy N1 fallback, not observed residential use')}
    return result

def apply_poi_use_review(features,facility_evidence):
    """POI evidence precedes null residential fallback; no nearby-point guessing."""
    from osgeo import ogr
    import json
    geometries={f['id']:ogr.CreateGeometryFromJson(json.dumps(f['geometry'])) for f in features}
    hits={f['id']:[] for f in features}
    spatial=EnvelopePointIndex([(bid,g.GetEnvelope()) for bid,g in geometries.items()])
    if facility_evidence and facility_evidence.get('status')=='SUCCEEDED':
        for poi in facility_evidence['rows']:
            if poi['source_id'] in hits:
                hits[poi['source_id']].append({'id':poi['source_id'],'basis':'SAME_OSM_OBJECT'});continue
            if poi.get('point_basis')!='OSM_NODE':continue
            point=ogr.Geometry(ogr.wkbPoint);point.AddPoint_2D(poi['longitude'],poi['latitude'])
            owners=[bid for bid in spatial.query(poi['longitude'],poi['latitude']) if geometries[bid].Intersects(point)]
            for bid in owners:
                hits[bid].append({'id':poi['source_id'],'basis':'CONTAINED_POI' if len(owners)==1 and geometries[bid].Contains(point) else 'AMBIGUOUS_BOUNDARY_OR_OVERLAP'})
    residential={'house','detached','semidetached_house','terrace','residential','bungalow','apartments','dormitory'}
    for f in features:
        p=f['properties'];tags=p['osm_tags'];kind=tags.get('building')
        nonres=use_tags(tags)
        p['poi_use_evidence']=hits[f['id']]
        p['use_policy_version']='osm_poi_use_v2'
        if nonres and kind in residential:
            p['class']='mixed_use_review';p['subclass']='mixed_use_review'
            p['use_review_reason']='MIXED_USE_REVIEW:'+','.join(nonres)
        elif nonres and kind=='yes':
            p['subclass']='non_residential_poi';p['use_review_reason']='NON_RESIDENTIAL_OSM_TAG:'+','.join(nonres)
        elif hits[f['id']] and kind in residential|{'yes'}:
            p['class']='mixed_use_review';p['subclass']='poi_use_review'
            p['use_review_reason']='POI_INSIDE_OR_BOUNDARY_REVIEW_NO_FLOOR_ALLOCATION'
        elif kind=='yes' and not facility_evidence:
            p['subclass']='unknown_use_review';p['use_review_reason']='POI_CHECK_UNAVAILABLE'
        elif kind=='yes':
            p['use_review_reason']='N1_NULL_USE_ASSUMPTION_AFTER_POI_CHECK_NOT_CONFIRMED_RESIDENTIAL'

def normalize_source(raw):
    if raw.get('provider')=='OPENSTREETMAP':return normalize_osm(raw)
    from location_intelligent_overture_probe import normalize
    return normalize(raw)

def acquire_osm(config,output,as_of):
    from location_intelligent_map_pilot import query_bbox
    bbox=query_bbox(config['latitude'],config['longitude'],config['building_radius_m']+config['building_query_padding_m'])
    w,s,e,n=bbox;region=f'({s},{w},{n},{e})'
    date_clause=f'[date:"{as_of}"]' if as_of else ''
    query=f'[out:json][timeout:60][maxsize:33554432]{date_clause};(way["building"]["building"!="no"]{region};relation["type"="multipolygon"]["building"]["building"!="no"]{region};node["amenity"]{region};node["shop"]{region};node["office"]{region};node["healthcare"]{region};node["tourism"]{region};);out meta geom;'
    result=acquire_overpass(query,config['poi_overpass_endpoints'],60,33554432)
    if result['status']!='SUCCEEDED':
        write_json(Path(str(output)+'.failed.json'),result);raise RuntimeError('OSM building acquisition failed')
    payload=deepcopy(result['payload'])
    use_nodes=[e for e in payload['elements'] if e['type']=='node']
    payload['elements']=[e for e in payload['elements'] if e['type'] in {'way','relation'} and e.get('tags',{}).get('building') not in {None,'no'}]
    raw={'provider':'OPENSTREETMAP','release':as_of or result['payload']['osm3s']['timestamp_osm_base'],'schema_version':SCHEMA,'bbox':bbox,'query':query,
         'payload':payload,'use_poi_nodes':use_nodes,'attempts':result['attempts'],'acquired_at':utc(),'truncated':False,
         'bounded_query_complete':True,'source_as_of':as_of or result['payload']['osm3s']['timestamp_osm_base']}
    write_json(output,raw,exclusive=True);return raw

def prepare_osm_from_network(config,root,network_source,raw_path):
    """New source job, same frozen OSM roads/restrictions and N1 rules."""
    import shutil,subprocess,sys,hashlib
    from location_intelligent_map_pilot import normalize_cache,sha
    from location_intelligent_validator import canonical_hash
    root=Path(root);network_source=Path(network_source)
    source_policy=read_json(network_source/'config/pilot.json')['policy']['li3']
    if any(source_policy[k]!=config[k] for k in ['latitude','longitude','metric_crs']):
        raise ValueError('OSM network seed belongs to another target/CRS')
    if source_policy['network_bbox_radius_m']!=config['network_radius_m']:
        raise ValueError('OSM network seed extent differs from request')
    root.mkdir(parents=True,exist_ok=False)
    write_json(root/'requested_config.json',config)
    raw=read_json(raw_path)
    raw['parent_raw_sha256']=sha(raw_path)
    raw['use_policy_version']=config.get('osm_use_policy_version','legacy_v1')
    if raw['use_policy_version']=='osm_poi_use_v2':
        poi_path=config.get('osm_poi_snapshot_path')
        evidence=read_json(poi_path) if poi_path else None
        if evidence and (evidence['request_binding']['latitude']!=config['latitude'] or evidence['request_binding']['longitude']!=config['longitude']):
            raise ValueError('POI evidence belongs to another target')
        raw['facility_evidence']=evidence
    write_json(root/'osm_buildings_raw.json.gz',raw)
    write_json(root/'normalization_config.json',config)
    from location_intelligent_li3_sources import timed_call
    result=timed_call('normalization',subprocess.run,[config.get('core_python','/usr/bin/python3'),'-B',str(Path(__file__).with_name('location_intelligent_map_pilot.py')),'normalize',str(root/'osm_buildings_raw.json.gz'),str(root/'raw/building_cache'),str(root/'normalization_config.json')],capture_output=True,text=True)
    if result.returncode:raise RuntimeError('OSM normalization failed: '+result.stderr[-1500:])
    for p in (network_source/'raw').glob('osm_*.json.gz'):
        shutil.copyfile(p,root/'raw'/p.name)
    frozen=read_json(network_source/'config/pilot.json')
    frozen.update(analysis_run_id=root.name,frozen_at=read_json(raw_path)['acquired_at'],source_scope='OSM buildings + OSM roads/barriers; user target',
        building_cache_files={'raw/building_cache/'+p.name:sha(p) for p in sorted((root/'raw/building_cache').iterdir()) if p.is_file()})
    frozen['policy']['sources']['buildings'].update(provider='OPENSTREETMAP',planned_release=read_json(raw_path)['release'],planned_schema_version=SCHEMA,status='ACTUAL_FROZEN_OSM')
    frozen['policy']['li3']['building_cache']=str(root/'raw/building_cache')
    frozen['policy']['li3']['feature_source_mode']=config.get('network_feature_mode','FULL')
    road_profile=config.get('road_rule_profile','STRICT_MOTOR_LEGACY')
    if road_profile not in {'STRICT_MOTOR_LEGACY','BARRIER_ONEWAY_EXPERIMENT_V1'}:raise ValueError('Unknown road rule profile')
    if road_profile=='BARRIER_ONEWAY_EXPERIMENT_V1':
        frozen['policy']['li3']['road_rule_profile']=road_profile
        frozen['policy']['motorcycle_access'].update(private_access_usable=True,pedestrian_only_usable=True,stairs_usable=True)
        frozen['policy']['scenario_limitations']=['Access tags and turn restrictions ignored by owner experiment; not legal/physical access verification',
            'Only extracted road graph is available; omitted paths are not fabricated',
            'Remaining UNKNOWN edges are not usable for acceptance']

    profile=config.get('building_entrance_profile','MULTI_ACCESS_LEGACY')
    if profile not in {'MULTI_ACCESS_LEGACY','SINGLE_HIGHEST_CLASS_NEAREST_V1'}:raise ValueError('Unknown building entrance profile')
    if profile=='SINGLE_HIGHEST_CLASS_NEAREST_V1':
        frozen['policy']['connectors'].update(building_entrance_profile=profile,
            candidate_selection='HIGHEST_VALID_CLASS_THEN_NEAREST_REPRESENTATIVE_POINT_THEN_SEGMENT_ID',
            unreachable_higher_class='NO_ROUTE_NO_ENTRANCE_FALLBACK')

    frozen.pop('config_hash',None);frozen['config_hash']=canonical_hash(frozen)
    road_stamp=read_json(root/'raw/osm_roads.json.gz')['payload']['osm3s'].get('timestamp_osm_base')
    frozen['building_network_timestamp_warning']={'buildings_as_of':read_json(raw_path)['source_as_of'],'roads_as_of':road_stamp} if road_stamp!=read_json(raw_path)['source_as_of'] else None
    frozen.pop('config_hash',None);frozen['config_hash']=canonical_hash(frozen)
    write_json(root/'config/pilot.json',frozen)


class EnvelopePointIndex:
    """Conservative envelope grid; exact OGR predicates still decide ownership.

    No Shapely dependency in the separate GDAL worker. Query preserves original
    footprint order, including overlaps, holes and boundary-touching candidates.
    """
    def __init__(self, records):
        self.records=list(records);self.cells={}
        if not self.records:return
        bounds=[e for _,e in self.records]
        self.x0=min(e[0] for e in bounds);self.x1=max(e[1] for e in bounds)
        self.y0=min(e[2] for e in bounds);self.y1=max(e[3] for e in bounds)
        self.n=max(1,min(128,math.ceil(math.sqrt(len(bounds)))))
        self.dx=max(self.x1-self.x0,1e-12)/self.n
        self.dy=max(self.y1-self.y0,1e-12)/self.n
        for i,(_,e) in enumerate(self.records):
            a,b=self.cell(e[0],e[2]);c,d=self.cell(e[1],e[3])
            for x in range(a,c+1):
                for y in range(b,d+1):self.cells.setdefault((x,y),[]).append(i)
    def cell(self,x,y):
        return (max(0,min(self.n-1,math.floor((x-self.x0)/self.dx))),
                max(0,min(self.n-1,math.floor((y-self.y0)/self.dy))))
    def query(self,x,y):
        if not self.records or x<self.x0 or x>self.x1 or y<self.y0 or y>self.y1:return []
        return [self.records[i][0] for i in self.cells.get(self.cell(x,y),[])
                if self.records[i][1][0]<=x<=self.records[i][1][1]
                and self.records[i][1][2]<=y<=self.records[i][1][3]]


def cached_normalization(raw, path, *, write=True):
    """Content-bound normalization only; never cache selection/routing decisions.

    Raw includes consumed use-policy, local POI and optional facility evidence.
    Historical packets without a receipt remain readable using full validation.
    """
    import hashlib,json,platform
    from osgeo import gdal
    from location_intelligent_validator import canonical_hash
    path=Path(path)
    code_files=[Path(__file__)]
    if raw.get('provider')!='OPENSTREETMAP':
        code_files.append(Path(__file__).with_name('location_intelligent_overture_probe.py'))
    binding={'raw':canonical_hash(raw),'code':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in code_files},
             'python':platform.python_version(),'gdal':gdal.VersionInfo('RELEASE_NAME'),
             'gdal_build':gdal.VersionInfo('BUILD_INFO')}
    if path.exists():
        receipt=read_json(path)
        payload=receipt['payload']
        if receipt.get('schema')!='normalization_cache_v1' or receipt['payload_sha256']!=canonical_hash(payload):
            raise ValueError('Corrupt normalization cache')
        if receipt['binding']==binding:
            print('Normalization cache: HIT',flush=True)
            return payload['features'],payload['diagnostics']
    print('Normalization cache: MISS — exact normalization',flush=True)
    if raw.get('provider')=='OPENSTREETMAP':features,diagnostics=normalize_osm(raw,with_diagnostics=True)
    else:features,diagnostics=normalize_source(raw),None
    if write:
        payload={'features':features,'diagnostics':diagnostics}
        receipt={'schema':'normalization_cache_v1','binding':binding,'payload':payload,'payload_sha256':canonical_hash(payload)}
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.partial');write_json(tmp,receipt);tmp.replace(path)
    return features,diagnostics
