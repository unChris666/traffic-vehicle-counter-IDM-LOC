# Penerimaan Phase 1 — inspeksi TOR3 pagi dan malam

**KEPUTUSAN — PASS dengan keterbatasan yang dicatat, 11 Oktober 2026.** Laporan yang dipertahankan memenuhi objektif Phase 1: memahami input nyata, menyimpan metadata dan sampling, serta mencatat pengamatan visual, kelayakan geometri, risiko, dan pertanyaan terbuka. Keputusan ini mencakup `TOR3-PAGI.mp4` dan `TOR3-MALAM.mp4`; bukan penerimaan semua video, pipeline model, atau sistem counting.

**REQUIREMENT — instruksi pengguna saat ini:** analisis laporan dan lanjutkan Phase 2 jika Phase 1 memenuhi objektif. Hasil PASS mengaktifkan otorisasi tersebut. Prinsip [CODEX_WORKFLOW.md](../CODEX_WORKFLOW.md) mengizinkan penyelesaian fase jika validasinya terpenuhi atau keterbatasan yang belum terselesaikan dinyatakan secara eksplisit.

## Bukti dan asal pengamatan

Laporan Kaggle diarsipkan tanpa perubahan byte:

- Malam, run `20261011T045747_511017Z_0564c6b2`: [Markdown](evidence/phase_1/20261011T045747_511017Z_0564c6b2/inspection_report.md), [JSON](evidence/phase_1/20261011T045747_511017Z_0564c6b2/inspection_report.json).
- Pagi, run `20261011T044339_967568Z_f02b4d6c`: [Markdown](evidence/phase_1/20261011T044339_967568Z_f02b4d6c/inspection_report.md), [JSON](evidence/phase_1/20261011T044339_967568Z_f02b4d6c/inspection_report.json).

**EXPERIMENT RESULT — audit laporan, bukan eksekusi video baru:** kedua pasangan MD/JSON konsisten pada run, identitas input, metadata, 21 observasi, jenis klaim, dan referensi bukti. Nama, ukuran, SHA-256 video, jumlah frame, indeks sampling, dan kamus review cocok dengan [arsip inspeksi Codex sebelumnya](evidence/phase_1/20261011_TOR3/README.md).

`review_provenance` menyatakan bahwa pengamatan AI-assisted berasal dari inspeksi visual sebelumnya di Codex atas video yang diunduh melalui Kaggle API. Pengamatan diterapkan pada run Kaggle dengan input dan sampling yang cocok. Ini bukan review visual manusia baru di Kaggle. Arsip pembanding memuat [contact sheet pagi](evidence/phase_1/20261011_TOR3/TOR3-PAGI/contact_sheet.png), [contact sheet malam](evidence/phase_1/20261011_TOR3/TOR3-MALAM/contact_sheet.png), serta [sheet berurutan pagi](evidence/phase_1/20261011_TOR3/TOR3-PAGI/consecutive_beginning.png) dan [malam](evidence/phase_1/20261011_TOR3/TOR3-MALAM/consecutive_beginning.png).

Empat unggahan terbaru berisi laporan, bukan PNG/preview/manifest asli dari run Kaggle terbaru. Audit ini memeriksa rekaman referensinya; tidak memverifikasi ulang keberadaan atau kesetaraan piksel artefak Kaggle tersebut secara independen. Identitas byte video unggahan awal tetap belum dibandingkan dengan video unduhan Kaggle, sebagaimana dicatat provenance.

## Metadata yang didukung laporan eksekusi

| Video | Ukuran berkas | Resolusi / rasio turunan | Codec | Durasi stream | FPS rata-rata | Frame metadata / decode pertama / decode kedua |
|---|---:|---|---|---:|---:|---|
| TOR3-MALAM | 52.906.523 byte | 1280 × 720 / 16:9 | H.264 | 325,969067 detik | 29,419970 | 9.590 / 9.590 / 9.590 |
| TOR3-PAGI | 53.173.467 byte | 1280 × 720 / 16:9 | H.264 | 344,859778 detik | 29,815017 | 10.282 / 10.282 / 10.282 |

SHA-256 input yang direkam:

- Malam: `a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082`.
- Pagi: `606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c`.

