"""LI-0: read-only JSON contract validation; standard library, no engine imports.

Canonical contract: docs/AREA_COVERAGE_DATA_CONTRACT.md (LI-0 v1).
READY means the local input gate for LI-1 building selection, not calculation,
geographic coverage, live access, capacity semantics or production validation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from graphlib import CycleError, TopologicalSorter
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any
SCHEMA = 'location_intelligent_v1'
RESULT_SCHEMA = 'location_intelligent_validation_v1'
ID = re.compile('[A-Za-z0-9_-]+\\Z')
SHA256 = re.compile('[0-9a-f]{64}\\Z')
AVAILABILITY = {'NOT_ATTEMPTED', 'UNAVAILABLE', 'REQUEST_FAILED', 'AVAILABLE_EMPTY', 'AVAILABLE', 'PARTIAL'}
STATUSES = {'NOT_RUN', 'RUNNING', 'BLOCKED', 'SUCCEEDED', 'SUCCEEDED_WITH_WARNINGS', 'PARTIAL', 'FAILED', 'STALE'}
LAYERS = {'RAW', 'NORMALIZED', 'FROZEN', 'DERIVED_GEOSPATIAL', 'TRAFFIC_MACHINE', 'REVIEWED', 'PPAC_FEATURES', 'PPAC_RESULT'}
POSITIVE = {'building_radius_m': 'm', 'min_area_m2': 'm2', 'max_area_m2': 'm2', 'apartment_average_unit_area_m2': 'm2', 'dormitory_average_room_area_m2': 'm2', 'hotel_average_room_area_m2': 'm2', 'default_floor_height_m': 'm', 'max_building_to_road_m': 'm', 'max_travel_min': 'min', 'motorcycle_speed_kmh': 'km/h', 'network_radius_m': 'm', 'hotel_average_guests_per_room': 'guest/room', 'standard_residential_household': 'legacy_unknown'}
RATIOS = {'standard_residential_occupancy', 'apartment_net_floor_ratio', 'apartment_occupancy', 'dormitory_net_floor_ratio', 'dormitory_occupancy', 'hotel_net_floor_ratio', 'hotel_occupancy'}
REQUIRED_PARAMETERS = {'building_radius_m', 'min_area_m2', 'max_area_m2'}

def canonical_hash(value: Any) -> str:
    """Python JSON v1: sorted keys, compact, UTF-8, no nonfinite numbers."""
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def context_hash(context: dict) -> str:
    return canonical_hash({key: value for key, value in context.items() if key != 'context_hash'})

def _number(value: Any) -> bool:
    return type(value) in (int, float) and (type(value) is int or math.isfinite(value))

def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())

def _strict_pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key')
        result[key] = value
    return result

def _reject_constant(value: str) -> None:
    raise ValueError('Nonfinite JSON constant')

class _Validator:

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.diagnostics: list[dict] = []
        self.verified_sources: set[str] = set()

    def issue(self, code: str, path: str, message: str, severity: str='ERROR', blocking: bool=True) -> None:
        self.diagnostics.append(dict(code=code, path=path, severity=severity, blocking=blocking, message=message))

    def obj(self, value: Any, path: str, required: str, optional: str='') -> dict:
        if not isinstance(value, dict):
            self.issue('TYPE_OBJECT', path, 'Supply a JSON object.')
            return {}
        req, opt = (set(required.split()), set(optional.split()))
        for key in sorted(req - value.keys()):
            self.issue('FIELD_REQUIRED', f'{path}.{key}', 'Supply the required field; do not substitute a default.')
        for key in sorted(value.keys() - req - opt):
            self.issue('FIELD_UNKNOWN', f'{path}.{key}', 'Use a field defined by this schema version.')
        return value

    def text(self, value: Any, path: str) -> bool:
        if not _text(value):
            self.issue('TYPE_STRING', path, 'Supply a nonempty string.')
            return False
        return True

    def identifier(self, value: Any, path: str) -> bool:
        if not isinstance(value, str) or not ID.fullmatch(value):
            self.issue('ID_INVALID', path, 'Use a nonempty path-safe ID containing only letters, digits, _ or -.')
            return False
        return True

    def enum(self, value: Any, allowed: set, path: str) -> bool:
        if not isinstance(value, str) or value not in allowed:
            self.issue('ENUM_INVALID', path, 'Use an explicitly supported value from the canonical contract.')
            return False
        return True

    def array(self, value: Any, path: str) -> list:
        if not isinstance(value, list):
            self.issue('TYPE_ARRAY', path, 'Supply a JSON array.')
            return []
        return value

    def strings(self, value: Any, path: str) -> list[str]:
        items = self.array(value, path)
        valid = []
        for index, item in enumerate(items):
            if self.text(item, f'{path}[{index}]'):
                valid.append(item)
        if len(set(valid)) != len(valid):
            self.issue('REFERENCE_DUPLICATE', path, 'Remove duplicate references.')
        return valid

    def stamp(self, value: Any, path: str) -> datetime | None:
        try:
            if not isinstance(value, str) or 'T' not in value:
                raise ValueError
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if stamp.utcoffset() != timezone.utc.utcoffset(stamp):
                raise ValueError
            return stamp
        except (ValueError, TypeError, OverflowError):
            self.issue('TIMESTAMP_INVALID', path, 'Supply an ISO8601 UTC timestamp with timezone.')
            return None

    def digest(self, value: Any, path: str) -> bool:
        if not isinstance(value, str) or not SHA256.fullmatch(value):
            self.issue('CHECKSUM_INVALID', path, 'Supply a lowercase 64-digit SHA256 digest.')
            return False
        return True

    def fingerprint(self, value: Any, byte_count: Any, path: str) -> bool:
        fp = self.obj(value, f'{path}.fingerprint', 'algorithm value')
        valid = self.digest(fp.get('value'), f'{path}.fingerprint.value')
        if fp.get('algorithm') != 'sha256':
            self.issue('CHECKSUM_ALGORITHM', f'{path}.fingerprint.algorithm', 'Only sha256 is supported in v1.')
            valid = False
        if type(byte_count) is not int or byte_count < 0:
            self.issue('BYTE_COUNT_INVALID', f'{path}.byte_count', 'Supply an explicit nonnegative integer byte count.')
            valid = False
        return valid

    def unknown(self, data: dict, key: str, path: str, *, blocking: bool) -> None:
        reasons = data.get('unknown_reasons')
        if not isinstance(reasons, dict) or not _text(reasons.get(key)):
            self.issue('UNKNOWN_REASON_REQUIRED', f'{path}.unknown_reasons.{key}', 'Explain the explicitly unknown field.')
        self.issue('VALUE_UNKNOWN', f'{path}.{key}', 'Value remains unknown; supply evidence before using it.', 'UNKNOWN', blocking)

    def reasons(self, value: Any, path: str) -> None:
        if not isinstance(value, dict) or not all((_text(k) and _text(v) for k, v in value.items())):
            self.issue('UNKNOWN_REASONS_INVALID', path, 'Supply a mapping of unknown field names to nonempty reasons.')

    def json_values(self, value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key in sorted(value, key=str):
                if not isinstance(key, str):
                    self.issue('JSON_KEY_INVALID', path, 'JSON object keys must be strings.')
                    continue
                try:
                    key.encode('utf-8')
                except UnicodeError:
                    self.issue('JSON_STRING_INVALID', path, 'JSON keys must be encodable as valid UTF-8 Unicode.')
                    continue
                self.json_values(value[key], f'{path}.{key}')
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self.json_values(child, f'{path}[{index}]')
        elif value is not None and type(value) not in (str, bool, int, float):
            self.issue('JSON_VALUE_INVALID', path, 'Supply a JSON-compatible value.')
        elif type(value) is float and (not math.isfinite(value)):
            self.issue('NUMBER_NONFINITE', path, 'Replace NaN/Infinity with explicit null and a reason.')
        elif isinstance(value, str):
            try:
                value.encode('utf-8')
            except UnicodeError:
                self.issue('JSON_STRING_INVALID', path, 'Supply valid Unicode before computing canonical UTF-8 hashes.')

    def config(self, value: Any) -> None:
        cfg = self.obj(value, 'context.config', 'version area_coverage')
        self.text(cfg.get('version'), 'context.config.version')
        area = self.obj(cfg.get('area_coverage'), 'context.config.area_coverage', 'parameters metric_crs unresolved_decisions')
        crs = area.get('metric_crs')
        if crs is None:
            self.issue('METRIC_CRS_REQUIRED', 'context.config.area_coverage.metric_crs', 'Select an explicit supported metric CRS before calculation.', 'BLOCKER')
        elif not isinstance(crs, str) or not re.fullmatch('EPSG:32[67](0[1-9]|[1-5][0-9]|60)', crs):
            self.issue('METRIC_CRS_UNSUPPORTED', 'context.config.area_coverage.metric_crs', 'LI-0 v1 supports explicit WGS84 UTM EPSG:32601–32660/32701–32760 only.')
        decisions = self.strings(area.get('unresolved_decisions'), 'context.config.area_coverage.unresolved_decisions')
        if decisions:
            self.issue('POLICY_UNRESOLVED', 'context.config.area_coverage.unresolved_decisions', 'Resolve the listed decisions for the declared calculation scope.', 'BLOCKER')
        params = area.get('parameters')
        if not isinstance(params, dict):
            self.issue('TYPE_OBJECT', 'context.config.area_coverage.parameters', 'Supply parameter quantities.')
            return
        for key in sorted(REQUIRED_PARAMETERS - params.keys()):
            self.issue('CONFIG_REQUIRED', f'context.config.area_coverage.parameters.{key}', 'Supply the explicit reference parameter and unit.', 'BLOCKER')
        values = {}
        for key in sorted(params):
            path = f'context.config.area_coverage.parameters.{key}'
            if key not in POSITIVE and key not in RATIOS:
                self.issue('CONFIG_UNSUPPORTED', path, 'This LI-0 version does not validate this parameter; do not silently ignore it.')
                continue
            q = self.obj(params[key], path, 'value unit', 'unknown_reason')
            if 'unknown_reason' in q:
                self.text(q['unknown_reason'], f'{path}.unknown_reason')
            expected = POSITIVE.get(key, 'ratio')
            if q.get('unit') != expected:
                self.issue('UNIT_INVALID', f'{path}.unit', f'Use the canonical unit {expected}.')
            val = q.get('value')
            if val is None:
                if not _text(q.get('unknown_reason')):
                    self.issue('UNKNOWN_REASON_REQUIRED', path, 'Explain the missing parameter value.')
                self.issue('CONFIG_UNKNOWN', path, 'Supply the parameter before calculation; no default is applied.', 'UNKNOWN')
            elif not _number(val):
                self.issue('TYPE_NUMBER', f'{path}.value', 'Supply a finite number; bool and numeric strings are invalid.')
            elif key in RATIOS and (not 0 <= val <= 1) or (key in POSITIVE and val <= 0):
                self.issue('CONFIG_RANGE', f'{path}.value', 'Use a positive quantity or a ratio within [0,1], as applicable.')
            else:
                values[key] = val
        if 'min_area_m2' in values and 'max_area_m2' in values and (values['min_area_m2'] >= values['max_area_m2']):
            self.issue('CONFIG_ORDER', 'context.config.area_coverage.parameters', 'min_area_m2 must be less than max_area_m2.')
        if 'standard_residential_household' in params:
            self.issue('CAPACITY_UNIT_UNRESOLVED', 'context.config.area_coverage.parameters.standard_residential_household', 'Legacy mixed capacity is not an approved household/resident unit.', 'WARNING', False)

    def context(self, value: Any) -> dict:
        c = self.obj(value, 'context', 'schema_version analysis_run_id parent_analysis_run_id created_at target config context_hash')
        if c.get('schema_version') != SCHEMA:
            self.issue('SCHEMA_UNSUPPORTED', 'context.schema_version', f'Use {SCHEMA}.')
        self.identifier(c.get('analysis_run_id'), 'context.analysis_run_id')
        if c.get('parent_analysis_run_id') is not None:
            self.identifier(c['parent_analysis_run_id'], 'context.parent_analysis_run_id')
            if c['parent_analysis_run_id'] == c.get('analysis_run_id'):
                self.issue('PARENT_SELF', 'context.parent_analysis_run_id', 'A revision cannot be its own parent.')
        self.stamp(c.get('created_at'), 'context.created_at')
        target = self.obj(c.get('target'), 'context.target', 'store_code store_name latitude longitude crs unknown_reasons')
        self.reasons(target.get('unknown_reasons'), 'context.target.unknown_reasons')
        for key in ('store_code', 'store_name'):
            if target.get(key) is None:
                self.unknown(target, key, 'context.target', blocking=False)
            else:
                self.text(target[key], f'context.target.{key}')
        if target.get('crs') != 'EPSG:4326':
            self.issue('CRS_INVALID', 'context.target.crs', 'Declare target coordinates as EPSG:4326; do not infer axis order.')
        lat, lon = (target.get('latitude'), target.get('longitude'))
        if (lat is None) != (lon is None):
            self.issue('COORDINATE_PAIR', 'context.target', 'Supply both coordinates or explicitly mark both unknown.')
        for key, limit in (('latitude', 90), ('longitude', 180)):
            v = target.get(key)
            if v is None:
                self.unknown(target, key, 'context.target', blocking=True)
            elif not _number(v):
                self.issue('TYPE_NUMBER', f'context.target.{key}', 'Supply a finite number; bool and strings are invalid.')
            elif not -limit <= v <= limit:
                self.issue('COORDINATE_RANGE', f'context.target.{key}', 'Use the documented geographic coordinate range.')
        self.config(c.get('config'))
        cfg = c.get('config')
        area = cfg.get('area_coverage') if isinstance(cfg, dict) else None
        crs = area.get('metric_crs') if isinstance(area, dict) else None
        if _number(lat) and _number(lon) and isinstance(crs, str) and re.fullmatch('EPSG:32[67](0[1-9]|[1-5][0-9]|60)', crs):
            zone, south = (int(crs[-2:]), crs.startswith('EPSG:327'))
            if not (-80 <= lat <= 84 and (lat <= 0 if south else lat >= 0) and (-180 + 6 * (zone - 1) <= lon <= -180 + 6 * zone)):
                self.issue('METRIC_CRS_DOMAIN', 'context.config.area_coverage.metric_crs', 'Target lies outside the declared UTM zone/hemisphere domain; select/review CRS explicitly.')
        if self.digest(c.get('context_hash'), 'context.context_hash'):
            try:
                actual = context_hash(c)
            except (TypeError, ValueError, OverflowError):
                actual = None
            if actual is not None and actual != c['context_hash']:
                self.issue('CONTEXT_HASH_MISMATCH', 'context.context_hash', 'Recompute the context hash after an intentional revision.')
        return c

    def local_file(self, locator: Any, fingerprint: Any, byte_count: Any, path: str, *, historical: bool=False) -> bool:
        if not self.fingerprint(fingerprint, byte_count, path):
            return False
        if not self.text(locator, f'{path}.path'):
            return False
        raw = PurePosixPath(locator)
        if '\\' in locator or ':' in locator or '..' in raw.parts or (raw.is_absolute() and (not historical)):
            self.issue('PATH_UNSAFE', f'{path}.path', 'Use a confined relative path; historical sources may explicitly use an absolute local path.')
            return False
        candidate = Path(locator) if raw.is_absolute() else self.root / locator
        try:
            resolved = candidate.resolve()
            if not raw.is_absolute() and (not resolved.is_relative_to(self.root)):
                self.issue('PATH_ESCAPE', f'{path}.path', 'The resolved path or symlink must remain inside the input root.')
                return False
            if not resolved.is_file():
                self.issue('LOCAL_FILE_MISSING', path, 'Supply the referenced regular file; no fetch or stub is created.', 'BLOCKER')
                return False
            with resolved.open('rb') as stream:
                digest = hashlib.sha256()
                size = 0
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    size += len(chunk)
                    digest.update(chunk)
            if size != byte_count or digest.hexdigest() != fingerprint['value']:
                self.issue('FILE_FINGERPRINT_MISMATCH', path, 'Verify file identity/byte count and provide the matching immutable reference.')
                return False
            return True
        except (OSError, RuntimeError, ValueError):
            self.issue('LOCAL_READ_FAILED', path, 'Check the local path and read permission; no network fallback is attempted.')
            return False

    def source(self, value: Any, path: str) -> dict:
        s = self.obj(value, path, 'source_ref_id inventory_id kind provider locator acquisition_mode availability source_version source_as_of acquired_at schema_version fingerprint byte_count row_count coverage crs units provenance unknown_reasons', 'auth_ref local_path freshness freshness_policy_ref')
        self.reasons(s.get('unknown_reasons'), f'{path}.unknown_reasons')
        self.identifier(s.get('source_ref_id'), f'{path}.source_ref_id')
        self.enum(s.get('inventory_id'), {f'SRC{x:02d}' for x in range(1, 14)}, f'{path}.inventory_id')
        self.enum(s.get('kind'), {'BIGQUERY', 'OBJECT_STORAGE', 'API', 'LOCAL_FILE'}, f'{path}.kind')
        self.enum(s.get('acquisition_mode'), {'LIVE_ACQUIRED', 'OFFLINE_SNAPSHOT', 'SYNTHETIC_FIXTURE'}, f'{path}.acquisition_mode')
        available = s.get('availability') in ('AVAILABLE', 'AVAILABLE_EMPTY')
        if s.get('availability') is None:
            self.unknown(s, 'availability', path, blocking=True)
        else:
            self.enum(s.get('availability'), AVAILABILITY, f'{path}.availability')
        for key in ('provider', 'locator', 'source_version', 'source_as_of', 'acquired_at', 'schema_version', 'crs', 'units'):
            v = s.get(key)
            if v is None:
                self.unknown(s, key, path, blocking=available and key in {'schema_version', 'crs', 'units', 'acquired_at'})
            elif key in {'source_as_of', 'acquired_at'}:
                self.stamp(v, f'{path}.{key}')
            elif key == 'units':
                if not isinstance(v, dict) or not v or (not all((_text(k) and _text(x) for k, x in v.items()))):
                    self.issue('UNITS_INVALID', f'{path}.units', 'Supply a nonempty mapping from field to explicit unit.')
            else:
                self.text(v, f'{path}.{key}')
        prov = self.obj(s.get('provenance'), f'{path}.provenance', 'origin description dependencies')
        self.enum(prov.get('origin'), {'LIVE_ACQUIRED', 'OFFLINE_SNAPSHOT', 'SYNTHETIC_FIXTURE'}, f'{path}.provenance.origin')
        if prov.get('origin') != s.get('acquisition_mode'):
            self.issue('PROVENANCE_MODE_MISMATCH', f'{path}.provenance.origin', 'Match provenance origin to the declared acquisition mode.')
        self.text(prov.get('description'), f'{path}.provenance.description')
        self.strings(prov.get('dependencies'), f'{path}.provenance.dependencies')
        for key in ('auth_ref', 'local_path'):
            if key in s:
                self.text(s[key], f'{path}.{key}')
        freshness = s.get('freshness')
        if freshness is None or freshness == 'UNKNOWN':
            self.issue('FRESHNESS_UNKNOWN', path, 'Freshness is unverified; offline does not automatically mean stale.', 'UNKNOWN', False)
        elif self.enum(freshness, {'WITHIN_POLICY', 'STALE_FOR_POLICY'}, f'{path}.freshness'):
            self.text(s.get('freshness_policy_ref'), f'{path}.freshness_policy_ref')
            if freshness == 'STALE_FOR_POLICY':
                self.issue('SOURCE_STALE', path, 'Select input permitted by the declared freshness policy.', 'BLOCKER')
        coverage = s.get('coverage')
        if coverage is None:
            self.unknown(s, 'coverage', path, blocking=available)
        else:
            cov = self.obj(coverage, f'{path}.coverage', 'scope completeness')
            self.text(cov.get('scope'), f'{path}.coverage.scope')
            self.enum(cov.get('completeness'), {'COMPLETE', 'PARTIAL', 'UNKNOWN'}, f'{path}.coverage.completeness')
            if available and cov.get('completeness') != 'COMPLETE':
                self.issue('SOURCE_COVERAGE_INCOMPLETE', path, 'Resolve partial/unknown coverage before the offline input gate.', 'BLOCKER')
        count = s.get('row_count')
        if s.get('availability') in ('NOT_ATTEMPTED', 'UNAVAILABLE', 'REQUEST_FAILED') or s.get('availability') is None:
            if count is not None:
                self.issue('ROW_COUNT_UNOBSERVED', f'{path}.row_count', 'Keep unobserved row_count null; unavailable/failed is not zero.')
        elif type(count) is not int or count < 0:
            self.issue('ROW_COUNT_INVALID', f'{path}.row_count', 'Supply an observed nonnegative integer row count.')
        elif s.get('availability') == 'AVAILABLE_EMPTY' and count != 0 or (s.get('availability') == 'AVAILABLE' and count == 0):
            self.issue('EMPTY_STATUS_MISMATCH', f'{path}.row_count', 'Use AVAILABLE_EMPTY for an observed successful zero-row result.')
        if available:
            local = s.get('local_path') or (s.get('locator') if s.get('kind') == 'LOCAL_FILE' else None)
            if local is None:
                self.issue('SOURCE_NOT_LOCAL', path, 'Provide a checksummed local snapshot; remote locators are never fetched.', 'BLOCKER')
                self.fingerprint(s.get('fingerprint'), s.get('byte_count'), path)
            elif self.local_file(local, s.get('fingerprint'), s.get('byte_count'), path, historical=True):
                if isinstance(s.get('source_ref_id'), str):
                    self.verified_sources.add(s['source_ref_id'])
        elif s.get('availability') in ('NOT_ATTEMPTED', 'UNAVAILABLE', 'REQUEST_FAILED') or s.get('availability') is None:
            if s.get('fingerprint') is not None or s.get('byte_count') is not None:
                self.issue('FINGERPRINT_UNOBSERVED', path, 'Unobserved sources must keep fingerprint/byte_count null; retain prior artifacts as separate snapshot references.')
        elif s.get('availability') == 'PARTIAL' and (s.get('fingerprint') is not None or s.get('byte_count') is not None):
            self.fingerprint(s.get('fingerprint'), s.get('byte_count'), path)
        return s

    def records(self, value: Any, path: str, id_key: str) -> dict:
        result = {}
        for index, item in enumerate(self.array(value, path)):
            key = item.get(id_key) if isinstance(item, dict) else None
            if self.identifier(key, f'{path}[{index}].{id_key}'):
                if key in result:
                    self.issue('ID_DUPLICATE', f'{path}[{index}].{id_key}', 'Use unique identifiers within the manifest.')
                result[key] = item
        return result

    def manifest(self, value: Any, c: dict) -> None:
        m = self.obj(value, 'manifest', 'schema_version analysis_run_id context_hash sources modules artifacts')
        if m.get('schema_version') != SCHEMA:
            self.issue('SCHEMA_UNSUPPORTED', 'manifest.schema_version', f'Use {SCHEMA}.')
        for key in ('analysis_run_id', 'context_hash'):
            if m.get(key) != c.get(key):
                self.issue('CONTEXT_BINDING_MISMATCH', f'manifest.{key}', 'Bind the manifest to the supplied immutable context.')
        self.identifier(m.get('analysis_run_id'), 'manifest.analysis_run_id')
        self.digest(m.get('context_hash'), 'manifest.context_hash')
        sources = self.records(m.get('sources'), 'manifest.sources', 'source_ref_id')
        modules = self.records(m.get('modules'), 'manifest.modules', 'module_run_id')
        artifacts = self.records(m.get('artifacts'), 'manifest.artifacts', 'artifact_id')
        if sources.keys() & artifacts.keys():
            self.issue('REFERENCE_NAMESPACE_COLLISION', 'manifest', 'Use distinct source and artifact IDs to keep dependency references unambiguous.')
        area_required = set()
        for r in modules.values():
            if r.get('module') == 'area_coverage' and isinstance(r.get('required_inputs'), list):
                area_required.update((x for x in r['required_inputs'] if isinstance(x, str)))
        inventories = set()
        for index, value in enumerate(self.array(m.get('sources'), 'manifest.sources')):
            start = len(self.diagnostics)
            s = self.source(value, f'manifest.sources[{index}]')
            required = isinstance(s.get('source_ref_id'), str) and s['source_ref_id'] in area_required
            if not required:
                for d in self.diagnostics[start:]:
                    if d['severity'] != 'ERROR':
                        d['blocking'] = False
                        if d['severity'] == 'BLOCKER':
                            d['severity'] = 'WARNING'
            if required and s.get('inventory_id') == 'SRC04':
                if isinstance(s.get('source_ref_id'), str) and s['source_ref_id'] in self.verified_sources:
                    inventories.add('SRC04')
                if s.get('availability') not in ('AVAILABLE', 'AVAILABLE_EMPTY'):
                    self.issue('REQUIRED_SOURCE_UNAVAILABLE', f'manifest.sources[{index}]', 'Building source is not available; preserve its status instead of zero.', 'BLOCKER')
            prov = s.get('provenance')
            deps = prov.get('dependencies') if isinstance(prov, dict) else None
            if isinstance(deps, list):
                for ref in deps:
                    if isinstance(ref, str) and (ref not in sources or ref == s.get('source_ref_id')):
                        self.issue('SOURCE_DEPENDENCY_INVALID', f'manifest.sources[{index}].provenance.dependencies', 'Reference another declared source.')
        if 'SRC04' not in inventories:
            self.issue('BUILDINGS_SNAPSHOT_REQUIRED', 'manifest.sources', 'Provide a verifiable local SRC04 buildings snapshot for LI-1.', 'BLOCKER')
        area_runs = []
        for index, value in enumerate(self.array(m.get('modules'), 'manifest.modules')):
            p = f'manifest.modules[{index}]'
            r = self.obj(value, p, 'module_run_id module analysis_run_id context_hash config_hash status required_inputs artifact_refs started_at finished_at engine error')
            self.enum(r.get('module'), {'area_coverage', 'traffic_counter', 'recount', 'ppac'}, f'{p}.module')
            self.enum(r.get('status'), STATUSES, f'{p}.status')
            if r.get('module') == 'area_coverage':
                area_runs.append(r)
            for key in ('analysis_run_id', 'context_hash'):
                if r.get(key) != c.get(key):
                    self.issue('CONTEXT_BINDING_MISMATCH', f'{p}.{key}', 'Match module identity to this context.')
            if self.digest(r.get('config_hash'), f'{p}.config_hash'):
                try:
                    expected = canonical_hash(c.get('config'))
                except (TypeError, ValueError, OverflowError):
                    expected = None
                if expected is not None and expected != r['config_hash']:
                    self.issue('CONFIG_HASH_MISMATCH', f'{p}.config_hash', 'Bind the module to the supplied configuration hash.')
            required = self.strings(r.get('required_inputs'), f'{p}.required_inputs')
            stage_required = r.get('module') == 'area_coverage'
            for ref in required:
                if ref not in sources:
                    self.issue('SOURCE_REF_MISSING', f'{p}.required_inputs', 'Declare each required source reference.', 'BLOCKER' if stage_required else 'WARNING', stage_required)
                elif ref not in self.verified_sources:
                    self.issue('MODULE_SOURCE_NOT_VERIFIED', f'{p}.required_inputs', 'Supply the required local file and verify its fingerprint.', 'BLOCKER' if stage_required else 'WARNING', stage_required)
            if r.get('module') == 'area_coverage' and (not any((sources.get(ref, {}).get('inventory_id') == 'SRC04' for ref in required))):
                self.issue('AREA_SOURCE_REQUIRED', f'{p}.required_inputs', 'Explicitly bind the area module to its SRC04 source.', 'BLOCKER')
            refs = self.strings(r.get('artifact_refs'), f'{p}.artifact_refs')
            for ref in refs:
                if ref not in artifacts or artifacts[ref].get('module_run_id') != r.get('module_run_id'):
                    self.issue('ARTIFACT_REF_INVALID', f'{p}.artifact_refs', 'Reference an artifact produced by this module run.')
            stamps = {}
            for key in ('started_at', 'finished_at'):
                if r.get(key) is not None:
                    stamps[key] = self.stamp(r[key], f'{p}.{key}')
            if r.get('status') == 'NOT_RUN' and (r.get('started_at') is not None or r.get('finished_at') is not None):
                self.issue('NOT_RUN_TIMESTAMPS', p, 'NOT_RUN cannot carry execution start/finish timestamps.')
            if r.get('status') == 'RUNNING' and (stamps.get('started_at') is None or r.get('finished_at') is not None):
                self.issue('RUNNING_TIMESTAMPS', p, 'RUNNING needs started_at and no finished_at.')
            if r.get('status') in ('FAILED', 'PARTIAL') and any((stamps.get(k) is None for k in ('started_at', 'finished_at'))):
                self.issue('EXECUTION_TIMESTAMPS_REQUIRED', p, 'Executed FAILED/PARTIAL runs require both execution timestamps.')
            if all((stamps.get(k) is not None for k in ('started_at', 'finished_at'))) and stamps['finished_at'] < stamps['started_at']:
                self.issue('TIMESTAMP_ORDER', p, 'finished_at cannot precede started_at.')
            if r.get('status') in ('BLOCKED', 'FAILED', 'PARTIAL'):
                self.text(r.get('error'), f'{p}.error')
            elif r.get('error') is not None:
                self.text(r['error'], f'{p}.error')
            if r.get('engine') is not None:
                engine = self.obj(r['engine'], f'{p}.engine', 'name version source_hashes')
                self.text(engine.get('name'), f'{p}.engine.name')
                self.text(engine.get('version'), f'{p}.engine.version')
                hashes = engine.get('source_hashes')
                if not isinstance(hashes, dict) or not hashes:
                    self.issue('ENGINE_PROVENANCE_REQUIRED', f'{p}.engine.source_hashes', 'Supply immutable engine source hashes.')
                else:
                    for key in sorted(hashes):
                        self.digest(hashes[key], f'{p}.engine.source_hashes.{key}')
            elif r.get('status') in ('RUNNING', 'FAILED', 'PARTIAL'):
                self.issue('ENGINE_PROVENANCE_REQUIRED', f'{p}.engine', 'Executed/running modules require engine provenance.')
            if r.get('status') in ('SUCCEEDED', 'SUCCEEDED_WITH_WARNINGS'):
                if r.get('engine') is None or not refs or any((stamps.get(k) is None for k in ('started_at', 'finished_at'))):
                    self.issue('SUCCESS_EVIDENCE_REQUIRED', p, 'Successful runs require engine provenance, timestamps and output references.')
        if len(area_runs) != 1:
            self.issue('AREA_MODULE_REQUIRED', 'manifest.modules', 'LI-0 input gate needs exactly one selected area_coverage module run.', 'BLOCKER')
        elif area_runs[0].get('status') != 'NOT_RUN':
            self.issue('AREA_STAGE_NOT_PENDING', 'manifest.modules', 'LI-0 prepares a NOT_RUN area stage; historical/completed jobs are not a new-stage readiness claim.', 'BLOCKER')
        for index, value in enumerate(self.array(m.get('artifacts'), 'manifest.artifacts')):
            p = f'manifest.artifacts[{index}]'
            a = self.obj(value, p, 'artifact_id layer schema_version module_run_id path fingerprint byte_count dependencies status completeness')
            self.enum(a.get('layer'), LAYERS, f'{p}.layer')
            self.text(a.get('schema_version'), f'{p}.schema_version')
            self.enum(a.get('status'), STATUSES, f'{p}.status')
            self.enum(a.get('completeness'), {'COMPLETE', 'PARTIAL', 'UNKNOWN'}, f'{p}.completeness')
            owner = a.get('module_run_id')
            if not isinstance(owner, str) or owner not in modules:
                self.issue('PRODUCER_REF_INVALID', f'{p}.module_run_id', 'Declare the producing module run.')
            elif not isinstance(modules[owner].get('artifact_refs'), list) or a.get('artifact_id') not in modules[owner]['artifact_refs']:
                self.issue('ARTIFACT_REF_INVALID', p, 'The producer must also reference this artifact.')
            elif modules[owner].get('status') in ('NOT_RUN', 'BLOCKED'):
                self.issue('ARTIFACT_BEFORE_EXECUTION', p, 'A module that has not executed cannot produce an existing output artifact.')
            elif modules[owner].get('status') in ('SUCCEEDED', 'SUCCEEDED_WITH_WARNINGS') and (a.get('status') not in ('SUCCEEDED', 'SUCCEEDED_WITH_WARNINGS') or a.get('completeness') != 'COMPLETE'):
                self.issue('ARTIFACT_STATUS_MISMATCH', p, 'A completed-success producer must reference complete successful outputs.')
            deps = self.strings(a.get('dependencies'), f'{p}.dependencies')
            if not deps:
                self.issue('ARTIFACT_LINEAGE_REQUIRED', f'{p}.dependencies', 'Bind an existing output to at least one source or upstream artifact.')
            for ref in deps:
                if ref == a.get('artifact_id') or (ref not in sources and ref not in artifacts):
                    self.issue('ARTIFACT_DEPENDENCY_INVALID', f'{p}.dependencies', 'Reference existing source/artifact IDs without self-dependency.')
            self.local_file(a.get('path'), a.get('fingerprint'), a.get('byte_count'), p)
        graph = {}
        for key, record in sources.items():
            prov = record.get('provenance')
            deps = prov.get('dependencies') if isinstance(prov, dict) else None
            graph[key] = [x for x in deps if isinstance(x, str)] if isinstance(deps, list) else []
        for key, record in artifacts.items():
            deps = record.get('dependencies')
            graph[key] = [x for x in deps if isinstance(x, str)] if isinstance(deps, list) else []
        try:
            tuple(TopologicalSorter(graph).static_order())
        except CycleError:
            self.issue('DEPENDENCY_CYCLE', 'manifest', 'Source/artifact provenance must form an acyclic dependency graph.')

    def result(self) -> dict:
        diagnostics = sorted(self.diagnostics, key=lambda d: (d['path'], d['code'], d['severity'], d['message']))
        invalid = any((d['severity'] == 'ERROR' for d in diagnostics))
        blocked = any((d['blocking'] for d in diagnostics))
        return {'schema_version': RESULT_SCHEMA, 'validation_status': 'INVALID' if invalid else 'VALID', 'offline_readiness': 'BLOCKED' if blocked else 'READY', 'readiness_scope': 'LI1_BUILDING_SELECTION_INPUT_CONTRACT_ONLY', 'live_readiness': 'NOT_VERIFIED', 'verified_local_source_count': len(self.verified_sources), 'limitations': ['No source retrieval or live authorization check.', 'No payload geometry/schema, geographic coverage or calculation validation.', 'No capacity, routing, Recount, Traffic or PPAC readiness claim.'], 'diagnostics': diagnostics}

def validate(context: Any, manifest: Any, *, root: Path | str) -> dict:
    """Validate supplied JSON values and declared local fingerprints; never mutate inputs."""
    v = _Validator(Path(root))
    v.json_values(context, 'context')
    v.json_values(manifest, 'manifest')
    if any((d['severity'] == 'ERROR' for d in v.diagnostics)):
        return v.result()
    c = v.context(context)
    v.manifest(manifest, c)
    return v.result()

def validate_files(context_path: Path | str, manifest_path: Path | str, *, root: Path | str) -> dict:
    """Strict local JSON loading: malformed, duplicate keys and nonfinite fail closed."""
    v = _Validator(Path(root))
    loaded = []
    for label, path in (('context', context_path), ('manifest', manifest_path)):
        try:
            if not Path(path).is_file():
                v.issue('JSON_FILE_UNAVAILABLE', label, 'Supply a readable regular local JSON file; directories/devices/FIFOs are not inputs.')
                continue
            with Path(path).open(encoding='utf-8') as stream:
                loaded.append(json.load(stream, object_pairs_hook=_strict_pairs, parse_constant=_reject_constant))
        except (ValueError, UnicodeError, RecursionError):
            v.issue('JSON_INVALID', label, 'Supply valid UTF-8 JSON without duplicate keys or nonfinite constants.')
        except OSError:
            v.issue('JSON_FILE_UNAVAILABLE', label, 'Supply a readable local JSON input file.')
    if v.diagnostics:
        return v.result()
    return validate(*loaded, root=root)

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path, help='Local reference root; no files are written.')
    args = parser.parse_args(argv)
    result = validate_files(args.context, args.manifest, root=args.root)
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))
    return 1 if result['validation_status'] == 'INVALID' else 2 if result['offline_readiness'] == 'BLOCKED' else 0
if __name__ == '__main__':
    raise SystemExit(main())
