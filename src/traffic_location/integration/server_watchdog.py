"""Bounded loopback observations independent of Gradio's event queue."""
import json
import os
import threading
import time
from datetime import datetime,timezone
from pathlib import Path
from ..artifacts import read,write


def probe(url,*,public=False):
    import re,urllib.request,urllib.error
    pattern=r'https://[a-zA-Z0-9.-]+\.gradio\.live/config' if public else r'http://127\.0\.0\.1:[0-9]{1,5}/config'
    if not isinstance(url,str) or not re.fullmatch(pattern,url):return {'status':'NOT_CHECKED'}
    try:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        handlers=[NoRedirect()] if public else [urllib.request.ProxyHandler({}),NoRedirect()]
        with urllib.request.build_opener(*handlers).open(url,timeout=5 if public else 2) as response:
            data=response.read(1024*1024+1);code=response.status
        if len(data)>1024*1024:raise ValueError('CONFIG_RESPONSE_TOO_LARGE')
        config=json.loads(data)
        return {'status':'READY' if isinstance(config,dict) and isinstance(config.get('components'),list) else 'INVALID_RESPONSE','code':code}
    except urllib.error.HTTPError as exc:return {'status':'HTTP_ERROR','code':exc.code,'error_type':type(exc).__name__}
    except Exception as exc:return {'status':'UNREACHABLE','error_type':type(exc).__name__}


def lifecycle(base,state):
    write(Path(base)/'server-lifecycle.json',{'state':state,'pid':os.getpid(),'observed_at':datetime.now(timezone.utc).isoformat()})


def observation(base,*,public=False):
    """Fresh probe; retain the prior monitor sample explicitly as historical."""
    from .job_status import observation as process_observation
    base=Path(base)
    def saved(name):
        try:
            p=base/name
            return read(p) if p.is_file() and p.stat().st_size<=65536 else {}
        except (OSError,ValueError):return {}
    previous=saved('server-status.json');life=saved('server-lifecycle.json')
    pid=life.get('pid',previous.get('pid'));alive=process_observation(pid)['process_alive'] if isinstance(pid,int) else None
    local=probe((previous.get('local_url') or '')+'/config') if alive is True else {'status':'NOT_CHECKED'}
    closing=life.get('state') in ('STOPPING','STOPPED')
    state='STOPPED' if alive is False else 'STOPPING' if closing else 'RUNNING_LOCAL_HTTP_OK' if local['status']=='READY' else 'RUNNING_LOCAL_HTTP_UNAVAILABLE' if alive else 'UNKNOWN'
    result={'observed_at':datetime.now(timezone.utc).isoformat(),'status':state,'pid':pid,'process_alive':alive,
            'local_http':local,'public_tunnel':{'status':'NOT_PROBED'},'lifecycle':life,
            'previous_monitor_sample':previous,'watchdog':saved('server-watchdog.json'),'ui_poll_observation':saved('system/ui-poll-status.json'),
            'scope':'Fresh HTTP/process observations; HTTP readiness does not prove event streaming, browser responsiveness or engine progress.'}
    if previous.get('access_mode')=='colab':
        result['public_tunnel']={'status':'BROWSER_AUTH_REQUIRED_NOT_PROBED'}
    elif public and alive is True and not closing:
        result['public_tunnel']=probe((previous.get('public_url') or '')+'/config',public=True)
    return result


def append_diagnostics(base,archive,*,public=False):
    import zipfile,re
    from .failure_details import safe
    base=Path(base)
    with zipfile.ZipFile(archive,'a',zipfile.ZIP_DEFLATED) as z:
        z.writestr('server-observation.json',json.dumps(observation(base,public=public),indent=2))
        for name in ('server.log','server-status.json','server-lifecycle.json','server-watchdog.json','server-stacks.log'):
            p=base/name
            if not p.is_file() or p.is_symlink() or name in z.namelist():continue
            with p.open('rb') as stream:
                stream.seek(max(0,p.stat().st_size-65536));tail=stream.read().decode('utf-8',errors='replace')
            tail=re.sub(r'-----BEGIN[^\n]*PRIVATE KEY-----.*?-----END[^\n]*PRIVATE KEY-----','[REDACTED_KEY]',tail,flags=re.S)
            z.writestr(name,'\n'.join(safe(line) for line in tail.splitlines()))


class Watchdog:
    def __init__(self,base,port,interval=15):
        self.base=Path(base);self.url='http://127.0.0.1:'+str(port)+'/config';self.interval=interval
        self.stop=threading.Event();self.failures=0;self.dumped=False
        self.thread=threading.Thread(target=self.run,name='gradio-local-watchdog',daemon=True)

    def tick(self):
        http=probe(self.url);self.failures=self.failures+1 if http['status']!='READY' else 0
        write(self.base/'server-watchdog.json',{'pid':os.getpid(),'observed_at':datetime.now(timezone.utc).isoformat(),
              'local_http':http,'consecutive_failures':self.failures,'scope':'Independent loopback probe; not public tunnel or engine progress.'})
        if self.failures>=2 and not self.dumped:
            import faulthandler
            with (self.base/'server-stacks.log').open('w') as stream:faulthandler.dump_traceback(file=stream,all_threads=True)
            print('GRADIO_LOCAL_HTTP_STALLED: dua probe lokal gagal; stack thread disimpan di server-stacks.log.',flush=True)
            self.dumped=True
        if self.failures==0:self.dumped=False

    def run(self):
        while not self.stop.wait(self.interval):
            try:self.tick()
            except Exception:pass  # Monitoring must never abort a running job.

    def start(self):self.thread.start();return self
    def close(self):self.stop.set();self.thread.join(timeout=3)
