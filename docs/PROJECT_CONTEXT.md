# Project Context

## 1. Objective and Status

**REQUIREMENT:** Build a production-oriented traffic counter that processes real-world road videos and produces auditable counts by object category and recording period.

The primary use case is traffic around a retail store/location. Development begins with a Kaggle GPU prototype for one video. Modular Python, UI, Docker, and GPU VM deployment follow only after the core pipeline is stable and manually audited.

**FACT — current evidence:** Phase 0 specifications, the Phase 1 tool, historical Kaggle reports, and [actual TOR3 visual reviews](evidence/phase_1/20261011_TOR3/README.md) are available. The latest retained Kaggle reports match the two TOR3 identities, sampling, and earlier AI-assisted Codex reviews; [Phase 1 acceptance](PHASE_1_ACCEPTANCE.md) is PASS for these two videos only. Uploaded-video byte identity remains unverified. Historical `TDLE-PAGI` manual observations and other inputs remain unresolved. The user's conditional instruction authorized Phase 2. Official YOLO26M assets/API, Ultralytics 8.4.175, CPU smoke, and the selected Kaggle `cuda:0` baseline are verified. [The GPU report](evidence/phase_2/20261011T052950_360560Z_ed399fb8/detection_report.json) records 10,282 processed TOR3-PAGI decoder frames and matching serialized rows. The [Phase 2 review](PHASE_2_REVIEW.md) passed its defined technical objective without rerunning detection, satisfying the user's condition for Phase 3. Direct BoT-SORT subsequently completed all 10,282 cached rows in Kaggle with verified input/video identity, no YOLO inference, CPU association, ReID disabled and GMC none. See [detection status](YOLO_DETECTION.md) and [tracking execution/review](BOTSORT_TRACKING.md). The subsequently authorized [Phase 4 comparison](REID_EXPERIMENT.md) completed ReID off/on on the same 10,282 cached frames, with a verified dedicated external encoder, actual CUDA appearance inference and CPU association. The tested person-domain setting is not selected as the current vehicle-ReID default; priority duplicate/class-handoff problems remain and physical-identity benefit is unestablished. Product mapping, tuned settings, final vehicle-ReID configuration and generalization remain OPEN. [Phase 5 readiness](PHASE_5_READINESS.md) recorded conditional geometry readiness at that time. The user subsequently authorized the staged workflow in [PHASE_5_TASK.md](PHASE_5_TASK.md). It is now in visual-feedback/revision: [feedback 002](evidence/phase_5/feedback/G1_review_002.json) supplies the revised line, Side B cap and BC anchor. Only bounded read-only placement screening and source/figure checks have occurred; no crossing implementation, synthetic geometry tests or accepted crossing state-machine replay has been executed.

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

Discovery contains metadata for 13 candidates, with dimensions 640 × 480, 640 × 360, 512 × 288, and 1280 × 720; reported average FPS ranges from about 24.003271 to 29.876442 and stream durations from 300.762749 to 344.859778 seconds. The historical TDLE run decoded/sampled one selected video; the new TOR3 runs decoded/sampled two additional inputs with separate reviews. Discovery is not inspection of all 13 candidates. Candidate filenames do not establish store, weekday/weekend, recording-period, night visibility, or completeness of the required eight-video set for a location.

## 3. Camera Condition

**EXPERIMENT RESULT — sampled TOR3 pixels:** both morning/night examples show an oblique roadside view and diagonal vehicle movement. Five 30-frame bursts per video appear `effectively_stationary` qualitatively; this does not prove a tripod, absence of fine shake, or continuous alignment across the recording. Morning road/markings are visible; night has extensive darkness, headlight glare, and some blurred nearby vehicles. Both inputs have a burned-in lower-right metadata overlay that obscures some entering-vehicle pixels. At the time of those Phase 1 reviews, numeric viewing angle, height, actual A/B coordinates/semantics, and anchor remained OPEN. These findings are video-scoped; see the retained evidence above. The later TOR3-PAGI geometry decisions below do not alter the historical observations.

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

**EXPERIMENT RESULT — actual weights:** the verified YOLO26M asset has 80 raw labels, including `0: person`, `2: car`, `3: motorcycle`, `5: bus`, and `7: truck`; no `angkot` label exists. See [model specification](MODEL_SPEC.md) and [asset verification](evidence/phase_2/asset_verification.json). **OPEN:** mapping raw labels to product reporting categories, particularly riders versus pedestrians and bus/angkot. A CPU sample places `person` and `motorcycle` boxes on the same rider; `person` must not silently become `pedestrian`.

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

**CONFIRMED:** YOLO26M, BoT-SORT, and ReID are the target architecture. Official YOLO26M provenance, Ultralytics 8.4.175, CPU frame-API loading/inference, the selected Kaggle CUDA detection baseline, and direct pinned BoT-SORT replay are verified. Phase 4 additionally verified one dedicated external ReID encoder/integration through an actual controlled comparison, but its tested setting was not selected as the current vehicle default. A final suitable vehicle-ReID configuration, tracker settings, identity consistency and compatibility outside the tested runtime remain open. The no-ReID/no-GMC Phase 3 baseline is an isolated experiment, not removal of ReID or a GMC-need decision. Unknown compatibility is not permission to substitute another technology or silently remove ReID.

## 6. Geometry and Direction Semantics

**CONFIRMED:** Initial geometry uses image pixel coordinates. It contains a Side A region/polygon, counting line, and Side B region/polygon. World-coordinate, geographic, and homography projections are not required for the initial prototype.

Side regions lie on the configured opposite sides of the counting boundary. Support per-video line endpoints and polygon vertices, including arbitrary diagonal geometries. The reference diagram is conceptual; do not hardcode an angle, coordinates, image orientation, or polygon dimensions.

