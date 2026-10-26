<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

## Status implementasi aktif

Profil CUDAaktif adalah candidate_fp32: YOLO26M FP32batch4 dan encoderReID ONNX yang sama, IO binding/window8/crop32. Encoder diekstrak di adapters/reid_encoder.py; model_worker.py dipakai bersama oleh runtime dan benchmark. Tracker diperbarui berurutan perframe. Profilebaseline_fp32 tetap tersedia. Precision/recall kendaraan belum terbukti; lihat CURRENT_STATUS.md.

## Konteks dan kontrak terdahulu

# Model Specification

## 1. Confirmed Target Architecture

VIDEO
→ optional explicitly configured preprocessing
→ YOLO26M
→ BoT-SORT with ReID-assisted identity association
→ track state
→ trajectory
→ direction and per-video geometry
→ valid crossing event
→ counting
→ aggregation
→ audit output

**CONFIRMED:** YOLO26M is the target detector; BoT-SORT is the target multi-object tracker; ReID is part of the target tracking architecture. This architectural choice does not establish implementation compatibility or measured performance. Do not replace the detector/tracker or remove ReID without an explicit architecture decision.

The initial environment is Kaggle with GPU. Production dependency/model versions are to be pinned later inside Docker after the prototype and audit phases, not selected or packaged in Phase 0.

## 2. YOLO26M — Object Detection

**CONFIRMED:** The Kaggle prototype uses the Ultralytics Python API.

Responsibilities:

- frame-level object detection
- bounding boxes
- model class labels/IDs
- confidence scores

Persistent identity, geometry, eligibility, direction, crossing state, and traffic counting are downstream responsibilities.

