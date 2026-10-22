# QC kontinuitas identitas — 31 kandidat timeout B v4

## Cakupan dan hasil

Audit ini membaca 31 pending `IDENTITY_CONTINUITY_UNRESOLVED_FOR_TIMEOUT`
TGDI-WEEKDAY-SIANG dari snapshot machine B v4. Video dan cache diambil kembali
dari Kaggle, lalu diverifikasi SHA sesuai sumber yang dipakai B v4. Source
didekode berurutan 9.128 frame; **282 frame unik benar-benar ditinjau melalui
34 contact sheet**, dengan pixel source dicocokkan terhadap cache. Decode penuh
bukan review manual seluruh frame. Review ini sudah mengetahui hasil model,
bukan blind, dan bukan ground truth formal.

Tidak ada executable, config, baseline, model, counting, atau enhancement yang
diubah/dijalankan ulang. Keputusan berikut adalah **adjudikasi QC AI yang
diusulkan**, disimpan terpisah; ledger machine tetap 31 pending.

| Hasil QC kandidat | Jumlah | Kontribusi tambahan kandidat ini |
|---|---:|---:|
| Van/truk parkir di kanan depan bangunan; bbox berubah saat terhalang |25|+0; tidak eligible |
| Motor merah parkir di kanan van |1|+0; tidak eligible |
| Raw ID2445 berpindah dari motor bergerak ke motor parkir; episode campuran |1|+0 untuk kandidat timeout campuran; telusuri episode awal terpisah |
| Fragmen2560 bagian passage minivan putih-merah yang juga direview2549/2561 |1|+0 tambahan; satu passage bersama, taxonomy tetap perlu keputusan |
| Motor bergerak yang kelanjutan passage/anchor-nya belum cukup jelas |3|Unresolved; jangan otomatis diterima |

**28 kandidat dapat diusulkan ditutup sebagai +0/tidak eligible atau fragmen
duplikat. Tiga kandidat tetap unresolved.** Ini bukan 28 kendaraan fisik dan
bukan penambahan 28 hitungan. Sebanyak 25 kandidat di kelompok pertama mengacu
pada kendaraan parkir yang tampak sama pada interval-interval bukti, bukan 25
kendaraan berlainan.

Lihat [31 keputusan lengkap](per_case_decisions.jsonl),
[ringkasan CSV](decisions_summary.csv), [manifest bukti](evidence_manifest.json),
[251 verifikasi frame awal](source_pixel_checks.json), dan
[40 verifikasi frame fokus](focus_pixel_checks.json). Kedua himpunan frame
memiliki overlap, sehingga total uniknya 282.

## Temuan akar masalah

### Objek parkir: menyambung ID tidak menyelesaikan eligibility

Contoh raw228: f253 melekat pada van/truk parkir dengan ID214; f268–276 berubah
menjadi 228. MPV lewat menutupi bagian bawah van, sehingga bbox mengecil pada276.
Pada306/336 van masih berada di lokasi yang sama relatif terhadap bangunan.
Tidak ada bukti kendaraan parkir itu melakukan passage di frame-frame review.

Pola yang sama terlihat pada raw340, 387, 756, 1134, 1304, 1648, 1745, 1843, 1837,
2282, 2374, 2413, 2535, 2544, 2708, 2722, 2931, 3253, 3557, 3678, 3778, 3976, 4525, 4944.
Beberapa bbox melekat pada kaca depan saja saat tertutup motor/person di jalan.
Perubahan bottom-center bbox tersebut tidak menunjukkan perpindahan fisik
van/truk. Kategori `car↔truck`, ID baru, dan clock yang habis tidak memperbaiki
ketiadaan passage.

Ini mendukung penutupan kandidat terkait sebagai `NOT_ELIGIBLE/+0`, bukan
melonggarkan linkage kemudian menghitung timeout. Handoff ID pada kendaraan
parkir boleh benar secara identitas, tetapi kontribusi passage tetap nol.
Observasi ini dibatasi interval bukti; kendaraan yang kemudian benar-benar
berangkat harus tetap dapat memperoleh eligibility baru.

### Batas episode kelas sama masih mempunyai counterexample

Raw2445 pada3717 menunjuk motor kecil di jalan jauh sebelah kiri. Raw2445
pada3976 menunjuk motor merah yang parkir di kanan van. Motor merah parkir
sudah terlihat pada sisi kanan ketika motor awal berada jauh di kiri, sehingga
kedua objek tidak dapat diperlakukan sebagai satu episode kontinu.

Keduanya berlabel motorcycle: perubahan kelas tidak diperlukan untuk terjadi
ID reuse. Kandidat timeout 4036 dari riwayat campuran ini perlu ditolak/+0,
sementara passage objek awal direkonsiliasi terpisah. Jangan menerapkan label
parkir secara global kepada seluruh raw2445. Ini counterexample baru terhadap
klaim bahwa pemisahan episode B v4 sudah menyelesaikan semua kontaminasi origin.

