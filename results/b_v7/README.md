# B v7 — hasil investigasi handoff P0

**Replay selesai; P0 keseluruhan BLOCKED.** Pada TGDI-WEEKDAY-SIANG, pasangan
1049/1123 yang merupakan satu motor pada review sumber tidak lagi menghasilkan
dua accepted. Keduanya menjadi invalid/+0: satu passage fisik belum terhitung.
QC menemukan blocker terpisah4843, dengan origin motor biru dan destination
motor merah setelah occlusion, yang tetap accepted inferred.

| Output operasional | B v6 | B v7 |
|---|---:|---:|
| Accepted |74|72|
| Measured |66|66|
| Estimated timeout |5|4|
| Estimated line-margin |3|2|
| Pending |24|24|
| Invalid candidate scopes |84|86|

Ini hasil software, bukan ground truth. Pending dan invalid tidak dijumlahkan
sebagai kendaraan fisik. Seluruh9.128 frame diproses dari cache yang sama;
model/tracker/ReID/enhancement tidak dijalankan ulang. Runtime cache187,76detik.

- [Review engineering,5 Whys,MECE,Pareto dan SWQOT](../../docs/B_V7_HANDOFF_REVIEW.md).
- [Kontrak dan kontrol eksperimen](../../docs/B_V7_HANDOFF_CONTRACT.md).
- [Keputusan gate](review/p0_gate.json) dan [QC independen](review/INDEPENDENT_QC_REVIEW.md).
- [Perbandingan lengkap](comparison/full_pilot_v1/comparison.json) serta
  [CSV dua event yang dikeluarkan](comparison/full_pilot_v1/event_deltas.csv).
- [17 perubahan ID tampilan](review/display_id_mappings.csv), tanpa perubahan
  passage sumber. Gunakan versi,rawID,frame dan witness saat membandingkan.
- [Bukti blocker4843](review/independent_4843_identity_review.json) dan
  [gambar temporal](review/inferred_detail_4843.jpg).
- [Fixture aktual1049/1123](fixtures/1049_1123_v1/fixture_manifest.json),
  [hasil fixture B v7](verification/fixture_comparison.json),
  [hasil penuh](execution/pilot_v7_machine_final/weekday_siang/counting_result.json.gz)
  dan [batch report](execution/pilot_v7_machine_final/batch_report.json).
- [211 tes software](verification/tests.json),
  [verifikasi akhir](verification/final_checks.json), dan
  [rekonsiliasi inventory68+16+10](review/legacy_inventory_comparison.json).

Hanya dua event target yang dikeluarkan;72 event lainnya mempertahankan isi
counting,24 pending dan seluruh source assignments/component links tetap sama.
Tidak dibuat annotated video baru atau inference baru pada tugas ini.

Kode baru ada pada `notebooks/phase_8_b_v7_handoff.py`,
`phase_8_b_v7_counting.py`, `phase_8_b_v7_batch.py`, pengujian terkait,
`phase_9_v7_compare.py`, dan
[notebook09d](../../notebooks/09d_motion_handoff_replay.ipynb).
Snapshot executable yang benar-benar dipakai berada di
`execution/pilot_v7_machine_final/source_snapshot/`. Cell ID notebook
dilengkapi setelah eksekusi CLI; source cell tidak berubah, snapshot asli
dipertahankan, dan perbedaan metadata terikat pada
[receipt](verification/notebook_metadata_correction.json).

Untuk mereproduksi di workspace dengan input donor/video yang identik:

```bash
/workspace/.venvs/traffic-inspection/bin/python notebooks/phase_8_b_v7_batch.py \
  --repo-root . \
  --source-run-root /tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z \
  --source-video-root /tmp/qc-source \
  --output-root results/b_v7/execution \
  --run-id pilot_v7_machine_reproduction_NEW
```

Jalankan dari root repository; nama run harus baru. Policy yang dibekukan
tersimpan pada `config/policy.json`. Di Kaggle, gunakan09d dan pilih direktori
donor/source aktual. Pengulangan menghitung ulang policy dari cache, bukan
model inference. Replay penuh dalam laporan ini dijalankan sekali; fixture
diulang untuk memeriksa determinisme. Tidak diperlukan pengulangan untuk
membaca hasil yang sudah tersedia.

Verifikasi retensi dan struktur notebook:

```bash
/workspace/.venvs/traffic-inspection/bin/python results/b_v7/verification/verify_delivery.py
```

Branch saat investigasi `work`, HEAD `806ae761998e487265f3a032d616a59af56bb9a7`.
Seluruh3.936 file historis pada snapshot sebelum pekerjaan tetap identik.
Tidak ada promosi B v7 menjadi baseline produksi, commit/push baru, atau
publikasi video sumber privat dalam tugas ini.
