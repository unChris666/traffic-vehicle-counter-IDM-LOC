# Eksperimen aktual confidence detector setelah implementasi P0

Tanggal review: 20 Oktober 2026, Asia/Bangkok.

**Keputusan: confidence0,10 tetap kandidat riset; belum dipilih sebagai default.**
Eksperimen selesai secara teknis dengan CUDA. Perbaikan counting yang andal
lintasvideo belum ditetapkan.

## Input, kontrol dan keluaran

Notebook private baru:
[phase-9-tgdi-confidence-retention-after-p0, version1](https://www.kaggle.com/code/chrisbiran/phase-9-tgdi-confidence-retention-after-p0).
Notebook Kaggle pengguna yang lama tidak diubah. Source reproducible ada pada
[09b](../notebooks/09b_model_configuration_experiment.ipynb) dan helper model.

- Video aktual TGDI-WEEKDAY-SIANG, SHA sama dengan pilot QC.
- Frame7380–7979:600 frame kontinu;7380–7439 konteks/warmup dan7440–7979 evaluasi.
  State tracker direset pada7380; tidak mengklaim riwayat full-video.
- Dua actual detector calls per source frame, conf0,25 versus0,10. YOLO26M,
  imgsz640, pinned package, raw, BoT-SORT dan person-domain ReID tetap.
- Satu device CUDA0; bukti detector dan kernel encoder CUDA tersimpan. Ini bukan
  eksperimen mengganti weights, retraining, multi-GPU atau enhancement malam.
- Runtime aktual: Python3.13.15, PyTorch2.11.0+cu128, OpenCV4.14.0, TeslaT4.
  Ultralytics tetap versi8.4.175. Runtime ini berbeda dari donor Phase8 lama;
  pembandingan terkontrol berlaku antara dua varian run baru, bukan klaim
  ekuivalensi bitwise dengan cache baseline lama.
- Seluruh600 pasangan pixel sama. Himpunan deteksi berskor≥0,25 juga cocok
  pada600 frame setelah rounding bbox4desimal/confidence5desimal; ini bukan
  klaim identitas bitwise output floating point.

[Output actual](../results/model_experiments/20261020_confidence_retention/kaggle_output_v1/phase9_model_confidence_v1/report.json)
dan [perbandingan frame](../results/model_experiments/20261020_confidence_retention/paired_review/comparison.json)
disimpan terpisah dari cache lama. Seluruh23 artefak output yang diunduh cocok
manifest SHA/size. Dua weights di assets tidak diunduh kembali; bukan klaim
semua25 file manifest tersedia lokal.

## Hasil aktual

| Ukuran pada600frame konteks | Conf0,25 | Conf0,10 |
|---|---:|---:|
| Deteksi tersimpan |7.533|10.990|
| Observasi emitted tracker |6.863|7.628|
| Observasi emitted berskor<0,25 |0|716|
| Waktu detector, detik |22,106|19,693|
| Waktu tracker termasuk encoder, detik |35,893|87,958|

Observasi berskor rendah berasal dari135 raw tracker IDs; bukan135 kendaraan
tambahan. Pada540 frame evaluasi terdapat679 emitted observations berskor rendah.
Waktu tracker sekitar2,45× baseline dalam run sequential terinstrumentasi ini;
tidak menyimpulkan latency produksi atau bahwa detector0,10 lebih cepat dari
satu pasangan timing. Encoder sudah termasuk tracker, jangan dijumlahkan lagi.

Kedua cache baru direplay menggunakan **policy P0 v2 yang sama**, tanpa review
raw ID lama atau relasi donor. Global frame=local+7380, tanpa fake prehistory
atau post-clip frames. Policy ini sendiri belum lulus P0 untuk default.

| Hasil operasional aktivasi pada540frame evaluasi | Conf0,25 | Conf0,10 |
|---|---:|---:|
| Accepted |13|12|
| Measured |9|11|
| Inferred |4|1|

Pada seluruh600 frame, hasilnya14/11 dan13/12 accepted/pending. Pending memakai
scope konteks600, sehingga tidak disamakan dengan hanya540 frame evaluasi.
Jumlah lebih kecil/besar dan measured lebih banyak belum membuktikan counting
lebih benar. Angka ini tidak sebanding langsung dengan172 event baseline lama.

## Review bukti visual dan temporal

Sebelas paired contact sheets benar-benar dibuka, dengan source frames
7400/7422/7509/7604/7615/7625/7635/7651/7711/7900/7979. Ini sampling, bukan
adjudikasi seluruh600frame atau semua passage.

- **Tambahan observasi nyata:** beberapa box kecil pada person/two-wheeler yang
  sebagian tertutup/distant muncul di kandidat. Kelas person tetap tidak
  otomatis pedestrian. Box tambahan di area kaca/komponen kendaraan juga perlu
  diteliti; tidak dihitung sebagai kendaraan baru dari banyaknya bbox.
- **Bukti crossing berubah:** kandidat memiliki pair kontinu source7636→7637
  dan7710→7711 pada event yang kemudian dikonfirmasi. Baseline dan kandidat
  harus dicocokkan melalui source bbox/frame; event yang waktunya berdekatan
  belum tentu kendaraan fisik sama. Tidak mengklaim dua tambahan measured
  berarti dua kendaraan yang sebelumnya terlewat telah diperbaiki.
- **ID reuse belum selesai:** pada7615 dan7625, baseline raw266/kandidat261
  mengamati motorcycle pengendara merah. Pada7651, kedua raw ID tersebut
  mengamati car di posisi/objek berbeda. Source view memperlihatkan motor dan
  SUV sebagai objek berbeda. Lower confidence tidak menyelesaikan masalah ini.
- **Kategori tetap berubah:** SUV hitam baseline578/kandidat542 berlabelcar
  pada7900 lalu truck pada7979. Mengubah confidence tidak memperbaiki label
  mentah tersebut.

Paket bukti yang dibuka ada di
[paired_review](../results/model_experiments/20261020_confidence_retention/paired_review/).
Observasi temporal terikat actual emitted rows dan native source hashes,
bukan kesamaan angka ID antarvarian.

## Keputusan berikutnya

Pertahankan0,25 sebagai kontrol tersimpan. Kandidat0,10 layak dibawa ke
eksperimen lanjut setelah unit/episode gate diperbaiki, dengan perbandingan
physical passage serta false track, wrong merge, duplikasi dan miss.
Jangan sekaligus tuning ReID, enhancement dan counting untuk mengejar subtotal.

Vehicle-ReID final, dataset anotasi, role classifier/fine-tuning bila memang
dibutuhkan, berbagai kondisi malam, dan batas penerimaan produksi masih open.
Tidak ada accuracy/precision/recall/F1/MAPE atau jaminan zero mistakes.
