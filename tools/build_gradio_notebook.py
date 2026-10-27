"""Build the self-contained Kaggle Gradio notebook from an exact source wheel."""
import argparse,base64,hashlib,io,json,zipfile
from pathlib import Path


def build(wheel,output,*,area_test=False):
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

Jalankan notebook dengan Internet dan GPU aktif. Aktifkan Secret **LocatioIntelligent** pada pengaturan notebook. Isi delapan slot video weekday/weekend × pagi/siang/sore/malam melalui Gradio. Dataset T7SL juga tersedia sebagai contoh.

Notebook menyiapkan aplikasi lalu mencetak **GRADIO_PUBLIC_URL**. Buka URL itu untuk mengisi lokasi/input bisnis, mengunggah video, meninjau geometri/hari/sesi setiap video, memeriksa kesiapan, dan menekan **Mulai proses**. Setup aplikasi tidak menjalankan engine. URL aktif selama sesi notebook/server berjalan. Hentikan cell terakhir untuk menutup UI.

Hasil job menggunakan GCS **aretfak-location-intelligence** dan BQ **locdeproject.location_intelligence**. Siapkan tabel sekali sesuai panduan CLOUD_STORAGE_SETUP.md; model/PBF tetap memakai sumber terpisah yang sudah ada. Folder job dibuat otomatis saat penyimpanan. Jika setup BQ sudah dilakukan, jalankan ulang SQL terbaru untuk menambahkan referensi peta (tanpa menghapus data). Panel hasil membuka tabel BQ dan peta Folium/Esri dari artefak GCS.

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
    if area_test:
        cells[0]['source']='# USER TEST — Area Coverage · kandidat 0.6.1rc1\n\nNotebook ini adalah kandidat lokal untuk pengujian owner. Tersedia pada branch pengujian fix/area-user-testing; belum dipublikasikan ke Kaggle atau dipromosikan ke branch konsolidasi, dan belum dianggap stabil. HOME/RESULT tetap tersedia; mode awal **Area Coverage**. Startup tidak menjalankan engine. Gunakan sesi baru dengan GPU, Internet, serta Secret **LocatioIntelligent** aktif. Jangan menempelkan isi credential ke notebook atau chat.\n\n## Langkah pengujian\n\n1. Run All, buka **GRADIO_PUBLIC_URL**, isi KDTK 4karakter dan Nama Toko, periksa Latitude/Longitude. Periode otomatis tanggal Jakarta. Default koordinat Sorong; sesuaikan jika lokasi berbeda.\n2. Pada Action, pastikan **Area Coverage**. Tidak perlu upload video atau menjalankan Traffic/PPAC. Klik pemeriksaan kesiapan, kemudian **Process**.\n3. Di RESULT, periksa status Area dan tabel alokasi, kompetitor/Indomaret, serta peta interaktif Folium/Esri. Coba pan/zoom dan layer. PPAC **NOT_RUN** pada Area-only adalah wajar.\n4. Catat job_id yang dihasilkan. Klik **Buka hasil BQ** untuk membaca kembali job yang sama dari penyimpanan; jangan hanya menilai hasil yang masih ada di RAM.\n5. Jika gagal, klik **Periksa penyebab kegagalan Area** lalu **Siapkan paket diagnosis Area**. Unduh ZIP, catat tahap/kode error dan job_id. Tidak perlu menjalankan Traffic untuk menyelidiki Area.\n6. Berikan hasil pengujian dan paket diagnosis. Push ke refactor/deployment-foundation serta pembaruan dokumen aktif menunggu hasil owner. CI lokal bukan bukti fresh Area Sorong atau IAM berhasil.\n\nOutput menggunakan gs://aretfak-location-intelligence dan dataset locdeproject.location_intelligence. Tabel harus sudah disiapkan; notebook tidak membuat atau menghapus tabel. Source model/PBF/reference tetap terpisah. Jejak tahapan disimpan lokal per run pada area/area-trace.json dan ikut manifest GCS bila publikasi berhasil. ZIP diagnosis memuat metadata error terbatas, bukan private key/video/source rows. Jika publikasi gagal, hasil dan diagnosis lokal tetap dapat diunduh pada sesi ini.\n\nSetelah selesai, interrupt cell server. Bila UI tidak bisa mengunduh ZIP, jalankan cell diagnosis terakhir lalu ambil file dari panel Files Kaggle. Jangan mematikan seluruh sesi sebelum menyimpan bukti.\n'
        cells[0]['source']=cells[0]['source'].replace('0.6.1rc1',wheel.name.split('-')[1])
        cells[1]['source']=cells[1]['source'].replace('/kaggle/working/gate2-gradio','/kaggle/working/gate2-area-user-test')
        cells[2]['source']=cells[2]['source'].replace('share=True)','share=True,default_mode="Area Coverage")')
        md('## Diagnosis setelah menghentikan server (opsional)\nCell ini hanya membaca jejak run Area terakhir pada workspace notebook ini. Tidak menjalankan engine atau menghubungi cloud.')
        code('''from traffic_location.integration.area_trace import export_report
from IPython.display import display,FileLink
traces=sorted((BASE/'system/targets').glob('*/runs/*/area/area-trace.json'),key=lambda p:p.stat().st_mtime)
if traces:
    workspace=traces[-1].parents[3]
    diagnostic=export_report(workspace,BASE/'diagnostics/area-diagnostics.zip')
    print('DIAGNOSTIC_ZIP='+str(diagnostic))
    display(FileLink(str(diagnostic)))
else:
    print('Belum ada run Area pada workspace ini. Catat pesan startup/validasi jika UI belum bisa menjalankan Area.')
''')
    for i,c in enumerate(cells):c['id']='gradio-'+str(i)
    n={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3'},'language_info':{'name':'python'}},'cells':cells}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(n,ensure_ascii=False,indent=1)+'\n')
    print('Prepared',output,Path(output).stat().st_size)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wheel',required=True)
    parser.add_argument('--output',default='notebooks/14_gate2_sorong_t7sl_gradio.ipynb')
    parser.add_argument('--area-test',action='store_true',help='Build owner-run Area-first test notebook, with diagnostic export instructions')
    args=parser.parse_args();build(args.wheel,args.output,area_test=args.area_test)
