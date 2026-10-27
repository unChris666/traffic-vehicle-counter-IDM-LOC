"""Resource observations must be optional and must not initialize CUDA."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from subprocess import TimeoutExpired,CompletedProcess
from traffic_location.runtime_resources import snapshot,record

class ResourcesTests(unittest.TestCase):
    def test_nvidia_memory_is_separate_from_torch_and_has_no_capacity_claim(self):
        with tempfile.TemporaryDirectory() as d,patch('traffic_location.runtime_resources.subprocess.run',return_value=CompletedProcess([],0,'1, GPU-fixture, 512, 15360, 17\n','')):
            r=snapshot(d)
        self.assertEqual(r['gpus'][0]['memory_used_mib'],512)
        self.assertEqual(r['gpu_status'],'OBSERVED')
        self.assertGreater(r['process_peak_rss_bytes'],0)
        self.assertIn('NOT_A_CAPACITY_BENCHMARK',r['sampling_scope'])
    def test_missing_gpu_command_and_timeout_do_not_fail_the_job(self):
        for error in [FileNotFoundError(),TimeoutExpired('nvidia-smi',3)]:
            with tempfile.TemporaryDirectory() as d,patch('traffic_location.runtime_resources.subprocess.run',side_effect=error):
                record(d,'finished');r=json.loads((Path(d)/'resources-finished.json').read_text())
                self.assertEqual(r['gpu_status'],'UNAVAILABLE')
    def test_diagnostic_storage_failure_is_not_an_engine_failure(self):
        with patch('traffic_location.artifacts.write',side_effect=OSError('disk fixture')):
            record('/tmp','finished')

if __name__=='__main__':unittest.main()
