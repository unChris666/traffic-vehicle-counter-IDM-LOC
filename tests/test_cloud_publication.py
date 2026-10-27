"""Mock transport and explicit software-ledger fixtures; no cloud writes."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import tempfile,unittest,json,hashlib,base64
from traffic_location.artifacts import read,write,sha,semantic_hash
from traffic_location.persistence import publish
from traffic_location.integration.adapters import ref
from traffic_location.integration.cloud_schema import CloudDestination,SCHEMAS,setup_sql,publication_sql
from traffic_location.integration.cloud_publish import prepare,CloudPublisher

class NotFound(Exception):pass

def fixture_crc(path):return base64.b64encode(hashlib.sha256(Path(path).read_bytes()).digest()[:4]).decode()

class Blob:
    def __init__(self):self.data=None;self.metadata=None;self.generation=1;self.uploads=0
    def reload(self,**kw):
        if self.data is None:raise NotFound()
    @property
    def size(self):return len(self.data)
    def upload_from_filename(self,path,**kw):
        assert kw['if_generation_match']==0 and kw['checksum']=='crc32c'
        self.data=Path(path).read_bytes();self.crc32c=fixture_crc(path);self.uploads+=1

class Bucket:
    def __init__(self):self.blobs={}
    def reload(self,**kw):pass
    def blob(self,name):return self.blobs.setdefault(name,Blob())

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.context={'target_id':'SOFTWARE_FIXTURE','period_id':'2026-10-27','latitude':0.,'longitude':0.}
        self.destination=CloudDestination();self.video=self.root/'source.mp4';self.video.write_bytes(b'SOFTWARE_FIXTURE_NO_INFERENCE')
        source={'video_sha256':sha(self.video)}
        events=[{'event_id':'measured','category':'motorcycle','direction':'A_TO_B','accepted_count_event':True,'status':'accepted','evidence':{'measured_crossing':True}},
                {'event_id':'estimated','category':'car','direction':'B_TO_A','accepted_count_event':True,'status':'accepted','evidence':{'measured_crossing':False}}]
        native={'events':events,'aggregate':{'total':2,'measured_total':1,'inferred_total':1,'pending':1,'invalid':0,
                'by_category':{'car':1,'motorcycle':1},'by_direction':{'A_TO_B':1,'B_TO_A':1}},'decisions':[{'status':'pending'}],
                'invalid_decisions':[],'source_identity':source,'report':{'frame_count':30,'supported_categories':['motorcycle','car','bus','truck','pedestrian']}}
        r={'schema_version':'traffic_result_v2','execution_status':'SUCCEEDED','result_version':'a'*64,'branch':'machine',
           'counting_executed':True,'operation_executed':'count_replay','scope':{'source_frames':30,'processed_frames':30},
           'source_identity':source,'result_quality':'PARTIAL','native_semantic_sha256':semantic_hash(native),
           'summary':{'accepted_total':2,'accepted_measured':1,'accepted_estimated':1,'pending':1,'invalid':0}}
        folder=self.root/'engine';publish(folder,{'result.json':r,'native.json.gz':native,
             'request.json':{'source_identity':source,'profile':'machine','frame_count':30,'artifacts':{},'software_fixture':True}},
             metadata={'engine':'traffic','result_version':r['result_version']})
        self.result={'engines':[{'id':'upload_fixture','engine':'traffic','execution_status':'SUCCEEDED','quality':'PARTIAL','summary':r['summary'],'result_ref':ref(folder)}],
                     'ppac':{'execution_status':'BLOCKED','std_total':None,'diagnostics':[{'code':'OBSERVATIONS_INCOMPLETE'}]}}
        self.inventory=[{'id':'upload_fixture','path':str(self.video),'filename':'source.mp4','duration_seconds':1.,
                         'slot':{'sha256':sha(self.video),'decoded_frames':30,'day':'weekday','session':'pagi'}}]
        self.output=self.root/'job';self.output.mkdir()
        self.bucket=Bucket();self.storage=Mock();self.storage.bucket.return_value=self.bucket
        self.bq=Mock();self.bq.get_dataset.return_value=SimpleNamespace(location='US')
        self.bq.get_table.side_effect=lambda name,**kw:SimpleNamespace(schema=[SimpleNamespace(name=k,field_type=v) for k,v in SCHEMAS[name.split('.')[-1]].items()])
    def prepared(self):return prepare(self.output,self.result,self.inventory,self.context,{},self.destination)
    def publisher(self):return CloudPublisher(self.destination,self.storage,self.bq)
    def test_owner_destinations_and_setup_are_explicit_non_destructive(self):
        self.assertEqual(self.destination.bucket,'aretfak-location-intelligence')
        self.assertEqual(self.destination.dataset,'locdeproject.location_intelligence')
        sql=setup_sql();self.assertEqual(sql.count('CREATE TABLE IF NOT EXISTS'),5)
        self.assertEqual(sql.count('CREATE VIEW IF NOT EXISTS'),2);self.assertNotIn('DROP ',sql);self.assertNotIn('REPLACE',sql)
        checked=(Path(__file__).resolve().parents[1]/'sql/location_intelligence_setup.sql').read_text();self.assertEqual(checked,sql)
    def test_flat_counts_are_only_accepted_ledger_not_pending(self):
        q=self.prepared();rows=q['rows']['traffic_counts'];self.assertEqual(sum(r['accepted_count'] for r in rows),2)
        self.assertEqual(sum(r['accepted_count'] for r in rows if r['evidence_level']=='measured'),1)
        self.assertEqual(q['rows']['traffic_videos'][0]['pending'],1)
        self.assertIsNone(q['rows']['ppac_results'][0]['std_total']);self.assertEqual(q['rows']['traffic_videos'][0]['result_quality'],'PARTIAL')
        self.assertEqual(q,self.prepared());self.assertTrue(all(e['object'].startswith('jobs/SOFTWARE_FIXTURE/2026-10-27/'+q['job_id']+'/') for e in q['entries']))
    def test_failed_missing_input_is_not_a_zero_count(self):
        self.result['engines'][0]={'id':'upload_fixture','engine':'traffic','execution_status':'FAILED'};self.inventory[0]['path']=None
        q=self.prepared();self.assertEqual(q['rows']['traffic_counts'],[])
        self.assertIsNone(q['rows']['traffic_videos'][0]['accepted_measured']);self.assertEqual(q['rows']['job_runs'][0]['execution_status'],'FAILED')
    def test_receipt_cannot_change_verified_summary_or_quality(self):
        self.result['engines'][0]['summary']['accepted_measured']=999
        with self.assertRaisesRegex(ValueError,'Rekap receipt'):self.prepared()
        self.result['engines'][0]['summary']['accepted_measured']=1
        self.result['engines'][0]['quality']='COMPLETE_WITHIN_DECLARED_SCOPE'
        with self.assertRaisesRegex(ValueError,'Kualitas receipt'):self.prepared()
    def test_inventory_cannot_relabel_another_video(self):
        self.inventory[0]['slot']['sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'sumber'):self.prepared()
    def test_cloud_metadata_transaction_and_idempotent_object_retry(self):
        q=self.prepared();publisher=self.publisher()
        with patch('traffic_location.integration.cloud_publish._crc32c',side_effect=fixture_crc),patch.object(publisher,'commit') as commit:
            first=publisher.publish(self.output);second=publisher.publish(self.output)
        self.assertEqual(first,second);self.assertEqual(commit.call_count,2)
        self.assertTrue(all(b.uploads==1 for b in self.bucket.blobs.values()))
        self.assertTrue(list(self.bucket.blobs)[-1].endswith('/manifest.json'));self.assertEqual(first['status'],'READY')
    def test_missing_bq_table_fails_before_uploading_large_inputs(self):
        self.prepared();self.bq.get_table.side_effect=NotFound()
        with self.assertRaisesRegex(ValueError,'belum ada'):self.publisher().publish(self.output)
        self.assertFalse(self.bucket.blobs)
    def test_conflicting_object_is_never_overwritten(self):
        q=self.prepared();publisher=self.publisher();entry=q['entries'][0]
        blob=self.bucket.blob(entry['object']);blob.data=b'wrong';blob.crc32c='wrong';blob.metadata={'sha256':entry['sha256']}
        with patch('traffic_location.integration.cloud_publish._crc32c',side_effect=fixture_crc),patch.object(publisher,'commit') as commit:
            with self.assertRaisesRegex(ValueError,'ditimpa'):publisher.publish(self.output)
            commit.assert_not_called()
        self.assertEqual(blob.data,b'wrong');self.assertFalse((self.output/'publication-status.json').exists())
    def test_bq_failure_has_no_success_marker_and_retry_needs_no_engine(self):
        self.prepared();p=self.publisher()
        with patch('traffic_location.integration.cloud_publish._crc32c',side_effect=fixture_crc),patch.object(p,'commit',side_effect=RuntimeError('fixture failure')):
            with self.assertRaises(RuntimeError):p.publish(self.output)
        self.assertFalse((self.output/'publication-status.json').exists())
    def test_modified_summary_cannot_reach_the_cloud(self):
        q=self.prepared();q['rows']['traffic_counts'][0]['accepted_count']=999
        write(self.output/'publication-request.json',q)
        with self.assertRaisesRegex(ValueError,'Rekap berubah'):self.publisher().publish(self.output)
        self.bq.get_dataset.assert_not_called();self.assertFalse(self.bucket.blobs)
    def test_same_job_cannot_publish_concurrently_on_this_host(self):
        import fcntl
        self.prepared()
        with (self.output/'.publication.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError,'proses lain'):self.publisher().publish(self.output)
        self.bq.get_dataset.assert_not_called()
    def test_sql_is_one_transaction_parameters_and_job_scoped_replacement(self):
        sql=publication_sql(self.destination)
        self.assertTrue(sql.startswith('BEGIN TRANSACTION;'));self.assertTrue(sql.endswith('COMMIT TRANSACTION;'))
        self.assertEqual(sql.count('DELETE FROM'),len(SCHEMAS));self.assertEqual(sql.count('WHERE job_id=@job_id'),len(SCHEMAS)+1)
        self.assertIn('manifest_sha256!=@manifest_sha256',sql)
        for table in SCHEMAS:self.assertIn('@rows_'+table,sql)
        with self.assertRaises(ValueError):CloudDestination(dataset='project.dataset`; DROP TABLE x')


class BigQuerySdkTests(unittest.TestCase):
    def test_sdk_query_has_typed_parameters_location_and_budget(self):
        try:from google.cloud import bigquery
        except ImportError:self.skipTest('Optional Google SDK installed in cloud integration runtime')
        bq=Mock();publisher=CloudPublisher(CloudDestination(),Mock(),bq);publisher.location='US'
        request={'job_id':'job_fixture','manifest_sha256':'a'*64,'rows':{name:[] for name in SCHEMAS}}
        publisher.commit(request)
        config=bq.query.call_args.kwargs['job_config'];self.assertIsInstance(config,bigquery.QueryJobConfig)
        self.assertEqual(config.maximum_bytes_billed,268435456)
        self.assertEqual(bq.query.call_args.kwargs['location'],'US')
        self.assertEqual({p.name for p in config.query_parameters},{'job_id','manifest_sha256'}|{'rows_'+t for t in SCHEMAS})

if __name__=='__main__':unittest.main()
