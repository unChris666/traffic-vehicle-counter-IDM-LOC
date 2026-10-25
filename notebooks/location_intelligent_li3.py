"""LI-3 explicit acquire/build/replay commands. Existing LI-1/LI-2 are reused."""
import argparse
import csv
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from location_intelligent_li3_sources import read_json, write_json, canonical_bytes, build_queries, acquire_overpass, utc
from location_intelligent_validator import canonical_hash

REPO = Path(__file__).resolve().parents[1]
CORE = REPO/'notebooks/location_intelligent_li3_core.py'


def run_core(root, stage):
    env = {**os.environ, 'PROJ_NETWORK': 'OFF', 'PYTHONDONTWRITEBYTECODE': '1'}
    cmd = ['/usr/bin/python3', '-B', str(CORE), stage, '--root', str(root)]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode:
        raise RuntimeError('Core stage failed: '+stage+' '+result.stderr[-1800:]+result.stdout[-1800:])
    for line in result.stderr.splitlines():
        if line.startswith('Normalization cache:'):print(line,flush=True)
    return json.loads(result.stdout)


def freeze(root):
    from pyproj import Transformer
    from location_intelligent_config import get_config
    if root.exists():
        raise ValueError('Choose a new pilot directory')
    p = get_config(); li = p['li3']
    forward = Transformer.from_crs(4326, li['metric_crs'], always_xy=True)
    inverse = Transformer.from_crs(li['metric_crs'], 4326, always_xy=True)
    x, y = forward.transform(li['longitude'], li['latitude']); radius = li['network_bbox_radius_m']
    corners = [inverse.transform(a, b) for a in (x-radius, x+radius) for b in (y-radius, y+radius)]
    cache = REPO/li['building_cache']
    checksums = {str(f.relative_to(REPO)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(cache.iterdir()) if f.is_file()}
    frozen = {'schema_version': 'li3_pilot_config_v1', 'algorithm_version': 'LI3_V1',
              'analysis_run_id': root.name, 'frozen_at': utc(), 'policy': p, 'target_xy': [x,y],
              'extraction_bbox_wgs84': [min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners), max(c[1] for c in corners)],
              'reference_metric_bbox': [x-radius,y-radius,x+radius,y+radius], 'building_cache_files': checksums,
              'target_snap_decision': 'OWNER_APPROVED_NEAREST_VALID_ROAD', 'source_scope': 'N1 technical pilot only; not TGDI',
              'core_python': '/usr/bin/python3', 'diagnostic_gap_m': 10.0}
    frozen['config_hash'] = canonical_hash(frozen)
    write_json(root/'config/pilot.json', frozen, exclusive=True)
    return frozen


def acquire(root):
    f = read_json(root/'config/pilot.json'); p = f['policy']; li = p['li3']
    for name, digest in f['building_cache_files'].items():
        source = REPO/name
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError('Building cache changed: '+name)
        destination = root/'raw/building_cache'/source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
    queries = build_queries(f['extraction_bbox_wgs84'], p)
    write_json(root/'config/queries.json', queries)
    for name in ('roads', 'features_pinned', 'features'):
        path = root/'raw'/f'osm_{name}.json.gz'
        if path.exists():
            continue
        query = queries['roads' if name == 'roads' else 'features']
        if name != 'roads':
            roads = read_json(root/'raw/osm_roads.json.gz')
            if roads['status'] != 'SUCCEEDED':
                return {'roads': roads['status'], 'features': 'NOT_ATTEMPTED_ROAD_SOURCE_FAILED'}
            asof = roads['payload']['osm3s'].get('timestamp_osm_base')
            if name == 'features' and (root/'raw/osm_features_pinned.json.gz').exists() and read_json(root/'raw/osm_features_pinned.json.gz')['status'] == 'SUCCEEDED':
                continue
            if name == 'features_pinned' and asof:
                query = query.replace(';', f'[date:"{asof}"];', 1)
        result = acquire_overpass(query, li['overpass_endpoints'], li['request_timeout_s'], li['max_response_bytes'])
        result['actual_query'] = query
        if name == 'features_pinned':
            result['requested_snapshot_as_of'] = asof
        write_json(path, result, exclusive=True)
    selected, warnings = select_feature_source(root)
    return {'roads': read_json(root/'raw/osm_roads.json.gz')['status'],
            'features': read_json(selected)['status'] if selected.exists() else 'SOURCE_MISSING', 'warnings': warnings}


