# Phase 5 — staged geometry collaboration on TOR3-PAGI

**AUTHORIZATION:** the user requested the staged workflow: visual candidate → feedback → revision → documented rules → synthetic tests → temporal review → parameter selection. This task starts with a concrete visual proposal for feedback. It does not treat that proposal as approved geometry or skip dependent stages.

**CURRENT STAGE:** first visual draft G1, pending user feedback. No anchor, crossing rule, numerical tolerance, hysteresis, confirmation length or gap policy is selected. No crossing algorithm, event generation or counting is implemented or executed at this stage.

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

The user must review line placement, region extent, coverage of the intended vehicle paths, and actual directional meaning. If A/B instead mean separate opposing lanes, resolve that interpretation before adopting the required A → line → B/B → line → A contract. Do not silently reinterpret an accepted counting requirement.

The two displayed anchor candidates use the same detector-linked observation of retained ReID-on motorcycle track 973: center approximately `(249,509)` and bottom-center approximately `(249,546)` on frame 5140. Both remain candidates. The displayed raw box and points are illustrative track evidence; they do not establish physical road-contact position, eligibility or a valid crossing. Shared polygon/line edges shown in G1 do not select boundary or tolerance rules.

## Subsequent stages and gates

1. **Feedback and revision:** obtain feedback on G1 geometry and actual direction mapping; revise the proposal with preserved version/provenance. No response is not approval. Candidate coordinates belong to per-video configuration, not a hardcoded reusable pipeline.
2. **Document rules before dependent implementation:** define coordinate/dimension conventions, finite-line/endpoint and polygon validity semantics, boundary/overlap/gap handling, origin/crossing/opposite-side transitions, and treatment of observed versus predicted/missing trajectory points. Compare center and bottom-center explicitly; select an anchor only after its evidence and decision are recorded. Numerical values remain OPEN until investigated in the agreed later stage.
3. **Synthetic validation first:** once the required contract is accepted, verify diagonal paths in both directions, parallel motion, touches without crossing, boundary/endpoint cases, initial-frame objects, incomplete transitions, outside-region paths, jitter and documented gap behavior. Report genuine unknown policies instead of encoding invented acceptance criteria. These tests validate deterministic behavior, not video accuracy.
4. **Temporal review of retained tracks:** replay existing Phase 4 ReID-on track records/observations against the geometry and anchor candidates. Preserve source-detection links, history, class/component ambiguity and duplicate-ID evidence. No YOLO, tracker or encoder rerun is required or authorized by this replay stage. Use actual stored frames/temporal evidence and state the inspected scope. Retained experimental ReID-on traces are not acceptance of that tested encoder as the final product default.
5. **Parameter selection after evidence:** investigate explicitly recorded geometry/noise/gap parameters on the agreed cases, retain both useful behavior and failures, and select values only when justified. Do not present this stage as detector/tracker/ReID tuning or a model-quality benchmark.

## Deliverables and scope limits

The current deliverable is the reviewable G1 pixel proposal, its actual source/track provenance and this staged task record. Later authorized stages produce versioned per-video geometry configuration, the documented contract, deterministic geometry capability/tests, temporal/anchor review and explicit parameter decisions. These later artifacts/results do not yet exist by implication of this task description.

ReID remains part of the confirmed architecture. Phase 4 rejected selection of one tested setting as the current vehicle default; a final vehicle-ReID configuration remains OPEN. Preserve all Phase 1–4 original evidence and decisions. Do not remove ReID, switch detector/tracker, restrict full-frame detection by these polygons, implement GMC/stabilization, enhance night video, process other videos or add multi-GPU/UI/Docker/production modules in this task.

Phase 5 establishes geometry/crossing behavior; trustworthy event/category counting and aggregation belong to Phase 6 and remain blocked by unresolved duplicate/identity/category policies. No actual crossing events, traffic totals or accuracy/improvement claim is established by G1, synthetic tests or visual plausibility. No formal ground truth exists.
