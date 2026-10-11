# Phase 4 — TOR3-PAGI appearance association experiment

**REQUIREMENT:** the user authorized a controlled TOR3-PAGI ReID experiment and Phase 5 readiness analysis. Scope and acceptance are in [PHASE_4_TASK.md](PHASE_4_TASK.md). Phase 5 implementation is outside this task.

**STATUS — actual experiment complete:** the private [Kaggle notebook](https://www.kaggle.com/code/chrisbiran/traffic-counter-phase-4-reid-comparison), version 1, completed both 10,282-frame sequences. Actual retained artifacts passed 19 independent audit checks; subsequent AI-assisted visual/source-link review is complete within its declared sample scope. **DECISION:** the tested untuned candidate/configuration is not selected as the current vehicle-ReID default. Phase 4 passes as a contribution experiment with explicit candidate rejection; a final suitable vehicle-ReID configuration remains OPEN. Phase 5 has not started.

## Verified candidate and integration

**FACT — authoritative asset/source:** dedicated `yolo26n-reid.onnx` is documented for the pinned Ultralytics BoT-SORT external-encoder path. The official release [asset verification](evidence/phase_4/verification/official_asset_verification.json) records its URL, 9,873,245-byte size and SHA-256 `8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb`. Installed pinned encoder/backend sources match authoritative v8.4.175 source hashes; see [CPU source/integration verification](evidence/phase_4/verification/cpu_candidate_smoke.json).

**FACT — declared training provenance:** inspected model metadata identifies `MSMT17-v1.yaml`; the original CVPR paper describes MSMT17 as a person-ReID benchmark. The [authoritative reference record](evidence/phase_4/verification/official_runtime_references.json) identifies sources/hashes. No training was performed here, the actual training corpus was not inspected, and vehicle-domain effectiveness is UNKNOWN. **PROPOSAL:** test this available dedicated encoder as one candidate; availability is not acceptance for vehicle identity.

The pinned API is `BOTSORT(args)` with an explicit external model and device; `update(Boxes(...), img=actual_BGR_frame, feats=None)`. The source selects high/low detection boxes and computes appearance features through its encoder. Native `auto` without cached detector features supplies no usable appearance evidence and is excluded.

## Untuned preprocessing and association behavior

**FACT — pinned source behavior:** the model input is dynamic float32 `[batch,3,height,width]`, output is 512-dimensional float32 embeddings. Because the spatial dimensions are dynamic, the direct wrapper uses its 224×224 fallback, despite model metadata/export size 448. No size experiment is performed in this initial comparison.

Upstream crops use `save_one_box` with gain 1.02/pad 10 and clipping, then bilinear resizing and division by 255. Its crop channel reversal and tensor channel reversal result in BGR channel order relative to the original frame. This records the actual upstream path; no alternate channel/normalization correction is silently introduced and the asset's expected color convention is not asserted from absent metadata.

BoT-SORT normalizes/smooths appearance features. Its source computes cosine distance divided by two, masks appearance costs above `1 - appearance_thresh` and spatial pairs above `1 - proximity_thresh`, then takes the minimum of appearance and score-fused IoU cost. With fixed published defaults (`appearance_thresh=0.8`, `proximity_thresh=0.5`), appearance can lower eligible costs; it cannot itself veto an IoU match. Low-confidence second-stage matching remains IoU-based, class gating is absent, and duplicate removal is IoU-based. ReID is therefore not an implemented class-stabilization or concurrent-duplicate-merging policy.

**REQUIREMENT — controlled comparison:** preserve the original detector cache, tracker thresholds/lifecycle, seed, frame order, all raw classes and GMC none. Compare fresh ReID-off and ReID-on trackers over all 10,282 frames. Association remains CPU; the encoder requests CUDA 0 in Kaggle. Actual encoder-session provider/inference evidence, not PyTorch visibility, must establish GPU execution. Candidate runtime pins are `onnx==1.20.1` and `onnxruntime-gpu==1.24.4`; verified package provenance is retained with local CPU counterparts.

## Actual local validation

**EXPERIMENT RESULT — tiny CPU compatibility smoke:** six retained detections in native TOR3-PAGI frame 5140 generated six finite/nonzero unit-norm 512D features. Repeat feature maximum absolute difference was zero for this CPU sample. Direct external-encoder BoT-SORT emitted a 6×8 array and all six tracks held normalized current features. [The smoke report](evidence/phase_4/verification/cpu_candidate_smoke.json) records actual inputs, model/source identities, runtime and outputs; [the method](evidence/phase_4/verification/cpu_candidate_smoke.py) is retained. No detector weights were loaded or detection inference executed. This verifies compatibility for that tiny CPU combination only, not Kaggle CUDA or physical identity quality. The [12 helper checks](evidence/phase_4/verification/notebook_helper_validation.json) and [independent observer review](evidence/phase_4/verification/independent_observer_review.json) additionally verify exact output/lifecycle/feature equivalence to the uninstrumented tracker on declared software fixtures, empty-frame behavior, malformed-feature rejection and profiling-factory restoration. Repeated use of one frame in a software fixture is not a chronological source-video experiment.

## Actual Kaggle execution and review

**EXPERIMENT RESULT:** run `20261011T095924_205716Z_90cf7319` executed on 2026-10-11, 09:59:24–10:08:11 UTC. Both variants replayed all 10,282 original cached frames. No detector inference ran. The off variant matches original Phase 3 across every source/association/lifecycle frame record and all 4,922 captured track histories, excluding timing and run/variant metadata. Original [execution report](evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_report.json) and [manifest](evidence/phase_4/20261011T095924_205716Z_90cf7319/run_manifest.json) retain their export-time pending-review fields; the subsequent [AI-assisted review](evidence/phase_4/20261011T095924_205716Z_90cf7319/manual_reid_review.json) records the later findings and decision separately.

The dedicated encoder produced 50,713 finite/nonzero 512D embeddings in 10,275 calls. The [actual first-update profile](evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/encoder_provider_evidence.json) records **137 CUDA node events and 20 CPU node events**. This establishes actual CUDA execution with explicit CPU graph partitions, rather than merely visible GPUs. Association remains CPU; the second visible T4 was unused. Profiling covers the first real encoder update, not every call.

Appearance lowered **53,152 candidate costs** relative to motion/score-fused IoU on the **same on-variant tracker state**; 11,606 association calls contained usable features and 11,105 calls changed costs. This is not an off/on assignment-pair comparison after tracker histories diverge, and is not a number of improved identities. The [direction check](evidence/phase_4/20261011T095924_205716Z_90cf7319/association_cost_direction_verification.json) records the limited independent matrix reconstruction and full-run observer/source assertions.

The [independent read-only artifact audit](evidence/phase_4/20261011T095924_205716Z_90cf7319/artifact_audit.json) passed **19/19 checks**: input hashes/frame order, exact off-baseline compatibility, embedding/association/summary consistency, provider profile, 84 declared artifact hashes, native source pixels and 10 exported clips × 30 decoded frames. This audit executed no detector, tracker or encoder. The final audit helper passed five software checks; a float64-versus-upstream-float32 audit-method correction is documented separately without changing execution exports. All full records are retained losslessly compressed; [archive details](evidence/phase_4/20261011T095924_205716Z_90cf7319/README.md) describe what remains in private Kaggle Output.

| Actually reviewed case | ReID off | ReID on | Supported finding |
|---|---|---|---|
| Same visible red scooter | Concurrent motorcycle IDs 1934/1951 | Concurrent 964/973 | The observed duplicate remains. |
| Entering rider/scooter | IDs 3681/3683 with class/component handoff | IDs 1772/1774 with the same source-linked class sequences | `handbag → person → motorcycle` and `motorcycle → person` persist. |
| Roadside motorcycle gap | 3622 absent on 7713–7717, returns 7718 | 1731 follows the same observation gap/recovery | Existing local recovery is preserved; additional benefit is not established. |
| Small beginning raw-car candidate | Fresh unconfirmed 6/8/9/10/11 | 6 confirmed/reacquired on 11/16/19/29 | Appearance changes real association/confirmation. Physical same-car benefit is visually unestablished. |
| Receding/end controls | Locally continuous sampled rider/motorcycle/car components | Locally continuous corresponding sampled components | No apparent regression at displayed positions; intervening frames and whole-video correctness are not established. |

The beginning candidate is approximately 33×20 native pixels and partly covered by annotation labels. Display-only crops from retained annotated MP4s do not restore missing discriminative detail. Source-linked assignments and changed costs establish a software difference, but do not prove physical identity improvement. Cross-variant IDs are mapped by frame/source-detection links; unequal numeric IDs are not themselves switches.

### Measured cost and diagnostic limits

| Actual measured quantity | ReID off | ReID on |
|---|---:|---:|
| Full instrumented loop, seconds | 41.1397 | 422.9125 |
| Tracker update calls, seconds | 18.2061 | 399.1188 |
| Encoder time, already inside tracker time, seconds | 0 | 373.8537 |
| Mean tracker update, milliseconds | 1.7707 | 38.8172 |
| Captured software IDs, including unconfirmed | 4,922 | 2,402 |
| Emitted software IDs | 780 | 997 |
| Within-ID observation gap events | 1,633 | 2,135 |
| Within-ID raw class changes | 497 | 1,088 |

Loop timing includes decode, observer/cost validation, serialization and selected rendering/writes. Sequential order and warmup affect the measurement; it is not an optimized production benchmark or full YOLO pipeline FPS. Encoder time must not be added again to tracker time. ID/gap/class counters describe software behavior and changed track histories; fewer captured IDs do not prove less fragmentation, and more raw class changes do not alone establish more physical ID errors. No physical vehicle totals or accuracy metrics are justified.

### Explicit tested-candidate decision

**EXPERIMENTAL DECISION — reject this tested untuned configuration for selection as the current vehicle-ReID default.** The reviewed priority duplicate and class/component failures remain, convincing physical identity benefit is not established within the actual review, and measured instrumented processing cost is higher. The candidate's declared person-ReID provenance leaves vehicle transfer unestablished. This decision applies to this asset, preprocessing/settings and scene; it does not prove every ReID approach ineffective, select a replacement, or remove ReID from the target architecture.

Further vehicle-ReID experiments should define the intended association problem and comparable, visibly discriminative cases before varying one documented factor at a time. Duplicate component handling and category assignment require their own policies; this appearance-cost integration does not implement them. No tuning or alternative candidate was silently selected here.

**Unresolved execution/review limits:** OpenCV returned `read_false` after all expected cache rows; this alone cannot distinguish ordinary EOF from a terminal decoding condition. All expected frames aligned and exported clips decoded. Frame-index/FPS time estimates are not verified original PTS. Review is sampled and AI-assisted, not full-video human annotation or ground truth; night behavior remains untested in this experiment.

## Phase 5 readiness

**DECISION — conditionally ready for synthetic deterministic geometry first:** Phase 4 capability, controlled comparison, actual difficult-case review and explicit candidate decision are complete. The [Phase 5 readiness assessment](PHASE_5_READINESS.md) defines the remaining per-video geometry, anchor, boundary/overlap, gap/prediction and noise/state-transition decisions before dependent implementation. Duplicate/category policy and final vehicle identity configuration still block trustworthy counting. Phase 5 has not started and no geometry/counting implementation is included in this task.