def select_feature_source(root):
    """Prefer a successful exact-as-of extract, preserve failed attempts."""
    policy=read_json(root/'config/pilot.json')['policy']['li3']
    if policy.get('feature_source_mode')=='ROADS_ONLY_EXPERIMENT':
        path=root/'raw/osm_features_roads_only.json.gz'
        source=read_json(path)
        if source.get('coverage')!='ROAD_EXTRACT_ONLY_EXTERNAL_FEATURES_NOT_REQUESTED' or source.get('external_features_requested') is not False:
            raise ValueError('Road-only feature provenance missing')
        if source.get('source_roads_sha256')!=hashlib.sha256((root/'raw/osm_roads.json.gz').read_bytes()).hexdigest():
            raise ValueError('Road-derived feature source does not match roads')
        return path,[{'code':'EXTERNAL_FEATURES_NOT_REQUESTED','effect':'Road graph experiment; external barriers and turn restrictions not fully checked'}]
    pinned = root/'raw/osm_features_pinned.json.gz'
    if pinned.exists() and read_json(pinned)['status'] == 'SUCCEEDED':
        return pinned, []
    tiles = sorted((root/'raw').glob('osm_features_tile_*.json.gz'))
    if len(tiles) == 4 and all(read_json(p)['status'] == 'SUCCEEDED' for p in tiles):
        from location_intelligent_li3_graph import merge_elements
        values = [read_json(p) for p in tiles]
        elements = {}
        for v in values:
            elements = merge_elements(list(elements.values()), v['payload']['elements'])
        combined = {'status': 'SUCCEEDED', 'payload': {'elements': sorted(elements.values(), key=lambda e: (e['type'], e['id'])),
                    'osm3s': values[0]['payload']['osm3s'], 'generator': values[0]['payload'].get('generator')},
                    'requested_snapshot_as_of': values[0].get('requested_snapshot_as_of'), 'tile_sources': [str(p.relative_to(root)) for p in tiles]}
        target = root/'raw/osm_features_combined.json.gz'
        write_json(target, combined)
        return target, []
    fallback = root/'raw/osm_features.json.gz'
    warnings = []
    if fallback.exists() and read_json(fallback)['status'] == 'SUCCEEDED':
        road_source = read_json(root/'raw/osm_roads.json.gz') if (root/'raw/osm_roads.json.gz').exists() else {}
        road_asof = (road_source.get('payload') or {}).get('osm3s', {}).get('timestamp_osm_base')
        feature = read_json(fallback)
        feature_asof = feature.get('requested_snapshot_as_of', feature['payload']['osm3s'].get('timestamp_osm_base'))
        if feature_asof != road_asof:
            warnings.append({'code': 'NON_ATOMIC_SOURCE_TIMESTAMPS', 'road_as_of': road_asof, 'feature_as_of': feature_asof,
                             'effect': 'Shared source elements must match exactly; no temporal completeness claim'})
    return fallback, warnings


