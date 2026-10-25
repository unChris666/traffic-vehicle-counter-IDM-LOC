"""System-Python worker reusing LI-0/LI-1/capacity/motor; no network calls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from location_intelligent_buildings import select_buildings, _backend, _spatial
from location_intelligent_capacity import estimate_capacity
from location_intelligent_motor_routing import route_motor_buildings
from location_intelligent_validator import canonical_hash, context_hash
from location_intelligent_li3_sources import read_json, write_json


def prepare(root):
    frozen = read_json(root/'config/pilot.json')
    cache = root/'raw/building_cache'
    for original, expected in frozen['building_cache_files'].items():
        p = cache/Path(original).name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('Retained building cache changed: '+str(p))
    context = read_json(cache/'context.json')
    manifest = read_json(cache/'manifest.json')
    # The retained source packet includes raw WKB and the bounded-query proof.
    # Verify content/code/runtime-bound normalization; old packets recompute.
    raw = read_json(cache/'raw_probe.json.gz')
    planned = frozen['policy']['sources']['buildings']
    if raw['release'] != planned['planned_release'] or raw['schema_version'] != planned['planned_schema_version']:
        raise ValueError('Cached building release/schema differs from frozen source plan')
    target = context['target']; pilot = frozen['policy']['li3']
    if target['longitude'] != pilot['longitude'] or target['latitude'] != pilot['latitude'] or context['config']['area_coverage']['metric_crs'] != pilot['metric_crs']:
        raise ValueError('Building cache target/CRS differs from approved pilot')
    from location_intelligent_osm_buildings import cached_normalization
    import contextlib,sys
    with contextlib.redirect_stdout(sys.stderr):
        normalized,_ = cached_normalization(raw,cache/'normalization_cache.json',write=False)
    old = read_json(cache/'buildings.geojson')
    if normalized != old:
        raise ValueError('Cached normalized building data differs from retained raw source')
    payload = normalized
    write_json(root/'normalized/buildings.geojson', payload)
    context.update(analysis_run_id=frozen['analysis_run_id'], created_at=frozen['frozen_at'])
    context['context_hash'] = context_hash(context)
    manifest.update(analysis_run_id=context['analysis_run_id'], context_hash=context['context_hash'])
    source = manifest['sources'][0]
    data = (root/'normalized/buildings.geojson').read_bytes()
    source.update(locator='normalized/buildings.geojson', acquisition_mode='OFFLINE_SNAPSHOT',
                  byte_count=len(data), fingerprint={'algorithm': 'sha256', 'value': hashlib.sha256(data).hexdigest()},
                  provenance={'origin': 'OFFLINE_SNAPSHOT', 'description': 'Verified raw building snapshot; provider/version retained under raw/building_cache', 'dependencies': []})
    for module in manifest['modules']:
        module.update(analysis_run_id=context['analysis_run_id'], context_hash=context['context_hash'], config_hash=canonical_hash(context['config']))
    write_json(root/'normalized/context.json', context)
    write_json(root/'normalized/input_manifest.json', manifest)
    result = select_buildings(context, manifest, root=root, source_ref_id=source['source_ref_id'])
    write_json(root/'building_results/selection.json', result)
    if result['status'] not in {'SUCCEEDED', 'PARTIAL'}:
        raise ValueError('LI-1 selection blocked: '+str(result['diagnostics']))
    capacity = estimate_capacity(result, frozen['policy'])
    write_json(root/'building_results/capacity.json', capacity)
    _, ogr, osr = _backend()
    with osr.ExceptionMgr(useExceptions=True):
        tx, target = _spatial(frozen['policy']['li3']['metric_crs'], context['target'], ogr, osr)
        all_buildings = []
        for feature in payload['features']:
            g = ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
            if g is None or not g.IsValid():
                continue
            if g.Transform(tx) != 0:
                raise ValueError('Building metric transform failed')
            all_buildings.append({'building_id': feature['properties']['building_id'], 'metric_geometry': json.loads(g.ExportToJson())})
        selected = []
        for b in result['selected']:
            coords = tx.TransformPoint(*b['representative_point']['coordinates'])[:2]
            selected.append({'building_id': b['building_id'], 'representative_point_m': list(coords)})
        metrics = {'target_xy': [target.GetX(), target.GetY()], 'all_buildings': sorted(all_buildings, key=lambda b: b['building_id']),
                   'selected_buildings': sorted(selected, key=lambda b: b['building_id'])}
    write_json(root/'normalized/metric_buildings.json', metrics)
    return {'selection': result['summary'], 'capacity': capacity['summary_by_unit']}


def route(root):
    frozen = read_json(root/'config/pilot.json')
    selection = read_json(root/'building_results/selection.json')
    context = read_json(root/'normalized/context.json')
    manifest = read_json(root/'normalized/input_manifest.json')
    graph = read_json(root/'graph/graph.json.gz')
    evidence = read_json(root/'connectors/evidence.json.gz')
    result = route_motor_buildings(context, manifest, selection, graph, evidence, root=root, policy=frozen['policy'])
    write_json(root/'building_results/routing.json.gz', result)
    return {'status': result['status'], 'summary': result['summary'], 'diagnostics': result['diagnostics']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['prepare', 'route'])
    p.add_argument('--root', required=True, type=Path)
    a = p.parse_args()
    result = prepare(a.root) if a.stage == 'prepare' else route(a.root)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
