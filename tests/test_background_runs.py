"""A waiting engine cannot hold submit/poll HTTP requests or duplicate a job."""
import tempfile,threading,time,unittest,os,inspect
from pathlib import Path
from unittest.mock import patch
from traffic_location.integration.background_runs import BackgroundRuns
from traffic_location.artifacts import write
class RunnerTests(unittest.TestCase):
    def test_elapsed_seconds_increase_even_without_new_snapshot_and_stop_at_completion(self):
        from traffic_location.integration.background_runs import elapsed_line
        state={'started_monotonic':100.,'snapshot_monotonic':105.,'done':False}
        self.assertIn('10 detik',elapsed_line(state,110))
        self.assertIn('20 detik',elapsed_line(state,120))
        self.assertIn('15 detik',elapsed_line(state,120))
        state.update(done=True,finished_monotonic=125.)
        self.assertIn('25 detik',elapsed_line(state,200))

    def test_disconnected_browser_and_duplicate_submit_do_not_duplicate_engine(self):
        runner=BackgroundRuns();entered=threading.Event();release=threading.Event();finished=threading.Event();calls=[]
        self.addCleanup(release.set)
        def events():
            yield 'accepted'
            calls.append('engine');entered.set();release.wait(3)
            yield 'complete';finished.set()
        start=time.monotonic();token,first,reused=runner.submit(events)
        self.assertLess(time.monotonic()-start,1);self.assertEqual(first,'accepted');self.assertFalse(reused)
        self.assertTrue(entered.wait(1))
        second,_,reused=runner.submit(lambda:(_ for _ in () ))
        self.assertTrue(reused);self.assertEqual(token,second);self.assertEqual(calls,['engine'])
        # No browser poll is needed for completion.
        release.set();self.assertTrue(finished.wait(1))
        for _ in range(100):
            if runner.snapshot(token)['done']:break
            threading.Event().wait(.01)
        self.assertTrue(runner.snapshot(token)['done']);self.assertEqual(runner.snapshot(token)['value'],'complete')
        self.assertIsNone(runner.current());self.assertEqual(runner.current(completed=True),token)
    def test_worker_error_is_bounded_and_redacted_and_releases_slot(self):
        r=BackgroundRuns()
        def events():
            yield 'accepted'
            raise RuntimeError('Authorization: Bearer fixture-secret')
        token,_,_=r.submit(events)
        for _ in range(100):
            if r.snapshot(token)['done']:break
            threading.Event().wait(.01)
        state=r.snapshot(token);self.assertTrue(state['done']);self.assertNotIn('fixture-secret',state['error']);self.assertIsNone(r.current())
    def test_simultaneous_clicks_share_one_job(self):
        r=BackgroundRuns();release=threading.Event();barrier=threading.Barrier(5);tokens=[];self.addCleanup(release.set)
        def events():yield 'accepted';release.wait(3);yield 'done'
        def click():barrier.wait();tokens.append(r.submit(events)[0])
        threads=[threading.Thread(target=click) for _ in range(5)]
        for t in threads:t.start()
        for t in threads:t.join(1)
        self.assertEqual(len(tokens),5);self.assertEqual(len(set(tokens)),1)
    def test_snapshot_limit_does_not_discard_current_job(self):
        r=BackgroundRuns()
        for _ in range(25):
            token,_,_=r.submit(lambda:iter(['accepted','done']))
            for _ in range(100):
                if r.snapshot(token)['done']:break
                threading.Event().wait(.001)
        self.assertLessEqual(len(r.records),20);self.assertIsNotNone(r.snapshot(token))

class PollingCallbackTests(unittest.TestCase):
    def test_running_uses_short_callbacks_and_retains_result_without_browser(self):
        from traffic_location.integration.gradio_app import build_app,validate
        from traffic_location.integration.job_input import review
        import test_gradio_ui as fixture
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LI_PHASE123':'1','LI_COMPONENT_FLOW':'1'}):
            p=Path(d);write(p/'config/experiment.json',{'videos':[]});app,c=build_app(p/'ui',p/'config')
            self.addCleanup(app.close)
            functions={f.fn.__name__:f for f in app.fns.values() if f.fn}
            self.assertFalse(functions['submit_job'].queue);self.assertFalse(functions['poll_job'].queue)
            self.assertFalse(inspect.isgeneratorfunction(functions['submit_job'].fn));self.assertFalse(inspect.isgeneratorfunction(functions['poll_job'].fn))
            values=fixture.inputs(mode='Area Coverage')+['Dataset T7SL (contoh)',[],None,False,None,True,'MENENGAH ATAS']
            values[18]=review(validate(values,[]))
            release=threading.Event();done=threading.Event();self.addCleanup(release.set)
            def process(*v):
                yield 'accepted',[],{},'',None,None
                release.wait(3)
                yield 'complete',[],{'execution_status':'SUCCEEDED','std_total':None},'',None,{'output':str(p/'run'),'context':{'target_id':'T7SL'}}
                done.set()
            with patch.object(c,'process',side_effect=process):
                initial=functions['submit_job'].fn(*values);token=initial[0]
                self.assertEqual(len(initial),38)
                unchanged=functions['poll_job'].fn(token,1)
                self.assertIn('Waktu total job:',unchanged[4])
                self.assertIn('umur snapshot pemantauan:',unchanged[4])
                duplicate=functions['submit_job'].fn(*values);self.assertEqual(duplicate[0],token)
                poll=functions['poll_job'].fn(token,0);self.assertEqual(len(poll),36)
                release.set();self.assertTrue(done.wait(1))
                for _ in range(100):
                    if c.background_runs.snapshot(token)['done']:break
                    threading.Event().wait(.01)
                final=functions['poll_job'].fn(token,0)
                self.assertEqual(final[1],'complete');self.assertIn('belum dipublikasikan',final[7])
                self.assertEqual(functions['reconnect_job'].fn()[0],token)
