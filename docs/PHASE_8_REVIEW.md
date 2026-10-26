<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Phase 8 — status pengembangan TGDI

**STATUS — 15 Oktober 2026:** Phase8 dimulai atas instruksi pengguna. Persiapan input aktual dan implementasi notebook tersedia; pemrosesan/counting delapan video belum dinyatakan selesai. [Task](PHASE_8_TASK.md) menetapkan acceptance dan batas fase.

## Gate Phase 7

[Phase7](PHASE_7_REVIEW.md) memenuhi objektif eksperimen malam yang scoped. Raw dan gamma0.7 telah dibandingkan pada sumber dan kontrol yang sama, dengan bukti DEV/hold-out dan review terpisah. Raw dipertahankan sebagai baseline penelitian; eksperimen tidak mensyaratkan enhancement menang. Kedua cabang menerima tujuh passage yang sama setelah review, bukan total seluruh video. Temuan tersebut mengizinkan pengembangan Phase8 tanpa menyatakan parameter atau kualitas counting sudah final.

## Input aktual

Dataset baru adalah `/kaggle/input/datasets/chrisbiran/tgdi-traffic-videos`. Format nama yang dikonfirmasi pengguna memetakan tepat delapan TGDI ke weekday/weekend × pagi/siang/sore/malam. [Inventory](evidence/phase_8/inventory/TGDI_actual_discovery.json) dan [laporan persiapan](evidence/phase_8/input_preparation/README.md) mengikat SHA sumber, metadata dan gambar aktual.

Seluruh **72.590 frame** berhasil didekode; delapan video native **640×480**, dengan jumlah aktual sama dengan metadata framecount OpenCV. Estimasi durasi sekitar300,8–306,5detik berasal dari framecount/FPS, bukan analisis PTS. Persiapan artefak lulus355/355 pemeriksaan, termasuk hash/pixel56PNG native dan40 sampel awal yang didekode ulang secara independen. Video sumber tetap di luar Git.

## Implementasi

