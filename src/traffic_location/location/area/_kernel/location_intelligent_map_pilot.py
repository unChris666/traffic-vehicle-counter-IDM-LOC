"""Readable CPU notebook support: new-target sources, BQ layers and interactive map.

This is a scoped notebook prototype, not the approved implementation of the
Area modularization audit. Existing selection/routing algorithms stay unchanged.
"""
_NOTEBOOK_BQ_CREDENTIALS = None
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import subprocess
import sys
import re
from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json, write_json, canonical_bytes

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def query_bbox(latitude, longitude, radius_m):
    """Conservative bounding prefilter only; final predicates determine inclusion."""
    from pyproj import Geod
    geod = Geod(ellps='WGS84')
    positions = [geod.fwd(longitude, latitude, azimuth, radius_m)[:2] for azimuth in range(0, 360, 5)]
    return [min((p[0] for p in positions)), min((p[1] for p in positions)), max((p[0] for p in positions)), max((p[1] for p in positions))]

def acquire_buildings(config, output, *, extension_directory=None, partition_index=None):
    """Official pinned STAC items + bbox predicate + explicit nontruncated rows."""
    import requests
    import duckdb
    output = Path(output)
    if output.exists():
        raise ValueError('Raw building output immutable; choose a new source revision')
    release = config['overture_release']
    prefix = f'https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/release/{release}/theme=buildings/type=building/'
    url = f'https://stac.overturemaps.org/{release}/buildings/building/collection.json'
    bbox = query_bbox(config['latitude'], config['longitude'], config['building_radius_m'] + config['building_query_padding_m'])

    def metadata(url):
        response = requests.get(url, timeout=40)
        response.raise_for_status()
        if len(response.content) > 4000000:
            raise ValueError('STAC metadata exceeds bound')
        return (response.json(), hashlib.sha256(response.content).hexdigest())
    collection, catalog_hash = metadata(url)
    links = sorted({link['href'] for link in collection['links'] if link['rel'] == 'item'})
    if not links or len(links) > 2000:
        raise ValueError('Unexpected STAC item inventory')

    def fetch_item(link):
        item, checksum = metadata(link)
        return {'url': link, 'bbox': item['bbox'], 'asset': item['assets']['aws']['href'], 'sha256': checksum}
    if partition_index is not None:
        if sha(partition_index) != config['partition_index_sha256']:
            raise ValueError('Partition inventory checksum differs')
        inventory = read_json(partition_index)
        if inventory['release'] != release or inventory['errors'] or inventory['items_checked'] != len(inventory['items']):
            raise ValueError('Unverified partition inventory')
        if catalog_hash != config['partition_catalog_sha256'] or {r['url'] for r in inventory['items']} != set(links):
            raise ValueError('Pinned partition inventory/catalog differs')
        items = inventory['items']
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            items = list(pool.map(fetch_item, links))
    matching = [item for item in items if item['bbox'][0] <= bbox[2] and item['bbox'][2] >= bbox[0] and (item['bbox'][1] <= bbox[3]) and (item['bbox'][3] >= bbox[1])]
    if not matching or len(matching) > 8 or any((not item['asset'].startswith(prefix) for item in matching)):
        raise ValueError('Unsupported/incomplete partition selection')
    if partition_index is not None:
        for item in matching:
            current = fetch_item(item['url'])
            if current['asset'] != item['asset'] or current['bbox'] != item['bbox']:
                raise ValueError('Matching partition changed from verified inventory')
    assets = sorted({item['asset'] for item in matching})
    connection = duckdb.connect()
    try:
        if extension_directory:
            connection.execute('SET extension_directory=?', [str(extension_directory)])
        try:
            connection.execute('LOAD httpfs')
        except duckdb.Error:
            connection.execute('INSTALL httpfs')
            connection.execute('LOAD httpfs')
        for statement in ['SET enable_geoparquet_conversion=false', 'SET http_timeout=45', 'SET http_retries=1', 'SET threads=2', "SET memory_limit='1GB'"]:
            connection.execute(statement)
        schema = connection.execute('DESCRIBE SELECT * FROM read_parquet(?)', [assets]).fetchall()
        fields = {row[0]: row[1] for row in schema}
        expected = {'id': 'VARCHAR', 'class': 'VARCHAR', 'subtype': 'VARCHAR', 'geometry': 'BLOB', 'height': 'DOUBLE', 'num_floors': 'INTEGER', 'version': 'INTEGER'}
        if any((fields.get(k) != v for k, v in expected.items())) or not {'sources', 'bbox'} <= set(fields):
            raise ValueError('Overture consumed-column schema changed')
        query = 'SELECT id,class,subtype,height,num_floors,version,sources,bbox,hex(geometry) AS geometry_wkb_hex FROM read_parquet(?) WHERE bbox.xmin<=? AND bbox.xmax>=? AND bbox.ymin<=? AND bbox.ymax>=? ORDER BY id LIMIT ?'
        cursor = connection.execute(query, [assets, bbox[2], bbox[0], bbox[3], bbox[1], config['max_building_rows'] + 1])
        names = [item[0] for item in cursor.description]
        rows = [dict(zip(names, row)) for row in cursor.fetchall()]
        if len(rows) > config['max_building_rows']:
            raise ValueError('Building row cap reached; do not publish a truncated coverage result')
    finally:
        connection.close()
    value = {'release': release, 'schema_version': config['overture_schema'], 'collection_url': url, 'collection_sha256': catalog_hash, 'bbox': bbox, 'items': matching, 'items_checked': len(items), 'partition_inventory': items, 'physical_schema': schema, 'sql': query, 'row_cap': config['max_building_rows'], 'truncated': False, 'rows': rows, 'acquired_at': now(), 'bounded_query_complete': True, 'coverage_meaning': 'All intersecting advertised STAC items queried; not proof of physical building completeness'}
    write_json(output, value, exclusive=True)
    return value

