<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Review aktual P0 B v5 dan kesiapan P1

Tanggal: 20 Oktober 2026, Asia/Bangkok.

**Keputusan: implementasi dan replay selesai; P0 belum lulus untuk mengganti
baseline atau dipromosikan ke P1 sebagai milestone yang sudah diterima.**
Riset P1 terisolasi dapat membantu menutup blocker, tetapi tidak mengesahkan
hasil counting baru sebagai hasil produksi. Tidak ada klaim akurasi atau
zero mistakes.

## Implementasi dan eksekusi

[Kontrak P0](B_V5_P0_CONTRACT.md) diimplementasikan pada helper B v5 terpisah
dan [notebook 09a](../notebooks/09a_p0_qc_replay.ipynb). Input pilot sebenarnya,
cache dan geometri terikat SHA; seluruh 9.128 frame TGDI-WEEKDAY-SIANG direplay.
Tidak ada model yang dijalankan ulang dalam replay P0. Snapshot B v4 dan paket
QC sebelumnya tetap immutable. Rekomendasi QC baru tidak dimasukkan sebagai
prediksi machine atau daftar raw ID yang di-hardcode dalam algoritme.

| Snapshot machine | Accepted operasional | Measured | Inferred | Pending |
|---|---:|---:|---:|---:|
| B v4 baseline |172|121|51|68|
| P0 v1 |120|97|23|59|
| P0 v2 |117|98|19|65|

Ini bukan total kendaraan benar. Pending antarversi mempunyai kandidat dan
scope episode berbeda; 68→65 bukan bukti tiga kasus lama selesai. Perbandingan
68 kasus lama, 16 cancellation proposals dan 10 discovery groups tersedia pada
[matriks sumber v2](../results/b_v5/review/pilot_v2_qc_matrix/comparison.json).

P0 v1 ditolak sebagai kandidat pilihan: co-motion/overlap lintaskategori
terlalu luas menahan motor185/205/235 dan truck4149 yang benar-benar bergerak.
Sebanyak 25 pasangan measured lama tidak mempunyai counterpart pasangan yang
sama dalam accepted baru; 22 ditemukan pada cancelled events akibat konflik
lintaskategori. Selisih bersih measured −24 juga mencakup satu witness baru,
sehingga bukan 24 individu yang telah dipastikan terlewat.

Guard seluruh sudut bbox juga menahan truck643 dan motor lain yang kemudian
memakai ID643, serta SUV4864 yang mengecil karena perspektif. Pada v2 guard ini
**dinonaktifkan untuk crossing terukur**, tetap diuji untuk eligibility
estimasi. Bukti sumber ada pada
[review anchor](../results/b_v5/verification/anchor_guard_review/source_pixel_receipt.json).

V2 memakai exact-frame high-IoU ambiguity hold, dengan kontrol IoU lama 0,59;
overlap/co-motion lemah menjadi audit-only. Relasi ambigu tidak digabung menjadi
satu identitas. Investigasi bersama mempertahankan pending per passage asal.
Perubahan namespace/family raw ID tanpa bukti kontinuitas menahan origin/timer
lama, termasuk ketika flag batas episode belum aktif.

## Temuan yang membaik dan blocker yang tetap ada

| Kasus sumber | Hasil v2 | Interpretasi |
|---|---|---|
| Kendaraan parkir2536/2584/2680/3512/4569 dan konteks4627 | Tidak mempunyai counterpart accepted sumber | Estimasi palsu target QC tidak diterbitkan; bukan validasi semua kendaraan parkir |
| Motor4934 kemudian person/rider | Timeout lama tertahan;4953 tetap satu event inferred | Tidak menerapkan role global; origin lama tidak dibiarkan menghitung saat raw ID masih terlihat sebagai person |
| SUV4480 dan motor4552 | Assignment independen dipertahankan | Historical clique tidak lagi menyupresi motor; motor belum menjadi accepted, kebijakan band-born masih open |
| Motor185/205/235 | Crossing measured kembali accepted pada v2 | Regresi v1 pada contoh ini berkurang |
| Motor4251 dan4281 | Keduanya masih accepted untuk satu motor yang sama | **Duplikasi residual terverifikasi; blocker P0** |
| Truck4149, SUV3582/4480 dan kendaraan lain | Konflik high-IoU masih dapat menahan passage nyata | **False hold/coverage blocker; P0 belum lulus** |
| Gradual same-class ID reuse2445 | Belum terbukti terselesaikan | Geometri saja belum memberikan batas episode fisik yang andal |

