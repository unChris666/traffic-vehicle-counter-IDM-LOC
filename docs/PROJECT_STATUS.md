# Location Intelligent — status proyek terverifikasi

## Terbaru — LI-3 N1 actual pilot

LI-3 source/graph/connectors/replay sudah diimplementasikan dan pilot nyata
dijalankan. **Hasil PARTIAL; replay PASS**.201tests lulus (158existing+43LI-3),
0failure/error/skip.21calculation artifacts byte-identical pada replay code
snapshot tanpa source requests. [Review dan command](LI_3_REVIEW.md).

Overture nyata retained packet diverifikasi/re-normalize;1322selected dari
2623records. OSM nyata170557road-source elements dan13879feature-source
elements; normalized/split graph145318nodes,302820directed edges.641accepted
scenario,7over-time,54no valid connector,620unverified; seluruh2623rows
direkonsiliasi. Kapasitas per unit, standard5288unit unresolved, accepted
scenario2564pada unit sama; bukan KK/population.

Tidak ada timestamp-pinned feature retrieval yang sukses: timeout/memory
failures dipertahankan; successful source timestamps berbeda satu menit dan
shared elements cocok.53turn relations diaccount (30normalized/23quarantine).
Raw/evidence/CSV/map/manifest/code lock berada di
[pilot folder](../results/location_intelligent/li3_n1_20261022_v1/report.md).
Unknown/assumptions tetap terlihat. Produksi/actual travel-time/physical access
belum tervalidasi. Tidak menjalankan Traffic/UI/Recount/PPAC atau mulai LI-4.

Bagian berikut adalah riwayat status sebelum LI-3.

22 Oktober 2026. Scope terbaru: **LI-2 PARTIAL — routing subset PASS,
final accessibility BLOCKED**. LI-0/LI-1 tetap PASS untuk scope offline.
Seluruh graph/building tests memakai synthetic fixtures; tidak ada full Area,
capacity/Recount/PPAC, query BigQuery, request provider, download dataset atau
inference baru. Status lingkungan cloud hanya diperiksa untuk setup.

## Repository dan dasar bukti

Workspace `unChris666/traffic-vehicle-counter-IDM-LOC`, branch `work`, HEAD
`806ae761998e487265f3a032d616a59af56bb9a7`. `git status --short` memuat
perubahan pengguna `.gitignore`, `README.md`, `docs/PHASE_9_TASK.md` dan
banyak sumber/artifact untracked yang dipertahankan. Tidak ada pemeriksaan
GitHub remote pada tugas ini. Home/router/framework aplikasi terpadu belum
diimplementasikan pada repo ini; legacy di repo lain bukan runtime R1.

| Klaim terdahulu | Konfirmasi yang tersedia sekarang | Batas kesimpulan |
|---|---|---|
| 30 link/anchor checks pass,7 dokumen | Laporan QA lokal sebelumnya `/workspace/scratch/location-intelligent-documentation-qa.json`; ketujuh hash dokumen cocok sebelum revisi T2 | Bukti revisi dokumentasi sebelumnya, bukan jumlah link revisi sekarang; laporan scratch bukan artifact repo yang dijamin ada di clone baru |
| 4.080 historical files tetap konsisten | [Final verification B v8](../results/b_v8/verification/final_verification.json) mencatat4080; hash receipt cocok dengan retention manifest | Tidak mengulang scan4080 file pada tugas sekarang; memakai laporan tersimpan yang terikat checksum |
| B v7/B v8 dipertahankan | [Baseline retention malam](../results/nighttime_validation/verification/baseline_retention.json) terikat manifest; manifest hashes B v7/B v8 masih cocok | Catatan132/451 retained files dan11/15 live bindings adalah pemeriksaan historis, bukan inference baru |
| Runtime dan filter tidak berubah | Fingerprint sebelum tugas atas121 file runtime/config/receipt/source terpilih; filter user asli ikut dilindungi; pemeriksaan ulang pada QA tugas ini | Bukan klaim seluruh source di luar workspace diverifikasi; perubahan tugas ini terbatas dokumentasi+arsip brief |
| Night preview tervalidasi, counting malam belum | [Night verification](../results/nighttime_validation/verification/final_verification.json) terikat manifest, status PASS_WITH_EXPLICIT_E2E_BLOCKERS | Pixel/profile tests terdahulu tidak membuktikan nighttime counting reliable |

