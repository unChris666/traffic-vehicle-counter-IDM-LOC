# Project Context

## 1. Objective and Status

**REQUIREMENT:** Build a production-oriented traffic counter that processes real-world road videos and produces auditable counts by object category and recording period.

The primary use case is traffic around a retail store/location. Development begins with a Kaggle GPU prototype for one video. Modular Python, UI, Docker, and GPU VM deployment follow only after the core pipeline is stable and manually audited.

**FACT — current evidence:** Phase 0 specifications, the Phase 1 tool, historical Kaggle reports, and [actual TOR3 visual reviews](evidence/phase_1/20261011_TOR3/README.md) are available. The latest retained Kaggle reports match the two TOR3 identities, sampling, and earlier AI-assisted Codex reviews; [Phase 1 acceptance](PHASE_1_ACCEPTANCE.md) is PASS for these two videos only. Uploaded-video byte identity remains unverified. Historical `TDLE-PAGI` manual observations and other inputs remain unresolved. The user's conditional instruction authorized Phase 2. Official YOLO26M assets/API, Ultralytics 8.4.175, CPU smoke, and the selected Kaggle `cuda:0` baseline are verified. [The GPU report](evidence/phase_2/20261011T052950_360560Z_ed399fb8/detection_report.json) records 10,282 processed TOR3-PAGI decoder frames and matching serialized rows. The [Phase 2 review](PHASE_2_REVIEW.md) passed its defined technical objective without rerunning detection, satisfying the user's condition for Phase 3. Direct BoT-SORT subsequently completed all 10,282 cached rows in Kaggle with verified input/video identity, no YOLO inference, CPU association, ReID disabled and GMC none. See [detection status](YOLO_DETECTION.md) and [tracking execution/review](BOTSORT_TRACKING.md). The subsequently authorized [Phase 4 comparison](REID_EXPERIMENT.md) completed ReID off/on on the same 10,282 cached frames, with a verified dedicated external encoder, actual CUDA appearance inference and CPU association. The tested person-domain setting is not selected as the current vehicle-ReID default; priority duplicate/class-handoff problems remain and physical-identity benefit is unestablished. Product mapping, tuned settings, final vehicle-ReID configuration and generalization remain OPEN. [Phase 5 readiness](PHASE_5_READINESS.md) recorded conditional geometry readiness at that time. The user subsequently authorized the staged workflow in [PHASE_5_TASK.md](PHASE_5_TASK.md). Its earlier visual-feedback/revision stage established the scaled-coordinate correction: [latest G2 feedback](evidence/phase_5/feedback/G2_review_001.json) clarifies that the supplied coordinates came from a scaled image, not native 1280 × 720 pixels. The original display dimensions and crop/offset mapping remain UNKNOWN. The user subsequently delegated an adjustable default in [feedback 002](evidence/phase_5/feedback/G2_review_002.json), so recovering that original size is no longer a prerequisite to proposing G3. G2 and its bounded placement screening retain historical evidence of the earlier assumption, not validation of the new template or intended gate. Subsequent [G3 approval](evidence/phase_5/feedback/G3_review_001.json), reaffirmed with the same A points, accepts the qualitative [geometry contract](GEOMETRY_CONTRACT.md). The prototype executed40/40 synthetic tests and six cached-track geometry configurations, followed by independent audit and targeted original-pixel review; see [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md). These are diagnostics, not traffic counts or model-quality evidence. Suitable numerical defaults remain OPEN. The user subsequently selected Phase6 Option A, implemented under the [audit-gated physical-passage contract](COUNTING_CONTRACT.md). [Actual Phase6 execution and review](PHASE_6_REVIEW.md) consume the retained Phase4/5 evidence without model or geometry-state-machine reruns: 18 accepted events, 141 pending audit items and 7 rider/component candidates rejected. Positive bounded pixel review gates unit/category/identity; unresolved taxonomy, unit changes and geometric ambiguity remain outside the accepted subtotal. This is not a complete-video traffic result or model/counting accuracy evidence. Phase7 has not started.

