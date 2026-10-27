"""Build the self-contained Kaggle Gradio notebook from an exact source wheel."""
import argparse,base64,hashlib,io,json,zipfile
from pathlib import Path


def build(wheel,output):
    root=Path(__file__).resolve().parents[1];wheel=Path(wheel).resolve()
    with zipfile.ZipFile(wheel) as package:
        for name in package.namelist():
            if name.startswith('traffic_location/') and name.endswith('.py'):
                assert (root/'src'/name).read_bytes()==package.read(name),name
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(wheel,'package/'+wheel.name)
        for p in sorted((root/'results/t7sl_modular/config').rglob('*.json')):
            z.write(p,'config/'+str(p.relative_to(root/'results/t7sl_modular/config')))
    payload=buf.getvalue();cells=[]
    def md(text):cells.append({'cell_type':'markdown','metadata':{},'source':text})
    def code(text):
        compile(text,'cell','exec')
        cells.append({'cell_type':'code','metadata':{},'source':text,'execution_count':None,'outputs':[]})
    md('''# Gradio — Area Coverage, Traffic Counter, PPAC

Jalankan notebook dengan Internet dan GPU aktif. Aktifkan Secret **LocatioIntelligent** pada pengaturan notebook. Upload video Anda melalui Gradio. Dataset T7SL juga tersedia sebagai contoh.

Notebook menyiapkan aplikasi lalu mencetak **GRADIO_PUBLIC_URL**. Buka URL itu untuk mengisi lokasi/input bisnis, mengunggah video, meninjau geometri/hari/sesi setiap video, memeriksa kesiapan, dan menekan **Mulai proses**. Setup aplikasi tidak menjalankan engine. URL aktif selama sesi notebook/server berjalan. Hentikan cell terakhir untuk menutup UI.

Hasil job menggunakan GCS **aretfak-location-intelligence** dan BQ **locdeproject.location_intelligence**. Siapkan tabel sekali sesuai panduan CLOUD_STORAGE_SETUP.md; model/PBF tetap memakai sumber terpisah yang sudah ada. Folder job dibuat otomatis saat penyimpanan.

Default lokasi Sorong: latitude -0.8994976613947719, longitude 131.3221639428227. Traffic menggunakan kandidat FP32 dan satu video per GPU; akurasi identitas belum tervalidasi. Untuk PPAC dengan delapan video normal, gunakan jam operasional <=15. Operasional >15 jam tetap menunggu sesi tambahan.
''')
    code('''import base64,hashlib,io,zipfile,json,sys,subprocess,importlib,importlib.metadata
from pathlib import Path
BASE=Path('/kaggle/working/gate2-gradio');BASE.mkdir(parents=True,exist_ok=True)
PAYLOAD=base64.b64decode('''+repr(base64.b64encode(payload).decode())+''')
assert hashlib.sha256(PAYLOAD).hexdigest()=='''+repr(hashlib.sha256(payload).hexdigest())+'''
zipfile.ZipFile(io.BytesIO(PAYLOAD)).extractall(BASE)
WHEEL=BASE/'package'/'''+repr(wheel.name)+'''
assert hashlib.sha256(WHEEL.read_bytes()).hexdigest()=='''+repr(hashlib.sha256(wheel.read_bytes()).hexdigest())+'''
subprocess.run([sys.executable,'-m','pip','install','--no-deps','--force-reinstall',str(WHEEL)],check=True)
subprocess.run([sys.executable,'-m','pip','install','gradio==5.49.1','google-cloud-storage==3.6.0','google-cloud-bigquery==3.46.2','google-crc32c==1.7.1','jsonschema==4.26.0','numpy==2.1.3','pandas==2.3.3'],check=True)
for key in list(sys.modules):
    if key=='traffic_location' or key.startswith('traffic_location.'):del sys.modules[key]
importlib.invalidate_caches()
import traffic_location,gradio
assert gradio.__version__=='5.49.1','Restart sesi agar Gradio sesuai versi terpasang.'
package_root=Path(traffic_location.__file__).parent
with zipfile.ZipFile(WHEEL) as package:
    for name in package.namelist():
        if name.startswith('traffic_location/') and name.endswith('.py'):
            assert (package_root/Path(name).relative_to('traffic_location')).read_bytes()==package.read(name),name
print('Paket dan UI siap. Belum ada engine berjalan.')
''')
    code('''from traffic_location.integration.gradio_app import launch
if 'APP' in globals():
    APP.close()
APP, PUBLIC_URL=launch(BASE/'system',BASE/'config',share=True)
print('GRADIO_PUBLIC_URL='+PUBLIC_URL,flush=True)
print('Buka URL publik tersebut. Engine berjalan setelah tombol Mulai proses ditekan.',flush=True)
try:
    APP.block_thread()
finally:
    APP.close()
''')
    for i,c in enumerate(cells):c['id']='gradio-'+str(i)
    n={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3'},'language_info':{'name':'python'}},'cells':cells}
    Path(output).write_text(json.dumps(n,ensure_ascii=False,indent=1)+'\n')
    print('Prepared',output,Path(output).stat().st_size)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wheel',required=True)
    parser.add_argument('--output',default='notebooks/14_gate2_sorong_t7sl_gradio.ipynb')
    args=parser.parse_args();build(args.wheel,args.output)
