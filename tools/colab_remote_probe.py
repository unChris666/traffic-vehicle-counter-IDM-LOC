"""Notebook-side public Gradio smoke checks; no engine or cloud job is started."""
def probe_remote(url,*,allow_loopback=False):
    import json,urllib.request,urllib.error,re,secrets,time
    from datetime import datetime,timezone
    valid=isinstance(url,str) and re.fullmatch(r'https://[a-zA-Z0-9.-]+\.gradio\.live/?',url)
    if allow_loopback:valid=valid or bool(re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/?',url or ''))
    report={'observed_at':datetime.now(timezone.utc).isoformat(),'status':'NOT_READY','checks':[],
            'scope':'Public HTML/config/POST reachability only; not browser rendering, upload capacity or engine success.'}
    if not valid:report['reason']='PUBLIC_URL_INVALID_OR_PENDING';return report
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*a,**kw):return None
    opener=urllib.request.build_opener(*([urllib.request.ProxyHandler({})] if allow_loopback else []),NoRedirect())
    nonce=secrets.token_hex(16)
    for path,body in (('/',None),('/config',None),('/remote-check',{'nonce':nonce})):
        start=time.monotonic();entry={'path':path,'method':'GET' if body is None else 'POST'}
        try:
            data=json.dumps(body).encode() if body is not None else None
            req=urllib.request.Request(url.rstrip('/')+path,data=data,headers={'Content-Type':'application/json'} if data else {})
            with opener.open(req,timeout=5) as response:raw=response.read(1024*1024+1);entry['code']=response.status
            if len(raw)>1024*1024:raise ValueError('RESPONSE_TOO_LARGE')
            if path=='/':ok=b'gradio' in raw.lower()
            else:
                value=json.loads(raw)
                ok=isinstance(value,dict) and (isinstance(value.get('components'),list) if path=='/config' else value.get('nonce')==nonce and value.get('engine_started') is False)
            entry['status']='READY' if ok else 'INVALID_RESPONSE'
        except urllib.error.HTTPError as exc:entry.update(status='HTTP_ERROR',code=exc.code)
        except Exception as exc:entry.update(status='UNREACHABLE',error_type=type(exc).__name__)
        entry['seconds']=round(time.monotonic()-start,3);report['checks'].append(entry)
    report['status']='READY' if all(c['status']=='READY' for c in report['checks']) else 'NOT_READY'
    return report
