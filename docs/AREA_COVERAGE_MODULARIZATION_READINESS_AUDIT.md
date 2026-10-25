# Audit kesiapan modularisasi Area Coverage

> Pembaruan baseline OSM/GPU/Market V5 tersedia pada
> [audit26Oktober2026](AREA_COVERAGE_MODULARIZATION_AUDIT_20261026.md).
> Dokumen di bawah tetap audit historis N1/LI-4/LI-5.


24 Oktober 2026, Asia/Jakarta. **AUDIT SAJA — IMPLEMENTASI MENUNGGU PERSETUJUAN.**
Acuan pemeriksaan repository: commit `0564ae87b606db047f8aa906bc072a975a1ce0d8`.
Instruksi owner terbaru membatasi pekerjaan ini pada audit, bukan kelanjutan
implementasi mandiri pada scope Area Coverage. Traffic RC tetap utuh.

## 1. Kesimpulan dan rekomendasi persetujuan

**FAKTA:** Area Coverage sudah memiliki irisan modular untuk membaca snapshot
LI-4, menjalankan selection/capacity, dan Recount LI-5. Routing motor, graph,
konektor, akuisisi, serta sebagian exporter/viewer masih di helper `notebooks/`.
Jadi migrasi berikutnya melanjutkan boundary yang ada, bukan memulai dari nol.

**REKOMENDASI:** layak disetujui untuk migrasi bertahap berbasis **snapshot N1
frozen dan algoritme acuan**. Belum layak dinyatakan modularisasi end-to-end
selesai, layanan koordinat bebas siap produksi, atau aksesibilitas tervalidasi.

Pemisahan kode tidak perlu menunggu 620 akses unverified selesai. Namun migrasi
wajib mempertahankan status tersebut dan menunjukkan bahwa parity bisa
mempertahankan kekurangan baseline, bukan memperbaiki kebenaran dunia nyata.

| Scope | Kesiapan saat audit | Batas kelulusan |
|---|---|---|
| Selection/capacity snapshot | Siap sebagai acuan migrasi; sudah ada adapter dan parity | GDAL asli, row identity, formula dan unit tetap |
| Recount offline | Siap sebagai acuan migrasi; R1/R2 dan delta tersedia | Selected universe, representative point, predicate dan union tetap |
| Routing/graph/konektor frozen | Layak diekstrak dengan gate; belum ada facade routing di package | Wajib parity LI-3, bukan hanya subtotal accepted |
| Export/peta/tabel offline | Prototype sudah teruji; migrasi ke adapter belum lengkap | Tidak mengambil/menghitung rute baru untuk menggambar |
| Acquisition/refresh koordinat baru | Pekerjaan terpisah setelah parity core | Memerlukan snapshot sumber baru, scope/CRS dan pengujian lokasi baru |
| Backend/UI/GCS/produksi | Di luar kelulusan audit ini | Tidak dianggap selesai oleh modularisasi |

## 2. Metode dan batas pemeriksaan

Dibaca: aturan repo/workflow, kontrak dan keputusan Area Coverage, review LI-3/
LI-4/LI-5, kode package, helper sumber/routing/export, test boundary, registry
extraction serta retained receipts. Tidak menjalankan acquisition, routing,
selection/capacity/Recount ulang, Traffic, model, atau perubahan konfigurasi.

**HASIL PEMERIKSAAN AKTUAL pada audit ini:** verifikasi daftar file, ukuran dan
SHA256 pada empat manifest dengan verifier integritas lokal yang sudah ada.
Semua lulus. Enam pasangan notebook source → module pada
[registry extraction](../results/engine_modularization/location_source_extraction.json)
juga cocok hash source dan module-nya. Ini pemeriksaan integritas, bukan rerun
parity dan bukan semantic/physical-access validation baru.

