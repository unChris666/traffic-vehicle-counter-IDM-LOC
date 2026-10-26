<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Phase 3 — BoT-SORT tracking status

**REQUIREMENT:** the user authorized Phase 3 after a Phase 2 review without rerunning detection. [PHASE_2_REVIEW.md](PHASE_2_REVIEW.md) records the technical gate; [PHASE_3_TASK.md](PHASE_3_TASK.md) defines the scope. This capability replays the retained detector stream, then decodes the matching video for alignment and rendering. It does not load YOLO weights or execute detector inference.

**STATUS — PASS for the scoped Phase 3 technical objective.** Kaggle version 1 actually completed all 10,282 aligned cached frames in run `20261011T060227_579936Z_05ebe213`, on 2026-10-11 at 13:02:27–13:03:25 WIB. No detector inference was rerun. Source verification, 16 local helper/render checks and 12 independent actual-artifact checks passed. Subsequent AI-assisted temporal review records both usable continuity and concrete identity/category risks below. This establishes an auditable no-ReID baseline for a later Phase 4 comparison, not traffic-counting readiness or identity accuracy.

## Verified tracker implementation

**EXPERIMENT RESULT — source and compatibility checks:** the [verification record](evidence/phase_3/verification/source_verification.json) compares installed Ultralytics 8.4.175 tracker/config/results files with the matching official pinned sources; their SHA-256 digests match. The verified class is `ultralytics.trackers.bot_sort.BOTSORT`, constructed with `BOTSORT(args)` and updated with `update(results, img=None, feats=None, **kwargs)`.

The cache adapter constructs Ultralytics `Boxes` from native-pixel rows:

| Boundary | Verified representation |
|---|---|
| Cached detections → tracker | `N × 6`: `x1, y1, x2, y2, confidence, class_id`; frame dimensions remain attached. |
| Activated tracker outputs | `N × 8`: Kalman box `x1, y1, x2, y2`, `track_id`, score, latest class ID, original detection index. |
| No emitted outputs | The library may return shape `(0,)`; the adapter normalizes that to `(0, 8)`. |
| Frame order | Tracker `frame_id` is the one-based update-call count; cached zero-based `frame_index = frame_id - 1`. Empty-detection rows still advance it. |

Each emitted score/class is checked against the linked original cached detection. IDs are scoped to one tracker instance/video and do not prove physical identity. The pinned association is class-agnostic: there is no hard class gate, and the track class is updated from its latest matched detection. Raw class changes are retained for inspection rather than stabilized or mapped to product categories.

The source requires `lap>=0.5.12`. **EXPERIMENT RESULT:** `lap==0.5.13` was verified against PyPI metadata, its CPython 3.12 Linux wheel digest, and an actual installation in the isolated validation environment. The local direct tracker import/update succeeded. The actual Kaggle report also verifies these pinned tracker/dependency versions and successful full-sequence updates.

## Explicit untuned configuration

**PROPOSAL — controlled Phase 3 baseline:** inherit the pinned package's published `botsort.yaml` defaults, record their provenance, and explicitly disable GMC/ReID for this experiment. These are not tuned production thresholds.

| Setting | Published value | Experiment value / meaning |
|---|---|---|
| `tracker_type` | `botsort` | Unchanged. |
| `track_high_thresh` | `0.25` | Unchanged, untuned. |
| `track_low_thresh` | `0.1` | Unchanged; the parent cache does not contain the complete lower-confidence range. |
| `new_track_thresh` | `0.25` | Unchanged, untuned. |
| `track_buffer` | `30` | Literal frames in this verified implementation; actual `max_frames_lost=30`, with no FPS conversion or established source-time duration. |
| `match_thresh` | `0.8` | Unchanged, untuned. |
| `fuse_score` | `True` | Unchanged. |
| `gmc_method` | `sparseOptFlow` | Explicit override `none`; actual local `gmc.method` is `None`. No need/benefit decision is established. |
| `proximity_thresh` | `0.5` | Retained, inactive appearance setting in this baseline. |
| `appearance_thresh` | `0.8` | Retained, inactive appearance setting in this baseline. |
| `with_reid` | `False` | Explicitly disabled for Phase 3; actual local encoder is `None`. |
| `model` | `auto` | Retained; no appearance model is loaded with ReID disabled. |

