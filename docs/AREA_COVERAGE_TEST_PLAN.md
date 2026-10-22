# Area Coverage — rencana verifikasi

## LI-3 actual validation

201tests PASS:158existing pada system Python dan43LI-3 offline tests pada
source env. Ordinary tests tidak memanggil layanan. Raw-source pilot dan
recorded-code replay dijalankan terpisah.21calculation artifacts identik,
0differences; graph/candidate/class/time/capacity/decisions/CSV dan normalized
data termasuk perbandingan. Manifest checksum/completeness/DAG diuji.

Real-source cases dan synthetic cases dilabel terpisah. Source case inventory
mencakuponeway/alley/private/gates/bridges/grade/turns/gaps/unknown; source tags
tidak menjadi field verification. Synthetic cases melengkapi no/only/U-turn,
quarantine, source failures versus validempty, connector limits/barriers,
ranking/fallback, exact Python round threshold dan deterministic routing index.
[Review/evidence](LI_3_REVIEW.md). Test PASS tidak membuktikan semua real cases
atau accuracy ETA/population. Bagian D34 di bawah adalah riwayat.

## D34 — validasi aktual terbaru

158tests PASS:130baseline+8capacity+16motor/access+4Overture normalization,
0failure/error/skip. Command unittest discovery ada pada
[receipt](../results/location_intelligent/execution_d34.json).
Cases baru: split units/missing floors/height fallback/duplicate/immutability;
class-over-time/no-path fallback; denied network edges dan turn restrictions;
unknown barrier/evidence hash/config change; target connector cost/unbounded
snap; conditional-unresolved/private rejection; *_link parent rank;
specific motorcycle permission dan provider subtype/null preservation.

Source nyata2623record dieksekusi melalui LI-0/LI-1 dan capacity. Offline
replay identical; dua motor CLI fixture byte-identical. Source columns/types
yang dikonsumsi diperiksa, bukan exhaustive official schema validation. Graph
motor nyata/automatic connector-barrier generation/conditional parser belum
diuji atau dinyatakan ready. Hasil/report di
[results](../results/location_intelligent/README.md).

