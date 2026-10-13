# Phase 6 — review per passage Opsi A/B

**EXPERIMENT RESULT — 13 Oktober 2026:** uji sintetis, replay episode kendaraan dari cache TOR3-PAGI, dan perbandingan passage telah dijalankan. Opsi B memulihkan satu passage motorcycle1772/rider1774 secara otomatis, tetapi belum menyelesaikan duplikasi964/973 secara otomatis. Keputusan produksi untuk memakai resolusi otomatis tetap **OPEN**. Pending yang turun setelah review gambar bukan keberhasilan otomatis B.

## Bukti dan cakupan

- Notebook: [06b_identity_resolution_comparison.ipynb](../notebooks/06b_identity_resolution_comparison.ipynb).
- Konfigurasi final: [TOR3-PAGI_option_b_v1.json](evidence/phase_6/config/TOR3-PAGI_option_b_v1.json).
- Run final: [report.json](evidence/phase_6/20261013T104301_354775Z/report.json), [executed notebook](evidence/phase_6/20261013T104301_354775Z/06b_identity_resolution_comparison.executed.ipynb.gz).
- [Perbandingan per passage](evidence/phase_6/20261013T104301_354775Z/passage_comparison.md), [JSON](evidence/phase_6/20261013T104301_354775Z/passage_comparison.json), [CSV](evidence/phase_6/20261013T104301_354775Z/passage_comparison.csv).
- [Frame sumber dan pemetaan piksel](evidence/phase_6/option_b_temporal_review/sample_index.json), [review visual](evidence/phase_6/option_b_temporal_review/pixel_review.json), [visualisasi perbandingan](evidence/phase_6/20261013T104301_354775Z/comparison_visualizations/README.md).

Input adalah cache Phase4 `reid_on` yang terikat SHA-256: 10.282 frame, 48.228 observasi emitted yang terhubung ke raw detection, dan geometri G3 TOR3-PAGI 1280×720. Seluruh cache divalidasi dan dibagi menjadi episode sebelum memilih 13 ID dan enam window konfigurasi. B menghasilkan enam kandidat kendaraan untuk lima passage fisik yang diperiksa; asosiasi880/893 serta negative control880/892 diperiksa terpisah. Crossing kendaraan880 berada di luar window kasusnya, sehingga tidak dihitung dalam subtotal ini.

Replay memakai CPU dan raw bbox/BC retained. Tidak ada inferensi YOLO, BoT-SORT, encoder ReID, embedding baru, atau perubahan geometri. State machine geometri dijalankan pada episode kendaraan baru; ini memang diperlukan untuk menguji origin kendaraan setelah pergantian family. Decode video terpisah hanya menghasilkan gambar review aktual, tanpa model atau preprocessing malam. Timestamp frame/FPS adalah estimasi; PTS otoritatif belum tersedia.

## Hasil pada passage yang sama

| Passage fisik | A original / A_updated | B mesin v1 | B setelah review eksplisit | Sumber crossing B |
|---|---|---|---|---|
| Car1 | Accepted | Pending: identitas positif belum tersedia; competitor3 | Satu car, diterima melalui review gambar | Car1, origin0, 76→77 |
| Motorcycle923 + rider912 | Accepted | Pending: relasi positif otomatis berada setelah window passage | Satu motorcycle, diterima melalui gambar dalam window passage | Motorcycle923, origin5017, 5028→5029 |
| Skuter merah964/973 + rider967 | Satu motorcycle melalui973;964 pending | Kedua kandidat pending; duplikasi belum terselesaikan | Satu motorcycle melalui964;973 `duplicate_suppressed` | Motorcycle964, origin5122, 5128→5129 |
| Car1323 | Pending; A_updated mencatat kategori car dari pengguna | Pending; kategori car, identitas competitor kecil belum jelas | Tetap pending | Car1323, origin6257, 6257→6258; tidak menjadi CountEvent |
| Motorcycle1772 + rider1774 | Pending kendaraan;1774 ditolak sebagai komponen yang tidak dihitung sendiri | **Satu motorcycle otomatis** | Payload/event ID otomatis dipertahankan persis | Motorcycle1772, origin7716, 7721→7722 |

Subtotal accepted pada lima passage ini: **A=3; B mesin=1; B reviewed=4**. B reviewed berisi **tiga passage yang diterima melalui review gambar dan satu passage otomatis**. Ablation dengan episode yang sama namun pengelompokan dimatikan menghasilkan **0 accepted / 6 pending**. Perbedaan ini mendukung kontribusi relasi komponen pada kasus1772, tetapi tidak membuktikan reliabilitas umum.

