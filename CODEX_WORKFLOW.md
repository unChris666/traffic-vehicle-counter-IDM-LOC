# Codex Development Workflow

## Operating Rule

Work strictly phase-by-phase. A phase is complete only when its defined validation is satisfied or its unresolved limitations are explicitly documented.

Do not implement the entire application in one task.

---

## PHASE 0 — Project Specification

Goal:
Establish repository rules, requirements, constraints, and decisions.

Read:
- AGENTS.md
- docs/PROJECT_CONTEXT.md
- docs/PRODUCT_SPEC.md
- docs/MODEL_SPEC.md
- docs/COUNTING_LOGIC.md
- docs/ARCHITECTURE.md
- docs/TEST_PLAN.md
- docs/EVALUATION.md
- docs/OPEN_DECISIONS.md
- docs/CONFIG_SCHEMA.md
- docs/API_CONTRACT.md

Output:
- cleaned project structure
- explicit open decisions
- initial configuration schema
- implementation-independent interface contract

Validation:
No implementation claims. Only specification consistency.

---

## PHASE 1 — Video Inspection

Goal:
Understand actual input videos before selecting thresholds or assumptions.

Tasks:
- inspect duration
- FPS
- resolution
- aspect ratio
- frame count
- brightness/night characteristics
- handheld shake while the camera stays at one recording position
- visible alignment changes relative to candidate counting geometry
- representative frames

Output:
- inspection notebook
- metadata table
- representative images/clips
- documented failure cases

Read `docs/PHASE_1_TASK.md` for the prepared task scope. Actual videos are required; a screenshot does not establish temporal behavior, FPS, duration, or frame count.

Do not implement detection, tracking, ReID, counting, stabilization, or GMC in Phase 1. Record whether shake merits a later GMC/stabilization experiment; do not claim its effect on detector/tracker outputs without later inference evidence.

---

## PHASE 2 — YOLO Detection

Goal:
Prove frame-level detection on one video.

Tasks:
- load actual model asset
- verify model/library compatibility
- inspect class mapping
- run inference
- visualize detections
- measure actual inference performance

Output:
- detection notebook
- annotated samples
- configuration
- measured observations

Do not implement tracking or counting.

---

## PHASE 3 — BoT-SORT Tracking

Goal:
Convert detections into persistent tracks.

Tasks:
- integrate BoT-SORT
- visualize track IDs
- inspect fragmentation
- inspect temporary detection gaps
- inspect ID switches

Output:
- tracking notebook
- annotated samples/video
- track-level records

Do not implement line crossing yet.

---

## PHASE 4 — ReID

Goal:
Evaluate whether appearance-based association improves identity consistency.

Tasks:
- verify the actual ReID capability of the selected tracker implementation
- choose/implement a ReID model only after documenting the choice
- compare with ReID disabled where possible
- inspect difficult overlap/occlusion cases

Output:
- ReID experiment record
- actual evidence
- accepted ReID configuration or explicit rejection of a tested ReID candidate/configuration

ReID remains part of the confirmed target architecture. Disabling it for a controlled comparison does not remove it from that architecture. Replacing BoT-SORT or removing ReID requires an explicit architecture decision.

Do not claim improvement without measured evidence.

---

## PHASE 5 — Geometry / Side A-B / Line Crossing

Goal:
Build deterministic geometry and direction logic independently from model quality.

Tasks:
- define per-video Side A polygon
- define counting line
- define Side B polygon
- define point/trajectory representation
- implement crossing state machine
- implement A → B and B → A logic

Use synthetic trajectories first.

Output:
- geometry module/notebook
- deterministic tests
- JSON geometry configuration

Do not use raw YOLO detections as the source of count events.

---

## PHASE 6 — Counting

Goal:
Generate one auditable event per valid track crossing.

Tasks:
- track eligibility
- crossing event generation
- duplicate prevention
- category assignment
- event schema
- aggregation

Output:
- event-level output
- category totals
- annotated crossing visualization

Validation must include synthetic geometry tests plus real-video visual inspection.

---

## PHASE 7 — Night Preprocessing Experiments

Goal:
Investigate whether image enhancement helps difficult night videos.

Candidate transformations:
- gamma
- brightness/exposure
- contrast
- sharpening
- explicitly documented combinations

Run controlled experiments against the same video samples.

Do not assume enhancement improves results.

Output:
- experiment table
- before/after samples
- observed detector/tracker/counting behavior
- selected configuration only if evidence supports it

---

## PHASE 8 — End-to-End 8-Video Processing

Goal:
Process all eight videos for one location.

Input:
- store metadata
- 4 weekday videos
- 4 weekend videos
- per-video geometry configuration

Desired GPU behavior:

1 GPU:
process sequentially / one active video per GPU.

2 GPUs:
process videos in parallel / one active video per GPU where resource usage permits.

First prove correctness with explicit device assignment. Optimize scheduling second.

Output:
- eight per-video results
- weekday aggregate
- weekend aggregate
- annotated videos
- machine-readable logs

---

## PHASE 9 — Manual Audit

Goal:
Create an auditable reference set without pretending it is ground truth.

For selected videos inspect:
- detections
- track IDs
- class labels
- trajectory
- Side A/B
- crossing event
- duplicate counting
- missed counting
- night behavior

Record failures systematically.

Output:
- audit notes
- failure categories
- prioritized fixes

---

## PHASE 10 — Refactor → Modular Python

Goal:
Move stable logic from notebook prototypes into maintainable modules.

Suggested boundaries:
- video
- preprocessing
- detection
- tracking
- ReID
- track state
- geometry
- counting
- aggregation
- audit/output

Requirements:
- preserve behavior
- add regression tests
- avoid rewriting working algorithms without a reason

---

## PHASE 11 — UI

Goal:
Build the first simple user interface.

Pages:
- Home
- Result
- Edit Value
- Audit

Add geometry configuration per video before processing.

UI must call the processing engine rather than reimplementing it.

---

## PHASE 12 — Docker

Goal:
Package the modular application into a reproducible container.

Requirements:
- explicit Python/runtime dependencies
- GPU runtime compatibility
- configuration through environment/config where appropriate
- health/smoke test
- reproducible build

Do not containerize unstable notebook-only logic.

---

## PHASE 13 — GPU VM

Goal:
Deploy the containerized application to a GPU VM.

Validate:
- GPU visibility
- model loading
- video processing
- concurrent job behavior if enabled
- output persistence
- resource usage
- restart behavior

Production deployment must preserve the same core processing semantics validated in earlier phases.

---

# Codex Task Template

For every implementation task, use this structure:

## Task
[one concrete change]

## Read First
[list exact relevant docs/files]

## Scope
[what is included]

## Out of Scope
[what must not be changed]

## Constraints
[technical/business constraints]

## Validation
[exact tests/commands/manual checks]

## Deliverables
[files/artifacts expected]

## Reporting
Report:
- files changed
- tests run
- tests passed/failed
- actual measured results
- assumptions
- unresolved issues

If a required decision is missing, do not silently invent it.