## Status workstream

| Workstream | Bukti aktual | Readiness/batas |
|---|---|---|
| Traffic Counter B v7/B v8 | [Selected run](../results/b_v8/selected_run.json): reviewed pilot TGDI-WEEKDAY-SIANG9128frame,74 accepted objek=73kendaraan+1pedestrian,67measured+7inferred,1pending,83invalid | Scoped reviewed pilot; bukan produksi otomatis. B v7 machine pembanding72accepted/24pending/86invalid tetap terpisah |
| Night input/Review-Filter | Retained Kaggle inspection10video/89.199frame; user memilih TKVQ-WEEKEND-MALAM, gamma0.65/exposure0.2/sharpness0.35/brightness0/shadows0 | Filter dipertahankan sebagai kandidat; geometri video ini dan actual model/counting smoke belum tervalidasi |
| Reference Area N1 | Arsip notebook23cell, query/code dan stored output contoh tersedia; tidak dieksekusi ulang | Summary1321/1304/5216 bukan proof full frozen spatial dataset. Export cell tidak punya output eksekusi |
| Source discovery | Dua identifier BigQuery, Overture buildings/places dan OSMnx operation terkonfirmasi secara statis | Live physical schema/permission/quota/pricing/freshness belum diverifikasi. RWI source UNKNOWN |
| Architecture/contracts | Envelope location_intelligent_v1 dan diagnostics/readiness kini implemented sesuai kontrak kanonis | Full geospatial/output contract masih rancangan; engine/business policy tetap mengikuti decision log |
| Validator offline LI-0 |49 tes PASS setelah6 regression fixes; baseline43 tes dipertahankan | Gate input lokal; READY bukan bukti isi geometry, actual coverage atau live integration |
| LI-1 local building selection |40 tes PASS;9record=5selected+4excluded. Invalid fixture=1selected+2excluded+6rejected/PARTIAL | Canonical GeoJSON synthetic, explicit CRS/metric transform, reconcilable ledger. Tidak ada real-snapshot validation |
| LI-2 directed routing |41 tes PASS,5reference routes pada main fixture; deterministic repeated output | Routing subset PASS; final accessibility BLOCKED oleh D02/D03/D05/D10, overall PARTIAL |
| Full Area E2E/Recount | Arsitektur/reference rules terdokumentasi | Belum implemented/validated; needs real source acquisition dan keputusan unit/routing/universe/predicate/coverage |
| PPAC | Feature interface/gates terdokumentasi | Numerik BLOCKED: Excel/formula/constants/units/period/label/evaluation belum tersedia/disetujui; historical SPD unit UNKNOWN |

Diagram besar Location Intelligent dan brief bisnis Area–Recount–PPAC terpisah
belum tersedia, demikian pula workbook Excel. Tidak direkonstruksi sebagai
requirement atau formula. RWI tidak diasumsikan dari BigQuery/GEE/provider lain.

## Dasar dokumentasi yang sudah diselesaikan

Inventaris source beserta identifier/query/schema expectations, kontrak
raw→normalized→frozen→derived/reviewed/features, status multidimensi dan
roadmap offline/live diperjelas. Source adapters dibedakan dari downstream
PPAC feature adapters. Tahap dokumentasi sebelumnya bukan uji engine;
implementasi LI-0 terbaru dibatasi di bawah.

Peta otoritas dokumen:

