"""Build a self-contained owner-run Colab L4 notebook from the exact source wheel."""
import argparse,base64,hashlib,io,json,zipfile
from pathlib import Path


def build(wheel,output):
    root=Path(__file__).resolve().parents[1];wheel=Path(wheel).resolve()
    version=wheel.name.split('-')[1]
    with zipfile.ZipFile(wheel) as z:
        for name in z.namelist():
            if name.startswith('traffic_location/') and name.endswith('.py'):assert z.read(name)==(root/'src'/name).read_bytes(),name
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(wheel,'package/'+wheel.name)
        z.write(root/'tools/colab_bootstrap.py','bootstrap.py')
        z.write(root/'deploy/requirements.lock','locks/requirements.lock')
        for name in ('science','core'):z.write(root/'deploy/colab'/(name+'-linux-64.lock'),'locks/'+name+'-linux-64.lock')
        for p in sorted((root/'results/t7sl_modular/config').rglob('*.json')):z.write(p,'config/'+str(p.relative_to(root/'results/t7sl_modular/config')))
    raw=data.getvalue();cells=[]
    def md(s):cells.append({'cell_type':'markdown','metadata':{},'source':s})
    def code(s):
        compile(s,'colab-cell','exec');cells.append({'cell_type':'code','metadata':{},'source':s,'execution_count':None,'outputs':[]})
    md(f'''# Colab L4 — Area dahulu, Traffic dan PPAC sesudah verifikasi\n\nKandidat **{version} — perbaikan setup r2**, branch pengujian fix/area-user-testing. Belum lulus fresh Area Sorong/L4 atau deployment. Formula engine tidak diubah. Notebook ini tidak menjalankan analisis saat startup; pemrosesan dimulai dari tombol Gradio.\n\n1. Pilih **Runtime → Change runtime type → L4 GPU**, kemudian reconnect. Metadata notebook hanya petunjuk; pemeriksaan di bawah menolak GPU selain L4. Alokasi bergantung akses/kuota Colab.\n2. Run All. Dependency dipasang sekali di awal pada Python3.12 terisolasi; paket bawaan kernel Colab tidak diubah. GDAL/PROJ memakai interpreter core terpisah. Setiap sesi Colab baru memerlukan setup lagi. Unduhan beberapa GB memerlukan waktu dan ruang; kegagalan pip check/import/CUDA menghentikan startup.\n3. Ikuti dialog autentikasi Google. Gunakan akun yang berizin membaca sumber, membuat query BQ dan membaca/menulis hasil. Kredensial tidak perlu ditempel ke notebook.\n4. Buka GRADIO_PUBLIC_URL, isi KDTK/Nama Toko/koordinat, jalankan **Area Coverage** tanpa video.\n5. Buka RESULT dan **Buka hasil BQ** untuk job yang sama. Tabel dan peta GCS harus berhasil dibaca dan diverifikasi sebelum Traffic/PPAC dibuka untuk target/periode/koordinat/versi tersebut. Penerimaan artefak oleh viewer bukan bukti tile eksternal/pan/zoom berhasil; tinjau sendiri di browser.\n6. Setelah itu, gunakan upload Gradio atau gs:// pada slot video. Path lokal yang diizinkan: /content/videos/. Dataset Kaggle tidak dimount otomatis. PPAC tetap menunggu Area valid serta semua sesi yang diwajibkan, termasuk shift3 untuk jam>15. Missing bukan nol.\n\nOutput: **gs://aretfak-location-intelligence**, dataset **locdeproject.location_intelligence**. Sumber model/PBF/toko tetap terpisah. Setup tidak membuat tabel, tidak mengubah IAM, dan tidak membuka bucket publik. Workspace /content sementara; simpan diagnosis/hasil sebelum runtime dihentikan. Jangan menyalin ADC/private key ke chat atau GitHub. Main dan refactor/deployment-foundation belum dipromosikan.''')
    code('''import csv,io,json,os,subprocess,sys,time,signal
from pathlib import Path
BASE=Path('/content/location-intelligence-colab');BASE.mkdir(parents=True,exist_ok=True)
try:
    output=subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid,memory.total,driver_version','--format=csv,noheader,nounits'],text=True,timeout=30)
except (OSError,subprocess.SubprocessError):
    raise RuntimeError('GPU belum tersedia. Pilih Runtime → Change runtime type → L4 GPU lalu reconnect.') from None
GPU=[dict(zip(('name','uuid','memory_mib','driver'),(v.strip() for v in row))) for row in csv.reader(io.StringIO(output)) if len(row)==4]
import re
if not GPU or not all(re.search(r'\\bL4\\b',v['name']) for v in GPU):
    raise RuntimeError('GPU yang benar-benar dialokasikan bukan L4: '+str(GPU)+'. Pilih L4 pada pengaturan Colab.')
print('GPU_ALLOCATION='+json.dumps(GPU))
(BASE/'gpu-allocation.json').write_text(json.dumps(GPU,indent=2))
''')
    md('## Setup sekali di awal\nEnvironment scientific dan core memakai lock terpisah. Transitive pip memakai hash; conda memakai URL build dan SHA256. Biner ffmpeg/osmium dipasang melalui apt jika belum tersedia; versi sistem tetap diperiksa. Jangan menjalankan ulang setup saat server/engine masih aktif.')
    code('''import base64,hashlib,zipfile,io
if 'SERVER' in globals() and SERVER.poll() is None:
    raise RuntimeError('Hentikan cell server dahulu sebelum menjalankan setup ulang.')
PAYLOAD=base64.b64decode('''+repr(base64.b64encode(raw).decode())+''')
assert hashlib.sha256(PAYLOAD).hexdigest()=='''+repr(hashlib.sha256(raw).hexdigest())+'''
with zipfile.ZipFile(io.BytesIO(PAYLOAD)) as bundle:
    bundle.extractall(BASE)
WHEEL=BASE/'package'/'''+repr(wheel.name)+'''
assert hashlib.sha256(WHEEL.read_bytes()).hexdigest()=='''+repr(hashlib.sha256(wheel.read_bytes()).hexdigest())+'''
def run_logged(command,log_name,env=None):
    # Python-level streaming works in Colab even when inherited child FDs are hidden.
    import re
    log_path=BASE/(log_name+'.log')
    print('Menjalankan '+log_name+'; log: '+str(log_path),flush=True)
    with log_path.open('w') as logs:
        process=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                 text=True,encoding='utf-8',errors='replace',bufsize=1,start_new_session=True)
        hiding_key=False
        try:
            for line in process.stdout:
                if '-----BEGIN' in line and 'PRIVATE KEY' in line:
                    hiding_key=True;line='[REDACTED PRIVATE KEY]\\n'
                elif hiding_key:
                    if '-----END' in line and 'PRIVATE KEY' in line:hiding_key=False
                    continue
                line=re.sub(r'(?i)(bearer\\s+)[A-Za-z0-9._~+/-]+',r'\\1[REDACTED]',line)
                line=re.sub(r'(?i)(private_key|access_token|refresh_token|authorization)["\\s:=]+[^\\n]+',r'\\1=[REDACTED]',line)
                logs.write(line);logs.flush();print(line,end='',flush=True)
            returncode=process.wait()
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
            raise
        finally:
            if process.stdout is not None:process.stdout.close()
    if returncode:
        status_path=BASE/('setup-status.json' if log_name=='setup' else 'colab-startup-failure.json')
        try:status=json.loads(status_path.read_text())
        except (OSError,ValueError):status={}
        with log_path.open('rb') as logs:
            logs.seek(max(0,log_path.stat().st_size-16384));tail=logs.read().decode('utf-8',errors='replace')
        tail='\\n'.join(tail.splitlines()[-80:])
        raise RuntimeError(log_name+' gagal pada tahap '+str(status.get('stage','lihat log'))+
                           '; exit='+str(returncode)+'; '+str(log_path)+'\\n'+tail)
    return returncode
run_logged([sys.executable,'-u',str(BASE/'bootstrap.py'),str(BASE),'--wheel',WHEEL.name],'setup')
SETUP=json.loads((BASE/'setup-ready.json').read_text())
SCIENCE=SETUP['science_python'];CORE=SETUP['core_python']
def child_env():
    env={**os.environ,'LI_RUNTIME_MODE':'bundled','LI_AUTH_MODE':'adc','LI_RUNTIME_PLATFORM':'colab',
         'LI_CORE_PYTHON':CORE,'LI_COLAB_GATE_ROOT':str(BASE/'area-verifications'),
         'GRADIO_ANALYTICS_ENABLED':'False','PROJ_NETWORK':'OFF','GOOGLE_CLOUD_PROJECT':'locdeproject'}
    for key in ('PROJ_LIB','PROJ_DATA','GDAL_DATA'):env.pop(key,None)
    return env
def command(operation):
    return [SCIENCE,'-u','-m','traffic_location.integration.colab_runtime',operation,'--base',str(BASE),'--config-root',str(BASE/'config')]
''')
    md('## Periksa import dan CUDA\nPemeriksaan ini menjalankan tensor/kernel sintetis kecil pada CuPy, Torch, dan ONNX Runtime CUDA. Tidak menjalankan Area/Traffic atau model inference. Provider CUDA harus benar-benar bekerja; tidak ada fallback CPU tersembunyi.')
    code("run_logged(command('verify'),'runtime-check',env=child_env())\n")
    md('## Autentikasi Google dan pemeriksaan akses\nDialog ini untuk akun Google pemilik pengujian. ADC dipakai proses terisolasi dan worker. Pemeriksaan mencakup metadata sumber, schema/izin tabel hasil, izin object GCS, serta query kecil. Keberhasilan write/publish/reopen nyata tetap diuji lewat job Area; IAM check bukan transaksi write.')
    code('''from google.colab import auth
auth.authenticate_user(project_id='locdeproject')
run_logged(command('preflight'),'cloud-preflight',env=child_env())
print('Akses awal diperiksa. Belum ada engine berjalan.')
''')
    md('## Jalankan UI — Area Coverage lebih dahulu\nBuka GRADIO_PUBLIC_URL yang tercetak. Isi identity/koordinat, pilih Area Coverage lalu Process. Tinjau tabel dan map di RESULT, kemudian Buka hasil BQ untuk job yang sama. Traffic/PPAC ditahan sampai pembacaan ulang terverifikasi. Startup UI mengulang pemeriksaan ringan tanpa instalasi.\n\nCell ini tetap berjalan selama UI digunakan. Interrupt untuk menutup server. Hentikan setelah job selesai bila ingin menyimpan hasil lengkap; interrupt saat job aktif dapat membatalkan worker. Log tersimpan di /content/location-intelligence-colab/server.log. Nama panggilan L4 tidak membuktikan performa, akurasi atau parity dengan T4.')
    code('''if 'SERVER' in globals() and SERVER.poll() is None:
    raise RuntimeError('Server masih aktif; hentikan dahulu.')
log_path=BASE/'server.log';stream=log_path.open('wb')
SERVER=subprocess.Popen(command('serve'),env=child_env(),stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
offset=0
try:
    while SERVER.poll() is None:
        with log_path.open('rb') as logs:
            logs.seek(offset);chunk=logs.read();offset=logs.tell()
        if chunk:print(chunk.decode('utf-8',errors='replace'),end='',flush=True)
        time.sleep(1)
    with log_path.open('rb') as logs:
        logs.seek(offset);print(logs.read().decode('utf-8',errors='replace'),end='')
    if SERVER.returncode:raise RuntimeError('Server berhenti; lihat pesan terakhir dan server.log. Jangan lanjut ke Traffic sebelum Area terverifikasi.')
except KeyboardInterrupt:
    print('Menghentikan server dan worker milik sesi aplikasi ini...')
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
''')
    md('## Unduh diagnosis setelah server dihentikan\nTombol Siapkan paket diagnosis Area juga tersedia di Gradio. Cell berikut tetap bisa diunduh bila setup gagal sebelum Python aplikasi tersedia. ZIP memuat tahap gagal dan tail log terbatas; jika Area pernah berjalan, laporan run terakhir juga disertakan. Tidak memuat file credential/source/video. Unduhan ini tidak menjalankan ulang engine.')
    script='''from pathlib import Path
import sys,json,zipfile
from traffic_location.integration.area_trace import latest_report
from traffic_location.integration.failure_details import safe
base=Path(sys.argv[1]);traces=sorted((base/'system/targets').glob('*/runs/*/area/area-trace.json'),key=lambda p:p.stat().st_mtime)
report=latest_report(traces[-1].parents[3]) if traces else {'status':'NO_AREA_RUN'}
def clean(v):
    if isinstance(v,str):return safe(v)
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,list):return [clean(x) for x in v]
    return v
with zipfile.ZipFile(base/'colab-diagnostics.zip','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('area-report.json',json.dumps(clean(report),indent=2))
    for name in ('gpu-allocation.json','colab-runtime-verified.json','colab-preflight.json','colab-startup-failure.json','setup-status.json'):
        path=base/name
        if path.is_file() and path.stat().st_size<131072:z.writestr(name,json.dumps(clean(json.loads(path.read_text())),indent=2))
print('DIAGNOSTIC_ZIP='+str(base/'colab-diagnostics.zip'))
'''
    code("""# This cell also works when setup failed before SCIENCE was assigned.
import zipfile,re
archive=BASE/'colab-diagnostics.zip'
exported=False
if 'SCIENCE' in globals() and Path(SCIENCE).is_file():
    result=subprocess.run([SCIENCE,'-c',"""+repr(script)+""",str(BASE)],env=child_env(),capture_output=True,text=True)
    exported=result.returncode==0
    if exported:print(result.stdout)
with zipfile.ZipFile(archive,'a' if exported else 'w',zipfile.ZIP_DEFLATED) as bundle:
    if not exported:bundle.writestr('status.txt','Setup/startup diagnosis only; Area report not available yet.')
    for name in ('setup-status.json','setup.log','runtime-check.log','cloud-preflight.log'):
        path=BASE/name
        if not path.is_file():continue
        with path.open('rb') as stream:
            stream.seek(max(0,path.stat().st_size-65536));text=stream.read().decode('utf-8',errors='replace')
        text=re.sub(r'-----BEGIN[^\\n]*PRIVATE KEY-----.*?-----END[^\\n]*PRIVATE KEY-----','[REDACTED_KEY]',text,flags=re.S)
        text=re.sub(r'(?i)(bearer\\s+)[A-Za-z0-9._~+/-]+',r'\\1[REDACTED]',text)
        text=re.sub(r'(?i)(private_key|access_token|refresh_token|authorization)["\\s:=]+[^\\n]+',r'\\1=[REDACTED]',text)
        bundle.writestr(name,text)
from google.colab import files
files.download(str(archive))
""")
    for i,c in enumerate(cells):c['id']='colab-l4-'+str(i)
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'accelerator':'GPU','colab':{'name':'15_colab_l4_area_first.ipynb','gpuType':'L4'},'kernelspec':{'name':'python3','display_name':'Python 3'},'language_info':{'name':'python'}},'cells':cells}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n');print('Prepared',output,output.stat().st_size)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--output',default='notebooks/active/15_colab_l4_area_first.ipynb');a=p.parse_args();build(a.wheel,a.output)
