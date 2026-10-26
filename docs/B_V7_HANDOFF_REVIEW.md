<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Review B v7 — konflik handoff dan keputusan P0

21 Oktober 2026. **EXPERIMENT RESULT:** implementasi terisolasi, regresi dan
replay cache penuh selesai. Duplikasi target1049→1123 tertahan melalui
invalid/+0. **P0 keseluruhan tetap BLOCKED:** review menemukan event4843 dengan
bukti origin dan destination berasal dari objek berbeda setelah occlusion.
B v7 belum menjadi default produksi dan tidak menetapkan accuracy.

## Scope dan sumber yang diverifikasi

Branch `work`, HEAD `806ae761998e487265f3a032d616a59af56bb9a7`.
Workspace memuat notebook/helper serta hasil eksperimen yang belum seluruhnya
tercermin pada commit tersebut. Perubahan pengguna yang sudah ada dipertahankan;
HEAD saja tidak dipakai sebagai bukti identitas executable.

Tugas aktif historis `PHASE_9_TASK.md` membatasi audit bukti. Brief terbaru
mengotorisasi implementasi dan replay cache **khusus investigasi blocker B v6**;
tidak mengganti baseline Phase8 atau mengotorisasi fase deployment.

**FACT:** 168 artefak manifest B v6 dan16 binding code/dokumen cocok. Snapshot
sebelum pekerjaan mengikat3.936 file historis. Video dan cache sementara sempat
hilang setelah resume; download read-only Kaggle memulihkan byte yang sama.

| Input | SHA256 |
|---|---|
| Video aktual | `5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1` |
| Cache track donor | `bc484aff0372242925f8b87e6d91ffc2ac11ae696ed3f59201a73d44f98a145b` |
| Geometri | `d4a3861f0a0130dc7fe0ba4cfe574b5ceeafd8cb9c7141be46ee4541163909d1` |
| Hasil B v6 pembanding | `82f80239e25e64386f0423a18817b2f87eac98b0e88e9d93081994d5b436ee3e` |
| Policy eksperimen B v7 | `9a53f2f7c1d1d3588b45bfedd1825d7e2e1a360d88ece4997c02d2484090d7fd` |

Detail: [source state](../results/b_v7/verification/source_state.json),
[restore receipt](../results/b_v7/verification/source_restore_receipt.json),
[freeze](../results/b_v7/verification/configuration_freeze.json), dan
[kontrak eksperimen](B_V7_HANDOFF_CONTRACT.md). Source video tidak dimasukkan
ke GitHub. Tidak ada YOLO, tracker, ReID atau enhancement yang dijalankan ulang.

## Akar masalah dengan 5 Whys

1. **Mengapa satu motor menghasilkan dua hitungan?** Raw1049 menghasilkan
   timeout dan raw1123 menghasilkan line-margin inferred; keduanya accepted
   A→B pada1396.
2. **Mengapa kedua kandidat berjalan sendiri?** Konteks/unit yang berbeda
   membentuk dua state passage, tanpa relasi konflik handoff yang relevan.
3. **Mengapa konflik tidak terdeteksi?** Pemeriksaan endpoint statis pada
   `_possible_handoffs` di `phase_8_b_v4_identity.py` mensyaratkan IoU≥0,59 dan
   perpindahan center ternormalisasi≤0,1. Pada sumber ini IoU0,0 dan
   perpindahan≈0,643; pasangan gugur walau gap13 masih dalam horizon60.
4. **Mengapa endpoint statis tidak cukup?** Kendaraan bergerak selama
   occlusion. Posisi box sebelum dan sesudah gap tidak harus beririsan pada
   koordinat waktu yang berbeda. Tidak tersedia bukti embedding ReID yang
   membolehkan identitas disahkan untuk pasangan ini.
5. **Mengapa kegagalan proposal menjadi duplikasi accepted?** `emit` dan
   pemeriksaan timeout pada engine B v5, yang dipakai B v6, memutuskan per
   state. Gate B v6 hanya bisa menangani konflik yang sudah diusulkan.
   Tidak ada pemeriksaan gerak lintas-kandidat sebelum publikasi final.

