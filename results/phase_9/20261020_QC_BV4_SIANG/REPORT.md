# QC B v4 — keputusan lengkap dan rekomendasi

Tanggal 20 Oktober 2026, zona waktu Asia/Bangkok. **Audit AI atas sumber dan bukti
tersimpan; bukan ground truth formal atau hasil algoritme baru.** Scope:
TGDI-WEEKDAY-SIANG, 640×480, 9.128 frame, indeks0–9.127. Baseline machine tetap
172 accepted(121 measured/51 inferred) dan 68 pending. Model, counting, enhancement,
config dan ledger lama tidak diubah/dijalankan ulang.

## Hasil seluruh 68 pending

| Kelompok | Ditinjau | Rekomendasi selesai | Tetap unresolved |
|---|---:|---:|---:|
| Kontinuitas identitas |31|28|3|
| Role person |29|27|2|
| Konflik duplikasi |8|4|4|
| Total |68|59|9|

**59 rekomendasi selesai terdiri dari 57 kasus+0 dan 2 kasus+1.** Tidak ada case
pending yang hilang dari inventaris; join ke baseline memakai passage/episode,
bukan rawID saja. Nilai di atas adalah rekomendasi QC yang belum diterapkan:
machine belum menjadi 9 pending. Kasus-kasus software ini bukan 68 objek fisik.

- Identitas:25 kandidat pada van/truk parkir kanan, 1 motor parkir, 1riwayat2445
  berpindah dari motor jalan ke motor parkir, dan 1fragmen2560 yang sudah
  merujuk passage2549/2561 dapat ditutup+0. Menyambung ID tidak membuat objek
  parkir menjadi passage. Tiga kasus bergerak belum cukup bukti kontinuitas.
- Role:20 rider+0, 2 occupant/fragmen orang dalam kendaraan+0, 4 person tanpa
  passage+0, 1pedestrian54 direkomendasikan+1, dan 2 role tetap belum jelas.
  Person54 sudah mempunyai adjudikasi pada branch review-assisted lama;
  jangan menambahkannya lagi jika branch tersebut menjadi dasar.
- Duplikasi:2615/4990 parkir+0, 4820duplikat4774+0, SUV3582+1 car measured.
  Empat identitas passage lain berhasil direview tetapi kategori bisnisnya
  tetap OPEN. Rekomendasi+1SUV bersumber BC6346→6347 yang berturutan; koreksi
  identitas/kategori tidak mengubah gap menjadi measured.

[Seluruh 68keputusan dalam Markdown](PENDING_DECISIONS.md) ·
[CSV indeks](case_index.csv) · [ledger QC lengkap](review_decisions.jsonl) ·
[ringkasan terstruktur](qc_summary.json).

## Sembilan keputusan yang masih terbuka

| RawID/scope | Masalah | Perlakuan yang direkomendasikan |
|---|---|---|
|1210|Vehicle/person1269 dan continuation belum bisa disatukan dengan anchor kendaraan yang cukup.|Tetap unresolved; person BC bukan pengganti vehicle BC.|
|4200|Komponen4196/4200 serta kelanjutan sesudah7353 belum jelas.|Jangan sambung ke4281 yang bergerak berlawanan arah.|
|4808|Occlusion dan kelanjutan belum cukup;4843 koeksis sebagai objek berbeda.|Tahan estimasi; jangan alias hanya karena warna/dekat.|
|2958|Person kecil berjalan lalu bertumpuk dengan motor2982; target akhir mungkin berbeda.|Role per interval; jangan global pedestrian.|
|3185|Riwayat rider/vehicle; person5579 hanya sekitar 13×19 px.|Role/identity tetap unknown pada interval yang tak cukup detail.|
|2549/2561 dengan2560|Satu minivan/angkot putih-merah, physical crossing ada.|Putuskan mapping bisnis kategori; fragmen2560 tidak menambah+1.|
|3761|Pickup bergerak lalu rawID berpindah ke kendaraan parkir.|Pisahkan scope; putuskan pickup dalam taxonomy.|
|4115 vehicle|Minivan/angkot, raw class truck/bus/car berubah.|Putuskan mapping penumpang; jangan campur person4115 sesudahnya.|
|4774 dengan4820|Satu cargo van;4820 adalah duplikat.|Putuskan cargo van kategori apa; tetap satu physical passage.|

Usulan taxonomy:pickup/cargo van barang→TRUCK; MPV/minivan penumpang→CAR;
angkot perlu keputusan eksplisit CAR atau BUS terpisah. Ini belum diterapkan.
866unknown-person role keys di luar/dalam kandidat bukan target29 kasus ini dan
tidak otomatis selesai karena59 pending mendapat rekomendasi.

