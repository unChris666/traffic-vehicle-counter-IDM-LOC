# Audit modularisasi Area Coverage — baseline OSM/GPU/Market V5

26 Oktober2026, Asia/Jakarta. **AUDIT SAJA; tidak mengimplementasikan migrasi.**
Acuan source repository: `9e31f46`; notebook:
https://www.kaggle.com/code/chrisbiran/area-coverage-market-gpu-hybrid/edit.
Audit ini memperbarui lingkup audit24Oktober yang masih berbasis N1 offline.
Traffic Counter dan Recount lama tidak diubah.

## Kesimpulan

**READY_FOR_STAGED_MIGRATION**, dengan gate pembekuan hasil aktual sebelum
memindahkan algoritme domain. Keberhasilan notebook adalah baseline eksekusi,
bukan bukti bahwa modularisasi selesai, GPU=CPU pada lokasi aktual, seluruh
lokasi didukung atau hasil telah tervalidasi untuk keputusan bisnis.

| Lingkup | Keputusan audit |
|---|---|
| Pemetaan boundary, facade, kontrak dan rencana migrasi | Siap dirancang dari source sekarang |
| Memulai ekstraksi algoritme dengan bukti parity | Bersyarat: baseline output aktual wajib dibekukan dahulu |
| Package Location yang ada | Reuse selektif; belum mencakup engine terbaru secara end-to-end |
| Stabilitas fresh GPU tiga pengulangan | Belum terverifikasi untuk run berhasil yang dilaporkan owner |
| CPU/GPU equivalence lokasi aktual | Belum terverifikasi; default notebook GPU_EXECUTE tidak menjalankan full CPU reference |
| Deployment multi-job/container/UI | Belum lulus; bukan keluaran audit ini |

## Bukti, metode dan batas

- **FAKTA owner:** notebook berhasil dijalankan. Tidak mengarang jumlah bangunan,
  alokasi, durasi, status input lengkap atau URI hasil dari pernyataan tersebut.
- **PEMERIKSAAN LANGSUNG:** source Kaggle dipull dan seluruh cell source identik
  dengan notebook repo; AST seluruh code cell valid. Ada46code cells,
  35helper Python yang di-writefile, total7.753baris helper. Cell output pada
  source yang dipull kosong.
- **PEMERIKSAAN LANGSUNG API:** kernels_status COMPLETE, failureMessage=null.
  Listing session output mengembalikan daftar kosong, tanpa halaman selanjutnya.
  Status API tidak membuktikan run tertentu memakai policy V5 atau seluruh
  stage sukses. Output ZIP/receipt GCS terbaru belum dibaca dalam audit ini.
- **BUKTI TES HISTORIS yang dibaca:** suite terakhir184tes,169lulus,15skip pada
  results/area_coverage_map/market_scope_validation. Audit tidak menjalankan ulang
  tes, acquisition, inference, routing, allocation atau upload hasil engine.
- Dibaca: AGENTS/workflow/reproducibility, audit lama, package Location,
  helper source/PBF/GPU/routing/market/map/storage dan gate validasi.
- Inventory source hash dan hasil listing disimpan pada
  results/area_coverage_map/modularization_audit_20261026.

## Algoritme dan kebijakan efektif yang harus dibekukan

| Bagian | Baseline efektif; tidak ditafsirkan ulang saat migrasi |
|---|---|
| Data analitik | PBF OSM Indonesia GCS generation/bytes/SHA dipin; ekstraksi lokal native CPU; BQ snapshot per job |
| Provenance | Road-derived feature mengikat checksum file jalan; recovery legacy ke sibling immutable, parent tetap utuh |
| Geometri | CRS metrik eksplisit; footprint/hole, area, representative point dan aturan batas asli |
| Seleksi residential | Luas>=36m² dan<550m²; keputusan source/POI terhadap penggunaan bangunan tetap sama |
| Zona | 100/400/800/2000m; radius seleksi bukan bukti akses jaringan |
| Jalan | Radius3km, topology node asli; profil BARRIER_ONEWAY_EXPERIMENT_V1 sesuai konfigurasi owner |
| Akses | SINGLE_NEAREST_VALID_V1, arah/biaya/precision/inset/batas125m untuk bangunan sesuai effective policy; tidak kembali ke highest-class legacy |
| Target toko | Pencarian akses valid tanpa batas snap numerik; masih dapat mahal; jangan tambah cutoff saat migrasi |
| Routing | Motor-only,7km/jam seluruh segmen, biaya konektor dan aturan `round(menit)<=10` Python half-even dipertahankan |
| Peserta market | Kompetitor dan Indomaret<=800m, primer/sekunder dan core masing-masing tetap; inventory BQ2km bukan semua peserta |
| POI gate V5 | Pemicu<=400m, tanpa konektor/routing POI; missingPOI UNKNOWN; zona800–2000m memerlukan gate terbuka |
| Restoran | Minimal5bangunan unik,>=40m², complete-link<=200m dan koridor bersama; nama/ref jalan terdekat adalah asumsi geometris, bukan akses |
| Huff | Equal attractiveness, beta2, jarak rute, satu footprint ke skor tertinggi; zero-distance dan tie-break baseline tetap |
| Kapasitas | Referensi N1 dipisah per unit; bukan populasi; unknown/null dan unit belum disahkan tidak dipaksa nol |
| Tampilan | Esri Imagery/Street online, layer analitik OSM tersimpan; kegagalan tile tidak mengubah kalkulasi |
| Publikasi | ZIP+checksum, objek GCS immutable, manifest terakhir; STORED menyatakan persistensi, bukan validasi bisnis |