def normalize_cache(raw_path, cache, config):
    """Runs under GDAL worker: same original WKB normalization and selection input."""
    from traffic_location.location.area._kernel.location_intelligent_validator import canonical_hash, context_hash
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=False)
    raw = read_json(raw_path)
    if raw['truncated'] or not raw['bounded_query_complete']:
        raise ValueError('Incomplete building input')
    from traffic_location.location.area._kernel.location_intelligent_osm_buildings import cached_normalization
    features, osm_diagnostics = cached_normalization(raw, cache / 'normalization_cache.json')
    write_json(cache / 'raw_probe.json.gz', raw)
    write_json(cache / 'buildings.geojson', features)
    stamp = raw['acquired_at']
    run_id = 'area-800m-' + hashlib.sha256(canonical_bytes(config)).hexdigest()[:12]
    context = {'schema_version': 'location_intelligent_v1', 'analysis_run_id': run_id, 'parent_analysis_run_id': None, 'created_at': stamp, 'target': {'store_code': None, 'store_name': None, 'latitude': config['latitude'], 'longitude': config['longitude'], 'crs': 'EPSG:4326', 'unknown_reasons': {'store_code': 'User supplied coordinates only', 'store_name': 'User supplied coordinates only'}}, 'config': {'version': config.get('selection_profile', 'area-map-800m-v1'), 'area_coverage': {'metric_crs': config['metric_crs'], 'parameters': {'building_radius_m': {'value': config['building_radius_m'], 'unit': 'm'}, 'min_area_m2': {'value': config['min_area_m2'], 'unit': 'm2'}, 'max_area_m2': {'value': config['max_area_m2'], 'unit': 'm2'}}, 'unresolved_decisions': []}}}
    context['context_hash'] = context_hash(context)
    is_osm = raw.get('provider') == 'OPENSTREETMAP'
    source = {'source_ref_id': 'osm-buildings-new-target' if is_osm else 'overture-buildings-new-target', 'inventory_id': 'SRC04', 'kind': 'LOCAL_FILE', 'provider': 'OPENSTREETMAP' if is_osm else 'OVERTURE_MAPS', 'locator': 'buildings.geojson', 'acquisition_mode': 'LIVE_ACQUIRED', 'availability': 'AVAILABLE', 'source_version': raw['release'] if is_osm else config['overture_release'], 'source_as_of': raw['source_as_of'] if is_osm else None, 'acquired_at': stamp, 'schema_version': 'li_building_snapshot_v1', 'fingerprint': {'algorithm': 'sha256', 'value': sha(cache / 'buildings.geojson')}, 'byte_count': (cache / 'buildings.geojson').stat().st_size, 'row_count': len(features['features']), 'coverage': {'scope': f"Bounded source query bbox={raw['bbox']}; not physical completeness", 'completeness': 'COMPLETE'}, 'crs': 'EPSG:4326', 'units': {'coordinates': 'degree'}, 'freshness': 'UNKNOWN', 'provenance': {'origin': 'LIVE_ACQUIRED', 'description': ('Actual frozen OSM tags/topology; ' if is_osm else 'Actual pinned Overture WKB; ') + 'raw SHA256=' + sha(raw_path), 'dependencies': []}, 'unknown_reasons': {} if is_osm else {'source_as_of': 'Provider release is known; individual observation dates vary'}}
    manifest = {'schema_version': 'location_intelligent_v1', 'analysis_run_id': run_id, 'context_hash': context['context_hash'], 'sources': [source], 'artifacts': [], 'modules': [{'module_run_id': 'area-selection-new-target', 'module': 'area_coverage', 'analysis_run_id': run_id, 'context_hash': context['context_hash'], 'config_hash': canonical_hash(context['config']), 'status': 'NOT_RUN', 'required_inputs': [source['source_ref_id']], 'artifact_refs': [], 'engine': None, 'started_at': None, 'finished_at': None, 'error': None}]}
    write_json(cache / 'context.json', context)
    write_json(cache / 'manifest.json', manifest)
    write_json(cache / 'report.json', {'bounded_query_complete': True, 'source_records': len(features['features']), 'raw_sha256': sha(raw_path), 'schema_validation_scope': 'Consumed columns/types and canonical geometry; not full official provider schema', 'osm_normalization': osm_diagnostics})

