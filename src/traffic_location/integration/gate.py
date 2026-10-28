"""Validate engine handoffs and adapt features. No routing/counting/PPAC formula."""
from copy import deepcopy
from .contracts import need, fields
from ..ppac.konstatna import CATEGORIES, SESSIONS_NORMAL, SESSIONS_SHIFT3, DAY_WEIGHTS

def features(binding, results, parameters, *, traffic_only=False):
    fields(binding, {'schema_version','context','area','traffic','category_mapping','supplemental'})
    need(binding['schema_version']=='gate2_binding_v1','BINDING_SCHEMA_UNSUPPORTED','Gunakan gate2_binding_v1')
    mvp=parameters.get('schema_version')=='ppac_parameters_mvp_v2'
    categories=tuple(c for c in CATEGORIES if not mvp or c!='sepeda')
    context=binding['context'];fields(context, {'target_id','period_id','latitude','longitude','evidence'})
    need(all(isinstance(context[k],str) and bool(context[k].strip()) for k in ('target_id','period_id','evidence')),
         'CONTEXT_MISSING','Target, periode dan referensi bukti binding wajib eksplisit')
    if traffic_only:
        need(binding['area'] is None,'UNEXPECTED_AREA','Traffic saja tidak menerima hasil Area.')
        ah=an=ar=None;area=None;gate=None;facilities=None
    else:
        area=binding['area'];fields(area,{'job_id','result_version'})
        ah=_select(area,results,'area');an=ah['native'];ar=ah['result']
        need((mvp and ah['quality'] in ('SUCCEEDED','PARTIAL')) or (ah['quality']=='SUCCEEDED' and an['market_inputs_complete'] is True and
             an['summary']['market_status_counts'].get('UNVERIFIED',0)==0),'AREA_INCOMPLETE',
             'Area masih PARTIAL/UNVERIFIED atau input market belum lengkap; bukan Residential 0')
        target=an['identity']['market_config']['target']
        need(all(target[k]==context[k] for k in ('latitude','longitude')),'TARGET_MISMATCH','Koordinat target Area berbeda')
        gate=an['attractor_gate']
        need(gate['state'] in ('OPEN','CLOSED'),'AREA_GATE_UNKNOWN','Kelayakan zona luar belum diketahui')
        facilities=[{'distance_m':r['distance_to_candidate_m']} for r in gate['evidence']]
    need(parameters.get('schema_version') in ('ppac_parameters_v1','ppac_parameters_mvp_v2'),'PARAMETER_SCHEMA_UNSUPPORTED','Gunakan ppac_parameters_v1')
    fields(parameters, {'schema_version','residential','traffic','aggregation','provenance'})
    need(isinstance(parameters['provenance'],str) and bool(parameters['provenance'].strip()),
         'PARAMETER_PROVENANCE_MISSING','Nyatakan sumber parameter; lookup AC17/AK30/AE18 belum otomatis')
    fields(parameters['residential'],{'operating_days_per_week','swot_factor'} if mvp else {'combined_coefficient','operating_days_per_week','swot_factor'})
    fields(parameters['traffic'],{'road_type','operating_hours','drive_thru'} if mvp else {'road_type','operating_hours','balance_multiplier','drive_thru'})
    fields(parameters['aggregation'],{'traffic_cut_factor','parking_factor'})
    from ..ppac._reference import _number
    if not traffic_only:_number(an['summary']['candidate_whole_buildings'],'candidate_whole_buildings')
    for facility in facilities or []:
        _number(facility['distance_m'],'fasum.distance_m')
    for k,v in parameters['residential'].items():
        _number(v,k,maximum=7 if k=='operating_days_per_week' else None)
    for k in ('traffic_cut_factor','parking_factor'):
        _number(parameters['aggregation'][k],k)
    hours=_number(parameters['traffic']['operating_hours'],'operating_hours',maximum=24)
    need(hours>0,'HOURS_INVALID','Jam operasional harus positif')
    if not mvp:_number(parameters['traffic']['balance_multiplier'],'balance_multiplier')
    from ..ppac.konstatna import ROAD_RATES
    need(parameters['traffic']['road_type'] in ROAD_RATES and type(parameters['traffic']['drive_thru']) is bool,
         'ROAD_PROFILE_INVALID','Pilih profil PPAC yang sah dan drive_thru bool; mapping OSM belum diputuskan')
    sessions=SESSIONS_NORMAL+(SESSIONS_SHIFT3 if hours>15 else ())
    samples={d:{s:{} for s in sessions} for d in DAY_WEIGHTS}
    mapping=binding['category_mapping']
    need(isinstance(mapping,dict) and all(v is None or v in categories for v in mapping.values()),
         'CATEGORY_MAPPING_INVALID','Kategori harus kategori PPAC atau null untuk eksklusi eksplisit')
    need(isinstance(binding['traffic'],list) and bool(binding['traffic']),'TRAFFIC_MISSING','Tidak ada binding Traffic')
    selected=set() if traffic_only else {area['job_id']};videos=set();slots=set();branch=None;lineage=[];excluded=[]
    for b in binding['traffic']:
        fields(b,{'job_id','result_version','video_sha256','target_id','period_id','day','session','observed_seconds','observed_categories','evidence'})
        h=_select(b,results,'traffic');r=h['result'];n=h['native']
        need(b['job_id'] not in selected,'DUPLICATE_RESULT','Result dipakai dua kali')
        selected.add(b['job_id'])
        need(b['target_id']==context['target_id'] and b['period_id']==context['period_id'],
             'CONTEXT_MISMATCH','Target/periode Traffic tidak sesuai context')
        need(isinstance(b['evidence'],str) and bool(b['evidence'].strip()),'CONTEXT_MISSING','Referensi bukti observasi diperlukan')
        need((mvp and h['quality'] in ('COMPLETE_WITHIN_DECLARED_SCOPE','PARTIAL')) or (h['quality']=='COMPLETE_WITHIN_DECLARED_SCOPE' and r['summary']['pending']==0),
             'TRAFFIC_INCOMPLETE','Hasil Traffic masih PARTIAL/pending')
        need(r['scope']['processed_frames']==r['scope']['source_frames'] and r['scope']['source_frames']>0,
             'FRAME_GAP','Frame belum lengkap')
        branch=r['branch'] if branch is None else branch
        need(branch==r['branch'],'BRANCH_MISMATCH','Machine dan reviewed tidak boleh dicampur')
        need(b['video_sha256']==r['source_identity']['video_sha256'],'SOURCE_MISMATCH','SHA video tidak cocok')
        need(b['video_sha256'] not in videos,'DUPLICATE_SOURCE','Video yang sama digunakan lebih dari sekali')
        videos.add(b['video_sha256'])
        need(type(b['observed_seconds']) in (int,float) and (300<=b['observed_seconds']<=306 if mvp else b['observed_seconds']==300),
             'DURATION_INCOMPATIBLE','Durasi tidak kompatibel: v1 tepat300detik; MVP v2 menerima300–306detik tanpa penskalaan count')
        d,s=b['day'],b['session']
        need(d in samples and s in sessions,'SLOT_INVALID','Hari/sesi tidak sesuai kebutuhan PPAC')
        need((d,s) not in slots,'DUPLICATE_SLOT','Slot hari/sesi dipakai dua kali');slots.add((d,s))
        observed=b['observed_categories']
        need(isinstance(observed,list) and len(observed)==len(set(observed)) and
             set(observed)<=set(n['report']['supported_categories']) and set(observed)<=set(mapping),
             'CATEGORY_UNSUPPORTED','Kategori belum didukung/diamati/memiliki mapping')
        out=samples[d][s]
        for category in observed:
            if mapping[category] is not None:
                out.setdefault(mapping[category],0)
        for e in n['events']:
            need(e['category'] in observed,'CATEGORY_UNSUPPORTED','Event di luar kategori observasi')
            if mapping[e['category']] is None:
                excluded.append({'job_id':b['job_id'],'event_id':e['event_id'],'category':e['category']})
            else:
                out[mapping[e['category']]]+=1
        lineage.append({'job_id':b['job_id'],'result_version':h['result_version'],'result_ref':h['result_ref'],
                        'branch':r['branch'],'summary':r['summary'],'observation_binding':deepcopy(b)})
    need(isinstance(binding['supplemental'],list),'SCHEMA_INVALID','supplemental harus list')
    for obs in binding['supplemental']:
        fields(obs,{'day','session','category','count','evidence'})
        d,s,c=obs['day'],obs['session'],obs['category']
        need((d,s) in slots and c in categories,'SLOT_INVALID','Observasi tambahan harus melengkapi slot yang sah')
        need(c not in samples[d][s],'DUPLICATE_OBSERVATION','Observasi tambahan tidak boleh menimpa hasil engine')
        need(type(obs['count']) is int and obs['count']>=0 and isinstance(obs['evidence'],str) and bool(obs['evidence'].strip()),
             'OBSERVATION_INVALID','Count integer nonnegatif dan bukti wajib tersedia')
        samples[d][s][c]=obs['count']
    missing=[f'{d}/{s}/{c}' for d in samples for s in samples[d] for c in categories if c not in samples[d][s]]
    if not traffic_only:need(not missing,'OBSERVATIONS_INCOMPLETE','Belum dicacah: '+', '.join(missing))
    need(selected==set(results),'UNSELECTED_RESULT','Ada hasil yang tidak dipilih eksplisit dalam binding')
    from .area_residential import building_basis
    residential_basis=building_basis(an) if not traffic_only else None
    return {'schema_version':'ppac_features_v1','context':deepcopy(context),
            'allocated_buildings':None if traffic_only else residential_basis['ppac_buildings'] if mvp else an['summary']['candidate_whole_buildings'],
            'area_building_basis':None if traffic_only else residential_basis if mvp else {'policy':'ALLOCATED_ONLY','status':ah['quality']},
            'outer_zone_open':None if traffic_only else gate['state']=='OPEN','samples':samples,'fasum':facilities,
            'missing_observations':missing,
            'upstream_quality':{k:{'quality':h['quality'],'summary':h['summary']} for k,h in results.items()},
            'duration_policy':'300_TO_306_SECONDS_NO_RESCALE' if mvp else 'EXACT_300_SECONDS',
            'lineage':{'area':None if traffic_only else ah['result_ref'],'area_result_version':None if traffic_only else ah['result_version'],'traffic':lineage},
            'supplemental':deepcopy(binding['supplemental']),'excluded_events':excluded,
            'traffic_policy':'ACCEPTED_MEASURED_AND_ESTIMATED_BOTH_DIRECTIONS',
            'binding_trust':'Caller asserts target/period/duration; not independently GPS/PTS verified'}

def _select(b, results, engine):
    need(b['job_id'] in results,'RESULT_MISSING','Hasil wajib belum tersedia: '+str(b['job_id']))
    h=results[b['job_id']]
    need(h['engine']==engine,'ENGINE_MISMATCH','Jenis engine tidak cocok')
    need((b['result_version'] is None and h.get('action')=='run') or b['result_version']==h['result_version'],
         'VERSION_MISMATCH','Versi hasil tidak cocok; null hanya untuk action=run pada workflow ini')
    return h
