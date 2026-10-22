# B v5 P0 — hasil penelitian, belum default

- [Review utama](../../docs/B_V5_P0_REVIEW.md) dan [kontrak](../../docs/B_V5_P0_CONTRACT.md).
- [Policy v2](config/policy.json), [readiness](review/readiness.json).
- [Replay v1](execution/pilot_p0_v1/batch_report.json):120 accepted/59 pending.
- [Replay v2](execution/pilot_p0_v2/batch_report.json):117 accepted/65 pending.
- [Matriks seluruh68 pending +16 cancellation +10 discovery](review/pilot_v2_qc_matrix/comparison.json).
- [Ringkasan sumber/pasangan crossing](review/pilot_v2_summary.json).
- [Verifikasi dan bukti regresi](verification/).
- [Eksperimen konfigurasi model yang terpisah](../../docs/MODEL_CONFIGURATION_EXPERIMENT_REVIEW.md).

Semua subtotal merupakan hasil operasional, bukan traffic ground truth.
P0 belum lulus acceptance: raw4281 masih menduplikasi4251; konflik high-IoU
menahan beberapa kendaraan nyata. Empirical P0 gate bukan PASS walaupun tes
software dan replay lengkap lulus. Rekomendasi QC baru tidak dimasukkan sebagai
prediksi machine. Tidak ada baseline lama ditimpa atau model rerun dalam P0.

Reproduksi pilot setelah source/cache donor tersedia:

```bash
PYTHONPATH=notebooks python notebooks/phase_8_b_v5_batch.py \
  --repo-root . \
  --source-run-root /path/to/verified/phase8/donor/run \
  --source-video-root /path/to/tgdi/videos \
  --policy-path results/b_v5/config/policy.json \
  --output-root /tmp/p0-replay
```

Gunakan Python dengan OpenCV dan dependency inspeksi yang tersedia. Folder
output baru wajib berbeda dari source/baseline. Model experiment memerlukan
Kaggle GPU dan input yang dinyatakan notebook09b, bukan command replay ini.
