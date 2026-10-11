# AGENTS.md

## Project

Traffic Vehicle Counter: a computer-vision system for counting traffic objects by vehicle category from real-world handheld road videos.

Initial development environment: Kaggle Notebook with GPU.
Production target: modular Python application packaged in Docker and deployed to a GPU VM.

## Source of Truth

Read these files before making implementation decisions:

- `docs/PROJECT_CONTEXT.md` — real-world context, inputs, constraints, and known facts.
- `docs/PRODUCT_SPEC.md` — product behavior and user-facing requirements.
- `docs/MODEL_SPEC.md` — detection, tracking, ReID, track state, and model responsibilities.
- `docs/COUNTING_LOGIC.md` — geometry, Side A/B, trajectory, crossing, and counting rules.
- `docs/ARCHITECTURE.md` — system boundaries and development architecture.
- `docs/TEST_PLAN.md` — software correctness tests.
- `docs/EVALUATION.md` — model/system evaluation rules and current absence of ground truth.
- `docs/OPEN_DECISIONS.md` — confirmed decisions, unknowns, required evidence, and experiments.
- `docs/CONFIG_SCHEMA.md` — preliminary logical configuration, with unresolved values explicit.
- `docs/API_CONTRACT.md` — implementation-independent processing boundaries.

Confirmed target: YOLO26M through the Ultralytics Python API in Kaggle, with BoT-SORT and ReID-assisted identity association. Official `yolo26m.pt`, Ultralytics 8.4.175, the frame API, CPU smoke, the selected TOR3-PAGI Kaggle `cuda:0` detection baseline, and direct BoT-SORT replay of its retained detections are verified; see `docs/MODEL_SPEC.md`. The actual Phase 4 external-encoder integration is also verified; `docs/REID_EXPERIMENT.md` records the controlled comparison and rejection of the tested setting as the current vehicle default. Product-category mapping, tuned parameters, other-scene performance, and a final suitable vehicle-ReID configuration remain open. Do not replace the detector/tracker or remove ReID without an explicit architecture decision.

The camera stays at one recording position during a video; small handheld shake may occur. Geometry uses per-video pixel coordinates. No world projection or homography is required initially. The user selected bottom-center (BC) for TOR3-PAGI in Phase 5 feedback; raw-versus-filtered box source, noise/gap rules and robustness remain OPEN. A requested shared line template is not verified geometry for every video.

## Non-Negotiable Agent Rules

1. Do not invent requirements, labels, datasets, metrics, APIs, model weights, or business rules.
2. Distinguish clearly between FACT, REQUIREMENT, ASSUMPTION, PROPOSAL, and EXPERIMENT RESULT.
3. If a decision is unknown and affects correctness, stop that part of implementation and report the uncertainty instead of silently deciding.
4. Do not change an accepted architectural or counting decision without documenting the change.
5. Prefer the smallest implementation that satisfies the current phase.
6. Do not implement later-phase architecture prematurely.
7. Do not refactor unrelated code while implementing a scoped task.
8. Never claim model accuracy, counting accuracy, precision, recall, F1, MAPE, or improvement without appropriate ground-truth evidence.
9. Never fabricate benchmark results, experiment results, screenshots, logs, or test outcomes.
10. Every behavioral change must have a test, validation procedure, or explicit documented reason why automated validation is not yet possible.
11. Preserve reproducibility: explicit configuration, dependencies, device selection, and seeds where applicable.
12. Prefer deterministic and inspectable behavior over hidden magic.
13. Do not silently add fallback behavior that changes scientific or business meaning. Make fallbacks explicit in configuration and logs.
14. When a dependency, model, class mapping, or API is uncertain, inspect the repository/documentation first. If evidence is still missing, state what is missing.
15. Do not optimize for speed before correctness is demonstrated on the current phase.
16. Keep processing logic independent from UI logic.
17. Keep counting logic independent from detector/tracker implementation details.
18. Never count raw detections. Counting must be derived from eligible persistent tracks and explicit crossing events.

## Required Decision Discipline

For any non-trivial implementation choice, state one of:

- FACT — directly supported by project documentation or observed evidence.
- REQUIREMENT — explicitly required by the product specification.
- ASSUMPTION — necessary but not yet validated.
- PROPOSAL — a recommended option that has not yet been accepted.
- EXPERIMENT RESULT — observed result from an actual run.

Do not present a PROPOSAL or ASSUMPTION as an established fact.

## Development Phases

