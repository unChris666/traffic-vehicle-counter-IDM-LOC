# Conceptual Pipeline Contract

Status: conceptual product contract established in Phase 0, complemented by the scoped [Phase 5 geometry contract](GEOMETRY_CONTRACT.md) and authorized [Phase 6 audit-gated counting contract](COUNTING_CONTRACT.md). Notebook-prototype callable interfaces and `CountEvent` encoding now exist; final production schemas/public API remain OPEN. This document does not define a REST endpoint. Actual execution/review and limits belong to [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md) and [PHASE_6_REVIEW.md](PHASE_6_REVIEW.md). Newly proposed product payload names below remain **PROPOSAL**; minimum documented track fields are retained from [MODEL_SPEC.md](MODEL_SPEC.md).

Read with [ARCHITECTURE.md](ARCHITECTURE.md), [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md), [COUNTING_LOGIC.md](COUNTING_LOGIC.md), and [TEST_PLAN.md](TEST_PLAN.md). Historical [G2 feedback](evidence/phase_5/feedback/G2_review_001.json) establishes scaled coordinates with UNKNOWN original dimensions/crop; G2 is not adoptable native geometry. After [default delegation](evidence/phase_5/feedback/G2_review_002.json), [G3 feedback](evidence/phase_5/feedback/G3_review_001.json) accepts the new 960 × 540 context and B outline, labels unchanged A points, and is recorded as contextual acceptance of the qualitative rules offered in that question. The [accepted configuration](evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json) uses the valid A→B→D→C perimeter and explicit native mapping. Preserve historical drafts and feedback without rewriting their original status or conditional findings. No original image-size recovery or all-video reliability follows from acceptance.

## Boundaries and responsibilities

| Boundary | Information passed conceptually | Required separation |
|---|---|---|
| Video input → preprocessing/detector | Video identity, recording/location metadata, ordered frames, frame/time reference, observed dimensions, effective configuration. | Actual input metadata is inspected rather than inferred from a screenshot. Frames remain traceable to the input video. |
| Preprocessing → detector | Frame plus selected transformation/configuration evidence and coordinate relationship to original pixels. | Preprocessing is explicit and experimental where applicable; no enhancement/GMC chosen in Phase 0. |
| Detector → tracker | Per-frame bounding boxes, model class identity/name, detection confidence, video/frame/time reference, coordinate convention, model configuration reference. | YOLO26M detects throughout the frame. Detections do not supply counting decisions or prove persistent identity. Actual labels/IDs come from verified assets. |
| ReID ↔ tracker identity association | Appearance evidence associated with observations and effective ReID configuration. | ReID supports association; it is not another detector. One external-encoder integration was verified in [Phase 4](REID_EXPERIMENT.md); its tested setting was not selected as the current vehicle default. A final suitable vehicle-ReID configuration and generalization remain OPEN. |
| Tracker → track state | Persistent track identity and updated observations with confidence, category evidence, frame/time references, lifecycle/missing-observation information. | Tracking may begin outside the configured sides or in the initial frame. Geometry eligibility is evaluated separately. Identity continuity through gaps is a target, not a guarantee. |
| Track state → trajectory/geometry | Ordered measured per-track history, frame/dimension/source-detection references, raw bbox BC, per-video geometry/configuration reference and geometric origin. | TOR3-PAGI BC comes from emitted detector-linked `raw_bbox`, not Kalman `bbox` or stored `center`. Predictions are not crossing evidence. Direction cannot be assigned from a single detection or fixed image axis. Business eligibility remains separate. |
| Trajectory/geometry → Phase 5 diagnostic | Measured origin, finite line passage, opposite-ROI confirmation, parameter/configuration reference and supporting frame/point/measurement evidence. | `GEOMETRY_TRANSITION` has `accepted_count_event=False`. Polygon boundaries are neutral; touch alone is insufficient; endpoint/gap passage is ambiguous. Mandatory half-width/confirmation parameters are experiments, not product defaults. |
| Phase 5 diagnostic → Phase 6 crossing decision | Retained diagnostic plus full measured origin–confirmation class history, explicit counting config and unit/category/identity review. | Audit-gated Opsi A: unreviewed/conflicting candidates stay pending. Review cannot repair gap/endpoint/prediction or person↔vehicle history. Only confirmed same physical unit + passage is deduplicated; schema follows the counting contract. Automatic resolver and production schema remain OPEN. |
| Accepted crossing event → counting/aggregation | Accepted event, video/category/direction, configuration identity and auditable trajectory evidence. | Count once for that valid event. Raw detections, tracker updates, and merely touching a line do not increment totals. |
| Aggregation → results/audit output | Event references and totals by location, weekday/weekend, recording period, and product category; direction retained in event evidence. | Machine totals must reconcile with accepted events. Final product table layout/CSV follows [PRODUCT_SPEC.md](PRODUCT_SPEC.md); directional table expansion is not implied. |
| Processing/results → audit output | Effective configuration, dependency/model identities when verified, event/track evidence, annotated samples/video, aggregate results, documented failures and later manual overrides. | Preserve machine results separately from overrides. Audit observations are not ground-truth performance metrics. |