### Satu minivan, beberapa kandidat; jangan menambah hitungan lagi

Raw2557 pada4082 dan 2560 pada4088/4092 memperlihatkan minivan/angkot putih dengan
strip merah yang sama, bergerak B→A. Reviewer duplikasi menemukan passage fisik
yang sama pada raw2549/2561, termasuk BC kendaraan2549 pada4117→4118.

Pending raw2560 pada4152 harus direferensikan ke **QC_DUP_2549**, bukan menjadi
passage tambahan. Hubungan identitas source-bound ini tidak mengubah gap
2557→2560 menjadi crossing terukur. Pemetaan bisnis minivan/angkot belum
disepakati; resolusi identitas tidak mengesahkan kategori secara otomatis.

## Tiga kasus yang tetap unresolved

| Kasus | Bukti yang ditinjau | Mengapa belum menerima hitungan |
|---|---|---|
|IDENTITY-06/raw1210, pending1567|Motor1210 sebelum1511, person/motor1269 sampai1516, konteks1434–1570; motor1217 koeksis.|Relasi komponen/class jitter dan kelanjutan setelah1516 belum cukup direkonsiliasi menjadi satu passage. Person1269 tidak boleh menjadi pengganti anchor kendaraan.|
|IDENTITY-28/raw4200, pending7413|4196 person dan 4200 motorcycle koeksis pada7264;4200 terakhir7353; konteks sampai7410.|Dugaan handoff dapat sebenarnya komponen orang–motor. Jangan sambungkan ke4281 yang bergerak B→A, berlawanan dengan approach4200 A→B. Kandidat kelanjutan person4286 tidak otomatis memberi vehicle crossing.|
|IDENTITY-30/raw4808, pending7964|4778 terakhir7769, 4808 mulai7809/terakhir7907; konteks sampai7960 termasuk SUV yang menutup pandangan.|4808 dan 4843 koeksis pada7900 dengan bbox berbeda. Kedekatan/warna tidak cukup untuk menyamakan keduanya; accepted4843 tidak otomatis menyelesaikan passage4808.|

Tiga kasus ini tidak diberi nilai nol traffic fisik. Nilai kontribusinya tetap
unknown dalam ledger QC sampai continuity/role/anchor/passage direkonsiliasi.

## Rekomendasi sistematis untuk video lain

1. **Eligibility fisik sebelum handoff/timer.** Bukti bbox mendekati garis
   harus dibedakan dari bbox objek diam yang menyusut saat tertutup. Pelihara
   state konteks stationary/moving berdasarkan bukti temporal; jangan blacklist
   raw ID atau koordinat contoh. Pilihan algoritme/threshold perlu eksperimen.
2. **Review cakupan jalan.** A/B saat ini juga menerima kendaraan di halaman
   parkir. Pertimbangkan counting eligibility ROI koridor jalan atau zona netral
   parkir per video, dengan review manual dan pengujian agar kendaraan yang
   keluar dari parkir masih dapat eligible setelah benar-benar bergerak. Ini
   proposal konfigurasi, bukan perubahan geometri yang telah diterapkan.
3. **Hubungkan episode objek, bukan riwayat raw ID.** Koeksistensi objek dan
   object context harus dapat memutus episode walau kelas tetap motorcycle,
   seperti2445. ID display tidak menyelesaikan kesalahan sumber.
4. **Pisahkan komponen dari kompetitor identitas.** Relasi person–motor yang
   koeksis seperti4196/4200 perlu diuji sebagai komponen; kelas vehicle satu
   frame pada person tidak boleh otomatis membentuk kompetitor timeout yang
   memblokir seluruh passage. Tetap jangan menetapkan rider dari overlap saja.
5. **Satu indeks passage fisik untuk seluruh review.** Fragmen2560 harus menunjuk
   ke review2549/2561. Kelompok identity/duplikasi/role tidak boleh menghasilkan
   beberapa +1 untuk kendaraan fisik yang sama.
6. **Pengujian lintasvideo.** Bekukan keputusan development ini dan uji pada
   kondisi siang/malam serta geometri lain dengan kontrol model/counting tetap.
   Ukur false count, salah gabung, duplikasi, dan missed passage pada objek
   fisik yang sama, termasuk yang tidak pernah menjadi kandidat; pending turun
   saja tidak cukup. Angka25 px/3 observasi belum tervalidasi sebagai default.

Kontrak minimum yang dapat dipertahankan lintasvideo ialah stationary tidak
menjadi passage, raw ID bukan unit fisik, komponen rider+0, satu physical
passage maksimal satu kontribusi, dan gap tidak berubah menjadi pengukuran.
Parameter numerik, ROI, dan algoritme asosiasi tetap memerlukan validasi sumber
per video; audit satu video ini tidak membuktikan generalisasi.
