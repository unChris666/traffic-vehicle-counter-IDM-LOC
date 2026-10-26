<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Audit kesiapan modularisasi Traffic Counter

Tanggal: **24 Oktober 2026, Asia/Jakarta**. Status: **DRAFT — MENUNGGU PERSETUJUAN AUDIT**.
Scope: audit kode, batas tanggung jawab, rencana migrasi dan acceptance criteria.
Implementasi migrasi berikutnya dimulai setelah audit ini disetujui.

Klarifikasi [batas review dan kontrak](TRAFFIC_REVIEW_CONTRACT_BOUNDARIES.md)
memisahkan source-context review dari candidate adjudication; typed contracts/config
memiliki dependency DAG yang wajib diuji.

Rincian alur input–output serta proposal **37file fungsional +6package initializer**
tersedia pada [TRAFFIC_FLOW_AND_FILE_PLAN](TRAFFIC_FLOW_AND_FILE_PLAN.md).
Jumlah tersebut adalah target package Traffic, bukan total repo atau perintah
rewrite sekaligus. Dokumen rincian ini menjadi lampiran audit untuk persetujuan.

## 1. Kesimpulan dan dasar penilaian

**REKOMENDASI:** siap merencanakan migrasi bertahap dengan menjaga kompatibilitas.
Belum layak menyatakan seluruh engine sudah modular untuk aplikasi produksi.
Package awal sudah ada; pekerjaan berikutnya memisahkan dependensi dan operasi
yang masih tercampur, bukan memulai engine dari nol atau mengganti algoritme.

**ASUMSI PERENCANAAN DARI OWNER:** alur fresh measurement → counting modular →
batch delapan video → agregasi kategori×arah×measured/estimated → pengujian
konfigurasi terkunci dianggap berhasil untuk menyusun audit ini. Asumsi tersebut
tidak mengubah status eksperimen, tidak menghasilkan angka T7SL baru, dan bukan
bukti bahwa semua acceptance criteria migrasi sudah lulus. Sebelum menetapkan
golden migrasi, berkas hasil aktual dan pemeriksaan integritas tetap diperlukan.

**FAKTA KODE:** `src/traffic_location/traffic/` sudah menyediakan kontrak,
adapter notebook/fresh, pipeline counting, agregasi batch, renderer dan worker
inference. `src/traffic_location/location/` merupakan engine terpisah di repo sama.
Cabang kerja yang sebelumnya dipublikasikan adalah
`codex/engine-adapters-20261023`; audit ini tidak mengizinkan merge ke main.

**BUKTI HISTORIS TERBATAS:** review 23 Oktober mencatat51tes unik, kesetaraan
native dua branch pada pilot TGDI dan smoke fresh CPU32frame. Bukti tersebut
berlaku pada source/code/profile saat itu. Penambahan fresh/batch berikutnya
memiliki tes dan source bundle tersendiri; angka tes historis bukan hasil tes
ulang pada audit ini. Tidak menjalankan ulang model atau counting untuk audit.

**BATAS VALIDASI:** kesetaraan algoritme tidak membuktikan identitas fisik atau
akurasi traffic. Konfigurasi vehicle-ReID final, audit malam, geometri provisional
dan masalah kualitas yang sudah diketahui tetap menjadi agenda evaluasi terpisah.

## 2. Perilaku yang wajib dipertahankan

1. YOLO26M → BoT-SORT + ReID tetap arsitektur inference. Asset, preprocessing,
   precision, seed, parameter dan backend mengikuti profil eksperimen yang dibekukan.
2. Crossing memakai BC dari bbox deteksi terukur yang terhubung ke track.
   Bbox union motorcycle+rider untuk tampilan tidak menggantikan BC kendaraan.
3. Episode identitas, scope role, eligibility, konflik, deduplikasi, category
   precedence dan genuine return mengikuti implementasi acuan, termasuk urutannya.
4. Timeout60 **frame sumber** tetap estimasi untuk kandidat eligible tanpa konflik
   identitas relevan; prediksi/gap tidak menjadi crossing terukur. Tidak mengubah
   horizon menjadi asumsi2detik atau mengaktifkan ulang passage karena ID berubah.
