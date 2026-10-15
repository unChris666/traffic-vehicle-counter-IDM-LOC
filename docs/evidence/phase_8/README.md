# Bukti Phase 8 — TGDI

**STATUS:** pengembangan dan persiapan input aktual; belum ada hasil counting delapan TGDI. Berkas ini memisahkan sumber video, pengujian perangkat lunak, persiapan notebook dan regresi teknis dari hasil traffic.

- [Otorisasi dataset pengguna](authorization/dataset_clarification_20261015.json) menetapkan path dan konvensi filename. [Manifest v1](config/batch_manifest_v1.json) mempertahankan snapshot persiapan yang belum disetujui. [Manifest research v2](config/batch_manifest_TGDI_G3_T1_v2.json) mengikat geometri/arah yang kemudian disetujui pada seluruh delapan sumber serta metadata lokasi yang dikonfirmasi unknown.
- [Inventory aktual](inventory/TGDI_actual_discovery.json) mengikat SHA delapan sumber, native dimensions, metadata, laporan dan proposal. [Source preparation](input_preparation/README.md) mendokumentasikan72.590frame hasil decode,56PNG native dan355/355 pemeriksaan. Video sumber berada di luar Git.
- [Delapan gambar G3-T1](geometry_proposals/TGDI_eight_video_G3_T1_overview.png) tetap disimpan sebagai proposal historis. Accepted geometry berada di direktori terpisah, terikat [feedback pengguna](feedback/TGDI_all_eight_user_confirmation_20261015.json).
- [Processing profile](config/processing_profile_v1.json) membekukan raw, YOLO26M/BoT-SORT/ReID dan kontrol Bv1. Notebook08 defaults `prepare`; tidak ada model atau hitungan traffic dari mode ini.
- [Pilot TOR3 full scope](cache_pilot/TOR3-MALAM-full-scope-v1/counting_report.json) mereplay cache lama pada CPU, bukan mengulang model:9.590frames,1.633episodes,7accepted otomatis motorcycle dan49pending. Ketujuhnya berbeda dari tujuh passage reviewed scoped Phase7; belum diaudit manual dan bukan hasil TGDI.
- [Pilot annotation](pilot_annotation/README.md) memeriksa penulisan serta decode ulang MP4 penuh dan menyimpan sampel PNG. MP4 berada sementara di luar Git; anotasi bukan ground truth atau audit fisik.
- [Baseline retention](baseline_retention/context_retention_mapping.json) mempertahankan bytes konteks Phase7 sebelum status berkembang. Source dan artefak eksperimen terdahulu tetapimmutable.

Validasi akhir menggunakan `verification/check_phase8_artifacts.py` dan manifest retensi pada direktori ini. Pemeriksa membaca bukti tersimpan, source, frame terpilih dan cache detector-linked; ia tidak menjalankan model, resolver atau state machine geometri. Jumlah check bukan metrik kualitas model.

Untuk status dan langkah eksekusi, baca [PHASE_8_REVIEW.md](../../PHASE_8_REVIEW.md). Missing/pending/unsupported tidak menjadi nol palsu; subtotal accepted menjelaskan passage pada rekaman yang diproses dan tidak diekstrapolasi menjadi traffic24jam.

## Persiapan Kaggle v1 yang selesai

[Eksekusi aktual](kaggle_submission/execution_record_v1.json) menyimpan10JSON asli dan log Kaggle: delapan sumber TGDI ditemukan, dua TeslaT4 terlihat melalui nvidia-smi,169tes lulus dan2tes pilot opsional dilewati. Seluruh9hash/ukuran artefak cocok dengan manifest retensi asli. Mode ini tidak menjalankan model/counting. [Source v1](source_retention/prepare_v1_source_manifest.json) diarsipkan byte-exact sebelum pengembangan research v2; kode/bundle lama tidak diubah untuk menyesuaikan hasil baru.

[Preflight v2](verification/TGDI_research_v2_full_source_preflight.json) memvalidasi ulang seluruh sumber dan native PNG geometri setelah persetujuan: ready=true,0isu. Persetujuan awal tidak membuktikan robustness seluruh video. Unknown bisnis tetapnull; metadatareview terikatdelapanSHA mengizinkan penelitian, dengan business_metadata_complete=false.

## Research job dimulai

[Submission v3](kaggle_research_submission_v3/submission.json) semula diperiksa RUNNING, lalu kernel versi1 berakhir ERROR pada gate delapan path sumber, sebelum model. [Log asli dan terminal binding](kaggle_research_run_v1_failure/execution_failure.json) mempertahankan kegagalan tersebut. Resolver runtime kini memeriksa delapan SHA aktual dan membuat salinan manifest yang hanya mengubah path; manifest/geometri/kontrol penelitian asli tetap. [Submission v4](kaggle_research_submission_v4/submission.json) diterima sebagai kernel versi2, teramati RUNNING saat startup. Paket334.694byte mematuhi batas1MB; delapan PNG byte-identical tetap berada pada dataset pendamping privat dan diverifikasi perSHA. Belum ada hasil counting delapan TGDI yang ditahan. [Current software checks](verification/current_software_validation.json) mengikat pengujian pada source terbaru; source/bukti delivery sebelumnya diarsipkan. Status scheduler tidak menjadi bukti inferensi CUDA atau progress frame; review hasil aktual dilakukan setelah keluaran tersedia.
