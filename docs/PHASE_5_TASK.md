# Phase 5 — staged geometry collaboration on TOR3-PAGI

**AUTHORIZATION:** the user requested the staged workflow: visual candidate → feedback → revision → documented rules → synthetic tests → temporal review → parameter selection. This task starts with a concrete visual proposal for feedback. It does not treat that proposal as approved geometry or skip dependent stages.

**CURRENT STAGE:** the user has supplied concrete revision instructions after the initial [G1 feedback](evidence/phase_5/feedback/G1_review_001.json): see [feedback 002](evidence/phase_5/feedback/G1_review_002.json). Use full line endpoints `P1=(4.5,516.5)` and `P2=(936.4,305.4)`, adjust A/B polygons to that line, and cap Side B at `X=875`. Bottom-center (BC) is selected. TOR3-PAGI event direction remains `A_TO_B` approaching / `B_TO_A` away. [G2](evidence/phase_5/review_drafts/G2/README.md) is the revised visual-review stage; the engineer-adjusted polygons and dependent contract still require review. Numerical tolerances, hysteresis, confirmation and gap policy remain OPEN. No crossing algorithm, event generation or counting is implemented or executed at this stage.

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

G1 remains an unapproved historical proposal. Feedback 002 now supplies the requested line positions and authorizes the engineer to revise its polygons accordingly; preserve G1 and feedback 001 rather than overwriting their original coordinates/status. Preserve the A → line → B/B → line → A sequence and confirmed TOR3-PAGI direction mapping; do not reinterpret A/B as separate opposing lanes.

G1 displayed center approximately `(249,509)` and bottom-center approximately `(249,546)` from the same detector-linked observation of retained ReID-on motorcycle track 973 on frame 5140. The latest user instruction selects **BC**, not center, for the current geometry. This does not establish physical road-contact position, eligibility or a valid crossing. Whether operational BC comes from the linked raw box or Kalman-filtered box remains OPEN; the preview raw box is evidence, not an implicit operational choice. Shared polygon/line edges in a preview do not select boundary or tolerance rules.

## Requested G2 revision and default template

**USER REQUIREMENT:** retain the complete segment from `(4.5,516.5)` to `(936.4,305.4)`. Side B ends at `X=875`; this clips its polygon only and must not truncate the line endpoint to 875. Engineer-adjusted A/B polygons are a revision proposal within these constraints. A trajectory intersecting the part of the line beyond the B cap does not automatically establish arrival in B.

**ASSUMPTION FOR THE VISUAL REVISION:** the supplied numbers use the existing G1 native 1280 × 720 pixel frame. Display scaling must not silently change their meaning.

**USER REQUIREMENT — reusable default:** the user requests this line as a default and reliable behavior across videos. Preserve it as the requested starting template while retaining per-video configurable geometry and explicit source dimensions. Cross-video reliability is **NOT ESTABLISHED**. Resolution/aspect-ratio mapping, viewpoint/path coverage, region adjustment and actual validation for each video remain OPEN; no automatic scaling/transfer or universal geometric correctness is selected by the request. The first deliverable remains the TOR3-PAGI G2 visual revision, not an eight-video experiment.

## Subsequent stages and gates

1. **Feedback and revision:** the direction mapping, exact revised line, B cap and BC selection are supplied. Produce G2 with preserved version/provenance and review the engineer-adjusted polygon outlines. Do not shorten the line to the B cap or treat a requested default as validated for every video. The staged workflow remains authorized; dependent rules/tests/replay wait for the required geometry/contract review. Coordinates belong to per-video configuration with the requested reusable starting template.
2. **Document rules before dependent implementation:** define coordinate/dimension conventions, finite-line/endpoint and polygon validity semantics, boundary/overlap/gap handling, origin/crossing/opposite-side transitions, and treatment of observed versus predicted/missing trajectory points. Use the user-selected BC and explicitly define which track-box representation supplies it; do not silently switch to center. Validate its behavior rather than presenting the selection as proven robustness. Numerical values remain OPEN until investigated in the agreed later stage.
3. **Synthetic validation first:** once the required contract is accepted, verify diagonal paths in both directions, parallel motion, touches without crossing, boundary/endpoint cases, initial-frame objects, incomplete transitions, outside-region paths, jitter and documented gap behavior. Report genuine unknown policies instead of encoding invented acceptance criteria. These tests validate deterministic behavior, not video accuracy.
4. **Temporal review of retained tracks:** replay existing Phase 4 ReID-on track records/observations against the reviewed geometry and selected BC, with its box-source contract explicit. Preserve source-detection links, history, class/component ambiguity and duplicate-ID evidence. No YOLO, tracker or encoder rerun is required or authorized by this replay stage. Use actual stored frames/temporal evidence and state the inspected scope. Retained experimental ReID-on traces are not acceptance of that tested encoder as the final product default.
5. **Parameter selection after evidence:** investigate explicitly recorded geometry/noise/gap parameters on the agreed cases, retain both useful behavior and failures, and select values only when justified. Do not present this stage as detector/tracker/ReID tuning or a model-quality benchmark.

## Deliverables and scope limits

The current deliverable is the G2 visual revision based on the supplied coordinates/BC/B cap, its actual source/track provenance and this staged task record; G1 and both feedback records remain retained. Later authorized stages produce versioned per-video geometry configuration, the documented contract, deterministic geometry capability/tests, temporal/anchor review and explicit parameter decisions. These later artifacts/results do not yet exist by implication of this task description.

ReID remains part of the confirmed architecture. Phase 4 rejected selection of one tested setting as the current vehicle default; a final vehicle-ReID configuration remains OPEN. Preserve all Phase 1–4 original evidence and decisions. Do not remove ReID, switch detector/tracker, restrict full-frame detection by these polygons, implement GMC/stabilization, enhance night video, process other videos or add multi-GPU/UI/Docker/production modules in this task.

Phase 5 establishes geometry/crossing behavior; trustworthy event/category counting and aggregation belong to Phase 6 and remain blocked by unresolved duplicate/identity/category policies. No actual crossing events, traffic totals or accuracy/improvement claim is established by G1, synthetic tests or visual plausibility. No formal ground truth exists.
