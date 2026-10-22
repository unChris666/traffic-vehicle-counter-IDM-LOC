# Review B v6 — kebijakan terbaru dan gate P0

20 Oktober 2026. **Implementasi, regresi dan replay pilot selesai. P0 BELUM
LULUS karena duplikasi fisik residual 1049→1123.** B v6 tetap profil penelitian.
Kelulusan software tidak sama dengan kelulusan counting fisik.

## Perubahan dan isolasi eksperimen

[Kontrak B v6](B_V6_USER_POLICY_CONTRACT.md) menerapkan keputusan pengguna:
konflik unit ambigu menjadi invalid/+0 per passage; origin/timer dilindungi;
arah balik yang valid tetap passage tersendiri; BUS beserta prefix B masuk
policy, panel dan CSV. Pickup→TRUCK; cargo van/minivan/angkot→CAR; BUS→BUS.
Pemetaan subtipe memerlukan bukti positif, tidak ditebak dari label COCO.
Unknown role/kategori tidak dipindahkan ke invalid begitu saja.

[Notebook 09c](../notebooks/09c_user_policy_replay.ipynb) memakai helper baru
`notebooks/phase_8_b_v6_*.py`. Pengukuran YOLO26M/BoT-SORT/ReID, raw preprocessing,
geometri native 640×480, half-margin 25px dan clock 60 frame sumber tetap.
Tidak ada model/encoder/enhancement dijalankan ulang atau threshold model
berubah. Review QC baru tidak disubstitusi menjadi prediksi machine. Frame index
berbasis nol. Identitas video/cache/geometri terikat SHA pada
[run final](../results/b_v6/execution/pilot_v6_machine_final/batch_report.json).

Sebanyak 1.544 file baseline, QC, eksperimen lama dan executable yang dibekukan
terverifikasi tidak berubah. Snapshot sumber aktual tersimpan di setiap run.
Run awal diulang setelah koreksi nama file audit standalone menjadi
`ambiguity_invalid_audit`; **hasil counting lengkap identik byte demi byte**,
bukan hanya subtotal. [Receipt pengikatan render](../results/b_v6/verification/final_render_binding.json)
mengikat video dari hasil awal ke hasil final identik tersebut.

## Hasil eksperimen aktual

Seluruh 9.128 frame TGDI-WEEKDAY-SIANG direplay dari cache yang sama.

| Snapshot machine | Accepted operasional | Measured | Estimasi | Pending | Invalid/+0 |
|---|---:|---:|---:|---:|---:|
| B v4 |172|121|51|68|—|
| B v5 P0 v2 |117|98|19|65|—|
| B v6 final |74|66|8|24|84|

Accepted B v6 terdiri dari 71 motorcycle, 2 car dan 1 truck; BUS dan pedestrian
accepted nol. A→B 28; B→A 46. Delapan estimasi terdiri dari 5 timeout dan 3
line-margin inferred. BUS nol tidak membuktikan tidak ada bus. Cache mentah
mempunyai 35 observasi berlabel bus pada lima raw ID; ini bukan 35 bus fisik,
dan tidak membuktikan subtipe bisnis minivan/angkot.

Angka 84 adalah **scope kandidat/passage invalid**, bukan 84 kendaraan fisik
atau 84 miss terverifikasi. Daftar kandidat berubah antarversi: 65→24 pending
tidak berarti 41 masalah fisik dipulihkan. Accepted 117→74 menunjukkan kebijakan
jauh lebih konservatif; penurunan itu bukan bukti peningkatan akurasi. Jangan
menjumlahkan accepted, pending dan invalid sebagai traffic total.

## Kasus sumber dan dampak terhadap cakupan

