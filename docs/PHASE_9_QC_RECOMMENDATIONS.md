# Rekomendasi sistematis setelah QC B v4

Status: **PROPOSAL berbasis audit sumber, belum implementasi atau default produksi**.
Bukti: [paket QC](../results/phase_9/20261020_QC_BV4_SIANG/REPORT.md).
Semua rekomendasi memakai raw BC sumber, satu physical unit per passage,
timeout 60 frame sumber, dan pemisahan measured/inferred yang telah disepakati.
YOLO26M/BoT-SORT/ReID tetap arsitektur; model/weights baru tidak dipilih.

## Urutan penyelesaian

1. **P0 — perbaiki unit sebelum agregasi.** Historical retained clique hanya
   hipotesis hubungan, bukan canonical physical identity. Raw4480 dan 4552
   koeksis sebagai SUV dan motor berbeda; mereka tidak boleh disupresi ke satu
   pengukuran karena nama unit sama. Hubungan positif harus menyebut episode,
   interval, bukti pengukuran, tipe relasi, serta kontradiksi. Dukungan raw4552
   sebagai mobil di masa berikutnya tidak berlaku mundur pada episode motor.
2. **P0 — eligibility gerak fisik sebelum timer.** Static van/motor tetap
   +0 ketika bbox menyusut akibat occlusion. Net BC25 px/3 observasi ternyata
   dapat lolos pada objek parkir dan belum layak jadi jaminan approach. Uji
   kualitas anchor, konsistensi badan/roda dan konteks gerak; algoritme dan
   threshold masih OPEN. Pertimbangkan road eligibility ROI terpisah dari
   polygon arah, dengan review per video. Objek parkir yang kemudian berangkat
   tetap harus bisa eligible; jangan blacklist ID/koordinat selamanya.
3. **P0 — rekonsiliasi passage lintas ID dan kategori secara offline.** Satu
   MPV dengan bbox car/truck, satu motor dengan rider/muatan, atau tiga rawID
   pada satu motor bukan beberapa passage. Kategori tidak boleh menjadi syarat
   awal yang menyembunyikan kandidat duplikasi lintaskategori. Gunakan temporal
   graph episode dengan relasi SAME_UNIT, COMPONENT_OF dan DIFFERENT_UNIT;
   jangan global union-find seluruh riwayat rawID. Relasi yang ambigu tetap
   pending; dua motor berdekatan bukan otomatis satu unit.
4. **P0 — finalisasi sebelum subtotal final.** Cocokkan seluruh kandidat pada
   passage fisik yang sama sebelum agregasi: bukti terukur yang valid diutamakan,
   upgrade inferensi tidak menambah count, dan timeout alias dibatalkan bila
   passage sudah terwakili. Muatan motor3555 tidak menambah truck; rider+0.
   Label route LINE_MARGIN tetap dapat inferred. Measured tidak menjamin
   physical-unit uniqueness. Counterexample:3563+3555 keduanya punya pasangan
   crossing tetapi sumber memperlihatkan satu motor bermuatan kardus.
5. **P1 — role berbatas dan generik untuk komponen kendaraan.** Pertahankan
   parent episode yang didukung saat relasi lokal putus, hanya pada scope yang
   bisa dibuktikan. Bedakan positive observed role dengan inferred continuity;
   hentikan propagasi saat parent/objek berubah. Lengan2531 pada jendela truk
   bukan pedestrian. Kategori person, helmet, overlap atau tidak adanya parent
   motor saja tidak menjadi bukti pedestrian. Jangan memperluas label2958/3185.
6. **P1 — putuskan aturan band-born.** Raw49 memiliki pair31→32 yang melintasi
   finite line tetapi tidak membentuk origin sebelum crossing. Uji rute khusus
   untuk track pertama terlihat di band: observasi dua sisi yang nyata,
   arah konsisten, unit/role positif, finite intersection dan deduplikasi.
   Konfirmasi jitter/touch/endpoint perlu eksperimen; tidak mengubah gap menjadi
   measured dan tidak melonggarkan seluruh timeout.4552 juga perlu pemisahan
   unit dahulu, bukan langsung +1 dari setiap sign change.
7. **P1 — selesaikan taxonomy.** Usulan bisnis: pickup/cargo van pengangkut
   barang→TRUCK; SUV/MPV penumpang→CAR; minivan/angkot perlu keputusan eksplisit
   apakah CAR atau BUS terpisah. BUS memerlukan schema/prefix yang disepakati.
   Ini rekomendasi, belum pemetaan pengguna yang diterapkan. Empat passage
   2549, 3761, 4115, 4774 tetap tertahan kategori walaupun identitas fisik direview.

