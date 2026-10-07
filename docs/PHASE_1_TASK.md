# Phase 1 Task — Video Inspection

## Status

REQUIREMENT: Phase 1 is now explicitly authorized by the user. The inspection tool is `../notebooks/01_video_inspection.ipynb`. Actual dataset inspection has not been executed from the current cloud environment; see `VIDEO_INSPECTION.md` for execution status rather than treating this task specification as a result.

The supplied screenshot is a spatial reference, not a video dataset or temporal measurement. The user supplied Kaggle input path `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos` and notebook editor `https://www.kaggle.com/code/chrisbiran/new-traffic-counter/edit`. That path is not mounted in Codex. No actual video is present in this checkout. Kaggle GPU availability and runtime dependencies must be verified by running the notebook in Kaggle.

## Task

Create a small Kaggle-compatible inspection notebook for one actual video. Establish observed input properties and visible handheld shake before selecting model/tracker/counting parameters. Keep input/output paths configurable. Inspect additional supplied videos only within the task's agreed scope; no eight-video processing orchestration yet.

## Read First

- `AGENTS.md` and `CODEX_WORKFLOW.md`.
- `docs/PROJECT_CONTEXT.md`, `docs/COUNTING_LOGIC.md`, and `docs/ARCHITECTURE.md`.
- `docs/OPEN_DECISIONS.md`, `docs/CONFIG_SCHEMA.md`, and `docs/API_CONTRACT.md`.
- `docs/TEST_PLAN.md` and `docs/EVALUATION.md`.

## Prerequisites and setup

- Obtain the actual video identifier/path and its recording-period/store metadata when supplied. Do not invent a Kaggle dataset slug or credentials. Use supported Kaggle input mounts; record unresolved metadata as unknown.
- Confirm the actual Kaggle runtime and available hardware. A GPU is the intended prototype environment, but this inspection task does not establish CUDA or detector compatibility.
- Inspect existing video metadata/decoding tools and install only missing inspection dependencies through verified package sources after selecting the inspection implementation. Record actual versions; no dependency pins are established by this document.
- Cloud preflight commands already executed successfully during Phase 0: `python3 --version`, `git --version`, `ffprobe -version`, and `ffmpeg -version`. Observed versions: Python 3.12.14, Git 2.52.0, FFmpeg/ffprobe 7.1.5. These observations apply to the current cloud instance, not Kaggle, and are not production pins.
- Use the existing isolated checkout. Do not create a Git worktree unless the user requests one.
- No server/service needs to be started for the documentation workflow. No model package or weights need to be installed for Phase 0.

## Scope

- Record container/codec and available duration, frame-rate metadata, width/height, aspect ratio, and frame-count evidence.
- Distinguish metadata-reported frame count/FPS from decoded observations. Report absent or conflicting properties; do not substitute nominal 30 FPS or five-minute duration as measurements.
- Record actual frame/timestamp selection and retain representative unenhanced frames or short clips. The sampling policy is PROPOSAL until documented in the task; no fixed interval is prescribed here.
- Inspect lighting, darkness, occlusion, viewpoint, diagonal motion, and stationary-handheld shake. Record observations with frame/time references.
- Inspect whether shake visibly changes road/line/polygon alignment. Describe implications for future bounding-box/trajectory checks, without claiming to have tested those model outputs.
- Document whether a later GMC/stabilization experiment is warranted. Do not choose or implement a correction strategy here.

## Out of Scope

YOLO inference; BoT-SORT tracking; ReID; final anchor selection; counting; fixed geometry coordinates; stabilization/GMC implementation; night enhancement; multi-GPU scheduling; UI; Docker; deployment; accuracy claims.

## Validation

- Execute the notebook against the identified actual video in the declared runtime, preserving its failure status.
- Confirm the selected file can be opened and representative frames actually decode. Verify retained outputs belong to the current run and input.
- Reconcile reported metadata with observable decode/timestamp evidence where possible; explicitly document variable/unknown FPS and decode failures.
- Record the exact video, tool/dependency versions, input/output configuration, selected frame/timestamp references, and any unrun checks.
- Manual observations must link to actual retained evidence. A software check or visually plausible sample does not establish real-world counting accuracy.

## Deliverables

Phase 1 deliverable locations:

- `notebooks/01_video_inspection.ipynb` — inspection only.
- `docs/VIDEO_INSPECTION.md` — execution status and tool-validation evidence now; actual metadata/observations only after reviewing a Kaggle run. Runtime reports retain the executed metadata table, manual observations, and limitations.
- Generated metadata/frames/clips in a configurable artifact directory outside tracked source. Exact layout and serialization are selected and documented in that task. Do not commit raw videos or invent outputs.
- Update `docs/OPEN_DECISIONS.md` only where actual video evidence changes a decision's status.

## Reporting and next gate

Report files changed, checks executed/passed/failed/unrun, measured metadata, evidence references, assumptions, and remaining unknowns. Phase 1 can establish video characteristics; detector/tracker behavior and the effect of GMC require later authorized experiments.

Before Phase 2, verify the actual YOLO26M asset, Ultralytics package/API compatibility, runtime, and class mapping. Preserve the target technology; report a blocker if unavailable rather than silently substituting a detector.
