# B v8 / P1 — penyelesaian pending dan pemulihan passage konservatif

21 Oktober 2026. **REQUIREMENT:** pengguna mengotorisasi P1 melalui brief
yang disimpan pada `results/b_v8/verification/user_p1_brief.txt`. P1 adalah
eksperimen perbaikan lanjutan dalam prototype/audit, bukan pengulangan Phase1
atau pernyataan bahwa gate P0 mesin sudah lulus. Baseline B v7, source snapshot,
hasil dan seluruh manifest historis tetap dipertahankan.

## Baseline dan scope

Baseline aktual adalah
`results/b_v7/execution/pilot_v7_machine_final/weekday_siang/counting_result.json.gz`,
SHA256 `b72269090426172cd67f814a40403b2367151cbab80889fe6cb77ab37c183bad`.
Hasil:72 accepted,66 measured,6 estimated (4timeout,2line-margin),24 pending,
86 invalid/+0. Ini output operasional, bukan ground truth seluruh video.

Gunakan video TGDI-WEEKDAY-SIANG640×480, seluruh9.128 frame, geometri native,
cache YOLO26M/BoT-SORT/ReID dan raw preprocessing yang sama. Tidak ada inference
model, konfigurasi ReID baru, enhancement, tuning parameter, atau generalisasi
malam dalam eksperimen ini. Sumber input diverifikasi sebelum code baru.

Urutan kerja: verifikasi baseline → inventory24 pending → review bukti dan
fixture4843 → helper/tes terisolasi → freeze config → replay reviewed penuh →
perbandingan event/rekonsiliasi → QC independen → gate P1.

## Prioritas keputusan

1. Satu passage fisik terverifikasi maksimal satu accepted. Pergantian raw ID,
   keputusan, atau route tidak membuka passage baru.
2. Jangan membuat crossing/identity merge tanpa bukti. Kendaraan hanya muncul
   di destination dan menjauhi garis tidak otomatis eligible.
3. Selesaikan pending dengan alasan positif yang bersumber. Rider/komponen
   memberi tambahan0; unknown tanpa bukti tetap pending. Invalid ambiguity
   mengikuti kontrak B v6/v7 dan tidak menjadi nama baru untuk semua unknown.
4. Pulihkan coverage hanya setelah geometri, unit, kategori dan identitas
   memenuhi aturan. Inferred/timeout tidak dipromosikan menjadi measured.

Semua pengaman B v7 tetap berlaku: timeout60 frame sumber, raw vehicle BC,
finite line+margin, motion/eligibility guards, episode/timer isolation,
genuine-return evidence, source-scoped role, DISTINCT veto, dan joint offline
handoff publication. Jendela fit5 serta spatial gate B v7 tidak dituning.

## Cabang dan asal keputusan

**FACT:** baseline mesin B v7 tetap72/24/86. P1 menggunakan cabang baru
`review_assisted`; hasil cabang tersebut tidak dijumlahkan dengan machine.
Penurunan pending atau pemulihan pada cabang ini bukan bukti bahwa model
otomatis sudah belajar mengenali role/identitas baru.

- Gunakan overlay bersumber yang sudah menjadi konvensi B v4. Wrapper B v8
  menambahkan referensi type dan scope yang dibutuhkan engine tanpa mengubah
  executable adapter lama.
- USER_REVIEW hanya untuk keputusan yang benar-benar diberikan pengguna,
  terikat hash instruksi. Pemetaan raw ID/frame berdasarkan inspeksi AI tetap
  dicatat sebagai pemetaan bukti berbantuan AI. Pengguna tidak dianggap telah
  memberi anotasi setiap frame.
- Review AI lainnya mempertahankan
  `ADJUDICATED_AI_PIXELS_REVIEW` dan
  `NOT_NEWLY_ADJUDICATED_BY_USER`, berikut pixel/source receipts.
- Identity/role overlay berlaku pada scope per-track yang tepat; interval dan
  daftar raw ID tidak diperluas menjadi hasil perkalian yang menyentuh objek
  lain. Asumsi kontinuitas di antara frame review harus disebutkan.
- Tidak ada label warna/raw ID/case ID sebagai kondisi runtime. Identitas
  kasus hanya data fixture, overlay dan audit.