## Kontrak runtime yang perlu diuji

`pengukuran → episode observasi → unit fisik berbatas → role/komponen →
kandidat geometri → rekonsiliasi passage → kategori → hasil final → agregasi`

- Raw ID dan ID tampilan tidak menjadi identitas fisik global.
- Positive alias melanjutkan kandidat/clock yang sama; last-origin terlihat
  mereset clock. Handoff ambigu menahan estimasi terkait saja.
- Completed passage tidak dibuka ulang oleh rawID baru;4367 adalah ekor
  pickup4149 yang sudah counted, bukan return.
- Raw vehicle BC tidak diganti union box, rider BC, muatan, atau prediksi.
- Unknown tetap unknown, bukan pedestrian atau nol traffic yang terlewat.
- Keputusan +0 menyimpan alasan dan tidak menghilangkan pengukuran audit.
- QC dan machine merupakan snapshot berbeda; koreksi event didedup berdasarkan
  eventID dan reconciliation group. Primary4774 dan duplikat4820, serta
  2549/2561 dengan fragmen2560, tidak boleh menghasilkan +1 ganda.

## Input → proses → output eksperimen berikutnya

| Jalur | Input | Proses yang diusulkan | Output dan pengaman |
|---|---|---|---|
| Phase 1/5 | Source/hash, geometri native, kondisi/occlusion, posisi parkir/jalan | Review eligibility area dan kualitas anchor per video | Config eksplisit; pengendara di jalan dan kendaraan keluar parkir tetap tercakup |
| Phase 2 | Deteksi tersimpan beserta raw class/score, crop sumber | Bedakan duplicate class/cargo dari missed detection | Jangan langsung retraining atau mengubah NMS secara global; source cache di bawah confidence tersimpan tetap UNKNOWN |
| Phase 3/4 | Episode2445, 1107, 4552, positive/negative link, appearance yang benar-benar tersedia | Uji split/merge berbatas dan relasi negatif koeksistensi/arah | Pasangan salah gabung tidak dipaksa sama; vehicle-ReID final tetap OPEN |
| Phase 6 | Unit/role positif, geometri, semua kandidat termasuk noncandidate discovery | Uji finalizer dedup, stationary eligibility, clock dan band-born | Satu unit/passage maksimal1; measured/inferred dan unresolved dipisah |
| Phase 7 | Raw malam dan source/passage yang sama, config model/counting dibekukan | Uji policy terpilih pada malam sebelum tuning enhancement terpisah | Raw tetap kontrol; tidak mengasumsikan gamma memperbaiki counting |
| Phase 8 | Event final, koreksi/cancellation dan raw↔episode mapping | Rekonsiliasi panel dengan ledger dan audit sources | Tidak menjumlahkan machine+reviewed; tidak mengubah count lewat renderer |

## Regression cases yang sudah tersedia

Positif:3582 SUV satu measured passage;185 dengan rider166;54 pedestrian
bounded; satu unit2697/2706, 4251/4281, 4934/4946/4953, 3563/3555.
Negatif:25 kandidat stationary van, motor parkir, same-class ID reuse2445,
4480SUV dan 4552 motor yang koeksis, 4808 dan 4843 berbeda, arah4200 dan 4281
berlawanan, person2531 berupa lengan, dan EOF tidak ditambah frame.

Kasus bernuansa: band-born49, partial anchors dekat garis4614/4709,
reviewed physical category-open2549/3761/4115/4774, serta unresolved
1210/4200/4808/2958/3185. Jangan menyusun threshold hanya agar kasus ini lolos.

## Sebelum dipakai di seluruh video

Bekukan profil development setelah perbaikan P0; gunakan B v4 sebagai kontrol
immutable. Bandingkan physical passage yang sama dan juga source inventory
tanpa kandidat. Catat false count, duplicate, wrong merge, role/kategori/arah,
missed passage dan regresi; pending yang turun saja bukan kelulusan.
Lalu lakukan evaluasi prospektif pada tujuh video lain, termasuk kedua malam,
dengan source/geometri terverifikasi dan konfigurasi yang eksplisit. Jangan
menyebutnya blind jika sumber/output pernah dilihat. Model/counting/enhancement
tidak dituning bersamaan. Batas penerimaan numerik produksi belum ditetapkan;
tidak ada klaim akurasi, zero-error, atau generalisasi dari audit satu video.

Perbaikan berikut tetap notebook research version baru dengan hasil terpisah,
bukan Phase 10 refactor/UI/Docker/deploy. QC ini tidak mengimplementasikan atau
menjalankan rekomendasi di atas.
