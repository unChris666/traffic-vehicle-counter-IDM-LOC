# TOR3-MALAM — N1 diterima untuk uji awal

**USER-CONFIRMED, 14 Oktober 2026 (Asia/Bangkok):** pengguna menjawab **“Setuju untuk uji awal”** terhadap garis/polygon N1, dan **“Ya, pemetaan arah benar”** terhadap `A_TO_B = mendekati kamera`, `B_TO_A = menjauhi kamera`. [Feedback exact](../feedback/N1_review_001.json) menyimpan pertanyaan, jawaban dan hash gambar/proposal.

[N1 accepted](TOR3-MALAM-N1.json) adalah artifact terpisah dari [proposal historis](../geometry_proposals/TOR3-MALAM-N1.json). Semua koordinat reference, normalized, native, cap B dan selisih P2–vertex A tetap identik. Angka rounded pada pertanyaan tidak menggantikan angka lengkap. PNG proposal berlabel “PROPOSAL” dan sampling plan yang dibekukan sebelum feedback tetap disimpan tanpa perubahan.

Persetujuan ini membuka pemakaian geometri per-video dalam eksperimen Phase 7 setelah gate software/source terpenuhi. Ia tidak membuktikan whole-video completeness, keandalan produksi, threshold terbaik, atau akurasi. BC raw kendaraan setelah asosiasi dan b0_c1 tetap kontrol eksperimen yang disepakati.

`Geometry.from_draft(path,1280,720)` menerima artifact ini dan memvalidasi polygon sederhana, non-overlap, normalisasi dan finite line. Persetujuan malam diperoleh langsung dari feedback; tidak diwariskan diam-diam dari TOR3-PAGI.

Reproduksi acceptance dari keputusan yang sudah tersimpan:

```bash
python docs/evidence/phase_7/verification/build_accepted_n1.py --repo .
```

Validasi read-only artifact/feedback:

```bash
/workspace/.venvs/traffic-inspection/bin/python \
  docs/evidence/phase_7/verification/check_accepted_n1.py --repo .
```
