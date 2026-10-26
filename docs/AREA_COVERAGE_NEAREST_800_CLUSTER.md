<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Kompetitor 800 m, nearest access, exact-node clustering — 25 Oktober 2026

## Kontrak terbaru

- Kompetitor dihitung hanya jika jarak geodesik dari calon toko <=800 m.
  Filter dijalankan sebelum konflik identitas kompetitor di luar scope, sebelum
  pencarian konektor, routing dan Huff. Eksklusi dicatat sebagai
  OUTSIDE_COMPETITOR_CALCULATION_RADIUS dan bukan kegagalan sumber.
- PRIMARY: koridor name/ref yang sama dalam 800 m, termasuk sisi seberang;
  SECONDARY: koridor yang diketahui berbeda. Koridor belum diketahui tetap
  UNVERIFIED_CORRIDOR, tidak diam-diam menjadi sekunder.
- Profil entrance baru SINGLE_NEAREST_VALID_V1 berlaku pada bangunan dan toko.
  Bangunan: kandidat jalan dalam 125 m, pilih konektor valid dengan jarak
  representatif-ke-ruas terkecil; tie menggunakan ID segmen. Kelas jalan masih
  menjadi metadata/kelayakan kandidat, bukan prioritas atas jarak.
- Satu entrance tetap, tidak berpindah entrance jika routing ke toko gagal.
  Snap toko tetap tanpa batas numerik pada graph yang tersedia.
- Batas Indomaret, inventory POI dan syarat zona luar tetap seperti sebelumnya;
  batas kompetitor baru tidak mengecilkan inventory POI/Indomaret menjadi 800 m.
- Profil barrier/oneway sebelumnya tetap aktif, termasuk penolakan penggunaan
  edge UNKNOWN dalam rute accepted. Pemeriksaan konektor tetap berlaku.

Konfigurasi: location_intelligent_market_config.py, access.building_entrance_profile
serta sources.competitor_calculation_radius_m. Inventory BQ dapat tetap memakai
snapshot 2 km; perhitungan kompetitor memakai subset 800 m tanpa refetch.

## Percepatan yang diterapkan

Pencarian akses target menggunakan STRtree. Mulai dari jarak nearest geometry,
ambil kandidat dalam kotak pencarian, saring jarak aktual, urutkan jarak/ID dan
perluas jendela jika kandidat ditolak. Tidak menetapkan radius snap baru atau
batas jumlah percobaan yang dapat membuang akses valid. Radius awal pencarian
adalah parameter teknis, bukan batas bisnis. Extent dihitung sekali, tidak
menghitung jarak ke seluruh ruas untuk setiap target. Log memberi progres target.

Routing bangunan dikelompokkan berdasarkan node akses graph yang benar-benar
identik. Satu lookup per source node/target node; setiap bangunan menambahkan
panjang konektor sendiri. Node dengan posisi berbeda, meskipun berdekatan atau
pada jalan sama, tidak digabung. Tidak ada centroid, pembulatan baru, atau
pelabelan satu keputusan bagi semua anggota cluster.

Huff, core/zona, time threshold, kelayakan, winner dan skor tetap dihitung per
bangunan. Semua baris tetap direkonsiliasi. Kelompok kompetitor dan jumlah node
cluster ditampilkan di bagian 8 dan disimpan dalam result.json; peta sudah
memiliki layer primer/sekunder/koridor unknown terpisah. Jika node bangunan
sebagian besar unik, penghematan dari grouping memang terbatas; tidak
menjanjikan semua bangunan dapat dikelompokkan.

## Verifikasi aktual

- Suite Area Coverage: 108 tes, 93 lulus dan 15 skip pada interpreter utama.
- Suite LI-3: 43 lulus; worker motor GDAL: 17 tes lama lulus.
- Nearest spatial order vs full scan sama untuk 302 segmen sintetis, termasuk
  tie, target pada ruas, dan target jauh di luar extent. Pencarian tetap lengkap.
- Nearest bangunan memilih jalan residential dekat dibanding primary jauh;
  bila konektor terdekat gagal geometri, kandidat valid berikutnya dipilih.
- Dua bangunan pada node sama: satu lookup, jarak total berbeda, matriks rute
  sama dengan baseline per-bangunan. Ini menguji reuse tanpa menyamakan biaya.
- Smoke SYNTHETIC fresh kalkulasi dan market: nearest profile dibekukan, competitor
  700/800 m masuk, 800,01 m tidak pernah diteruskan ke pencarian konektor;
  Indomaret 1.500 m tetap tersedia. Seluruh tiga baris sumber direkonsiliasi.
  Evidence: results/area_coverage_map/nearest800/synthetic_smoke.json.

Ini perubahan kebijakan frontage dan scope kompetitor, sehingga tidak
mengklaim total sama dengan baseline lama. Belum ada rerun penuh lokasi aktual
atau pengukuran percepatan seluruh job Kaggle.

## Penggunaan

Muat notebook terbaru lalu Run All. Perubahan entrance bangunan membutuhkan
hasil bagian 6 baru; bagian 8 tidak boleh memakai graph entrance kelas-tertinggi
lama seolah-olah sudah memakai nearest. Sumber yang cocok tetap dipakai ulang;
konfigurasi entrance adalah kalkulasi dan dikeluarkan dari source identity,
namun masuk identitas job/frozen policy/hasil. Snapshot lama tetap disimpan.
