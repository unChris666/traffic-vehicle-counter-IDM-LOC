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

**OPEN TECHNICAL DECISION:** Verify the actual package/version, weights source and identifier, model availability, runtime dependencies, Kaggle GPU compatibility, and supported API against authoritative documentation and the actual environment. Image size, confidence threshold, suppression settings, and the model-to-reporting-category mapping are not selected here. Do not invent weights paths, class IDs, or API call signatures.

**REQUIREMENT:** YOLO may detect anywhere in the frame. A Side A/B detection ROI is not part of the accepted prototype design; any later detection restriction requires an explicit experiment and decision.

## 3. BoT-SORT — Multi-Object Tracking

Responsibilities:

- associate detections across time
- maintain track identities within a video
- use the selected implementation's motion/temporal association
- expose track updates and the evidence needed to inspect gaps and identity changes

**OPEN TECHNICAL DECISION:** The selected integration/library, version, lifecycle behavior, available ReID/GMC capability, and all tracker parameters must be verified. Confirmation, minimum age, lost-track duration, buffer, association thresholds, and handling of ID switches are not assigned numerical values.

Tracker IDs are not a guarantee of physical-object identity. Fragmentation, gaps, overlaps, and ID switches require inspection in Phase 3 and later ReID experiments.

## 4. ReID — Appearance-Assisted Identity Association

**CONFIRMED:** ReID is part of the target architecture, not an extra detector and not a technology that may be silently discarded after an experiment.

Its purpose is to use appearance information when it can help maintain or recover identity association. No improvement is claimed before an actual experiment.

Potential inspection cases include overlap, occlusion, similar-looking vehicles, temporary disappearance, and handheld shake.

**OPEN TECHNICAL DECISION:** Verify the selected tracker implementation's real ReID support. Model/weights source, embeddings, association strategy, gallery/history management where applicable, thresholds, and enabled configuration remain open.

**EXPERIMENT REQUIRED:** Phase 4 must document the selected capability and run controlled comparisons where supported, including ReID disabled as an experimental baseline. A baseline comparison is not permission to remove ReID from the target architecture. Unsupported integration or ineffective results must be reported with evidence and a proposed decision.

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

**OPEN TECHNICAL DECISION:** Anchor candidates include bounding-box center and bottom-center. No default is accepted. Category stabilization and category assignment at crossing also require a documented rule.

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

Phase 1 inspects visual shake and candidate geometry alignment using actual videos. Effects on actual detection and trajectory outputs require later model/tracker experiments. Whether GMC/stabilization is necessary, supported, and appropriate remains open; no strategy is selected and no tracker capability is assumed.

## 8. Night Preprocessing

**EXPERIMENT REQUIRED:** Night preprocessing belongs to Phase 7. Candidate operations may include gamma, brightness/exposure, contrast, sharpening, and explicitly documented combinations. These are candidates, not defaults or accepted improvements.

Evaluate comparable video samples with explicit configuration and retain both improvements and regressions. No preprocessing performance or counting accuracy claim is valid without the required evidence.

## 9. Reproducibility and Phase Limits

Record verified model/library identifiers, dependency versions, input identity, device choice, and explicit configuration during future runs. Do not invent versions or store secret values in configuration.

Phase 0 defined this model specification. The Phase 1 inspection tool does not load models, run inference/tracker/ReID, or measure their performance. None of those model operations has been executed here. See [OPEN_DECISIONS.md](OPEN_DECISIONS.md), [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md), [TEST_PLAN.md](TEST_PLAN.md), and [EVALUATION.md](EVALUATION.md).
