"""Google-only notebook bootstrap, generation-pinned staging and frontend assets."""
from pathlib import Path
import hashlib,json,os,platform,re,subprocess,sys,sysconfig,tarfile
from urllib.parse import quote,urlsplit

BUCKET='feeder-location-intelligent'
PBF={'object':'sources/osm/indonesia/bb1b60f7dfdbb1f19d33fa1ffb0c546f7e75928126ac3a2c004839a3ff2003bc/indonesia.osm.pbf',
     'generation':1792937275821365,'bytes':1739881462,
     'sha256':'bb1b60f7dfdbb1f19d33fa1ffb0c546f7e75928126ac3a2c004839a3ff2003bc'}


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def environment():
    import importlib.metadata
    info=platform.freedesktop_os_release()
    return {'python':f'{sys.version_info.major}.{sys.version_info.minor}','platform':sysconfig.get_platform(),
            'os':info.get('ID'),'os_version':info.get('VERSION_ID'),
            'retained_packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','shapely','pyproj','requests','google-auth']}}


def install_google_only_guard():
    import requests,urllib.request
    if getattr(requests.sessions.Session.request,'google_only',False) is True:return
    original=requests.sessions.Session.request;send=requests.sessions.Session.send;urlopen=urllib.request.urlopen
    redirect=urllib.request.HTTPRedirectHandler.redirect_request
    def validate(url):
        parsed=urlsplit(url);host=(parsed.hostname or '').lower()
        if parsed.scheme!='https' or not (host=='googleapis.com' or host.endswith('.googleapis.com')):
            raise RuntimeError('EXTERNAL_NETWORK_FORBIDDEN: '+host)
    def request(self,method,url,*a,**kw):validate(url);return original(self,method,url,*a,**kw)
    def send_request(self,request,*a,**kw):validate(request.url);return send(self,request,*a,**kw)
    def open_url(url,*a,**kw):validate(url.full_url if hasattr(url,'full_url') else url);return urlopen(url,*a,**kw)
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate(newurl);return redirect(self,req,fp,code,msg,headers,newurl)
    request.google_only=True;requests.sessions.Session.request=request;requests.sessions.Session.send=send_request
    urllib.request.urlopen=open_url;urllib.request.HTTPRedirectHandler.redirect_request=redirect_request


def google_session():
    from kaggle_secrets import UserSecretsClient
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    # Kaggle credential bootstrap precedes the provider-data egress guard.
    try:info=json.loads(UserSecretsClient().get_secret('LocatioIntelligent'))
    except Exception as error:raise RuntimeError('KAGGLE_SECRET_UNAVAILABLE') from error
    credentials=service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/cloud-platform'])
    install_google_only_guard()
    return AuthorizedSession(credentials)


def gcs_json(session,name):
    url='https://storage.googleapis.com/download/storage/v1/b/'+BUCKET+'/o/'+quote(name,safe='')
    response=session.get(url,params={'alt':'media'},timeout=60)
    if response.status_code==404:raise RuntimeError('GCS_REQUIRED_OBJECT_MISSING: '+name)
    response.raise_for_status();return response.json()


def stage(session,ref,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.stat().st_size!=ref['bytes'] or sha(path)!=ref['sha256']:raise RuntimeError('LOCAL_INPUT_HASH_MISMATCH')
        print('GCS local cache verified:',path.name,flush=True);return path
    tmp=path.with_suffix(path.suffix+'.partial');digest=hashlib.sha256();done=0;next_log=0
    url='https://storage.googleapis.com/download/storage/v1/b/'+BUCKET+'/o/'+quote(ref['object'],safe='')
    with session.get(url,params={'alt':'media','generation':str(ref['generation'])},stream=True,timeout=(30,120)) as response:
        response.raise_for_status()
        with tmp.open('wb') as f:
            for chunk in response.iter_content(8*1024*1024):
                f.write(chunk);digest.update(chunk);done+=len(chunk)
                if done>=next_log:print('GCS staging:',path.name,done,'bytes',flush=True);next_log=done+128*1024*1024
    if done!=ref['bytes'] or digest.hexdigest()!=ref['sha256']:raise RuntimeError('GCS_INPUT_HASH_MISMATCH')
    tmp.replace(path);return path


def bootstrap_runtime():
    import importlib.metadata
    session=google_session();env=environment();key=hashlib.sha256(json.dumps(env,sort_keys=True).encode()).hexdigest()[:20]
    manifest=gcs_json(session,'runtime/area/'+key+'/manifest.json')
    basemap=manifest.get('basemap')
    if not basemap or basemap.get('status')!='READY' or basemap.get('source')!=PBF:
        raise RuntimeError('GCS_BASEMAP_PREPARATION_REQUIRED')
    if manifest['environment']!=env:raise RuntimeError('GCS_RUNTIME_ENVIRONMENT_MISMATCH')
    for package,version in manifest['retained'].items():
        if importlib.metadata.version(package)!=version:raise RuntimeError('GCS_RUNTIME_PACKAGE_MISMATCH: '+package)
    archive=stage(session,manifest,Path('/kaggle/working/gcs_runtime_cache')/(manifest['sha256']+'.tar.gz'))
    root=archive.parent/manifest['sha256']
    if not root.exists():
        root.mkdir()
        with tarfile.open(archive) as bundle:bundle.extractall(root,filter='data')
    inventory=json.loads((root/'bundle.json').read_text())
    for name,digest in inventory['files'].items():
        file=root/name
        if not file.resolve().is_relative_to(root.resolve()) or not file.is_file() or sha(file)!=digest:
            raise RuntimeError('GCS_RUNTIME_CONTENT_CHANGED: '+name)
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--disable-pip-version-check',
                    *map(str,sorted((root/'wheels').glob('*.whl')))],check=True)
    subprocess.run([str(root/'core-python'),'-c','from osgeo import gdal;import pyproj;assert int(gdal.VersionInfo("VERSION_NUM"))>=3070000'],check=True)
    subprocess.run([str(root/'osmium'),'--version'],check=True)
    os.environ['LI_GCS_RUNTIME_ROOT']=str(root);os.environ['PROJ_NETWORK']='OFF'
    print('GOOGLE-ONLY runtime and national basemap manifest verified:',root,flush=True);return root,session,basemap