- [Overview](LOCATION_INTELLIGENT_OVERVIEW.md): register sumber dan scope.
- [Architecture](AREA_COVERAGE_ARCHITECTURE.md): batas engine, alur dan persistence.
- [Inventory](DATA_SOURCE_INVENTORY.md): sumber terkonfirmasi dan UNKNOWN.
- [Canonical contract](AREA_COVERAGE_DATA_CONTRACT.md): fields/units/CRS/status/provenance.
- [Roadmap](IMPLEMENTATION_ROADMAP.md): urutan dan acceptance gates.
- [Decision log](AREA_COVERAGE_DECISIONS.md): keputusan terbuka dan dampak.
- [Reference specification](AREA_COVERAGE_SPEC.md), [test plan](AREA_COVERAGE_TEST_PLAN.md), [PPAC gates](PPAC_SPEC.md).

## Hasil eksekusi LI-0

**Historical21 Oktober2026, sebelum gap audit.** Python3.12.14,43 tes PASS;
source/fixture/documen baseline sekarang diarsipkan, bukan ditimpa sebagai
hasil baru. Perintah yang benar-benar dijalankan saat itu:

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover \
  -s notebooks -p 'location_intelligent_validator_tests.py' -v

python -B notebooks/location_intelligent_validator.py \
  --context notebooks/fixtures/li0/context.json \
  --manifest notebooks/fixtures/li0/manifest.json \
  --root notebooks/fixtures/li0
```

- **43 tes,0failure,0error — PASS**; termasuk14 kasus fixture negatif/blocked,
  salah tipe nested, strict JSON, identity/config hashes, missing/empty/failed/
  unknown sources, quantity/unit/CRS, producer/artifact consistency,
  traversal/symlink, checksums dan dependency cycles.
- CLI fixture: **exit0, VALID, READY**,1 local source terverifikasi.
  `live_readiness=NOT_VERIFIED`; freshness/source vintage synthetic tetap
  UNKNOWN nonblocking. Source fixture bukan data Overture aktual.
- CLI diuji dalam child process dengan environment hanya
  PYTHONDONTWRITEBYTECODE, tanpa inherited credentials/PATH. Tes juga menolak
  socket/network dan write saat validator berjalan serta memeriksa import
  tidak menjalankan I/O/engine. Exit1 INVALID dan exit2 VALID/BLOCKED diuji.
- Bukan uji engine/building geometry atau replay Traffic. Tidak mengulang
  suite historis. Fingerprint121 existing protected files diperiksa untuk
  memastikan baseline/filter/runtime pengguna tetap utuh.

File implementasi: [validator](../notebooks/location_intelligent_validator.py),
[tests](../notebooks/location_intelligent_validator_tests.py),
[fixture context](../notebooks/fixtures/li0/context.json),
[manifest](../notebooks/fixtures/li0/manifest.json),
[invalid cases](../notebooks/fixtures/li0/invalid_cases.json), serta synthetic
building/empty GeoJSON di folder yang sama. Klarifikasi teknis ada pada
kontrak kanonis dan D25 decision log, tanpa schema tandingan.

**Historical LI-0 PASS** tidak menutup unit capacity, actual source schema/coverage,
freshness policy, global ID uniqueness, RWI/Excel atau keputusan PPAC.
Tidak ada known blocker untuk acceptance validator dalam scope ini.

## Hasil audit LI-0 dan eksekusi LI-1

Baseline43 tes dijalankan kembali dan lulus sebelum edit. Enam tes audit baru
direproduksi gagal pada source lama, lalu lulus setelah fix: unpaired Unicode
value/key, checksum PARTIAL, optional reason salah tipe, unused SRC04 yang
memblokir dan pembukaan FIFO. [Baseline v1](evidence/location_intelligent/li0_baseline_v1/manifest.json)
mempertahankan source/fixtures/documen asli sebelum perbaikan.

Command aktual setelah implementasi (Python3.13.5 sistem):

```bash
PROJ_NETWORK=OFF PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover \
  -s notebooks -p 'location_intelligent_*tests.py' -v

