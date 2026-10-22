# B v6 — implementasi keputusan counting terbaru

Status: versi penelitian baru untuk diuji; bukan default produksi. Otorisasi
pengguna: implementasi → regresi → replay cache pilot → penetapan gate P0.
Keputusan sumber: [POST_P0_POLICY_DECISIONS.md](POST_P0_POLICY_DECISIONS.md).
Hasil aktual akan dicatat pada [review B v6](B_V6_USER_POLICY_REVIEW.md).

## Input dan isolasi

Gunakan video, cache model donor, review lama, serta geometri native640×480
TGDI-WEEKDAY-SIANG yang sama dengan B v5. Model YOLO26M/BoT-SORT/ReID dan raw
preprocessing dibekukan; tidak ada inference, enhancement atau tuning model.
Executable dan hasil B v2–v5, paket QC dan eksperimen confidence tidak ditimpa.
Code/notebook baru dan output ditaruh pada namespace B v6.

## Hasil per passage

| Status | Kontribusi ke accepted | Arti |
|---|---:|---|
| Accepted measured |+1| Geometri terukur dan gate unit/kategori memenuhi profil |
| Accepted estimated |+1, terpisah dari measured| Timeout/rute inferensi yang memenuhi aturan; bukan bukti crossing selama gap |
| Invalid ambiguity |+0| Konflik unit/identitas relevan tidak terselesaikan; pengguna menerima risiko kehilangan passage |
| Pending |+0| Masih memerlukan role/kategori/bukti lain; tidak disamarkan sebagai invalid |
| Not eligible/component |+0| Tidak memenuhi passage atau komponen bukan unit kendaraan tambahan |

Invalid dibatasi pada kandidat/passage yang terkait konflik. Semua kendaraan
berdekatan tidak otomatis invalid. Algoritme tidak menggabungkan identitas fisik
ketika hanya menandai konflik. Jumlah invalid dilaporkan terpisah; tidak berarti
traffic sebenarnya nol. Scope klasifikasi status tidak boleh menjadi blacklist
raw ID seumur video.

## Duplikasi, arah dan clock

- Satu unit fisik per passage maksimal satu event aktif. Keputusan final dan
  pengelompokan tidak dibuat hanya dari raw ID atau kategori.
- Passage berlawanan arah yang sah tidak dideduplikasi. Mengubah arah sebelum
  crossing tidak otomatis menghasilkan passage baru.
- Timeout tetap60 frame sumber dari observasi origin terakhir, setelah
  eligibility terbukti dan tidak ada konflik identitas relevan. Kendaraan yang
  tetap terlihat belum dianggap hilang untuk menghasilkan timeout baru.
- Pergantian ID tidak membuka ulang passage selesai. Kandidat raw ID yang
  berpotensi saling menggantikan tidak diberi dua estimasi tanpa resolusi.
- Tidak memaksakan pemulihan origin ambigu. Origin/timer objek lama tidak
  diwariskan ketika kelas/family/konteks objek berubah tanpa bukti kontinuitas.
- Objek pertama muncul di polygon lalu menjauhi garis tidak eligible hanya
  karena keberadaannya. BC kendaraan mentah dan finite geometry tetap berlaku.

Kontrol geometris/numerik penelitian sebelumnya tetap eksplisit. Ekstensi
kandidat ambiguity same-category memakai kontrol overlap yang sudah ada, bukan
threshold yang dipilih untuk meloloskan satu contoh QC. Unknown role dan
kategori tetap membutuhkan bukti positif.

## Taxonomy, BUS dan role

Mapping terbaru: pickup→TRUCK; cargo van/minivan/angkot→CAR; BUS→BUS. Helper
taxonomy hanya menerapkan subtipe yang mempunyai bukti; tidak menebak subtipe
baru dari label COCO atau warna kendaraan. Raw bus didukung sebagai kategori
BUS dalam profil penelitian. Validitas hasil pengenalannya tetap harus diaudit.

**Pilihan implementasi:** BUS memakai prefix tampilan `B`, empat digit angka,
digit pertama genap untuk A→B dan ganjil untuk B→A, tanpa leading zero. ID
tampilan per passage tetap berbeda dari identitas fisik dan raw tracker ID.
Pivot/panel/CSV memuat motorcycle, car, truck, bus dan pedestrian.

Rider/passenger tetap komponen kendaraan +0. Gerak bersama merupakan bukti
pendukung; pedestrian yang berjalan di dekat motor, rider berhenti, pergantian
peran dan pengemudi di jendela kendaraan harus tetap dibedakan. Tidak ada role
global berdasarkan raw ID dan tidak ada model role baru dalam tugas ini.

## Panel dan ekspor

Panel video menggunakan final offline accepted ledger; invalid/pending tidak
menambah pivot kategori×arah, termasuk pada frame perantara. Audit log boleh
menampilkan riwayat pembatalan dengan status yang jelas. Raw ID, ID passage,
parent kendaraan, sumber crossing, invalid reason dan frame sumber dipertahankan.
Waktu atribusi passage pada video tidak disamakan dengan waktu tersedianya
keputusan offline. CSV accepted, invalid dan pending terpisah serta dapat
direkonsiliasi dengan snapshot yang sama.

## Gate scoped P0

Uji sintetis positif/negatif mendahului replay9128 frame. Kasus4251/4281 wajib
berakhir maksimal satu event atau keduanya invalid; bukan dua accepted. Kasus
raw ID berganti di origin,4934vehicle→person,4149/4367false return, kendaraan
muncul menjauh dan passage balik sah wajib diuji. Seluruh inventory QC lama
68pending+16cancellation+10discovery tetap mempunyai counterpart/status audit.

Gate dapat lulus untuk kebijakan penolakan ambigu yang disepakati apabila
regresi tersebut memenuhi kontrak dan tidak ada duplicate/timer leakage yang
terverifikasi tersisa pada scope audit. Kelulusan itu bukan bukti akurasi,
kelengkapan seluruh video/delapan video, atau zero mistakes. Intentional misses,
role yang pending, band-born, vehicle-ReID final dan validasi malam tetap dicatat
sebagai batas/pekerjaan P1. Jika blocker terverifikasi masih ada, gate tidak
dinyatakan lulus hanya karena pending berkurang.
