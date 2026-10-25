"""Ingestion-only CPU job. External downloads happen here, never in Area engine."""
from pathlib import Path
import base64,hashlib,importlib.metadata,json,mimetypes,os,platform,re,subprocess,sys,sysconfig,tarfile


def fingerprint():
    osinfo=platform.freedesktop_os_release()
    return {'python':f'{sys.version_info.major}.{sys.version_info.minor}',
            'platform':sysconfig.get_platform(),'os':osinfo.get('ID'),'os_version':osinfo.get('VERSION_ID'),
            'retained_packages':json.loads(os.environ['LI_RUNTIME_BASE_PACKAGES']) if 'LI_RUNTIME_BASE_PACKAGES' in os.environ else
                {p:importlib.metadata.version(p) for p in ['numpy','pandas','shapely','pyproj','requests','google-auth']}}


def run():
    import requests
    from kaggle_secrets import UserSecretsClient
    from google.oauth2 import service_account
    from google.cloud import storage
    try:info=json.loads(UserSecretsClient().get_secret('LocatioIntelligent'))
    except Exception as error:raise RuntimeError('KAGGLE_SECRET_UNAVAILABLE: activate Secret and Run All interactively') from None
    creds=service_account.Credentials.from_service_account_info(info)
    bucket=storage.Client(project='locdeproject',credentials=creds).bucket('feeder-location-intelligent')
    env=fingerprint();key=hashlib.sha256(json.dumps(env,sort_keys=True).encode()).hexdigest()[:20]
    root=Path('/kaggle/working/area_runtime_prepare');root.mkdir(exist_ok=True)
    wheels=root/'wheels';wheels.mkdir(exist_ok=True);native=root/'native';native.mkdir(exist_ok=True)
    retained=env['retained_packages']
    specs=['duckdb==2.0.0','osmnx==2.1.1','geopandas==1.2.0','google-cloud-bigquery==3.46.2',
           'google-cloud-storage','google-crc32c','folium==0.20.0','osmium==4.3.2','cupy-cuda12x==13.6.0','fastrlock==0.8.3']
    specs += [k+'=='+v for k,v in retained.items()]
    subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:','--dest',str(wheels),*specs],check=True)
    (root/'requirements.txt').write_text('\n'.join(specs)+'\n')
    subprocess.run(['apt-get','update','-qq'],check=True)
    roots=['python3-gdal','python3-pyproj','osmium-tool']
    output=subprocess.check_output(['apt-cache','depends','--recurse','--no-recommends','--no-suggests',
        '--no-conflicts','--no-breaks','--no-replaces','--no-enhances',*roots],text=True)
    names=sorted(set(line.strip() for line in output.splitlines() if line and not line[0].isspace()
                     and not line.startswith('<') and re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?',line)))
    for name in names:
        subprocess.run(['apt-get','download',name],cwd=native,check=True,stdout=subprocess.DEVNULL)
    # Extract to a private root; engine never updates its OS or apt repositories.
    system=root/'system';system.mkdir(exist_ok=True)
    for deb in native.glob('*.deb'):subprocess.run(['dpkg-deb','-x',str(deb),str(system)],check=True)
    import glob
    for link in system.rglob('*'):
        if link.is_symlink() and os.readlink(link).startswith('/'):
            target=system/os.readlink(link).lstrip('/');link.unlink();link.symlink_to(os.path.relpath(target,link.parent))
    paths=sorted(set(str(p.parent) for p in system.rglob('*.so*') if p.is_file()))
    for name,binary in [('core-python','/usr/bin/python3'),('osmium',str(system/'usr/bin/osmium'))]:
        script=root/name
        script.write_text('#!/bin/sh\nR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'+
            'export LD_LIBRARY_PATH="'+':'.join(p.replace(str(root),'$R') for p in paths)+':${LD_LIBRARY_PATH:-}"\n'+
            'export PYTHONPATH="$R/system/usr/lib/python3/dist-packages:${PYTHONPATH:-}"\n'+
            'export PROJ_DATA="$R/system/usr/share/proj"\nexport GDAL_DATA="$R/system/usr/share/gdal"\nexport PROJ_NETWORK=OFF\n'+
            'exec "'+binary.replace(str(root),'$R')+'" "$@"\n')
        script.chmod(0o755)
    subprocess.run([str(root/'core-python'),'-c','from osgeo import gdal;import pyproj;assert int(gdal.VersionInfo("VERSION_NUM"))>=3070000;print(gdal.VersionInfo())'],check=True)
    subprocess.run([str(root/'osmium'),'--version'],check=True)
    # Resolve every CSS image/font to data URI in the ingestion job.
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--find-links',str(wheels),'folium==0.20.0'],check=True)
    import folium
    from folium.plugins import Fullscreen,MarkerCluster
    from urllib.parse import urljoin
    assets={}
    def fetch(url,css=False):
        if url in assets:return assets[url]
        response=requests.get(url,timeout=60);response.raise_for_status();body=response.text
        body=re.sub(r'(?m)//[#@]\s*source(?:Mapping)?URL=[^\r\n]*','',body)
        body=re.sub(r'/\*[#@]\s*source(?:Mapping)?URL=.*?\*/','',body,flags=re.S)
        if css:
            def inline(match):
                link=match.group(1).strip(' \"\'')
                if link.startswith(('data:','#')):return match.group(0)
                absolute=urljoin(url,link);r=requests.get(absolute,timeout=60);r.raise_for_status()
                mime=r.headers.get('content-type') or mimetypes.guess_type(absolute)[0] or 'application/octet-stream'
                return 'url(data:'+mime+';base64,'+base64.b64encode(r.content).decode()+')'
            body=re.sub(r'url\(([^)]+)\)',inline,body)
            if '@import' in body:raise RuntimeError('Unresolved CSS import')
        assets[url]=body;return body
    for cls in [folium.Map,Fullscreen,MarkerCluster]:
        for _,url in cls.default_js:fetch(url)
        for _,url in cls.default_css:fetch(url,True)
    (root/'frontend.json').write_text(json.dumps(assets))
    files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*')
           if p.is_file() and not p.is_symlink() and not p.is_relative_to(native)}
    (root/'bundle.json').write_text(json.dumps({'environment':env,'retained':retained,'files':files},indent=2))
    archive=root.parent/'area-runtime.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        for p in sorted(root.iterdir()):
            if p!=native:t.add(p,arcname=p.name)
    sha=hashlib.sha256(archive.read_bytes()).hexdigest();object_name='runtime/area/'+key+'/'+sha+'/area-runtime.tar.gz'
    blob=bucket.blob(object_name);blob.metadata={'sha256':sha}
    blob.upload_from_filename(str(archive),if_generation_match=0,checksum='crc32c',timeout=600);blob.reload()
    manifest={'schema':'area_gcs_runtime_v1','environment':env,'object':object_name,'generation':int(blob.generation),
        'sha256':sha,'bytes':archive.stat().st_size,'retained':retained}
    pointer=bucket.blob('runtime/area/'+key+'/manifest.json')
    generation=0
    if pointer.exists():pointer.reload();generation=int(pointer.generation)
    pointer.upload_from_string(json.dumps(manifest),content_type='application/json',if_generation_match=generation)
    (root.parent/'runtime_preparation_receipt.json').write_text(json.dumps(manifest,indent=2))
    print('READY: gs://'+bucket.name+'/'+pointer.name)


if __name__=='__main__':run()
