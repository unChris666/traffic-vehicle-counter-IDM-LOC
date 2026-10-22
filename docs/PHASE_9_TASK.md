# Phase 9 — audit bukti dan daftar perbaikan Phase 1–8

**REQUIREMENT — tujuan pengguna:** menghasilkan daftar perbaikan berbasis bukti untuk mengurangi hitungan palsu, duplikasi, salah penggabungan, dan passage terlewat. Pending dapat diselesaikan sebagai **tidak eligible/+0**. Pending turun bukan ukuran keberhasilan tunggal.

**Status dokumen:** kontrak audit yang diperbarui setelah klarifikasi timeout. Pengguna kemudian mengotorisasi verifikasi input dan pilot TGDI-WEEKDAY-SIANG, serta memilih menyelesaikan pilot dan daftar perbaikan dahulu. [Hasil pilot aktual](../results/phase_9/20261019T140653Z_TGDI_WEEKDAY_SIANG_PILOT/REPORT.md) tersimpan terpisah; audit menyeluruh dan perbaikan algoritme belum dinyatakan selesai. Pengguna akan memberikan brief pivot untuk pekerjaan implementasi berikutnya.

## Mulai dari sini

- [Protokol input → proses → output dan pemeriksaan setiap fase](PHASE_9_AUDIT_PROTOCOL.md).
- [Prompt siap pakai untuk pelaksanaan audit](PHASE_9_PROMPT.md).
- [Template rencana, inventory, kasus, keputusan dan backlog](templates/PHASE_9_AUDIT_TEMPLATES.md).
- [Bukti kasus pedestrian/rider yang sudah diperiksa](PHASE_9_ROLE_REVIEW_WORKFLOW.md). Bagian agentic pada dokumen tersebut adalah usulan historis; audit ini dapat dilakukan dengan sistem biasa dan review manusia, tanpa membangun enam agen.

## Read first

`AGENTS.md`, `CODEX_WORKFLOW.md`, `docs/PROJECT_CONTEXT.md`, `docs/PRODUCT_SPEC.md`, `docs/MODEL_SPEC.md`, `docs/COUNTING_LOGIC.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/CONFIG_SCHEMA.md`, `docs/TEST_PLAN.md`, `docs/EVALUATION.md`, dan `docs/OPEN_DECISIONS.md`.

Untuk status terbaru, baca juga [kontrak B v2](B_V2_COUNTING_CONTRACT.md), [kontrak revisi B v3](PHASE_8_REVISION_CONTRACT.md), [hasil B v3](../results/b_v3/README.md), [kelompok pending](../results/b_v3/PENDING_DECISIONS.md), serta protokol audit di atas. Status OPEN dalam snapshot historis tidak membatalkan keputusan pengguna yang lebih baru; bedakan aturan saat run dengan aturan penilaian audit.

## Baseline yang harus dipertahankan

**EXPERIMENT RESULT — bukti tersimpan, bukan hasil audit baru:**

| Komponen | Identitas |
|---|---|
| Input utama | Delapan video TGDI di `/kaggle/input/datasets/chrisbiran/tgdi-traffic-videos`; sumber asli tidak dimasukkan ke GitHub. |
| Snapshot counting | `results/b_v3/execution/final_20261019T045405_106031Z/`, termasuk manifest retensi dan `batch_report.json.gz`. |
| Eksekusi anotasi | Kaggle `chrisbiran/phase-8-tgdi-b-v3-review`, version2, run `20261019T070846_020453Z`. |
| Bukti output | [Delapan video](../results/b_v3/VIDEOS.md), [delivery manifest](../results/b_v3/delivery_manifest.json), [kesamaan Kaggle/lokal](../results/b_v3/verification/actual_kaggle_local_comparison.json). |
| Hasil operasional | 72.590 frame; 3.500 event kendaraan: 895 terukur dan 2.605 inferensi, termasuk 2.454 timeout. Bukan jumlah fisik yang selesai diaudit. |
| Pending | 2.890 kunci unik: 2.427 unknown-person, 462 vehicle, 1 positive-role pedestrian. Kunci software bukan jumlah objek fisik. |
| Pembanding lama | B v2 tetap disimpan; denominator pending berbeda sehingga jumlah pending tidak dibandingkan langsung sebagai tingkat kegagalan. |

