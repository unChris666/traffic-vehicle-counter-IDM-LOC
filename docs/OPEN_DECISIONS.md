# Decision Register

Status: Phase 0 decision register maintained during Phase 1 tool creation. Confirmed means accepted project intent, not verified model availability or measured performance. No actual Kaggle-video inspection, inference, tracking, ReID, counting, or benchmark experiment has been executed in the cloud task. Runtime findings remain unknown until the real dataset is inspected.

Source of this update: the user's clarification prompt and reference-image side confirmation, 2026-10-08 (Asia/Jakarta). These supersede the earlier proposal-only model status, camera-travel interpretation, pre-tracker ROI filter, center-anchor default, and unspecified projection discussion. They do not provide model assets, numerical parameters, or experiment results.

Read with [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), [MODEL_SPEC.md](MODEL_SPEC.md), [COUNTING_LOGIC.md](COUNTING_LOGIC.md), [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md), [API_CONTRACT.md](API_CONTRACT.md), and [EVALUATION.md](EVALUATION.md).

## CONFIRMED

- First implementation environment: Kaggle Notebook with GPU. Prove a single-video pipeline before eight-video processing, production modularization, UI, Docker, GPU VM deployment, or multi-GPU orchestration.
- YOLO26M is the target detector; Kaggle uses the Ultralytics Python API. Actual package/assets/compatibility are not yet verified. Production dependencies will later be pinned in Docker.
- BoT-SORT is the target tracker; ReID-assisted identity association is part of the target architecture. Replacing BoT-SORT or removing ReID requires an explicit architecture decision, including after experiments.
- The camera stays at its recording location during each video; handheld shake/jitter is possible. It does not travel through the environment. Position/orientation may differ between videos.
- Initial geometry uses independently configured per-video pixel coordinates: Side A polygon, diagonal counting line, Side B polygon. No world-coordinate projection, homography, geographic projection, fixed angle, fixed orientation, or fixed dimensions are required.
- Reference example mapping confirmed by the user: A is upper-left of the yellow diagonal and approaching the camera; B is lower-right and moving away. This applies to that example only. Other videos require their own polygons/line and semantic metadata; no image-axis rule follows from the example.
- `A_TO_B` means origin in A → line crossing → arrival in B. `B_TO_A` is the reverse. Approaching/away labels are per-video semantic metadata, not inferred from X/Y or left/right/top/bottom motion.
- YOLO detects throughout the frame. Tracking, geometry eligibility, and counting are separate. Initial-frame objects may be tracked and establish an eligible origin, but count only after a subsequent valid crossing reaches the opposite side.
- Counting is derived from eligible persistent-track crossing events. Bounding-box contact is insufficient. Protect against jitter, trajectory fluctuation, temporary detection loss, re-entry, and noisy re-crossing; count once per valid event.
- Geometry anchor remains OPEN without a default. Candidate center/bottom-center choices require evidence.
- No formal ground-truth dataset exists. No accuracy, precision, recall, F1, MAPE, or counting-performance claim is justified by this specification or visual audit.
- Current authorization covers Phase 1 video inspection only. The user supplied Kaggle dataset mount `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos` and notebook editor `https://www.kaggle.com/code/chrisbiran/new-traffic-counter/edit`. These are supplied execution locations, not verified dataset contents. Do not implement model inference, tracking, crossing/counting, stabilization, or select model/counting thresholds in this phase.

## OPEN TECHNICAL DECISION

| Decision | Known | Unknown | Evidence needed | Proposed experiment / next action |
|---|---|---|---|---|
| Detector assets and runtime | YOLO26M; Ultralytics Python API; Kaggle target. | Exact supported package version, authoritative weights, dependencies, Python/CUDA compatibility, callable usage. | Actual assets, official package/model documentation, available Kaggle runtime. | Phase 2: verify provenance and compatibility, then model loading/inference smoke test. Do not substitute a detector silently. |
| Model-to-product classes | Target categories: pedestrian, motorcycle, car, bus/angkot, truck. | Actual labels/IDs and defensible bus/angkot mapping. | Verified model class metadata and product-category interpretation. | Phase 2: inspect label mapping and representative detections; document any unresolved category coverage. |
| BoT-SORT/ReID integration | Both are accepted targets; ReID supports identity association. | Actual tracker implementation/capabilities and embedding integration boundary. | Verified library/version documentation and exposed configuration. | Phase 3–4: integration verification and identity-association experiments; missing capability needs explicit resolution. |
| Geometry representation | Per-video pixels, line, A/B polygons; arbitrary diagonal placement. | Coordinate convention, decoded/resized-frame relationship, anchor representation, boundaries, polygon/line validation, overlap treatment. | Video dimensions and a documented consistent convention. | Phase 5: synthetic boundary, diagonal, touch/parallel, transition, and coordinate-consistency tests. Anchor choice is evaluated separately below. |
| Eligibility and lifecycle | Geometry eligibility is separate from detection/tracking; initial-frame tracks need later crossing. | Confirmation, minimum age, entry gates, buffer/lost duration, missing-frame rules. | Real track observations and supported tracker settings. | Phase 3–6: controlled gap/entry cases and documented parameter trials without invented values. |
| Event identity and repeated visits | One accepted crossing must not be duplicated by noise, gaps, re-entry, or unstable IDs. | Duplicate identity scope across ID changes; genuine repeated crossings/U-turn policy; event timing through gaps. | Explicit counting policy plus audited trajectory/identity evidence. | Phase 5–6: synthetic cases and later real-track audit; clarify genuine repeats before implementing that behavior. |
| Category/confidence policy | Events require auditable category/track evidence. | Category stabilization, confidence meaning/summary, uncertain-category handling. | Verified detection/tracking fields and observed category changes. | Phase 2–6: inspect class consistency; document policy and test it independently of aggregate counting. |
| Config/API encoding | Logical boundaries and reproducible configuration are required. | Final field types, IDs, serialization, frame/time convention, schema validation. | Accepted conceptual contracts and actual library outputs. | Phase 0–6: document choices before their implementation; future deterministic schema/boundary tests. Proposed names are not callable APIs. |
| Production persistence/overrides | Original machine results must survive manual overrides. | Storage, versioning, override audit schema, output retention. | Concrete production workflow and persistence requirements. | Before Phase 10–11: document a focused production design; not required for early prototype. |
| Device/runtime scheduling | Kaggle GPU first; later dynamic GPU discovery and one active video per GPU target. | Actual resources, compatible runtimes, scheduling behavior. | Actual environment/resource inspection in the relevant phase. | Verify single-video device assignment first; orchestration only in the explicitly authorized later phase. |

