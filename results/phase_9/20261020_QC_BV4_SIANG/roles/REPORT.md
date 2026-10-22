# QC role person — seluruh 29 pending B v4 TGDI-WEEKDAY-SIANG

Status: audit bukti selesai pada 29 kunci passage software yang dipilih. Ini adjudikasi AI dari sampel temporal, bukan ground truth formal, bukan audit seluruh 866 unknown-role keys, dan bukan perubahan pipeline.

## Cakupan dan integritas

- Source aktual: TGDI-WEEKDAY-SIANG, video SHA `5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1`.
- Cache Kaggle frozen SHA `bc484aff0372242925f8b87e6d91ffc2ac11ae696ed3f59201a73d44f98a145b`.
- 192 frame native unik didekode berurutan, dicek pixel SHA terhadap input detector tersimpan, dilihat lewat 29 contact sheet role, tiga sheet tambahan, dan satu sheet accepted-duplicate. Frame/scope yang benar-benar dilihat dicatat per kasus.
- Konteks yang dipilih tidak blind: reviewer sudah membaca pending dan relasi sumber. Tidak semua frame setiap interval diperiksa secara visual.
- Tidak menjalankan detector, tracker, ReID, enhancement, counting, atau renderer batch baru. Bounding-box pada sheet adalah alat penelusuran source-only, bukan pengukuran/count baru.

## Hasil rekomendasi QC

| Disposisi kandidat person | Jumlah | Dampak yang diusulkan |
|---|---:|---|
| Rider/passenger sebagai komponen kendaraan |20| Person +0; jangan otomatis menambah motorcycle baru. |
| Occupant truk/pickup |2| Person +0; kendaraan memakai event/BC kendaraan sendiri. |
| Person di bahu toko, tanpa bukti passage |4| Tidak eligible/+0; role tidak perlu dipaksakan menjadi pedestrian counted. |
| Pedestrian54 |1| +1 pada event terukur yang sama dengan adjudikasi review-assisted yang sudah disimpan; jangan tambah dua kali. |
| Role/identitas akhir belum cukup jelas |2|2958 dan 3185 tetap unresolved; tidak dipromosikan atau dinyatakan tidak ada passage fisik. |

Total: 27 kandidat memiliki rekomendasi keputusan QC, dua masih unresolved. Sebanyak 26 dari 27 rekomendasi adalah penutupan +0. Semua angka ini proposal adjudikasi; machine tetap172 accepted/68 pending karena ledger/config tidak diubah. Role orang tidak otomatis memperbaiki identitas, kategori, atau crossing kendaraan parent.

## Daftar seluruh kasus

| Raw ID | Frame sumber / keputusan | Role/keputusan QC | Parent kendaraan yang didukung konteks | Status |
|---|---|---|---|---|
|12|41 / 41|RIDER_PASSENGER|11|QC_DECIDED|
|54|127 / 127|PEDESTRIAN|—|QC_DECIDED|
|375|510 / 510|RIDER_PASSENGER|381; identitas parent di overlap belum dipastikan|QC_DECIDED|
|385|1044 / 1044|RIDER_PASSENGER|744|QC_DECIDED|
|1486|1677 / 1677|RIDER_PASSENGER|1483|QC_DECIDED|
|1651|1923 / 1983|RIDER_PASSENGER|1617|QC_DECIDED|
|1686|2002 / 2002|RIDER_PASSENGER|1688|QC_DECIDED|
|1687|2003 / 2003|RIDER_PASSENGER|1688|QC_DECIDED|
|1826|2139 / 2199|RIDER_PASSENGER|1822|QC_DECIDED|
|1948|2350 / 2350|RIDER_PASSENGER|1944; identitas parent di overlap belum dipastikan|QC_DECIDED|
|2195|3116 / 3116|RIDER_PASSENGER|2211|QC_DECIDED|
|2531|3997 / 3997|VEHICLE_OCCUPANT|—|QC_DECIDED|
|2958|4974 / 5034|UNKNOWN|—|UNRESOLVED|
|3239|5494 / 5494|RIDER_PASSENGER|3205|QC_DECIDED|
|3185|5579 / 5579|UNKNOWN|—|UNRESOLVED|
|3446|6105 / 6105|RIDER_PASSENGER|3450|QC_DECIDED|
|3434|6311 / 6371|ON_FOOT_NON_PASSAGE|—|QC_DECIDED|
|3593|6380 / 6440|ON_FOOT_NON_PASSAGE|—|QC_DECIDED|
|3844|6717 / 6717|RIDER_PASSENGER|3789|QC_DECIDED|
|4094|7063 / 7063|RIDER_PASSENGER|4089; identitas parent di overlap belum dipastikan|QC_DECIDED|
|4198|7329 / 7329|RIDER_PASSENGER|4166|QC_DECIDED|
|4244|7363 / 7363|RIDER_PASSENGER|4251|QC_DECIDED|
|4115|7326 / 7386|ON_FOOT_NON_PASSAGE|—|QC_DECIDED|
|4175|7354 / 7414|RIDER_PASSENGER|4200; identitas parent di overlap belum dipastikan|QC_DECIDED|
|4283|7451 / 7451|RIDER_PASSENGER|4306|QC_DECIDED|
|4397|7503 / 7503|VEHICLE_OCCUPANT|—|QC_DECIDED|
|4561|7685 / 7685|RIDER_PASSENGER|4558; identitas parent di overlap belum dipastikan|QC_DECIDED|
|4725|7885 / 7945|ON_FOOT_NON_PASSAGE|—|QC_DECIDED|
|4938|8012 / 8012|RIDER_PASSENGER|4953|QC_DECIDED|

