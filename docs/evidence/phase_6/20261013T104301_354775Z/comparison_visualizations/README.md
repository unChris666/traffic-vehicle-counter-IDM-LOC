# Visualisasi review kasus Opsi B — TOR3-PAGI

**EXPERIMENT RESULT:** lima kartu kasus dan satu overview dibuat dari foto/overlay retained, lalu **keenam PNG benar-benar dibuka dengan `view_image`**. [Index](index.json) mengikat SHA input/output, koordinat crop sumber, resize tampilan, metode dan font. [Review visual](visual_review.json) mencatat pemeriksaan gambar aktual. **73/73 pemeriksaan sumber, status, geometri, crop, dan dimensi lulus.**

Buka [overview](00_overview.png), lalu kartu kasus:

- [1772/1774](01_motorcycle1772.png): satu motorcycle diterima mesin; rider bukan event tambahan.
- [964/973](02_duplicate964_973.png): mesin pending; review manual satu event via raw BC964, bukan dua event.
- [1323](03_car1323.png): kategori car untuk kasus ini; identitas tiny edge box tetap belum diketahui.
- [923](04_motorcycle923.png): mesin pending karena dukungan relasi di luar passage; review manual memakai foto window passage asli.
- [880/892](05_negative880_892.png): dua kendaraan nyata tidak disatukan; kontrol asosiasi tidak menjadi total crossing.

Angka overview **B_machine=1 dan B_reviewed=4** berlaku pada subset kasus. Tiga event tambahan adalah keputusan review manual, bukan kontribusi otomatis atau bukti peningkatan akurasi. Perbandingan A/B yang lengkap berada dalam [review Opsi B](../../../../PHASE_6_OPTION_B_REVIEW.md).

Foto berasal dari [sample index temporal](../../option_b_temporal_review/sample_index.json). Gambar ini memakai bbox/BC/garis yang telah digambar pada source overlay. Resize LANCZOS hanya untuk tampilan; tidak mengubah pengukuran, threshold, event, atau foto sumber. Tidak ada decode video, detector/tracker/encoder/resolver run pada pembuatan kartu.

Untuk meregenerasi presentasi dari root repositori:

```bash
python docs/evidence/phase_6/option_b_verification/build_comparison_visuals.py
```

Metode kembali menandai review visual sebagai menunggu pembukaan gambar; pembacaan actual dengan tool dan pencatatan review dilakukan sebagai langkah terpisah. [Manifest](manifest.json) mengikat file publik setelah pembukaan gambar tersebut.