Status **LI-0/LI-1 dan LI-2 routing subset EXECUTED/PASS; accessibility policy BLOCKED**.
Command dan130 tes aktual ada di
[PROJECT_STATUS](PROJECT_STATUS.md#hasil-li-2-dan-limitation).
Tidak menjalankan retrieval, real-source routing, UI atau inference. Pemeriksaan dokumen
bukan hasil tes engine. Source dan observed notebook output:
[overview](LOCATION_INTELLIGENT_OVERVIEW.md), [spec](AREA_COVERAGE_SPEC.md).

## Prinsip fixture dan acceptance

Gunakan fixture lokal kecil dengan input/expected/source hashes; network dan
clock dikontrol pada tes. Pisahkan **reference parity N1** dari **policy baru
yang diusulkan**. Test tidak boleh diubah hanya agar angka cocok. Kelulusan
parity menunjukkan implementasi sejalan referensi, bukan kapasitas penduduk
atau akses jalan benar secara empiris. Approval rule bisnis adalah gate lain.

LI-1 mencakup payload/geometry/ID, projected area/distance, PointOnSurface
untuk polygon cekung/holes/multipart, selection numeric boundaries dan row
disposition. LI-2 menambahkan directed/parallel/tie/cost/connector/boundary
fixtures dan graph failures; bukan validasi physical/legal access R09 atau
seluruh N1/source routing. H01–H04 capacity, Q01–Q04 Recount dan P01–P02
PPAC belum diimplementasikan/dijalankan. Tidak ada real building snapshot
yang diuji; fixture berlabel SYNTHETIC, bukan gold dataset N1.

## Unit, geometri dan kapasitas

| ID | Kasus | Expected/reference atau gate yang harus dinyatakan |
|---|---|---|
| C01 | Lat/lon valid, NaN/Inf, bool, string invalid, swapped axis | Validator eksplisit sebelum projection/network; tidak memilih koordinat contoh |
| C02 | UTM utara/selatan, contoh N1, longitude180, polar, antimeridian | Contoh EPSG32748; kasus di luar domain memerlukan CRS/policy eksplisit, bukan zona tak valid |
| G01 | Polygon cekung/berlubang/multipart | Representative point vs centroid dibedakan; footprint area penuh dalam projected meters |
| G02 | Empty, invalid/self-crossing, non-polygon, malformed WKB | Error/reject ledger dan repair policy yang disetujui; tidak hilang tanpa jejak |
| G03 | Distance399.999m/400m/400.001m | Parity N1: masuk/masuk/keluar berdasarkan representative point, bukan nearest boundary |
| G04 | Standard area45/45+ε/550−ε/550; special550 dan lebih | Strict bounds sesuai SPEC, full footprint tidak di-clip radius |
| G05 | Unsupported class dengan subtype kosong, category special vs residential | Bekukan observed fallback N1; taxonomy baru diberi versi dan expected sendiri |
| G06 | Duplicate ID, geometri duplikat ID berbeda, source release berbeda | Duplicate policy/dataset identity eksplisit; tidak menjumlah hasil join berulang |
| H01 | Floors valid/fractional/0/negative/missing; height positive/missing | Source field dan Python rounding/fallback3m terlacak; unknown tidak dianggap1floor |
| H02 | Standard occupancy diubah, area/level berbeda | Parity: household4, occupied_units1 tetap; perubahan semantic memerlukan business decision |
| H03 | Apartment/dormitory/hotel known/unknown GFA | Unit/kamar/guest tidak tercampur; legacy dan corrected fields terpisah |
| H04 | Sum dengan null/malformed capacity dan hotel | Known subtotal+unknown count; jangan mengklaim lengkap lewat fillna0 |

## Routing dan data-source failure

| ID | Kasus | Expected/reference atau gate |
|---|---|---|
| R01 | Access distance100/100.1/125/125.1m | Parity CFG125: tiga pertama dapat menjadi candidate, terakhir tidak; business100 vs125 tetap OPEN |
| R02 | Nearest edge disconnected; edge kedua reachable | Periksa semua eligible candidates sebelum pemilihan; bukan nearest-road shortcut |
| R03 | Nearest reachable detour lama vs slightly farther route cepat | Parity memilih nearest reachable; minimum-time varian memerlukan approval dan comparison terpisah |
| R04 | Oneway, divided carriageway, missing U-turn, bridge/tunnel, service/gang | Graph asli tetap directed; tidak menambahkan koneksi atau reverse edge; access filter berbeda dari graph-path filter |
| R05 | Edge geometry terbalik, parallel edges, access di ujung edge | Distance, partial geometry dan actual edge keys konsisten dengan u→v dan path |
| R06 | Time7/9.999/10/lebih10; nilai tepat di sekitar pembulatan3desimal | Parity N1 strict<10 atas nilai yang sudah dibulatkan; perubahan full-precision bukan fix diam-diam |
| R07 | Reachable tetapi time≥limit; route reconstruction gagal | Route bukan otomatis accessible; reason/flag/provenance konsisten, false route tidak tampil valid |
| R08 | Store snap jauh/di luar graph; candidate di luar request coverage | Snap offsets/coverage explicit; jangan mengeluarkan road length pendek sebagai perjalanan endpoint sebenarnya |
| R09 | Geometrically near road tetapi fence/river/entrance mismatch | Connector adalah asumsi, bukan akses fisik yang terverifikasi; limitation/policy tercatat |
| S01 | Provider timeout/auth/schema/release error | FAILED/PARTIAL/null sesuai scope, bukan count/demand0 atau silent provider replacement |
| S02 | Valid query benar-benar kosong; area tidak tercakup | Empty observed dataset dibedakan dari coverage gap dan retrieval failure |
| S03 | Missing dependency/extension, graph kosong, no directed path | Error setup terpisah dari no-path per building; Area tidak bergantung BigQuery similarity |
| S04 | NOT_ATTEMPTED vs unavailable vs successful empty vs request failed | Availability tidak digabung; no request bukan error query, row_count null berbeda dari0 |
| S05 | Frozen fixture synthetic/real, schema mismatch, stale policy unknown | Hash/schema/mode dinyatakan; offline bukan otomatis stale dan pass mock bukan pass provider |
| S06 | BQ/Overture/OSM adapter mocked vs real acquisition | Contract tests offline terpisah dari schema/permission/coverage/cost live evidence; downstream PPAC adapter tidak menggantikannya |

## Integrasi, Recount dan UI

| ID | Kasus | Expected/gate usulan |
|---|---|---|
| I01 | Home/context target diubah setelah Area/Traffic selesai | Revision baru, downstream STALE; hasil lama tidak berubah |
| I02 | Satu engine gagal, lainnya sukses; job dibatalkan/retry | Status independen; PPAC BLOCKED jika input wajib gagal; retry namespace baru |
| I03 | Rerender/navigasi/download/session berakhir | Tidak memulai job, kehilangan run identity, atau menampilkan hasil target lama sebagai target baru |
| Q01 | Polygon Recount valid/invalid, holes, boundary points | Predicate/boundary disetujui dan versioned; label map cocok tabel membership |
| Q02 | Dua polygon overlap dengan shared building | Per-polygon boleh overlap, union unique source building key; capacity tidak didobelkan |
| Q03 | Polygon sebagian/seluruhnya di luar snapshot | Coverage limited/blocked eksplisit atau retrieval baru yang disetujui; bukan0 untuk bagian tak diambil |
| Q04 | All-footprints vs eligible vs accessible | Universe dan denominator jelas; filtered N1 tidak menyamar menjadi complete inventory |
| E01 | JSON/CSV/GeoJSON/HTML export lalu reload | CRS/units/count/ID/checksum konsisten, null dipertahankan, nested capacity JSON aman, no NaN/Inf |
| E02 | Empty layer dan export failure setelah beberapa file ditulis | Manifest membedakan empty/absent/partial; final success hanya setelah output wajib diverifikasi |
| P01 | PPAC formula/Excel/constant/unit/normalization belum approved | BLOCKED dan SPD null, bukan ilustrasi numeric |
| P02 | Recount source atau Traffic branch/model version berbeda | Join lineage gagal jelas; tidak memakai hasil yang kebetulan punya store name sama |

## Regresi Traffic Counter yang wajib dipertahankan

Tidak menjalankan inference ulang untuk memvalidasi dokumen. Saat adapter
aplikasi kelak dibuat, verifikasi hash/retention B v7/B v8, lalu jalankan tes
yang relevan menurut [kontrak P1](B_V8_P1_CONTRACT.md) dan source-bound fixtures.
Angka302 tes pada [review P1](B_V8_P1_REVIEW.md) adalah hasil historis, bukan
tes Area Coverage atau tes yang dijalankan ulang dalam tugas ini.

Coverage regresi minimal: satu unit/satu passage; measured BC dari kendaraan,
rider+0, raw ID change tidak membuka passage baru, blue destination presence
tidak menjadi crossing, verified genuine return berbeda dari jitter, origin/
timer isolation, timeout60 sourceframes tetap estimasi, conflict/unknown tidak
dipromosikan diam-diam, dan machine/reviewed tidak dijumlahkan. Assertion
1049→1123 dan4843 harus mengikuti scope reviewed/source bukti yang ada; jangan
menyalin label kasus tersebut ke video lain.

## Gate readiness berikutnya

G0 source/config/decisions dan context jelas → G1 offline unit/predicate/schema
fixtures lulus → G2 directed routing/repro/export lulus → G3 source integration
dan real Area E2E, kemudian Recount pada scope berlabel → G4 business/PPAC
empirical evaluation. Detail urutan dan batas tugas mengikuti
[roadmap](IMPLEMENTATION_ROADMAP.md), bukan hasil tes yang sudah dieksekusi.
Setiap gate menyimpan command, environment, hashes, expected/actual, failures,
unknowns dan artifact refs. Numeric acceptance empiris belum ditentukan;
jangan mengklaim production-validation dari output contoh notebook.
