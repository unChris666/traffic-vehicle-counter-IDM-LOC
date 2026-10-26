<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Area modular — 0.3.0rc1, scoped frozen-input candidate

26 Oktober2026, Asia/Jakarta. Melanjutkan audit dan instruksi owner; algoritme
V5 dipertahankan, bukan diganti/tuning untuk mengejar jumlah tertentu.
Status rinci: [release_status.json](../results/area_modularization/20261026/actual_validation/release_status.json).
Bukti agregat disimpan di folder yang sama; data privat tidak dipublikasikan.

## Audit input aktual

Tiga bagian ZIP telah digabung; setiap chunk SHA dan SHA keseluruhan cocok
parts_manifest dan receipt owner. ZIP69.951.800byte,
`f7340d3fd913020ddf661dc87674ff204511095f2494bd9b5b0036d7575bbc8c`.
96member; manifest sumber/network/calculation/market lolos, termasuk canonical
verifier dependency DAG pilot. Semua35source helper cocok freeze yang disetujui.
Tidak commit ZIP, BQ rows, source geodata atau per-building ledger privat ke Git.
Source Python asli diarsipkan untuk lineage dan source/module hashes dicatat.

| Denominator/hasil aktual | Jumlah |
|---|---:|
| Semua source rows dari ekstraksi, bukan semua di dalam lingkaran2km |36.536|
| Selected calculation |17.227|
| ACCEPTED akses skenario |1.577|
| ACCESS_UNVERIFIED |469|
| NO_ROUTE |146|
| NO_VALID_CONNECTOR |1.423|
| OVER_TIME_LIMIT |13.612|
| Bangunan dialokasikan market |1.285|
| Belum dialokasikan, termasuk excluded dan tidak eligible |35.251|
| Bangunan dialokasikan ke calon |22|

`36.536=1.285+35.251`. Calon22 adalah17MARKET_CANNIBALIZATION +5VALID.
Kompetitor1.074 dan Indomaret189; UNVERIFIED290. OTHERS34.961 termasuk
bangunan yang memang tidak eligible, bukan seluruhnya kasus terlewat.
Kapasitas tetap per unit; nilai campur unit tetapnull. Ini bukan jumlah orang,
KK atau pelanggan tervalidasi. Semua hasil tetap skenario estimasi/PARTIAL.

Gate luarOPEN dengan12POI pemicu; peserta1calon+9kompetitor+8Indomaret.
Koridor calon belum diketahui; seluruh9kompetitor UNVERIFIED_CORRIDOR. Ini
keterbatasan baseline yang sengaja dipertahankan, bukan diperbaiki lewat migrasi.

## Yang dipisahkan

`src/traffic_location/location/area/` menyediakan kontrak, facade, adapter,
domain, backend, application/job, runtime dan output. Library berjalan tanpa
menambahkan `notebooks/` ke sys.path. Existing Location LI4/LI5 dan algoritme
Traffic tetap kompatibel; package minor version bertambah karena API Area baru.

- `input_contracts`, `execution_contracts`, `result_contracts`, `artifact_refs`:
  request/result bertipe dan berversi, identity dan status tidak dicampur.
- `facade`: freeze/reopen artefak, execute job, reopen hasil finalized.
- `sources`: legacy baseline adapter, **source bundle tanpa hasil sebelumnya**,
  PBF/provenance recovery, GCS staging dan BQ adapter. BQ `query_bq_layer`
  menerima credentials eksplisit; auth/ingestion bukan aturan domain.
- `domain`: selection, capacity, graph, connectors, routing, gatePOI, market,
  aggregation dan perbandingan metadata yang eksplisit.
- `backends`: CPU geometry/routing dan CUDA geometry/weighted labels. Backend
  tidak beralih diam-diam ketika CUDA tidak tersedia.
- `application`: satu proses per job; lock untuk output yang sama, timeout dan
  penghentian process group, checkpoint diagnostik, publish atomik, cache
  tervalidasi dan penolakan revision conflict. Private patch sementara hanya
  berada di worker job; tidak dipakai sebagai state webserver bersama.
- `outputs`: renderEsri, JSON/CSV/native, ZIP streaming deterministik dan GCS
  publishing dengan bucket terautentikasi yang diinjeksi caller.
- `_kernel`:35helper baseline hasil ekstraksi mekanis;36file termasuk initializer.
  Ini compatibility layer terkunci, bukan dependency pada notebook saat runtime.
  Reorganisasi lebih dalam dapat dilakukan kemudian dengan parity yang sama.

Transformasi kernel hanya import/patch target qualified, pemisahan nama module
versus nama file worker, locator CORE portable, inisialisasi hook credential
opsionalNone dan format AST. Formula/kernels/threshold/batas/tie-break tidak
dituning. Registry: results/area_modularization/source_extraction.json.

## Dua kontrak komputasi yang sengaja berbeda

