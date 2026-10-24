# T7SL fresh modular batch

[Review, konfigurasi dan batas klaim](../../docs/T7SL_FRESH_BATCH_REVIEW.md).

Notebook baru: https://www.kaggle.com/code/chrisbiran/t7sl-fresh-modular-traffic-batch

`inspection/` menyimpan inventory aktual71.380frame dan sampel visual.
`config/` menyimpan policy, request, geometri kandidat dan experiment lock.
`kaggle_packet/` adalah submission V1 frozen, termasuk bundle SHA; jangan menimpa
snapshot ini jika membuat versi berikutnya. `verification/` menyimpan tes lokal
dan receipt submission. Belum ada total T7SL terverifikasi pada status RUNNING.

Buka `combined.json` dan `combined.csv` di output notebook setelah selesai;
per-video result dan event ledger tersedia untuk rekonsiliasi.
