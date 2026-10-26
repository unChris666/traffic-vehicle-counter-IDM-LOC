<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# T7SL annotated full-frame output — 24 Oktober 2026

## Why three videos were still running

Five measurements were reused. Weekend-siang and weekend-pagi were generating
new full-frame measurements on separate Tesla T4s, while weekend-sore waited in
the second queue. Live measured throughput was approximately5.6–6.5FPS, below
source28–30FPS; a five-minute recording therefore takes longer than five minutes.
No frame skipping is used. The existing model run is preserved to avoid losing
partially completed inference.

## Added rendering

`traffic/annotation.py` consumes saved decisions and fresh measurements without
calling detector/tracker/ReID/counting. `run_t7sl_job.py` now has a rendering stage
for future complete pipeline executions. The dedicated readable notebook
`notebooks/10b_t7sl_full_annotation.ipynb` performs CPU-only rendering from the
current completed producer, avoiding an unnecessary eight-video model rerun.

Notebook: https://www.kaggle.com/code/chrisbiran/t7sl-annotated-full-review
Producer: https://www.kaggle.com/code/chrisbiran/t7sl-traffic-counter-readable

The annotation notebook draft is published without GPU execution. The active
`tools/submit_t7sl_annotation_when_ready.py` watcher waits for terminal success,
verifies all eight full-video jobs and then submits the CPU render notebook.
If producer fails/is partial, annotation is BLOCKED rather than pretending to have
eight complete videos. The draft/queued state is not a successful render.

## What is displayed

- Native image, frame number, approximate source time, polygons and finite line
  with experimental margin.
- Raw ID and raw category on colored bbox labels with backgrounds; accepted
  passage ID/final category displayed only for matching activated episode evidence.
- Exact-frame supported rider+motorcycle display union; raw parent vehicle BC
  remains the counting anchor. Conflicting parent candidates are not arbitrarily merged.
- Category×direction running accepted pivot and separate measured/estimated totals.
- Accepted passage log between accepted table and final pending queue.
- Final pending reasons/IDs and invalid total; neither enters accepted counts.
- Explicit OFFLINE FINALIZED label because classifications can use later evidence.

No renderer decision creates or repairs an event. Label colors describe the raw
category; FINAL category/passages come from the saved event ledger. Positive
pedestrian is distinct from unknown person/rider. Unrelated raw classes are not
shown as countable units.

## Output in Kaggle

`/kaggle/working/results/t7sl_annotated_full_v1/` contains:

- `annotated/<VIDEO>.mp4`: one H264/yuv420p MP4 per full source;
- `annotated/<VIDEO>.json`: source hashes, encoded/redecoded frames and final panel;
- `annotation_manifest.json`: all-eight render status and frame total;
- `combined.json`, `combined.csv`, `jobs.json`: unchanged producer count outputs;
- `review.html`: index with video players.

Open the MP4 files in the notebook Output panel. They use all source frames,
constant output rate from reported source FPS, original-resolution source region
plus audit panel, and no audio. Original VFR timestamps are not reconstructed;
this timing limitation is recorded rather than claiming original PTS preservation.

## Verification actually performed

A96-frame preview encoded and fully redecoded96frames. A complete actual
T7SL-WEEKDAY-MALAM test encoded and fully redecoded **9,082frames**. Every input
frame pixel digest matched the retained measurement. Final panel reconciled with
all10 accepted events in that G1 test snapshot; native result and all inputs
remained unchanged. This is renderer validation on a saved G1 snapshot, not the
final G2 batch count or an accuracy claim. Four annotation tests cover final
pivot, activation chronology, immutable decisions and exact-frame parent links.

Receipts: `results/t7sl_modular/annotation_verification/`. Large test MP4 is kept
in the workspace, not committed as source. The eight-video Kaggle output is not
claimed complete until its own annotation manifest passes. Geometry and physical
counting quality remain experimental.
