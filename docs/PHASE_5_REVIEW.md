<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Phase 5 — review geometri dan replay TOR3-PAGI

**EXPERIMENT RESULT — gate software:** notebook [05_geometry_replay.ipynb](../notebooks/05_geometry_replay.ipynb) benar-benar dieksekusi di Codex cloud CPU. **40/40 tes sintetis PASS**, 0 fail/error/skip, sebelum enam konfigurasi replay. [Audit independen](evidence/phase_5/20261011T161440_100155Z_2e39a11c/replay_audit.json) mencatat **25 PASS, 0 FAIL** terhadap artefak tersimpan, tanpa mengulang pipeline. Seluruh 877 baris transisi antar konfigurasi ditelusuri; baris ini bukan 877 kendaraan.

**Keputusan:** baseline geometri dan semantik software siap untuk review/eksperimen lanjutan. **Default numerik yang layak belum dikunci.** Counting Phase 6 belum dimulai; physical deduplication, rider/kategori, eligibility dan genuine return policy masih membutuhkan keputusan. Tidak ada ground truth atau klaim accuracy/precision/recall/F1/MAPE.

## Geometri dan persetujuan

[Feedback G3 001](evidence/phase_5/feedback/G3_review_001.json) menyimpan pertanyaan dan jawaban; [reafirmasi 002](evidence/phase_5/feedback/G3_review_002.json) mengulang titik yang sama. User menyetujui G3/reference dan B; aturan awal diterima secara kontekstual karena pertanyaannya secara eksplisit memuat aturan tersebut. Tidak ada angka yang digeser. [G3-L1](evidence/phase_5/review_drafts/G3-L1/README.md) memperjelas label dan lulus lima pemeriksaan anotasi/source/browser; ini terpisah dari tes crossing.

| Titik A | Unit template960×540 |
|---|---|
| P1A | `(4.5,516.5)` |
| P1B | `(4.5,348.2)` |
| P1C | `(936.6,305.8)` |
| P1D | `(557.5,165.3)` |

Keliling sederhana **P1A→P1B→P1D→P1C→P1A** menjaga empat titik; daftar label tidak mengharuskan perimeter ABCD yang menyilang. Garis tetap `(4.5,516.5)`→`(936.4,305.4)`; B berhenti X875, tanpa memperpendek garis. P2 tetap berbeda sedikit dari P1C. Normalisasi `u=x/960,v=y/540` dipetakan ke native1280×720 untuk video ini. Canvas baru tidak memulihkan ukuran screenshot terdahulu, dan tidak menjamin template reliable pada semua video.

[Konfigurasi diterima](evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json) dan [GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md) menetapkan raw detection-linked emitted-track BC, finite segment, batas polygon netral, touch-only tidak cukup, endpoint/gap ambigu, dan prediksi tidak mengesahkan passage. Polygon membership tidak disamakan dengan tanda garis. A→B mendekati kamera, B→A menjauhi kamera adalah metadata TOR3-PAGI.

## Implementasi dan tes yang benar-benar dijalankan

Helper [phase_5_geometry_helpers.py](../notebooks/phase_5_geometry_helpers.py) merupakan prototype notebook standard library, belum refactor produksi `src/`. [Suite independen](../notebooks/phase_5_synthetic_tests.py) menguji diagonal dua arah, finite extension/endpoint, kontak/return dan kontak diapit opposite signs, initial presence, incomplete arrival, batas/area luar, jitter/confirmation, gap/prediksi, class-independent diagnostics dan raw-source integrity.

Dua regresi awal benar-benar gagal sebelum diperbaiki: origin A dapat memiliki kedua tanda karena tepi polygon dan garis tidak identik; kontak sepanjang garis yang keluar melalui endpoint tidak boleh menggunakan kontak interior lama untuk mengesahkan crossing. [Kegagalan historis](evidence/phase_5/20261011_G3_analysis/initial_synthetic_regression_failures.json) dipertahankan. Perbaikan mengacu pada entry/exit sign passage aktual serta membatalkan interval kontak melalui endpoint. Kandidat yang benar-benar keluar lalu kembali ke region asal dibatalkan; tetap di strip A setelah passage belum berarti kembali ke A. Tiga tes integritas kemudian menolak campuran variant/parent run, confidence nonfinite dan detection index ganda pada frame. Ini bukan deduplikasi kendaraan: deteksi berbeda dengan kotak sama masih boleh menjadi diagnostik.

