"""Replay a retained bounded Overture probe through LI-0/LI-1 and capacity.

No network. Templates and target are explicit inputs; uses a new output folder.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from location_intelligent_capacity import estimate_capacity
from location_intelligent_config import get_config
from location_intelligent_overture_probe import normalize
from location_intelligent_buildings import select_buildings
from location_intelligent_validator import canonical_hash, context_hash


def run(raw_path, context_template, manifest_template, out, longitude, latitude, partition_verification=None):
    if out.exists():
        raise ValueError('Use a new evidence directory')
    raw_bytes = raw_path.read_bytes()
    raw = json.loads(raw_bytes)
    coverage_proven = False
    proof_hash = None
    if partition_verification is not None:
        proof_bytes = partition_verification.read_bytes()
        proof = json.loads(proof_bytes)
        items = proof.get('items', [])
        bbox = raw['bbox']
        intersects = lambda b: b[0] <= bbox[2] and b[2] >= bbox[0] and b[1] <= bbox[3] and b[3] >= bbox[1]
        matches = {r['asset'] for r in items if 'bbox' in r and intersects(r['bbox'])}
        if (proof.get('release') != raw['release'] or proof.get('errors') or
            proof.get('items_checked') != len(items) or not items or
            len({r['url'] for r in items}) != len(items) or
            matches != {r['asset'] for r in raw['items']} or raw['truncated']):
            raise ValueError('Partition proof incomplete or does not match the bounded query')
        coverage_proven = True
        proof_hash = hashlib.sha256(proof_bytes).hexdigest()
    normalized = normalize(raw)
    out.mkdir(parents=True)
    def write(name, value):
        payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False).encode()
        (out / name).write_bytes(payload)
        return payload
    payload = write('buildings.geojson', normalized)
    context = deepcopy(json.loads(context_template.read_text()))
    manifest = deepcopy(json.loads(manifest_template.read_text()))
    context.update(analysis_run_id='li-overture-20261021-n1-technical-probe',
                   created_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    context['target'].update(longitude=longitude, latitude=latitude, store_code='N1-TECHNICAL-PILOT',
                             store_name='Owner-approved N1 technical location; not TGDI')
    context['context_hash'] = context_hash(context)
    manifest.update(analysis_run_id=context['analysis_run_id'], context_hash=context['context_hash'])
    source = manifest['sources'][0]
    source.update(source_ref_id='overture-bounded-probe', provider='OVERTURE_MAPS', locator='buildings.geojson',
                  acquisition_mode='LIVE_ACQUIRED', availability='AVAILABLE', source_version=raw['release'],
                  acquired_at=context['created_at'], source_as_of=None,
                  byte_count=len(payload), row_count=len(normalized['features']),
                  fingerprint={'algorithm': 'sha256', 'value': hashlib.sha256(payload).hexdigest()},
                  coverage={'completeness': 'COMPLETE' if coverage_proven else 'PARTIAL', 'scope': 'Complete bounded query only after all STAC partition bboxes verified; bbox=' + str(raw['bbox']) + '; not physical building completeness'},
                  provenance={'origin': 'LIVE_ACQUIRED', 'description': 'Normalized actual Overture WKB, class/subtype and source attributes; original probe SHA256=' + hashlib.sha256(raw_bytes).hexdigest(), 'dependencies': []},
                  unknown_reasons={'source_as_of': 'Release date known; per-feature observation vintage varies'})
    for module in manifest['modules']:
        module.update(analysis_run_id=context['analysis_run_id'], context_hash=context['context_hash'],
                      config_hash=canonical_hash(context['config']), required_inputs=['overture-bounded-probe'])
    write('context.json', context)
    write('manifest.json', manifest)
    policy = get_config()
    write('policy.json', policy)
    selection = select_buildings(context, manifest, root=out, source_ref_id=source['source_ref_id'])
    write('selection.json', selection)
    capacity = estimate_capacity(selection, policy) if selection['status'] in {'SUCCEEDED', 'PARTIAL'} else None
    write('capacity.json', capacity)
    report = {'raw_probe_sha256': hashlib.sha256(raw_bytes).hexdigest(), 'raw_probe_rows': len(raw['rows']),
              'raw_probe_truncated': raw['truncated'], 'release': raw['release'], 'provider_schema_version': raw['schema_version'],
              'schema_validation_scope': raw['schema_validation_scope'],
              'selection_status': selection['status'], 'selection_summary': selection['summary'],
              'capacity_status': capacity['status'] if capacity else 'BLOCKED',
              'capacity_by_unit': capacity['summary_by_unit'] if capacity else None,
              'observed_height_count': sum(row['height'] is not None for row in raw['rows']),
              'observed_num_floors_count': sum(row['num_floors'] is not None for row in raw['rows']),
              'null_subtype_selected_count': sum(row['subclass'] is None for row in selection['selected']),
              'bounded_acquisition_scope_complete': coverage_proven, 'partition_verification_sha256': proof_hash,
              'spatial_completeness_verified': False, 'motor_routing_executed_on_real_graph': False,
              'limitations': ['N1 technical location only, not TGDI', 'Provider critical columns/types validated; not exhaustive official JSON Schema validation', 'Null-subtype legacy residential fallback is not positive residential classification', 'Capacity estimates are split reference units, not observed population or final business demand']}
    write('report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['raw', 'context-template', 'manifest-template', 'output']:
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--longitude', required=True, type=float)
    parser.add_argument('--latitude', required=True, type=float)
    parser.add_argument('--partition-verification', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.raw, args.context_template, args.manifest_template, args.output, args.longitude, args.latitude, args.partition_verification), sort_keys=True))
