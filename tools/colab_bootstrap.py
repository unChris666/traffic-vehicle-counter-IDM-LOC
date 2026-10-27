"""Owner-run initial Colab setup. Stdlib host; never changes Colab kernel packages."""
import hashlib,json,os,shlex,shutil,subprocess,sys,urllib.request
from pathlib import Path

MAMBA_URL='https://github.com/mamba-org/micromamba-releases/releases/download/2.10.0-0/micromamba-linux-64'
MAMBA_SHA='701f39c06f8e6a670a0e186c8479b9e5c0502a2f0cda6cef65d83bdd2875e8bd'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setup(base):
    base=Path(base).resolve();base.mkdir(parents=True,exist_ok=True)
    wheels=list((base/'package').glob('*.whl'))
    if len(wheels)!=1:raise ValueError('Satu wheel aplikasi eksplisit diperlukan.')
    wheel=wheels[0];inputs=[wheel,base/'locks/requirements.lock',base/'locks/core-linux-64.lock',base/'locks/science-linux-64.lock',Path(__file__)]
    identity=hashlib.sha256(json.dumps({p.name:sha(p) for p in inputs},sort_keys=True).encode()).hexdigest()
    science=base/'runtime/science/bin/python';core=base/'runtime/core-python';marker=base/'setup-ready.json'
    if marker.exists():
        saved=json.loads(marker.read_text())
        if saved.get('identity')!=identity:raise RuntimeError('Setup berubah. Hentikan server, gunakan workspace Colab baru untuk kandidat ini.')
        if not science.is_file() or not core.is_file():raise RuntimeError('Runtime hilang. Gunakan sesi/workspace baru.')
        subprocess.run([str(science),'-m','pip','check'],check=True,timeout=120)
        print('Dependency sudah disiapkan; tidak menginstal ulang.',flush=True);return saved
    if shutil.disk_usage(base).free<18*1024**3:raise RuntimeError('Ruang kosong minimal18GiB diperlukan untuk runtime, sumber PBF dan staging; ini bukan kapasitas video produksi.')
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
        subprocess.run([str(binary),'--no-rc','create','--yes','--prefix',str(base/'runtime'/name),'--file',str(base/'locks'/(name+'-linux-64.lock'))],env=env,check=True,timeout=1800)
    # GDAL/PROJ data belongs to the core process only. Never leak conda's
    # PROJ database into the scientific interpreter's pip pyproj wheel.
    core.write_text('#!/bin/sh\nunset PROJ_LIB\nexport PROJ_DATA='+shlex.quote(str(base/'runtime/core/share/proj'))+'\nexport GDAL_DATA='+shlex.quote(str(base/'runtime/core/share/gdal'))+'\nexec '+shlex.quote(str(base/'runtime/core/bin/python'))+' "$@"\n')
    core.chmod(0o755)
    missing=[name for name in ('ffmpeg','ffprobe','osmium') if shutil.which(name) is None]
    if missing:
        if os.geteuid()!=0:raise RuntimeError('Biner sistem belum tersedia; setup Colab memerlukan runtime dengan akses apt.')
        subprocess.run(['apt-get','-o','Acquire::Retries=2','update','-qq'],check=True,timeout=300)
        subprocess.run(['apt-get','install','-y','--no-install-recommends','ffmpeg','osmium-tool'],check=True,timeout=600,env={**env,'DEBIAN_FRONTEND':'noninteractive'})
    subprocess.run([str(science),'-m','pip','install','--require-hashes','--only-binary=:all:','--no-cache-dir','--disable-pip-version-check','--timeout','60','--retries','2','-r',str(base/'locks/requirements.lock')],check=True,timeout=2400)
    subprocess.run([str(science),'-m','pip','install','--no-deps','--force-reinstall',str(wheel)],check=True,timeout=120)
    subprocess.run([str(science),'-m','pip','check'],check=True,timeout=120)
    subprocess.run([str(core),'-c','from osgeo import gdal,osr;import pyproj;assert int(gdal.VersionInfo("VERSION_NUM"))>=3070000;s=osr.SpatialReference();assert s.ImportFromEPSG(4326)==0;print("GDAL",gdal.VersionInfo("RELEASE_NAME"),"PROJ",pyproj.__version__)'],check=True,timeout=60)
    subprocess.run([str(science),'-c','import numpy,pandas,shapely,pyproj,osmnx,geopandas,folium,osmium,cupy,torch,onnxruntime;from google.cloud import storage,bigquery'],check=True,timeout=120)
    for command in (['ffmpeg','-version'],['ffprobe','-version'],['osmium','--version']):subprocess.run(command,check=True,stdout=subprocess.DEVNULL,timeout=30)
    saved={'schema_version':'colab_setup_v1','identity':identity,'science_python':str(science),'core_python':str(core),
           'requirements_sha256':sha(base/'locks/requirements.lock'),'core_lock_sha256':sha(base/'locks/core-linux-64.lock'),
           'freeze':subprocess.check_output([str(science),'-m','pip','freeze'],text=True)}
    temporary=marker.with_suffix('.partial');temporary.write_text(json.dumps(saved,indent=2));temporary.replace(marker)
    print('SETUP_READY. Dependency terisolasi; belum ada engine berjalan.',flush=True)
    return saved

if __name__=='__main__':setup(sys.argv[1])