Penyebab primer adalah proposal asosiasi yang terlewat; finalisasi independen
memperbesar dampaknya. Mengubah timeout saja tidak menyelesaikan rute
line-margin inferred dan dapat menambah risiko hitungan palsu.

## Pemecahan MECE

Klasifikasikan setiap kegagalan pada **gate pertama yang gagal**, agar satu
kasus tidak dijumlahkan pada beberapa kelompok primer. Faktor berikutnya boleh
dicatat sebagai kontributor terpisah.

| Kelompok primer | Pertanyaan pembeda | Bukti dan status |
|---|---|---|
| Kepemilikan measurement/konteks | Apakah satu riwayat sumber mencampur objek fisik? |4843: motor biru sebelum gap, motor merah sesudahnya. Masih BLOCKED. |
| Hubungan antarkonteks | Jika konteks sumber terpisah, apakah hubungan lintas-ID yang diperlukan terlewat? |1049→1123: duplikasi baseline direproduksi; B v7 menahan dua kandidat. |
| State passage/finalisasi | Jika konteks dan relasi memadai, apakah state tetap membuka hitungan ganda atau return palsu? |Regresi timer/return lulus; tidak ada event tambahan yang berubah pada replay ini. Ini belum bukti semua state nyata benar. |
| Penyajian/rekonsiliasi | Jika event benar tersimpan, apakah panel/log/agregat berbeda? |Ledger dan delta log sesuai72 accepted; renderer video baru tidak dibuat pada tugas ini. |

Kesamaan raw ID dan kelas bukan pengganti pemeriksaan kelompok pertama.
Kesamaan trajectory bukan pengganti verifikasi identitas pada kelompok kedua.

## Implementasi dan hasil aktual

Helper [handoff](../notebooks/phase_8_b_v7_handoff.py) memakai lima pengukuran
berurutan pada masing-masing sisi gap, fit gerak dua arah, arah BC teramati,
gap≤60, irisan luas positif box yang ditranslasikan, serta veto identitas
berbeda yang terverifikasi. Tidak ada raw ID target di logika runtime.

Helper [counting](../notebooks/phase_8_b_v7_counting.py) membungkus engine B v6
sebagai kalkulasi kandidat privat. Gate bersama menyelesaikan konflik sebelum
mengembalikan ledger offline B v7. Dua kandidat yang tepat diberi invalid/+0;
pending lama tidak diubah. Log kandidat memiliki delta0 dan keputusan invalid
aktual di EOF9127, sementara waktu kandidat1396 tetap disimpan.

Percobaan center-inside-box awal gagal pada fixture; hasil dan sourcenya
dipertahankan. Revisi menggunakan extent kedua box untuk menyaring konflik
spasial, tanpa toleransi piksel baru. Ini perubahan desain development setelah
melihat target; belum hold-out atau validasi parameter produksi.

**EXPERIMENT RESULT — 9.128 frame sumber yang sama:**

| Output operasional | B v6 | B v7 |
|---|---:|---:|
| Accepted |74|72|
| Accepted measured |66|66|
| Accepted estimated |8|6|
| Estimated timeout |5|4|
| Estimated line-margin |3|2|
| Pending |24|24|
| Invalid/+0 candidate scopes |84|86|

Kategori B v7: motorcycle69, car2, truck1; bus/pedestrian accepted0. A→B26,
B→A46. Nol accepted bukan bukti kategori tersebut tidak ada. Runtime replay
cache187,76detik pada environment yang tercatat; tidak termasuk download,
seluruh QC atau inference model.

