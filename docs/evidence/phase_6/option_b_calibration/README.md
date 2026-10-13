# Opsi B — kalibrasi terbatas dari bukti tersimpan

**EXPERIMENT RESULT:** feature dihitung dari raw bbox emitted-track yang terikat ke sumber. Tidak menjalankan model, geometry state machine, counting, atau fitur kasus held-out ID1772/1774. Ini pengembangan parameter eksperimen; bukan ground truth atau ukuran accuracy.

| Relasi dan pasangan | Window | Common/consecutive max | Foot inside | Center distance max | Relative-motion residual max | IoU min |
|---|---|---:|---:|---:|---:|---:|
| COMPONENT_OF 893/880 | [4975, 4979] | 5/5 | 1.000000 | 0.350363035 | 0.0878045190975844 | 0.211578410 |
| COMPONENT_OF 912/923 | [5011, 5022] | 10/10 | 1.000000 | 0.508568709 | 0.14709144894354145 | 0.106039840 |
| COMPONENT_OF 967/964 | [5118, 5126] | 9/9 | 1.000000 | 0.302672591 | 0.06045734787755452 | 0.390116223 |
| SAME_VEHICLE 964/973 | [5129, 5130] | 2/2 | 0.000000 | 0.095087617 | 0.00978274108110126 | 0.598789486 |
| SAME_VEHICLE 1/3 | [60, 60] | 1/1 | 0.000000 | 0.776345805 | None | 0.007114490 |

**ENGINEERING EXPERIMENT — frozen thresholds:**

```json
{
  "component": {
    "min_common_frames": 3,
    "min_consecutive_common_frames": 3,
    "min_first_bc_inside_second_fraction": 1.0,
    "max_center_distance_norm": 0.51,
    "max_relative_motion_residual_norm": 0.15
  },
  "same_vehicle": {
    "min_common_frames": 2,
    "min_consecutive_common_frames": 2,
    "min_iou": 0.59,
    "max_center_distance_norm": 0.1,
    "max_relative_motion_residual_norm": 0.01
  }
}
```

Component spatial/motion upper bounds = ceil(100 * largest positive-window value)/100. Duplicate IoU lower bound = floor(100 * smallest positive-window value)/100; other bounds use same ceiling. Foot-inside minimum = smallest positive-window fraction. No target used. Rounding precision .01 is an explicit engineering control, not calibrated probability.

Component common/consecutive frames >=3 is an explicit engineering control to require temporal support. Duplicate >=2 reuses the two actually pixel-reviewed coexistent calibration frames; its reliability/generalization are unestablished.

Pasangan alternatif mempunyai label **UNKNOWN**. Nilainya membantu memeriksa ambiguity assignment, tetapi tidak diubah menjadi negative label tanpa pixel review. Pasangan ID1/3 memang kendaraan berbeda menurut review frame60; ia merupakan negative lintas kategori, bukan bukti kemampuan membedakan dua motorcycle berdekatan.

No held-out duplicate positive. Only one pixel-backed real negative, cross-category and one frame; same-category near-neighbour and walking-person negatives require additional actual review. Synthetic negatives do not substitute for those reviews.

Tidak ada embedding per observation dalam cache ini; feature appearance tidak digunakan. Label person dari rider tidak ikut menentukan kategori motorcycle. Source raw bbox/BC tetap disimpan apa adanya.

Reproduksi dari root repository:

```bash
python docs/evidence/phase_6/option_b_calibration/calibrate_retained_pairs.py --repo .
```

Artefak `pair_features.json` mempertahankan setiap frame/detection index/raw bbox/class/confidence, formula, alternatif dan hash sumber; `frozen_thresholds.json` mengikat angka ke metode serta feature bytes. Tidak boleh mengubah angka memakai hasil target lalu mengklaim target held-out.
