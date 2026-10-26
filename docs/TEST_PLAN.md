<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

## Status implementasi aktif

Validasi rilis0.4.7rc1:208tes lokal selesai,8dilewati. Cakupan baru meliputi pemilihanprofile, maskGPU perchild, eksklusi satuvideo/GPU, antrean1/2GPU, failurecontinuation, reusecache dan independensiArea/Traffic. GPUganda diuji simulasi; belum ada dualGPUbenchmark nyata. Akurasianotasi belum dievaluasi.

## Konteks dan kontrak terdahulu

# Test Plan

## 1. Ground Truth Status

No formal ground-truth dataset currently exists.

Therefore, model accuracy and counting accuracy are NOT current acceptance criteria.

This document specifies checks, not executed results. Phase 0 validation is specification consistency; original evidence/status for later phases remains in their own review documents. Scoped TOR3 Phase 1 inspection is retained, and original [Phase 6](PHASE_6_TASK.md) Opsi A validation follows [COUNTING_CONTRACT.md](COUNTING_CONTRACT.md). The subsequently authorized [Opsi B task](PHASE_6_OPTION_B_TASK.md) adds the component/episode checks below; actual execution belongs to [PHASE_6_OPTION_B_REVIEW.md](PHASE_6_OPTION_B_REVIEW.md). Synthetic checks and bounded real pixel review remain distinct from formal ground-truth evaluation.

## 2. Test Levels

### Unit Tests

Test deterministic logic independently from the model:

- point-in-polygon
- line intersection
- side classification
- trajectory transition
- duplicate-count prevention
- state-machine transitions
- aggregation

### Integration Tests

Test the pipeline boundaries:

- detector output → tracker input
- tracker output → geometry
- geometry → counting event
- events → aggregation

### End-to-End Tests

Run representative videos through the complete pipeline and verify that:

- output video is produced
- track IDs exist
- events are produced in the expected schema
- result aggregation is internally consistent

## 3. Detection Invariants

- bounding boxes have valid coordinates
- confidence values are valid
- class IDs are from the configured class set
- detections are serializable/loggable

## 4. Tracking Invariants

- active track IDs are unique within a video
- track state is updated consistently
- temporary detection gaps do not automatically imply a new physical object
- track history is monotonic in frame order

Do not assume a tracker can guarantee identity under every occlusion. Such behavior must be evaluated empirically.

## 5. Geometry Tests

Use synthetic points/trajectories to test:

- points inside Side A
- points inside Side B
- points outside both regions
- line intersection
- diagonal trajectories
- movement parallel to the line
- movement that touches but does not cross
- crossing with jitter near the line
- arbitrary per-video diagonal line/polygon placement in pixel coordinates
- explicitly configured anchor candidates, without treating a candidate as an accepted default

These tests do not require a trained model or ground truth.

## 6. Counting Tests

Required invariants:

- one valid A → B crossing produces one event
- one valid B → A crossing produces one event
- repeated frames after crossing do not produce duplicate events
- jitter around the line does not create repeated events
- an ineligible track does not create a count
- changing class confidence alone must not create a new vehicle
- an object visible in an eligible region in the first processed frame is not counted on presence alone
- an eligible initial-frame object can produce an event after a subsequent valid crossing and opposite-side arrival
- bounding-box contact with the counting line alone does not produce an event
- a crossing without confirmed arrival in the opposite configured side does not produce an accepted directional event

The [Phase 6 counting contract](COUNTING_CONTRACT.md) now specifies audit-gated identity/dedup/return handling for the prototype: unreviewed or conflicted candidates do not count; only reviewed same unit + same passage is deduplicated; a later episode requires independent return review. Positive-duration overlapping crossing intervals assigned distinct passage IDs remain pending. Geometry gaps/endpoint/predictions and person↔vehicle histories cannot be repaired by review overrides. Suitable production identity recovery, numerical thresholds and final taxonomy remain OPEN; tests must exercise explicit pending behavior rather than hide the unresolved policy.

## 7. Night Preprocessing Tests

Treat each preprocessing variant as an experiment.

For identical sampled frames, compare configured variants such as:

- raw
- gamma
- brightness/exposure
- contrast
- sharpening
- combinations only when justified

Record actual observations.

Do not claim improvement without evidence.

## 8. Regression Tests

Once a behavior is accepted, preserve a minimal fixture or deterministic test so future refactors do not silently change it.

## 9. Manual Validation

Because ground truth is unavailable, maintain a small manually inspected audit set.

