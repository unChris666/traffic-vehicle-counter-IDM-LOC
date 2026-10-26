<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Optimasi bagian 6 — 25 Oktober 2026

Scope: pengukuran durasi, indeks POI–footprint, cache normalisasi tervalidasi.
Tidak mengubah kandidat konektor, threshold, graph, routing, kapasitas atau
aturan alokasi. Tidak memakai satu keputusan akses untuk satu cluster rumah.

## Implementasi

- Tiap stage notebook mencatat `duration_seconds`, termasuk stage gagal.
- Bagian calculation mencetak START/SUCCEEDED/FAILED dengan durasi untuk
  persiapan bangunan/normalisasi, seleksi–kapasitas–proyeksi, graph, konektor,
  diagnostik graph, routing, ekspor keputusan dan manifest.
- Timing operasional berada di
  `/kaggle/working/results/area_coverage_market/calculation_performance.json`;
  timing stage di `notebook_readiness.json`. Durasi nondeterministik tidak
  dimasukkan ke paket hasil domain beku. Timing append per pemanggilan.
- Indeks spasial envelope grid tanpa dependency tambahan pada worker GDAL.
  Kandidat tetap diuji dengan OGR Intersects/Contains asli, urutan footprint
  tetap, overlap dan sentuhan boundary tidak dihilangkan.
- Satu normalisasi menghasilkan features dan diagnostik sekaligus. Receipt
  `raw/building_cache/normalization_cache.json` mengikat hash seluruh raw input
  (termasuk use-policy, POI lokal dan bukti inventory opsional), kode normalizer,
  versi Python dan GDAL serta checksum payload features/diagnostik.
  Semua kebijakan yang dikonsumsi normalizer berada pada raw; radius, CRS,
  seleksi dan routing tetap divalidasi oleh tahap masing-masing.
- Worker prepare memverifikasi receipt dan hasil GeoJSON terhadap frozen
  checksums. Cache beda input/kode/runtime tidak dipakai; normalisasi ulang.
  Receipt/payload rusak ditolak. Snapshot historis tanpa receipt tetap dibaca
  dengan normalisasi ulang, tanpa menulis berkas baru ke snapshot lama.
- Paket dengan manifest tetap menggunakan REOPEN/verifikasi, tidak dihitung
  ulang hanya agar optimasi terlihat bekerja. Cache baru berlaku pada kalkulasi
  baru; jangan menghapus snapshot untuk memaksa benchmark.

## Verifikasi yang dijalankan

- Suite Area Coverage: 76 tes, 64 lulus dan 12 skip karena interpreter utama
  tanpa GDAL. Worker system Python: 10 tes OSM dan 5 tes optimasi lulus,
  mencakup 12 tes yang dilewati serta tiga tes non-GDAL yang diulang.
- Indeks vs scan penuh: kasus boundary, polygon overlap, POI di luar footprint;
  candidate envelopes juga dibandingkan dengan scan pada 1.000 titik.
- Cache: hit tanpa normalisasi, perubahan POI/runtime memicu miss, korupsi
  ditolak, snapshot lama tidak ditulis ulang.
- Replay snapshot SYNTHETIC dengan kode sebelum perubahan (git HEAD 330808f)
  dibanding kode baru: selection, capacity, routing, decisions, metric buildings
  dan connectors identik. Ini bukan validasi akses lokasi nyata.
- Benchmark SYNTHETIC 1.600 bangunan/400 POI: scan 0,330 s, indeks 0,060 s;
  cache miss 0,091 s dan hit 0,024 s. Features/diagnostik identik. Angka ini
  khusus sampel sintetis lokal, bukan durasi total Kaggle atau jaminan speedup.
  Evidence: `results/area_coverage_map/optimization/`.

## Penggunaan Kaggle

Buka versi notebook terbaru lalu Run All agar helper dan hash sumber sinkron.
Log menunjukkan bagian yang sedang bekerja dan apakah cache HIT/MISS.
Hasil beku yang sudah ada tetap REOPEN; observasi waktu kalkulasi baru memerlukan
job/source revision baru yang eksplisit. Tidak menjalankan ulang unduhan atau
perhitungan penuh Kaggle hanya untuk perubahan instrumentasi ini.
