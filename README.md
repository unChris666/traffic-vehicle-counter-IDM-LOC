# Traffic Vehicle Counter

Vehicle/object traffic counting from real road videos, starting with a Kaggle GPU prototype and progressing to modular Python, UI, Docker, and GPU VM deployment after validation and manual audit.

## Current status

Phase 1: the [parameterized video-inspection notebook](notebooks/01_video_inspection.ipynb) is available. Actual dataset execution must happen in Kaggle; no actual-video inspection findings, model inference, benchmark, or ground-truth dataset have been produced by the cloud implementation task. See [execution status and instructions](docs/VIDEO_INSPECTION.md).

Confirmed target: YOLO26M using the Ultralytics Python API → BoT-SORT with ReID-assisted association → track state/trajectory → per-video pixel geometry → valid crossing events → counts → aggregation/audit.

The camera remains at one recording position during each video, with possible small handheld shake. Geometry is independently configured per video. Target versions, model assets, class mapping, anchors, and operational thresholds remain OPEN.

## Read first

1. [Agent rules](AGENTS.md).
2. [Development phases](CODEX_WORKFLOW.md).
3. [Project context](docs/PROJECT_CONTEXT.md), [product specification](docs/PRODUCT_SPEC.md), [model specification](docs/MODEL_SPEC.md), [counting logic](docs/COUNTING_LOGIC.md), and [architecture](docs/ARCHITECTURE.md).
4. [Test plan](docs/TEST_PLAN.md) and [evaluation rules](docs/EVALUATION.md).
5. [Decision register](docs/OPEN_DECISIONS.md), [preliminary configuration](docs/CONFIG_SCHEMA.md), and [conceptual interface contract](docs/API_CONTRACT.md).

## Execute the Phase 1 inspection

[Phase 1 — video inspection](docs/PHASE_1_TASK.md) is authorized. Open or import `notebooks/01_video_inspection.ipynb` into the [provided Kaggle notebook](https://www.kaggle.com/code/chrisbiran/new-traffic-counter/edit), with the dataset mounted at `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos`. Run through discovery, copy one actual discovered path into `VIDEO_PATH`, then restart the kernel and run all cells. Inspect the generated frames/temporal previews, enter evidence-based manual observations, and regenerate the report. Changing `VIDEO_PATH` selects another video without changing the inspection logic.

Generated frames, previews, reports, and notebook outputs remain in the configured runtime artifact directory, not GitHub source. No detector, tracker, ReID, crossing, counting, enhancement, stabilization, or multi-GPU processing is implemented by this notebook. Phase 2 is not started.

Documentation is part of the project contract. Preserve the distinction between FACT, REQUIREMENT, ASSUMPTION, PROPOSAL, and EXPERIMENT RESULT. Do not report formal accuracy without appropriate ground-truth evidence.
