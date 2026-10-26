<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Phase 2 — detection status

**REQUIREMENT:** Phase 1 reports have passed the documented acceptance gate and the user has authorized Phase 2. Detection uses YOLO26M through the Ultralytics Python API on one actual video. [Phase 2 task](PHASE_2_TASK.md) defines the scope; no tracking/counting phase is authorized by this result.

## Authoritative verification

**EXPERIMENT RESULT — source/asset verification, not inference:** the official model/predict documentation, pinned source, PyPI metadata/wheel, and GitHub release asset were retrieved successfully on 2026-10-11. Actual downloaded hashes match published digests. The retained [verification record](evidence/phase_2/asset_verification.json) records URLs, identifiers, API source checks, and inspected checkpoint metadata.

| Item | Verified evidence |
|---|---|
| Ultralytics | 8.4.175; PyPI wheel actually downloaded and hash checked |
| YOLO26M | Official `yolo26m.pt`, release v8.4.0; 44,255,705 bytes; SHA-256 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7` |
| Raw labels | 80 checkpoint labels; relevant IDs: 0 person, 2 car, 3 motorcycle, 5 bus, 7 truck; no angkot label |
| Frame API | `YOLO(weights)` → `predict(source=BGR_frame, device=...)` → original-frame boxes/classes/confidence |
| Defaults in pinned source | `conf=0.25`, `imgsz=640`, `iou=0.7`, `max_det=300`, `batch=1`, `rect=True`, `classes=None`, `nms=None`, `quantize=None` |

**PROPOSAL — experiment baseline:** retain these published prediction defaults for the first morning-video run, record the predictor's actual effective configuration, and use GPU 0 only. These values are not tuned requirements or evidence of suitable production settings. The pinned package defaults to one-to-many/external NMS; optional `nms=False` requests the other head. Record the actual backend `end2end` state instead of asserting a head mode from a model family name. `quantize=None` is the native baseline, not an optimization experiment.

## Actual local compatibility validation

**EXPERIMENT RESULT — Codex CPU only:** the [retained smoke report](evidence/phase_2/cpu_smoke/cpu_smoke_report.json) records successful model loading and inference on native TOR3-PAGI frames 0 and 7718. Python 3.12.14, PyTorch 2.13.0+cpu, torchvision 0.28.0+cpu, and Ultralytics 8.4.175 were used in an isolated virtual environment. The actual task is `detect`, all 80 model labels match the checkpoint, native coordinates/confidences pass validation, and no track IDs are produced. The observed backend is `end2end=False`. This two-call smoke test does not establish representative runtime or Kaggle CUDA compatibility.

Actual raw/annotated PNGs are retained under [CPU evidence](evidence/phase_2/cpu_smoke/). The visible motorcycle rider in frame 7718 has both `person` and `motorcycle` boxes. Therefore raw `person` is not an accepted product pedestrian label. Frame 0 also retains a raw `bench` prediction on a roadside wooden structure; all classes remain inspectable. Neither observation is a formal correctness metric.

**EXPERIMENT RESULT — software checks only:** [ten helper checks](evidence/phase_2/notebook_helper_validation.json) passed: sequential stream/output retention, bounded-prefix and zero-detection rows, invalid boxes, midstream failure/partial evidence, wrong input hash, invalid official-asset hash before loading, invalid frame limit, evidence-path escape, empty decoding, and the actual CPU runtime's missing-CUDA guard. Video/predictor stubs are explicitly identified; they do not establish dataset or GPU results. Notebook format, compilation, and empty source outputs passed.

## Kaggle execution — technical baseline complete

**STATUS — PASS within Phase 2 scope:** the actual one-video CUDA run, retained predictions/annotations, and subsequent visual review satisfy the frame-level detection objective. This is not acceptance of model quality, tuned parameters, product mapping, or the later pipeline.

**EXPERIMENT RESULT — submission only:** the official authenticated API created the separate private [Phase 2 notebook](https://www.kaggle.com/code/chrisbiran/traffic-counter-phase-2-yolo26m), version 1, and submitted a batch execution. [Submission receipt](evidence/phase_2/kaggle_job/submission_receipt.json) and [authenticated source readback](evidence/phase_2/kaggle_job/source_readback_verification.json) are retained. The Phase 1 editor was preserved. The batch finished with worker status `COMPLETE`. Later source version 2 is a Markdown-only `QUICK_SAVE` clarifying restart/Run All and curated evidence; executable cells are unchanged, and the measured result belongs to batch version 1.

For a new experiment, restart the kernel and **Run All**. Reusing only the inference cell can reuse predictor warmup/state; the fresh-run timing and sample manifest are the reproducibility basis. GPU 0 is the tested target of this notebook baseline. Selecting a different GPU index requires validating Ultralytics' logical-device normalization and the surrounding CUDA operations; GPU scheduling is not implemented.

### Actual retained result

**EXPERIMENT RESULT — Kaggle, run `20261011T052950_360560Z_ed399fb8`:** [original JSON report](evidence/phase_2/20261011T052950_360560Z_ed399fb8/detection_report.json), [original Markdown report](evidence/phase_2/20261011T052950_360560Z_ed399fb8/detection_report.md), and [artifact audit](evidence/phase_2/20261011T052950_360560Z_ed399fb8/artifact_audit.json) establish:

| Field | Actual result |
|---|---|
| Input | SHA-identified TOR3-PAGI, 1280 × 720, 10,282 processed frames matching metadata |
| Runtime | Python 3.12.13; Ultralytics 8.4.175; PyTorch 2.10.0+cu128; torchvision 0.25.0+cu128; OpenCV 4.13.0 |
| CUDA | Available; two visible Tesla T4s; predictor actually uses **cuda:0 only** |
| Backend | Native PT, FP32 (`fp16=False`), `end2end=False`, mode `predict` |
| Retained stream | 10,282 sequential rows, frame 0–10281; input/class/bounds/confidence/hash checks passed |
| Prediction settings | Published untuned defaults resolved as documented above; no class filter, geometry ROI, or enhancement |
| First call including setup/warmup | 3.0871 seconds |
| Subsequent mean library inference | 13.8955 ms/frame, 10,281 calls |
| Subsequent mean external prediction call | 16.9797 ms/frame |
| Whole decode/predict/JSONL/sample loop | 195.9344 seconds; 52.4767 processed frames/second |
| Decode read time within loop | 12.7225 seconds |

The loop includes serialization and annotation/sample IO; those do not have independent timer counters. The library inference stage excludes warmup and is distinct from overall throughput. Setup/asset acquisition and Kaggle worker provisioning are not included in the loop. No system-comparison or real-time production requirement is implied. Twenty-seven independent artifact checks passed; the five raw PNGs also match the earlier actual Phase 1 native frames byte-for-byte and pixel-for-pixel.

### Actual sampled visual review

The original Kaggle reports retain their honest export status `completed_decoder_stream_manual_review_pending`. A separate [subsequent Codex AI-assisted review](evidence/phase_2/20261011T052950_360560Z_ed399fb8/manual_detection_review.md) records direct inspection of all five native original/annotated pairs; their source reports were not rewritten to pretend Kaggle human review occurred.

- Frames 2570 and 5140 show `person` and `motorcycle` boxes on the same rider. Product pedestrian-versus-rider mapping remains OPEN.
- Frame 7711 shows an entering scooter cropped at the right boundary and covered by burned-in text. Its right-hand region has `handbag/person` predictions; the retained frame row has no `motorcycle` box localizing that scooter. This is one observed audit case, not a recall estimate or measured failure rate.
- Frames 0 and 10281 retain non-target `bench` predictions on roadside wooden structures. All raw classes remain inspectable; these outputs are not traffic totals.

**OPEN / limits:** suitable thresholds/image settings, pedestrian/rider and bus/angkot mapping, difficult-event frequency, unsampled detector errors, night detection, future hardware/runtime compatibility, and all tracker/ReID/counting decisions. Decode EOF versus failure and authoritative source timestamps remain unresolved. Matching metadata does not guarantee integrity. No ground truth, formal accuracy metrics, tracker, ReID, night enhancement, crossing, or counting was evaluated.

**PROPOSAL — next task, requiring the next user instruction:** Phase 3 BoT-SORT integration verification and persistent-track inspection on one video. Preserve raw class evidence, investigate observed detection gaps/cropped entries and identity fragmentation, and keep ReID experiments/geometry/counting within their later phase scopes. Do not tune away an observed case or claim improvement without a controlled executed comparison.