| Paket retained | File dalam manifest | Manifest SHA256 | Hasil |
|---|---:|---|---|
| LI-3 `li3_n1_20261022_v1` |76|`0f309776b1e6302aa67183818b0354725ff9d07a4338f1b723241b5e53676eb9`|PASS integritas|
| LI-4 `li4_n1_20261023_v1` |90|`909987bb3114316f513d3035a92d1ff21a4fce5b4aa0ae1c3dc7deee5a0be166`|PASS integritas|
| LI-5 R1 |20|`9fa41767b2e268e737ecec9953f449831dde9e9352a4fab55ed01ba8abb9ac60`|PASS integritas|
| LI-5 R2 |21|`19390341784572e35e437d7dbae121d2aa6afe67f2d93129a728f9677737281f`|PASS integritas|

**BUKTI HISTORIS YANG DIBACA, bukan dijalankan ulang pada audit:**

- [LI-3 completion](../results/location_intelligent/li3_n1_20261022_v1/validation/completion.json)
  dan replay: 21 calculation artifacts cocok byte, network diblok. Replay
  receipt memakai origin manifest yang diarsipkan; hash origin berbeda dari
  manifest paket final adalah lineage yang disengaja, bukan mismatch disembunyikan.
- [Selection/capacity modular](../results/engine_modularization/20261023/verification/location_selection.json):
  tiga pengulangan identik, payload selection/capacity sama dengan acuan.
- [Recount modular](../results/engine_modularization/20261023/verification/location_recount.json):
  tiga pengulangan per revisi, membership/domain/delta sama; versi kode berubah
  eksplisit sesuai ekstraksi sebelumnya.
- [LI-4 receipt](../results/location_intelligent/li4_n1_20261023_validation/receipt.json):
  228 tes historis, rekonsiliasi ekspor, browser offline dan relocated reopen.
- [LI-5 receipt](../results/location_intelligent/li5_n1_20261023_validation/receipt.json):
  259 tes historis, lima output R2 byte-identical dan compact relocated packet.
  Jumlah historis tersebut mencakup tes fase sebelumnya, bukan tes baru audit.

## 3. Angka acuan yang harus tetap sama

| Denominator/status | Jumlah |
|---|---:|
| Semua source rows |2623|
| Selected |1322|
| Excluded |1301|
| Rejected selection pada pilot |0|
| ACCEPTED menurut skenario, dalam selected |641|
| ACCESS_UNVERIFIED |620|
| NO_VALID_CONNECTOR |54|
| OVER_TIME_LIMIT |7|

Identitas rekonsiliasi: `2623 = 1322 + 1301 + 0` dan
`1322 = 641 + 620 + 54 + 7`. Recount R1 union663, R2 union1072; delta409 entered,
0 exited. Membership union bukan jumlah accepted akses: R2 mempunyai565accepted
skenario,463unverified,42no-valid-connector,2over-time.

Kapasitas selected5288 dan accepted2564 adalah **N1_STANDARD_VALUE_UNIT_UNRESOLVED**.
Bukan KK/populasi. `mixed_unit_total` dan `final_business_capacity` tetap null.
Unknown numerik kapasitas berbeda dari unknown izin akses dan unknown unit.

Pilot: lokasi contoh N1, bukan TGDI; EPSG:32748, radius seleksi400m, footprint
minimum45m² dan maksimum standard550m² dengan strictness kode asli. Semua1322
selected memiliki subtype null dan memakai fallback N1; tidak boleh disebut
1322 rumah tinggal yang telah diklasifikasi positif. Tidak ada tinggi/lantai
pada data pilot ini; formula special types memerlukan fixture regresi tersendiri.

## 4. Peta implementasi saat ini dan input/output

Package `src/traffic_location/location/` berisi9file Python termasuk initializer
serta `recount_policy.json`. Boundary saat ini terutama berbasis dict/file,
bukan keseluruhan kontrak DTO bertipe seperti target migrasi.

