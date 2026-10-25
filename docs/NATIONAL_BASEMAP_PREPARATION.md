# Basemap nasional pada notebook persiapan

> Superseded untuk notebook development: [GCS/BQ + setup Kaggle + Esri](AREA_ESRI_GCS_DEVELOPMENT.md).
> PMTiles/runtime GCS bukan prasyarat run Area saat ini. Isi berikut disimpan sebagai riwayat.


25 Oktober2026, Asia/Jakarta. Owner meminta basemap nasional disertakan sebelum
menjalankan notebook persiapan. Ini menambah pekerjaan ingestion/display,
tanpa mengubah seleksi/routing/konektor/Huff atau Traffic counting.

## Yang kini dibuat oleh Run All

Notebook https://www.kaggle.com/code/chrisbiran/indonesia-gcs-source-ingestion-cpu/edit
mencakup runtime/wheel/native/frontend bundle DAN pembangunan PMTiles nasional.
Pilih image yang sama dengan Area/T4x2 dan aktifkan LocatioIntelligent. Komputasi
build vector menggunakan CPU; accelerator dipilih untuk kompatibilitas image.
Tidak mengunduh tile dari OSM/Google/Mapbox. PBF sumber berasal dari GCS,
generation1792937275821365 dan SHA256
bb1b60f7dfdbb1f19d33fa1ffb0c546f7e75928126ac3a2c004839a3ff2003bc.

Compiler Planetiler0.10.2 dikunci SHA256
f310bd0413e2e4512b27f4046d418664e8e1d3bf31603c2a70e23de06c167e4d;
source profile Java terlihat di cell national_basemap.py. JAR/compiler/frontend
diambil pada job INGESTION, bukan notebook Area. PBF yang sudah disimpan tidak
diganti download Geofabrik terbaru. Date/provenance berasal header PBF asli.

Profil dasar Indonesia OSM mencakup fitur yang dipetakan: roads, buildings,
water, waterways, landuse, places, POI, coastline dan administrative boundaries.
Arsip metadata mencatat layer yang benar-benar dihasilkan. Gate nasional
mewajibkan roads/buildings/water/coastline/places; layer lain mengikuti input.
Tidak mengklaim seluruh objek nyata sudah dipetakan. Bukan raster/citra satelit,
bukan style resmi Google. Label nama fitur tersedia melalui popup; profil ini
belum menyamai label-placement/rendering lengkap aplikasi peta komersial.

Default teknis eksperimen: native zoom0–14, overzoom klien sampai20. Overzoom
tidak menambah detail sumber. Bangunan dipertahankan pada native14, raw footprint
analitik tetap terpisah dari geometri vector tile yang terkuantisasi. Perhitungan
luas/coverage tidak pernah memakai tile tersebut.

## Storage dan commit

```text
basemaps/indonesia/indonesia-osm-basic-v1-z14/<archive_sha>/indonesia.pmtiles
basemaps/indonesia/indonesia-osm-basic-v1-z14/<pbf_sha>/manifest.json
runtime/area/<environment_fingerprint>/manifest.json
```

Manifest basemap berisi generation, ukuran, SHA256/CRC32C, PBF source generation/
hash, timestamp, compiler/profile hash, layer, bounds dan jumlah tile. Upload
conditional dan validasi dilakukan sebelum pointer READY. Runtime pointer baru
dipublikasikan setelah basemap READY dan membawa referensi arsip itu. Arsip
nasional yang sudah valid dipakai ulang pada run berikutnya. Pembuatan gagal,
input/hash berubah atau layer wajib hilang tidak menerbitkan READY baru.

Build pertama memerlukan download1,74GB dari GCS, scan PBF, intermediate disk,
sort dan upload arsip. Default JVM heap8GB, maksimum4threads, node mmap dan
compressed temp. Durasi/ukuran basemap Indonesia belum diukur. Tool memeriksa
resource, tetapi kapasitas Kaggle tidak dijamin cukup untuk semua perubahan
profil; build gagal harus dilaporkan, tidak dianggap basemap kosong.

