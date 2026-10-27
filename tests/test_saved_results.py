import hashlib,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from traffic_location.integration.cloud_results import ResultsReader
from traffic_location.integration.cloud_schema import CloudDestination
from traffic_location.integration.gradio_app import Controller,UPLOAD_SLOTS,EXTRA_SLOTS
from traffic_location.artifacts import write

class SavedResultTests(unittest.TestCase):
    def setUp(self):
        self.destination=CloudDestination();self.storage=Mock();self.bq=Mock()
        self.bq.get_dataset.return_value.location='asia-southeast1'
        self.reader=ResultsReader(self.destination,self.storage,self.bq)
        self.job={'job_id':'job_'+'1'*32,'target_id':'STORE','period_id':'2026-10-27'}
    def test_queries_are_target_bound_and_failed_map_retains_tables(self):
        responses=[[self.job],[{'video_id':'video','accepted_count':2}],
                   [{'map_html_uri':'gs://wrong/evil','map_html_sha256':'a'*64}],[{'std_total':None,'diagnostics_json':[{'code':'BLOCKED'}]}]]
        self.bq.query.side_effect=[Mock(result=Mock(return_value=r)) for r in responses]
        result=self.reader.load('STORE')
        self.assertEqual(len(result['traffic_counts']),1);self.assertIn('gagal',result['map_status'])
        self.assertIsNone(result['ppac_results'][0]['std_total'])
        self.storage.bucket.assert_not_called()
        for call in self.bq.query.call_args_list:
            self.assertIn('target_id=@target_id',call.args[0]);self.assertEqual(call.kwargs['location'],'asia-southeast1')
            self.assertEqual(call.kwargs['job_config'].maximum_bytes_billed,268435456)
    def test_no_saved_job_is_explicit_not_fake_zero(self):
        self.bq.query.return_value.result.return_value=[]
        with self.assertRaisesRegex(ValueError,'Belum ada hasil'):self.reader.load('STORE')
        self.storage.bucket.assert_not_called()
    def test_bad_ids_do_not_query(self):
        for target,job in [('x` UNION SELECT',None),('STORE',"job_' OR 1=1")]:
            with self.assertRaises(ValueError):self.reader.load(target,job)
        self.bq.query.assert_not_called()
    def test_map_bytes_hash_generation_and_iframe_isolation(self):
        html=b'<html><script>window.example=1</script>Folium Esri</html>'
        blob=self.storage.bucket.return_value.blob.return_value
        blob.size=len(html);blob.generation=7;blob.download_as_bytes.return_value=html
        area={'map_html_uri':f"gs://{self.destination.bucket}/jobs/STORE/2026-10-27/{self.job['job_id']}/engines/area/area/map.html",'map_html_sha256':hashlib.sha256(html).hexdigest()}
        view=self.reader.map_html(self.job,area)
        self.assertIn('sandbox="allow-scripts"',view);self.assertNotIn('allow-same-origin',view)
        self.assertIn('&lt;script&gt;',view)
        self.assertEqual(blob.download_as_bytes.call_args.kwargs['if_generation_match'],7)
        blob.download_as_bytes.return_value=b'changed'
        with self.assertRaisesRegex(ValueError,'Checksum'):self.reader.map_html(self.job,area)
    def test_map_size_limit_prevents_download(self):
        blob=self.storage.bucket.return_value.blob.return_value;blob.size=65*1024**2
        area={'map_html_uri':f"gs://{self.destination.bucket}/jobs/STORE/2026-10-27/{self.job['job_id']}/engines/area/area/map.html",'map_html_sha256':'1'*64}
        with self.assertRaisesRegex(ValueError,'Ukuran'):self.reader.map_html(self.job,area)
        blob.download_as_bytes.assert_not_called()

class SlotTests(unittest.TestCase):
    def test_slots_assign_day_session_without_review_and_do_not_shift_empty_slots(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);write(root/'config/experiment.json',{'videos':[]})
            write(root/'config/geometry/T7SL-WEEKDAY-PAGI.json',{})
            c=Controller(root/'ui',root/'config',runtime_factory=Mock())
            files=[None]*14;files[1]='weekday-siang.mp4';files[7]='weekend-malam.mp4'
            prepared=[{'id':'one','filename':'one','reviewed':False},{'id':'two','filename':'two','reviewed':False}]
            with patch('traffic_location.integration.uploads.prepare',return_value=prepared):rows,_,status=c.prepare_slots(*files)
            self.assertEqual(rows[0]['upload_slot'],['weekday','siang']);self.assertEqual(rows[1]['upload_slot'],['weekend','malam'])
            self.assertFalse(rows[0]['reviewed']);self.assertIn('weekday/pagi',status)
            self.assertEqual(len(UPLOAD_SLOTS),8);self.assertEqual(len(EXTRA_SLOTS),6)
            with patch('traffic_location.integration.uploads.review') as review:
                _,status=c.save_review(rows,'one','weekend','siang','A_TO_B',True)
                review.assert_not_called();self.assertIn('sesuai slot',status)

class BundledRuntimeTests(unittest.TestCase):
    def test_bundled_mode_never_calls_installers(self):
        from traffic_location.integration.kaggle_runtime import KaggleRuntime
        with tempfile.TemporaryDirectory() as t,patch.dict('os.environ',{'LI_RUNTIME_MODE':'bundled'}):
            runtime=KaggleRuntime(t,t,0,0)
            with patch('traffic_location.integration.container_runtime.verify_runtime',return_value={'status':'READY'}) as verify,patch('subprocess.run') as proc:
                runtime.setup_runtime('area');runtime.setup_runtime('traffic')
                proc.assert_not_called();self.assertEqual(verify.call_count,2)
    def test_adc_does_not_import_kaggle_secret(self):
        from traffic_location.integration.kaggle_runtime import KaggleRuntime
        with tempfile.TemporaryDirectory() as t,patch.dict('os.environ',{'LI_AUTH_MODE':'adc'}),patch('google.auth.default',return_value=(Mock(),'locdeproject')),patch('google.cloud.storage.Client') as client:
            runtime=KaggleRuntime(t,t,0,0);self.assertIs(runtime.connect(),client.return_value)

if __name__=='__main__':unittest.main()
