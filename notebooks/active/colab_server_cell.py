"""Notebook-only process and loopback HTTP monitoring; no public tunnel probe."""
def server_snapshot(process, base, previous=None):
    import datetime,json,re,urllib.request,urllib.error
    from pathlib import Path
    base=Path(base);previous=previous or {}
    local=previous.get('local_url');public=previous.get('public_url')
    log=base/'server.log'
    if log.is_file():
        with log.open('rb') as stream:
            stream.seek(max(0,log.stat().st_size-65536))
            tail=stream.read().decode('utf-8',errors='replace')
        ports=re.findall(r'Running on local URL:\s+http://(?:0\.0\.0\.0|127\.0\.0\.1|localhost):(\d+)',tail)
        if ports and 0<int(ports[-1])<65536:local='http://127.0.0.1:'+ports[-1]
        urls=re.findall(r'(?:GRADIO_PUBLIC_URL=|Running on public URL:\s+)(https://[a-zA-Z0-9.-]+\.gradio\.live)\b',tail)
        if urls:public=urls[-1]
    exit_code=process.poll()
    http={'status':'NOT_CHECKED','url':local+'/config' if local else None}
    if exit_code is None and local:
        try:
            # Loopback only. Do not send local health probes through an HTTP proxy.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self,*args,**kwargs):return None
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            with opener.open(http['url'],timeout=2) as response:
                code=response.status;data=response.read(1024*1024+1)
            if len(data)>1024*1024:raise ValueError('CONFIG_RESPONSE_TOO_LARGE')
            config=json.loads(data)
            http.update(code=code,status='READY' if isinstance(config,dict) and isinstance(config.get('components'),list) else 'INVALID_RESPONSE')
        except urllib.error.HTTPError as error:http.update(status='HTTP_ERROR',code=error.code)
        except Exception as error:http.update(status='UNREACHABLE',error_type=type(error).__name__)
    status=('STOPPED' if exit_code is not None else
            'RUNNING_LOCAL_HTTP_OK' if http['status']=='READY' else
            'STARTING' if not local else 'RUNNING_LOCAL_HTTP_UNAVAILABLE')
    return {'schema_version':'colab_server_status_v1',
            'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'status':status,'pid':process.pid,'exit_code':exit_code,'local_url':local,'public_url':public,
            'local_http':http,'public_tunnel':'NOT_PROBED',
            'scope':'Local HTTP readiness only; does not prove public tunnel/browser access or engine success.'}


def record_server_status(process,base,previous=None,reason=None):
    import json
    from pathlib import Path
    report=server_snapshot(process,base,previous)
    if reason:report['stop_reason']=reason
    if report['exit_code'] is not None and previous:
        report['last_running_observation']={k:previous.get(k) for k in
            ('observed_at','status','local_http','public_tunnel')}
    path=Path(base)/'server-status.json';temporary=path.with_suffix('.partial')
    temporary.write_text(json.dumps(report,indent=2));temporary.replace(path)
    print('GRADIO_STATUS='+json.dumps(report),flush=True)
    return report

if 'SERVER' in globals() and SERVER.poll() is None:
    raise RuntimeError('Server masih aktif; hentikan dahulu.')
log_path=BASE/'server.log';stream=log_path.open('wb')
SERVER=subprocess.Popen(command('serve'),env=child_env(),stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
offset=0;health=None;next_health=0;stop_reason='PROCESS_EXITED'
print('PERHATIAN: menghentikan/interrupt cell ini MENUTUP server Gradio dan tunnel. URL publik tidak dapat dipakai setelah server ditutup. Biarkan cell berjalan selama memakai UI.',flush=True)
try:
    while SERVER.poll() is None:
        with log_path.open('rb') as logs:
            logs.seek(offset);chunk=logs.read();offset=logs.tell()
        if chunk:print(chunk.decode('utf-8',errors='replace'),end='',flush=True)
        if time.monotonic()>=next_health:
            health=record_server_status(SERVER,BASE,health);next_health=time.monotonic()+30
            if health['status']=='RUNNING_LOCAL_HTTP_OK':
                print('HTTP lokal siap. Jika URL publik timeout, periksa tunnel/jaringan browser; akses publik belum diuji oleh probe lokal.',flush=True)
        time.sleep(1)
    with log_path.open('rb') as logs:
        logs.seek(offset);print(logs.read().decode('utf-8',errors='replace'),end='')
    if SERVER.returncode:raise RuntimeError('Server berhenti; lihat pesan terakhir dan server.log. Jangan lanjut ke Traffic sebelum Area terverifikasi.')
except KeyboardInterrupt:
    stop_reason='NOTEBOOK_INTERRUPT'
    print('Cell di-interrupt: server dan tunnel Gradio ditutup. Jalankan kembali cell ini lalu gunakan URL baru untuk membuka UI.',flush=True)
finally:
    if SERVER.poll() is None:
        os.killpg(SERVER.pid,signal.SIGINT)
        try:SERVER.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(SERVER.pid,signal.SIGTERM)
            try:SERVER.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(SERVER.pid,signal.SIGKILL);SERVER.wait(timeout=5)
    stream.close()
    health=record_server_status(SERVER,BASE,health,reason=stop_reason)
    print('Gradio BERHENTI. URL publik sesi ini tidak aktif. Jalankan kembali cell server untuk memperoleh URL aktif.',flush=True)