Ada banyak config legacy dengan provider Overture/Overpass dan profil lama.
Sumber kebenaran migrasi adalah **effective frozen config dari run aktual**,
bukan default lama yang kebetulan tersedia pada module package.

## Input → proses → output

1. Request: koordinat/CRS, revision kebijakan, execution profile, snapshot refs,
   environment/backend identity dan output destination. Secret tidak masuk request.
2. Prepare: staging GCS terverifikasi; ekstrak PBF; normalisasi; snapshot BQ;
   validasi coverage/provenance. Refresh sumber adalah operasi terpisah.
3. Calculation: seleksi/kapasitas → graph → konektor → routing → status per baris.
4. Allocation: verifikasi calculation → gate radialPOI400 → peserta toko800 →
   akses toko → rute per access node → alokasi per bangunan → rekonsiliasi.
5. Presentation: peta/tabel/CSV dari hasil tersimpan, bukan menghitung ulang.
6. Publication: arsip berisi input lokal/config/code/environment/audit/output,
   verifikasi upload, baru manifest completion dan receipt GCS.

Kontrak request versi baru perlu memisahkan refs input immutable dari policy,
execution/backend dan presentation. Kontrak result memisahkan:
`execution_status`, `data_quality_status`, `equivalence_status`,
`reproducibility_status`, `publication_status` dan `claim_type`.
Jangan memetakan PARTIAL menjadi FAILED atau menghitung unknown sebagai nol.
Huff/kapasitas adalah **ESTIMATED_SCENARIO**. Luas/jarak adalah turunan geometri
sumber, bukan observasi fisik tervalidasi; jangan memakai label measured Traffic
untuk memberi kesan perhitungan Area telah diverifikasi lapangan.

Setiap row mempertahankan building/source ID dan source_row_index, selected/
excluded/rejected, access_status/reason, market_status/reason, winner, semua
scores, route/connector refs, area/type, kapasitas per unit serta evidence gate.
Summary menyertakan denominator dan assigned/unassigned; unknown tetap eksplisit.

## Temuan kesiapan dan risiko

