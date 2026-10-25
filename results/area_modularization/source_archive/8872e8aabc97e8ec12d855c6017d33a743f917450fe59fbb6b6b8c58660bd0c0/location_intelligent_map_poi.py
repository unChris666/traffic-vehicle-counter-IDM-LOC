"""OSM facility snapshot and display-only layers; no Area counting changes."""
from pathlib import Path
import hashlib
import math

from location_intelligent_li3_sources import canonical_bytes, read_json, write_json, acquire_overpass


POI_CATEGORIES = {
    'hospital': ('Rumah sakit', 'red', 'plus-square'),
    'clinic': ('Klinik', 'pink', 'medkit'),
    'market': ('Pasar', 'orange', 'shopping-basket'),
    'police': ('Kantor polisi', 'darkblue', 'shield'),
    'school': ('Sekolah', 'green', 'graduation-cap'),
    'government': ('Kantor pemerintahan', 'purple', 'university'),
    'office': ('Kantor', 'cadetblue', 'briefcase'),
    'university': ('Universitas', 'darkpurple', 'graduation-cap'),
    'station': ('Stasiun', 'black', 'train'),
    'recreation': ('Rekreasi / taman', 'lightgreen', 'tree'),
    'bank': ('Bank', 'darkred', 'bank'),
    'restaurant': ('Restoran', 'beige', 'cutlery'),
    'mall': ('Mall / pusat perbelanjaan', 'lightblue', 'shopping-bag'),
}
POI_RULE_VERSION = 'osm_facilities_eight_categories_v1'


def categories_for(config):
    return POI_CATEGORIES if config.get('poi_profile') == 'market_attractors_v2' else {
        k: v for k, v in POI_CATEGORIES.items() if k not in {'station','recreation','bank','restaurant','mall'}}


def classify_poi(tags, *, market=False):
    """One primary category per OSM feature; positive tags, not building shape."""
    amenity = tags.get('amenity', '').strip().lower()
    healthcare = tags.get('healthcare', '').strip().lower()
    office = tags.get('office', '').strip().lower()
    if market:
        if tags.get('railway') == 'station' or tags.get('public_transport') == 'station':
            return 'station'
        if tags.get('leisure') in {'park', 'garden', 'recreation_ground', 'theme_park'} or tags.get('tourism') in {'theme_park', 'zoo'}:
            return 'recreation'
        if amenity == 'bank':
            return 'bank'
        if amenity == 'restaurant':
            return 'restaurant'
        if tags.get('shop') in {'mall', 'shopping_centre'}:
            return 'mall'
    if amenity == 'hospital' or healthcare == 'hospital':
        return 'hospital'
    if amenity == 'clinic' or healthcare == 'clinic':
        return 'clinic'
    if amenity == 'marketplace':
        return 'market'
    if amenity == 'police':
        return 'police'
    if amenity == 'school':
        return 'school'
    if amenity == 'university':
        return 'university'
    if office == 'government' or amenity == 'townhall':
        return 'government'
    if office and office not in {'no', 'vacant', 'disused', 'abandoned'}:
        return 'office'
    return None


def poi_binding(config):
    return {'latitude': config['latitude'], 'longitude': config['longitude'],
            'radius_m': config['poi_radius_m'], 'rules': 'osm_market_attractors_v2' if config.get('poi_profile') == 'market_attractors_v2' else POI_RULE_VERSION}


def build_poi_query(config):
    """Small buffer for acquisition; final WGS84 geodesic test stays <=2km."""
    lat, lon = config['latitude'], config['longitude']
    if not all(math.isfinite(v) for v in [lat, lon]) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid target coordinates')
    radius = float(config['poi_radius_m']) + 100.0
    region = f'(around:{radius},{lat},{lon})'
    extra = ''
    if config.get('poi_profile') == 'market_attractors_v2':
        extra = (f'nwr["railway"="station"]{region};nwr["public_transport"="station"]{region};'
                 f'nwr["leisure"~"^(park|garden|recreation_ground|theme_park)$"]{region};'
                 f'nwr["tourism"~"^(theme_park|zoo)$"]{region};'
                 f'nwr["amenity"~"^(bank|restaurant)$"]{region};'
                 f'nwr["shop"~"^(mall|shopping_centre)$"]{region};')
    return ('[out:json][timeout:45][maxsize:16777216];('
            f'nwr["amenity"~"^(hospital|clinic|marketplace|police|school|university|townhall)$"]{region};'
            f'nwr["healthcare"~"^(hospital|clinic)$"]{region};'
            f'nwr["office"]{region};{extra});out body center;')