**EXPERIMENT RESULT — Phase 6 Option B, 13 October 2026 (Asia/Jakarta):** the authorized [component/episode comparison](PHASE_6_OPTION_B_TASK.md) executed on CPU against retained `reid_on` measurements, with fresh geometry replay on vehicle-only episodes and no detector/tracker/encoder inference. [Final v1 run](evidence/phase_6/20261013T104301_354775Z/report.json) passed 63/63 synthetic tests and produced one automatic motorcycle event for vehicle ID1772/rider ID1774, plus five pending vehicle candidates in the declared 13-ID/six-window case scope. The event uses motorcycle origin frame 7716, measured crossing 7721→7722 and confirmation 7722; the earlier person origin and rider crossing are excluded. Episode-only ablation accepts none. Supported global relations require additional passage-local evidence before acceptance; full vehicle-episode category evidence is explicitly offline/noncausal. Initial v0 is retained as superseded after an earlier 923 passage relied on later identity support. These results do not replace Option A's historical aggregate, establish full-video traffic volume or demonstrate counting accuracy. Automatic duplicate 964/973, physical identity for the user-classified car 1323, suitable product settings, final vehicle-ReID and cross-video generalization remain unresolved; see [actual comparison review](PHASE_6_OPTION_B_REVIEW.md). Phase 7 has not started.

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

**EXPERIMENT RESULT — actual weights:** the verified YOLO26M asset has 80 raw labels, including `0: person`, `2: car`, `3: motorcycle`, `5: bus`, and `7: truck`; no `angkot` label exists. See [model specification](MODEL_SPEC.md) and [asset verification](evidence/phase_2/asset_verification.json). **OPEN:** automatic product-category mapping and pickup/bus/angkot taxonomy. The subsequent [Phase6 contract](COUNTING_CONTRACT.md) requires positive unit/role/category review; riders/passengers are not independent vehicle units. A CPU sample places `person` and `motorcycle` boxes on the same rider; `person` must not silently become `pedestrian`.

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

**HISTORICAL — G2 coordinate clarification, superseded by accepted G3 below:** the user retains line `P1=(4.5,516.5)` and `P2=(936.4,305.4)`, Side B cap `X=875`, and bottom-center (BC), but confirms the coordinates are from a scaled image rather than native video pixels. The cap does not truncate the full line. TOR3-PAGI `A_TO_B` means approaching and `B_TO_A` means moving away; a spatial side alone does not establish motion direction. The latest requested A point set is `(4.5,516.5)`, `(4.5,348.2)`, `(936.6,305.8)`, `(557.5,165.3)`. All four were labeled P1; the supplied list is not an accepted polygon traversal order. Original display dimensions and cropping/padding remain UNKNOWN, so G2 is not an adoptable native-pixel configuration. Preserve G1/G2 artifacts unchanged. The later delegation authorizes a new explicit template proposal, not reconstruction of the unknown original image. See [coordinate feedback](evidence/phase_5/feedback/G2_review_001.json), [default delegation](evidence/phase_5/feedback/G2_review_002.json) and [PHASE_5_TASK.md](PHASE_5_TASK.md).

**USER-SELECTED TRANSFER POLICY:** use a relative reusable template with review for each video. The user does not know the original scaled-image dimensions and delegates an adjustable default; do not require the original dimensions again. The earlier G2 assumption that the numbers were native 1280 × 720 pixels remains superseded.

**CONFIRMED — accepted G3:** [G3 feedback](evidence/phase_5/feedback/G3_review_001.json) accepts the new 960 × 540 reference/B and names unchanged A points P1A/B/C/D. [Accepted geometry](evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json) preserves every numerical line/point/cap value and uses simple A perimeter P1A→P1B→P1D→P1C. Normalize with `u=x/960`, `v=y/540`, then map explicitly to a target native frame `(u×width, v×height)`. This is a new reference, not recovery of the UNKNOWN original display size/crop. The [geometry contract](GEOMETRY_CONTRACT.md) and [actual Phase5 review](PHASE_5_REVIEW.md) document accepted measured BC/boundary/gap rules and executed validation. Per-video transfer and all-video reliability remain unproved; historical proposals are unchanged.

**REQUIREMENT — future UI:** provide a page for setup/editing of the line and polygons, reiterated by the user in the default delegation. This belongs to Phase 11; no production UI is implemented in the current Phase6 prototype.

## 7. Detection, Eligibility, and Counting

**REQUIREMENT:** Detection, tracking, eligibility, and counting are separate responsibilities.

YOLO may detect objects throughout the frame. A tracked object becomes eligible for counting only after satisfying the configured geometry/entry rules. Do not filter detections by Side A/B before tracking or restrict detection to these regions without a later explicitly authorized experiment.

