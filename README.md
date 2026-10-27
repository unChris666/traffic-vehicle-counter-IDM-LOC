Area gagal atau peta kosong: [diagnosis dan pemulihan](docs/AREA_FAILURE_RECOVERY.md).

Kaggle: [hasil BQ, HTML peta dari GCS dan tabel breakdown PPAC](docs/KAGGLE_READABLE_RESULTS.md).

Kaggle terbaru: [upload terputus, sumber GCS/Input, tabel ringkas dan isi PPAC](docs/KAGGLE_UPLOAD_RECOVERY.md).

Panduan terbaru: [Docker dan Cloud Run GPU](docs/DOCKER_CLOUD_RUN_GUIDE.md), termasuk delapan slot upload dan hasil BQ/peta.

> Upload video Gradio dan konfigurasi hasil GCS/BQ0.5.0rc1: [panduan setup owner](docs/CLOUD_STORAGE_SETUP.md), [SQL tabel/view](sql/location_intelligence_setup.sql). Sumber model/PBF/reference tetap terpisah.

<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](docs/CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Traffic Vehicle Counter + Area Coverage + PPAC

Package **0.4.8rc1** menyediakan engine modular dan workflow headless. Traffic memakai YOLO26M FP32 batch4, ReID IO binding/window8/crop32; satu GPU menangani satu video dan dua GPU dapat menangani dua video bersamaan.

Mulai dari [status terkini](docs/CURRENT_STATUS.md), [integration layer](docs/GATE2_INTEGRATION.md), dan [perubahan Traffic/GPU](docs/TRAFFIC_CANDIDATE_GPU_RUNTIME.md).

[Notebook Kaggle workflow Sorong + T7SL](https://www.kaggle.com/code/chrisbiran/gate2-t7sl-sorong-integration-quiz) memakai paket tertanam yang sama. Aktifkan GPU, Internet dan Secret `LocatioIntelligent`, lalu jalankan notebook. Gradio mencetak URL publik; engine menunggu tombol pengguna.

Area dan Traffic dapat dijalankan terpisah. PPAC MVP v2 menerima hasil PARTIAL yang lolos validasi; input hilang/gagal/tidak kompatibel tetap ditolak. Jam operasional >15 memerlukan sesi tambahan, sehingga delapan video T7SL belum cukup untuk PPAC18jam.

Kandidat menghemat33,16% pada satu video, dengan total133 yang sama tetapi identitas track berbeda. Precision/recall dan percepatan dua GPU belum dibuktikan.

UI sementara sekarang memakai [Gradio](docs/GRADIO_INTEGRATION_UI.md). Jalankan notebook, lalu buka `GRADIO_PUBLIC_URL`; seluruh input dan proses dilakukan dari browser.

## Riwayat checkpoint dan hasil terdahulu

**T7SL fresh batch — 24 Oktober 2026:** [notebook Kaggle baru](https://www.kaggle.com/code/chrisbiran/t7sl-fresh-modular-traffic-batch) sedang berjalan; dua Tesla T4 dan mount dataset teramati. [Scope, konfigurasi, revisi geometri dan status verifikasi](docs/T7SL_FRESH_BATCH_REVIEW.md). Belum ada total T7SL terverifikasi sebelum output terminal direkonsiliasi.

**B v6 — kebijakan terbaru (20 Oktober 2026):** [review implementasi dan gate P0](docs/B_V6_USER_POLICY_REVIEW.md), [notebook replay cache](notebooks/09c_user_policy_replay.ipynb), dan [hasil/video audit](results/b_v6/README.md). Seluruh 9.128 frame pilot direplay tanpa model baru: 74 accepted (66 measured +8 estimasi), 24 pending dan 84 scope invalid/+0. BUS dan panel/ekspor baru tersedia; 146 tes software lulus. **P0 tetap BLOCKED:** review sumber menemukan dua estimasi untuk satu motor pada 1049→1123; penurunan pending belum membuktikan counting lebih benar.

**P0 B v5 dan eksperimen model (20 Oktober 2026):** [review hasil dan gate P1](docs/B_V5_P0_REVIEW.md), [notebook replay P0](notebooks/09a_p0_qc_replay.ipynb), dan [eksperimen confidence CUDA aktual](docs/MODEL_CONFIGURATION_EXPERIMENT_REVIEW.md). Dua replay pilot serta eksperimen model selesai; B v5 masih mempunyai duplikasi residual dan false holds sehingga belum mengganti baseline. Confidence 0,10 belum dipilih sebagai default. Artefak baru tersimpan di `results/b_v5/` dan `results/model_experiments/`.

**QC lanjutan B v4 (20 Oktober 2026):** [hasil dan keputusan seluruh 68 pending](results/phase_9/20261020_QC_BV4_SIANG/REPORT.md), [daftar 68 kasus beserta bukti](results/phase_9/20261020_QC_BV4_SIANG/PENDING_DECISIONS.md), dan [rekomendasi perbaikan lintasvideo](docs/PHASE_9_QC_RECOMMENDATIONS.md). Sebanyak 59 kasus direkomendasikan selesai (57 dengan +0, dua dengan +1); sembilan tetap unresolved. Terdapat pula 16 event accepted unik yang direkomendasikan batal. Ini keputusan QC berbasis sumber, belum perubahan ledger atau hasil algoritme baru; cakupannya satu video TGDI-WEEKDAY-SIANG.

**Perbaikan B v4 dan review 360° (20 Oktober 2026 WIB):** [hasil aktual, batas bukti dan SWOT](results/b_v4/REVIEW_360.md), [notebook replay](notebooks/08d_episode_eligibility_role_replay.ipynb), dan [artefak review](results/b_v4/README.md). Pilot TGDI-WEEKDAY-SIANG selesai tanpa inference model baru: 121 crossing terukur baseline tetap dipertahankan; machine 172 accepted/68 pending, review-assisted 173/67. Kandidat penelitian ini belum default produksi. Bagian berikut mempertahankan status historisnya masing-masing.

**Persiapan Phase 9:** [tugas audit](docs/PHASE_9_TASK.md), [input–proses–output Phase 1–8](docs/PHASE_9_AUDIT_PROTOCOL.md), [prompt siap pakai](docs/PHASE_9_PROMPT.md), dan [template pencatatan](docs/templates/PHASE_9_AUDIT_TEMPLATES.md). Targetnya daftar perbaikan berbasis bukti; dokumen ini belum menyatakan audit selesai atau algoritme counting diperbaiki. Hasil audit aktual kelak disimpan terpisah di `results/phase_9/<audit_id>/`.

**Pilot Phase 9 selesai pada scope yang dipilih:** [laporan TGDI-WEEKDAY-SIANG](results/phase_9/20261019T140653Z_TGDI_WEEKDAY_SIANG_PILOT/REPORT.md), [sembilan item perbaikan](results/phase_9/20261019T140653Z_TGDI_WEEKDAY_SIANG_PILOT/improvement_backlog.csv), dan [bukti audit](results/phase_9/README.md). Review mencakup 70 sampel frame native, tujuh frame anotasi rilis dan tujuh objek target; audit seluruh video/delapan video belum dilakukan. Usulan reviewed terpisah dari machine B v3; tidak ada model, counting, enhancement atau renderer yang dijalankan ulang.

**Revisi Phase 8 B v3 (19 Oktober 2026):** [kode, konfigurasi dan bukti uji terbaru](results/b_v3/README.md) · [kontrak identitas/passage/pedestrian](docs/PHASE_8_REVISION_CONTRACT.md) · [objektif Phase 9](docs/PHASE_9_TASK.md). Replay baru memakai cache model terverifikasi, dengan hasil terpisah dari baseline B v2. Eksekusi Kaggle selesai: 236 tes lulus, delapan video/72.590 frame, dan [delapan anotasi B v3 di GitHub](results/b_v3/VIDEOS.md). Snapshot siap untuk audit Phase 9; bagian fase sebelumnya di bawah dipertahankan sebagai riwayat.

Phase 8 research has processed the **eight actual TGDI videos** at `/kaggle/input/datasets/chrisbiran/tgdi-traffic-videos`: **72,590 frames, 58 passages accepted by the machine and 1,825 pending candidates**. Physical audit remains open. See the [task](docs/PHASE_8_TASK.md), [batch notebook](notebooks/08_end_to_end_batch.ipynb), [current review](docs/PHASE_8_REVIEW.md), and [actual input preparation](docs/evidence/phase_8/input_preparation/README.md). All eight G3-T1 geometries/directions are approved for an initial research trial. User-confirmed unknown store name/coordinates remain null; final-product metadata is incomplete. The batch notebook defaults to `prepare`; the retained research execution used the approved v2 manifest and `run_batch`.

[Annotation review](docs/ANNOTATED_VIDEO_REVIEW.md) and [notebook 08a](notebooks/08a_annotation_review.ipynb) add a render-only category/direction pivot, raw-class bbox colours, frame references and supported component-unit labels from the immutable results. **[All eight annotated MP4s are available in GitHub Releases](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/tag/phase8-annotation-review-v1)**, independently of Kaggle session lifetime. [Actual publication evidence](docs/evidence/phase_8_publication/success_20261016/final_publication_receipt.json) binds every video to its source and server SHA. Publication used a scoped GitHub Actions job token; models/counting were not rerun and occlusion ID changes remain open.

Phase 1 has [passed acceptance for TOR3 morning/night](docs/PHASE_1_ACCEPTANCE.md). The latest retained Kaggle reports match the earlier Codex input identities, sampling, and AI-assisted visual reviews. All 21 fields contain observations or explicit unknown/open limitations; model risks remain untested hypotheses. The older `TDLE-PAGI` report-only review and other inputs remain visually unresolved.

The authorized [Phase 2: one-video YOLO detection](docs/PHASE_2_TASK.md) completed its technical baseline in Kaggle: YOLO26M / Ultralytics 8.4.175 processed all **10,282 TOR3-PAGI frames returned by the decoder** on `cuda:0`, with matching serialized rows. The [retained-evidence review](docs/PHASE_2_REVIEW.md) passed its technical objective without rerunning detection. See [detection status and retained GPU evidence](docs/YOLO_DETECTION.md) for sampled review and limitations; model quality, other-scene generalization, and production suitability remain unproven.

The subsequently authorized [Phase 3 baseline](docs/PHASE_3_TASK.md) also executed in Kaggle: direct Ultralytics 8.4.175 BoT-SORT replayed all 10,282 retained detection rows against the matching video, without loading or running YOLO. Association used CPU with `with_reid=False` and `gmc_method='none'`; two Tesla T4s were visible but did not perform tracking inference. See [tracking execution, temporal review and limitations](docs/BOTSORT_TRACKING.md), [source notebook](notebooks/03_botsort_tracking.ipynb), and the [private Kaggle notebook](https://www.kaggle.com/code/chrisbiran/traffic-counter-phase-3-botsort). Tracker IDs and gap/class diagnostics are not vehicle totals or confirmed identity-error counts. At that phase, crossing and counting algorithms had not been implemented; the later Phase5 geometry prototype is described below.

The authorized [Phase 4 contribution experiment](docs/PHASE_4_TASK.md) completed ReID-off/on processing of the same 10,282 TOR3-PAGI cached frames, without detector inference. The dedicated official `yolo26n-reid.onnx` produced 50,713 finite 512D features with actual CUDA execution; the off replay matches Phase 3 and 19 independent artifact checks passed. [Actual paired review](docs/REID_EXPERIMENT.md) finds the priority duplicate/component-handoff cases unchanged and the five-frame gap recovered in both variants. The tested person-domain encoder setting is **not selected as the current vehicle-ReID default**; physical-identity benefit is unestablished and measured instrumented cost increased. This does not remove ReID from the architecture. See the [source notebook](notebooks/04_reid_comparison.ipynb), [private Kaggle notebook](https://www.kaggle.com/code/chrisbiran/traffic-counter-phase-4-reid-comparison), and [Phase 5 conditional readiness](docs/PHASE_5_READINESS.md). That readiness assessment supports synthetic geometry first after documenting its contract; trustworthy counting remains blocked.

[Phase 5](docs/PHASE_5_TASK.md) now uses [accepted G3 geometry](docs/evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json), [labelled G3-L1](docs/evidence/phase_5/review_drafts/G3-L1/README.md) and the [qualitative geometry contract](docs/GEOMETRY_CONTRACT.md). A/B labels preserve all coordinates; the simple A perimeter is P1A→P1B→P1D→P1C. The new960×540 reference is explicit, not recovered screenshot dimensions, and still requires review per video. [05_geometry_replay.ipynb](notebooks/05_geometry_replay.ipynb) runs synthetic tests before CPU replay of retained ReID observations, without model inference. [Actual Phase5 review](docs/PHASE_5_REVIEW.md) distinguishes geometry diagnostics, bounded pixel evidence and experimental parameter sensitivity from vehicle counting. Suitable numerical defaults remain OPEN; Phase6 subsequently defines the conservative audit-gated counting contract described below. The eventual geometry setup page remains Phase11.

[Phase 6 Option A](docs/COUNTING_CONTRACT.md) now implements reviewed physical-passage counting in [06_counting_audit.ipynb](notebooks/06_counting_audit.ipynb). The [actual retained-evidence review](docs/PHASE_6_REVIEW.md) records 59/59 synthetic tests and CPU execution without model or geometry-state-machine reruns. It produces **18 accepted passage events** (16 motorcycle, 1 car, 1 truck), with 141 pending audit items and 7 rider/component candidates rejected. This is a bounded review-supported subtotal, not the complete traffic count. Machine outputs, reviews, resolved decisions, aggregate and visual evidence are retained separately. Bus/angkot and pickup taxonomy, suitable numerical settings, full physical-identity recovery and whole-video audit remain OPEN. Phase7 had not started when this baseline was completed; the authorized night experiment is described below.

The authorized [Phase 6 Option B comparison](docs/PHASE_6_OPTION_B_TASK.md) has now executed on retained TOR3-PAGI observations using [06b_identity_resolution_comparison.ipynb](notebooks/06b_identity_resolution_comparison.ipynb). [Final v1 evidence](docs/evidence/phase_6/20261013T104301_354775Z/summary.json) records **63/63 synthetic tests, one automatic accepted motorcycle passage and five pending vehicle candidates** within 13 selected IDs and six declared windows; episode-only ablation accepts none. Vehicle 1772 and rider 1774 produce one event from the motorcycle BC, with a rebuilt vehicle origin at 7716 and crossing 7721→7722. Duplicate 964/973 remains pending automatically because the frozen motion gate fails; ID1323 is car for this user-reviewed case but has unresolved identity, and later rider association cannot confirm the earlier 923 passage. The [separate reviewed overlay](docs/evidence/phase_6/20261013T104301_354775Z/reviewed/report.json) contains **four events: three manually confirmed passages and one preserved automatic event**, with duplicate 973 suppressed and car 1323 still pending. [Actual A/B review](docs/PHASE_6_OPTION_B_REVIEW.md) distinguishes these sources and preserves the historical 18-event A snapshot. These bounded results do not establish automated counting quality or a complete-video total. Phase 7 had not started when this comparison was completed; the authorized night experiment is described below.

Confirmed target: YOLO26M using the Ultralytics Python API → BoT-SORT with ReID-assisted association → track state/trajectory → per-video pixel geometry → valid crossing events → counts → aggregation/audit.

The camera remains at one recording position during each video, with possible small handheld shake. Geometry is independently configured per video. Product-category mapping, BC robustness, suitable numerical parameters, a final suitable vehicle-ReID configuration, and night/other-scene behavior remain OPEN. Raw model `person` includes riders and is not an accepted `pedestrian` mapping; bus/angkot interpretation is also OPEN. Published detector/tracker defaults were used as untuned experiment baselines, not accepted suitable product settings. Disabling ReID/GMC in the isolated tracking baseline does not remove ReID from the architecture or settle GMC need.

## Read first

1. [Agent rules](AGENTS.md).
2. [Development phases](CODEX_WORKFLOW.md).
3. [Project context](docs/PROJECT_CONTEXT.md), [product specification](docs/PRODUCT_SPEC.md), [model specification](docs/MODEL_SPEC.md), [counting logic](docs/COUNTING_LOGIC.md), and [architecture](docs/ARCHITECTURE.md).
4. [Test plan](docs/TEST_PLAN.md) and [evaluation rules](docs/EVALUATION.md).
5. [Decision register](docs/OPEN_DECISIONS.md), [preliminary configuration](docs/CONFIG_SCHEMA.md), and [conceptual interface contract](docs/API_CONTRACT.md).

## Execute the Phase 1 inspection

[Phase 1 — video inspection](docs/PHASE_1_TASK.md) is authorized. Open or import `notebooks/01_video_inspection.ipynb` into the [provided Kaggle notebook](https://www.kaggle.com/code/chrisbiran/new-traffic-counter/edit), with the dataset mounted at `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos`. Run through discovery, copy one actual discovered path into `VIDEO_PATH`, then restart the kernel and run all cells. Inspect the generated frames/temporal previews, enter evidence-based manual observations, and regenerate the report. Changing `VIDEO_PATH` selects another video without changing the inspection logic.

Native frames, previews, videos, and executed notebook outputs remain in the runtime artifact directory. Curated review sheets, reports, manifests, and frame hashes are retained under `docs/evidence/phase_1/`; original videos are excluded. The TOR3 review is applied only to the matching input SHA-256 and sampling, while other videos remain unknown until reviewed. No detector, tracker, ReID, crossing, counting, enhancement, stabilization, or multi-GPU processing is implemented by the Phase 1 notebook. Phase 2 is a separate detection capability.

Documentation is part of the project contract. Preserve the distinction between FACT, REQUIREMENT, ASSUMPTION, PROPOSAL, and EXPERIMENT RESULT. Do not report formal accuracy without appropriate ground-truth evidence.


## Execute Phase 5 geometry

From the checkout root, run `python notebooks/phase_5_synthetic_tests.py` before opening `notebooks/05_geometry_replay.ipynb` and choosing **Run All**. Geometry/replay uses Python standard library and the retained gzip; GPU and original video are not needed. Explicit experiment controls are not selected product defaults. Copy the full checkout to Kaggle and configure `REPO_ROOT`/paths if using Kaggle. Do not start counting from diagnostic totals.


## Execute Phase 6 counting audit

From the checkout root, run `python notebooks/phase_6_synthetic_tests.py`, then open `notebooks/06_counting_audit.ipynb` and choose **Run All**. The notebook has its own test guard before processing retained input. Standard-library counting needs CPU only; GPU, the original video and YOLO/tracker/ReID dependencies are not required. Kaggle can use the same checkout with explicit `REPO_ROOT`/input/output paths. To inspect the existing results without re-execution, read [PHASE_6_REVIEW.md](docs/PHASE_6_REVIEW.md) and the retained `audit_queue.jsonl.gz`/`review_queue.csv`. Resolve pending candidates with hash-bound evidence and review records; never edit aggregate totals directly.
## Phase 7 night experiment

The user has authorized TOR3-MALAM raw-versus-enhancement experiments and approved N1 for the initial geometry trial. Start with [Phase 7 task](docs/PHASE_7_TASK.md), [experiment protocol](docs/NIGHT_PREPROCESSING_EXPERIMENT.md), [screening notebook](notebooks/07_night_preprocessing.ipynb), [temporal notebook](notebooks/07b_night_temporal_comparison.ipynb), and [actual review/status](docs/PHASE_7_REVIEW.md). The scoped experiment completed: raw and gamma0.7 each processed9,590frames, while counting reviewed five declared windows. Both branches accept the same six motorcycle and one truck passages after explicit review, with one category conflict pending. Raw is retained as the next research baseline; gamma is not promoted to production. Machine/reviewed results, old A/B comparisons and night sources remain separate; no formal ground truth exists.

## Execute Phase 8 preparation

Use the source bundle or repository checkout in Kaggle, attach `chrisbiran/tgdi-traffic-videos`, and open [08_end_to_end_batch.ipynb](notebooks/08_end_to_end_batch.ipynb). The [private Kaggle preparation notebook](https://www.kaggle.com/code/chrisbiran/phase-8-tgdi-batch-preparation) contains the exact hash-bound source bundle. Keep `MODE = 'prepare'`, then **Run All**. This retains discovery, runtime inventory, manifest readiness and software guard reports under `/kaggle/working/phase_8_batch/preparation/`. It does not run detection or count traffic. The user has approved the [eight G3-T1 views](docs/evidence/phase_8/geometry_proposals/TGDI_eight_video_G3_T1_overview.png) for the initial trial. Select [the active research v2 manifest](docs/evidence/phase_8/config/batch_manifest_TGDI_G3_T1_v2.json) explicitly for `run_batch`; it binds each actual video/native frame and the user-confirmed unknown store metadata. Missing facts are retained null, with business_metadata_complete=false. Raw and frozen Bv1 controls remain fixed, with sequential CUDA0 for new inference.


Migrasi Traffic bertipe dan berversi: [release candidate dan bukti](docs/TRAFFIC_MODULARIZATION_RELEASE.md).
Facade: `traffic_location.traffic.application.pipeline.process_video`; API mapping
lama tetap tersedia melalui `traffic_location.traffic.pipeline.run`.
