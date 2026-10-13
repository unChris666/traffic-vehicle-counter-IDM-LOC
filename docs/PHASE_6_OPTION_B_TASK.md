# Phase 6 — eksperimen resolusi unit Opsi B dan pembanding A/B

**USER AUTHORIZATION — 13 Oktober 2026, Asia/Jakarta:** pengguna meminta menjalankan urutan **uji sintetis pengelompokan komponen dan pemisahan episode → replay kasus TOR3-PAGI → bandingkan keputusan A/B per passage**. Perbandingan harus memeriksa salah penggabungan, duplikasi, kategori dan sumber crossing; penurunan pending saja tidak membuktikan perbaikan. Ini melanjutkan [proposal Opsi B](PHASE_6_OPTION_B_PROPOSAL.md), bukan izin untuk fase selanjutnya.

**FACT — baseline historis:** snapshot Opsi A `20261012T144625_030645Z` mempunyai 18 accepted passage, 141 pending audit items dan 7 rejected komponen pengendara. Angka itu berasal dari [review sebelumnya](PHASE_6_REVIEW.md); bukan hasil Opsi B, total lalu lintas lengkap, atau jumlah kendaraan unik. Pertahankan snapshot dan semua diagnostik Phase 1–5 tanpa perubahan.

## Task dan scope

Implementasikan resolver notebook yang terinspeksi untuk `COMPONENT_OF(person, motorcycle)` dan `SAME_VEHICLE(vehicle, vehicle)`, episode pengukuran kendaraan, kategori temporal, gate counting dan comparator per passage. Gunakan retained Phase 4 `reid_on` emitted-track records serta G3 dan kontrol geometri tersimpan. Tidak menjalankan kembali YOLO, BoT-SORT atau encoder ReID. Tidak membuat UI, `src/` refactor produksi, enhancement malam, GMC/stabilisasi, delapan-video processing atau multi-GPU.

**REQUIREMENT — read first:** `AGENTS.md`, `CODEX_WORKFLOW.md`, dokumen konteks/product/model/counting/architecture/API/config/test/evaluation/open decisions, [GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md), [COUNTING_CONTRACT.md](COUNTING_CONTRACT.md), [proposal](PHASE_6_OPTION_B_PROPOSAL.md), [feedback pengguna](evidence/phase_6/feedback/user_review_20261013_001.json), serta [kalibrasi terikat sumber](evidence/phase_6/option_b_calibration/README.md).

## Input, context dan scope replay

Input SHA/native-coordinate harus sama dengan baseline: TOR3-PAGI 1280×720, cache `reid_on`, diagnostik `b0_c1`, dan [G3](evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json). Pertahankan setiap frame, `raw_bbox`, raw label/confidence, original detection index, track dan source hash. Raw BC kendaraan tetap berasal dari bbox pengukuran asli; tidak memakai `center` tersimpan, Kalman bbox atau lifecycle prediction.

**ENGINEERING EXPERIMENT — case windows, inklusif:** `[[0,80], [4975,4980], [5011,5030], [5116,5132], [6256,6260], [7712,7725]]`. Jendela ini membatasi pemeriksaan hubungan dan output kasus, bukan mengubah histori track. Case IDs dalam konfigurasi hanya memilih audit source views; fungsi hubungan, reset, kategori dan counting tidak boleh mempunyai aturan khusus ID1772, ID1774, ID1323, ID964 atau ID973.

Ekstrak episode dari urutan **sumber penuh terlebih dahulu**, lalu hitung feature hubungan dalam case window. Jangan memotong input sebelum episode extraction atau mewarisi origin person sebagai origin motorcycle. Simpan konteks mentah penuh yang diperlukan untuk alternative/contradiction screening, termasuk raw detections yang belum emitted atau assigned-but-unconfirmed. Raw detections tambahan hanya bukti konflik; tidak menjadi trajectory atau count source. Kandidat alternatif tanpa pengukuran persistent yang cukup tidak otomatis dinyatakan kendaraan duplikat atau rider.

## Parameter dibekukan sebelum target

