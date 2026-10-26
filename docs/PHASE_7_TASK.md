<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Phase 7 — eksperimen preprocessing TOR3-MALAM

**REQUIREMENT — otorisasi 14 Oktober 2026:** pengguna menyetujui profil penelitian B v1 dengan overlay review eksplisit, keputusan offline setelah episode/video selesai, unresolved tetap pending, dan perbandingan enhancement pada passage fisik yang sama. Opsi A tetap menjadi pembanding tersimpan; B belum dipilih sebagai default produksi. Instruksi “lanjutkan pengembangan” mengizinkan persiapan serta eksperimen Phase 7 dalam batas berikut.

Dokumen ini mendefinisikan tugas dan gate. Hasil eksekusi dicatat terpisah setelah benar-benar dijalankan; rencana, tes software, gambar pencerahan, dan keluaran detector tidak membuktikan perbaikan tracking/counting.

**EXPERIMENT RESULT — status 14 Oktober 2026:** [screen 7A](evidence/phase_7/screening/20261014T060849_366767Z/report.json) selesai pada Kaggle Tesla T4 `cuda:0`, YOLO26M FP32, dengan guard [60/60 tes software](evidence/phase_7/screening/20261014T060849_366767Z/pre_execution_guard/synthetic_test_results.json). Lima recipe menghasilkan 75 prediction rows terukur (15 DEV×5) serta lima call warmup terpisah; tidak ada hold-out enhancement/inference, tracker, encoder atau CountEvent dalam run screen. [N1 sudah disetujui pengguna untuk uji awal](evidence/phase_7/feedback/N1_review_001.json). [Shortlist gamma0,7](evidence/phase_7/selection/TOR3-MALAM_DEV_shortlist_v1.json) dibekukan berdasarkan DEV sebelum [run temporal aktual](evidence/phase_7/temporal/20261014T062858_002323Z/report.json): raw dan gamma masing-masing memproses seluruh 9.590 frame dengan detector/encoder pada `cuda:0` serta association CPU. Counting tetap dibatasi kelima window deklarasi. Snapshot **mesin** raw memuat 0 accepted/8 pending; gamma 1 accepted/7 pending. Status review fisik di report mesin tetap historis `PENDING_PHYSICAL_PASSAGE_REVIEW`; keputusan overlay dan kesimpulan akhir berada di [PHASE_7_REVIEW.md](PHASE_7_REVIEW.md), terpisah dari output mesin immutable. Selisih subtotal mesin tidak membuktikan perbaikan.

## 1. Input dan pertanyaan penelitian

**FACT — input yang ditentukan pengguna:**

```text
/kaggle/input/datasets/chrisbiran/traffic-tracker-videos/TOR3-MALAM.mp4
```

[Bukti Phase 1](evidence/phase_1/20261011_TOR3/TOR3-MALAM/inspection_report.json) mengikat TOR3-MALAM ke SHA-256 `a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082`, ukuran 52.906.523 byte, resolusi 1280×720, dan 9.590 frame decoder. Notebook baru wajib memverifikasi file yang benar-benar tersedia, bukan menerima filename sebagai bukti identitas. Jangan menyimpan video asli di GitHub.

**FACT — observasi terdahulu:** [review visual Phase 1](evidence/phase_1/20261011_TOR3/TOR3-MALAM/manual_review.json) mendukung gelap, silau lampu, sebagian blur, dan teks kanan bawah yang mengganggu visibilitas. Efeknya pada detector/tracker/ReID/counting belum ditetapkan oleh inspeksi tersebut.

**REQUIREMENT — pertanyaan Phase 7:** apakah enhancement tertentu memberi bukti yang lebih berguna untuk pipeline dibandingkan frame malam asli, dan regresi apa yang ditimbulkannya? Raw baseline selalu disertakan; kandidat boleh ditolak seluruhnya. Lihat [protokol kandidat](NIGHT_PREPROCESSING_EXPERIMENT.md).

## 2. Tahapan dan gate

