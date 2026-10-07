# Phase 1 — Video Inspection Execution Status

## Actual dataset status

**FACT — user-supplied execution context:** actual videos are in Kaggle at `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos`. The supplied editor is [new-traffic-counter](https://www.kaggle.com/code/chrisbiran/new-traffic-counter/edit). GitHub contains source and documentation, not the video files.

**FACT — observed in Codex:** that dataset mount is unavailable. No actual dataset filenames, file metadata, frames, camera/lighting observations, geometry coordinates, or Kaggle GPU/runtime properties have been inspected here. No Kaggle-video inspection report is claimed. The earlier screenshot remains spatial context only.

**IMPLEMENTATION:** [01_video_inspection.ipynb](../notebooks/01_video_inspection.ipynb) is an output-free inspection notebook. It verifies the execution environment, discovers video candidates and available metadata, requires explicit selection of one video, records metadata provenance, and retains representative and temporal evidence. Manual observations remain UNKNOWN until supported by that run's evidence. This does not implement or validate a detector, tracker, ReID, counting, stabilization, night enhancement, or Phase 2.

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

Actual video metadata and contents; qualitative camera stability; view/road orientation and any defensible approximate angle; lighting/night visibility; occlusion, blur, reflections, shadows, diagonal paths, entries/exits; per-video geometry feasibility; and downstream detection/tracking/ReID risks remain unknown until actual evidence is inspected.

Do not automatically assign a 45-degree angle, a shake category, geometry coordinates, or an improvement claim. Low-light risks are hypotheses until later relevant experiments. No ground truth exists and no formal model/counting performance is reported. Phase 1 real-video acceptance remains pending Kaggle execution and human review.
