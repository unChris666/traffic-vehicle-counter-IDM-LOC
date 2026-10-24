# Audit akuisisi Area Coverage — 25 Oktober 2026

## Bukti dan diagnosis

Traceback owner berhenti pada `OSM roads unavailable`. Impor dependensi telah
terlewati; ini kegagalan retrieval sebelum routing/Huff, bukan bukti algoritma
market salah. Status HTTP persis pada session interaktif owner belum tersedia;
traceback generik saja tidak membedakan timeout, rate limit dan penolakan request.
Probe terpisah dari Codex untuk roads radius100m mendapat HTTP502. Probe GET
terpisah mendapat406; tidak ditambahkan fallback GET yang belum berhasil.
Ini probe ketersediaan, bukan validasi graph penuh atau hasil lokasi owner.

## Temuan dan perbaikan P0

| Temuan | Perbaikan | Pengaman |
|---|---|---|
| Roads full gagal langsung berhenti | Full query sekali, lalu empat tile, seperti kebutuhan barrier | Tidak mengurangi radius/filter atau menambah ruas palsu |
| Draft dengan raw gagal tidak dapat dilanjutkan | Resume berdasarkan konfigurasi, query dan cache sukses | Config/query berbeda ditolak |
| Data berhasil ikut diambil ulang | Per-piece cache dan receipt checksum | Yang gagal saja dicoba lagi saat cell diulang |
| Query antar-tile bisa berbeda snapshot | Timestamp tile roads pertama mem-pin tile berikutnya dan barrier | Konflik elemen sumber ditolak oleh merger asli |
| Kegagalan generik tidak membantu diagnosis | `network/acquisition_status.json` memuat tahap, failed_tile dan HTTP/error_type | Tidak memasukkan credential/key |
| Gagal mengganti draft menutupi bukti | Riwayat raw gagal disimpan; canonical draft ditulis via file sementara | Snapshot finalized diverifikasi dan tidak dimutasi |
| HTTP400/401/403 dapat dianggap masalah ukuran | Penolakan permanen dihentikan, tidak diulang sebagai tile | Tidak mencoba mengatasi larangan akses dengan retry |
| POI gagal tidak punya receipt mudah dibaca | `sources/poi_readiness.json` | Tidak dianggap nol fasilitas |
| Helper Python lama masih di memory session | Reload helper akuisisi/runtime pada cell5 | Tidak mengubah ledger/domain |

Status source network hanya SUCCEEDED setelah roads dan barrier lengkap. Tile
parsial tidak membuat `network_manifest.json`. Rerun memakai source timestamp
yang sama; refresh waktu data membutuhkan SOURCE_REVISION baru secara eksplisit.
Retries tetap terbatas: satu request chain per tile yang belum berhasil dalam
satu pemanggilan, tidak ada infinite retry/hot-loop atau sleep panjang.

Cakupan jaringan, road policy, konektor, aturan waktu, luas, Huff, dan keputusan
alokasi tidak diubah oleh perbaikan transport ini. Stage acquisition diisolasi
pada `notebooks/location_intelligent_network_acquisition.py` agar dapat diuji
terpisah; ini bukan migrasi seluruh engine Area Coverage.

## Validasi aktual

- 59 tes Area: 50 lulus, 9 dilewati pada venv tanpa GDAL; sembilan itu sudah
  memiliki pengujian terpisah pada runtime GDAL dalam checkpoint sebelumnya.
- Kasus khusus: roads full gagal; tile kedua gagal lalu resume tanpa mengambil
  ulang tile pertama; seluruh tile pinned; checksum rusak ditolak; HTTP403 tidak
  dicoba sebagai tile; barrier parsial tidak diterima; finalized reopen tanpa API.
- Smoke aktual CPU/GDAL pada tiga bangunan **SYNTHETIC**: routing, gate,
  alokasi, ekspor dan reopen tetap lulus. Tidak menjadi jumlah rumah lokasi owner.
- Source notebook/paket/helper identik, seluruh cell parse, config job owner
  dibandingkan dengan source Kaggle yang ditarik dan tidak berubah.
- Publikasi Kaggle QUICK_SAVE. Tidak menjalankan full live job lagi saat probe
  sumber masih gagal. Belum mengklaim end-to-end lokasi baru sukses.

## Cara melanjutkan di Kaggle

Buka source terbaru:
https://www.kaggle.com/code/chrisbiran/area-coverage-market-osm-2km-cpu/edit

Jalankan cell implementasi/helper dan konfigurasi terbaru, kemudian bagian5.
Run All juga bisa dipakai; stack numerik tetap dipertahankan. Tidak perlu
menghapus snapshot berhasil atau mengganti koordinat untuk retry. Jika session
masih menyimpan source draft yang gagal, retry melanjutkan bagian yang belum
berhasil. Source finalized/FROZEN tidak otomatis mengambil ulang data.

Bila upstream tetap gagal, baca file `acquisition_status.json` yang disebut pada
error, bukan menganggap jaringan kosong atau mengesahkan market count nol.

## Gate menuju modularisasi

| Gate | Status |
|---|---|
| Isolasi transport, bounded failure, resume, checksum | Lulus pengujian lokal |
| Aturan domain dan ekspor pada fixture sintetis | Lulus, bukan validasi market nyata |
| Satu full run lokasi baru: roads/barrier/building/POI dan BQ | Belum terverifikasi lengkap |
| Frozen replay menghasilkan ledger/pemenang/agregat sama | Lulus sintetis; run nyata masih diperlukan |
| Peta, CSV, JSON dan seluruh source rows konsisten | Lulus sintetis; audit output nyata masih diperlukan |

Persiapan rencana modularisasi dapat memakai batas source adapter → snapshot →
selection/routing → allocation → rendering/export. Migrasi engine keseluruhan
belum dinyatakan lulus hanya karena retry network telah dites. Unknown tetap
unknown; tidak perlu mengarang kelengkapan fisik OSM agar gate software lulus.

## Checkpoint fitur barrier berikutnya

[Penjelasan bagian5 dan strategi per kategori](AREA_COVERAGE_STAGE_5.md)
menambahkan pemecahan enam jenis fitur setelah tile gabungan gagal. Catatan
checkpoint sebelumnya tentang empat tile bukan batas strategi terbaru. Aturan
market/routing dan syarat kelengkapan sumber tetap sama.
