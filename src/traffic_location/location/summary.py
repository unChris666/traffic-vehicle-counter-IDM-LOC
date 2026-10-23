import math
def capacity_groups(rows):
    """Never aggregate different units or count missing capacity as zero."""
    groups = {}
    for row in rows:
        if row['selection_status'] != 'SELECTED':
            continue
        unit = row['capacity_unit']
        if not isinstance(unit, str) or not unit:
            raise ValueError('Selected capacity unit is missing')
        group = groups.setdefault(row['decision_state'], {}).setdefault(unit, {'buildings': 0, 'known_subtotal': 0, 'unknown_buildings': 0})
        group['buildings'] += 1
        value = row['capacity_reference']
        if value is None:
            group['unknown_buildings'] += 1
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or (not math.isfinite(value)) or (value < 0):
            raise ValueError('Invalid capacity')
        else:
            group['known_subtotal'] += value
    return groups