| Kasus | Hasil B v6 | Penilaian |
|---|---|---|
|4251/4281, satu skuter|Keduanya invalid; 0 accepted|Duplikasi target dicegah, tetapi satu passage fisik sengaja hilang; bukan pemulihan menjadi 1 count.|
|4149/4367, pickup biru dan fragmen belakang|Passage 4149 invalid; tidak ada accepted counterpart salah|False-return target tidak diterbitkan, tetapi crossing truck sebenarnya juga tidak dipulihkan.|
|4934/4946/4953, motor Gojek dan komponen person|Timeout konteks lama tidak accepted; 4953 juga invalid|Tidak ada dua count pada referensi ini; passage motor ikut dikeluarkan.|
|2445, konteks motor berubah bertahap|Kandidat terkait invalid|Belum membuktikan batas semua episode fisik dapat ditemukan otomatis.|
|4552 motor dan 4480 SUV|Assignment tetap dua unit; SUV invalid, motor belum accepted|Tidak salah digabung pada kontrol frame 7615; motor tetap persoalan coverage/band-born.|
|506/4558/4953, tiga source join awal kosong|Supplement temporal menemukan invalid lebih awal dalam konteks kandidat yang sama|Tidak dianggap miss baru hanya karena frame keputusan berbeda; exact matcher tetap.|
|**1049→1123, motor merah**|**Dua accepted A→B pada 1396: timeout 1049 dan line-margin inferred 1123**|**Duplikasi fisik residual terkonfirmasi; blocker P0.**|

Review 1049→1123 memakai decoding sumber kontinu dan
[sembilan frame bukti](../results/b_v6/review/independent_inferred_1049_1123_continuity.jpg):
motor merah terlihat sebagai 1049 sampai 1336, tertutup motor dengan penumpang
berbaju biru pada 1340/1344, lalu muncul sebagai 1123 pada 1349/1355. Kedua event
juga terdapat pada B v5; ini kegagalan residual, bukan kegagalan baru akibat B v6.

Gap 13 frame berada dalam horizon 60. Namun endpoint IoU=0,0 dan normalized
center jump≈0,643 tidak memenuhi gate lama IoU≥0,59/jump≤0,1. Pemeriksaan bbox
statis gagal menangkap perpindahan kendaraan selama occlusion. Timeout lama
1336+60=1396 masih aktif ketika episode baru juga menghasilkan event. Identitas
fisik sama belum tersambung, dan ketidakpastiannya belum dikenali mesin sebagai
konflik. Menambah horizon saja tidak menyelesaikan kasus ini.

[QC independen](../results/b_v6/review/independent_qc_review.json) menyimpan
kontrol, bukti decode dan supplement: 74 counterpart accepted +43 intentional
invalid menjelaskan 117 event B v5 secara dokumenter. Ini bukan inventory fisik
lengkap. Seluruh 68 pending +16 cancellation +10 discovery QC historis tetap
mempunyai entri review.

## Pending, panel dan ekspor

Pending 24 terdiri dari 23 scope unknown person/role/identity dan 1 kandidat
gerak fisik 3555 yang belum cukup. [Ringkasan kelompok](../results/b_v6/review/pending_group_summary.csv)
dan [frame/ID](../results/b_v6/review/pending_cases_grouped.csv) memberi aksi
berikutnya. Label manusia 54 tidak diam-diam dimasukkan ke branch machine.
Rider +0; peran positif tidak otomatis mengesahkan crossing/+1.

Panel menampilkan raw ID, ID passage final, parent rider, kategori×arah,
measured/estimasi, log VOID +0, invalid dan pending. Seluruh 9.128 frame video
H264 ditulis dan didekode ulang. Citra sumber native 640×480 dipertahankan,
panel terpisah; output 1280×1450, audio tidak disertakan. Pivot akhir dan
[CSV audit final](../results/b_v6/execution/pilot_v6_machine_final/weekday_siang/audit_exports/summary_pivot.csv)
cocok 74 accepted/66 measured/8 estimasi/84 invalid/24 pending. Invalid/cancelled
tidak masuk pivot accepted, termasuk pada checkpoint perantara. Machine dan
reviewed tidak dijumlahkan. Video lokal:
[TGDI-WEEKDAY-SIANG B v6](../results/b_v6/videos/TGDI-WEEKDAY-SIANG-b-v6-annotated.mp4).