def map_decisions(selection, routing, connector_package):
    rows = []
    rejected = connector_package.get('rejected_candidates', [])
    by_id = {r['building_id']: r for r in routing.get('routes', [])}
    connectors = connector_package.get('connectors', [])
    own_connectors, own_rejections = {}, {}
    for c in connectors:
        own_connectors.setdefault(c.get('building_id'), []).append(c)
    for r in rejected:
        own_rejections.setdefault(r.get('building_id'), []).append(r)
    for b in selection['selected']:
        key = b['building_id']; route = by_id.get(key)
        own = own_connectors.get(key, [])
        own_rejects = own_rejections.get(key, [])
        if routing.get('status') in {'FAILED', 'BLOCKED'}:
            state = 'ACCESS_UNVERIFIED' if routing['status'] == 'BLOCKED' else 'PROCESSING_ERROR'
        elif route and route['route_found'] is True:
            state = 'ACCEPTED' if route['scenario_accessible'] else 'OVER_TIME_LIMIT'
        elif not own:
            uncertain = any('UNVERIFIED' in r['reason'] for r in own_rejects)
            state = 'ACCESS_UNVERIFIED' if uncertain else 'NO_VALID_CONNECTOR'
        elif route and route['route_found'] is None:
            state = 'ACCESS_UNVERIFIED'
        else:
            state = 'NO_ROUTE'
        rows.append({'building_id': key, 'source_row_index': b['source_row_index'], 'selection_status': 'SELECTED',
                     'decision_state': state, 'reason': route.get('reason') if route else 'ROUTING_UNAVAILABLE',
                     'routing_ref': key, 'capacity_ref': key, 'connector_count': len(own), 'rejected_connector_candidates': len(own_rejects),
                     'selected_candidate': route.get('selected_candidate') if route else None,
                     'verification_required': True, 'claim_type': 'CONFIGURED_SCENARIO_NOT_PHYSICAL_VERIFICATION'})
    for rejection in selection['reject_ledger']:
        rows.append({'building_id': rejection.get('building_id'), 'source_row_index': rejection['source_row_index'],
                     'selection_status': rejection['disposition'], 'decision_state': 'INVALID_GEOMETRY' if rejection.get('stage') == 'GEOMETRY' else 'EXCLUDED_BY_SELECTION',
                     'reason': rejection['code'], 'capacity_ref': None, 'routing_ref': None})
        if rejection['disposition'] == 'REJECTED' and rejection.get('stage') != 'GEOMETRY':
            rows[-1]['decision_state'] = 'PROCESSING_ERROR'
    return sorted(rows, key=lambda r: r['source_row_index'])


def build(root):
    from location_intelligent_li3_graph import build_graph, graph_diagnostics
    from location_intelligent_li3_connectors import generate_connectors
    f = read_json(root/'config/pilot.json')
    expected = f.pop('config_hash')
    if canonical_hash(f) != expected:
        raise ValueError('Frozen configuration changed')
    f['config_hash'] = expected
    from location_intelligent_li3_sources import timed_call
    prep = timed_call('selection_capacity_projection',run_core,root,'prepare')
    roads = read_json(root/'raw/osm_roads.json.gz') if (root/'raw/osm_roads.json.gz').exists() else {'status': 'SOURCE_MISSING'}
    feature_path, warnings = select_feature_source(root)
    if f.get('building_network_timestamp_warning'):
        warnings.append({'code':'BUILDING_NETWORK_SNAPSHOTS_DIFFER','details':f['building_network_timestamp_warning'],'effect':'Frozen separately; no atomic snapshot claim'})
    osm_report=read_json(root/'raw/building_cache/report.json').get('osm_normalization')
    if osm_report and any(r['reason']!='RELATION_MEMBER_COMPONENT' for r in osm_report['excluded']):
        warnings.append({'code':'OSM_BUILDING_NORMALIZATION_EXCLUSIONS','effect':'Some raw objects unresolved; inspect raw/building_cache/report.json'})
    features = read_json(feature_path) if feature_path.exists() else {'status': 'SOURCE_MISSING'}
    resolved = {'road_source': 'raw/osm_roads.json.gz', 'feature_source': str(feature_path.relative_to(root)), 'warnings': warnings}
    write_json(root/'config/resolved_sources.json', resolved)
    base = timed_call('road_graph',build_graph,roads,features,f)
    write_json(root/'diagnostics/source_graph.json', base['diagnostics'])
    if base['graph'] is None:
        selection = read_json(root/'building_results/selection.json')
        report = {'status': 'BLOCKED', 'reason': base['status'], 'accepted': None,
                  'rows': [{'building_id': b['building_id'], 'decision_state': base['status']} for b in selection['selected']]}
        write_json(root/'building_results/decisions.json.gz', report)
        write_json(root/'report.json', report)
        return report
    write_json(root/'graph/base_graph.json.gz', base['graph'])
    write_json(root/'graph/base_edge_sources.json.gz', base['edge_sources'])
    metrics = read_json(root/'normalized/metric_buildings.json')
    package = timed_call('connectors',generate_connectors,base,metrics,features,f)
    for edge in package['graph']['edges']:
        edge['access_allowed'] = package['edge_rules'][edge['edge_id']]['allowed']
    selection = read_json(root/'building_results/selection.json')
    context = read_json(root/'normalized/context.json')
    evidence = {'schema_version': 'li_motor_evidence_v1', 'graph_hash': canonical_hash(package['graph']),
                'selection_hash': canonical_hash(selection), 'context_hash': context['context_hash'], 'policy_hash': canonical_hash(f['policy']),
                'edge_rules': package['edge_rules'], 'blocked_turns': package['blocked_turns'],
                'restrictions_complete': f['policy']['li3'].get('feature_source_mode')!='ROADS_ONLY_EXPERIMENT',
                'feature_scope': f['policy']['li3'].get('feature_source_mode','FULL'), 'connectors': package['connectors']}
    write_json(root/'graph/graph.json.gz', package['graph'])
    write_json(root/'graph/edge_sources.json.gz', package['edge_sources'])
    write_json(root/'connectors/evidence.json.gz', evidence)
    write_json(root/'connectors/connectors.json.gz', package['connectors'])
    write_json(root/'connectors/rejected.json.gz', package['rejected_candidates'])
    write_json(root/'diagnostics/connectors.json', package['diagnostics'])
    gd = timed_call('graph_diagnostics',graph_diagnostics,package['graph'],package['edge_rules'],f['diagnostic_gap_m'])
    write_json(root/'diagnostics/graph.json', gd)
    outcome = timed_call('routing',run_core,root,'route')
    return timed_call('decisions_export',finalize,root,package,prep,warnings)