[Notebook08](../notebooks/08_end_to_end_batch.ipynb) dimulai dalam `MODE = 'prepare'`: discovery input, inventory runtime, readiness manifest, guard perangkat lunak dan retensi hasil persiapan. Mode ini tidak menjalankan model atau mengeluarkan subtotal traffic. [Notebook persiapan Kaggle](https://www.kaggle.com/code/chrisbiran/phase-8-tgdi-batch-preparation) memakai [bundle source terikat SHA](evidence/phase_8/kaggle_submission/source_bundle_manifest.json), dengan19berkas kode/config minimal dan tanpa video/modelweights. Notebook canonical GitHub dipertahankan verbatim setelah bootstrap; arsip submitted bukan klaim notebook output yang sudah dieksekusi.

Mode `run_batch` menggunakan raw, YOLO26M/Ultralytics8.4.175, BoT-SORT+ReID dan Bv1/b0_c1 yang dibekukan. Inference baru berurutan pada CUDA0 dengan state terpisah per video; jumlah GPU dilaporkan sesuai bukti. Tidak ada scheduler dua GPU. Scope counting adalah seluruh episode video, tanpa13ID/six-window PAGI atau lima window Phase7. Encoder person-domain tetap kontrol eksperimen; vehicle-ReID final masih terbuka.

Helper Phase8 membatasi penerimaan event pada keputusan, konfigurasi, geometri dan BC sumber yang cocok. Overlay review membuat snapshot terpisah tanpa mengubah hasil mesin, tanpa mengimpor review lama atau memperbaiki crossing invalid melalui kategori manual. Agregasi memilih tepat satu snapshot per input dan hanya accepted passage unik. Pending, slot gagal serta kategori unsupported tidak menjadi nol palsu. Pedestrian belum didukung oleh frozen Bv1; bus/angkot masih belum memiliki pemetaan yang cukup.

## Bukti eksekusi notebook persiapan

[Canonical nbclient lokal](evidence/phase_8/verification/canonical_prepare_execution.json) mengeksekusi sembilan sel canonical pada delapan sumber aktual:171/171 tes lulus, tanpa skip. [Kaggle v1 aktual](evidence/phase_8/kaggle_submission/execution_record_v1.json) menyelesaikan source bundle v1 pada dataset TGDI, dengan169tes lulus dan2tes pilot opsional dilewati karena cache TOR3 tidak dibundel. Dua TeslaT4 terdeteksi melalui nvidia-smi; ini bukan bukti dua GPU dipakai atau bukti inference baru.

10JSON output asli beserta log disimpan; seluruh9hash/ukuran pada manifest asli cocok. Gangguan HTTP502 selama retrieval telah dipulihkan, tanpa mengganti laporan dengan hasil rekonstruksi. V1 tidak menjalankan model/counting dan tetap menjadi snapshot persiapan yang blocked saat itu. [Arsip source v1](evidence/phase_8/source_retention/prepare_v1_source_manifest.json) mempertahankan metode yang benar-benar dieksekusi sebelum extension research v2.

## Replay teknis aktual tanpa model ulang

[Cache pilot TOR3-MALAM](evidence/phase_8/cache_pilot/TOR3-MALAM-full-scope-v1/counting_report.json) memakai seluruh9.590 records lama dan1.633 episodes dengan scope `track_ids=null`, `association_frame_windows=null`. Replay CPU aktual menghasilkan56 keputusan:7 accepted otomatis motorcycle dan49 pending; waktu resolver tercatat8,291detik. Tidak ada deteksi/tracker/encoder baru atau overlay review lama yang disalin.

[Anotasi penuh](evidence/phase_8/pilot_annotation/README.md) berhasil ditulis lalu didekode ulang untuk9.590frame; native PNG frame898 tersedia. Waktu render aktual78,503detik adalah biaya anotasi CPU, bukan kecepatan inference GPU. MP4 sementara tetap di luar Git. Pemeriksaan ini memverifikasi berkas/overlay, bukan kebenaran identitas fisik.

Ketujuh event otomatis berasal dari passage di luar lima window Phase7. Karena scope dan kendaraan berbeda, angka7 ini **bukan** tujuh passage reviewed Phase7, bukan bukti perbaikan dan bukan hasil TGDI. Accepted otomatis belum diaudit terhadap identitas fisik secara manual; pending tetap dikecualikan dari subtotal.

## Konfirmasi pengguna dan kesiapan research v2

Pengguna menyatakan nama lengkap toko/latitude/longitude **belum diketahui**, menerima garis/polygon G3-T1 untuk **uji awal pada semua delapan video**, dan mengonfirmasi **A→B mendekati kamera / B→A menjauhi kamera** untuk seluruhnya. [Feedback](evidence/phase_8/feedback/TGDI_all_eight_user_confirmation_20261015.json), accepted geometry dan review per-video disimpan terpisah dari proposal v1 yang tidak diubah.

[Manifest research v2](evidence/phase_8/config/batch_manifest_TGDI_G3_T1_v2.json) mempertahankan nama/koordinat null, dengan `research_only=true` dan `business_metadata_complete=false`. Pengakuan unknown harus terikat metadata review serta delapan identitas sumber; missing yang tidak diakui tetap memblok eksekusi. Ini mengizinkan eksperimen teknis tanpa mengarang metadata produk.

[Preflight aktual](evidence/phase_8/verification/TGDI_research_v2_full_source_preflight.json) menguji SHA, decode72.590frame, native dimensions, PNG review dan accepted geometry seluruh sumber: **ready=true, tanpa isu**. Belum ada hasil model TGDI dari preflight ini. Nama/koordinat bisnis, robustness temporal dan kategori/identitas produksi tetap terbuka.

Di frame representatif yang dibuka, map/teks bawah dapat menutup area ROI; beberapa truk menutupi koridor dan sampel malam menunjukkan glare/blur. Bukti gambar terbatas ini tidak menetapkan stabilitas seluruh video, angle kamera numerik atau kualitas model.

## Research delapan video — status eksekusi aktual

Paket research pertama ditolak Kaggle karena source harus **di bawah1MB**. Paket/diagnostik yang ditolak tetap dipertahankan. Transport kemudian memindahkan delapan PNG asli ke [dataset evidence privat](https://www.kaggle.com/datasets/chrisbiran/tgdi-phase8-geometry-evidence-v1), tanpa mengubah bytes, geometri, kode model atau kontrol counting. Paket baru328.853byte memverifikasi manifest asset, identitas sumber dan setiap PNG SHA sebelum materialisasi. Seluruh63berkas logis tetap identik dengan paket research sebelumnya; tiga tes transport negatif menolak dataset/manifest/PNG yang tidak cocok.

[Job research aktual](https://www.kaggle.com/code/chrisbiran/phase-8-tgdi-full-video-research) versi1 semula teramati RUNNING, lalu berakhir **ERROR**. [Log aktual dan review kegagalan](evidence/phase_8/kaggle_research_run_v1_failure/failure_review.json) menunjukkan gate sumber menolak seluruh delapan path manifest karena berkas tidak ditemukan pada mount tersebut. Model belum dijalankan. Ini kegagalan resolusi path; tidak membuktikan video rusak. [Submission v3](evidence/phase_8/kaggle_research_submission_v3/submission.json) dan observasi RUNNING awal tetap disimpan sebagai riwayat, dengan terminal binding terpisah.

Perbaikan mencari delapan video aktual berdasarkan SHA sumber, lalu memeriksa jejak nama berkas. Manifest asli tidak diubah; salinan khusus runtime hanya boleh mengganti `videos[*].source_path`. READINESS dan batch memakai salinan efektif yang sama, serta menyimpan pemetaan dan kedua SHA manifest. Sumber hilang, byte berbeda, duplikat atau assignment tertukar ditolak. [Bukti bootstrap](evidence/phase_8/verification/research_v4_source_mount_bootstrap_validation.json) memverifikasi 63 berkas logis dan delapan relokasi lokal tanpa model. Geometri, arah, model, parameter dan aturan counting tetap.

[Submission v4](evidence/phase_8/kaggle_research_submission_v4/submission.json) diterima sebagai **kernel versi2**; paket334.694byte memenuhi batas upload. Status awal aktual **RUNNING** merupakan status scheduler, **belum bukti jumlah frame atau GPU inference aktual**. API output saat startup belum mengekspos log/frame parsial. Tidak ada klaim subtotal TGDI, jumlah video selesai atau keberhasilan delapan pipeline sebelum output nyata tersedia.

[Validasi software current](evidence/phase_8/verification/current_software_validation.json) lulus **210/210 tanpa skip** pada checkout penuh setelah perbaikan path. [Preflight salinan runtime](evidence/phase_8/verification/research_v4_actual_full_source_preflight.json) memeriksa kembali delapan SHA, PNG geometri dan seluruh72.590frame: ready=true, tanpa isu. Paket research minimal mendaftarkan210tes:208lulus dan2tes cache TOR3 opsional dilewati. Source/model TGDI tidak dipakai sebagai hasil sintetis. Dependency installer mempertahankan empat pin eksperimen dan menyelesaikan published dependency requirements; konfigurasi/tracker/threshold tidak dituning. Source dan bukti delivery sebelum perbaikan diarsipkan terpisah, sehingga hasil pengujian lama tetap terikat versi kode aslinya.

Setelah job selesai, unduh dan validasi kedelapan output, cache/appearance records, anotasi, event/keputusan/audit queue, resource dan dua CSV. Kegagalan/partial/pending tetap eksplisit. **Objektif Phase8 end-to-end belum dinyatakan selesai pada status RUNNING ini.** Full manual audit tetap Phase9 dan belum dimulai. Metadata bisnis tetap belum lengkap meskipun proses penelitian diizinkan.

Tidak ada ground truth atau klaim accuracy/precision/recall/F1/MAPE. Phase9 audit menyeluruh dan fase modularisasi/UI/Docker/deployment belum dimulai. Bytes konteks dan seluruh bukti fase sebelumnya tetap dipertahankan melalui [arsip](evidence/phase_8/baseline_retention/context_retention_mapping.json).

## Pembaruan hasil aktual dan anotasi review — 15 Oktober 2026

Setelah snapshot startup di atas, kernel research versi2 selesai **COMPLETE**. Laporan output asli untuk run `20261015T083731_664817Z` menyatakan **8/8 video selesai, 72.590 frame**, dengan **58 accepted otomatis dan 1.825 kandidat pending**. Seluruh accepted berkategori motorcycle. Lima belas payload JSON yang diunduh cocok hash/ukurannya dengan manifest output asli; ringkasan dan byte laporan yang dipilih kini disimpan pada [baseline anotasi](evidence/phase_8_annotations/baseline/baseline_retention.json). Status hasil adalah `completed_research_snapshots_pending_audit`; subtotal ini belum menjadi jumlah kendaraan fisik yang tervalidasi.

Pengguna kemudian meminta panel kategori × arah, warna/label bbox, nomor frame dan penjelas unit/rider. [Notebook08a](../notebooks/08a_annotation_review.ipynb) merender ulang sumber/cache/keputusan tersimpan ke output terpisah, tanpa model atau resolusi counting baru. [Kontrak visual dan validasi](ANNOTATED_VIDEO_REVIEW.md) menjelaskan replay final offline, pemisahan kategori mentah/final, komponen `+0`, pending dan batas review. Pergantian ID setelah oklusi tetap terbuka; renderer tidak menyambung identitas baru.

[Arsip konteks sebelumnya](evidence/phase_8_annotations/baseline/context_retention_mapping.json) mempertahankan bytes dokumen pada delivery `467f3dc`; manifest/bukti eksekusi lama tetap utuh.

**Historis — anotasi selesai sebelum publikasi GitHub:** [terminal record](evidence/phase_8_annotations/kaggle_submission/execution_terminal_record.json) memverifikasi delapan output baru dan72.590frame, dengan subtotal58accepted/1.825pending tetap. Delapan salinan H.264 untuk review sudah siap dan SHA sumber/hasil dicatat terpisah, tetapi upload GitHub Release terblokir HTTP401 di uploads.github.com. Belum ada video di GitHub; output anotasi tersimpan pada versi notebook Kaggle, terpisah dari sesi interaktif. Lihat [status upload](ANNOTATED_VIDEO_REVIEW.md#status-upload-github). Ini pembaruan visual dan retensi, bukan perbaikan identitas atau audit fisik lengkap.

**Historis — pemeriksaan PAT 16 Oktober 2026 sebelum publikasi Actions:** environment revisi7 mengamati GH_TOKEN ready untuk api.github.com/ uploads.github.com. Uji upload checksum aktual ditolak HTTP403 “Resource not accessible by personal access token”; belum ada video di GitHub. [Bukti terbaru](evidence/phase_8_publication/credential_verification.json) dan [arsip konteks sebelumnya](evidence/phase_8_publication/baseline/context_retention_mapping.json) mempertahankan perbedaan dari kegagalan401 historis. Delapan output Kaggle tetap COMPLETE; unduhan besar dan eksekusi ulang model/counting tidak dimulai.

**Publikasi aktual selesai — 16 Oktober 2026:** delapan MP4 anotasi tersedia di [GitHub Release](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/tag/phase8-annotation-review-v1), bersama checksum, manifest delivery dan arsip audit. [Receipt aktual](evidence/phase_8_publication/success_20261016/final_publication_receipt.json) mengikat delapan berkas ke sumber Kaggle yang sama dan commit `7a403e18587d3b5561775181552967aaaff5b7f4`. Job memakai token native GitHub Actions setelah uji upload checksum; pipeline detector/tracker/ReID/counting tidak dijalankan ulang. Seluruh 72.590 frame dipertahankan, dengan 58 accepted/1.825 pending tetap. Kegagalan PAT 401/403 terdahulu tetap bukti historis, terpisah dari publikasi sukses. Review fisik menyeluruh tetap belum selesai.