**ENGINEERING EXPERIMENT:** [frozen_thresholds.json](evidence/phase_6/option_b_calibration/frozen_thresholds.json) merupakan kontrol eksperimen, **bukan default produk**. File tersebut mengikat metode dan feature bytes melalui SHA. Kalibrasi menggunakan komponen 893/880, 912/923, 967/964 dan duplikat 964/973 pada window pixel review terbatas. ID1772/1774 dikecualikan dari perhitungan batas; nilai target tidak boleh digunakan untuk mengubah parameter lalu dilaporkan sebagai held-out.

| Gate | COMPONENT_OF: first person, second motorcycle | SAME_VEHICLE: pasangan kendaraan |
|---|---:|---:|
| Minimum common frames | 3 | 2 |
| Minimum consecutive common frames | 3 | 2 |
| Minimum first BC inside second bbox fraction | 1,0 | — |
| Maximum normalized center distance | 0,51 | 0,10 |
| Maximum normalized relative-motion residual | 0,15 | 0,01 |
| Minimum IoU | — | 0,59 |

Component center normalization memakai diagonal bbox motorcycle. Duplicate normalization memakai rata-rata diagonal kedua bbox sehingga simetris. Motion residual adalah perubahan **pixel relative-center offset** pada common frames berturutan, dibagi rata-rata normalization diagonal kedua frame; bukan selisih offset yang dinormalisasi masing-masing. Semua formula dan nilai per frame berada pada [pair_features.json](evidence/phase_6/option_b_calibration/pair_features.json).

Batas spasial/motion berasal dari maksimum positif yang dibulatkan ke atas 0,01; batas duplicate IoU berasal dari minimum positif dibulatkan ke bawah 0,01. Dukungan minimum 3/2 frame adalah engineering control eksplisit. Jangan menyajikan passing pada sampel pengembangan sebagai generalisasi. Duplikat 964/973 merupakan **development-only**, tanpa held-out duplicate positive. Pasangan alternatif kalibrasi tetap UNKNOWN; satu negative pixel yang sudah diketahui, ID1/3 pada frame60, merupakan kendaraan berbeda lintas kategori.

## Kontrak relasi dan ambiguity

**ENGINEERING EXPERIMENT — graph:** bedakan hubungan komponen rider/passenger dengan hubungan dua track kendaraan duplikat. Rider menjadi anggota unit; ia tidak menjadi count tambahan dan label person tidak mengubah kategori vehicle primary. Satu unit dapat mempunyai beberapa rider/penumpang.

Positive pair gates hanya membuka kemungkinan hubungan. `SAME_VEHICLE` tidak boleh menyatukan rantai A–B–C secara transitif ketika A–C tidak mendukung hubungan; periksa clique/kontradiksi sebelum menerima grup. Setiap person membutuhkan satu parent **vehicle group** yang memenuhi aturan. Beberapa parent berbeda yang lolos, parent switching, insufficient temporal evidence atau kontradiksi tetap unresolved; tidak memilih berdasarkan urutan track ataupun score margin yang belum ditetapkan.

Pertahankan alternatives dan reasons, termasuk calon pasangan yang gagal, serta input sumber yang diperiksa. Co-moving pedestrian yang berada di bbox motor dapat menyerupai feature rider: algoritme ini belum membuktikan dapat menyelesaikannya. Konflik identity/role yang belum selesai tidak masuk subtotal accepted.

**ENGINEERING EXPERIMENT — v1, dukungan lokal passage:** graph global hanya bukti eksplorasi. Untuk acceptance, feature positif component/duplicate dan setiap edge clique harus memenuhi frozen gates pada **measured origin–confirmation window kandidat sendiri**, termasuk minimum common/consecutive frames. Hubungan yang baru didukung sesudah confirmation tidak membuktikan identitas passage sebelumnya. Initial v0 `20261013T103406_717807Z` dipertahankan sebagai superseded karena melanggar batas temporal ini pada kasus 923; v1 mengoreksi policy tanpa mengubah nilai numerik kalibrasi.