**Batas metadata waktu:** invalid dibuat pada finalisasi offline. `frame_index`
row invalid adalah frame kandidat; renderer mengisinya sebagai `decision_frame`
bila field eksplisit tidak ada. Nilai itu bukan bukti kapan keputusan invalid
final tersedia. Gunakan `offline_attribution_frame` untuk lokasi audit, label
OFFLINE untuk semantik, serta log pembatalan EOF jika ada. Waktu finalisasi
invalid eksplisit perlu ditambahkan; panel ini tidak membuktikan hasil realtime.

## Verifikasi dan keputusan gate

**81 tes B v6 +65 regresi B v5 lulus.** Cakupan: ambiguous same/cross-category,
verified distinct units, raw ID berubah di origin, perubahan role, muncul
menjauh, genuine return, BUS/prefix, scope invalid, taxonomy berbukti, input
bindings, panel/export serta encode/decode sintetis. Bukti ada pada
[log tes final](../results/b_v6/verification/regression_tests_final.log).

Enam belas kontrol pembatalan lama tidak menemukan duplicate blocker tersisa,
tetapi screening estimasi menemukan blocker 1049/1123. **Gate P0 keseluruhan
BLOCKED.** Izin invalid untuk unit ambigu tidak mengizinkan dua event untuk
satu passage yang terverifikasi sama. B v6 belum menutup milestone P0 untuk
dipromosikan sebagai selesai. P1 sebagai riset terisolasi dapat membantu
menutup blocker, bukan mengesahkan hasil ini sebagai baseline produksi.

## Rekomendasi berikutnya

1. Jadikan 1049→1123 fixture temporal positif dengan kendaraan berdekatan,
   arah berlawanan, dua motor menyusul dan genuine return sebagai kontrol
   negatif. Simpan scope/bukti; hindari blacklist raw ID.
2. Eksperimen **konflik handoff yang memperhitungkan gerak selama occlusion**
   sebelum timer/estimasi final: usulan trajectory, kompatibilitas kategori dan
   arah, batas episode serta constraint dua unit berbeda. Ambiguitas terdeteksi
   menjadi invalid/+0; verified same-unit menghasilkan maksimal 1 passage.
   Penyambungan tidak membuat gap crossing menjadi crossing terukur. Jangan
   tuning threshold hanya agar satu contoh lolos.
3. Replay cache dan audit dampak terhadap kendaraan berbeda: false counts,
   duplikasi, salah merge, deliberate exclusions dan misses. Setelah blocker
   terselesaikan, tetapkan P0 kembali sebelum menutupnya dan melanjutkan P1.
4. P1 coverage: pulihkan unit berbeda yang terbukti, role berbatas, band-born,
   pemetaan subtipe berbukti dan metadata waktu audit. Vehicle-ReID final,
   benchmark berlabel/batas penerimaan dan video malam lain tetap terbuka.
   Belum ada generalisasi delapan video atau klaim zero mistakes.

| Pilihan | Strength | Weakness | Opportunity | Threat |
|---|---|---|---|---|
|Konflik handoff berbasis trajectory, konservatif invalid/+0|Menarget timeout duplikat dan dapat diaudit|Prediksi gerak tetap hipotesis; passage nyata dapat tertahan|Memulihkan maksimal 1 unit dengan bukti lebih kuat|Dua kendaraan dapat salah terkait jika constraint lemah|
|Memperketat semua timeout|Cepat mengurangi sebagian estimasi salah|Menambah undercount; margin inferred masih dapat duplikat|Ablasi kontribusi timeout dengan cache tetap|Penurunan estimasi disalahartikan sebagai counting lebih benar|

Rekomendasi: pilihan pertama sebagai eksperimen berikutnya. Mengubah model
belum mengatasi kegagalan clock/identity yang ditemukan ini.
