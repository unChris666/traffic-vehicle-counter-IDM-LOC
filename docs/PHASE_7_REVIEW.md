<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Phase 7 — TOR3-MALAM, raw versus enhancement

**EXPERIMENT RESULT, 14 Oktober 2026:** Phase 7 selesai dalam scope eksperimen TOR3-MALAM: screening, temporal raw/gamma, hold-out, review passage dan biaya pemrosesan aktual. **RECOMMENDATION:** pertahankan raw sebagai baseline penelitian berikutnya; gamma0,7 tidak dipromosikan menjadi konfigurasi produksi. Hasil ini tidak menetapkan total traffic seluruh video atau manfaat counting otomatis secara umum.

## Keputusan dan sumber

- [Keputusan pengguna](evidence/phase_7/authorization/phase_7_user_decisions_20261014.json): B v1 dengan overlay review, offline, konflik pending, kontrol counting beku, genuine-return konservatif, taxonomy/ReID produksi OPEN.
- [Feedback N1](evidence/phase_7/feedback/N1_review_001.json), [geometri accepted](evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json), [gambar N1](evidence/phase_7/geometry_proposals/TOR3-MALAM-N1.png).
- [Sampling plan](evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json): tiga window DEV dan dua hold-out, masing-masing240frame. Sebagian kendaraan berada pada batas window/video; tidak semua passage lengkap.
- Actual Kaggle input `TOR3-MALAM.mp4`: SHA-256 `a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082`,52.906.523bytes,1280×720,9.590frame. Download saat task ini cocok dengan bukti Phase1. Source video tidak masuk GitHub.

## 7A — screening aktual