5. Motorcycle+rider/passenger satu unit motorcycle; rider+0. Person unknown tidak
   otomatis pedestrian. Konflik ambigu tetap sesuai kebijakan pending/invalid/+0.
6. Accepted, measured/estimated, pending, invalid dan resolved-not-eligible tetap
   berbeda. Machine dan reviewed merupakan alternatif snapshot, tidak dijumlahkan.
7. Agregasi kendaraan mengecualikan pedestrian; agregasi passage lintas video
   bukan deduplikasi kendaraan fisik global, traffic24jam atau ramalan bisnis.
8. Sumber, geometry/review revision, model, konfigurasi dan versi hasil tetap
   terlacak. Source gagal/unknown tidak menjadi nol. Hasil lama immutable.

Perubahan threshold, taxonomy, model, filter malam, geometri G1/G2 atau cara
resolusi identitas merupakan eksperimen perilaku terpisah. Jangan memasukkannya
ke refactor lalu menafsirkan perubahan hitungan sebagai keberhasilan modularisasi.
Algoritme acuan beserta keterbatasan/known bugs dipertahankan untuk perbandingan;
known bug yang perlu diperbaiki memiliki tiket dan baseline eksperimen sendiri.

## 3. Inventaris kondisi dan komponen yang perlu dipisah

Prioritas P0 di tabel ini adalah **pengaman migrasi**, berbeda dari gate kualitas
counting/QC P0 pada dokumen historis.

| Komponen/sumber aktual | Yang sudah tersedia | Pemisahan yang diperlukan | Prioritas |
|---|---|---|---|
| `contracts.py`, `schemas/`, `results.py` | Validasi profile/artifact, status dan ringkasan native | Kontrak domain, serialisasi compatibility, validasi semantik dan versi schema terpisah; capability tiap format dinyatakan eksplisit | P0 |
| `measurements.py`, `fresh_bridge.py`, `_kernel/measurement_adapter.py` | Raw-link/BC/source guards; provenance fresh berbeda dari notebook | Satu kontrak frame terukur dengan adapter sumber terpisah; parent source/model/runtime tetap dapat ditelusuri | P0 |
| `pipeline.py` | Orkestrasi adapter → identity → counting → review | Application service tipis; kernel tidak membaca path/UI/GCS atau mengelola worker | P0 |
| `_kernel/identity_core.py` → `identity_lifecycle.py` → `identity.py` | Komponen, episode dan perlindungan konteks | Interface episode/role/relation eksplisit; ganti alias `previous` berlapis secara bertahap setelah parity | P1 |
| `_kernel/passage.py`, `eligibility.py`, `handoff.py`, `publication.py` | State/passage, eligibility, konflik dan finalisasi | Tetapkan pemilik state, rule evaluation, dedup/finalization dan projection agregat; urutan override tetap sama | P1 |
| `_kernel/reviews.py`, `overlay.py`, `review_finalizer.py`, `review_metadata.py` | Review berbukti dan lineage | Dua layanan terpisah: source context sebelum resolver dan candidate adjudication sesudah counting; kewenangan crossing tidak diberikan pada keduanya | P0 |
| `inference_worker.py` | YOLO, BoT-SORT, ReID dan pemeriksaan sumber dalam proses baru | Pisahkan decoder, preprocessing, detector, tracker/encoder adapter dan measurement writer di belakang facade kompatibel | P1 |
| `orchestration.py`, `tools/run_t7sl_job.py`, `run_t7sl_batch.py` | Isolasi proses, smoke dan dua slot GPU | Runtime scheduler generik, job lifecycle, resource policy, checkpoint dan log; konfigurasi T7SL menjadi input/deployment adapter | P0 |
| `batch.py` | Rekonsiliasi native dan pivot; menolak smoke/branch campuran | Pisahkan validator manifest/selection hasil dari proyeksi tabel/ekspor; kontrak produk8video tetap ditegakkan di entry point | P0 |
| `render.py`, `_kernel/render_*` | Renderer tidak memutuskan counting; hash hasil dijaga | View-model dari measurement/result; dukungan fresh diuji tanpa memberi provenance notebook palsu | P1 |
| `artifacts.py`, `persistence.py`, tools collector | SHA, publikasi lokal atomic, reopen | ArtifactStore port, local adapter dan manifest lifecycle; Git/Kaggle/GCS di lapisan luar, bukan domain | P0 |

