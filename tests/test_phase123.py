"""Review authority, immutable requests, source/storage failures and component states."""
import copy,importlib.util,json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from traffic_location.artifacts import read,write,semantic_hash
from traffic_location.integration import job_input,job_status
from traffic_location.integration.result_status import annotate
from traffic_location.integration.failure_details import category

class InputTests(unittest.TestCase):
    def test_review_rejects_coordinate_mode_parameter_and_video_changes(self):
        value={'latitude':-7.33,'longitude':110.504,'mode':'area','parameters':{'days':7},'videos':[{'sha256':'a'}]}
        token=job_input.review(value)
        self.assertEqual(job_input.checked_review(value,token,True),value)
        for key,new in (('longitude',105.048),('mode','traffic'),('parameters',{'days':6}),('videos',[{'sha256':'b'}])):
            changed=copy.deepcopy(value);changed[key]=new
            with self.assertRaisesRegex(ValueError,'INPUT|Input berubah'):job_input.checked_review(changed,token,True)
        with self.assertRaises(ValueError):job_input.checked_review(value,token,False)
        self.assertEqual(token['values'],value)
    def test_snapshot_copies_inputs_and_is_create_once_and_gcs_is_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            context={'target_id':'TGDI','period_id':'2026-10-28','latitude':-7.33,'longitude':110.504}
            params={'traffic':{'hours':15}};inventory=[{'id':'v','slot':{'sha256':'a'}}]
            snap=job_input.freeze(Path(d),'area',context,params,inventory)
            params['traffic']['hours']=24;context['longitude']=105;inventory[0]['slot']['sha256']='b'
            saved=read(Path(d)/'job-input.json')
            self.assertEqual(saved['context']['longitude'],110.504);self.assertEqual(saved['parameters']['traffic']['hours'],15)
            self.assertEqual(saved['videos'][0]['slot']['sha256'],'a')
            self.assertEqual(saved['input_sha256'],semantic_hash({k:v for k,v in saved.items() if k!='input_sha256'}))
            with self.assertRaisesRegex(ValueError,'dibekukan'):job_input.freeze(Path(d),'area',saved['context'],{},[])
            storage=Mock();destination=Mock(bucket='aretfak-location-intelligence')
            uri=job_input.upload(snap,destination,storage)
            args=storage.bucket.return_value.blob.return_value.upload_from_string.call_args
            self.assertEqual(args.kwargs['if_generation_match'],0);self.assertEqual(args.kwargs['checksum'],'crc32c')
            self.assertIn(snap['job_id']+'/inputs/job-input.json',uri)