| Tahap | Input → proses → output | Lokasi saat ini / pemisahan yang dibutuhkan |
|---|---|---|
| Context/config/manifest | Target+CRS+policy+refs → validasi → context/version | `config.py`, `validation.py`; pisahkan policy, source observation, pilot dan runtime |
| Provider acquisition | Bounded request+release/as-of → Overture/OSM → raw packets/receipts | `notebooks/location_intelligent_overture_*`, `location_intelligent_li3_sources.py`; adapter provider terpisah |
| Normalisasi | Raw WKB/OSM IDs/tags → canonical buildings/graph inputs | `location_intelligent_li3_core.prepare`, `li3_graph.py`; jangan membuat provider-unknown menjadi default |
| Selection | Canonical footprints+target+CRS → validasi/geometri/rules → selected dan reject ledger | `location/selection.py` masih mencampur baca file, backend dan rules; pecah boundary bertahap |
| Capacity | Selected+explicit policy → formula N1 → rows/subtotal per unit | `location/capacity.py`; hentikan default tersembunyi di facade baru, pertahankan legacy compatibility |
| Directed graph/access | Source nodes/ways/relations → arah, izin, quarantine → graph+evidence | `li3_graph.py`, `motor_routing.py`, validator graph di `routing.py`; belum dimigrasikan ke package |
| Connectors | Footprint/target+road+barrier → kandidat/splits → connectors/reject ledger | `li3_connectors.py`; geometri dan lineage tidak dicampur ke shortest path |
| Routing/decision | Selected+graph+connector+policy → edge-state path → candidates, chosen route, status/time | `motor_routing.py`, `li3.map_decisions/finalize`; preserve seluruh urutan keputusan |
| Snapshot selection facade | LI-4 verified → selection/capacity | `location/snapshot.py`, `engine.run_selection`; **bukan routing baru** |
| Recount/delta | Parent frozen+polygon revision → membership/union/delta | `location/recount.py`, `engine.run_recount`; pecah I/O, transform, core dan lineage |
| Presentation/export | Canonical decisions/routes/units → map/tabel/CSV/GeoJSON/HTML | `notebooks/location_intelligent_li4.py/.html`, Recount notebook; package hanya punya `summary.py` subset |
| Publish/reopen | Mandatory artifacts → verify/stage/publish → immutable bundle | `traffic_location/persistence.py` dan verifier legacy; adaptasi versi manifest wajib eksplisit |

Alur target tetap: **target+frozen config → source snapshot → normalisasi →
selection/capacity → graph/access → connectors → routing/decision → snapshot →
export/view**. Recount bercabang dari snapshot final; edit polygon tidak kembali
ke acquisition, routing atau formula kapasitas. Traffic/PPAC merupakan konsumen
atau engine lain, bukan langkah internal Area Coverage.

## 5. Algoritme yang wajib dibekukan

1. **Selection:** GEOS PointOnSurface dalam EPSG:4326 sebelum proyeksi GDAL;
   XY/[lon,lat], CRS/domain checks; radius inclusive; minimum area strict `>`;
   maksimum standard strict `<`; special-class precedence dan subtype-null
   fallback, urutan rejection serta penolakan semua duplicate source IDs.
2. **Capacity:** rounded floors/height fallback, formula/ratio/occupancy dan
   Python rounding asli, missing-level null,4reference standard, unit terpisah.
   Recount hanya menjumlahkan stored capacity, tidak menjalankan formula ulang.
3. **Graph/access:** source-node topology, directed edges, OSM ID/raw tags,
   motorcycle-specific precedence, private/prohibition, direction/gates,
   restriction quarantine dan bridge/tunnel/layer. Ruas berpotongan secara
   visual bukan otomatis junction; tidak membuat reverse/U-turn/bridge palsu.
4. **Connectors:** search125m dari representative point ke road geometry pada
   CRS meter; bukan jarak rute. Frontage assumption, barrier/building checks,
   split nodes/edges/source lineage dan numeric controls frozen tetap persis.
   Target nearest valid road tanpa cap numerik hanya di graph yang tersedia.
