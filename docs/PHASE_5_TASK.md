# Phase 5 — staged geometry collaboration on TOR3-PAGI

**AUTHORIZATION:** the user requested the staged workflow: visual candidate → feedback → revision → documented rules → synthetic tests → temporal review → parameter selection. This task starts with a concrete visual proposal for feedback. It does not treat that proposal as approved geometry or skip dependent stages.

**CURRENT STAGE:** [G2 feedback 001](evidence/phase_5/feedback/G2_review_001.json) confirms that the supplied coordinates came from a scaled image, refuting G2's native-1280 × 720 interpretation. Original image dimensions/crop remain UNKNOWN. The user does not know them and [delegates preparation of a relative default](evidence/phase_5/feedback/G2_review_002.json), with review per video and a future geometry-setup page. Proceed with the newly proposed [G3 template](evidence/phase_5/review_drafts/G3/README.md), not reconstruction of that unknown source. Its 960 × 540 reference canvas and polygon order are ENGINEER PROPOSALS pending review. BC and TOR3-PAGI `A_TO_B` approaching / `B_TO_A` away remain selected. No polygon/crossing contract, numerical tolerances, hysteresis, confirmation or gap policy is accepted. No crossing state-machine, event generation, counting or synthetic crossing tests are implemented/executed at this stage.

## Read first

- [AGENTS.md](../AGENTS.md) and [CODEX_WORKFLOW.md](../CODEX_WORKFLOW.md).
- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), [COUNTING_LOGIC.md](COUNTING_LOGIC.md), [MODEL_SPEC.md](MODEL_SPEC.md), [API_CONTRACT.md](API_CONTRACT.md) and [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md).
- [TEST_PLAN.md](TEST_PLAN.md), [EVALUATION.md](EVALUATION.md), [OPEN_DECISIONS.md](OPEN_DECISIONS.md), [REID_EXPERIMENT.md](REID_EXPERIMENT.md) and [PHASE_5_READINESS.md](PHASE_5_READINESS.md).

## First review proposal

[Draft G1](evidence/phase_5/review_drafts/G1/README.md) presents configurable pixel geometry on the unchanged retained TOR3-PAGI frame 5140, at native 1280 × 720 dimensions. The draft includes deterministic coordinate-based SVG/HTML evidence; any generated conceptual illustration is supplementary, not an authoritative pixel configuration.

**PROPOSAL — G1 coordinates, not approved:**

| Element | Native-frame pixel points |
|---|---|
| Counting-line candidate | `(160,650)`, `(620,500)` |
| Side A candidate | `(70,425)`, `(620,500)`, `(160,650)`, `(120,545)`, `(75,470)` |
| Side B candidate | `(160,650)`, `(620,500)`, `(850,550)`, `(850,710)`, `(180,710)` |

The proposal uses A on the far/upper-left side and B on the near/lower-right side of one transverse gate. Each region spans the road's two traffic directions; these are not one polygon per opposing lane. Upper-left A/lower-right B follows the reference example's visual placement, but neither actual TOR3-PAGI coordinates nor its event-to-approaching/away mapping is approved by that example. Being in A does not establish that an object is approaching the camera.

**CONFIRMED — TOR3-PAGI event direction:** for the proposed A-far/B-near spatial scheme, the user answered “Ya, pemetaan arah tersebut benar”: `A_TO_B` means approaching the camera and `B_TO_A` means moving away. This is video-specific semantic metadata, not a rule that every object present in A approaches or every object in B moves away. Direction confirmation does not approve G1 line/polygon coordinates.

G1 and its feedback remain historical. [G2](evidence/phase_5/review_drafts/G2/README.md) preserves the conditional native-pixel placement assumption; the later scaled-image correction means its placement screening is not evidence about the user's intended gate. Preserve both drafts and all feedback rather than rewriting their original artifacts/results. Preserve the A → line → B/B → line → A sequence and confirmed TOR3-PAGI direction mapping; do not reinterpret A/B as separate opposing lanes.

G1 displayed center approximately `(249,509)` and bottom-center approximately `(249,546)` from the same detector-linked observation of retained ReID-on motorcycle track 973 on frame 5140. The latest user instruction selects **BC**, not center, for the current geometry. This does not establish physical road-contact position, eligibility or a valid crossing. Whether operational BC comes from the linked raw box or Kalman-filtered box remains OPEN; the preview raw box is evidence, not an implicit operational choice. Shared polygon/line edges in a preview do not select boundary or tolerance rules.

## Delegated relative default and G3 proposal

**USER-CONFIRMED POLICY:** use a relative template and review per video. The user delegates an adjusted default despite not knowing the scaled source's dimensions, and requests a later page for setting lines/polygons. Do not ask for those dimensions again as a prerequisite to this newly authorized default. A future setup page belongs to Phase 11; no product UI is implemented here.

