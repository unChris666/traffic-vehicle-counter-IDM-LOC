"""Explicit bounded source probe, not a general LI-3 acquisition service.

Run using the isolated DuckDB environment; no network on import. Output raw
rows are normalized separately with system Python/GDAL. Never overwrite runs.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
import urllib.request


RELEASE = '2026-10-21.0'
CATALOG = f'https://stac.overturemaps.org/{RELEASE}/buildings/building/collection.json'


def _read(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'LI-bounded-source-probe/1'})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read(4_000_001)
    if len(data) > 4_000_000:
        raise ValueError('Metadata response too large')
    return json.loads(data), hashlib.sha256(data).hexdigest()


def probe(bbox, row_limit, output, extension_directory):
    import duckdb
    if len(bbox) != 4 or not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90) or bbox[2]-bbox[0] > .02 or bbox[3]-bbox[1] > .02:
        raise ValueError('Use an explicit small geographic bbox (<=.02 degrees per side)')
    if not 1 <= row_limit <= 10001:
        raise ValueError('Bound rows to1..10001')
    if output.exists():
        raise ValueError('Use a new output path; retained evidence must not be overwritten')
    collection, collection_hash = _read(CATALOG)
    boxes = collection['extent']['spatial']['bbox']
    links = [x for x in collection['links'] if x['rel'] == 'item']
    if len(boxes) != len(links)+1:
        raise ValueError('STAC partition extent layout changed')
    def intersects(b):
        return b[0] <= bbox[2] and b[2] >= bbox[0] and b[1] <= bbox[3] and b[3] >= bbox[1]
    indices = [i for i, b in enumerate(boxes[1:]) if intersects(b)]
    if not 1 <= len(indices) <= 4:
        raise ValueError('Probe scope requires1..4 candidate partitions')
    assets, items = [], []
    for i in indices:
        item, digest = _read(links[i]['href'])
        if not intersects(item['bbox']):
            raise ValueError('Item and indexed extent disagree')
        asset = item['assets']['aws']['href']
        if not asset.startswith(f'https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/release/{RELEASE}/theme=buildings/type=building/'):
            raise ValueError('Asset must belong to requested official release/theme')
        assets.append(asset)
        items.append({'url': links[i]['href'], 'metadata_sha256': digest, 'bbox': item['bbox'], 'asset': asset})
    c = duckdb.connect()
    c.execute("SET extension_directory = ?", [str(extension_directory)])
    c.execute('LOAD httpfs')
    for statement in ['SET enable_geoparquet_conversion=false', 'SET http_timeout=30', 'SET http_retries=1', 'SET threads=2', "SET memory_limit='256MB'"]:
        c.execute(statement)
    descriptor = c.execute('DESCRIBE SELECT * FROM read_parquet(?)', [assets]).fetchall()
    required = {'id': 'VARCHAR', 'geometry': 'BLOB', 'class': 'VARCHAR', 'subtype': 'VARCHAR', 'height': 'DOUBLE', 'num_floors': 'INTEGER', 'version': 'INTEGER'}
    actual = {r[0]: r[1] for r in descriptor}
    if any(actual.get(k) != val for k, val in required.items()) or 'bbox' not in actual or 'sources' not in actual:
        raise ValueError('Physical Parquet schema incompatible with expected source fields')
    sql = ('SELECT id, class, subtype, height, num_floors, version, sources, bbox, hex(geometry) AS geometry_wkb_hex '
           'FROM read_parquet(?) WHERE bbox.xmin <= ? AND bbox.xmax >= ? AND bbox.ymin <= ? AND bbox.ymax >= ? '
           'ORDER BY id LIMIT ?')
    start = time.monotonic()
    cursor = c.execute(sql, [assets, bbox[2], bbox[0], bbox[3], bbox[1], row_limit])
    cols = [x[0] for x in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    result = {'release': RELEASE, 'schema_version': '2.0.0', 'collection_url': CATALOG,
              'collection_sha256': collection_hash, 'items': items, 'bbox': bbox, 'sql': sql,
              'row_cap': row_limit, 'truncated': len(rows) == row_limit, 'physical_schema': descriptor,
              'schema_validation_scope': 'Consumed Parquet columns/types and downstream canonical geometry; not full official schema validation',
              'coverage_complete': False, 'coverage_reason': 'Bounded technical probe; partition candidate completeness not independently established',
              'duckdb_version': duckdb.__version__, 'elapsed_s': time.monotonic()-start, 'rows': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        json.dump(result, f, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return result


def normalize(raw):
    """Map provider subtype->canonical subclass without guessing taxonomy."""
    from osgeo import ogr
    if raw.get('release') != RELEASE or raw.get('schema_version') != '2.0.0':
        raise ValueError('Wrong release/schema')
    features = []
    for row in raw['rows']:
        if not {'id', 'class', 'subtype', 'height', 'num_floors', 'geometry_wkb_hex', 'version', 'sources'} <= row.keys():
            raise ValueError('Missing provider columns')
        geom = ogr.CreateGeometryFromWkb(bytes.fromhex(row['geometry_wkb_hex']))
        if geom is None:
            raise ValueError('Unreadable source WKB')
        features.append({'type': 'Feature', 'id': row['id'], 'geometry': json.loads(geom.ExportToJson()),
                         'properties': {'building_id': row['id'], 'class': row['class'], 'subclass': row['subtype'],
                                        'height': row['height'], 'num_floors': row['num_floors'],
                                        'source_feature_version': row['version'], 'sources': row['sources']}})
    return {'type': 'FeatureCollection', 'features': features}


def verify_partitions(bbox, output):
    """Independently read every advertised item bbox, not extent-order alone."""
    if output.exists():
        raise ValueError('Use a new partition verification output')
    collection, digest = _read(CATALOG)
    links = [x['href'] for x in collection['links'] if x['rel'] == 'item']
    def fetch(url):
        item, sha = _read(url)
        return {'url': url, 'bbox': item['bbox'], 'asset': item['assets']['aws']['href'], 'metadata_sha256': sha}
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(fetch, links))
    matches = [r for r in rows if r['bbox'][0] <= bbox[2] and r['bbox'][2] >= bbox[0] and r['bbox'][1] <= bbox[3] and r['bbox'][3] >= bbox[1]]
    result = {'release': RELEASE, 'collection_sha256': digest, 'items_checked': len(rows),
              'errors': [], 'matching': matches, 'items': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        json.dump(result, f, sort_keys=True, allow_nan=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bbox', nargs=4, required=True, type=float)
    parser.add_argument('--row-limit', type=int, default=10001)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--extension-directory', required=True, type=Path)
    parser.add_argument('--verify-partitions-output', type=Path)
    args = parser.parse_args()
    r = probe(args.bbox, args.row_limit, args.output, args.extension_directory)
    if args.verify_partitions_output:
        verify_partitions(args.bbox, args.verify_partitions_output)
    print(json.dumps({'rows': len(r['rows']), 'truncated': r['truncated'], 'elapsed_s': r['elapsed_s'], 'output': str(args.output)}))
