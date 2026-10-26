<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Audit dependency eksternal dan transisi GCS

25 Oktober 2026, Asia/Jakarta. Audit kode, bukan bukti bucket sudah tersedia.

## Keputusan arsitektur owner

Perhitungan kedua engine memakai input lokal yang sudah diverifikasi. Transfer
input/output melalui GCS dikerjakan storage adapter sebelum/sesudah engine.
API provider hanya boleh dipanggil pekerjaan ingestion terpisah, bukan saat
routing/counting. GCS sendiri memakai API HTTPS; sasaran ini menghilangkan
dependency provider live selama perhitungan, bukan menghilangkan transport GCS.
Tidak ada fallback otomatis ke provider ketika snapshot/model hilang.

Ini requirement baru; notebook saat ini BELUM memenuhi seluruhnya.

## Inventori Area Coverage

| Dependency | Pemakaian sekarang / sumber kode | Target GCS dan gate |
|---|---|---|
| Jalan/node OSM | Overpass, `location_intelligent_li3_sources.py:build_queries/acquire_overpass`, `location_intelligent_market_runtime.py:acquire_market_network`; adapter retry GPU | Snapshot graph-source mentah, query/filter/bbox/date, seluruh tile/node, checksums. Source jalan wajib lengkap sebelum manifest finalized. Parameter jaringan notebook kini3km; jangan mengecilkan lingkup diam-diam. |
| Footprint OSM | `location_intelligent_osm_buildings.py:acquire_osm` | Footprint mentah, metadata/tag dan versi, cakupan dan raw checksum. Radius mengikuti config market saat ini hingga2km beserta padding; minimum luas/seleksi tetap dihitung engine. |
| POI OSM | `location_intelligent_map_poi.py:load_osm_pois` | Snapshot POI2km; status missing/partial tetap eksplisit. Unduhan opsional; kegagalan tidak berarti tidak ada POI atau gate bisnis CLOSED. |
| Barrier/air/turn restrictions | `location_intelligent_network_acquisition.py` | Query terpisah hanya mode FULL. Default ROADS_ONLY_EXPERIMENT melewatinya, dengan batas bukti tetap dilaporkan; jangan menambahnya sebagai requirement wajib baru. |
| Kompetitor | BigQuery `locdeproject.DWH_NS_LOC.COMPETITOR`, `location_intelligent_map_pilot.py:load_bq_layers` | Export versioned, schema/query/as-of/checksum, koordinat invalid dan row accounting. Radius sumber2km, seleksi kompetitor<=800m tetap kebijakan engine. |
| Indomaret | BigQuery `locdeproject.DWH_NS_LOC.AREA_COVERAGE` | Export versioned seperti kompetitor. Nama/koordinat/atribut unavailable tetap unknown; jangan mengarang lebar toko. |
| Overture (legacy/reference) | STAC HTTP + object S3, `location_intelligent_map_pilot.py:acquire_buildings`, `location_intelligent_overture_probe.py` | Simpan hanya bila menjalankan baseline Overture. Bukan dependency jalur OSM aktif; jangan mengganti sumber snapshot lama. |
| Basemap | Folium `tiles='OpenStreetMap'`, `location_intelligent_market_map.py` | Peta hasil masih bergantung tile live. Sediakan vector/raster tile berlisensi yang dilayani sendiri, dibatasi coverage/zoom. Jangan bulk-download tile publik OSM sebagai solusi cache. |
| JS/CSS/ikon | Folium, Leaflet, plugin Fullscreen/MarkerCluster dan CDN yang dirujuk HTML | Paket aset frontend versi terkunci, dilayani sendiri. Periksa HTML dan request browser sebelum mengklaim peta offline. |
| CRS/geometri | PyProj/GDAL, CRS EPSG:32748 saat ini | Bundle database PROJ/grid yang diperlukan; PROJ_NETWORK=OFF. CRS lain perlu audit tersendiri. |

