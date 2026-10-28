"""Gate 2 software fixtures; these are not actual traffic/market observations."""
import tempfile,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from traffic_location.artifacts import write,read,sha,semantic_hash
from traffic_location.persistence import publish
from traffic_location.integration.adapters import ref
from traffic_location.integration.workflow import run,reopen
from traffic_location.integration.contracts import GateError
from traffic_location.ppac import calculate

class Gate2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.binding={'schema_version':'gate2_binding_v1','context':{'target_id':'SOFTWARE_FIXTURE','period_id':'TEST',
            'latitude':-6.,'longitude':106.,'evidence':'Synthetic fixture, not GPS/timing evidence'},
            'area':{'job_id':'area','result_version':'a'*64},'traffic':[],
            'category_mapping':{'motorcycle':'motor','car':'mobil','bus':'angkutan_umum','truck':None,'pedestrian':'pejalan_kaki'},'supplemental':[]}
        self.params={'schema_version':'ppac_parameters_v1','residential':{'combined_coefficient':1.5,
            'operating_days_per_week':7,'swot_factor':1},'traffic':{'road_type':'street','operating_hours':15,
            'balance_multiplier':.6,'drive_thru':False},'aggregation':{'traffic_cut_factor':.9,'parking_factor':.8},
            'provenance':'SOFTWARE_FIXTURE illustrative lookup values, not business defaults'}
        self.q={'schema_version':'gate2_workflow_v1','jobs':[],'ppac':None}
        from traffic_location.location.area.domain.aggregation import reconcile
        rows=[{'building_id':str(i),'winner_store_key':'candidate','count_candidate':1,'market_status':'VALID',
               'reason':'FIXTURE','scores':[{'huff_score':1}]} for i in range(1000)]
        identity={'market_config':{'target':{'latitude':-6.,'longitude':106.}}}
        n={'schema_version':'area_market_result_v1','status':'SUCCEEDED','rows':rows,'summary':reconcile(rows),
           'market_inputs_complete':True,'identity':identity,'fingerprint':semantic_hash(identity),
           'attractor_gate':{'state':'OPEN','evidence':[{'distance_to_candidate_m':d} for d in [100,200,400,500,800]]}}
        r={'schema_version':'area_execution_result_v1','execution_status':'SUCCEEDED','result_version':'a'*64,
           'summary':n['summary'],'data_quality_status':'SUCCEEDED','native_domain_sha256':self.domain(n)}
        self.packet('area','area',r,n)
        i=0
        for day in ('weekday','weekend'):
            for session in ('pagi','siang','sore','malam'):
                i+=1;key=day+'_'+session;source={'video_sha256':f'{i:064x}'}
                counts={'motorcycle':100,'car':50,'bus':10,'pedestrian':20} if day=='weekday' else {'motorcycle':80,'car':40,'bus':8,'pedestrian':16}
                events=[{'event_id':key+c+str(j),'category':c,'direction':'A_TO_B','status':'accepted',
                         'accepted_count_event':True,'evidence':{'measured_crossing':True}} for c,num in counts.items() for j in range(num)]
                a={'total':len(events),'measured_total':len(events),'inferred_total':0,'pending':0,'invalid':0,
                   'by_category':counts,'by_direction':{'A_TO_B':len(events)}}
                native={'events':events,'aggregate':a,'decisions':[],'invalid_decisions':[], 'source_identity':source,
                        'report':{'frame_count':9000,'supported_categories':list(counts)+['truck']}}
                result={'schema_version':'traffic_result_v2','execution_status':'SUCCEEDED','result_version':f'{100+i:064x}',
                        'branch':'machine','counting_executed':True,'operation_executed':'count_replay',
                        'scope':{'source_frames':9000,'processed_frames':9000},'source_identity':source,
                        'result_quality':'COMPLETE_WITHIN_DECLARED_SCOPE','native_semantic_sha256':semantic_hash(native),
                        'summary':{'accepted_total':len(events),'accepted_measured':len(events),'accepted_estimated':0,'pending':0,'invalid':0}}
                self.packet(key,'traffic',result,native,{'request.json':{'source_identity':source,'profile':'machine','frame_count':9000}})
                self.binding['traffic'].append({'job_id':key,'result_version':result['result_version'],'video_sha256':source['video_sha256'],
                    'target_id':'SOFTWARE_FIXTURE','period_id':'TEST','day':day,'session':session,'observed_seconds':300,
                    'observed_categories':list(counts)+['truck'],'evidence':'SOFTWARE_FIXTURE'})
                self.binding['supplemental'].append({'day':day,'session':session,'category':'sepeda','count':0,'evidence':'SOFTWARE_FIXTURE observed zero'})
        self.config()
    def domain(self,n):return semantic_hash({k:v for k,v in n.items() if k not in {'identity','fingerprint','output_path'}})
    def packet(self,key,engine,r,n,extra=None):
        folder=self.root/key
        publish(folder,{'result.json':r,'native.json.gz':n,**(extra or {})},metadata={'engine':engine,'result_version':r['result_version']})
        self.q['jobs'].append({'id':key,'engine':engine,'action':'reuse','result_ref':ref(folder)})
    def config(self):
        refs={}
        for name,value in [('binding',self.binding),('parameters',self.params)]:
            p=self.root/(name+'.json');write(p,value);refs[name+'_ref']={'path':str(p),'sha256':sha(p)}
        self.q['ppac']=refs
    def flow(self,output='out',**kw):
        self.config();return run(self.q,self.root/output,**kw)
    def test_owner_simulation_241_and_retry_without_recalculation(self):
        result=self.flow();self.assertEqual(result['execution_status'],'SUCCEEDED')
        p=result['ppac'];self.assertEqual(p['residential']['std_residential'],125)
        self.assertEqual(p['traffic']['std_traffic_raw'],150);self.assertEqual(p['fasum']['std_fasum'],8)
        self.assertEqual(p['std_total'],241);self.assertEqual(reopen(self.root/'out'),result)
        with patch('traffic_location.integration.workflow.execute') as execute,patch('traffic_location.ppac.calculate') as calc:
            self.assertEqual(run(self.q,self.root/'out'),result);execute.assert_not_called();calc.assert_not_called()
    def test_independent_engines_never_call_ppac(self):
        with patch('traffic_location.ppac.calculate') as calc:
            a=self.flow('a-only',operation='area');t=self.flow('t-only',operation='traffic')
            self.assertEqual(len(a['jobs']),1);self.assertEqual(len(t['jobs']),8)
            self.assertEqual(a['ppac']['execution_status'],'NOT_RUN');calc.assert_not_called()
    def test_failed_engine_retains_other_successes(self):
        self.q['jobs'][0]['result_ref']['path']=str(self.root/'missing')
        r=self.flow();self.assertEqual(r['execution_status'],'FAILED')
        self.assertEqual(sum(j['execution_status']=='SUCCEEDED' for j in r['jobs']),8)
        self.assertIsNone(r['ppac']['std_total'])
    def reject(self,code):
        with patch('traffic_location.ppac.calculate') as calc:
            r=self.flow();self.assertEqual(r['ppac']['execution_status'],'BLOCKED',r['ppac'])
            self.assertEqual(r['ppac']['diagnostics'][0]['code'],code);self.assertIsNone(r['ppac']['std_total']);calc.assert_not_called()
    def test_missing_bicycle_not_zero(self):
        self.binding['supplemental']=[];self.reject('OBSERVATIONS_INCOMPLETE')
    def test_wrong_target(self):
        self.binding['context']['latitude']=-7;self.reject('TARGET_MISMATCH')
    def test_wrong_period(self):
        self.binding['traffic'][0]['period_id']='OTHER';self.reject('CONTEXT_MISMATCH')
    def test_wrong_version(self):
        self.binding['traffic'][0]['result_version']='f'*64;self.reject('VERSION_MISMATCH')
    def test_wrong_source(self):
        self.binding['traffic'][0]['video_sha256']='e'*64;self.reject('SOURCE_MISMATCH')
    def test_duration_not_normalized(self):
        self.binding['traffic'][0]['observed_seconds']=299;self.reject('DURATION_INCOMPATIBLE')
    def test_duplicate_slot(self):
        self.binding['traffic'][1]['session']='pagi';self.reject('DUPLICATE_SLOT')
    def test_unknown_category_cannot_be_observed(self):
        self.binding['traffic'][0]['observed_categories'].append('bicycle');self.reject('CATEGORY_UNSUPPORTED')
    def test_missing_lookup_has_no_default(self):
        del self.params['residential']['combined_coefficient'];self.reject('SCHEMA_INVALID')
    def test_shift3_not_fabricated(self):
        self.params['traffic']['operating_hours']=16;self.reject('OBSERVATIONS_INCOMPLETE')
    def test_override_supplement_rejected(self):
        self.binding['supplemental'][0]['category']='motor';self.reject('DUPLICATE_OBSERVATION')
    def test_tamper_rejected(self):
        p=self.root/'weekday_pagi/result.json';p.write_text('{}');self.reject('REQUIRED_ENGINE_UNAVAILABLE')
    def test_partial_area_rejected(self):
        job=self.q['jobs'].pop(0);p=Path(job['result_ref']['path']);r=read(p/'result.json');n=read(p/'native.json.gz')
        n['status']=r['data_quality_status']='PARTIAL';r['native_domain_sha256']=self.domain(n)
        self.packet('partial-area','area',r,n);self.binding['area']['job_id']='partial-area';self.reject('AREA_INCOMPLETE')
    def test_partial_traffic_rejected(self):
        job=self.q['jobs'].pop(1);p=Path(job['result_ref']['path']);r=read(p/'result.json');n=read(p/'native.json.gz')
        r['result_quality']='PARTIAL';self.packet('partial-traffic','traffic',r,n,{'request.json':read(p/'request.json')})
        self.binding['traffic'][0]['job_id']='partial-traffic';self.reject('TRAFFIC_INCOMPLETE')
    def test_ppac_failure_has_no_total(self):
        with patch('traffic_location.ppac.calculate',side_effect=RuntimeError('Fixture failure')):
            r=self.flow()
        self.assertEqual(r['execution_status'],'FAILED');self.assertIsNone(r['ppac']['std_total'])
        self.assertTrue(all(j['execution_status']=='SUCCEEDED' for j in r['jobs']))
    def test_revision_conflict(self):
        self.flow();self.q['ppac']=None
        with self.assertRaisesRegex(GateError,'revision'):run(self.q,self.root/'out')
    def test_fasum_boundaries_and_two_zone_residential(self):
        from traffic_location.ppac.fasum import calculate as f
        from traffic_location.ppac.residential import calculate as residential
        self.assertEqual([r['std'] for r in f([{'distance_m':d} for d in [0,400,400.1,800,800.1]])['rows']],[2,2,1,1,0])
        self.assertEqual(residential(1000,outer_zone_open=False,**self.params['residential'])['std_residential'],140)
    def test_schema_and_ids(self):
        self.q['schema_version']='unknown'
        with self.assertRaises(GateError):run(self.q,self.root/'out')
    def test_branch_mixing_rejected(self):
        job=self.q['jobs'].pop(1);p=Path(job['result_ref']['path']);r=read(p/'result.json');n=read(p/'native.json.gz')
        request=read(p/'request.json');r['branch']=request['profile']='review_assisted'
        self.packet('reviewed','traffic',r,n,{'request.json':request})
        self.binding['traffic'][0]['job_id']='reviewed';self.reject('BRANCH_MISMATCH')
    def test_frame_gap_rejected(self):
        job=self.q['jobs'].pop(1);p=Path(job['result_ref']['path']);r=read(p/'result.json');n=read(p/'native.json.gz')
        r['scope']['processed_frames']=n['report']['frame_count']=8999;r['native_semantic_sha256']=semantic_hash(n)
        self.packet('gap','traffic',r,n,{'request.json':read(p/'request.json')})
        self.binding['traffic'][0]['job_id']='gap';self.reject('FRAME_GAP')
    def test_null_versions_allowed_only_for_current_run(self):
        self.binding['area']['result_version']=None;self.reject('VERSION_MISMATCH')
    def test_current_run_joins_versions_after_facades_finish(self):
        from traffic_location.integration.adapters import execute
        specs={j['id']:deepcopy(j) for j in self.q['jobs']}
        write(self.root/'dummy.json',{})
        for j in self.q['jobs']:
            j.pop('result_ref');j.update(action='run',root=str(self.root),request_ref={
                'path':str(self.root/'dummy.json'),'sha256':sha(self.root/'dummy.json')})
        self.binding['area']['result_version']=None
        for b in self.binding['traffic']:b['result_version']=None
        with patch('traffic_location.integration.workflow.execute',side_effect=lambda j,root,out:execute(specs[j['id']],root,out)):
            r=self.flow()
        self.assertEqual(r['ppac']['std_total'],241)
        self.assertIsNotNone(r['ppac']['features']['lineage']['area_result_version'])
    def test_reference_provenance(self):
        import hashlib
        p=Path(__file__).resolve().parents[1]/'src/traffic_location/ppac'
        manifest=read(p/'source_manifest.json')
        for r in manifest['reference_files']:
            raw=(p/r['module']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),r['module_sha256'])
            self.assertEqual(hashlib.sha256(raw.replace(b'from . import konstatna as K',b'import konstatna as K')).hexdigest(),r['source_sha256'])
    def use_mvp(self):
        self.params['schema_version']='ppac_parameters_mvp_v2'
        self.params['residential'].pop('combined_coefficient')
        self.params['traffic'].pop('balance_multiplier')
        self.binding['supplemental']=[]
        for b in self.binding['traffic']:b['observed_seconds']=305.67836666666665
    def test_mvp_four_categories_approximate_duration_no_lookups(self):
        self.use_mvp();r=self.flow();p=r['ppac']
        self.assertEqual(r['execution_status'],'SUCCEEDED');self.assertEqual(p['std_total'],272)
        self.assertNotIn('sepeda',p['traffic']['coefficients'])
        self.assertFalse(p['lookup_policy']['enabled']);self.assertEqual(p['lookup_policy']['residential_multiplier'],1)
        self.assertEqual(p['features']['samples']['weekday']['pagi']['motor'],100)
    def test_mvp_partial_area_retained_and_labelled(self):
        self.use_mvp();job=self.q['jobs'].pop(0);p=Path(job['result_ref']['path'])
        r=read(p/'result.json');n=read(p/'native.json.gz');n['status']=r['data_quality_status']='PARTIAL'
        r['native_domain_sha256']=self.domain(n);self.packet('partial-area','area',r,n)
        self.binding['area']['job_id']='partial-area';r=self.flow()
        self.assertEqual(r['ppac']['execution_status'],'SUCCEEDED');self.assertEqual(r['ppac']['result_quality'],'PARTIAL')
    def test_mvp_includes_unverified_buildings_without_changing_area_status(self):
        self.use_mvp();job=self.q['jobs'].pop(0);p=Path(job['result_ref']['path'])
        r=read(p/'result.json');n=read(p/'native.json.gz')
        n['rows'].append({'building_id':'unverified-fixture','winner_store_key':None,
            'count_candidate':0,'market_status':'UNVERIFIED','reason':'PRIMARY_CORRIDOR_UNVERIFIED','scores':[]})
        from traffic_location.location.area.domain.aggregation import reconcile
        n['summary']=reconcile(n['rows']);r['summary']=n['summary']
        n['status']=r['data_quality_status']='PARTIAL';r['native_domain_sha256']=self.domain(n)
        self.packet('unverified-area','area',r,n);self.binding['area']['job_id']='unverified-area'
        result=self.flow();p=result['ppac']
        self.assertEqual(p['execution_status'],'SUCCEEDED');self.assertEqual(p['result_quality'],'UNVERIFIED')
        self.assertEqual(p['features']['allocated_buildings'],1001)
        self.assertEqual(p['residential']['total_penghuni'],4004)
        self.assertEqual(p['residential']['building_basis']['allocated_buildings'],1000)
        self.assertEqual(p['residential']['building_basis']['unverified_buildings_included'],1)
        self.assertEqual(read(self.root/'unverified-area/native.json.gz')['rows'][-1]['market_status'],'UNVERIFIED')

    def test_mvp_pending_not_accepted_or_zero_filled(self):
        self.use_mvp();job=self.q['jobs'].pop(1);p=Path(job['result_ref']['path'])
        r=read(p/'result.json');n=read(p/'native.json.gz');r['result_quality']='PARTIAL'
        n['decisions']=[{'status':'pending'}];r['summary']['pending']=n['aggregate']['pending']=1
        r['native_semantic_sha256']=semantic_hash(n)
        self.packet('partial-traffic','traffic',r,n,{'request.json':read(p/'request.json')})
        self.binding['traffic'][0]['job_id']='partial-traffic';r=self.flow()
        self.assertEqual(r['ppac']['std_total'],272);self.assertEqual(r['ppac']['result_quality'],'PARTIAL')
        self.assertEqual(r['ppac']['features']['upstream_quality']['partial-traffic']['summary']['pending'],1)
    def test_mvp_missing_video_still_rejected(self):
        self.use_mvp();self.binding['traffic']=self.binding['traffic'][:-1];self.reject('OBSERVATIONS_INCOMPLETE')
    def test_mvp_short_clip_still_not_five_minutes(self):
        self.use_mvp();self.binding['traffic'][0]['observed_seconds']=32;self.reject('DURATION_INCOMPATIBLE')
    def test_workflow_lock(self):
        import fcntl
        out=self.root/'out';out.mkdir()
        with (out/'.workflow.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(GateError,'sedang'):run(self.q,out)

if __name__=='__main__':unittest.main()
