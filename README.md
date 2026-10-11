# Traffic Vehicle Counter

Vehicle/object traffic counting from real road videos, starting with a Kaggle GPU prototype and progressing to modular Python, UI, Docker, and GPU VM deployment after validation and manual audit.

## Current status

Phase 1 has [passed acceptance for TOR3 morning/night](docs/PHASE_1_ACCEPTANCE.md). The latest retained Kaggle reports match the earlier Codex input identities, sampling, and AI-assisted visual reviews. All 21 fields contain observations or explicit unknown/open limitations; model risks remain untested hypotheses. The older `TDLE-PAGI` report-only review and other inputs remain visually unresolved.

The authorized [Phase 2: one-video YOLO detection](docs/PHASE_2_TASK.md) completed its technical baseline in Kaggle: YOLO26M / Ultralytics 8.4.175 processed all **10,282 TOR3-PAGI frames returned by the decoder** on `cuda:0`, with matching serialized rows. The [retained-evidence review](docs/PHASE_2_REVIEW.md) passed its technical objective without rerunning detection. See [detection status and retained GPU evidence](docs/YOLO_DETECTION.md) for sampled review and limitations; model quality, other-scene generalization, and production suitability remain unproven.

The subsequently authorized [Phase 3 baseline](docs/PHASE_3_TASK.md) also executed in Kaggle: direct Ultralytics 8.4.175 BoT-SORT replayed all 10,282 retained detection rows against the matching video, without loading or running YOLO. Association used CPU with `with_reid=False` and `gmc_method='none'`; two Tesla T4s were visible but did not perform tracking inference. See [tracking execution, temporal review and limitations](docs/BOTSORT_TRACKING.md), [source notebook](notebooks/03_botsort_tracking.ipynb), and the [private Kaggle notebook](https://www.kaggle.com/code/chrisbiran/traffic-counter-phase-3-botsort). Tracker IDs and gap/class diagnostics are not vehicle totals or confirmed identity-error counts. Crossing and counting algorithms have not been implemented.

The authorized [Phase 4 contribution experiment](docs/PHASE_4_TASK.md) completed ReID-off/on processing of the same 10,282 TOR3-PAGI cached frames, without detector inference. The dedicated official `yolo26n-reid.onnx` produced 50,713 finite 512D features with actual CUDA execution; the off replay matches Phase 3 and 19 independent artifact checks passed. [Actual paired review](docs/REID_EXPERIMENT.md) finds the priority duplicate/component-handoff cases unchanged and the five-frame gap recovered in both variants. The tested person-domain encoder setting is **not selected as the current vehicle-ReID default**; physical-identity benefit is unestablished and measured instrumented cost increased. This does not remove ReID from the architecture. See the [source notebook](notebooks/04_reid_comparison.ipynb), [private Kaggle notebook](https://www.kaggle.com/code/chrisbiran/traffic-counter-phase-4-reid-comparison), and [Phase 5 conditional readiness](docs/PHASE_5_READINESS.md). That readiness assessment supports synthetic geometry first after documenting its contract; trustworthy counting remains blocked.

The user has now authorized [staged Phase 5 collaboration](docs/PHASE_5_TASK.md): candidate image → feedback → revision → rules → synthetic tests → temporal review → parameter selection. [Latest feedback](docs/evidence/phase_5/feedback/G1_review_002.json) selects the revised line P1=(4.5,516.5)/P2=(936.4,305.4), Side B maxX875, bottom-center (BC), and TOR3-PAGI A→B approaching/B→A away. [G2 review](docs/evidence/phase_5/review_drafts/G2/README.md) preserves these choices over an unchanged native frame, with proposed polygon adjustment and concrete rules for review. Native1280x720 interpretation needs confirmation; a requested shared default is not established reliable across videos. Source/figure checks and bounded read-only placement screening do not establish accepted crossings or counting. Rules/thresholds remain unresolved; subsequent synthetic validation and retained-track state replay have not occurred. No YOLO, tracker or encoder is rerun for this stage.

Confirmed target: YOLO26M using the Ultralytics Python API → BoT-SORT with ReID-assisted association → track state/trajectory → per-video pixel geometry → valid crossing events → counts → aggregation/audit.

The camera remains at one recording position during each video, with possible small handheld shake. Geometry is independently configured per video. Product-category mapping, BC measurement-source/robustness, tuned parameters, a final suitable vehicle-ReID configuration, and night/other-scene behavior remain OPEN. Raw model `person` includes riders and is not an accepted `pedestrian` mapping; bus/angkot interpretation is also OPEN. Published detector/tracker defaults were used as untuned experiment baselines, not accepted suitable product settings. Disabling ReID/GMC in the isolated tracking baseline does not remove ReID from the architecture or settle GMC need.

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
