# Bukti irisan modularisasi dua engine

23 Oktober 2026. [Review dan batas klaim](../../docs/ENGINE_MODULARIZATION_REVIEW.md).
Goldens merujuk hasil historis yang tidak diubah; request menyimpan path aktual
lingkungan eksekusi. Jika direlokasi, ubah path referensi saja, pertahankan SHA
dan profil, lalu verifikasi ulang. Jangan membuat cache pengganti berisi data rekaan.

## Input dan artefak

- `20261023/goldens/baselines.json`: SHA bytes dan seluruh field native per branch.
- `20261023/goldens/*_policy.json`: effective policy acuan, bukan threshold baru.
- `20261023/requests/`: request nyata untuk replay, snapshot dan smoke CPU.
- `source_extraction.json` / `location_source_extraction.json`: asal kode, SHA dan
  transformasi. Reproduksi dengan `tools/extract_traffic_kernel.py` dan
  `tools/extract_location_kernel.py`; sumber notebook tidak dimodifikasi.
- `20261023/verification/`: receipt dan log tes yang benar-benar dijalankan.

Ringkasan aktual: **51 tes unik PASS** pada runtime yang sesuai; enam replay
Traffic penuh (tiga/branch) setara seluruh field; Location selection/capacity
dan Recount R1/R2 masing-masing stabil tiga kali. Fresh CPU32 frame stabil
tiga proses, ditambah satu smoke orchestration. Lihat
[summary.json](20261023/verification/summary.json),
[machine](20261023/verification/traffic_machine.json),
[review-assisted](20261023/verification/traffic_review_assisted.json),
[Location](20261023/verification/location_recount.json) dan
[fresh CPU](20261023/verification/fresh_cpu.json).

Video, model weights dan cache measurement lengkap disimpan di
`/workspace/scratch/modularization`, **tidak ditambahkan ke GitHub**.
Download sumber yang sama bila cache lokal hilang:

```bash
/workspace/.venvs/kaggle-cli/bin/kaggle kernels output \
  chrisbiran/phase-8-tgdi-full-video-research \
  -p /workspace/scratch/modularization/input \
  --file-pattern 'weekday_siang/track_records.jsonl.gz' -q
/workspace/.venvs/kaggle-cli/bin/kaggle kernels output \
  chrisbiran/phase-8-tgdi-full-video-research \
  -p /workspace/scratch/modularization/input \
  --file-pattern 'weekday_siang/counting/relations.json.gz' -q
```

Request mengikat SHA cache serta video/geometry/run/dimensions. File dari kernel
lain atau versi baru akan ditolak jika hash tidak sama. Asset resmi berasal dari
rilis Ultralytics `v8.4.0` di `github.com/ultralytics/assets`; byte SHA yang
digunakan tercantum dalam `requests/fresh_cpu.json`. Smoke membutuhkan video
TGDI-WEEKDAY-SIANG dari dataset resmi `chrisbiran/tgdi-traffic-videos`.

## Menjalankan boundary

Package memerlukan Python≥3.12. Dependensi geometri/inference sengaja tidak
dipaksa menjadi satu environment; gunakan runtime yang tercatat. Untuk validasi
schema, environment tes menggunakan jsonschema4.26.0. Package dapat diinstal
melalui `python -m pip install '.[validation]'`, atau source melalui `PYTHONPATH=src`.
Instalasi package saja tidak memasang CUDA/GDAL/model assets.

```bash
PYTHONPATH=src python -B -m traffic_location traffic \
  --request results/engine_modularization/20261023/requests/machine.json \
  --output /tmp/traffic-machine-new

PYTHONPATH=src python -B -m traffic_location reopen \
  --output /tmp/traffic-machine-new

PYTHONPATH=src /usr/bin/python3 -B -m traffic_location location-selection \
  --request results/engine_modularization/20261023/requests/location_selection.json \
  --output /tmp/location-selection-new

PYTHONPATH=src /workspace/.venvs/location-intelligent-sources/bin/python -B \
  -m traffic_location location-recount \
  --request results/engine_modularization/20261023/requests/location_recount_r1.json \
  --output /tmp/location-recount-new
```

Pilih direktori output baru; revisi lama immutable. Reopen memverifikasi manifest
dan tidak menghitung ulang. Refresh sumber merupakan pekerjaan baru, bukan reopen.

Uji ulang kesetaraan penuh tanpa inference:

```bash
PYTHONPATH=src python -B tools/verify_traffic_modular_parity.py \
  --branch machine --repetitions 3 --output /tmp/parity-machine-new
PYTHONPATH=src python -B tools/verify_traffic_modular_parity.py \
  --branch review_assisted --repetitions 3 --output /tmp/parity-reviewed-new
```

Uji fresh yang terpisah, bukan perintah replay:

```bash
PYTHONPATH=src python -B -m traffic_location fresh-inference \
  --request results/engine_modularization/20261023/requests/fresh_cpu.json \
  --python /workspace/.venvs/traffic-detection-validation/bin/python \
  --output /tmp/fresh-cpu-new
```

Ini prefix32 frame dengan ReID aktif, belum counting baru. Tidak ada fallback
CPU untuk request CUDA, atau fallback encoder/model otomatis. Per video/job
dibuat proses worker baru. Perbandingan measured/estimated dan counting tidak
dapat disimpulkan dari keluaran measurement smoke ini saja.