Filter A memakai ID **dan** window crossing/confirmation yang sama: 14 item audit = 3 accepted + 4 pending + 7 rejected-komponen. Salah satu pending adalah gap lama923, bukan passage fisik tambahan yang diterima. Inventori notebook yang hanya memfilter ID merupakan konteks; comparator per passage menerapkan window secara ketat. Subtotal historis A untuk seluruh video tetap18 dan tidak digabung dengan event B. Hasil subset ini bukan total trafik video atau benchmark A/B.

## Empat pemeriksaan yang diminta

**Salah penggabungan.** Dua motorcycle880/892 terlihat berbeda dan tidak digabung; relasi `SAME_VEHICLE` ditolak oleh kontrol spasial/gerak. Car1 dan motorcycle3 pada frame60 juga berbeda secara visual. Alternatif yang belum dapat diinterpretasikan tetap UNKNOWN, bukan negative label buatan. Cakupan negatif ini terbatas; pedestrian yang berada di dalam bbox motorcycle dan dua motorcycle berdekatan masih memerlukan kasus nyata tambahan.

**Duplikasi.** Resolver belum menggabungkan964/973. IoU minimum0,598789 dan jarak pusat maksimum0,099887 memenuhi kontrol0,59/0,10, tetapi residual gerak relatif maksimum0,057293 pada5129–5132 melewati kontrol0,01. Kalibrasi positif duplikasi hanya memakai5129–5130. Ambiguitas parent rider967 membuat kedua kandidat pending, sehingga mesin tidak menghasilkan dua accepted events. Review gambar5122/5128/5129/5130 kemudian menyatukan keduanya menjadi satu passage; ini hasil review, bukan keberhasilan deduplikasi otomatis.

**Kategori.** Person/rider tidak ikut voting kategori motorcycle. Pergantian family person→vehicle memulai episode baru; label vehicle yang saling bertentangan tetap disimpan dan ditahan. User menetapkan1323 sebagai car untuk kasus ini; bbox car kecil detection index3/ID1336 di tepi van belum pasti kendaraan lain, bagian van, atau false detection. Menutup kategori tidak menutup identitas. Pemetaan bus/angkot, majority vote dan kategori produksi tetap OPEN.

**Sumber crossing.** Setiap CountEvent memakai BC dari bbox kendaraan mentah yang terhubung ke detection source. Tidak memakai bbox union, titik rider, prediksi atau interpolasi. Untuk1772, person pada7712 tidak diwarisi sebagai origin; motorcycle7713–7715 belum mempunyai origin ROI yang memenuhi aturan. Origin valid7716 dan crossing7721→7722 berbeda dari crossing rider1774 pada7717→7718. Review964/973 memilih crossing valid terawal kendaraan964 tanpa menyambung episode person5116.

## Metode dan kontrol eksperimen

Relasi `COMPONENT_OF` membedakan person pengendara dari unit kendaraan, sedangkan `SAME_VEHICLE` mengelompokkan dua episode kendaraan. Assignment rider harus mempunyai satu parent group. Duplicate group harus membentuk clique; rantai relasi transitif saja tidak cukup. Semua raw competitor, termasuk yang tidak emitted atau di luar daftar ID kasus, tetap diperiksa. Split episode karena family/gap tidak otomatis mengesahkan genuine return; passage sebelumnya, termasuk pending, tetap menjadi penghalang return yang belum direview.

[Kalibrasi retained](evidence/phase_6/option_b_calibration/README.md) memakai tiga pasangan komponen dan satu pasangan duplikasi development. Numeric controls dibekukan sebelum replay target1772/1774, dengan pembulatan eksplisit. Target tidak ikut derivasi angka, tetapi sudah dikenal dari feedback pengguna, sehingga bukan blind test. Tidak ada held-out duplicate positive. Kontrol common/consecutive frames, neutral band0 dan confirmation1 adalah kontrol eksperimen, bukan default produk.

Pada v1, bukti relasi positif harus memenuhi kontrol **di dalam origin–confirmation kandidatnya sendiri**. Graph relasi global tetap eksploratif. Kategori diperiksa atas **seluruh episode kendaraan/group**, termasuk observasi setelah crossing; ini kebijakan offline/noncausal yang dinyatakan eksplisit, bukan keputusan online. Tidak ada embedding penampilan per observation dalam cache. ReID tetap arsitektur target; eksperimen ini tidak menguji ulang kontribusi encoder maupun memilih konfigurasi ReID produksi.

## Koreksi dan jejak eksekusi

