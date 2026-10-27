"""Owner-run initial Colab setup. Stdlib host; never changes Colab kernel packages."""
import argparse,hashlib,json,os,platform,re,shlex,shutil,subprocess,sys,traceback,urllib.request
from pathlib import Path

MAMBA_URL='https://github.com/mamba-org/micromamba-releases/releases/download/2.10.0-0/micromamba-linux-64'
MAMBA_SHA='701f39c06f8e6a670a0e186c8479b9e5c0502a2f0cda6cef65d83bdd2875e8bd'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()



def safe(text):
    text=re.sub(r'-----BEGIN[^\n]*PRIVATE KEY-----.*?-----END[^\n]*PRIVATE KEY-----','[REDACTED_KEY]',str(text),flags=re.S)
    text=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/-]+',r'\1[REDACTED]',text)
    text=re.sub(r'(?i)(private_key|access_token|refresh_token|authorization)["\s:=]+[^\n]+',r'\1=[REDACTED]',text)
    return text[:1500]


class Progress:
    def __init__(self,base):
        self.path=Path(base)/'setup-status.json'
        self.value={'schema_version':'colab_setup_status_v1','stage':'input_validation',
                    'status':'RUNNING','host_python':platform.python_version()}
    def mark(self,stage):
        self.value.update(stage=stage,status='RUNNING');self.save()
        print('SETUP_STAGE='+stage,flush=True)
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.partial');temporary.write_text(json.dumps(self.value,indent=2));temporary.replace(self.path)
    def run(self,stage,command,**kwargs):
        self.mark(stage);return subprocess.run(command,check=True,**kwargs)
    def fail(self,error):
        self.value.update(status='FAILED',error_type=type(error).__name__,message=safe(error),
                          exit_code=getattr(error,'returncode',None));self.save()
    def finish(self):
        self.value.update(stage='ready',status='READY');self.save()


def select_wheel(base,name=None):
    if name is not None:
        if Path(name).name!=name or not name.endswith('.whl'):raise ValueError('Nama wheel eksplisit tidak valid.')
        wheel=Path(base)/'package'/name
        if not wheel.is_file():raise ValueError('Wheel yang diminta tidak tersedia.')
        return wheel
    wheels=list((Path(base)/'package').glob('*.whl'))
    if len(wheels)!=1:raise ValueError('Pilih satu wheel aplikasi eksplisit melalui --wheel; tidak memilih wheel lama secara otomatis.')
    return wheels[0]


def ensure_environment(binary,prefix,lock,env,progress,name):
    prefix=Path(prefix)
    # Resume an existing conda environment; create --yes can reset installed
    # scientific packages after a later setup failure. Never remove environments.
    existing=(prefix/'conda-meta/history').is_file()
    if prefix.exists() and not existing and any(prefix.iterdir()):
        raise RuntimeError('Prefix runtime berisi file non-conda; gunakan workspace baru: '+str(prefix))
    operation='install' if existing else 'create'
    progress.run('environment_'+name,[str(binary),'--no-rc',operation,'--yes','--prefix',str(prefix),'--file',str(lock)],env=env,timeout=1800)


