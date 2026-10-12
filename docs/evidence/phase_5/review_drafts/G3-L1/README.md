# G3-L1 — label titik A, koordinat G3 tetap

**USER DECISION:** [jawaban G3](../../feedback/G3_review_001.json) menyetujui G3 dan Polygon B, lalu memberi label P1A, P1B, P1C, P1D pada empat koordinat A yang identik dengan gambar G3. Nama titik adalah identitas, bukan permintaan menghubungkan titik dalam urutan alfabet. Keliling sederhana **P1A → P1B → P1D → P1C** mempertahankan semua titik; urutan ABCD akan menyilang.

[PNG](TOR3-PAGI-G3-L1.png), [SVG](TOR3-PAGI-G3-L1.svg), dan [viewer](review.html) hanya memperjelas label. Semua angka label titik A dan endpoint garis memakai acuan template **960×540**, sementara gambar dirender native **1280×720**. [vertex_labels.json](vertex_labels.json) dan pointer viewer membedakan kedua acuan. Foto, polygon, garis, batas B dan contoh BC tidak berubah dari G3. P1C tetap berbeda dari endpoint P2; tidak ada snapping.

Persetujuan aturan kualitatif dibaca dalam konteks pertanyaan G3 yang menyertakan aturan awal, dengan pertanyaan/jawaban/interpretasi disimpan bersama. Lihat [kontrak](../../../../GEOMETRY_CONTRACT.md) dan [konfigurasi diterima untuk uji Phase 5](../../accepted_geometry/TOR3-PAGI-G3.json). Threshold numerik belum menjadi default produk. Template tetap perlu review per video; ukuran gambar berskala terdahulu tetap UNKNOWN.

**EXPERIMENT RESULT — anotasi:** [figure_validation.json](figure_validation.json) merekam lima pemeriksaan aktual: byte foto sama, geometri sama, label exact, render native, dan toggle anotasi. Ini bukan tes crossing atau pengukuran performa. G1/G2/G3 dan manifest historisnya tetap utuh.

Dari root repository:

```bash
python docs/evidence/phase_5/verification/build_g3_labels.py
python docs/evidence/phase_5/verification/check_g3_labels.py
```

Render/check memakai Playwright dan Chromium yang tersedia di lingkungan review; helper/replay geometri menggunakan Python standard library. Viewer adalah alat review lokal tanpa penyimpanan konfigurasi produk; halaman setup nantinya berada pada Phase 11.
