# TGDI — persiapan delapan input aktual

**EXPERIMENT RESULT:** delapan berkas aktual di dataset Kaggle `chrisbiran/tgdi-traffic-videos` diunduh ke direktori sementara di luar Git, diperiksa terhadap ukuran byte dari daftar Kaggle, di-hash SHA-256, lalu didekode secara berurutan dari frame nol. Total **72.590 frame** berhasil didekode; seluruh video berukuran native **640 × 480**. Pada delapan input ini, jumlah hasil decode sama dengan metadata frame count OpenCV. Hasil ini memverifikasi input dan keterbacaan yang diamati, bukan performa model atau kelengkapan counting.

| Video | Frame berhasil didekode | FPS metadata OpenCV | Estimasi durasi (detik) |
|---|---:|---:|---:|
| TGDI-WEEKDAY-PAGI | 9.052 | 29,904050 | 302,701 |
| TGDI-WEEKDAY-SIANG | 9.128 | 29,781214 | 306,502 |
| TGDI-WEEKDAY-SORE | 9.077 | 29,956869 | 303,002 |
| TGDI-WEEKDAY-MALAM | 9.022 | 29,972441 | 301,010 |
| TGDI-WEEKEND-PAGI | 9.017 | 29,976559 | 300,802 |
| TGDI-WEEKEND-SIANG | 9.124 | 29,983459 | 304,301 |
| TGDI-WEEKEND-SORE | 9.138 | 29,869970 | 305,926 |
| TGDI-WEEKEND-MALAM | 9.032 | 29,980012 | 301,267 |

Durasi pada tabel adalah `actual_decoded_frame_count / OpenCV_reported_FPS`. Metadata ffprobe asli disimpan di setiap `source_inspection.json`; tabel tersebut tidak membuktikan source PTS atau CFR/VFR. `VideoCapture.read()` berakhir dengan `False`; API ini tidak membedakan EOF normal dari kegagalan decode. Perbandingan jumlah metadata/hasil decode dipertahankan untuk audit.

[Inventory aktual](../inventory/TGDI_actual_discovery.json) mengikat identitas sumber, pengelompokan input, laporan, proposal, dan preview. Label `weekday`/`weekend` serta `pagi`/`siang`/`sore`/`malam` mengikuti format nama file yang dikonfirmasi pengguna. Nama bisnis dan koordinat lokasi tetap `null`; teks/GPS yang tertanam pada gambar tidak otomatis menjadi metadata bisnis.

Setiap direktori video menyimpan tujuh PNG native tanpa enhancement: frame **0, 15, 30, 45, 59**, frame tengah aktual, dan frame akhir aktual. Dua contact sheet menggunakan salinan visual yang diperkecil; PNG sumber tetap native. Burst awal adalah lima sampel dalam 60 frame awal, bukan rekaman setiap frame pada interval tersebut. Ini mendukung review temporal terbatas dan tidak menetapkan stabilitas kamera atau alignment geometri sepanjang video.

**PROPOSAL:** [delapan kandidat G3-T1](../geometry_proposals/TGDI_eight_video_G3_T1_overview.png) memproyeksikan persis template relatif G3 dari canvas 960 × 540 ke frame native 640 × 480. Polygon A mempertahankan urutan keliling P1A–P1B–P1D–P1C, B tetap berhenti pada X referensi 875, dan selisih endpoint garis/P1C tidak di-snap. Perubahan aspect ratio dan viewpoint belum divalidasi sebagai geometri counting. Endpoint native pada proyeksi ini adalah P1 `(3, 459.111...)`, P2 `(624.266..., 271.466...)`, dan cap B `X=583.333...`.

**OPEN:** semua proposal memerlukan review garis, polygon, dan arah **per video**. Belum ada geometri yang diterima atau arah mendekati/menjauhi kamera yang dikonfirmasi untuk TGDI. Tidak ada model, bbox, trajectory, titik BC track, crossing, counting, atau enhancement yang dijalankan dalam persiapan ini.

**OBSERVASI VISUAL TERBATAS:** frame nol yang benar-benar dibuka melalui overview memperlihatkan koridor jalan miring dan overlay peta/teks pada bagian bawah. Truk besar menutupi sebagian koridor pada frame nol `WEEKDAY-SORE` dan `WEEKEND-PAGI`; frame nol `WEEKDAY-MALAM` memuat orang dekat kamera dan blur pada kendaraan; frame malam memuat glare lampu. Temuan ini hanya berlaku pada frame yang disebutkan, bukan kesimpulan seluruh video. Frame tengah/akhir tersedia untuk menilai penempatan yang tertutup objek pada frame awal.

Validasi aktual [355/355 pemeriksaan artefak](preparation_artifact_validation.json) memeriksa sumber, hash/pixel 56 PNG native, geometri sederhana tanpa overlap interior, status proposal, dan 40 sampel awal yang didekode ulang secara independen. Penghitungan frame penuh berasal dari pass sequential pertama; validasi independen tidak mengulangi decode penuh atau inferensi model.

Perintah reproduksi dari root repository, setelah delapan video aktual tersedia di direktori lokal atau mount Kaggle:

```bash
python docs/evidence/phase_8/verification/build_tgdi_preparation.py \
  --source-root /kaggle/input/datasets/chrisbiran/tgdi-traffic-videos \
  --repository-root .
```

Dependensi alat persiapan: Python, OpenCV, NumPy, Pillow, `ffprobe`, dan font `DejaVuSans.ttf` pada path Linux yang dinyatakan di builder. Versi Python/OpenCV/NumPy dari eksekusi aktual tercatat per video. `--reuse-complete` hanya menggunakan kembali laporan yang identitas sumber dan sampel tersimpannya cocok; output adalah checkpoint persiapan, bukan cache hasil model.
