"""Preserve the actual ingestion error rather than only CalledProcessError."""
import tempfile,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from traffic_location.integration.kaggle_runtime import KaggleRuntime
from traffic_location.integration.contracts import GateError
from traffic_location.artifacts import write

class PreparationErrorTests(unittest.TestCase):
    def test_child_root_cause_is_forwarded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);runtime=KaggleRuntime(root,root,-7.33058110387148,110.50486365193136)
            def fail(args,**kwargs):
                write(root/'area-preparation-failure.json',{'code':'PBF_NO_ROADS_IN_REQUESTED_EXTENT','message':'NO_HIGHWAY_WAYS; nodes=2; ways=1'})
                raise subprocess.CalledProcessError(1,args)
            with patch.object(runtime,'setup_runtime',return_value={'status':'READY'}),patch('subprocess.run',side_effect=fail):
                with self.assertRaises(GateError) as caught:runtime.prepare_area()
            self.assertEqual(caught.exception.code,'PBF_NO_ROADS_IN_REQUESTED_EXTENT')
            self.assertIn('NO_HIGHWAY_WAYS',str(caught.exception))
    def test_old_failure_file_cannot_mislabel_new_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);runtime=KaggleRuntime(root,root,0.,131.)
            write(root/'area-preparation-failure.json',{'code':'STALE','message':'old failure'})
            with patch.object(runtime,'setup_runtime',return_value={'status':'READY'}),patch('subprocess.run',side_effect=subprocess.CalledProcessError(2,['fixture'])):
                with self.assertRaises(subprocess.CalledProcessError):runtime.prepare_area()
            self.assertFalse((root/'area-preparation-failure.json').exists())

if __name__=='__main__':unittest.main()
