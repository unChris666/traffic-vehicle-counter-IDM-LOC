"""Colab adapter/gates are tested without Google credentials or GPU execution."""
import ast,base64,hashlib,io,json,os,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import Mock,patch
from traffic_location import __version__
from traffic_location.integration.colab_runtime import ColabRuntime,require_l4
from traffic_location.integration.kaggle_runtime import KaggleRuntime
from traffic_location.artifacts import write
ROOT=Path(__file__).resolve().parents[1]

class ColabGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'LI_RUNTIME_MODE':'bundled','LI_AUTH_MODE':'adc','LI_COLAB_GATE_ROOT':str(self.base/'gate')})
        self.env.start();self.addCleanup(self.env.stop)
        self.runtime=ColabRuntime(self.base/'runtime',self.base/'config',-.899,131.322,target_id='T7SL',period_id='2026-10-27')
    def result(self):
        job='job_'+'1'*32
        return {'job_id':job,'job_context':{'target_id':'T7SL','period_id':'2026-10-27','latitude':-.899,'longitude':131.322,'package_version':__version__},
                'manifest_job_id':job,'map_html':'<iframe>checksum-bound fixture</iframe>',
                'area_results':[{'job_id':job,'target_id':'T7SL','execution_status':'SUCCEEDED','result_version':'v'}],
                'area_trace':{'runtime_platform':'colab','execution_status':'SUCCEEDED','package_version':__version__,'gpu':[{'name':'NVIDIA L4'}],
                              'context':{'target_id':'T7SL','period_id':'2026-10-27','latitude':-.899,'longitude':131.322},'result':{'result_version':'v'}},
                'display':{'schema_version':'area_display_v1','area':[],'competitors':[],'indomaret':[]}}
    def test_allocated_gpu_must_be_l4_not_just_cuda_available(self):
        self.assertEqual(require_l4([{'name':'NVIDIA L4'}])[0]['name'],'NVIDIA L4')
        for rows in ([],[{'name':'Tesla T4'}],[{'name':'NVIDIA L4'},{'name':'A100'}]):
            with self.assertRaises(ValueError):require_l4(rows)
    def test_traffic_is_blocked_before_any_worker_or_cloud_call(self):
        with patch.object(KaggleRuntime,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'Area Coverage dahulu'):self.runtime.execute('traffic',{})
        execute.assert_not_called()
    def test_area_is_allowed_first_and_only_verified_reopen_unlocks_traffic(self):
        with patch.object(KaggleRuntime,'execute',return_value='fixture') as execute:
            self.assertEqual(self.runtime.execute('area',{}),'fixture')
            self.assertIn('diverifikasi',self.runtime.note_reopened_area(self.result()))
            self.assertEqual(self.runtime.execute('traffic',{}),'fixture')
            self.assertEqual(execute.call_count,2)
    def test_missing_map_failed_area_wrong_manifest_or_version_cannot_unlock(self):
        for mutate in (lambda r:r.update(map_html=''),lambda r:r['area_results'][0].update(execution_status='FAILED'),
                       lambda r:r.update(manifest_job_id='other'),lambda r:r['job_context'].update(package_version='old'),lambda r:r['area_trace'].update(runtime_platform='kaggle'),
                       lambda r:r['area_trace']['result'].update(result_version='other')):
            result=self.result();mutate(result);self.runtime.note_reopened_area(result)
            with self.assertRaises(ValueError):self.runtime.execute('workflow',{})
    def test_target_period_coordinate_changes_require_new_area_reopen(self):
        self.runtime.note_reopened_area(self.result())
        for kwargs in ({'target_id':'ABCD'},{'period_id':'other'},{'latitude':-.898},{'longitude':131.323}):
            settings={'target_id':'T7SL','period_id':'2026-10-27','latitude':-.899,'longitude':131.322,**kwargs}
            runtime=ColabRuntime(self.base/'next',self.base/'config',**settings)
            with self.assertRaises(ValueError):runtime.execute('traffic',{})
    def test_coordinate_identity_normalizes_integer_and_float_zero(self):
        from traffic_location.integration.colab_runtime import gate_identity
        a={'target_id':'ABCD','period_id':'test','latitude':0,'longitude':131}
        b={**a,'latitude':0.,'longitude':131.}
        self.assertEqual(gate_identity(a),gate_identity(b))

    def test_job_runtime_verifies_without_installing(self):
        with patch('traffic_location.integration.container_runtime.verify_runtime',return_value={'status':'READY'}),patch('subprocess.run') as install:
            self.runtime.setup_runtime('area');self.runtime.setup_runtime('traffic')
        install.assert_not_called()
    def test_colab_local_reference_rejects_adc_files_and_kaggle_paths(self):
        from traffic_location.integration.upload_transport import resolve_reference
        with patch.dict(os.environ,{'LI_RUNTIME_PLATFORM':'colab'}):
            for value in ('/content/.config/application_default_credentials.json','/kaggle/input/video.mp4','/etc/passwd'):
                with self.assertRaisesRegex(ValueError,'/content/videos'):resolve_reference(value,self.base/'staging',Mock())