**EXPERIMENT RESULT — verified asset/API, 2026-10-11:** official `yolo26m.pt` from the Ultralytics assets release v8.4.0 is available, with SHA-256 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`. Ultralytics 8.4.175 and the actual frame API were verified against authoritative sources; see [asset verification](evidence/phase_2/asset_verification.json). A [Codex CPU smoke test](evidence/phase_2/cpu_smoke/cpu_smoke_report.json) loaded the model and inferred two native TOR3-PAGI frames successfully through `YOLO(weights).predict(source=BGR_frame, device='cpu', ...)`. This verifies that CPU combination, not Kaggle CUDA or representative performance.

**EXPERIMENT RESULT — raw labels:** the asset contains 80 labels, including `0: person`, `2: car`, `3: motorcycle`, `5: bus`, and `7: truck`, with no `angkot` label. Phase 2 retains all raw classes. The inspected CPU annotation on frame 7718 has `person` and `motorcycle` boxes over the same rider; raw `person` is not an accepted product `pedestrian` mapping.

**EXPERIMENT RESULT — selected Kaggle GPU baseline:** [run `20261011T052950_360560Z_ed399fb8`](evidence/phase_2/20261011T052950_360560Z_ed399fb8/detection_report.json) loaded/inferred YOLO26M successfully with Python 3.12.13, PyTorch 2.10.0+cu128, torchvision 0.25.0+cu128, Ultralytics 8.4.175, and OpenCV 4.13.0. CUDA exposed two Tesla T4s; inference used only `cuda:0`, FP32, with actual predictor `end2end=False`. All 10,282 frames returned by the TOR3-PAGI decoder were processed, matching metadata and 10,282 validated serialized rows. Input/weights hashes match the verified sources. This establishes that selected runtime/baseline, not all CUDA combinations or model quality; see [detection status](YOLO_DETECTION.md) for timing and review evidence.

**OPEN TECHNICAL DECISION:** automatic product mapping and pickup/bus/angkot taxonomy remain OPEN. The subsequent [Phase6 contract](COUNTING_CONTRACT.md) establishes a positive-review pedestrian/rider distinction and one vehicle unit including driver/passengers; raw person does not map automatically to pedestrian. Suitable image size, confidence/suppression settings, and other tuned parameters are not established; night/other-scene inference remains untested. **PROPOSAL — untuned baseline:** the run used the pinned package's published prediction defaults and recorded resolved values; defaults are not validated product requirements or suitable thresholds by implication. Do not invent weights paths, class IDs, or API call signatures.

**REQUIREMENT:** YOLO may detect anywhere in the frame. A Side A/B detection ROI is not part of the accepted prototype design; any later detection restriction requires an explicit experiment and decision.

## 3. BoT-SORT — Multi-Object Tracking

Responsibilities:

- associate detections across time
- maintain track identities within a video
- use the selected implementation's motion/temporal association
- expose track updates and the evidence needed to inspect gaps and identity changes

**EXPERIMENT RESULT — verified Phase 3 baseline:** the pinned Ultralytics 8.4.175 implementation is `ultralytics.trackers.bot_sort.BOTSORT`, constructed with `BOTSORT(args)` and fed the retained Phase 2 detections through `update(results, img=None, feats=None, **kwargs)`. Native-pixel `Boxes` rows contain box coordinates, confidence and raw class; activated outputs expose eight fields, including `track_id` and the original detection index. Empty detection rows still advance the tracker. Source/API/default verification and actual Kaggle execution are retained in [tracking status](BOTSORT_TRACKING.md).

[Run `20261011T060227_579936Z_05ebe213`](evidence/phase_3/20261011T060227_579936Z_05ebe213/tracking_report.json) completed 10,282 aligned cached frames without detector inference, with Ultralytics 8.4.175 and lap 0.5.13. Association ran on CPU despite two visible Tesla T4s. **PROPOSAL — untuned baseline:** published `botsort.yaml` settings were retained with explicit `with_reid=False` and `gmc_method='none'`. The verified `track_buffer=30` means 30 update-call frames without FPS rescaling; it is not an accepted elapsed-source-time or product lifecycle policy. Association is class-agnostic and emitted class/score follow the latest matched raw detection.

**OPEN TECHNICAL DECISION:** suitable confirmation/lifecycle/association settings, physical-identity recovery, category stabilization, a suitable vehicle-ReID configuration and GMC need remain unresolved. The parent cache discarded detections below `conf=0.25`; it cannot reproduce the tracker's complete lower-confidence second-stage range. Recorded defaults/source behavior establish what this baseline did, not that its thresholds or identity outcomes are suitable for counting.

Tracker IDs are not a guarantee of physical-object identity. Fragmentation, gaps, overlaps, and ID switches require inspection in Phase 3 and later ReID experiments.

## 4. ReID — Appearance-Assisted Identity Association

**CONFIRMED:** ReID is part of the target architecture, not an extra detector and not a technology that may be silently discarded after an experiment.

Its purpose is to use appearance information when it can help maintain or recover identity association. No improvement is claimed before an actual experiment.

Potential inspection cases include overlap, occlusion, similar-looking vehicles, temporary disappearance, and handheld shake.

**FACT — verified source boundary:** the pinned BoT-SORT implementation exposes ReID configuration. Its native `model='auto'` appearance path needs detector features that are absent from the retained Phase 2 cache; the Phase 3 baseline has no encoder and runs no ReID inference. Enabling `auto` on this cache is not an established supported experiment. See [tracking status](BOTSORT_TRACKING.md).

**EXPERIMENT RESULT — actual Phase 4 comparison:** [run `20261011T095924_205716Z_90cf7319`](evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_report.json) completed independent off/on sequences of the same 10,282 cached TOR3-PAGI frames without detector inference. The official dedicated `yolo26n-reid.onnx` external encoder is integrated through the verified pinned wrapper; its declared MSMT17 person-ReID domain does not establish vehicle suitability. The on variant made 10,275 encoder calls and produced 50,713 finite, nonzero 512D features. Its first-inference profile records 137 CUDA and 20 CPU kernel events; association remains CPU. Appearance lowered 53,152 eligible cost pairs. Independent artifact audit passed 19/19 checks, including canonical off replay equality with all original Phase 3 records/histories. See [verified integration, actual review and limits](REID_EXPERIMENT.md).

**EXPERIMENTAL DECISION — tested setting not selected as current vehicle default:** actual paired samples retain the concurrent red-scooter tracks and entry class/component handoff; both variants recover the roadside five-frame observation gap. A changed beginning raw-car association is physically ambiguous. No convincing physical-identity benefit is established within the review; instrumented loop cost was higher. This rejects selection of this tested setting, not ReID as a technology or part of the target architecture.

**OPEN TECHNICAL DECISION:** a final suitable vehicle-ReID model/configuration, vehicle-domain effectiveness, association/gallery policies where applicable, tuned thresholds, optimized resource cost and whole-video physical-identity benefit remain open. A working appearance integration and changed costs do not establish improved identity.

**EXPERIMENT REQUIREMENT:** the scoped Phase 4 capability verification, controlled disabled/enabled comparison and tested-candidate decision are complete. Further candidates or settings require separately documented, authorized comparisons, with raw evidence and regressions retained. A baseline comparison or rejected candidate is not permission to remove ReID from the target architecture.

## 5. Track State and Trajectory — Conceptual Contract

The intended information includes:

- video identity and frame/time references
- tracker identity and relevant identity-association evidence
- current bounding box and observed class/confidence evidence
- first/last observation and lifecycle/gap information
- temporal trajectory/history
- geometry anchor and its selected definition
- established origin side, eligibility, direction, and counting state

Preserve the minimum documented logical track fields: `track_id`, `class_id`, `class_name`, `confidence`, `bbox`, `center`, `trajectory`, `first_seen_frame`, `last_seen_frame`, `detection_count`, `missing_frame_count`, `direction`, and `counting_state`.

These fields and conceptual data needs do not select a library data structure. Exact types, serialization, units, identity scope, counter semantics, and handling of observations versus predicted states must be defined before their respective implementation phases. `center` is observation information and does not settle the geometry anchor. Additional data should be added only when required. See [API_CONTRACT.md](API_CONTRACT.md).

**CONFIRMED — TOR3-PAGI:** user-selected BC uses raw detector-linked emitted-track observations under the contextually accepted [G3 contract](GEOMETRY_CONTRACT.md); predictions do not confirm passage and observation gaps break pending evidence. Stored centers/Kalman boxes do not replace this measurement. The subsequent [Phase6 contract](COUNTING_CONTRACT.md) provides review-gated category and explicit physical-passage deduplication; automatic category/identity recovery, suitable numerical settings and universal BC robustness remain OPEN. [Accepted G3](evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json) uses a new960×540 reference and explicit normalized-to-native mapping, not recovery of the UNKNOWN original scaled-image size/crop. Historical G2 placement is not evidence of the intended gate. [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md) records actual software tests, cached geometry replay and targeted-pixel findings without model reruns.

**EXPERIMENT RESULT — Phase 6 Option B:** [final retained run](evidence/phase_6/20261013T104301_354775Z/report.json) implements source-wide unit-family/gap episode extraction before selecting case windows. New vehicle geometry does not inherit person origin, rider BC or prediction. The frozen spatial/relative-motion resolver distinguishes `COMPONENT_OF` from `SAME_VEHICLE`, requires unique component assignment and complete duplicate cliques, screens raw competing vehicles, and gates identity support inside the candidate's own measured origin–confirmation window. Full vehicle-episode raw-category unanimity excludes person components and is explicitly offline/noncausal; it is not calibrated category confidence or a streaming policy. The 63/63 software guard and bounded replay produced one automatic motorcycle passage for 1772/1774 and five pending vehicle candidates; grouping-disabled ablation accepted none. No per-observation appearance vectors were available or extracted, so this is not a new ReID contribution experiment. The original detector/tracker/ReID evidence and Option A outputs remain immutable. [Actual A/B review](PHASE_6_OPTION_B_REVIEW.md) records the limits: duplicate 964/973 fails the frozen motion gate, car 1323 identity remains unresolved, and future-only rider support cannot confirm an earlier 923 passage. Suitable automatic identity/category settings and the final vehicle-ReID configuration remain OPEN.

## 6. Separate Responsibilities

| Responsibility | Question |
|---|---|
| Detection | Which objects are observed in this frame? |
| Tracking | Which observations belong to the same temporal track? |
| ReID | Does appearance evidence support identity association? |
| Track eligibility | Does this tracked object satisfy configured entry/geometry rules? |
| Trajectory | How has the selected geometric representation moved over time? |
| Direction | Which configured side transition does the trajectory represent? |
| Crossing | Did an eligible track cross the line and reach the opposite side? |
| Counting | Is this a valid event that has not already been recorded? |

**REQUIREMENT:** Counting consumes valid track-level crossing events. Never count raw frame detections, tracker updates, region presence, or bounding-box contact with the line.

## 7. Camera Shake and GMC

**CONFIRMED:** The camera remains at its location during a video; small handheld shake is possible. Do not implement stabilization in this specification task.

Phase 1 inspects visual shake and candidate geometry alignment using actual videos. The pinned tracker exposes a GMC setting; Phase 3 explicitly uses `gmc_method='none'` to isolate cached detection association and executes no correction. Whether GMC/stabilization is necessary or helpful remains open; the disabled baseline does not decide a correction strategy or benefit.

## 8. Night Preprocessing

**EXPERIMENT REQUIRED:** Night preprocessing belongs to Phase 7. Candidate operations may include gamma, brightness/exposure, contrast, sharpening, and explicitly documented combinations. These are candidates, not defaults or accepted improvements.

Evaluate comparable video samples with explicit configuration and retain both improvements and regressions. No preprocessing performance or counting accuracy claim is valid without the required evidence.

## 9. Reproducibility and Phase Limits

Record verified model/library identifiers, dependency versions, input identity, device choice, and explicit configuration during future runs. Do not invent versions or store secret values in configuration.

Phase 0 defined this model specification. Phase 1's inspection tool does not load models, run inference/tracker/ReID, or measure their performance; its TOR3 evidence passed [scoped acceptance](PHASE_1_ACCEPTANCE.md). The authorized [Phase 2](PHASE_2_TASK.md) CPU smoke and TOR3-PAGI Kaggle GPU technical baseline completed with retained execution and sampled review evidence. The original Kaggle report's pending manual-review fields are preserved; subsequent review is separate in [detection status](YOLO_DETECTION.md). The user's later instruction authorized [Phase 3](PHASE_3_TASK.md) after the [retained-evidence gate](PHASE_2_REVIEW.md) passed, without rerunning Phase 2. Actual cached BoT-SORT execution, temporal review and acceptance limits are documented in [tracking status](BOTSORT_TRACKING.md). Direction and counting state were uncomputed in Phase3. Phase4 subsequently completed its [contribution experiment](REID_EXPERIMENT.md), with the tested person-domain setting not selected as current vehicle-ReID default. ReID remains in the architecture. Phase5 now implements deterministic geometry diagnostics under the accepted [contract](GEOMETRY_CONTRACT.md): 40/40 synthetic tests then six configurations replayed the retained ReID-on observations without running detector/tracker/encoder again. Diagnostic direction is available; the subsequently authorized Phase6 prototype implements eligibility, reviewed CountEvent/category/physical dedup under [COUNTING_CONTRACT.md](COUNTING_CONTRACT.md), while suitable product parameters and automated physical-identity recovery remain OPEN. [PHASE_6_REVIEW.md](PHASE_6_REVIEW.md) records actual CPU execution and bounded AI-assisted review, without new detector/tracker/encoder or geometry-state-machine execution. [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md) separates actual software audit and bounded pixel review from model/counting quality. G3 preserves all user points on its new960×540 reference; original source-display reconstruction and all-video reliability remain unknown. See [OPEN_DECISIONS.md](OPEN_DECISIONS.md), [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md), [TEST_PLAN.md](TEST_PLAN.md), and [EVALUATION.md](EVALUATION.md).
