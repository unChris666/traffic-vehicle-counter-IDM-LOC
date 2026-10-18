# Review terbatas: estimasi timeout kendaraan tepi kanan

**Status: temuan review aktual yang memerlukan audit lanjutan.** Ini bukan ground truth atau perubahan keputusan counting. Tidak ada model, tracker, ReID, atau counting yang dijalankan ulang; enam sumber program dan hasil eksekusi tetap utuh.

**FACT — output tersimpan:** pada `TGDI-WEEKDAY-PAGI`, dua ID menghasilkan dua event `car`, `B_TO_A`, `ESTIMATED_TIMEOUT`:

| Track | Event | Frame aktivasi | Terakhir terlihat di asal | Band / destination / crossing terukur |
|---|---|---:|---:|---|
| 2 | `b_v2_68bf3096ed180e09befd4ace` | 76 | 16 | Tidak ada |
| 34 | `b_v2_96ffb884da2f9c8c566a0548` | 201 | 141 | Tidak ada |

Kedua event menyimpan `measured_crossing=false`, `direction_assumed=true`, dan `id_change_proven=false`. Keduanya berasal dari asumsi unit raw track yang berbeda; review ini tidak menggabungkan atau membatalkannya.

**OBSERVASI VISUAL TERBATAS:** keenam frame sumber asli telah dibuka dan dilihat. Kendaraan dengan kaca depan bermotif kotak terlihat di tepi kanan dekat bangunan/pagar yang sama. Pada beberapa sampel, kendaraan yang sedang melintas menutupi sebagian kendaraan tepi kanan tersebut.

| Frame sumber | Gambar native 640×480 | Observasi terbatas |
|---:|---|---|
| 0 | [PNG](source_frame_000000000.png) | Kendaraan tepi kanan terlihat; pengukuran tersimpan memakai ID 2. |
| 16 | [PNG](source_frame_000000016.png) | Kendaraan jalan masuk dari kanan dan menutupi bagian bawah area kendaraan tepi kanan; ID 2 masih emitted. |
| 76 | [PNG](source_frame_000000076.png) | Kendaraan tepi kanan kembali terlihat di dekat pagar; pengukuran memakai ID 34. Estimasi ID 2 aktif pada frame ini. |
| 110 | [PNG](source_frame_000000110.png) | Kendaraan bermotif kotak masih terlihat di dekat bangunan; ID 34 masih emitted. |
| 141 | [PNG](source_frame_000000141.png) | Mobil putih yang melintas menutupi bagian bawah area kendaraan tepi kanan; ini observasi emitted terakhir ID 34 dalam interval review 0–201. |
| 201 | [PNG](source_frame_000000201.png) | Kendaraan tepi kanan tampak lagi, tetapi tidak ada emitted ID 2/34 pada frame ini. Estimasi ID 34 aktif. |

**FACT — pengukuran raw ID 2:** BC berubah dari `(616.806, 306.193)` pada frame 0 menjadi `(617.943, 273.865)` pada frame 16. Jarak normal terhadap garis berubah dari `249.900` menjadi `224.020` pixel, tetap jauh di sisi B dan di luar half-width 25 pixel. Tinggi bbox berkurang dari sekitar 127.23 menjadi 99.16 pixel. Perubahan bbox ini dapat memenuhi syarat progres menuju garis pada eksperimen sekarang; perubahan tersebut sendiri tidak membuktikan kendaraan bergerak menuju garis di dunia nyata.

**HIPOTESIS, BELUM TERBUKTI:** kendaraan tepi kanan mungkin parkir/stasioner, dan variasi bbox akibat occlusion atau perubahan framing kamera mungkin memicu arah progres. ID 2 dan 34 mungkin merupakan fragmen kendaraan fisik yang sama, sehingga kedua estimasi berisiko menjadi duplikasi tanpa passage nyata. Kemiripan tampilan dan lokasi pada enam sampel belum membuktikan identitas fisik yang sama atau status parkir selama seluruh interval.

**Audit berikutnya:** review kontinu frame 0–201 dengan raw bbox, ID 2/34, dan seluruh kendaraan di sekitarnya. Bedakan perpindahan kendaraan dari perubahan bbox karena occlusion serta gerak kamera; putuskan apakah terdapat passage fisik dan apakah kedua ID menunjuk satu kendaraan. Simpan keputusan manual terpisah. Untuk eksperimen kebijakan selanjutnya, sertakan kendaraan parkir/berhenti sebagai kasus negatif, kendaraan bergerak sebagai kasus positif, serta fragmen ID pada objek tepi frame. Kasus tunggal ini tidak cukup untuk memilih threshold atau menyatakan kinerja keseluruhan.

[review.json](review.json) menyimpan identitas video/cache, dua event aktual, 89 observasi detector-linked ID 2/34 dalam lingkup frame 0–201, serta SHA file dan pixel RGB keenam PNG. PNG diekstrak dengan FFmpeg tanpa resize/enhancement; pixel-hash menyebut konvensi dekodenya dan tidak mengklaim byte pixel identik dengan backend dekoder lain. Byte hasil lokal tersimpan diverifikasi terhadap arsip gzip yang dirujuk. Belum ada klaim accuracy atau jumlah false count secara menyeluruh.
