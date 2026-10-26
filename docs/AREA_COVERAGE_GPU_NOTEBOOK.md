<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Area Coverage GPU V2 — 25 Oktober 2026

Status terkini: **smoke sintetis CUDA lulus di Kaggle Tesla T4; validasi lokasi penuh belum dijalankan**.
Notebook: https://www.kaggle.com/code/chrisbiran/area-coverage-market-gpu-hybrid/edit
Smoke terisolasi: https://www.kaggle.com/code/chrisbiran/area-coverage-gpu-connector-smoke
Run smoke tidak memakai BQ/OSM atau menjalankan perhitungan lokasi penuh.
Angka tes lokal, smoke CUDA, dan pengukuran lokasi nyata dibedakan di bawah.

## Business baseline tidak berubah

Notebook CPU dan helper business b84c850 tetap utuh. Hash dicatat di
AREA_COVERAGE_GPU_BASELINE.json. Generator menolak perubahan baseline tanpa
rebase eksplisit. GPU connector adapter dihasilkan dari control flow/graph
assembly CPU beku, dengan implementasi batch yang terlihat dalam notebook.

Kompetitor <=800 m, primer/sekunder/unknown, satu nearest valid entrance,
125 m search bangunan, source snap tanpa batas numerik, barrier/one-way,
unknown tidak mengesahkan akses, clustering node yang identik, biaya konektor,
7 km/jam, Python round<=10, Huff per bangunan, core/zona dan kapasitas tetap.
Tidak mengklaim akurasi, akses legal atau produksi dari skenario eksperimen.

## Target GPU yang kini diimplementasikan

| Pekerjaan | Backend V2 | CPU yang masih dipakai |
|---|---|---|
| Kandidat | Kernel CUDA FP64 point–segment untuk pasangan batch; GPU filter menggunakan padding numerik konservatif | STRtree broad phase untuk kandidat bangunan; canonical scalar distance pada kelompok urutan yang berdekatan |
| Intersection | Kernel CUDA panjang intersection segmen dengan Polygon/MultiPolygon, outer/holes; kernel primitive untuk barrier line/point | Buffer/proyeksi/endpoint construction scalar, serta fallback boundary/kollinear/geometry unsupported |
| Routing berbobot | CUDA FP64 reverse edge-state shortest-path, batch target; arah dan blocked transitions tetap | Ekstraksi path/penghitungan forward sum final; canonical graph search hanya untuk kasus ambigu yang diaudit |
| Kesetaraan | Mode VALIDATE membandingkan CPU reference | Default GPU_EXECUTE tidak menjalankan CPU reference penuh; hasil review belum disahkan untuk handoff |

V1 sebelumnya hanya offload reachability/pruning. V2 bukan sekadar mengaktifkan
GPU pada notebook: jalur default facade memakai kernel geometri dan weighted
router baru. Tidak mengklaim seluruh operasi menjadi GPU: GEOS buffer, OSM/BQ,
CRS, endpoint scalar, graph assembly, Huff dan rendering masih CPU.

### Geometri

GPU menghitung jarak kandidat secara batch, kemudian interval error numerik
membentuk shortlist. Scalar GEOS pada shortlist menjaga urutan/tie yang sama;
padding numerik bukan perubahan radius bisnis. Tidak mengkuantisasi koordinat.

Candidate geometry dibentuk dengan endpoint/buffer acuan. Satu window berisi
32 kandidat per target diperiksa secara spekulatif; hanya prefix sampai kandidat
valid pertama yang disahkan. Kandidat selebihnya tidak membuat cut graph atau
catatan penolakan domain. Ukuran window bukan batas pencarian target.
Inset footprint diratakan dan diunggah sekali; kernel berikutnya memakai indeks
ke data resident GPU. STRtree melakukan broadphase vektor di CPU; intersection
dan keputusan threshold biasa dilakukan GPU. Kernel mengintegrasikan
winding sepanjang segmen untuk mengukur bagian di dalam polygon; holes memiliki
orientasi berlawanan, bukan diisi sebagai footprint. Boundary, vertex-touch,
kollinearitas, dekat epsilon, gate opening dan tipe unsupported menggunakan
predicate GEOS acuan dan dicatat sebagai fallback. Tidak menghapus lubang atau
menyederhanakan polygon untuk mengejar kecepatan.

### Routing berbobot

Kernel melakukan relax berbobot FP64 atas edge states positif. Label memilih
cost, hop count, lalu next-edge rank dari ID edge yang diurutkan. Saat first edge
berbeda, ID pertama menentukan lexical path tie-break. Exact ties ditentukan
secara deterministik di GPU; near-ties numerik diperlakukan konservatif.