Policy, review manifest, geometri, source snapshot, MP4 dan artefak run tersebut tidak ditimpa. Penilaian terhadap kebijakan baru disimpan sebagai overlay audit terpisah.

## Kontrak penilaian audit terbaru

**REQUIREMENT — keputusan pengguna yang sudah disepakati dalam percakapan:**

1. Unit hitung adalah **kendaraan fisik per passage**, bukan raw tracker ID. Pergantian raw ID tidak membuat passage baru. Satu raw ID juga dapat berpindah objek sehingga penyambungan maupun pemisahan episode perlu bukti.
2. Motorcycle+rider/passenger menjadi satu motorcycle; rider memberi tambahan 0. Pedestrian adalah kategori tersendiri dan perlu bukti peran positif dalam interval yang jelas.
3. BC kendaraan berasal dari bbox kendaraan mentah yang terukur dan terhubung ke deteksi; bbox union hanya tampilan. Koreksi role/kategori/identitas tidak mengubah gap atau prediksi menjadi crossing terukur.
4. Timeout kandidat pertama adalah **60 frame sumber sejak terakhir terlihat di polygon asal**, hanya setelah eligible dan tanpa konflik identitas yang relevan. Hasil tetap estimasi. Observasi di polygon asal memperbarui clock; handoff terverifikasi melanjutkan episode/clock yang sama. Handoff ambigu menahan estimasi kandidat terkait, bukan menghentikan seluruh video.
5. Passage yang selesai tidak dibuka lagi oleh timer atau pergantian ID. Kemunculan di polygon tujuan dengan bukti gerak menjauhi garis adalah tidak eligible/+0. Genuine return membutuhkan bukti perjalanan/passage baru; gerak menjauh tidak disimpulkan dari satu frame atau jitter bbox.
6. Measured dan inferred dipisahkan. Machine dan reviewed adalah versi alternatif hasil, bukan dua subtotal yang dijumlahkan.

Persetujuan terbaru pada butir4–5 adalah acuan audit/revisi berikutnya, **bukan klaim bahwa seluruh pengaman tersebut sudah ada pada kode atau hasil B v3**. Audit mencatat perbedaan executed policy dan assessment policy. Kriteria numerik verifikasi identitas/gerak belum dipilih; jangan mengarangnya.

**OPEN:** perluasan occlusion/timeout untuk pedestrian; taxonomy BUS/angkot dan huruf tampilannya; kriteria numerik episode/handoff/role; konfigurasi vehicle-ReID final; enhancement malam produksi. Kontrol `pedestrian_routes=measured_only` pada B v3 adalah kontrol riset yang tercatat, bukan persetujuan perluasan atau pembatasan produk secara tersirat. Isu OPEN hanya menahan keputusan yang bergantung padanya.

## Scope pekerjaan audit

1. Validasi ketersediaan dan identitas video, versi anotasi, cache/model records, geometri, policy, review serta sumber executable.
2. Catat cakupan audit sebelum review. Mulai dengan pilot development TGDI-WEEKDAY-SIANG untuk menyelaraskan pencatatan; target perluasan mencakup delapan video dan kondisi malam. Full-video versus sampling serta intervalnya masih perlu ditetapkan, tanpa mengarang jumlah sampel atau ambang persentase kelulusan.
3. Untuk setiap segmen baru, buat inventory passage dari **video mentah sebelum melihat overlay model**. Simpan riwayat paparan reviewer; pengguna sudah melihat delapan anotasi sehingga audit ini tidak disebut blind.
4. Cocokkan inventory dengan accepted, pending, rejected/cancelled, episode person dan objek tanpa kandidat. Audit accepted estimasi sama pentingnya dengan pending.
5. Telusuri penyebab dari input → detection → association/episode → role/category → geometry → event → aggregate/output. Simpan penyebab primer dan faktor tambahan; satu kasus dapat menyentuh beberapa fase.
6. Catat keputusan berbukti, perubahan yang diusulkan pada hasil reviewed, serta daftar perbaikan dengan target uji dan regresi. Belum menerapkan perubahan ke pipeline.