## Episode, kategori dan geometri

**ENGINEERING EXPERIMENT — episode extraction:** perubahan unit-family atau observasi hilang menutup episode pengukuran sesuai policy eksplisit. Episode kendaraan baru hanya membawa raw vehicle observations sendiri dan membentuk origin eligible baru dari A/B. Simpan batas episode serta pengukuran yang dikeluarkan dan alasannya. Kebijakan berlaku universal sebelum menilai target crossing; tidak memilih sub-window karena ingin memperoleh count tertentu.

Tidak membuat bbox union, rata-rata anchor rider/motor, trajectory gabungan antar-ID, interpolasi gap ataupun origin kendaraan dari person. Resolusi identitas tidak memperbaiki pengukuran komponen yang salah. Perubahan kategori dalam vehicle family harus tetap terlihat sebagai category evidence/conflict; tidak boleh disembunyikan oleh pemilihan latest label.

**ENGINEERING EXPERIMENT — kategori temporal:** implementasi menggunakan unanimity raw category evidence pada **full vehicle episode/group**, termasuk observasi setelah confirmation bila ada. Ini policy **offline/noncausal** yang mencatat latest evidence frame; bukan keputusan kategori real time pada crossing. Person rider tidak ikut voting. Unanimity hanya interpretasi teknis eksperimental pada raw label yang didukung; bukan taxonomy bisnis baru, calibrated category confidence atau bukti bahwa semua minivan merupakan car. Mixed vehicle categories, unsupported classes dan taxonomy bus/angkot/pickup tetap membutuhkan resolusi atau pending. Geometri dan bukti identitas passage tetap memakai window terukur yang dinyatakan sendiri.

[Feedback ID1323=`car`](evidence/phase_6/feedback/user_review_20261013_001.json) adalah keputusan manusia untuk kasus tersebut. Bila digunakan pada kedua cabang, pengaruhnya dicatat sebagai human review, bukan keberhasilan klasifikasi otomatis. Feedback ID1772/1774 adalah reference evaluasi hubungan, bukan hardcoded feature result atau izin mengubah diagnostic lama menjadi accepted.

**REQUIREMENT — geometry preserved:** gunakan G3, raw measured BC, finite segment, neutral boundary dan aturan touch/endpoint/gap/prediction yang sudah diterima. Replay baru pada episode kendaraan menghasilkan diagnostic/candidate **baru**; historical hard-pending diagnostic tetap immutable. Kontrol `neutral_band_px=0` dan `confirmation_observations=1` tetap `b0_c1` engineering experiment, bukan parameter produksi. Acceptance membutuhkan origin terukur, complete continuous vehicle window, proper finite-line passage dan opposite-ROI confirmation. Relasi rider ataupun keputusan kategori tidak dapat mengatasi hard geometry.

## Counting dan pembanding yang disimpan terpisah

Pertahankan snapshot berikut dengan namespace konfigurasi, input review, source links dan alasan masing-masing:

1. **A original:** snapshot historis immutable.
2. **A updated human review:** penerapan feedback terbaru dengan gates Opsi A lama; person→vehicle hard block tetap berlaku.
3. **Episode-only ablation:** pemisahan episode tanpa menganggap hubungan otomatis sudah terpecahkan; pisahkan dampak recovery dari grouping/category.
4. **B machine:** resolver memakai frozen features/graph/category rules tanpa memasukkan jawaban kasus sebagai feature atau aturan ID.
5. **B reviewed:** resolusi manual yang benar-benar didukung evidence, disimpan terpisah dari hasil mesin.

Hitung satu event per physical unit/passage yang eligible, bukan per rider/raw ID/transisi. Pilih satu representatif kendaraan terukur secara deterministik dan simpan anggota sumber tambahan. Genuine return harus merupakan episode passage terpisah yang memenuhi kontrak; repeated rider recross atau dua ID pada kendaraan yang sama tidak otomatis passage baru. Pending/rejected/duplicate members tidak menambah accepted aggregate.