| Tahap | Pekerjaan yang diizinkan | Syarat melanjutkan |
|---|---|---|
| 7A — persiapan dan screen DEV | Verifikasi input/runtime, sampel berurutan, raw versus satu transform, gambar before/after, dan inferensi YOLO26M pada frame DEV yang dinyatakan eksplisit. Siapkan kandidat geometri N1. | Source/config/input terikat hash; tes software lulus; observasi DEV tersimpan. Tidak menyatakan tracker/counting sudah diuji. |
| 7B — review dan shortlist | N1/arah malam telah diterima untuk uji awal; review DEV memilih satu kandidat bagi pembanding raw dalam eksperimen temporal. | Shortlist/config dibekukan dari screen DEV saja; risiko/regresi DEV dicatat sebelum hold-out inference/outcome dibuka. |
| 7C — perbandingan temporal | Raw dan satu kandidat shortlist diproses dari frame 0 hingga 9589 dengan BoT-SORT/ReID dan counting B v1 + review, tanpa tuning simultan. | Kedua branch memakai seluruh 9.590 frame untuk konteks histori; episode/passage fisik, komponen, kategori, duplicate, sumber crossing, genuine return dan pending diaudit dengan bukti aktual. |
| 7D — hold-out dan keputusan | Review outcome DEV/hold-out dari run temporal yang telah dibekukan; simpan resource dan regresi. | Raw tetap pembanding; tidak mengubah kandidat sesudah melihat hold-out lalu menyebutnya hold-out yang sama. Pilih kandidat hanya bila bukti mendukung, atau pertahankan raw. |

**EXPERIMENT RESULT — gate execution:** screen 7A tidak menjalankan tracking, encoder ReID atau crossing/counting malam. Review N1/arah telah dipenuhi secara eksplisit untuk uji awal, bukan diasumsikan dari PAGI. Shortlist dan konfigurasi temporal dibekukan sebelum full-video inference baru; hold-out kemudian dieksekusi dengan recipe serta kontrol yang sama tanpa retuning. **REQUIREMENT — gate keputusan:** pemilihan konfigurasi membutuhkan review outcome temporal/hold-out, regresi dan biaya aktual. Rujuk [review akhir](PHASE_7_REVIEW.md) untuk penilaian gate; keberhasilan execution atau satu event accepted mesin tidak menetapkan konfigurasi produksi.

## 3. Sampel dan pengendalian kebocoran

**ENGINEERING EXPERIMENT:** anggaran awal adalah tiga segmen DEV dan dua segmen hold-out, masing-masing 240 frame berurutan. Panjang ini adalah anggaran eksperimen, bukan threshold lifecycle atau jaminan mencakup seluruh passage. Frame sumber, status split, konteks sebelum/sesudah, dan frame screen harus dinyatakan dalam manifest/config sebelum inference. Screen berbasis frame bukan benchmark temporal.

Plan v1 disimpan di [sampling/TOR3-MALAM_sampling_plan_v1.json](evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json): DEV `0–239`, `2277–2516`, `7072–7311`; hold-out `4674–4913`, `9350–9589`, seluruhnya inclusive. Screen 7A memakai tepat 15 frame DEV: `[0,7,14,29,239,2277,2337,2397,2457,2516,7072,7132,7192,7252,7311]`. Ini lima frame screen per segmen, bukan execution penuh 720 frame DEV atau 1.200 frame plan.

Review geometri memakai [N1 kandidat historis](evidence/phase_7/geometry_proposals/TOR3-MALAM-N1.json), [gambar N1](evidence/phase_7/geometry_proposals/TOR3-MALAM-N1.png), dan [alignment DEV](evidence/phase_7/geometry_proposals/TOR3-MALAM-N1_alignment.png). Proposal historis tetap immutable; [N1 accepted terpisah](evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json), SHA-256 `89ff1d6201fba37d6edb9501f1524a5c96781ff1b9f442f25b728cb4d543c7a4`, merekam persetujuan uji awal dan A→B=mendekati/B→A=menjauhi kamera TOR3-MALAM. Ini tidak membuktikan alignment kontinu, seluruh passage atau parameter produksi. Raw hold-out ikut inventory/sanity review saat membangun plan; enhancement dan inference hold-out tidak dipakai untuk pemilihan kandidat.

Segmen dipilih tanpa memakai hasil model/enhancement yang hendak dibandingkan. Saat passage berada di batas segmen, tandai bukti tidak lengkap; jangan menerima count atau menyimpulkan missed crossing dari konteks yang belum tersedia. Passage yang sama tidak boleh masuk DEV dan hold-out. Memindahkan batas untuk memenuhi konteks harus menghasilkan versi manifest baru dengan alasan sebelum eksperimen yang bergantung padanya.

