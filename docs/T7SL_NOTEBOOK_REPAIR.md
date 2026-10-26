<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# T7SL notebook repair — 24 Oktober 2026

## Confirmed failure and correction

V1 was real executable source inside a compressed bundle, but poor notebook
presentation and redirected subprocess logs made its work invisible. Cancellation
of user-linked session361635064 was acknowledged by the official Kaggle API.
No eight-video success was established.

Retained outputs reveal five complete GPU measurement files. Counting failed
with `Cross-frame role changes require a separate physical episode`, including
frame446/track164 (weekday-malam), frame603/track108 (weekday-pagi), and
frame388/track91 (weekday-siang). The fresh adapter assigned `track:<id>` to both
vehicle and person. The existing notebook adapter uses separate person context.
The repair restores `person-track:<id>`/`unreviewed-person` versus vehicle
`track:<id>`/`unreviewed-vehicle`; raw IDs, classes, bbox and measured BC stay intact.
The counting guard remains enabled. This is an adapter bug fix, not approval of
the separate architectural migration audit.

Three actual full-video cached regressions passed after repair:9082,9015 and
9110frames. See `results/t7sl_modular/repair_v2/full_cache_regression.json`.
These results use G1 for failure reproduction, not the new G2 experiment or a
full eight-video result. Fourteen targeted unit tests passed, including a synthetic
same-raw-ID vehicle→person case.

## Inspectable implementation

`notebooks/10_t7sl_readable_resume.ipynb` has83cells/42code cells. Actual module
source is visible using `%%writefile`; no base64 archive is used. The final cell
calls the source displayed above it. Configuration, data checks, G2 preview,
model assets, inference, identity/counting and pivot exports are visible.

Execution notebook: https://www.kaggle.com/code/chrisbiran/t7sl-traffic-counter-readable
Original latest editor: https://www.kaggle.com/code/chrisbiran/t7sl-fresh-modular-traffic-batch/edit
The `/edit/run/361635064` URL is an immutable historical run; it still shows V1.
Original latest source was updated using QUICK_SAVE without another GPU run.
Use the execution notebook to monitor the active run; do not start a duplicate.

## Resource controls and honest state

Five complete measurements are retained in the private dataset
`chrisbiran/t7sl-fresh-measurement-cache-v1`; original source license was unknown
and is preserved as unknown. No source video/model weights are uploaded there.
The canceled kernel cannot be attached through kernel_sources; that integration
was rejected by Kaggle. The resumed notebook instead explicitly attaches the
private cache dataset. Kaggle may expand gzip, so both `.result.json` and
`.result.json.gz` cache filenames are supported. A missing cache blocks inference.

Cached sources are checked against video SHA, frame count, model asset SHA,
seed, precision, preprocessing and tracker configuration. Only three missing
videos require new inference. Console relays stages/errors immediately, prints
frame128 progress and throughput, and emits20second heartbeats. Smoke has180second
and full jobs1800second watchdogs. First queue failure stops further jobs and
signals the other queue; this is not an unconditional retry loop.

New execution was submitted with T4x2 requested. Runtime/output verification is
still required; submission, a quick-save status COMPLETE or local regression
success must not be reported as an eight-video PASS. Exact publication/submission
receipts are under `results/t7sl_modular/repair_v2/`.

Kaggle cache mounting also exposed an I/O defect: expanded JSON was copied to a
`.gz` filename without compression. V4 correctly stopped both queues on that
error, before missing-video inference. The corrected job explicitly serializes
validated cache data using the gzip writer; a local expanded-JSON roundtrip test
confirmed the gzip header and unchanged semantic records digest. Both compressed
and expanded mounted cache names are supported. The deprecated half warning is
kept in artifact logs but suppressed from the live relay so progress stays readable.