Guard return memeriksa seluruh passage lengkap sebelumnya pada sumber, termasuk yang masih pending atau berada di luar output case window. Family reset, gap atau ID unit baru tidak menghapus kebutuhan review return. `B_reviewed` merupakan overlay review terpisah yang tidak mengubah source measurements, machine decisions atau frozen gates; keputusan manual harus terikat hash evidence dan tidak dapat mempromosikan hard geometry/category/unit conflict.

Comparator harus menautkan keputusan **per passage dan per sumber crossing**, bukan mengurangkan jumlah item dua namespace yang berbeda. Laporkan perubahan origin/episode, sumber representatif, grouping, kategori, status/reasons, ambiguity dan raw evidence. Pisahkan target-case result dari total historis seluruh audit queue.

## Validasi, deliverables dan gate

**REQUIREMENT — synthetic first:** uji rider/passenger satu kendaraan, pedestrian dekat motor, dua motor berdampingan, co-moving alternatif, duplicate bbox, ambiguous parent, non-clique transitivity, urutan input, class flip, reset tanpa inheritance, gap/endpoint/prediction, initial presence, category conflict, genuine return dan idempotensi/aggregate reconciliation. Fixtures adalah bukti correctness software, bukan video ground truth.

Setelah guard lulus, jalankan retained-source case replay dan buka foto/temporal evidence actual. Bekukan parameter terlebih dahulu; kasus held-out ID1772/1774 dan pasangan alternatif dievaluasi setelahnya. Periksa salah gabung, duplicate/missed passage, kategori, source BC/origin/passage/confirmation, dan konflik pending pada window yang benar-benar dilihat. Penurunan pending atau kenaikan accepted saja tidak memenuhi gate. Bukti negatif video terbatas; synthetic negatives tidak menggantikan additional real review.

**Deliverables aktual:** `notebooks/phase_6_identity_resolution_helpers.py`, `notebooks/phase_6_identity_resolution_tests.py`, `notebooks/06b_identity_resolution_comparison.ipynb`, current config [TOR3-PAGI_option_b_v1.json](evidence/phase_6/config/TOR3-PAGI_option_b_v1.json), [final run evidence](evidence/phase_6/20261013T104301_354775Z/report.json), bounded visual evidence, review overlay serta [PHASE_6_OPTION_B_REVIEW.md](PHASE_6_OPTION_B_REVIEW.md). Config v0 dan run `20261013T103406_717807Z` tetap tersimpan sebagai sejarah superseded; jangan mencampur hasil v0/v1.

**EXPERIMENT RESULT — scope terbatas:** final v1 menjalankan guard 63/63 tes lalu replay kasus 13 IDs/enam window. `B_machine` mempunyai satu accepted motorcycle 1772/rider 1774 dan lima pending vehicle candidates; episode-only ablation mempunyai nol accepted/enam pending. [Overlay reviewed aktual](evidence/phase_6/20261013T104301_354775Z/reviewed/report.json) mempunyai empat CountEvents: tiga physical passages dikonfirmasi manual (car 1, motorcycle 923 dan satu motorcycle 964/973), serta satu event 1772 yang tetap persis dari mesin. ID973 ditekan sebagai anggota duplikat dan ID1323 tetap pending identity meski kategori kasusnya car. Ini subtotal kasus, bukan hasil full-video atau bukti superioritas otomatis B.

**FACT — appearance limit:** cache tidak menyimpan embeddings per observation. Resolver eksperimen tidak boleh mengklaim menggunakan feature appearance baru. Retained `reid_on` track provenance dan ReID sebagai arsitektur tetap dipertahankan; ekstraksi appearance tambahan merupakan eksperimen tersendiri.

**OPEN:** suitability threshold, taxonomy bisnis global, real same-category negative coverage, co-moving pedestrian ambiguity, whole-video completeness, vehicle-ReID final dan generalisasi video lain. Tidak ada formal ground truth: jangan melaporkan accuracy/precision/recall/F1/MAPE atau superioritas B. Hasil aktual, koreksi temporal dan batas acceptance didokumentasikan pada review terpisah; Phase 7 belum dimulai.
