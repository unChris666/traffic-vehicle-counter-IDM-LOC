# Review geometri TGDI dan usulan kebijakan B v2

Status: alat review dan analisis; belum ada perubahan counting Phase 8. Hasil B v1, geometri yang sudah diterima, dan seluruh bukti sebelumnya tetap tersimpan. Dokumen ini membedakan keputusan pengguna, fakta implementasi, dan usulan eksperimen.

## Keputusan pengguna dan fakta koordinat

- Pengguna meminta editor untuk mengganti polygon A, garis beserta margin, dan polygon B.
- Pengguna mempertahankan motorcycle + rider/passenger sebagai satu motorcycle, dengan satu bbox tampilan.
- Pengguna memilih **otomatis menambah hitungan** untuk aturan tidak muncul di polygon tujuan selama 60 frame. Pilihan ini dicatat sebagai kebutuhan usulan baru; implementasi dan hasilnya belum ada.
- TGDI aktual berukuran 640×480. TOR3 berukuran 1280×720. Lebar bukan satu-satunya pembeda: aspect ratio berubah dari 16:9 menjadi 4:3. Pemetaan koordinat lama tidak membuktikan kesesuaian jalan pada video baru.
- G3 historis berasal dari acuan 960×540. Konfigurasi TGDI G3-T1 yang sudah diterima **telah** dipetakan ke ukuran native, menggunakan u=x/960, v=y/540, lalu x_native=u×640, y_native=v×480. Jadi tidak ada bukti bahwa semua pending disebabkan koordinat 1280 yang dipakai langsung pada TGDI.

Editor [results/review.html](../results/review.html) menampilkan delapan frame 0 asli yang retained, dengan geometri lama sebagai titik awal yang bisa diubah. Angka hasil edit adalah koordinat native frame yang dipilih; gambar yang diperkecil di browser tidak mengubah ruang koordinat ekspor. Frame0 tidak membuktikan kesesuaian sepanjang video; perubahan tetap perlu replay temporal. Margin pada editor adalah **half-width tegak lurus terhadap garis dalam pixel native**; lebar total pita = 2×margin. Nilai awal mengikuti baseline nol, bukan rekomendasi threshold baru. Ekspor merupakan format review terpisah, belum menjadi konfigurasi yang otomatis dimuat pipeline.

## Tiga jalur hitung yang diusulkan

Ketiganya harus mengacu pada satu unit fisik dan satu passage yang sama. Jika satu kendaraan memenuhi dua atau tiga jalur, kontribusinya tetap **satu**, dengan jenis bukti diperbarui. ID tracker tidak boleh menjadi satu-satunya kunci deduplikasi ketika ID dapat berganti.

| Jalur | Bukti dan log yang diusulkan | Batas makna |
|---|---|---|
| Garis dengan margin | Trajectory BC kendaraan terukur berpindah dari satu sisi luar pita ke sisi berlawanan melalui segmen garis. Log `ID-KATEGORI; A_TO_B/B_TO_A; CROSSING_LINE`. | BC tepat berada di garis/pita hanya kontak. Kendaraan bisa menyentuh, berhenti, bergerak sejajar, atau kembali. Pengukuran dapat melompati koordinat garis di antara dua frame; tidak perlu ada pixel BC yang tepat sama dengan garis. |
| A ke B atau B ke A setelah occlusion/gap | BC kendaraan terukur terlihat di polygon asal, hilang, lalu terlihat di polygon tujuan; identitas fisik perlu diasosiasikan. Log `ID-KATEGORI; A_TO_B/B_TO_A; OCCLUSION_DIFF_POLYGON`. | Kedatangan di polygon berbeda adalah bukti perpindahan ROI, bukan observasi langsung crossing segmen. Jika jalan mempunyai jalur alternatif di luar endpoint atau ROI salah tempat, finite-line crossing belum terbukti. |
| Timeout 60 frame | Sesuai pilihan pengguna, menambah hitungan operasional otomatis. Log `ID-KATEGORI; arah_asumsi/UNKNOWN; CHANGE_ID; ESTIMATED_TIMEOUT`. | Timeout sendiri tidak membuktikan ID berubah, kendaraan menyeberang, atau arah aktual. Jika arah A→B ditentukan hanya karena terakhir di A, simpan sebagai asumsi, bukan arah terukur. |

