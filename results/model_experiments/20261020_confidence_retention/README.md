# Eksperimen confidence aktual setelah eksekusi P0

[Review dan keputusan](../../../docs/MODEL_CONFIGURATION_EXPERIMENT_REVIEW.md).

Kaggle private version1 selesai pada600 source frames per varian, dengan dua
actual YOLO26M predictions (conf0,25/0,10), BoT-SORT dan ReID CUDA0. Kedua
varian raw, tanpa enhancement. Confidence0,10 belum dipilih untuk produksi.

- `preparation/`: plan, submission receipt, source bundle dan tes persiapan.
- `kaggle_output_v1/phase9_model_confidence_v1/`: output aktual immutable baru.
- `verification/download_validation.json`:23 file unduhan cocok SHA/size;
  assets weights yang sudah terverifikasi pada run tidak diunduh ulang.
- `paired_review/`:600 pasangan frame terikat pixel,11 contact sheets yang
  dibuka, dan riwayat observasi berskor rendah.
- `p0_clip_replay/`: hasil dua cache baru dengan policy P0 v2 yang sama;
  local0–599 dipetakan eksplisit ke source7380–7979. Tidak memakai old ID review
  atau relasi donor, tanpa fake prehistory/post-clip frames.

Perbandingan540 frame evaluasi memberi13 versus12 accepted operasional,
dengan9 versus11 measured. Ini bukan total benar, bukan benchmark akurasi,
dan bukan perbandingan ekuivalen dengan172event full-video baseline lama.
Riset role/identitas dan validasi lintasvideo masih diperlukan.