def prepare_pilot(config, root, *, core_python='/usr/bin/python3', extension_directory=None, partition_index=None):
    """Acquire a NEW target; never relabel or edit the old N1 snapshot."""
    from pyproj import Transformer
    from traffic_location.location.area._kernel.location_intelligent_config import get_config
    from traffic_location.location.area._kernel.location_intelligent_validator import canonical_hash
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import build_queries, acquire_overpass
    root = Path(root)
    if root.exists():
        raise ValueError('Pilot directory exists; use frozen mode or a new source revision')
    root.mkdir(parents=True)
    write_json(root / 'requested_config.json', config)
    raw = acquire_buildings(config, root / 'overture_raw.json.gz', extension_directory=extension_directory, partition_index=partition_index)
    cache = root / 'raw/building_cache'
    completed = subprocess.run([str(core_python), '-B', str(Path(__file__).resolve()), 'normalize', str(root / 'overture_raw.json.gz'), str(cache), str(root / 'requested_config.json')], capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError('GDAL normalization failed: ' + completed.stderr[-1400:])
    policy = get_config()
    policy['li3'].update(latitude=config['latitude'], longitude=config['longitude'], metric_crs=config['metric_crs'], building_cache=str(cache), network_bbox_radius_m=config['network_radius_m'], pilot_location_source='USER_COORDINATE_20261024')
    forward = Transformer.from_crs(4326, config['metric_crs'], always_xy=True)
    inverse = Transformer.from_crs(config['metric_crs'], 4326, always_xy=True)
    x, y = forward.transform(config['longitude'], config['latitude'])
    radius = config['network_radius_m']
    corners = [inverse.transform(a, b) for a in (x - radius, x + radius) for b in (y - radius, y + radius)]
    frozen = {'schema_version': 'li3_pilot_config_v1', 'algorithm_version': 'LI3_V1', 'analysis_run_id': root.name, 'frozen_at': raw['acquired_at'], 'policy': policy, 'target_xy': [x, y], 'extraction_bbox_wgs84': [min((p[0] for p in corners)), min((p[1] for p in corners)), max((p[0] for p in corners)), max((p[1] for p in corners))], 'reference_metric_bbox': [x - radius, y - radius, x + radius, y + radius], 'building_cache_files': {'raw/building_cache/' + p.name: sha(p) for p in sorted(cache.iterdir()) if p.is_file()}, 'target_snap_decision': 'OWNER_APPROVED_NEAREST_VALID_ROAD', 'source_scope': 'User target; building800m / POI2000m', 'core_python': str(core_python), 'diagnostic_gap_m': 10.0}
    frozen['config_hash'] = canonical_hash(frozen)
    write_json(root / 'config/pilot.json', frozen)
    queries = build_queries(frozen['extraction_bbox_wgs84'], policy)
    write_json(root / 'config/queries.json', queries)
    roads = acquire_overpass(queries['roads'], policy['li3']['overpass_endpoints'], policy['li3']['request_timeout_s'], policy['li3']['max_response_bytes'])
    roads['actual_query'] = queries['roads']
    write_json(root / 'raw/osm_roads.json.gz', roads)
    if roads['status'] != 'SUCCEEDED':
        raise RuntimeError('Road acquisition failed; inspect attempts, not a valid empty graph')
    stamp = roads['payload']['osm3s'].get('timestamp_osm_base')
    feature_query = queries['features'].replace(';', f'[date:"{stamp}"];', 1) if stamp else queries['features']
    features = acquire_overpass(feature_query, policy['li3']['overpass_endpoints'], policy['li3']['request_timeout_s'], policy['li3']['max_response_bytes'])
    features['actual_query'] = feature_query
    write_json(root / 'raw/osm_features_pinned.json.gz', features)
    if features['status'] != 'SUCCEEDED':
        features = acquire_overpass(queries['features'], policy['li3']['overpass_endpoints'], policy['li3']['request_timeout_s'], policy['li3']['max_response_bytes'])
        features['actual_query'] = queries['features']
        write_json(root / 'raw/osm_features.json.gz', features)
    if features['status'] != 'SUCCEEDED':
        raise RuntimeError('Barrier/restriction acquisition failed; cannot assume clear access')
    return frozen

def bq_credentials(secret_name='LocatioIntelligent'):
    """No secret is displayed, written to output, or embedded in the notebook."""
    if globals().get('_NOTEBOOK_BQ_CREDENTIALS') is not None:
        return _NOTEBOOK_BQ_CREDENTIALS
    import google.auth
    try:
        from kaggle_secrets import UserSecretsClient
    except ImportError:
        return google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])[0]
    from google.oauth2 import service_account
    user_secrets = UserSecretsClient()
    secret_value_0 = user_secrets.get_secret(secret_name)
    info = json.loads(secret_value_0)
    if not isinstance(info, dict) or info.get('type') != 'service_account':
        raise ValueError('Expected a service-account JSON object in the named Kaggle Secret')
    return service_account.Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/cloud-platform'])

