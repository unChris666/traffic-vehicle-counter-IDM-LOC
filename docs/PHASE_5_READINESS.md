# Phase 4 acceptance and Phase 5 readiness

**Scope:** the user authorized TOR3-PAGI Phase 4 execution and an assessment of whether Phase 5 can follow. This assessment implements no geometry, crossing or counting. Phase 5 has not started.

**DECISION — Phase 4 experiment: PASS for the scoped contribution test. Phase 5: conditionally ready for deterministic geometry using synthetic trajectories first. Trustworthy vehicle counting: not ready.**

## Actual Phase 4 objective checks

The [experiment record](REID_EXPERIMENT.md), [original Kaggle execution report](evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_report.json), [independent audit](evidence/phase_4/20261011T095924_205716Z_90cf7319/artifact_audit.json) and [subsequent visual review](evidence/phase_4/20261011T095924_205716Z_90cf7319/manual_reid_review.json) support this assessment. Original pending-review fields remain unchanged; the later review is separate.

| Phase 4 objective | Actual retained evidence | Acceptance limit |
|---|---|---|
| Verify real appearance capability | Official `yolo26n-reid.onnx` and pinned integration verified; 10,275 encoder calls produced 50,713 finite, nonzero 512D features. An encoder profile confirms CUDA kernels with explicit CPU graph partitions. | Working appearance inference is established; vehicle-domain suitability is not. |
| Controlled disabled/enabled comparison | Both variants completed the same 10,282 TOR3-PAGI cached frames. Input identity, detector evidence and tracker motion/lifecycle thresholds were preserved; GMC remained none. No detector inference ran. | This is one untuned encoder/configuration comparison. |
| Baseline compatibility and inspectable association | All off-variant frame records and 4,922 captured track histories/lifecycles match original Phase 3 canonically. Independent actual-artifact audit passed 19/19 checks; local helper validation passed 12 checks. Appearance lowered 53,152 eligible association-cost pairs. | Changed costs and software ID/gap/class counters are not physical-identity improvement metrics. |
| Review difficult and stable cases | Actual paired temporal pixels and detection-linked records were reviewed for the duplicate red scooter, entry component/class handoff, five-frame gap/recovery and stable controls. | Sampled review is not full-video physical-identity annotation. |
| Decide the tested candidate | The tested candidate/configuration is not selected as the current vehicle-ReID default; reasons are retained below. | This completes the experiment without accepting a final vehicle-ReID solution or removing ReID from the architecture. |

## Tested candidate decision

**EXPERIMENT RESULT:** the same visible red scooter still has concurrent motorcycle tracks (off 1934/1951; on 964/973). The entering rider/scooter still shows the same class/component handoff (off 3681/3683; on 1772/1774). The roadside track recovers after five missing observations in both variants (off 3622; on 1731). Previously stable receding/end controls retain local continuity in both.

The beginning sequence shows a software association/confirmation difference on a very small raw-car candidate. Its physical identity is visually ambiguous; this does not establish a vehicle-identity benefit. Numeric ID correspondence follows shared source observations, not equal ID numbers across variants.

**EXPERIMENTAL DECISION:** reject this tested untuned setting for selection as the current vehicle-ReID default. The reviewed priority failures remain, no convincing physical-identity benefit is established within this review, and instrumented loop time was 41.1397 seconds off versus 422.9125 seconds on. These measured costs include instrumentation, sequential execution and warmup effects; they are not an optimized production benchmark. The model's declared MSMT17 person-ReID provenance further leaves vehicle transfer unestablished.

This decision applies to this asset, preprocessing, thresholds and scene only. It does not prove every ReID approach ineffective, select a replacement, or remove ReID from the confirmed target. A final suitable vehicle-ReID configuration remains OPEN.

## What may follow in Phase 5

`CODEX_WORKFLOW.md` defines Phase 5 as deterministic geometry/direction logic developed independently of model quality, with synthetic trajectories first. The completed comparison and explicit candidate decision satisfy the Phase 4 experimental prerequisite. The next task can therefore document and test geometry while retaining the identity limitations.

Before dependent implementation, explicitly define:

1. Per-video coordinate convention, native/processed dimensions, configurable A/B polygons and line endpoints, and per-video semantic metadata. The reference screenshot does not provide TOR3-PAGI polygon vertices.
2. Line-segment intersection, point-on-line/polygon boundaries, polygon validity, overlap/gap treatment and dimension consistency.
3. A selected or explicitly compared anchor, such as center or bottom-center. Stored track `center` does not select a default; candidate comparison is allowed before a final choice.
4. Which observation/prediction histories enter the trajectory, and how gaps affect crossing evidence. Missing observations must not silently become measured movement.
5. Origin establishment, crossing followed by opposite-side arrival, and explicit noise/state-transition semantics. Numerical hysteresis, confirmation and time/gap values remain unset until documented.

Use synthetic diagonal, parallel, touch-only, incomplete-crossing, initial-frame, outside-region, boundary and jitter trajectories to validate the chosen contract. Real-track replay may later inspect alignment and anchor behavior; it does not establish counting reliability. No geometry implementation is authorized by this readiness assessment alone.

## Remaining blockers for counting

Concurrent duplicate-track treatment, identity recovery across changed IDs/re-entry, genuine repeat-crossing policy, pedestrian-versus-rider and bus/angkot mapping, category stabilization/assignment, suitable lifecycle thresholds and final vehicle-ReID configuration remain OPEN. Resolving these is necessary before claiming trustworthy event/category totals in Phase 6. Camera alignment and source timestamp limits also remain; frame-index/FPS estimates are not verified source PTS.

No formal ground truth exists. No accuracy, tracking/counting score, general identity improvement or physical vehicle total is claimed. See [COUNTING_LOGIC.md](COUNTING_LOGIC.md), [OPEN_DECISIONS.md](OPEN_DECISIONS.md), [TEST_PLAN.md](TEST_PLAN.md) and [EVALUATION.md](EVALUATION.md).
