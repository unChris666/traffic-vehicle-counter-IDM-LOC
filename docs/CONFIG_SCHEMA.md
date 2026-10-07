# Preliminary Configuration Schema

Status: Phase 0 documentation only. No executable schema, defaults, parser, or configuration file has been implemented or validated.

The section and field names below are **PROPOSAL**: they describe the information to make explicit, not an accepted Python API or finalized serialization format. A confirmed value is a project requirement; an OPEN value must remain unset until its decision is documented. Unknown values must not be replaced with invented defaults. Identifier formats and configuration-version representation are also OPEN.

Read with [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), [MODEL_SPEC.md](MODEL_SPEC.md), [COUNTING_LOGIC.md](COUNTING_LOGIC.md), [API_CONTRACT.md](API_CONTRACT.md), and [OPEN_DECISIONS.md](OPEN_DECISIONS.md).

## Proposed logical structure

| Section | Proposed field or group | Value status and meaning |
|---|---|---|
| `project` | `project_id`, `configuration_id` | PROPOSAL for identifying the project and effective configuration; formats OPEN. |
| `project` | `phase`, `environment` | CONFIRMED current scope: Phase 0 documentation. CONFIRMED first implementation environment: Kaggle Notebook with GPU. |
| `store_location` | `store_code`, `store_name`, `latitude`, `longitude` | CONFIRMED location information required by the product. Actual values, representation, and input validation OPEN. Coordinates are location metadata, not geometry projection. |
| `video` | `video_id`, `source`, `store_code` | CONFIRMED need to identify input and location; actual source/path and identifiers OPEN. |
| `video` | `day_type`, `recording_period` | CONFIRMED product groups: weekday/weekend and pagi/siang/sore/malam. Serialized labels PROPOSAL; assignment to each actual video requires input metadata. |
| `video` | `observed_metadata` | PROPOSAL group for measured duration, FPS, width, height, aspect ratio, and frame count. All actual values UNKNOWN until Phase 1 inspection. Approximate descriptions are not measured values. |
| `video` | `device` | CONFIRMED device selection must be explicit in later processing, with dynamic GPU discovery a later requirement. Actual device assignment and discovery implementation OPEN; early phases must not introduce multi-GPU orchestration. |
| `geometry` | `geometry_id`, `video_id` | CONFIRMED each video needs independently identifiable geometry. Identifier format OPEN. |
| `geometry` | `coordinate_space` | CONFIRMED pixel coordinates for the initial prototype; coordinate origin, units convention, orientation, and relationship to decoded/resized frames OPEN and must be recorded consistently. No world-coordinate projection, homography, or geographic projection required. |
| `geometry` | `side_a_polygon`, `counting_line`, `side_b_polygon` | CONFIRMED arbitrary per-video polygon and diagonal line coordinates. Actual points, endpoint representation, boundary treatment, and geometry validation rules OPEN. No fixed angle, coordinates, orientation, or polygon size. |
| `geometry` | `side_semantics` | CONFIRMED per-video metadata associates configured sides with approaching/away from camera. Reference example only: A is upper-left of the yellow diagonal and approaching; B is lower-right and away. This mapping is not a reusable image-axis rule. |
| `geometry` | `anchor` | **OPEN, with no default**. Candidates include bounding-box center and bottom-center. A track's `center` field does not choose the geometry anchor. |
| `geometry` | `shake_handling` | OPEN experimental decision. Camera stays at the recording location with possible handheld shake; no stabilization/GMC strategy selected. |
| `model` | `detector`, `interface` | CONFIRMED target: YOLO26M using the Ultralytics Python API in Kaggle. No executable call signature specified here. |
| `model` | `package_version`, `weights_source`, `weights_identity`, `runtime_dependencies` | OPEN; verify actual authoritative assets, installed environment, compatibility, and reproducibility before inference. Production pinning occurs later in Docker. |
| `model` | `class_mapping` | OPEN model-to-product mapping. Product categories are pedestrian, motorcycle, car, bus/angkot, and truck. No model class IDs or availability asserted. |
| `model` | `inference_settings` | OPEN input size, confidence threshold, NMS settings, and other verified supported settings. No numerical values selected. Full-frame detection is CONFIRMED; an ROI detector is not an implicit fallback. |
| `tracking` | `tracker` | CONFIRMED BoT-SORT target; actual implementation/version and capabilities OPEN. |
| `tracking` | `reid` | CONFIRMED ReID-assisted identity association is part of the target. Model, weights, embedding representation, gallery policy, thresholds, configuration, and compatibility OPEN. Removal or replacement requires an explicit architecture decision. |
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
- Phase 0 checks document consistency only. Runtime validation and the executable schema are future scoped work; none is claimed here.
