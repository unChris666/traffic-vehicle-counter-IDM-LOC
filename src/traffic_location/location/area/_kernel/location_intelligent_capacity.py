"""N1 reference capacity, split units; no final population/household claims."""
from copy import deepcopy
import math
from traffic_location.location.area._kernel.location_intelligent_config import get_config
from traffic_location.location.area._kernel.location_intelligent_validator import canonical_hash

def estimate_capacity(selection, policy=None):
    policy = get_config() if policy is None else deepcopy(policy)
    cfg = policy['capacity_reference']
    if cfg['profile'] != 'N1_SPLIT_REFERENCE_ONLY' or cfg['allow_mixed_unit_total'] is not False:
        raise ValueError('Only split N1 reference capacity is supported')
    if type(cfg['estimate_level_from_height']) is not bool:
        raise ValueError('Height fallback must be an explicit boolean')
    if selection.get('schema_version') != 'location_intelligent_building_selection_v1' or selection.get('status') not in {'SUCCEEDED', 'PARTIAL'}:
        raise ValueError('Supply an available LI-1 selection')
    for name, value in [('floor_height_m', cfg['floor_height_m']), ('standard_residential_value', cfg['standard_residential_value'])]:
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid capacity parameter: ' + name)
    for name in ('apartment', 'dormitory', 'hotel'):
        for key, value in cfg[name].items():
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('Invalid capacity parameter: ' + name + '.' + key)
            if key in {'occupancy', 'net_ratio'} and value > 1:
                raise ValueError('Ratio exceeds one')
    units = {'standard_residential': 'N1_STANDARD_VALUE_UNIT_UNRESOLVED', 'apartment': 'OCCUPIED_DWELLING_UNITS_ESTIMATED', 'dormitory': 'OCCUPIED_ROOMS_ESTIMATED', 'hotel': 'GUESTS_ESTIMATED'}
    rows, seen = ([], set())
    for building in selection['selected']:
        key = building['building_id']
        if key in seen:
            raise ValueError('Duplicate building identity')
        seen.add(key)
        kind, props = (building['building_type'], building['raw_properties'])
        if kind not in units:
            raise ValueError('Unsupported building type')
        area = building['area_m2']
        if type(area) not in (int, float) or not math.isfinite(area) or area <= 0:
            raise ValueError('Invalid footprint area')
        for name in ('num_floors', 'height'):
            x = props.get(name)
            if x is not None and (type(x) not in (int, float) or not math.isfinite(x) or x <= 0):
                raise ValueError('Invalid optional level input')
        level, source = (None, 'UNKNOWN')
        if props.get('num_floors') is not None:
            level, source = (max(1, round(props['num_floors'])), 'NUM_FLOORS')
        elif cfg['estimate_level_from_height'] and props.get('height') is not None:
            level, source = (max(1, round(props['height'] / cfg['floor_height_m'])), 'ESTIMATED_FROM_HEIGHT')
        gfa = area * level if level is not None else None
        if gfa is not None and (not math.isfinite(gfa)):
            raise ValueError('Gross floor area overflow')
        raw = occupied = None
        if kind == 'standard_residential':
            raw = cfg['standard_residential_value']
        elif gfa is not None:
            c = cfg[kind]
            occupied = gfa * c['net_ratio'] / c['average_area_m2'] * c['occupancy']
            raw = occupied * c.get('guests_per_occupied_room', 1)
        if raw is not None and (not math.isfinite(raw)):
            raise ValueError('Capacity overflow')
        rows.append({'building_id': key, 'building_type': kind, 'level': level, 'level_source': source, 'gross_floor_area_m2': gfa, 'occupied_units_or_rooms_unrounded': occupied, 'capacity_unrounded': raw, 'capacity_reference_rounded': round(raw) if raw is not None else None, 'unit': units[kind], 'claim_type': 'REFERENCE_ESTIMATE_NOT_OBSERVATION', 'reason': 'MISSING_LEVEL' if raw is None else 'REFERENCE_FORMULA'})
    groups = {}
    for unit in units.values():
        group = [r for r in rows if r['unit'] == unit]
        groups[unit] = {'buildings': len(group), 'known_subtotal': sum((r['capacity_reference_rounded'] for r in group if r['capacity_reference_rounded'] is not None)), 'unknown_buildings': sum((r['capacity_reference_rounded'] is None for r in group))}
    return {'schema_version': 'li_capacity_reference_v1', 'status': 'PARTIAL' if selection['status'] == 'PARTIAL' or any((r['capacity_reference_rounded'] is None for r in rows)) else 'SUCCEEDED', 'profile': cfg['profile'], 'selection_hash': canonical_hash(selection), 'policy_hash': canonical_hash(policy), 'rows': rows, 'summary_by_unit': groups, 'mixed_unit_total': None, 'final_business_capacity': None, 'limitations': ['Standard value4 has no approved household/population unit', 'Not observed occupancy; no mixed-unit total', 'Capacity describes selected buildings, not accessible buildings']}