## Accepted juga mengandung kesalahan

QC tidak berhenti pada pending. Terdapat **16 event accepted unik yang
direkomendasikan dibatalkan**, dengan bukti dan eventID masing-masing pada
[accepted_event_actions.jsonl](accepted_event_actions.jsonl).

| Mekanisme | Contoh dan perlakuan |
|---|---|
| Static/BC berubah karena occlusion |2536, 2584, 2680, 3512, 4569: objek parkir;4627 mencampur Honda dengan van parkir.|
| Riwayat objek campuran |2583 motor parkir→bagian SUV;1107 pickup→fragmen motor;4567 van→Honda→motor.|
| Timeout passage balik palsu |4367 adalah ekor pickup4149 yang sudah counted A→B7422;4541 mengklaim B→A pada Honda yang terlihat mendekat.|
| Duplicate lintaskategori |2697/T1001 merupakan MPV yang sudah diwakili2706/C1003;3555/T1002 adalah muatan motor3563/M1054.|
| Duplicate komponen/ID |4934/M1074 dan 4946/M1075 bagian motor4953/M1073;4281/M1063 sama motor4251/M1062.|

Kasus4934/4946/4953 direkonsiliasi satu kelompok; event4934 tidak dibatalkan
dua kali walaupun ditemukan lebih dari satu reviewer.4953 tetap INFERRED
LINE_MARGIN.4251 measured, 4281 inferred.3563 dan 3555 sama-sama mempunyai
pasangan crossing tetapi sumber memperlihatkan hanya satu motor bermuatan.
**Mempertahankan121 pasangan crossing baseline tidak membuktikan121 unit unik.**

Kontrol tambahan seluruh 34 accepted timeout memiliki ledger tersendiri:
14direkomendasikan cancel, 20masih belum final secara QC.20ini bukan berarti
pasti salah; physical identity/category dan representation uniqueness belum
selesai dari sampel. Dua cancel lainnya berada di LINE_MARGIN. Pemeriksaan
ini belum menyatakan seluruh 138 event LINE_MARGIN telah diaudit penuh.

57penutupan+0 tidak mengurangi accepted karena awalnya pending. Dua usulan+1
dan 16cancel memberi delta bookkeeping parsial−14 pada subset keputusan yang
ditutup. **Jangan menyebut172−14 sebagai total traffic benar:** kandidat
category-open, accepted unresolved dan passage di luar kandidat masih ada.

## Rekonsiliasi inferensi yang tidak diterima

Koreksi terhadap interpretasi agregat pada review360° sebelumnya:

| Pencocokan artefak Bv3→Bv4 | Jumlah |
|---|---:|
| Inferensi Bv3 lama |463|
| Counterpart sumber yang cocok di Bv4 |44|
| Lama tanpa counterpart accepted sumber di Bv4 |419|
| Inferensi Bv4 baru tanpa counterpart accepted lama |7|
| Inferensi Bv4 total |51|

Jadi419 hilang dan 7 baru menghasilkan **selisih bersih412**, bukan daftar412
event lama yang semuanya hilang. Pencocokan memakai rawID/frame/bbox/index
sumber dan arah/kategori, bukan event hash antarversi.419bukan419kendaraan
palsu yang telah dibuktikan.

Seluruh 463 row dipetakan dokumenter.419tanpa counterpart dikelompokkan menjadi
190 progress kurang dari kontrol25 px, 91kurang dari 3 observasi kontinu, 87 endpoint
menjauh, 29context split, 16 pending identity/role, 5 retreat/turn, 1 guard lain.
Ini klasifikasi numerik artefak, bukan penetapan penyebab fisik semua 419.
Review visual terarah mencakup24 kasus lintasstrata, termasuk seluruh 9 OCCLUSION
lama dan 7new-only estimates dengan follow-up. Banyak contoh tambahan lama
adalah rider/komponen, parked bbox, atau kontaminasi rawID; tidak dikurangi lagi
dari subtotal Bv4 yang memang sudah tidak memuatnya.

[Mapping463 row](removed_inferences/exhaustive_mapping.csv) ·
[24review visual](removed_inferences/targeted_visual_decisions.jsonl).

## Passage di luar kandidat

Pencarian dimulai dari sumber tanpa overlay pada jendela awal/tengah/akhir,
lalu153 frame merata dengan interval60 frame sumber, dan perluasan lokal.
Ini bukan menonton seluruh 9.128 frame secara kontinu dan bukan benchmark blind.