def resolve_bq_fields(table, kind, overrides=None):
    """Schema-driven binding; aliases are proposals and every selection is recorded."""
    schema = {f.name.upper(): f for f in table.schema}

    def pick(aliases, required=False):
        found = next((schema[n.upper()] for n in aliases if n.upper() in schema), None)
        if required and found is None:
            raise ValueError('Required BigQuery coordinate columns not found')
        return None if found is None else {'name': found.name, 'type': found.field_type}
    cfg = overrides or {}
    if any((not isinstance(v, str) or not v.strip() for v in cfg.values())):
        raise ValueError('Nonempty field names required in overrides')
    if set(cfg) - {'latitude', 'longitude', 'point', 'id', 'name'}:
        raise ValueError('Unknown BigQuery schema override')
    if bool(cfg.get('latitude')) != bool(cfg.get('longitude')):
        raise ValueError('Both numeric coordinate overrides required')
    lat = pick([cfg['latitude']] if cfg.get('latitude') else ['LAT', 'LATITUDE'], required=bool(cfg.get('latitude')))
    lon = pick([cfg['longitude']] if cfg.get('longitude') else ['LONG', 'LON', 'LONGITUDE'], required=bool(cfg.get('longitude')))
    point = pick([cfg['point']] if cfg.get('point') else ['KOORDINAT', 'GEOGRAPHY', 'GEOMETRY'])
    if cfg.get('point'):
        point = pick([cfg['point']], required=True)
        lat = lon = None
    elif not cfg.get('latitude') and kind == 'indomaret' and (point is not None):
        lat = lon = None
    if not (lat and lon) and (not point or point['type'] not in {'STRING', 'GEOGRAPHY'}):
        raise ValueError('Unsupported coordinate schema; set BQ_SCHEMA_OVERRIDES explicitly')
    return {'latitude': lat, 'longitude': lon, 'point': point, 'id': pick([cfg['id']] if cfg.get('id') else ['KDTK', 'STORE_ID', 'KODE_TOKO', 'ID'], required=bool(cfg.get('id'))), 'name': pick([cfg['name']] if cfg.get('name') else ['NAMA_TOKO', 'NAMA', 'NAME', 'COMPETITOR', 'BRAND'], required=bool(cfg.get('name'))), 'table_kind': kind}

def build_bq_query(table_id, fields):
    if not re.fullmatch('[A-Za-z0-9_-]+\\.[A-Za-z0-9_]+\\.[A-Za-z0-9_]+', table_id):
        raise ValueError('Invalid table identifier')

    def column(field):
        if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', field['name']):
            raise ValueError('Unsupported field identifier')
        return '`' + field['name'] + '`'
    sid = 'CAST(' + column(fields['id']) + ' AS STRING)' if fields['id'] else 'CAST(NULL AS STRING)'
    name = 'CAST(' + column(fields['name']) + ' AS STRING)' if fields['name'] else 'CAST(NULL AS STRING)'
    if fields['latitude'] and fields['longitude']:
        coordinates = 'SAFE_CAST(' + column(fields['latitude']) + ' AS FLOAT64) AS latitude,SAFE_CAST(' + column(fields['longitude']) + ' AS FLOAT64) AS longitude'
        cte = f'raw AS (SELECT {sid} AS store_id,{name} AS store_name,{coordinates} FROM `{table_id}`)'
    else:
        p = column(fields['point'])
        point = p if fields['point']['type'] == 'GEOGRAPHY' else f'SAFE.ST_GEOGFROMTEXT({p})'
        cte = f'points AS (SELECT {sid} AS store_id,{name} AS store_name,{point} AS p FROM `{table_id}`), raw AS (SELECT store_id,store_name,SAFE.ST_Y(p) AS latitude,SAFE.ST_X(p) AS longitude FROM points)'
    return f'WITH {cte}, quality AS (SELECT COUNT(*) AS _source_rows,COUNTIF(latitude IS NULL OR longitude IS NULL OR NOT(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)) AS _invalid_coordinates FROM raw), valid AS (SELECT *,ST_DISTANCE(CASE WHEN latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180 THEN ST_GEOGPOINT(longitude,latitude) ELSE NULL END,ST_GEOGPOINT(@longitude,@latitude),TRUE) AS distance_m FROM raw WHERE latitude BETWEEN @south AND @north AND longitude BETWEEN @west AND @east AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180), matched AS (SELECT DISTINCT store_id,store_name,latitude,longitude,distance_m FROM valid WHERE distance_m<=@radius_m) SELECT matched.*,quality._source_rows,quality._invalid_coordinates FROM quality LEFT JOIN matched ON TRUE ORDER BY distance_m,store_id,store_name,latitude,longitude'

