# Sampel eksperimen TOR3-MALAM

**Keputusan berikutnya:** N1 dan arah malam kemudian diterima untuk uji awal pada [accepted geometry](../accepted_geometry/README.md). Sampling plan tetap dibekukan dengan referensi proposal sebelum feedback; approval tidak mengubah split, frame screen, koordinat atau hasil lama.

**EXECUTED RAW EVIDENCE:** builder membaca video Kaggle SHA `a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082`, ukuran 52,906,523 byte, dan mengeluarkan 9,590 frame native 1280×720. Jumlah cocok dengan bukti decoder Phase 1; ini tidak membuktikan integritas sumber atau tidak adanya frame unsupported/corrupt. Tidak ada model atau enhancement dijalankan dalam pembuatan arsip ini.

[Rencana sampel v1](TOR3-MALAM_sampling_plan_v1.json) dibekukan sebelum hasil enhancement/model. `end_frame` inclusive dan indeks dimulai dari nol. Semua window memuat 240 frame berurutan sebagai budget eksperimen, bukan threshold eligibility atau jaminan satu passage lengkap.

| Split | Segment | Frame inclusive | Anchor Phase 1 |
|---|---|---|---|
| Development | dev_beginning | 0–239 | 0 |
| Development | dev_quarter | 2277–2516 | 2397 |
| Development | dev_three_quarters | 7072–7311 | 7192 |
| Hold-out | holdout_middle | 4674–4913 | 4794 |
| Hold-out | holdout_end | 9350–9589 | 9589 |

**Development screen:** 15 native frame dipilih di dalam ketiga window: `0, 7, 14, 29, 239, 2277, 2337, 2397, 2457, 2516, 7072, 7132, 7192, 7252, 7311`. Frame 7/14/29 menyertakan motorcycle dekat pada awal, yang mudah terlewat oleh sampling seragam. Pemilihan memakai bukti raw, tidak memakai hasil model/enhancement. Frame sparse ini cukup untuk screening photometric/detection; ia tidak menggantikan rangkaian kontinu yang dibutuhkan tracker/counting.

**Hold-out reserved:** sepuluh indeks raw tersedia untuk reproduksi, tetapi tidak boleh dipakai untuk seleksi/tuning kandidat melalui hasil enhancement/model. Hold-out **tidak blind**: anchor dan burst telah ditinjau di Phase 1, dan lembar raw temporal saat ini ditinjau untuk batas konteks sampel. Ia adalah pemisahan development/evaluation, bukan dataset GT atau bukti generalisasi ke rekaman baru.

**VISUAL OBSERVATION AI-ASSISTED, dari lima lembar raw temporal yang dibuka:**

- Awal: motorcycle masuk dari kanan/dekat, mengecil menuju kiri/jauh; motorcycle lain menyusul. Riwayat sebelum file dimulai tidak tersedia.
- Quarter: motorcycle sudah sebagian berada di tepi kanan pada awal window; setelah bergerak jauh, kendaraan berlampu depan terang terlihat bergerak mendekat dan keluar ke kanan. Silau dominan pada sebagian frame.
- Three-quarter: flatbed truck sudah ada pada frame pertama; tidak ada klaim origin/truck passage lengkap. Berikutnya motorcycle/rider dan mobil putih masuk dari kanan/dekat lalu bergerak jauh. Teks tertanam menutup sebagian kendaraan dekat. Kendaraan berikutnya mulai terlihat di akhir window.
- Middle hold-out: satu motorcycle berlampu bergerak mendekat/keluar ke kanan, dan motorcycle lain masuk dari kanan lalu bergerak jauh. Ini review konteks raw saja.
- End hold-out: beberapa kendaraan tampak bersama, dan kendaraan dengan lampu depan masih mendekat pada EOF. Bukti sesudah akhir file tidak tersedia; passage yang belum lengkap tetap belum lengkap.

Saat sampling plan dibekukan, semantik A/B malam masih PROPOSAL pada [N1](../geometry_proposals/TOR3-MALAM-N1.json). Pengguna kemudian mengonfirmasi geometri awal dan arah dalam [feedback terpisah](../feedback/N1_review_001.json). Observasi mendekat/menjauh dari gambar saja tidak menjadi approval polygon atau `CountEvent`. Identitas lintas window tidak ditetapkan. Pending/hard ambiguity tidak boleh diperbaiki melalui perubahan kategori/review.

Lima `*_raw_temporal.png` adalah display sheet dari **135 frame raw unik**, berukuran thumbnail 640×360 dengan indeks sumber. `frames/` memuat **25 PNG lossless native** untuk lima indeks per window. [Build manifest](build_manifest.json) menyimpan SHA artifact, hash pixel raw RGB, transform display, metadata OpenCV, dan FPS-derived timing yang tetap estimasi. Clip kontinu 640×360 dibuat di `/tmp/traffic-phase7-source/raw_sampling_clips` untuk review runtime, tidak disimpan di Git, tidak mempertahankan source PTS, dan tidak digunakan sebagai input model.

Validasi read-only:

```bash
/workspace/.venvs/traffic-inspection/bin/python \
  docs/evidence/phase_7/verification/check_night_geometry_and_sampling.py --repo .
```

[Hasil aktual](artifact_validation.json): **1,384/1,384 assertions PASS**, termasuk 1,200 pemeriksaan dimensi per-frame untuk lima clip runtime. Cakupan: hash/source/native pixels, pemisahan sampel, budget frame dan topologi/mapping proposal geometri. Ini bukan test/model benchmark atau pengukuran akurasi.
