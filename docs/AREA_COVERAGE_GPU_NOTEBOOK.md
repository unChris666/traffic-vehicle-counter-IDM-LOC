# Notebook GPU hibrida — 25 Oktober 2026

Status: implementasi/adaptor diuji dengan oracle CPU; **CUDA aktual belum diuji**.
Tidak ada run Kaggle yang diajukan. Notebook baru disimpan sebagai draft privat
QUICK_SAVE: https://www.kaggle.com/code/chrisbiran/area-coverage-market-gpu-hybrid/edit

## Batas port dan baseline

`notebooks/area_coverage_market_gpu_2km.ipynb` adalah notebook baru dengan semua
helper terlihat dalam cell writefile. Tidak memakai ZIP/bootstrap tersembunyi.
Notebook CPU tetap byte-identical. Baseline business commit b84c850 dan hashes
helper tercatat pada AREA_COVERAGE_GPU_BASELINE.json. Generator menolak perubahan
baseline CPU tanpa rebase eksplisit. CONFIG/MARKET_CONFIG serta semua helper
CPU disalin tanpa perubahan arti/rumus: kompetitor <=800 m, primer/sekunder,
nearest valid entrance, satu entrance, node clustering, barrier/oneway, unknown,
core/zona, 7 km/jam, Python round<=10, Huff dan satuan kapasitas.

Ini **bukan port seluruh kalkulasi ke GPU**. GEOS/GDAL, pencarian/validasi
konektor, proyeksi, shortest-path numerik kanonik, Huff dan peta masih CPU.
Memilih accelerator GPU saja tidak mempercepat operasi Shapely/NetworkX.
Percepatan keseluruhan belum dibuktikan; jika konektor tetap mendominasi, backend
ini belum menyelesaikan bottleneck tersebut. Tidak ada janji speedup atau
kesiapan produksi hanya dari notebook tersedia.

## Pekerjaan GPU nyata yang disiapkan

CuPy RawKernel melakukan fixed-point reachability **integer**, secara batch dan
berarah, tanpa menambahkan edge balik atau mengubah izin. Profil tanpa larangan
belok menggunakan graph node sederhana. Jika pembatasan belok ada, graph
node-entry/edge-arrival memelihara transisi edge; tidak boleh reset previous-edge
pada simpang sehingga larangan belok tidak hilang.

1. Hitung scope yang mungkin dicapai dari seluruh origin connector. Pada scope
   potential, UNKNOWN boleh menjelaskan ketidakpastian, bukan menerima
   akses. Semua path dari origin yang relevan tetap ada dalam subgraph.
2. Hitung reverse reachability target secara batch memakai edge yang allowed
   True saja. Target yang tak terjangkau tidak memicu pencarian numerik sia-sia.
3. CPU menjalankan algoritme jarak/hop/edge-ID tie-break baseline pada scope
   tersebut. Tidak ada konversi bobot float32, pembulatan/quantization jarak,
   atau penggantian rule threshold dengan hasil GPU yang mendekati saja.

GPU dapat memangkas pekerjaan ketika graph mengandung bagian tidak relevan.
Pada graph yang seluruhnya relevan, transfer/penyiapan GPU dapat menjadi
**overhead**. Report mencatat original_edges/retained_edges, iterasi dan waktu;
benchmark lokasi aktual diperlukan sebelum menyimpulkan manfaat.

## Kontrak eksekusi

- `GPU_REACHABILITY_CANONICAL_CPU_V1`; device default 0, satu GPU cukup. Tidak
  mengklaim memakai kedua T4 paralel. Tidak memulai Traffic Counter.
- GPU wajib: tanpa CuPy/device/kernel preflight yang lulus, dependencies FAILED;
  tidak ada fallback diam-diam ke CPU yang dilabeli GPU.
- Jika CuPy belum ada, instal cupy-cuda12x==13.6.0 dan fastrlock==0.8.3 dengan
  --no-deps agar NumPy/scientific stack tidak diganti. Kedua rilis diverifikasi
  tersedia di PyPI, bukan klaim versi terbaru. Image Kaggle tetap harus punya
  driver/CUDA/NVRTC yang kompatibel; kernel preflight adalah pemeriksaan aktual.
- Preflight GPU membandingkan traversal integer dengan oracle CPU pada graph
  kecil (one-way, isolasi, self-target, turn transition), sebelum fetch OSM/BQ.