[Perbandingan event](../results/b_v7/comparison/full_pilot_v1/comparison.json)
menunjukkan72 event dengan isi counting yang sama,2 removed,0 added,0 changed
pada bukti/keputusan counting. Ada **17 perubahan ID tampilan A→B** karena
ordinal dihitung ulang setelah dua pengecualian, misalnya raw1179 pada1422
dariM2009 menjadiM2007. Ini metadata lintas-versi, bukan passage baru. Raw ID,
scope dan witness sumber mengikat padanannya. Source assignments dan component
links sama; tidak ada perubahan kategori/arah pada event yang tetap aktif,
atau upgrade inferred→measured. Semua pending lama sama secara semantik.
[CSV delta](../results/b_v7/comparison/full_pilot_v1/event_deltas.csv) memuat
source witness dan alasan perubahan.

| Perubahan material | Bukti | Dampak |
|---|---|---|
|1049 timeout1396 → invalid |Observasi sampai1336; dukungan fit1332–1336; gap13|Accepted−1 estimasi timeout |
|1123 inferred1396 → invalid |Muncul1349; dukungan fit1349–1353; source destination1396|Accepted−1 estimasi line-margin |

Keduanya satu motor merah menurut review temporal sumber. **Dua menjadi nol
mencegah hitungan ganda tetapi menghilangkan satu passage nyata dari accepted.**
Mesin tidak menghasilkan penyambungan identitas positif. Review manusia dapat
menetapkan satu unit dalam ledger reviewed terpisah pada pekerjaan berikutnya;
hasil itu tidak disisipkan ke machine aggregate eksperimen ini.

## Regresi dan QC independen

**EXPERIMENT RESULT:**211 tes software lulus: B v7 handoff24, counting15,
batch12, comparator14; B v6 terkait81 dan B v5 terkait65. Perintah dan log
individual ada pada [tests.json](../results/b_v7/verification/tests.json).
Fixture aktual juga deterministik saat diulang; replay penuh dilakukan sekali.
Tidak ada klaim uji determinisme seluruh video dua kali.

Validasi notebook awal menemukan cell ID yang belum tersimpan pada format4.5.
Setelah replay CLI, metadata `cells[*].id` dilengkapi. Snapshot eksekusi asli
tetap utuh dan seluruh source cell identik; perubahan ini bukan replay baru.
[Receipt koreksi metadata](../results/b_v7/verification/notebook_metadata_correction.json)
dan [pemeriksaan akhir](../results/b_v7/verification/final_checks.json)
memverifikasi kedua versi tanpa warning tersebut.

Kontrol mencakup motor berbeda yang mengikuti, arah berlawanan, jalur sama
dengan bukti DISTINCT, genuine return, rider, window bukti, gap, sentuhan box,
perubahan raw ID dan imutabilitas sumber. Kontrol genuine return yang eksplisit
adalah sintetis; tidak dibuat label return nyata baru dari agregat.

Kasus4251/4281,4149/4367,4934/4946/4953,2445 dan4552/4480 mempertahankan
keputusan baseline. Banyak kasus tersebut sudah invalid/+0; status yang sama
tidak membuktikan hitungan fisiknya selesai dipulihkan. Motor1101 yang mengikuti
dan1070 berlawanan arah terlihat berbeda dari1123 pada sumber; keduanya tidak
mempunyai accepted baseline pada scope ini, sehingga tidak dilaporkan sebagai
dua hitungan nyata yang berhasil dipertahankan.

[QC independen](../results/b_v7/review/INDEPENDENT_QC_REVIEW.md) menemukan12
kontrol aktual dengan keputusan yang sama. Inventory historis68 pending,
16 cancellation dan10 discovery tetap mempunyai case ID serta disposisi sumber
yang sama. Daftar tersebut merupakan inventory QC lama, bukan pending24 pada
hasil mesin terbaru.17 perubahan ID tampilan juga tercatat pada
[mapping CSV](../results/b_v7/review/display_id_mappings.csv).

Review independen memeriksa semua delapan estimasi baseline secara temporal
terbatas. **FACT:**4843 sebelum gap menempel motor biru; sesudah tertutup SUV,
bbox4843 mencakup motor merah. Event7935 A→B inferred memakai origin7899
dan destination7935 dari riwayat yang tercampur. Raw4808 sudah invalid dan
4913 tidak mempunyai event aktif; belum ada dasar menyebut kasus ini duplikasi
accepted kedua atau menetapkan besar kesalahan hitungnya.

