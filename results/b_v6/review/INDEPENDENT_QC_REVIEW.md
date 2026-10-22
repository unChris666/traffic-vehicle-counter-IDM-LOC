# QC independen B v6 — P0 masih terblokir

Audit ini membaca hasil final replay TGDI-WEEKDAY-SIANG, cache pengukuran yang
sama, serta frame sumber. Audit tidak menjalankan model, counting atau
enhancement. Berkas [independent_qc_review.json](independent_qc_review.json)
mencatat hash hasil final dan bukti setiap kesimpulan.

## Hasil yang benar-benar diperiksa

| Ukuran keluaran | B v5 | B v6 |
|---|---:|---:|
| Accepted |117|74|
| Crossing terukur |98|66|
| Inferensi/estimasi |19|8|
| Pending |65|24|
| Invalid ambiguity |0|84|

Agregat B v6 cocok dengan ledger aktif:71 motorcycle,2 car dan1 truck.
Tidak ada sumber komponen/person atau beberapa physical-context episode
tercampur dalam sumber event aktif pada pemeriksaan struktural. Ini pemeriksaan
perangkat lunak, bukan pengesahan kebenaran74 hitungan fisik.

Seluruh inventory QC lama tetap ditelusuri:68 pending,16 usulan pembatalan
accepted, dan10 kelompok discovery. Enam belas kontrol lama tidak lagi
memperlihatkan sumber duplicate yang diketahui masih aktif. Pemeriksaan itu
ternyata belum cukup untuk meluluskan P0.

## Blocker baru: satu motor menghasilkan dua event

Pada frame1300–1336, motor merah mendekati kamera di sisi kiri pickup Daihatsu
dan memiliki tracker1049. Motor tersebut tertutup motor dengan penumpang
berkerudung biru pada1340–1344; motor merah yang sama terlihat sebagai1123
pada1349–1355. Rangkaian sumber dapat dibuka pada
[bukti kontinuitas](independent_inferred_1049_1123_continuity.jpg).
Kesembilan frame didekode secara berurutan dari awal video dan pixel hash
dicocokkan dengan input cache sebelum bbox ditambahkan.

Hasil final tetap mempunyai dua event A→B untuk passage fisik tersebut:

| Raw ID | ID passage tampilan | Atribusi frame | Rute | Bukti |
|---|---|---:|---|---|
|1123|M2007|1396|LINE_MARGIN|Inferensi; bukan crossing terukur|
|1049|M2008|1396|ESTIMATED_TIMEOUT|Estimasi|

Pada scope QC ini terdapat1 passage fisik dan2 event aktif: sekurangnya satu
event berlebih untuk passage tersebut. Audit belum menerapkan pembatalan atau
memilih event canonical. LINE_MARGIN tidak otomatis berarti crossing terukur.

Diagnosis resolver: gap endpoint1336→1349 adalah13 frame dan masih berada di
horizon60 frame. Endpoint IoU0,0 gagal memenuhi kontrol0,59; perpindahan pusat
ternormalisasi0,643 melampaui kontrol0,1. Kandidat hubungan tidak pernah
diusulkan, sehingga finalizer memperlakukan keduanya sebagai unit terpisah.
Kontrol overlap endpoint statis melewatkan perpindahan kendaraan selama
occlusion. Audit tidak mengubah threshold untuk meloloskan contoh ini.

## Penurunan accepted dan invalid yang disengaja

Pencocokan sumber persis awalnya menjelaskan74 accepted lama yang tetap aktif,
40 yang menjadi invalid, dan3 yang tidak mempunyai witness sama. Tiga kasus
terakhir diperiksa terpisah tanpa melonggarkan matcher:

| Raw ID | Frame accepted lama | Witness invalid baru | Hasil pemeriksaan |
|---|---:|---:|---|
|506|598|563|Episode, passage dan physical context sama; semua pengukuran563–598 diperiksa|
|4558|7652|7649|Episode, passage dan physical context sama; pengukuran7649–7652 diperiksa|
|4953|8025|8018|Episode, passage dan physical context sama; pengukuran8018–8025 diperiksa|

Setiap frame interval tersebut memiliki pengukuran detector sumber dan tidak
melewati batas physical-context baru. Bukti visual dan verifikasi pixel berada
di [contact sheet](independent_transition_source_sheet.jpg) dan
[receipt decode](independent_decode_verification.json). Dengan supplement ini,
117 accepted lama terpetakan menjadi74 yang tetap accepted dan43 yang
disengaja menjadi invalid. Ini pencatatan perubahan kebijakan, bukan bukti43
hitungan palsu telah diperbaiki.

4251/4281 sekarang keduanya invalid dan tidak menambah accepted. Visual lama
menunjukkan satu skuter; perubahan2→0 menghilangkan duplikasi sekaligus
mengecualikan satu passage fisik.4953 juga menjadi invalid; pemulihan satu
motor dari riwayat4934/4946/4953 belum tercapai. Truck4149 di7422 menjadi
invalid, sementara false return4367 tidak aktif. Hal ini tetap kehilangan
cakupan, bukan pemulihan truck. Raw2445 menjadi invalid; pemisahan gradual
reuse generik masih perlu dibuktikan.4552 dan4480 terpisah pada7615, tetapi
4552 tetap open/band-born dan4480 invalid; pemisahan unit belum menjamin
semuanya terhitung.

84 invalid adalah jumlah scope kandidat/passage, bukan84 kendaraan fisik atau
84 kesalahan yang telah diperbaiki. Beberapa scope dapat merujuk kendaraan
fisik yang sama.24 pending tersisa terdiri dari22 role person,1 bukti gerak
inferensi3555, dan1 kontinuitas identitas unknown-person4175.

## Rekomendasi keputusan

**P0 belum lulus karena duplicate1049/1123 yang terverifikasi dari sumber.**
Pekerjaan P1 boleh berlangsung terisolasi, tetapi hasil ini belum layak
dipromosikan sebagai counting produksi atau dinyatakan bebas kesalahan.

Eksperimen berikutnya perlu menguji usulan handoff berbasis gerak untuk gap
occlusion, lalu merekonsiliasi passage sebelum finalisasi timeout/line-margin.
Relasi terverifikasi boleh mempunyai satu event; relasi relevan yang masih
ambigu mengikuti kebijakan invalid/+0. Memperbaiki identitas tidak menciptakan
crossing terukur selama gap. Gunakan kasus baru ini beserta contoh negatif
kendaraan berdekatan yang berbeda, arah passage berlawanan yang sah, perubahan
role dan penggunaan ulang ID. Hindari aturan runtime khusus1049/1123 atau
penyesuaian threshold hanya agar contoh ini berhasil.

Sesudah regresi targeted lulus, ulangi replay cache yang sama dan periksa
duplicate, salah gabung, estimasi palsu, intentional exclusions serta passage
terlewat. Pengujian role, band-born, vehicle-ReID dan malam tetap memerlukan
bukti tersendiri. Audit ini bukan benchmark berlabel dan tidak melaporkan
akurasi atau zero mistakes.