**FACT — pinned internal behavior:** second-stage IoU cost limit `0.5`, unconfirmed-track cost limit `0.7`, and tracked/lost duplicate IoU-distance ceiling `0.15` are source constants, not user-selected or tuned product parameters. Their actual behavior, including discarded/unconfirmed IDs, is retained for later inspection.

ReID remains part of the confirmed architecture and belongs to Phase 4. The Phase 2 cache contains no native detector embeddings/features. The verified native `auto` appearance path requires those features; enabling it on this cache is not an established supported ReID experiment. Appearance model/assets/integration and benefit remain OPEN. This baseline also does not decide that GMC is unnecessary.

## Retained input and execution provenance

- Parent detector run: `20261011T052950_360560Z_ed399fb8`.
- Video: TOR3-PAGI, 1280 × 720, expected 10,282 cached frames; SHA-256 `606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c`.
- Original `frame_detections.jsonl`: 13,712,465 bytes; SHA-256 `033a2815d3abbd23327936a1b9d948b2b9b7d312796516e5ee46aec5685be345`.
- [Retained input audit](evidence/phase_3/verification/retained_input_audit.json): 10,282 rows, seven zero-detection rows, 50,713 repeated raw detector observations. Those are frame-level observations, not vehicle totals.
- Private supporting input: [traffic-counter-phase-2-retained-cache](https://www.kaggle.com/datasets/chrisbiran/traffic-counter-phase-2-retained-cache). [Upload manifest](evidence/phase_3/kaggle_job/cache_upload_manifest.json) records unchanged prediction/report bytes. This is retained output replay, not a new ground-truth dataset, new inference or a grant of a new reuse license; inherited source-license metadata remains unknown.
- Separate private [Phase 3 notebook](https://www.kaggle.com/code/chrisbiran/traffic-counter-phase-3-botsort), source [03_botsort_tracking.ipynb](../notebooks/03_botsort_tracking.ipynb), version 1. [Submission receipt](evidence/phase_3/kaggle_job/submission_receipt.json) and [source readback verification](evidence/phase_3/kaggle_job/source_readback_verification.json) retain source identity, privacy and attached dataset configuration.

The actual Kaggle environment records Python 3.12.13, four CPUs, Ultralytics 8.4.175, lap 0.5.13, PyTorch 2.10.0+cu128, NumPy 2.0.2, OpenCV 4.13.0 and two visible Tesla T4s. Association/Kalman operations ran on CPU with no detector or ReID inference; GPU visibility is not GPU tracker execution. The mounted input/cache hashes match the original retained Phase 2 identities.

## Executed local validation

**EXPERIMENT RESULT — real cache CPU smoke, not full-video tracking:** [cached smoke report](evidence/phase_3/verification/cached_smoke_report.json) records successful direct BoT-SORT updates on the first 200 actual retained TOR3-PAGI rows, frame 0–199, without image/model inference. Python 3.12.14, Ultralytics 8.4.175, lap 0.5.13, NumPy 2.5.2 and PyTorch 2.13.0+cpu were used. Output index/class/score linkage, frame progression and finite eight-column outputs passed. Fourteen emitted tracker IDs and 651 repeated emitted records are software observations only. No physical-identity review or full-run claim follows from this smoke.

**EXPERIMENT RESULT — software/helper checks:** [16 checks](evidence/phase_3/verification/notebook_helper_validation.json) passed, with zero failures. They cover actual 200-row observer/uninstrumented output and lifecycle equivalence, all cached-row validation, empty updates and fresh IDs, malformed identity/order/hash/box/confidence/class/linkage and duplicate-ID rejection, partial-failure retention, actual 30-frame clip write/decode roundtrip, and contact-sheet/display-crop helpers. Negative fixtures are software checks, not detector/tracker performance evidence. Full Kaggle execution is explicitly unestablished by this helper record.

## Evidence schema and counter semantics

The notebook writes separate run directories and preserves failed/partial status in `tracking_report.json`. Output semantics are declared in notebook Markdown cell 6:

- `track_records.jsonl`: one row for each cached source frame, including empty rows. `raw_detections` preserves parent evidence; `emitted_tracks` contains activated outputs linked to original detection indices. Tracker `bbox` is Kalman-filtered; `raw_bbox` is the associated detector observation. Unclipped out-of-frame Kalman estimates remain inspectable; drawing coordinates alone are bounded by the renderer.
- `track_summary.json`: every captured ID, including never-emitted/unconfirmed IDs. The observer retains newly created object references before pool deduplication and does not change tracker association/state transitions; actual 200-row equivalence was tested.
- Lifecycle snapshots separate library state, pool membership, current measurement and prediction. `not_retained` means disappearance from retained library pools without an explicit removal notification; it is not fabricated as `Removed`. Newly removed objects can remain in the lost pool for an update.
- `trajectory`: ordered detection-linked observations, including unconfirmed assignments. Predicted/lost states do not become measured trajectory. Raw-box centers are debug observations and do not select the OPEN geometry anchor.
- `detection_count`: number of assigned observations for that ID, once per frame. `emitted_observation_count` counts the subset actually emitted. `first_seen_frame`/`last_seen_frame` delimit assigned observations; `missing_frame_count` is consecutive frames since the latest assignment at the ID's last recorded lifecycle snapshot. Gap events between observations retain the intervening missing-frame count.
- `direction` and `counting_state` remain `None`. Unique IDs, gap events, class changes and lifecycle transitions are software diagnostics; no physical vehicle totals or traffic events are generated.

Actual representative evidence includes five full-history 30-frame bursts, native samples and a focused frame 7711–7718 entering-scooter sheet. Temporal records/clips inherit all earlier tracker updates instead of reinitializing the tracker for each burst. Display cropping never affects association, eligibility or detector evidence. The original execution export remains pending visual review; the actual subsequent [review supplement](evidence/phase_3/20261011T060227_579936Z_05ebe213/manual_tracking_review.json) records its AI-assisted provenance and bounded inspected scope separately.

## Actual full-run result and temporal review

**EXPERIMENT RESULT:** the original [execution report](evidence/phase_3/20261011T060227_579936Z_05ebe213/tracking_report.json) and manifest record 10,282 consecutive tracker updates and aligned video reads. The subsequent [independent artifact audit](evidence/phase_3/20261011T060227_579936Z_05ebe213/artifact_audit.json) passed 12/12 checks: retained input identity, all source/record links, lifecycle/history bookkeeping, timings, 37 declared artifact hashes, five raw frame pairs identical to Phase 2, and five decodable 30-frame clips. No detector/tracker was rerun by the audit.

| Actual measurement | Value and interpretation |
|---|---|
| Full processing loop | 34.1562 seconds, including decode, association, bookkeeping, serialization and selected frame writes. |
| Tracker updates plus Boxes adapter | 13.6615 seconds total; mean 1.3287 ms/update, median 1.2068 ms/update. CPU association only. |
| Decoder reads | 9.8365 seconds; 10,282 frames plus the final unsuccessful read probe. |
| Selected render/PNG writes | 1.3024 seconds; separate temporal export/audit stage 6.2866 seconds. |
| IDs ever emitted | 780; 45,756 repeated emitted observations. These are software counters, not vehicle totals. |
| All captured IDs | 4,922, including 4,142 never emitted/unconfirmed IDs. This does not mean 4,142 false objects. |
| Within-ID gaps / raw class changes | 1,633 / 497; diagnostic candidates, not physical ID-switch counts. |
| Empty input / no emitted outputs | Seven / 14 frames; every frame still advanced tracker state. |

**EXPERIMENT RESULT — bounded AI-assisted visual review:** [the review supplement](evidence/phase_3/20261011T060227_579936Z_05ebe213/manual_tracking_review.json) uses actual saved pixels and records. Its scope is six displayed positions from each of five bursts, all eight focused entering-scooter frames, four native focused annotations, and six consecutive frames decoded from the retained red-scooter clip. Clip frame-count validation is separate from visual review: the five clips were not all watched end to end and the full video was not physically annotated.

- **Local continuity:** person ID 933 and motorcycle ID 935 stay on the visible receding rider/scooter in the displayed 2555–2584 positions. They describe components of the same vehicle scene, so raw person must not become a pedestrian count.
- **Concurrent duplicate tracks:** on the visibly same red scooter, motorcycle ID 1934 remains active while motorcycle ID 1951 is initialized at 5128 and emitted alongside it at 5129–5132. Distinct raw boxes/indices back both outputs. The [six-frame clip sheet](evidence/phase_3/20261011T060227_579936Z_05ebe213/temporal/red_scooter_5125_5130_clip_contact_sheet.png) and [record trace](evidence/phase_3/20261011T060227_579936Z_05ebe213/duplicate_scooter_trace_5125_5154.json) show a duplicate-track risk, not a simple replacement of one ID by another or an implemented counting error.
- **Class/component association handoff:** ID 3681 starts as unconfirmed handbag at 7711, emits person at 7712, then motorcycle at 7713. ID 3683 starts unconfirmed motorcycle at 7712 and emits person from 7713. Native annotations show rider/scooter components changing these assignments at the cropped, overlaid entry. See the [focused sheet](evidence/phase_3/20261011T060227_579936Z_05ebe213/temporal/entering_scooter_000007711_000007718_contact_sheet.png) and [trace](evidence/phase_3/20261011T060227_579936Z_05ebe213/focused_track_trace_7711_7718.json). This is observed local association/class instability; a whole-video physical ID-switch total remains unknown.
- **Gap and reactivation:** roadside-position motorcycle ID 3622 has no assignment at 7713–7717 and returns under the same ID at 7718. Native frames/records support this one local recovery case. The missing observations' cause and general recovery reliability remain unknown.

The original exported report's pending review fields remain unchanged. The later supplement records the actual review with its provenance; no human ground truth, accuracy score or fabricated in-notebook review is added.

**ACCEPTANCE — scoped PASS:** verified BoT-SORT integration, complete ordered processing, inspectable ID/history/lifecycle records and actual temporal review satisfy the Phase 3 objectives. Identity/category risks remain concrete limitations. This baseline supports a separately authorized Phase 4 experiment; it is not ready to provide vehicle counts. Verify a usable appearance encoder/assets/integration first, then compare ReID enabled/disabled on equivalent retained inputs without assuming an improvement. Native `auto` cannot supply missing detector features from this cache. Phase 4 has not started.

## Artifact retention and reproduction

[The archive](evidence/phase_3/20261011T060227_579936Z_05ebe213/README.md) keeps original execution reports unchanged, losslessly compressed full records/summary, curated tracked PNGs/contact sheets, and subsequent audit/review supplements. The [compression manifest](evidence/phase_3/20261011T060227_579936Z_05ebe213/compression_manifest.json) records compressed and original byte identities. Original videos/weights, raw frames already retained in Phase 2, executed notebooks and the five annotated MP4 clips remain outside this Git archive; the private Kaggle version-1 output retains the complete run artifacts.

To inspect the retained result, open the private Phase 3 notebook's version-1 Output and the linked archive/review; no rerun is required. For a later authorized reproduction, import `03_botsort_tracking.ipynb`, attach the two datasets in the saved metadata, use a fresh session and Run All. Explicit input paths/parent run/hashes must remain coherent; this would execute only cached BoT-SORT. Reproducing Phase 3 is separate from rerunning YOLO.

## Remaining limits and review gate

The detector cache already used `conf=0.25`; boxes discarded below that score are unavailable for the tracker's complete lower-confidence second-stage range. Missing detector boxes cannot be reconstructed by replaying this cache. No detector rerun or threshold change is implied.

Sampled continuity, gap/reactivation and identity/class risks were reviewed from actual retained temporal pixels and records below; whole-video identity correctness remains unknown. Programmatic gap/class/ID diagnostics are candidates, not confirmed physical-identity errors. Five short bursts cannot prove every identity throughout the complete video. Product pedestrian/rider and bus/angkot mapping, tuned tracker settings, ReID/GMC, night/other scenes, source PTS/decode integrity and later geometry/counting decisions remain OPEN.

Actual timing separates association/update, decode, selected rendering and total loop where measured; serialization is included in the loop without its own counter. Tracking-only time is not an equivalent detector/tracker benchmark against Phase 2. No ground truth exists; no accuracy, precision, recall, F1, MAPE, IDF1, MOTA or counting-quality claim is supported. Phase 4 is not started by this baseline.
