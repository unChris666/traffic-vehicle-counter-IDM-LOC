<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Phase 5 — staged geometry collaboration on TOR3-PAGI

**AUTHORIZATION:** the user requested the staged workflow: visual candidate → feedback → revision → documented rules → synthetic tests → temporal review → parameter selection. The subsequent G3 approval, in the context of the explicit G3-and-initial-rules question, authorizes progression to the documented qualitative contract, synthetic validation and retained-track replay. Keep the question and answer together; this does not mean the user restated every rule or accepted numerical product parameters.

**CURRENT STAGE:** [G3 feedback 001](evidence/phase_5/feedback/G3_review_001.json) records the explicit G3-and-initial-rules question and the user's contextual approval, including Polygon B and unchanged A points labelled `P1A/P1B/P1C/P1D`. [G3-L1](evidence/phase_5/review_drafts/G3-L1/README.md) adds labels without moving points. The simple perimeter `A → B → D → C → A` is the valid engineering representation of the accepted point set, not a new approval gate or an assertion that the user requested `A → B → C → D`. G3's 960 × 540 canvas is the accepted new template context, not reconstruction of the UNKNOWN scaled source dimensions/crop. Relative defaults require review per video. BC from linked raw detection boxes and TOR3-PAGI `A_TO_B` approaching / `B_TO_A` away are the accepted baseline. [GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md) is documented and the prototype executed 40/40 synthetic tests followed by six retained-track configurations. [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md) records actual results, the 25-check independent audit and visual/parameter limits. Numerical jitter/confirmation parameters, physical-identity deduplication/category policy and universal reliability remain OPEN.

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

G1 displayed center approximately `(249,509)` and bottom-center approximately `(249,546)` from the same detector-linked observation of retained ReID-on motorcycle track 973 on frame 5140. The latest user instruction selects **BC**, not center, for the current geometry. This does not establish physical road-contact position, eligibility or a valid crossing. The later contextual G3 approval adopts BC from linked raw detection boxes for the initial contract; Kalman predictions do not confirm a crossing. The original preview alone did not select that box source. Shared polygon/line edges do not establish numerical tolerance or robustness.

## Delegated relative default and G3 label review

**USER-CONFIRMED POLICY:** use a relative template and review per video. The user delegates an adjusted default despite not knowing the scaled source's dimensions, and requests a later page for setting lines/polygons. Do not ask for those dimensions again as a prerequisite to this newly authorized default. A future setup page belongs to Phase 11; no product UI is implemented here.

**CONFIRMED G3 CONTEXT — new reference:** the user approves G3, including its new 960 × 540 template context, containing the supplied points and matching TOR3-PAGI's 16:9 aspect ratio. This remains an engineering convention, not a discovered/recovered source-image size. Normalize `u=x/960`, `v=y/540`; preview at native 1280 × 720 by `x_native=u×1280`, `y_native=v×720`. Runtime geometry remains resolved per-video image pixels. This coordinate mapping does not establish equivalent physical-road placement for other viewpoints/aspects.

| User-supplied element | Coordinates preserved in the G3 template |
|---|---|
| Complete counting line | `P1=(4.5,516.5)`, `P2=(936.4,305.4)` |
| Side A point labels, not an explicit traversal | `P1A=(4.5,516.5)`; `P1B=(4.5,348.2)`; `P1C=(936.6,305.8)`; `P1D=(557.5,165.3)` |
| Side B extent | Maximum `X=875` in template units; polygon cap only, not a shortened counting line |

**ENGINEERING REPRESENTATION — accepted A point set:** connect `A → B → D → C → A` (the existing `1 → 2 → 4 → 3 → 1` simple perimeter), retaining every coordinate. The user's new labels identify points rather than requesting traversal in label order; using the simple perimeter is routine polygon validation, not a new user-approval gate. Connecting `A → B → C → D → A` would cross edges. A point `P1C=(936.6,305.8)` differs from line P2 `(936.4,305.4)`; preserve both without snapping or claiming an identical boundary.

**CONFIRMED — Polygon B:** the user approves G3's B outline beneath the shared A edge, clipped at template `X=875`, with bottom reference `Y=532.5`.

**CONTEXTUALLY ACCEPTED — initial qualitative contract:** use BC from observed linked raw detection boxes and the finite counting-line segment. Boundary observations are neutral; touching the line alone is insufficient. Require an observed origin → line passage → observed arrival at the opposite side. Ambiguous endpoint or gap passage cannot confirm that sequence, and Kalman predictions do not confirm it. This baseline is accepted through the G3-and-initial-rules question/answer, not because the user separately repeated every rule. Numerical neutral-band/jitter tolerance and destination confirmation settings remain OPEN and require experiments.