Host mengekstrak path dan memeriksa transisi, hop, target serta reverse sum.
Jumlah jarak final memakai forward summation CPU yang sama dengan baseline.
Jika label/pointer ambigu, dekat tie numerik atau sum berbeda, canonical CPU
index dibuat lazy untuk target tersebut. Alasan dan origin/target fallback
tersimpan. Tidak menggunakan float32 atau membulatkan bobot jalan.

Oracle lokal bukan bukti kernel CUDA benar. Karena itu ekuivalensi penuh pada
sumber aktual tetap wajib dan hasil tidak diteruskan jika berbeda.

## Mode eksekusi dan gate Traffic Counter

1. CuPy/device preflight integer V1 lalu V2: distance, holes, MultiPolygon,
   boundary, primitive barrier, weighted paths, one-way dan blocked transitions.
   Dijalankan sebelum OSM/BQ. GPU tidak tersedia/compile gagal -> dependencies
   FAILED; tidak ada silent CPU-only fallback yang diberi label GPU.
2. Mode VALIDATE: bagian 6 GPU -> frozen manifest -> shadow CPU reference dari input yang sama.
   Bandingkan metric buildings, selection/capacity, graph, seluruh entrance,
   routing/path/distance/status dan keputusan per bangunan secara exact.
3. Mode VALIDATE: bagian 8 GPU -> CPU reference market dengan layers/POI yang sama. Bandingkan
   rows termasuk skor Huff, summary, stores, excluded stores, gate, kelompok
   kompetitor dan metadata cluster. Identity/path output berbeda bukan data
   business; field tersebut tidak dipakai sebagai pembanding semantic.
4. Mismatch menyimpan FAIL di gpu_equivalence.json, stage FAILED, output diblok.
   Tidak otomatis mengganti seluruh hasil dengan CPU dan menyebutnya GPU lulus.
5. Handoff memerlukan calculation dan market PASS, actual CUDA V2 preflight,
   output/archive checksum valid dan cleanup berhasil. Tidak memulai traffic.

**Default sekarang GPU_EXECUTE.** Mode ini menjalankan GPU utama tanpa otomatis
mengulang seluruh perhitungan di CPU. CPU tetap menangani endpoint GEOS,
buffer awal, graph assembly, I/O/Huff/render dan fallback numerik yang dicatat.
Peta/tabel/ekspor tersedia untuk review dengan kesetaraan NOT_RUN dan banner
belum tervalidasi. Handoff tetap NOT_READY; NOT_RUN tidak pernah menjadi PASS.
Untuk pembuktian kesetaraan snapshot nyata, ubah satu variabel
`GPU_VALIDATION_MODE='VALIDATE'` di cell konfigurasi, lalu jalankan tahapan sesudahnya.
Mode ini memakai hasil GPU beku yang sesuai dan menghitung pembanding CPU.
ZIP/manifest ekspor dipisahkan per mode agar metadata lama tidak dipakai ulang.

## Artefak / audit

- gpu_preflight.json: device/CUDA/CuPy dan hasil self-test aktual ketika dijalankan.
- <job>/gpu_runtime.json: jumlah pasangan GPU, polygon/primitive queries, weighted
  iterations/targets, query GPU vs fallback, alasan dan referensi kasus fallback.
- <job>/pilot-gpu-weighted.json.gz: label FP64/hop/next-edge terikat hash graph dan
  evidence; worker GDAL memvalidasi binding sebelum memakai label.
- <job>/gpu_equivalence.json: PASS/FAIL dan field mismatch, reference location.
- Peta, tabel, JSON, CSV, GeoJSON dan ZIP tetap tersedia. ZIP juga berisi CPU
  reference, hasil comparison, GPU metadata dan kode yang terlihat.
- <job>/engine_handoff.json: NOT_READY bila mismatch/export/cleanup gagal.

Cold GPU execution vs REOPEN tetap berbeda. Code hashes baru membentuk job baru;
source snapshot yang cocok dapat dipakai ulang. Source/secret BQ tidak diubah.

## Setup owner

1. Buka notebook, accelerator GPU (satu device 0 digunakan), Internet ON.
2. Aktifkan secret `LocatioIntelligent` pada notebook ini bila belum aktif.
3. Restart session agar modul lama tidak tertinggal, Run All. Default GPU_EXECUTE:
   periksa preflight CUDA dan review hasil; kesetaraan masih NOT_RUN.
4. Jalankan VALIDATE untuk kedua gate PASS sebelum handoff. Simpan artifact
   privat, periksa handoff, stop kernel GPU Area, baru jalankan
   Traffic Counter GPU. Tidak menjalankan dua engine bersamaan.

