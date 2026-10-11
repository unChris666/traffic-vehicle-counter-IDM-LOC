# Architecture

## 1. Strategy and Current Scope

**REQUIREMENT:** Develop phase by phase: Kaggle prototype first, production architecture after the single-video pipeline, eight-video processing, and manual audit are stable.

Phase 0 established specifications and conceptual boundaries. Current executed capabilities are Phase 1 inspection, Phase 2 one-video YOLO26M detection, and Phase 3 direct BoT-SORT replay of the retained detections; see [detection status](YOLO_DETECTION.md), [Phase 2 gate](PHASE_2_REVIEW.md) and [tracking status](BOTSORT_TRACKING.md). The architecture below remains the confirmed target, with later components and unresolved integration details still unimplemented.

## 2. Confirmed Prototype Pipeline

VIDEO INPUT + LOCATION/VIDEO METADATA
→ optional explicitly configured preprocessing
→ YOLO26M detection through the Ultralytics Python API
→ BoT-SORT tracking with ReID-assisted identity association
→ track state
→ trajectory
→ pixel geometry / direction / crossing
→ counting
→ aggregation
→ annotated output + structured result + audit evidence

**CONFIRMED:** YOLO26M, BoT-SORT, and ReID are target architectural choices. Actual versions, assets, runtime compatibility, and ReID configuration must be verified. Unsupported features or adverse experiments require an explicit decision; they do not authorize silent technology substitutions.

Phases 0–9 may remain notebook-oriented while conceptual responsibilities and evidence remain separate. A component named below does not require a separate Python module before Phase 10.

## 3. Functional Boundaries

### Video Input

Reads the actual video and its store/location, day group, period, and identity metadata. Phase 1 inspects duration, FPS, resolution, aspect ratio, frame count, lighting, shake, and representative frames without running inference or counting.

### Preprocessing

Applies only explicitly configured transformations. Night enhancement remains a Phase 7 experiment. No enhancement or stabilization algorithm is an accepted default.

### Detection

Produces frame-level observations across the frame. Does not assign persistent identity, decide track eligibility, or count. A later detection ROI needs an explicitly authorized experiment.

### Tracking and ReID

BoT-SORT associates observations over time. The Phase 3 notebook verifies direct Ultralytics 8.4.175 `BOTSORT` integration and replays the byte-identical retained detection stream against the matching video, without detector inference. Its isolated CPU baseline disables ReID and GMC and retains raw labels, detection linkage and lifecycle evidence. Source association is class-agnostic and uses the latest matched raw class. These settings are recorded untuned experiment configuration, not product identity/category policies.

ReID remains the target appearance-assisted association component. Its enabled model/assets/integration and benefit remain OPEN; cached detector features are unavailable for the verified native `auto` appearance path. Baseline IDs do not guarantee physical-object identity. ReID removal, tracker replacement and GMC need are not decided by the disabled baseline.

### Track State

Maintains track history, lifecycle, category/identity evidence, and the information needed for geometry eligibility. Unconfirmed lifecycle parameters and identity recovery rules remain explicit open decisions.

### Trajectory

Represents temporal movement using the selected geometric anchor. Bounding-box center and bottom-center are candidates; neither is selected. Missing/predicted observation treatment remains open.

### Geometry and Direction

Uses per-video pixel Side A/Side B polygons and counting-line endpoints. Evaluates side membership, track eligibility/origin, trajectory transitions, and line crossing. No homography, geographic projection, fixed angle, or image-axis traffic-direction rule is required.

Side semantics are configured per video. The sample's upper-left Side A/approaching and lower-right Side B/away mapping is confirmed for that sample only.

### Counting

Accepts an eligible track event only after crossing the line and reaching the opposite side. Prevents duplicate recording of the same event. Does not count detections or mere region/line contact. Re-entry, true repeat crossings, noise, gaps, and ID recovery policies need explicit decisions before their implementation.

### Aggregation

Summarizes accepted events by category, recording period, and weekday/weekend while retaining video/location provenance. It must be consistent with the event log.

### Audit and Output

Retains annotated samples/videos, structured event evidence, processing configuration, and observed failures. Future manual value edits preserve original machine results and require a documented override/audit policy.