Raw source dan hasil normalisasi berbeda. Graph/konektor/rute/Huff adalah hasil
turunan, bukan kebutuhan API baru. Snapshot regional harus mencakup extent
permintaan aktual. Koordinat di luar cakupan menghasilkan SOURCE_NOT_AVAILABLE
dan memicu job ingestion terpisah; tidak dianggap coverage0.

## Inventori Traffic Counter

| Dependency | Fakta kode | Target |
|---|---|---|
| Video asli | Dataset Kaggle sekarang di-mount; worker membaca lokal | Upload GCS dengan SHA256/generation; stage lokal sebelum decode. Tidak memakai API analitik eksternal. |
| Detector YOLO26M | Cell model assets `10_t7sl_readable_resume.ipynb` mengambil GitHub Ultralytics Assets | Bobot berlisensi sesuai ketentuan di GCS, nama+SHA256+versi wajib. Tidak download otomatis saat inferensi. |
| Encoder ReID | Cell model assets yang sama mengunduh aset ReID | ONNX/bobot dan metadata versi/hash. ReID tetap bagian arsitektur; konfigurasi final/kualitas kendaraan masih terbuka. |
| Tracker/model config | Berkas dan Ultralytics lokal | YAML/config/label taxonomy terkunci bersama model bundle; periksa juga asset yang bisa diunduh framework secara implisit. |
| Measurement/replay | Cache detector/tracker, source context, review dan passage lokal | Bundle terpisah untuk fresh/machine/review-assisted/replay. Overlay tidak otomatis dicampur baseline. |
| Geometri/filter malam | JSON per video/config lokal | Revisi immutable; hash terikat job. Bukan API tambahan. |
| Hasil/anotasi | JSON/CSV/MP4 lokal, publikasi sebelumnya memakai Kaggle/GitHub | GCS results immutable + manifest. API Kaggle/GitHub adalah orchestration/publikasi, bukan algoritma counting. |

`src/traffic_location/traffic/inference_worker.py` mewajibkan aset eksternal lokal
yang terikat hash; kode tersebut tidak mengunduh bobot. Namun notebook setup dan
dependency framework belum diuji secara menyeluruh dengan egress diblok.

## Dependency build, terpisah dari data bisnis

pip/PyPI, apt/OS repositories, CUDA/CuPy/NVRTC, ONNX Runtime dan registry container
masih diperlukan pada setup tertentu. Pindahkan instalasi ke build image terkunci,
pin digest dan simpan wheels/binaries yang perlu. Container produksi tidak pip
install atau pull kode dari GitHub pada startup. Kaggle tetap lingkungan uji;
setup Kaggle yang membutuhkan internet tidak membuktikan engine butuh API data.

## Paket dan publikasi

Contoh layout yang diusulkan (bucket belum dibuat):

```text
sources/location/<snapshot_id>/osm/{roads,buildings,poi}/...
sources/location/<snapshot_id>/stores/{competitor,indomaret}/...
sources/location/<snapshot_id>/manifest.json
models/traffic/<bundle_id>/{detector,reid,tracker,manifest.json}
inputs/traffic/<video_sha256>/original.mp4
configs/<engine>/<revision>/...
results/<engine>/<job_fingerprint>/<revision>/...
web-assets/<version>/...
sandbox/<run_id>/...
```

Setiap manifest menyimpan object generation, ukuran, SHA256, schema, provenance,
as-of, coverage/bbox, filter/config/model/code versions, kelengkapan dan unknown.
Publikasikan manifest terakhir setelah seluruh objek wajib diverifikasi.
Gunakan if_generation_match=0 pada objek immutable; latest pointer memakai CAS.
Dataset yang gagal tile3 belum boleh dipublikasikan sebagai snapshot siap pakai.
Stabilitas berarti sumber+config+code/model+backend sama; GCS saja tidak menjamin
determinisme inferensi. Fresh inference masih memerlukan pengujian tersendiri.

## Kesiapan GCS dan langkah berikutnya

