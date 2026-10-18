# B v2 — geometri pengguna, counting dan log passage

**Status 18 Oktober 2026:** kode dan replay CPU lokal delapan video selesai; annotated video sedang dijalankan dalam [notebook Kaggle B v2](https://www.kaggle.com/code/chrisbiran/phase-8-tgdi-b-v2-review). Status terminal dan tautan video aktual akan dicatat setelah output tersedia. Eksekusi baru memakai cache model Phase 8 yang sudah selesai, tanpa inference YOLO/BoT-SORT/ReID ulang.

[Notebook sumber](../../notebooks/08b_counting_b_v2_replay.ipynb) · [Kontrak yang diterapkan](../../docs/B_V2_COUNTING_CONTRACT.md) · [Geometri delapan video](config/geometry_manifest.json) · [Policy eksplisit](config/policy.json) · [Input asli pengguna](input/TGDI-WEEKDAY-PAGI-geometry-review.json)

Geometri native 640×480 memakai margin 25px per sisi (pita 50px). Clock 60 frame dimulai ulang setiap pengukuran di polygon asal. Jalur garis, polygon setelah occlusion tanpa sampel pita, serta timeout estimasi mempunyai log berbeda. Passage balik yang sah boleh dihitung lagi; upgrade bukti satu passage tidak menambah event kedua. Motorcycle+rider menjadi satu bbox tampilan ketika relasi komponen didukung, dengan BC kendaraan mentah tetap sebagai anchor.

## Hasil replay lokal aktual

Seluruh 72.590 frame direplay dari cache yang SHA-nya terverifikasi. Total operasional **3.717** terdiri dari **898 crossing terukur dan 2.819 inferensi**. Berdasarkan jalur: **1.024 LINE_MARGIN** (termasuk 126 yang crossing-nya tidak terlihat kontinu), **26 OCCLUSION_DIFF_POLYGON**, dan **2.667 ESTIMATED_TIMEOUT**. Angka ini hasil aturan yang diminta, belum jumlah kendaraan fisik yang tervalidasi. Kontribusi timeout yang besar perlu diaudit; penambahan event otomatis tidak membuktikan peningkatan akurasi.

| Video | Operasional | Terukur | Inferensi | Timeout | Baris pending |
|---|---:|---:|---:|---:|---:|
| weekday_pagi | 526 | 137 | 389 | 371 | 17 |
| weekday_siang | 613 | 122 | 491 | 465 | 102 |
| weekday_sore | 466 | 116 | 350 | 328 | 40 |
| weekday_malam | 394 | 83 | 311 | 285 | 6 |
| weekend_pagi | 440 | 121 | 319 | 308 | 15 |
| weekend_siang | 477 | 136 | 341 | 333 | 11 |
| weekend_sore | 493 | 129 | 364 | 352 | 49 |
| weekend_malam | 308 | 54 | 254 | 225 | 4 |

Pending B v2 dimaksudkan sebagai keputusan per unit/passage. Audit aktual menemukan **244 baris pending untuk 242 kunci unit/passage berbeda**: dua kunci di weekend_sore mempunyai baris diagnostik berulang. Laporan eksekusi asli dipertahankan; keterbatasan ini dicatat, bukan dihapus dari bukti. Angka tersebut tidak dapat dibandingkan langsung sebagai persentase perbaikan terhadap 1.825 diagnostik/kandidat B v1. Kasus kehadiran awal tanpa bukti passage atau yang belum selesai di akhir video tetap ada dalam open_passage_diagnostics, bukan disembunyikan sebagai nol. Semua snapshot B v1 tetap terpisah.

**Kasus yang perlu direview:** [kendaraan di tepi kanan dan dua estimasi timeout](review/timeout_edge_car/review.md), ID 2/frame 76 dan ID 34/frame 201. Enam sampel aktual memperlihatkan kendaraan serupa di dekat bangunan yang sama; kedua event tidak mempunyai crossing/pita/destination yang teramati. Dugaan kendaraan diam serta fragmentasi ID memerlukan review kontinu, bukan disimpulkan sebagai ground truth.

[Ringkasan aktual lokal](execution/local_replay_summary.json) dan arsip byte laporan/event beserta source_snapshot berada di execution/. Manifest retensi mengikat bytes asal dan gzip tersimpan. Ini bukan eksperimen ablation satu faktor: geometri dan beberapa aturan counting berubah bersamaan.

## Preview aktual panel baru

- [Crossing garis, frame 110](previews/TGDI-WEEKDAY-PAGI-LINE_MARGIN-frame-110.png)
- [Occlusion polygon, frame 326](previews/TGDI-WEEKDAY-PAGI-OCCLUSION_DIFF_POLYGON-frame-326.png)
- [Timeout estimasi, frame 76](previews/TGDI-WEEKDAY-PAGI-ESTIMATED_TIMEOUT-frame-76.png)

Preview berasal dari frame TGDI aktual dan hasil B v2, dengan hash pixel sumber diperiksa. Log berada **di bawah passage accepted dan di atas pending**. Panel memisahkan measured/inferred, jalur LINE/POLYGON/TIMEOUT, ID/kategori/arah, serta revisi +0/pembatalan −1. Label CHANGE_ID pada timeout tetap ditandai estimasi; pergantian ID tidak dianggap terbukti.

## Menjalankan ulang di Kaggle

Notebook khusus CPU dipaketkan melalui:

```bash
python results/b_v2/verification/build_kaggle_bundle.py --repo-root . --output-dir /tmp/phase8-bv2-kaggle
```

Paket tidak berisi video, cache model, bobot, atau kredensial. Sumber Kaggle yang ditambahkan adalah dataset chrisbiran/tgdi-traffic-videos dan output notebook chrisbiran/phase-8-tgdi-full-video-research. Default VIDEO_IDS=None memproses delapan video; ['weekday_pagi'] menjalankan subset yang dilabeli subset. Output baru berada di /kaggle/working/results/phase_8_b_v2/<run_id>/.

Untuk cache lokal yang sudah diunduh dan diverifikasi:

```bash
python notebooks/phase_8_b_v2_batch.py --repo-root . --source-run-root /path/to/original/run --source-video-root /path/to/TGDI/videos --output-root /path/to/new/results
```

Jangan arahkan output ke input lama. Source/model caches diverifikasi sebelum replay; output run yang sudah ada tidak ditimpa. Hasil partial/error mempertahankan laporan dan tidak dinyatakan selesai.

## Validasi

Tiga suite menghitung 45 uji counting, 25 uji renderer, 15 uji batch; seluruh 85 lulus tanpa skip. Pengujian mencakup timeout/return, rekonsiliasi event, finite endpoints, sumber BC, kategori pita, raw detection linkage, bbox rider, dan encode/decode H.264 sintetis. Validasi packaging menguji 22 guard dan source 30 file. Uji ini memverifikasi software; tidak mengukur counting accuracy. Publisher terpisah mempunyai 20 uji offline dan tidak menjalankan ulang pipeline. Satu annotated video lokal penuh (weekday_pagi, 9.052 frame) juga selesai di-encode dan di-decode kembali; [laporan aktualnya](execution/local_annotation/annotation_report.json) terpisah dari batch replay tanpa render. Video publik harus memakai checksum output Kaggle aktual.
