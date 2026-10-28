"""Three-mode orchestration using immutable software engine packets, no GPU/cloud."""
import os,unittest
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path
import test_gate2 as fixtures
import test_uploads as upload_fixtures
from traffic_location.integration.kaggle_runtime import KaggleRuntime
from traffic_location.integration.colab_runtime import ColabRuntime
from traffic_location.integration.adapters import inspect
from traffic_location.integration.uploads import valid_inventory
from traffic_location.artifacts import read

class ComponentFlowTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.Gate2Tests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.use_mvp()
        self.env=patch.dict(os.environ,{'LI_COMPONENT_FLOW':'1'});self.env.start();self.addCleanup(self.env.stop)
        self.runtime=KaggleRuntime(self.f.root/'runtime',self.f.root/'config',-6.,106.,target_id='SOFTWARE_FIXTURE',period_id='TEST')
        self.items=[{'id':b['job_id'],'kind':'traffic','status':'READY','filename':b['job_id']+'.mp4',
            'duration_seconds':b['observed_seconds'],'slot':{'day':b['day'],'session':b['session'],'sha256':b['video_sha256']}}
            for b in self.f.binding['traffic']]
        self.seen=[]
    def schedule(self,tasks,root):
        for item in tasks:
            self.seen.append(item['kind'])
            job=next(j for j in self.f.q['jobs'] if j['id']==item['id'])
            h=inspect(job['engine'],job['result_ref'],self.f.root)
            result={'execution_status':'SUCCEEDED','jobs':[{'id':item['id'],'engine':job['engine'],
                'result_ref':job['result_ref'],'result_version':h['result_version'],'summary':h['summary'],'quality':h['quality']}]}
            yield item,result,None
    def run_mode(self,mode,items=None):
        with patch.object(self.runtime,'video_inventory',return_value=self.items if items is None else items),patch.object(self.runtime,'_scheduled_tasks',side_effect=self.schedule):
            return self.runtime.execute(mode,self.f.params,target_confirmed=True)
    def test_area_runs_no_traffic_and_produces_residential_fasum_only(self):
        r=self.run_mode('area');p=r['ppac']
        self.assertEqual(self.seen,['area']);self.assertEqual(p['execution_status'],'SUCCEEDED')
        self.assertEqual(p['residential']['total_penghuni'],4000);self.assertEqual(p['fasum']['std_fasum'],8)
        self.assertNotIn('traffic',p);self.assertIsNone(p['std_total']);self.assertEqual(p['scope'],'area')
    def test_area_component_cloud_payload_preserves_null_total_and_numeric_components(self):
        from traffic_location.integration.cloud_publish import prepare
        from traffic_location.integration.cloud_schema import CloudDestination
        result=self.run_mode('area')
        context={k:self.f.binding['context'][k] for k in ('target_id','period_id','latitude','longitude')}
        request=prepare(Path(result['output']),result,[],context,self.f.params,CloudDestination())
        row=request['rows']['ppac_results'][0]
        self.assertIsNone(row['std_total']);self.assertIsNone(row['std_traffic'])
        self.assertEqual(row['std_residential'],84);self.assertEqual(row['std_fasum'],8)
        entry=next(e for e in request['entries'] if e['object'].endswith('/ppac/result.json'))
        self.assertEqual(read(entry['path'])['scope'],'area')

    def test_traffic_runs_no_area_and_produces_traffic_component_only(self):
        p=self.run_mode('traffic')['ppac']
        self.assertEqual(self.seen,['traffic']*8);self.assertNotIn('residential',p);self.assertNotIn('fasum',p)
        self.assertEqual(p['traffic']['status'],'lengkap');self.assertIsNone(p['std_total'])
    def test_subset_traffic_preserves_missing_observations_and_provisional_status(self):
        p=self.run_mode('traffic',self.items[:1])['ppac']
        self.assertEqual(self.seen,['traffic']);self.assertEqual(p['execution_status'],'SUCCEEDED')
        self.assertTrue(p['traffic']['provisional']);self.assertTrue(p['traffic']['missing_observations'])
        self.assertNotIn('motor',p['features']['samples']['weekend']['pagi']);self.assertIsNone(p['std_total'])
    def test_short_clip_counting_is_preserved_but_excluded_from_ppac_samples(self):
        items=deepcopy(self.items);items[0]['duration_seconds']=32
        result=self.run_mode('traffic',items);p=result['ppac']
        self.assertEqual(len(result['engines']),8)
        self.assertTrue(all(e['execution_status']=='SUCCEEDED' for e in result['engines']))
        self.assertEqual(p['execution_status'],'SUCCEEDED');self.assertTrue(p['traffic']['provisional'])
        self.assertEqual(p['features']['excluded_ppac_samples'][0]['job_id'],items[0]['id'])
        self.assertIsNone(p['std_total'])

    def test_ppac_runs_area_then_traffic_and_preserves_existing_full_formula(self):
        p=self.run_mode('workflow')['ppac']
        self.assertEqual(self.seen,['area']+['traffic']*8);self.assertEqual(p['std_total'],272)
        self.assertEqual(p['execution_status'],'SUCCEEDED');self.assertEqual(p['scope'],'combined')
    def test_combined_subset_keeps_components_while_total_is_blocked(self):
        p=self.run_mode('workflow',self.items[:1])['ppac']
        self.assertEqual(p['execution_status'],'BLOCKED');self.assertIsNone(p['std_total'])
        self.assertIn('residential',p);self.assertIn('fasum',p);self.assertIn('traffic',p)
        self.assertTrue(p['traffic']['provisional'])
    def test_unavailable_dataset_video_is_skipped_and_valid_video_still_runs(self):
        bad=deepcopy(self.items[1]);bad['status']='NOT_FOUND'
        r=self.run_mode('traffic',[self.items[0],bad])
        self.assertEqual(self.seen,['traffic']);self.assertEqual(r['skipped_videos'][0]['status'],'SKIPPED')
        self.assertEqual(r['skipped_videos'][0]['video_id'],bad['id'])
    def test_new_colab_modes_do_not_require_previous_area_job(self):
        runtime=ColabRuntime(self.f.root/'colab',self.f.root/'config',-6.,106.)
        with patch.dict(os.environ,{'LI_RUNTIME_MODE':'bundled','LI_AUTH_MODE':'adc'}),patch.object(KaggleRuntime,'execute',return_value='fixture') as execute:
            self.assertEqual(runtime.execute('traffic',{}),'fixture')
            self.assertEqual(runtime.execute('workflow',{}),'fixture');self.assertEqual(execute.call_count,2)

