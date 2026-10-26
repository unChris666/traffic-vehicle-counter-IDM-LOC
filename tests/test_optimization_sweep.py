"""Controlled sweep acceptance must reject changed discrete decisions, not numerical drift alone."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from traffic_location.artifacts import write
from traffic_location.traffic.experiments.optimization_sweep import summary,configurations,compare_results,sweep

class SweepTests(unittest.TestCase):
    def test_pair_runs_exactly_two_and_rejects_fast_candidate_when_results_change(self):
        for equivalent in (True,False):
            calls=[]
            def fake_job(base,config,folder,source,geometry,policy,frames,assets,**kwargs):
                calls.append(config)
                seconds=10. if config['name']=='baseline' else 5.
                return {'status':'SUCCEEDED','folder':str(folder),'processing_seconds':seconds,
                        'counting_seconds':1.,'startup_seconds':2.,'inference_process_seconds':seconds+2.}
            with tempfile.TemporaryDirectory() as d:
                root=Path(d)
                with patch('traffic_location.traffic.experiments.optimization_sweep.run_job',fake_job),\
                     patch('traffic_location.traffic.experiments.optimization_sweep.compare_results',return_value={'domain_equivalent':equivalent,'checks':{}}):
                    result=sweep({},root/'results',root,root/'geometry',root/'policy',9015,{},pair_only=True)
            self.assertEqual([c['name'] for c in calls],['baseline','candidate_fp32'])
            self.assertTrue(all(c['precision']==c['reid_precision']=='FP32' and c['backend']=='pytorch' for c in calls))
            self.assertEqual(result['best_config']['name'],'candidate_fp32' if equivalent else 'baseline')
    def test_configs_change_one_factor_from_baseline_except_explicit_precision_backend_pair(self):
        configs=configurations();base=configs[0]
        for c in configs[1:]:
            changed={k for k in set(base)|set(c) if k!='name' and c.get(k)!=base.get(k)}
            if c['name']=='trt_fp16':self.assertEqual(changed,{'backend','precision','input_shape'})
            elif c['name']=='trt_fp32':self.assertEqual(changed,{'backend','input_shape'})
            else:self.assertEqual(len(changed),1,c['name'])
    def test_single_run_reports_actual_time_without_false_variation(self):
        row={'status':'SUCCEEDED','processing_seconds':10.,'counting_seconds':2.,'startup_seconds':1.,'inference_process_seconds':11.}
        score=summary([row]);self.assertEqual(score['processing_plus_counting_seconds'],12.)
        self.assertEqual(score['total_plus_counting_seconds'],13.)
        self.assertNotIn('median',score)
        row['status']='FAILED';self.assertEqual(summary([row])['status'],'INCOMPLETE')
    def test_gate_rejects_event_change_even_if_aggregate_same(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b'
            m={'environment':{},'records':[{'frame_index':0,'emitted_measurements':[],'detections':[{'confidence':.7}]}]}
            n={'events':[{'track_id':1,'decision_frame':5,'status':'accepted','event_id':'source-a'}],
               'decisions':[],'aggregate':{'total':1}}
            for folder in (a,b):
                write(folder/'measurement/result.json.gz',m);write(folder/'count-result.json.gz',{'native':n})
            self.assertTrue(compare_results(a,b)['domain_equivalent'])
            other=copy.deepcopy(n);other['events'][0]['decision_frame']=6
            write(b/'count-result.json.gz',{'native':other})
            self.assertFalse(compare_results(a,b)['domain_equivalent'])
    def test_numeric_difference_and_source_bound_event_ids_are_reported_separately(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b'
            m={'environment':{},'records':[{'frame_index':0,'emitted_measurements':[],'detections':[{'confidence':.7}]}]}
            n={'events':[{'track_id':1,'decision_frame':5,'status':'accepted','event_id':'source-a'}],'decisions':[],'aggregate':{'total':1}}
            write(a/'measurement/result.json.gz',m);write(a/'count-result.json.gz',{'native':n})
            m['records'][0]['detections'][0]['confidence']=.700001;n['events'][0]['event_id']='source-b'
            write(b/'measurement/result.json.gz',m);write(b/'count-result.json.gz',{'native':n})
            result=compare_results(a,b)
            self.assertTrue(result['domain_equivalent']);self.assertFalse(result['exact_records_equal']);self.assertFalse(result['raw_event_ids_equal'])
    def test_one_full_video_run_per_profile_and_distinct_combination(self):
        calls=[]
        speeds={'baseline':10.,'yolo_b4':8.,'reid_cpu_input':9.,'combined':7.}
        def fake_job(base,config,folder,source,geometry,policy,frames,assets,**kwargs):
            calls.append((config['name'],frames))
            return {'status':'SUCCEEDED','config':config['name'],'folder':str(folder),
                    'processing_seconds':speeds.get(config['name'],12.),
                    'counting_seconds':1.,'startup_seconds':2.,
                    'inference_process_seconds':speeds.get(config['name'],12.)+2.}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch('traffic_location.traffic.experiments.optimization_sweep.run_job',fake_job),\
                 patch('traffic_location.traffic.experiments.optimization_sweep.compare_results',return_value={'domain_equivalent':True,'checks':{}}):
                result=sweep({},root/'results',root,root/'geometry',root/'policy',9015,{})
        self.assertEqual(result['runs_per_config'],1)
        self.assertEqual(len(calls),len(configurations())+1)
        self.assertTrue(all(frames==9015 for _,frames in calls))
        self.assertEqual(result['best_config']['name'],'combined')
        self.assertTrue(all(len(score['runs'])==1 for score in result['screen'].values()))

if __name__=='__main__':unittest.main()
