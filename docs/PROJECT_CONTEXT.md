# Project Context

## 1. Objective and Status

**REQUIREMENT:** Build a production-oriented traffic counter that processes real-world road videos and produces auditable counts by object category and recording period.

The primary use case is traffic around a retail store/location. Development begins with a Kaggle GPU prototype for one video. Modular Python, UI, Docker, and GPU VM deployment follow only after the core pipeline is stable and manually audited.

**FACT — current evidence:** Phase 0 specifications, a sample-video screenshot, the Phase 1 inspection tool, and uploaded Kaggle execution reports are available. The retained Markdown/JSON reports for run `20261007T180055_252361Z_27a6f8f3` have been reviewed for internal consistency. They record one video's metadata/decode/sampling; original video and referenced pixel artifacts were not supplied for this review. All 21 manual observations remain unknown. Model assets, class mapping, and model performance have not been verified. See [VIDEO_INSPECTION.md](VIDEO_INSPECTION.md) for source reports, findings, and limits. The earlier screenshot is not evidence of this run's visual conditions or model/counting performance.

Decision provenance: the user's specification-update prompt and subsequent reference-side confirmation, received on 2026-10-08 (Asia/Jakarta). The reference screenshot was supplied in chat; no image asset or extracted polygon coordinates are stored in this documentation update.

## 2. Input Per Location

**REQUIREMENT:** Each location is associated with:

- Store code / Kode Toko
- Store name / Nama Toko
- Latitude
- Longitude

The target input is eight videos:

| Day group | Recording periods |
|---|---|
| Weekday | morning / pagi; noon / siang; afternoon / sore; night / malam |
| Weekend | morning / pagi; noon / siang; afternoon / sore; night / malam |

**FACT — reported input characteristics, not measurements:** Videos are approximately five minutes long and approximately 30 FPS. Resolution and aspect ratio may vary. Lighting varies by recording period, and night videos may be very dark. Phase 1 must inspect actual metadata and representative frames rather than treat these descriptions as measured properties.

**EXPERIMENT RESULT — retained Kaggle report:** the selected `TDLE-PAGI.mp4` has reported H.264 metadata, 640 × 480 pixels (derived aspect ratio 4:3), 8,960 frames, stream duration 301.058555 seconds, and average FPS 29.761652209830647. Both decode passes record 8,960 frames. The nominal rate is 64.333 FPS; constant/variable frame rate and source timestamps remain unverified. These are report-supported facts about that input, not defaults for all videos or a guarantee of file integrity.

Discovery contains metadata for 13 candidates, with dimensions 640 × 480, 640 × 360, 512 × 288, and 1280 × 720; reported average FPS ranges from about 24.003271 to 29.876442 and stream durations from 300.762749 to 344.859778 seconds. Only the selected video has full decode/sampling evidence. Candidate filenames do not establish store, weekday/weekend, recording-period, night visibility, or completeness of the required eight-video set for a location.

## 3. Camera Condition

**CONFIRMED:** The camera remains at the recording location throughout an individual video. It does not translate to another position during that video.

The camera is handheld and may experience small physical shake/jitter. This must not be modeled as camera travel through the environment. Camera position, orientation, and road layout may differ between videos; geometry is therefore configured independently per video.

The camera views the road obliquely in the reference example. The reported approximate viewing angle is descriptive context, not an exact calibration or a fixed geometry requirement. Vehicle paths may appear diagonal.

**REQUIRES VIDEO EVIDENCE:** Phase 1 must inspect the magnitude and temporal behavior of shake and the stability of the road relative to candidate geometry. Do not implement stabilization or GMC at Phase 0/1. Effects on actual detections and trajectories require the later detection/tracking phases before selecting a strategy.

## 4. Target Object Categories

**REQUIREMENT:** Target reporting categories are:

- pedestrian
- motorcycle
- car
- bus / angkot
- truck

**OPEN TECHNICAL DECISION:** Verify the actual selected weights' labels and the mapping to these reporting categories, including whether and how bus/angkot can be supported. Do not invent class IDs or assume labels shown in the sample overlay come from YOLO26M.

## 5. Confirmed Target Pipeline

VIDEO
→ optional explicitly configured preprocessing
→ YOLO26M detection via the Ultralytics Python API
→ BoT-SORT tracking with ReID-assisted identity association
→ track state
→ trajectory and direction
→ per-video Side A/B geometry
→ valid line-crossing event
→ counting
→ aggregation
→ audit/result export

