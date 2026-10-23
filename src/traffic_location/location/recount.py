from collections import Counter
import hashlib,json,math
from pathlib import Path
from ..artifacts import read as read_json,canonical as canonical_bytes,sha as digest
from .summary import capacity_groups
VERSION='LI5_OFFLINE_V1'
HERE=Path(__file__).resolve().parent
def engine_digest():
 from ..artifacts import semantic_hash
 return semantic_hash({p.name:digest(p) for p in sorted(HERE.iterdir()) if p.suffix in {'.py','.json'}})
def software_versions():
    import shapely, pyproj
    return {'shapely': shapely.__version__, 'geos': shapely.geos_version_string, 'pyproj': pyproj.__version__, 'proj': pyproj.proj_version_str}

def checked_policy(policy):
    expected = read_json(HERE / 'recount_policy.json')
    if set(policy) != set(expected) or any((policy[k] != expected[k] for k in expected if k not in {'predicate', 'policy_version'})):
        raise ValueError('Unsupported or implicit Recount policy')
    if policy['predicate'] not in {'covers', 'contains'} or not isinstance(policy['policy_version'], str) or (not policy['policy_version']):
        raise ValueError('Explicit predicate and version required')
    return policy

def validate_polygons(collection):
    from shapely.geometry import shape
    if collection.get('type') != 'FeatureCollection' or collection.get('schema_version') != 'li_recount_polygons_v1':
        raise ValueError('Explicit polygon collection schema required')
    if collection.get('crs') != 'EPSG:4326' or not collection.get('revision_id') or (not collection.get('claim_type')):
        raise ValueError('Polygon CRS/revision/claim required')
    ids = set()
    for f in collection['features']:
        pid = f['properties']['polygon_id']
        if not isinstance(pid, str) or not pid or pid in ids:
            raise ValueError('Missing/duplicate polygon ID')
        ids.add(pid)
        g = shape(f['geometry'])
        if g.geom_type not in {'Polygon', 'MultiPolygon'} or g.is_empty or (not g.is_valid):
            raise ValueError('Invalid polygon; no silent repair')
        for ring in rings(g):
            for xy in ring.coords:
                if len(xy) != 2 or not all((math.isfinite(x) for x in xy)) or (not -180 <= xy[0] <= 180) or (not -90 <= xy[1] <= 90):
                    raise ValueError('Invalid lon/lat polygon coordinate')
    return collection

def rings(g):
    for p in g.geoms if g.geom_type == 'MultiPolygon' else [g]:
        yield p.exterior
        yield from p.interiors

def evaluate(records, polygons, *, center, radius, predicate='covers'):
    """Metric-only membership core. Coverage is analytic disk, not source completeness."""
    from shapely.geometry import Point
    if predicate not in {'covers', 'contains'} or not math.isfinite(radius) or radius <= 0:
        raise ValueError('Invalid predicate/radius')
    indices = [r['source_row_index'] for r in records]
    if len(set(indices)) != len(indices):
        raise ValueError('Duplicate source row')
    keys = [r['building_key'] for r in records]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate building source key')
    if any((len(r['point_m']) != 2 or not all((math.isfinite(x) for x in r['point_m'])) for r in records)):
        raise ValueError('Invalid representative point')
    output, union = ({}, set())
    for pid, g in sorted(polygons.items()):
        if g.geom_type not in {'Polygon', 'MultiPolygon'} or not g.is_valid or g.is_empty:
            raise ValueError('Invalid polygon')
        inside = [r for r in records if getattr(g, predicate)(Point(r['point_m']))]
        indices = sorted((r['source_row_index'] for r in inside))
        union.update(indices)
        outside = any((math.hypot(x - center[0], y - center[1]) > radius for ring in rings(g) for x, y in ring.coords))
        output[pid] = {'source_row_indices': indices, 'coverage_status': 'PARTIAL_OUTSIDE_ANALYSIS_DOMAIN' if outside else 'WITHIN_FROZEN_ANALYSIS_DOMAIN', 'decision_counts': dict(sorted(Counter((r['decision_state'] for r in inside)).items())), 'capacity_by_decision_and_unit': capacity_groups(inside), 'mixed_unit_total': None}
    return (output, sorted(union))

def load_inputs(root):
    rows = read_json(root / 'input/buildings.json')
    selection = read_json(root / 'input/snapshot/building_results/selection.json')
    summary = read_json(root / 'input/summary.json')
    config = read_json(root / 'input/snapshot/config/pilot.json')
    indices = [r['source_row_index'] for r in rows]
    if sorted(indices) != list(range(summary['source_records'])):
        raise ValueError('Source row reconciliation failed')
    selected = {b['source_row_index']: b for b in selection['selected']}
    if len(selected) != len(selection['selected']) or set(selected) != {r['source_row_index'] for r in rows if r['selection_status'] == 'SELECTED'}:
        raise ValueError('Selected universe mismatch')
    if dict(sorted(Counter((r['decision_state'] for r in rows if r['selection_status'] == 'SELECTED')).items())) != summary['decision_counts_selected']:
        raise ValueError('Frozen decision reconciliation failed')
    return (rows, selected, summary, config)

