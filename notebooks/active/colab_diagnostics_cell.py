# Ganti SELURUH cell unduh diagnosis lama dengan kode ini.
# This cell also works when setup failed before SCIENCE was assigned.
import zipfile,re
archive=BASE/'colab-diagnostics.zip'
exported=False
if 'SCIENCE' in globals() and Path(SCIENCE).is_file():
    result=subprocess.run([SCIENCE,'-c',"from pathlib import Path\nimport sys,json,zipfile\nfrom traffic_location.integration.area_trace import latest_report\nfrom traffic_location.integration.failure_details import safe\nbase=Path(sys.argv[1]);traces=sorted((base/'system/targets').glob('*/runs/*/area/area-trace.json'),key=lambda p:p.stat().st_mtime)\nreport=latest_report(traces[-1].parents[3]) if traces else {'status':'NO_AREA_RUN'}\ndef clean(v):\n    if isinstance(v,str):return safe(v)\n    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}\n    if isinstance(v,list):return [clean(x) for x in v]\n    return v\nwith zipfile.ZipFile(base/'colab-diagnostics.zip','w',zipfile.ZIP_DEFLATED) as z:\n    z.writestr('area-report.json',json.dumps(clean(report),indent=2))\n    for name in ('gpu-allocation.json','colab-runtime-verified.json','colab-preflight.json','colab-startup-failure.json','setup-status.json','core-runtime-isolation.json'):\n        path=base/name\n        if path.is_file() and path.stat().st_size<131072:z.writestr(name,json.dumps(clean(json.loads(path.read_text())),indent=2))\nprint('DIAGNOSTIC_ZIP='+str(base/'colab-diagnostics.zip'))\n",str(BASE)],env=child_env(),capture_output=True,text=True)
    exported=result.returncode==0
    if exported:print(result.stdout)
with zipfile.ZipFile(archive,'a' if exported else 'w',zipfile.ZIP_DEFLATED) as bundle:
    if not exported:bundle.writestr('status.txt','Setup/startup diagnosis only; Area report not available yet.')
    for name in ('setup-status.json','setup.log','runtime-check.log','cloud-preflight.log','core-isolation.log','core-runtime-isolation.json','server.log','server-status.json'):
        path=BASE/name
        if not path.is_file() or name in bundle.namelist():continue
        with path.open('rb') as stream:
            stream.seek(max(0,path.stat().st_size-65536));text=stream.read().decode('utf-8',errors='replace')
        text=re.sub(r'-----BEGIN[^\n]*PRIVATE KEY-----.*?-----END[^\n]*PRIVATE KEY-----','[REDACTED_KEY]',text,flags=re.S)
        text=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/-]+',r'\1[REDACTED]',text)
        text=re.sub(r'(?i)(private_key|access_token|refresh_token|authorization)["\s:=]+[^\n]+',r'\1=[REDACTED]',text)
        bundle.writestr(name,text)
from google.colab import files
files.download(str(archive))
