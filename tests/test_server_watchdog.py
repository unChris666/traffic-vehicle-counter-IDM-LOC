"""Fresh server observations and evidence for a freeze before notebook interruption."""
import contextlib,io,json,os,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import Mock,patch
from traffic_location.artifacts import write,read
from traffic_location.integration import server_watchdog as w

class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        write(self.base/'server-status.json',{'status':'RUNNING_LOCAL_HTTP_OK','pid':123,'local_url':'http://127.0.0.1:7860','public_url':'https://fixture.gradio.live'})
    def test_dead_server_cannot_inherit_historical_http_ready(self):
        with patch('traffic_location.integration.job_status.observation',return_value={'process_alive':False}),patch.object(w,'probe') as probe:
            status=w.observation(self.base,public=True)
        probe.assert_not_called();self.assertEqual(status['status'],'STOPPED')
        self.assertEqual(status['previous_monitor_sample']['status'],'RUNNING_LOCAL_HTTP_OK')
    def test_closing_process_is_not_a_healthy_server_even_when_threads_linger(self):
        w.lifecycle(self.base,'STOPPING')
        with patch('traffic_location.integration.job_status.observation',return_value={'process_alive':True}),patch.object(w,'probe',return_value={'status':'READY'}):
            self.assertEqual(w.observation(self.base)['status'],'STOPPING')
    def test_local_ready_and_public_failure_are_distinct(self):
        with patch('traffic_location.integration.job_status.observation',return_value={'process_alive':True}),patch.object(w,'probe',side_effect=[{'status':'READY'},{'status':'UNREACHABLE'}]):
            status=w.observation(self.base,public=True)
        self.assertEqual(status['status'],'RUNNING_LOCAL_HTTP_OK');self.assertEqual(status['public_tunnel']['status'],'UNREACHABLE')
        self.assertIn('event streaming',status['scope'])
    def test_http_stall_captures_threads_once_per_stall_and_recovers(self):
        watcher=w.Watchdog(self.base,7860)
        with patch.object(w,'probe',return_value={'status':'UNREACHABLE'}),patch('faulthandler.dump_traceback') as dump,contextlib.redirect_stdout(io.StringIO()):
            watcher.tick();self.assertFalse(dump.called)
            watcher.tick();watcher.tick();dump.assert_called_once()
        self.assertEqual(read(self.base/'server-watchdog.json')['consecutive_failures'],3)
        with patch.object(w,'probe',return_value={'status':'READY'}):watcher.tick()
        self.assertFalse(watcher.dumped);self.assertEqual(watcher.failures,0)
    def test_export_is_bounded_redacted_and_has_fresh_probe(self):
        (self.base/'server.log').write_text('x'*70000+'\nAuthorization: Bearer fixture-secret\n')
        (self.base/'server-stacks.log').write_text('Thread fixture\n')
        archive=self.base/'diagnostics.zip'
        with zipfile.ZipFile(archive,'w'):pass
        with patch('traffic_location.integration.job_status.observation',return_value={'process_alive':False}):w.append_diagnostics(self.base,archive)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(json.loads(z.read('server-observation.json'))['status'],'STOPPED')
            self.assertNotIn(b'fixture-secret',z.read('server.log'));self.assertLess(len(z.read('server.log')),65537)
            self.assertIn('server-stacks.log',z.namelist())
    def test_probe_rejects_external_or_redirect_targets_without_network(self):
        with patch('urllib.request.build_opener') as opener:
            for url in ('http://example.invalid/config','http://127.0.0.1:7860/config?token=secret','https://example.invalid/config'):
                self.assertEqual(w.probe(url)['status'],'NOT_CHECKED')
                self.assertEqual(w.probe(url,public=True)['status'],'NOT_CHECKED')
        opener.assert_not_called()

class TrafficDiagnosticTests(unittest.TestCase):
    def test_shared_preparation_failure_is_checkpointed_and_receipts_exported_without_area(self):
        from traffic_location.integration.kaggle_runtime import KaggleRuntime
        from traffic_location.integration.area_trace import latest_report,export_report
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);root=base/'runs/test';root.mkdir(parents=True)
            runtime=KaggleRuntime(base,base/'config',-6.,106.,target_id='TEST',period_id='TEST')
            tasks=[{'id':'v1','kind':'traffic'}]
            with patch.object(runtime,'connect'),patch.object(runtime,'setup_runtime',side_effect=RuntimeError('CUDA fixture unavailable')),contextlib.redirect_stdout(io.StringIO()):
                results=list(runtime._scheduled_tasks(tasks,root))
            self.assertIsNotNone(results[0][2]);status=read(root/'traffic-preparation/job-status.json')
            self.assertEqual(status['stage'],'traffic_runtime_validation');self.assertEqual(status['status'],'FAILED')
            write(root/'job-input.json',{'schema_version':'job_input_v1','job_id':'job_fixture'})
            write(root/'progress.json',[{'id':'v1','engine':'traffic','execution_status':'FAILED','message':'Authorization: Bearer fixture-secret','diagnostics':[{'code':'CUDA_ERROR'}]}])
            report=latest_report(base);self.assertIsNone(report['trace'])
            self.assertEqual(report['traffic_preparation_status']['category'],'RUNTIME_ERROR')
            self.assertEqual(report['current_engine_receipts'][0]['diagnostics'][0]['code'],'CUDA_ERROR')
            self.assertEqual(report['diagnostics']['category'],'DIAGNOSTIC_COLLECTION_ONLY')
            archive=export_report(base,base/'out.zip')
            with zipfile.ZipFile(archive) as z:self.assertNotIn(b'fixture-secret',z.read('area-diagnostic-report.json'))


class LiveReceiptTests(unittest.TestCase):
    def test_completed_area_is_visible_during_traffic_without_mixing_previous_job(self):
        from traffic_location.integration.gradio_app import Controller
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'config/experiment.json',{'videos':[]})
            c=Controller(root/'ui',root/'config');run=root/'run'
            write(run/'job-input.json',{'job_id':'job_current'})
            write(run/'progress.json',[{'id':'area','execution_status':'SUCCEEDED','summary':{'buildings':5}}])
            runtime=Mock(_active_run_root=run)
            self.assertEqual(c.live_engine_rows(runtime,{'job_id':'job_current'})[0][1],'SUCCEEDED')
            self.assertEqual(c.live_engine_rows(runtime,{'job_id':'job_previous'}),[])

if __name__=='__main__':unittest.main()