An object already in an eligible region in the first processed frame may be initialized/tracked, but its presence does not produce a count. Counting requires a subsequent valid track crossing and arrival in the opposite side.

## 8. Track Information and Robustness

The intended conceptual information includes track identity, bounding box, category evidence, confidence, time/frame references, trajectory/history, origin/entry side, eligibility, direction, and counting state. Scoped notebook geometry/counting schemas now exist; the final production schema remains OPEN. See [API_CONTRACT.md](API_CONTRACT.md).

**CONFIRMED — user selection:** bottom-center (BC) is the anchor for the current TOR3-PAGI geometry revision. This is a design selection, not evidence that BC is universally best or physically locates road contact. **CONFIRMED — accepted G3 source:** operational BC uses the raw detector-linked emitted-track `raw_bbox`; Kalman-filtered boxes and predictions do not confirm geometry. Boundaries are neutral; touch-only is insufficient; endpoint/gap passage remains ambiguous. Phase6 adds the [audit-gated counting contract](COUNTING_CONTRACT.md), without changing these rules. Suitable numerical settings, lifecycle tuning, automatic category/identity recovery and universal BC robustness remain OPEN.

**REQUIREMENT:** Counting must protect against bounding-box jitter, trajectory fluctuation, temporary detection loss, re-entry, and noisy crossing/re-crossing. Occlusion, overlaps, diagonal movement, variable viewpoints between videos, handheld shake, and dark scenes must be inspected and documented. Do not claim that any model configuration already solves them.

## 9. Ground Truth and Validation

**FACT:** There is currently no formal ground-truth dataset.

- Do not invent manual labels or report accuracy, precision, recall, F1, MAPE, or counting performance without appropriate ground-truth evidence.
- Later validation may use deterministic/synthetic geometry tests, software invariants, visual inspection, and manual audit.
- A future annotated benchmark subset is a proposal and requires a documented protocol before quantitative claims.
- A screenshot is visual context, not an executed experiment or a quantitative validation result.

## 10. Phase Boundaries and Related Decisions

Work follows [CODEX_WORKFLOW.md](../CODEX_WORKFLOW.md), from Phase 0 specification through Phase 13 GPU VM deployment. Prove the single-video pipeline before eight-video processing or multi-GPU orchestration. The eventual GPU target detects available GPUs dynamically: one GPU processes sequentially; two GPUs may process videos in parallel with one active video assigned to each GPU where resources permit.

The Phase 0 task established documentation only. Phase 1's inspection tool and retained TOR3 evidence passed [scoped acceptance](PHASE_1_ACCEPTANCE.md). The single-video, full-frame YOLO26M Phase 2 baseline completed on one Kaggle GPU, with actual execution and sampled review documented separately from Phase 1. Its retained-evidence review authorized the scoped Phase 3 transition under the user's earlier instruction. The cached-detection BoT-SORT baseline then completed in Kaggle; its actual execution, temporal review and acceptance limits are in [BOTSORT_TRACKING.md](BOTSORT_TRACKING.md). The later authorized [Phase 4 contribution experiment](REID_EXPERIMENT.md) completed its controlled off/on comparison and actual bounded review, with the tested setting not selected as the current vehicle-ReID default. No quality or generalization claim follows from execution alone. [Phase 5 readiness](PHASE_5_READINESS.md) was an analysis, not implementation authorization at that time. The subsequently authorized [Phase5 task](PHASE_5_TASK.md) completed accepted G3/qualitative rules, synthetic validation, retained-track geometry replay and bounded pixel review; see [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md). The later user-selected OptionA authorizes and implements [Phase6 counting](COUNTING_CONTRACT.md), with actual retained-evidence execution in [PHASE_6_REVIEW.md](PHASE_6_REVIEW.md). Crossing diagnostics and reviewed passage events are now implemented; suitable numerical defaults, taxonomy, automatic identity recovery and complete-video traffic results remain unresolved. UI, Docker, stabilization/GMC, night enhancement, other-video counting and orchestration have not started.

See [OPEN_DECISIONS.md](OPEN_DECISIONS.md) for confirmed/open decisions, [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md) for preliminary configuration, and [API_CONTRACT.md](API_CONTRACT.md) for implementation-independent boundaries.
