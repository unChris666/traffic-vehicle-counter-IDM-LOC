import tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
from traffic_location.artifacts import read,write
from traffic_location.integration.failure_details import details,safe

class AreaFailureTests(unittest.TestCase):
    def test_child_exception_is_visible_not_replaced_by_process_error(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'area-preparation.log';p.write_text('Traceback:\nModuleNotFoundError: No module named osmium\n')
            result=details(d,RuntimeError('child failed'))
            self.assertIn('ModuleNotFoundError',str(result['evidence']));self.assertIn('osmium',str(result['evidence']))
    def test_old_worker_logs_do_not_explain_a_new_failure(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'worker.log').write_text('RuntimeError: OLD\n')
            self.assertEqual(details(d,RuntimeError('new'),time.time()+1)['evidence'],[])
    def test_tokens_are_redacted(self):
        text=safe('Authorization: Bearer secret-token\nprivate_key: hidden\nValueError: bad geometry')
        self.assertNotIn('secret-token',text);self.assertNotIn('hidden',text);self.assertIn('bad geometry',text)
    def test_area_setup_is_fresh_child_with_persistent_output_log(self):
        import subprocess
        from types import SimpleNamespace
        from traffic_location.integration.kaggle_runtime import KaggleRuntime
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'LI_RUNTIME_MODE':'kaggle'}),patch('shutil.which',return_value='/usr/bin/nvidia-smi'):
            runtime=KaggleRuntime(d,d,0,0)
            def run(command,**kwargs):
                if command[0]=='nvidia-smi':return SimpleNamespace(returncode=0,stdout='GPU 0: FIXTURE')
                self.assertIn('-u',command);compile(command[3],'setup-child','exec')
                self.assertEqual(kwargs['stderr'],subprocess.STDOUT)
                write(command[-1],{'status':'READY','core_python':'/usr/bin/python3','osmium':'/usr/bin/osmium'})
                return SimpleNamespace(returncode=0)
            with patch('traffic_location.integration.kaggle_runtime.subprocess.run',side_effect=run):
                self.assertEqual(runtime._setup_runtime('area')['status'],'READY')
            self.assertTrue((Path(d)/'area-setup.log').exists())

    def test_renderer_error_preserves_numeric_result_and_removes_partial_html(self):
        from traffic_location.location.area.outputs.map import render_safely
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'presentation';target.mkdir();(target/'views').mkdir();(target/'views/map.html').write_text('partial')
            write(target/'display-tables.json',{'area':[{'jumlah_bangunan':22}]})
            native={'output_path':str(target),'summary':{'candidate_whole_buildings':22}}
            with patch('traffic_location.location.area.outputs.map.render_esri',side_effect=RuntimeError('RENDER_FIXTURE')):
                status=render_safely({}, {},Path(d),{},native)
            self.assertEqual(status['status'],'FAILED');self.assertEqual(native['summary']['candidate_whole_buildings'],22)
            self.assertTrue((target/'display-tables.json').exists());self.assertFalse((target/'views/map.html').exists())
            self.assertEqual(read(target/'error.json')['code'],'RuntimeError')

if __name__=='__main__':unittest.main()
