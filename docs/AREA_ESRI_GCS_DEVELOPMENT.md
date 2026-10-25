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

## Perbaikan provenance PBF — 26 Oktober 2026

Adapter sebelumnya tidak menyertakan `source_roads_sha256` pada road-derived
features. Sources dinyatakan berhasil, tetapi pemeriksaan calculation
`select_feature_source` menolak relasi sumber sebelum road_graph dimulai.
Ini defect adapter, bukan kegagalan transfer, CUDA atau data bisnis.

Sumber baru menambahkan hash byte file jalan dan memvalidasi provenance sebelum
manifest sumber dipublikasikan. Cache legacy yang manifest-nya utuh, referensi
PBF cocok dan payload roads/features identik dipulihkan ke sibling
`<source_key>-provenance-v2` secara lokal. Parent tetap immutable. Manifest
network dan source dihitung ulang; receipt mencatat parent hash. Recovery
atomik: output belum dianggap tersedia sebelum seluruh validasi lulus.
Checksum yang sudah ada namun salah tidak diperbaiki otomatis. Cache rusak atau
payload berbeda ditolak. Tidak ada download/scan ulang pada jalur recovery.

Notebook menggunakan path return adapter dan memperbarui NETWORK_FOLDER.
Configuration menghitung CODE_SHA baru sehingga job/pilot hasil parsial lama
tidak ditimpa. Guard menampilkan kode provenance aman, trace lokasi dan aksi
pemulihan tanpa payload/kredensial. Cache lama yang salah tetap tersimpan
sebagai bukti. Snapshot/PILOT tidak dimodifikasi manual.

Sesudah membuka draft baru: pertahankan session/disk Kaggle bila masih hidup,
jangan restart/delete `/kaggle/working`; jalankan ulang cell helper dan
configuration (Run All paling mudah agar versi modul konsisten). Cache PBF
valid dipakai ulang; sources akan mencetak recovery revision. Calculation dan
cell sesudahnya kemudian berjalan pada job baru. Bila sesi lama telah berakhir,
cache temporer memang hilang dan PBF perlu ditarik lagi dari GCS.

Regresi lokal178tes:163lulus,15skip. Mencakup PBF sintetis nyata -> adapter ->
fungsi gate calculation; reproduksi bug legacy -> recovery -> gate; reopen,
parent byte-identical, corrupt input, payload berbeda, checksum salah,
referensi PBF berbeda, recovery terputus dan diagnostik kode aman. Ekstraksi
CLI pada fixture di-stub; tidak mengklaim full run nasional/GPU atau upload
GCS baru sudah berhasil. Bukti: results/area_coverage_map/pbf_provenance_validation.
