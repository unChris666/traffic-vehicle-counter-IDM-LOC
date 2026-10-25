"""Render only stored market decisions; map styling never changes ownership."""
from pathlib import Path
import hashlib
import json
from html import escape
from traffic_location.location.area._kernel.location_intelligent_li3_sources import read_json, write_json, canonical_bytes

def market_map(config, market_config, pilot, facilities, result, output):
    import folium
    from folium.plugins import MarkerCluster, Fullscreen
    from pyproj import Transformer
    from shapely.geometry import shape, Point, LineString, mapping
    from shapely.ops import transform
    from traffic_location.location.area._kernel.location_intelligent_map_pilot import sha, road_display_style, query_bbox
    from traffic_location.location.area._kernel.location_intelligent_map_poi import add_poi_layers
    from traffic_location.location.area._kernel.location_intelligent_market import reconcile
    pilot = Path(pilot)
    output = Path(output)
    if result['identity']['pilot'] != sha(pilot / 'manifest.json') or result['identity']['config'] != config or result['identity']['market_config'] != market_config:
        raise ValueError('Market map and calculation inputs differ')
    if result['identity']['facilities'] != hashlib.sha256(canonical_bytes(facilities)).hexdigest():
        raise ValueError('POI snapshot changed after market calculation')
    if reconcile(result['rows']) != result['summary']:
        raise ValueError('Map totals do not reconcile')
    normalized = read_json(pilot / 'normalized/buildings.geojson')
    graph = read_json(pilot / 'graph/graph.json.gz')
    display = market_config['display']
    lat, lon = (config['latitude'], config['longitude'])
    m = folium.Map(location=[lat, lon], zoom_start=15, tiles='OpenStreetMap', prefer_canvas=True)
    target = folium.FeatureGroup(name='Calon toko — pin putih', show=True)
    folium.CircleMarker([lat, lon], radius=8, color=display['candidate_pin_outline_color'], weight=2, fill=True, fill_color=display['candidate_pin_color'], fill_opacity=1, tooltip='Calon toko').add_to(target)
    target.add_to(m)
    for ring in display['candidate_rings']:
        group = folium.FeatureGroup(name=f"Calon — radius {ring['radius_m']:g} m", show=True)
        folium.Circle([lat, lon], radius=ring['radius_m'], color=ring['color'], fill=False, weight=2).add_to(group)
        group.add_to(m)
    store_groups = {}
    rings = {}
    labels = {'PRIMARY': 'Kompetitor primer', 'SECONDARY': 'Kompetitor sekunder', 'UNVERIFIED_CORRIDOR': 'Kompetitor — koridor belum terverifikasi', 'INDOMARET': 'Indomaret'}
    for tier, label in labels.items():
        store_groups[tier] = MarkerCluster(name=label + ' — pin', show=True).add_to(m)
        rings[tier] = folium.FeatureGroup(name=label + ' — radius', show=True).add_to(m)
    for store in result['stores']:
        if store['kind'] == 'candidate':
            continue
        tier = store['tier']
        color = 'blue' if tier == 'INDOMARET' else 'red'
        pos = [store['latitude'], store['longitude']]
        name = store['name']
        popup = '<br>'.join([escape(name), escape(store['store_key']), escape(tier), f"Jarak calon: {store['distance_to_candidate_m']:.1f} m", escape(', '.join(store['corridor_tokens']) or 'Koridor unknown'), 'Radius visual bukan bukti akses; area eksklusif terpisah dari pengaruh Huff'])
        folium.Marker(pos, tooltip=escape(labels[tier] + ': ' + name), popup=folium.Popup(popup, max_width=420), icon=folium.Icon(color=color, icon='shopping-cart')).add_to(store_groups[tier])
        radius = store['display_radius_m']
        if radius:
            style = display['indomaret'] if tier == 'INDOMARET' else display['competitor_primary'] if tier == 'PRIMARY' else display['competitor_secondary']
            folium.Circle(pos, radius=radius, color=style['ring_color'], fill=False, weight=1.5, tooltip=escape(name) + f' — radius {radius:g} m').add_to(rings[tier])
    forward = Transformer.from_crs(4326, config['metric_crs'], always_xy=True)
    inverse = Transformer.from_crs(config['metric_crs'], 4326, always_xy=True)
    rows = {r['building_id']: r for r in result['rows']}
    names = {s['store_key']: s['name'] for s in result['stores']}
    features = []
    for f in normalized['features']:
        bid = f['properties']['building_id']
        row = rows.get(bid)
        if row is None:
            raise ValueError('Missing market row for source footprint')
        status = row['market_status']
        area = row['area_m2']
        if area is None:
            area = transform(forward.transform, shape(f['geometry'])).area
        scores = [{'toko': names[s['store_key']], 'skor_estimasi': round(s['huff_score'], 6), 'jarak_rute_m': round(s['total_distance_m'], 2)} for s in row['scores']]
        reason = row['reason'] + ' | akses: ' + row['access_status']
        if result.get('network_feature_mode') == 'ROADS_ONLY_EXPERIMENT':
            reason += ' | ROAD_GRAPH_ONLY: external barrier/turn checks skipped'
        if scores:
            reason += ' | Huff: ' + json.dumps(scores, ensure_ascii=False)
        if row.get('use_review_reason'):
            reason += ' | ' + row['use_review_reason']
        features.append({'type': 'Feature', 'geometry': f['geometry'], 'properties': {'ID': bid, 'AREA': round(area, 2), 'Status': status, 'Reason': escape(reason), 'Alternatif': escape(json.dumps([names[s['store_key']] for s in sorted(row['scores'], key=lambda s: (s['total_distance_m'], s.get('store_road_rank', 99), s['store_key']))], ensure_ascii=False)), 'winner_store_key': row['winner_store_key'], 'candidate_count': row['count_candidate'], 'color': display['building_colors'].get(status.lower(), display['building_colors']['others'])}})
    group = folium.FeatureGroup(name='Building footprint — alokasi market eksperimen', show=True)
    if features:
        folium.GeoJson({'type': 'FeatureCollection', 'features': features}, style_function=lambda f: {'color': f['properties']['color'], 'fillColor': f['properties']['color'], 'weight': 0.6, 'fillOpacity': 0.5}, tooltip=folium.GeoJsonTooltip(fields=['ID', 'AREA', 'Status', 'Reason', 'Alternatif']), popup=folium.GeoJsonPopup(fields=['ID', 'AREA', 'Status', 'Reason', 'Alternatif'])).add_to(group)
    group.add_to(m)
    xy = forward.transform(lon, lat)
    disk = Point(*xy).buffer(config['poi_radius_m'], quad_segs=64)
    roads = []
    seen = set()
    for e in graph['edges']:
        g = e.get('geometry')
        if not g:
            continue
        line = LineString(g['coordinates'])
        key = (line.wkb, e.get('highway'))
        if key in seen:
            continue
        seen.add(key)
        clipped = line.intersection(disk)
        if clipped.is_empty or clipped.geom_type not in {'LineString', 'MultiLineString'}:
            continue
        roads.append({'type': 'Feature', 'geometry': mapping(transform(inverse.transform, clipped)), 'properties': {'highway': e.get('highway'), 'motor_access': str(e.get('access_allowed'))}})
    network = folium.FeatureGroup(name='Network OSM — tipe jalan', show=True)
    if roads:
        folium.GeoJson({'type': 'FeatureCollection', 'features': roads}, style_function=lambda f: road_display_style(f['properties']['highway']), tooltip=folium.GeoJsonTooltip(fields=['highway', 'motor_access'])).add_to(network)
    network.add_to(m)
    add_poi_layers(m, config, facilities)
    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen().add_to(m)
    west, south, east, north = query_bbox(lat, lon, config['poi_radius_m'] + 100)
    m.fit_bounds([[south, west], [north, east]])
    output.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output))
    write_json(output.with_suffix('.geojson'), {'type': 'FeatureCollection', 'features': features}, exclusive=True)
    return m