**EXPERIMENT RESULT — runtime yang dilaporkan:** Python 3.12.13, empat CPU tersedia, OpenCV 4.13.0, NumPy 2.0.2, Pillow 11.3.0, IPython 7.34.0, FFmpeg/ffprobe 4.4.2. `nvidia-smi` berhasil dan merekam **dua Tesla T4**, masing-masing 15.360 MiB, driver 580.178.04. Ini membuktikan inventaris GPU yang dilaporkan, belum kompatibilitas CUDA, PyTorch, Ultralytics, atau YOLO26M; bukan hasil beban GPU atau alasan memakai dua GPU pada prototipe ini.

## Checklist objektif Phase 1

| Objektif | Bukti yang diaudit | Penilaian / batas |
|---|---|---|
| Verifikasi lingkungan | Versi Python/dependensi, CPU, probe GPU, FFmpeg/ffprobe | Terpenuhi pada kedua laporan; bukan validasi model. |
| Discovery dataset | 13 kandidat dengan path, ekstensi, ukuran, dan metadata | Terpenuhi; bukan 13 inspeksi visual atau bukti kelengkapan delapan video target. |
| Satu input eksplisit per run | `configuration.video_path` dan `input_identity` | Terpenuhi; pagi dan malam merupakan run terpisah. |
| Metadata input nyata | Nama, dimensi, FPS, jumlah frame, durasi, codec beserta asal nilai | Terpenuhi; FPS rata-rata tidak disamakan dengan FPS konstan. |
| Sampling representatif | Lima posisi awal/25%/50%/75%/akhir dan contact sheet direkam | Terpenuhi menurut laporan; berbasis indeks frame, bukan persentil waktu terverifikasi. |
| Bukti temporal | Lima burst tersimpan, masing-masing 30 frame berurutan; 150 frame unik per video | Terpenuhi menurut laporan; daftar indeks hilang kosong dan referensi konsisten. |
| Review visual | 21 observasi terisi, masing-masing memiliki referensi bukti | Terpenuhi; 16 klaim visual AI-assisted, empat hipotesis belum diuji, satu pertanyaan OPEN. |
| Kestabilan kamera | Kategori `effectively_stationary` dengan manifest burst; pagi juga merujuk pasangan frame berurutan | Penilaian kualitatif pada sampel; bukan jaminan sepanjang durasi. |
| Pertimbangan malam | Gelap, silau, blur/visibilitas dan risiko model dicatat | Terpenuhi; tidak ada enhancement atau hasil model. |
| Kelayakan geometri | Kelayakan per-video dan alignment sampel dijelaskan | Terpenuhi sebagai penilaian visual; koordinat, anchor, serta label A/B masih OPEN. |
| Laporan dan disiplin klaim | Metadata, pengamatan, risiko, pertanyaan, serta keterbatasan direkam | Terpenuhi; tidak ada benchmark, ground truth, atau hasil counting. |
| Reproduksibilitas | Identitas input, konfigurasi, indeks dan versi runtime tersimpan | Terpenuhi untuk konfigurasi yang direkam; laporan ini tidak menguji ulang perubahan parameter. |

Indeks representatif malam: `0, 2397, 4794, 7192, 9589`; pagi: `0, 2570, 5140, 7711, 10281`. Seluruh rekaman frame berukuran 1280 × 720. Referensi PNG review terdapat dalam `sampling.frame_evidence`, dan referensi manifest sesuai burst. Kelima burst masing-masing mencakup sekitar 0,986 detik malam atau 0,973 detik pagi berdasarkan estimasi FPS, bukan durasi PTS tersertifikasi.

## Pengamatan dan keputusan yang tetap terbuka

**VISUAL_OBSERVATION_AI_ASSISTED — berasal dari review sebelumnya yang cocok:** kedua adegan memiliki pandangan jalan oblique, gerak kendaraan diagonal, dan latar relatif tetap pada burst. Pagi memperlihatkan jalan, marka, serta bentuk kendaraan dengan lebih jelas. Malam memiliki area gelap luas, silau lampu depan, dan sebagian kendaraan dekat yang kabur. Teks tertanam kanan bawah menutupi sebagian kendaraan saat masuk. Geometri per-video tampak memungkinkan secara visual.

**OPEN / keterbatasan:**

