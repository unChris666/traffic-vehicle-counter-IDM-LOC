"""Versioned live-ingestion adapter; frozen extracted kernel remains unchanged.

Derived from PBF_LOCAL_V1 materialize. Fixes way/bbox segment intersection and
records bounded diagnostics before an empty-road failure. No provider fallback.
"""
from pathlib import Path
from copy import deepcopy
import json,subprocess
from collections import Counter
from .._kernel.location_intelligent_li3_sources import read_json,write_json,utc
from .._kernel.location_intelligent_pbf_sources import matches,read_extract,recover_legacy_packet,validate_road_provenance

READER_VERSION='PBF_LOCAL_SEGMENT_BBOX_V2'

class PbfSourceError(RuntimeError):
    def __init__(self,code,report):
        self.code=code
        super().__init__(code+': '+json.dumps(report,sort_keys=True))


def segment_intersects_bbox(a,b,box):
    """Inclusive rectangular clipping in the source WGS84 lon/lat coordinates."""
    west,south,east,north=box;x,y=a['lon'],a['lat']
    dx=b['lon']-x;dy=b['lat']-y;lo,hi=0.,1.
    for p,q in ((-dx,x-west),(dx,east-x),(-dy,y-south),(dy,north-y)):
        if p==0:
            if q<0:return False
        else:
            value=q/p
            if p<0:lo=max(lo,value)
            else:hi=min(hi,value)
            if lo>hi:return False
    return True


def way_intersects_bbox(way,nodes,box):
    points=[]
    for node_id in way['nodes']:
        if node_id not in nodes:raise RuntimeError('PBF_MISSING_WAY_NODE: '+str(way['id']))
        points.append(nodes[node_id])
    west,south,east,north=box
    if any(west<=n['lon']<=east and south<=n['lat']<=north for n in points):return True
    return any(segment_intersects_bbox(a,b,box) for a,b in zip(points,points[1:]))