**V1 — validasi/replay terhadap baseline:** `area_execution_request_v1`,
`operation=replay_recorded` atau `compute_gpu_frozen`, ref`baseline` path+SHA,
core_python,render,timeout_seconds. Recorded replay tidak menjalankan CUDA baru;
GPU frozen menghitung ulang dan membandingkan dengan golden dalam paket.

**V2 — komputasi dari input saja:** `area_execution_request_v2`,
`operation=compute_gpu_sources`, ref`input` path+SHA,core_python,render,
timeout_seconds. `area_source_bundle_v1` berisi konfigurasi, snapshot sumber
OSM, snapshot BQ, runtime profile dan checksums. Tidak berisi pilot/market result.
`create_source_bundle` menyiapkan paket ini tanpa menjalankan analisis. Snapshot
lokasi baru dapat disiapkan ingestion terpisah; engine tidak mensyaratkan
hasil lama sebagai input baru. Uji lokasi baru tetap gate kualitas terpisah.

Contoh internal request (path dan SHA wajib diisi dari artefak aktual):

```json
{
  "schema_version": "area_execution_request_v2",
  "operation": "compute_gpu_sources",
  "input": {"path": "/job/input/source-bundle.zip", "sha256": "<sha256 aktual>"},
  "core_python": "/usr/bin/python3",
  "render": true,
  "timeout_seconds": 3600
}
```

Contract ini internal/trusted job, bukan HTTP body publik yang langsung memberi
user hak memilih executable server. Backend kelak men-stage input dan menetapkan
runtime/credentials/operator policy. CLI: `area-engine execute --request ... --output ...`.
Python: `from traffic_location.location.area import execute,reopen_result`.

Result memisahkan executionSUCCEEDED, kualitasPARTIAL, claim eksperimen,
parity_scope dan gpu_cpu_equivalence. Pada input baru tanpa golden, comparison
status NOT_REQUESTED, bukan PASS palsu. Native rows/scores/reasons/capacity
terikat artefak finalized; `native_domain_sha256` tidak memasukkan code identity,
fingerprint native atau lokasi output yang berubah karena packaging.

## Gate yang diuji

- Tiga proses replay independen pada input aktual: hasil dan result_version
  identik.17.227rute recorded-GPU-label, kapasitas penuh,1.285kelompok skor Huff
  dari contender tersimpan, serta rekonsiliasi36.536baris cocok tepat.
- **Fresh GPU aktual di Kaggle/T4 (version5): PASS.** Graph, konektor, metric
  buildings, routing, decisions cocok; delapanfield market termasuk semua rows,
  scores, stores, excluded, gate dan agregat cocok. Hash domain
  `ccf757ccf20d039e1cab58bf15411ecaf8e16e98d58c516015f465c2321dbcbc`.
- Fresh selection selected/reject_ledger/summary/status/rule_version cocok.
  Kapasitas domain cocok setelah mengecualikan hanya policy_hash/selection_hash
  yang mengikat metadata baru. Routing comparison mengecualikan hanya tiga
  hash provenance dan path building_cache di effective policy; tidak ada
  angka/keputusan/rute/geometry yang dibulatkan atau dihilangkan agar lulus.
- Renderer modular menghasilkan HTML/GeoJSON pada hasil aktual;8script inline
  lulus Node syntax. Ini bukan klaim browser visual regression otomatis.
- Publikasi lokal, cache, failure, lock, timeout, source-only contract, source
  identity, namespace, unknown/null, archive determinism dan injected storage
  boundary memiliki tes. GCS adapter final belum menjalankan CRUD baru di Codex.
- **Source-only GPU RC version 6: PASS.** Engine menghitung dari paket sumber
  tanpa pilot/market result. Oracle eksternal baru dibaca setelah komputasi;
  lima artefak calculation, kapasitas dan delapan field market cocok baseline.
  Hash domain sama dengan version 5. Tidak mengambil ulang OSM/BQ.

Perubahan facade forwarding/ZIP storage/timeout race/result typing sesudah
GPU version5 diuji terarah. Kernels tetap identik; version 6 telah menjalankan RC 0.3.0rc1
pada source-only input dan lulus pembandingan eksternal. Metadata distribusi penuh Kaggle ternyata memuat entry
lama/duplikat; runtime strict memakai source_software/core_software yang dicatat
saat calculation, bukan memilih versi terakhir dari daftar distribusi.

## Ringkasan acceptance criteria migrasi