| ID | Temuan pada source | Risiko | Penanganan migrasi |
|---|---|---|---|
| P0-01 | Belum ada ZIP/manifest run terbaru yang diperiksa pada audit ini | Tidak ada golden output untuk membuktikan parity | Retain dan verifikasi paket aktual sebelum domain dipindah |
| P0-02 | market_scope dan gpu_runtime mengganti fungsi module-global sementara | Concurrent job dapat saling memakai backend/policy | Tahap awal satu proses per job; target dependency injection eksplisit |
| P0-03 | RLock menserialkan adapter, tetapi pemanggil canonical lain belum tentu memakai lock yang sama | Lock bukan isolasi seluruh layanan | Jangan menjalankan multi-job dalam satu interpreter sebelum gate isolation |
| P0-04 | Package SnapshotAdapter mensyaratkan li4_package_v1 | Tidak bisa langsung membaca area_market_result_v1/ZIP terbaru | Adapter versi baru, jangan relabel paket baru sebagai LI4 |
| P0-05 | Notebook globals/sys.path/module reload dan /kaggle/working serta /usr/bin/python3 | CLI/container tidak portable | Context per job, locator runtime terinjeksi, notebook menjadi client tipis |
| P0-06 | Backend GPU dan fallback CPU memiliki audit; default equivalence NOT_RUN | Eksekusi berhasil dianggap parity | Bekukan profil GPU; uji parity antarversi pada backend sama; CPU=GPU gate tersendiri |
| P0-07 | CODE_SHA calculation mengecualikan satu adapter allocation untuk reuse | Pengecualian luas dapat membuat cache salah | Identity per tahap dengan dependency graph eksplisit; hash adapter wajib pada allocation |
| P0-08 | Bootstrap pip/apt + Google guard + UI berada dalam alur notebook | Instalasi/credential/network bocor ke domain | Setup hanya development/build; GCS/BQ adapter terpisah, browser Esri terpisah |
| P1-01 | Stage status/global MARKET dapat direset oleh cell sebelumnya | Resume salah/hasil lawas ditampilkan | Checkpoint per job dengan upstream fingerprint dan commit atomik |
| P1-02 | Snap target tidak dibatasi dan penolakan geometri bisa banyak | Latensi tidak terjamin | Catat target/rejection/time; optimasi terpisah dari ekstraksi algoritme |
| P1-03 | Adaptor Esri merender lewat patch folium.Map | Reentransi, global mutation dan coupling renderer | Renderer menerima pilihan basemap eksplisit; uji layer/tooltip/event tidak berubah |
| P1-04 | Scope filter Indomaret memakai label legacy OUTSIDE_COMPETITOR_CALCULATION_RADIUS | Audit mudah disalahartikan | Pertahankan native reason; boundary tambahkan normalized reason+kind, versi eksplisit |
| P1-05 | Snapshot BQ live dapat berubah; Esri/CDN juga dapat berubah | Run ulang berkoordinat sama berbeda | FROZEN snapshot default untuk replay; refresh versi baru; basemap tidak bagian angka |
| P1-06 | Checkpoint parsial/failed harus dipisah dari artefak final | Retry menimpa baseline atau meloloskan hasil belum selesai | Pending/failed job tidak dipublikasikan sebagai finalized; retain diagnostic |

Batas sumber OSM/izin akses asumtif, footprint yang belum dipetakan, frontage
unknown, interpretasi penggunaan bangunan, dan validasi kapasitas/Huff adalah
pekerjaan kualitas terpisah. Tidak harus selesai agar ekstraksi kode dapat
berjalan, tetapi tidak boleh hilang dari hasil modular.

## Target pemisahan yang diusulkan

Lokasi: `src/traffic_location/location/area/`, terpisah dari
`src/traffic_location/traffic/`. Existing Location N1/LI4/LI5 tetap kompatibel;
reuse selection/capacity hanya setelah kesetaraan semantics terbukti.
**29file fungsional** berikut adalah rancangan, belum dibuat; initializer
subpackage, schema JSON, tests, fixture dan build files dihitung terpisah.

| Kelompok | File relatif di area/ | Tanggung jawab |
|---|---|---|
| Public boundary (7) | `__init__.py`, `facade.py`, `input_contracts.py`, `result_contracts.py`, `artifact_refs.py`, `config.py`, `validation.py` | API kecil, input/output bertipe dan berversi, refs, policy, validasi; contracts tidak mengimpor runtime/provider |
| Sources (4) | `sources/gcs.py`, `sources/pbf.py`, `sources/bigquery.py`, `sources/snapshots.py` | Transfer/CRC/SHA, PBF+recovery, query snapshot, format+coverage/provenance |
| Domain (8) | `domain/selection.py`, `domain/capacity.py`, `domain/graph.py`, `domain/connectors.py`, `domain/routing.py`, `domain/market.py`, `domain/poi_gate.py`, `domain/aggregation.py` | Aturan yang dibekukan, tanpa auth/pip/HTML/provider HTTP |
| Backends (4) | `backends/geometry_cpu.py`, `backends/geometry_gpu.py`, `backends/routing_cpu.py`, `backends/routing_gpu.py` | GEOS/GDAL/CUDA, precision/fallback/tie-break efektif; interface terinjeksi |
| Application (2) | `application/pipeline.py`, `application/checkpoints.py` | Urutan stage, context/state/job, resume/cancel/cleanup |
| Outputs (3) | `outputs/map.py`, `outputs/export.py`, `outputs/storage.py` | Hasil tersimpan → Esri/layers, CSV/ZIP, manifest-last GCS |
| Runtime (1) | `runtime/environment.py` | Preflight, executable/device/version; tanpa instalasi saat engine run |