Setiap transisi menyimpan origin/passage/confirmation, track/frame/source-detection links dan parameter. Semua menggunakan `accepted_count_event=False` dan `repeat_business_policy_open=True`; reverse geometry diagnostics tidak menetapkan kebijakan bisnis count berulang.

## Eksekusi dan sensitivitas parameter

Run **20261011T161440_100155Z_2e39a11c**, Python3.12.14 pada CPU, memproses **10.282 frame kontinu, 48.228 measured emitted observations, 997 ID software** pada setiap konfigurasi. Source ReID-on berasal dari Phase4 `20261011T095924_205716Z_90cf7319`; `parent_run_id` dalam baris adalah Phase2 `20261011T052950_360560Z_ed399fb8`. Ini replay cache track; YOLO/BoT-SORT/encoder tidak dimuat atau dieksekusi ulang.

[Analisis BC](evidence/phase_5/20261011_G3_analysis/anchor_variation_analysis.json) menemukan tiga measured return excursions satu frame, semua kelas mentah `person`. Band eksploratif adalah kontrol0, median4.567185192815604, maksimum39.945593728512996 native px. Maksimum merupakan stress sensitivity, bukan estimasi noise. Konfirmasi1/2 menguji pengaruh arrival berturut-turut. Band adalah **half-width** terhadap garis; angka berikut bukan nilai terbaik/default produk.

| Eksperimen | Half-width px | Konfirmasi obs | Diagnostik A→B | Diagnostik B→A | Ambiguous gap |
|---|---:|---:|---:|---:|---:|
| `b0_c1` | 0.000000 | 1 | 67 | 93 | 6 |
| `b0_c2` | 0.000000 | 2 | 64 | 89 | 6 |
| `bmedian_c1` | 4.567185 | 1 | 65 | 88 | 8 |
| `bmedian_c2` | 4.567185 | 2 | 64 | 86 | 7 |
| `bmax_c1` | 39.945594 | 1 | 60 | 73 | 10 |
| `bmax_c2` | 39.945594 | 2 | 57 | 71 | 10 |

Angka tabel adalah frekuensi diagnostik software dari seluruh kelas mentah, **bukan traffic count**. Nol endpoint ambigu pada cache ini tidak membuktikan endpoint selalu aman; fixture sintetis tetap menguji kasus tersebut. Durasi CPU terukur per konfigurasi3.02–3.23 detik tersimpan dalam report; ini tidak termasuk detector/tracker/ReID/video-processing end-to-end.

[Review temporal output aktual](evidence/phase_5/20261011T161440_100155Z_2e39a11c/temporal_replay_review.json) menunjukkan perubahan yang tidak selalu monoton: pada band median/C2, ID912 berpindah passage dari5019→5020 ke5021→5022. Konfirmasi2 menunda 153 passage kontrol yang bertahan satu frame dan menghilangkan tujuh passage kontrol lainnya. Band maksimum menunda beberapa konfirmasi sampai sembilan frame; lebih sedikit diagnostik bukan bukti lebih baik.

## Kasus yang tetap penting

- Skuter merah: rider967 dan overlapping motorcycle964/973 memberikan passage terpisah pada kontrol. Median band menghilangkan973 karena origin pertama yang memenuhi band menjadi A5130, bukan bukti bahwa identitas fisik telah dideduplikasi.
- Rider1774 dan motorcycle1772 tetap memberi dua diagnostik terkait lintasan skuter yang sama **di seluruh enam konfigurasi**. Threshold geometri tidak menyelesaikan kategori/rider-versus-vehicle association.
- ID1217 pada6017→6019 dan ID1712 pada7559→7565 tetap `AMBIGUOUS_GAP` tanpa interpolasi, tanpa transisi terkait, pada enam konfigurasi. Confidence/prediksi tidak dipakai untuk mengarang passage yang hilang.
- Excursions893@4978 dan912@5020/@5021 memiliki perubahan raw BC; angka amplitudo tidak sendiri membuktikan jitter/gerak balik kendaraan. Interpretasi harus mengacu pada pixel asli dan komponen bbox yang diasosiasikan.

[Review pixel retained awal](evidence/phase_5/20261011_G3_analysis/retained_visual_review.json) memeriksa empat pasangan exact dari contact sheet/full-res samples. Contact sheet interval30frame hanya menyimpan enam sampel; bukan semua frame. Review ini dibedakan dari suplementasi video asli berikutnya.

## Suplementasi pixel asli — 12 Oktober 2026

