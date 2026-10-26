<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Sumber nasional GCS dan deployment bertahap

25 Oktober2026 (Asia/Jakarta). Bucket owner: gs://feeder-location-intelligent,
us-central1, Standard/private/uniform/PAP. Owner melaporkan tes Kaggle CRUD PASS
dengan SHA25651b899b63af0b2ecc18639340fcafddfe7200d2c322d785cc1d5c86b1979e2b4.
Ini bukti dari owner untuk identitas Kaggle, bukan ADC Codex atau ingest nasional.

## Arahan terbaru

- Sumber geospasial seluruh Indonesia disimpan; lokasi baru dibaca dari indeks
  lokal/GCS tanpa Overpass saat engine berjalan.
- BigQuery DIPERBOLEHKAN live, menggantikan larangan sebelumnya pada dependency
  ini. Tidak wajib mirror seluruh tabel. Untuk mengulang hasil lama, pin hasil
  query per job (atau referensi snapshot/time-travel yang masih tersedia); query
  fresh menjadi revisi baru. Reliable availability tidak menjamin baris tetap sama.
- Model/video/config disimpan GCS; dependency instalasi dipindahkan ke build.
- Nasional adalah cakupan extract, bukan klaim data OSM lengkap di lapangan.

## Sumber dan prioritas

| Paket | Implementasi/pekerjaan | Gate |
|---|---|---|
| OSM nasional | PBF Geofabrik Indonesia; jalan, nodes, footprint, POI, tag yang dipetakan dapat diekstrak lokal | Header/date/provenance, completeness referensi, node/way/relation; indeks spasial; adapter mempertahankan filter/versi/topologi. Tidak semua fitur ada di OSM. |
| Model Traffic | Bobot detector dan ReID yang SHA-nya sudah terkunci | Hash dan GCS generation; bundel tracker/config serta uji no implicit download menyusul. |
| Basemap nasional | Vector basemap berlisensi, misalnya paket PMTiles/self-hosted tile service; frontend JS/CSS/ikon lokal | Pilih dan ukur rentang zoom/style/atribusi; jangan menyalin semua raster tile publik OSM. Tetap butuh kesesuaian source date dengan analitik. |
| Overture nasional | Ekstraksi release+schema tertentu ke GeoParquet berpartisi, terpisah dari OSM | Verifikasi katalog/release aktual, batas Indonesia dan checksum. Tetap jalur referensi, tidak otomatis mengganti footprint OSM. Persiapan dapat paralel dengan deployment awal. |
| Video Traffic | Input asli dipindah dari Kaggle/milik user ke GCS | Hash ukuran/frame metadata; jangan menganggap video di workspace mewakili seluruh dataset. |
| Runtime | Dua engine terpisah, base CUDA compatible, dependencies lock/image digest | Tidak pip/apt pada startup; local staging; hasil dan manifest GCS; tes CPU/GPU dan reopen. |

Pemeriksaan HTTP aktual: URL
https://download.geofabrik.de/asia/indonesia-latest.osm.pbf mengembalikan200,
Content-Length1739881462byte (sekitar1,74GB desimal), Last-Modified24Okt2026
23:00:01GMT. Halaman Indonesia dan sidecar.md5 juga200. Ini bukan bukti
download/upload/checksum PBF sudah selesai. Alias latest dapat berubah: notebook
memverifikasi provider MD5 dan menolak publikasi jika berbeda; objek GCS memakai
SHA256 sebagai identitas immutable. Timestamp PBF harus dibaca sesudah ingest.

## Notebook ingestion siap direview

`notebooks/indonesia_gcs_source_ingestion.ipynb`, dibangun oleh
`tools/build_national_ingestion_notebook.py`. CPU/Internet, Secret
LocatioIntelligent harus diaktifkan di notebook BARU. Tidak otomatis mewarisi
izin Secret notebook Area. Tidak menjalankan routing/counting/inference/BQ.

Notebook mengunduh PBF Indonesia dan dua model, memverifikasi MD5/SHA256,
mengunggah objek content-addressed memakai generation0 dan CRC32C, lalu
memeriksa ukuran/MD5/metadata SHA remote. Manifest RAW_ASSETS_UPLOADED ditulis
setelah objek selesai. Bukan manifest engine siap produksi; langkah yang belum
selesai dicatat. Cakupan file/header/indeks/adaptor belum dipalsukan sebagai PASS.

Keterbatasan saat ini: belum dieksekusi untuk ingest nyata, ADC Codex unavailable,
Overture nasional/basemap/video/container belum dibuat. Uji lokal helper memakai
stub storage adalah software checks, bukan bukti CRUD GCS nasional. Container
tidak perlu menunggu Overture referensi untuk tes rilis OSM, tetapi dependency
basemap/JS harus dipenuhi sebelum mengklaim UI bebas provider eksternal.

## Urutan menuju container

1. Jalankan ingestion CPU dan verifikasi objek nasional/model GCS.
2. Buat partisi/index nasional sekali. Setiap job hanya mengekstrak cakupan lokal
   yang dibutuhkan (termasuk buffer jaringan), bukan memproses Indonesia utuh.
3. Validasi adapter PBF terhadap snapshot acuan yang sama: pemilihan jalan,
   topologi, node refs, footprint/POI, connector/status/rute dan agregat. Jika
   tanggal/sumber berbeda, itu eksperimen sumber baru, bukan uji exact parity.
4. Adapter GCS staging/hash dan BQ result pinning; bekukan job fingerprint.
5. Basemap/aset frontend sendiri dan image kedua engine; konfigurasi di luar image,
   secrets runtime, raw/video/snapshot tidak ditanam ke image.
6. Smoke container untuk dua engine, API provider diblok kecuali GCS dan BQ yang
   disetujui; uji gagal input, pengulangan, isolasi job, persistent result.

Prioritas Pareto: PBF+indeks menghapus dependency Overpass per lokasi; model
bundle menghapus unduhan inferensi; build image menghapus instalasi startup.
Menyimpan raster semua zoom atau menunggu seluruh baseline legacy selesai
tidak menjadi syarat teknis smoke container pertama. Tidak ada klaim production
ready atau tanggal penyelesaian yang belum didukung tes.