[Bukti4843](../results/b_v7/review/independent_4843_identity_review.json)
dan [gambar temporal](../results/b_v7/review/inferred_detail_4843.jpg) membuktikan
konflik sumber yang harus diselesaikan. B v7 sengaja membatasi handoff lintas-ID,
sehingga event4843 tetap accepted seperti baseline. Ini blocker lama yang baru
ditemukan QC, bukan regresi akibat dua event target dibatalkan.

## Prioritas Pareto dan rekomendasi SWQOT

**PROPOSAL — Pareto kualitatif:** fokus pada kontinuitas identitas di titik
occlusion karena dua mekanisme yang kini terkonfirmasi berada di sana. Tidak
tersedia distribusi kegagalan global untuk menghitung atau menjanjikan80/20.

1. Buat fixture same-raw-ID/same-class lintas objek untuk4843, dengan dua motor
   berdekatan sebagai kontrol. Pisahkan origin/destination ketika kepemilikan
   measurement bertentangan; jangan mewariskan timer hanya karena raw ID tetap.
2. Uji bukti identitas positif yang berscope episode untuk mempertahankan satu
   kandidat eligible terkuat, termasuk1123 yang **tetap inferred**. Bedakan
   hasil reviewed dari prediksi otomatis.
3. Setelah dua mekanisme itu terkendali, validasi parameter pada video lain
   dan malam. Baru nilai kebutuhan perubahan model/ReID berdasarkan jenis
   kegagalan residual. Tidak langsung melakukan retraining atau tuning global.

SWQOT berikut memakai SWOT dengan **Q=pertanyaan validasi**; ini tambahan
analitis yang dinyatakan, bukan nama framework baku yang diasumsikan.

| Opsi | S — kekuatan | W — kelemahan | Q — pertanyaan validasi | O — peluang | T — ancaman |
|---|---|---|---|---|---|
|Pertahankan B v7 sebagai pengaman riset invalid/+0|Perubahan sempit, auditable, duplikasi target tertahan|Satu passage target hilang;4843 belum tertangani|Apakah motor berbeda yang tidak koeksis ikut tertahan pada video lain?|Perluas kontrol dan ukur trade-off false count/missed passage|Turunnya accepted dapat disalahartikan sebagai peningkatan kualitas |
|Eksperimen episode dan identitas positif bersumber|Berpotensi menangani fragmentasi dan perpindahan objek, lalu mempertahankan satu event valid|Memerlukan bukti serta validasi lebih luas; belum diimplementasikan di sini|Kapan origin/destination benar milik unit yang sama dan kapan harus diputus?|Mengurangi duplikasi sekaligus menghindari kehilangan passage akibat penolakan ambigu|False merge; bukti role/kategori disalahgunakan sebagai bukti identitas |

Rekomendasi: simpan B v7 sebagai eksperimen pembanding; prioritaskan opsi
kedua untuk blocker4843. Parameter jendela, vehicle-ReID final, hold-out
berlabel dan validasi malam tetap terbuka. Pending tidak ditargetkan nol.

## Keputusan

**Target regresi1049→1123: PASS untuk pencegahan duplikasi melalui invalid/+0.**
**Gate P0 keseluruhan: BLOCKED**, karena kontinuitas sumber4843 belum sah.
Satu passage target yang belum dipulihkan tetap menjadi kehilangan cakupan
yang disengaja pada kebijakan invalid, bukan kriteria baru yang diam-diam
membatalkan kebijakan pengguna tersebut. Detail
kriteria dan batas klaim ada pada [gate machine-readable](../results/b_v7/review/p0_gate.json).
Belum ada dasar menutup P0, mengganti baseline produksi, atau mengklaim zero
mistakes/delapan video reliable. Implementasi eksperimen dan validasinya selesai;
masalah counting secara keseluruhan masih terbuka.