def normalize_pois(config, payload):
    from pyproj import Geod
    geod = Geod(ellps='WGS84')
    rows, excluded, seen = [], [], set()
    elements = payload.get('elements')
    if payload.get('remark') or not isinstance(elements, list) or not isinstance(payload.get('osm3s'), dict):
        raise ValueError('Incomplete OSM facility response')
    for element in elements:
        key = f"{element['type']}/{element['id']}"
        if key in seen:
            raise ValueError('Duplicate OSM source identity in response')
        seen.add(key)
        tags = element.get('tags', {})
        category = classify_poi(tags, market=config.get('poi_profile') == 'market_attractors_v2')
        if category is None:
            excluded.append({'source_id': key, 'reason': 'NO_SUPPORTED_ACTIVE_FACILITY_TAG'})
            continue
        center = element if element['type'] == 'node' else element.get('center', {})
        lat, lon = center.get('lat'), center.get('lon')
        if not isinstance(lat, (float, int)) or not isinstance(lon, (float, int)) or not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            excluded.append({'source_id': key, 'reason': 'MISSING_OR_INVALID_REPRESENTATIVE_POINT'})
            continue
        distance = geod.inv(config['longitude'], config['latitude'], lon, lat)[2]
        if distance > config['poi_radius_m']:
            excluded.append({'source_id': key, 'reason': 'REPRESENTATIVE_POINT_OUTSIDE_RADIUS'})
            continue
        rows.append({'source_id': key, 'name': tags.get('name') or tags.get('name:id') or None,
                     'category': category, 'latitude': lat, 'longitude': lon, 'distance_m': distance,
                     'point_basis': 'OSM_NODE' if element['type'] == 'node' else 'OSM_BOUNDING_BOX_CENTER_NOT_ENTRANCE',
                     'tags': tags})
    rows.sort(key=lambda r: (r['category'], r['distance_m'], r['source_id']))
    return {'status': 'SUCCEEDED', 'provider': 'OPENSTREETMAP_OVERPASS', 'request_binding': poi_binding(config),
            'rows': rows, 'count': len(rows), 'counts_by_category': {
                key: sum(r['category'] == key for r in rows) for key in categories_for(config)},
            'source_elements': len(elements), 'excluded': excluded,
            'source_as_of': payload['osm3s'].get('timestamp_osm_base'),
            'completeness': 'OSM_TAGGED_FEATURES_NOT_COMPLETE_PHYSICAL_FACILITY_INVENTORY',
            'identity_policy': 'OSM_TYPE_AND_ID; NODE_WAY_RELATION_CAN_DESCRIBE_SAME_SITE_NOT_AUTO_MERGED'}


def load_osm_pois(config, cache, *, mode='FROZEN', frozen_input=None, expected_sha256=None):
    """Frozen normal; explicit acquisition caches complete responses immutably."""
    cache = Path(cache)
    if mode not in {'FROZEN', 'ACQUIRE_ONCE'}:
        raise ValueError('Unsupported POI mode')
    source = cache if cache.exists() else (Path(frozen_input) if frozen_input else None)
    if source is not None:
        raw = source.read_bytes()
        if expected_sha256 and hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('POI snapshot checksum differs')
        layer = read_json(source)
        if layer.get('request_binding') != poi_binding(config) or layer.get('status') != 'SUCCEEDED':
            raise ValueError('POI snapshot target/radius/rules differ')
        actual = normalize_pois(config, layer['raw_payload'])
        for field in ['rows', 'count', 'counts_by_category', 'source_elements', 'excluded']:
            if actual[field] != layer[field]:
                raise ValueError('POI normalized result differs from raw snapshot')
        if not cache.exists():
            write_json(cache, layer, exclusive=True)
        return layer
    if mode == 'FROZEN':
        return {'status': 'BLOCKED', 'provider': 'OPENSTREETMAP_OVERPASS', 'rows': None, 'count': None,
                'request_binding': poi_binding(config), 'error_type': 'FROZEN_POI_INPUT_MISSING'}
    query = build_poi_query(config)
    result = acquire_overpass(query, config['poi_overpass_endpoints'], 45, 16_777_216)
    if result['status'] != 'SUCCEEDED':
        return {'status': 'FAILED', 'provider': 'OPENSTREETMAP_OVERPASS', 'rows': None, 'count': None,
                'request_binding': poi_binding(config), 'attempts': result['attempts'],
                'error_type': 'OSM_FACILITY_RETRIEVAL_FAILED'}
    layer = normalize_pois(config, result['payload'])
    layer.update(raw_payload=result['payload'], query=query, attempts=result['attempts'])
    write_json(cache, layer, exclusive=True)
    return layer


