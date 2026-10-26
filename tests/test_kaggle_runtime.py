"""No live cloud, apt or inference: fault injection for the real-route adapter."""
from pathlib import Path
import tempfile,unittest
from unittest.mock import Mock,patch
from traffic_location.artifacts import write,sha
from traffic_location.integration.kaggle_runtime import KaggleRuntime,area_config,continue_jobs,error_status

class NotFound(Exception):pass
class Forbidden(Exception):pass

class KaggleRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.client=Mock();self.runtime=KaggleRuntime(self.root/'work',self.root/'config',-.8994976613947719,131.3221639428227,client=self.client)
        write(self.root/'config/fresh_request.json',{'artifacts':{k:{'path':name,'sha256':'a'*64} for k,name in [('detector','yolo26m.pt'),('reid','yolo26n-reid.onnx')]}})
    def test_sorong_target_and_projection_not_old_location(self):
        q=area_config(-.8994976613947719,131.3221639428227)
        self.assertEqual(q['CONFIG']['metric_crs'],'EPSG:32752')
        self.assertEqual(q['MARKET_CONFIG']['target']['longitude'],131.3221639428227)
        self.assertEqual(q['MARKET_CONFIG']['sources']['indomaret_calculation_radius_m'],800)
    def test_gcs_unknown_notfound_denied_ready_distinct(self):
        self.assertEqual(self.runtime.state['gcs']['status'],'NOT_CHECKED')
        blob=self.client.bucket.return_value.blob.return_value
        blob.reload.side_effect=NotFound();self.assertEqual(self.runtime.object_status({'object':'x'})['status'],'NOT_FOUND')
        blob.reload.side_effect=Forbidden();self.assertEqual(self.runtime.object_status({'object':'x'})['status'],'ACCESS_DENIED')
        blob.reload.side_effect=None;blob.generation=12;blob.size=3
        self.assertEqual(self.runtime.object_status({'object':'x','generation':12,'bytes':3})['status'],'READY')
        self.assertEqual(self.runtime.object_status({'object':'x','generation':11})['status'],'ERROR')
    def test_probe_does_not_download_or_build_area(self):
        blob=self.client.bucket.return_value.blob.return_value;blob.generation=1;blob.size=1
        with patch.object(self.runtime,'object_status',return_value={'status':'READY','generation':1,'bytes':1}):
            r=self.runtime.probe()
        self.assertEqual(r['gcs']['status'],'READY');self.assertEqual(r['gcs']['area_source'],'BUILDABLE_FROM_PINNED_PBF')
        blob.download_to_filename.assert_not_called()
    def test_hash_mismatch_never_publishes_staged_file(self):
        dest=self.root/'input.zip';blob=self.client.bucket.return_value.blob.return_value
        blob.download_to_filename.side_effect=lambda path,**kw:Path(path).write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'Checksum'):
            self.runtime.stage({'object':'source','generation':9,'sha256':'a'*64},dest)
        self.assertFalse(dest.exists());self.assertFalse(dest.with_name(dest.name+'.partial').exists())
        blob.download_to_filename.assert_called_once_with(str(dest)+'.partial',if_generation_match=9)
    def test_stage_good_hash_and_cache_avoids_new_download(self):
        source=self.root/'source';source.write_bytes(b'hello');digest=sha(source)
        blob=self.client.bucket.return_value.blob.return_value
        blob.download_to_filename.side_effect=lambda path,**kw:Path(path).write_bytes(b'hello')
        dest=self.root/'local';ref={'object':'source','generation':2,'sha256':digest}
        self.runtime.stage(ref,dest);self.runtime.stage(ref,dest);self.assertEqual(blob.download_to_filename.call_count,1)
    def test_cache_write_denied_does_not_destroy_verified_local(self):
        p=self.root/'model';p.write_bytes(b'weights')
        self.client.bucket.return_value.blob.return_value.upload_from_filename.side_effect=Forbidden()
        self.assertEqual(self.runtime.cache_upload(p,'models/x')['status'],'ACCESS_DENIED');self.assertTrue(p.exists())
    def test_area_failure_does_not_cancel_traffic_and_ppac_is_blocked(self):
        inventory=[{'id':'T7SL-WEEKDAY-PAGI','status':'READY','duration_seconds':303.,'slot':{'sha256':'b'*64}}]
        result={'execution_status':'SUCCEEDED','jobs':[{'id':'T7SL-WEEKDAY-PAGI','engine':'traffic','quality':'PARTIAL',
                'summary':{'accepted_total':2},'result_version':'c'*64,'result_ref':{'path':'dummy','sha256':'d'*64}}]}
        with patch.object(self.runtime,'video_inventory',return_value=inventory),patch.object(self.runtime,'run_area',side_effect=RuntimeError('fixture failure')),patch.object(self.runtime,'run_video',return_value=result) as video:
            r=self.runtime.execute('workflow',{},target_confirmed=True)
        video.assert_called_once();self.assertEqual([x['execution_status'] for x in r['engines']],['FAILED','SUCCEEDED'])
        self.assertEqual(r['ppac']['execution_status'],'BLOCKED');self.assertIsNone(r['ppac']['std_total'])
        self.assertTrue((Path(r['output'])/'summary.json').is_file())
    def test_one_video_failure_does_not_cancel_next_video(self):
        items=[{'id':'bad'},{'id':'good'}]
        def callback(item):
            if item['id']=='bad':raise ValueError('bad')
            return 3
        self.assertEqual([r['status'] for r in continue_jobs(items,callback)],['FAILED','SUCCEEDED'])
    def test_no_runtime_setup_on_module_import_or_constructor(self):
        with patch('traffic_location.integration.kaggle_runtime.subprocess.run') as proc:
            KaggleRuntime(self.root/'other',self.root,0,131)
        proc.assert_not_called()
    def test_missing_gcs_models_bootstrap_exact_official_weights_and_cache(self):
        seed=self.root/'seed';seed.write_bytes(b'SOFTWARE_FIXTURE_WEIGHTS');digest=sha(seed)
        write(self.root/'config/fresh_request.json',{'artifacts':{k:{'path':name,'sha256':digest} for k,name in [('detector','yolo26m.pt'),('reid','yolo26n-reid.onnx')]}})
        self.client.bucket.return_value.blob.return_value.reload.side_effect=NotFound()
        response=Mock();response.iter_content.return_value=[seed.read_bytes()]
        context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
        get=Mock(return_value=context)
        with patch.dict('sys.modules',{'requests':Mock(get=get)}),patch.object(self.runtime,'cache_upload',return_value={'status':'STORED'}) as upload:
            result=self.runtime.prepare_models()
            self.assertEqual(get.call_count,2);self.assertEqual(upload.call_count,2)
            self.assertEqual(sha(result['detector']),digest)
            self.runtime.prepare_models();self.assertEqual(get.call_count,2)
        self.assertEqual(self.runtime.state['models']['detector']['source'],'VERIFIED_LOCAL_CACHE')
    def test_model_access_denied_does_not_trigger_unannounced_download(self):
        get=Mock()
        with patch.object(self.runtime,'object_status',return_value={'status':'ACCESS_DENIED'}),patch.dict('sys.modules',{'requests':Mock(get=get)}):
            with self.assertRaisesRegex(ValueError,'Akses model GCS gagal'):self.runtime.prepare_models()
            get.assert_not_called()
    def test_area_ingestion_runs_fresh_process_not_notebook(self):
        with patch.object(self.runtime,'setup_runtime',return_value={'status':'READY','core_python':'/usr/bin/python3','osmium':'osmium'}),patch('traffic_location.integration.kaggle_runtime.subprocess.run') as proc:
            def result(*args,**kw):
                write(self.runtime.base/'area-preparation-result.json',{'area':{'status':'READY'},'request':{'test':'request'}})
            proc.side_effect=result
            self.assertEqual(self.runtime.prepare_area(),{'test':'request'})
        command=proc.call_args.args[0];self.assertIn('traffic_location.integration.kaggle_runtime',command)
        self.assertIn('prepare-area',command)

if __name__=='__main__':unittest.main()