- Perhitungan bagian 6 tetap memvalidasi input dan evidence asli. Worker GDAL
  terpisah menerima scope yang terikat hash graph/evidence; patch routing hanya
  berlaku di worker tersebut, bukan mengubah modul sumber baseline.
- Bagian 8 memakai adaptor market yang scoped dan dipulihkan pada finally.
  Facade hanya untuk job berurutan, bukan layanan paralel dalam satu interpreter.
- CONFIG sumber tetap sama; namespace output GPU terpisah. Code hashes GPU masuk
  identitas job; software/device/preflight/scope berada pada metadata runtime,
  bukan angka domain nondeterministik. Hasil REOPEN berbeda dari fresh execution.

## Output dan urutan engine

Output domain tetap result.json, market_buildings.csv, GeoJSON, peta interaktif,
manifest dan ZIP privat termasuk source snapshots. ZIP GPU juga menyimpan
metadata GPU dan scope. BQ secret/key tidak disimpan dalam paket.

- `gpu_preflight.json`: apakah CUDA nyata/driver/kernel berhasil, nama device,
  versi CuPy/CUDA/Python. Jangan membaca hasil pengujian oracle sebagai CUDA.
- `<job>/gpu_runtime.json`: backend, traversal, jumlah edge dan actual_cuda_executed.
- `<job>/engine_handoff.json`: READY_FOR_TRAFFIC_COUNTER hanya setelah stage output
  berhasil, checksum market/archive diverifikasi, dan cleanup GPU berhasil.
  Partial business result tetap PARTIAL; ready adalah kesiapan teknis output.
  Export gagal/cleanup gagal menjadi NOT_READY. Tidak menjalankan traffic.

Urutan yang dituju: Area selesai dan artifact tersimpan -> lepaskan pool GPU ->
akhiri proses/kernel Area -> Traffic Counter GPU. Pool dibersihkan tanpa
`deviceReset` yang dapat merusak context library lain; CUDA context kecil dapat
bertahan sampai proses berakhir. Untuk notebook Kaggle terpisah, **stop sesi GPU
Area dahulu** sebelum memulai Traffic. Queue/exclusive-worker produksi lintas
proses belum diimplementasikan oleh notebook ini.

## Langkah owner

1. Buka notebook baru, pilih accelerator GPU (T4/T4x2 sesuai ketersediaan), Internet ON.
2. Add-ons -> Secrets: aktifkan `LocatioIntelligent` untuk notebook baru.
   Memiliki secret di notebook lama tidak otomatis mengaktifkannya pada notebook baru.
3. Run All; periksa GPU_PREFLIGHT, readiness dan peta. Simpan/download ZIP privat.
4. Periksa engine_handoff.json, stop sesi Area, lalu jalankan Traffic Counter GPU.

Jangan menjalankan keduanya bersamaan untuk membandingkan performa. Tidak perlu
mengubah secret/key ke dalam cell; autentikasi BQ baseline tetap sama.

## Validasi yang benar-benar dijalankan di Codex

- Tidak ada nvidia-smi maupun CuPy/GPU pada workspace; CUDA **NOT_EXECUTED**.
- Suite Area Coverage: 114 tes; 99 lulus, 15 skip karena kebutuhan worker GDAL.
- Tes GPU-adaptor memakai oracle CPU eksplisit, bukan fallback produksi. Pada
  30 graph random berarah/unknown/blocked-turn, reachability, hasil path lengkap
  dan potential reachability cocok dengan baseline kanonik untuk seluruh
  pasangan origin/target yang diuji. Scope basi ditolak; tanpa CuPy gagal jelas.
- Matriks market, gate POI, immutability, notebook AST/helper hashes, business
  CONFIG dan output-failure handoff diuji. Semua cell notebook belum dieksekusi.
- Smoke SYNTHETIC dengan scope oracle: selection, capacity, routing, decisions,
  graph, connectors serta semantic market sama dengan CPU. Manifest diverifikasi.
  Evidence: results/area_coverage_map/gpu_validation/cpu_oracle_smoke.json,
  dengan actual_cuda_executed=false. Ini tidak membuktikan kernel CUDA berjalan.

Gate berikutnya adalah Run All owner setelah Add-ons siap: CUDA preflight,
kesetaraan artifact pada sumber beku, durasi end-to-end dan resource aktual.
