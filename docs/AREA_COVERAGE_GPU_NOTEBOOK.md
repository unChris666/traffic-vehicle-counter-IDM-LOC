# Area Coverage GPU V2 — 25 Oktober 2026

Status: **backend kode V2 diimplementasikan; CUDA nyata belum dieksekusi**.
Notebook: https://www.kaggle.com/code/chrisbiran/area-coverage-market-gpu-hybrid/edit
Tidak ada run Kaggle yang diajukan. Semua angka tes di bawah adalah lokal/oracle,
bukan hasil CUDA atau benchmark performa lokasi aktual.

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
| Kesetaraan | Gate CPU reference wajib | Cold validation menghitung CPU baseline juga; ini terpisah dari fallback normal |

V1 sebelumnya hanya offload reachability/pruning. V2 bukan sekadar mengaktifkan
GPU pada notebook: jalur default facade memakai kernel geometri dan weighted
router baru. Tidak mengklaim seluruh operasi menjadi GPU: GEOS buffer, OSM/BQ,
CRS, endpoint scalar, graph assembly, Huff dan rendering masih CPU.

### Geometri

GPU menghitung jarak kandidat secara batch, kemudian interval error numerik
membentuk shortlist. Scalar GEOS pada shortlist menjaga urutan/tie yang sama;
padding numerik bukan perubahan radius bisnis. Tidak mengkuantisasi koordinat.

Candidate geometry dibentuk dengan endpoint/buffer acuan, lalu satu gelombang
kandidat diperiksa batch terhadap footprint/barrier. Kernel mengintegrasikan
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

## Gate sebelum output / Traffic Counter

1. CuPy/device preflight integer V1 lalu V2: distance, holes, MultiPolygon,
   boundary, primitive barrier, weighted paths, one-way dan blocked transitions.
   Dijalankan sebelum OSM/BQ. GPU tidak tersedia/compile gagal -> dependencies
   FAILED; tidak ada silent CPU-only fallback yang diberi label GPU.
2. Bagian 6 GPU -> frozen manifest -> shadow CPU reference dari input yang sama.
   Bandingkan metric buildings, selection/capacity, graph, seluruh entrance,
   routing/path/distance/status dan keputusan per bangunan secara exact.
3. Bagian 8 GPU -> CPU reference market dengan layers/POI yang sama. Bandingkan
   rows termasuk skor Huff, summary, stores, excluded stores, gate, kelompok
   kompetitor dan metadata cluster. Identity/path output berbeda bukan data
   business; field tersebut tidak dipakai sebagai pembanding semantic.
4. Mismatch menyimpan FAIL di gpu_equivalence.json, stage FAILED, output diblok.
   Tidak otomatis mengganti seluruh hasil dengan CPU dan menyebutnya GPU lulus.
5. Handoff memerlukan calculation dan market PASS, actual CUDA V2 preflight,
   output/archive checksum valid dan cleanup berhasil. Tidak memulai traffic.

**Mode notebook saat ini VALIDATE.** Run pertama juga menjalankan CPU reference
penuh sehingga bisa lebih lama daripada GPU saja. Reference yang lengkap disimpan
untuk reopen. Ukur waktu blok GPU dan waktu validation secara terpisah; durasi
Run All mode validasi bukan benchmark percepatan produksi.

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
3. Run All; periksa preflight V2 dan kedua gate PASS. GPU self-test tidak boleh
   dianggap sudah lulus hanya karena tes oracle lokal lulus.
4. Simpan artifact privat, periksa handoff, stop kernel GPU Area, baru jalankan
   Traffic Counter GPU. Tidak menjalankan dua engine bersamaan.

CuPy CUDA12x 13.6.0 dan fastrlock 0.8.3 diinstal jika perlu tanpa upgrade NumPy.
Driver/NVRTC image Kaggle tetap harus kompatibel dan dicek oleh preflight nyata.
Pool dibebaskan tanpa deviceReset; CUDA context berakhir sepenuhnya ketika
proses/kernel Area berhenti. Scheduler produksi lintas proses belum dibuat.

## Pengujian yang benar-benar dijalankan

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

Gate berikutnya: eksekusi owner di Kaggle, verifikasi kedua perbandingan pada
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