def finalize(root, package=None, prep=None, warnings=None):
    f = read_json(root/'config/pilot.json')
    selection = read_json(root/'building_results/selection.json')
    if package is None:
        package = {'connectors': read_json(root/'connectors/connectors.json.gz'),
                   'rejected_candidates': read_json(root/'connectors/rejected.json.gz'),
                   'diagnostics': read_json(root/'diagnostics/connectors.json')}
    if prep is None:
        prep = {'capacity': read_json(root/'building_results/capacity.json')['summary_by_unit']}
    if warnings is None:
        warnings = read_json(root/'config/resolved_sources.json')['warnings']
    gd = read_json(root/'diagnostics/graph.json')
    routing = read_json(root/'building_results/routing.json.gz')
    rows = map_decisions(selection, routing, package)
    write_json(root/'building_results/decisions.json.gz', rows)
    by_building = {b['building_id']: b for b in selection['selected']}
    capacity_rows = {b['building_id']: b for b in read_json(root/'building_results/capacity.json')['rows']}
    with (root/'building_results/decisions.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['source_row_index','building_id','selection_status','decision_state','reason',
            'class','subclass','area_m2','capacity_reference_rounded','capacity_unit','total_time_min','threshold_time_min',
            'building_connector_id','target_connector_id','verification_required'])
        writer.writeheader()
        for row in rows:
            b = by_building.get(row['building_id'], {}); cap = capacity_rows.get(row['building_id'], {}); candidate = row.get('selected_candidate') or {}
            writer.writerow({**{k:row.get(k) for k in ['source_row_index','building_id','selection_status','decision_state','reason','verification_required']},
                'class': b.get('class'), 'subclass': b.get('subclass'), 'area_m2': b.get('area_m2'),
                'capacity_reference_rounded': cap.get('capacity_reference_rounded'), 'capacity_unit': cap.get('unit'),
                **{k:candidate.get(k) for k in ['total_time_min','threshold_time_min','building_connector_id','target_connector_id']}})
    selected_rows = [r for r in rows if r['selection_status'] == 'SELECTED']
    summary = dict(sorted(Counter(r['decision_state'] for r in selected_rows).items()))
    capacity_by_decision = {}
    for row in selected_rows:
        cap = capacity_rows[row['building_id']]
        group = capacity_by_decision.setdefault(row['decision_state'], {}).setdefault(cap['unit'], {'buildings':0,'known_subtotal':0,'unknown_buildings':0})
        group['buildings'] += 1
        if cap['capacity_reference_rounded'] is None:
            group['unknown_buildings'] += 1
        else:
            group['known_subtotal'] += cap['capacity_reference_rounded']
    report = {'status': 'PARTIAL' if warnings or routing['status'] == 'PARTIAL' else routing['status'],
              'analysis_run_id': f['analysis_run_id'], 'source_records': selection['summary']['source_records'],
              'selected_buildings': len(selected_rows), 'all_source_rows_accounted': len(rows),
              'decision_counts_selected': summary, 'decision_denominator': len(selected_rows),
              'graph': gd, 'connectors': len(package['connectors']), 'connector_diagnostics': package['diagnostics'],
              'routing_status': routing['status'], 'routing_diagnostics': routing['diagnostics'],
              'source_warnings': warnings, 'capacity_by_unit': prep['capacity'],
              'capacity_by_decision_state_and_unit': capacity_by_decision,
              'limitations': ['Reference7kmh, not observed ETA', 'Owner entrance/alley/gate assumptions, not physical/legal verification',
                              'No mixed-unit capacity/population claim', 'Bounded OSM graph, unknown permissions retained',
                              'Conditional and complex restrictions conservatively quarantined, not fully interpreted']}
    if len(rows) != selection['summary']['source_records']:
        raise ValueError('Building decisions do not reconcile to source records')
    write_json(root/'report.json', report)
    text = '# LI-3 N1 pilot — actual result\n\n' + 'Status: **'+report['status']+'**.\n\n'
    text += f"{report['source_records']} source records; {report['selected_buildings']} selected; {report['all_source_rows_accounted']} rows accounted.\n\n"
    text += '| Selected-building decision | Count |\n|---|---:|\n' + ''.join(f'| {k} | {v} |\n' for k,v in summary.items())
    text += '\nDenominator: all selected LI-1 buildings. Source exclusions have separate rows.\n\n'
    text += '\n'.join('- '+v for v in report['limitations'])+'\n\n'
    text += 'Full source/query/provenance and uncertainties: report.json, config/, raw/, diagnostics/.\n'
    (root/'report.md').write_text(text)
    return report


