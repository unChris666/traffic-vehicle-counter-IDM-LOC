"""Owner integration-layer policy: allocated buildings, x4, two/three zones."""
from ._reference import _number, excel_round

def calculate(buildings, *, outer_zone_open, combined_coefficient,
              operating_days_per_week, swot_factor):
    buildings = _number(buildings, 'allocated_buildings')
    if not buildings.is_integer():
        raise ValueError('allocated_buildings harus integer')
    if type(outer_zone_open) is not bool:
        raise ValueError('outer_zone_open harus bool dari hasil Area')
    coefficient = _number(combined_coefficient, 'combined_coefficient')
    days = _number(operating_days_per_week, 'operating_days_per_week', maximum=7)
    swot = _number(swot_factor, 'swot_factor')
    people = buildings * 4
    shares = (0.35, 0.45, 0.20) if outer_zone_open else (0.40, 0.60, 0.)
    monthly = days * 4 + (2 if days > 6 else 0)
    groups = []
    for label, share, multiplier in zip(('0_400m','gt400_800m','gt800_2000m'), shares, (1., .5, .25)):
        population = people * share
        std = excel_round(population / 30 * multiplier * coefficient * monthly / 30 * swot)
        groups.append({'zone': label, 'share': share, 'estimated_occupants': population, 'std': std})
    return {'std_residential': sum(g['std'] for g in groups), 'total_penghuni': people,
            'allocation_method': 'owner_35_45_20' if outer_zone_open else 'owner_40_60',
            'allocated_buildings': int(buildings), 'groups': groups, 'operating_days_month': monthly}