**Usulan transparansi output:** simpan jumlah `CROSSING_LINE`, `OCCLUSION_DIFF_POLYGON`, dan `ESTIMATED_TIMEOUT` terpisah. Total operasional yang diminta pengguna dapat memasukkan ketiganya setelah deduplikasi per passage. Kolom `measured_crossing=false` dan dasar asumsi tetap melekat pada event estimasi. Dengan begitu, pilihan otomatis +1 dijalankan tanpa menyebut semua event sebagai crossing teramati.

**Usulan rekonsiliasi:** jika event timeout kemudian memperoleh bukti crossing/arrival kendaraan yang sama, perbarui atau supersede event tersebut; jangan menambah +1 kedua. Bila bukti berikutnya membantah estimasi, hasil offline memerlukan revisi yang tersimpan. Kebijakan revisi ini belum disepakati atau diimplementasikan.

## SWOT tiga jalur

| Jalur | Strength — kekuatan | Weakness — kelemahan | Opportunity — peluang eksperimen | Threat — risiko |
|---|---|---|---|---|
| Garis + margin | Bukti crossing dapat ditelusuri ke BC, frame, segmen dan arah. Pita berpotensi membantu membedakan sentuhan dari perpindahan sisi. | Margin terlalu lebar menunda atau menggagalkan konfirmasi; terlalu sempit sensitif terhadap jitter. Nilai yang tepat belum diketahui. | Bandingkan beberapa half-width eksplisit pada trajectory tersimpan; audit sentuh-kembali, gerak paralel, endpoint dan dua arah. | Menganggap masuk pita = crossing menghasilkan hitungan saat kendaraan berhenti/jitter. Ketebalan bbox gabungan rider juga dapat menggeser BC. |
| Polygon berbeda setelah gap | Dapat memulihkan passage yang garisnya tertutup, bila identitas dan koridor benar. | Crossing sebenarnya tidak terlihat. Pengukuran sebelum dan sesudah gap belum menjamin kendaraan yang sama. | Cocokkan pasangan observasi, arah gerak, urutan waktu, kompetitor dan jalur yang mungkin; gunakan kasus positif serta kendaraan berdekatan yang harus tetap terpisah. | Salah menyambung kendaraan A dengan kendaraan lain di B; jalur di luar endpoint; dua count ketika direct crossing dan arrival sama-sama diterbitkan. |
| Timeout 60 frame otomatis | Menjamin aturan timeout menghasilkan keputusan otomatis sesuai pilihan pengguna, sehingga kasus tersebut tidak menunggu review. | Kekurangan bukti crossing/arah tetap ada; pending turun secara administratif tanpa bukti lebih banyak. 60 frame bukan durasi tetap antarsumber. | Ukur berapa estimasi timeout yang benar-benar cocok dengan passage fisik dan berapa yang harus dibatalkan; bandingkan dengan jalur measured pada cache yang sama. | Kendaraan berhenti di A, keluar sisi asal, salah deteksi sesaat, berganti jalur, video berakhir, atau ID baru muncul setelah timeout dapat menghasilkan false count/duplikasi. |

Contoh hipotetis: satu motor terlihat di A pada frame 100 dan berhenti sampai frame 200. Aturan “tidak mencapai B dalam 60 frame sejak masuk A” akan menambah +1 pada frame 160 walaupun tidak menyeberang. Jika timer dimulai setelah observasi terakhir, perilakunya berbeda. Contoh ini bukan hasil eksperimen TGDI.

## Lima istilah dengan contoh

