# B v6 — hasil kebijakan baru, pilot TGDI-WEEKDAY-SIANG

**P0 BLOCKED:** duplikasi fisik residual 1049→1123. Lihat
[review keputusan](../../docs/B_V6_USER_POLICY_REVIEW.md) dan
[QC independen](review/INDEPENDENT_QC_REVIEW.md). Profil penelitian; bukan
default produksi. Detector/tracker/ReID/enhancement tidak dijalankan ulang.

- [Notebook 09c](../../notebooks/09c_user_policy_replay.ipynb)
- [Konfigurasi](config/policy.json) dan [kontrak](../../docs/B_V6_USER_POLICY_CONTRACT.md)
- [Run final 9.128 frame](execution/pilot_v6_machine_final/batch_report.json)
- [Accepted events](execution/pilot_v6_machine_final/weekday_siang/audit_exports/accepted_events.csv)
- [Invalid/+0](execution/pilot_v6_machine_final/weekday_siang/audit_exports/invalid_passages.csv)
- [Pending](execution/pilot_v6_machine_final/weekday_siang/audit_exports/pending_passages.csv)
- [Pivot kategori×arah](execution/pilot_v6_machine_final/weekday_siang/audit_exports/summary_pivot.csv)
- [Kelompok pending](review/pending_group_summary.csv) dan [kasus/frame](review/pending_cases_grouped.csv)
- [Bukti motor 1049→1123](review/independent_inferred_1049_1123_continuity.jpg)
- [Gate P0](review/p0_gate.json) dan [fixture yang belum lulus](review/regression_fixture_1049_1123.json)
- [Video anotasi lokal](videos/TGDI-WEEKDAY-SIANG-b-v6-annotated.mp4)
- [Preview akhir](verification/preview/frame-9127.jpg) dan [preview 4251/4281](verification/preview/frame-7369.jpg)

Hasil machine: 74 accepted =66 measured +8 estimasi; 24 pending; 84 scope
kandidat/passage invalid; 17 not eligible. Invalid bukan jumlah kendaraan
fisik atau nilai traffic nol. 4251/4281 menjadi 2→0, menghilangkan duplikasi
sekaligus mengecualikan satu motor. Semua 68+16+10 inventory QC lama ditelusuri;
audit tambahan tetap menemukan dua event untuk satu motor merah1049/1123.

Video H264 berukuran sekitar144MB, 1280×1450, 9.128 frame ditulis dan didekode
ulang. Native source640×480 dipertahankan, audio tidak disertakan. Pivot final
tidak memuat invalid/pending/cancelled. Video tersimpan lokal dan belum
dipublikasikan ke GitHub; bila dipublikasikan, gunakan aset Release karena
ukurannya melebihi batas file Git biasa. Video mentah tidak dimasukkan Git.

Run `pilot_v6_machine` adalah eksekusi awal; `pilot_v6_machine_final` memperbaiki
nama file audit standalone. Counting JSON kedua run identik byte demi byte.
Render awal tetap sah untuk final melalui
[binding SHA](verification/final_render_binding.json). Snapshot final cocok
dengan seluruh executable yang dikirim. [Pemeriksaan panel/ekspor](verification/real_export_panel_check.json)
memeriksa seluruh9.128 checkpoint, raw ID, rider/parent dan BC. Batas metadata
waktu invalid offline dijelaskan di review; frame kandidat bukan bukti waktu
ketersediaan keputusan final.

81 tes B v6 dan65 regresi B v5 lulus; log ada di [verification](verification/).
Ini verifikasi software dan audit sumber terbatas, bukan benchmark ground truth.
Manifest `retention_manifest.json` mengikat artefak, code dan dokumen baru;
manifest lama tidak diubah.

Untuk reproduksi lokal dengan donor dan video yang sama:

```bash
PYTHONPATH=notebooks /workspace/.venvs/traffic-inspection/bin/python \
  notebooks/phase_8_b_v6_batch.py --repo-root . \
  --source-run-root /tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z \
  --source-video-root /tmp/qc-source \
  --output-root results/b_v6/execution --run-id NAMA_RUN_BARU
```

Notebook menyiapkan ekspor/render setelah replay. Input Kaggle donor harus
ditentukan dari mount sebenarnya; placeholder tidak boleh dianggap dataset ada.
Langkah berikutnya adalah eksperimen handoff berbasis gerak dan regresi negatif
kendaraan berbeda, sebelum menetapkan P0 kembali. Jangan tuning model untuk
menutupi masalah timer/identitas ini.
