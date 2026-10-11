# Phase 4 — controlled TOR3-PAGI ReID contribution experiment

**REQUIREMENT / AUTHORIZATION:** the user requested actual Phase 4 execution on TOR3-PAGI, review of its results, and a readiness assessment for Phase 5. This does not authorize Phase 5 implementation. Read `AGENTS.md`, `CODEX_WORKFLOW.md`, `MODEL_SPEC.md`, `BOTSORT_TRACKING.md`, `OPEN_DECISIONS.md`, `API_CONTRACT.md`, `TEST_PLAN.md`, and `EVALUATION.md` first.

## Objective and scope

Evaluate whether an actually working appearance encoder changes identity association beneficially on the inspected cases. Verify its implementation, retain a controlled ReID-disabled comparison, inspect both changed and unchanged cases/regressions, and explicitly accept an experimental configuration or reject the tested candidate/configuration. Successful execution alone is not evidence of improved identity.

Use the same TOR3-PAGI source and all 10,282 ordered Phase 2 cached detection rows. Preserve source/cache hashes, raw classes, confidence, frame order, native-pixel boxes, published tracker thresholds/lifecycle, seed, and `gmc_method='none'`. No YOLO detection inference, detector-threshold change, stabilization, night enhancement, category filtering, geometry, crossing, counting, or multi-GPU orchestration is included.

## Documented experimental encoder choice

**PROPOSAL — one untuned candidate:** use the officially documented dedicated `yolo26n-reid.onnx` encoder through the pinned Ultralytics 8.4.175 BoT-SORT external-model path. This is an appearance model, not a replacement detector. Its authoritative release asset is:

- URL: `https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-reid.onnx`.
- SHA-256: `8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb`.
- Published size: 9,873,245 bytes.
- **FACT — inspected ONNX metadata:** the training configuration identifies `MSMT17-v1.yaml`, a person-ReID domain. Vehicle-domain suitability/transfer is **UNKNOWN**; no vehicle-performance claim follows from the model name or official availability.
- **FACT — verified input/output:** the asset has dynamic float32 image input and 512-dimensional embeddings. The pinned direct wrapper falls back to input size 224 for dynamic spatial dimensions; record this untuned wrapper setting explicitly. The documented/export size 448 is not an embedding dimension or proof that the runtime uses 448.

Verify the asset, pinned encoder source, actual crop/normalization, embedding output, runtime/provider and tracker integration before accepting any experiment. Use an explicitly recorded ONNX Runtime version verified against authoritative package metadata. The selected GPU execution provider must be available and used in an actual encoder inference; do not infer this from PyTorch CUDA visibility and do not silently fall back to a different model/provider.

The native `model='auto'` path lacks detector features in this retained cache and is excluded. Off/on variants differ in the appearance component and its required model/device configuration; all motion/lifecycle/association thresholds remain fixed. Runtime costs must identify decoder, tracker and encoder work where actually measured; no comparison with Phase 2 detector latency is implied.

## Required evidence and comparisons

1. Actual finite, nonzero embeddings, their dimensions/counts, encoder calls and provider/device evidence; prove that features reach association and record whether appearance changes association costs.
2. Fresh independent trackers for the complete off/on sequences. Preserve ordered detection links, IDs/history/lifecycle, gaps and raw-class evidence. Verify instance-scoped ID/state independence; the pinned implementation supplies its own per-tracker ID iterator.
3. Compare off replay with retained Phase 3 outputs to establish baseline compatibility, without rerunning detector inference or silently replacing the original evidence.
4. Review actual temporal pixels and linked records for red-scooter duplicate tracks (5125–5154), entering rider/scooter class/component handoff (7696–7725, focused 7711–7718), roadside gap/recovery (7712–7718), and previously stable beginning/receding/end cases.
5. Compare variants by source frame/detection index and visible physical component, not by assuming equivalent numeric IDs after associations diverge. Lower ID/gap/class-change totals are software diagnostics, not identity improvement or vehicle counts.
6. Keep original execution exports unchanged. Record the subsequent AI-assisted review separately with its exact sampling scope, observed benefits, unchanged cases, regressions and unknowns. No formal identity/counting accuracy metrics without appropriate annotations.

## Deliverables and validation

- `notebooks/04_reid_comparison.ipynb`: reproducible, parameterized capability notebook; no saved execution output or source videos in Git.
- `docs/REID_EXPERIMENT.md`: verified choice/integration, actual run, evidence-linked review, candidate decision, limitations and Phase 5 readiness assessment.
- `docs/evidence/phase_4/`: provenance, retained actual paired records, representative temporal evidence, independent audit and review; lossless compression is allowed with original hashes retained.
- Minimal supported status updates in existing project documentation after actual execution.

Validate pinned compatibility, cache identity/order, feature/association plumbing, independent ID/lifecycle behavior, record links, actual artifacts and decodable temporal samples. Distinguish local checks from actual Kaggle execution and sampled visual review.

## Phase 5 readiness assessment

The decision must distinguish completion of this tested ReID experiment from acceptance of a final ReID solution. A supported, actually executed candidate with no demonstrated benefit may be explicitly rejected; this does not remove ReID from the confirmed architecture.

Phase 5 develops deterministic geometry independently of model quality, using synthetic trajectories first. Recommend it only with retained Phase 4 results and an explicit candidate decision/limitations. Before real-track geometry relies on an anchor or crossing rule, document per-video coordinates/dimensions/A-B semantics, boundary/overlap/line rules, selected or explicitly compared anchor, observed-versus-predicted/gapped trajectory policy and crossing/noise semantics. Duplicate/category/identity risks still block trustworthy vehicle counting and remain open for Phase 6. Do not implement Phase 5 in this task.