## REQUIRES VIDEO EVIDENCE

| Question | Known | Unknown | Evidence needed | Proposed inspection, not yet executed |
|---|---|---|---|---|
| Actual input characteristics | Documentation describes approximately five-minute, approximately 30 FPS videos with potentially variable dimensions. A sample image is provided. | Actual duration, FPS, frame count, resolution/aspect ratio, time metadata, input completeness. | Actual original video files and supplied recording/location metadata. | Phase 1 metadata inspection. A screenshot cannot establish these properties. |
| Shake and geometry alignment | Camera stationary in place; small handheld shake possible. | Magnitude/frequency of shake and effect on boxes, trajectories, line, and polygons. | Representative temporal samples from actual videos. | Phase 1 inspect shake across frames and document visible geometry drift; do not implement stabilization. |
| Per-video geometry/semantics | Reference example A/B labels confirmed; arbitrary per-video geometry required. | Actual coordinates, usable regions, side mapping for other videos, occluded/out-of-frame paths. | Full frames/temporal samples and per-video semantic confirmation. | Phase 1 inspect paths and candidate geometry; retain unknown coordinates. Final geometry implementation belongs to Phase 5. |
| Lighting and hard cases | Night may be very dark; overlap, jitter, and gaps are relevant risks. | Actual brightness/visibility, scene variation, occlusion and traffic density. | Day/night examples and representative difficult segments. | Phase 1 capture representative samples and failure-case notes, without claims of detector/tracker performance. |
| Initial-frame/re-entry scenarios | Initial-frame objects need later crossing; noise/re-entry must not duplicate an event. | Which difficult starts, exits, returns, or reversals appear in the real recordings. | Temporal video evidence. | Phase 1 inventory observed scenarios; later phases test their handling. |

## EXPERIMENT REQUIRED

| Decision | Known | Unknown | Evidence needed | Proposed experiment, not yet executed |
|---|---|---|---|---|
| Anchor choice | Bounding-box center and bottom-center are candidates; neither is selected. | Which point yields appropriate side/crossing evidence for the scenes and categories. | Same tracks under candidate anchors, configured geometry, and visual audit. | Phase 5 compare candidate points on identical trajectories/segments plus synthetic geometry cases. No default until documented. |
| ReID configuration/benefit | ReID is a target, not a proven improvement. | Model/weights, embeddings, gallery policy, thresholds, association behavior, resource cost. | Verified implementation and difficult track examples. | Phase 4 controlled comparison with ReID disabled where possible, same inputs/settings; record identity observations and regressions. An experiment does not silently authorize removal. |
| GMC/stabilization need | Stationary handheld recording may shake; no strategy selected. | Whether correction is necessary, compatible, or helpful; coordinate effects. | Phase 1 shake/alignment evidence. | Phase 1 inspect only. If warranted, separately authorize and compare a documented correction in the tracking/geometry context. |
| Detector/tracker/counting parameters | Thresholds and lifecycle parameters are tunable and currently unspecified. | Suitable values, robustness to gaps/jitter, impact on identity and accepted events. | Actual detector/tracker capability and representative tracks. | Relevant Phase 2–6 controlled configuration trials, with recorded inputs, settings, observations, and deterministic counting checks. |
| Night preprocessing | Enhancement is experimental; no variant selected. | Whether gamma, exposure, contrast, sharpening, or combinations help or harm. | Same night samples, stable baseline, equivalent evaluation procedure. | Phase 7 controlled variants; preserve before/after evidence and report failures as well as successes. |

## Phase 1 readiness and limits

The documentation can define a focused Phase 1 inspection task without deciding detector thresholds, anchor, ReID settings, or stabilization. **Execution readiness still requires actual videos and their source/metadata**, which are not established by a reference image.

Phase 1 tool implementation is now authorized. Run `../notebooks/01_video_inspection.ipynb` in Kaggle against one explicitly selected discovered video, inspect metadata and temporal evidence, and record manual observations. See [VIDEO_INSPECTION.md](VIDEO_INSPECTION.md) for actual execution status. Tool validation on a synthetic fixture does not resolve any real-video question in the tables above. Do not implement inference, tracking, crossing, counting, or stabilization, and do not advance to Phase 2 in this task.
