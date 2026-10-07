# Conceptual Pipeline Contract

Status: Phase 0, implementation-independent documentation. This is not a public API, Python signature, REST endpoint, or implemented interface. Payload names newly proposed here are **PROPOSAL**. Existing minimum track fields are retained from [MODEL_SPEC.md](MODEL_SPEC.md); their exact types and encoding remain OPEN.

Read with [ARCHITECTURE.md](ARCHITECTURE.md), [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md), [COUNTING_LOGIC.md](COUNTING_LOGIC.md), and [TEST_PLAN.md](TEST_PLAN.md).

## Boundaries and responsibilities

| Boundary | Information passed conceptually | Required separation |
|---|---|---|
| Video input → preprocessing/detector | Video identity, recording/location metadata, ordered frames, frame/time reference, observed dimensions, effective configuration. | Actual input metadata is inspected rather than inferred from a screenshot. Frames remain traceable to the input video. |
| Preprocessing → detector | Frame plus selected transformation/configuration evidence and coordinate relationship to original pixels. | Preprocessing is explicit and experimental where applicable; no enhancement/GMC chosen in Phase 0. |
| Detector → tracker | Per-frame bounding boxes, model class identity/name, detection confidence, video/frame/time reference, coordinate convention, model configuration reference. | YOLO26M detects throughout the frame. Detections do not supply counting decisions or prove persistent identity. Actual labels/IDs come from verified assets. |
| ReID ↔ tracker identity association | Appearance evidence associated with observations and effective ReID configuration. | ReID supports association; it is not another detector. Adapter shape, extraction location, model, and association method remain OPEN. BoT-SORT/ReID implementation boundaries must be verified in the actual stack. |
| Tracker → track state | Persistent track identity and updated observations with confidence, category evidence, frame/time references, lifecycle/missing-observation information. | Tracking may begin outside the configured sides or in the initial frame. Geometry eligibility is evaluated separately. Identity continuity through gaps is a target, not a guarantee. |
| Track state → trajectory/geometry | Ordered per-track history, lifecycle state, candidate geometry point after anchor selection, origin/eligibility state, per-video geometry reference. | Stored `center` does not settle the OPEN geometry anchor. Direction cannot be assigned from a single detection or fixed image axis. |
| Trajectory/geometry → crossing decision | Origin-side evidence, temporal path, line-crossing evidence, arrival at opposite side, eligibility and noise/duplicate-check evidence. | Box contact alone is insufficient. A valid subsequent crossing is required for initial-frame objects. Gap-crossing and jitter algorithms remain OPEN. |
| Accepted crossing event → counting/aggregation | Accepted event, video/category/direction, configuration identity and auditable trajectory evidence. | Count once for that valid event. Raw detections, tracker updates, and merely touching a line do not increment totals. |
| Aggregation → results/audit output | Event references and totals by location, weekday/weekend, recording period, and product category; direction retained in event evidence. | Machine totals must reconcile with accepted events. Final product table layout/CSV follows [PRODUCT_SPEC.md](PRODUCT_SPEC.md); directional table expansion is not implied. |
| Processing/results → audit output | Effective configuration, dependency/model identities when verified, event/track evidence, annotated samples/video, aggregate results, documented failures and later manual overrides. | Preserve machine results separately from overrides. Audit observations are not ground-truth performance metrics. |

## Minimum documented track information

The minimum track fields already specified in `MODEL_SPEC.md` are:

| Field | Conceptual meaning / unresolved detail |
|---|---|
| `track_id` | Tracker identity within a video; identity across ID switches/re-entry is OPEN. |
| `class_id`, `class_name` | Verified model class evidence; product-category mapping and stabilization policy OPEN. |
| `confidence` | Confidence evidence; detection/association/summary interpretation must be defined, not invented. |
| `bbox` | Bounding box in the declared image coordinate convention; exact encoding OPEN. |
| `center` | Geometric observation field; does not impose the center as the crossing anchor. |
| `trajectory` | Ordered observation history tied to frame/time references; storage and selected anchor representation OPEN. |
| `first_seen_frame`, `last_seen_frame` | Track observation boundaries; frame indexing convention OPEN. |
| `detection_count`, `missing_frame_count` | Observation/gap bookkeeping; counter update/reset semantics OPEN. |
| `direction` | Geometry-derived state, with accepted event direction `A_TO_B` or `B_TO_A`; undecided-state encoding OPEN. |
| `counting_state` | Crossing/counting progress; implementation enum and transition details OPEN. |

Origin-side, eligibility, geometry/configuration references, and category-selection evidence must be available conceptually to the crossing decision. Whether these are stored on the track, derived from history, or carried separately is an OPEN interface decision; no additional executable fields are mandated here.

## Accepted event and audit evidence

**REQUIREMENT:** establish an eligible origin in A or B, observe a trajectory crossing the configured line, and confirm arrival at the opposite side before accepting the event. Initial visibility in a side, direction metadata, or bounding-box contact is insufficient. Protect against noise, temporary detection loss, re-entry, and duplicate counting.

The following logical event fields are **PROPOSAL**, based on the existing counting-output requirements. Their encoding, exact schema, and identity policy are OPEN:

| Proposed information | Purpose |
|---|---|
| Event reference; video ID/type; store/location reference | Trace a result to the source and aggregate group. |
| Track ID and available identity evidence | Trace the accepted track and later inspect fragmentation/ID switches. |
| Product category and supporting class evidence | Audit the category selected at the event without inventing class IDs. |
| Origin side, destination side, `A_TO_B` / `B_TO_A` | Audit the geometric transition independently from approaching/away metadata. |
| Origin, crossing, and opposite-side frame/time evidence | Show event ordering. Line-crossing time and opposite-side acceptance time may differ; their exact timestamp conventions remain OPEN. |
| Geometry and effective configuration references | Reconstruct polygons/line, coordinate convention, selected anchor, and applicable gates. |
| Relevant trajectory, gap, eligibility, and duplicate-check evidence | Explain why the event was accepted; retained representation and completeness criteria OPEN. |
| Confidence summary or supporting track observations | Inspect model/tracker evidence; summary formula OPEN. |

Approaching/away labels must be read from that video's side metadata, never inferred from screen direction. For the reference example only, A is upper-left/approaching and B lower-right/away; these labels do not hardcode future geometry.

## Invariants and limits

- Track histories are ordered and video-scoped; geometry and observations use compatible declared coordinates.
- An ineligible track creates no accepted event. Repeated updates after a valid event do not create duplicates for that event.
- No algorithm, parameter value, model asset, guarantee of identity recovery, performance metric, or experiment outcome is specified by this contract.
- Future deterministic interface/geometry tests follow `TEST_PLAN.md`; real-video observations follow [EVALUATION.md](EVALUATION.md). Neither has been executed as part of this documentation task.