The entire line continues to template `X=936.4`. Intersecting its part beyond B's cap does not automatically establish arrival in B. Proceed from the labelled G3 visual to the documented initial contract, synthetic tests and retained-track replay; do not request the same A coordinates or a new perimeter approval.

**RELIABILITY STATUS:** the requested default is an initial editable template. Review/adjust geometry and directional metadata per video; cross-video reliability is NOT ESTABLISHED. Source-image reconstruction remains UNKNOWN but does not block the delegated G3 template. No original camera-angle/road alignment, all-video counting quality or successful crossing follows from normalization. The current scope is TOR3-PAGI geometry/trajectory validation, not an eight-video experiment.

## Subsequent stages and gates

1. **Accepted visual and label clarification:** the user approves G3 and its initial rules in context, including Polygon B, BC and relative-template review per video. Finalize [G3-L1](evidence/phase_5/review_drafts/G3-L1/README.md) with the supplied A labels and unchanged coordinates, using the validated simple perimeter rather than treating the point listing as explicit traversal. Preserve all prior drafts/feedback. Do not recover an unknown source by assumption, snap distinct vertices, shorten the line to the B cap or treat the default as validated for every video. No repeated coordinate/perimeter approval blocks the next stage.
2. **Document the accepted initial contract before dependent implementation:** retain coordinate/dimension and valid-polygon conventions, finite-line passage, neutral boundaries, touch-only exclusion, ambiguous endpoint/gap treatment, origin/passage/opposite-side arrival and observed-versus-predicted behavior. Use BC from linked raw detection boxes; do not silently switch to center or a predicted box. Validate behavior rather than presenting this choice as proven robustness. Numerical values remain OPEN until investigated in the agreed later stage.
3. **Synthetic validation first — completed scoped software gate:** verify the accepted qualitative contract with diagonal paths in both directions, parallel motion, touches without crossing, boundary/endpoint cases, initial-frame objects, incomplete transitions, outside-region paths, jitter and documented gap behavior. Label experimental parameter choices explicitly rather than inventing accepted numerical settings. Report results only after execution and retention. These tests validate deterministic behavior, not video accuracy.
4. **Temporal review of retained tracks — completed cache replay, visual scope explicit:** replay existing Phase 4 ReID-on track records/observations against the accepted G3 geometry using observed linked raw-box BC and the documented initial contract; retain results before claiming findings. Preserve source-detection links, history, class/component ambiguity and duplicate-ID evidence. No YOLO, tracker or encoder rerun is required or authorized by this replay stage. Use actual stored frames/temporal evidence and state the inspected scope. Retained experimental ReID-on traces are not acceptance of that tested encoder as the final product default.
5. **Parameter decision after evidence — suitable defaults OPEN:** investigate explicitly recorded geometry/noise/gap parameters on the agreed cases, retain both useful behavior and failures, and select values only when justified. Do not present this stage as detector/tracker/ReID tuning or a model-quality benchmark.

## Deliverables and scope limits

Current work comprises the G3-L1 label-only clarification, versioned TOR3-PAGI geometry, the accepted initial qualitative contract, deterministic synthetic validation and retained-track temporal/anchor replay. Coordinates remain unchanged, and G1/G2/G3 plus question/answer feedback remain retained with actual source/track provenance. The actual software/replay results are retained in [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md); figure checks and diagnostic frequencies are distinct from physical counting. Parameter decisions follow actual evidence; no universal/product values are accepted by implication of geometry approval.

ReID remains part of the confirmed architecture. Phase 4 rejected selection of one tested setting as the current vehicle default; a final vehicle-ReID configuration remains OPEN. Preserve all Phase 1–4 original evidence and decisions. Do not remove ReID, switch detector/tracker, restrict full-frame detection by these polygons, implement GMC/stabilization, enhance night video, process other videos or add multi-GPU/UI/Docker/production modules in this task.

Phase 5 establishes geometry/crossing behavior; trustworthy event/category counting and aggregation belong to Phase 6 and remain blocked by unresolved duplicate/identity/category policies. No physical-vehicle traffic total or accuracy/improvement claim follows from visual geometry approval, deterministic tests or provisional track-event replay. No formal ground truth exists.
