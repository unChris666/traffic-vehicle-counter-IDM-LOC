"""Independent component calculations; absent engines never become zero inputs."""
from . import residential,fasum,traffic

def calculate(features,parameters,scope):
    if features.get('schema_version')!='ppac_features_v1' or scope not in ('area','traffic') or parameters.get('schema_version')!='ppac_parameters_mvp_v2':
        raise ValueError('PPAC_COMPONENT_SCHEMA_UNSUPPORTED')
    result={'schema_version':'ppac_result_v1','execution_status':'SUCCEEDED','unit':'STD/hari',
            'scope':scope,'std_total':None,'result_quality':'PARTIAL',
            'policy_version':'owner_independent_components_v1',
            'reason':'Komponen '+scope+' saja; STD total menunggu Area dan Traffic lengkap.',
            'diagnostics':[{'code':'COMBINED_INPUTS_NOT_REQUESTED','message':'Engine lain tidak dijalankan pada mode ini.'}]}
    if scope=='area':
        res=residential.calculate(features['allocated_buildings'],outer_zone_open=features['outer_zone_open'],
                                  combined_coefficient=1.,**parameters['residential'])
        res['building_basis']=features['area_building_basis']
        result.update(residential=res,fasum=fasum.calculate(features['fasum']))
        if features['area_building_basis']['status']=='UNVERIFIED':result['result_quality']='UNVERIFIED'
    else:
        computed=traffic.calculate(features['samples'],**parameters['traffic'])
        computed['provisional']=computed['status']!='lengkap'
        result['traffic']=computed
        if computed['missing_observations']:
            result['diagnostics'].append({'code':'OBSERVATIONS_INCOMPLETE','missing':computed['missing_observations'],
                'message':'Nilai komponen Traffic sementara memakai formula MVP atas observasi tersedia; sesi hilang tidak dibuat sebagai sampel nol. Bobot hari tetap mengikuti policy Excel 4/3.'})
    return result