5. **Routing:** profil motor aktif `motorcycle_experiment_v8_li3`,7km/jam untuk
   seluruh segmen, termasuk kedua konektor; kelas akses valid/reachable tertinggi
   dahulu, waktu total terendah dalam kelas itu, lalu ID tie-break asli.
   Edge-state shortest path mempertahankan cost/hops/edge-ID serta penjumlahan
   floating-point forward asli. Turun kelas karena tidak ada rute bukan berarti
   memilih kelas lebih rendah hanya agar lolos batas waktu.
6. **Time gate:** Python half-even `round(total_minutes) <= 10`, bukan floor,
   full-precision <=10 atau round3. Contoh10.5 diterima,10.51 tidak. N1 diagnostic
   lama `round(time,3)<10` adalah profil historis lain, jangan dicampur.
7. **Decision/reconciliation:** `None` untuk belum dapat dievaluasi dibedakan
   dari known no-route/over-time; seluruh source rows dan alasan tetap ada.
   Status execution, analysis quality, source coverage dan per-building decision
   merupakan dimensi berbeda; accepted adalah modeled scenario.
8. **Recount:** selected universe dan stored representative point; covers pada
   profil acuan, contains hanya profil eksplisit; holes/multipolygons/boundary,
   per-polygon overlap boleh, union dedup sekali dalam snapshot yang terikat.
   Source_row_index tetap identitas baris lokal; provider+version/snapshot+ID
   dibutuhkan untuk identitas lintas snapshot, tanpa mengganti ID acuan.
9. **Revisions:** input/policy/code/software yang kompatibel untuk delta;
   perubahan polygon perlu revision baru. Parent routing/decision/capacity dan
   historical result tidak ditimpa atau diberi hash baru secara retroaktif.

## 6. Blocker/risk engineering dan perlakuan migrasi

| ID / prioritas | Temuan yang didukung kode/bukti | Penanganan yang diusulkan setelah approval |
|---|---|---|
| A01 P0 | Belum ada package facade untuk graph/connectors/motor routing dan LI-4 export lengkap | Extract sebagai compatibility core, mapping source/import/SHA; golden LI-3 lebih dahulu |
| A02 P0 | Runtime terpisah dan interpreter `/usr/bin/python3` terikat pada pilot orchestration | Worker boundary eksplisit per backend; pin environment, tidak mengganti GDAL dengan Shapely |
| A03 P0 | Target, CRS, cache N1 dan bbox berada di config/source preparation | Ubah menjadi input tervalidasi; tetap menolak cache target/CRS berbeda. Multi-lokasi acquisition tetap pekerjaan baru |
| A04 P0 | Dict/file contracts dan `validation.py`556baris mencampur beberapa tanggung jawab | DTO immutable/versioned + legacy decoder; split boundary dahulu, bukan rewrite sekaligus |
| A05 P0 | `capacity(policy=None)` memakai config global; config juga memuat source-plan berlabel PLANNED meski manifest aktual tersedia | Facade memakai effective policy eksplisit; pisahkan source_plan dari observed receipt, jangan mengedit policy frozen untuk memperbaiki label |
| A06 P0 | `recount.engine_digest()` menghash seluruh folder Location; selection juga memakai digest itu | Hash per operasi/dependency closure dan versi wrapper baru. Renderer-only change tidak memengaruhi kalkulasi |
| A07 P0 | Parent/previous dan environment lineage Recount ketat; perubahan code hash memang mengganti versi | Terima perbedaan metadata yang dideklarasikan, compare domain persis; previous baru harus compatible, bukan force-import baseline lama |
| A08 P0 | Test modular11kasus belum membuktikan migrasi routing/export/provider | Bawa fixture motor/LI-3/LI-4/LI-5, three-replay gate, failure/source-mutation/ordering checks |
| A09 P1 | Filesystem staging dan notebook/REPO paths bercampur dengan orkestrasi | Artifact/worker adapters, relative packet refs, immutable publication; tidak import Traffic sebagai storage backend |
| A10 P1 | Default normal lookup koordinat→snapshot dan cache refresh policy belum produk terintegrasi | FROZEN lookup berbasis fingerprint; REFRESH eksplisit, hasil lama tetap tersedia |

