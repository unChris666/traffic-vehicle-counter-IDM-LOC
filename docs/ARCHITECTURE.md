# Architecture

## 1. Strategy and Current Scope

**REQUIREMENT:** Develop phase by phase: Kaggle prototype first, production architecture after the single-video pipeline, eight-video processing, and manual audit are stable.

Phase 0 established specifications. Executed model capabilities are Phase 1 inspection, Phase 2 one-video YOLO26M, Phase 3 cached BoT-SORT and the controlled [Phase 4 ReID comparison](REID_EXPERIMENT.md). The staged [Phase 5 task](PHASE_5_TASK.md) now uses accepted G3/reference/B and contextual qualitative rules from [latest feedback](evidence/phase_5/feedback/G3_review_001.json). The four named A points remain exact; simple perimeter ABDC avoids self-intersection. [GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md) defines the notebook-only prototype; [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md) records actual software validation and cached replay evidence. There is no accepted counting implementation or final suitable numerical setting. The architecture below remains the target; later components remain unimplemented.

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

ReID remains the target appearance-assisted association component. [Phase 4](REID_EXPERIMENT.md) verified and actually ran the official dedicated `yolo26n-reid.onnx` external-encoder path, comparing off/on against the same retained detections without detector inference. CUDA appearance inference and CPU association are established for this run; cached detector features remain unavailable for native `auto`. The tested person-domain setting is not selected as the current vehicle default because physical-identity benefit is unestablished within the reviewed cases and measured instrumented cost increased. A final suitable vehicle-ReID configuration remains OPEN. Baseline IDs do not guarantee physical-object identity. This candidate decision removes neither ReID from the target nor BoT-SORT, and does not decide GMC need.

### Track State

Maintains track history, lifecycle, category/identity evidence, and the information needed for geometry eligibility. Unconfirmed lifecycle parameters and identity recovery rules remain explicit open decisions.

### Trajectory

Represents temporal movement using user-selected BC from raw detector-linked emitted-track observations, under [GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md). This is measured trajectory after association, not counting raw detections. Stored center/Kalman boxes and predictions do not replace the BC measurement. Gaps break passage/confirmation evidence and may produce ambiguous diagnostics. Suitable jitter/confirmation settings and all-video robustness remain OPEN.

### Geometry and Direction

Uses per-video pixel Side A/Side B polygons and counting-line endpoints. Evaluates side membership, track eligibility/origin, trajectory transitions, and line crossing. No homography, geographic projection, fixed angle, or image-axis traffic-direction rule is required.

Side semantics are per-video; TOR3-PAGI `A_TO_B` means approaching and `B_TO_A` away. [Accepted G3](evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json) uses new template960×540, normalized u=x/960,v=y/540 and explicit target-native mapping. The original scaled-image size/crop remains UNKNOWN. Preserve exact line, B cap875 (without shortening the line), four A vertices and the line/P1C offset. Polygon membership and line-sign/passages are independent; boundaries are neutral. Relative transfer needs per-video review and is not reliable-all-video evidence. G1/G2/G3 remain immutable; G3-L1 labels alone do not change geometry.

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

Phase 0 itself reported no experiment. Phase 1–4 retain their separate scopes; ReID architecture remains while the tested person-domain setting is not the current vehicle default. Phase 5 separates source/figure checks, independent synthetic software tests, complete cached-measurement diagnostics and bounded retained-pixel review in [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md). No model is rerun for geometry. Diagnostic transitions are not CountEvent or traffic totals; all raw classes remain visible. Numeric sensitivity comparisons do not establish optimal thresholds. Original scaled-image mapping and all-video reliability remain unknown. There is no formal ground truth; software invariants and visual plausibility cannot be presented as model/counting accuracy.

## 9. Production Transition

The phase order is specification → video inspection → detection → BoT-SORT → ReID → geometry/crossing → counting → night experiments → eight-video processing → manual audit → modular Python → UI → Docker → GPU VM.

After Phase 9 audit, extract stable notebook behavior into modular Python at Phase 10 and preserve it with relevant regression validation. Phase 11 UI provides Home, Result, Edit Value, and Audit plus per-video geometry configuration. The user reiterated a page for setup/editing of line and polygons in [default delegation](evidence/phase_5/feedback/G2_review_002.json); this future requirement does not implement a product UI in Phase 5. Phase 12 pins and packages the validated runtime/model dependency stack in Docker. Phase 13 validates GPU VM deployment and operational behavior.

Do not introduce production web frameworks, databases, orchestration, or containers to make the current documentation appear implemented.

## 10. Persistence and Open Decisions

**OPEN TECHNICAL DECISION:** Production persistence, output serialization details, manual override/versioning, resource policies, and finalized processing interfaces remain undefined. Do not introduce a database without an established requirement.

JSON/CSV/local files are possible prototype artifact formats, not a decision about production storage. Product CSV export remains a requirement; exact schemas are established in the relevant later phases.

See [OPEN_DECISIONS.md](OPEN_DECISIONS.md) for confirmed choices, open technical decisions, missing video evidence, and required experiments.