PROJ_NETWORK=OFF /usr/bin/python3 -B notebooks/location_intelligent_buildings.py \
  --context notebooks/fixtures/li1/context.json \
  --manifest notebooks/fixtures/li1/manifest.json \
  --root notebooks/fixtures/li1 --source-ref fixture-buildings
```

**89 tes PASS,0failure,0error,0skip:**49 LI-0 termasuk43 baseline;40 LI-1.
GDAL/OGR3.10.3, GEOS3.13.1 dan PROJ lokal dipakai tanpa instalasi/network.
Shapely tidak tersedia; backend dan kesesuaian operasi N1 dijelaskan dalam
kontrak. Default Python3.12 tanpa GDAL hanya mendukung validator LI-0.

- [Fixture hasil bersih](evidence/location_intelligent/li01_20261022/li1_fixture_result.json):
  SUCCEEDED,9record=5selected+4selection exclusions+0quality rejections.
- [Fixture masalah](evidence/location_intelligent/li01_20261022/li1_invalid_fixture_result.json):
  PARTIAL,9record=1selected+2excluded+6rejected, semua row teraccount.
  Duplicate ID ditolak seluruh kemunculannya; tidak memilih first/last.
- JSON/GeoJSON canonical lokal `li_building_snapshot_v1` saja; source-level
  missing/failed/invalid berbeda dari valid empty/zero qualifying. Failure
  summary=null. Tidak ada CSV/Parquet/live adapter atau actual Overture run.
- Representative point WGS84 sebelum transformasi metric CRS context;
  full footprint area, distance≤radius, area>min dan standard area<max.
  Class/subtype precedence dan null-subtype fallback N1 dipertahankan.
- CLI LI-0/LI-1 diuji tanpa inherited credentials; PROJ_NETWORK=OFF pada
  geospatial tests. Input read-only, tidak ada OGR dataset Open/network atau
  Traffic inference. Geometri tidak direpair dan capacity tidak dihitung.

Hasil/log/commands tersimpan pada
[execution receipt](evidence/location_intelligent/li01_20261022/execution.json).
Perlindungan121 berkas runtime/baseline/filter lama diperiksa kembali pada
verification receipt task ini; tidak mengulang4080 historical-file audit.

**LI-0 PASS; LI-1 PASS untuk synthetic offline reference selection.** Real
building snapshot belum tersedia/tervalidasi. Actual source coverage/schema,
unit capacity, identity lintas ID/provider, routing/accessibility dan PPAC
tetap terbuka. Satu primary rejection per record tidak mengklaim semua isu
sekunder ditemukan. Parent manifest tidak diubah menjadi full-engine success.

File baru: [building helper](../notebooks/location_intelligent_buildings.py),
[tes LI-1](../notebooks/location_intelligent_buildings_tests.py), fixture folder
`notebooks/fixtures/li1/`; helper/tes LI-0 diperbaiki dan dokumen kanonis
diupdate. Tidak membuat framework baru.

## Tugas coding terkecil berikutnya

**Review dan tetapkan policy D02/D03/D05/D10**, lalu implementasikan policy
version/gate yang disetujui dan uji offline. Jangan mengubah reference
threshold atau menandai fixture sebagai production evidence. LI-3 belum dimulai.

## Hasil LI-2 dan limitation

File baru: [routing helper](../notebooks/location_intelligent_routing.py),
[tes](../notebooks/location_intelligent_routing_tests.py),
[graph fixture](../notebooks/fixtures/li2/graph.json),
[routing config](../notebooks/fixtures/li2/config.json). LI-0/LI-1 source,
fixtures dan historical results tetap identik. Dokumen LI-0/LI-1 sebelum
update status disimpan pada
[arsip context](evidence/location_intelligent/li01_document_baseline_before_li2/manifest.json),
sehingga verification receipt historis tetap dapat dicocokkan dengan bytes asal.

Command aktual:

```bash
PROJ_NETWORK=OFF PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover \
  -s notebooks -p 'location_intelligent_*tests.py' -v