**Risiko sumber/bisnis yang tidak diselesaikan oleh pemindahan file:**620akses
unverified,23restriction relations dikarantina, OSM roads/features berselisih
waktu, coverage terbatas, evidence freshness/akses lapangan,7km/jam dan unit
standard belum tervalidasi. Semua tetap tercatat; bukan blocker untuk parity
N1. Validasi lokasi baru, unit bisnis/PPAC dan akses produksi adalah gate terpisah.

## 7. Rencana struktur file — PROPOSAL

Target awal **36file fungsional+6initializer=42file** dalam
`src/traffic_location/location/`. Ini anggaran struktur, bukan syarat memperbanyak
file. Compatibility helpers/core dan tests/CLI di luar42dicatat tersendiri;
tidak mengklaim seluruh isi helper lama sudah menjadi pure functions.

| Kelompok | File yang diusulkan | Batas fungsi |
|---|---|---|
| Root,1 | `ports.py` | Protocol geometry/source/artifact; tidak menjalankan I/O |
| Contracts,8 | `source.py`, `geometry.py`, `buildings.py`, `routing.py`, `recount.py`, `execution.py`, `results.py`, `versioning.py` | DTO immutable, scoped identities, versi/decoder; tidak import service/config loader |
| Config,4 | `schema.py`, `profiles.py`, `validation.py`, `loader.py` | Policy/overrides tervalidasi, explicit effective config; legacy full policy lossless |
| Adapters,9 | `snapshot.py`, `overture.py`, `osm.py`, `geometry_gdal.py`, `geometry_shapely.py`, `worker.py`, `artifacts.py`, `exports.py`, `viewer.py` | Manifest/provider/backend/I/O/presentation terpisah dari rules |
| Domain,10 | `selection.py`, `capacity.py`, `access.py`, `graph.py`, `connectors.py`, `routing.py`, `coverage.py`, `aggregation.py`, `recount.py`, `delta.py` | Rules dari acuan; geometry melalui port/runtime yang benar; tanpa network/UI/storage |
| Application,4 | `pipeline.py`, `recount.py`, `refresh.py`, `runtime.py` | Komposisi tahap, explicit operation, worker/status/error; bukan rumus domain |

Initializers: root, contracts, config, adapters, domain, application.
`engine.run_selection/run_recount` tetap compatibility facade sampai consumer
bermigrasi. Generator `tools/extract_location_kernel.py` tidak dijalankan untuk
menimpa module baru; perubahan extraction plan harus ditinjau dan source archive
beserta mapping transformation disimpan sebelum edit.

DAG: contracts → data dasar; config/ports → contracts; domain → contracts/ports;
adapters → contracts/ports/infrastruktur; application → loader/domain/adapters;
CLI/backend/UI → application. Registry mengimpor DTO; DTO tidak mengimpor registry.
Graph builder tidak memanggil routing; routing menerima graph dan connector yang
sudah dibentuk. Recount/delta tidak mengimpor refresh atau UI.

GDAL selection dan Shapely connector/Recount tetap backend berbeda. Layer
abstraction tidak berarti keduanya interchangeable. Nilai geometri/backend serta
runtime direkam di kontrak dan dicek sebelum eksekusi kalkulasi.

## 8. Urutan migrasi dan gate sebelum lanjut

