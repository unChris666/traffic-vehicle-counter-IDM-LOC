import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from traffic_location.artifacts import write
from traffic_location.integration.gradio_app import Controller,validate,build_app

VIDEOS=['T7SL-WEEKDAY-PAGI','T7SL-WEEKDAY-SIANG']
def inputs(**changes):
    from traffic_location.integration.gradio_app import INPUT_NAMES
    v=dict(zip(INPUT_NAMES,['Gabungan + PPAC','T7SL',-.899,131.322,'2026-10-27',VIDEOS,'mainstreet',7,15,False,1.,1.,1.,True]))
    v.update(changes);return [v[k] for k in INPUT_NAMES]

class GradioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.config=self.root/'config'
        write(self.config/'experiment.json',{'videos':[{'filename':v+'.mp4'} for v in VIDEOS]})
    def test_invalid_input_is_rejected_before_runtime(self):
        for changes in ({'confirmed':False},{'latitude':float('nan')},{'target_id':'../secret'},{'video_ids':['foreign']},{'cut':-1}):
            with self.assertRaises(ValueError):validate(inputs(**changes),VIDEOS)
    def test_independent_engines_ignore_missing_ppac_answers_and_allow_subset(self):
        x=validate(inputs(mode='Traffic Counter',road=None,days=None,hours=None,confirmed=False,video_ids=VIDEOS[:1]),VIDEOS)
        self.assertEqual(x['mode'],'traffic');self.assertEqual(x['video_ids'],VIDEOS[:1])
    def test_eighteen_hours_is_not_rewritten(self):
        self.assertEqual(validate(inputs(hours=18),VIDEOS)['parameters']['traffic']['operating_hours'],18)
    def test_result_retains_failure_and_ppac_block_without_exposing_system(self):
        seen=[]
        class Runtime:
            def __init__(self,base,*a,**kw):self.base=base
            def execute(self,*a,**kw):
                seen.append((a,kw));return {'engines':[{'id':'area','execution_status':'FAILED','code':'MISSING'},
                  {'id':VIDEOS[0],'execution_status':'SUCCEEDED','summary':{'total':133}}],
                  'ppac':{'execution_status':'BLOCKED','std_total':None},'system':{'token':'do-not-export'}}
        c=Controller(self.root/'app',self.config,runtime_factory=Runtime)
        output=list(c.process(*inputs(video_ids=VIDEOS[:1])))[-1]
        self.assertEqual(len(output[1]),2);self.assertEqual(output[2]['execution_status'],'BLOCKED')
        self.assertEqual(seen[0][1]['video_ids'],VIDEOS[:1])
        self.assertIsNone(output[4]);self.assertNotIn('do-not-export',str(output[2]))
    def test_bad_input_never_constructs_runtime(self):
        with patch('traffic_location.integration.gradio_app.KaggleRuntime') as factory:
            c=Controller(self.root/'app',self.config,runtime_factory=factory)
            rows=list(c.process(*inputs(confirmed=False)))
            factory.assert_not_called();self.assertIsNone(rows[-1][-1])
    def test_gradio_constructs_without_engine_or_cloud_calls(self):
        try:import gradio
        except ImportError:self.skipTest('Optional Gradio UI dependency not installed')
        with patch('traffic_location.integration.gradio_app.KaggleRuntime') as factory:
            app,c=build_app(self.root/'app',self.config,runtime_factory=factory)
            self.assertTrue(app.enable_queue);factory.assert_not_called()
            labels=[c.get('props',{}).get('label') for c in app.get_config_file()['components']]
            for day in ('weekday','weekend'):
                for session in ('pagi','siang','sore','malam'):
                    self.assertIn(day+' / '+session,labels)
            for table in ('traffic_counts','area_results','ppac_results'):
                self.assertIn(table,labels)
            app.close()

if __name__=='__main__':unittest.main()