def derive(root):
    from shapely.geometry import shape
    from shapely import transform as _transform

    def transform(fn, g):
        return _transform(g, fn, interleaved=False)
    from pyproj import Transformer
    root = Path(root)
    policy = checked_policy(read_json(root / 'policy.json'))
    fc = validate_polygons(read_json(root / 'polygons.geojson'))
    rows, selected, source, config = load_inputs(root)
    crs = config['policy']['li3']['metric_crs']
    tx = Transformer.from_crs(4326, crs, always_xy=True)
    target = config['policy']['li3']
    center = tx.transform(target['longitude'], target['latitude'])
    radius = read_json(root / 'input/snapshot/normalized/context.json')['config']['area_coverage']['parameters']['building_radius_m']['value']
    if radius != read_json(root / 'input_binding.json')['analysis_radius_m']:
        raise ValueError('Radius differs from source')
    records = []
    for r in rows:
        if r['source_row_index'] not in selected:
            continue
        b = selected[r['source_row_index']]
        if b['building_id'] != r['building_id']:
            raise ValueError('Building identity mismatch')
        key = b['building_key']
        point = tx.transform(*b['representative_point']['coordinates'])
        records.append({**r, 'building_key': json.dumps(key, sort_keys=True, separators=(',', ':')), 'point_m': point})
    metric = {f['properties']['polygon_id']: transform(tx.transform, shape(f['geometry'])) for f in fc['features']}
    groups, union = evaluate(records, metric, center=center, radius=radius, predicate=policy['predicate'])
    membership = {pid: set(g['source_row_indices']) for pid, g in groups.items()}
    ledger = []
    for row in rows:
        i = row['source_row_index']
        inside = sorted((pid for pid, ids in membership.items() if i in ids))
        ledger.append({**row, 'building_key': selected[i]['building_key'] if i in selected else None, 'membership_point': selected[i]['representative_point'] if i in selected else None, 'recount_evaluated': i in selected, 'polygon_ids': inside, 'in_union': bool(inside), 'membership_reason': 'EVALUATED_STORED_REPRESENTATIVE_POINT' if i in selected else 'OUTSIDE_SELECTED_UNIVERSE_NOT_EVALUATED'})
    union_rows = [r for r in rows if r['source_row_index'] in set(union)]
    input_hash = hashlib.sha256(canonical_bytes(read_json(root / 'input_binding.json'))).hexdigest()
    source_partial = source['analysis_status'] == 'PARTIAL'
    result = {'schema_version': 'li_recount_result_v1', 'engine_version': VERSION, 'engine_sha256': engine_digest(), 'software': software_versions(), 'policy': policy, 'result_version': hashlib.sha256(canonical_bytes({'inputs': input_hash, 'policy': policy, 'polygons': fc, 'engine': VERSION, 'engine_sha256': engine_digest(), 'software': software_versions()})).hexdigest(), 'input_fingerprint': input_hash, 'polygon_sha256': hashlib.sha256(canonical_bytes(fc)).hexdigest(), 'polygon_revision': fc['revision_id'], 'polygon_claim_type': fc['claim_type'], 'source_records': len(rows), 'evaluated_selected': len(records), 'not_evaluated_source_rows': len(rows) - len(records), 'analysis_status': 'PARTIAL' if source_partial or any((g['coverage_status'].startswith('PARTIAL') for g in groups.values())) else source['analysis_status'], 'source_analysis_status': source['analysis_status'], 'polygons': groups, 'union_source_row_indices': union, 'union_count': len(union), 'union_decision_counts': dict(sorted(Counter((r['decision_state'] for r in union_rows)).items())), 'union_capacity_by_decision_and_unit': capacity_groups(union_rows), 'mixed_unit_total': None, 'final_business_capacity': None, 'physical_access_validated': False, 'claim_type': 'OFFLINE_EXPERIMENT_NOT_APPROVED_BUSINESS_BOUNDARY', 'coverage_meaning': 'Geometric relation to frozen LI-1 analysis disk; not completeness of real buildings or permissions', 'no_retrieval_routing_or_capacity_recalculation': True, 'source_warnings': source['source_warnings']}
    previous = root / 'previous_result.json'
    delta = None
    if previous.exists():
        old = read_json(previous)
        if old['input_fingerprint'] != input_hash or old['policy'] != policy or old['engine_sha256'] != result['engine_sha256'] or (old['software'] != result['software']):
            raise ValueError('Delta requires same source and policy')
        if old['polygon_revision'] == fc['revision_id'] and old['polygon_sha256'] != result['polygon_sha256']:
            raise ValueError('Changed polygon requires new revision ID')
        delta = {'previous_result_version': old['result_version'], 'current_result_version': result['result_version'], 'polygons': {}}
        for pid in sorted(set(old['polygons']) | set(groups)):
            before = set(old['polygons'].get(pid, {}).get('source_row_indices', []))
            after = set(groups.get(pid, {}).get('source_row_indices', []))
            delta['polygons'][pid] = {'entered': sorted(after - before), 'exited': sorted(before - after)}
        before = set(old['union_source_row_indices'])
        after = set(union)
        delta['union'] = {'entered': sorted(after - before), 'exited': sorted(before - after)}
    return (result, ledger, delta)