1. **Kendaraan mandiri dan motorcycle+rider.** Mobil tunggal tetap satu car tanpa membutuhkan relasi rider. Motorcycle bersama rider/passenger tetap satu motorcycle. Untuk tampilan satu bbox, usulnya adalah bbox gabungan komponen yang sudah terasosiasi, berlabel motorcycle. Simpan bbox raw kendaraan/rider untuk audit dan tetap gunakan BC bbox **kendaraan terukur** untuk geometri. BC bbox tampilan gabungan dapat bergeser; menggantinya akan menjadi keputusan anchor baru. Motor bersebelahan tidak digabung hanya karena dekat.
2. **Overlap yang terjelaskan.** Contoh: truk dan motor berbeda mempunyai bbox bertumpang tindih ketika berpapasan, tetapi trajectory terpisah menunjukkan dua kendaraan. Keduanya boleh diproses sebagai unit berbeda setelah hubungan itu terselesaikan. Sebaliknya, dua bbox pada satu skuter adalah calon duplikasi. B v1 saat ini menahan setiap overlap raw vehicle yang belum dimiliki unit; jenis overlap perlu dibedakan, bukan semua overlap diabaikan.
3. **Kategori temporal.** Contoh hipotetis: ID42 mempunyai label car pada 29 observasi dan truck pada1 observasi. B v1 memerlukan label kendaraan seragam sepanjang episode sehingga bisa menahan kasus itu. Usulan konsensus temporal memakai dukungan observasi, confidence dan durasi untuk memilih kategori atau tetap ambigu. Angka29/30 hanya ilustrasi, bukan threshold yang dipilih. Label bbox pada frame terakhir yang benar tidak otomatis menyelesaikan histori episode.
4. **Perlakuan gap.** Contoh: BC terlihat di A pada frame 100, tidak terukur101–110, terlihat di B pada111. Ini perpindahan ROI melintasi gap, bukan crossing garis yang diobservasi. Contoh lain: gap terjadi jauh sebelum garis, lalu kendaraan punya trajectory lengkap melewati garis; gap awal tidak semestinya otomatis disamakan dengan crossing yang hilang. Sambungan ID lama/baru tetap perlu bukti asosiasi.
5. **Passage berulang / genuine return.** Contoh: kendaraan yang sama benar-benar A→B, kemudian berbalik dan melakukan B→A. Ini dapat menjadi dua passage bila bukti keduanya lengkap dan kebijakan return mengizinkan. BC yang bergetar di sekitar garis atau ID yang berganti saat satu kali melintas tidak boleh menciptakan passage baru. Jeda waktu saja tidak membuktikan return.

## Pareto: fokus pada penghambat yang paling luas

**EXPERIMENT RESULT terdahulu:** batch TGDI B v1 menyimpan58 accepted dan1.825 kandidat pending. Tidak ada hasil B v2. Diagnosis di bawah dihitung ulang secara read-only dari byte laporan asli yang SHA-nya diverifikasi; [JSON diagnosis](../results/b_v2_pending_diagnosis.json) menyimpan sumber dan batas interpretasinya.

| Alasan | Jumlah kandidat terdampak, tumpang tindih |
|---|---:|
| Raw competitor belum terselesaikan | 1.216 |
| Belum ada bukti relasi identitas positif | 1.184 |
| Gap ambigu | 464 |
| Konflik kategori | 341 |
| Relasi di luar window passage | 168 |
| Return memerlukan review | 125 |
| Assignment alternatif ambigu | 114 |
| Konflik identitas transitif | 9 |

Dua alasan teratas bersama-sama muncul pada **1.721 dari 1.825 kandidat (94,3%)**, dengan 679 kandidat memiliki keduanya. Ada 844 kandidat yang hanya membawa salah satu atau kedua alasan tersebut. Ini peta prioritas, **bukan prediksi 844 event akan diterima**: deduplikasi, validitas passage fisik dan evaluasi kebijakan baru tetap diperlukan. Sebanyak 464 item adalah diagnostik gap, sedangkan 1.361 item adalah transisi geometri yang masih pending; keduanya bukan jumlah kendaraan fisik unik.

Prinsip Pareto di sini berarti memusatkan eksperimen pada sedikit mekanisme yang memengaruhi banyak kasus. Angka 80/20 bukan hukum atau target hasil. Menggambar ulang geometri penting untuk kesesuaian jalan, tetapi tidak otomatis menghilangkan kewajiban relasi identitas dan blok overlap dalam resolver lama.

Urutan eksperimen yang disarankan:

1. **Review koordinat native dan margin.** Ekspor geometri baru per video; periksa overlay di beberapa waktu dan arah. Belum mengubah rule penerimaan. Pisahkan dampak geometri dari dampak policy.
2. **Standalone acceptance.** Uji jalur kendaraan mandiri dengan trajectory/identitas yang didukung, tanpa mewajibkan relasi rider/duplicate pada setiap kendaraan. Motorcycle+rider tetap satu unit. Ini perlu pengganti bukti identitas yang eksplisit, bukan penghapusan semua pemeriksaan.
3. **Resolusi competitor.** Uji pembedaan kendaraan berbeda, komponen rider, duplicate bbox dan konflik yang benar-benar belum selesai. Jangan menggabungkan kendaraan berdekatan demi mengurangi pending.
4. **Margin dan kategori temporal.** Kalibrasi masing-masing pada kasus development. Pertahankan baseline dan ubah satu faktor per ablation agar penyebab perubahan diketahui.
5. **Jalur occlusion dan timeout otomatis.** Bandingkan setelah aturan waktu, arah, deduplikasi dan rekonsiliasi ditulis. Catat kontribusi estimasi terpisah; jangan menyembunyikan false count dengan menurunkan pending.

Awali replay dengan cache pengukuran Phase 8 yang sudah ada; detector, tracker dan ReID tidak perlu dijalankan ulang untuk eksperimen geometri/kebijakan ini. Memilih konfigurasi ReID/parameter tracker baru akan membutuhkan eksperimen berbeda. Jangan sekaligus mengubah semuanya.

## Bukti yang perlu direview

Gunakan segmen kontinu siang dan malam dengan reference passage manual, termasuk kendaraan yang tidak pernah menghasilkan kandidat. Pisahkan development dan hold-out sebelum memilih nilai; hasil hold-out tidak dipakai untuk retuning pada eksperimen yang sama. Reference minimal: video, interval frame, unit fisik, kategori, arah aktual/unknown, apakah crossing tampak, duplicate/same-unit/distinct-unit, dan catatan ketidakpastian.

Perbandingan B v1 vs setiap varian harus mencocokkan passage fisik yang sama: salah gabung, hitungan ganda, kendaraan terlewat, kategori, arah, sumber BC/crossing, kontribusi timeout, serta regresi baru. Tidak ada klaim accuracy atau manfaat kebijakan baru sebelum ada referensi dan eksekusi yang sesuai.

## OPEN sebelum implementasi counting baru

- Timer 60 frame dimulai dari pertama masuk polygon, observasi terakhir, atau titik lain? Apakah kendaraan yang masih terlihat/stasioner di asal tetap dihitung saat timeout?
- Frame 60 adalah 60 indeks frame sumber atau 60 observasi track? Pada FPS 30 sekitar 2 detik; waktu aktual mengikuti sumber dan tidak boleh diasumsikan selalu 30 FPS.
- Bagaimana video berakhir sebelum timeout, timeout berulang, objek keluar sisi asal, dan event yang kemudian terbukti salah diperlakukan?
- Apakah arah timeout boleh diasumsikan dari polygon asal, atau dilaporkan UNKNOWN? ID baru perlu dihubungkan ke unit lama sebelum `CHANGE_ID` dinyatakan terbukti.
- Apakah A/B harus menempel pita atau boleh ada area netral di antaranya? Apakah konfigurasi menjamin satu-satunya jalur A↔B melewati segmen garis?
- Berapa margin, dukungan temporal kategori, batas gap/assignment dan syarat genuine return? Belum ada angka baru yang dipilih atau diuji.
- Pilihan tampilan bbox gabungan tidak dengan sendirinya mengubah anchor counting. BC raw kendaraan adalah baseline; penggantinya membutuhkan keputusan dan eksperimen terpisah.

Editor dapat digunakan sekarang. Jawaban atas keputusan terbuka diperlukan untuk implementasi counting berikutnya; tidak diperlukan untuk mengirim koordinat draft. Seluruh snapshot B v1 tetap menjadi pembanding terpisah dan tidak dijumlahkan dengan varian baru.
