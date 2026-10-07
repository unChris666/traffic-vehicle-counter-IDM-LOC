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

Confirmed target: YOLO26M through the Ultralytics Python API in Kaggle, with BoT-SORT and ReID-assisted identity association. Versions, weights, class mapping, and the ReID implementation remain unverified. Do not replace the detector/tracker or remove ReID without an explicit architecture decision.

The camera stays at one recording position during a video; small handheld shake may occur. Geometry uses per-video pixel coordinates. No world projection or homography is required initially. The geometry anchor is OPEN; do not silently choose a default.

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

The present task completes documentation for Phase 0 only. `docs/PHASE_1_TASK.md` prepares the next task; it is not authorization to execute Phase 1. Phase 1 inspects actual video metadata, representative frames, and handheld shake. Detector/tracker inference and GMC/stabilization implementation belong to later authorized tasks.

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
