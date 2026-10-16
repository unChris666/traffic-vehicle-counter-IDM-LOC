# Results — pintu masuk hasil dan review

Folder ini sejajar dengan `docs/` dan `notebooks/` agar hasil mudah ditemukan.

## Editor geometri

[review.html](review.html) adalah file mandiri dengan delapan frame TGDI asli, polygon A/B, garis dan margin yang bisa diedit. Halaman ini tidak menjalankan model atau menghitung kendaraan.

1. Unduh [review.zip](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/raw/refs/heads/main/results/review.zip), ekstrak, lalu buka `review.html` di browser desktop. Alternatif: download file HTML melalui tombol **Download raw file** di GitHub; jika browser menampilkan kode, simpan dengan nama `review.html`. Tidak perlu server, Kaggle, atau koneksi internet setelah file tersimpan.
2. Pilih video. Edit titik melalui drag atau tabel koordinat native; atur margin garis. X ke kanan, Y ke bawah; frame TGDI 640×480.
3. Gunakan **Unduh JSON video ini** atau **Unduh JSON semua video** untuk mengirim koordinat hasil review. Simpan satu video atau seluruh konfigurasi sesuai tombol yang tersedia. Ekspor belum otomatis mengubah konfigurasi pipeline.
4. Berikan JSON hasil ekspor beserta catatan per video. Nilai margin dipilih untuk review, belum berarti threshold counting telah diuji.

Gambar bawaan adalah frame 0, bukan keseluruhan video. Cocokkan posisi jalan terhadap beberapa waktu pada video anotasi. Penggantian gambar lokal dapat membantu review frame lain; provenance gambar pengganti harus tetap dinyatakan dan tidak otomatis dianggap berasal dari sumber bawaan.

[Analisis SWOT, contoh kasus, dan prioritas Pareto B v2](../docs/B_V2_GEOMETRY_REVIEW.md) · [Diagnosis pending aktual](b_v2_pending_diagnosis.json)

## Video anotasi Phase 8

Delapan MP4 aktual tersedia pada [GitHub Release phase8-annotation-review-v1](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/tag/phase8-annotation-review-v1). Buka bagian **Assets** atau pilih tautan di bawah. MP4 tetap berada di GitHub Releases; folder `results/` menyediakan indeks yang mudah ditemukan, bukan salinan video di riwayat Git.

| Video | Hasil |
|---|---|
| TGDI-WEEKDAY-PAGI | [Buka/unduh MP4](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/download/phase8-annotation-review-v1/TGDI-WEEKDAY-PAGI-annotated-review.mp4) |
| TGDI-WEEKDAY-SIANG | [Buka/unduh MP4](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/download/phase8-annotation-review-v1/TGDI-WEEKDAY-SIANG-annotated-review.mp4) |
| TGDI-WEEKDAY-SORE | [Buka/unduh MP4](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/download/phase8-annotation-review-v1/TGDI-WEEKDAY-SORE-annotated-review.mp4) |
| TGDI-WEEKDAY-MALAM | [Buka/unduh MP4](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/download/phase8-annotation-review-v1/TGDI-WEEKDAY-MALAM-annotated-review.mp4) |
| TGDI-WEEKEND-PAGI | [Buka/unduh MP4](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/download/phase8-annotation-review-v1/TGDI-WEEKEND-PAGI-annotated-review.mp4) |
| TGDI-WEEKEND-SIANG | [Buka/unduh MP4](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/download/phase8-annotation-review-v1/TGDI-WEEKEND-SIANG-annotated-review.mp4) |
| TGDI-WEEKEND-SORE | [Buka/unduh MP4](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/download/phase8-annotation-review-v1/TGDI-WEEKEND-SORE-annotated-review.mp4) |
| TGDI-WEEKEND-MALAM | [Buka/unduh MP4](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/download/phase8-annotation-review-v1/TGDI-WEEKEND-MALAM-annotated-review.mp4) |

[Receipt final dan checksum server](../docs/evidence/phase_8_publication/success_20261016/final_publication_receipt.json) mengikat kedelapan asset ke sumber yang benar. Hasil B v1 tetap 58 accepted dan 1.825 kandidat pending; belum menjadi audit seluruh kendaraan fisik. Editor geometri dan analisis baru tidak mengubah hasil itu.

## Hasil berikutnya

Gunakan `results/` sebagai pintu masuk publikasi selanjutnya: tautan release, nama video, versi/run, ringkasan, serta rujukan manifest/checksum. Pisahkan setiap versi hasil; jangan menimpa baseline. Video besar tetap di release assets, sedangkan indeks dan laporan kecil berada di folder ini. Perubahan notebook uploader atau counting Phase 8 belum dilakukan dalam tugas ini.

[Validasi editor](verification/README.md): pengujian geometri dan alur browser disimpan terpisah dari hasil counting.