## Minimum documented track information

The minimum track fields already specified in `MODEL_SPEC.md` are:

| Field | Conceptual meaning / unresolved detail |
|---|---|
| `track_id` | Tracker identity within a video; identity across ID switches/re-entry is OPEN. |
| `class_id`, `class_name` | Verified raw model evidence. Phase 6 checks the entire origin–confirmation history and requires category review; person is not automatically pedestrian. Pickup/bus/angkot taxonomy remains OPEN. |
| `confidence` | Confidence evidence; detection/association/summary interpretation must be defined, not invented. |
| `bbox` | Track bounding box; final product encoding OPEN. The current cache also carries `raw_bbox` in native xyxy coordinates, source-linked to the measured detection; geometry uses that distinct field. |
| `center` | Geometric observation field; does not impose the center as the crossing anchor. |
| `trajectory` | Ordered observation history tied to frame/time/source references. Current prototype uses measured raw-bbox BC and consecutive frame indices; no predicted/gap interpolation. Final product storage remains OPEN. |
| `first_seen_frame`, `last_seen_frame` | Track observation boundaries. Retained cache uses zero-based ordered decoder-frame indices; authoritative source PTS and final product timing convention remain OPEN. |
| `detection_count`, `missing_frame_count` | Observation/gap bookkeeping; counter update/reset semantics OPEN. |
| `direction` | Geometry-derived state, with accepted event direction `A_TO_B` or `B_TO_A`; undecided-state encoding OPEN. |
| `counting_state` | Crossing/counting progress; implementation enum and transition details OPEN. |

Origin-side, eligibility, geometry/configuration references and category-selection evidence are inputs to the Phase 6 prototype decision. The geometry helper maintains measured state independently from counting; the counting helper layers candidate, machine decision, review, resolved decision and event evidence. Their final production representation remains OPEN.

## Scoped prototype interface

[GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md) defines `Geometry.from_draft`, independent polygon/distance/finite-segment predicates, `GeometryStateMachine.update`, and `replay_cached_records`. The state-machine constructor requires explicit `neutral_band_px` (native-pixel half-width) and `confirmation_observations`; no suitable product values are implicit.

The geometry decision keeps side membership separate from signed line distance, preserving the slight G3 line/shared-edge offset. A measured passage can still lie in the narrow origin strip; it is not a return until the track measurably leaves that region and returns. Measured destination confirmation must be consecutive. Gaps/predictions invalidate pending evidence and cannot authorize a crossing. After a confirmed geometric transition the state may rebase and emit a later valid reverse diagnostic, while `repeat_business_policy_open=True` and `accepted_count_event=False` keep the future repeat/count policy explicit.

The replay consumes existing Phase 4 emitted track records with source-detection links. It performs no YOLO, tracker or encoder inference; raw classes remain diagnostic evidence rather than accepted product categories. Cache/geometry/helper identities, parameters, source dimensions, measurement links and actual processed scope are retained for reproducibility.