| Tahap | Pekerjaan setelah approval | Gate keluar |
|---|---|---|
| M0 Freeze | Archive current source/package, config/runtime, raw/normalized input refs, golden LI-3/4/5 dan extraction registry | Baseline dapat diverifikasi dari fresh checkout; tanpa network |
| M1 Kontrak/facade | Pisahkan selection-capacity, route-frozen, Recount, open dan refresh; DTO/schema/negative tests | Tidak bisa tertukar profile/manifest/target/runtime atau masuk live fallback |
| M2 Adapter | Legacy LI-3/4/5, Overture/OSM canonical, geometri dan artifact I/O | Lossless roundtrip, null/reason/units/keys/coverage tetap; unsupported schema ditolak |
| M3 Domain | Ekstrak selection/capacity → access/graph → connectors/routing → aggregation/Recount/delta | Parity tiap substage dan full N1; satu mismatch menahan tahap terkait |
| M4 Runtime | Worker backend terisolasi, runtime/config eksplisit, reset job/cache, retry/cancel | A→B→A dan tiga replay stabil; tidak ada state/rute/cache bocor antar target |
| M5 Output | Export/viewer/storage consumers dari immutable result; relocated open | Peta/tabel/CSV/JSON/GeoJSON rekonsiliasi; mandatory export gagal bukan sukses |
| M6 RC | Wheel/CLI, clean install/import, combined regression dengan Traffic | Semua acceptance relevan PASS atau capability secara eksplisit unsupported |

`REFRESH` adapter dapat dipisahkan/didefinisikan pada migrasi tanpa otomatis
menjalankan fetch. Peluncuran acquisition untuk koordinat baru perlu tugas serta
validasi tersendiri setelah core parity. Jangan mengklaim arbitrary-location
validation dari satu pilot atau mengubah disk400m/bbox5500m sebagai default universal.

## 9. Acceptance criteria yang harus disepakati

| ID | Kriteria lulus yang dapat diuji |
|---|---|
| AC01 Freeze | Semua input/source/code/schema/runtime/policy/parent hashes diverifikasi sebelum migrasi; archive/oracle tidak diubah |
| AC02 Profiles | Request versi/operasi eksplisit. Snapshot selection tidak diam-diam routing; edit polygon tidak fetch/route/capacity ulang; open tidak menjadi replay |
| AC03 Typed boundary | DTO+schema runtime+static type check; unknown fields/versions dan incompatible payload ditolak; nested data tidak mutable; no import cycles/GPU/network effects |
| AC04 Coordinates | XY/WGS84/metrik, CRS/axis/domain/radius/coverage dan representative point asli tetap; salah lat-lon/target/cache/CRS gagal jelas |
| AC05 Full ledger | Setiap2623source row tepat sekali;1322selected,1301excluded,0rejected; tidak hanya jumlah total yang cocok |
| AC06 Selection/capacity | Seluruh payload lama sama pada scope native, termasuk reason order, geometry metrics, null fallback, floors/rounding dan per-unit values; special fixtures lulus |
| AC07 Graph/access | Node/edge IDs, arah, permissions, split lineage, barriers, turn restrictions/quarantine dan reject diagnostics sama; tidak ada invented edges |
| AC08 Routes | Candidate set/order, selected connector/class, edge sequence, segment costs, raw/rounded time dan decision per bangunan cocok;641/620/54/7 hanya ringkasan wajib tambahan |
| AC09 Recount | Seluruh membership R1/R2, coverage, unit/status subtotals, union663/1072 dan delta409/0 sama. Overlap tidak menggandakan union;1301nonselected tetap not-evaluated |
| AC10 Quality/units | PARTIAL/source warnings/null/modeled vs observed tetap; unknown bukan zero/false/accepted; mixed/final business total null; traffic measured-crossing tidak dipakai untuk modeled Location |
| AC11 Reproducibility | Minimal3pengulangan independen per capability pada input/config/code/runtime yang sama, network/PROJ network off untuk replay; hasil dan versi stabil; urutan A→B→A tidak bocor state |
| AC12 Version/parity | Algoritme dan field native acuan tidak ditoleransi agar cocok. Metadata versi/hash baru hanya pada allowlist eksplisit dan lineage valid; numeric mismatch menahan gate sampai diselesaikan |
| AC13 Publication | Stage→verify→publish immutable; missing/tamper/unlisted/symlink/partial write/duplicate publish/crash/retry/cancel tidak menghasilkan sukses palsu atau merusak baseline |
| AC14 Presentation | Map/table/CSV/JSON/GeoJSON berasal dari snapshot sama; source IDs, null, route lineage, attribution dan unit konsisten; renderer/export tidak mengubah keputusan/version kalkulasi |
| AC15 Relocation/open | Paket final dipindah dan dibuka tanpa repo/cache/provider/network. Read-only artifact open tidak memerlukan backend kalkulasi lama; semantic recomputation adalah operasi berbeda yang memerlukan runtime pin |
| AC16 Packaging/isolation | Clean install wheel dari luar repo, CLI/import tanpa notebook path; backend hilang/mismatch menghasilkan unsupported/blocked tanpa silent backend fallback; Traffic RC regression tetap lulus |
| AC17 Pilot/fresh boundary | Tidak memindahkan source N1 ke koordinat baru. Capability fresh belum diuji ditandai unsupported; kelulusan multi-lokasi perlu dataset/coverage/runtime receipts baru |

