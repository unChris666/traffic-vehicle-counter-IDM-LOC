"""Private national PMTiles on GCS -> self-contained bounded notebook basemap."""
import base64, gzip, hashlib, json, math
from urllib.parse import quote
VECTORGRID_URL = 'https://unpkg.com/leaflet.vectorgrid@1.3.0/dist/Leaflet.VectorGrid.bundled.js'
BUCKET = 'feeder-location-intelligent'

class GcsRangeReader:

    def __init__(self, session, ref):
        self.session = session
        self.ref = ref
        self.cache = {}
        self.requests = 0

    def __call__(self, offset, length):
        key = (offset, length)
        if key in self.cache:
            return self.cache[key]
        if length <= 0 or length > 32 * 1024 * 1024 or offset < 0 or (offset + length > self.ref['bytes']):
            raise RuntimeError('BASEMAP_RANGE_INVALID')
        url = 'https://storage.googleapis.com/download/storage/v1/b/' + BUCKET + '/o/' + quote(self.ref['object'], safe='')
        with self.session.get(url, params={'alt': 'media', 'generation': str(self.ref['generation'])}, headers={'Range': f'bytes={offset}-{offset + length - 1}', 'Accept-Encoding': 'identity'}, stream=True, timeout=(30, 90)) as response:
            if response.status_code >= 400:
                raise RuntimeError('GCS_BASEMAP_HTTP_' + str(response.status_code))
            response.raise_for_status()
            if response.status_code != 206 or response.headers.get('Content-Range') != f"bytes {offset}-{offset + length - 1}/{self.ref['bytes']}":
                raise RuntimeError('BASEMAP_GCS_RANGE_RESPONSE_INVALID')
            actual = response.headers.get('x-goog-generation')
            if actual is not None and actual != str(self.ref['generation']):
                raise RuntimeError('BASEMAP_GENERATION_CHANGED')
            data = response.content
        if len(data) != length:
            raise RuntimeError('BASEMAP_SHORT_READ')
        self.cache[key] = data
        self.requests += 1
        return data

def tile_coordinates(box, zoom):
    west, south, east, north = box
    n = 2 ** zoom

    def x(lon):
        return min(n - 1, max(0, int((lon + 180) / 360 * n)))

    def y(lat):
        lat = max(-85.05112878, min(85.05112878, lat))
        r = math.radians(lat)
        return min(n - 1, max(0, int((1 - math.asinh(math.tan(r)) / math.pi) / 2 * n)))
    return [(zoom, a, b) for a in range(x(west), x(east) + 1) for b in range(y(north), y(south) + 1)]

def load_tiles(session, ref, box):
    from pmtiles.reader import Reader
    from pmtiles.tile import TileType, Compression
    if ref.get('status') != 'READY' or ref.get('schema') != 'indonesia_basemap_v1':
        raise RuntimeError('GCS_NATIONAL_BASEMAP_NOT_READY')
    read = GcsRangeReader(session, ref)
    reader = Reader(read)
    header = reader.header()
    metadata = reader.metadata()
    if header['tile_type'] != TileType.MVT or header['max_zoom'] != ref['maxzoom'] or header['addressed_tiles_count'] != ref['tiles']:
        raise RuntimeError('BASEMAP_HEADER_MANIFEST_MISMATCH')
    bounds = [header[k] / 10000000.0 for k in ['min_lon_e7', 'min_lat_e7', 'max_lon_e7', 'max_lat_e7']]
    if bounds != ref['bounds']:
        raise RuntimeError('BASEMAP_BOUNDS_MISMATCH')
    if not (bounds[0] <= box[0] <= box[2] <= bounds[2] and bounds[1] <= box[1] <= box[3] <= bounds[3]):
        raise RuntimeError('BASEMAP_VIEW_OUTSIDE_ARCHIVE')
    layers = {row['id'] for row in metadata.get('vector_layers', [])}
    if layers != set(ref['layers']):
        raise RuntimeError('BASEMAP_LAYER_MANIFEST_MISMATCH')
    if header['tile_compression'] not in {Compression.GZIP, Compression.NONE}:
        raise RuntimeError('BASEMAP_COMPRESSION_UNSUPPORTED')
    tiles = {}
    checked = 0
    for z in range(header['min_zoom'], header['max_zoom'] + 1):
        for coord in tile_coordinates(box, z):
            checked += 1
            if checked > 4096:
                raise RuntimeError('BASEMAP_NOTEBOOK_VIEW_TOO_LARGE')
            data = reader.get(*coord)
            if data:
                if header['tile_compression'] == Compression.GZIP:
                    data = gzip.decompress(data)
                tiles['/'.join(map(str, coord))] = base64.b64encode(data).decode()
    return (tiles, {'requested_tiles': checked, 'nonempty_tiles': len(tiles), 'gcs_range_requests': read.requests, 'view_bbox': box, 'archive': ref, 'transport': 'GCS_GENERATION_PINNED_RANGE_HTTPS'})