## 4. Temuan yang perlu ditangani saat migrasi

| ID | Temuan dari pembacaan kode | Dampak dan rekomendasi |
|---|---|---|
| A01 | Modul lokal masih memanggil `previous`/helper internal berlapis; `publication` memproyeksikan perilaku lapisan sebelumnya | Batas file sudah ada tetapi perubahan urutan mudah mengubah keputusan. Bungkus interface dahulu; jangan langsung menggabungkan semua fungsi |
| A02 | Fresh contract saat ini hanya mengizinkan branch machine dan menolak review/relationships lama | Benar sebagai pengaman saat ini. Jangan menjanjikan fresh review-assisted sudah tersedia. Rancang review baru yang terikat measurement fresh dengan versi/capability eksplisit |
| A03 | `results.wrap_native()` menetapkan `fresh_inference_executed` dari format input; G2 mengoreksinya pada skrip luar | Asal data dan operasi bisa tertukar. Pisahkan measurement origin dari operation executed; cached replay tidak boleh mengklaim inference baru. Perubahan metadata ini perlu compatibility mapping/versioning |
| A04 | Batch launcher menyebut T7SL, dua T4, urutan slot, prefix smoke dan path tools secara langsung | Belum runtime service umum. Pisahkan konfigurasi dataset dan device requirements; profil T4×2 tetap strict, tidak diam-diam fallback ke CPU |
| A05 | `inference_worker` menyimpan seluruh records, beberapa adapter/kernel mematerialisasi atau menyalin seluruh video | Kebutuhan RAM dapat meningkat. Ukur scope aktual sebelum merancang streaming. Finalisasi kategori offline memakai observasi kemudian; streaming/chunking tidak boleh mengubah jendela bukti |
| A06 | Worker memproses prefix yang diminta dan label scope masih menyebut prefix; job luar menandai full-video | Standarkan frame scope/coverage/EOF dan definisi full-video. Jangan menerima prefix sebagai hasil lengkap hanya karena nama job menyebut FULL_VIDEO |
| A07 | Renderer video masih memakai guard/struktur cache historis | Fresh→counting yang berhasil tidak otomatis meluluskan fresh→annotated video. Tambahkan adapter tampilan dan uji hash frame/raw ID/parent/BC terpisah |
| A08 | `publish()` menjaga direktori lokal immutable; subprocess failure pada orchestration dibersihkan bersama staging | Ini belum durable job retry/cancel/idempotency. Pertahankan log kegagalan dan status terminal; pisahkan retry job dari penambahan hitungan |
| A09 | `implementation_hash()` mengikat banyak file Traffic sekaligus; perubahan modul non-domain dapat mengubah versi counting | Petakan dependencies/fingerprint per operasi. Catat code/schema/model/runtime yang efektif; jangan mempertahankan versi lama dengan menghapus pembeda yang relevan |
| A10 | Batch memvalidasi kategori/arah dan asal branch; aturan memilih delapan snapshot masih tersebar di launcher/collector | Buat manifest pemilihan satu snapshot/video dan kebijakan compatible profile. Tes rekonsiliasi per sel, source-frame scope dan subtotal per-video, bukan hanya grand total |
| A11 | Source/default referensi pilot privat dan status readiness hardcoded masih dipertahankan untuk compatibility | Jangan dipakai sebagai produk umum. Public contract wajib input explicit; wrapper generik perlu scope/readiness nyata tanpa mengubah native baseline |
| A12 | Storage beroperasi pada path lokal; collector juga mengatur polling dan publikasi Git | Pisahkan result persistence, remote collection dan publikasi. GCS dipilih owner, tetapi bucket/IAM/CRUD belum menjadi kemampuan terverifikasi |

Temuan adalah hasil audit statis, bukan reproduksi failure baru. Tidak menetapkan
angka RAM/throughput/akurasi yang belum diukur. Pemisahan nama file saja tidak
dianggap menyelesaikan temuan.

