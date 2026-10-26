<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Spesifikasi market — lokasi baru (keputusan owner dan implementasi)

Tanggal: 24 Oktober 2026. Permintaan owner mengubah prototype Area Coverage,
bukan Traffic Counter. Model Huff tetap skenario eksperimen, belum model perilaku pelanggan tervalidasi.

## Requirement yang sudah dicatat

Target: latitude **-6.190690620514923**, longitude **106.83819549844226**.
Konfigurasi terpisah: [location_intelligent_market_config.py](../notebooks/location_intelligent_market_config.py).
Koordinat ini sekitar 24,4 km dari target lama. Snapshot jaringan lokal lama
tidak dapat menjadi sumber lokasi baru; bangunan/network/POI/BQ harus memiliki
binding target dan cakupan baru. Notebook baru memakai akuisisi bounded untuk lokasi ini; tidak memakai seed
lokasi lama. Query BQ dibatasi biaya bytes pada konfigurasi.

- Pin calon putih; radius tampilan 100/400/2000 m: hijau/kuning/oranye.
- Kompetitor primer: radius 400 m merah bata; sekunder: 100 m merah cerah;
  pin keduanya merah. Penentuan primer memakai koridor nama/ref yang dapat dicocokkan.
- Pin Indomaret biru; aturan tampilan radius <400 m = 0;
  400–<800 m = 100 m biru. Radius >=800 m = 0; pengaruh statistik mengikuti zona.
- Footprint: valid hijau, kompetisi oranye, cannibalization biru,
  milik kompetitor merah, milik Indomaret biru, lainnya abu-abu.
  Warna market merupakan field terpisah dari kelayakan routing. Warna tidak
  mengubah NO_ROUTE menjadi ACCEPTED. Konflik warna harus memakai hasil
  alokasi tersimpan, bukan urutan layer yang kebetulan digambar terakhir.
- Jalan tetap mengikuti highway OSM; kategori POI dibedakan.
- Minimum luas residential >=36 m² dan maksimum <550 m².
- Perhitungan harus mempertimbangkan jaringan motor, bukan lingkaran saja.

## Keputusan owner yang diterapkan

| Topik | Aturan |
|---|---|
| Overlap core | Calon menang pada overlap radius 100 m dengan toko yang pusatnya <=100 m dari calon. Tidak mengambil seluruh core toko lain. Berlaku juga terhadap Indomaret jika core-nya aktif. |
| Indomaret | Jarak pusat <400 m: pin saja, tanpa core eksklusif. 400–<800 m: core/radius 100 m. >=800–2000 m: pin saja. Tetap dapat ikut pengaruh statistik di luar core pada zona yang diizinkan. |
| Primer | Satu koridor nama/ref dengan calon dalam <=800 m; sisi berseberangan juga primer. Ruas OSM berbeda tidak otomatis berarti koridor berbeda. Tidak membuat koneksi menembus barrier. |
| Huff | Daya tarik sama, eksponen jarak rute 2. Satu bangunan utuh ke skor tertinggi; seluruh skor tetap diekspor, tidak dijumlah sebagai footprint pecahan. Tidak ada undian. |
| Gate luar | >=1 pasar/RS/stasiun/rekreasi/polisi/bank/mall/pusat perbelanjaan dalam 2 km dan memiliki rute dari calon membuka zona 800–2000 m. |
| Restoran | Alternatif gate: >=5 bangunan restoran berbeda, luas footprint masing-masing >=40 m², satu koridor dan jarak setiap pasangan <=200 m. Footprint/koridor yang belum terbukti tidak lolos. |
| Eligibility | Zona jarak lurus; rute motor wajib. Kecepatan seluruh segmen 7 km/jam; Python round(total_menit)<=10. Residential >=36 m² dan <550 m². |
| Pengaruh | Area inti eksklusif berbeda dari radius pengaruh statistik; di luar inti toko tetap dapat berpengaruh pada zona yang diizinkan. |

## Urutan operasional dan interpretasi eksplisit

1. Simpan semua source rows. Residential di luar kelayakan penggunaan/luas,
   akses calon belum ACCEPTED, atau di luar 2 km tidak dialokasikan ke calon.
2. Zona >800 m membutuhkan gate OPEN. UNKNOWN tidak menjadi CLOSED yang
   berarti tidak ada fasilitas secara fisik, maupun menjadi accepted.
3. Core eksklusif **100 m** diterapkan sebelum duel statistik. Radius primer
   **400 m pada peta bukan area eksklusif 400 m**; ini mempertahankan aturan
   owner bahwa area di luar core 100 m dapat diperebutkan. Toko tetap memerlukan
   rute yang lolos batas waktu untuk menerima alokasi.