- **Raw49:** motor berbeda dari 11, crossing BC31→32 terukur secara geometri,
  tetapi lahir di band dan tidak mempunyai event/pending. Rute band-born harus
  diuji; jangan melonggarkan timeout atau menerima semua jitter di garis.
- **Raw4552:** motor hoodie merah dan SUV4480 koeksis sebagai dua objek;
  historical clique4480/4552 membuat motor kehilangan kandidat independen.
  Kaitan4552 sebagai mobil pada waktu berikutnya tidak berlaku mundur.
  Ini confirmed wrong unit grouping; count/passage confirmation perlu gate.
- **Raw2771, 2643, 3255:** contoh sign change dari fragmen/duplikat kendaraan
  yang sudah mempunyai accepted2750, 2632, 3224. Bukti lebih kuat dapat upgrade
  +0; bukan+1 baru dari setiap ID.
- **4614, 4709/4630:** sumber memperlihatkan motor datang dan pair sangat
  dekat garis; ada band-born/duplicate-candidate issue. Label count tetap
  unresolved sampai unit dan konfirmasi route disepakati.
- Clip-start13/24, riwayat putih763/816/856, danEOF5298 tetap mempunyai batas
  bukti. EOF tidak ditambah frame. Mereka tidak diberi fake accepted event.

[Discovery ledger](unmatched/unmatched_passages.jsonl) ·
[inventaris sumber dan matching shortlist](unmatched/source_inventory.csv).
153 frame global dan 14 seed inventaris tidak dapat membuktikan tidak ada miss
lain. Temporal shortlist yang belum diadjudikasi ditandai jelas, bukan dipaksa
cocok dengan machine. Detector confidence di bawah ambang cache 0.25 tidak tersedia
untuk diagnosis; keberadaan source object tidak otomatis membuktikan detector
tidak pernah menghasilkan deteksi.

## Akar masalah dan keputusan sistematis

Prioritasnya adalah **unit fisik → eligibility gerak fisik → rekonsiliasi
passage → role/kategori → agregasi**, bukan menerima timeout yang tertahan.

1. Historical clique tanpa positive scoped proof tidak boleh menyatukan state
   dan menyupresi objek lain. Kasus4552 membuktikan kehilangan passage dari
   grouping, bukan masalah detector semata.
2. BC bbox yang menyusut di objek diam bukan physical approach. Gate25 px/3
   perlu revisi berbasis anchor quality/konteks gerak; road eligibility ROI
   per video bisa diuji tanpa mengganti garis demi subtotal.
3. Dedup harus mencakup kategori berbeda dan komponen cargo/occupant/rider.
   Satu physical passage diselesaikan offline sebelum menjadi subtotal final.
4. Role perlu temporal scope dan parent episode; person kecil/tertutup tetap
   unknown. Positive role tidak otomatis+1.
5. Band-born, taxonomy dan genuine return harus mempunyai aturan eksplisit
   serta counterexample test sebelum dipromosikan lintasvideo.

[Rancangan input→proses→output dan regresi per fase](../../../docs/PHASE_9_QC_RECOMMENDATIONS.md)
memberikan spesifikasi perbaikan. Implementasi baru belum dilakukan; hasil
machine berikutnya adalah NOT_RUN. Model dan enhancement tetap dibekukan.

## Kelengkapan, batas audit, dan langkah berikutnya

[COMPLETENESS.md](COMPLETENESS.md) memisahkan cakupan penuh artefak dan review
visual sampling.68 pending mempunyai keputusan/unknown dan bukti;34timeout
mempunyai status;463inferensi dipetakan;10discovery/diagnostic groups dicatat.
Semua 117 artefak baseline awal lolos pemeriksaan hash dan dicek kembali sebelum
penutupan. Detail verifikasi ada di validation.json dan evidence/manifest.json.

Audit ditutup pada scope di atas dengan unresolved yang eksplisit, bukan
menyatakan seluruh video terhitung benar. Tujuh video lain dan malam belum
divalidasi oleh QC ini. Rekomendasi dapat menjadi kontrak kandidat lintasvideo,
tetapi angka/ROI/aturan baru harus diuji pada sumber lain sebelum produksi.

Langkah berikut: selesaikan keputusan taxonomy dan kebijakan band-born;
implementasikan P0 pada versi penelitian baru yang terpisah; uji fixture
positif/negatif QC; replay cache pilot dan bandingkan physical passage yang
sama; baru validasi tujuh video lain termasuk malam. Pending turun bukan
satu-satunya ukuran keberhasilan. Refactor/UI/Docker/deploy tetap fase berikut.