## 5. Batas arsitektur yang diusulkan

Struktur berikut adalah **PROPOSAL**, bukan daftar file yang sudah diimplementasikan:

```text
src/traffic_location/
  traffic/
    contracts/       # config, measured frame, episode/relation, passage, result
    application/     # process_video, replay, review, process_batch, render
    domain/          # geometry, trajectory, role/episode, eligibility, counting
    adapters/
      measurement/  # notebook dan fresh; guard dan provenance per sumber
      inference/    # decoder, preprocessing, YOLO, BoT-SORT/ReID
      rendering/    # video/panel/export view-model
    runtime/         # per-job process, resource/device policy, lifecycle
    compatibility/   # native v7/v8 wrappers selama migrasi
  location/          # engine Area Coverage independen; audit berikutnya
  shared/            # artifact refs, hashing, manifests; tanpa aturan traffic
  storage/           # interface ArtifactStore dan adapter lokal/GCS bertahap
```

Domain menerima data tervalidasi dan mengembalikan keputusan; tidak mengimpor
UI, Kaggle CLI, Git, GCS, Torch atau OpenCV. Torch/OpenCV/encoder adalah adapter
inference/render. UI/backend hanya memanggil application API, tidak menyalin
aturan counting. Shared tidak berisi taxonomy kendaraan, geometri traffic,
aturan jalan motor, atau formula kapasitas.

Kontrak konseptual yang perlu dibekukan: `MeasuredFrame` (source/hash/frame/raw
detection link), `EpisodeRelation` (scope dan dasar bukti), `PassageEvent`
(unit/category/direction/evidence/status), `VideoResult` (coverage/status/version),
`BatchSelection` dan `BatchResult` (snapshot refs dan pivot). Nama/type akhir
ditetapkan lewat interface review; tidak perlu memperkenalkan framework baru
untuk mengganti dict sebelum parity gate tersedia.

## 6. Rencana migrasi setelah persetujuan

| Tahap | Input | Pekerjaan dan output | Acceptance criteria untuk maju |
|---|---|---|---|
| M0 — freeze acuan | Actual source/config/model/runtime dan dua branch historis; T7SL aktual jika tersedia | Registry input/output hashes, selected snapshots, known limitations, capability matrix dan rollback refs | Artefak dapat dibuka dan diverifikasi; assumption tidak dipakai menggantikan hasil actual yang belum ada |
| M1 — kontrak dan facade | Acuan M0 dan contract saat ini | Satu facade publik, definisi operasi/lineage/status, compatibility mapping/versioned schema | Native domain tidak berubah; request invalid, branch/overlay salah, source/scope salah ditolak; schema dan runtime validator sepakat |
| M2 — adapter measurement | Notebook cache dan fresh packet terikat sumber | Dua adapter menghasilkan measured-frame contract yang sama | Frame coverage, kategori mentah, raw ID/index/bbox/BC/observed tetap sama; source/provenance tidak diganti; dukungan review eksplisit |
| M3 — kernel identity/counting | Measured frames, geometry dan policy locked | Pisahkan episode/role, rule evaluation, passage/finalization dan aggregate projection satu irisan per perubahan | Seluruh event/keputusan/role/relation/pending/invalid dan agregat setara; tidak ada fallback baru atau threshold berubah |
| M4 — application/runtime | Facade M1–M3 dan runtime profile | Generic video/batch runner; dataset dan slot GPU menjadi konfigurasi; state/log/error terisolasi | Retry/reorder/concurrent jobs tidak mewariskan state atau menggandakan passage; partial/failure/cancel terlapor dan bukan sukses palsu |
| M5 — render/export | Immutable result, frames dan assignments | View-model dan renderer notebook/fresh; pivot serta ekspor memakai sumber keputusan sama | Rerender tidak mengubah native hash; raw ID, role-parent, kategori, BC dan evidence terbaca; pivot/CSV/event konsisten |
| M6 — persistence/reopen | ArtifactStore contract dan result manifest | Local adapter dahulu; rancangan GCS terpisah, package/CLI dan runtime recipe | Reopen tanpa model/refetch; corrupt/missing/export failure ditolak; wheel bekerja di luar repo; dependency dan versi terdokumentasi |
| M7 — acceptance/release candidate | Seluruh artefak M0–M6 | Laporan diff, regression results, API/capability docs dan rollback checklist | Gate di bagian7 lulus dalam scope yang dinyatakan; merge/release tidak diperlakukan sebagai persetujuan produksi |