Akses dataset Kaggle diuji berhasil, lalu satu file TOR3-PAGI diunduh ke `/tmp`, tanpa disertakan di GitHub. [Decode/alignment](evidence/phase_5/20261012_temporal_review/decode_alignment.json) memverifikasi SHA-256 dan ukuran identik dengan input sebelumnya, **10.282 frame native1280×720** serta kesamaan pixel persis pada frame5140 terhadap PNG Phase2. Ini memperkuat mapping indeks decoder pada review ini, bukan bukti authoritative source PTS atau integritas setiap pixel/frame sepanjang video. Metadata current dan decode sama10282; tidak ada dugaan frame hilang yang dibuat dari count tersebut.

[Review pixel aktual](evidence/phase_5/20261012_temporal_review/README.md) membuka sepuluh contact sheet raw/overlay, **20 frame exact pada lima kasus**. Decode seluruh video dilakukan untuk ekstraksi; hanya sampel yang disebut di laporan direview secara visual. Crop native, hash pixel, bbox/detection/frame links dan transform overlay tersimpan di manifest. Gambar anotasi memakai raw-bbox BC, tanpa inference, enhancement atau stabilisasi.

- **ID893/912:** skuter tetap tampak bergerak ke kiri/menjauh, tanpa U-turn tampak pada sampel. Kotak `person` sesaat memendek bagian bawah; pada ID912 y2 berubah577.21→518.61→572.05. Excursions konsisten dengan perubahan cakupan bbox rider, sehingga amplitudo39.95px tidak layak disebut estimasi noise kamera murni atau alasan otomatis memilih band40px.
- **ID1217:** pickup tetap terlihat dan raw detection truck tersedia di6018 ketika1217 tidak emitted. Observasi assigned1279 terkait deteksi itu `is_activated=True` tetapi **`emitted=False`**, lifecycle `not_retained`; observasi ini tidak dimasukkan ke trajectory. Activated tidak sama dengan emitted. Gap mencerminkan ketidaktersediaan pengukuran emitted/lifecycle, bukan bukti semua deteksi atau visibilitas hilang.
- **ID1712:** ada dukungan pixel untuk tertutup kendaraan foreground di sekitar7560 dan terlihat kembali7564/7565. Lima frame gap tidak semuanya direview; posisi sebelum/sesudah gap belum menjadi passage kontinu. Kandidat unconfirmed7564 tidak menggantikan pengukuran1712 yang hilang.
- **Skuter merah:** raw crops/overlay mengonfirmasi overlap motorcycle964/973 pada skuter yang sama plus rider967; parameter geometri tidak menyelesaikan identitas/kategori komponen.

**Keputusan parameter:** pertahankan enam konfigurasi sebagai eksperimen reproducible; **jangan tetapkan median/maksimum sebagai default produksi**. Bukti ini mengarahkan prioritas ke konsistensi anchor per kendaraan, rider association dan physical dedup. Suitability numeric tetap OPEN sampai audited vehicle-level trajectories dan tradeoff origin/arrival dibahas; tidak perlu mengarang threshold baru. Software Phase5 lulus scoped gate, sedangkan counting belum dapat dipercaya hanya dari jumlah diagnostik.

## Bukti dan reproduksi

[Direktori run](evidence/phase_5/20261011T161440_100155Z_2e39a11c/README.md) menyimpan report, diagnostics.gz, konfigurasi efektif, hasil tes, manifest hash, audit dan executed notebook terkompresi. Notebook source tetap tanpa output; artefak executed berasal dari run nyata. Video asli dikecualikan dari GitHub. G1/G2/G3 dan evidence Phase1–4 tetap immutable.

```bash
python notebooks/phase_5_synthetic_tests.py
```

Kemudian buka `notebooks/05_geometry_replay.ipynb` dari checkout lengkap, atur path eksplisit bila diperlukan, dan **Run All**. Notebook menjalankan guard tes sebelum membaca cache. GPU/video asli tidak diperlukan untuk geometry replay. Reproduksi tidak dibutuhkan untuk menerima review dari evidence yang sudah tersimpan.

**OPEN / tindakan berikutnya:** review kasus BC/component fluctuation dan tradeoff origin/arrival sebelum menetapkan numeric defaults. Phase6 membutuhkan kebijakan kategori/eligibility/dedup/true return tersendiri; tidak boleh menjumlahkan diagnostik menjadi kendaraan. ReID tetap dalam arsitektur; final vehicle-domain setting, night experiments, GMC/stabilization, video lain dan UI tetap di fase masing-masing.