Untuk routing native, prioritaskan rekonsiliasi21calculation artifacts acuan.
Jika rename/path/code-provenance membuat wrapper berbeda, pertahankan decoder
native dan compare seluruh field domain; daftarkan perubahan metadata per field.
Jangan mengabaikan candidate ordering, source IDs atau edge-cost float untuk
menyamarkan selisih pilihan rute. Packaging/render metadata bukan pengecualian
untuk selisih calculation artifacts yang seharusnya sama.

## 10. Keputusan yang ditawarkan dalam approval audit

**PROPOSAL TEKNIS, belum diimplementasikan:**

1. Setujui scope pertama N1 frozen end-to-end; arbitrary coordinates/fresh
   acquisition merupakan capability berikutnya, dengan gate tersendiri.
2. Pertahankan dua runtime geometri yang sudah tervalidasi lewat worker boundary;
   penyatuan runtime/backend adalah eksperimen terpisah.
3. Jadikan effective policy dan source snapshot refs input eksplisit; hilangkan
   pilot/global defaults dari facade baru, tetap sediakan legacy adapter lossless.
4. Pertahankan semua angka, semantics, unknown dan unit pada §5; peningkatan
   source/izin/kecepatan/formula tidak digabung dengan refactor.
5. Gunakan versi wrapper baru dan operation-specific code identity; jangan
   mengubah hasil historis agar hash kode baru terlihat sama.
6. Reuse source/runtime/provider yang ada. GCS tetap provider pilihan owner,
   implementasi bucket/CRUD dan database/backend/UI bukan syarat audit selesai.
   Area tidak mengimpor `traffic.*` untuk memperoleh storage.
7. Tidak meminta polygon manual. Existing demo R1/R2 adalah fixture eksperimen;
   drawing/input UI kelak hanya mengirim revision. Tidak otomatis menjadi batas
   bisnis dan tidak mengganti parent analysis dengan polygon baru.

Keputusan produksi yang masih **OPEN di luar scope migrasi**: unit kapasitas
bisnis, evidence/freshness izin nyata, validitas kecepatan dan threshold bisnis,
source-update SLA/coverage lokasi baru, project/bucket/IAM GCS serta PPAC. Tidak
perlu mengarang jawaban untuk meluluskan parity offline.

## 11. Perubahan yang dilakukan pada tugas audit ini

Hanya dokumen ini dan checkpoint Area Coverage pada
[workflow aktif](CURRENT_DEVELOPMENT_WORKFLOW.md). Tidak ada perubahan Python,
notebook, policy, manifest/baseline, hasil perhitungan, runtime/dependency atau
infrastruktur. Tidak mengeksekusi tes/parity/kalkulasi baru; hasil historis
secara eksplisit dibedakan dari pemeriksaan integritas pada §2.

**Gate berikutnya adalah persetujuan audit ini.** Setelah disetujui, tahap pertama
M0 freeze terlebih dahulu; approval tidak berarti langsung mengubah algoritme,
mengambil sumber live, atau menyatakan accepted sebagai akses fisik yang terbukti.