GCS CRUD, backend authentication/queue/metadata database, UI, Docker dan deployment
adalah milestone integrasi berikutnya. Desain ini menyiapkan boundary-nya;
audit ini tidak memilih framework atau memprovision cloud.

## 7. Acceptance criteria lintas tahap

| Gate | Definisi kelulusan yang harus dibuktikan |
|---|---|
| AC01 — native parity | Pada input/profile yang sama, keputusan diskret dan seluruh field native acuan tidak berbeda: event ID, episode/unit/role, kategori, arah, measured/estimated, source refs/frame, dedup, pending/invalid/+0 dan agregat. Diff harus kosong atau perubahan metadata yang disetujui dipetakan eksplisit |
| AC02 — status/provenance | Execution success berbeda dari quality partial/unknown. Machine/reviewed tidak tercampur. Measurement origin berbeda dari operasi fresh/replay/reopen. Format tidak didukung ditolak dengan alasan |
| AC03 — frame/identity guards | Source/model/config/review/geometry salah, frame hilang/duplikat, raw link berubah, prediction-only atau rider BC untuk crossing kendaraan ditolak; source indices tetap sumber, bukan indeks hasil sampling |
| AC04 — preservasi rule | Regression source-bound mencakup pergantian ID, class/object reuse, rider/pedestrian, occlusion, konflik ambigu, timeout origin, muncul menjauh, genuine return dan endpoint/gap; hasil acuan dipertahankan |
| AC05 — batch/pivot | Satu snapshot/video; no duplicate source/rerun, no smoke dalam full total. Per sel kategori×arah×evidence cocok event ledger dan subtotal. Pedestrian terpisah, pending/invalid tidak dihitung; missing/failed menghasilkan partial/null |
| AC06 — isolasi/repeat | Minimal tiga replay independen per profile yang dimigrasikan; native hash dan logical result version stabil pada input/code/runtime identik. Ubah urutan video dan jalankan job bersamaan; output per-video tidak terpengaruh |
| AC07 — fresh inference | Adapter pindah tanpa mengubah weights/precision/filter/backend. Jika inference path dipindah, uji fresh terpisah minimal tiga kali pada scope bounded dan perangkat yang direkam. Counting-cache repeat tidak meluluskan GPU fresh determinism; mismatch dicatat dan menghentikan klaim profile itu |
| AC08 — renderer | Sumber didekode dengan cara yang cocok hash frame; random seek tidak diasumsikan identik. Periksa raw ID, parent motorcycle, kategori, frame, BC, evidence log/pivot dan panel. Rendering tidak menghasilkan keputusan atau event baru |
| AC09 — persistence/retry | Hasil final immutable dan dibuka tanpa refetch/inference. Corruption, missing artifact, gagal ekspor dan concurrent duplicate request tidak menghasilkan sukses/total palsu; log kegagalan dapat diperiksa |
| AC10 — package/boundary | Engine dapat diimpor/dijalankan dari luar repo tanpa notebook import path; domain tidak membutuhkan UI/cloud/GPU runtime. Model/device adapter tetap diwajibkan hanya pada operasi yang membutuhkannya |
| AC11 — versi dan rollback | Source/model/schema/code/runtime/result version dan capability matrix tercatat; rollback mengembalikan pilihan snapshot/entry point acuan, tidak mengedit hasil candidate agar match |

Kompresi JSON/container video, path deployment, timestamp/job ID serta hash kode
baru dapat berubah. Itu tidak mengizinkan perubahan event atau menghilangkan
field pembanding agar diff terlihat kosong. Logical result version **boleh berubah
ketika code/schema/runtime berubah**, dan harus stabil ketika identitas pekerjaan
yang relevan sama. Wrapper versi baru memetakan native lama secara eksplisit.
Toleransi floating-point hanya boleh dideklarasikan sebelum uji dan tidak boleh
menyembunyikan perubahan accepted/category/direction/eligibility.