def basemap_layer(tiles, maxzoom):
    import folium
    from branca.element import Template

    class LocalVectorBasemap(folium.map.Layer):

        def __init__(self):
            super().__init__(name='Basemap OSM Indonesia — GCS', overlay=False, control=True, show=True)
            self.tiles = json.dumps(tiles)
            self.maxzoom = maxzoom
            self._template = Template("{% macro script(this, kwargs) %}\nvar tiles_{{this.get_name()}}={{this.tiles | safe}};\n{{this._parent.get_name()}}.createPane('gcsBasemap');\n{{this._parent.get_name()}}.getPane('gcsBasemap').style.zIndex=190;\nvar {{this.get_name()}}=L.vectorGrid.protobuf('',{\n pane:'gcsBasemap',rendererFactory:L.canvas.tile,maxNativeZoom:{{this.maxzoom}},maxZoom:20,minZoom:0,\n attribution:'© OpenStreetMap contributors, ODbL',interactive:true,\n vectorTileLayerStyles:{\n  landuse:{weight:0,fill:true,fillColor:'#dce7d0',fillOpacity:0.65},\n  water:{weight:0,fill:true,fillColor:'#a9d4eb',fillOpacity:1},\n  waterways:{color:'#88bddc',weight:1.2},coastline:{color:'#69a6cb',weight:1},\n  boundaries:{color:'#ad9cac',weight:1,dashArray:'4 3'},\n  buildings:{color:'#9ea4a5',weight:0.5,fill:true,fillColor:'#c5c9c8',fillOpacity:0.9},\n  roads:function(p,z){var k=p.class||'';return {color:/^(motorway|trunk)/.test(k)?'#eab477':/^(primary|secondary)/.test(k)?'#f1ce66':/^tertiary/.test(k)?'#f5e8b9':'#fafafa',weight:/^(motorway|trunk|primary|secondary)/.test(k)?3:1.4,opacity:1};},\n  places:{radius:3,color:'#555',fill:true,fillColor:'#555',fillOpacity:1},\n  pois:{radius:2,color:'#97778b',fill:true,fillColor:'#97778b',fillOpacity:0.8}\n }});\nvar decode_{{this.get_name()}}={{this.get_name()}}._getVectorTilePromise;\n{{this.get_name()}}._getVectorTilePromise=function(c){\n var data=tiles_{{this.get_name()}}[c.z+'/'+c.x+'/'+c.y];\n if(!data)return Promise.resolve({layers:{}});\n var request=Object.create(this);request._url='data:application/x-protobuf;base64,'+data;\n return decode_{{this.get_name()}}.call(request,c).then(function(tile){\n  var order=['landuse','water','coastline','boundaries','waterways','buildings','roads','places','pois'],layers={};\n  order.forEach(function(name){if(tile.layers[name])layers[name]=tile.layers[name];});tile.layers=layers;return tile;\n });\n};\n{{this.get_name()}}.on('click',function(e){\n var p=e.layer.properties||{};if(p.name||p.class){var label=document.createElement('span');label.textContent=p.name||p.class;L.popup().setLatLng(e.latlng).setContent(label).openOn({{this._parent.get_name()}});}\n});\n{{this.get_name()}}.on('load',function(){document.body.dataset.basemapLoaded='true';});\n{{this.get_name()}}.on('tileerror',function(){document.body.dataset.basemapError='true';});\n{{this.get_name()}}.addTo({{this._parent.get_name()}});\n{% endmacro %}")
    return LocalVectorBasemap()
