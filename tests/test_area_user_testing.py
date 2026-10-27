"""Regression of failure visibility and independent Area artifact recovery."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from traffic_location.artifacts import write,read
from traffic_location.integration.cloud_results import ResultsReader
from traffic_location.integration.cloud_schema import CloudDestination
from traffic_location.integration.kaggle_runtime import KaggleRuntime
from traffic_location.integration.failure_details import details

class AreaUserTestingTests(unittest.TestCase):
    def test_ppac_download_failure_does_not_hide_valid_map_or_area_failure(self):
        d=CloudDestination();reader=ResultsReader(d,Mock(),Mock())
        reader.bq.get_dataset.return_value.location='asia-southeast1'
        job={'job_id':'job_'+'1'*32,'target_id':'T7SL','period_id':'2026-10-27','manifest_uri':'manifest','manifest_sha256':'a'*64}
        entries=[{'object':name,'sha256':'a'*64} for name in ['x/ppac/result.json','x/summary.json','x/engines/area/area/presentation/views/esri/market_map.html']]
        def verified(j,uri,*args):
            if uri=='manifest':return json.dumps({'files':entries}).encode()
            if uri.endswith('/ppac/result.json'):raise ValueError('PPAC_CHECKSUM_FIXTURE')
            return json.dumps({'engines':[{'engine':'area','execution_status':'SUCCEEDED'}]}).encode()
        with patch.object(reader,'query',side_effect=[[job],[],[],[]]),patch.object(reader,'verified_bytes',side_effect=verified),patch.object(reader,'map_html',return_value='<iframe>verified</iframe>'):
            result=reader.load('T7SL')
        self.assertIn('verified',result['map_html'])
        self.assertTrue(any('PPAC' in s for s in result['artifact_status']))

    def test_bq_failure_reports_table_stage_and_http_without_raw_rows(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=KaggleRuntime(d,d,-.89949,131.32216)
            layers={'competitor':{'status':'FAILED','table':'locdeproject.DWH_NS_LOC.COMPETITOR','error_stage':'BIGQUERY_METADATA_OR_QUERY','error_type':'Forbidden','error_diagnostics':{'chain':[{'type':'Forbidden','http_status':403}]},'rows':[{'secret':'must-not-copy'}]}}
            with patch.object(runtime,'setup_runtime',return_value={'core_python':'/usr/bin/python3'}),patch.object(runtime,'connect'),patch('traffic_location.location.area._kernel.location_intelligent_map_pilot.load_bq_layers',return_value=layers):
                with self.assertRaisesRegex(ValueError,'Forbidden'):
                    runtime._prepare_area()
            report=details(d,ValueError('child failed'))
            self.assertIn('BIGQUERY_METADATA_OR_QUERY',str(report));self.assertIn('403',str(report))
            self.assertNotIn('must-not-copy',str(report))

    def test_bq_failed_cache_is_diagnosed_instead_of_generic_cache_error(self):
        # Diagnostics must be read even when no matching error line reached stdout.
        with tempfile.TemporaryDirectory() as d:
            write(Path(d)/'bq-readiness.json',{'competitor':{'status':'FAILED','error_type':'BadRequest','error_stage':'BIGQUERY_METADATA_OR_QUERY','rows':None}})
            self.assertIn('BadRequest',str(details(d,ValueError('preparation failed'))))


class TraceTests(unittest.TestCase):
    def test_failed_source_access_writes_run_trace_without_starting_worker(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=KaggleRuntime(d,d,0,131)
            with patch.object(runtime,'object_status',return_value={'status':'ACCESS_DENIED','code':'Forbidden'}),patch.object(runtime,'prepare_area') as prepare:
                with self.assertRaisesRegex(ValueError,'Forbidden'):runtime.run_area(Path(d)/'runs/test/area')
                prepare.assert_not_called()
            trace=read(Path(d)/'runs/test/area/area-trace.json')
            self.assertEqual(trace['execution_status'],'FAILED');self.assertEqual(trace['stage'],'source_access')
            self.assertIn('Forbidden',str(trace['failure']))

    def test_diagnostic_export_does_not_copy_raw_sources_or_keys(self):
        import zipfile
        from traffic_location.integration.area_trace import export_report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'credentials.json',{'private_key':'must-not-copy'})
            (root/'area-preparation.log').write_text('Forbidden: Authorization: Bearer fixture-secret\n')
            output=export_report(root,root/'diagnostics.zip')
            with zipfile.ZipFile(output) as z:
                self.assertEqual(z.namelist(),['area-diagnostic-report.json'])
                payload=z.read(z.namelist()[0]).decode()
                self.assertNotIn('fixture-secret',payload);self.assertNotIn('must-not-copy',payload)

    def test_diagnostic_does_not_require_name_or_video_to_find_error(self):
        from traffic_location.integration.gradio_app import Controller
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'config/experiment.json',{'videos':[]})
            controller=Controller(root/'ui',root/'config')
            vals=['Area Coverage','T7SL',-.89949,131.32216,'2026-10-27']
            runtime=controller.diagnostic_runtime(vals)
            (runtime.base/'area-preparation.log').write_text('ModuleNotFoundError: fixture\n')
            self.assertIn('ModuleNotFoundError',controller.area_diagnostic(*vals))

class ActiveNotebookTests(unittest.TestCase):
    def test_active_notebook_is_exact_candidate_area_first_and_has_no_auto_engine_run(self):
        import ast,base64,io,zipfile
        from traffic_location import __version__
        root=Path(__file__).resolve().parents[1]
        notebook=json.loads((root/'notebooks/active/14_gate2_area_user_testing.ipynb').read_text())
        code=[]
        for cell in notebook['cells']:
            if cell['cell_type']=='code':
                source=cell['source'] if isinstance(cell['source'],str) else ''.join(cell['source'])
                compile(source,'active-notebook','exec');code.append(source)
                self.assertEqual(cell['outputs'],[]);self.assertIsNone(cell['execution_count'])
        bootstrap=next(c for c in code if 'PAYLOAD=' in c)
        node=next(n for n in ast.walk(ast.parse(bootstrap)) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in n.targets))
        bundle=zipfile.ZipFile(io.BytesIO(base64.b64decode(ast.literal_eval(node.value.args[0]))))
        wheel=zipfile.ZipFile(io.BytesIO(bundle.read('package/traffic_location_engines-'+__version__+'-py3-none-any.whl')))
        for name in wheel.namelist():
            if name.startswith('traffic_location/') and name.endswith('.py'):self.assertEqual(wheel.read(name),(root/'src'/name).read_bytes())
        self.assertIn('default_mode="Area Coverage"','\n'.join(code))
        self.assertNotIn('.execute(','\n'.join(code));self.assertIn('export_report','\n'.join(code))

class TraceSuccessTests(unittest.TestCase):
    def test_success_records_same_engine_version_and_separate_presentation_failure(self):
        from traffic_location.integration.area_trace import AreaTrace,latest_report
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);folder=base/'engine';write(folder/'result.json',{'result_version':'v','presentation_status':'FAILED','presentation_ref':None})
            trace=AreaTrace(base,base/'runs/test/area',{'target_id':'T7SL'})
            trace.finish(result={'jobs':[{'quality':'PARTIAL','result_ref':{'path':str(folder),'sha256':'a'*64}}]})
            report=latest_report(base)
            self.assertEqual(report['trace']['execution_status'],'SUCCEEDED')
            self.assertEqual(report['trace']['result']['presentation_status'],'FAILED')
            self.assertEqual(report['trace']['result']['result_version'],'v')

class PublicationTraceTests(unittest.TestCase):
    def test_local_diagnostic_reports_publication_failure_for_same_run(self):
        from traffic_location.integration.area_trace import AreaTrace,latest_report
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);trace=AreaTrace(base,base/'runs/test/area',{'target_id':'T7SL'})
            trace.finish(error=RuntimeError('fixture'))
            write(base/'runs/test/publication-status.json',{'status':'FAILED','code':'Forbidden','diagnostics':{'message':'fixture BQ permission'},'private_key':'must-not-copy'})
            report=latest_report(base)
            self.assertEqual(report['publication']['code'],'Forbidden')
            self.assertNotIn('must-not-copy',str(report))

class AreaFirstUITests(unittest.TestCase):
    def test_area_first_mode_and_diagnostic_export_construct_without_engine(self):
        from traffic_location.integration.gradio_app import build_app
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'config/experiment.json',{'videos':[]})
            app,_=build_app(root/'ui',root/'config',default_mode='Area Coverage',runtime_factory=Mock())
            try:
                props=[c['props'] for c in app.get_config_file()['components']]
                self.assertTrue(any(p.get('label')=='Proses' and p.get('value')=='Area Coverage' for p in props))
                self.assertTrue(any(p.get('label')=='Paket diagnosis Area (ZIP)' for p in props))
            finally:app.close()

if __name__=='__main__':unittest.main()
