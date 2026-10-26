"""Owner MVP rule: per supplied facility row, <=400m +2, >400..800m +1."""
from ._reference import _number

def calculate(rows):
    if not isinstance(rows, list):
        raise ValueError('fasum wajib list; [] menyatakan tidak ada kontribusi')
    contributions = []
    for row in rows:
        distance = _number(row['distance_m'], 'fasum.distance_m')
        contributions.append({'distance_m': distance, 'std': 2 if distance <= 400 else 1 if distance <= 800 else 0})
    return {'std_fasum': sum(r['std'] for r in contributions), 'rows': contributions,
            'policy': 'owner_distance_sum_mvp_v1'}
