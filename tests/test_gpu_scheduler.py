"""Resource isolation, queueing and the promoted candidate execution contract."""
import os,time,threading,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from traffic_location.traffic.gpu_scheduler import run_video_jobs,visible_gpu_ids
from traffic_location.traffic.execution_profile import resolve_profile

class SchedulerTests(unittest.TestCase):
    def test_integration_prepares_models_once_and_retains_independent_failures(self):
        from traffic_location.integration.kaggle_runtime import KaggleRuntime
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);runtime=KaggleRuntime(root/'system',root/'config',0,0)
            tasks=[{'id':'area','kind':'area'},{'id':'bad','kind':'traffic'},{'id':'good','kind':'traffic'}]
            def video(item,path,**kw):
                self.assertIn(kw['gpu_id'],['0','1']);self.assertEqual(kw['models'],{'ready':True})
                if item['id']=='bad':raise ValueError('bad source')
                return {'ok':True}
            with patch.object(runtime,'run_area',side_effect=ValueError('area unavailable')),\
                 patch.object(runtime,'connect'),patch.object(runtime,'setup_runtime'),\
                 patch.object(runtime,'prepare_models',return_value={'ready':True}) as models,\
                 patch.object(runtime,'run_video',side_effect=video),\
                 patch('traffic_location.traffic.gpu_scheduler.visible_gpu_ids',return_value=['0','1']):
                outcomes=list(runtime._scheduled_tasks(tasks,root/'runs'))
            models.assert_called_once()
            self.assertIsNotNone(outcomes[0][2]);self.assertIsNotNone(outcomes[1][2])
            self.assertEqual(outcomes[2][1],{'ok':True});self.assertIsNone(outcomes[2][2])
    def test_one_or_two_gpus_never_share_an_active_video(self):
        for ids in (['0'],['0','1']):
            active=set();maximum=0;guard=threading.Lock();barrier=threading.Barrier(len(ids))
            def work(job,gpu):
                nonlocal maximum
                with guard:
                    self.assertNotIn(gpu,active);active.add(gpu);maximum=max(maximum,len(active))
                if job<len(ids):barrier.wait(timeout=3)
                time.sleep(.01)
                with guard:active.remove(gpu)
                if job==2:raise ValueError('video failed')
                return job
            rows=run_video_jobs(range(5),work,gpu_ids=ids)
            self.assertEqual(maximum,len(ids));self.assertEqual(len(rows),5)
            self.assertEqual(rows[2]['execution_status'],'FAILED')
            self.assertEqual(rows[4]['result'],4)
    def test_detection_respects_existing_visibility_mask(self):
        with patch.dict(os.environ,{'CUDA_VISIBLE_DEVICES':'GPU-a,GPU-b'}),patch('subprocess.check_output',return_value='2'):
            self.assertEqual(visible_gpu_ids(),['GPU-a','GPU-b'])
    def test_missing_or_duplicate_devices_rejected(self):
        for ids in ([],['0','0']):
            with self.assertRaises(ValueError):run_video_jobs([1],lambda j,g:j,gpu_ids=ids)
    def test_candidate_is_default_on_cuda_and_cpu_keeps_baseline(self):
        p=resolve_profile({'device':'cuda:0','half':False})
        self.assertEqual((p['batch_size'],p['reid_window'],p['crop_batch']),(4,8,32))
        self.assertEqual(p['reid_transport'],'io_binding');self.assertEqual(p['precision'],'FP32')
        self.assertIsNone(resolve_profile({'device':'cpu','half':False}))
        self.assertIsNone(resolve_profile({'device':'cuda:0','execution_profile':'baseline_fp32'}))
    def test_worker_routes_to_shared_candidate_without_mutating_request(self):
        from traffic_location.traffic.inference_worker import execute
        r={'device':'cuda:0','half':False}
        with patch('traffic_location.traffic.model_worker.execute',return_value={'ok':True}) as worker:
            self.assertEqual(execute(r,'output'),{'ok':True})
        self.assertNotIn('experiment',r);self.assertEqual(worker.call_args.kwargs['profile']['name'],'candidate_fp32')
    def test_subprocess_visibility_does_not_mutate_parent(self):
        from traffic_location.traffic.adapters.detector import execute_worker
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'CUDA_VISIBLE_DEVICES':'0,1'}):
            with patch('subprocess.Popen') as popen:
                popen.return_value.__enter__.return_value.wait.return_value=0
                execute_worker('request',Path(d)/'worker',python_executable='python',log_path=Path(d)/'log',timeout_seconds=1,gpu_id='1')
                self.assertEqual(popen.call_args.kwargs['env']['CUDA_VISIBLE_DEVICES'],'1')
            self.assertEqual(os.environ['CUDA_VISIBLE_DEVICES'],'0,1')

if __name__=='__main__':unittest.main()
