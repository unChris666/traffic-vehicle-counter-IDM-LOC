# Perbandingan dua konfigurasi FP32 T7SL

Sumber: report.json yang dilampirkan pengguna. Unduhan output Kaggle saat audit hanya menyediakan log, tanpa measurement mentah. Satu run per konfigurasi; tanpa anotasi ground truth.

| Tahap | Baseline (s) | Kandidat (s) | Penghematan |
|---|---:|---:|---:|
| Startup | 14.71 | 6.08 | 58.70% |
| Pemrosesan video | 616.98 | 388.29 | 37.07% |
| Counting dan penyimpanan | 83.15 | 83.43 | -0.33% |
| Total | 714.84 | 477.79 | 33.16% |

Total 133 kendaraan, kategori dan arah, pending 28, invalid 11, cancelled 10 sama. Seluruh 9015 frame tercakup.

Kesetaraan domain gagal: track links, accepted/cancelled anchors, decisions, invalid decisions, frame assignments berbeda. Perbedaan ID bisa berupa penomoran ulang atau perubahan asosiasi fisik; laporan ringkas belum membedakannya. Confidence pertama berbeda sekitar 0.00000125.

Kandidat lebih cepat pada run ini, tetapi precision/recall/ID accuracy tidak dievaluasi. Baseline tetap dipilih oleh gate ketat.

Waktu backend ReID baseline dan kandidat mencakup jalur transfer berbeda; bukan waktu kernel GPU murni. Tracker candidate tidak mencakup ekstraksi embedding yang telah diprefetch. encoder_calls=0 pada kandidat bukan berarti ReID mati: counter hanya dihitung pada jalur pemanggilan sinkron.