**ENGINEER PROPOSAL — new reference:** use 960 × 540 template units, containing the supplied points and matching TOR3-PAGI's 16:9 aspect ratio. This is not a discovered/recovered source-image size. Normalize `u=x/960`, `v=y/540`; preview at native 1280 × 720 by `x_native=u×1280`, `y_native=v×720`. Runtime geometry remains resolved per-video image pixels. This coordinate mapping does not establish equivalent physical-road placement for other viewpoints/aspects.

| User-supplied element | Coordinates preserved in the proposed template |
|---|---|
| Complete counting line | `P1=(4.5,516.5)`, `P2=(936.4,305.4)` |
| Side A points in supplied order | 1: `(4.5,516.5)`; 2: `(4.5,348.2)`; 3: `(936.6,305.8)`; 4: `(557.5,165.3)` |
| Side B extent | Maximum `X=875` in template units; polygon cap only, not a shortened counting line |

**ENGINEER PROPOSAL — polygon outlines:** connect A as `1 → 2 → 4 → 3 → 1` to avoid the crossed edges of the supplied listing, retaining every coordinate. This perimeter order is not user-approved. A point `(936.6,305.8)` differs from line P2 `(936.4,305.4)`; preserve both without snapping or claiming an identical boundary. Propose B beneath the shared A edge, clipped at template `X=875`, with bottom reference `Y=532.5`. B's precise outline/bottom and handling of the distinct line/A edge remain proposals, not accepted rules or thresholds.

The entire line continues to template `X=936.4`. Intersecting its part beyond B's cap does not automatically establish arrival in B. Review G3 before documenting boundary/intersection/gap behavior.

**RELIABILITY STATUS:** the requested default is an initial editable template. Review/adjust geometry and directional metadata per video; cross-video reliability is NOT ESTABLISHED. Source-image reconstruction remains UNKNOWN but does not block the delegated G3 proposal. No original camera-angle/road alignment, all-video counting quality or successful crossing follows from normalization. The current deliverable is a TOR3-PAGI preview, not an eight-video experiment.

## Subsequent stages and gates

1. **Feedback and revision:** the user supplies the line/A points/B cap, selects BC and confirms relative-template review per video. Produce/review G3 using the explicitly proposed new reference and perimeter order, with all prior drafts preserved. Do not recover an unknown source by assumption, snap distinct vertices, shorten the line to the B cap or treat the default as validated for every video. Dependent rules/tests/replay wait for the required geometry/contract review.
2. **Document rules before dependent implementation:** define coordinate/dimension conventions, finite-line/endpoint and polygon validity semantics, boundary/overlap/gap handling, origin/crossing/opposite-side transitions, and treatment of observed versus predicted/missing trajectory points. Use the user-selected BC and explicitly define which track-box representation supplies it; do not silently switch to center. Validate its behavior rather than presenting the selection as proven robustness. Numerical values remain OPEN until investigated in the agreed later stage.
3. **Synthetic validation first:** once the required contract is accepted, verify diagonal paths in both directions, parallel motion, touches without crossing, boundary/endpoint cases, initial-frame objects, incomplete transitions, outside-region paths, jitter and documented gap behavior. Report genuine unknown policies instead of encoding invented acceptance criteria. These tests validate deterministic behavior, not video accuracy.
4. **Temporal review of retained tracks:** replay existing Phase 4 ReID-on track records/observations against the reviewed geometry and selected BC, with its box-source contract explicit. Preserve source-detection links, history, class/component ambiguity and duplicate-ID evidence. No YOLO, tracker or encoder rerun is required or authorized by this replay stage. Use actual stored frames/temporal evidence and state the inspected scope. Retained experimental ReID-on traces are not acceptance of that tested encoder as the final product default.
5. **Parameter selection after evidence:** investigate explicitly recorded geometry/noise/gap parameters on the agreed cases, retain both useful behavior and failures, and select values only when justified. Do not present this stage as detector/tracker/ReID tuning or a model-quality benchmark.

## Deliverables and scope limits

The current deliverable is the G3 proposed normalized default/visual revision based on the supplied line/A points/BC/B cap and delegated preparation, its actual source/track provenance and this staged task record; G1/G2 and all feedback remain retained. Later authorized stages produce versioned per-video geometry configuration, the documented contract, deterministic geometry capability/tests, temporal/anchor review and explicit parameter decisions. These later artifacts/results do not yet exist by implication of this task description.

ReID remains part of the confirmed architecture. Phase 4 rejected selection of one tested setting as the current vehicle default; a final vehicle-ReID configuration remains OPEN. Preserve all Phase 1–4 original evidence and decisions. Do not remove ReID, switch detector/tracker, restrict full-frame detection by these polygons, implement GMC/stabilization, enhance night video, process other videos or add multi-GPU/UI/Docker/production modules in this task.

Phase 5 establishes geometry/crossing behavior; trustworthy event/category counting and aggregation belong to Phase 6 and remain blocked by unresolved duplicate/identity/category policies. No actual crossing events, traffic totals or accuracy/improvement claim is established by G1, synthetic tests or visual plausibility. No formal ground truth exists.