| Gate | Hasil pada lingkup saat ini |
|---|---|
| M0 freeze sumber dan hasil | VERIFIED, ZIP aktual dan seluruh 35 helper cocok |
| M1 kontrak/facade | V1 replay/golden dan V2 source-only terpisah, bertipe dan berversi |
| M2 adapter | Paket input aktual lolos SHA, manifest, identitas lokasi dan source binding |
| M3 domain/backend | Fresh GPU versi 5 dan 6 cocok baseline; compatibility kernel tetap dipin |
| M4 runtime/job | Proses terisolasi, pengulangan, lock, failure dan timeout diuji |
| M5 renderer/export/storage | Render aktual, ekspor lokal dan adapter storage tersedia; upload GCS baru belum diuji live |
| M6 release candidate | **Lulus untuk lingkup frozen-source V5**, bukan persetujuan produksi |

Suite paket final: 125 tes, 116 lulus, 9 dilewati; suite notebook: 184 tes,
169 lulus, 15 dilewati. Skip tidak dianggap lulus. Tiga replay pada kode RC final
memiliki hasil dan result_version identik. Uji GPU versi 6 memakai wheel yang
seluruh modul Area-nya identik dengan source RC; SHA wheel tercatat dalam
[wheel.json](../results/area_modularization/20261026/actual_validation/wheel.json).

## Koreksi yang ditemukan saat uji sungguhan

1. Kaggle mengekstrak ZIP/gz secara otomatis saat ingestion dataset. Input test
   kini opaque `.bin`, dipulihkan/dibaca setelah SHA cocok; byte asli tetap sama.
2. Digest image CPU dari metadata notebook tidak menyediakan library driver
   meskipun device nodes terlihat. Hostprobe menemukan NVML/libcuda tidak bisa
   dimuat. GPU image Kaggle yang benar memperlihatkan duaT4, driver API13000,
   cuInit0; scientific/core versions tetap dicek ketat sebelum perhitungan.
3. Extractor sempat mengubah literal filename`.py` menjadi module path. Dibetulkan
   dan diberi regresi statis; CLI normalisasi diuji pada sumber aktual sebelum
   mengulang GPU. Tidak memperbaiki angka secara manual setelah mismatch.

## Menjalankan dan membuka kembali

Notebook baru (privat, input sudah attached):
https://www.kaggle.com/code/chrisbiran/area-modular-v5-frozen-parity/edit

Notebook acuan sukses tidak ditimpa. Notebook baru merupakan client tipis yang
memverifikasi wheel/input SHA, setup dependency development, host preflight,
memanggil package dan menampilkan hasil. Input test privat; tidak mengambil ulang
OSM/BQ dan tidak menjalankan Traffic Counter. Baseline lama tetap tersedia.

Untuk deployment kelak dependency dipasang pada build image, bukan di engine.
Extras `area`, `area-gpu`, `gcp` terpisah; GDAL/osmium native tetap dependency OS
operator dan core_python tervalidasi. ZIP/GCS publication terpisah dari kalkulasi;
reopen hasil finalized tidak memerlukan GPU atau re-fetch sumber.

`publish_gcs(root,archive,bucket=...)` memverifikasi root, membuat ZIP di luar
root immutable, lalu menggunakan manifest-last uploader. Caller mengelola
Workload Identity/ADC; tidak ada service-account key yang disimpan dalam paket.
Receipt menyebut engine result version dan content schema. Legacy ZIP baseline
dan ZIP modular memakai reader berbeda; jangan relabel modular output sebagai
baseline V5 lama. BQ/source snapshot refresh adalah versi input baru.

## Batas candidate dan pekerjaan selanjutnya

- Ini candidate untuk frozen-input V5, bukan layanan publik atau validasi bisnis.
- Satu lokasi aktual dan T4 teruji; lokasi lain, admission/scheduling multi-job
  GPU, hard-crash/stale-lock recovery, observability dan API security perlu gate
  integration/deployment. Dua proses berbeda tidak otomatis menata kuota GPU.
- GPU–CPU full equivalence tetap NOT_VERIFIED. Guard handoff baseline memerlukan
  kedua laporan PASS; `NOT_READY` baseline bukan kegagalan hasil Area. Traffic tidak
  dijalankan otomatis atau guard dilonggarkan untuk menutupi hal ini.
- Tiga replay bukan tiga fresh GPU run. Stabilitas fresh GPU lintas mesin/driver
  belum dijanjikan. Paket/config/runtime harus dipin; perubahan source/policy/
  model/environment/renderer yang relevan menghasilkan revision baru.
- 9 kompetitor koridor unknown dan 290 UNVERIFIED perlu review kualitas sumber/
  frontage terpisah. Jangan paksa secondary/accepted hanya untuk menurunkan unknown.
- Data OSM bounded, generic-use residential fallback, izin jalan asumtif,
  Huff equal attractiveness dan kapasitas N1 belum divalidasi perilaku pelanggan.
- Backend/job metadata DB, frontend kedua engine, provisioning/container build
  dan uji GCS baru adalah tahap integration berikutnya. Engine SourceBundle bisa
  menerima source baru yang disiapkan ingestion; pipeline universal lokasi baru
  belum diuji hanya dengan keberhasilan pilot ini.
