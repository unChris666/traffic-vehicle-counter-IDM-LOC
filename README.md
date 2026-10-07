# Traffic Vehicle Counter

Vehicle/object traffic counting from real road videos, starting with a Kaggle GPU prototype and progressing to modular Python, UI, Docker, and GPU VM deployment after validation and manual audit.

## Current status

Phase 0: project specification. This repository currently contains documentation only. No notebook pipeline, model inference, video inspection, benchmark, or ground-truth dataset has been produced here.

Confirmed target: YOLO26M using the Ultralytics Python API → BoT-SORT with ReID-assisted association → track state/trajectory → per-video pixel geometry → valid crossing events → counts → aggregation/audit.

The camera remains at one recording position during each video, with possible small handheld shake. Geometry is independently configured per video. Target versions, model assets, class mapping, anchors, and operational thresholds remain OPEN.

## Read first

1. [Agent rules](AGENTS.md).
2. [Development phases](CODEX_WORKFLOW.md).
3. [Project context](docs/PROJECT_CONTEXT.md), [product specification](docs/PRODUCT_SPEC.md), [model specification](docs/MODEL_SPEC.md), [counting logic](docs/COUNTING_LOGIC.md), and [architecture](docs/ARCHITECTURE.md).
4. [Test plan](docs/TEST_PLAN.md) and [evaluation rules](docs/EVALUATION.md).
5. [Decision register](docs/OPEN_DECISIONS.md), [preliminary configuration](docs/CONFIG_SCHEMA.md), and [conceptual interface contract](docs/API_CONTRACT.md).

## Next task

[Phase 1 — video inspection](docs/PHASE_1_TASK.md) is prepared as a task specification. It requires actual input videos and explicit authorization to start. No Phase 1 processing has been executed by the documentation update.

Documentation is part of the project contract. Preserve the distinction between FACT, REQUIREMENT, ASSUMPTION, PROPOSAL, and EXPERIMENT RESULT. Do not report formal accuracy without appropriate ground-truth evidence.