CuPy CUDA12x 13.6.0 dan fastrlock 0.8.3 diinstal jika perlu tanpa upgrade NumPy.
Driver/NVRTC image Kaggle tetap harus kompatibel dan dicek oleh preflight nyata.
Pool dibebaskan tanpa deviceReset; CUDA context berakhir sepenuhnya ketika
proses/kernel Area berhenti. Scheduler produksi lintas proses belum dibuat.

## Pengujian V2 awal (historis sebelum perbaikan batch)

- Workspace tidak mempunyai GPU/CuPy: CUDA **NOT_EXECUTED**.
- Suite Area Coverage: 120 tes; 105 lulus, 15 skip untuk worker terpisah.
- Recurrence weighted diuji dengan oracle Python pada 35 graph random berarah,
  blocked-turn/unknown: hasil path/distance sama dengan canonical CPU untuk
  seluruh pasangan yang diuji. Exact ties deterministik; near-tie memicu audit.
- Ring orientation/holes dan batched adapter diuji dengan oracle CPU, termasuk
  target banyak agar koordinat toko tidak salah memakai titik calon toko.
- Smoke oracle V2 fresh calculation -> mandatory CPU reference -> GPU-adapter
  market -> CPU market PASS pada tiga building SYNTHETIC, dengan beberapa toko.
- Gate mismatch diuji menolak hasil. AST, visible helpers/hash dan CONFIG CPU
  tetap diverifikasi. Artefak: gpu_validation/cpu_oracle_v2_smoke.json,
  actual_cuda_executed=false. Tidak melaporkan hasil CUDA yang belum dieksekusi.

Gate berikutnya: eksekusi lokasi owner di Kaggle, verifikasi kedua perbandingan pada
snapshot nyata, ukur fallback share, waktu per komponen, transfer dan memory.
Jika fallback mendominasi atau konektor scalar masih dominan, belum ada bukti
bahwa target percepatan tercapai. Tidak menjanjikan speedup dari kode saja.

## Perbaikan CompileException routing —25 Oktober 2026

Bug kernel direproduksi memakai NVRTC 12.8 tanpa GPU. `fmax(1,bh)` mempunyai
argumen `(int,int)` dan ambigu antara overload float/double; compile relax.cu
berhenti pada baris tolerance. Diperbaiki menjadi `fmax(1.0,(double)bh)` agar
FP64 eksplisit. Nilai max/hop dan kebijakan numerik tidak berubah.

Lima kernel diuji ulang ke PTX pada compute_75 (T4) dan compute_80: 10/10 PASS.
Ini compile-only, **bukan eksekusi device** atau benchmark GPU. Bukti before/fixed
tersimpan sebagai gpu_validation/nvrtc_compile_before.json dan
nvrtc_compile_fixed.json. Tool maintainer `notebooks/check_gpu_nvrtc.py` dapat
mengulang pengujian dengan standalone library NVRTC; tidak membutuhkan CuPy/GPU.

Notebook sekarang eager-compile semua kernel sebelum functional self-test dan
sebelum OSM/BQ. Hasil per kernel ada di kernel_compilation.json; kegagalan
menyimpan `<kernel>_compile.log` serta compiler_log lengkap di gpu_preflight.json.
Generic auth/BQ exception messages tidak ditambahkan ke diagnostic publik.

dependencies FAILED sengaja memblok configuration dan stage berikutnya.
Memperbaiki source kompilasi membuat preflight bisa diteruskan; gate tidak
bypass dan bukan diubah menjadi sukses palsu. Muat notebook versi terbaru dan
Run All agar cell helper serta hash source diperbarui bersama. Tidak perlu
mengubah izin BQ atau setting accelerator untuk bug overload ini.

Regresi terkini: 123 tes Area Coverage, 108 lulus dan 15 skip. Tiga tes baru
memeriksa persistensi compile log, status fail dan pembedaan compile vs device
execution, termasuk larangan mencetak generic credential exception. Tidak ada
run penuh Kaggle yang diajukan oleh perbaikan ini.

## Perbaikan section 8 —25 Oktober2026

Log owner berulang `remaining=25`, tanpa traceback. Tahap yang macet secara
throughput masih `market_reuse_connectors_add_targets`, sebelum routing atau
CPU reference. Implementasi lama memeriksa satu kandidat per target per wave;
25 target sulit menyebabkan banyak launch kecil serta pengemasan ulang polygon
di CPU. Tidak ada bukti infinite loop dari log tersebut.

Perbaikan: window32 bounded batch4096, urutan kanonik tetap; upload footprint
resident sekali, query broadphase vektor, perhitungan intersection/threshold di
GPU, transfer balik hanya hit/ambigu. Progress mencatat evaluated, canonical
checked, remaining, exhausted dan elapsed. Pencarian target tetap tak dibatasi
secara numerik dalam graph sumber; target tanpa konektor valid tetap dilaporkan.