def materialize(config, folder, pbf, osmium_binary, pbf_ref):
    import osmium
    from pyproj import Transformer
    from traffic_location.location.area._kernel.location_intelligent_config import get_config
    from traffic_location.location.area._kernel.location_intelligent_validator import canonical_hash
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import build_queries
    from traffic_location.location.area._kernel.location_intelligent_map_pilot import query_bbox, sha
    from traffic_location.location.area._kernel.location_intelligent_map_poi import normalize_pois
    from traffic_location.location.area._kernel.location_intelligent_market_runtime import source_request_config, verify_market_source_packet
    root = Path(folder)
    if (root / 'source_manifest.json').exists():
        return recover_legacy_packet(root, config, pbf_ref)
    if config['network_feature_mode'] != 'ROADS_ONLY_EXPERIMENT':
        raise RuntimeError('PBF_FULL_FEATURE_PROFILE_NOT_VALIDATED')
    root.mkdir(parents=True, exist_ok=True)
    network = root / 'network_roads_only'

    def emit(path, value, **kwargs):
        path = Path(path)
        if path.exists():
            if read_json(path) != value:
                raise RuntimeError('PBF_DRAFT_CONTENT_CHANGED: ' + path.name)
            return
        temp = path.with_name(path.stem + '.partial' + path.suffix)
        write_json(temp, value)
        temp.replace(path)
    policy = get_config()
    policy['li3'].update(latitude=config['latitude'], longitude=config['longitude'], metric_crs=config['metric_crs'], network_bbox_radius_m=config['network_radius_m'])
    tx = Transformer.from_crs(4326, config['metric_crs'], always_xy=True)
    inv = Transformer.from_crs(config['metric_crs'], 4326, always_xy=True)
    x, y = tx.transform(config['longitude'], config['latitude'])
    r = config['network_radius_m']
    corners = [inv.transform(a, b) for a in (x - r, x + r) for b in (y - r, y + r)]
    road_box = [min((a for a, b in corners)), min((b for a, b in corners)), max((a for a, b in corners)), max((b for a, b in corners))]
    building_box = query_bbox(config['latitude'], config['longitude'], config['building_radius_m'] + config['building_query_padding_m'])
    poi_box = query_bbox(config['latitude'], config['longitude'], config['poi_radius_m'] + 100)
    box = [min((b[0] for b in [road_box, building_box, poi_box])), min((b[1] for b in [road_box, building_box, poi_box])), max((b[2] for b in [road_box, building_box, poi_box])), max((b[3] for b in [road_box, building_box, poi_box]))]
    with osmium.io.Reader(str(pbf)) as reader:
        header = reader.header()
        stamp = header.get('osmosis_replication_timestamp')
        if not stamp:
            raise RuntimeError('PBF_HEADER_SNAPSHOT_TIMESTAMP_MISSING')
        b = header.box()
        boxes = [(b.bottom_left.lon, b.bottom_left.lat, b.top_right.lon, b.top_right.lat)] if b.valid() else []
    if not boxes or not any((b[0] <= box[0] and b[1] <= box[1] and (b[2] >= box[2]) and (b[3] >= box[3]) for b in boxes)):
        raise RuntimeError('REQUEST_OUTSIDE_PBF_HEADER_COVERAGE')
    local = root / 'local_extract.osm.pbf'
    receipt = local.with_suffix('.receipt.json')
    if not local.exists():
        tmp = local.with_name('local_extract.partial.osm.pbf')
        print('PBF: local extraction START; native CPU scan, no Overpass', flush=True)
        subprocess.run([str(osmium_binary), 'extract', '--bbox', ','.join(map(str, box)), '--strategy', 'smart', '--overwrite', '--output', str(tmp), str(pbf)], check=True)
        tmp.replace(local)
        emit(receipt, {'sha256': sha(local), 'pbf_sha256': pbf_ref['sha256'], 'bbox': box})
    if not receipt.exists() or read_json(receipt) != {'sha256': sha(local), 'pbf_sha256': pbf_ref['sha256'], 'bbox': box}:
        raise RuntimeError('PBF_LOCAL_EXTRACT_CHANGED')
    nodes, ways, relations = read_extract(local)

    def inside(n, b):
        return b[0] <= n['lon'] <= b[2] and b[1] <= n['lat'] <= b[3]

    def geometry(w):
        missing = [i for i in w['nodes'] if i not in nodes]
        if missing:
            raise RuntimeError('PBF_MISSING_WAY_NODE: ' + str(w['id']))
        return [{'lon': nodes[i]['lon'], 'lat': nodes[i]['lat']} for i in w['nodes']]

    def intersects(w, b):
        return way_intersects_bbox(w,nodes,b)
    filters = build_queries(road_box, policy)['filters']
    eligible=[w for w in ways.values() if matches(w['tags'],filters)]
    roads = [w for w in eligible if intersects(w, road_box)]
    highways=[w for w in ways.values() if w['tags'].get('highway')]
    report={'schema_version':'pbf_source_diagnostics_v1','reader_version':READER_VERSION,
            'target':{'latitude':config['latitude'],'longitude':config['longitude']},
            'metric_crs':config['metric_crs'],'road_bbox_wgs84':road_box,'extract_bbox_wgs84':box,
            'nodes':len(nodes),'ways':len(ways),'relations':len(relations),
            'node_extent_wgs84':([min(n['lon'] for n in nodes.values()),min(n['lat'] for n in nodes.values()),max(n['lon'] for n in nodes.values()),max(n['lat'] for n in nodes.values())] if nodes else None),
            'highway_ways':len(highways),'filter_eligible_ways':len(eligible),'selected_road_ways':len(roads),
            'highway_types':dict(Counter(w['tags']['highway'] for w in highways).most_common(30)),
            'status':'READY' if roads else 'NO_ROADS',
            'cause':None if roads else 'EXTRACT_EMPTY' if not nodes and not ways else 'NO_HIGHWAY_WAYS' if not highways else 'ACCESS_FILTER_EXCLUDED_ALL' if not eligible else 'NO_ELIGIBLE_GEOMETRY_IN_BBOX'}
    write_json(root/'pbf-source-diagnostics.json',report)
    print('PBF_SOURCE_DIAGNOSTICS='+json.dumps(report,sort_keys=True),flush=True)
    if not roads:raise PbfSourceError('PBF_NO_ROADS_IN_REQUESTED_EXTENT',report)
    wanted = {i for w in roads for i in w['nodes']}
    for w in roads:
        geometry(w)
    payload = {'elements': sorted([*roads, *[nodes[i] for i in wanted]], key=lambda e: (e['type'], e['id'])), 'osm3s': {'timestamp_osm_base': stamp}, 'generator': 'PBF_LOCAL_V1'}
    buildings = [{**w, 'geometry': geometry(w)} for w in ways.values() if w['tags'].get('building') not in {None, 'no'} and intersects(w, building_box)]
    for relation in relations.values():
        if relation['tags'].get('type') != 'multipolygon' or relation['tags'].get('building') in {None, 'no'}:
            continue
        members = [ways.get(m['ref']) for m in relation['members'] if m['type'] == 'way']
        if not any((w and intersects(w, building_box) for w in members)):
            continue
        row = deepcopy(relation)
        for member in row['members']:
            if member['type'] == 'way':
                if member['ref'] not in ways:
                    raise RuntimeError('PBF_MULTIPOLYGON_MEMBER_MISSING')
                member['geometry'] = geometry(ways[member['ref']])
        buildings.append(row)
    pois = []
    from traffic_location.location.area._kernel.location_intelligent_map_poi import classify_poi
    for entry in [*nodes.values(), *ways.values(), *relations.values()]:
        if not classify_poi(entry['tags'], market=True):
            continue
        row = deepcopy(entry)
        if entry['type'] != 'node':
            coordinates = []
            if entry['type'] == 'way':
                coordinates = geometry(entry)
            else:
                for m in entry['members']:
                    if m['type'] == 'way' and m['ref'] in ways:
                        coordinates.extend(geometry(ways[m['ref']]))
                    elif m['type'] == 'node' and m['ref'] in nodes:
                        coordinates.append(nodes[m['ref']])
            if coordinates:
                row['center'] = {'lon': (min((n['lon'] for n in coordinates)) + max((n['lon'] for n in coordinates))) / 2, 'lat': (min((n['lat'] for n in coordinates)) + max((n['lat'] for n in coordinates))) / 2}
        pois.append(row)
    layer = normalize_pois(config, {'elements': pois, 'osm3s': {'timestamp_osm_base': stamp}})
    layer.update(provider='OPENSTREETMAP_GCS_PBF', raw_payload={'elements': pois, 'osm3s': {'timestamp_osm_base': stamp}}, source_profile='PBF_LOCAL_V1_CENTERS_FROM_SMART_EXTRACT', attempts=[])
    emit(root / 'optional_poi_result.json', layer)
    emit(root / 'optional_poi_result.receipt.json', {'sha256': sha(root / 'optional_poi_result.json')})
    raw = {'provider': 'OPENSTREETMAP', 'schema_version': 'osm_buildings_adapter_v1', 'release': stamp, 'source_as_of': stamp, 'bbox': building_box, 'payload': {'elements': buildings, 'osm3s': {'timestamp_osm_base': stamp}}, 'use_poi_nodes': [n for n in nodes.values() if inside(n, building_box)], 'attempts': [], 'acquired_at': read_json(root / 'osm_buildings_raw.json.gz')['acquired_at'] if (root / 'osm_buildings_raw.json.gz').exists() else utc(), 'truncated': False, 'bounded_query_complete': True, 'source_profile': 'PBF_LOCAL_V1'}
    emit(root / 'osm_buildings_raw.json.gz', raw)
    network.mkdir(exist_ok=True)
    frozen = {'schema_version': 'li3_pilot_config_v1', 'algorithm_version': 'LI3_V1', 'analysis_run_id': network.name, 'frozen_at': raw['acquired_at'], 'policy': policy, 'target_xy': [x, y], 'reference_metric_bbox': [x - r, y - r, x + r, y + r], 'extraction_bbox_wgs84': road_box, 'diagnostic_gap_m': 10.0, 'building_cache_files': {}, 'source_scope': 'GCS_PBF_LOCAL_V1', 'pbf_input': pbf_ref}
    frozen['config_hash'] = canonical_hash(frozen)
    emit(network / 'config/pilot.json', frozen)
    roads_raw = {'status': 'SUCCEEDED', 'payload': payload, 'provider': 'GCS_PBF', 'pbf_input': pbf_ref}
    emit(network / 'raw/osm_roads.json.gz', roads_raw)
    emit(network / 'raw/osm_features_roads_only.json.gz', {'status': 'SUCCEEDED', 'payload': payload, 'coverage': 'ROAD_EXTRACT_ONLY_EXTERNAL_FEATURES_NOT_REQUESTED', 'external_features_requested': False, 'source_roads_sha256': sha(network / 'raw/osm_roads.json.gz')}, exclusive=True)
    validate_road_provenance(root)
    emit(network / 'network_manifest.json', {'config': source_request_config(config), 'files': {str(p.relative_to(network)): sha(p) for p in network.rglob('*') if p.is_file() and p.name != 'network_manifest.json'}}, exclusive=True)
    emit(root / 'pbf_source.json', {'input': pbf_ref, 'reader_version': READER_VERSION, 'header_timestamp': stamp, 'profile': 'PBF_LOCAL_V1', 'extract_sha256': sha(local), 'extract_bbox': box, 'nodes': len(nodes), 'ways': len(ways), 'relations': len(relations), 'limits': ['New snapshot/source profile; no exact parity claim against older Overpass data', 'Header bounding box is a coarse coverage check, not a verified Indonesia boundary polygon', 'POI inventory bounded by complete-way/multipolygon extract, not complete real-world inventory']}, exclusive=True)
    emit(root / 'source_manifest.json', {'config': source_request_config(config), 'files': {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}}, exclusive=True)
    verify_market_source_packet(root, config)
    print('GCS PBF source finalized:', root, flush=True)
    return root
