# Area development — GCS/BQ, Kaggle setup, Esri online

25 Oktober 2026. Keputusan owner menggantikan persyaratan runtime GCS dan
PMTiles nasional pada notebook `area-coverage-market-gpu-hybrid`. Baseline CPU,
algoritma konektor/routing/Huff dan kernel GPU tidak diubah.

## Run All

https://www.kaggle.com/code/chrisbiran/area-coverage-market-gpu-hybrid/edit

1. Refresh draft; restart session jika sebelumnya menjalankan versi runtime
   bundle. Pilih T4x2, Internet ON, aktifkan Secret `LocatioIntelligent`.
2. Run All. Setup memasang versi paket Python yang berbeda/belum ada dan
   memeriksa import melalui proses baru. GDAL/PyProj/osmium native diperiksa;
   apt hanya memasang kebutuhan eksplisit beserta dependency wajib resolver,
   tanpa mengunduh dependency rekursif manual. Timeout/retry dibatasi.
3. GPU preflight nyata wajib lulus. Tidak beralih diam-diam ke CPU-only.
4. Google credentials dibaca setelah setup; HTTP Python analisis dibatasi ke
   Google API. PBF berasal dari `feeder-location-intelligent`, generation dan
   SHA yang dilaporkan owner; tidak ada fallback Overpass. Cache hash valid
   dipakai ulang. Transfer PBF terputus dicoba maksimal tiga kali; checksum
   salah/HTTP403/404 tetap error eksplisit. Ekstraksi nasional pertama masih
   memakai scan CPU; GCS bukan indeks spasial nasional.
5. BQ memakai tabel yang sama; snapshot query disertakan dalam paket replay.
   Missing BQ tidak menjadi nol kompetitor atau hasil lengkap.
6. Peta menyediakan Esri World Imagery (default), World Street Map, dan Tanpa
   basemap. Tile diminta browser langsung ke endpoint Esri, tanpa credentials
   GCP. JS/CSS Folium berasal CDN selama development. Lisensi/atribusi layanan
   tetap berlaku; HTTP200 sampel bukan janji kuota/ketersediaan produksi.
7. Output ZIP mencakup snapshot lokal, konfigurasi, kode, environment paket,
   keputusan, peta dan laporan GPU. File view/arsip terpisah dari versi PMTiles.
   Paket diunggah ke `gs://feeder-location-intelligent/results/area-coverage/<zip_sha>/`.
   Manifest diterbitkan terakhir, setelah CRC32C upload dan size/SHA metadata
   diverifikasi. Receipt lokal `gcs_result_receipt.json` mencatat URI manifest.
   Hak tulis bucket diperlukan. Upload gagal membuat output FAILED/EXPORT_FAILED;
   hasil lokal tidak dihapus dan upload dapat dicoba lagi.

Peta memiliki listener `tileerror` dan pilihan latar kosong; kegagalan tile Esri
bukan alasan mengubah hitungan. Paket analitik bisa direplay tanpa re-fetch;
background Esri/CDN tetap memerlukan koneksi. Tidak mengklaim HTML sepenuhnya
offline atau citra Esri immutable. Hasil analitik tetap skenario eksperimen;
mode GPU_EXECUTE belum membuktikan kesetaraan CPU (VALIDATE gate terpisah).

## Bukti pengujian dan batas

Suite lokal: `python -m unittest discover -s notebooks -p 'area_coverage*tests.py'`.
Suite170tes:155lulus,15skip. Bukti lokal: results/area_coverage_map/esri_validation.
Tes baru mencakup setup cache/missing/native/failure, Folium render+JS syntax,
dua basemap+fallback, cache/tamper, upload gagal/manifest terakhir, retry transfer
serta notebook/helper sync dan AST. Cloud dan instalasi di fixture adalah mock,
bukan akses GCS/BQ atau apt Kaggle nyata. Versi paket eksplisit dicek tersedia di
PyPI; kedua endpoint Esri sampel menghasilkan HTTP200 image/jpeg pada25Okt2026.
Belum ada klaim run PBF nasional+GPU+upload hasil baru selesai. Run All owner
masih diperlukan; layanan eksternal tidak dapat dijamin tanpa gangguan.

Produksi: dependency dipasang saat build image, bukan setiap analisis. PMTiles
nasional menjadi pekerjaan terpisah; Planetiler/Java tidak diperlukan run ini.