class StatusTests(unittest.TestCase):
    def test_stage_duration_and_history_and_source_error_classification(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('traffic_location.integration.job_status.time.time',side_effect=[100,120,130]):
                job_status.stage(d,'market_allocation');job_status.stage(d,'market_allocation','SUCCEEDED');job_status.stage(d,'renderer')
            report=read(Path(d)/'job-status.json')
            self.assertEqual(report['stage_started_epoch'],130)
            self.assertEqual(report['events'][1]['duration_seconds'],20)
        self.assertEqual(category('PBF_NO_ROADS_IN_REQUESTED_EXTENT'),'SOURCE_DATA_UNAVAILABLE')
        self.assertEqual(category('AREA_FROZEN_RUNTIME_MISMATCH'),'RUNTIME_ERROR')
        self.assertEqual(category('INPUT_REVIEW_REQUIRED'),'INPUT_ERROR')
    def test_stale_running_checkpoint_does_not_claim_progress_or_scan_source_tree(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'runs/job/checkpoint.json',{'stage':'market_allocation','status':'RUNNING','pid':123,'updated_epoch':100,'stage_started_epoch':50})
            write(root/'area-source/large/job-status.json',{'stage':'must-not-show','status':'RUNNING'})
            with patch('traffic_location.integration.job_status.time.time',return_value=200),patch('traffic_location.integration.job_status.observation',return_value={'process_alive':True}):
                text='\n'.join(job_status.lines(root,0))
            self.assertIn('150 detik',text);self.assertIn('100 detik',text);self.assertIn('bukan bukti',text)
            self.assertNotIn('must-not-show',text)
    def test_component_availability_is_separate_from_execution_and_total(self):
        p={'execution_status':'SUCCEEDED','std_total':None,'residential':{'building_basis':{'status':'UNVERIFIED'}},'fasum':{'std_fasum':0}}
        annotate(p,'area')
        self.assertEqual(p['components_status'],{'residential':'UNVERIFIED','fasum':'AVAILABLE','traffic':'NOT_REQUESTED'})
        self.assertEqual(p['std_total_status'],'INCOMPLETE')
        p={'execution_status':'BLOCKED','std_total':None,'traffic':{'status':'sementara'}};annotate(p,'workflow')
        self.assertEqual(p['components_status']['traffic'],'INCOMPLETE');self.assertEqual(p['components_status']['residential'],'UNAVAILABLE')

class OrchestrationTests(unittest.TestCase):
    def fixture(self):
        import test_component_flow as f
        case=f.ComponentFlowTests('runTest');case.setUp();self.addCleanup(case.doCleanups);return case
    def test_frozen_job_id_binds_final_cloud_manifest_and_coordinates(self):
        from traffic_location.integration.cloud_publish import prepare
        from traffic_location.integration.cloud_schema import CloudDestination
        f=self.fixture();identity={'job_id':'job_'+'9'*32,'review_sha256':'a'*64}
        with patch.dict(os.environ,{'LI_PHASE123':'1'}),patch.object(f.runtime,'video_inventory',return_value=[]),patch.object(f.runtime,'_scheduled_tasks',side_effect=f.schedule):
            r=f.runtime.execute('area',f.f.params,request_identity=identity)
        snapshot=read(Path(r['output'])/'job-input.json')
        request=prepare(Path(r['output']),r,[],snapshot['context'],f.f.params,CloudDestination())
        self.assertEqual(request['job_id'],identity['job_id'])
        self.assertTrue(any(e['object'].endswith('/inputs/job-input.json') for e in request['entries']))
        self.assertEqual(snapshot['context']['longitude'],f.runtime.longitude)
    def test_external_parameter_edits_do_not_change_running_job_or_snapshot(self):
        f=self.fixture()
        def changing(tasks,root):
            f.f.params['residential']['swot_factor']=10000
            yield from f.schedule(tasks,root)
        with patch.dict(os.environ,{'LI_PHASE123':'1'}),patch.object(f.runtime,'_scheduled_tasks',side_effect=changing):
            result=f.runtime.execute('area',f.f.params,request_identity={'review_sha256':'a'*64})
        self.assertEqual(result['ppac']['residential']['std_residential'],84)
        self.assertEqual(read(Path(result['output'])/'job-input.json')['parameters']['residential']['swot_factor'],1)

    def test_snapshot_storage_failure_prevents_engine_launch(self):
        f=self.fixture();f.runtime.publication=Mock(bucket='aretfak-location-intelligence')
        storage=Mock();storage.bucket.return_value.blob.return_value.upload_from_string.side_effect=OSError('fixture storage unavailable')
        with patch.dict(os.environ,{'LI_PHASE123':'1'}),patch.object(f.runtime,'connect',return_value=storage),patch.object(f.runtime,'_scheduled_tasks') as engines:
            with self.assertRaisesRegex(ValueError,'fixture storage unavailable'):f.runtime.execute('area',f.f.params,request_identity={'review_sha256':'a'*64})
            engines.assert_not_called()
    def test_phase_ui_requires_review_without_starting_runtime(self):
        import test_gradio_ui as f
        from traffic_location.integration.gradio_app import Controller
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LI_PHASE123':'1','LI_COMPONENT_FLOW':'1'}):
            root=Path(d);write(root/'config/experiment.json',{'videos':[]});controller=Controller(root/'ui',root/'config',runtime_factory=Mock())
            result=list(controller.process(*f.inputs(mode='Area Coverage')))
            self.assertIn('konfirmasi',result[0][0]);controller.runtime_factory.assert_not_called()

class SnapshotReaderTests(unittest.TestCase):
    def readback(self,mismatch=False):
        from traffic_location.integration.cloud_results import ResultsReader
        from traffic_location.integration.cloud_schema import CloudDestination
        with tempfile.TemporaryDirectory() as d:
            snap=job_input.freeze(Path(d),'area',{'target_id':'TGDI','period_id':'2026-10-28','latitude':-7.33,'longitude':110.504},{},[],{'review_sha256':'a'*64})
        job={**snap['context'],'job_id':snap['job_id'],'manifest_uri':'gs://aretfak-location-intelligence/jobs/TGDI/2026-10-28/'+snap['job_id']+'/manifest.json','manifest_sha256':'b'*64}
        if mismatch:job['longitude']=105.048
        manifest={'job_id':snap['job_id'],'files':[{'object':'jobs/TGDI/2026-10-28/'+snap['job_id']+'/inputs/job-input.json','sha256':'c'*64}]}
        reader=ResultsReader(CloudDestination(),Mock(),Mock())
        reader.query=Mock(side_effect=[[job],[],[],[]])
        reader.verified_bytes=Mock(side_effect=lambda job,uri,*a:json.dumps(manifest if uri.endswith('/manifest.json') else snap).encode())
        return reader.load('TGDI',job['job_id'])
    def test_result_identity_shows_exact_snapshot_coordinates_and_review(self):
        result=self.readback()
        self.assertEqual(result['input_snapshot']['context']['longitude'],110.504)
        self.assertIn('110.504',result['identity_text']);self.assertIn('Review SHA256',result['identity_text'])
    def test_different_bq_coordinate_cannot_be_presented_as_confirmed_snapshot(self):
        result=self.readback(True)
        self.assertNotIn('input_snapshot',result)
        self.assertIn('INPUT_SNAPSHOT_CONTEXT_MISMATCH',' '.join(result['artifact_status']))

class LiveResultTests(unittest.TestCase):
    def test_failed_publication_keeps_current_ppac_and_never_loads_previous_job(self):
        from traffic_location.integration.gradio_app import Controller
        from traffic_location.integration.ppac_view import rows
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'config/experiment.json',{'videos':[]})
            c=Controller(root/'ui',root/'config');write(root/'run/publication-status.json',{'status':'FAILED'})
            pointer={'output':str(root/'run'),'job_id':'job_'+'1'*32,'context':{'target_id':'TGDI','latitude':-7.33,'longitude':110.504}}
            with patch.object(c,'cloud_results') as old:
                response=c.current_cloud_results(pointer,'TGDI','job_'+'2'*32,rows({'execution_status':'SUCCEEDED','residential':{'std_residential':84},'std_total':None,'scope':'area'}))
            old.assert_not_called();self.assertIn('belum terbukti tersimpan',response[0])
            self.assertIn(84,response[11]['Total'].tolist());self.assertIn('110.504',response[-1])

@unittest.skipUnless(importlib.util.find_spec('folium'),'Run native presentation environment')
class PreviewTests(unittest.TestCase):
    def test_preview_keeps_exact_target_and_contains_pin_before_confirmation(self):
        import test_gradio_ui as f
        from traffic_location.integration.gradio_app import Controller
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'config/experiment.json',{'videos':[]});c=Controller(root/'ui',root/'config')
            token,html,summary,confirmed=c.preview_job(*f.inputs(mode='Area Coverage',latitude=-7.33058110387148,longitude=110.50486365193136))
            self.assertIsNotNone(token);self.assertIn('iframe',html)
            self.assertEqual(json.loads(summary)['Longitude'],110.50486365193136)
            self.assertFalse(confirmed)

if __name__=='__main__':unittest.main()
