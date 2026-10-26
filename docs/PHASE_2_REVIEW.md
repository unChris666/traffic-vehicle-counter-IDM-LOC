<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Phase 2 review and Phase 3 gate

**STATUS — PASS for the defined technical objective.** This review reads retained execution/audit/review evidence; Phase 2 was not rerun. The user's subsequent instruction authorizes Phase 3 if Phase 2 is ready. That condition is met for a one-video, raw-detection tracking experiment, with the limitations below.

The objective in [CODEX_WORKFLOW.md](../CODEX_WORKFLOW.md) is to prove frame-level detection on one video, not establish detector accuracy or production readiness.

## Retained evidence against the objective

All evidence belongs to Kaggle run `20261011T052950_360560Z_ed399fb8`:

- [Original detection report](evidence/phase_2/20261011T052950_360560Z_ed399fb8/detection_report.json).
- [Independent artifact audit](evidence/phase_2/20261011T052950_360560Z_ed399fb8/artifact_audit.json).
- [Subsequent AI-assisted visual review](evidence/phase_2/20261011T052950_360560Z_ed399fb8/manual_detection_review.json).

| Phase 2 objective | Actual retained evidence | Assessment |
|---|---|---|
| Load the real model and verify compatibility | Official YOLO26M asset identity matches the verified digest; Ultralytics 8.4.175 loaded/inferred in the recorded Kaggle runtime. | Met for that runtime/asset combination. |
| Verify GPU execution | Actual predictor used `cuda:0` on Tesla T4, FP32, `end2end=False`; two devices were visible but only one was used. | Met for the selected device; no multi-GPU claim. |
| Inspect actual class mapping | All 80 raw labels were retained, including person/car/motorcycle/bus/truck; no angkot label exists. | Raw-label inspection met; product mapping remains OPEN. |
| Run frame-level inference on one video | 10,282 TOR3-PAGI decoder frames and sequential serialized rows, frame 0–10281; input and output hashes validated. | Met for the decoder-returned stream. |
| Visualize and inspect detections | Five native raw/annotated frame pairs and contact sheet retained; subsequent review explicitly identifies its Codex origin. | Met for the five sampled frames. |
| Measure actual inference performance | Loop 195.9344 s; subsequent mean library inference 13.8955 ms/frame and mean external prediction call 16.9797 ms/frame; first call/setup recorded separately. | Met for that run/configuration; runtime is not model quality. |
| Preserve reproducible configuration/output | Input/model identities, runtime, resolved settings, timings, frame records and sampled artifacts retained; 27 independent artifact checks passed. | Met within documented retention and repeatability limits. |

**EXPERIMENT RESULT:** the reviewed samples show person/motorcycle boxes on the same rider, roadside bench predictions, and a cropped/overlaid entering scooter on frame 7711 without a motorcycle box localizing it. These are concrete audit observations, not accuracy/recall estimates. The original exported report correctly keeps its manual review pending; the separate later review supplies the completed sampled review without changing the original report.

## What remains open

- Pedestrian-versus-rider and bus/angkot product mapping, class stabilization, suitable detector thresholds/image settings, and model quality.
- Continuous visual correctness, night/other-scene performance, and compatibility outside the tested runtime.
- Decoder EOF versus failure, authoritative source PTS, and source integrity. Matching metadata counts and sample pixels do not settle those questions.
- Tracker implementation/lifecycle/settings, ReID configuration, GMC need, geometry anchor/coordinates, crossing and counting policies.

These do not block a scoped Phase 3 experiment: preserve raw classes, consume ordered frame indices, and implement no product-category mapping, geometry or counts. Verified source timestamps remain necessary before accepting time-based semantics; the first tracking experiment must identify any FPS-to-buffer conversion as package behavior rather than verified elapsed-source-time behavior.

## Phase 3 readiness and restrictions

**REQUIREMENT:** do not rerun Phase 2. Reuse the retained `frame_detections.jsonl`, SHA-256 `033a2815d3abbd23327936a1b9d948b2b9b7d312796516e5ee46aec5685be345`, tied to video SHA-256 `606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c`. Reading/decoding the matching source video for frame alignment and track visualization is not detector inference.

**PROPOSAL — controlled tracking baseline:** verify the pinned Ultralytics BoT-SORT implementation and call it directly with the cached detections. Explicitly disable ReID for Phase 3 and GMC for this baseline; ReID remains a confirmed Phase 4 target and GMC need remains OPEN. Record all resolved tracker settings as untuned package defaults/explicit baseline overrides, never as accepted product requirements.

The cache was produced with detector confidence `0.25`. Detections below that cutoff are absent: a tracker cannot recover their discarded boxes or reproduce a lower-threshold detector experiment from this cache. Record the interaction with tracker thresholds and this limitation instead of silently rerunning YOLO. Raw class changes and tracking identity association must also remain inspectable; IDs are not guaranteed physical-object identity.

The exact next scope, validation and deliverables are in [PHASE_3_TASK.md](PHASE_3_TASK.md). No Phase 3 execution result is established by this gate review.