def setup(base,wheel_name=None,progress=None):
    base=Path(base).resolve();base.mkdir(parents=True,exist_ok=True)
    progress=progress or Progress(base);progress.mark('input_validation')
    wheel=select_wheel(base,wheel_name);inputs=[wheel,base/'locks/requirements.lock',base/'locks/core-linux-64.lock',base/'locks/science-linux-64.lock',Path(__file__)]
    identity=hashlib.sha256(json.dumps({p.name:sha(p) for p in inputs},sort_keys=True).encode()).hexdigest()
    science=base/'runtime/science/bin/python';core=base/'runtime/core-python';marker=base/'setup-ready.json'
    if marker.exists():
        saved=json.loads(marker.read_text())
        if saved.get('identity')==identity:
            if not science.is_file() or not core.is_file():raise RuntimeError('Runtime hilang. Gunakan sesi/workspace baru.')
            progress.run('reuse_pip_check',[str(science),'-m','pip','check'],timeout=120)
            progress.finish();print('Dependency sudah disiapkan; tidak menginstal ulang.',flush=True);return saved
        print('Recipe berubah; validasi ulang dengan mempertahankan environment yang sudah ada.',flush=True)
    progress.mark('disk_preflight');free=shutil.disk_usage(base).free
    if free<18*1024**3:raise RuntimeError(f'Ruang kosong {free/1024**3:.1f} GiB; minimal18GiB diperlukan untuk setup, PBF dan staging. Bukan kapasitas produksi.')
    progress.mark('micromamba_download')
    binary=base/'tools/micromamba';binary.parent.mkdir(parents=True,exist_ok=True)
    if not binary.exists():
        temporary=binary.with_suffix('.partial')
        with urllib.request.urlopen(MAMBA_URL,timeout=120) as response,temporary.open('wb') as output:shutil.copyfileobj(response,output,1024*1024)
        if sha(temporary)!=MAMBA_SHA:raise RuntimeError('Checksum micromamba berbeda.')
        temporary.replace(binary)
    if sha(binary)!=MAMBA_SHA:raise RuntimeError('Checksum micromamba lokal berbeda.')
    binary.chmod(0o755)
    env={**os.environ,'MAMBA_ROOT_PREFIX':str(base/'mamba'),'CONDA_PKGS_DIRS':str(base/'mamba-pkgs'),'XDG_CACHE_HOME':str(base/'setup-cache')}
    for name in ('core','science'):
        print('Setup environment '+name+' dari lock build dan SHA256.',flush=True)
        ensure_environment(binary,base/'runtime'/name,base/'locks'/(name+'-linux-64.lock'),env,progress,name)
    # GDAL/PROJ data belongs to the core process only. Never leak conda's
    # PROJ database into the scientific interpreter's pip pyproj wheel.
    progress.mark('core_wrapper')
    core.write_text('#!/bin/sh\nunset PROJ_LIB\nexport PROJ_DATA='+shlex.quote(str(base/'runtime/core/share/proj'))+'\nexport GDAL_DATA='+shlex.quote(str(base/'runtime/core/share/gdal'))+'\nexec '+shlex.quote(str(base/'runtime/core/bin/python'))+' "$@"\n')
    core.chmod(0o755)
    progress.mark('system_binaries')
    missing=[name for name in ('ffmpeg','ffprobe','osmium') if shutil.which(name) is None]
    if missing:
        if os.geteuid()!=0:raise RuntimeError('Biner sistem belum tersedia; setup Colab memerlukan runtime dengan akses apt.')
        progress.run('apt_update',['apt-get','-o','Acquire::Retries=2','update','-qq'],timeout=300)
        progress.run('apt_install',['apt-get','install','-y','--no-install-recommends','ffmpeg','osmium-tool'],timeout=600,env={**env,'DEBIAN_FRONTEND':'noninteractive'})
    progress.run('pip_locked_dependencies',[str(science),'-m','pip','install','--require-hashes','--only-binary=:all:','--no-cache-dir','--disable-pip-version-check','--timeout','60','--retries','2','-r',str(base/'locks/requirements.lock')],timeout=2400)
    progress.run('application_wheel',[str(science),'-m','pip','install','--no-deps','--force-reinstall',str(wheel)],timeout=120)
    progress.run('pip_check',[str(science),'-m','pip','check'],timeout=120)
    progress.run('core_import_crs',[str(core),'-c','from osgeo import gdal,osr;import pyproj;assert int(gdal.VersionInfo("VERSION_NUM"))>=3070000;s=osr.SpatialReference();assert s.ImportFromEPSG(4326)==0;print("GDAL",gdal.VersionInfo("RELEASE_NAME"),"PROJ",pyproj.__version__)'],timeout=60)
    progress.run('scientific_imports',[str(science),'-c','import numpy,pandas,shapely,pyproj,osmnx,geopandas,folium,osmium,cupy,torch,onnxruntime;from google.cloud import storage,bigquery'],timeout=120)
    for command in (['ffmpeg','-version'],['ffprobe','-version'],['osmium','--version']):progress.run('binary_'+command[0],command,stdout=subprocess.DEVNULL,timeout=30)
    progress.mark('runtime_freeze')
    saved={'schema_version':'colab_setup_v1','identity':identity,'science_python':str(science),'core_python':str(core),
           'requirements_sha256':sha(base/'locks/requirements.lock'),'core_lock_sha256':sha(base/'locks/core-linux-64.lock'),
           'freeze':subprocess.check_output([str(science),'-m','pip','freeze'],text=True)}
    temporary=marker.with_suffix('.partial');temporary.write_text(json.dumps(saved,indent=2));temporary.replace(marker)
    progress.finish()
    print('SETUP_READY. Dependency terisolasi; belum ada engine berjalan.',flush=True)
    return saved

def main():
    parser=argparse.ArgumentParser();parser.add_argument('base');parser.add_argument('--wheel');args=parser.parse_args()
    progress=Progress(args.base)
    try:setup(args.base,args.wheel,progress)
    except BaseException as error:
        progress.fail(error)
        print('BOOTSTRAP_FAILED stage='+progress.value['stage']+' '+safe(error),file=sys.stderr,flush=True)
        traceback.print_exc();return 130 if isinstance(error,KeyboardInterrupt) else 1
    return 0

if __name__=='__main__':raise SystemExit(main())