def query_bq_layer(config, table_id, kind, *, credentials=None, overrides=None):
    """Metadata → dry run → bounded read; errors are unavailable, never zero stores."""
    from google.cloud import bigquery
    client = bigquery.Client(project=config['bq_billing_project'], credentials=credentials)
    table = client.get_table(table_id, timeout=30)
    fields = resolve_bq_fields(table, kind, overrides)
    print('BQ VERIFIED SCHEMA BINDING', table_id, fields)
    sql = build_bq_query(table_id, fields)
    west, south, east, north = query_bbox(config['latitude'], config['longitude'], config['poi_radius_m'] + 100.0)
    params = [bigquery.ScalarQueryParameter(k, 'FLOAT64', v) for k, v in {'latitude': config['latitude'], 'longitude': config['longitude'], 'radius_m': config['poi_radius_m'], 'west': west, 'south': south, 'east': east, 'north': north}.items()]
    location = table.location
    dry = client.query(sql, location=location, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False, query_parameters=params))
    estimate = dry.total_bytes_processed
    print('BQ DRY RUN BYTES', table_id, estimate, 'budget', config['bq_maximum_bytes_billed'])
    if estimate is None or estimate > config['bq_maximum_bytes_billed']:
        raise ValueError('BigQuery dry-run byte budget exceeded/unknown; adjust budget explicitly')
    job = client.query(sql, location=location, job_config=bigquery.QueryJobConfig(query_parameters=params, maximum_bytes_billed=config['bq_maximum_bytes_billed'], use_query_cache=True))
    try:
        returned = [dict(r.items()) for r in job.result(timeout=120)]
    except BaseException:
        job.cancel()
        raise
    if not returned:
        raise ValueError('BigQuery quality row missing')
    quality = {'total_source_rows': returned[0]['_source_rows'], 'invalid_coordinates_global': returned[0]['_invalid_coordinates'], 'scope': 'Global parse quality; invalid coordinates cannot be assigned to a radius'}
    rows = []
    for record in returned:
        row = {k: v for k, v in record.items() if not k.startswith('_')}
        if row['latitude'] is None and row['longitude'] is None and (row['distance_m'] is None):
            continue
        rows.append(row)
    for row in rows:
        if not (math.isfinite(row['distance_m']) and 0 <= row['distance_m'] <= config['poi_radius_m']):
            raise ValueError('BigQuery radius binding differs')
    return {'status': 'SUCCEEDED', 'table': table_id, 'kind': kind, 'rows': rows, 'count_source_rows_distinct': len(rows), 'fields': fields, 'coordinate_quality': quality, 'quality': 'PARTIAL_INVALID_COORDINATES' if quality['invalid_coordinates_global'] else 'COMPLETE_QUERY_RESULT', 'table_schema': [{'name': f.name, 'type': f.field_type, 'mode': f.mode} for f in table.schema], 'table_modified': table.modified.isoformat() if table.modified else None, 'location': location, 'radius_m': config['poi_radius_m'], 'distance_method': 'BIGQUERY_ST_DISTANCE_WGS84_SPHEROID_TRUE', 'sql': sql, 'job_id': job.job_id, 'dry_run_bytes': estimate, 'billed_bytes': job.total_bytes_billed, 'acquired_at': now()}

def poi_locations(layer):
    """Collapse repeated history at the same exact ID/location; retain conflicts."""
    groups = {}
    by_id = {}
    for row in layer.get('rows', []):
        key = (row['store_id'], row['latitude'], row['longitude'])
        g = groups.setdefault(key, {'store_id': row['store_id'], 'latitude': row['latitude'], 'longitude': row['longitude'], 'distance_m': row['distance_m'], 'names': set(), 'source_rows': 0})
        if row.get('store_name'):
            g['names'].add(row['store_name'])
        g['source_rows'] += 1
        if row['store_id'] is not None:
            by_id.setdefault(row['store_id'], set()).add((row['latitude'], row['longitude']))
    result = []
    for key, g in groups.items():
        g['names'] = sorted(g['names'])
        g['identity_location_conflict'] = g['store_id'] is not None and len(by_id[g['store_id']]) > 1
        result.append(g)
    return sorted(result, key=lambda g: (g['distance_m'], str(g['store_id']), g['latitude'], g['longitude']))

def road_display_style(highway):
    """Readable road hierarchy; illustrative palette, not Google's proprietary style."""
    name = highway if isinstance(highway, str) else 'unknown'
    if name.endswith('_link'):
        name = name[:-5]
    palette = {'motorway': ('#e99a61', 4.5), 'trunk': ('#f0ad61', 4.2), 'primary': ('#f6bf43', 3.8), 'secondary': ('#f8d778', 3.2), 'tertiary': ('#f4e5b2', 2.6), 'unclassified': ('#ffffff', 2.0), 'residential': ('#ffffff', 2.0), 'living_street': ('#eef1f4', 1.8), 'service': ('#c7cdd4', 1.5), 'track': ('#a68b65', 1.2), 'path': ('#8d9d80', 1.0), 'footway': ('#8d9d80', 1.0), 'steps': ('#8d9d80', 1.0)}
    color, width = palette.get(name, ('#8b7ca8', 1.2))
    return {'color': color, 'weight': width, 'opacity': 1.0, 'dashArray': '4,4' if name in {'track', 'path', 'footway', 'steps'} else None}