Dependensi diarahkan: contracts/refs → config/validation → domain interfaces;
backends/sources/outputs mengimplementasikan interface; application melakukan
komposisi; facade/notebook/CLI memanggil application. Domain tidak mengimpor
facade/notebook. Notebook tidak menyisipkan source lewat writefile pada target
akhir. Tidak ada satu config/contracts yang menampung semua tanggung jawab.

## Rencana migrasi dan acceptance criteria

| Tahap | Pekerjaan | Gate sebelum lanjut |
|---|---|---|
| M0 Freeze | Retain paket aktual, source V5/helper hash, input manifests, BQ snapshots, configs, GPU/runtime, gate/rows/summary, HTML/CSV dan GCS receipt | Manifest+generation+SHA lolos; semua source row direkonsiliasi; versi run terikat source aktual |
| M1 Contracts/facade | Skema typed request/result/ref, result profile dan operasi reopen/replay/refresh | Invalid/unknown version ditolak; PARTIAL/null/unit/status tidak kehilangan makna; package existing tetap kompatibel |
| M2 Adapters | GCS/PBF+provenance/BQ/config adapter, path locator | Membaca input lama tanpa re-fetch/mutasi; corruption/missing/forbidden path ditolak; recovery idempotent |
| M3 Domain/backend | Ekstrak selection/capacity/graph/connectors/routing/gate/market/aggregation bertahap | Setiap langkah dibandingkan golden; semua discrete rows dan agregat sama; tidak tuning algoritme |
| M4 Runtime | Context per job, injection, proses terisolasi, checkpoint | A→B→A, retry, cancel, failure, duplicate job tidak mengubah/mencampur hasil; cleanup GPU nyata |
| M5 Presentation/persistence | Renderer Esri, tabel, export, GCS | Map/CSV/JSON reconcile; render ulang tidak mengubah domain; upload gagal bukan sukses; reopen tanpa compute/provider sumber |
| M6 RC | Package/CLI + thin notebook, image build terpisah | Tiga replay independen representatif stabil, failure suite, dependency lock/runtime record, source extraction registry dan rollback tersedia |

Tidak ada pergantian backend atau penghilangan fallback bersamaan dengan migrasi.
Hash source/path/result_version memang berubah saat dipaketkan. Bandingkan
payload domain yang didefinisikan, bukan memaksakan hash kode versi baru sama
atau mengabaikan perubahan event/row yang berpengaruh terhadap kalkulasi.
ZIP timestamp/HTML random ID/metadata upload bukan angka domain; tetap diuji
integritas dan pemetaannya. Waktu/resource dilaporkan, belum diberi SLA rekaan.

## Matrix verifikasi wajib

- Seleksi: universe/source row, ID, selected/excluded/rejected, area/type,
  capacity formula+unit+unknown; total campur unit tetap null.
- Graph/konektor: node/edge/arah/weights/permission, entrance/snap/footprint
  intersection,125m, posisi pada ruas, endpoint, hole dan boundary.
- Routing: path/tie-break, source/target connector cost, unknown/no-route,
  waktu full precision dan Python round khusus10.49/10.5/10.5001.
- Market: scope toko799.99/800/800.01, POI399.99/400/400.01, gate
  OPEN/CLOSED/UNKNOWN, restoran4vs5 dan area39.99/40, tidak ada routingPOI.
- Alokasi: core/overlap/primary-secondary, Indomaret boundary400/800, skor
  Huff/zero distance/tie, winner/building/count dan assigned+unassigned=rows.
- Isolasi: dua koordinat bergantian dan concurrent proses; restore setelah
  exception; state GPU/global tidak diwariskan antarjob.
- Failure: missing/corrupt source, salah generation/CRS/extent, snapshot lama,
  transfer putus, dependency/CUDA gagal, BQ unavailable, Esri unavailable,
  export/upload/manifest gagal, retry tanpa duplikasi/publikasi parsial palsu.
- Parity: baseline versus modular pada frozen input+backend sama. GPU versus
  CPU dan fresh versus replay adalah eksperimen terpisah, bukan satu klaim.

## Langkah selanjutnya

Bekukan paket hasil sukses terbaru dari GCS (URI receipt, generation, SHA) dan
verifikasi isi paket; ini bisa dilakukan mandiri bila akses tersedia, tanpa
meminta polygon atau mengulang full analysis. Karena API output saat audit
kosong dan GCS receipt belum tersedia di workspace, **golden output terbaru
belum dinyatakan terverifikasi**. Setelah gate M0, lakukan kontrak/facade dan
adapter dahulu. Audit ini tidak mengubah engine/notebook atau memulai M1–M6.
