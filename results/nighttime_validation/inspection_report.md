# Inspeksi dataset malam resmi —21 Oktober2026

**EXPERIMENT RESULT:** inspeksi CPU selesai di Codex dan Kaggle. Dataset resmi: `chrisbiran/video-traffic-malam`.

Mount Kaggle aktual: `/kaggle/input/datasets/chrisbiran/video-traffic-malam`.

| File | Byte | Durasi dilaporkan (s) | FPS rata-rata dilaporkan | Resolusi | Codec | Frame decoded |
|---|---:|---:|---:|---|---|---:|
| F1YV-WEEKDAY-MALAM.mp4 | 15605045 | 305.594 | 29.879504 | 640×480 | h264 | 9131 |
| F1YV-WEEKEND-MALAM.mp4 | 15611820 | 303.962 | 29.868826 | 640×480 | h264 | 9079 |
| FMMQ-MALAM.mp4 | 52799979 | 301.534 | 29.284688 | 640×480 | h264 | 8861 |
| FMMQ-WEEKDAY-MALAM.mp4 | 52851773 | 302.412 | 29.252859 | 640×480 | h264 | 8882 |
| TC0Q-WEEKDAY-MALAM.mp4 | 21039450 | 309.992 | 27.687809 | 1280×720 | h264 | 8583 |
| TC0Q-WEEKEND-MALAM.mp4 | 21104726 | 315.659 | 26.873974 | 1280×720 | h264 | 8483 |
| TKVQ-WEEKDAY-MALAM.mp4 | 31478469 | 301.308 | 29.992533 | 1024×576 | h264 | 9037 |
| TKVQ-WEEKEND-MALAM.mp4 | 32500804 | 310.840 | 29.992922 | 1024×576 | h264 | 9323 |
| TQHD-WEEKDAY-MALAM.mp4 | 20906777 | 304.300 | 29.073322 | 1280×720 | h264 | 8847 |
| TQHD-WEEKEND-MALAM.mp4 | 20853894 | 302.230 | 29.689316 | 1280×720 | h264 | 8973 |

Semua10 file berhasil dibaca berurutan sampai EOF, total89.199frame; count decoder sesuai header. Tidak ditemukan extension unsupported atau input gagal decode pada inspeksi ini. Ini bukan sertifikasi bitstream bebas korupsi. FPS rata-rata bukan jaminan constant-frame-rate;60frame sumber tidak diasumsikan tepat2detik. Video asli tidak diubah.

## Observasi visual bersumber

### F1YV-WEEKDAY-MALAM.mp4

Frame review: 0, 2282, 4565, 6848, 9130.

Lampu jalan menerangi area dekat; kendaraan jauh kecil, badan gelap lebih sulit dibedakan dari latar. Ada halo lampu jalan dan headlight; area pohon/langit gelap. Motor dekat padaframe0 tampak kurang tajam dibanding objek statis; belum memisahkan blur gerak dari kompresi. Kendaraan besar pada9130 berpotensi menutupi lajur/objek lain. Jalan tampak diagonal ke kejauhan; lima frame memberi framing relatif mirip, bukan sertifikasi stabilitas penuh.

### F1YV-WEEKEND-MALAM.mp4

Frame review: 0, 2270, 4539, 6808, 9078.

Badan jalan/objek gelap lebih redup daripada pasangan weekday dalam sampel; motor/headlight tetap terlihat. Lampu jalan terang berdampingan dengan foreground gelap. Detail kendaraan jauh terbatas pada resolusi640×480; penyebab blur tidak dipastikan. Ada kendaraan di kedalaman berbeda; occlusion temporal belum diukur. Pandangan jalan relatif mirip weekday pada contact sheet; geometri tetap perlu review source ini.

### FMMQ-MALAM.mp4

Frame review: 0, 2215, 4430, 6645, 8860.

Bagian jalan/objek kanan sangat gelap; truk dekat2215 dan4430 masih terlihat. Headlight serta lampu kendaraan terang; kecerahan berubah kuat antarsampel. Kendaraan dekat4430 tampak terseret/kurang tajam. Truk besar4430 menutupi bagian kanan jalan. Pandangan memanjang jalan; tidak dipetakan ke weekday/weekend dari nama FMMQ-MALAM.

### FMMQ-WEEKDAY-MALAM.mp4

Frame review: 0, 2220, 4440, 6661, 8881.

Penurunan detail gelap jelas pada4440,6661,8881; native8881 sebagian besar foreground/latar sangat gelap. Highlight headlight kontras dengan badan kendaraan/latar yang gelap. Ketajaman kendaraan jauh sulit dinilai dari sampel gelap; unknown. Arus dengan kendaraan pada kedalaman berbeda; gap identitas belum diukur. Posisi tepi jalan/tiang terlihat pada sampel; pergerakan kamera penuh belum ditinjau.