Run [20261014T060849_366767Z](evidence/phase_7/screening/20261014T060849_366767Z/report.json), [notebook Kaggle privat](https://www.kaggle.com/code/chrisbiran/phase-7-tor3-malam-enhancement-screening), [submission/log provenance](evidence/phase_7/kaggle_submission/screen_submission.json).

Lima varian memakai15DEVframe yang identik: raw; gamma power0.7; exposure gain1.25; contrast factor1.25/pivot128; unsharp Gaussian sigma1/amount0.5. Nilai adalah engineering test points, bukan hasil tuning atau default terbaik. Operasi memakai float64, `numpy.rint`, clip0…255, BGRuint8; tidak ada crop/resize geometri tambahan. Detector mempertahankan preprocessing standar model.

YOLO26M resmi, SHA`401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`, Ultralytics8.4.175, CUDA0 TeslaT4, FP32 dan kontrol predictor yang sama dengan Phase2 terverifikasi. Dua GPU terlihat; hanya CUDA0 dipakai.75prediksi sampel tersimpan;5warmup nyata disimpan terpisah dan dikecualikan dari statistik prediction.127observasi bbox adalah observasi frame, bukan jumlah kendaraan/passage.

- [60/60 guard software aktual](evidence/phase_7/screening/20261014T060849_366767Z/pre_execution_guard/synthetic_test_results.json).
- [2.059/2.059 audit independen](evidence/phase_7/screening/20261014T060849_366767Z/independent_artifact_audit.json): source/native pixels,75transform/annotations, source/config/model hashes, class/bbox links, actual runtime, frame scope dan immutable Phase6A.
- [Review visual DEV](evidence/phase_7/screening/20261014T060849_366767Z/visual_review/README.md): semua15frame/lima varian,30contact sheet benar-benar dibuka,592/592 pemeriksaan sumber dan crop. [Before/after overview](evidence/phase_7/screening/20261014T060849_366767Z/development_transformed_overview.png) dan [deteksi overview](evidence/phase_7/screening/20261014T060849_366767Z/development_annotated_overview.png).

Audit anotasi awal menggunakan OpenCV5 berbeda pada rendering teks. Verifikasi akhir memakai OpenCV4.13.0/NumPy2.0.2 yang sama dengan Kaggle; seluruh transform dan anotasi bit-identical. Ini koreksi lingkungan/metode audit; output model asli tidak diubah.

## Shortlist DEV dan regresi

[Gamma0.7 dibekukan](evidence/phase_7/selection/TOR3-MALAM_DEV_shortlist_v1.json) sebagai **probe temporal**, karena shadow/midtone jalan dan underbody tampak lebih terbuka dalam sampel DEV. Raw tetap pembanding. Ini tidak membuktikan manfaat detector/tracker/counting.

| Kasus DEV | Observasi aktual yang harus diuji secara temporal |
|---|---|
| Frame14 | Bbox motorcycle yang ada pada raw tidak muncul pada gamma. |
| Frame2277 | Gamma menambah bbox car yang bertumpuk pada bagian depan motor dekat; unit/kategori belum terselesaikan. |
| Frame2337 | Bbox motorcycle background kecil tidak muncul pada gamma; identitas fisik kecil tetap terbatas. |
| Frame7072 | Dua bbox truck bertumpuk tetap ada pada gamma. |
| Frame7252 | Interpretasi bicycle/motorcycle pada two-wheeler kecil masih berbeda antarvarian. |

Exposure menambah highlight dan tidak mempertahankan bbox car7311. Contrast menggelapkan shadow; satu bbox truck7072 tidak membuktikan manfaat downstream. Unsharp tidak menghilangkan motion blur dan juga menghasilkan bbox car tambahan2277. Semua kesimpulan terbatas pada frame DEV yang dibuka; tidak menyebut bbox yang ambigu sebagai false detection tanpa bukti fisik.

Hold-out belum dipakai untuk enhancement/inference atau pemilihan kandidat pada tahap7A. Decoder sequential dapat membaca dan membuang frame di interval hold-out saat menuju sampel DEV. Raw hold-out pernah diinspeksi untuk Phase1/geometri/sampling; pemisahan ini withholding outcome, bukan blind benchmark.

## Perbandingan temporal

[Source notebook07b](../notebooks/07b_night_temporal_comparison.ipynb) dan [konfigurasi](evidence/phase_7/config/TOR3-MALAM_temporal_v1.json) telah dipersiapkan dengan [41/41 guard sintetis](evidence/phase_7/verification/pre_execution_temporal_synthetic_tests.json). [Submission temporal](evidence/phase_7/kaggle_submission/temporal_v1_submission.json) memisahkan pengajuan job dari hasil eksekusi.

Desain: raw versus gamma0.7, detector/BoT-SORT/ReID/counting tetap, frame yang sama diberikan ke detector dan encoder. Encoder person-domain `yolo26n-reid.onnx` Phase4 merupakan kontrol eksplisit, bukan vehicle-ReID final. Efek detector/appearance tidak diklaim terpisah karena enhancement mengubah input keduanya.

Seluruh9.590frame per varian diproses untuk riwayat dan state, sementara kandidat/counting hanya pada lima window yang dinyatakan sebelum hasil. ID dipilih dari observasi malam aktual; ID kasus PAGI tidak dipakai. B v1 mempertahankan controls, episode/return/raw-BC/local-identity rules; adapter source hanya mengubah literal validasi provenance menjadi `retained_phase_7_detection`, dengan hash/archive. Seluruh sumber sebelum filtering tetap tersedia.

**EXPERIMENT RESULT:** [run temporal](evidence/phase_7/temporal/20261014T062858_002323Z/report.json) menyelesaikan9.590frame per varian, raw lalu gamma, dengan state baru pada awal masing-masing varian. Detector/encoder berjalan di CUDA0, association di CPU. Dua T4 terlihat; satu dipakai. Seluruh85artefak manifest run cocok size/SHA setelah download diverifikasi.

## Hasil mesin dan review terpisah

| Snapshot aktual | Raw | Gamma0,7 |
|---|---:|---:|
| Mesin — DEV | 0 accepted / 6 pending | 1 accepted / 5 pending |
| Mesin — hold-out | 0 accepted / 2 pending | 0 accepted / 2 pending |
| Setelah review terjaga — DEV | 5 accepted / 1 pending | 5 accepted / 1 pending |
| Setelah review terjaga — hold-out | 2 accepted / 0 pending | 2 accepted / 0 pending |
| Setelah review — seluruh scope | **7 accepted / 1 pending** | **7 accepted / 1 pending** |
| Sumber accepted | 7 manual | 6 manual + 1 event mesin asli |

Sumber: [raw mesin](evidence/phase_7/temporal/20261014T062858_002323Z/raw/counting_report.json), [gamma mesin](evidence/phase_7/temporal/20261014T062858_002323Z/gamma_070/counting_report.json), [raw reviewed](evidence/phase_7/temporal/20261014T062858_002323Z/raw_reviewed/report.json), [gamma reviewed](evidence/phase_7/temporal/20261014T062858_002323Z/gamma_070_reviewed/report.json), dan [perbandingan final per passage](evidence/phase_7/temporal/20261014T062858_002323Z/final_physical_passage_comparison.csv).

Kedua reviewed branch berisi passage fisik yang sama: **6 motorcycle dan1truck**, A→B satu dan B→A enam. Rider menjadi bagian unit motorcycle, tidak menghasilkan event kendaraan tambahan. Crossing memakai raw detector-linked emitted **vehicle BC**, bukan rider/prediksi. Payload event otomatis gamma dipertahankan persis; output mesin asli tidak ditimpa. Subtotal ini bukan total traffic seluruh video.

## Temuan per passage dan regresi

[Review pixel temporal](evidence/phase_7/temporal/20261014T062858_002323Z/temporal_review/README.md) benar-benar membuka22contact PNG,73frame sumber unik, delapan kandidat passage dan tiga kontrol. Kendaraan dicocokkan melalui gambar/frame/trajectory fisik, bukan kesamaan ID lintas varian.

| Kasus | Temuan yang didukung bukti |
|---|---|
| Motorcycle crossing26→27 | Kandidat bertumpuk pada satu unit tetap memerlukan review; gamma tidak menyelesaikan duplikasi otomatis. |
| Motorcycle crossing112→113 | Gamma track15+rider18 memang satu motorcycle, vehicle BC valid. Raw pending, gamma accepted otomatis. Episode raw berlanjut sampai119; label bicycle memutus episode gamma setelah114. Relasi raw lokal105–113 memenuhi kontrol motion, tetapi observasi115→116 menolak relasi global. Selisih acceptance sensitif terhadap batas episode/aturan offline; bukan bukti ReID atau enhancement lebih andal. |
| Motorcycle crossing2296→2297 | Kedua varian memerlukan review karena dukungan identitas otomatis berada di luar window passage. Gamma2277 memberi label car pada komponen motorcycle yang terlihat. |
| Truck crossing7113→7114 | Bbox/competitor pada satu loaded truck tetap membutuhkan review; gamma memiliki episode lebih pendek. Tidak ada bukti perbaikan deduplikasi otomatis secara umum. |
| Motorcycle crossing7169→7170 | Review mendukung satu unit; konflik dukungan identitas/competitor gamma tidak terselesaikan hanya karena gambar lebih terang. |
| Kendaraan putih crossing7243→7244 | Class history car/truck konflik pada kedua varian. Kendaraan penumpang terlihat pada frame dekat, tetapi kategori episode penuh dan taxonomy belum terselesaikan. **Tetap pending**, tidak dipaksa car melalui review. |
| Hold-out crossing4868→4869 dan9355→9356 | Passage fisik/crossing sama, keduanya pending otomatis lalu diterima melalui review positif. Tidak ada tambahan accepted otomatis hold-out dari gamma. |
| Kontrol silau/akhir | Gamma tidak mengembalikan detail tubuh kendaraan yang tidak jelas dari glare; observasi emitted lokal9410 juga hilang. Kasus batas/EOF tidak dipromosikan menjadi passage lengkap. |

Label bicycle sesudah crossing, label car pada motor, perubahan episode dan hilangnya observasi dipertahankan sebagai regresi. Tidak ditemukannya salah penggabungan pada tujuh passage reviewed ini tidak membuktikan seluruh video bebas salah gabung atau semua passage telah ditemukan. B resolver tidak memakai embeddings untuk grouping komponen; ReID aktif di tracker.

## Biaya pemrosesan aktual

| Wall time, detik | Raw | Gamma0,7 |
|---|---:|---:|
| Decode | 10,241 | 12,225 |
| Transform | 3,337 | 450,340 |
| Detector | 181,779 | 257,648 |
| Tracker, termasuk encoder | 392,491 | 397,027 |
| Encoder, bagian dari tracker | 380,939 | 384,935 |
| Loop penuh terinstrumentasi | **673,549** | **1.205,209** |

Loop gamma sekitar **1,79×** raw pada run sequential ini; transform float64 menyumbang tambahan besar. Encoder tidak dijumlahkan kembali dengan tracker. Urutan branch, warmup dan instrumentasi membatasi atribusi; ini bukan throughput produksi atau biaya moneter. Peak Torch allocated sekitar159MiB dan reserved198MiB per branch tidak mencakup seluruh alokasi ONNXRuntime. Peak process RSS sekitar1,84GiB raw/1,93GiB gamma bersifat cumulative dalam proses yang sama, bukan RAM independen tiap branch.

## Validasi dan masalah decode/review

- Temporal: **41/41** guard software dan [343.820/343.820 audit independen](evidence/phase_7/temporal/20261014T062858_002323Z/independent_artifact_audit.json), termasuk seluruh native donor raw/gamma, cache, BC, kategori, event, CUDA profile dan retensi historis.
- Review: **601/601** pixel/source/media checks, **32/32** guard sintetis overlay dan52/52 integritas tambahan. Manual review tidak memperbaiki crossing invalid, gap/prediksi, kategori hard block atau genuine return tanpa bukti.
- [Notebook temporal Kaggle privat](https://www.kaggle.com/code/chrisbiran/phase-7-tor3-malam-temporal-comparison) selesai. [Provenance/log](evidence/phase_7/kaggle_submission/temporal_v1_submission.json) mengikat source submitted, embedded bundle, actual report dan log. Submitted notebook tidak diklaim sebagai notebook beroutput eksekusi.
- Sebagian download pertama berupa HTML332byte. Pengambilan artifact versi1 memulihkan85/85kecocokan size/SHA; model tidak diulang. Satu checker temporal awal belum memasukkan field scope feedback; koreksi method/failed report disimpan transparan, output pipeline tidak diubah.
- Tidak ada decode gagal pada9.590frame yang diuji. Timestamp index/FPS bukan PTS otoritatif; integritas timing/VFR tetap OPEN. Embeddings dan matriks biaya tidak disimpan, sehingga rekalkulasi numerik association independen terbatas; actual runtime observer/hash/CUDA profile tersedia.
- [Setup cloud audit](evidence/phase_7/verification/cloud_audit_readiness.json) lulus7/7pemeriksaan fungsional. Install/start instructions disimpan sebagai draft lingkungan; publikasi/fresh-task restoration belum diuji. Codex memverifikasi software/artifact; model GPU berjalan di Kaggle. Tidak ada inference ulang selama final audit/review.
- [Validasi retensi final](evidence/phase_7/final_artifact_validation.json) mengikat source, dokumentasi, actual artifacts, reviewed events dan sumber BC asli; [reproduksi packaging](evidence/phase_7/verification/source_packaging_reproduction.json) menghasilkan notebook submitted yang identik tanpa menjalankan model.

Untuk audit source-pixel dengan video identik yang tersedia di `/tmp`, mulai dari argumen checker:

```bash
/workspace/.venvs/phase7-audit/bin/python \
  docs/evidence/phase_7/verification/check_temporal_artifacts.py --help
```

Checker ini tidak menjalankan model; pilih path video/run/context eksplisit sesuai manifest retained. Source video dan weights tetap eksternal.

## Keputusan akhir dan pekerjaan berikutnya

[Keputusan terikat evidence](evidence/phase_7/selection/TOR3-MALAM_final_decision_v1.json): **Phase7 selesai untuk eksperimen scoped TOR3-MALAM; raw dipertahankan sebagai baseline penelitian; tidak ada enhancement produksi yang dipilih.** Gamma membuka beberapa piksel tetapi manfaat passage pada hold-out belum terbukti, regresi tetap ada, dan biaya naik. Kandidat lain hanya discreen DEV; belum diuji temporal sehingga tidak dinyatakan lebih baik secara menyeluruh.

OPEN yang dibawa: relasi global versus dukungan lokal passage/batas episode; kategori episode penuh; vehicle-ReID final; taxonomy; threshold jitter/duplikasi; genuine return otomatis; audit passage yang terlewat dan kelengkapan full-video. Semuanya membutuhkan eksperimen terpisah, tanpa retuning pada hold-out yang sudah dibuka ini.

**PROPOSAL — tugas Phase8 berikutnya:** konfirmasi inventaris tepat delapan video beserta lokasi/hari/periode, review geometri per video, kemudian proses dengan raw dan B v1 + overlay audit eksplisit. Dataset ditemukan memuat13video; delapan input tidak dipilih diam-diam. Phase8 belum dimulai.

Raw hold-out pernah dilihat pada Phase1/planning. Shortlist dibekukan sebelum outcome model, tetapi offline whole-video state/episode memakai konteks melintasi split. Ini eksperimen longitudinal satu video, bukan benchmark blind/iid atau bukti generalisasi.

## Batas

Tidak ada ground truth, accuracy, precision, recall, F1 atau MAPE. Synthetic correctness, descriptor piksel, lebih banyak detections/confidence/accepted atau lebih sedikit pending tidak membuktikan perbaikan counting. Tidak ada Phase8, UI, Docker atau multi-GPU processing dimulai.

Dokumen status Phase6B yang berubah mempertahankan versi aslinya dalam [context retention](evidence/phase_7/baseline_retention/context_retention_mapping.json); original source/evidence dan103artefak original A tetap utuh.
