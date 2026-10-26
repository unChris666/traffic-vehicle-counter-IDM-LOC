<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Konektor batch per ruas, satu entrance — 25 Oktober 2026

## Keputusan owner yang diimplementasikan

Profil baru `SINGLE_HIGHEST_CLASS_NEAREST_V1` pada bagian 6 notebook market:

1. Maksimal satu entrance asumsi untuk setiap bangunan.
2. Kandidat dalam 125 m diurutkan berdasarkan kelas jalan, jarak dari titik
   representatif bangunan ke segmen jalan (aturan pencarian yang sudah ada),
   lalu ID segmen sebagai tie-break deterministik.
3. Kandidat harus lolos izin, grade-separation, hambatan yang tersedia dan
   pemeriksaan menembus footprint bangunan lain. Kandidat berikutnya dicoba
   hanya bila validasi konektor gagal, bukan karena rute menuju toko gagal.
4. Setelah satu konektor dipilih, tidak ada entrance fallback saat routing.
   Akses terpilih dengan bukti tidak ada rute menjadi NO_ROUTE. Bukti akses/
   izin yang belum lengkap tetap UNKNOWN/UNVERIFIED; tidak diubah menjadi
   penolakan rute yang telah terbukti.
5. Arah jalan, larangan motor, posisi proyeksi pada ruas, biaya konektor,
   kecepatan 7 km/jam dan round(menit)<=10 tetap berlaku.

Ini perubahan kebijakan bisnis, bukan refactor yang menjanjikan semua status
bangunan sama dengan multi-access. Cakupan bisa turun bila entrance lain
sebenarnya dapat mencapai toko. Entrance tetap asumsi, bukan observasi lapangan.

## Pemrosesan

- Persiapkan geometri/rank/panjang segmen sekali per pemanggilan.
- Footprint inset/buffer disimpan per building ID dan dihitung paling banyak
  sekali ketika diperlukan, termasuk footprint penghalang tetangga.
- Susun urutan kandidat tiap bangunan, kelompokkan pilihan berikutnya menurut
  segmen, lalu evaluasi dalam batch per segmen. Jika gagal pemeriksaan geometri,
  bangunan maju ke kandidat berikutnya pada gelombang berikutnya.
- Akses setiap bangunan tetap diperiksa sendiri; tidak ada centroid cluster
  yang dianggap mewakili akses semua rumah.
- Hanya konektor terpilih yang menyumbang titik pemecahan graph. Pemecahan ruas
  tetap dilakukan per segmen setelah seluruh posisi terpilih dikumpulkan.
- Log menampilkan entrance terpilih, bangunan yang masih menunggu, dan jumlah
  kandidat yang telah diperiksa. Diagnostik mencatat profil, jumlah buffer,
  jumlah entrance dan batching `ROAD_SEGMENT_WAVES`.

## Konfigurasi, versi dan integrasi

`notebooks/location_intelligent_market_config.py`:
`MARKET_CONFIG['access']['building_entrance_profile']` memilih profil baru.
Notebook menyalinnya ke CONFIG dan membekukannya pada policy konektor PILOT.
Konfigurasi/hashes hasil berubah sehingga keluaran baru terisolasi dari baseline.
Routing menolak input multi-entrance yang disajikan sebagai profil single.

Snapshot jaringan tidak berubah hanya karena pilihan entrance berubah. Source
key dan akuisisi jaringan mengecualikan parameter entrance yang hanya berlaku
pada kalkulasi. Cache jalan/footprint/POI/BQ yang sesuai tetap dapat digunakan.
Jangan menghapus sumber lama atau mengulang pengambilan data untuk mengganti
profil ini. Snapshot hasil lama tetap immutable; mode historis tanpa marker
menggunakan `MULTI_ACCESS_LEGACY`.

Bagian 8 memakai policy beku yang sama dan tidak membuat entrance alternatif
untuk menyelamatkan NO_ROUTE. Biaya perjalanan, Huff dan gate POI tidak diubah.

## Validasi aktual

- Suite Area Coverage: 85 tes; 71 lulus, 14 dilewati pada interpreter tanpa GDAL.
- Suite LI-3 lama: 43 tes lulus, termasuk determinisme, arah/akses, barrier,
  proyeksi ruas dan batas 125 m.
- System Python/GDAL: 17 tes motor lama lulus; dua tes motor profil baru lulus
  (NO_ROUTE tanpa fallback dan penolakan multi-entrance yang tidak sesuai).
- Tes baru juga memeriksa prioritas kelas vs jarak, tie deterministik, bangunan
  penghalang, fallback khusus validasi konektor, batas 125 m, input tidak
  dimutasi, dan cache sumber tetap dapat dibuka tanpa refetch.
- Smoke end-to-end SYNTHETIC: normalisasi/cache HIT, seleksi, konektor, routing,
  ekspor dan manifest berhasil; tiga baris sumber seluruhnya direkonsiliasi,
  maksimal satu entrance per bangunan.
- Contoh benchmark SYNTHETIC 100 rumah/empat jalan paralel: konektor bangunan
  turun 400 menjadi 100; graph edges 405 menjadi 105. Durasi generator pada
  sampel lokal ini sekitar 0,023 menjadi 0,010 detik. Ini bukan proyeksi durasi
  run Kaggle 44 menit dan bukan klaim kualitas akses nyata.
  Bukti: `results/area_coverage_map/single_entrance/`.

Belum ada rerun penuh lokasi aktual Kaggle setelah perubahan ini. Ukur log
konektor/routing dan audit bangunan yang berubah status sebelum menyatakan
perbaikan waktu/kualitas lokasi aktual. Buka versi notebook terbaru lalu Run All;
job hasil baru memakai profil baru, source snapshot yang cocok tetap digunakan.

Fix kompatibilitas snapshot lama pada sel 5: [detail dan regresi](AREA_COVERAGE_SOURCE_COMPATIBILITY_FIX.md).