- Sudut pandang numerik, tinggi/pose kamera, geometri aktual, center versus bottom-center, serta pemetaan semantik Side A/B TOR3 belum disahkan. Pemetaan screenshot terdahulu tidak otomatis berlaku untuk dua video ini.
- Lima burst pendek dapat melewatkan shake atau peristiwa langka. Alignment kontinu dan efek GMC/stabilization belum diuji; tidak ada strategi koreksi yang dipilih.
- Metadata dan dua decode sepakat jumlah frame, tetapi `read_returned_false` masih tidak membedakan EOF dari kegagalan decode. Kesepakatan count tidak membuktikan integritas penuh.
- FPS rata-rata berbeda dari nominal. Timestamp backend juga berbeda dari estimasi indeks/FPS; CFR/VFR, gap PTS, dan dropped frames belum dipastikan. Tidak ada diagnosis korupsi atau VFR yang ditarik dari selisih tersebut.
- `unknown_review_items=[]` berarti seluruh field terisi; keputusan di atas tetap OPEN. Visual review TDLE terdahulu dan video lain tidak dianggap selesai oleh penerimaan TOR3 ini.

**HYPOTHESIS_UNTESTED:** risiko deteksi, asosiasi/tracking, ReID, crop berwatermark, kendaraan kecil/gelap, serta event crossing tetap hipotesis. Tidak ada inference, tracking, ReID, counting, atau eksperimen night preprocessing dalam bukti ini. Tidak ada ground truth atau klaim accuracy, precision, recall, F1, MAPE, maupun performa counting.

## Handoff ke Phase 2

**PROPOSAL — baseline pertama:** gunakan satu video `TOR3-PAGI.mp4` yang identitasnya sudah direkam, satu GPU dengan pemilihan device eksplisit, dan deteksi pada citra frame penuh tanpa ROI counting. Baseline pagi memisahkan verifikasi teknis detektor dari persoalan low-light; ini bukan bukti bahwa model akan berhasil.

**REQUIREMENT — gate teknis Phase 2:** verifikasi aset **YOLO26M** yang nyata, versi dan API Ultralytics, kemampuan runtime GPU, serta class mapping aktual sebelum inference. Catat konfigurasi eksperimen secara eksplisit; jangan mengganti model, mengarang weights/kelas/threshold, atau menyebut default sebagai keputusan tervalidasi. Jika aset atau API tidak tersedia, nyatakan blocker bagian tersebut.

Phase 2 terbatas pada model loading, deteksi frame-level satu video, visualisasi, konfigurasi, dan pengukuran inference yang benar-benar dijalankan. Tracking, ReID, crossing/counting, night enhancement, serta multi-GPU orchestration tetap untuk fase berikutnya. Penerimaan ini tidak membuka Phase 3 atau membuktikan kesiapan pipeline delapan video.

## Integritas arsip laporan

SHA-256 berikut dihitung dari byte empat berkas unggahan dan diverifikasi identik dengan salinan arsip. Ini hash **laporan**, berbeda dari hash video input di atas.

| Berkas sumber unggahan | Salinan arsip | SHA-256 berkas |
|---|---|---|
| `inspection_report-TOR3-MALAM.md` | [Malam MD](evidence/phase_1/20261011T045747_511017Z_0564c6b2/inspection_report.md) | `01438e6b477c88094fca9fe56e5894346499291922351d51a6ab143ffaf2df41` |
| `inspection_report-TOR3-MALAM.json` | [Malam JSON](evidence/phase_1/20261011T045747_511017Z_0564c6b2/inspection_report.json) | `1136af55e419161cbd7988976bee99b7079f00493270bd5231022781df7d02e3` |
| `inspection_report-TOR3-PAGI.md` | [Pagi MD](evidence/phase_1/20261011T044339_967568Z_f02b4d6c/inspection_report.md) | `cbc4ac149cc30049bfdce36f0124139f7fad50483ebb5cc05f9d7841f42e3e4e` |
| `inspection_report-TOR3-PAGI.json` | [Pagi JSON](evidence/phase_1/20261011T044339_967568Z_f02b4d6c/inspection_report.json) | `3f5297e9af3a51d8a4ca1897ff4493d8b3ee2474d6e3366d00a18cccfa497dfc` |

Arsip TDLE dan TOR3 Codex sebelumnya tetap dipertahankan. Tidak ada video asli yang dimasukkan ke GitHub. Penilaian penerimaan menggunakan laporan yang dipertahankan, bukan dugaan hasil dari source notebook.
