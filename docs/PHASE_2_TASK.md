# Phase 2 — YOLO26M detection on one video

## Authorization and gate

**STATUS — technical baseline completed:** actual one-video Kaggle CUDA execution, retained artifacts, and five-frame AI-assisted visual review passed the Phase 2 gate with explicit quality/mapping/timing limits. See [executed detection status](YOLO_DETECTION.md). This does not authorize Phase 3.

**REQUIREMENT:** the user authorized Phase 2 after reviewing the supplied TOR3 Kaggle reports if Phase 1 met its objective. [Phase 1 acceptance](PHASE_1_ACCEPTANCE.md) records PASS with explicit timing, sampling, and geometry limits. Acceptance establishes input understanding, not detector performance or ground truth.

## Scope

Implement `notebooks/02_yolo_detection.ipynb` as a separate Kaggle notebook. Verify the actual package and official weights, CUDA/device availability, model loading, and class metadata before frame-level inference. Process ONE video sequentially and retain configuration, timings, raw predictions, and annotated representative samples.

**PROPOSAL — first baseline:** use the already discovered and reviewed `TOR3-PAGI.mp4`, full-frame inference, one explicitly selected GPU (`DEVICE=0`), and the verified package's published prediction defaults. This is an untuned experiment baseline, not an accepted production configuration. Other image sizes/confidence/suppression variants remain later controlled experiments.

## Verified assets

- Package: `ultralytics==8.4.175`, published PyPI wheel hash `16245f680cb6c27856398b3d78a4f4e43d583d0f0c65de0b22431526881b1e1d`, independently downloaded and matched.
- Weights: [official `yolo26m.pt`, release v8.4.0](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26m.pt), 44,255,705 bytes, SHA-256 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`, independently downloaded and matched to the GitHub release digest.
- Actual checkpoint metadata exposes 80 classes, including `person`, `car`, `motorcycle`, `bus`, and `truck`. There is no `angkot` label. Preserve raw model labels; product mapping remains OPEN.
- API source in the pinned wheel verifies `YOLO(actual_weights_path)` and `model.predict(source=opencv_bgr_frame, device=...)`, with native-frame `boxes.xyxy`, `boxes.cls`, `boxes.conf`, `orig_shape`, `names`, and `speed`.

These are authoritative asset/source checks. They do not by themselves establish model loading, CUDA compatibility, or project inference performance. See [detection status](YOLO_DETECTION.md) for actual execution evidence.

## Constraints

- No tracker, ReID, persistent IDs, trajectories, line crossing, counting, geometry coordinates, night enhancement, stabilization, multi-GPU orchestration, UI, or Docker.
- Do not substitute another model or silently fall back from requested CUDA to CPU.
- All model classes remain inspectable. Do not invent class IDs, map `bus` to `angkot`, or turn per-frame boxes into traffic counts.
- Record package/runtime/model identities, video hash, effective settings, explicit device, and source/frame/timestamp uncertainty. Do not assume exactly 30 FPS.
- Distinguish first-call/warmup, inference, decode, and total processing time; disclose where annotation/serialization IO is included rather than claiming independently measured counters. Performance here means observed runtime, not accuracy or counting quality.
- Retain failure status and partial-run scope. Keep original videos, weights, and executed notebook outputs outside GitHub source.

## Validation

1. Validate notebook format/compilation and failure paths for missing input/CUDA, wrong input or asset hash, and invalid configuration.
2. Load the verified model and read its actual names/task in an isolated runtime. A local CPU smoke test is compatibility evidence only.
3. Execute in Kaggle on the selected GPU and input; retain manifests, raw frame predictions, timings, and representative annotations.
4. Inspect actual annotations before writing visual detector conclusions. Missing/misclassified objects may be recorded as audit observations; there is no labelled reference set for formal metrics.
5. Report unexecuted checks and remaining class/runtime/configuration decisions. Stop before Phase 3.