For each inspected video, record:

- video identifier
- geometry configuration
- model configuration
- preprocessing configuration
- observed count behavior
- obvious false detections
- obvious ID switches
- duplicate counts
- missed crossings

Manual inspection is evidence, but it is not a statistically rigorous accuracy benchmark.

## 10. Test Reporting

Every implementation task should report:

- tests executed
- tests passed
- tests failed
- tests not run
- relevant assumptions
- unresolved issues


## Phase 5 implemented prototype validation

The standard-library [synthetic suite](../notebooks/phase_5_synthetic_tests.py) exercises the [accepted qualitative contract](GEOMETRY_CONTRACT.md), including diagonal A→B/B→A, finite endpoints/extensions, measured touches, region boundaries, gaps/predictions, explicit band/confirmation, G3 line-versus-polygon offset and raw detection linkage. Numeric fixtures are test controls, not product defaults. The [notebook](../notebooks/05_geometry_replay.ipynb) stops before cache replay when a test fails. See [PHASE_5_REVIEW.md](PHASE_5_REVIEW.md) for results actually executed, initial regressions, retained provenance and visual scope. This historical validation remains separate from Phase 6 counting tests.

## Phase 6 implemented prototype validation

**ENGINEERING EXPERIMENT — checks, not results:** [phase_6_synthetic_tests.py](../notebooks/phase_6_synthetic_tests.py) tests the [Opsi A contract](COUNTING_CONTRACT.md) before [06_counting_audit.ipynb](../notebooks/06_counting_audit.ipynb) processes retained sources. Required cases include unreviewed hold despite no overlap, full supported A→B/B→A, rider/pedestrian distinction, full-window component changes, category conflicts, missing/tampered evidence, same-unit/passage dedup, return review, simultaneous conflicting episodes, idempotent IDs/snapshots and accepted-event reconciliation. Reviews used in fixtures are software test inputs, not evidence of real-video outcomes.

Actual real-window reviews must validate raw pixel/source alignment and state which origin/contact/passage/confirmation frames were inspected. A contact interval requires its measured contact evidence, not just an endpoint. Review cannot upgrade ambiguous geometry or component-changing trajectories; unknown pickup/bus/angkot interpretation stays pending. Machine outputs must remain separate from resolved outcomes, and event subtotal must reconcile without implying completeness or accuracy. Actual executed test counts, retained events/decisions and independent artifact checks belong only to [PHASE_6_REVIEW.md](PHASE_6_REVIEW.md).

## Phase 6 Opsi B component/episode validation

**IMPLEMENTED ENGINEERING EXPERIMENT — checks, not results:** [phase_6_identity_resolution_tests.py](../notebooks/phase_6_identity_resolution_tests.py) guards [06b_identity_resolution_comparison.ipynb](../notebooks/06b_identity_resolution_comparison.ipynb) before retained-source replay. Fixtures test measured family/gap reset before scope, no origin inheritance, immutable raw source linkage/vehicle BC, rider/passenger grouping, duplicate vehicles, nearby pedestrian/two-motor negatives, unique-parent ambiguity, raw unconfirmed alternatives, non-clique transitivity, category conflict, gap/endpoint/prediction exclusion, genuine return, idempotence and accepted-only reconciliation. Synthetic coordinates/thresholds are explicit software fixtures, not actual video observations.

For v1, regression tests require sufficient component/duplicate support **within each candidate origin–confirmation interval**: later graph support cannot accept an earlier passage, insufficient local duplicate support stays pending, and excluded earlier passages still affect genuine-return review. Category checks preserve complete vehicle episode/group evidence and disclose offline use of later observations. Episode-only/no-grouping ablation must preserve episode/geometry inputs while changing relation authorization; each output has its own namespace.

Actual replay compares A original, A updated, ablation, B machine and B reviewed per physical passage and raw crossing source. The 13-ID/six-window case scope requires bounded pixel/temporal audit of wrong merge, duplicates/misses, categories, origin/passage/confirmation and alternatives. Full A pending totals or raw namespace decision counts are not comparable performance metrics. Frozen development controls and held-out component support remain separate; real negative/duplicate generalization coverage is limited and must be stated. Machine outputs stay immutable when review is added, and absent appearance vectors cannot be claimed as used. Actual test totals, corrected-run provenance, artifact checks and findings belong to [PHASE_6_OPTION_B_REVIEW.md](PHASE_6_OPTION_B_REVIEW.md), with no ground-truth accuracy claim.
