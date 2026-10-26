"""Performance contracts: full chronology, integrity, failed-stage retry and profile isolation."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from traffic_location.artifacts import write
from traffic_location.traffic.experiments.performance import batch_size,decode_batches,Progress
from traffic_location.traffic.experiments.cache import StageCache


class PerformanceTests(unittest.TestCase):
    def test_batches_keep_all_frames_including_tail(self):
        cap=Mock();cap.read.side_effect=[(True,i) for i in range(9)]
        self.assertEqual(list(decode_batches(cap,9,4)),[(0,[0,1,2,3]),(4,[4,5,6,7]),(8,[8])])
        self.assertEqual(cap.read.call_count,9)

    def test_short_video_is_not_partial_success(self):
        cap=Mock();cap.read.side_effect=[(True,0),(False,None)]
        with self.assertRaisesRegex(ValueError,'Decode failed'):
            list(decode_batches(cap,4,4))

    def test_invalid_batch_profiles_rejected(self):
        for value in (0,151,True,1.5,'4'):
            with self.assertRaises(ValueError):batch_size({'performance':{'batch_size':value}})

    def test_progress_clock_and_eta(self):
        now=[0.];clock=lambda:now[0]
        with tempfile.TemporaryDirectory() as d:
            p=Progress(Path(d)/'p.json',clock=clock)
            with p.stage('decode'):now[0]=2.
            r=p.snapshot('inference',completed=20,total=100)
            self.assertEqual(r['wall_seconds']['decode'],2)
            self.assertEqual(r['fps_actual'],10)
            self.assertEqual(r['eta_seconds'],8)

    def test_cache_reuses_but_rejects_modified_or_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            cache=StageCache(d);calls=[]
            def build(p):
                calls.append(p);write(p/'result.json',{'count':3});return {'path':str(p/'result.json')}
            first,hit=cache.get_or_create('count',{'sha':'a'},build);self.assertFalse(hit)
            second,hit=cache.get_or_create('count',{'sha':'a'},build)
            self.assertTrue(hit);self.assertEqual(first,second);self.assertEqual(len(calls),1)
            Path(first['path']).write_text('{}')
            with self.assertRaisesRegex(ValueError,'CACHE_INTEGRITY_FAILED'):
                cache.get_or_create('count',{'sha':'a'},build)

    def test_failed_attempt_is_never_reused(self):
        with tempfile.TemporaryDirectory() as d:
            cache=StageCache(d)
            def failed(p):
                write(p/'partial.json',{})
                raise RuntimeError('interrupted')
            with self.assertRaises(RuntimeError):cache.get_or_create('inference',{'batch':1},failed)
            _,hit=cache.get_or_create('inference',{'batch':1},lambda p:{'ok':True})
            self.assertFalse(hit)

    def test_batch_source_environment_changes_miss_cache(self):
        with tempfile.TemporaryDirectory() as d:
            cache=StageCache(d)
            for key in ({'batch':1,'source':'a','env':'a'},{'batch':4,'source':'a','env':'a'},
                        {'batch':4,'source':'b','env':'a'},{'batch':4,'source':'b','env':'b'}):
                _,hit=cache.get_or_create('inference',key,lambda p:{'ok':True})
                self.assertFalse(hit)

if __name__=='__main__':unittest.main()

class RuntimeReuseTests(unittest.TestCase):
    def test_repeated_video_reuses_measurement_and_counting_policy_change_only_recounts(self):
        from unittest.mock import patch
        from traffic_location.artifacts import read,sha
        from traffic_location.integration.kaggle_runtime import KaggleRuntime
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cfg=root/'config';cfg.mkdir();video=root/'video.mp4';video.write_bytes(b'video')
            model=root/'model';model.write_bytes(b'model')
            write(cfg/'fresh_request.json',{'artifacts':{k:{'path':str(model),'sha256':sha(model)} for k in ('detector','reid')}})
            write(cfg/'experiment.json',{'experiment_id':'trial'})
            write(cfg/'geometry/T7SL-WEEKDAY-PAGI.json',{'geometry':1});write(cfg/'policy.json',{'policy':1})
            runtime=KaggleRuntime(root/'system',cfg,0,0,client=Mock(),performance={'batch_size':1,'reuse':True})
            item={'id':'T7SL-WEEKDAY-PAGI','status':'READY','path':str(video),
                  'slot':{'decoded_frames':2,'width':10,'height':10,'sha256':sha(video)}}
            def infer(request,folder,**kw):write(folder/'result.json.gz',{'records':[]})
            with patch.object(runtime,'setup_runtime'),patch.object(runtime,'prepare_models',return_value={'detector':str(model),'reid':str(model)}),patch('traffic_location.traffic.orchestration.fresh_inference',side_effect=infer) as fresh,patch('traffic_location.integration.kaggle_runtime.run',return_value={'execution_status':'SUCCEEDED','jobs':[]}) as count:
                runtime.run_video(item,root/'run1');runtime.run_video(item,root/'run2')
                self.assertEqual(fresh.call_count,1);self.assertEqual(count.call_count,1)
                write(cfg/'policy.json',{'policy':2})
                runtime.run_video(item,root/'run3')
                self.assertEqual(fresh.call_count,1);self.assertEqual(count.call_count,2)

class ComparisonTests(unittest.TestCase):
    def test_numeric_difference_is_reported_without_rounding_or_ignoring_ids(self):
        from traffic_location.traffic.experiments.benchmark import first_difference
        self.assertEqual(first_difference({'bbox':[1.0]},{'bbox':[1.00001]})['path'],'$.bbox[0]')
        self.assertEqual(first_difference({'event_id':'a'},{'event_id':'b'})['path'],'$.event_id')
        self.assertIsNone(first_difference({'frames':[1,2]},{'frames':[1,2]}))

class Batch150Tests(unittest.TestCase):
    def test_150_is_one_decode_batch_and_only_tail_is_smaller(self):
        self.assertEqual(batch_size({'performance':{'batch_size':150}}),150)
        cap=Mock();cap.read.side_effect=[(True,i) for i in range(315)]
        batches=list(decode_batches(cap,315,150))
        self.assertEqual([len(images) for _,images in batches],[150,150,15])
        self.assertEqual([i for _,images in batches for i in images],list(range(315)))

    def test_failed_run_is_not_reported_as_comparable(self):
        from traffic_location.traffic.experiments.video150 import compare
        result=compare({'status':'SUCCEEDED'},{'status':'FAILED','reason':'GPU_OUT_OF_MEMORY'})
        self.assertEqual(result['status'],'NOT_COMPARABLE')