Run awal [20261013T103406_717807Z](evidence/phase_6/20261013T103406_717807Z/superseded_run_audit_note.json) menerima dua events, termasuk923 dengan relasi komponen yang baru memenuhi kontrol pada5116–5131. Bukti masa depan tersebut tidak cukup untuk mengesahkan passage5028→5029. Ini kesalahan gate temporal, lalu diperbaiki dengan policy v1 dan regression tests. Output serta source run awal disimpan sebagai **superseded**, tidak dihapus atau ditulis ulang. Angka threshold tidak diubah untuk membuat target lolos.

Run final v1 menyimpan source notebook/helper/tests, input/config/calibration, keputusan mesin, ablation, dan hash provenance. [A_updated](evidence/phase_6/option_b_a_updated_20261013/report.json) hanya menerapkan feedback pengguna dengan helper A yang sama:18 accepted /141 pending /7 rejected; accepted event IDs tidak berubah. [Review input B](evidence/phase_6/reviews/TOR3-PAGI_option_b_v1_reviewed.json) diterapkan melalui postprocessor terpisah, tanpa resolver/geometri/model replay. [Snapshot reviewed](evidence/phase_6/20261013T104301_354775Z/reviewed/report.json) baru dihitung dari typed accepted CountEvents, bukan menambahkan snapshot lama.

Validasi yang benar-benar dijalankan:

- [63/63 uji sintetis resolver/episode](evidence/phase_6/20261013T104301_354775Z/synthetic_test_results.json), termasuk rider ganda, salah parent, duplicate clique, class flip, gap, return, raw BC/source, dan relasi masa depan.
- [24/24 uji postprocessor review](evidence/phase_6/20261013T104301_354775Z/review_overlay_synthetic_tests.json), termasuk idempotensi, deduplikasi manual, sumber raw BC, kategori, missing-frame evidence, dan hard-block yang tidak boleh dipromosikan.
- Reproduksi kalibrasi15/15; pixel/source extraction126/126 atas32 frame unik yang benar-benar didecode, dengan20 gambar dibuka untuk review tujuh kasus.
- [653/653 pemeriksaan artefak independen](evidence/phase_6/20261013T104301_354775Z/independent_artifact_audit.json) lulus: hash, tautan raw detection, episode, bukti temporal, CountEvent, aggregate, A/ablation dan snapshot reviewed.
- [Comparator per passage](evidence/phase_6/20261013T104301_354775Z/passage_comparison.json) lulus309/309 pemeriksaan scope/hash/source/event; reproduksi JSON/CSV/Markdown identik. [Notebook source dan executed](evidence/phase_6/20261013T104301_354775Z/notebook_format_validation.json) valid menurut nbformat.

Software checks dan review terbatas tersebut tidak merupakan ground truth. Tidak ada klaim accuracy, recall, precision, F1, MAPE, kelengkapan trafik, atau perbaikan counting performance.

## Keputusan dan langkah berikut

**FACT/DECISION:** prinsip satu motorcycle bersama rider, source BC kendaraan, isolasi episode, passage-local identity evidence, dan pemisahan output machine/reviewed sudah konkret dan teruji pada scope ini. Opsi B tersedia sebagai resolver eksperimen yang memberikan proposal auditable.

**OPEN:** generalisasi pemisahan episode; cara menerima kendaraan tunggal tanpa komponen; threshold duplikasi yang tahan jitter tanpa menggabungkan kendaraan berbeda; kategori causal/online; genuine return; van1323/competitor kecil; konfigurasi vehicle-ReID final; serta ambang produk dan hasil lintas video/malam.

**PROPOSAL:** pertahankan audit gate A dan gunakan proposal B untuk membantu review. Sebelum memilih otomatisasi produksi, perluas kasus nyata positif/negatif duplikasi, dua motorcycle berdekatan dan pedestrian bukan rider; pisahkan development dan hold-out, bekukan kontrol baru lalu bandingkan per passage lagi. Untuk1323 diperlukan bukti temporal/crop tambahan yang dapat menjawab identitas competitor, bukan sekadar override kategori. Phase7 belum dimulai.

Untuk meninjau hasil sekarang, buka tabel per passage dan visualisasi di atas; tidak perlu menjalankan model atau notebook ulang. Reproduksi opsional CPU dari root repo memakai notebook06b, kemudian review overlay:

```bash
python docs/evidence/phase_6/option_b_verification/build_reviewed_comparison.py \
  --repo . \
  --run docs/evidence/phase_6/20261013T104301_354775Z \
  --reviews docs/evidence/phase_6/reviews/TOR3-PAGI_option_b_v1_reviewed.json \
  --output /tmp/tor3-pagi-option-b-reviewed-reproduction
```

Perintah terakhir hanya mereproduksi keputusan review retained; tidak menambah eksperimen maupun mengeksekusi video/model.
