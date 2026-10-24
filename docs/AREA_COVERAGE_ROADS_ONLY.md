# Mode sederhana berbasis graph jalan

Keputusan owner,25 Oktober2026: enam query tambahan boleh dilewati; bila tidak
ada jalur pada jaringan yang dipakai, bangunan tidak masuk cakupan calon toko.

## Yang tetap wajib

Bagian5 tetap menyiapkan jaringan jalan, POI dan footprint. Jaringan dipakai
untuk arah/konektivitas, POI untuk gate zona luar, footprint untuk seleksi dan
penghitungan. Melewati seluruh bagian5 tanpa snapshot akan menghilangkan input.

Enam query barrier/air/relasi turn adalah pengayaan validasi, bukan prasyarat
membangun graph dari node/way jalan OSM. OSM dapat memiliki data tersebut, tetapi
kelengkapannya tidak otomatis tersedia untuk setiap lokasi. Query gabungan atau
split6 yang dibuat pada iterasi sebelumnya kini tidak dipaksakan pada mode ini.

## Profil yang diaktifkan

`MARKET_CONFIG['sources']['network_feature_mode']='ROADS_ONLY_EXPERIMENT'`.

- Tidak ada request fitur eksternal dalam mode ini. Data pendamping berasal dari
  extract roads yang benar-benar berhasil, bukan respons API kosong buatan.
- Node jalan harus terhubung dalam graph. Persilangan gambar tidak membuat edge.
  Oneway, akses privat/larangan motor dan barrier yang sudah ikut extract jalan
  tetap diperiksa. Predikat unknown/prohibited pada edge tidak diubah menjadi yes.
- Pengambilan tambahan barrier/air/turn tidak dilakukan. Coverage-nya dicatat
  NOT_REQUESTED, `restrictions_complete=False`, bukan klaim semua aman/lengkap.
- Hasil routing tetap PARTIAL dan physical_access_validated=False. ACCEPTED
  adalah penerimaan skenario pada graph tersedia. JSON/tooltip mengungkap mode.
- Konektor bangunan–jalan tetap memakai asumsi frontage/snap125m yang sudah ada,
  dengan pemeriksaan geometri yang tersedia. Snap bukan bukti pintu masuk nyata.
- Tidak ada rute calon yang eligible → tidak dialokasikan ke calon. Batas waktu,
  seleksi luas, gate attractor dan aturan market tidak dihapus.

Hanya profil kebijakan/evidence yang keduanya eksplisit ROAD_ONLY yang dapat
memproses coverage fitur belum lengkap. FULL tetap BLOCKED jika evidence tidak
lengkap; perubahan ini bukan fallback otomatis setelah suatu query gagal.

## Snapshot dan pemulihan

Mode baru memakai `network_roads_only`, menyalin extract roads terikat lokasi dari
folder `network` yang sudah ada jika tersedia. Folder lama tidak diubah. Mode
menjadi bagian fingerprint job/hasil, sementara source key dasar dipertahankan
agar roads sukses pada draft owner dapat dipakai ulang. Source manifest lengkap
milik profil berbeda tetap tidak direlabel; gunakan SOURCE_REVISION baru bila
mengubah profil pada paket yang sudah finalized.

Setelah source notebook diperbarui: jalankan bagian2/helper, bagian3/config,
kemudian bagian5. Bagian5 mengimpor ulang helper agar session tidak memakai kode
lama. Tidak perlu menghapus roads yang sudah berhasil. Log seharusnya tidak lagi
menampilkan pengambilan fitur/enam kategori pada profil ini. POI dan bangunan
masih memerlukan sumbernya masing-masing bila belum tersimpan.

## Validasi

- 64 tes Area:55 lulus dan9 skip karena venv tidak memiliki GDAL.
- 17 tes motor pada system Python/GDAL lulus, termasuk FULL tetap menolak
  coverage kurang, ROAD_ONLY berstatusPARTIAL, dan akses dilarang tetap ditolak.
- Uji resume membuktikan roads dari draft gagal dipakai ulang, tidak ada request
  features, tidak ada perubahan pada draft lama, serta coverage eksplisitfalse.
- Integrasi aktual CPU/GDAL pada tiga bangunan SYNTHETIC lulus dalam kedua mode,
  termasuk graph/routing/market/export/reopen. Ini bukan hitungan lokasi owner.
- Source notebook/helper/packet sama; semua cell parse. Publikasi QUICK_SAVE,
  bukan klaim full run lokasi owner berhasil.

Sumber acuan lengkap dan hasil mode sederhana harus tetap dapat dibedakan.
Pemeriksaan hambatan di luar roads dapat menjadi pengayaan kualitas berikutnya
bila dibutuhkan, bukan penghalang eksekusi skenario graph yang disepakati ini.