FAKTA: provider GCS dipilih owner. Project BigQuery sekarang locdeproject.
Pemeriksaan ADC Codex25Okt2026 gagal DefaultCredentialsError; manifest identity
tidak memiliki koneksi GCP. Bucket/IAM/CRUD belum diverifikasi. Secret
LocatioIntelligent di Kaggle tidak otomatis tersedia untuk Codex dan izin BQ
tidak otomatis memberi izin Storage.

Owner memilih biaya lebih rendah dan menyebut us-central-1. Region GCP yang
dipakai dalam rencana adalah Iowa `us-central1`, project locdeproject, Standard,
private, uniform bucket access, public access prevention. Ini bukan bukti
perbandingan harga termurah; transfer ke Kaggle/runtime GPU juga perlu dihitung.
Nama bucket global harus diperiksa ketika dibuat.

Urutan kerja:

1. Tetapkan project/region dan verifikasi billing/admin identity. Siapkan bucket
   privat. Pisahkan hak provisioner dari ingestion writer dan compute reader.
2. Uji CRUD pada sandbox saja, dengan generation preconditions, CRC32C dan
   SHA256. Retention/soft-delete/lifecycle ditetapkan dengan biaya yang terlihat.
3. Siapkan snapshot lokasi LENGKAP melalui ingestion CPU dan export BQ. Tidak
   menyamakan keberhasilan bucket dengan keberhasilan ekstraksi OSM.
4. Upload model/config/video Traffic serta sumber Location. Verifikasi manifest.
5. Tambahkan adapter GCS->local terverifikasi ke notebook. Area memakai
   SOURCE_MODE=FROZEN dan BQ_MODE=FROZEN; model notebook Traffic memakai local
   files. Implementasi adapter ini belum dilakukan pada audit ini.
6. Jalankan engine dengan egress provider diblok. Uji missing/corrupt input,
   snapshot di luar coverage, reopen, retry, hasil map/table/export konsisten.
7. Pisahkan image/worker Traffic dan Location; jalankan berurutan pada GPU.
   GCS menjadi penyimpanan permanen; metadata/job DB tetap komponen terpisah.

Di Cloud Shell project yang benar: Cloud Storage -> Buckets -> Create. Pilih
region yang disepakati, Standard, uniform access, enforce public access
prevention. Periksa pilihan soft-delete/lifecycle dan biayanya sebelum Create.
Tambahkan service account Kaggle sebagai Storage Object Viewer pada bucket
input; writer hasil sebaiknya dibatasi bucket/prefix hasil. Gunakan role admin
provisioning hanya untuk penyiapan, bukan notebook harian. Kredensial/key tetap
di Secret, tidak pernah ke repo/chat. Produksi memakai attached service account
atau Workload Identity. Akses project/IAM tidak diasumsikan dari email akun.

Alternatif Cloud Shell: `BUCKET_NAME=<nama-global-baru> bash tools/setup_engine_gcs.sh`.
Script default project locdeproject / region us-central1, membuat bucket BARU
private dan uji CRUD satu objek sandbox. Bucket tetap ada setelah tes;
soft-deleted test object mungkin masih tersimpan sesuai kebijakan recovery.
Syntax script sudah diperiksa; eksekusi GCS/IAM aktual belum diuji.
Tes ini memakai identitas Cloud Shell; belum membuktikan akses service account
Kaggle. Setelah bucket siap, set Storage Object Viewer untuk identitas Kaggle
pada bucket input, lalu verifikasi akses baca dengan credential Secret yang
sudah ada tanpa menampilkan nilai key. Akses tulis results memerlukan binding
terbatas yang diuji terpisah. Jangan menaruh JSON key pada dataset Kaggle.

Gate selesai: bucket nyata+izin benar, CRUD teruji, paket input lengkap,
stage/download hash tervalidasi, engine tanpa akses provider live, test
reproducibility dan keluaran persisten. Saat ini gate tersebut masih OPEN.