## 8. Strategi perubahan, review dan rollback

Satu repo, dua engine; tidak perlu repo baru atau rewrite sekaligus. Setelah
persetujuan, usulkan branch `refactor/traffic-modularization-v2` dari commit yang
dipilih dan dicatat. Branch itu **belum dibuat** oleh audit ini. Branch existing
dan source bundle/notebook acuan dipertahankan sebagai pembanding.

Setiap perubahan memindahkan satu tanggung jawab, menjalankan gate relevan dan
menyimpan before/after diff di direktori candidate terpisah. Jalankan facade baru
dan compatibility facade lama pada measurement frozen yang sama. Jangan menjalankan
model mahal untuk perubahan yang hanya memindahkan counting/renderer/storage.
Jika mismatch domain muncul, hentikan irisan itu, diagnosis, lalu rollback facade
atau pilih snapshot lama; jangan menimpa golden. Perbaikan bug/perilaku dibuat
eksperimen tersendiri dengan alasan dan pengujian baru.

Persetujuan audit mencakup scope modularisasi, perilaku yang dipertahankan,
urutan M0–M7 dan AC01–AC11. Persetujuan tidak otomatis menyetujui model/threshold
baru, kualitas produksi, final taxonomy, penyederhanaan algoritme yang mengubah
hasil, atau deployment/cloud spending.

## 9. Handoff ke Area Coverage

Pekerjaan berikutnya adalah **audit Area Coverage**, bukan langsung implementasi
migrasi Traffic. Inputnya: modul `location/`, snapshot LI3/LI4 N1, selection,
capacity, routing decisions, Recount R1/R2, policy serta manifest/software versions.

Audit berikutnya perlu memetakan acquisition/normalization → selection/capacity →
motor graph/access/connectors/routing → keputusan waktu → Recount → ekspor/peta.
Selection/capacity/Recount yang sudah menjadi modul tidak ditulis ulang; routing
dan source acquisition yang masih di notebook diperiksa sebagai kandidat adapter.
Pertahankan boundary GDAL/OGR versus Shapely/PyProj sampai ada uji kesetaraan.

Gate Area yang harus dibawa: seluruh source rows direkonsiliasi; unknown tidak
menjadi zero/accepted; akses/barrier/one-way/restriction tidak dilonggarkan;
125m tetap candidate-search experiment; hierarchy valid road dan waktu mengikuti
policy frozen, termasuk `round(total_min) <= 10`,7km/jam dan biaya konektor.
Kapasitas dengan unit berbeda tidak dijumlahkan. Perubahan koordinat/polygon/
snapshot/config adalah revision baru; reopen tetap offline. Ini daftar pemeriksaan
audit berikutnya, bukan pernyataan bahwa audit Area sudah dilakukan sekarang.

## 10. Referensi pembacaan

- [Review fondasi modularisasi](ENGINE_MODULARIZATION_REVIEW.md).
- [Kontrak dua engine](ENGINE_IO_CONTRACT_DRAFT.md).
- [Kebijakan reproduksibilitas](REPRODUCIBILITY_POLICY.md).
- [Review dan batas eksperimen T7SL](T7SL_FRESH_BATCH_REVIEW.md).
- [Kontrak/profil](../src/traffic_location/traffic/contracts.py),
  [pipeline](../src/traffic_location/traffic/pipeline.py),
  [fresh adapter](../src/traffic_location/traffic/fresh_bridge.py),
  [batch](../src/traffic_location/traffic/batch.py),
  [renderer](../src/traffic_location/traffic/render.py),
  [inference worker](../src/traffic_location/traffic/inference_worker.py),
  [publikasi lokal](../src/traffic_location/persistence.py).


## Pelaksanaan audit yang diotorisasi

Instruksi owner berikutnya mengotorisasi migrasi ini. Status proposal/menunggu
persetujuan di atas merupakan checkpoint historis; hasil implementasi, keputusan
dan bukti uji ada di [release migrasi](TRAFFIC_MODULARIZATION_RELEASE.md).