The intended order is:

0. Project specification
1. Video inspection
2. YOLO detection
3. BoT-SORT tracking
4. ReID
5. Geometry / Side A-B / line crossing
6. Counting
7. Night preprocessing experiments
8. End-to-end 8-video processing
9. Manual audit
10. Refactor to modular Python
11. UI
12. Docker
13. GPU VM deployment

Do not skip directly to later phases unless explicitly instructed.

Phase 0 established the specifications. Phase 1 passed the scoped TOR3 morning/night acceptance in `docs/PHASE_1_ACCEPTANCE.md`; historical TDLE visual review and other inputs remain unresolved. Phase 2 completed its one-video Kaggle `cuda:0` technical baseline on 10,282 TOR3-PAGI decoder frames; see `docs/YOLO_DETECTION.md`. The earlier user instruction requested review without rerunning Phase 2 and authorized Phase 3 if its gate passed. `docs/PHASE_2_REVIEW.md` records PASS; `docs/PHASE_3_TASK.md` defines direct BoT-SORT on the retained detections, with ReID disabled and GMC none for this isolated baseline. The actual Phase 3 Kaggle run completed all 10,282 aligned cached frames without detector inference; see `docs/BOTSORT_TRACKING.md` for retained execution, temporal review and acceptance limits. Do not load/run YOLO again in this task. Association runs on CPU; two visible Tesla T4s do not imply GPU tracking. These baseline settings do not remove ReID from the target architecture or decide GMC need. The actual dataset and byte-identical private cache are mounted in Kaggle. The subsequently authorized Phase 4 compared ReID off/on across the same 10,282 TOR3-PAGI cached frames. The official person-domain `yolo26n-reid.onnx` actually produced 512D appearance features with CUDA encoder execution and CPU association; independent artifact checks and bounded temporal review completed. The tested setting is not selected as the current vehicle-ReID default: the priority duplicate/class-handoff cases remain and physical-identity benefit is unestablished. ReID remains in the target architecture. See `docs/REID_EXPERIMENT.md` and `docs/PHASE_5_READINESS.md` for the completed experiment and conditional geometry readiness; that assessment alone did not authorize Phase 5 implementation. Cloud fixtures and software ID counters do not establish physical-object identity or traffic counts.

The user has since authorized staged Phase 5 collaboration: visual candidate → feedback → revision → documented rules → synthetic tests → temporal review → parameter selection. `docs/PHASE_5_TASK.md` defines the scope. The current stage is G2 visual revision after explicit user feedback: P1=(4.5,516.5), P2=(936.4,305.4), Side B maxX875, BC anchor and TOR3-PAGI A→B approaching/B→A away. Exact new polygon vertices are engineer proposals under the user's adjustment instruction; coordinate-reference, polygon and contract review remain pending. The line remains complete beyond B's x875 cap. Native1280x720 interpretation is an explicit assumption. The user requests a shared reliable default; transfer across dimensions/viewpoints and all-video reliability are unestablished. Draft A/B are spatial zones, not proof that every object in A approaches or every object in B moves away. Only source/figure checks and bounded read-only placement screening have occurred; no accepted crossing state-machine replay, synthetic crossing tests, event/count implementation or threshold selection has occurred. Complete the required contract before dependent synthetic/temporal work; later replay uses existing ReID track evidence without rerunning YOLO, tracker or encoder. ReID remains in the architecture. Stabilization/GMC, night enhancement and multi-GPU orchestration remain outside this task.

## Task Execution Protocol

Before coding:

1. Read the relevant docs.
2. Identify the exact scope.
3. Identify dependencies and unknowns.
4. Produce a short implementation plan for non-trivial work.

After coding:

1. Run the smallest relevant validation.
2. Report exactly what was tested.
3. Report what was not tested.
4. Report assumptions and open issues.
5. Do not claim success beyond the evidence.

## Kaggle Prototype Rules

The Kaggle notebook is the experimental reference implementation.

During prototype phases:

- Prefer one clear notebook per capability.
- Keep configuration explicit.
- Avoid introducing a production web framework, database, Docker orchestration, or distributed job system before Phase 10–12.
- Save representative outputs for inspection.
- Keep model/tracker configuration visible in notebook cells.

## Production Transition Rule

Do not modularize or containerize unstable logic merely to make the architecture look complete.
The transition to `src/`, tests, UI, Docker, and VM deployment happens after the end-to-end prototype is validated through manual audit.