4. Di luar core, zona <=400 m: calon vs kompetitor primer. Kompetitor sekunder
   tetap memiliki core 100 m. Di zona >400 m: calon vs kompetitor dan Indomaret
   yang eligible, termasuk toko yang radius tampilannya nol.
5. Kategori primer memakai koridor yang dapat dicocokkan dan batas pusat 800 m
   dari klarifikasi owner. Toko tanpa nama/ref memadai berstatus koridor belum
   terverifikasi; tidak dipaksa primer/sekunder pada wilayah yang terpengaruh.
6. Konflik antar-core selain prioritas calon yang disepakati diselesaikan dengan
   skor Huff. Tie persis: jarak rute lalu stable store key. Ini keputusan teknis
   deterministik, bukan bukti preferensi pelanggan.
7. Cluster restoran memakai complete-link (setiap pasangan <=200 m), tidak
   memakai rantai yang dapat memanjang tanpa batas. Node/way POI di bangunan
   sama hanya dihitung satu site. Area 40 m² adalah luas footprint bangunan,
   bukan klaim luas lantai usaha.
8. Jika calon menang melawan kedua jenis toko, warna cannibalization biru
   didahulukan; field `contest_kinds` tetap mencatat kompetisi juga. Jika calon
   kalah, warna mengikuti jenis pemenang. Status akses tetap disimpan terpisah.
9. Jarak Huff memakai rute gedung→toko termasuk konektor. Rute calon tetap dari
   primary ledger; penambahan titik graph alternatif tidak menulis ulang hasil
   primary. Larangan belok, arah dan barrier mengikuti engine motor yang sama.

**Implikasi batas waktu:** gate membuka kelayakan zona, bukan menerima semua
bangunan hingga 2 km. Dengan 7 km/jam dan round(menit)<=10, banyak rute di zona
luar tetap OVER_TIME_LIMIT. Jangan menghapus batas waktu untuk menaikkan hasil.

Dengan daya tarik sama, pemenang Huff adalah toko dengan jarak rute terpendek
di antara kontestan yang eligible. Skor tetap memberi informasi relatif, tetapi
belum membuktikan peluang pelanggan atau menangkap ukuran/frontage toko.

Generic building=yes tetap dapat memakai fallback N1 berlabel asumsi setelah
pemeriksaan POI; bukan residential terverifikasi. Mixed-use/POI ambigu tetap di
luar alokasi residential sampai ada bukti. Kapasitas bersatuan berbeda tidak
dijumlahkan; keluaran market utama adalah jumlah footprint utuh per pemenang.

## Implementasi dan cara review

- [Notebook source terlihat](../notebooks/area_coverage_market_cpu_2km.ipynb).
- [Konfigurasi tunggal](../notebooks/location_intelligent_market_config.py).
- Domain murni: `location_intelligent_market.py`; I/O/routing/cache:
  `location_intelligent_market_runtime.py`; renderer: `location_intelligent_market_map.py`.
