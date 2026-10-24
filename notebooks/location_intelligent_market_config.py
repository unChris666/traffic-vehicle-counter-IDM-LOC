"""Owner-confirmed experimental market policy; no acquisition at import.

Importing this file neither fetches data nor changes the active CPU notebook.
Statistical scores are scenario estimates, not calibrated customer probabilities.
"""
from copy import deepcopy


MARKET_CONFIG = {
    'schema_version': 'area_market_spec_v1',
    'policy_version': 'owner_market_huff_v1_2026_10_24',
    'status': 'EXPERIMENTAL_OWNER_CONFIRMED',
    'target': {'latitude': -6.190690620514923,
               'longitude': 106.83819549844226,
               'coordinate_source': 'OWNER_EXPLICIT_INPUT',
               'store_id': None, 'store_name': None},
    'sources': {
        'buildings': 'OPENSTREETMAP',
        'network': 'OPENSTREETMAP_MOTOR_POLICY',
        'network_feature_mode': 'ROADS_ONLY_EXPERIMENT',
        'network_radius_m': 3000.0,
        'poi_required_for_pipeline': False,
        'basemap': 'OPENSTREETMAP',
        'competitor_table': 'locdeproject.DWH_NS_LOC.COMPETITOR',
        'indomaret_table': 'locdeproject.DWH_NS_LOC.AREA_COVERAGE',
        'reuse_previous_target_snapshot': False,
        'store_inventory_radius_m': 2000.0,
    },
    'display': {
        'candidate_pin_color': '#ffffff',
        'candidate_pin_outline_color': '#374151',
        'candidate_rings': [
            {'radius_m': 100.0, 'color': '#16a34a'},
            {'radius_m': 400.0, 'color': '#eab308'},
            {'radius_m': 2000.0, 'color': '#f97316'},
        ],
        'competitor_primary': {'radius_m': 400.0, 'ring_color': '#b7410e',
                               'pin_color': '#dc2626'},
        'competitor_secondary': {'radius_m': 100.0, 'ring_color': '#ff2020',
                                 'pin_color': '#dc2626'},
        # These are display rules from the owner, not allocation overrides.
        'indomaret': {'pin_color': '#2563eb', 'ring_color': '#2563eb',
                     'distance_lt_400_radius_m': 0.0,
                     'distance_gte_400_lt_800_radius_m': 100.0,
                     'distance_gte_800_radius_m': 0.0},
        'building_colors': {
            'valid': '#16a34a', 'market_competition': '#f97316',
            'market_cannibalization': '#2563eb', 'competitor_owned': '#dc2626',
            'indomaret_owned': '#2563eb', 'others': '#9ca3af',
        },
        'network_style': 'EXISTING_OSM_HIGHWAY_HIERARCHY',
        'poi_style': 'DISTINCT_PER_CATEGORY',
    },
    'allocation_requirements': {
        'residential_min_area_m2': 36.0,
        'zones_m': [100.0, 400.0, 800.0, 2000.0],
        'network_access_required': True,
        'candidate_competitor_contest_inner_radius_m': 400.0,
        'competition_cannibalization_zone_m': 800.0,
        'outer_zone_requires_attractor': True,
        'attractor_kinds': ['market', 'hospital', 'station', 'recreation',
                            'police', 'bank', 'restaurant_cluster',
                            'mall', 'shopping_centre'],
        'statistical_model': 'HUFF_ROUTE_DISTANCE_EQUAL_ATTRACTIVENESS',
        'huff_exponent': 2.0,
        'allocation': 'ONE_WHOLE_BUILDING_TO_HIGHEST_SCORE',
        'exclusive_core_m': 100.0,
        'indomaret_core_target_min_m': 400.0, 'indomaret_core_target_max_m': 800.0,
        'primary_same_corridor_within_m': 800.0,
        'same_corridor': 'NORMALIZED_NAME_OR_REF_INTERSECTION',
        'influence_outside_core': True,
        'speed_kmh': 7.0, 'max_travel_minutes': 10.0,
        'time_rule': 'PYTHON_ROUND_HALF_EVEN_LE_10',
        'residential_max_area_m2_exclusive': 550.0,
        'area_min_inclusive': True,
        'restaurant_cluster': {'minimum_sites': 5, 'minimum_footprint_m2': 40.0,
                               'maximum_pair_distance_m': 200.0,
                               'same_corridor_required': True},
        'attractor_gate': 'ONE_REACHABLE_ATTRACTOR_WITHIN_2000M_OPENS_ALL_OUTER_ZONE',
        'tie_break': 'MIN_ROUTE_DISTANCE_THEN_STABLE_STORE_KEY',
        'distance_zero': 'ZERO_DISTANCE_OPTIONS_ONLY_EQUAL_SCORES',
        'outputs_are_validated_customer_probabilities': False,
    },
    'open_decisions': {},
}


def get_market_config():
    """Return isolated editable input; caller edits cannot leak into other jobs."""
    return deepcopy(MARKET_CONFIG)


def require_market_decisions(config):
    """Fail before retrieval/allocation rather than manufacture market totals."""
    unresolved = sorted(k for k, v in config['open_decisions'].items() if v is None)
    if unresolved:
        raise ValueError('MARKET_POLICY_UNRESOLVED: ' + ', '.join(unresolved))
    import math
    p=config['allocation_requirements']
    if p['statistical_model']!='HUFF_ROUTE_DISTANCE_EQUAL_ATTRACTIVENESS' or p['allocation']!='ONE_WHOLE_BUILDING_TO_HIGHEST_SCORE':
        raise ValueError('Unsupported market allocation policy')
    for key in ['huff_exponent','speed_kmh','max_travel_minutes','exclusive_core_m',
                'residential_min_area_m2','residential_max_area_m2_exclusive']:
        if type(p[key]) not in (float,int) or not math.isfinite(p[key]) or p[key]<=0:
            raise ValueError('Invalid market policy value: '+key)
    if p['residential_min_area_m2']>=p['residential_max_area_m2_exclusive']:
        raise ValueError('Invalid market area range')
    if not p['area_min_inclusive'] or p['time_rule']!='PYTHON_ROUND_HALF_EVEN_LE_10':
        raise ValueError('Unsupported market threshold semantics')
    return deepcopy(config)