def decide(root):
    run_core(root, 'route')
    return finalize(root)


def make_manifest(root, filename='manifest.json'):
    stage = lambda p: p.split('/')[0]
    files = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p in {root/filename, (root/filename).with_suffix('.tmp')}:
            continue
        if not p.resolve().is_relative_to(root.resolve()) or p.is_symlink():
            raise ValueError('Artifact outside pilot root')
        name = str(p.relative_to(root)); data = p.read_bytes()
        if name.startswith('normalized/'):
            deps = ['config/pilot.json'] + [str(x.relative_to(root)) for x in sorted((root/'raw/building_cache').glob('*')) if x.is_file()]
        elif name.startswith('graph/'):
            deps = ['config/pilot.json', 'normalized/metric_buildings.json', 'raw/osm_roads.json.gz', read_json(root/'config/resolved_sources.json')['feature_source']]
        elif name.startswith('connectors/'):
            deps = ['graph/graph.json.gz', 'normalized/metric_buildings.json', 'config/pilot.json']
        elif name.startswith('building_results/'):
            deps = ['normalized/buildings.geojson', 'config/pilot.json']
            if 'routing' in name or 'decisions' in name:
                deps += ['graph/graph.json.gz', 'connectors/evidence.json.gz']
        else:
            deps = []
        deps = [d for d in deps if (root/d).is_file()]
        if name == 'normalized/metric_buildings.json':
            deps.append('building_results/selection.json')
        if name == 'building_results/selection.json':
            deps += ['normalized/context.json', 'normalized/input_manifest.json']
        if name == 'building_results/capacity.json':
            deps.append('building_results/selection.json')
        if name == 'building_results/routing.json.gz':
            deps.append('building_results/selection.json')
        if name in {'building_results/decisions.json.gz', 'building_results/decisions.csv'} and (root/'building_results/routing.json.gz').exists():
            deps += ['building_results/routing.json.gz', 'building_results/capacity.json', 'connectors/rejected.json.gz']
        if name in {'report.json', 'report.md'}:
            deps += ['building_results/decisions.json.gz']
        files.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'role': stage(name), 'dependencies': sorted(set(deps))})
    manifest = {'schema_version': 'li3_manifest_v1', 'analysis_run_id': read_json(root/'config/pilot.json')['analysis_run_id'],
                'status': read_json(root/'report.json')['status'], 'files': files,
                'notes': ['Manifest excludes its own bytes', 'Checksums do not prove data accuracy/completeness']}
    available = {r['path'] for r in files}
    if any(d not in available for row in files for d in row['dependencies']):
        raise ValueError('Manifest dependency missing')
    path = root/filename
    temporary = path.with_suffix('.tmp')
    write_json(temporary, manifest)
    os.replace(temporary, path)
    return manifest