class ColabNotebookTests(unittest.TestCase):
    def test_self_contained_payload_matches_source_wheel_locks_and_bootstrap(self):
        path=ROOT/'notebooks/active/15_colab_l4_area_first.ipynb';n=json.loads(path.read_text())
        sources=[]
        for c in n['cells']:
            if c['cell_type']=='code':
                source=c['source'];compile(source,'colab-cell','exec');sources.append(source)
                self.assertEqual(c['outputs'],[]);self.assertIsNone(c['execution_count'])
        bootstrap=next(s for s in sources if 'PAYLOAD=' in s)
        node=next(n for n in ast.walk(ast.parse(bootstrap)) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in n.targets))
        data=base64.b64decode(ast.literal_eval(node.value.args[0]));self.assertIn(hashlib.sha256(data).hexdigest(),bootstrap)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for source,target in [('tools/colab_bootstrap.py','bootstrap.py'),('deploy/requirements.lock','locks/requirements.lock'),('deploy/colab/core-linux-64.lock','locks/core-linux-64.lock'),('deploy/colab/science-linux-64.lock','locks/science-linux-64.lock')]:self.assertEqual(z.read(target),(ROOT/source).read_bytes())
            wheel=zipfile.ZipFile(io.BytesIO(z.read('package/traffic_location_engines-'+__version__+'-py3-none-any.whl')))
            for name in wheel.namelist():
                if name.startswith('traffic_location/') and name.endswith('.py'):self.assertEqual(wheel.read(name),(ROOT/'src'/name).read_bytes(),name)
        code='\n'.join(sources)
        self.assertIn('auth.authenticate_user',code);self.assertIn("'LI_RUNTIME_MODE':'bundled'",code)
        self.assertNotIn('.execute(',code);self.assertNotIn('kaggle_secrets',code)
        self.assertIn('default_mode', (ROOT/'src/traffic_location/integration/colab_runtime.py').read_text())
    def test_conda_locks_pin_urls_and_sha256_not_floating_versions(self):
        for name in ('core','science'):
            text=(ROOT/'deploy/colab'/(name+'-linux-64.lock')).read_text();self.assertIn('@EXPLICIT',text)
            rows=[r for r in text.splitlines() if r.startswith('https://')]
            self.assertGreater(len(rows),20)
            for row in rows:self.assertRegex(row,r'^https://conda\.anaconda\.org/conda-forge/(linux-64|noarch)/.+#[a-f0-9]{64}$')



class ColabPreflightTests(unittest.TestCase):
    def test_readiness_checks_permissions_without_writing_objects_or_running_engines(self):
        from types import SimpleNamespace
        from traffic_location.integration.colab_runtime import preflight
        from traffic_location.integration.cloud_schema import CloudDestination
        runtime=Mock();runtime.publication=CloudDestination();publisher=runtime.cloud_publisher.return_value
        publisher.location='US';publisher.check.return_value={'status':'READY'}
        publisher.storage.bucket.return_value.test_iam_permissions.return_value=['storage.objects.get','storage.objects.create']
        publisher.bq.test_iam_permissions.return_value={'permissions':['bigquery.tables.getData','bigquery.tables.updateData']}
        publisher.bq.get_table.return_value=SimpleNamespace(schema=[SimpleNamespace(name=n,field_type=t) for n,t in [('LAT','FLOAT'),('LONG','FLOAT'),('KDTK','STRING'),('NAMA_TOKO','STRING')]])
        runtime.probe.return_value={'gcs':{'objects':{'national_pbf':{'status':'READY'},'detector':{'status':'NOT_FOUND'}}}}
        with tempfile.TemporaryDirectory() as d,patch('traffic_location.integration.colab_runtime.observe_gpu',return_value=[{'name':'NVIDIA L4'}]),patch('traffic_location.integration.colab_runtime.ColabRuntime',return_value=runtime):
            result=preflight(d,d)
        self.assertEqual(result['objects']['national_pbf']['status'],'READY')
        runtime.execute.assert_not_called();publisher.publish.assert_not_called()
        self.assertEqual(publisher.bq.test_iam_permissions.call_count,5)
        self.assertEqual(publisher.bq.query.call_args.args[0],'SELECT 1 AS access_probe')
        publisher.storage.bucket.return_value.blob.assert_not_called()
    def test_core_wrapper_sets_only_core_data_paths_and_is_valid_shell(self):
        import shlex,subprocess
        path=ROOT/'tools/colab_bootstrap.py';tree=ast.parse(path.read_text())
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='write_text' and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='core')
        with tempfile.TemporaryDirectory() as d:
            core=Path(d)/'core-python';exec(compile(ast.Module(body=[node],type_ignores=[]),'wrapper','exec'),{'base':Path(d),'core':core,'shlex':shlex})
            self.assertTrue(core.read_bytes().startswith(b'#!/bin/sh\nunset PROJ_LIB\n'))
            self.assertIn('runtime/core/share/proj',core.read_text())
            subprocess.run(['/bin/sh','-n',str(core)],check=True)

if __name__=='__main__':unittest.main()