PROJ_NETWORK=OFF /usr/bin/python3 -B notebooks/location_intelligent_routing.py \
  --context notebooks/fixtures/li1/context.json \
  --manifest notebooks/fixtures/li1/manifest.json \
  --buildings docs/evidence/location_intelligent/li01_20261022/li1_fixture_result.json \
  --graph notebooks/fixtures/li2/graph.json \
  --config notebooks/fixtures/li2/config.json --root notebooks/fixtures/li1
```

**130 tes PASS,0failure,0error,0skip:**49 LI-0+40 LI-1+41 LI-2.
Tests mencakup directed/disconnected/parallel/equal-cost paths, zero-cost
cycles, connector permissions/costs, missing geometry, coverage/snap boundary,
time rounding strictness, malformed/overflow graph costs, provenance binding
dan deterministic reconciliation. Tidak menjalankan ulang suite Traffic atau
4080-file historical audit yang tidak relevan dengan perubahan ini.

Main fixture3node/3edge menghasilkan5reference routes untuk5selected
buildings. Route-found5/no-route0/not-evaluated0 teraccount; reference-within-
time5. **Final accepted_accessible=null**, policy-unresolved5. Bukan5 gedung
yang terbukti accessible. CLI exit3 adalah PARTIAL yang disengaja, bukan test
failure. Dua run dengan input sama, environment tanpa inherited credentials,
menghasilkan stdout byte-identical; tidak ada field yang dikeluarkan dari
perbandingan. Bukti:
[execution](evidence/location_intelligent/li2_20261022/execution.json),
[routing result](evidence/location_intelligent/li2_20261022/routing_fixture_result.json).

Graph lokal menyatakan coverage dan izin akses fixture, bukan observasi OSM
atau legal access. Snap50m hanyalah input fixture; D05 belum menetapkan batas
produksi. Perhitungan reference mempertahankan125m/7kmh dan round(time,3)<10;
connector target omitted ditampilkan beserta biaya jika dimasukkan. Cost graph
dan path-weight variant ditandai eksplisit. Geometry hasil EPSG4326 berasal
dari stored road edges, tanpa entrance/road segment yang dibuat-buat.

D02/D03 memerlukan keputusan threshold dan rounding; D05 selection objective,
snap/entrance/connector; D10 mode/legal access dan physical connector evidence.
Tidak ada flag config yang boleh menyelesaikan keputusan tersebut tanpa
approval. **LI-2 keseluruhan PARTIAL**, bagian routing offline PASS, gate
accessibility BLOCKED. Data real/freshness/full E2E masih belum tervalidasi.
Verification task ini memeriksa156 protected files, termasuk baseline/filter
Traffic dan seluruh source/fixtures/results LI-0/LI-1, tanpa perubahan.

## Update D28 — konfigurasi motor dan readiness LI-3

22 Oktober2026. Dibuat
[location_intelligent_config.py](../notebooks/location_intelligent_config.py)
sebagai satu titik edit kebijakan baru. Memuat125m eksperimen,10min skenario,
7km/h asumsi N1, akses wajib berbukti, private/pedestrian-only/tangga/unknown
tidak digunakan. Parameter yang belum disepakati tetap null. Rincian delta:
[D28](AREA_COVERAGE_DECISIONS.md#d28--kebijakan-motor-dan-konfigurasi-tunggal).
Tidak mengubah source/config/baseline routing existing; profile baru belum
terintegrasi. LI-2 tetap PARTIAL dan **LI-3 belum dimulai**.

Export snapshot (command ini tidak menjalankan engine):

```bash
python notebooks/location_intelligent_config.py > /tmp/li-policy.json
```

**Validasi aktual:** command unittest discovery LI yang tercantum di atas
dijalankan setelah perubahan:130 tests,0failure,0error,0skip, OK.
Smoke checks lokal juga PASS untuk silent import, independent deep copy,
propagasi nilai yang diedit, dua CLI outputs byte-identical dan JSON parity
dengan get_config(). Tidak melakukan live retrieval atau routing data nyata.
Tidak ada klaim akses fisik/legal/ETA tervalidasi.

Dokumen diperbarui: kontrak data (schema snapshot dan batas integrasi),
decision register D28, roadmap (input/keputusan/alur LI-3), dan status ini.
Rekomendasi berikutnya: mapping provider/evidence + adapter mock tests;
minimal live validation membutuhkan target nyata dan request scope eksplisit.

### Delta D29/D30

Policy snapshot kini `motorcycle_experiment_v3`: minimum total time,
motor-only, target snap UNBOUNDED pada graph tersedia, floor(total_min)<=10,
asumsi gang usable/portal passable kecuali larangan dan entrance menghadap
kelas tertinggi. Hierarki/precedence akses dan connector cost belum diputuskan.
Engine LI-2 masih reference-only; tidak menjalankan LI-3 atau inference.
130 regresi kembali PASS, smoke export/parity serta contoh floor9.8/10/10.9/11
PASS. Versi/documentation metadata publik diperiksa, bukan source data query;
lihat [inventaris terbaru](DATA_SOURCE_INVENTORY.md#verifikasi-dokumentasi-publik--22-oktober2026).

### D33 — config v6 dan assessment terbaru

Policy snapshot kini motorcycle_experiment_v6: Python round(total_min)<=10
menggantikan floor, drive_service menjadi acquisition filter, source/version
plan berada pada file konfigurasi tunggal dan tabel inventaris. D32 prioritas
kelas tetap berlaku. LI-1 PASS offline-selection, bukan capacity/live parity;
LI-2 PARTIAL karena profile baru belum diimplementasikan dan beberapa detail
mapping/topology/connector belum selesai. Lihat assessment di roadmap.

Validasi aktual setelah update:130 existing tests PASS (0failure/error/skip).
Smoke checks config PASS: round9.8/10.49/10.5/10.51/10.9, source plan bukan
snapshot aktual, independent copy, baseline N1 dan JSON export deterministik.
Tidak melakukan source acquisition, mengubah engine LI-1/LI-2 atau menjalankan
LI-3. Tabel sumber latest memakai verifikasi publik22 Oktober yang sudah
dicatat; tidak menyatakan library/adapter terbaru telah diinstal atau diuji.

## D34 — Overture nyata, kapasitas referensi dan motor engine

Config v7 dikonsumsi helper motor baru dan kapasitas referensi; helper N1,
LI-0/LI-1 tidak diubah.158tes PASS:130existing+8capacity+16motor/access+
4normalization,0failure/error/skip. Real-source selection/capacity offline
replay identik; dua motor CLI fixture byte-identical. Tidak menjalankan
detector/tracker/ReID/counting/enhancement.

Overture2026-10-21.0/schema2.0.0 kolom yang dikonsumsi diperiksa dari Parquet.
2623records→1322selected+1301excluded+0rejected.512STAC item bboxes diverifikasi,
satu partisi intersect query, cap10001 tidak terpotong. Coverage query verified,
physical map completeness belum. Standard subtotal5288 tetap unit unresolved,
semua1322selected memakai null-subtype fallback N1. Height/num_floors kosong.

Hasil/raw/proof/commands: [results](../results/location_intelligent/README.md).
First blocked coverage attempt tetap disimpan. Env DuckDB2.0.0+httpfs terpisah
dipasang untuk bounded validation; tidak mengubah env Traffic.

**Status:** LI-1 PASS bounded-source selection/capacity reference, bukan final
business capacity. LI-2 motor integration PASS offline, real accessibility
belum verified. Bisa melanjutkan LI-3 source adapters; probe nyata bukan full
LI-3 completion. Connector/barrier/access/conditional/turn mapping dan
supplemental motor paths masih membutuhkan real-source integration/tests.
