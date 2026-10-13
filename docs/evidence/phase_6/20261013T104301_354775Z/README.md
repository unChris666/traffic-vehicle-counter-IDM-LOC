# TOR3-PAGI — eksperimen Opsi B v1

**EXPERIMENT RESULT:** run CPU notebook06b dari cache Phase4 `reid_on`, tanpa inferensi detector/tracker/encoder. Geometri episode kendaraan baru direplay dengan G3 dan kontrol eksperimen b0_c1. Scope13ID/enam window, bukan total trafik seluruh video.

Mulai dari [review teknik](../../../PHASE_6_OPTION_B_REVIEW.md), [perbandingan passage](passage_comparison.md), dan [gambar perbandingan](comparison_visualizations/README.md).

| Snapshot | Accepted CountEvents | Keterangan |
|---|---:|---|
| A original / A_updated, subset sebanding | 3 | Decision A retained; full-video historis18 terpisah |
| B episode-only ablation | 0 | Enam kandidat pending, grouping dimatikan |
| B_machine v1 | 1 | Motorcycle1772/rider1774; lima kandidat pending |
| B_reviewed | 4 | Tiga physical passages direview + satu automatic event1772 dipertahankan;973 duplicate-suppressed;1323 tetap pending |

Empat pemeriksaan per passage meliputi salah penggabungan, duplikasi, kategori, dan sumber crossing vehicle BC. Pending yang turun melalui review tidak dianggap manfaat otomatis B. Tidak ada ground truth atau accuracy benchmark.

Artefak utama:

- `report.json`, `software_report.json`, `runtime.json`, `summary.json`: eksekusi aktual dan keterbatasan.
- `configuration_input.json`, `calibration_input.json`: input/control beku; kontrol tidak dipilih sebagai default produk.
- `episodes.jsonl.gz`, `relations.jsonl.gz`, `derived_diagnostics.jsonl.gz`: bukti episode, asosiasi, dan geometri.
- `machine_decisions.jsonl.gz`, `accepted_events.jsonl.gz`, `aggregate.json`: mesin v1 tanpa feedback manual sebagai feature.
- `ablation/`: kontrol episode yang sama dengan grouping dimatikan.
- `reviewed/`: snapshot review eksplisit; source machine tidak diubah; satu event otomatis tetap identik.
- `passage_comparison.json/csv/md`: scope A/B yang sama, bukan membandingkan full-video18 dengan subset1.
- `synthetic_test_results.json`:63/63; `review_overlay_synthetic_tests.json`:24/24.
- `independent_artifact_audit.json`:653/653 pemeriksaan aktual, termasuk sumber cache dan reviewed overlay.
- `execution_manifest.json`: manifest eksekusi awal yang tidak ditulis ulang oleh review.
- `retention_manifest.json`, `final_retention_validation.json`: hash source/evidence/dokumentasi final serta pemeriksaan retensi.
- `*.executed_source.py.gz`, notebook original/executed gzip: source tepat yang benar-benar dieksekusi.

Run [v0](../20261013T103406_717807Z/superseded_run_audit_note.json) disimpan sebagai superseded karena relasi masa depan ikut mengesahkan passage923. V1 memperbaiki gate temporal tanpa mengubah angka threshold. Category policy memakai seluruh episode kendaraan secara offline/noncausal. Foto retained ada di [temporal review](../option_b_temporal_review/README.md), termasuk generation1 yang disimpan terpisah. Source video tidak dimasukkan ke GitHub.

No UI, night preprocessing, Phase7, multi-GPU, atau refactor aplikasi produksi dilakukan.
