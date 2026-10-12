# Phase 6 — counting TOR3-PAGI dengan Opsi A

**USER DECISION:** Phase 6 diizinkan setelah pengguna memilih Opsi A: accepted hanya ketika bukti geometri, unit, kategori dan identitas memenuhi aturan eksplisit; konflik tetap pending dan tidak masuk subtotal sampai terselesaikan. Review menggunakan notebook/berkas audit, tanpa UI. Kontrak konkret berada di [COUNTING_CONTRACT.md](COUNTING_CONTRACT.md).

Dokumen ini mendefinisikan pekerjaan dan gate, bukan melaporkan hasil tes/run yang belum dilakukan.

## Task

Bangun dan jalankan prototype counting yang dapat diaudit atas diagnostik crossing TOR3-PAGI tersimpan, dengan urutan **metrik passage → unit/rider → kategori → deduplikasi → genuine return → eligibility → parameter dan schema event**.

## Read first

- [AGENTS.md](../AGENTS.md) dan [CODEX_WORKFLOW.md](../CODEX_WORKFLOW.md).
- [COUNTING_CONTRACT.md](COUNTING_CONTRACT.md), [COUNTING_LOGIC.md](COUNTING_LOGIC.md), [GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md).
- [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md) dan retained geometry diagnostics/track/pixel evidence.
- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), [PRODUCT_SPEC.md](PRODUCT_SPEC.md), [MODEL_SPEC.md](MODEL_SPEC.md), [ARCHITECTURE.md](ARCHITECTURE.md).
- [API_CONTRACT.md](API_CONTRACT.md), [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md), [OPEN_DECISIONS.md](OPEN_DECISIONS.md), [TEST_PLAN.md](TEST_PLAN.md), [EVALUATION.md](EVALUATION.md).

## Scope

1. Dokumentasikan keputusan pengguna terpisah dari aturan implementasi eksperimen dan keputusan OPEN.
2. Baca `GEOMETRY_TRANSITION` dari retained Phase 5 `b0_c1` dan rekonstruksi class/source evidence dari window origin–confirmation cache emitted-track Phase 4. Jangan membentuk crossing baru.
3. Buat candidate decisions dengan hard block unit-changing history, category/identity conflict screening dan audit-gated pending untuk semua unit/identity/category yang belum direview positif.
4. Buat review input yang memuat bukti pixel aktual, path/hash/frame scope, unit/kategori/identity conclusions serta physical-unit/passage references.
5. Resolve review yang valid menjadi accepted/rejected/pending; deduplicate hanya same physical unit + same passage yang dikonfirmasi. Genuine return baru memerlukan episode review.
6. Simpan event schema/provenance deterministik, original machine outputs, resolved outputs, audit queue dan per-video accepted-event subtotal yang dapat direkonsiliasi.
7. Buat annotated crossing visualization untuk window aktual yang direview. Batasi klaim visual ke frame yang benar-benar tersedia dan dilihat.

## Parameter dan execution context

**ENGINEERING EXPERIMENT:** baseline counting menggunakan kontrol geometri tersimpan `neutral_band_px=0`, `confirmation_observations=1`. Nilai ini sudah dijalankan di Phase 5, bukan nilai pilihan numerik pengguna atau default produk terbaik. Counting configuration harus menyebut input/cache/diagnostic/geometry identities dan versi aturan eksperimen.

Pemrosesan artefak tersimpan dapat berjalan di Codex CPU tanpa GPU/model dependencies. Kaggle dapat menjalankan notebook yang sama setelah path helper, diagnostik, cache, geometri dan evidence disetel eksplisit. GPU tidak diperlukan untuk counting retained evidence. Actual source dataset/video tidak ditambahkan ke GitHub.

## Out of scope

- Rerun YOLO, tracker, ReID, geometry pipeline atau reprocessing video untuk memperoleh trajectory baru.
- Mengubah G3/BC/aturan gap, endpoint, touch dan prediksi yang disepakati.
- Resolver ReID/identity otomatis baru, unit-changing recovery atau threshold tuning yang tidak didukung eksperimen.
- Memaksakan pickup car/truck, bus/angkot, unknown recording/day/store metadata.
- Night preprocessing Phase 7, delapan-video/multi-GPU Phase 8, full formal ground-truth benchmark atau klaim akurasi.
- Production `src/` refactor, database, UI, Docker, GPU VM, GMC/stabilisasi.

## Validation

Jalankan terlebih dahulu:

```bash
python notebooks/phase_6_synthetic_tests.py
```

Tes bermakna harus meliputi:

- Full measured crossing dan arrival, arah dua sisi, initial presence tidak counted.
- Unreviewed evidence tetap pending; absence of overlap bukan positive identity proof.
- Rider rejected, walking pedestrian accepted hanya dengan review lengkap.
- Person↔vehicle history hard blocked walaupun latest/category override mengatakan motorcycle.
- Category conflict dan taxonomy OPEN tetap terlihat; unsupported label tidak diberi category palsu.
- Duplicate confirmed same unit/passage menjadi satu event dengan semua source links; kategori confidence change tidak membuat unit baru.
- Genuine return terpisah dapat menghasilkan event baru hanya setelah review episode; jitter/update berulang tidak menambah event.
- Invalid/missing/tampered pixel evidence dan review contradictions tidak diterima.
- Ambiguous gap/endpoint/prediction tidak dapat disahkan lewat manual review.
- Stable IDs, rerun idempotence, aggregate-event reconciliation dan immutable machine-vs-resolved separation.

Setelah tes lulus, execute `notebooks/06_counting_audit.ipynb` dengan input/config eksplisit. Retain executed notebook atau execution record, input/effective-config hashes, test report, machine/resolved output, review input dan pemeriksaan artefak. Independently inspect kasus unit/category/duplicate yang relevan dari pixel evidence nyata. Tes sintetis PASS tidak menggantikan review real-video.

## Deliverables

- `docs/COUNTING_CONTRACT.md` dan dokumen tugas ini.
- `notebooks/phase_6_counting_helpers.py`.
- `notebooks/phase_6_synthetic_tests.py`.
- `notebooks/06_counting_audit.ipynb`.
- Artefak evidence Phase 6: konfigurasi/provenance, review input, candidate/machine/resolved decisions, accepted events, aggregate snapshot, audit queue, visualizations dan manifest/hash validation.
- Review hasil Phase 6 yang dibuat dari eksekusi aktual, dengan batas audit dan keputusan OPEN.
- Pembaruan minimum status/spec docs sesuai kontrak dan findings yang benar-benar didukung evidence.

## Reporting and acceptance limits

Laporkan files changed, exact tests/run yang benar-benar dijalankan, pass/fail, candidate decisions, accepted-event subtotal, pending reasons, visual scope, idempotence/reconciliation dan unresolved decisions. Jangan menyebut diagnostik Phase 5 sebagai total kendaraan atau menyamakan accepted subtotal dengan whole-video traffic completeness.

Gate teknis Phase 6 adalah output auditable dan konsisten menurut kontrak, bukan counting accuracy. Keputusan OPEN boleh ditahan di pending tanpa menciptakan angka atau kebijakan baru; pemrosesan kasus yang independen tetap dilanjutkan. Setelah Phase 6, jangan otomatis memulai Phase 7 atau fase lain tanpa instruksi pengguna.
