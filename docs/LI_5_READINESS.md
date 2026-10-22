# LI-4 readiness, reproducibility, dan persiapan LI-5

23 Oktober 2026. LI-4 PASS terbatas untuk paket offline N1. Analysis tetap
PARTIAL. Dokumen ini tidak mengimplementasikan LI-5 atau mengesahkan keputusan
Recount yang masih proposal.

## Arti lengkap dan PARTIAL

Ada tiga dimensi berbeda:

1. Kelengkapan paket: seluruh output wajib, source rows dan manifest konsisten.
   LI-4 sudah memenuhi gate ini pada N1.
2. Kelengkapan evaluasi skenario: akses dapat diputuskan atau tetap unverified.
   N1 masih 620 ACCESS_UNVERIFIED dari 1322 selected, dengan 23 restriction
   relations dikarantina dan acquisition jalan/features berbeda waktu.
3. Validitas dunia nyata: akses fisik/legal, 7km/h dan kapasitas belum disahkan
   oleh bukti lapangan/bisnis. Paket lengkap tidak otomatis production-valid.

PARTIAL tidak sama dengan satu lokasi pilot, dan menyelesaikan PARTIAL tidak
mensyaratkan semua bangunan accepted. Known denied/no-route/over-time boleh
menjadi hasil lengkap untuk scope yang dinyatakan. Missing/unknown tetap jelas.
Coverage map yang lengkap secara fisik tidak diasumsikan dari query sukses.

## Mengganti koordinat

LI-3 sekarang memakai cached Overture packet N1; prepare() menolak target/CRS
berbeda dari packet. Mengganti longitude/latitude saja belum menjadi alur
multi-lokasi. Lokasi baru membutuhkan bounded building acquisition/coverage
proof, target/metric CRS yang sesuai, graph+barriers+turns, frozen config/manifest,
dan validasi scope. Rules motor dapat direuse; data N1 tidak boleh direlabel
sebagai lokasi lain. LI-4 sendiri hanya membuka/mengekspor snapshot, bukan
mengambil sumber baru atau menghitung area untuk koordinat bebas.

## Keputusan reproduksibilitas owner

Owner tidak menginginkan hasil berubah pada running ulang koordinat sama.
Pada pemakaian normal, gunakan paket/snapshot yang sama dan konfigurasi,
source/code/software versions yang terkunci. Koordinat saja bukan identity
run; input data live dapat berubah meskipun koordinat sama.

- **Reopen:** buka paket LI-4 yang ada. Tidak ada re-fetch/re-routing.
- **Replay:** frozen sources/config/code/environment yang sama. Baseline LI-3
  mencatat 21 calculation artifacts byte-identical. Metadata run baru tidak
  boleh diperlakukan sebagai bukti perbedaan kalkulasi.
- **Refresh sumber:** operasi eksplisit pada run/version baru; historical
  packet tidak ditimpa. Hasil boleh berbeda dan delta harus diperlihatkan.

Existing LI-3/LI-4 menolak overwrite output dan memeriksa checksum. Belum ada
aplikasi multi-lokasi yang otomatis mengikat koordinat ke historical snapshot;
jangan mengklaim default aplikasi tersebut sudah diimplementasikan. Hash
checksum dan validasi environment adalah gate reproduksibilitas, bukan ukuran
akurasi dunia nyata.

## GitHub dan membuka review

GitHub blob viewer tidak mengeksekusi HTML. Unduh paket ZIP dari Release
`li4-n1-offline-review-v1`, ekstrak seluruh folder, lalu buka review.html.
GitHub Pages belum diaktifkan. Screenshot QA dapat dilihat langsung dari repo;
HTML standalone tidak memerlukan Python/server/internet. Link ekspor memerlukan
file tetangga dalam paket yang sama. Pada managed browser QA file:// diblok;
interaksi diuji offline menggunakan local HTML bytes lewat setContent.

## LI-5 — Recount, yang perlu disiapkan

Input wajib: verified LI-4/LI-3 packet N1, target+CRS+source/policy hashes,
polygon revision GeoJSON EPSG:4326, keputusan D06/D07, dan fixture harapan.
Tidak memerlukan sumber live atau perubahan model/routing.

Keputusan berikut adalah **PROPOSAL**, bukan keputusan owner yang sudah sah:

| Topik | Rekomendasi awal | Contoh/dampak |
|---|---|---|
| Universe | Laporkan semua source footprints sebagai konteks; selected dan accepted sebagai subtotal terpisah, unknown terpisah | Polygon bisa berisi 100 selected tetapi hanya 60 accepted; jangan menyebut keduanya angka sama |
| Predicate | Representative point berada di polygon; pertahankan footprint utuh | Bangunan yang sedikit menyentuh polygon tidak otomatis masuk |
| Boundary | Include boundary secara eksplisit (covers), lalu tes titik tepat di tepi | Keputusan deterministik pada titik batas; tidak memakai tolerance tak disepakati |
| Overlap | Per-polygon membership boleh overlap; gabungan dedup memakai provider+source version/snapshot+building ID | Satu bangunan pada dua polygon tampil di keduanya, union dihitung sekali |
| Coverage | Tidak auto-fetch; untuk v1 hitung hanya dalam universe analisis yang dibekukan dan laporkan bagian polygon di luar universe sebagai tidak lengkap | Building snapshot bbox lebih luas daripada radius seleksi400m; source extent tidak sama dengan calculated accessibility extent |
| Capacity | Per status dan unit; subtotal known beserta unknown count; mixed total null | Unit standard belum disahkan tidak berubah menjadi KK |
| Perubahan polygon | Simpan revisi baru dan membership delta; tidak mengubah original packet/routing | Edit polygon hanya memengaruhi membership/subtotal Recount |

Universe analisis, extent query bangunan, extent graph jalan dan physical map
coverage harus dibedakan. Untuk recount accepted/selected, jaminan evaluasi
hanya pada selected universe N1 yang disimpan; polygon di luar radius analisis
bukan cakupan lengkap meskipun footprints mungkin ada di bounded source cache.

Fixture minimum: di dalam/luar/tepat batas, footprint memotong batas, hole,
multipolygon, polygon invalid, polygon overlap, repeated revision, empty,
unknown access, null capacity, mixed units, dan polygon melampaui cakupan.
Expected membership dapat memakai fixture sintetis berlabel; tidak mengklaim
fixture sebagai kebenaran bangunan di lapangan.

Output LI-5 yang dituju: polygon/revision+hash, membership ledger per source key,
per-polygon subtotal, union dedup, status/coverage/units dan delta revisi.
Kelulusan: membership deterministik, no double union count, source immutable,
unknown tidak jadi accepted/0, ekspor/peta/tabel sama dan zero retrieval/routing
pada polygon edit. D06/D07 perlu disepakati sebelum implementasi semantics ini.
