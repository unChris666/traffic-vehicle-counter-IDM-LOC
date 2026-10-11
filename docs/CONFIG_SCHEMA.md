# Preliminary Configuration Schema

Status: preliminary logical schema established in Phase 0 and maintained for the currently authorized [Phase 5 visual-feedback/revision stage](PHASE_5_TASK.md). Notebook experiment configurations and visual geometry drafts are retained separately; no finalized executable geometry schema/parser, crossing implementation, synthetic geometry tests or accepted crossing state-machine replay is established.

The section and field names below are **PROPOSAL**: they describe the information to make explicit, not an accepted Python API or finalized serialization format. A confirmed value is a project requirement; an OPEN value must remain unset until its decision is documented. Unknown values must not be replaced with invented defaults. Identifier formats and configuration-version representation are also OPEN.

Read with [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), [MODEL_SPEC.md](MODEL_SPEC.md), [COUNTING_LOGIC.md](COUNTING_LOGIC.md), [API_CONTRACT.md](API_CONTRACT.md), and [OPEN_DECISIONS.md](OPEN_DECISIONS.md).

## Proposed logical structure

| Section | Proposed field or group | Value status and meaning |
|---|---|---|
| `project` | `project_id`, `configuration_id` | PROPOSAL for identifying the project and effective configuration; formats OPEN. |
| `project` | `phase`, `environment` | CONFIRMED first implementation environment: Kaggle Notebook with GPU. Current authorized geometry scope is Phase 5 visual-feedback/revision; Phase 1–4 execution evidence is retained separately. |
| `store_location` | `store_code`, `store_name`, `latitude`, `longitude` | CONFIRMED location information required by the product. Actual values, representation, and input validation OPEN. Coordinates are location metadata, not geometry projection. |
| `video` | `video_id`, `source`, `store_code` | CONFIRMED need to identify input and location; actual source/path and identifiers OPEN. |
| `video` | `day_type`, `recording_period` | CONFIRMED product groups: weekday/weekend and pagi/siang/sore/malam. Serialized labels PROPOSAL; assignment to each actual video requires input metadata. |
| `video` | `observed_metadata` | PROPOSAL group for measured duration, FPS, width, height, aspect ratio, and frame count. Inspected values are retained in Phase 1 reports and later input evidence; uninspected videos remain UNKNOWN. Approximate descriptions are not measured values. |
| `video` | `device` | CONFIRMED device selection must be explicit in later processing, with dynamic GPU discovery a later requirement. Actual device assignment and discovery implementation OPEN; early phases must not introduce multi-GPU orchestration. |
| `geometry` | `geometry_id`, `video_id` | CONFIRMED each video needs independently identifiable geometry. Identifier format OPEN. |
| `geometry` | `coordinate_space` | CONFIRMED pixel coordinates for the initial prototype; coordinate origin, units convention, orientation, and relationship to decoded/resized frames OPEN and must be recorded consistently. No world-coordinate projection, homography, or geographic projection required. |
| `geometry` | `side_a_polygon`, `counting_line`, `side_b_polygon` | CONFIRMED per-video configurable polygons/line. TOR3-PAGI user line: `P1=(4.5,516.5)`, `P2=(936.4,305.4)`; Side B maximum `X=875` does not shorten the line. Engineer-adjusted G2 polygons are PROPOSAL; boundary/endpoint and geometry validity rules remain OPEN. See [feedback 002](evidence/phase_5/feedback/G1_review_002.json). |
| `geometry` | `side_semantics` | CONFIRMED per-video semantic metadata; reference example has A upper-left/approaching and B lower-right/away. Separately confirmed TOR3-PAGI: `A_TO_B` approaching / `B_TO_A` away. A region alone does not establish motion direction; no reusable image-axis rule is selected. |
| `geometry` | `anchor` | CONFIRMED user-selected bottom-center (BC) for current TOR3-PAGI geometry. Universal superiority is unproved. Operational raw-detection versus Kalman-filtered-box source and observed/predicted-point handling remain OPEN; stored `center` does not override BC. |
| `geometry` | `template_transfer` | PROPOSAL field for the USER REQUIREMENT to reuse the supplied line as a default. ASSUMPTION for this visual revision: supplied numbers use G1 native 1280 × 720 pixels. Per-video scaling/aspect-ratio/viewpoint transfer and cross-video reliability remain OPEN; no automatic transfer algorithm is selected. |
| `geometry` | `shake_handling` | OPEN experimental decision. Camera stays at the recording location with possible handheld shake; no stabilization/GMC strategy selected. |
| `model` | `detector`, `interface` | CONFIRMED target: YOLO26M using the Ultralytics Python API in Kaggle. No executable call signature specified here. |
| `model` | `package_version`, `weights_source`, `weights_identity`, `runtime_dependencies` | Verified Phase 2 assets/runtime are documented in [MODEL_SPEC.md](MODEL_SPEC.md). Broader compatibility and later production pinning remain OPEN; do not infer untested support. |
| `model` | `class_mapping` | OPEN model-to-product mapping. Product categories are pedestrian, motorcycle, car, bus/angkot, and truck. No model class IDs or availability asserted. |
| `model` | `inference_settings` | OPEN input size, confidence threshold, NMS settings, and other verified supported settings. No numerical values selected. Full-frame detection is CONFIRMED; an ROI detector is not an implicit fallback. |
| `tracking` | `tracker` | CONFIRMED BoT-SORT target; pinned implementation/actual Phase 3 replay are verified in [MODEL_SPEC.md](MODEL_SPEC.md). Suitable tuned settings and broader capabilities remain OPEN. |
| `tracking` | `reid` | CONFIRMED ReID-assisted identity association is part of the target. One tested integration is verified in [REID_EXPERIMENT.md](REID_EXPERIMENT.md), but not selected as the current vehicle default. Final vehicle model/configuration, tuning and broader compatibility remain OPEN. Removal or replacement requires an explicit architecture decision. |
| `tracking` | `lifecycle`, `association`, `identity_recovery` | OPEN confirmation, minimum age, lost duration, track buffer, association gates, ID-switch handling, and identity continuity. |
| `counting` | `eligibility_rules` | CONFIRMED eligibility acts on tracked objects using configured entry/geometry rules, separately from full-frame detection. Exact gates OPEN. Initial-frame objects inside a side may be tracked and establish an origin, but require a subsequent valid crossing to count. |
| `counting` | `event_rule` | CONFIRMED origin side → crosses line → reaches opposite side → accepted event → count once. Directions: `A_TO_B`, `B_TO_A`. Bounding-box contact alone is insufficient. |
| `counting` | `noise_protection`, `duplicate_policy` | CONFIRMED protection against jitter, fluctuation, detection gaps, re-entry, and noisy re-crossing. Exact gates, duplicate identity scope, gap-crossing policy, and treatment of genuine repeated crossings OPEN. |
| `counting` | `category_policy` | OPEN stabilization and category selection at the event, including uncertain/conflicting labels and bus/angkot mapping. |
| `preprocessing` | `variant`, `parameters`, `coordinate_mapping` | OPEN optional transformations and their parameters; no night enhancement or stabilization selected. Any spatial transform must preserve the declared geometry relationship. Candidate night enhancement requires later controlled experiments. |
| `output` | `destination`, `event_format`, `aggregate_format`, `annotation_settings` | CONFIRMED need for auditable event/aggregate outputs and annotated video; final product exports both result tables as CSV. Prototype format/schema details, actual paths, and annotation settings OPEN. |
| `audit` | `configuration_reference`, `evidence_references`, `experiment_reference` | CONFIRMED outputs must retain effective configuration and inspectable evidence. Field names and reference formats PROPOSAL; retention/storage policy OPEN. |
| `audit` | `manual_override_policy` | CONFIRMED preserve original machine-generated results. Exact override/versioning behavior OPEN before production. |

## Configuration consistency requirements

- Geometry, frames, bounding boxes, trajectory points, and the selected anchor must refer to a declared compatible coordinate system. Preprocessing/resizing must not silently shift the line or polygons.
- Detection, tracking, eligibility, and counting remain separate; the counting configuration cannot silently crop YOLO to side regions.
- Unknown detector/tracker/ReID capabilities must be verified rather than represented as supported settings. No missing asset, parameter, or category mapping may be silently substituted.
- Configuration and output must preserve video identity and effective settings for audit. No secret values belong in configuration examples or committed evidence.
- Phase 0 checked document consistency only. The current Phase 5 visual revision records supplied geometry/BC choices; engineer-adjusted polygons and dependent contract remain under review. No crossing implementation, synthetic geometry tests, temporal replay or validated all-video default is claimed here.