def interactive_map(config, pilot, layers, output, *, facilities=None, alternatives=None):
    """Display-only Folium layers; no routing, capacity or source fetch here."""
    import folium
    from traffic_location.location.area._kernel.location_intelligent_li3_sources import canonical_bytes
    from folium.plugins import MarkerCluster, Fullscreen, MeasureControl
    from html import escape
    from shapely.geometry import LineString, mapping, Point
    from shapely.ops import transform
    from pyproj import Transformer
    pilot = Path(pilot)
    if alternatives and alternatives.get('status') == 'SUCCEEDED':
        identity = alternatives.get('identity', {})
        if identity.get('pilot') != sha(pilot / 'manifest.json'):
            raise ValueError('Alternative routes belong to another calculation snapshot')
        if identity.get('attributes') != config.get('store_attributes', {}):
            raise ValueError('Store attributes changed; recalculate alternatives')
        if identity.get('layer_hashes') != {k: hashlib.sha256(canonical_bytes(v)).hexdigest() for k, v in layers.items()}:
            raise ValueError('Store snapshot changed; recalculate alternatives')
    decisions = read_json(pilot / 'building_results/decisions.json.gz')
    selection = read_json(pilot / 'building_results/selection.json')
    buildings = read_json(pilot / 'normalized/buildings.geojson')
    graph = read_json(pilot / 'graph/graph.json.gz')
    report = read_json(pilot / 'report.json')
    frozen = read_json(pilot / 'config/pilot.json')['policy']['li3']
    context = read_json(pilot / 'normalized/context.json')
    if frozen['latitude'] != config['latitude'] or frozen['longitude'] != config['longitude'] or frozen['metric_crs'] != config['metric_crs']:
        raise ValueError('Map target/CRS differs from actual Area result')
    if context['config']['area_coverage']['parameters']['building_radius_m']['value'] != config['building_radius_m']:
        raise ValueError('Map radius differs from actual selection')
    if len(decisions) != report['source_records'] or len(selection['selected']) != report['selected_buildings']:
        raise ValueError('Map ledger/source denominator differs')
    by_id = {r['building_id']: r for r in decisions if r.get('building_id')}
    m = folium.Map(location=[config['latitude'], config['longitude']], zoom_start=15, tiles='OpenStreetMap', prefer_canvas=True)
    folium.Marker([config['latitude'], config['longitude']], tooltip='Target pengguna', popup='Koordinat pengguna; bukan ID toko hasil tebakan', icon=folium.Icon(color='red', icon='flag')).add_to(m)
    folium.Circle([config['latitude'], config['longitude']], radius=config['building_radius_m'], color='#2563eb', fill=False, tooltip=f"Seleksi bangunan {config['building_radius_m']:g} m").add_to(m)
    folium.Circle([config['latitude'], config['longitude']], radius=config['poi_radius_m'], color='#7c3aed', fill=False, tooltip=f"Radius toko/kompetitor {config['poi_radius_m']:g} m").add_to(m)
    selected_ids = {b['building_id'] for b in selection['selected']}
    selected_records = {b['building_id']: b for b in selection['selected']}
    excluded_metrics = {b.get('building_id'): b.get('metrics') or {} for b in selection.get('reject_ledger', [])}
    colors = {'ACCEPTED': '#16a34a', 'ACCESS_UNVERIFIED': '#f59e0b', 'NO_VALID_CONNECTOR': '#64748b', 'NO_ROUTE': '#dc2626', 'OVER_TIME_LIMIT': '#a855f7', 'EXCLUDED_BY_SELECTION': '#cbd5e1'}
    selected_group = folium.FeatureGroup(name=f"Bangunan terpilih {config['building_radius_m']:g} m — status skenario", show=True)
    excluded_group = folium.FeatureGroup(name='Footprint sumber di luar seleksi / excluded', show=True)
    selected_features = []
    excluded_features = []
    for feature in buildings['features']:
        bid = feature['properties']['building_id']
        row = by_id.get(bid, {})
        state = row.get('decision_state', 'UNKNOWN')
        props = feature['properties']
        measured = selected_records.get(bid) or excluded_metrics.get(bid, {})
        area = measured.get('area_m2')
        alt_rows = (alternatives or {}).get('by_building', {}).get(bid)
        alt_names = [r['name'] for r in alt_rows] if alt_rows is not None else None
        display_reason = row.get('reason') or 'UNKNOWN'
        if props.get('use_review_reason'):
            display_reason += ' | ' + props['use_review_reason']
        if alt_names is None:
            display_reason += ' | ALTERNATIVES_NOT_VERIFIED'
        elif not alt_names:
            display_reason += ' | NO_VERIFIED_ALTERNATIVE_IN_CONFIGURED_GRAPH'
        view = {'type': 'Feature', 'geometry': feature['geometry'], 'properties': {'building_id': bid, 'state': state, 'area_full_m2': round(area, 2) if area is not None else None, 'area_basis': 'Full footprint in ' + config['metric_crs'] + '; not clipped to circle', 'class_source': props.get('class') or 'UNKNOWN (source null)', 'subclass_source': props.get('subclass') or 'UNKNOWN (source null)', 'selection_status': row.get('selection_status'), 'reason': escape(display_reason), 'alternatives': escape(json.dumps(alt_names, ensure_ascii=False)) if alt_names is not None else 'Belum diverifikasi', 'connector_count': row.get('connector_count'), 'routing_note': '125m = search limit, not proof of road connectivity or a route to store', 'capacity_reference': row.get('capacity_reference_rounded'), 'capacity_unit': row.get('capacity_unit'), 'claim': 'Skenario; bukan akses fisik/legal terverifikasi'}}
        (selected_features if bid in selected_ids else excluded_features).append(view)
    for group, features in [(selected_group, selected_features), (excluded_group, excluded_features)]:
        if features:
            folium.GeoJson({'type': 'FeatureCollection', 'features': features}, style_function=lambda f: {'fillColor': colors.get(f['properties']['state'], '#ef4444'), 'color': colors.get(f['properties']['state'], '#ef4444'), 'weight': 0.6, 'fillOpacity': 0.45}, tooltip=folium.GeoJsonTooltip(fields=['building_id', 'area_full_m2', 'state', 'reason', 'alternatives'], aliases=['ID', 'AREA (m²)', 'Status', 'Reason', 'Alternatif'], max_width=440), popup=folium.GeoJsonPopup(fields=['building_id', 'area_full_m2', 'state', 'reason', 'alternatives'], aliases=['ID', 'AREA (m²)', 'Status', 'Reason', 'Alternatif'])).add_to(group)
    selected_group.add_to(m)
    excluded_group.add_to(m)
    inverse = Transformer.from_crs(config['metric_crs'], 4326, always_xy=True)
    forward = Transformer.from_crs(4326, config['metric_crs'], always_xy=True)
    xy = forward.transform(config['longitude'], config['latitude'])
    display_disk = Point(*xy).buffer(config['poi_radius_m'], quad_segs=64)
    roads = []
    seen = set()
    for edge in graph['edges']:
        geom = edge.get('geometry')
        if not geom:
            continue
        line = LineString(geom['coordinates'])
        key = (line.wkb, edge.get('highway'))
        if key in seen:
            continue
        seen.add(key)
        clipped = line.intersection(display_disk)
        if clipped.is_empty or clipped.geom_type not in {'LineString', 'MultiLineString'}:
            continue
        roads.append({'type': 'Feature', 'geometry': mapping(transform(inverse.transform, clipped)), 'properties': {'edge_id': edge['edge_id'], 'highway': edge.get('highway'), 'motor_access': 'UNKNOWN' if edge.get('access_allowed') is None else 'ALLOWED' if edge['access_allowed'] else 'DENIED', 'claim': 'OSM graph; class color does not authorize motor access'}})
    if roads:
        road_group = folium.FeatureGroup(name=f"Network OSM — tampilan {config['poi_radius_m']:g} m", show=True)
        collection = {'type': 'FeatureCollection', 'features': roads}
        folium.GeoJson(collection, style_function=lambda f: {'color': '#727b85', 'weight': road_display_style(f['properties']['highway'])['weight'] + 1.3, 'opacity': 0.8}, interactive=False).add_to(road_group)
        folium.GeoJson(collection, style_function=lambda f: road_display_style(f['properties']['highway']), tooltip=folium.GeoJsonTooltip(fields=['highway', 'motor_access', 'edge_id'])).add_to(road_group)
        road_group.add_to(m)
    from traffic_location.location.area._kernel.location_intelligent_map_poi import add_poi_layers
    statuses = add_poi_layers(m, config, facilities) if facilities is not None else []
    for kind, title, color in [('indomaret', 'Indomaret', 'blue'), ('competitor', 'Kompetitor', 'orange')]:
        layer = layers[kind]
        if layer['status'] == 'SUCCEEDED':
            request = layer.get('request_binding', {})
            if request.get('latitude') != config['latitude'] or request.get('longitude') != config['longitude'] or request.get('radius_m') != config['poi_radius_m']:
                raise ValueError('POI snapshot belongs to a different target/radius')
            if any((not math.isfinite(r['distance_m']) or not 0 <= r['distance_m'] <= config['poi_radius_m'] for r in layer['rows'])):
                raise ValueError('Out-of-radius POI cannot enter map')
        locations = poi_locations(layer) if layer['status'] == 'SUCCEEDED' else None
        group = MarkerCluster(name=title + f" ≤{config['poi_radius_m']:g}m" + (' — BELUM TERSEDIA' if locations is None else ''), show=True)
        radius = float(config.get('store_buffer_radius_m', 400.0))
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError('Store display buffer radius must be positive and finite')
        buffers = folium.FeatureGroup(name=title + f' — radius {radius:g} m per toko' + (' — BELUM TERSEDIA' if locations is None else ''), show=True)
        for row in locations or []:
            popup = '<br>'.join([escape(title), escape(str(row['store_id'])), escape(' / '.join(row['names'])), f"Jarak {row['distance_m']:.1f} m", 'KONFLIK ID/lokasi' if row['identity_location_conflict'] else '', escape(layer['table'])])
            folium.Marker([row['latitude'], row['longitude']], tooltip=escape(title + ': ' + (' / '.join(row['names']) or str(row['store_id']))), popup=folium.Popup(popup, max_width=400), icon=folium.Icon(color=color, icon='shopping-cart')).add_to(group)
            folium.Circle([row['latitude'], row['longitude']], radius=radius, color='#2563eb' if kind == 'indomaret' else '#f97316', weight=1, fill=True, fill_opacity=0.045, tooltip=escape(title + ' ' + str(row['store_id'])) + f' — radius {radius:g} m (bukan routing)').add_to(buffers)
        group.add_to(m)
        buffers.add_to(m)
        statuses.append(f'{title}: ' + ('BELUM TERSEDIA — ' + escape(layer.get('error_type', 'UNKNOWN')) if locations is None else str(len(locations)) + ' lokasi marker' + (' — ada koordinat sumber invalid' if layer.get('coordinate_quality', {}).get('invalid_coordinates_global') else '')))
    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen().add_to(m)
    MeasureControl().add_to(m)
    west, south, east, north = query_bbox(config['latitude'], config['longitude'], config['poi_radius_m'] + 100)
    m.fit_bounds([[south, west], [north, east]])
    m.save(str(output))
    return m