**CONFIRMED — reference screenshot only:** Side A is the region on the upper-left side of the yellow line; Side B is the region on its lower-right side. The user confirmed the semantic metadata Side A = approaching the camera and Side B = moving away for this example. The screenshot does not supply labeled polygon boundaries or an approved set of pixel coordinates. This reference mapping must not become a global rule for other videos.

For each video, store the intended semantic metadata with its geometry. Infer a crossing direction from temporal side transitions, never from left/right, top/bottom, or the sign of X/Y movement:

- `A_TO_B`: track starts/enters in Side A → crosses the counting line → reaches Side B.
- `B_TO_A`: track starts/enters in Side B → crosses the counting line → reaches Side A.

**CONFIRMED — current TOR3-PAGI revision:** the user selected `P1=(4.5,516.5)` and `P2=(936.4,305.4)`, capped the Side B polygon at `X=875`, and selected bottom-center (BC). The full line remains intact beyond the B cap. TOR3-PAGI `A_TO_B` means approaching and `B_TO_A` means moving away; a spatial side alone does not establish motion direction. Engineer-adjusted G2 polygons remain a visual proposal. See [feedback 002](evidence/phase_5/feedback/G1_review_002.json) and [PHASE_5_TASK.md](PHASE_5_TASK.md).

**USER REQUIREMENT / OPEN TRANSFER POLICY:** the user requested the line as a reusable default for all videos and reliable behavior. It is a starting template, not proven universal geometry. Its current interpretation uses the G1 native 1280 × 720 frame as an explicit visual-revision assumption. Per-video configuration remains required; resolution/aspect-ratio scaling, viewpoint transfer and cross-video reliability are OPEN and unvalidated.

## 7. Detection, Eligibility, and Counting

**REQUIREMENT:** Detection, tracking, eligibility, and counting are separate responsibilities.

YOLO may detect objects throughout the frame. A tracked object becomes eligible for counting only after satisfying the configured geometry/entry rules. Do not filter detections by Side A/B before tracking or restrict detection to these regions without a later explicitly authorized experiment.

An object already in an eligible region in the first processed frame may be initialized/tracked, but its presence does not produce a count. Counting requires a subsequent valid track crossing and arrival in the opposite side.

## 8. Track Information and Robustness

The intended conceptual information includes track identity, bounding box, category evidence, confidence, time/frame references, trajectory/history, origin/entry side, eligibility, direction, and counting state. Its exact schema is not yet an implementation contract; see [API_CONTRACT.md](API_CONTRACT.md).

**CONFIRMED — user selection:** bottom-center (BC) is the anchor for the current TOR3-PAGI geometry revision. This is a design selection, not evidence that BC is universally best or physically locates road contact. **OPEN TECHNICAL DECISION:** whether operational BC uses the linked raw detection box or Kalman-filtered track box; any proposed box source needs explicit acceptance. Track lifecycle, category stabilization, temporary-gap handling, and identity recovery also remain OPEN.

**REQUIREMENT:** Counting must protect against bounding-box jitter, trajectory fluctuation, temporary detection loss, re-entry, and noisy crossing/re-crossing. Occlusion, overlaps, diagonal movement, variable viewpoints between videos, handheld shake, and dark scenes must be inspected and documented. Do not claim that any model configuration already solves them.

## 9. Ground Truth and Validation

**FACT:** There is currently no formal ground-truth dataset.

- Do not invent manual labels or report accuracy, precision, recall, F1, MAPE, or counting performance without appropriate ground-truth evidence.
- Later validation may use deterministic/synthetic geometry tests, software invariants, visual inspection, and manual audit.
- A future annotated benchmark subset is a proposal and requires a documented protocol before quantitative claims.
- A screenshot is visual context, not an executed experiment or a quantitative validation result.

## 10. Phase Boundaries and Related Decisions

Work follows [CODEX_WORKFLOW.md](../CODEX_WORKFLOW.md), from Phase 0 specification through Phase 13 GPU VM deployment. Prove the single-video pipeline before eight-video processing or multi-GPU orchestration. The eventual GPU target detects available GPUs dynamically: one GPU processes sequentially; two GPUs may process videos in parallel with one active video assigned to each GPU where resources permit.

The Phase 0 task established documentation only. Phase 1's inspection tool and retained TOR3 evidence passed [scoped acceptance](PHASE_1_ACCEPTANCE.md). The single-video, full-frame YOLO26M Phase 2 baseline completed on one Kaggle GPU, with actual execution and sampled review documented separately from Phase 1. Its retained-evidence review authorized the scoped Phase 3 transition under the user's earlier instruction. The cached-detection BoT-SORT baseline then completed in Kaggle; its actual execution, temporal review and acceptance limits are in [BOTSORT_TRACKING.md](BOTSORT_TRACKING.md). The later authorized [Phase 4 contribution experiment](REID_EXPERIMENT.md) completed its controlled off/on comparison and actual bounded review, with the tested setting not selected as the current vehicle-ReID default. No quality or generalization claim follows from execution alone. [Phase 5 readiness](PHASE_5_READINESS.md) was an analysis, not implementation authorization at that time. The subsequent user authorization starts the staged [Phase 5 task](PHASE_5_TASK.md), currently visual-feedback/revision using the supplied line, B cap and BC selection. Dependent rules, synthetic tests and retained-track geometry replay wait for the required geometry/contract review. Crossing/event/count implementation and parameter selection have not occurred; UI, Docker, stabilization/GMC, enhancement, other-video processing and orchestration remain outside the current stage.

See [OPEN_DECISIONS.md](OPEN_DECISIONS.md) for confirmed/open decisions, [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md) for preliminary configuration, and [API_CONTRACT.md](API_CONTRACT.md) for implementation-independent boundaries.