def load_optional_osm_pois(config, folder, *, mode='ACQUIRE_ONCE'):
    """Freeze a successful inventory OR an unavailable observation, never fake zero.

    Reopen returns the same observation. Refresh requires a new source revision.
    """
    folder=Path(folder);path=folder/'optional_poi_result.json'
    receipt=folder/'optional_poi_result.receipt.json'
    if path.exists():
        if not receipt.exists() or read_json(receipt)['sha256']!=hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('Optional POI observation changed')
        saved=read_json(path)
        if saved.get('request_binding')!=poi_binding(config):raise ValueError('Optional POI target/rules changed')
        if saved['status']=='SUCCEEDED':
            actual=normalize_pois(config,saved['raw_payload'])
            if any(actual[k]!=saved[k] for k in ['rows','count','counts_by_category','source_elements','excluded']):
                raise ValueError('Optional POI source evidence changed')
        elif saved.get('rows') is not None or saved.get('count') is not None:
            raise ValueError('Unavailable POI observation must preserve unknowns')
        return saved
    try:
        layer=load_osm_pois(config,folder/'osm_poi_snapshot.data',mode=mode)
    except (OSError,ValueError) as error:
        layer={'status':'FAILED','provider':'OPENSTREETMAP_OVERPASS','rows':None,'count':None,
               'request_binding':poi_binding(config),'error_type':type(error).__name__}
    write_json(path,layer,exclusive=True)
    write_json(receipt,{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},exclusive=True)
    return layer


def add_poi_layers(map_object, config, layer):
    """Render only measured source positions; no fabricated zero on retrieval failure."""
    import folium
    from folium.plugins import MarkerCluster
    from html import escape
    if layer is None or layer.get('status') != 'SUCCEEDED':
        folium.FeatureGroup(name='POI — belum tersedia (input opsional)',show=False).add_to(map_object)
        return ['POI OSM: BELUM TERSEDIA']
    if layer['request_binding'] != poi_binding(config):
        raise ValueError('POI layer belongs to another target/radius/rules')
    counts = {key: 0 for key in categories_for(config)}
    groups = {}
    for key, (label, color, icon) in categories_for(config).items():
        groups[key] = MarkerCluster(name=f'POI {label} ≤{config["poi_radius_m"]:g} m', show=True).add_to(map_object)
    for row in layer['rows']:
        if not math.isfinite(row['distance_m']) or not 0 <= row['distance_m'] <= config['poi_radius_m']:
            raise ValueError('Out-of-radius facility cannot enter map')
        label, color, icon = POI_CATEGORIES[row['category']]
        name = row['name'] or '(tanpa nama di OSM)'
        popup = '<br>'.join([escape(label), escape(name), escape(row['source_id']),
                            f"Jarak {row['distance_m']:.1f} m", escape(row['point_basis']), 'Sumber: OpenStreetMap'])
        folium.Marker([row['latitude'], row['longitude']], tooltip=escape(label + ': ' + name),
                      popup=folium.Popup(popup, max_width=400),
                      icon=folium.Icon(color=color, icon=icon, prefix='fa')).add_to(groups[row['category']])
        counts[row['category']] += 1
    return ['POI OSM: ' + str(len(layer['rows'])) + ' fitur bertag dalam2km (bukan inventori lengkap)']
