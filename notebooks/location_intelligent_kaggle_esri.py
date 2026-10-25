"""Development setup, Esri presentation, and immutable result publication.

No selection, connector, routing, capacity or market policy lives here.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from location_intelligent_google_only import BUCKET, PBF, sha

PACKAGES = ['osmnx==2.1.1', 'geopandas==1.2.0', 'folium==0.20.0',
            'osmium==4.3.2', 'google-cloud-bigquery==3.46.2',
            'google-cloud-storage==3.6.0', 'google-crc32c==1.7.1',
            'cupy-cuda12x==13.6.0', 'fastrlock==0.8.3']
ESRI = {
    'imagery': ('Esri World Imagery', 'World_Imagery',
                'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'),
    'street': ('Esri World Street Map', 'World_Street_Map',
               'Tiles © Esri — Sources: Esri, HERE, Garmin, USGS, Intermap, and the GIS User Community'),
}


def setup_dependencies():
    """Only development setup may access pip/apt; never collect recursive debs."""
    missing = []
    for spec in PACKAGES:
        name, version = spec.split('==')
        try:
            present = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            present = None
        if present != version:
            missing.append(spec)
    if missing:
        print('Setup: install explicit development packages:', missing, flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                        '--retries', '2', '--timeout', '60', *missing], check=True, timeout=900)
    core = '/usr/bin/python3'
    probe = 'from osgeo import gdal;import pyproj;assert int(gdal.VersionInfo("VERSION_NUM"))>=3070000'
    ready = subprocess.run([core, '-c', probe], capture_output=True).returncode == 0
    if not ready or not shutil.which('osmium'):
        print('Setup: install GDAL/PyProj/osmium with apt dependency resolver', flush=True)
        subprocess.run(['apt-get', '-o', 'Acquire::Retries=2', '-o', 'Acquire::http::Timeout=60',
                        'update', '-qq'], check=True, timeout=300)
        subprocess.run(['apt-get', '-o', 'Acquire::Retries=2', '-o', 'Acquire::http::Timeout=60',
                        'install', '-y', '--no-install-recommends',
                        'python3-gdal', 'python3-pyproj', 'osmium-tool'], check=True, timeout=600,
                       env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})
    subprocess.run([core, '-c', probe], check=True, timeout=60)
    binary = shutil.which('osmium')
    if not binary:
        raise RuntimeError('OSMIUM_EXECUTABLE_MISSING')
    subprocess.run([binary, '--version'], check=True, timeout=30)
    # Check actual imports in a new process: metadata alone cannot detect ABI errors.
    subprocess.run([sys.executable, '-c',
        'import numpy,pandas,shapely,pyproj,osmnx,geopandas,folium,osmium,cupy;'
        'from google.cloud import bigquery,storage'], check=True, timeout=90)
    os.environ['PROJ_NETWORK'] = 'OFF'
    return core, binary


def connect_google():
    from kaggle_secrets import UserSecretsClient
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    from location_intelligent_google_only import install_google_only_guard
    try:
        info = json.loads(UserSecretsClient().get_secret('LocatioIntelligent'))
    except Exception:
        raise RuntimeError('KAGGLE_SECRET_UNAVAILABLE: activate LocatioIntelligent') from None
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/cloud-platform'])
    # Install only AFTER setup. Browser Esri/CDN requests are separate from Python.
    install_google_only_guard()
    return AuthorizedSession(credentials)


def render_esri(config, market_config, pilot, facilities, result, *, default='imagery'):
    import folium
    from branca.element import Element, MacroElement
    from jinja2 import Template
    from unittest.mock import patch
    from location_intelligent_market_map import market_map
    from location_intelligent_li3_sources import read_json, write_json, canonical_bytes
    if default not in ESRI:
        raise ValueError('UNKNOWN_ESRI_BASEMAP')
    artifact = Path(result['output_path']) / 'result.json'
    if read_json(artifact) != result:
        raise ValueError('Retained market result changed')
    identity = {'result_sha256': sha(artifact), 'renderer_sha256': sha(__file__),
                'basemap_default': default, 'basemaps': ESRI,
                'folium': importlib.metadata.version('folium'), 'online_basemap': True}
    # JSON normalization makes tuples equivalent after reopening stored JSON.
    identity = json.loads(canonical_bytes(identity))
    root = artifact.parent / 'views' / ('esri-' + hashlib.sha256(canonical_bytes(identity)).hexdigest())
    manifest = root / 'view_manifest.json'
    if manifest.exists():
        saved = read_json(manifest)
        if saved['identity'] != identity:
            raise RuntimeError('ESRI_VIEW_IDENTITY_CHANGED')
        for name, digest in saved['files'].items():
            if sha(root / name) != digest:
                raise RuntimeError('ESRI_VIEW_CHANGED')
        return root / 'market_map.html'
    if root.exists():
        raise RuntimeError('ESRI_VIEW_INCOMPLETE: inspect before retry')
    original = folium.Map.__init__
    def init(m, *args, **kwargs):
        kwargs['tiles'] = None
        original(m, *args, **kwargs)
        # No basemap is a real selectable fallback, not a fake analytical status.
        folium.TileLayer(tiles='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
                         name='Tanpa basemap', attr='Layer analitik © OpenStreetMap contributors, ODbL',
                         show=False).add_to(m)
        for key, (name, service, attribution) in ESRI.items():
            layer = folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/' + service + '/MapServer/tile/{z}/{y}/{x}',
                name=name, attr=attribution + ' | Analitik © OpenStreetMap contributors, ODbL',
                max_native_zoom=19, max_zoom=20, show=key == default).add_to(m)
            listener = MacroElement()
            listener._template = Template('{% macro script(this, kwargs) %}' +
                layer.get_name() + '.on("tileerror",function(){var n=document.getElementById("esri-status");'
                'if(n){n.textContent="Tile Esri tidak tersedia. Layer hasil tetap valid; pilih Tanpa basemap.";}});' + '{% endmacro %}')
            listener.add_to(m)
        m.get_root().html.add_child(Element('<div id="esri-status" role="status" style="position:fixed;bottom:25px;left:10px;z-index:9999;background:white;font-size:11px;padding:3px">Basemap Esri online; layer analitik OSM tersimpan.</div>'))
    with patch.object(folium.Map, '__init__', init):
        market_map(config, market_config, pilot, facilities, result, root / 'market_map.html')
    write_json(manifest, {'identity': identity, 'files': {
        name: sha(root / name) for name in ['market_map.html', 'market_map.geojson']}}, exclusive=True)
    return root / 'market_map.html'


def upload_result(session, archive, *, bucket=None):
    """Content addressed archive; publish completion manifest only after verification."""
    from google.api_core.exceptions import PreconditionFailed
    archive = Path(archive)
    if not archive.is_file():
        raise RuntimeError('RESULT_ARCHIVE_MISSING')
    digest = sha(archive)
    if bucket is None:
        from google.cloud import storage
        bucket = storage.Client(project='locdeproject', credentials=session.credentials).bucket(BUCKET)
    prefix = 'results/area-coverage/' + digest
    blob = bucket.blob(prefix + '/result.zip')
    if not blob.exists():
        blob.metadata = {'sha256': digest}
        try:
            blob.upload_from_filename(str(archive), if_generation_match=0, checksum='crc32c', timeout=600)
        except PreconditionFailed:
            pass  # A concurrent identical publication must still pass verification.
    blob.reload()
    if blob.size != archive.stat().st_size or (blob.metadata or {}).get('sha256') != digest:
        raise RuntimeError('GCS_RESULT_VERIFICATION_FAILED')
    manifest = {'schema': 'area_result_bundle_v1', 'status': 'STORED',
                'object': blob.name, 'generation': int(blob.generation),
                'bytes': blob.size, 'sha256': digest, 'crc32c': blob.crc32c,
                'input_pbf': PBF, 'scope': 'artifact persistence, not production accuracy approval'}
    pointer = bucket.blob(prefix + '/manifest.json')
    if pointer.exists():
        if json.loads(pointer.download_as_text()) != manifest:
            raise RuntimeError('GCS_RESULT_MANIFEST_CONFLICT')
    else:
        try:
            pointer.upload_from_string(json.dumps(manifest), content_type='application/json',
                                       if_generation_match=0, checksum='crc32c')
        except PreconditionFailed:
            if json.loads(pointer.download_as_text()) != manifest:
                raise RuntimeError('GCS_RESULT_MANIFEST_CONFLICT')
    return {'manifest_uri': 'gs://' + bucket.name + '/' + pointer.name, **manifest}


def stage_input(session, ref, path):
    """Bounded retry for interrupted PBF transfer; content mismatch is never ignored."""
    import requests
    import time
    from location_intelligent_google_only import stage
    for attempt in range(3):
        try:
            return stage(session, ref, path)
        except requests.RequestException as error:
            status = error.response.status_code if error.response is not None else None
            if status is not None and status not in {408, 429, 500, 502, 503, 504}:
                raise RuntimeError('GCS_INPUT_HTTP_ERROR: ' + str(status)) from None
            if attempt == 2:
                raise RuntimeError('GCS_INPUT_TRANSFER_UNAVAILABLE: retry sources; no calculation accepted') from None
            print('GCS transfer interrupted; retry', attempt + 2, '/3; retained finalized cache unchanged', flush=True)
            time.sleep(2 * (attempt + 1))
