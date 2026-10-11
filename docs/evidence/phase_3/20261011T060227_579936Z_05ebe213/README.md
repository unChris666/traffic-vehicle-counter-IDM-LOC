# Retained actual Phase 3 evidence

Kaggle run `20261011T060227_579936Z_05ebe213`, private notebook [traffic-counter-phase-3-botsort](https://www.kaggle.com/code/chrisbiran/traffic-counter-phase-3-botsort), version 1. See [tracking status/review](../../../BOTSORT_TRACKING.md) and [scope](../../../PHASE_3_TASK.md).

Actual BoT-SORT processed all 10,282 retained TOR3-PAGI detection rows with aligned video decoding. YOLO was not loaded or rerun. ReID is disabled and GMC none for this CPU association baseline; the actual environment exposed two T4 GPUs. No traffic counts or ground-truth metrics exist.

## Original execution versus later review

- `tracking_report.json`, `tracking_report.md`, `run_manifest.json`: original Kaggle exports, unchanged. Their pending visual-review fields reflect the export time.
- `track_records.jsonl.gz`, `track_summary.json.gz`, `representative_temporal_track_records.json.gz`: lossless full-data compression, not sampled/recomputed replacements. `compression_manifest.json` records original and compressed identities. Use `gzip -dc` to read them; write decompressed bulk files outside Git.
- `samples/`, `temporal/`: curated original tracked PNGs/contact sheets. `red_scooter_5125_5130_clip_contact_sheet.png` is a subsequent display-only crop from the retained lossy annotated MP4, not new tracking. Cropping does not affect association.
- `artifact_audit.json`: compact analytical summary of an actual independent read-only 12/12 PASS audit. It retains the full audit's original SHA/size/provenance; the bulky intermediate audit is outside Git. Compaction changes neither experiment records nor audit outcomes. The reusable audit method is retained under `../verification/audit_tracking.py`.
- `manual_tracking_review.json`: actual subsequent AI-assisted Codex visual review, with inspected frame indices, evidence references, risks and explicit unknowns. It is not a human ground-truth annotation.
- Focused/duplicate traces and diagnostic candidates: extracted actual records, not inferred physical labels. Gaps/class changes/ID totals are software diagnostics.

The visual review covers six displayed positions from each of five 30-frame bursts, eight focused entering-scooter frames, four native focused annotations and six consecutive red-scooter clip frames. All 150 subset rows and five clip frame counts were software audited; this does not mean all clips or the full video were visually reviewed end to end.

## Retention boundaries

Original videos/model weights and executed notebooks are excluded. Original raw sample PNGs are already retained in [Phase 2](../../phase_2/20261011T052950_360560Z_ed399fb8/samples/); five Phase 3 raw representatives matched them byte-for-byte and pixel-for-pixel. The five annotated 30-frame MP4 clips and other full output files remain in the private Kaggle version-1 output and local downloaded run directory; their original hashes remain in the execution report. The raw source video is not included in this archive.

`archive_manifest.json` records every archived file except itself. No Phase 1/2 execution evidence was modified by this transition.
