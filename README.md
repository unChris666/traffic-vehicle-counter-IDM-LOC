# Traffic Vehicle Counter

Vehicle/object traffic counting from real road videos, starting with a Kaggle GPU prototype and progressing to modular Python, UI, Docker, and GPU VM deployment after validation and manual audit.

## Current status

Phase 1 has [passed acceptance for TOR3 morning/night](docs/PHASE_1_ACCEPTANCE.md). The latest retained Kaggle reports match the earlier Codex input identities, sampling, and AI-assisted visual reviews. All 21 fields contain observations or explicit unknown/open limitations; model risks remain untested hypotheses. The older `TDLE-PAGI` report-only review and other inputs remain visually unresolved.

The authorized [Phase 2: one-video YOLO detection](docs/PHASE_2_TASK.md) has completed its technical baseline in Kaggle: YOLO26M / Ultralytics 8.4.175 processed all **10,282 TOR3-PAGI frames returned by the decoder** on `cuda:0`, with matching serialized rows. This follows the verified official assets/API and CPU smoke. See [detection status and retained GPU evidence](docs/YOLO_DETECTION.md) for execution, sampled review, and limitations. Model quality, other-scene generalization, and production suitability remain unproven. Phase 3 is not authorized; tracking, ReID, and counting have not started.

Confirmed target: YOLO26M using the Ultralytics Python API → BoT-SORT with ReID-assisted association → track state/trajectory → per-video pixel geometry → valid crossing events → counts → aggregation/audit.

The camera remains at one recording position during each video, with possible small handheld shake. Geometry is independently configured per video. Product-category mapping, anchors, tuned parameters, tracker/ReID versions, and night/other-scene behavior remain OPEN. Raw model `person` includes riders and is not an accepted `pedestrian` mapping; bus/angkot interpretation is also OPEN. Published prediction defaults were used as an untuned experiment baseline, not accepted suitable product settings.

## Read first

1. [Agent rules](AGENTS.md).
2. [Development phases](CODEX_WORKFLOW.md).
3. [Project context](docs/PROJECT_CONTEXT.md), [product specification](docs/PRODUCT_SPEC.md), [model specification](docs/MODEL_SPEC.md), [counting logic](docs/COUNTING_LOGIC.md), and [architecture](docs/ARCHITECTURE.md).
4. [Test plan](docs/TEST_PLAN.md) and [evaluation rules](docs/EVALUATION.md).
5. [Decision register](docs/OPEN_DECISIONS.md), [preliminary configuration](docs/CONFIG_SCHEMA.md), and [conceptual interface contract](docs/API_CONTRACT.md).

## Execute the Phase 1 inspection

[Phase 1 — video inspection](docs/PHASE_1_TASK.md) is authorized. Open or import `notebooks/01_video_inspection.ipynb` into the [provided Kaggle notebook](https://www.kaggle.com/code/chrisbiran/new-traffic-counter/edit), with the dataset mounted at `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos`. Run through discovery, copy one actual discovered path into `VIDEO_PATH`, then restart the kernel and run all cells. Inspect the generated frames/temporal previews, enter evidence-based manual observations, and regenerate the report. Changing `VIDEO_PATH` selects another video without changing the inspection logic.

Native frames, previews, videos, and executed notebook outputs remain in the runtime artifact directory. Curated review sheets, reports, manifests, and frame hashes are retained under `docs/evidence/phase_1/`; original videos are excluded. The TOR3 review is applied only to the matching input SHA-256 and sampling, while other videos remain unknown until reviewed. No detector, tracker, ReID, crossing, counting, enhancement, stabilization, or multi-GPU processing is implemented by the Phase 1 notebook. Phase 2 is a separate detection capability.

Documentation is part of the project contract. Preserve the distinction between FACT, REQUIREMENT, ASSUMPTION, PROPOSAL, and EXPERIMENT RESULT. Do not report formal accuracy without appropriate ground-truth evidence.