### TC0Q-WEEKDAY-MALAM.mp4

Frame review: 0, 2146, 4291, 6436, 8582.

Jalan relatif terang, kendaraan dan dua orang pada2146 terlihat; kendaraan gelap masih berkontras rendah. Glare/haze dekat headlight terlihat; bayangan panjang di jalan. Native4291 memperlihatkan detail motor/lampu yang lembut; pengaruh gerak/kompresi belum dipisahkan. Kendaraan parkir besar di kiri memotong foreground sepanjang sampel. Frame miring; garis/polygon horizontal TGDI tidak boleh dianggap sesuai tanpa review.

### TC0Q-WEEKEND-MALAM.mp4

Frame review: 0, 2120, 4241, 6362, 8482.

Badan jalan relatif terbuka dan terang; kendaraan yang melintas masih terlihat. Silau kuat pada2120 dan sorot kendaraan pada6362. Kendaraan6362 tampak membaur/tersapu; sharpening bukan pengganti bukti temporal. Foreground lebih terbuka daripada pasangan weekday, konfigurasi tidak diasumsikan identik. Pandangan jalan samping; harus diperiksa sendiri sebelum crossing.

### TKVQ-WEEKDAY-MALAM.mp4

Frame review: 0, 2259, 4518, 6777, 9036.

Frame0 seluruhnya hitam; frame1 sudah berisi jalan/kendaraan (dicek ulang0,1,2,5,15,30). Bodi kendaraan besar gelap sementara langit/toko masih terlihat; label malam tidak memastikan tingkat gelap seragam. Kendaraan dekat melintas tampak kurang tajam; sumber blur belum diestimasi. Truck/van dekat menutupi kendaraan/lajur pada2259 dan9036. Jalan tampak dominan melintang; frame0 hitam bukan kegagalan decode seluruh file.

### TKVQ-WEEKEND-MALAM.mp4

Frame review: 0, 2330, 4661, 6992, 9322.

Badan truck besar sangat gelap; latar toko dan jalan sebagian masih terlihat. Headlight/taillight memberi titik terang di tengah foreground gelap. Detail kendaraan bergerak pada beberapa sampel tidak tajam. Bus0 dan truck2330/4661/6992 menutupi bagian besar scene. Area jalan yang teramati berubah karena occluder besar; tidak mengarang posisi objek di belakangnya.

### TQHD-WEEKDAY-MALAM.mp4

Frame review: 0, 2212, 4423, 6634, 8846.

Toko/lampu terang membantu melihat kendaraan; mobil gelap menutup jalan pada2212. Highlight lampu/taillight kontras; ada shadow besar di foreground. Motor4423/6634 tampak terseret/kurang tajam. Mobil dekat2212 menutupi bagian jalan. Sudut kamera miring pada sebagian sampel; alignment geometri harus ditinjau temporal.

### TQHD-WEEKEND-MALAM.mp4

Frame review: 0, 2243, 4486, 6729, 8972.

Banyak motor parkir memenuhi foreground, arus jalan terlihat lebih jauh. Toko/lampu menerangi scene, masih ada area gelap dan glare kecil. Detail arus bergerak dibatasi jarak dan occlusion; blur temporal belum diukur. Motor parkir serta orang foreground menghalangi jalan pada banyak sampel. Tambahanframe0,30,60,120,240,480 memperlihatkan landmark relatif serupa dengan sedikit perubahan; overlay speed bukan bukti kamera bergerak sendiri.

Noise sensor, blur gerak dan kompresi belum dipisahkan secara kuantitatif. Sampling ini tidak membuktikan stabilitas kamera sepanjang video atau menemukan semua passage. Lihat [bukti terstruktur](visual_review.json) dan [inventory asli Kaggle](kaggle_execution/nighttime_input_inspection/inventory.json).

## Relevansi kontrol

Gamma, exposure digital dan brightness relevan untuk probe kecerahan. Shadows/sharpness adalah kandidat eksplisit baru dalam tool review, bukan enhancement produksi terpilih. Gamma memakai eksponen langsung; sharpness3×3 berbeda dari Gaussian sigma1 pada eksperimenPhase7. Jangan membandingkan keduanya sebagai varian yang sama. Raw tetap pembanding. Filter tidak mengembalikan detail yang hilang karena clipping/occlusion dan tidak membuktikan perbaikan identitas atau counting.

## Readiness

Dataset dan inspeksi: PASS. Review-Filter: implementasi dan uji browser/pixel PASS; alur detector/ReID/counting aktual dengan konfigurasi ekspor belum divalidasi. Smoke end-to-end: BLOCKED sebelum inferensi. [Rencana smoke](smoke_plan.json) mencatat source, scope usulan dan prasyarat. Tidak ada hasil detector, tracking, ReID atau counting baru.