def render_market(config, market_config, pilot, facilities, result):
    """Immutable presentation cache; reopen verifies HTML/GeoJSON, never recalculates."""
    from traffic_location.location.area._kernel.location_intelligent_map_pilot import sha
    if result['identity']['config'] != config or result['identity']['market_config'] != market_config or result['identity']['pilot'] != sha(Path(pilot) / 'manifest.json'):
        raise ValueError('Presentation inputs differ from market result')
    if result['identity']['facilities'] != hashlib.sha256(canonical_bytes(facilities)).hexdigest():
        raise ValueError('Presentation POI source differs from market result')
    if read_json(Path(result['output_path']) / 'result.json') != result:
        raise ValueError('Market result differs from retained artifact')
    identity = {'result_sha256': sha(Path(result['output_path']) / 'result.json'), 'renderer_sha256': sha(__file__)}
    version = hashlib.sha256(canonical_bytes(identity)).hexdigest()
    root = Path(result['output_path']) / 'views' / version
    manifest = root / 'view_manifest.json'
    if manifest.exists():
        saved = read_json(manifest)
        if saved['identity'] != identity:
            raise ValueError('Presentation identity changed')
        for name, digest in saved['files'].items():
            if sha(root / name) != digest:
                raise ValueError('Saved market presentation changed')
    else:
        if root.exists():
            raise ValueError('Incomplete presentation; inspect before rerendering')
        market_map(config, market_config, pilot, facilities, result, root / 'market_map.html')
        write_json(manifest, {'identity': identity, 'files': {n: sha(root / n) for n in ['market_map.html', 'market_map.geojson']}}, exclusive=True)
    return root / 'market_map.html'
