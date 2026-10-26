<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Review bangunan tetangga, penggunaan POI, dan alternatif toko

Tanggal: 24 Oktober 2026. Profil: eksperimen OSM CPU; baseline lama tetap utuh.

## Bukti dan batas kesimpulan

Owner melaporkan 2.575 bangunan terpilih, 739 accepted, 32 marker Indomaret dan
37 kompetitor. Angka ini bukan hasil eksekusi ulang independen dalam perubahan ini.

| ID dari owner | Status yang dilaporkan | Tag OSM publik saat diperiksa |
|---|---|---|
| way500294496 | ACCEPTED | building=yes |
| way500294495 | NO_ROUTE | building=yes |
| way500294493 | OVER_TIME_LIMIT | building=yes |

[Ringkasan sumber publik](evidence/area_coverage_neighbor_review/public_tag_check.json)
menyimpan URL resmi, versi dan timestamp masing-masing way. Tag generik tersebut
tidak membuktikan residential maupun penyebab perbedaan routing. Snapshot keputusan
aktual owner belum tersedia untuk diagnosis independen; tidak ada penyebab pasti
yang dinyatakan atau status yang dipaksa sama.

Jarak ke jalan <125 m hanya syarat pencarian kandidat. Arah ruas, izin, barrier,
larangan belok, posisi konektor dan jalur ke toko tetap diperiksa. Kedekatan dua
footprint tidak mengesahkan akses bersama. NO_ROUTE berbeda dari tidak ada
konektor; OVER_TIME_LIMIT memerlukan rute tersimpan dengan waktu melampaui aturan.

## Perubahan yang diterapkan

- Panel ringkasan besar dihapus; attribution peta tetap ada.
- Tooltip/popup bangunan: ID, AREA (m²), Status, Reason, Alternatif.
- Alternatif hanya dari input toko BQ dalam radius konfigurasi yang sudah dimuat.
  Graph alternatif terpisah memakai sumber motor yang sama dan tidak mengubah
  keputusan utama. Urutan: jarak perjalanan total → kelas jalan toko → frontage
  terlebar, dengan tie-break stabil. Akses bangunan tetap mengikuti kebijakan
  kelas tertinggi di antara kandidat valid. Keterjangkauan ini bersifat model,
  bukan bukti akses fisik atau market share.
- Lebar toko tanpa nilai dan referensi sumber tetap unknown. Identitas/lokasi
  toko konflik dikeluarkan dengan alasan; BQ gagal tidak menjadi daftar kosong
  seolah semua toko sudah diperiksa. Alternatif terikat checksum snapshot.
- Kebijakan sumber `osm_poi_use_v2` memeriksa tag penggunaan bangunan dan POI
  sebelum fallback residential: indikasi nonresidential eksplisit tidak otomatis
  dihitung residential; mixed-use/POI ambigu memerlukan review. POI dekat saja
  tidak dipindahkan ke bangunan tetangga. Tidak ada klaim inventori POI lengkap.
- `building=yes` tanpa penggunaan positif masih dapat memakai asumsi N1 yang
  diberi alasan eksplisit, bukan dianggap residential terverifikasi. Review
  mixed-use bukan bukti kapasitas atau demand nol.
- Baseline sumber lama tidak ditimpa. Refresh OSM dapat berbeda dari snapshot;
  gunakan FROZEN untuk replay pembanding yang dapat direproduksi.

## Cara membuka dan mengaudit di Kaggle

Notebook: [Area Coverage CPU](https://www.kaggle.com/code/chrisbiran/area-coverage-800m-poi-2km-cpu/edit).
Seluruh helper Python ditampilkan sebagai source cell, bukan bootstrap tersembunyi.

1. Muat notebook terbaru dan jalankan konfigurasi/dependency/helper untuk session
   baru. Pertahankan secret `LocatioIntelligent` aktif; jangan cetak key.
2. Jalankan alur snapshot, kalkulasi, BQ dan fasilitas. Untuk menerapkan klasifikasi
   POI baru, alur kalkulasi perlu dijalankan dengan kebijakan baru; render saja tidak
   mengubah kelayakan residential hasil lama.
3. Bagian **9 — Audit peta tanpa menghitung ulang** menggambar hasil yang sudah
   dimuat dengan tooltip ringkas. Alternatif belum diperiksa dinyatakan demikian.
4. Bagian **10 — Alternatif toko yang bisa dicapai** membangun graph alternatif
   terisolasi atau membuka cache identik; menampilkan tabel toko dan frontage.
5. Bagian **11 — Audit tiga kasus tetangga** memuat ketiga ID di atas, keputusan,
   kandidat terpilih, konektor, alasan penolakan dan jalur tersimpan. Layer audit
   menampilkan konektor biru, penolakan merah putus, dan rute ungu. JSON tersedia
   sebagai `OUTPUT/neighbor_building_review.json`; HTML melalui link pada cell.

ID yang tidak ditemukan tetap SOURCE_ID_NOT_FOUND; jangan memakai snapshot lain
sebagai penjelasan kasus owner. Hasil utama dan artefak audit dipisahkan.

## Validasi aktual

- Suite `area_coverage*tests.py`: 37 tes, 28 lulus dan 9 dilewati karena runtime
  venv tidak memiliki GDAL. Sembilan tes OSM tersebut dijalankan terpisah pada
  system Python dengan GDAL: semuanya lulus.
- Regresi mencakup arah/larangan belok, unknown permission, pemeringkatan,
  pemisahan graph, cache reopen, penolakan alternatif dari snapshot lain, lima
  field tooltip, POI-first dan bangunan tetangga yang tidak dilabeli sembarangan.
- Seluruh 58 cell notebook ter-parse; paket Kaggle identik dan tanpa output privat.
- Browser Chromium pada preview snapshot publik: peta interaktif dan toggle
  layer berfungsi, panel besar tidak muncul, tidak ada JavaScript/resource error.
  Preview ini bukan eksekusi BQ owner atau validasi rute ketiga ID.

Belum dijalankan: matrix alternatif seluruh toko aktual owner, jumlah baru akibat
kebijakan POI, dan diagnosis definitif ketiga rute owner. Publikasi source Kaggle
memakai QUICK_SAVE; tidak menyatakan full job terbaru sudah sukses.
