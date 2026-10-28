"""Process death versus loopback readiness, including real HTTP on a random port."""
import contextlib,importlib.util,io,json,tempfile,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('server_monitor',ROOT/'tools/colab_server_monitor.py')
monitor=importlib.util.module_from_spec(spec);spec.loader.exec_module(monitor)

class Handler(BaseHTTPRequestHandler):
    mode='ready'
    def do_GET(self):
        if self.mode=='redirect':
            self.send_response(302);self.send_header('Location','https://example.invalid/');self.end_headers();return
        self.send_response(200);self.end_headers()
        self.wfile.write(json.dumps({'components':[]} if self.mode=='ready' else {'detail':'other app'}).encode())
    def log_message(self,*args):pass

class ServerMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.process=Mock(pid=123);self.process.poll.return_value=None
    def tearDown(self):self.temp.cleanup()
    def test_not_started_and_stopped_do_not_claim_http_readiness(self):
        status=monitor.server_snapshot(self.process,self.base)
        self.assertEqual(status['status'],'STARTING')
        self.process.poll.return_value=-2
        (self.base/'server.log').write_text('* Running on local URL:  http://0.0.0.0:7860\n')
        with patch('urllib.request.build_opener') as http:
            with contextlib.redirect_stdout(io.StringIO()):
                status=monitor.record_server_status(self.process,self.base,
                    previous={'status':'RUNNING_LOCAL_HTTP_OK','local_http':{'status':'READY'}},
                    reason='NOTEBOOK_INTERRUPT')
        http.assert_not_called()
        self.assertEqual(status['status'],'STOPPED');self.assertEqual(status['exit_code'],-2)
        self.assertEqual(json.loads((self.base/'server-status.json').read_text())['stop_reason'],'NOTEBOOK_INTERRUPT')
        self.assertEqual(status['last_running_observation']['status'],'RUNNING_LOCAL_HTTP_OK')
    def test_real_local_http_ready_invalid_and_redirect_without_public_probe(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        port=server.server_port
        (self.base/'server.log').write_text(f'* Running on local URL: http://0.0.0.0:{port}\nGRADIO_PUBLIC_URL=https://fixture.gradio.live\n')
        with patch.object(Handler,'mode','ready'):
            status=monitor.server_snapshot(self.process,self.base)
        self.assertEqual(status['status'],'RUNNING_LOCAL_HTTP_OK')
        self.assertEqual(status['public_tunnel'],'NOT_PROBED')
        self.assertEqual(status['public_url'],'https://fixture.gradio.live')
        # Log tail rotation cannot erase the observed port/URL.
        (self.base/'server.log').write_text('x'*70000)
        with patch.object(Handler,'mode','invalid'):
            invalid=monitor.server_snapshot(self.process,self.base,status)
        self.assertEqual(invalid['status'],'RUNNING_LOCAL_HTTP_UNAVAILABLE')
        self.assertEqual(invalid['local_http']['status'],'INVALID_RESPONSE')
        with patch.object(Handler,'mode','redirect'):
            redirect=monitor.server_snapshot(self.process,self.base,status)
        self.assertEqual(redirect['local_http']['code'],302)
        self.assertEqual(redirect['local_http']['status'],'HTTP_ERROR')
        server.shutdown();server.server_close()
        unavailable=monitor.server_snapshot(self.process,self.base,status)
        self.assertEqual(unavailable['status'],'RUNNING_LOCAL_HTTP_UNAVAILABLE')
        self.assertEqual(unavailable['local_http']['status'],'UNREACHABLE')

if __name__=='__main__':unittest.main()