- Notebook Kaggle berganti judul dan slug menjadi
  [Area Coverage Market OSM 2km CPU](https://www.kaggle.com/code/chrisbiran/area-coverage-market-osm-2km-cpu/edit).
  Ini pembaruan notebook yang sama; output historis tidak dianggap output target baru.
- Bagian 8 menunjukkan gate, alasan, pembagian dan rekonsiliasi; bagian 9 peta
  interaktif, CSV, GeoJSON, JSON, manifest serta ZIP source/result privat.
- Min luas inklusif hanya aktif pada profile `area-market-ge36-v1`; profile lama
  tetap memakai minimum eksklusif. POI market menggunakan versi cache baru,
  mencakup stasiun, rekreasi, bank, restoran dan mall; cache delapan kategori
  lama tidak dipakai sebagai bukti syarat gate.

Radius/pin baru, warna footprint, network highway dan POI per kategori dipenuhi
oleh renderer ledger. Tidak ada panel ringkasan besar. Tooltip tetap ID, AREA,
Status, Reason, Alternatif; Reason menyertakan akses dan skor estimasi Huff.
Tidak mengklaim frontage toko diketahui; daya tarik sementara disamakan.

## Reproduksibilitas

- Sources disimpan di `/kaggle/working/results/area_coverage_market_sources/<source_key>/`.
- Job/pilot di `/kaggle/working/results/area_coverage_market/<job_key>/`.
- Hasil `market/<fingerprint>/result.json`, `market_buildings.csv`, `manifest.json`.
- Peta dan GeoJSON di `market/<fingerprint>/views/<presentation_hash>/`.
- Fingerprint mengikat sumber, konfigurasi, kebijakan, kode dan hasil primary.
  Cache dibuka dengan checksum; data berubah/kegagalan export tidak menghasilkan
  cache sukses. Worker/library aktual disimpan bersama manifest pilot.
- Sumber live yang diambil kembali pada waktu berbeda dapat berubah. Untuk
  session baru, simpan ZIP privat, extract dan arahkan `FROZEN_SOURCE_INPUT` ke
  folder `sources`, `BQ_FROZEN_CACHE_INPUT` ke snapshot BQ lama, dan pakai mode
  FROZEN. ZIP tidak berisi service-account key; hasil BQ tetap data privat.

## Validasi aktual dan batasnya

- Suite `area_coverage*tests.py`: 55 tes; 46 lulus dalam venv dan 9 OSM dilewati
  karena GDAL terpisah. Sembilan OSM dijalankan pada system Python: lulus.
- Seleksi bangunan: 40 tes lulus; routing motor: 16 tes lulus pada system
  Python/GDAL. Menjalankan suite motor pada venv tanpa GDAL membuat input gate
  BLOCKED, sehingga suite tersebut harus dijalankan pada runtime GDAL.
- Smoke integrasi aktual menggunakan source **SYNTHETIC**, tanpa live API:
  tiga bangunan melewati GDAL, routing, gate, alokasi, CSV dan peta; rekonsiliasi
  serta cache result/presentation reopen lulus. Tiga hasil sintetis bukan jumlah
  rumah untuk lokasi owner.
- Browser Chromium: peta sintetis target baru dan 27 toggle layer dimuat,
  tanpa JavaScript/resource error; radius dan kategori POI baru tampil.
- Pengujian export notebook: kegagalan ZIP tidak membuat manifest sukses,
  retry menghasilkan ZIP valid termasuk snapshot BQ, reopen tidak menulis ulang,
  dan korupsi ditolak. Notebook/packet/helper source diperiksa identik.
- Semua 61 cell source notebook parse dan tidak membawa output/key privat.
- Run CPU Kaggle benar-benar dijalankan, tetapi berakhir ERROR saat source barrier
  (HTTP 502 dan ReadTimeout). Network roads SUCCEEDED (191.517 source elements);
  BQ preflight BLOCKED pada KAGGLE_SECRET_READ (ConnectionError/HTTP400).
  Tidak ada hasil market aktual. Fallback empat tile exact-as-of ditambahkan
  setelah kegagalan dan dites sintetis; source terbaru disimpan QUICK_SAVE,
  tanpa mengulang full run yang input/BQ-nya masih blocked.
  [Receipt bukti](evidence/area_coverage_market/validation_receipt.json).

Perintah verifikasi lokal:

```bash
/workspace/.venvs/area-coverage-map/bin/python -m unittest discover -s notebooks -p 'area_coverage*tests.py'
/usr/bin/python3 -m unittest discover -s notebooks -p 'area_coverage_osm_tests.py'
/usr/bin/python3 -m unittest discover -s notebooks -p 'location_intelligent_buildings_tests.py'
/usr/bin/python3 -m unittest discover -s notebooks -p 'location_intelligent_motor_routing_tests.py'
PYTHONPATH=notebooks /workspace/.venvs/area-coverage-map/bin/python notebooks/area_coverage_market_smoke.py
```

## Perbaikan error runtime NumPy pada session interaktif

Traceback owner menunjukkan `AttributeError: numpy._core._multiarray_umath`
`has no attribute _blas_supports_fpe` dalam rantai OSMnx → sklearn → SciPy →
NumPy testing, sebelum query jaringan dijalankan. Ini konsisten dengan pergantian
NumPy pada session yang telah memuat binary lama; bukan kegagalan renderer atau
aturan Huff. Penyebab lingkungan lengkap belum direproduksi pada image Kaggle.

Dependency cell sekarang mempertahankan versi NumPy/pandas/Shapely/pyproj dari
image, bukan memaksakan NumPy2.5.4 ke kernel aktif. Pemeriksaan versi memory/disk
serta impor numpy.testing/SciPy/sklearn/OSMnx dilakukan sebelum akuisisi.
Session lama wajib Restart Session lalu Run All dari cell pertama.

Pembuatan query dipindahkan sebelum penulisan state jaringan. Folder yang hanya
berisi config/pilot.json dari crash sebelum query dapat dilanjutkan jika hash,
policy dan bbox identik; folder dengan percobaan raw gagal tetap tidak ditimpa.
Konfigurasi job dibandingkan dengan source Kaggle yang ditarik dan tetap sama.

Validasi sesudah fix: 57 tes area (48 lulus, 9 skip GDAL); source helper/packet
notebook identik dan seluruh cell parse. Source dipublikasikan QUICK_SAVE;
full run pada session Kaggle bersih belum diverifikasi oleh perbaikan ini.


## Checkpoint 25 Oktober2026

[Audit akuisisi terbaru](AREA_COVERAGE_ACQUISITION_AUDIT.md) menggantikan batas
retry draft pada catatan sebelumnya: raw gagal kini dapat dilanjutkan dengan
riwayat dan checksum, tanpa mengubah snapshot finalized atau aturan market.
