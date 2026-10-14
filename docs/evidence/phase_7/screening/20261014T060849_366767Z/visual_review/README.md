# Review aktual screening DEV TOR3-MALAM

**EXPERIMENT RESULT — screening detector saja:** run Kaggle `20261014T060849_366767Z` menjalankan YOLO26M pada 15 frame DEV untuk raw, gamma0.7, exposure1.25, contrast1.25/pivot128, dan unsharpσ1/amount0.5. Review ini membaca gambar dan detection records yang sudah tersimpan; tidak menjalankan enhancement, model, tracker, encoder, crossing, atau counting kembali.

**PROPOSAL — kandidat temporal:** lanjutkan **raw vs gamma0.7** pada segmen DEV kontinu yang sama dengan konfigurasi downstream tetap. Gamma dipilih sebagai probe hipotesis shadow/midtone visibility: tekstur jalan dan truck underbody lebih terbuka pada sampel aktual. Dibanding exposure1.25, perluasan highlight tampak lebih kecil. Pemilihan ini bukan kemenangan detector, konfigurasi produksi, atau bukti peningkatan counting.

Regresi gamma yang konkret tetap disimpan: pada frame14, motor terlihat tetapi bbox `motorcycle` yang ada pada raw tidak dikeluarkan. Pada frame2277, gamma menambah bbox `car` tepat di bagian depan motor dekat; ini konflik komponen/kategori, bukan mobil baru yang terkonfirmasi. Dua bbox truck tumpang tindih pada frame7072 juga tetap muncul. Jadi gamma harus diuji terhadap bukti temporal dan boleh ditolak pada hasil berikutnya.

## Bukti yang benar-benar ditinjau

- Frame DEV: `0,7,14,29,239,2277,2337,2397,2457,2516,7072,7132,7192,7252,7311`.
- Semua **30 contact sheet** dibuka secara aktual: 15 transformed +15 annotated, masing-masing berisi lima varian pada frame sama.
- Tambahan enam frame raw native penuh dibuka: `14,2277,2397,7072,7192,7252`.
- Crop kontak `x=[0,1280), y=[360,700)` menyalin piksel native tanpa resampling, dengan jalan, body bawah, glare, roadside, dan teks pada posisi identik. Bagian di luar crop tetap tersedia pada sumber native asli; crop tidak membuktikan seluruh frame telah ditinjau pada semua varian.
- [Index/hash/tile mapping](contact_index.json) mengikat source/raw hash, transformed/annotated hash, crop, dan posisi tile. [Review per frame](visual_review.json) menyimpan pengamatan eksplisit dan detection rows asli.

Source video SHA-256: `a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082`.

## Kasus yang menentukan

| Frame | Bukti aktual | Konsekuensi untuk replay temporal |
|---|---|---|
| 7 | Motor/rider dekat blur dan terpotong; semua varian hanya bbox person besar. | Periksa awal episode/unit kendaraan; rider tidak menjadi sumber crossing kendaraan. |
| 14 | Raw motorcycle0.402; gamma dan contrast tidak mengeluarkan motorcycle. Exposure dan unsharp masih mengeluarkannya. | Regresi gamma wajib dilacak sampai origin/crossing/konfirmasi; pencerahan tidak cukup. |
| 29 | Raw/gamma/exposure/unsharp mempunyai person+motorcycle; contrast person saja. Bbox gamma berbeda lebar. | Periksa titik BC mentah dan perubahan dukungan crossing, bukan confidence saja. |
| 2277 | Gamma/unsharp menambah bbox car pada area depan motor dekat; semua varian belum mempunyai motorcycle bbox. | Konflik kategori/komponen; jangan menganggap tambahan car sebagai kendaraan lain. |
| 2337 | Motor kiri terdeteksi pada semua varian. Motorcycle kecil di rumah tengah ada pada raw/exposure/unsharp, tidak pada gamma/contrast. | Identitas bbox kecil UNKNOWN; hilangnya bbox tidak otomatis perbaikan. |
| 2397 | Raw/gamma/contrast kosong; exposure memberi car dan unsharp motorcycle pada objek kecil bercahaya hampir sama. | Label berbeda dan glare memerlukan urutan temporal. Headlight/objek UNKNOWN tidak dilabeli false vehicle. |
| 2457 | Dua sumber lampu sangat kuat; kelima varian nol deteksi. | Tidak berarti jalan tanpa kendaraan; tipe/unit/crossing belum terbukti. |
| 7072 | Satu truck dekat tampak pada raw native. Raw/gamma/exposure/unsharp mempunyai dua bbox truck tumpang tindih; contrast satu. | Audit duplikasi fisik; pengurangan bbox contrast belum membuktikan hasil passage lebih baik. |
| 7132 | Truck dan bbox person rumah kanan tetap muncul pada kelima varian; gamma membuka shadow chassis. | Periksa dukungan trajectory dan kelas, bukan perbedaan confidence. |
| 7192 | Motor+rider terdeteksi pada semua varian; variasi bbox kecil roadside masih ada. | Unit utama dibandingkan sebagai satu kendaraan; alternatif kecil tidak dihapus tanpa bukti. |
| 7252 | Car putih terdeteksi semua varian; two-wheeler kecil bicycle pada raw/gamma/unsharp, motorcycle pada exposure, tidak ada pada contrast. Truck bbox roadside belum terkonfirmasi sebagai unit truck tersendiri. | Kategori/identitas tetap OPEN, perlu physical-passage review. |
| 7311 | Raw/gamma/contrast/unsharp mempertahankan motorcycle+person dekat dan car jauh; exposure tidak mengeluarkan car. | Regresi exposure dan dukungan car diuji sepanjang segmen. |

