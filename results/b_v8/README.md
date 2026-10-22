# P1 / B v8 — hasil pilot reviewed

**Gate: PASS pada pilot development TGDI-WEEKDAY-SIANG reviewed.** Ini bukan
kelulusan sistem otomatis/produksi. Baseline mesin B v7 tetap terpisah.

- [Laporan engineering](../../docs/B_V8_P1_REVIEW.md) dan [kontrak](../../docs/B_V8_P1_CONTRACT.md).
- [Run terpilih](selected_run.json): `execution/pilot_p1_reviewed_v3`, policy/overlay `v5`.
- [Gate](review/p1_gate.json), [QC sumber](review/full_pilot_v3_qc.json), [verifikasi akhir](verification/final_verification.json).
- [Perbandingan event](comparison/pilot_p1_reviewed_v3/comparison.json), [delta CSV](comparison/pilot_p1_reviewed_v3/event_deltas.csv).
- [24 disposisi pending](comparison/pilot_p1_reviewed_v3/pending_dispositions.csv), [mapping 17 ID tampilan](review/display_id_mappings.csv).
- [Tes302](verification/tests.json), [inventaris pending](pending_review/pending_inventory.json), [retensi](retention_manifest.json).
- [Notebook parameterized](../../notebooks/09e_p1_pending_recovery.ipynb), default replay tidak aktif.

Hasil terpilih:74 accepted objek (73 kendaraan+1 pedestrian),67 terukur dan7
estimasi (4 timeout+3 line-margin),1 pending,83 invalid. Dari24 pending lama,
22 selesai komponen/+0,1 pedestrian diterima,1 tetap pending (3185 pada5579).
Satu motorcycle1049→1123 dipulihkan melalui bukti reviewed; merah4843 dikoreksi
sumbernya, bukan penambahan count baru. Output mesin dan reviewed tidak dijumlahkan.

Semua tiga replay penuh dan revisi development disimpan. `v1`/`v2` bukan hasil
terpilih. Defaults modul CLI lama menunjuk data development pertama: selalu
berikan path policy/overlay terpilih secara eksplisit seperti di bawah.

## Reproduksi dari cache yang sama

Jalankan dari root repo setelah menyediakan kembali source/cache dengan hash
pada `execution/pilot_p1_reviewed_v3/baseline_reference.json` dan guarded inputs.
Path `/tmp` adalah lokasi eksekusi sesi ini, bukan jaminan dataset tersedia
pada mesin lain. Di Kaggle, sesuaikan root video/cache yang benar-benar tersedia.
Gunakan run-id baru agar bukti lama tidak ditimpa.

```bash
/workspace/.venvs/traffic-inspection/bin/python notebooks/phase_8_b_v8_batch.py \
  --repo-root . \
  --source-run-root /tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z \
  --source-video-root /tmp/qc-source \
  --overlay-path results/b_v8/config/review_overlay_v5.json \
  --policy-path results/b_v8/config/policy_v5.json \
  --output-root results/b_v8/execution --run-id pilot_p1_reviewed_reproduction
```

Replay asli dilakukan dengan run-id `pilot_p1_reviewed_v3`. Tidak ada inference
model baru. Entry notebook setelah eksekusi hanya diubah dua path konfigurasi
agar menunjuk kandidat terpilih; [receipt](verification/notebook_selected_configuration_receipt.json)
mempertahankan source snapshot asli. Notebook belum dieksekusi tersendiri.

Paket berisi keputusan/event, bukti gambar terbatas dan audit; tidak menyertakan
video asli atau MP4 anotasi baru. Tidak dilakukan upload/commit GitHub pada tugas ini.
