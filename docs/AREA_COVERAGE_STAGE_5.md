# Bagian 5 — akuisisi sumber, bukan counting

Tanggal review: 25 Oktober 2026. Konteks: owner telah melewati roads full/four
road tiles; error berikutnya adalah features tile1/4. Tidak ada dasar dari
traceback saja untuk menyatakan jaringan jalan gagal lagi.

## Apa yang dilakukan

1. Periksa snapshot lokal dengan konfigurasi target dan checksum yang cocok.
2. Jika belum lengkap, ambil node/way jalan OSM memakai filter motor yang sama.
3. Ambil data pengaman akses: barrier node/way, waterways, water polygons,
   water relations dan turn restrictions pada timestamp roads yang sama.
4. Ambil inventori POI dan footprint bangunan untuk lokasi ini.
5. Simpan source manifest hanya setelah seluruh sumber wajib lengkap.

Bagian6 baru melakukan normalisasi, seleksi, graph/konektor, routing dan
kapasitas. Bagian8 melakukan gate attractor dan alokasi Huff. Bagian9 menggambar
peta dan ekspor. Bagian5 tidak menjalankan Traffic Counter atau GPU inference.

Lingkaran market2km berbeda dari bbox jaringan5,5km yang sudah dibekukan.
Pengambilan barrier pada jaringan yang lebih luas ditujukan untuk routing,
bukan menambah rumah di luar zona bisnis. Radius/filter tidak dikurangi untuk
menyembunyikan error.

## Mengapa error tetap terjadi

- `PARTIAL_OR_INVALID` pada HTTP200 bukan sukses: isi respons memiliki remark
  server atau schema wajib tidak lengkap. Pesan remark sekarang diteruskan ke
  diagnostics sehingga timeout/memori dapat dibedakan dari masalah schema.
- HTTP502 berarti kegagalan gateway/upstream; ReadTimeout berarti client belum
  menerima respons lengkap dalam batas waktu.
- Query lama menggabungkan enam jenis data dan ekspansi relasi `(._;>>;)`.
  Pembagian empat wilayah masih dapat menghasilkan query berat. Ini kelemahan
  strategi sebelumnya; rerun tanpa memecah query tidak menjamin kemajuan.
- Penyebab persis HTTP200 pada session owner belum dapat dipastikan tanpa remark
  yang tersimpan. Tidak ada hasil counts yang dinyatakan dari respons parsial.

## Perbaikan

Jika tile gabungan gagal, data dipecah menjadi enam permintaan independen dengan
selector yang sama persis. Setiap bagian memiliki file cache/receipt sendiri di
`network/raw/feature_parts/<tile>/`. Tidak ada jenis barrier yang dihilangkan.

Request kecil memakai server timeout maksimal20detik. Hanya jika remark server
menyebut timeout/memori, kategori gagal dibagi empat lagi, maksimal dua tingkat.
Kategori lain tidak diambil ulang. Kegagalan gateway tanpa bukti resource tidak
memicu pembagian rekursif tanpa batas.

Satu pemanggilan dibatasi64 request chain (masing-masing mencoba endpoint yang
terkonfigurasi). Jika anggaran habis, checkpoint tersimpan dan cell dapat
melanjutkan bagian yang belum selesai. Timestamp, query, checksum dan konflik
source tetap diperiksa. Respons parsial tidak pernah menjadi manifest sukses.

Source/helper transport di-reload pada cell5 agar perbaikan tidak tertahan oleh
module Python lama yang sudah diimpor session. Konfigurasi koordinat, kebijakan
motor, seleksi luas, waktu dan Huff tidak diubah.

## Cara menggunakan perbaikan

1. Buka source terbaru notebook Kaggle yang sama.
2. Jalankan bagian2 (cell implementasi/helper) dan bagian3 (konfigurasi job).
3. Jalankan bagian5. Jangan menghapus folder SOURCES yang berisi roads sukses.
4. Perhatikan nama kategori pada log. Jika masih blocked, lihat
   `network/acquisition_status.json`; status sekarang memuat remark/failure_reason.

Run All juga dapat dipakai. Source key masih terikat konfigurasi yang sama,
sehingga data roads sukses pada working folder yang masih tersedia dapat dibuka
ulang. Menghentikan/menghapus session dapat menghilangkan working folder; simpan
paket source untuk FROZEN replay lintas session.

Untuk penggunaan berulang yang lancar, targetnya adalah **akuisisi sekali →
validasi snapshot → proses dan review dari snapshot**. Layanan publik Overpass
bukan layanan dengan SLA aplikasi ini. Jika seluruh endpoint tidak tersedia,
program harus menunda pengambilan, bukan menghitung tanpa barrier.

## Bukti validasi

- 63 tes Area:54 lulus,9 skip pada venv tanpa GDAL. Meliputi HTTP200 dengan
  server remark, resume antar-kategori, split kategori resource-limited,
  selector lengkap, snapshot date dan cache tanpa re-fetch.
- Bukti sintetis tidak menjadi validasi hasil market lokasi owner.
- Source notebook/helper/paket diperiksa identik; seluruh cell parse.
- Dokumentasi OSM tentang endpoint berhasil diakses. Probe bounded pada mirror
  alternatif mengembalikan429; mirror tidak dimasukkan sebagai fallback default.
- Source dipublikasikan QUICK_SAVE. Full live run untuk lokasi owner belum
  dinyatakan sukses; tidak mengulang seluruh job saat sumber masih tidak pasti.

Referensi endpoint: https://wiki.openstreetmap.org/wiki/Overpass_API

## Perubahan scope owner berikutnya

[Mode graph jalan sederhana](AREA_COVERAGE_ROADS_ONLY.md) kini default pada
notebook market: keenam request eksternal tidak dijalankan. Penjelasan strategi
FULL di atas tetap riwayat/opsi; tidak lagi wajib pada skenario ROAD_ONLY.