def google_only_render(config,market_config,pilot,facilities,result,*,session=None,basemap_ref=None):
    import folium
    from unittest.mock import patch
    from location_intelligent_market_map import market_map
    from location_intelligent_li3_sources import read_json,write_json,canonical_bytes
    from location_intelligent_gcs_basemap import VECTORGRID_URL,load_tiles,basemap_layer
    from location_intelligent_map_pilot import query_bbox
    if session is None or basemap_ref is None:raise RuntimeError('GCS_BASEMAP_SESSION_REQUIRED')
    if read_json(Path(result['output_path'])/'result.json')!=result:raise ValueError('Retained market result changed')
    identity={'result_sha256':sha(Path(result['output_path'])/'result.json'),'adapter_sha256':sha(__file__),
              'frontend_sha256':sha(Path(os.environ['LI_GCS_RUNTIME_ROOT'])/'frontend.json'),
              'basemap_adapter_sha256':sha(Path(__file__).with_name('location_intelligent_gcs_basemap.py')),
              'basemap':basemap_ref}
    version=hashlib.sha256(canonical_bytes(identity)).hexdigest()
    view=Path(result['output_path'])/'views'/('google-'+version);manifest=view/'view_manifest.json'
    if manifest.exists():
        saved=read_json(manifest)
        if saved['identity']!=identity:raise RuntimeError('GCS_PRESENTATION_IDENTITY_CHANGED')
        for name,digest in saved['files'].items():
            if sha(view/name)!=digest:raise RuntimeError('GCS_PRESENTATION_CHANGED')
        return view/'market_map.html'
    if view.exists():raise RuntimeError('GCS_PRESENTATION_INCOMPLETE')
    path=view/'market_map.html'
    box=query_bbox(config['latitude'],config['longitude'],max(config['building_radius_m'],config['poi_radius_m'])+1000)
    tiles,audit=load_tiles(session,basemap_ref,box)
    assets=json.loads((Path(os.environ['LI_GCS_RUNTIME_ROOT'])/'frontend.json').read_text())
    original=folium.Map.__init__
    def init(self,*a,**kw):
        kw['tiles']=None;original(self,*a,**kw);self.add_child(basemap_layer(tiles,basemap_ref['maxzoom']))
    with patch.object(folium.Map,'__init__',init):market_map(config,market_config,pilot,facilities,result,path)
    text=path.read_text()
    text=text.replace('</head>','<script src="'+VECTORGRID_URL+'"></script></head>',1)
    if VECTORGRID_URL not in assets:raise RuntimeError('GCS_FRONTEND_VECTORGRID_MISSING')
    def script(match):
        url=match.group(1)
        if url not in assets:raise RuntimeError('GCS_FRONTEND_ASSET_MISSING: '+urlsplit(url).hostname)
        return '<script>'+assets[url].replace('</script','<\\/script')+'</script>'
    def css(match):
        url=match.group(1)
        if url not in assets:raise RuntimeError('GCS_FRONTEND_ASSET_MISSING: '+urlsplit(url).hostname)
        return '<style>'+assets[url]+'</style>'
    text=re.sub(r'<script[^>]+src="([^"]+)"[^>]*>\s*</script>',script,text)
    text=re.sub(r'<link[^>]+href="([^"]+)"[^>]*>',css,text)
    if re.search(r'(?:src|url\()\s*[=\"\s]*https?://',text):raise RuntimeError('EXTERNAL_FRONTEND_RESOURCE_REMAINS')
    text=text.replace('<body>','<body><p>Basemap OSM Indonesia dari GCS; tile tampilan wilayah ini tersimpan di HTML. © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, ODbL.</p>',1)
    path.write_text(text)
    write_json(view/'basemap_view.json',audit,exclusive=True)
    write_json(manifest,{'identity':identity,'files':{n:sha(view/n) for n in ['market_map.html','market_map.geojson','basemap_view.json']}},exclusive=True)
    return path
