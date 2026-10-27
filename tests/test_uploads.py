"""Upload fixtures validate I/O and review authority, not CV accuracy."""
from pathlib import Path
from copy import deepcopy
import tempfile,unittest
from unittest.mock import patch,Mock
from traffic_location.artifacts import read,write,sha
from traffic_location.integration import uploads
from traffic_location.integration.kaggle_runtime import KaggleRuntime
ROOT=Path(__file__).resolve().parents[1]

class UploadFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.source=self.root/'my-video.mp4';self.source.write_bytes(b'SOFTWARE_FIXTURE_NOT_A_REAL_VIDEO')
        self.template=read(ROOT/'results/t7sl_modular/config/geometry/T7SL-WEEKDAY-PAGI.json')
        self.upload_root=self.root/'uploads'
    def inspector(self,path,preview):
        Path(preview).write_bytes(b'FIXTURE_PREVIEW')
        return {'width':640,'height':480,'decoded_frames':9000,'fps':30.,'duration_seconds':300.,'inspection':'SOFTWARE_FIXTURE'}
    def prepare(self):return uploads.prepare([self.source],self.upload_root,self.template,inspector=self.inspector)
    def review(self,rows):return uploads.review(rows,rows[0]['id'],'weekday','pagi',uploads.DIRECTIONS[0],True,self.upload_root/'geometries')
