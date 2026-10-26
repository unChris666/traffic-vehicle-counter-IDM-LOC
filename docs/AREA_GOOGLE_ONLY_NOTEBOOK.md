<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Area notebook: input Google Cloud saja

> Superseded untuk notebook development: [GCS/BQ + setup Kaggle + Esri](AREA_ESRI_GCS_DEVELOPMENT.md).
> PMTiles/runtime GCS bukan prasyarat run Area saat ini. Isi berikut disimpan sebagai riwayat.


Update basemap: [persiapan nasional](NATIONAL_BASEMAP_PREPARATION.md) menggantikan
mode background kosong di versi awal yang didokumentasikan di bawah. Run All
persiapan kini mencakup PMTiles nasional, dan Area mensyaratkan referensi basemap
READY sebelum berjalan. Arsip nasional belum dibangun oleh Codex; fixture kecil
sudah diuji dengan Java/Planetiler nyata.

25 Oktober2026, Asia/Jakarta. Notebook tujuan tetap
https://www.kaggle.com/code/chrisbiran/area-coverage-market-gpu-hybrid/edit.

## Perubahan

- PBF sumber dikunci ke bucket feeder-location-intelligent, object SHA256
  bb1b60f7dfdbb1f19d33fa1ffb0c546f7e75928126ac3a2c004839a3ff2003bc,
  generation1792937275821365, bytes1739881462 berdasarkan receipt owner.
- Download memakai GCS generation, ukuran dan SHA256; local cache diverifikasi.
  Tidak ada fallback Overpass bila objek/hash/coverage tidak siap.
- Native `osmium extract --strategy smart` memotong wilayah lokal, kemudian
  adapter menjaga node refs/versi/tags, arah, building ring/hole dan POI ke
  kontrak raw yang sama. Date berasal header PBF; tanpa date proses diblok.
  Filter jalan tetap diperoleh dari OSMnx drive_service+motor supplements.
- FULL external-feature profile belum divalidasi; default ROADS_ONLY_EXPERIMENT
  tetap dipakai. Adapter menolak FULL agar tidak menganggap feature lengkap.
- Snapshot baru PBF_LOCAL_V1 terpisah dari snapshot Overpass lama. POI memakai
  center pada bounded smart extract dan normalizer/radius domain yang sama;
  ini profil sumber baru, bukan klaim exact parity inventory Overpass terdahulu.
  Tidak mengklaim seluruh POI/bangunan nyata sudah dipetakan.
- BigQuery tetap diizinkan. Credentials dibaca sekali dari Kaggle Secret saat
  bootstrap, dipakai ulang BQ/GCS; tidak membaca Secret lagi setelah HTTP guard.
- Guard requests/send/urllib/redirect menolak endpoint non-googleapis.com.
  Python subprocess pip memakai wheel lokal, --no-index --no-deps, tanpa apt.
  PROJ_NETWORK=OFF. Ini guard jalur HTTP aplikasi, bukan firewall OS untuk
  seluruh kemungkinan library/native code; egress container tetap gate terpisah.
- Runtime/frontend berasal bundle GCS, SHA+inventory terikat environment OS,
  Python, dan retained scientific packages. Native worker memakai wrapper dari
  bundle; tidak mengubah helper domain CPU. GPU kandidat/intersection/routing
  tetap memakai kernel yang sama; facade runner hanya memilih Python wrapper.
- Frontend Folium/Leaflet/CSS/font/image di-inline dari bundle GCS. Background
  tile eksternal dimatikan. Peta analitik (jalan, bangunan, POI, toko dan radius)
  tetap tersedia; basemap nasional belum diunggah dan tidak diganti layanan lain.
  View manifest baru mencakup adapter/frontend agar reopen tidak merusak hash.

## Persiapan sekali sebelum Run All Area

PBF dan model sudah ada menurut receipt owner. Wheel/native/frontend bundle
BELUM dilaporkan ada. Karena PyPI/apt/CDN dilarang pada notebook Area, bundle
harus dibuat lewat job ingestion TERPISAH terlebih dahulu.

Notebook `notebooks/area_gcs_runtime_preparation.ipynb` adalah versi preparation
pada https://www.kaggle.com/code/chrisbiran/indonesia-gcs-source-ingestion-cpu/edit.
Aktifkan Secret LocatioIntelligent, pilih accelerator/image yang sama dengan
Area (T4x2), lalu Run All interaktif. Komputasi preparation tetap CPU; pemilihan
image GPU menjaga paket ilmiah kompatibel. Ia mengambil paket dari provider
hanya pada INGESTION ini dan mengunggah runtime/native/frontend ke GCS. Tidak
menjalankan engine/GPU, BQ, atau mengunduh PBF Indonesia lagi.
Jika CPU dan GPU image berbeda paket ilmiahnya, preparation perlu memakai image
yang cocok dengan Area; fingerprint yang berbeda tidak dipaksakan kompatibel.

Job preparation otomatis version3 sudah dicoba: berhenti saat Kaggle Secret
bootstrap dengan ConnectionError/HTTP400, sebelum mengunggah runtime. Ini bukan
penolakan izin bucket yang sudah dibuktikan CRUD owner. Nilai Secret tidak
dicetak/disalin; perlu eksekusi interaktif karena konteks otomatis belum dapat
membaca Secret. Seluruh pipeline nasional tidak dijalankan ulang untuk error itu.

Setelah preparation mencetak READY dengan URI runtime manifest, buka notebook
Area, GPU aktif, Internet aktif untuk GCS/BQ, Secret aktif, muat semua helper
baru lalu Run All. Jika runtime hilang, dependencies memberi
GCS_REQUIRED_OBJECT_MISSING dan downstream tetap BLOCKED tanpa hasil palsu.

## Pengujian dan batas

Tes lokal menggunakan PBF sintetis nyata (pyosmium4.3.2): header date, node/way/
relation, hole/multipolygon, POI, arah jalan, frozen reopen dan corruption.
Ekstraksi CLI di tes kontrol di-stub copy fixture; scan native PBF Indonesia
belum dieksekusi dan tidak diklaim lulus. GCS transport memakai stub pada tes;
receipt nasional adalah bukti owner, bukan download 1,74GB oleh Codex.
Suite lokal149 tes:134 lulus,15 skip. HTTP/redirect Google-only, wrong SHA, generation pinning, inline frontend,
view cache/tamper dan AST jalur eksekusi ikut diuji.

Perhitungan source baru harus direview setelah run aktual. Tidak ada angka
bangunan/rute/Huff atau performance baru yang dibuat. Snapshot lengkap tetap
mengandung manifest/provenance. Ekstraksi pertama masih scan CPU nasional;
local frozen cache dipakai ulang. Indeks geospasial nasional persisten masih
pekerjaan percepatan ingestion tersendiri, bukan yang sudah selesai di sini.
