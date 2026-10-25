"""Extraction/isolation regressions. Actual private baseline parity is a separate tool."""
import ast,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from traffic_location.artifacts import sha,read,write
from traffic_location.location.area.application.pipeline import execute
from traffic_location.location.area._kernel.location_intelligent_market import huff,reconcile
ROOT=Path(__file__).resolve().parents[1]

class AreaMigrationTests(unittest.TestCase):
    def test_all_extracted_sources_and_modules_pinned_and_notebook_imports_absent(self):
        rows=read(ROOT/'results/area_modularization/source_extraction.json')
        self.assertEqual(len(rows),35)
        for row in rows:
            self.assertEqual(sha(ROOT/row['source']),row['source_sha256'])
            self.assertEqual(sha(ROOT/row['module']),row['module_sha256'])
            tree=ast.parse((ROOT/row['module']).read_text())
            for n in ast.walk(tree):
                if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.endswith('.py'):
                    self.assertFalse(n.value.startswith('traffic_location.location.area._kernel.'),'Filename was rewritten as module path')
                if isinstance(n,ast.ImportFrom):self.assertFalse((n.module or '').startswith('location_intelligent_'))
                if isinstance(n,ast.Import):self.assertFalse(any(a.name.startswith('location_intelligent_') for a in n.names))
    def test_huff_tie_and_zero_rules_are_deterministic(self):
        options=[{'store_key':'b','total_distance_m':100},{'store_key':'a','total_distance_m':100}]
        self.assertEqual(huff(options)[0]['store_key'],'a')
        self.assertEqual(huff([{'store_key':'a','total_distance_m':0},{'store_key':'b','total_distance_m':100}])[0]['huff_score'],1)
    def request(self,p):
        return {'schema_version':'area_execution_request_v1','operation':'replay_recorded',
                'baseline':{'path':str(p),'sha256':sha(p)},'core_python':'/usr/bin/python3','render':False,'timeout_seconds':5}
    def test_failed_worker_cannot_publish_and_releases_lock(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'source.zip';p.write_bytes(b'fixture')
            worker=SimpleNamespace(returncode=1,wait=lambda **kw:1)
            with patch('traffic_location.location.area.application.pipeline.subprocess.Popen',return_value=worker):
                with self.assertRaisesRegex(RuntimeError,'AREA_WORKER_FAILED'):execute(self.request(p),root/'out')
            self.assertFalse((root/'out').exists());self.assertFalse((root/'.out.lock').exists())
            failure=next(root.glob('.area-job-*/checkpoint.json'))
            self.assertEqual(read(failure)['status'],'FAILED')
    def test_concurrent_same_output_is_rejected_before_starting_worker(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'source.zip';p.write_bytes(b'fixture');(root/'.out.lock').write_text('running')
            with patch('traffic_location.location.area.application.pipeline.subprocess.Popen') as launch:
                with self.assertRaisesRegex(RuntimeError,'ALREADY_RUNNING'):execute(self.request(p),root/'out')
                launch.assert_not_called()
    def test_timeout_kills_worker_group_without_publishing_or_leaking_lock(self):
        import subprocess
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'source.zip';p.write_bytes(b'fixture')
            worker=SimpleNamespace(pid=1234,returncode=0)
            from unittest.mock import Mock
            worker.wait=Mock(side_effect=[subprocess.TimeoutExpired('fixture',5),0])
            with patch('traffic_location.location.area.application.pipeline.subprocess.Popen',return_value=worker),patch(
                'traffic_location.location.area.application.pipeline.time.monotonic',side_effect=[0,0,10]),patch(
                'traffic_location.location.area.application.pipeline.os.killpg') as kill:
                with self.assertRaises(subprocess.TimeoutExpired):execute(self.request(p),root/'out')
                kill.assert_called_once()
            self.assertFalse((root/'out').exists());self.assertFalse((root/'.out.lock').exists())

    def test_public_facade_forwards_without_changing_request(self):
        from traffic_location.location.area import execute as public_execute
        q={'fixture':'request'}
        with patch('traffic_location.location.area.application.pipeline.execute',return_value={'fixture':'result'}) as run:
            self.assertEqual(public_execute(q,'/fixture'),{'fixture':'result'})
            run.assert_called_once_with(q,'/fixture')

    def test_export_is_verified_repeatable_and_outside_immutable_root(self):
        from traffic_location.persistence import publish
        from traffic_location.location.area.outputs.export import archive_result
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);packet=root/'packet'
            publish(packet,{'result.json':{'result_version':'fixture'}})
            first=archive_result(packet,root/'a.zip');second=archive_result(packet,root/'b.zip')
            self.assertEqual(sha(first),sha(second))
            self.assertEqual(archive_result(packet,first),first)
            with self.assertRaises(ValueError):archive_result(packet,packet/'bad.zip')

    def test_storage_adapter_requires_explicit_bucket_and_keeps_result_version(self):
        from traffic_location.persistence import publish
        from traffic_location.location.area.outputs.storage import publish_gcs
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);publish(root/'packet',{'result.json':{'result_version':'fixture'}})
            bucket=object()
            with patch('traffic_location.location.area.outputs.storage.upload_result',return_value={'status':'STORED'}) as upload:
                result=publish_gcs(root/'packet',root/'packet.zip',bucket=bucket)
                self.assertEqual(result['engine_result_version'],'fixture')
                self.assertIs(upload.call_args.kwargs['bucket'],bucket)

    def test_partial_and_unknowns_not_implicitly_counted(self):
        rows=[{'building_id':'x','winner_store_key':None,'count_candidate':0,'scores':[],
               'market_status':'UNVERIFIED','reason':'UNKNOWN'}]
        self.assertEqual(reconcile(rows)['candidate_whole_buildings'],0)
        self.assertEqual(reconcile(rows)['unassigned'],1)

if __name__=='__main__':unittest.main()
