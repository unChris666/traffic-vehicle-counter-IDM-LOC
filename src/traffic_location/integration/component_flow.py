"""Explicit single-engine PPAC handoffs for notebook16. No cross-job merging."""
from .adapters import inspect
from .contracts import need
from .area_residential import building_basis
from .gate import features as complete_features
from ..ppac.components import calculate


def component_result(mode,jobs,bindings,context,parameters,root):
    need(bool(jobs),'REQUIRED_ENGINE_UNAVAILABLE','Belum ada hasil engine valid untuk menghitung komponen PPAC.')
    results={j['id']:inspect(j['engine'],j['result_ref'],root) for j in jobs}
    if mode=='area':
        need(len(results)==1,'AREA_RESULT_INVALID','Mode Area memerlukan satu hasil Area.')
        h=next(iter(results.values()));native=h['native']
        need(h['engine']=='area','ENGINE_MISMATCH','Mode Area tidak menerima Traffic.')
        target=native['identity']['market_config']['target']
        need(all(target[k]==context[k] for k in ('latitude','longitude')),'TARGET_MISMATCH','Koordinat Area berbeda.')
        gate=native['attractor_gate'];need(gate['state'] in ('OPEN','CLOSED'),'AREA_GATE_UNKNOWN','Zona luar belum diketahui.')
        basis=building_basis(native)
        f={'schema_version':'ppac_features_v1','context':context,'allocated_buildings':basis['ppac_buildings'],
           'outer_zone_open':gate['state']=='OPEN','area_building_basis':basis,
           'fasum':[{'distance_m':r['distance_to_candidate_m']} for r in gate['evidence']],
           'lineage':{'area':h['result_ref'],'area_result_version':h['result_version']},
           'upstream_quality':{k:{'quality':v['quality'],'summary':v['summary']} for k,v in results.items()}}
    else:
        eligible=[b for b in bindings if type(b.get('observed_seconds')) in (int,float) and 300<=b['observed_seconds']<=306]
        excluded=[{'job_id':b['job_id'],'observed_seconds':b.get('observed_seconds'),
                   'reason':'DURATION_INCOMPATIBLE: PPAC sample requires300–306seconds; counting result preserved.',
                   'result_ref':results[b['job_id']]['result_ref']} for b in bindings if b not in eligible]
        need(bool(eligible),'NO_VALID_PPAC_SAMPLES','Counting tersedia, tetapi tidak ada sampel PPAC berdurasi300–306detik.')
        binding={'schema_version':'gate2_binding_v1','context':context,'area':None,'traffic':eligible,
                 'category_mapping':{'motorcycle':'motor','car':'mobil','bus':'angkutan_umum','truck':None,'pedestrian':'pejalan_kaki'},'supplemental':[]}
        selected={b['job_id']:results[b['job_id']] for b in eligible}
        f=complete_features(binding,selected,parameters,traffic_only=True)
        f['excluded_ppac_samples']=excluded
    result=calculate(f,parameters,mode)
    result.update(features=f,parameters=parameters)
    if f.get('excluded_ppac_samples'):
        result['diagnostics'].append({'code':'PPAC_SAMPLES_EXCLUDED','samples':f['excluded_ppac_samples']})
    return result


def available_components(jobs,bindings,context,parameters,root):
    """Preserve successful components when a combined job cannot produce total."""
    output={};errors=[];lineage={}
    for mode,engine in (('area','area'),('traffic','traffic')):
        selected=[j for j in jobs if j['engine']==engine]
        if not selected:continue
        try:
            part=component_result(mode,selected,bindings if mode=='traffic' else [],context,parameters,root)
            for key in ('residential','fasum','traffic'):
                if key in part:output[key]=part[key]
            lineage[mode]=part['features']
        except Exception as error:
            errors.append({'code':getattr(error,'code',type(error).__name__),'component':mode,'message':str(error)[:1000]})
    return output,lineage,errors
