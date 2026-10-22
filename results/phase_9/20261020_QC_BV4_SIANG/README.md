# Paket QC lanjutan B v4

- [Laporan dan keputusan sistematis](REPORT.md).
- [Seluruh 68 kasus pending dengan tautan bukti](PENDING_DECISIONS.md).
- [Pemeriksaan kelengkapan](COMPLETENESS.md).
- [Indeks CSV68 kasus](case_index.csv) dan [ledger QC](review_decisions.jsonl).
- [Sembilan unresolved](unresolved_decisions.csv).
- [16usulan cancellation accepted unik](accepted_event_actions.jsonl).
- [Kontrol seluruh 34 accepted timeout](accepted_timeout_control/per_event_decisions.jsonl).
- [Mapping463inferensi](removed_inferences/exhaustive_mapping.csv) dan
  [24review visual terarah](removed_inferences/targeted_visual_decisions.jsonl).
- [Discovery tanpa kandidat dan diagnostic groups](unmatched/unmatched_passages.jsonl).
- [Backlog Phase 1–8](improvement_backlog.csv).
- [Spesifikasi kebijakan/usulan uji lintasvideo](../../../docs/PHASE_9_QC_RECOMMENDATIONS.md).
- [Verifikasi integritas](validation.json), [input](input_manifest.json),
  [guard sebelum](baseline_guard_before.json), dan [guard sesudah](baseline_guard_after.json).
- [Manifest bukti gambar](evidence/manifest.json) dan [manifest seluruh artefak QC](artifact_manifest.json).

QC memberikan59 rekomendasi penutupan pending dan 9unresolved pada scope68 kasus
pilot. Hasil machine tetap172 accepted/68 pending. Jangan menjumlahkan keputusan
dari subgroup berbeda yang menunjuk event/passage fisik sama. Person54sudah
mempunyai adjudikasi di branch review-assisted lama; bukan+1kedua pada branch itu.

Dataset/video sumber tidak dimasukkan ke folder ini. Frame/crop/contact sheet
bukti terpilih dan manifest tersimpan. File source dipulihkan read-only dari
Kaggle dengan SHA yang cocok. Baseline117artefak dan executable tidak berubah.
Tidak ada detector/tracker/ReID/counting/enhancement atau rendering batch baru.

Review ini sampling sumber percase dan source-first sepanjangtimeline, bukan
menonton semua 9.128 frame kontinu atau validasi delapan video.20 accepted-timeout
masih unresolved secara QC. Rekomendasi bukan ground truth formal, bukan total
traffic final, dan belum diterapkan pada pipeline.

`audit_tools/` menyimpan helper ekstraksi/diagnostik/kompilasi yang dipakai,
bukan aplikasi produksi. Validasi dapat diulang dengan Python+OpenCV dan
source/cache yang dipulihkan. Jangan menjalankan semua helper sembarangan:
helper persiapan dapat menulis ulang rencana sebelum adjudikasi. Ledger dan
manifest adalah rekaman hasil yang diutamakan. Publikasi GitHub belum dilakukan
untuk paket baru ini.
