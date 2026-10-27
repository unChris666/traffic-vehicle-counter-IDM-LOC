# Kaggle: upload terputus dan tampilan hasil

Rilis 0.5.2rc1,27 Oktober2026. Docker ditunda sesuai arahan owner.

Traceback owner berakhir pada `starlette.requests.ClientDisconnect` di parser
upload Gradio. Bukti ini menunjukkan koneksi terputus sebelum body selesai,
bukan kegagalan CUDA/engine. Penyebab jaringan/browser/tunnel tertentu belum
terbukti. Aplikasi menangani disconnect sebagai request gagal400 dengan pesan
pemulihan, tanpa stacktrace ASGI berulang; penanganan ini tidak dapat melanjutkan
body file yang sudah terputus. Untuk file besar gunakan sumber persisten berikut.

## Jalur video yang tidak melewati tunnel upload Gradio

1. Cloud Console → Storage → bucket `aretfak-location-intelligence` → Upload files.
   Simpan misalnya `incoming/TOKO/weekday-pagi.mp4`. Bucket tetap private.
2. Salin URI object: `gs://aretfak-location-intelligence/incoming/TOKO/weekday-pagi.mp4`.
3. Di slot weekday/pagi Gradio, isi **Referensi weekday / pagi** dengan URI itu.
   Kosongkan komponen file pada slot yang sama. Ulangi untuk video lain.
4. Alternatif: upload ke dataset Kaggle private → notebook Add Input → salin path
   `/kaggle/input/.../video.mp4` ke kolom referensi. File lokal lain dibatasi ke
   `/kaggle/working/videos/`; credential/path sembarang tidak diterima.
5. Klik Siapkan video dan geometri, tinjau masing-masing video, simpan tinjauan,
   lalu Periksa kesiapan dan Mulai proses.

Download GCS dilakukan backend dengan generation terikat dan CRC32C. Inspeksi
frame dan hash video asli tetap dijalankan. Maksimal1GiB/file dan2GiB/batch.
Tidak perlu mengganti tabel BQ atau membuat bucket public. Upload browser biasa
masih tersedia; bila terputus, ulangi satu video atau gunakan referensi.
Notebook yang sudah menjalankan engine tidak perlu dihentikan; gunakan versi
baru ketika job selesai. Jangan menganggap Run All selalu mengganti sesi aktif.

## Hasil ringkas

- Traffic: sesi weekday/weekend, waktu, kategori, accepted kendaraan lewat.
  Arah A→B/B→A dan measured/estimated dijumlah hanya untuk tabel ringkas;
  rincian tetap pada tabel BQ asli. Pending/invalid tidak ikut accepted.
- Area: jumlah bangunan yang dialokasikan ke calon toko pada bin radius
  centroid geodesik0–400,>400–800,>800–2000meter. Ini tampilan spasial hasil
  engine, bukan pembagian persentase zona PPAC. Radius tak terpetakan diberi
  baris tersendiri; total bangunan harus tetap cocok hasil engine.
- KK: asumsi owner **1bangunan=1KK;1KK=4penduduk**, bukan sensus terverifikasi.
- POI: kategori dan nama yang tersedia pada snapshot, bukan inventori lengkap.
- Kompetitor/Indomaret: maksimal5terdekat dari peserta engine menurut jarak
  ke calon toko, diurutkan stabil. Bukan klaim lima toko terdekat seluruh dunia
  di luar scope sumber. Kdtk diambil dari native/snapshot lokasi yang unik;
  tidak menggunakan hash internal sebagai kode toko.
- PPAC: Jumlah STD (`STD/hari`). NULL/BLOCKED tetap ditampilkan tanpa angka0.

Peta memiliki satu layer POI dan satu layer Indomaret & Kompetitor (primer,
sekunder dan koridor belum terverifikasi). Pin/radius ikut grupnya, tanpa
checkbox terpisah. Pin/radius calon toko juga tergabung. Perhitungan alokasi,
routing, counting dan PPAC tidak diubah.

Tabel Traffic/PPAC dibaca dari BQ untuk job READY; tabel detail spasial/POI/toko
berasal dari artefak kecil GCS yang terikat hash manifest job BQ. Job lama belum
memiliki artefak detail ini: tabel mentahnya tetap bisa dibuka. Hasil Area baru
menghasilkan `presentation/display-tables.json` dan peta yang dikelompokkan.

## Isi ppac.json

File ini adalah hasil/formula dan jejak evaluasi PPAC, bukan sekadar satu angka:
`execution_status`, `std_total` (STD/hari), breakdown `residential`, `traffic`,
`fasum`, dan `total`, `policy_version`, `result_quality`, serta limitations.
Pada integrasi juga ada parameter/input terikat dan diagnostics.
Jika input belum lengkap atau gate gagal, status BLOCKED dan STD null disertai
alasan. Tidak boleh dibaca sebagai permintaan/penjualan nyata yang tervalidasi.
