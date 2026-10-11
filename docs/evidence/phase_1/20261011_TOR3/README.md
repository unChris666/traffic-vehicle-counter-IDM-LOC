# Review visual TOR3 — Phase 1

**EXPERIMENT RESULT:** notebook inspeksi dijalankan di Codex pada dua berkas yang diunduh melalui API Kaggle dari dataset `chrisbiran/traffic-tracker-videos`. Frame hasil decode benar-benar dilihat: lima posisi representatif, lima rangkaian 30 frame berurutan, dan beberapa PNG pada resolusi asli. Review dilakukan dengan bantuan AI, bukan anotasi ground truth atau benchmark model.

| Input | Ukuran | Metadata | Decode kedua pass | Review |
|---|---:|---|---:|---|
| `TOR3-PAGI.mp4` | 53.173.467 byte | H.264, 1280 × 720, 344,859778 detik; FPS rata-rata 29,815017 | 10.282 frame | [Dictionary 21 field](TOR3-PAGI/manual_review.json), [laporan](TOR3-PAGI/inspection_report.md) |
| `TOR3-MALAM.mp4` | 52.906.523 byte | H.264, 1280 × 720, 325,969067 detik; FPS rata-rata 29,419970 | 9.590 frame | [Dictionary 21 field](TOR3-MALAM/manual_review.json), [laporan](TOR3-MALAM/inspection_report.md) |

Identitas lengkap dan data review tersimpan dalam [manual_reviews.json](manual_reviews.json). Nilai nominal FPS keduanya 29,970030; perbedaan rata-rata/nominal tidak dengan sendirinya membuktikan VFR atau dropped frames.

**FACT — batas sumber:** transfer unggahan Sediment dibatasi 32 MiB, sedangkan kedua berkas sekitar 51 MiB. Karena itu pemeriksaan menggunakan berkas bernama sama dari dataset Kaggle yang diberikan pengguna. SHA-256 dihitung atas berkas Kaggle yang benar-benar diunduh. Kesamaan byte dengan unggahan belum dapat diverifikasi karena hash unggahan tidak tersedia; tidak ada klaim bahwa kedua sumber telah dibandingkan.

**Pengamatan:** pandangan dari tepi jalan berbentuk oblique, dan kendaraan bergerak diagonal dalam gambar. Kedua video tampak `effectively_stationary` pada lima rangkaian pendek yang diperiksa. Pagi memperlihatkan jalan/marka dan bodi motor; malam memiliki banyak area gelap, lampu depan menyilaukan, dan beberapa kendaraan dekat kabur. Teks lokasi/waktu tertanam di kanan bawah dapat menutupi piksel kendaraan yang masuk dari kanan pada kedua video.

**OPEN:** sudut dalam derajat, tinggi kamera, poligon/koordinat garis, anchor, semantik A/B untuk dua video ini, toleransi drift, source PTS, integritas seluruh berkas, dan gerak kamera di sela sampel. Kelayakan geometri hanya penilaian visual bersyarat. Label A/B screenshot sebelumnya tidak diterapkan sebagai aturan umum.

**HYPOTHESIS_UNTESTED:** potensi dampak gelap, silau, blur, watermark, dan objek terpotong terhadap deteksi/tracking/ReID/counting. Tidak ada model, stabilization, night enhancement, atau Phase 2 yang dijalankan.

## Bukti yang disimpan

Setiap subfolder menyimpan laporan MD/JSON, `manual_review.json`, `run_manifest.json`, contact sheet, lima `consecutive_<label>.png` dengan seluruh 30 frame berturut-turut, manifest burst, serta inventori hash PNG asli. Gambar lembar review adalah thumbnail berlabel indeks; PNG asli, preview HTML, dan video tetap berada di direktori runtime, bukan GitHub. Referensi `frames/...` dan `bursts/.../preview.html` dalam laporan merujuk run asli; inventori tidak menyatakan PNG tersebut tersimpan dalam repositori. Hash PNG juga tidak menjamin kesamaan encoding/color conversion pada versi decoder lain.

| Input | Indeks representatif | Rentang burst, masing-masing 30 frame |
|---|---|---|
| Pagi | 0, 2570, 5140, 7711, 10281 | 0–29; 2555–2584; 5125–5154; 7696–7725; 10252–10281 |
| Malam | 0, 2397, 4794, 7192, 9589 | 0–29; 2382–2411; 4779–4808; 7177–7206; 9560–9589 |

Setiap burst hanya sekitar satu detik menurut FPS rata-rata; total lima burst bukan review kontinu selama lima menit. OpenCV berhenti ketika `read()` mengembalikan false, tanpa membedakan EOF normal dari semua decode failure. Jumlah decode cocok metadata, tetapi itu bukan jaminan integritas.

## Terapkan di Kaggle

Gunakan notebook sumber terbaru. Setelah discovery mengonfirmasi path, pilih satu input:

```python
VIDEO_PATH = DATASET_ROOT / 'TOR3-MALAM.mp4'
# Untuk review pagi, ganti menjadi:
# VIDEO_PATH = DATASET_ROOT / 'TOR3-PAGI.mp4'
```

Restart kernel dan **Run All**. Cell `manual_review` mereset dictionary, lalu menerapkan catatan yang telah ditinjau hanya bila SHA-256, nama/ukuran, jumlah decode, indeks sampling, dan keberadaan bukti run aktif cocok. Kondisi tidak cocok menghasilkan `UNKNOWN`; catatan malam tidak dibawa ke pagi atau video lain. `HASH_VIDEO=True` diperlukan untuk pencocokan. Laporan mencatat asal review di Codex dan run tempat catatan diterapkan. Pemilihan ini tidak menjalankan review visual/model baru secara otomatis.

**Validation procedure executed in Codex:** kedua video diprobe dan didecode dua pass dengan notebook; ekspor laporan menerima 21 field dan bukti temporal. Validasi independen menjalankan 22 pemeriksaan registry, termasuk SHA/sampling/decode yang berbeda, bukti hilang, reset provenance, dan pemisahan dictionary. Format notebook serta kompilasi seluruh cell lulus. Eksekusi baru di runtime Kaggle belum dilakukan; source notebook disimpan terpisah melalui API setelah validasi.