def safe_error_diagnostics(error):
    """Exception classes/HTTP status only; never serialize messages, URLs or values."""
    chain = []
    seen = set()
    while error is not None and id(error) not in seen and (len(chain) < 5):
        seen.add(id(error))
        item = {'type': type(error).__name__}
        status = getattr(error, 'code', None)
        if not isinstance(status, int):
            status = getattr(getattr(error, 'response', None), 'status_code', None)
        if isinstance(status, int) and 100 <= status <= 599:
            item['http_status'] = status
        chain.append(item)
        error = error.__cause__ or error.__context__
    return {'chain': chain}

def load_bq_layers(config, cache, *, secret_name='LocatioIntelligent', refresh=False, overrides=None):
    """A successful cached result can reopen without credentials or a new query."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    definitions = config.get('bq_tables', {'indomaret': 'locdeproject.DWH_NS_LOC.AREA_COVERAGE', 'competitor': 'locdeproject.DWH_NS_LOC.COMPETITOR'})
    result = {}
    credentials = None
    credential_error = None
    credential_diagnostics = None
    for kind, table in definitions.items():
        path = cache / (kind + '.json')
        binding = {'latitude': config['latitude'], 'longitude': config['longitude'], 'radius_m': config['poi_radius_m'], 'table': table, 'overrides': (overrides or {}).get(kind, {})}
        fingerprint = hashlib.sha256(canonical_bytes(binding)).hexdigest()
        if path.exists() and (not refresh):
            layer = read_json(path)
            if layer.get('request_fingerprint') != fingerprint or layer.get('status') != 'SUCCEEDED':
                raise ValueError('BigQuery cache differs; use a new explicit source revision')
            result[kind] = layer
            continue
        if path.exists() and refresh:
            raise ValueError('REFRESH requires a new cache directory before querying')
        try:
            if credentials is None:
                if credential_error:
                    raise RuntimeError(credential_error)
                try:
                    credentials = bq_credentials(secret_name)
                except Exception as error:
                    credential_error = type(error).__name__
                    credential_diagnostics = safe_error_diagnostics(error)
                    raise
            layer = query_bq_layer(config, table, kind, credentials=credentials, overrides=(overrides or {}).get(kind))
            layer['request_fingerprint'] = fingerprint
            layer['request_binding'] = binding
            if path.exists():
                raise ValueError('REFRESH requires a new cache directory; finalized query result is immutable')
            write_json(path, layer, exclusive=True)
            result[kind] = layer
        except Exception as error:
            result[kind] = {'status': 'BLOCKED' if credentials is None else 'FAILED', 'kind': kind, 'table': table, 'rows': None, 'count_source_rows_distinct': None, 'error_type': credential_error or type(error).__name__, 'error_stage': 'KAGGLE_SECRET_READ' if credentials is None else 'BIGQUERY_METADATA_OR_QUERY', 'error_diagnostics': credential_diagnostics or safe_error_diagnostics(error), 'radius_m': config['poi_radius_m'], 'request_fingerprint': fingerprint, 'next_action': 'Enable Kaggle Secret and verify BigQuery read/job permissions; rerun BQ/map cells'}
    return result
if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == 'normalize':
        normalize_cache(sys.argv[2], sys.argv[3], read_json(sys.argv[4]))
    else:
        raise SystemExit('This helper is executed by the visible notebook cells')