class UploadTests(UploadFixture):
    def test_source_bytes_preserved_and_template_not_approved_implicitly(self):
        rows=self.prepare();r=rows[0]
        self.assertEqual(sha(r['path']),sha(self.source));self.assertFalse(r['reviewed'])
        self.assertEqual(r['geometry']['normalized'],self.template['normalized'])
        self.assertNotEqual(r['geometry']['source_video']['sha256'],self.template['source_video']['sha256'])
        with self.assertRaisesRegex(ValueError,'Tinjau'):uploads.inventory(rows,self.upload_root)
    def test_review_binds_geometry_metadata_and_full_inspection(self):
        rows=self.review(self.prepare());i=uploads.inventory(rows,self.upload_root)[0]
        self.assertEqual(i['slot']['day'],'weekday');self.assertEqual(i['slot']['decoded_frames'],9000)
        self.assertEqual(read(i['geometry_ref']['path'])['source_video']['sha256'],sha(self.source))
    def test_missing_confirmation_or_slot_rejected(self):
        rows=self.prepare()
        for day,confirmed in [('weekday',False),(None,True)]:
            with self.assertRaises(ValueError):uploads.review(rows,rows[0]['id'],day,'pagi',uploads.DIRECTIONS[0],confirmed,self.upload_root/'geometries')
    def test_geometry_edits_invalidate_existing_review(self):
        rows=self.review(self.prepare());old=deepcopy(rows)
        changed=uploads.edit(rows,rows[0]['id'],'Garis',clear=True)
        self.assertFalse(changed[0]['reviewed']);self.assertNotIn('geometry_ref',changed[0]);self.assertEqual(rows,old)
        with self.assertRaises(ValueError):self.review(changed)
    def test_repeated_sources_and_invalid_format_rejected_before_inference(self):
        with self.assertRaisesRegex(ValueError,'sama'):uploads.prepare([self.source,self.source],self.upload_root,self.template,inspector=self.inspector)
        bad=self.root/'video.txt';bad.write_bytes(b'fixture')
        with self.assertRaises(ValueError):uploads.prepare([bad],self.upload_root,self.template,inspector=self.inspector)
    def test_changed_source_and_inspection_rejected(self):
        rows=self.review(self.prepare());ref=rows[0]['inspection_ref'];Path(ref['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'Inspeksi'):uploads.inventory(rows,self.upload_root)
    def test_paths_outside_upload_workspace_rejected(self):
        rows=self.review(self.prepare());rows[0]['path']=str(self.source)
        with self.assertRaisesRegex(ValueError,'workspace'):uploads.inventory(rows,self.upload_root)
    def test_native_pixel_click_maps_without_resizing_or_homography(self):
        rows=self.prepare();rows=uploads.edit(rows,rows[0]['id'],'Garis',clear=True)
        rows=uploads.edit(rows,rows[0]['id'],'Garis',point=(320,240))
        self.assertEqual(rows[0]['geometry']['normalized']['line']['P1'],[.5,.5])
    def test_upload_execution_does_not_require_t7sl_dataset_or_parse_upload_id(self):
        rows=self.review(self.prepare());video_id=rows[0]['id']
        runtime=KaggleRuntime(self.root/'runtime',ROOT/'results/t7sl_modular/config',0,0,client=Mock(),upload_root=self.upload_root)
        result={'execution_status':'SUCCEEDED','jobs':[{'id':video_id,'engine':'traffic','quality':'PARTIAL',
                'summary':{'accepted_total':0},'result_version':'a'*64,'result_ref':{'path':'fixture','sha256':'b'*64}}]}
        def scheduled(tasks,root):
            self.assertEqual(tasks[0]['slot']['session'],'pagi');yield tasks[0],result,None
        with patch.object(runtime,'video_inventory',side_effect=AssertionError('Dataset must not be read')),patch.object(runtime,'_scheduled_tasks',side_effect=scheduled):
            value=runtime.execute('traffic',{},uploaded_videos=rows)
        self.assertEqual(value['engines'][0]['id'],video_id);self.assertEqual(value['ppac']['execution_status'],'NOT_RUN')
    def test_invalid_dimension_rejected_before_full_decode(self):
        import json
        runner=Mock(return_value=Mock(stdout=json.dumps({'streams':[{'width':100000,'height':100000,'avg_frame_rate':'30/1','duration':'300'}]})))
        with self.assertRaises(ValueError):uploads.inspect_video(self.source,self.root/'preview.png',runner=runner)
        runner.assert_called_once()


class UploadedControllerTests(UploadFixture):
    def test_controller_passes_uploaded_state_to_runtime_without_t7sl_selection(self):
        from traffic_location.integration.gradio_app import Controller
        rows=self.review(self.prepare());seen=[]
        class Runtime:
            def __init__(self,base,*args,**kwargs):self.base=Path(base)
            def execute(self,*args,**kwargs):
                seen.append(kwargs)
                return {'engines':[],'ppac':{'execution_status':'NOT_RUN','std_total':None},'output':str(self.base/'runs/fixture')}
        c=Controller(self.root/'controller',ROOT/'results/t7sl_modular/config',runtime_factory=Runtime)
        values=['Traffic Counter','STORE',0.,0.,'2026-10-27',[],'mainstreet',7,15,False,1.,1.,1.,False,'Upload video',rows]
        output=list(c.process(*values))[-1]
        self.assertEqual(seen[0]['uploaded_videos'],rows)
        self.assertEqual(seen[0]['video_ids'],[rows[0]['id']]);self.assertIsNotNone(output[4])
    def test_uploaded_workflow_binding_never_claims_t7sl_source_provenance(self):
        rows=self.review(self.prepare());video_id=rows[0]['id'];area=self.root/'area';area.mkdir()
        write(area/'result.json',{'result_version':'b'*64})
        r=KaggleRuntime(self.root/'runtime',ROOT/'results/t7sl_modular/config',0,0,client=Mock(),upload_root=self.upload_root)
        def scheduled(tasks,root):
            for task in tasks:
                kind=task['kind'];folder=str(area) if kind=='area' else 'software-fixture'
                yield task,{'execution_status':'SUCCEEDED','jobs':[{'id':task['id'],'engine':kind,'quality':'PARTIAL','summary':{},'result_version':'b'*64,'result_ref':{'path':folder,'sha256':'a'*64}}]},None
        with patch.object(r,'_scheduled_tasks',side_effect=scheduled),patch.object(r,'_experiment_stage',return_value={'ppac':{'execution_status':'BLOCKED','std_total':None}}):
            result=r.execute('workflow',{},uploaded_videos=rows,target_confirmed=True)
        binding=read(Path(result['output'])/'binding.json')
        self.assertIn('User-uploaded source',binding['traffic'][0]['evidence'])
        self.assertNotIn('T7SL',binding['traffic'][0]['evidence'])
        self.assertEqual(binding['traffic'][0]['job_id'],video_id)
    def test_publication_retry_has_no_runtime_setup_or_counting(self):
        from traffic_location.integration.cloud_schema import CloudDestination
        runtime=KaggleRuntime(self.root/'runtime',ROOT/'results/t7sl_modular/config',0,0,client=Mock(),publication=CloudDestination())
        folder=self.root/'job';folder.mkdir();write(folder/'summary.json',{'ppac':{'execution_status':'NOT_RUN'}})
        publisher=Mock();publisher.publish.return_value={'status':'READY'}
        with patch.object(runtime,'cloud_publisher',return_value=publisher),patch.object(runtime,'setup_runtime',side_effect=AssertionError('No GPU setup on retry')):
            self.assertEqual(runtime.retry_publication(folder),{'status':'READY'})
        self.assertEqual(read(folder/'summary.json')['publication']['status'],'READY')

class PublicationPermissionTests(unittest.TestCase):
    def test_http_permission_code_is_a_safe_diagnostic_string(self):
        from traffic_location.integration.cloud_schema import CloudDestination
        class Forbidden(Exception):code=403
        with tempfile.TemporaryDirectory() as d:
            r=KaggleRuntime(d,ROOT/'results/t7sl_modular/config',0,0,publication=CloudDestination())
            publisher=Mock();publisher.publish.side_effect=Forbidden('software permission fixture')
            with patch.object(r,'cloud_publisher',return_value=publisher):status=r.retry_publication(d)
            self.assertEqual(status['code'],'Forbidden');self.assertEqual(status['status'],'FAILED')

if __name__=='__main__':unittest.main()
