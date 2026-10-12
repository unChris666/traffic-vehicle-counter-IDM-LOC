# Review pixel temporal G3 — TOR3-PAGI

**EXPERIMENT RESULT:** source video SHA-256 `606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c` didecode secara sequential sekali menggunakan OpenCV **5.0.0**, backend FFMPEG. Hasilnya **10.282 frame berhasil**, ukuran native **1280×720**; jumlah ini cocok dengan cache Phase 4. Metadata backend pada eksekusi ini juga melaporkan 10.282 frame. Tidak ada discrepancy metadata/decode baru yang diobservasi. Ini bukan bukti bahwa semua persoalan decoder historis atau source PTS telah terselesaikan.

**EXPERIMENT RESULT:** pixel array BGR `uint8` pada frame **5140** identik dengan PNG raw Phase 2 yang tersimpan. [decode_alignment.json](decode_alignment.json) memisahkan SHA file PNG dari SHA pixel terdecode dan mencatat dependency/method, metadata backend dan batas klaim alignment. File input identik, frame count/native size dan satu kecocokan pixel mendukung pemetaan indeks sequential; checksum pixel cache untuk seluruh frame dan authoritative source PTS tidak tersedia.

Metode reproduksi:

```bash
/workspace/.venvs/traffic-inspection/bin/python \
  docs/evidence/phase_5/verification/review_g3_targeted_pixels.py \
  --video /tmp/traffic-phase5-source/TOR3-PAGI.mp4
```

**FACT — cakupan retensi:** [targeted_pixel_manifest.json](targeted_pixel_manifest.json) menyimpan hash **54** frame native target, termasuk frame 5140; sepuluh contact sheet berisi raw/overlay empat frame per kasus, total **20 frame unik** yang direview langsung dengan `view_image`. Semua crop raw memakai pixel asli tanpa resize; asal crop native, posisi tiap tile, raw-crop pixel SHA, exact raw bbox/source detection link dan koordinat BC disimpan. Overlay merupakan anotasi audit terpisah, bukan gambar hasil preprocessing. Full video dan frame raw lengkap berada di `/tmp`, tidak dimasukkan ke GitHub. Decode lengkap bukan review visual lengkap seluruh video.

| Bukti pixel yang dibuka | Observasi bounded yang terkonfirmasi | Implikasi |
|---|---|---|
| [ID 893 raw](id893_return_raw_contact.png), [overlay](id893_return_overlay_contact.png), 4977–4980 | Scooter/rider bergerak berurutan ke kiri/menjauh. Bbox `person` pada 4978 memiliki batas bawah lebih pendek; bagian kaki/bawah tetap terlihat di luar kotak. | Excursion satu frame **4,1525 px** konsisten dengan perubahan cakupan bbox rider; bukan bukti U-turn kendaraan. |
| [ID 912 raw](id912_return_raw_contact.png), [overlay](id912_return_overlay_contact.png), 5019–5022 | Scooter dengan dua orang terus bergerak ke kiri/menjauh. Bbox `person` 5020 memendek jelas: y2 `577,21→518,61→572,05`. | Excursion **39,9456 px**, lalu return **4,5672 px**, tidak mengisolasi noise kamera. Band maksimum tersebut tidak otomatis menjadi default. |
| [ID 1217 raw](id1217_class_gap_raw_contact.png), [overlay](id1217_class_gap_overlay_contact.png), 6015/6017/6018/6019 | Pickup tetap terlihat jelas. Kelas 1217 berubah `truck→car→truck`; 1217 tidak emitted 6018 meski raw detection pickup tersedia. Assigned ID 1279 pada 6018 juga `emitted=False`, meski `is_activated=True`, dengan lifecycle `not_retained`. | Gap trajectory bukan bukti semua deteksi atau visibilitas hilang. Jangan menyatukan ID atau menjembatani gap menjadi passage valid. |
| [ID 1712 raw](id1712_five_missing_raw_contact.png), [overlay](id1712_five_missing_overlay_contact.png), 7559/7560/7564/7565 | Motorcycle kecil bergerak ke kanan/dekat; scooter foreground menutupnya pada 7560 dan objek terlihat kembali pada 7564/7565. 1712 tidak emitted pada 7560–7564, lalu kembali 7565. | Ada bukti occlusion dalam interval gap; arah sebelum/sesudah gap tetap bukan crossing terukur kontinu. Recovery satu ID bukan bukti keandalan umum. |
| [Scooter merah raw](red_scooter_components_raw_contact.png), [overlay](red_scooter_components_overlay_contact.png), 5128/5129/5130/5132 | Bbox `motorcycle` 964 dan 973 bertumpuk pada scooter yang sama, dengan `person` 967 pada rider. | Track/component BC dapat menghasilkan diagnostik berbeda untuk satu unit visual. Jumlah diagnostik bukan jumlah kendaraan unik. |

**EXPERIMENT RESULT — keputusan terbatas:** ketiga excursion singkat ID 893/912 kini memiliki exact-frame pixel evidence. Pada sampel yang direview tidak terlihat U-turn, sementara cakupan bbox rider berubah. Ini mendukung pemisahan persoalan anchor/kategori/komponen dari jitter geometri. Menyaring diagnostik menggunakan band atau konfirmasi belum menyelesaikan physical identity dan kategori.

**UNKNOWN:** threshold numerik terbaik, ground truth crossing/anchor, kontribusi noise detector versus camera/association, penyebab rinci ID 1279 tidak retained, dan generalisasi geometri/parameter ke video lain. Tidak semua lima frame gap 1712 direview sebagai gambar tertahan; laporan tidak mengklaim tingkat occlusion setiap frame.

[targeted_visual_review.json](targeted_visual_review.json) mencatat setiap gambar yang benar-benar dibuka, SHA, frame, observasi dan source extracts. Tidak ada detector, tracker, ReID, stabilisasi atau enhancement yang dijalankan. Tidak ada traffic count atau klaim accuracy, precision, recall, F1, MAPE.