Dari 16 usulan pembatalan QC, 15 tidak mempunyai accepted counterpart sumber
pada v2; raw4281 masih mempunyai counterpart. Ini bukan klaim 15 masalah fisik
selesai: canonical keep seperti truck4149 atau car2706 juga dapat tertahan.
Mencegah event salah dengan sekaligus menghilangkan passage benar belum memenuhi
tujuan sistem. Ada 23 pasangan measured lama tanpa exact counterpart accepted
di v2; tidak semuanya otomatis merupakan miss fisik atau kesalahan baru.

[Ringkasan terstruktur](../results/b_v5/review/pilot_v2_summary.json) menyimpan
seluruh daftar tersebut. Empat kasus taxonomy2549/3761/4115/4774 tetap pending;
tidak ada pemetaan bisnis baru yang diam-diam dipilih.

## Eksperimen model yang benar-benar dijalankan

Setelah P0 v1 selesai secara software/eksekusi, eksperimen konfigurasi terpisah
dijalankan pada Kaggle. Gate tersebut **bukan** acceptance fisik P0. Confidence
0,25 dan 0,10 dibandingkan melalui dua actual predictions pada 600 frame sumber
identik, lalu tracker/ReID dengan state baru per varian. Detail dan keputusan
ada pada [review eksperimen model](MODEL_CONFIGURATION_EXPERIMENT_REVIEW.md).
Kedua cache baru kemudian direplay dengan policy P0 v2 yang sama. Confidence
0,10 belum dipilih menjadi default; YOLO26M/BoT-SORT/ReID tetap arsitektur.

## Keputusan terbuka dan urutan berikutnya

1. **Bukti same-unit/component yang cukup kuat.** Rekomendasi: bedakan duplikasi
   bbox, rider/cargo, serta dua kendaraan yang occluded; uji bukti positif dan
   kontradiksi episode. Menaikkan atau menurunkan threshold agar contoh lolos
   belum mempunyai dasar. Same-category4281/4251 dan false holds4149/3582 wajib
   masuk fixture temporal sumber berikutnya.
2. **Pemulihan origin setelah class/family berubah.** Rekomendasi: origin baru
   dibangun dari konteks kendaraan yang terbukti kembali valid; jangan mewarisi
   timer yang ambigu atau menahan satu raw ID selamanya. Aturan konfirmasi
   pemulihan dan batas episode gradual masih membutuhkan eksperimen.
3. **Kategori bisnis.** Rekomendasi yang belum diterapkan: kendaraan barang
   pickup/cargo van→TRUCK, kendaraan penumpang MPV→CAR; minivan/angkot/BUS perlu
   pemetaan eksplisit, termasuk konsekuensi schema/prefix BUS.
4. **Band-born dan role positif.** Rekomendasi: eksperimen terpisah dengan source
   BC, jitter/endpoint controls, role berbatas dan parent episode; bukan
   perluasan semua timeout atau semua raw person menjadi pedestrian.
5. **Model dan validasi luas.** Vehicle-ReID final, benchmark anotasi formal,
   batas penerimaan numerik, tujuh video lain dan berbagai kondisi malam tetap
   open. Raw tetap pembanding malam; belum ada fine-tuning atau enhancement
   produksi yang dipilih.

Pintu kelulusan berikutnya: duplikasi residual selesai tanpa salah merge,
passage nyata tidak ikut hilang oleh conflict gate, origin/timer tidak bocor,
serta keputusan panel/ledger dapat direkonsiliasi. Setelah itu profil dibekukan
dan dievaluasi pada video lain. P1 dalam dokumen ini adalah **prioritas backlog
QC**, bukan pengulangan Phase 1 inspeksi atau izin melompati Phase 10–13.

## Verifikasi dan batas

Tes baru, regresi B v4, validasi notebook, hash frozen inputs dan manifest hasil
dicatat di [verification](../results/b_v5/verification/). Review visual memakai
frame terpilih dengan receipt pixel, bukan menonton seluruh video secara kontinu.
Source-pair join adalah perbandingan dokumenter, bukan label ground truth.
Belum ada eight-video replay B v5, audit produksi, UI, Docker atau deploy.
