# POI opsional dan gate bisnis terpisah

Keputusan owner,25 Oktober2026: jalan/footprint input utama; kegagalan POI tidak
menghentikan pipeline. Cakupan network diubah dari parameter5500m menjadi3000m.
Radius seleksi residential dan inventori POI/toko tetap2000m. Parameter network
mengikuti adapter bbox yang sudah ada (±3000m pada sumbu proyeksi); ini bukan
perubahan radius pasar atau klaim rute fisik telah diverifikasi.

## Perilaku yang diterapkan

| Kondisi | Pipeline utama | Gate zona >800m jika attractor diwajibkan |
|---|---|---|
| POI sukses, ada attractor eligible | Lanjut | OPEN |
| POI sukses, tidak ada attractor eligible pada snapshot | Lanjut | CLOSED sesuai bukti skenario |
| POI gagal/tidak tersedia | Lanjut; tampilkan POI belum tersedia | UNKNOWN, bukan CLOSED/OPEN |
| Kebutuhan attractor dinonaktifkan melalui kebijakan bisnis eksplisit | Lanjut | OPEN berdasarkan kebijakan, bukan klaim ditemukan POI |

`outer_zone_requires_attractor` tetap True sesuai aturan bisnis sebelumnya.
Kegagalan teknis tidak mengubahnya. Residential dalam zona <=800m tetap dapat
dialokasikan jika seluruh syarat lain terpenuhi; zona luar dengan gate UNKNOWN
berstatus UNVERIFIED/OUTER_GATE_UNKNOWN, tanpa alokasi pemenang yang dibuat-buat.
Perubahan teknis tidak otomatis menerima seluruh bangunan hingga2km.

## Source dan reproducibility

- Assertion yang mewajibkan keberhasilan unduhan POI di bagian5 dihapus.
- `load_optional_osm_pois` menyimpan inventori sukses atau observasi unavailable
  di `optional_poi_result.json` dengan receipt checksum. `rows`/`count` gagal
  tetap None, bukan daftar kosong/nol yang dianggap inventori lengkap.
- Snapshot normal yang sukses tetap `osm_poi_snapshot.data`; observasi gagal
  tidak disamarkan menjadi cache inventori sukses.
- Replay membaca observasi yang sama tanpa API, termasuk kegagalan tersimpan.
  Refresh POI memakai source revision baru; tidak mengubah hasil lama diam-diam.
- Jalan dan footprint tetap wajib. Kegagalannya tidak menjadi hasil sukses palsu.
- Pemeriksaan penggunaan bangunan menggunakan tag/POI lokal yang tersedia pada
  source footprint. Inventori fasilitas global gagal tidak menyebabkan TypeError
  rows=None atau meniadakan bukti penggunaan lokal yang positif.
- JSON memisahkan `poi_input_status` dari `attractor_gate`. Peta yang POI-nya
  tidak tersedia memiliki label layer opsional tersebut.
- Perubahan cakupan network menghasilkan source/job baru; snapshot jaringan
  5,5km lama tidak direlabel sebagai3km.

## Bukti verifikasi

69 tes Area:59 lulus dan10 skip karena GDAL worker terpisah. Kesepuluh tes OSM
kemudian dijalankan pada system Python/GDAL: lulus. Pengujian mencakup POI sukses
maupun gagal, frozen reopen tanpa API, gate UNKNOWN berbeda dari CLOSED, alokasi
inner tetap berjalan, outer UNKNOWN tidak diterima, serta source notebook dan
packet identik.

Smoke CPU/GDAL dengan POI sengaja gagal pada source SYNTHETIC menuntaskan
normalisasi, routing, market, CSV, peta dan reopen. Tiga fixture bangunan tetap
direkonsiliasi; gate UNKNOWN. Ini tidak menyatakan jumlah bangunan aktual owner.

Notebook source dipublikasikan QUICK_SAVE. Belum ada klaim full live job3km
selesai. Road-only tetap default; enam query eksternal tidak diaktifkan lagi.