**FACT — batas hold-out:** video dan beberapa posisi representatif sudah terlihat pada Phase 1; builder plan juga membuka raw temporal sheets kedua hold-out. Hold-out ini berarti hasil enhancement/inference tidak digunakan untuk pemilihan parameter/kandidat Phase 7, bukan piksel yang belum pernah dilihat atau blind benchmark independen. Segmen lain dari satu video juga bukan bukti generalisasi lintas malam/lokasi.

**ENGINEERING EXPERIMENT — konteks temporal lengkap:** tahap 7C memilih seluruh video 9.590 frame per branch, bukan mereset tracker pada masing-masing window 240 frame. Ini mempertahankan entry/origin, gallery dan histori sebelum passage yang sudah hadir di batas window. DEV/hold-out tetap scope pemilihan dan review, bukan lima video independen. Offline whole-vehicle-episode category dan state longitudinal dapat memakai konteks di luar window termasuk frame hold-out; shortlist dibekukan sebelum konteks model tersebut tersedia dan tidak dituning ulang berdasarkan outcome hold-out.

**REQUIREMENT — scope counting temporal:** subtotal accepted dibatasi lima window sampling yang sudah diumumkan (`0–239`, `2277–2516`, `4674–4913`, `7072–7311`, `9350–9589`). Track IDs ditemukan dari emitted measurements dalam window tersebut secara terpisah per variant; seluruh source sebelumnya tetap dipertahankan untuk episode/origin/return/raw-competitor guards. Jangan mengganti window/ID selection untuk menaikkan accepted sesudah melihat outcome. Inference/tracking full-video tidak berarti subtotal scoped ini adalah total traffic seluruh video.

## 4. Kontrol pipeline

