# Phase 3 — BoT-SORT tracking of retained Phase 2 detections

**AUTHORIZATION:** the user requested a Phase 2 review without rerunning it, then authorized Phase 3 if the technical gate passed. [PHASE_2_REVIEW.md](PHASE_2_REVIEW.md) records PASS with explicit limits. This task establishes a tracking baseline on one actual video; no Phase 3 result is claimed by this task specification.

## Read first

`AGENTS.md`, `CODEX_WORKFLOW.md`, `docs/PHASE_2_REVIEW.md`, `docs/PROJECT_CONTEXT.md`, `docs/MODEL_SPEC.md`, `docs/API_CONTRACT.md`, `docs/OPEN_DECISIONS.md`, `docs/TEST_PLAN.md`, and `docs/EVALUATION.md`.

## Objectives

1. Verify the actual pinned BoT-SORT class, configuration, input/output shape, lifecycle behavior, detection-index linkage, available ReID/GMC settings and association behavior before integration.
2. Convert all 10,282 retained TOR3-PAGI frame-level detection rows into ordered, video-scoped track updates without executing YOLO again. Update the tracker for zero-detection frames as well as populated frames.
3. Preserve persistent IDs, raw class/confidence evidence, native-pixel boxes, ordered observation history and lifecycle/gap evidence. Declare measured versus predicted states and exact bookkeeping semantics.
4. Visualize actual track IDs in representative samples and temporal evidence. Inspect continuity, fragmentation, temporary detection gaps and plausible ID switches, including the cropped/overlaid scooter entering around frames 7711–7718.
5. Retain input/cache/package/configuration identities, timing, failures, track records and an evidence-linked review. Assess whether this baseline is technically usable for the later controlled ReID experiment without claiming identity accuracy.

## Execution scope and explicit baseline choices

**REQUIREMENT:** create `notebooks/03_botsort_tracking.ipynb` as a separate reproducible capability notebook. Phase 2 notebook/report/predictions remain unchanged.

**PROPOSAL — baseline:** use the Ultralytics 8.4.175 BoT-SORT implementation after source/API verification, directly on cached native-coordinate detections. Preserve every raw model class; use no product-category filter or mapping. Record the pinned package's actual tracker defaults and any explicit overrides. Numerical defaults are an untuned experiment configuration; suitable production values remain OPEN.

- Select the input/cache paths explicitly and validate hashes before tracking. Require video SHA-256 `606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c` and detection JSONL SHA-256 `033a2815d3abbd23327936a1b9d948b2b9b7d312796516e5ee46aec5685be345` from Phase 2 run `20261011T052950_360560Z_ed399fb8`.
- Process the complete cached sequence once, with a fresh tracker for the video. Representative bursts must show state inherited from preceding frames, not separately reinitialized burst trackers.
- Set `with_reid=False` for the isolated Phase 3 baseline and `gmc_method='none'` to avoid introducing an unselected camera-correction method. These choices do not remove ReID from the architecture or decide GMC is unnecessary.
- Direct association can run on CPU when the verified implementation requires no appearance/GMC inference. Record the actual execution device; GPU hardware visibility does not prove tracker GPU execution and GPU orchestration is outside scope.
- Decode the matching source video for frame alignment and rendering. Do not load YOLO weights, call detector prediction/tracking wrappers that trigger detector inference, download a substitute detector, or silently fall back to a different tracker.
- Record frame indices as the tracking order. Retain backend/index-FPS timestamps separately with their existing uncertainty. Record any package FPS/buffer conversion explicitly; do not assume exactly 30 FPS or claim verified source-time behavior.
- Retain raw detector evidence even when the tracker filters observations or associates across a raw class change. Detector confidence filtering at `0.25` already removed lower-confidence observations; this baseline cannot test recovery from those absent boxes.

## Track record semantics

**PROPOSAL — inspectable prototype records:** serialize one frame-level tracker record for each source row, including frames with no emitted tracks, and retain per-ID ordered observed history and available lifecycle information. Define zero-based frame indexing, video-scoped IDs, native-pixel box representation, confidence provenance, input-detection linkage and observation/gap counters in the notebook/report before writing records.

Preserve the minimum conceptual fields from [API_CONTRACT.md](API_CONTRACT.md): `track_id`, `class_id`, `class_name`, `confidence`, `bbox`, `center`, `trajectory`, `first_seen_frame`, `last_seen_frame`, `detection_count`, `missing_frame_count`, `direction`, and `counting_state`. In this phase, `center` is only a box-derived observation and does not select a geometry anchor. Direction and counting state must explicitly remain uncomputed; do not implement their later-phase state machines. Missing/lost/predicted observations must not be silently presented as detector measurements.

Unique track-ID totals and repeated update frequencies are software/lifecycle summaries, never physical vehicle totals or traffic counts. Candidate fragmentation or ID-switch cases require temporal visual evidence; a programmatic discontinuity flag alone is not proof of a physical identity error.

## Validation and review

1. Validate notebook format/compilation and the verified cached-input/BoT-SORT adapter. Check wrong hashes, malformed/out-of-order rows, invalid coordinates, duplicate emitted IDs, empty detections and partial-run evidence handling with clearly identified software fixtures.
2. Execute actual BoT-SORT on all 10,282 retained frame records. Verify video/cache alignment, contiguous source rows, valid input-index linkage, unique emitted IDs per frame, finite boxes/confidences, monotonic per-track histories and declared lifecycle semantics.
3. Retain native annotated representatives and practical temporal clips/contact sheets. Recommended review: five 30-frame bursts near beginning/25%/50%/75%/end plus a focused entering-scooter sequence around 7711–7718. Include actual track histories for discussed cases.
4. Review the rendered temporal evidence before stating continuity/fragmentation/gap/identity findings. Separate observed cases, algorithm-generated candidates and unresolved interpretation. Record AI-assisted review provenance and evidence references.
5. Measure actual association/loop/render time only where separate counters exist. Do not compare tracking-only runtime to Phase 2 detector runtime as an equivalent pipeline benchmark.
6. Report failures/unexecuted checks and remaining open settings. No ground truth exists: do not report accuracy, precision, recall, F1, MAPE, IDF1, MOTA, or counting accuracy.

## Deliverables and phase boundary

- `notebooks/03_botsort_tracking.ipynb`: parameterized, output-free source notebook.
- A Phase 3 tracking status/review document with actual findings after execution.
- `docs/evidence/phase_3/<run_id>/`: verified configuration/runtime/input provenance, serialized track observations/histories, lifecycle/consistency audit, representative temporal evidence and subsequent review. Keep original videos/weights outside GitHub; identify where larger execution artifacts are retained.
- Small current-status documentation updates supported by the actual results, preserving unresolved product mapping, ReID/GMC, geometry and counting decisions.

Out of scope: Phase 4 ReID inference/association experiments, geometry/Side A-B coordinates, direction estimation, line crossing, counting, stabilization, night enhancement, multi-video/multi-GPU orchestration, UI, Docker and production refactoring.

Phase 3 acceptance requires working cached detection-to-track integration, ordered inspectable records and actual temporal review, with limitations documented. It does not require perfect physical-object identity or prove readiness for traffic counting. The review may recommend the next ReID experiment, but this task does not authorize starting Phase 4.