## Pemakaian notebook Area

Runtime loader menuntut basemap READY terikat PBF yang sama. Python membaca
PMTiles melalui HTTPS Range GCS dengan generation dan Content-Range diverifikasi.
Tidak perlu public bucket, signed URL pada browser, atau CORS bucket: tile
wilayah tampilan sekitar calon toko di-inline ke HTML bersama JS/CSS/font.

Arsipnya nasional; HTML notebook membawa viewport lokal saja (radius analitik
ditambah1km untuk tampilan), bukan seluruh file nasional. Zoom memakai tile
native14 dengan overzoom; pan jauh di luar wilayah yang diekspor tidak otomatis
mengunduh tile lain. Lokasi analisis baru dapat mengambil tile baru dari arsip
GCS yang sama. Deployment backend tile service dapat melayani pan nasional,
pekerjaan itu belum diimplementasikan di sini.

Range HTTP gagal, response200 yang mengabaikan Range, generation/header/bounds
berbeda, atau arsip belum READY menyebabkan error eksplisit; tidak menjadi
tile kosong sukses. Tile yang memang tidak ada dalam arsip boleh kosong.
View manifest mengikat referensi archive/profile/frontend dan checksum HTML.
Statistik tile/read GCS disimpan dalam basemap_view.json, terpisah dari agregat.

## Pengujian yang benar-benar dijalankan

Perbaikan25Oktober2026: driver memakai `shutil.rmtree` tanpa mengimpor
`shutil`; ini kesalahan kode, bukan konfigurasi owner. Error direproduksi dari
versi sebelumnya dan diperbaiki pada script serta cell notebook. Pemeriksaan
sebelumnya belum menjalankan driver persiapan sehingga defect ini lolos.

Gate sebelum publikasi kini: `python tools/check_area_preparation.py` dengan
environment development yang memuat Ruff dan dependency tes Area. Gate memeriksa
sinkronisasi notebook/script, syntax dan nama belum terdefinisi, lalu menjalankan
enam tes driver dari globals baru: cache kosong, reuse cache, cache rusak,
build gagal/partial, upload gagal dan dependency native gagal. Filesystem/hash/
arsip/manifest dieksekusi; pip/apt, HTTP, Secret, build basemap serta GCS memakai
fixture eksplisit. Basemap bukan READY ditolak sebelum publikasi runtime.
Suite Area keseluruhan:161tes,146lulus,15skip. Ini bukan bukti build nasional
atau upload GCS nyata berhasil; keduanya tetap memerlukan Run All interaktif.

- JAR0.10.2 diunduh dan SHA diverifikasi; Java21 menjalankan profile pada PBF
  sintetis nyata: menghasilkan5tile dengan roads/buildings/POI. Ini BUKAN
  pembangunan Indonesia penuh atau benchmark nasional.
- Header/metadata PMTiles dibaca dengan pmtiles3.8.1; range reader diuji memakai
  storage stub, termasuk pin generation, cache, range salah, input belum READY
  dan mismatch. Tidak diklaim sebagai akses GCS nyata oleh Codex.
- Frontend aktual diunduh untuk tes lokal, CSS font/image di-inline. Node memeriksa
  syntax seluruh7script HTML fixture dan PASS. Browser render belum tervalidasi:
  Chromium lingkungan ini timeout bahkan pada halaman HELLO statis.
- Bukti fixture/stats/validasi ada di results/area_coverage_map/basemap_validation.
  Belum ada hasil/upload PMTiles nasional; owner perlu Run All interaktif.

Tunggu dua penanda: `BASEMAP READY: gs://.../basemaps/.../manifest.json` dan
`READY: gs://.../runtime/area/.../manifest.json`. Setelah itu jalankan Area.
READY membuktikan paket selesai menurut gate artefak, bukan akurasi lapangan
atau kebenaran perhitungan bisnis.
