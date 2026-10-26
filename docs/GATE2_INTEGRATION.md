<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Gate2 — integrasi aktif0.4.7rc1

`KaggleRuntime.execute` menjalankan Area dan Traffic secara independen, memakai `candidate_fp32`, lalu meneruskan hasil tervalidasi ke PPAC. `_scheduled_tasks` menyiapkan runtime/model sekali dan memakai `run_video_jobs`; GPUdialokasikan per child process lewat `CUDA_VISIBLE_DEVICES`. YOLO dan ReID di child sama-sama memakai local `cuda:0`. Satu GPU berarti antrean serial; dua GPU berarti maksimal dua video aktif. Tidak ada CPUfallback diam-diam.

Fresh inference -> measurement -> counting -> hasilengine -> validasi context/source/schema/frame -> PPAC. Setiap tahap punya artefak dan status; cache terikat kode, runtime, sumber serta profil eksekusi. Mengubah input bisnis PPAC tidak perlu menjalankan ulang engine yang hasilnya masih cocok.

Notebook workflow terbaru: [Sorong+T7SL](https://www.kaggle.com/code/chrisbiran/gate2-t7sl-sorong-integration-quiz), source [notebook11](../notebooks/11_gate2_t7sl_sorong_quiz.ipynb), exact wheel0.4.7rc1 + SHA dan verifikasi source. Setup/engineOFF saat disimpan. Notebook13 dua-konfigurasi adalah benchmark terpisah, bukan workflowArea+Traffic+PPAC.

Policy aktif notebook ialah MVPv2: durasi300–306detik, tidak memerlukan sepeda/lookup, PARTIAL boleh dengan label dan validasi; jam>15 tetap butuh sesi tambahan. Status GCS NOT_CHECKED/NOT_FOUND/ACCESS_DENIED/ERROR/READY dibedakan. READYmetadata belum berarti runtime/model atau checksum isi sudah siap. Tidak mengklaim akses GCS live sudah diuji di sesi pengembangan ini.

Baseline714,84s dan kandidat477,79s pada satu video; total133 sama tetapi kesetaraantrack gagal. Owner mengizinkan adoption kandidat; gate integrasi memvalidasi kompatibilitas input, tidak membuktikan akurasi identitas kendaraan. [Rincian bukti dan batas](TRAFFIC_CANDIDATE_GPU_RUNTIME.md).

## Riwayat rilis dan Gate v1 — bukan konfigurasi default saat ini

# Koreksi sumber model Traffic —0.4.3rc1

Owner menetapkan kedua sumber GCS berikut:

- `gs://feeder-location-intelligent/models/traffic/detector/401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7/yolo26m.pt`
- `gs://feeder-location-intelligent/models/traffic/reid/8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb/yolo26n-reid.onnx`

`traffic/adapters/model_sources.py` menjadi sumber alamat bersama. Pemeriksaan
readiness, staging download dan cache upload Kaggle memakai helper yang sama;
prefix `sources/models/` tidak dipakai lagi pada jalur ini. SHA/model/counting
policy tidak berubah. Notebook memuat wheel0.4.3rc1 dengan SHA baru; force install
serta verifikasi source tetap aktif. Pengujian menggunakan mock transport dan
mencocokkan URI persis; tidak mengklaim akses GCS live telah diuji di luar akun
Kaggle owner, dan tidak menjalankan inferensi video.

---

# Update jalur uji nyata Sorong + T7SL —0.4.2rc1

Notebook Kaggle memakai bootstrap exact wheel+SHA, --force-reinstall, purge modul
lama dan verifikasi seluruh source package terhadap wheel. File wheel0.4.0/0.4.1
lama boleh tetap di cache, tetapi tidak dipilih lewat glob. Restart session Kaggle
untuk membuka notebook revisi terbaru; set ENABLE_NOTEBOOK_SETUP=True lalu run
cell kuis. Pilih GPU dan aktifkan Secret LocatioIntelligent. Tombol Mulai uji
adalah satu-satunya pemicu engine; tidak ada sakelar runtime/model tambahan.

`integration/kaggle_runtime.py` menangani deployment/ingestion, bukan perhitungan
analitik. Pemeriksaan GCS memanggil metadata API sebelum menampilkan status:
NOT_CHECKED, NOT_FOUND, ACCESS_DENIED, ERROR, READY. READY metadata tidak berarti
SHA penuh sudah diperiksa; staging selalu memverifikasi generation+SHA.

Registry integration/gate2/runtime-manifest.json tidak diperlukan lagi. Area
Sorong dibangun dari PBF nasional GCS yang generation/SHA-nya sudah dipin engine,
kemudian BQ snapshot target-bound dengan budget query yang sudah ditetapkan.
BQ diperiksa sebelum download PBF besar. Projection Sorong dihitung EPSG:32752,
bukan32748 lokasi lama. Ingestion berjalan pada interpreter baru setelah setup
agar tidak memakai NumPy/GDAL/GEOS lama dari kernel notebook. SourceBundle data
baru dibekukan sebelum facade Area dipanggil. Cache input baru dicoba ke GCS
content-addressed tanpa overwrite; read-only IAM boleh mempertahankan cache lokal.

Model diambil dari object GCS deterministik berdasarkan SHA. Bila API memastikan
object NOT_FOUND, bobot resmi Ultralytics versi terkunci diunduh, SHA diperiksa,
dan cache GCS dicoba. Akses GCS ditolak tidak dianggap object kosong dan tidak
memicu unduhan alternatif diam-diam. Ini bootstrap sumber bobot sama, bukan
penggantian model. Runtime ilmiah Area/GDAL serta Traffic/ReID otomatis disiapkan
pada mode terkait, tanpa fallback CPU.

Area dan setiap video T7SL diisolasi; failure dicatat ke progress.json dan hasil
berikut tetap diproses. Summary menampilkan hasil engine sukses meskipun PPAC
BLOCKED. PPAC tidak menggunakan false-zero untuk engine/video yang gagal.
Sesuai jawaban owner, rumus jam>15 tetap memerlukan sesi tambahan: delapan video
normal tidak otomatis diekstrapolasi menjadi18jam. Uji Area/Traffic tetap berjalan;
PPAC dapat diuji sampai hasil dengan <=15jam bila input lainnya valid.

Bukti: pengujian fault-injection storage/permission/hash/cache/independent jobs,
static notebook execution-OFF dan exact embedded-wheel, installed wheel dari
/tmp. Tidak ada claim akses cloud, coverage PBF Sorong, izin BQ/GCS, atau GPU
nyata telah diuji pada akun Kaggle owner. Notebook dipublikasikan dengan CPU
preparation-OFF; lokasi/video nyata belum dijalankan dalam persiapan ini.

---

# Update MVP v2 — keputusan owner

Aktif pada notebook Kaggle versi3, package0.4.1rc1, schema `ppac_parameters_mvp_v2`.

- Observasi300–306detik diterima sebagai sekitar5menit, count dipakai apa adanya,
  tanpa penskalaan. Seluruh durasi retained T7SL berada dalam rentang ini.
- Sepeda tidak diperlukan/dihitung. Kategori aktif motor/mobil/angkutan_umum/pejalan_kaki.
- Area/Traffic PARTIAL boleh dipakai; status dan summary asli ikut output PPAC.
  Pending/invalid tetap tidak masuk accepted count. Sumber frame/video gagal,
  target berbeda, checksum rusak atau slot yang tidak punya hasil tetap ditolak.
- Lookup AC17/AK30 dan AE18 tidak dipakai untuk MVP. Faktor Residential dan balance
  =1 sebagai penghilangan pengali lookup, bukan hasil Excel atau kalibrasi bisnis.
  Kedua parameter dihapus dari kuis dan schema v2.
- Contoh fixture yang dahulu241 pada parameter v1 menjadi272 pada MVP v2 karena
  pengali lookup dihapus. Ini angka sintetis software, bukan STD Sorong nyata.
- Sumber GCS Sorong/model/registry tetap perlu disiapkan sistem; belum terverifikasi
  tersedia. Perubahan policy ini tidak membuktikan data tersebut tersedia.

Validasi:165tes total,156PASS,9SKIP runtime opsional. Kernel lokasi/video nyata
belum dijalankan. Dokumen v1 di bawah dipertahankan sebagai referensi historis.

# Gate 2 — workflow headless dan PPAC modular

Implementasi 0.4.0rc1. Source Area/Traffic, model, threshold dan hasil historis
utuh. Local workflow tersedia; bukan deployment, integrasi GCS baru atau bukti
akurasi. Tidak ada UI dalam Gate 2.

## Boundary

- `integration/contracts.py`: schema JSON v1, refs dan error code.
- `integration/adapters.py`: facade run/reuse, manifest/SHA dan native reconciliation.
- `integration/gate.py`: kecocokan target/source/revision/slot/kategori/coverage;
  hanya adaptasi fitur, tidak menghitung routing/counting atau formula bisnis.
- `integration/workflow.py`: sequential jobs, independent failure, PPAC admission,
  immutable receipts, POSIX advisory lock, retry/reopen.
- `ppac/residential.py`: bangunan dialokasikan ke calon toko x4; 40/60 bila zona
  luar CLOSED, 35/45/20 bila OPEN. Pengali jarak 1/.5/.25, formula hari/pembulatan
  mengikuti referensi. Gate Area menentukan zona; tidak dievaluasi ulang di PPAC.
- `ppac/fasum.py`: per baris fasilitas yang tersedia di evidence gate Area,
  jarak <=400m +2, >400..800m +1, di luar itu +0. Tidak menambah filter jenis atau
  deduplikasi bisnis, mengikuti penyederhanaan owner.
- `ppac/_reference.py`, `konstatna.py`: Traffic, koefisien jalan, pembulatan dan
  agregasi owner dipertahankan. Fungsi Residential/Fasum historis hanya menjadi
  referensi, service memakai policy baru di atas.
- `ppac/service.py`: facade `calculate(features, parameters)`; tidak mengimpor
  integration/Area/Traffic. Output STD/hari, bukan APC/SPD/sales.

Source PPAC dipin ke commit `ba8eb090deb757759d80a0dde3bcc7f3ff9954d8` pada
`unChris666/traffic-vehicle-counter-IDM-LOC/counter-ppac`. Manifest provenance
berisi SHA sumber dan copy package; perubahan reference hanya relative import.
`README_PPAC.md` di package adalah dokumen referensi lama, pembagian 30/50/20
serta formula Fasum di sana disupersede oleh policy integration MVP di atas.

## Keputusan dan batas MVP

Combined coefficient AC17-AK30 dan balance multiplier AE18 tetap input wajib
beserta provenance. Tidak dipilihkan 1.5, .5 atau .6 sebagai default. Penelusuran
lookup Excel belum selesai; workflow BLOCKED bila parameter belum ada. Mapping
OSM yang direkomendasikan belum di-hardcode; parameter menerima profil PPAC
highway/mainstreet/street/substreet secara eksplisit.

MVP mengonsumsi accepted measured+estimated, kedua arah, dalam satu branch;
ledger pending/invalid tidak menjadi accepted. Machine/reviewed tidak dijumlah.
Mapping kategori adalah konfigurasi request, bukan form keputusan tambahan.
Tidak mengarang truck sebagai angkutan umum atau sepeda0. Observasi kategori
pelengkap dapat diberikan eksplisit beserta referensi bukti; tidak menimpa
hasil engine. Seluruh kategori PPAC dan slot wajib tersedia sebelum kalkulasi.

Tidak ada crop/normalisasi durasi; binding yang tidak menyatakan 300detik ditolak,
karena PPAC referensi mengasumsikan pencacahan5menit. Binding context, waktu dan
cakupan kategori adalah pernyataan pemanggil dengan referensi bukti, bukan hasil
verifikasi GPS/PTS otomatis. Manifest SHA memverifikasi paket, bukan kebenaran
semantik referensi tersebut. Today adalah periode analisis, bukan bukti rekaman.

Gate v1 konservatif: Area status kualitas SUCCEEDED, market input lengkap dan
UNVERIFIED=0; Traffic COMPLETE_WITHIN_DECLARED_SCOPE, frame utuh dan pending=0.
Eksekusi engine PARTIAL tetap boleh sukses secara mandiri; tidak dipromosikan
menjadi PPAC-ready. Baseline aktual masih PARTIAL. Dukungan partial yang hanya
mengenai fitur tidak dipakai memerlukan kontrak feature-scoped completeness
terpisah; belum ada bukti untuk melonggarkan gate secara otomatis.

## Menjalankan

```bash
python -m pip install .
engine-workflow traffic --request examples/gate2/traffic-smoke.json --root . --output /tmp/gate2-traffic-r1
engine-workflow area --request workflow.json --root . --output /tmp/gate2-area-r1
engine-workflow run --request workflow.json --root . --output /tmp/gate2-all-r1
engine-workflow ppac --request reuse-workflow.json --root . --output /tmp/gate2-ppac-r1
engine-workflow reopen --output /tmp/gate2-all-r1
```

Source-only: `PYTHONPATH=src python -B -m traffic_location.integration ...`.
`area` dan `traffic` tidak memanggil PPAC. `run` menjalankan/reuse job berurutan
lalu PPAC jika diminta. `ppac` hanya menerima reuse hasil finalized, tidak dapat
memicu inference. Counting facade menggunakan measurement yang telah disiapkan;
fresh detector/tracker/ReID tetap operasi engine terpisah, tidak dipicu otomatis.
Area facade mendukung replay_recorded/compute_gpu_frozen/compute_gpu_sources
pada runtime yang diperlukan. Instalasi wheel tidak memasang GPU/model/OS data.

Exit: 0 SUCCEEDED, 1 FAILED, 2 BLOCKED. JSON stdout mencantumkan status per job
serta PPAC; diagnostics mempunyai code dan message. STD total null pada failure
atau block. Engine lain tetap dijalankan bila satu gagal. Output engine sukses
tersimpan terpisah dan dapat di-reuse pada revision berikutnya.

Layout output: `engines/<id>/` untuk job run, `receipt/{result,identity,manifest}.json`
untuk hasil workflow. Retry request/root/kode/operasi sama memverifikasi sumber
referensi dan hasil tersimpan tanpa menghitung ulang. Perubahan atau recovery
receipt FAILED/BLOCKED memakai revision output baru. Reopen memverifikasi
receipt tanpa sumber/model/GPU. Storage local, lock POSIX single-host.

## Kontrak request

Contoh struktur; placeholder SHA harus diganti SHA aktual:

```json
{
  "schema_version": "gate2_workflow_v1",
  "jobs": [
    {"id":"area", "engine":"area", "action":"run",
     "request_ref":{"path":"area-request.json","sha256":"<SHA aktual>"}, "root":"."},
    {"id":"weekday_pagi", "engine":"traffic", "action":"reuse",
     "result_ref":{"path":"/data/weekday-pagi-result","sha256":"<SHA manifest.json>"}}
  ],
  "ppac": {
    "binding_ref":{"path":"binding.json","sha256":"<SHA aktual>"},
    "parameters_ref":{"path":"parameters.json","sha256":"<SHA aktual>"}
  }
}
```

PPAC memerlukan satu Area dan seluruh slot Traffic. `ppac:null` menjalankan
engine-only. Ref konfigurasi null menyatakan belum tersedia dan memblok PPAC.
Seluruh ref relatif mengikuti `--root`; job run.root adalah input-root engine,
juga relatif terhadap --root. Result ref mengikat SHA manifest, bukan SHA result.
Unknown schema/field/job ID unsafe/duplicate ditolak.

`binding.json` schema `gate2_binding_v1`:

- context: target_id, period_id, latitude, longitude, evidence (referensi bukti
  binding yang dapat diperiksa operator; tidak diklaim diverifikasi otomatis).
- area: job_id, result_version.
- traffic: list job_id, result_version, video_sha256, target_id, period_id, day
  weekday/weekend, session pagi/siang/sore/malam, observed_seconds,
  observed_categories (nama kategori Counter), evidence.
- category_mapping: kategori Counter ke motor/mobil/angkutan_umum/sepeda/
  pejalan_kaki, atau null untuk eksklusi eksplisit. Tidak ada mapping tersembunyi.
- supplemental: list day, session, category PPAC, count integer>=0 dan evidence;
  mengikuti context/periode/slot observasi di binding. [] tidak berarti kategori0.

Result version wajib exact untuk reuse; null diizinkan hanya untuk action=run
agar versi baru diikat setelah engine selesai. Expected video SHA tetap cocok;
lineage hasil PPAC menyimpan result version aktual. Satu video/result tidak
boleh mengisi dua slot. Tiap job harus dipilih eksplisit dalam binding.

`parameters.json` schema `ppac_parameters_v1`, seluruh field wajib:

```text
residential: combined_coefficient, operating_days_per_week, swot_factor
traffic: road_type, operating_hours, balance_multiplier, drive_thru
aggregation: traffic_cut_factor, parking_factor
provenance: sumber nilai parameter (teks non-kosong)
```

Tidak ada nilai netral otomatis. Untuk >15jam, sesi tengah_malam/dini_hari/subuh
juga diperlukan per kelompok hari. Tidak mengisi slot yang hilang dengan nol.

## Bukti

Tests meliputi simulasi sintetis 1.000 bangunan: Residential125, Traffic150,
Fasum8, potongan.9/parkir.8, total241; bukan STD lokasi nyata. Alur penolakan
mencakup partial/missing/tamper/context/source/branch/frame/duration/category,
shift3, lookup wajib, duplicate, lock, revision conflict, failure isolation,
serta retry tanpa kalkulasi. Delapan tes referensi PPAC tetap dipertahankan.

Smoke aktual menjalankan retained Area replay36.536baris dan Traffic counting
replay measurement CPU32frame. Bukan fresh GPU atau inferensi baru. Retry/reopen
lulus; PPAC tanpa parameter BLOCKED. Kelulusan teknis Gate2 tidak menyatakan
input pilot sudah lengkap atau bisnis/akurasi/produksi tervalidasi.
