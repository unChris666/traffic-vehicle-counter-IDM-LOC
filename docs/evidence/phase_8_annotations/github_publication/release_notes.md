Delapan annotated video TGDI Phase 8 dengan panel kategori × arah, warna kelas bbox, label ID/kategori berlatar, nomor frame/waktu, penanda BC dan unit motorcycle–rider.

Seluruh 72.590 frame berasal dari render-only Kaggle run `20261015T150218_945772Z`. Hasil counting asli tetap 58 accepted otomatis dan 1.825 kandidat pending; pending tidak masuk pivot. Ini replay snapshot final offline, bukan hasil real-time atau audit fisik seluruh kendaraan.

Pilih MP4 di **Assets**. Video disimpan sebagai GitHub Release assets agar tetap tersedia setelah sesi Kaggle berakhir. GitHub mungkin menawarkan download; MP4 H.264/yuv420p dapat diputar setelah diunduh. SHA256SUMS dan delivery_manifest.json mengikat salinan H.264 ke MP4 renderer asli. Kompresi delivery bersifat lossy, dengan jumlah frame, cadence, ukuran canvas dan timestamp presentasi yang diverifikasi.

Tidak ada eksekusi ulang YOLO, tracker, ReID, enhancement atau counting. Pergantian ID setelah oklusi masih merupakan masalah terbuka. Tidak ada klaim akurasi tanpa ground truth.

Mulai review pada TGDI-WEEKDAY-PAGI, frame 2432: kendaraan dan komponen rider berbagi unit tampilan, komponen berkontribusi +0 dan pivot bertambah satu event. Catat video, frame, track/unit/event ID, serta masalah unit, duplikasi, kategori atau crossing.