**Di luar scope:** inference YOLO/BoT-SORT/ReID baru, tuning threshold, menjalankan ulang counting, enhancement baru, retraining, model role baru, refactor `src/`, UI, Docker, multi-GPU dan deployment. Decode sumber untuk review serta pembacaan/verifikasi artefak tersimpan diperbolehkan dalam tugas audit berikutnya. Ketika bukti tidak cukup, simpan unresolved atau rencana eksperimen, bukan hasil yang dibuat-buat.

## Kasus development awal

| Video / sumber kasus | Pemeriksaan yang dibutuhkan |
|---|---|
| WEEKDAY-SIANG, person 54 frame 57–107 | Review pengguna: pedestrian mendorong gerobak. Tetapkan scope role; validitas passage diperiksa terpisah. |
| WEEKDAY-SIANG, person 166/motor 185 frame 226 | Periksa konteks188–301; pisahkan objek motor tepi jalan dari rider. Audit M1006 dan M1007 tanpa melabeli seluruh166 sebagai rider. |
| WEEKDAY-SIANG, person 857/motor 856 frame 1089 | Tentukan interval relasi; dukungan1100–1113 tidak mengesahkan seluruh riwayat. Timeout motor 856 bukan crossing terukur. |
| WEEKDAY-SIANG, person 3025 frame 5003 | Pedestrian menurut pengguna; angka50003 sudah dikoreksi menjadi5003. Jangan memperluas label tanpa review. |
| WEEKDAY-SIANG, truck 4149 crossing7422 / dugaan return7509 | Pertahankan passage selesai; periksa apakah ada bukti perjalanan baru. Motorcycle raw 4149 pada7611 adalah episode lain. |
| WEEKDAY-PAGI, 73/93; 2471/2473/2507 | Periksa scope handoff, konflik pasangan lain, rider+0, satu passage, serta sumber BC vehicle. Jangan membuat alias raw ID global. |

Kasus yang sudah digunakan memilih aturan adalah development/regresi. Belum ada dasar menyebutnya hold-out independen.

## Deliverables dan gate selesai

Hasil audit ditempatkan di `results/phase_9/<audit_id>/`, sejajar dengan `results/b_v3/`; daftar nama dan template ada pada protokol. [Paket pilot aktual](../results/phase_9/README.md) kini tersedia. Keberadaan paket pilot tidak berarti full-video audit atau seluruh perbaikan telah dilaksanakan.

Audit selesai pada cakupan yang disepakati bila input dan cakupan dapat ditelusuri, inventory mentah sudah dicocokkan, setiap kasus mempunyai keputusan atau unresolved beserta perlakuannya, dampak event/agregat dapat direkonsiliasi, serta backlog menyebut bukti dan uji regresi. Laporan harus mencatat area yang belum diperiksa dan apakah blocker masih menghalangi tahap berikutnya. Pending tidak harus nol.

Keberhasilan audit adalah menemukan dan menjelaskan kesalahan beserta tindakan yang dapat diuji. **Berkurangnya kesalahan otomatis baru dapat dinyatakan sesudah revisi yang diotorisasi benar-benar dijalankan dan dibandingkan pada passage yang sama.** Koreksi manual saja tidak membuktikan perbaikan mesin. Jangan melaporkan accuracy, precision, recall, F1, MAPE atau counting accuracy tanpa protokol ground truth yang belum tersedia.

Phase 10 belum otomatis dimulai. Sesudah laporan audit, pengguna memberi brief pivot untuk memilih perbaikan. Setelah Phase 9 masih ada Phase 10 modular Python, Phase 11 UI, Phase 12 Docker dan Phase 13 GPU VM; urutan teknis tidak menggantikan gate bukti.