**ENGINEERING EXPERIMENT — detector:** pertahankan asset resmi YOLO26M dan kontrol Phase 2 yang tercatat dalam [status detection](YOLO_DETECTION.md). Asset `yolo26m.pt` SHA-256 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`, Ultralytics `8.4.175`, `conf=0.25`, `imgsz=640`, `iou=0.7`, `max_det=300`, `batch=1`, `rect=True`, tanpa filter class/ROI, FP32, dengan backend `end2end=False` yang harus diverifikasi saat execution. Device dipilih eksplisit; catat runtime yang benar-benar hadir dan jangan menganggap dua GPU berarti dua GPU dipakai. Standard resize/letterbox/normalisasi model tetap berlaku pada raw baseline.

**DECISION — counting:** gunakan B v1 + overlay review terpisah dan hasil offline; unresolved tetap pending. Bekukan kontrol component center `0.51`, motion `0.15`, common/consecutive `3/3`, BC-inside fraction `1.0`; duplicate IoU `0.59`, center `0.10`, motion `0.01`, common/consecutive `2/2`; neutral band `0`, confirmation `1`. Ini kontrol eksperimen Phase 6, bukan parameter produksi. [Konfigurasi Phase 6](evidence/phase_6/config/TOR3-PAGI_option_b_v1.json) menjadi referensi policy, **bukan konfigurasi input malam**: SHA/cache/geometry, ID kasus, window, parent run dan metadata PAGI harus diganti dengan evidence malam aktual. Jangan memakai 13 ID pagi sebagai populasi malam.

**REQUIREMENT — semantic gate:** unit motorcycle termasuk rider/passengers; raw person tidak otomatis pedestrian. Crossing hanya dari raw detector-linked emitted vehicle BC, finite line dan measured geometry valid. Review tidak memperbaiki crossing gap/endpoint/prediksi; kategori yang disepakati tidak menutup konflik identitas. Genuine return memerlukan episode passage terukur yang terpisah dan review; pergantian ID saja bukan bukti return. Pickup/minivan/bus/angkot yang tidak memiliki pemetaan bisnis tetap pending. Riwayat hasil pagi tidak ditambahkan ke subtotal malam.

**OPEN — ReID final; ENGINEERING EXPERIMENT — kontrol temporal:** ReID tetap bagian arsitektur dan kandidat vehicle-ReID final belum dipilih. Tahap temporal memakai dedicated person-domain encoder resmi yang sudah diverifikasi pada Phase 4 sebagai kontrol eksperimen sama antarkondisi; penolakan sebelumnya sebagai vehicle default tetap berlaku. Policy dibekukan: **encoder menerima native/transformed frame yang sama dengan detector pada branch-nya** (`SAME_TRANSFORMED_FRAME_AS_DETECTOR`). Eksperimen mengubah satu faktor enhancement pada seluruh pipeline; kontribusi detector versus appearance tidak dapat dipisahkan dari perbandingan ini. Tidak mengimplementasikan encoder baru atau mengklaim vehicle effectiveness tanpa eksperimen tersendiri.

**FACT — referensi tracker teruji:** [Phase 4 report](evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_report.json) merekam BoT-SORT Ultralytics `8.4.175`, `track_high_thresh=0.25`, `track_low_thresh=0.1`, `new_track_thresh=0.25`, `track_buffer=30`, `match_thresh=0.8`, `fuse_score=True`, `gmc_method='none'`, `proximity_thresh=0.5`, `appearance_thresh=0.8`, dan dedicated encoder pada varian on. [Run malam aktual](evidence/phase_7/temporal/20261014T062858_002323Z/report.json) kemudian menggunakan kontrol tersebut pada raw/gamma dengan actual CUDA encoder evidence; penggunaannya tidak menetapkan threshold optimum atau final vehicle-ReID. Detector `conf=0.25` tidak menyimpan box di bawah nilai itu, sehingga tidak membuktikan manfaat seluruh low-confidence second-stage range tracker.

## 5. Berkas dan cara menjalankan screen

- [Notebook 07](../notebooks/07_night_preprocessing.ipynb): konfigurasi input, dependency/device verification, guard software, lalu mode photometric atau detector screen.
- [Helper Phase 7](../notebooks/phase_7_night_helpers.py): recipe, schema/stage/sample guards, decode DEV, detector adapter dan retained outputs.
- [Tes Phase 7](../notebooks/phase_7_night_tests.py): fixture software, bukan hasil model atau review video.
- [Config screen v1](evidence/phase_7/config/TOR3-MALAM_screen_v1.json): video/sample hash, recipe dan kontrol detector eksplisit.
- [Sampling plan](evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json) dan [N1](evidence/phase_7/geometry_proposals/TOR3-MALAM-N1.json): input plan dan usulan review.
- [N1 accepted](evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json) dan [feedback](evidence/phase_7/feedback/N1_review_001.json): keputusan uji awal, terpisah dari proposal asli.
- [Helper temporal Phase 7](../notebooks/phase_7_temporal_helpers.py) dan [tes temporal](../notebooks/phase_7_temporal_tests.py): pipeline baru full-video dua branch dengan source-bound counting adapter; hasil model belum diasumsikan dari adanya code.
- [Notebook 07b](../notebooks/07b_night_temporal_comparison.ipynb), [config temporal](evidence/phase_7/config/TOR3-MALAM_temporal_v1.json), dan [shortlist DEV](evidence/phase_7/selection/TOR3-MALAM_DEV_shortlist_v1.json): source/config/selection dibekukan sebelum execution aktual.
- [Screen run](evidence/phase_7/screening/20261014T060849_366767Z/report.json) dan [temporal run](evidence/phase_7/temporal/20261014T062858_002323Z/report.json): retained result/config/source/manifest dari execution aktual. Video asli dan model weights tidak dimasukkan ke GitHub; identitasnya tetap terikat hash dan asset URL.

Di Kaggle, buka notebook 07, mount dataset yang berisi path TOR3-MALAM, dan sediakan source/config repo sesuai bootstrap notebook. Pertahankan `VIDEO_PATH`, `CONFIG_PATH`, dan `SAMPLING_PLAN_PATH` eksplisit. Mode awal `MODE='photometric_only'` tidak memuat YOLO; untuk screen model gunakan `MODE='detection_screen'`, GPU aktif, device eksplisit, pinned Ultralytics terverifikasi, lalu restart kernel dan **Run All**. Dua mode menghasilkan run berbeda; photometric-only tidak menyatakan model sudah diuji. Notebook 07 menyediakan screen, sementara temporal/counting menggunakan notebook 07b dengan guard tersendiri.

Screen 07 tetap artifact screen terpisah. Tahap temporal memakai notebook/helper baru, shortlist terikat hash dan accepted N1; tidak menjalankan tracking dari lima foto screen atau menyulap sparse predictions menjadi cache continuous.

Codex dapat menjalankan guard/recipe dan decode source yang benar-benar tersedia. Screen model hanya boleh dilaporkan setelah CUDA/runtime dan inference aktual terverifikasi; jangan mengganti device CPU diam-diam untuk mengaku Kaggle GPU. GPU unavailable adalah alasan scope belum dieksekusi, bukan hasil eksperimen negatif terhadap enhancement.

## 6. Bukti, validasi dan penyelesaian

Sebelum inference aktual, validasi transform/schema/sample guard/input identity/source hashes. Simpan per-run configuration, runtime/devices, semua frame screen yang diumumkan, raw/enhanced source references, output deteksi mentah, before/after, timing/resource aktual, error dan batas review. Raw baseline tidak boleh dimodifikasi in-place.

Pada tahap temporal, simpan cache deteksi/tracks, episode/candidate provenance, machine decisions, input review, reviewed snapshot, event/aggregate reconciliation, dan tabel **per passage fisik**. Track ID lintas variant boleh berbeda; jangan memasangkan passage lewat kesamaan angka ID. Review wajib mencakup salah gabung, duplicate, unit/rider, kategori, crossing source, gap, visibility serta regresi. Pending turun, confidence naik atau gambar terang sendiri tidak cukup untuk memilih kandidat.

**ENGINEERING EXPERIMENT — adapter provenance:** helper B v1 asli tetap immutable dan dimuat dari source SHA `18949e7a44b6d73b9d50269f9d4569fbda781ba48269046b982287376ec3f054`. Adapter Phase 7 hanya mengganti satu literal validasi provenance `retained_phase_2_detection` menjadi `retained_phase_7_detection` untuk cache baru; tidak mengganti algoritme episode/geometri/group/category/return atau tuning angka. Simpan exact adapted source, base/adapted SHA, substitution count dan version mapping tiap run. Cache malam memuat actual new source detections, bukan relabel evidence pagi.

**REQUIREMENT — acceptance Phase 7:** controlled raw-versus-candidate pada sampel yang sama, retained before/after, observasi detector serta perilaku temporal/counting yang benar-benar diuji, evaluasi hold-out yang dibekukan, resource yang tersedia, keputusan kandidat/raw beserta limitations. Screen 7A selesai tidak berarti seluruh Phase 7 selesai. Jika gate/model/resource belum tersedia, laporkan bagian tersebut belum dieksekusi dan jangan isi hasil buatan.

**FACT — batas evaluasi:** tidak ada ground truth formal. Tes deterministik dan rekonsiliasi memvalidasi software; pixel review adalah audit terbatas. Tidak melaporkan accuracy, precision, recall, F1, MAPE, tracking/counting accuracy, atau klaim kelengkapan trafik.

**EXPERIMENT RESULT — hasil mesin dan biaya scoped:** kedua hold-out (`4674–4913`, `9350–9589`) memuat masing-masing satu kandidat pending pada raw maupun gamma; accepted mesin hold-out sama-sama 0. Enam kandidat DEV menghasilkan raw 0 accepted/6 pending dan gamma 1 accepted/5 pending. Ini hasil keputusan mesin pada delapan kandidat, bukan inventaris lengkap semua passage fisik. Loop sequential terinstrumentasi tercatat raw `673,549` detik dan gamma `1.205,209` detik (sekitar `1,79×`); transform raw `3,337` detik dan gamma `450,340` detik. Encoder sudah termasuk waktu tracker, sehingga tidak dijumlahkan lagi. Urutan raw lalu gamma, warmup dan instrumentasi membatasi interpretasi timing; ini bukan benchmark produksi. Angka review final, regresi serta keputusan kandidat harus dibaca pada [PHASE_7_REVIEW.md](PHASE_7_REVIEW.md).

**SCOPE:** tidak menjalankan Phase 8 delapan-video, Phase 10 refactor `src/`, UI, Docker/VM, multi-GPU orchestration, GMC/stabilisasi, retraining atau tuning deduplikasi bersama enhancement. Evidence Phase 1–6 tetap immutable. Hasil pagi dan malam adalah snapshot berbeda; tidak dijumlahkan silang.