## Temuan yang mengubah cara menyelesaikan pending

1. **Rider dan parent raw ID adalah dua pertanyaan berbeda.** Contoh375/1948/4094/4175/4561 tetap terlihat sebagai komponen orang yang duduk di kendaraan ketika parent terhalang atau bbox kendaraan lain bertumpuk. Role +0 dapat didukung secara fisik, tetapi parent ID pada interval overlap tidak boleh ditebak atau menyatukan kendaraan.
2. **Containment BC person100% di bbox motor terlalu rapuh sebagai satu-satunya bukti asosiasi.**1486/1483, 1826/1822, 3844/3789 memperlihatkan tubuh/kaki pengendara atau penumpang di luar bbox kendaraan. Ini tidak membuktikan pedestrian. Audit tidak memilih threshold pengganti.
3. **Person bukan hanya pedestrian atau rider motor.**2531 adalah lengan pengemudi keluar jendela truk hijau;4397 adalah pengemudi di kabin pickup hitam. Keduanya bukan unit lalu lintas orang yang mandiri. Rekomendasi kategori semantik `VEHICLE_OCCUPANT` adalah proposal, bukan taxonomy produksi baru yang diam-diam diterapkan.
4. **BC terukur masih dapat menyesatkan secara fisik ketika bbox menyusut.**3434, 3593, 4115, 4725 adalah person di bahu toko; mobil/motor foreground menyisakan head-only bbox. Pergeseran bottom bbox menuju garis tidak membuktikan orang berjalan ke garis. Timer60 frame tidak memperbaiki masalah tersebut.
5. **Satu raw ID tidak boleh diberi role global.**2958 muncul sebagai pejalan kaki jauh lalu bertumpuk dengan motor2982;3185 mula-mula rider dekat, lalu vehicle, dan akhirnya satu person bbox sekitar 13×19 px. Keputusan pada awal riwayat tidak membuktikan role/objek fragmen akhir.

## Temuan di luar pending: accepted duplicate4251/4281

Sheet tambahan7360, 7363, 7367, 7369, 7370, 7371, 7374, 7379 menunjukkan dua bbox vehicle pada satu motor dengan driver berhelm, anak di depan, dan penumpang wanita baju coklat/kain biru. Motor putih berlawanan arah adalah unit lain yang tetap terpisah.

- Keep `M1062`, event `b_v4_2749e461446564058a9407fd`, raw4251, B→A, LINE_MARGIN terukur, activation7369.
- Usulan cancel duplicate `M1063`, event `b_v4_90e26422bae172b528349fb5`, raw4281, B→A, LINE_MARGIN inferred, activation7371.
- Delta usulan: motorcycle B→A−1, inferred−1, measured0. Tidak diterapkan pada machine. Ini satu kasus tambahan accepted, bukan bagian dari 29 pending role atau otomatis kasus ke-9 pada delapan pending duplicate.
- Bukti lengkap: `accepted_duplicate_decision.json` dan `evidence/accepted-4251-4281-manifest.json`. Jangan membatalkan seluruh riwayat raw4281.

## Rekomendasi sistematis untuk eksperimen lintasvideo

| Masalah | Perlakuan yang direkomendasikan | Pengaman regresi |
|---|---|---|
| Relasi person–motor hilang singkat | Pisahkan belief role dari atribusi parent; gunakan scope episode lokal dan bukti sebelum/sesudah yang source-bound. | Tidak memperluas role melewati perubahan konteks; pedestrian di samping motor tidak dihapus. |
| Bbox rider keluar dari bbox motor | Evaluasi hubungan pose/kontak fisik dan gerak temporal yang benar-benar tersedia; jangan memakai containment sempurna sebagai satu-satunya gate. | Dua motor sejajar, penumpang side-seated, rider berhenti dan naik/turun motor. |
| Occupant kendaraan nonmotor | Bedakan person component occupant dari pedestrian; simpan parent vehicle dengan role scope. | Orang berjalan di samping truk tetap mandiri; BC kabin/lengan tidak menjadi crossing pedestrian. |
| Person statis lalu head-only karena occlusion | Gate kualitas anchor/ground support sebelum approach dan timeout; jangan mengganti rawBC dengan titik prediksi untuk membuat crossing. | Kendaraan/pedestrian benar-benar mendekat jangan terhapus; occlusion akhir tetap unresolved bila arah belum terbukti. |
| Bbox kendaraan duplikat bersamaan | Deduplikasi per unit fisik/passage dengan bukti sumber, termasuk identitas komponen yang konsisten. | Dua motor berdekatan tidak digabung; pergantian ID bukan passage baru. |
| Frame/ukuran terlalu kecil | UNKNOWN dengan alasan resolusi/occlusion; cari konteks tambahan sebelum melabeli. | Tidak mengubah semua UNKNOWN menjadi pedestrian atau rider demi pending turun. |

Peraturan tersebut masih PROPOSAL untuk diuji pada sumber lain, bukan jaminan sudah cocok untuk seluruh video atau malam. Bekukan controls dan uji kasus penyangkal serta hold-out video/episode yang tidak dipakai menetapkan aturan. Belum ada bukti baru untuk retraining YOLO atau model role baru.

## Berkas

`per_case_decisions.jsonl` mencantumkan scope, evidence hashes, parent uncertainty, rekomendasi counting, dan status NOT_RUN. `per_case_summary.csv` adalah ringkasan29baris. `summary.json`, `verification.json`, manifest native/extra, serta PNG/JPG bukti berada di subfolder ini. File helper audit hanya dibuat di `/tmp/qc-tools/roles_*.py` sesuai batas tugas.