Frame lain `0,239,2516` juga ditinjau pada semua varian; detailnya tercatat di JSON. Bbox person kecil dekat rumah kanan tidak dipakai untuk memastikan identitas fisik atau pedestrian passage.

## Deskripsi keluaran model

Ini jumlah **observasi frame**, bukan kendaraan unik, jumlah passage, atau metrik kualitas.

| Varian | Person | Motorcycle | Car | Truck | Bicycle | Total observasi |
|---|---:|---:|---:|---:|---:|---:|
| Raw | 13 | 6 | 2 | 4 | 1 | 26 |
| Gamma0.7 | 12 | 4 | 3 | 4 | 1 | 24 |
| Exposure1.25 | 13 | 7 | 2 | 4 | 0 | 26 |
| Contrast1.25/pivot128 | 12 | 4 | 2 | 3 | 0 | 21 |
| Unsharpσ1/amount0.5 | 14 | 8 | 3 | 4 | 1 | 30 |

Gamma tidak dipilih karena jumlah observasi/confidence. Exposure mengembangkan highlight dan kehilangan car7311; contrast menghancurkan detail shadow pada beberapa sampel serta kehilangan motorcycle14/29; unsharp tidak mencerahkan shadow atau menghapus motion blur, dan extra car2277 tetap bermasalah. Varian tersebut ditunda dari satu perbandingan temporal awal, bukan ditolak sebagai tidak berguna secara umum.

## Reproduksi dan validasi aktual

Jalankan dari root repository:

```bash
python docs/evidence/phase_7/screening/20261014T060849_366767Z/visual_review/build_review_contacts.py
python docs/evidence/phase_7/screening/20261014T060849_366767Z/visual_review/record_actual_visual_review.py
```

Dependensi tambahan metode visual: Pillow dan font DejaVuSans pada path eksplisit builder. Ini penggambaran ulang bukti tersimpan, bukan pengulangan eksperimen detector.

- Builder: **150/150** pemeriksaan copy piksel native sebelum PNG disimpan.
- [Validasi artefak](artifact_validation.json): **592/592** pemeriksaan source/report hash, detection class totals, dimensi/identitas input, hash sumber/contact dan piksel native contact yang dibuka ulang.
- Pemeriksaan ini membuktikan keterlacakan software/artefak; visual review tetap AI-assisted dan bukan anotasi ground truth.

## Batas kesimpulan dan langkah berikutnya

Hold-out tidak dikenai enhancement/inference/review kandidat di sini. Decoder screening membaca prefix melewati sebagian frame hold-out yang dibuang; laporan asal menjelaskan bahwa ini bukan evaluasi. Raw hold-out pernah dilihat dalam Phase1 sehingga hold-out bukan blind.

Belum ada track persisten, pemulihan identitas ReID, peristiwa crossing, accepted passage, biaya temporal, ataupun perbandingan hasil counting yang dapat disimpulkan dari screening sparse ini. Gamma masih memperlihatkan noise/tekstur gelap, glare, blur dan occlusion teks tetap ada. Tidak ada klaim accuracy/precision/recall/F1/MAPE.

Langkah berikutnya: bekukan proposal gamma0.7 sebagai satu kandidat eksperimen, jalankan **raw vs gamma pada DEV kontinu** dengan detector/tracker/ReID/geometri/counting tetap, dan audit kendaraan/passage fisik yang sama. Periksa salah gabung, duplikasi, kategori, dukungan crossing raw measured vehicle BC, observasi hilang dan regresi. Baru setelah keputusan kandidat dibekukan boleh melakukan evaluasi hold-out.
