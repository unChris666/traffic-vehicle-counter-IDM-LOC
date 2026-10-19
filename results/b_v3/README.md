# Phase 8 B v3 — hasil revisi identitas dan passage

**EXPERIMENT RESULT — replay lokal selesai:** delapan video TGDI, **72.590 frame**, **3.500 passage operasional**: 895 crossing terukur dan 2.605 inferensi, termasuk 2.454 timeout. Subtotal kendaraan 3.500; pedestrian 0. Nol pedestrian tidak membuktikan ketiadaan pedestrian: role `person` belum otomatis terpisah dari rider. Hasil belum merupakan hitungan fisik yang sudah diaudit.

**Kaggle version 2 COMPLETE:** delapan video telah dirender dan seluruh 72.590 frame output dibaca ulang. Ledger delapan video persis sama byte demi byte dengan replay lokal. [Bukti perbandingan](verification/actual_kaggle_local_comparison.json), [manifest delapan MP4](delivery_manifest.json), dan [retensi eksekusi aktual](kaggle_execution/v2/retention_manifest.json) tersedia. **Delapan video sudah tersedia di [GitHub Releases](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/tag/phase8-b-v3-tgdi-review-v1)**, tetap dapat diakses setelah sesi Kaggle berakhir. [Daftar tautan per video](VIDEOS.md) dan [verifikasi publikasi](publication/final_verification.json) mengikat checksum serta sumber eksekusinya. Versi 1 berhenti sebelum tes/counting karena root snapshot tertimpa sel parameter; kegagalan dan perbaikannya disimpan. Detector, tracker, dan ReID tidak dijalankan ulang.

## Mulai review

- **[Buka delapan video anotasi terbaru](VIDEOS.md)**. Rilis B v2 tetap tersimpan sebagai pembanding.

- [Enam kelompok pending dan keputusan yang dibutuhkan](PENDING_DECISIONS.md).
- [Kasus dan preview anotasi aktual](review/annotated_previews/preview_proof.json), termasuk [motorcycle 2473 + rider2471](review/annotated_previews/TGDI-WEEKDAY-PAGI-B-V3-frame-004241.png) dan [episode motorcycle4149](review/annotated_previews/TGDI-WEEKDAY-SIANG-B-V3-frame-007611.png).
- [Kontrak revisi](../../docs/PHASE_8_REVISION_CONTRACT.md) dan [objektif Phase 9](../../docs/PHASE_9_TASK.md).
- [Notebook08c](../../notebooks/08c_reviewed_identity_replay.ipynb), [keputusan review terbatas](input/review_decisions.json), dan [policy efektif](config/policy.json).

Ada **2.890 kunci pending unik**: 2.427 unknown-person, 462 vehicle, dan 1 pedestrian dengan role positif. Ini bukan 2.890 kendaraan fisik. Queue person-role seluruh episode berisi 6.099 kunci dan tidak ditambahkan lagi ke subtotal pending.

## Hasil per video

| Video | Operasional | Terukur | Inferensi |
|---|---:|---:|---:|
| TGDI-WEEKDAY-PAGI |485|137|348|
| TGDI-WEEKDAY-SIANG |584|121|463|
| TGDI-WEEKDAY-SORE |442|115|327|
| TGDI-WEEKDAY-MALAM |371|82|289|
| TGDI-WEEKEND-PAGI |412|121|291|
| TGDI-WEEKEND-SIANG |448|136|312|
| TGDI-WEEKEND-SORE |469|129|340|
| TGDI-WEEKEND-MALAM |289|54|235|
| **Total** |**3.500**|**895**|**2.605**|

Baseline B v2 tetap tersimpan. Delta 3.717→3.500 dijelaskan oleh −208 timeout passage ulang yang ditahan, −10 event identitas belum cukup, +1 estimasi motorcycle4149 yang kini terpisah. Ini bukan klaim peningkatan akurasi. [Audit delta aktual](verification/final_delta_audit.json) mempertahankan rinciannya.

## Bukti dan reproduksi

- [Snapshot final lokal, gzip byte-exact](execution/final_20261019T045405_106031Z/retained_bytes_manifest.json): batch, ledger/per-video, pending, perbandingan, dan sembilan source snapshot. Dekompresi satu lapis sesuai nama artefak; source snapshot asli sudah `.gz`, sehingga retensi luarnya `.gz.gz`.
- [151 tes pipeline aktual](verification/pipeline_software_validation.json), [52 tes packaging/publikasi](verification/packaging_software_validation.json), [65 pemeriksaan paket v2](verification/submitted_packet_v2/verification.json), dan [preflight paket aktual beserta sel parameter](verification/actual_packet_v2_preflight.json).
- [Paket Kaggle v2 persis yang disubmit](verification/submitted_packet_v2/), [status submission](verification/kaggle_v2_submission.json), serta [kegagalan v1](verification/kaggle_v1_failure/failure.json). Status submission bukan bukti penyelesaian.
- [B v2 baseline](../b_v2/README.md) dan video lamanya tetap utuh. Anotasi B v2 tidak boleh diberi label B v3.

Phase 9 **dapat dimulai untuk audit snapshot**; belum berarti siap produksi. Prioritasnya accepted timeout, identitas/duplikasi, pedestrian/rider, kategori dan crossing, serta passage yang terlewat. Kontrol pedestrian measured-only, taxonomyBUS, dan timeout passage berikutnya masih memerlukan keputusan; detailnya ada pada tabel pending. Tersisa lima fase termasuk 9 sampai 13, atau empat setelah 9 selesai.

Tes Kaggle aktual: **236 lulus**. Job publikasi GitHub selesai sukses; delapan MP4 berjumlah 896.297.721 byte dan seluruh 11 aset rilis mempunyai digest server yang cocok. MP4 dipindahkan byte-exact tanpa encoding/counting baru saat publikasi. [Receipt](publication/publication_receipt.json) juga mencatat probe izin unggah yang berhasil sebelum unduhan massal dan pembersihan draft probe.