The detector/tracker must not contain product aggregation logic. UI must call the engine rather than recreate processing algorithms. See [API_CONTRACT.md](API_CONTRACT.md) for implementation-independent conceptual exchanges; no callable signatures are finalized here.

## 4. Camera Shake and Geometry Stability

**CONFIRMED:** The camera remains at its recording location within a video; small handheld shake is possible. Viewpoint differences between videos require separate geometry.

**REQUIRES VIDEO EVIDENCE:** Phase 1 visually inspects shake and candidate geometry alignment. Propose GMC/stabilization only after actual input evidence; validate any tracker/detection impact in the relevant later phases. No algorithm or API is selected now.

## 5. GPU Strategy

Initial environment: Kaggle GPU. First establish single-video detection → tracking → ReID → trajectory → geometry → crossing → counting with explicit device selection.

**REQUIREMENT — later orchestration:** Detect available GPUs dynamically.

- One GPU: process videos sequentially, one active video on that GPU.
- Two GPUs: permit parallel independent video processing, one active video assigned to each GPU where resources allow.

Do not introduce multi-GPU scheduling, multiprocessing, CUDA orchestration, or performance optimization during the early prototype without explicit instruction. These requirements do not establish current GPU availability or a scheduler API.

## 6. Eight-Video Processing

After the single-video pipeline is technically stable, Phase 8 processes the eight weekday/weekend period videos for one store/location.

Retain each video's identity, geometry, model/tracker/ReID/preprocessing configuration, and result. Generate per-video evidence and weekday/weekend aggregates. Prove correctness with explicit device assignment before optimizing scheduling.

## 7. Explicit Configuration

Configuration covers project, store/location, video, geometry, model, tracking/ReID, counting, preprocessing, output, and audit. Important behavior must be visible and reproducible rather than hidden in globals.

[CONFIG_SCHEMA.md](CONFIG_SCHEMA.md) is preliminary. Unresolved numeric values, model assets, lifecycle choices, serialization details, and API interfaces are not defaults or validated configuration.

## 8. Experiment Artifacts and Evaluation

Meaningful experiments retain input identity, verified model/dependency identifiers, explicit configuration, device information, preprocessing variant, annotated evidence, observations actually measured, conclusions, and limitations.

Phase 0 itself reported no experiment. Subsequent Phase 1–3 records are retained with their individual scopes; Phase 3 separates successful cached execution, software diagnostics and evidence-linked temporal review in [BOTSORT_TRACKING.md](BOTSORT_TRACKING.md). Its unique IDs, missing-observation gaps and raw-class changes are not physical vehicle totals or confirmed ID-switch counts. There is no formal ground truth. Software invariants and visual plausibility cannot be presented as accuracy, precision, recall, F1, MAPE, or counting performance. See [TEST_PLAN.md](TEST_PLAN.md) and [EVALUATION.md](EVALUATION.md).

## 9. Production Transition

The phase order is specification → video inspection → detection → BoT-SORT → ReID → geometry/crossing → counting → night experiments → eight-video processing → manual audit → modular Python → UI → Docker → GPU VM.

After Phase 9 audit, extract stable notebook behavior into modular Python at Phase 10 and preserve it with relevant regression validation. Phase 11 UI provides Home, Result, Edit Value, and Audit plus per-video geometry configuration. Phase 12 pins and packages the validated runtime/model dependency stack in Docker. Phase 13 validates GPU VM deployment and operational behavior.

Do not introduce production web frameworks, databases, orchestration, or containers to make the current documentation appear implemented.

## 10. Persistence and Open Decisions

**OPEN TECHNICAL DECISION:** Production persistence, output serialization details, manual override/versioning, resource policies, and finalized processing interfaces remain undefined. Do not introduce a database without an established requirement.

JSON/CSV/local files are possible prototype artifact formats, not a decision about production storage. Product CSV export remains a requirement; exact schemas are established in the relevant later phases.

See [OPEN_DECISIONS.md](OPEN_DECISIONS.md) for confirmed choices, open technical decisions, missing video evidence, and required experiments.