## Accepted event and audit evidence

**REQUIREMENT:** establish an eligible origin in A or B, observe a trajectory crossing the configured line, and confirm arrival at the opposite side before accepting the event. Initial visibility in a side, direction metadata, or bounding-box contact is insufficient. Protect against noise, temporary detection loss, re-entry, and duplicate counting.

The following logical fields remain **PROPOSAL** for a final product payload. The separate [counting contract](COUNTING_CONTRACT.md) and implemented helper establish their scoped Phase 6 prototype representation and deterministic identity; production schema is OPEN:

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

Approaching/away labels must be read from that video's configuration, never inferred from screen direction or side presence alone. For the reference example only, A is upper-left/approaching and B lower-right/away. The user separately confirmed TOR3-PAGI `A_TO_B` approaching / `B_TO_A` away. The accepted relative template uses the new reference canvas with `u=x/960`, `v=y/540` and target-native mapping `(u×width, v×height)`. These transforms do not recover the UNKNOWN original display/crop mapping or establish cross-video reliability; effective placement remains subject to per-video review. Continuous native image-edge coordinates use origin upper-left, X rightward, Y downward, within `[0,width]×[0,height]`; array pixel indexing is distinct.

## Invariants and limits

- Track histories are ordered and video-scoped; geometry and observations use compatible declared coordinates.
- The future Phase 11 line/polygon setup page is a user requirement reiterated in the default delegation; it does not add a UI API or product interface at this stage.
- An ineligible track creates no accepted event. Repeated updates after a valid event do not create duplicates for that event.
- The latest user labels identify P1A/B/C/D without changing coordinates. Valid perimeter A→B→D→C is the simple-polygon representation; the line remains distinct from A's nearby endpoint and is not shortened at B's cap. Contextual qualitative-rule acceptance, explicit measurement source and conservative gap policy are recorded in the geometry contract. Numeric experiment settings, even when executed, do not become suitable product defaults automatically.
- Synthetic validation precedes processing under [PHASE_5_TASK.md](PHASE_5_TASK.md), [PHASE_6_TASK.md](PHASE_6_TASK.md) and [EVALUATION.md](EVALUATION.md). Actual execution/review belongs to the separate phase reviews. Prototype counting policies are explicit; final taxonomy, automatic identity resolution, production encoding, suitable thresholds and whole-video completeness remain OPEN. Internal consistency is not an accuracy claim.

## Phase 6 notebook interface and persistence boundary

**ENGINEERING EXPERIMENT:** [phase_6_counting_helpers.py](../notebooks/phase_6_counting_helpers.py) exposes `run_counting(diagnostics_path, records_path, geometry_path, *, config, reviews=None, evidence_root=None)`. It consumes retained crossing diagnostics/track records and validates input hashes/native/source links. It returns `machine_decisions`, `resolved_decisions`, `machine_events`, `accepted_events`, `machine_aggregate`, `aggregate`, and `report`; [06_counting_audit.ipynb](../notebooks/06_counting_audit.ipynb) executes the scoped workflow.

Candidate IDs identify measured diagnostic/source references; review IDs bind review evidence; event IDs identify a reviewed physical unit + passage within an input/counting-config namespace. Category corrections and execution-clock/random labels do not create another event. Event identity includes source-video/cache/diagnostic/geometry identities; rerunning the same inputs/config/reviews gives the same snapshot rather than append-counting old events.

Review evidence carries path/hash/frame scope supporting unit/category/identity and every required origin/contact/passage/confirmation frame. Same-unit episodes with positive-duration overlapping crossing intervals remain `OVERLAPPING_PASSAGE_EPISODES` even when assigned distinct passage IDs; non-overlapping later episodes still require positive independent-return review. Machine results are immutable inputs to the resolved view. Accepted events alone form category totals; pending/rejected remain visible. Unknown location/day metadata is null. No database/UI, cross-video identity API, formal ground truth or production override design is implied.
