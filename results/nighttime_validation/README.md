# Dataset malam resmi — inspeksi dan Review-Filter

**PARTIAL:** dataset/inspeksi dan tool review siap; smoke counting belum dijalankan.

- [Buka/unduh Review-Filter standalone](../review-filter.html). Tidak memerlukan file JS tambahan.
- [Laporan inspeksi](inspection_report.md), [inventory CSV Kaggle](kaggle_execution/nighttime_input_inspection/inventory.csv), [observasi visual](visual_review.json).
- [Readiness](readiness.json) dan [rencana smoke](smoke_plan.json).
- [Review engineering/integrasi](../../docs/NIGHTTIME_VALIDATION_REVIEW.md).
- [Notebook Kaggle aktual](https://www.kaggle.com/code/chrisbiran/b-v8-nighttime-input-inspection), version1 CPU, COMPLETE.
- [Source notebook09f](../../notebooks/09f_nighttime_validation.ipynb) melanjutkan B v8; notebook09e dan baseline lama tetap utuh.
- [Mount/source verification](verification/kaggle_mount_verification.json), [tes software](software_tests.log), [uji browser](browser_validation/browser_test.json), [pixel parity](browser_validation/preview_backend_parity.json), [retensi baseline](verification/baseline_retention.json).
- [Perintah aktual](verification/commands.json), [retensi paket](retention_manifest.json).

Dataset: `chrisbiran/video-traffic-malam`. Actual mount Kaggle:
`/kaggle/input/datasets/chrisbiran/video-traffic-malam`. Semua10 video berhasil
didecode:89.199 frame, tiga resolusi, semuaH.264. Video asli tidak disertakan
di repo atau diubah. Sampling tidak membuktikan seluruh passage sudah diaudit.

## Langkah review berikutnya

1. Unduh `review-filter.html`, buka di browser, lalu pilih video asli dari
   perangkat (misalnya file F1YV-WEEKDAY-MALAM yang diunduh dari dataset resmi).
   Halaman tidak mengunggah video ke server.
2. Bandingkan raw/filtered pada beberapa posisi; pilih kondisi hanya jika
   diketahui. Setelan per video dan profil kondisi tersimpan terpisah.
3. Klik **Ekspor konfigurasi JSON**. Semua default adalah raw, belum ada recipe
   produksi yang dipilih. Config browser test bukan pilihan untuk inference.
4. Review geometri native/arah source pertama. Setelah config dan geometri
   terikat source, jalur B v8 malam perlu divalidasi sebelum smoke model.

Source malam baru tidak boleh memakai label rider/identity overlay Siang.
Batch B v8 sekarang sengaja dibatasi cache pilot TGDI; helper full-video lama
masihB v1. Tidak ada pengaman yang dilepas untuk melewati pembatasan tersebut.

Opsional, bila browser memerlukan localhost, jalankan dari root repo:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory results
```

Lalu buka `http://127.0.0.1:8765/review-filter.html` pada mesin yang menjalankan
server tersebut. HTML juga dapat dibuka langsung sebagai file.

## Reproduksi inspeksi tanpa inference

Setelah dataset benar-benar tersedia, gunakan output baru agar bukti lama tidak tertimpa:

```bash
/workspace/.venvs/traffic-inspection/bin/python notebooks/nighttime_input_inspection.py \
  --dataset-root /tmp/official-night-dataset \
  --output /tmp/night-inspection-new-run \
  --execution-context codex_downloaded_dataset
```

`/tmp/official-night-dataset` adalah lokasi download sesi ini; jangan diasumsikan
ada pada sesi baru. Notebook09f menemukan actual Kaggle mount sebelum membaca.
Tidak ada GPU/model execution pada pemeriksaan ini. Area Coverage dan PPAC
berada di luar cakupan dan tidak dimodifikasi.