def verify_manifest(root):
    manifest = read_json(root/'manifest.json')
    paths = [r['path'] for r in manifest['files']]
    if len(set(paths)) != len(paths):
        raise ValueError('Duplicate manifest path')
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != root/'manifest.json'}
    if set(paths) != actual:
        raise ValueError('Manifest missing files or contains unlisted artifacts')
    dependencies = {r['path']: r.get('dependencies', []) for r in manifest['files']}
    visited, visiting = set(), set()
    def visit(name):
        if name in visiting:
            raise ValueError('Manifest dependency cycle')
        if name in visited:
            return
        if name not in dependencies:
            raise ValueError('Manifest dependency missing')
        visiting.add(name)
        for dependency in dependencies[name]:
            visit(dependency)
        visiting.remove(name); visited.add(name)
    for name in paths:
        visit(name)
    for row in manifest['files']:
        p = root/row['path']
        if not p.resolve().is_relative_to(root.resolve()) or not p.is_file() or p.is_symlink():
            raise ValueError('Missing/unsafe artifact '+row['path'])
        data = p.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Artifact checksum mismatch '+row['path'])
    return manifest


def replay(root, output):
    manifest = verify_manifest(root)
    if output.exists():
        raise ValueError('Replay output must be new')
    versions_path = root/'config/source_software.json'
    if versions_path.exists():
        import importlib.metadata
        import platform
        current = {'python': platform.python_version(), 'packages': {name: importlib.metadata.version(name) for name in read_json(versions_path)['packages']}}
        if current != read_json(versions_path):
            raise ValueError('Replay software differs from frozen source environment')
    core_versions = root/'config/core_software.json'
    if core_versions.exists():
        cmd = ['/usr/bin/python3', '-c', 'import platform,json,pyproj;from osgeo import gdal;print(json.dumps({"python":platform.python_version(),"gdal":gdal.VersionInfo("RELEASE_NAME"),"pyproj":pyproj.__version__}))']
        current = json.loads(subprocess.check_output(cmd))
        if current != read_json(core_versions):
            raise ValueError('Replay core software differs from frozen environment')
    for row in manifest['files']:
        if row['path'].startswith('engine_source/'):
            current = REPO/'notebooks'/Path(row['path']).name
            if not current.is_file() or hashlib.sha256(current.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Recorded algorithm differs: '+str(current))
    output.mkdir(parents=True)
    shutil.copytree(root/'config', output/'config')
    shutil.copytree(root/'raw', output/'raw')
    # Block accidental source requests during replay, including future regressions.
    import requests
    import urllib.request
    from unittest.mock import patch
    with patch.object(requests.Session, 'request', side_effect=RuntimeError('NETWORK_FORBIDDEN_DURING_REPLAY')), patch.object(urllib.request, 'urlopen', side_effect=RuntimeError('NETWORK_FORBIDDEN_DURING_REPLAY')):
        build(output)
    compared, differences = [], []
    for row in manifest['files']:
        name = row['path']
        if name.startswith(('normalized/', 'graph/', 'connectors/', 'building_results/', 'diagnostics/')) or name in {'report.json', 'report.md'}:
            p = output/name
            matched = p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256']
            compared.append(name)
            if not matched:
                differences.append(name)
    result = {'status': 'PASS' if not differences else 'FAIL', 'compared': len(compared), 'differences': differences,
              'network_forbidden': True, 'source_manifest_sha256': hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()}
    write_json(output/'replay_verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['freeze', 'acquire', 'build', 'decide', 'manifest', 'replay', 'verify'])
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'replay':
        if args.output is None:
            parser.error('--output required for replay')
        result = replay(args.root, args.output)
    else:
        result = {'freeze': freeze, 'acquire': acquire, 'build': build, 'decide': decide, 'manifest': make_manifest, 'verify': verify_manifest}[args.command](args.root)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
