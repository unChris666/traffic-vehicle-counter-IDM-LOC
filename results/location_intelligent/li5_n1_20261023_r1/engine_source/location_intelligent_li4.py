"""LI-4 offline presentation/export of a verified frozen LI-3 packet.

No retrieval, routing, capacity calculation, or modification of the input packet.
Build publishes a new directory only after verification. Open review.html directly.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

# Standalone verification must not create unlisted __pycache__ files in a frozen packet.
if __name__ == '__main__':
    sys.dont_write_bytecode = True

from location_intelligent_li3 import verify_manifest
from location_intelligent_li3_sources import read_json, write_json, canonical_bytes

HERE = Path(__file__).resolve().parent
CLAIM = 'EXPERIMENTAL_SCENARIO_NOT_PHYSICAL_LEGAL_OR_POPULATION_VALIDATION'
BANNER = ('SKENARIO EKSPERIMEN — bukan validasi akses fisik/legal, ETA nyata, atau populasi. '
          'Unknown tetap unknown. Kapasitas dipisahkan menurut satuan. '
          'Peta skematis offline tanpa basemap; posisi mengikuti snapshot.')
CSV_FIELDS = ['source_row_index', 'building_id', 'selection_status', 'decision_state',
              'reason', 'area_m2', 'total_time_min', 'threshold_time_min',
              'capacity_reference', 'capacity_unit', 'scenario_accessible',
              'verification_required', 'claim_type', 'evidence_ref']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique_by(rows, field):
    out = {}
    for row in rows:
        key = row[field]
        if key in out:
            raise ValueError('Duplicate '+field+': '+str(key))
        out[key] = row
    return out


def capacity_groups(rows):
    """Never aggregate different units or count missing capacity as zero."""
    groups = {}
    for row in rows:
        if row['selection_status'] != 'SELECTED':
            continue
        unit = row['capacity_unit']
        if not isinstance(unit, str) or not unit:
            raise ValueError('Selected capacity unit is missing')
        group = groups.setdefault(row['decision_state'], {}).setdefault(
            unit, {'buildings': 0, 'known_subtotal': 0, 'unknown_buildings': 0})
        group['buildings'] += 1
        value = row['capacity_reference']
        if value is None:
            group['unknown_buildings'] += 1
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid capacity')
        else:
            group['known_subtotal'] += value
    return groups


def derive(source):
    """Join stored outcomes by source row; project retained geometry for display only."""
    from pyproj import Transformer
    source = Path(source)
    report = read_json(source/'report.json')
    features = read_json(source/'normalized/buildings.geojson')['features']
    decisions = read_json(source/'building_results/decisions.json.gz')
    indices = unique_by(decisions, 'source_row_index')
    if set(indices) != set(range(len(features))) or report['source_records'] != len(features):
        raise ValueError('Source rows do not reconcile')
    selected = unique_by(read_json(source/'building_results/selection.json')['selected'], 'building_id')
    capacity = unique_by(read_json(source/'building_results/capacity.json')['rows'], 'building_id')
    routes = unique_by(read_json(source/'building_results/routing.json.gz')['routes'], 'building_id')
    if set(selected) != set(capacity) or set(selected) != set(routes):
        raise ValueError('Selected building/capacity/routing identities differ')
    graph = read_json(source/'graph/graph.json.gz')
    edges = unique_by(graph['edges'], 'edge_id')
    connectors = unique_by(read_json(source/'connectors/connectors.json.gz'), 'connector_id')
    rejection_counts = {}
    for item in read_json(source/'connectors/rejected.json.gz'):
        rejection_counts.setdefault(item.get('building_id'), Counter())[item['reason']] += 1
    project = Transformer.from_crs(graph['crs'], 'EPSG:4326', always_xy=True)

    def line(geometry):
        if geometry['type'] != 'LineString':
            raise ValueError('Unsupported retained line geometry')
        coords = [list(project.transform(*xy)) for xy in geometry['coordinates']]
        if len(coords) < 2 or not all(math.isfinite(v) for xy in coords for v in xy):
            raise ValueError('Invalid transformed line')
        return coords

    connector_features = []
    for key, item in sorted(connectors.items()):
        connector_features.append({'type': 'Feature', 'id': key,
            'geometry': {'type': 'LineString', 'coordinates': line(item['geometry'])},
            'properties': {k: v for k, v in item.items() if k != 'geometry'}})
    geo_connectors = unique_by(connector_features, 'id')
    rows, building_features, route_features = [], [], []
    seen_selected = set()
    for index, feature in enumerate(features):
        decision = indices[index]
        bid = feature['properties']['building_id']
        if decision['building_id'] != bid:
            raise ValueError('Source row identity changed')
        is_selected = decision['selection_status'] == 'SELECTED'
        b, cap = selected.get(bid, {}), capacity.get(bid, {})
        candidate = decision.get('selected_candidate')
        route = routes.get(bid) if is_selected else None
        if is_selected:
            seen_selected.add(bid)
            if route['selected_candidate'] != candidate:
                raise ValueError('Stored decision/routing candidate mismatch')
            expected = ('ACCEPTED' if route['scenario_accessible'] is True else 'OVER_TIME_LIMIT') if route['route_found'] is True else None
            if expected and decision['decision_state'] != expected:
                raise ValueError('Stored route outcome mismatch')
            if route['route_found'] is not True and decision['decision_state'] in {'ACCEPTED', 'OVER_TIME_LIMIT'}:
                raise ValueError('Unproven route cannot become accepted')
        row = {k: decision.get(k) for k in ['source_row_index', 'building_id', 'selection_status', 'decision_state', 'reason']}
        row.update({'area_m2': b.get('area_m2') if is_selected else None,
            'total_time_min': candidate.get('total_time_min') if candidate else None,
            'threshold_time_min': candidate.get('threshold_time_min') if candidate else None,
            'capacity_reference': cap.get('capacity_reference_rounded') if is_selected else None,
            'capacity_unit': cap.get('unit') if is_selected else None,
            'scenario_accessible': route['scenario_accessible'] if route else None,
            'verification_required': True, 'claim_type': CLAIM,
            'evidence_ref': f'snapshot/building_results/decisions.json.gz#source_row_index={index}',
            'connector_count': decision.get('connector_count'),
            'rejected_connector_reasons': dict(sorted(rejection_counts.get(bid, {}).items())) if is_selected else {},
            'selected_candidate': candidate,
            'route_ref': f'routes.geojson#source_row_index={index}' if candidate else None,
            'capacity_detail': cap if is_selected else None,
            'source_properties': feature['properties']})
        rows.append(row)
        building_features.append({'type': 'Feature', 'id': index, 'geometry': feature['geometry'], 'properties': row})
        if not candidate:
            continue
        bc, tc = connectors[candidate['building_connector_id']], connectors[candidate['target_connector_id']]
        chain = [edges[key] for key in candidate['network_edges']]
        current = bc['node_id']
        for edge in chain:
            if edge['u'] != current or edge['access_allowed'] is not True:
                raise ValueError('Invalid stored path continuity/permission')
            current = edge['v']
        if current != tc['node_id']:
            raise ValueError('Stored path does not reach target connector')
        segments = [geo_connectors[bc['connector_id']]['geometry']['coordinates']]
        segments += [line(edge['geometry']) for edge in chain]
        segments += [geo_connectors[tc['connector_id']]['geometry']['coordinates']]
        route_features.append({'type': 'Feature', 'id': index,
            'geometry': {'type': 'MultiLineString', 'coordinates': segments},
            'properties': {**{k: row[k] for k in CSV_FIELDS}, 'network_edges': candidate['network_edges'],
                'building_connector_id': bc['connector_id'], 'target_connector_id': tc['connector_id']}})
    if seen_selected != set(selected):
        raise ValueError('Selected rows missing')
    counts = dict(sorted(Counter(r['decision_state'] for r in rows if r['selection_status'] == 'SELECTED').items()))
    groups = capacity_groups(rows)
    if counts != report['decision_counts_selected'] or groups != report['capacity_by_decision_state_and_unit']:
        raise ValueError('Summary/capacity differs from frozen report')
    if len(seen_selected) != report['selected_buildings'] or len(rows) != report['all_source_rows_accounted']:
        raise ValueError('Selected/source denominator mismatch')
    context = read_json(source/'normalized/context.json')
    summary = {'schema_version': 'li4_view_v1', 'claim_type': CLAIM, 'banner': BANNER,
        'analysis_run_id': report['analysis_run_id'], 'analysis_status': report['status'],
        'source_records': len(rows), 'selected_buildings': len(seen_selected),
        'non_selected_records': len(rows)-len(seen_selected), 'decision_counts_selected': counts,
        'decision_counts_all': dict(sorted(Counter(r['decision_state'] for r in rows).items())),
        'capacity_by_decision_state_and_unit': groups, 'mixed_unit_total': None, 'final_business_capacity': None,
        'source_warnings': report['source_warnings'], 'limitations': report['limitations'],
        'source_manifest_sha256': digest(source/'manifest.json'), 'target': context['target'],
        'policy': read_json(source/'config/pilot.json')['policy'],
        'attribution': '© OpenStreetMap contributors (ODbL); Overture Maps and per-building source/license metadata retained.',
        'csv_null_encoding': 'Empty cell means null, never zero. Structured values are JSON. Text formula prefixes escaped with apostrophe.'}
    collection = lambda values: {'type': 'FeatureCollection', 'features': values}
    return {'summary': summary, 'rows': rows, 'buildings': collection(building_features),
            'routes': collection(route_features), 'connectors': collection(connector_features)}


def csv_value(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if isinstance(value, str) and value[:1] in '=+-@\t\r\n':
        return "'"+value
    return str(value)


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: csv_value(row[key]) for key in CSV_FIELDS})
    return stream.getvalue().encode('utf-8')


def html_bytes(data, template):
    # Escape script delimiters and HTML-sensitive chars in embedded, non-executable JSON.
    payload = canonical_bytes(data).decode().replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    if template.count('__LI4_PAYLOAD__') != 1:
        raise ValueError('HTML template payload marker missing/duplicated')
    return template.replace('__LI4_PAYLOAD__', payload).encode()


def exports(data, template):
    return {'summary.json': canonical_bytes(data['summary']), 'buildings.json': canonical_bytes(data['rows']),
        'buildings.csv': csv_bytes(data['rows']), 'buildings.geojson': canonical_bytes(data['buildings']),
        'routes.geojson': canonical_bytes(data['routes']), 'connectors.geojson': canonical_bytes(data['connectors']),
        'review.html': html_bytes(data, template)}


def verify(root):
    root = Path(root)
    manifest = verify_manifest(root)
    if manifest.get('schema_version') != 'li4_package_v1':
        raise ValueError('Not an LI-4 package')
    source_manifest = verify_manifest(root/'snapshot')
    if digest(root/'snapshot/manifest.json') != manifest['source_manifest_sha256']:
        raise ValueError('Source manifest binding mismatch')
    import pyproj
    if manifest['software'] != {'pyproj': pyproj.__version__, 'proj': pyproj.proj_version_str}:
        raise ValueError('Projection software differs; use recorded environment for semantic verification')
    data = derive(root/'snapshot')
    template = (root/'engine_source/location_intelligent_li4.html').read_text()
    for name, expected in exports(data, template).items():
        if (root/name).read_bytes() != expected:
            raise ValueError('Export/view reconciliation mismatch: '+name)
    if manifest['analysis_status'] != data['summary']['analysis_status'] or manifest['package_status'] != 'SUCCEEDED_WITH_WARNINGS':
        raise ValueError('Package/analysis status mismatch')
    return {'status': 'PASS', 'source_files_verified': len(source_manifest['files']),
        'package_files_verified': len(manifest['files']), 'source_records': len(data['rows']),
        'routes': len(data['routes']['features']), 'analysis_status': data['summary']['analysis_status'],
        'source_manifest_sha256': manifest['source_manifest_sha256'], 'network_or_routing_executed': False}


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Source and output must be separate directories')
    if output.exists():
        raise ValueError('Choose a new output directory; existing packages are immutable')
    verify_manifest(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.'+output.name+'-', dir=output.parent))
    try:
        shutil.copytree(source, staging/'snapshot')
        data = derive(staging/'snapshot')
        for name, value in exports(data, (HERE/'location_intelligent_li4.html').read_text()).items():
            (staging/name).write_bytes(value)
        engine = staging/'engine_source'; engine.mkdir()
        for name in ['location_intelligent_li4.py', 'location_intelligent_li4.html',
                     'location_intelligent_li3.py', 'location_intelligent_li3_sources.py', 'location_intelligent_validator.py']:
            shutil.copyfile(HERE/name, engine/name)
        (staging/'README.md').write_text('# LI-4 N1 — paket eksperimen offline\n\n'
            +BANNER+'\n\nBuka **review.html** langsung di browser. Tidak memerlukan server/CDN/basemap.\n'
            'Semua baris ada pada buildings.json/CSV/GeoJSON; routes dan connectors memakai EPSG:4326 [lon,lat].\n'
            'Waktu kosong/null berarti tidak diketahui, bukan nol. Rute over-time juga diekspor.\n'
            'snapshot/ adalah salinan lengkap LI-3, termasuk bukti dan manifest. Tidak ada inference/routing ulang.\n'
            'Klik bangunan untuk status, alasan, rute, dan referensi bukti. Warna bukan bukti akses lapangan.\n\n'
            'Verifikasi dari direktori paket dengan environment pyproj yang direkam:\n'
            '```bash\nPROJ_NETWORK=OFF python -B engine_source/location_intelligent_li4.py verify --root .\n```\n')
        import pyproj
        manifest = {'schema_version': 'li4_package_v1', 'package_status': 'SUCCEEDED_WITH_WARNINGS',
            'analysis_status': data['summary']['analysis_status'], 'claim_type': CLAIM,
            'source_manifest_sha256': digest(staging/'snapshot/manifest.json'),
            'software': {'pyproj': pyproj.__version__, 'proj': pyproj.proj_version_str},
            'files': [{'path': str(p.relative_to(staging)), 'bytes': p.stat().st_size, 'sha256': digest(p),
                       'dependencies': []} for p in sorted(staging.rglob('*')) if p.is_file()]}
        write_json(staging/'manifest.json', manifest)
        receipt = verify(staging)
        if output.exists():
            raise ValueError('Output appeared during build')
        staging.rename(output)
        return receipt
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'verify'])
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'build' and args.source and args.output:
            result = build(args.source, args.output)
        elif args.command == 'verify' and args.root:
            result = verify(args.root)
        else:
            parser.error('build requires --source/--output; verify requires --root')
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'reason': str(error)}), file=sys.stderr)
        sys.exit(1)