class ValidUploadTests(unittest.TestCase):
    def test_invalid_and_duplicate_uploads_are_isolated_without_bypassing_integrity(self):
        f=upload_fixtures.UploadFixture('runTest');f.setUp();self.addCleanup(f.doCleanups)
        rows=f.review(f.prepare());bad=deepcopy(rows[0]);bad['id']='unreviewed';bad['reviewed']=False
        valid,skipped=valid_inventory([bad,rows[0],deepcopy(rows[0])],f.upload_root)
        self.assertEqual(len(valid),1);self.assertEqual(len(skipped),2)
        self.assertEqual({s['code'] for s in skipped},{'GEOMETRY_REVIEW_REQUIRED','UPLOAD_DUPLICATE'})
        Path(rows[0]['path']).write_bytes(b'changed')
        valid,skipped=valid_inventory(rows,f.upload_root)
        self.assertFalse(valid);self.assertEqual(skipped[0]['code'],'UPLOAD_CHANGED')


class NewFlowUITests(unittest.TestCase):
    def test_mixed_uploads_select_only_reviewed_and_require_component_parameters(self):
        import test_gradio_ui as ui_fixture
        from traffic_location.integration.gradio_app import validate
        rows=[{'id':'good','reviewed':True},{'id':'bad','reviewed':False}]
        values=ui_fixture.inputs(mode='Traffic Counter',video_ids=[],confirmed=False)+['Upload video',rows]
        with patch.dict(os.environ,{'LI_COMPONENT_FLOW':'1'}):
            result=validate(values,ui_fixture.VIDEOS)
            self.assertEqual(result['video_ids'],['good'])
            values[6]=None
            with self.assertRaises(ValueError):validate(values,ui_fixture.VIDEOS)
    def test_bad_slot_does_not_erase_valid_slot_and_ui_exposes_three_modes(self):
        import tempfile,json
        from traffic_location.artifacts import write
        from traffic_location.integration.gradio_app import Controller,build_app
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LI_COMPONENT_FLOW':'1'}):
            root=Path(d);write(root/'config/experiment.json',{'videos':[]})
            write(root/'config/geometry/T7SL-WEEKDAY-PAGI.json',{})
            bad=root/'bad.mp4';good=root/'good.mp4';bad.write_bytes(b'bad');good.write_bytes(b'good')
            controller=Controller(root/'ui',root/'config')
            def prepare(paths,*args):
                if Path(paths[0])==bad:raise ValueError('VIDEO_STREAM_INVALID')
                return [{'id':'valid','filename':'good.mp4','sha256':'a'*64,'reviewed':False}]
            with patch('traffic_location.integration.uploads.prepare',side_effect=prepare):
                rows,choices,message=controller.prepare_independent_sources(*([str(bad),str(good)]+[None]*26))
            # pathlib converts stat inputs but prepare receives the supplied path string.
            self.assertEqual(rows[0]['upload_slot'],['weekday','siang'])
            self.assertTrue(any(r.get('skip_reason') for r in rows));self.assertIn('dilewati',message)
            app,_=build_app(root/'other',root/'config',default_mode='Area Coverage')
            try:
                config=app.get_config_file();dropdown=next(c['props'] for c in config['components'] if c['props'].get('label')=='Proses')
                self.assertEqual([c[0] for c in dropdown['choices']],['Area Coverage','Traffic Counter','PPAC'])
                self.assertTrue(any(fn.concurrency_id=='diagnostics' for fn in app.fns.values()))
            finally:app.close()

if __name__=='__main__':unittest.main()