Bukti aktual version1 smoke privat Kaggle:

- Tesla T4, actual_cuda_executed=true, preflight seluruh kernel PASS.
- Kasus kandidat valid pertama, setelah40 penolakan, dan seluruh70 kandidat
  invalid: graph/connector/rejection/arah identik dengan CPU.
- 402 konektor sintetis ×101 polygon (termasuk holes, batas, owner exclusion),
  dua batch: hasil cocok dengan GEOS. Total17.508 pasangan GPU, 478 fallback
  boundary/threshold; satu upload polygon. Durasi batch0,391s dan0,041s hanya
  untuk fixture ini, bukan benchmark lokasi Jakarta atau pembanding speedup CPU.
- Lokal127 tes:112 lulus,15 skip; oracle calculation/market setara CPU;
  kompilasi NVRTC compute75/80:10/10 PASS.

Artefak: `results/area_coverage_map/gpu_validation/kaggle_resident_smoke.json`,
`kaggle_resident_kernel_compilation.json`, `nvrtc_resident_compile.json`,
`cpu_oracle_resident_smoke.json` dan `retained_section8_log.json`.
CPU baseline tidak berubah. Percepatan456 target nyata, fallback share lokasi,
dan validasi market penuh masih belum diukur. GPU utilization tidak dijanjikan
100%; CPU masih menyiapkan data dan membentuk endpoint kanonik.

## Pemulihan source OSM —25 Oktober2026

Owner melaporkan `roads_tile_2/4`, `roads_tile_3/4`, lalu sumber FAILED dengan
RuntimeError. Ringkasan ini tidak memuat HTTP status/exception endpoint. Hasil
unduhan diagnostik dari API Kaggle juga tidak berisi receipt kegagalan session
tersebut; penyebab spesifik (misalnya502 versus ReadTimeout) tetap UNKNOWN.
Kode sumber menunjukkan penghentian segera saat tile jalan tidak tersedia,
sementara guard notebook menyembunyikan detail exception generik untuk menjaga
credential. Ini adalah kelemahan recovery/observability yang diperbaiki, bukan
bukti kegagalan kernel GPU.

Adapter `location_intelligent_gpu_sources.py` khusus notebook GPU:

- Memakai transport dan cache baseline; tanpa mengubah helper CPU beku.
- Retry terbatas untuk error sementara; timeout/resource error atau HTTP500/502/
  504 dapat membagi tile jalan yang gagal, maksimum2 tingkat tambahan.
- Retry503/429 maksimum sekali setelah jeda;403 tidak dicoba berulang.
- Maksimum16 request-chain per pemanggilan dan pemeriksaan budget240detik
  sebelum memulai chain baru; request yang sedang berjalan tunduk timeout HTTP.
- Tile berhasil dipakai ulang, receipt/checksum tetap diverifikasi; request anak
  berikutnya memakai snapshot date yang sama. Parent yang sudah mulai dipecah
  melanjutkan anak tanpa mengulang request parent. Konflik versi tidak digabung.
- Enam query fitur eksternal tetap dilewati dalam ROADS_ONLY_EXPERIMENT.
- Layar menampilkan error code, endpoint/HTTP/error type serta lokasi
  `acquisition_status.json` dan `network_roads_only_transport_status.json`.
  Readiness menyimpan referensi tersebut; pesan/key credential tidak dicetak.

Server eksternal tetap dapat unavailable; adapter tidak mengubah data jalan
yang belum lengkap menjadi kosong/sukses. Perhitungan GPU tetap BLOCKED sampai
input utama tersedia. POI opsional tetap terpisah dari kebutuhan jalan wajib.
Ini perubahan transport saja; aturan akses, biaya, geometri/Huff tetap sama.

Pengujian offline140 tes:125 lulus,15 skip. Termasuk simulasi502/503, retry
pulih, exhaustion budget, subdivisi bertingkat, reuse tile lama secara byte,
date pinning, conflict/checksum, diagnostik rusak, restore hook, serta cell GPU
sources gagal -> calculation BLOCKED/tidak ada false zero. Angka ini bukan bukti
server OSM pada session owner sudah pulih. Kernel CUDA tidak diubah atau di-run
ulang untuk perbaikan transport ini. Belum menjalankan lokasi penuh.

Gunakan session Kaggle yang sama, muat source/helper terbaru, jalankan konfigurasi
dan sources kembali (Run All juga dapat memakai cache source yang sama).
Jangan mengganti SOURCE_REVISION untuk retry biasa: source key dipertahankan.
Job perhitungan tetap berversi menurut code hash; snapshot lengkap yang sudah
dibekukan tidak di-fetch ulang. Simpan paket source lengkap agar reuse tetap
tersedia jika session Kaggle berakhir.
