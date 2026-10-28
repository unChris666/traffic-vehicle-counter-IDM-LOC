"""Versioned PPAC facade; explicit lookup values, no inferred business defaults."""
from . import residential, fasum, traffic as mvp_traffic
from . import _reference as reference

def calculate(features, parameters):
    if features.get('schema_version') != 'ppac_features_v1' or parameters.get('schema_version') not in ('ppac_parameters_v1','ppac_parameters_mvp_v2'):
        raise ValueError('PPAC_SCHEMA_UNSUPPORTED')
    # Validate traffic observations before any Residential/total calculation.
    mvp=parameters['schema_version']=='ppac_parameters_mvp_v2'
    traffic = (mvp_traffic.calculate if mvp else reference.calculate_traffic)(features['samples'], **parameters['traffic'])
    if traffic['status'] != 'lengkap':
        raise ValueError('PPAC_OBSERVATIONS_INCOMPLETE: ' + ', '.join(traffic['missing_observations']))
    res_params={**parameters['residential'],**({'combined_coefficient':1.0} if mvp else {})}
    res = residential.calculate(features['allocated_buildings'], outer_zone_open=features['outer_zone_open'],
                                population_estimate=features.get('area_building_basis',{}).get('population_estimate'),**res_params)
    if features.get('area_building_basis'):
        res['building_basis']=features['area_building_basis']
    facilities = fasum.calculate(features['fasum'])
    total = reference.calculate_ppac(residential=res, traffic=traffic, fasum_std=facilities['std_fasum'],
                                    drive_thru=parameters['traffic']['drive_thru'], **parameters['aggregation'])
    return {'schema_version': 'ppac_result_v1', 'execution_status': 'SUCCEEDED', 'unit': 'STD/hari',
            'std_total': total['std_total'], 'residential': res, 'traffic': traffic,
            'fasum': facilities, 'total': total, 'policy_version': 'owner_integration_mvp_v3' if mvp else 'owner_integration_mvp_v1',
            'result_quality':'UNVERIFIED' if features.get('area_building_basis',{}).get('status')=='UNVERIFIED' else 'PARTIAL' if any(v['quality']=='PARTIAL' or v['summary'].get('pending',0)>0 for v in features.get('upstream_quality',{}).values()) else 'COMPLETE_WITHIN_DECLARED_SCOPE',
            'reason':features.get('area_building_basis',{}).get('reason'),
            'lookup_policy':{'enabled':not mvp,'residential_multiplier':1.0 if mvp else parameters['residential']['combined_coefficient'],
                             'balance_multiplier':1.0 if mvp else parameters['traffic']['balance_multiplier']},
            'limitations': ['MVP v2: Residential/AE18 lookups disabled by owner; multiplier1 is not a lookup result.' if mvp else 'Manual combined_coefficient and balance_multiplier; Excel lookup unresolved.',
                           'Scenario estimate, not measured demand or validated sales.']}
