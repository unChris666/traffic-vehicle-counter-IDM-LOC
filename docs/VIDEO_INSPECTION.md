# Phase 1 — Video Inspection Execution Status

## Actual dataset status

**FACT — user-supplied execution context:** actual videos are in Kaggle at `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos`. The supplied editor is [new-traffic-counter](https://www.kaggle.com/code/chrisbiran/new-traffic-counter/edit). GitHub contains source and documentation, not the video files.

**FACT — review boundary:** the dataset mount is unavailable in Codex. The user supplied the retained Markdown and JSON reports from an actual Kaggle run; these have been reviewed for internal consistency. The original video, native PNGs, contact sheet, burst manifests/previews, and `run_manifest.json` were not supplied. Their paths/statuses in the reports are references, not independently inspected pixels or verified file existence. The earlier screenshot is not evidence of this run's camera, lighting, or geometry.

**IMPLEMENTATION:** [01_video_inspection.ipynb](../notebooks/01_video_inspection.ipynb) is an output-free inspection notebook. It verifies the execution environment, discovers video candidates and available metadata, requires explicit selection of one video, records metadata provenance, and retains representative and temporal evidence. Manual observations remain UNKNOWN until supported by that run's evidence. This does not implement or validate a detector, tracker, ReID, counting, stabilization, night enhancement, or Phase 2.

## Retained Kaggle execution evidence

**EXPERIMENT RESULT — report-supported, not a new Codex video execution:** [inspection_report.md](evidence/phase_1/20261007T180055_252361Z_27a6f8f3/inspection_report.md) and [inspection_report.json](evidence/phase_1/20261007T180055_252361Z_27a6f8f3/inspection_report.json) are archived byte-for-byte from the user uploads. Run `20261007T180055_252361Z_27a6f8f3` was recorded at `2026-10-07T18:00:55.253136+00:00`. Findings below come from those retained reports, not from executing or reading the source notebook to infer results.

| Selected-video field | Retained evidence |
|---|---|
| Input | `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos/TDLE-PAGI.mp4` |
| File size | 12,506,413 bytes, reported filesystem stat |
| Codec | H.264, reported ffprobe codec |
| Dimensions | 640 × 480 pixels; derived aspect ratio 4:3 |
| Stream duration | 301.058555 seconds; container duration 301.059 seconds |
| Average FPS | 29.761652209830647, ffprobe average rate |
| Nominal FPS | 64.333, ffprobe nominal rate |
| Frame count | 8,960 in ffprobe/OpenCV metadata and both sequential decode passes |
| Input SHA-256 | `7a5e1a3dd55c83549326515398d1eeadc07d223eea171626058fd1bfae61a46c`, reported value; original bytes unavailable for recomputation |

Discovery records metadata for **13 candidates**, not 13 completed visual inspections. Reported dimensions include 640 × 480, 640 × 360, 512 × 288, and 1280 × 720. Average FPS ranges from approximately 24.003271 to 29.876442; stream durations range from 300.762749 to 344.859778 seconds. Only `TDLE-PAGI.mp4` was selected for full sequential decoding and sampling. Filenames do not establish recording period, night conditions, store identity, weekday/weekend, or completeness of the target eight-video set.

Sampling records five representative indices: **0, 2240, 4480, 6719, 8959**. Five bursts each contain 30 consecutive frame records, giving 150 unique frame-evidence records with saved statuses and no missing requested indices. Each burst spans about 0.974 seconds by average-FPS estimation; this is not certified source timing. The source image files and previews were not attached, so this review verifies report records only.

Reported Kaggle environment: Python 3.12.13, four process-available CPUs, OpenCV 4.13.0, NumPy 2.0.2, Pillow 11.3.0, IPython 7.34.0, FFmpeg/ffprobe 4.4.2. `nvidia-smi` reports two Tesla T4 GPUs, each with 15,360 MiB, and driver 580.178.04. These are observations about that run, not dependency pins, proof of model/CUDA compatibility, or authorization for multi-GPU processing.

### Unresolved review and decode limits

- Run status is `evidence_saved_manual_review_pending`; review status is `incomplete_unknown_items`. All **21 manual observations** have null observations and empty evidence lists. Camera stability has no category. There is no retained visual conclusion about camera/road orientation, viewing angle, shake, lighting, vehicle visibility, occlusion, blur, reflections, shadows, entering/exiting or diagonal motion, geometry feasibility/alignment, low-light model risks, failure cases, or technical questions.
- Matching metadata/decode counts support the recorded reads but do not prove source integrity. The stop reason is `read_returned_false: EOF_or_decode_failure_not_distinguished`, and completeness is `not_guaranteed_by_OpenCV`. No confirmed damaged frame or confirmed decode failure is established by these reports.
- Average and nominal rates differ. Backend timestamps also differ from index/average-FPS estimates: for example, representative index 2240 has backend time 76.243918 seconds versus estimated time 75.264639 seconds. Neither is treated as an authoritative timestamp audit. CFR/VFR status, timestamp gaps, and dropped frames remain unknown; inspect original stream timestamps if timing decisions depend on them.
- No architectural or counting decision changed. No detector, tracker, ReID, stabilization, night preprocessing, or model/counting performance experiment is established. No ground-truth evaluation exists.

**PROPOSAL — next review action:** use the existing run's native frames, temporal previews, and original video in Kaggle to fill supported manual observations with references, then regenerate and retain the reports. Investigate timing without inventing a VFR/dropped-frame diagnosis. Additional temporal evidence may be needed for rare shake/events. Phase 2 remains a separate, explicitly authorized task.

## Run in Kaggle

1. Upload/import `notebooks/01_video_inspection.ipynb` into the supplied Kaggle editor. Attach the actual dataset and confirm that its mounted path matches `DATASET_ROOT` in the parameters cell.
2. Run through the **discovery** cell. Read the discovered full paths, filename, extension, size, backend statuses, and available metadata. Candidate extensions are configurable; filenames do not establish recording period or store identity.
3. Set `VIDEO_PATH` in the **parameters** cell to ONE exact path printed by discovery. It starts as `None`; stopping at selection in that state is intentional. Do not substitute a guessed filename.
4. Restart the kernel and run all cells. The default `OUTPUT_ROOT` is `/kaggle/working/video_inspection`; each inspection creates a separate run directory.
5. Inspect the native PNGs, contact sheet, consecutive-frame bursts, and the original video as needed. If an embedded preview is blocked by the notebook frontend, open its saved HTML or inspect the retained consecutive PNGs. Display copies are resized; native PNGs retain decoded dimensions.
6. Fill the **manual_review** cell with observations and evidence paths from the current run, then rerun **manual_review** and **report**. Camera stability requires an allowed human qualitative category and temporal evidence with at least two consecutive frames. Leave unsupported fields unknown. Inspect sufficient temporal evidence before judging shake; short bursts may miss rare movement.
7. Download `inspection_report.md`, `inspection_report.json`, `run_manifest.json`, and relevant evidence from the current run. Update repository findings only after reviewing those executed artifacts. Keep actual videos out of GitHub. Stop before Phase 2.

For another input, change `VIDEO_PATH` to another discovered path, restart, and rerun. Do not carry observations or evidence references from a different run/video.

## Runtime artifacts

Each successful technical inspection retains:

- `run_manifest.json`: input identity, optional streaming SHA-256, environment/dependency versions, configuration, probe/decode evidence, sampling references, warnings, and status.
- `frames/frame_<index>.png`: selected native decoded frames, including short consecutive-frame bursts. Duplicate positions for short videos share a PNG while retaining all five labels.
- `contact_sheet.png`: display thumbnails for beginning, approximately 25%, 50%, 75%, and end of the decoded frame-index range.
- `bursts/<label>/manifest.json` and `preview.html`: local temporal evidence and explicitly approximate/artificial playback timing.
- `inspection_report.md` and `inspection_report.json`: metadata, evidence-based manual observations, camera/lighting/geometry assessment, potential downstream failure hypotheses, open questions, and limitations.

An inspection failure retains `failure.json` and its manifest, re-raises the error, and does not create a success report. Missing dataset or unset selection stops before a run directory is created.

The last sample is the last sequentially decodable frame, not proof that the source file is complete. OpenCV does not distinguish normal EOF from every decode failure. Reported frame-count discrepancies are warnings requiring investigation. Percentiles are based on decoded indices; they are not exact time quartiles for variable-frame-rate input. Backend timestamps and FPS-derived times are separately labelled with uncertainty. Duration from metadata is distinct from the timestamp of the last frame.

## Codex validation evidence

**EXPERIMENT RESULT — tool validation only:** the following checks were actually executed on temporary synthetic fixtures outside the repository. They are not observations about the Kaggle traffic dataset or model performance.

| Check | Outcome |
|---|---|
| Notebook format validation, code-cell compilation, empty outputs/execution counts | Passed |
| Fresh Jupyter kernel: default unavailable Kaggle mount | Expected `FileNotFoundError`; no inspection output directory |
| Fresh Jupyter kernel: fixture discovery with `VIDEO_PATH=None` | Expected selection `RuntimeError`; no inspection output directory |
| Fresh Jupyter kernel: explicitly selected synthetic video through all cells | Passed; frames, temporal previews, and reports produced in `/tmp` |
| Independent synthetic decode/sampling checks | Passed: sample positions/end, raw PNG equality with decoded frames, metadata provenance, one-frame deduplication, and separate rerun directories |
| Unknown metadata/FPS and unavailable ffprobe | Passed: unknowns retained, derived duration labelled as estimate, unknown-FPS timing absent and preview playback labelled artificial |
| Corrupt/empty input and manual-review evidence guards | Passed: explicit failure; invalid stability categories and single-frame temporal claims rejected |
| Generated preview HTML and embedded PNG integrity | Passed |

The full-kernel fixture was a deliberately generated short lossless video, not traffic footage. Its known encoded properties verified the inspection implementation; they must not appear as dataset findings. All executed notebook copies and fixture artifacts remained in `/tmp`. The committed notebook has no execution outputs.

Observed cloud validation environment: Python 3.12.14, OpenCV 5.0.0 (`opencv-python-headless` 5.0.0.93), NumPy 2.5.3, Pillow 12.3.0, nbformat 5.11.1, nbclient 0.11.0, ipykernel 7.4.0, FFmpeg/ffprobe 7.1.5. These are observed tool versions, not production decisions or verified Kaggle versions. The cloud validation virtual environment is `/workspace/.venvs/traffic-inspection`.

## Remaining unknowns

The selected video's reported metadata, decode/sampling records, discovery metadata, and runtime visibility are now known within the report-review limits above. Pixel contents; qualitative camera stability; view/road orientation and any defensible approximate angle; lighting/night visibility; occlusion, blur, reflections, shadows, diagonal paths, entries/exits; per-video geometry feasibility; source integrity/timing; and downstream detection/tracking/ReID risks remain unknown.

Do not automatically assign a 45-degree angle, a shake category, geometry coordinates, or an improvement claim. Low-light risks are hypotheses until later relevant experiments. No ground truth exists and no formal model/counting performance is reported. Technical Kaggle execution is supported by the reports; visual Phase 1 review remains pending. Phase 2 has not started.