**CONFIRMED:** YOLO26M, BoT-SORT, and ReID are the target architecture. Package versions, weights sources, actual API compatibility, and ReID configuration remain open. Unknown compatibility is not permission to substitute another technology or silently remove ReID.

## 6. Geometry and Direction Semantics

**CONFIRMED:** Initial geometry uses image pixel coordinates. It contains a Side A region/polygon, counting line, and Side B region/polygon. World-coordinate, geographic, and homography projections are not required for the initial prototype.

Side regions lie on the configured opposite sides of the counting boundary. Support per-video line endpoints and polygon vertices, including arbitrary diagonal geometries. The reference diagram is conceptual; do not hardcode an angle, coordinates, image orientation, or polygon dimensions.

**CONFIRMED — reference screenshot only:** Side A is the region on the upper-left side of the yellow line; Side B is the region on its lower-right side. The user confirmed the semantic metadata Side A = approaching the camera and Side B = moving away for this example. The screenshot does not supply labeled polygon boundaries or an approved set of pixel coordinates. This reference mapping must not become a global rule for other videos.

For each video, store the intended semantic metadata with its geometry. Infer a crossing direction from temporal side transitions, never from left/right, top/bottom, or the sign of X/Y movement:

- `A_TO_B`: track starts/enters in Side A → crosses the counting line → reaches Side B.
- `B_TO_A`: track starts/enters in Side B → crosses the counting line → reaches Side A.

## 7. Detection, Eligibility, and Counting

**REQUIREMENT:** Detection, tracking, eligibility, and counting are separate responsibilities.

YOLO may detect objects throughout the frame. A tracked object becomes eligible for counting only after satisfying the configured geometry/entry rules. Do not filter detections by Side A/B before tracking or restrict detection to these regions without a later explicitly authorized experiment.

An object already in an eligible region in the first processed frame may be initialized/tracked, but its presence does not produce a count. Counting requires a subsequent valid track crossing and arrival in the opposite side.

## 8. Track Information and Robustness

The intended conceptual information includes track identity, bounding box, category evidence, confidence, time/frame references, trajectory/history, origin/entry side, eligibility, direction, and counting state. Its exact schema is not yet an implementation contract; see [API_CONTRACT.md](API_CONTRACT.md).

**OPEN TECHNICAL DECISION:** The geometry anchor may be bounding-box center or bottom-center; neither is an accepted default. Track lifecycle, category stabilization, temporary-gap handling, and identity recovery require defined evidence and later experiments.

**REQUIREMENT:** Counting must protect against bounding-box jitter, trajectory fluctuation, temporary detection loss, re-entry, and noisy crossing/re-crossing. Occlusion, overlaps, diagonal movement, variable viewpoints between videos, handheld shake, and dark scenes must be inspected and documented. Do not claim that any model configuration already solves them.

## 9. Ground Truth and Validation

**FACT:** There is currently no formal ground-truth dataset.

- Do not invent manual labels or report accuracy, precision, recall, F1, MAPE, or counting performance without appropriate ground-truth evidence.
- Later validation may use deterministic/synthetic geometry tests, software invariants, visual inspection, and manual audit.
- A future annotated benchmark subset is a proposal and requires a documented protocol before quantitative claims.
- A screenshot is visual context, not an executed experiment or a quantitative validation result.

## 10. Phase Boundaries and Related Decisions

Work follows [CODEX_WORKFLOW.md](../CODEX_WORKFLOW.md), from Phase 0 specification through Phase 13 GPU VM deployment. Prove the single-video pipeline before eight-video processing or multi-GPU orchestration. The eventual GPU target detects available GPUs dynamically: one GPU processes sequentially; two GPUs may process videos in parallel with one active video assigned to each GPU where resources permit.

The Phase 0 task established documentation only. Phase 1 now creates an inspection tool for actual video metadata and visual evidence, with execution intended in Kaggle. It does not implement inference, tracking, ReID, counting, UI, Docker, or orchestration.

See [OPEN_DECISIONS.md](OPEN_DECISIONS.md) for confirmed/open decisions, [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md) for preliminary configuration, and [API_CONTRACT.md](API_CONTRACT.md) for implementation-independent boundaries.