## Fixture blocker4843

**REQUIREMENT — keputusan pengguna:** passage motor merah dihitung tepat satu
kali. Motor biru yang muncul di destination dan menjauhi garis tidak mendapat
hitungan dari kemunculannya. U-turn atau passage biru terpisah tetap memerlukan
bukti crossing dan passage yang sah.

**FACT — bukti sumber development:** raw4808 sebelum occlusion memuat motor
merah; raw4843 memuat motor biru sebelum gap dan motor merah sesudah gap.
Raw4913 sesudahnya memuat motor biru pada sisi destination. Referensi rinci
berada pada `results/b_v8/fixtures/blocker4843/`.

Scope review harus memisahkan episode biru dari episode merah pada raw4843,
menutup/melindungi origin dan timer konteks sebelumnya, lalu menghubungkan
measurement merah yang benar dengan bukti review positif. Posisi BC berasal
dari bbox mentah sumber. Gap7907→7928 berisi20 frame tanpa observasi target;
pemulihan merah harus tetap **inferred**, tanpa trajectory atau BC buatan.
Box/penampilan destination yang tidak sempurna tidak sendirinya membatalkan
keputusan fisik yang diberikan pengguna, tetapi ketidakpastian sumber tetap
dicatat. Tidak ada alias raw4843 sepanjang video.

## Finalisasi pending yang dibatasi kandidat

Inventory authoritative berasal dari24 keputusan berstatus pending pada
baseline, bukan jumlah baris CSV lama atau inventory68 kasus QC historis.
Setiap kasus menyimpan unit/episode/passage key, raw ID, frame/detection/bbox,
reason lama, proof, reviewer origin, status baru dan evidence yang masih kurang.

Untuk review positif rider/penumpang/komponen, finalizer dapat menutup
**kandidat pending yang tepat** sebagai `resolved_not_eligible`, kontribusi0,
dengan alasan komponen tidak independen. Ini penggunaan status non-eligible
yang sudah ada, bukan kategori invalid baru. Bukti satu source point tidak
melabeli seluruh raw ID atau seluruh riwayat sebagai rider. Parent yang belum
diketahui tetap unknown; jangan mengarang parent, subtype atau alias.

Promosi accepted harus melalui replay geometri/eligibility yang sama dengan
B v7, bukan langsung karena role positif atau keputusan lama B v4. Khusus
person54, raw bbox/BC dapat berubah akibat truncation; status measured hanya
berarti crossing BC sumber sesuai kontrak, bukan waktu kaki fisik yang diukur
secara independen atau robustness yang sudah terbukti.

Simpan waktu kandidat asli terpisah dari waktu finalisasi EOF9127. Semua
penutupan menyimpan reason, exact witness, hash proof dan asal keputusan.
Pending yang tidak memperoleh bukti cukup tetap mempunyai next action yang
eksplisit. Tidak menambah accepted dari invalid/+0 atau penutupan komponen.

## Evaluasi dan gate

Jalankan seluruh211 regresi B v5/v6/v7 yang berlaku, lalu tes baru untuk
review scope, split/alias, blue-away, genuine return, kendaraan berbeda,
rider, timeout/inferred duplicate, finalisasi0, unknown dan provenance.
Fixture aktual mendahului replay reviewed penuh. Freeze source/config/proof
sebelum full replay; setiap perubahan setelahnya memerlukan run baru atau
receipt non-eksekutabel yang eksplisit.

Perbandingan harus menunjukkan accepted terukur/estimasi per route,24 kasus
asal beserta semua final disposition, invalid, event baru/diganti/dikeluarkan,
perubahan kategori/arah/ID tampilan, false merge atau coverage loss yang
terkonfirmasi, dan kasus tanpa bukti cukup. Bedakan koreksi sumber satu passage
dari tambahan passage; perbaikan origin pada event yang sudah accepted tidak
otomatis berarti accepted total bertambah1.

Gate P1 dilaporkan PASS, PARTIAL atau BLOCKED sesuai bukti aktual. Kelulusan
scope review tidak menetapkan kelulusan mesin otomatis, accuracy, zero mistakes,
malam/delapan video, atau produksi. Riwayat B v7 tetap utuh dan hasil reviewed
mempertahankan identitas serta provenance sendiri.
