# Phase 2 retained evidence

## Source and software validation

- [asset_verification.json](asset_verification.json): actual authoritative URL/package/checkpoint verification, not inference.
- [notebook_helper_validation.json](notebook_helper_validation.json): ten executed software checks, with synthetic/stub versus actual CPU CUDA-guard scope explicit. These are not traffic/model findings.
- [CPU smoke report](cpu_smoke/cpu_smoke_report.json): official model loaded and inferred two actual native TOR3-PAGI frames in Codex on CPU. The original report is unchanged, including its runtime absolute paths. Raw and annotated PNGs with the same basenames/indices are archived locally here for independent review: [raw frame 0](cpu_smoke/raw_frame_000000000.png), [annotated frame 0](cpu_smoke/annotated_frame_000000000.png), [raw frame 7718](cpu_smoke/raw_frame_000007718.png), [annotated frame 7718](cpu_smoke/annotated_frame_000007718.png).

## Kaggle job provenance

- [Submission receipt](kaggle_job/submission_receipt.json): actual official API save-and-run response, private Phase 2 notebook version 1.
- [Submitted metadata](kaggle_job/kernel-metadata.json): selected dataset, GPU environment, Internet, and image settings; GPU 0 is the inference device in source.
- [Source readback verification](kaggle_job/source_readback_verification.json): authenticated source pull compared with the validated cell sources before submission/result review. A successful save/readback or running status does not prove successful CUDA inference.

## Actual Kaggle CUDA run

[Run `20261011T052950_360560Z_ed399fb8`](20261011T052950_360560Z_ed399fb8/detection_report.json) retains original reports/manifest, five original/annotated PNG pairs and contact sheet, all frame detections compressed without changing bytes, five representative prediction rows, a 27-check independent artifact audit, and a separate subsequent Codex AI-assisted visual review. Original report status correctly remains manual-review pending at export; the review supplement documents the later image inspection.

Use `gzip -dc docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/frame_detections.jsonl.gz > /tmp/phase2-frame-detections.jsonl` to recover the original JSONL. Its decompressed SHA matches the original run manifest. Archive hashes are recorded in [archive_manifest.json](20261011T052950_360560Z_ed399fb8/archive_manifest.json). Absolute `/kaggle/working/...` paths in original reports are runtime provenance; run-relative sample references work here.

The GPU experiment belongs to batch source version 1. [Source guidance save receipt](kaggle_job/source_guidance_save_receipt.json) records a later version-2 Markdown-only Quick Save with unchanged executable cells; it is not a second GPU experiment. Actual runtime and limitations are summarized in [YOLO_DETECTION.md](../../YOLO_DETECTION.md). The Phase 1 notebook remains separate. No videos, weights, secrets, or executed notebook outputs are committed. Curated original/annotated sample images are evidence, not labelled ground truth. Raw frame predictions are per-frame detections and must never be interpreted as unique vehicle counts.
