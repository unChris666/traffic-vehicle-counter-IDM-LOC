# Area Coverage — kontrak data dan provenance

## LI-5 serialization yang diimplementasikan

li_recount_policy_v1 adalah profil eksperimen eksplisit; li_recount_polygons_v1
memuat CRS EPSG:4326, revision, claim, unique polygon IDs dan geometri valid.
li_recount_result_v1 memuat source/evaluated denominator, membership IDs,
per-polygon/union status+unit subtotals, coverage, input/policy/polygon/code/
software identities dan version. li5_manifest_v1 mengikat compact copied inputs
ke original LI-4 manifest; bukan klaim seluruh raw sources disalin lagi.
Semua source rows di ledger, selected saja dievaluasi. Revisions/delta tidak
mengubah source/routing/capacity. [Review](LI_5_REVIEW.md).

[ENGINE_IO_CONTRACT_DRAFT](ENGINE_IO_CONTRACT_DRAFT.md) adalah proposal envelope
Traffic/Location untuk review, bukan schema/interface existing yang diganti.
Measured/estimated Traffic tidak disamakan dengan modeled Location.

## LI-4 implemented offline package

`li4_package_v1` adalah manifest paket view/export baru dengan package_status
SUCCEEDED_WITH_WARNINGS terpisah dari analysis_status PARTIAL pada pilot ini.
Seluruh source packet LI-3 berada di snapshot/ dan source_manifest_sha256
mengikat snapshot tersebut. Files daftar lengkap, hash/bytes dan verifier
LI-3 reused; semantic verifier merekonstruksi exports dari stored outcomes,
bukan rerouting. Proyeksi display dipin lewat versi pyproj/PROJ manifest.

`li4_view_v1` summary dan buildings JSON/CSV/GeoJSON memakai source_row_index
untuk 2623 rows; selected denominator tetap 1322. Route GeoJSON memuat stored
candidate saja termasuk over-time, connector GeoJSON adalah ledger terpisah.
Geometry interchange EPSG:4326 [lon,lat]. CSV empty cell=null; structured JSON
aman; formula-like strings escaped. Capacity hanya per decision+unit,
mixed_unit_total/final_business_capacity null; unknown capacity counts berbeda
dari unknown access. review.html embedded tanpa network/CDN. Build atomic di
direktori baru; gagal write/verify tidak menerbitkan output sukses.
[Kontrak scope, bukti, dan batas](LI_4_REVIEW.md).

## LI-3 serialization yang diimplementasikan

`li3_pilot_config_v1` membekukan N1 scope, policy v8_li3, bbox, source-cache
hashes, source/software versions dan numeric engineering inputs. `config_hash`
adalah canonical hash seluruh config selain field config_hash. Actual raw
Overpass semantic JSON/metadata dipertahankan; original transport hash tidak
disamakan dengan canonical retained file hash.

Existing canonical buildings dan li_directed_graph_v1 tetap dipakai. OSM
source IDs/raw tags berada pada sidecars; effective per-direction permissions
pada li_motor_evidence_v1. Source-node IDs menentukan junction; virtual split
nodes dibatasi oleh source way+segment, tidak menggabungkan ruas bersilangan.
Unknown conditional/via-way movements diquarantine; restrictions_complete
berarti accounting exact-or-quarantined, bukan fully known legal access.

Connectors adalah owner assumptions dengan geometri dan mapped barrier
checks/reject ledger, bukan surveyed entrances. Tidak attach langsung pada
elevated/tunnel roads; river crossing harus menjadi mapped road/bridge path,
bukan off-road connector. Target memakai nearest valid road tanpa cap numerik.

`li3_manifest_v1`: per-file relative path, bytes/SHA256, role dan dependency
list; publish atomic. Verify menolak missing/unlisted/unsafe/changed files dan
dependency cycles. Engine-source snapshot dan software locks ikut manifest.
`validation/replay_origin_manifest.json` adalah manifest yang direplay;
receipt mengikat hash manifest itu, lalu final manifest mengikat keduanya.
Tidak ada circular hash atau silent exclusions dari perhitungan.

decisions.json.gz/CSV mencakup semua source_row_index tepat sekali. Primary
decision terpisah dari warnings/verification_required. ACCEPTED/OVER_TIME,
NO_VALID_CONNECTOR/NO_ROUTE/ACCESS_UNVERIFIED, SOURCE_MISSING/RETRIEVAL_FAILED,
INVALID_GEOMETRY/PROCESSING_ERROR dibedakan; EXCLUDED_BY_SELECTION adalah
tambahan untuk valid LI-1 exclusions. Kapasitas tetap per unit/per status.
Replay membandingkan21calculation artifacts; image/log QA tidak diklaim
sebagai calculation equivalence. Detail di [review](LI_3_REVIEW.md).

## D34 — profile motor dan kapasitas yang sudah dikonsumsi engine

Policy v7 kini dikonsumsi [motor helper](../notebooks/location_intelligent_motor_routing.py)
dan [capacity helper](../notebooks/location_intelligent_capacity.py), bukan oleh
engine N1 historis. Penjelasan snapshot-only di bagian sebelumnya merupakan
status historis sebelum D34. Tidak ada bypass approved flag.

`li_motor_evidence_v1` mengikat canonical graph/selection/context/policy hashes.
Seluruh edge mempunyai resolved bool/null permission dan evidence_refs; raw
tags dipertahankan, larangan/private tidak boleh ditimpa. Permission lookup
motorcycle→motor_vehicle→vehicle→access mengikuti specificity, dengan private
tetap ditolak oleh business policy. Conditional memerlukan resolved evidence.
`blocked_turns` berisi from_edge/to_edge/evidence_ref; adapter mengekspansi
only-turn restrictions sebelum mengklaim restrictions_complete=true.

Connectors: unique connector_id, kind BUILDING/TARGET, building_id untuk origin,
node_id, road_edge_id, status VERIFIED/OWNER_ASSUMPTION/BLOCKED/UNKNOWN,
barrier_clear bool/null, evidence_refs, geometry LineString dalam metric CRS.
Start origin harus berada pada footprint dan end tepat pada node; connector
target start pada node, end pada koordinat target. Tidak menginfer straight
connector; evidence barrier tetap diperlukan. Interior-edge access membutuhkan
adapter membelah edge secara benar; engine ini hanya node-bound connector.
Source candidate distance dihitung dari representative point ke road geometry
<=125m, berbeda dari panjang detour connector. Target snap tak dibatasi angka,
tetapi semua geometri tetap di dalam snapshot graph coverage.

`li_motor_routing_v1`: effective policy+hash dan seluruh candidate disimpan;
scenario_accessible bukan bukti physical/legal access. Missing/unknown connector
atau permission yang menghalangi evaluasi menghasilkan null/not_evaluated,
bukan count0. Denied/known no-path berbeda dari data hilang. Semua edge di
network ikut permission gate; edge-state Dijkstra menegakkan blocked turns.
No-route kelas tinggi dapat fallback kelas reachable berikut; over-time tidak.

`li_capacity_reference_v1`: rows dan summary_by_unit, subtotal known+unknown
building counts; mixed_unit_total/final_business_capacity null. Num_floors
didahulukan, fallback height/3m memakai Python round min1 bila explicit enabled.
Full footprint area × level = GFA. Formula occupancy sesuai N1; unit rumah
standard4 tetap unresolved, tidak dikonversi menjadi KK atau penduduk.

Overture probe mempertahankan raw WKB/source attrs/version, lalu subtype→
canonical subclass dan geometry→GeoJSON. Hash raw/normalized terpisah. Source
coverage COMPLETE hanya untuk bounded query setelah semua STAC item bboxes
diverifikasi dan query tidak truncated; bukan geographic/physical completeness.
First blocked attempt dipertahankan; tidak menurunkan gate untuk memaksa PASS.

## Snapshot konfigurasi kebijakan motor D28

[location_intelligent_config.py](../notebooks/location_intelligent_config.py)
menjadi satu tempat edit **kebijakan baru**, schema `li_access_policy_v1`.
`get_config()` menghasilkan deep copy; CLI mengekspor JSON deterministik tanpa
retrieval, file writes atau routing. Angka berunit eksplisit; `None`/JSON null
berarti belum diputuskan. Setelah mengedit policy, gunakan versi/revision baru
dan simpan export+hash bersama manifest run; hasil lama tidak ditimpa.

Snapshot ini **belum dikonsumsi LI-2** dan tidak kompatibel sebagai substitusi
`li_routing_config_v1`. Tidak menambah bypass `approved:true`. Integrasi profile
motor, mapping bukti dan effective-config hash memerlukan task tersendiri.
Unknown access tidak digunakan untuk routing, tetapi tidak disamakan dengan
observasi physical inaccessibility. Rincian keputusan di
[D28](AREA_COVERAGE_DECISIONS.md#d28--kebijakan-motor-dan-konfigurasi-tunggal);
baseline N1 dan bukti LI-2 tetap tidak diubah.

Update D30: pengecualian null adalah limit dengan `limit_type=UNBOUNDED`,
yang berarti tidak ada batas numerik; jangan mengubahnya menjadi0 atau
unresolved. Policy v3 membedakan asumsi akses gang/portal dari bukti nyata.
Unknown lain tetap excluded. Floor dilakukan pada total menit sebelum <=10;
raw total dipertahankan dan kandidat dipilih menurut waktu total asli.

Status **PROPOSAL** untuk integrasi. Field N1 yang sudah ada ditandai
**LEGACY**; [spec](AREA_COVERAGE_SPEC.md) adalah otoritas kalkulasi referensinya.
Envelope LI-0 v1 di bagian akhir telah diimplementasikan sebagai validator
offline saja; LI-1 kini menambahkan reader/seleksi bangunan lokal di bawah.
Full Area/accessibility, kapasitas, Recount dan PPAC belum diimplementasikan.
Null tidak sama dengan0.
Dokumen ini merupakan kontrak kanonis lintas engine; tidak membuat kontrak
`DATA_CONTRACT.md` kedua. Identifier/provider yang terbukti ada di
[inventaris sumber](DATA_SOURCE_INVENTORY.md); urutan implementasi di
[roadmap](IMPLEMENTATION_ROADMAP.md).

## Identity dan context

| Struktur | Field/semantik yang diperlukan |
|---|---|
| AnalysisContext | `analysis_run_id`, schema/config revision, parent revision, created_at UTC, target `{store_code,store_name,latitude,longitude}`, context hash |
| ModuleRun | `module_run_id`, parent analysis ID/context hash, engine/version/source hashes, config hash, status, started_at/finished_at, required inputs, error/reason, artifact refs |
| ArtifactRef | Path/URI, type/schema, checksum algorithm/value, byte count, module run, source/config lineage, completeness/status; referensi lama tidak diubah |
| SourceSnapshot | Provider, release/query/snapshot ID, acquired_at, schema version, actual geographic/semantic coverage, checksum, dependencies/environment refs |

ID unik dan path-safe; jangan hanya mengandalkan timestamp resolusi detik N1.
Lat/lon harus finite dan valid sebelum projection/query. Area Coverage BLOCKED
jika lokasi belum tersedia. Unknown store name dapat tetap null dengan status
metadata eksplisit; jangan mengisi koordinat contoh atau menebak dari overlay.
Traffic yang sudah selesai tetap dapat disimpan sebagai artifact independen,
tetapi join target untuk PPAC memerlukan bukti target/context yang benar.

## CRS dan geometri

- Storage/interchange GeoJSON memakai EPSG:4326 dengan koordinat **[lon,lat]**;
  UI/form dapat menampilkan latitude dahulu dengan label eksplisit.
- Area/metric distance/routing menggunakan local projected CRS meter yang
  dicatat per run. N1 memilih UTM; contoh EPSG:32748. Bukan area degree² atau
  Web Mercator sebagai pengganti metrik yang disetujui.
- CRS tidak disimpulkan dari magnitude angka. Tolak CRS hilang/ambigu, invalid
  coordinates, geometri kosong/unsupported; reject atau repair invalid
  geometry memerlukan policy versi dan audit sebelum/after.
- Floor area footprint tetap seluruh polygon/multipolygon; inclusion N1
  memakai representative point≤400m. Representative point berbeda dari
  centroid dan footprint-intersection. Recount predicate belum disetujui.
- Simpan raw geometry, representative point/method, measured area dan flags
  normalisasi. Geometry repair/split tidak boleh membuat ID dobel diam-diam.
- Koordinat video berada pada domain terpisah: native pixel top-left, X kanan,
  Y bawah, video hash dan dimensi. Polygon video bukan polygon geografis;
  tidak ada homography/georeferencing yang diasumsikan.

## BuildingRecord

Key usulan `(provider, release_or_snapshot, building_id)`; jangan dedup dari
representative point saja. Layer retrieved/eligible/accessible adalah universe
yang berbeda, masing-masing mempunyai count dan reason exclusions.

| Field | Tipe/unit dan makna |
|---|---|
| `building_id`, `class`, `subclass` | LEGACY strings/null; `subclass` N1 sebenarnya memuat Overture subtype |
| `geometry`, `lat`, `lon` | Footprint EPSG4326 dan representative point; bukan entrance yang diverifikasi |
| `area_m2`, `distance_to_store_m` | LEGACY projected full footprint dan target-to-representative-point distance; retain full precision baru, display precision terpisah |
| `building_type`, eligibility/rejection reason | Standard/apartment/dormitory/hotel atau unsupported; rule version wajib |
| `level`, `level_source`, raw floors/height | Nullable positive integer estimate; sumber Overture vs estimated_from_height dan metode/divisor dicatat |
| `gross_floor_area_m2`, `occupancy_rate`, `capacity_model` | Nullable derived area, fractional occupancy assumption, structured formula inputs/results; bukan label occupancy observasi |
| `household` → `legacy_household_capacity` | LEGACY mixed-unit value, nullable; alias baru tidak memberi arti household/resident yang belum disetujui |
| `estimated_guests` | LEGACY transient hotel guest estimate, nullable; terpisah dari households |
| Capacity fields usulan | `dwelling_units_estimated`, `occupied_dwelling_units_estimated`, `occupied_rooms_estimated`, `resident_equivalent_estimated`; isi hanya setelah unit/formula disetujui, lainnya null |

Ringkasan capacity harus memuat known subtotal, unknown count, excluded count,
unit/model version dan completeness. **Dilarang** mengganti unknown dengan0
untuk menyatakan demand lengkap. Jangan menjumlah household legacy dengan
estimated_guests atau menamainya resident_total.

## Routing dan accessibility

| Struktur/field | Makna |
|---|---|
| Graph identity | Source/time/request envelope/network_type/CRS/checksum, directed multiedge keys |
| Candidate identity | building key + `(u,v,key)` + graph hash; off-road distance, access point, partial edge direction/length, road taxonomy, topology status |
| `building_to_road_m` | LEGACY straight representative-point→access-point distance; bukan jalan masuk yang dibuktikan |
| `network_distance_m` | LEGACY directed v→store-node path length; bukan total seluruh perjalanan |
| `road_distance_m` | LEGACY off-road connector + partial edge + network path; store-node→target connector tidak termasuk |
| `travel_time_min` | LEGACY model constant speed; bukan live ETA. Catat precision/classification version |
| `accessible`, `accessibility_reason` | Keputusan threshold dan topology dengan flag validity/coverage; null/unresolved untuk source/graph failure pada kontrak baru |
| `route_generated`, route geometry | Visual reconstruction status, tidak otomatis sama dengan accessibility |
| Endpoint QA usulan | Target/node coordinates, snap distances, geographic coverage flags; larang nearest-node outside-coverage masquerading sebagai route yang valid |

Persist candidate yang ditolak dan dipilih, biaya/metode selection, selected
edge/path keys, threshold comparison dan input raw precision. N1 hanya
menyimpan sebagian informasi ini; jangan mengklaim audit table sudah tersedia.

## Recount

`polygon_id`, immutable revision/parent, geometry CRS, creator/time, source
snapshot and universe, predicate/boundary version, coverage relation dan result.
Membership table menyimpan polygon↔building key/reason; jumlah per-polygon
dapat overlap. Union total adalah jumlah **unique building keys**, bukan sum
subtotal polygon. Capacity union memakai member yang sama dan unit konsisten.

`OUTSIDE_COVERAGE`/`PARTIAL_COVERAGE` menandai polygon yang tidak sepenuhnya
didukung snapshot. Filtered residential table juga tidak mendukung klaim all
buildings walau footprint geographic tersedia. Pilihan retrieve tambahan vs
hanya visible covered result adalah [D06/D07](AREA_COVERAGE_DECISIONS.md).

## Status, output dan antar-engine

| Status usulan | Makna konsumen |
|---|---|
| NOT_RUN / RUNNING | Belum ada hasil final; jangan tampilkan0 |
| BLOCKED | Required input/policy belum tersedia; alasan eksplisit |
| SUCCEEDED | Perhitungan dalam scope dan seluruh output wajib lengkap; bukan label production-valid |
| SUCCEEDED_WITH_WARNINGS | Output dalam scope tersedia dengan keterbatasan nonfatal yang dinyatakan |
| PARTIAL | Sebagian scope gagal/tidak tercakup; unknown/null tetap terlihat |
| FAILED | Eksekusi/output wajib tidak dapat diselesaikan |
| STALE | Hasil historical sah untuk context lama, bukan input final context baru |

N1 memakai SUCCESS/PARTIAL/FAILED; adapter memetakan status sambil menyimpan
nilai aslinya. Empty result0 hanya sah jika query sukses dan definisi scope
dinyatakan; jangan mengartikannya sebagai tidak ada bangunan di dunia nyata.

Output minimum usulan: config/provenance/summary/diagnostics JSON, buildings
CSV+GeoJSON, route GeoJSON, source coverage, graph refs, candidate decisions,
manifest checksum. Map HTML adalah tampilan turunan; tabel menjadi data utama.
Tetapkan CSV `capacity_model` sebagai JSON terstruktur yang aman atau pindahkan
ke JSON tersendiri; jangan memakai `eval` terhadap repr dict export legacy.

Traffic refs menyimpan run/branch/video/filter/geometry/policy hashes, source
frame scope/FPS/date/period completeness, category/direction dan measured vs
estimated counts. Pending/invalid/cancelled bukan accepted. Machine/reviewed
adalah alternatif snapshot, tidak dijumlahkan. Attachment tidak mengganti
event IDs atau physical passage IDs existing. PPAC memilih satu referensi
eksplisit per feature; lihat [PPAC_SPEC](PPAC_SPEC.md).

## Lapisan data dan pembekuan

| Lapisan | Isi dan pembatasan |
|---|---|
| Raw source | Response/record asli, query/request envelope dan source namespace; simpan bytes/fingerprint, jangan overwrite dengan hasil normalisasi |
| Normalized source | Nama/type/CRS/unit kanonis, source key dan referensi raw; konversi/reject ledger berversi; bukan hasil estimasi bisnis |
| Frozen snapshot | Paket raw/normalized+manifest ber-checksum yang dipilih untuk suatu run; immutable; pembekuan adalah sifat artifact, bukan pengganti normalisasi |
| Derived geospatial | Seleksi building, capacity model, routes/accessibility dan Recount membership; setiap hasil mengikat snapshot/config/target |
| Traffic machine | Event/episode dari run mesin dan policy tertentu, dengan measured/estimated/pending/invalid tetap terpisah |
| Reviewed | Overlay keputusan dengan reviewer/scope/frame-bukti/reason; machine snapshot tetap tersedia; jangan sum keduanya |
| PPAC-ready features | Pilihan snapshot, unit/period/normalisasi/completeness eksplisit; tidak mengedit engine atau mengisi missing dengan0 |
| PPAC result | Formula/constants/baseline version, input refs dan breakdown; BLOCKED jika gate bisnis belum terpenuhi |

Frozen source bukan bukti source lengkap atau terkini. Hasil offline dapat
reproducible dan valid untuk scope historis; tidak otomatis STALE. Freshness
harus dibandingkan dengan policy/as-of yang dinyatakan. Tanpa policy, label
freshness `UNKNOWN`, jangan mengarang TTL. Kolom historis `SPD` pada BigQuery
berunit **UNKNOWN**; ia belum dapat dipetakan ke struk/hari atau fitur PPAC.

## Envelope minimum untuk validator offline berikutnya

**Kontrak teknis LI-0 v1**; bukan approval rumus bisnis.
Validator hanya menerima JSON lokal; tidak mengambil data,
memproyeksikan geometri, membuat context dari contoh N1 atau menjalankan engine.

| Dokumen/field | Type dan aturan minimum yang direncanakan |
|---|---|
| `context.schema_version` | String versi kontrak yang didukung; versi tidak dikenal ditolak, bukan ditebak |
| `context.analysis_run_id` | String opaque unik per analisis, aman sebagai satu komponen path: huruf/angka/`_`/`-`, tanpa separator atau `..`; timestamp saja tidak menjamin unik |
| `context.parent_analysis_run_id` | String/null; perubahan target/config membuat revision baru, tidak overwrite parent |
| `context.created_at` | String ISO8601 UTC; waktu pembuatan context, bukan otomatis source timestamp |
| `context.target` | Object `store_code`, `store_name` string/null; `latitude`, `longitude` finite number/null, keduanya tersedia atau keduanya null; `crs="EPSG:4326"`; reason untuk metadata unknown |
| Coordinate gate | Latitude [-90,90], longitude [-180,180]; bool/NaN/Infinity/string tidak dianggap number; missing coordinates membuat Area BLOCKED, bukan lokasi0,0. Koordinat geografis valid belum menjamin domain UTM/source didukung |
| `context.config` | Object `version`, per-module `parameters` dan `unresolved_decisions`; nilai tidak disuplai tidak diwarisi diam-diam dari CFG N1. Unit pada numeric parameter wajib eksplisit |
| `context.context_hash` | SHA256 dari content context selain field hash sendiri; canonicalization yang sama untuk producer/validator, bukan hash tampilan JSON arbitrer |
| `manifest.schema_version`, `analysis_run_id`, `context_hash` | String; harus cocok dengan context dan versi yang didukung |
| `manifest.sources` | Array SourceRef; boleh kosong pada context-only fixture, tetapi tidak berarti Area memiliki input lengkap |
| `manifest.modules` | Array ModuleRun; module/run IDs unik, parent/context cocok, required inputs dan status eksplisit |
| `manifest.artifacts` | Array ArtifactRef; unique artifact IDs, layer/schema, producer, path, checksum/byte count dan dependencies untuk artifact yang benar-benar tersedia |

Canonicalization usulan untuk fixture v1: JSON UTF-8, object keys sorted,
compact separators, tanpa NaN/Infinity, tanpa normalisasi string/angka implisit;
producer dan validator memakai aturan yang sama. Implementasi perlu fixture
hash yang deterministik; ini bukan klaim interoperabilitas lintas bahasa
sebelum diuji. Fingerprint source bytes tetap berbeda dari context/config hash.

SourceRef minimum: `source_ref_id`, `inventory_id` (SRCxx), `kind`
(`BIGQUERY`/`OBJECT_STORAGE`/`API`/`LOCAL_FILE`), `provider`, `locator`,
`acquisition_mode` (`LIVE_ACQUIRED`/`OFFLINE_SNAPSHOT`/`SYNTHETIC_FIXTURE`),
`availability`, `source_version`, `source_as_of`, `acquired_at`,
`schema_version`, `fingerprint`, `coverage`, `crs`, `units`, `provenance`.
Unknown metadata memakai null+`unknown_reasons` per field, bukan fabricated
value. `acquired_at` berbeda dari source release/as-of; successful artifact
memerlukan fingerprint nyata. `auth_ref` opsional hanya nama binding/secret,
tanpa token, private key atau nilai credential. Synthetic fixture tidak boleh
memakai identitas/hash seolah-olah response provider nyata.

ArtifactRef memakai path relatif di run baru dan tidak boleh keluar dari
root melalui traversal/symlink. Referensi historis di luar run baru memakai
SourceRef lokal read-only yang eksplisit, bukan ditulis ulang sebagai output.
URI remote hanya dicatat: validator offline tidak mengaksesnya. Checksum
artifact lokal yang tersedia dapat diverifikasi dengan baca file; file hilang
harus tercatat, tidak diganti stub. Missing mandatory config/policy/source
menghasilkan diagnostic dan readiness BLOCKED; malformed envelope/hash
mismatch menghasilkan INVALID. Envelope valid tidak berarti engine siap.

## Availability, freshness dan readiness adalah sumbu terpisah

| Source availability usulan | Bukti yang harus dicatat |
|---|---|
| `NOT_ATTEMPTED` | Tidak ada request; row_count=null. Bukan request FAILED |
| `UNAVAILABLE` | Required mount/file/binding/source belum tersedia; reason eksplisit, belum tentu request pernah dilakukan |
| `REQUEST_FAILED` | Request benar-benar dilakukan dan gagal; sanitized diagnostic, row_count=null |
| `AVAILABLE_EMPTY` | Request/decode/normalization scope sukses,0 records dan coverage tercatat; bukan exception yang ditangkap lalu dijadikan dataframe kosong |
| `AVAILABLE` | Artifact tersedia dan dapat diverifikasi; row count/completeness dan source scope tercatat |
| `PARTIAL` | Sebagian request/scope/records gagal; known row count dan unknown/excluded scope dibedakan |

`freshness` terpisah: `UNKNOWN`, `WITHIN_POLICY`, `STALE_FOR_POLICY` dengan
policy reference dan evaluasi as-of. Context mismatch tetap STALE terhadap
context baru walau tanggal source masih baru. `validation_status`
(`NOT_CHECKED`/`VALID`/`INVALID`) menilai contract/quality; ModuleRun status
menilai eksekusi. Contoh: source offline AVAILABLE bisa schema INVALID;
source AVAILABLE_EMPTY bisa freshness UNKNOWN; PPAC tetap BLOCKED walau Area
SUCCEEDED. Jangan memampatkan semua keadaan menjadi satu flag sukses.

## Kunci reuse Traffic pada integrasi

Source video/filter/model/frame-scope dan detector/tracker/ReID provenance
mengikat cache deteksi/track/appearance. Perubahan counting geometry/policy
saja dapat memakai cache upstream yang kompatibel dan lengkap, lalu membuat
event run baru; jangan menganggap event cache lama masih valid. Perubahan
filter membatalkan reuse output model dari input berbeda. Perubahan reviewed
overlay membuat snapshot reviewed baru tanpa mengubah machine baseline.
Tidak ada replay atau perubahan cache yang dilakukan oleh tugas dokumen ini.

## Klarifikasi serialization LI-0 v1 yang diimplementasikan

Otorisasi tugas LI-0 mencakup klarifikasi bentuk field terkecil yang belum
ditentukan di atas. Implementasi ada pada
[helper](../notebooks/location_intelligent_validator.py), dengan
[fixture](../notebooks/fixtures/li0/context.json) dan
[manifest](../notebooks/fixtures/li0/manifest.json). Tidak ada schema paralel.
LI-1 building-selection subset telah diimplementasikan; capacity/routing dan
aturan bisnis OPEN tidak diselesaikan oleh validator.

- `schema_version` context/manifest adalah `location_intelligent_v1`;
  hasil validator `location_intelligent_validation_v1`. External source/artifact
  schema version adalah nonempty string provenance, **belum verifikasi payload
  schema provider**. Schema envelope tak dikenal atau field salah ketik ditolak.
- `config={version,area_coverage:{parameters,metric_crs,unresolved_decisions}}`.
  LI-0 v1 membatasi config ke modul ini; penambahan modul memerlukan perluasan
  kontrak, bukan unknown keys yang diabaikan. `version` adalah label nonempty
  buatan caller, bukan default library.
- `parameters` adalah mapping nama→`{value,unit,unknown_reason?}`. Nama N1
  `building_radius_m`,`min_area_m2`,`max_area_m2` wajib sebelum input gate
  seleksi bangunan READY. Ketiganya positif/finite, min<max; unit `m`,`m2`,`m2`.
  Field parameter tidak disuplai→CONFIG_REQUIRED/BLOCKED; wrong type/unit/range
  →INVALID; explicit null+reason→UNKNOWN/BLOCKED. Tidak ada default400/45/550.
- Parameter numerik N1 lain yang dikenal dapat diperiksa bila disuplai:
  access/network/floor distance=`m`, travel=`min`, speed=`km/h`, average unit/
  room area=`m2`, guests per room=`guest/room`; quantity positif. Parameter
  `*_occupancy`/`*_net_floor_ratio` yang tercantum SPEC serta
  `standard_residential_occupancy` memakai `ratio` dalam[0,1].
  `standard_residential_household` memakai label `legacy_unknown`, hanya
  mempertahankan ketidakjelasan unit dan menghasilkan warning. Parameter
  selain allowlist N1 ini **UNSUPPORTED**, tidak diabaikan. Ini tidak
  mengesahkan kapasitas, threshold akses, atau config full engine N1.
- `metric_crs` wajib untuk READY. Versi ini menerima WGS84 UTM
  EPSG32601–32660/32701–32760 dengan target di zona6° dan hemisphere terkait,
  latitude[-80,84]. CRS lain belum didukung. Tidak melakukan proyeksi atau
  memilih zona otomatis. Range lat/lon geografis global tetap diperiksa
  terpisah; lokasi valid global belum berarti supported metric calculation.
- `unresolved_decisions` adalah array string unik untuk **scope seleksi
  bangunan yang diminta**; bila nonempty tetap BLOCKED. D04 bisnis kapasitas
  boleh tetap OPEN di decision log karena capacity tidak termasuk input gate ini.
- Hash memakai `ensure_ascii=False`, keys sorted, separators `(',',':')`,
  UTF-8, `allow_nan=False`. Context hash mengecualikan field `context_hash`;
  `config_hash` hanya atas object `context.config`. Fixture memuat golden hash
  untuk menguji producer/validator. Keunikan ID lintas seluruh penyimpanan
  belum dapat dibuktikan tanpa registry; validator memeriksa bentuk, parent
  bukan dirinya sendiri dan uniqueness dalam manifest.

### Source, module dan artifact

SourceRef menambahkan field yang sebelumnya hanya dijelaskan semantiknya:
`row_count` dan `byte_count` integer nonnegative/null, `unknown_reasons`
mapping field→reason, `coverage={scope,completeness}` dengan completeness
COMPLETE/PARTIAL/UNKNOWN, `provenance={origin,description,dependencies}`.
Origin harus sama dengan acquisition_mode; dependencies array source IDs
unik, tidak self/cyclic. `scope` adalah deklarasi coverage, **bukan hasil
verifikasi geographic completeness**. `units` adalah mapping field→unit.
Fingerprint berbentuk `{algorithm:"sha256",value:<lowercase64hex>}`.
Available data wajib checksum/byte_count/observed row_count; unavailable,
failed, not-attempted atau availability unknown memakai ketiganya null.
Null metadata wajib reason; null availability adalah unknown eksplisit,
bukan status sukses baru. AVAILABLE mensyaratkan row_count>0;
AVAILABLE_EMPTY mensyaratkan0 dan fingerprint artifact lokal yang tersedia.

`local_path` opsional menunjuk snapshot lokal suatu remote locator.
Tanpanya remote source tidak dapat memenuhi offline gate; tidak ada fetch.
LOCAL_FILE memakai locator sebagai path lokal. Path relatif harus tetap
di root input sesudah resolve symlink; absolute local SourceRef hanya untuk
referensi historical read-only eksplisit. Artifact output selalu relative,
tidak boleh traversal/keluar root. Semua checksum file dibaca streaming;
file tidak dibuat, diubah atau dipindah oleh validator.

`freshness` opsional, UNKNOWN bila tidak dinyatakan; evaluasi
WITHIN_POLICY/STALE_FOR_POLICY memerlukan nonempty `freshness_policy_ref`.
Validator memeriksa deklarasi, **tidak mengeksekusi freshness policy**.
Stale, partial, missing schema/CRS/units/acquired_at/coverage atau file sumber
wajib menghalangi gate. Unknown source vintage/provider tetap terlihat;
tidak mengubah file offline menjadi source terbaru. Metadata invalid tetap
error walau module opsional. Unknown/unavailable source modul opsional tidak
memblokir Area apabila tidak dipilih sebagai required input.

ModuleRun field konkret: `module_run_id,module,analysis_run_id,context_hash,
config_hash,status,required_inputs,artifact_refs,started_at,finished_at,
engine,error`. Module adalah area_coverage/traffic_counter/recount/ppac;
required_inputs adalah source_ref IDs, artifact_refs adalah output IDs.
Untuk NOT_RUN, execution timestamps null, engine null atau provenance rencana.
Engine jika ada berbentuk `{name,version,source_hashes}` dengan mapping
source→SHA256 nonempty. RUNNING perlu started_at tanpa finished_at;
FAILED/PARTIAL dan successful run perlu timestamps berurutan dan engine
provenance. Successful run juga perlu output refs. BLOCKED/FAILED/PARTIAL
memerlukan nonempty `error`/reason; pesan validator tidak mengulang nilainya.

ArtifactRef konkret: `artifact_id,layer,schema_version,module_run_id,path,
fingerprint,byte_count,dependencies,status,completeness`. Layer memakai
RAW/NORMALIZED/FROZEN/DERIVED_GEOSPATIAL/TRAFFIC_MACHINE/REVIEWED/PPAC_FEATURES/
PPAC_RESULT. Producer dan artifact harus saling merujuk; modul NOT_RUN/BLOCKED
tidak dapat menghasilkan existing artifact. Success producer membutuhkan
complete successful outputs. Dependencies output wajib nonempty dan memakai
source/artifact IDs yang ada, tanpa self/cycle; namespace source/artifact tidak
boleh bertabrakan.
Source/config lineage artifact ditelusuri melalui dependencies dan ModuleRun.

### Hasil dan perintah

Diagnostics berisi stable `code,path,severity,blocking,message`, diurutkan
deterministik. ERROR→validation_status INVALID; BLOCKER→envelope dapat VALID
tetapi readiness BLOCKED; WARNING dan UNKNOWN nonblocking tetap ditampilkan.
UNKNOWN juga dapat blocking ketika input itu wajib. Pesan memberi tindakan
tanpa mencetak isi file/credential/arbitrary error dari input.

`offline_readiness=READY` hanya **LI1_BUILDING_SELECTION_INPUT_CONTRACT_ONLY**:
context/config valid, tepat satu selected area module NOT_RUN, required
SRC04 terikat dan file lokal terbukti fingerprint-nya; metadata coverage
menyatakan COMPLETE. Bukan validasi payload/geometri/kelengkapan dunia nyata,
capacity/routing/PPAC atau izin/provider live. `live_readiness=NOT_VERIFIED`
selalu. Modul lain tidak mendapat readiness claim dari gate ini.

```bash
python -B notebooks/location_intelligent_validator.py \
  --context notebooks/fixtures/li0/context.json \
  --manifest notebooks/fixtures/li0/manifest.json \
  --root notebooks/fixtures/li0
```

Exit code0=VALID+READY,1=INVALID,2=VALID+BLOCKED. JSON rusak, duplicate keys,
nonfinite dan file JSON tidak dapat dibaca menghasilkan diagnostic terstruktur.
CLI hanya menulis JSON ke stdout; library `validate` dan `validate_files`
tidak memutasi input atau menulis artifact. Tidak ada credential/network,
UI/client database, source adapter, geospatial dependency atau engine import.

## Perbaikan LI-0 dan kontrak LI-1 offline — 22 Oktober 2026

Baseline43 tes dan source/fixture LI-0 sebelum perbaikan dipertahankan pada
[arsip baseline v1](evidence/location_intelligent/li0_baseline_v1/manifest.json).
Enam regresi direproduksi gagal sebelum fix: Unicode surrogate pada value/key,
checksum metadata PARTIAL yang diabaikan, alasan quantity bukan string,
unused SRC04 menghalangi selected source, dan FIFO JSON dibuka sebelum
regular-file check. Sekarang Unicode wajib UTF-8 encodable; optional reason
jika disuplai tetap harus string; fingerprint PARTIAL jika disuplai diperiksa;
readiness hanya bergantung pada selected required sources; input JSON harus
regular local file. Bukan perubahan makna READY atau penambahan fallback.
Sumber optional malformed tetap INVALID; optional unavailable tidak
membatalkan required snapshot lain yang sah. PARTIAL source tetap tidak READY.

### Format snapshot lokal

[LI-1 helper](../notebooks/location_intelligent_buildings.py) menerima satu
SourceRef SRC04 yang dipilih eksplisit dan ada di required_inputs modul Area.
Gate LI-0 wajib READY. `schema_version="li_building_snapshot_v1"` adalah
serialization lokal kanonis, **bukan schema/release provider baru**.
`li0_building_fixture_v1` lama tidak otomatis di-upgrade. Tidak ada raw
Overture mapping, reader Parquet/CSV/WKB atau source adapter pada tahap ini.

File `.json`/`.geojson`: root type=FeatureCollection dengan features array.
SourceRef wajib crs=EPSG:4326 dan units.coordinates=degree; posisi [lon,lat].
Optional legacy GeoJSON crs hanya diterima jika persis named EPSG:4326;
konflik gagal pada tingkat snapshot. CRS tidak ditebak dari magnitude angka.
Setiap Feature wajib properties dengan building_id string stabil nonempty,
class dan subclass string/null. Subclass adalah field kanonis subtype N1.
Omission tidak dianggap null; Feature.id bila ada harus sama dengan building_id.
ID dipertahankan persis, tanpa trim/case-fold/dedup diam-diam.

Optional num_floors/height menerima finite positive number/null, bukan bool
atau numeric string. Field tambahan dipertahankan di raw_properties; angka
nonfinite pada record ditolak. Household sumber tidak dihitung ulang,
diubah unit atau dijumlahkan. Tidak ada output capacity.

Footprint wajib 2D Polygon/MultiPolygon. Reject null/empty, unsupported type,
posisi nonfinite/bool/out-of-range, ring pendek/tidak tertutup, invalid topology
dan transform failure. Tidak memperbaiki polygon, menutup ring atau membuang Z.

### Backend dan selection reference

Backend yang tersedia pada `/usr/bin/python3` memakai GDAL/OGR3.10.3,
GEOS3.13.1 dan PROJ; versi aktual dicatat di output. Ini penggunaan dependency
lokal, bukan port seluruh notebook atau perubahan provider. OGR hanya parsing
geometry in-memory, tanpa Open dataset driver. Shapely tidak tersedia di
lingkungan ini; GEOS PointOnSurface adalah operasi representative point yang
dipakai Shapely/N1. Tidak mengklaim byte-identical dengan environment N1 lama.
LI-0 tetap standard-library tanpa import backend geospasial.

Mengikuti cell10 N1: representative point dihitung di WGS84 **sebelum**
proyeksi. Full footprint dan point ditransformasi melalui PROJ ke metric_crs
eksplisit context, axis XY. Seluruh vertex harus di ordinary UTM zone dan
hemisphere domain yang didukung LI-0; tidak auto-select/fallback CRS. Area
m² mencakup footprint penuh, holes dan multipart, tanpa clip circle. Distance
adalah representative-point→target dalam projected meter, bukan entrance.

Rule `N1_BUILDING_SELECTION_V1` membekukan class sets CFG N1: apartments,
dormitory, hotel; special class menang atas subtype. Selain itu subtype
trim/lower null/empty/residential→standard. Office+null tetap masuk sebagai
perilaku legacy, bukan bukti tipe bangunan nyata. Tidak menambah class taxonomy.
Urutan selection: distance≤configured radius → supported class → area>min →
khusus standard area<max. Fixture memakai400m/45m²/550m² eksplisit. Tidak ada
default, epsilon atau rounding sebelum gate. Tes exact numeric boundaries
dipisahkan dari geometri hasil floating-point transformation. Tidak ada
routing, accessibility, floor/capacity atau repair dalam LI-1.

### Disposition, duplicate policy dan hasil

Seluruh kemunculan ID berulang ditolak DUPLICATE_BUILDING_ID; tidak memilih
first/last. Snapshot menjadi PARTIAL dan record lain dapat diproses. Ini
policy integritas lokal, bukan entity matching bangunan fisik lintas ID.
Satu primary disposition per row0-based: payload structural → identity →
attributes/numerics → geometry → selection. Ledger tidak mengklaim seluruh
masalah sekunder record yang sudah ditolak. Selection exclusion diberi
EXCLUDED; quality/integrity failure diberi REJECTED.

Ledger membawa analysis/source/snapshot ID, source row, building ID bila ada,
stage/code/message/field, context/config hash, rule version dan metrics bila
tersedia. Selected records membawa raw properties/geometry, key/row/ID,
class, full-precision area/distance, representative point dan metric CRS.
Envelope `location_intelligent_building_selection_v1` mengikat snapshot,
provenance, config/context dan backend versions.

`source_records = selected + excluded + rejected = accounted_records`.
Ada rejected→PARTIAL dan complete_for_selection=false. Hanya selection
exclusions→SUCCEEDED walau selected0; valid empty source juga observed0.
Source missing/unreadable/malformed/unsupported schema/checksum/count mismatch
→BLOCKED/FAILED dan summary=null, **bukan zero buildings**. Bytes yang
dikonsumsi diperiksa hash-nya lagi setelah LI-0. Backend hilang→BLOCKED.

CLI/API hanya menghasilkan JSON/dict; input manifest immutable. Success
adalah stage seleksi, bukan full Area Coverage atau perubahan parent NOT_RUN.
Publication engine menunggu tahap lain. Live readiness selalu NOT_VERIFIED;
declared coverage belum membuktikan geographic completeness. Belum ada
real snapshot lengkap N1/Overture yang tervalidasi pada tugas ini.

```bash
PROJ_NETWORK=OFF /usr/bin/python3 -B notebooks/location_intelligent_buildings.py \
  --context notebooks/fixtures/li1/context.json \
  --manifest notebooks/fixtures/li1/manifest.json \
  --root notebooks/fixtures/li1 --source-ref fixture-buildings
```

Exit0=SUCCEEDED,1=FAILED,2=BLOCKED,3=PARTIAL. Python default tanpa GDAL tetap
menjalankan LI-0 tetapi tidak memenuhi dependency gate LI-1. Bukti run:
[execution](evidence/location_intelligent/li01_20261022/execution.json).

## LI-2 — directed routing offline dan policy gate

22 Oktober2026. [Helper](../notebooks/location_intelligent_routing.py) dan
[tes](../notebooks/location_intelligent_routing_tests.py) menambahkan routing
diagnostik; LI-0/LI-1 executable dan fixtures tidak diubah. Tidak ada adapter
OSM/live source, map, capacity, Recount atau PPAC. D02/D03/D05/D10 masih OPEN;
v1 tidak menyediakan flag config untuk mengesahkannya secara sepihak.

### Input, schema dan provenance

API `route_buildings(context,manifest,buildings,graph,config,root=...)`
memeriksa ulang LI-0, menerima hasil LI-1 yang tersedia (SUCCEEDED/PARTIAL),
dan memeriksa source/context/config binding, selected/ledger row counts,
unique building IDs serta representative-point CRS. PARTIAL LI-1 berarti
hanya selected subset yang dirutekan, bukan seluruh bangunan sumber.

Graph lokal `li_directed_graph_v1`: graph_id, directed=true, crs sama dengan
metric_crs context, units coordinates/distance=`m`, travel_time=`s`, coverage,
provenance, nodes dan edges. Ini schema **fixture/local normalized graph**,
bukan schema OSM baru atau source adapter. Coverage `{bbox,completeness,scope}`
memakai closed metric rectangle [xmin,ymin,xmax,ymax]; completeness
COMPLETE/PARTIAL/UNKNOWN adalah deklarasi, bukan bukti geographic completeness.
Provenance memuat origin SYNTHETIC_FIXTURE/OFFLINE_SNAPSHOT, source_version,
source_as_of (nullable), description. Belum tersedia actual frozen OSM package.

Node `{node_id,x,y}` dan edge `{edge_id,u,v,key,length_m,travel_time_s,highway,
service,access_allowed,geometry}` eksplisit. IDs string unik; `(u,v,key)`
unik untuk edge paralel. Cost wajib finite nonnegative, tidak default0;
aggregate overflow tidak diterima. Graph/node/edge/unit/coverage invalid
adalah source-level failure, bukan zero reachable buildings.

Graph edge geometry opsional/null, atau typed LineString dengan XY metric
sesuai graph CRS; ini internal graph schema, bukan GeoJSON WGS84 interchange.
Geometry jika tersedia wajib berorientasi tepat u→v dan di dalam extent;
tidak auto-reverse atau membuat garis dari node saat geometry hilang.
Positive geometry tidak boleh length0. Edge tanpa geometry boleh untuk
topological traversal, tetapi tidak untuk geometric access discovery.

Routing config `li_routing_config_v1` memuat version, analysis_run_id,
context_hash, selection_hash, graph_hash, profile N1_REFERENCE_ONLY,
path_weight (`travel_time_s`/`length_m`), parameters, policy_refs,
connector_policy dan target_connector_policy. Context harus cocok.
Selection/graph hash adalah **canonical JSON hash v1**, berbeda dari hash
bytes file; CLI juga mencatat input_file_sha256 atas bytes yang dibaca.
Policy refs D02/D03/D05/D10 wajib eksplisit; ref tidak menggantikan approval.

Quantities bersatuan wajib: max_building_to_road_m=125m, max_travel_min=10min,
motorcycle_speed_kmh=7km/h untuk profile reference ini. Nilai lain ditolak
REFERENCE_CONTROL_CHANGED, bukan silent tuning. max_target_snap_m adalah
**input diagnostik fixture**, bukan default/rekomendasi produksi D05;
fixture50m eksplisit, null+reason menghasilkan snap-policy unresolved.
Missing/wrong types/units tidak diisi default. Approval bisnis menunggu
policy/version baru, bukan menambah `approved=true` pada config.

### Topology, konektor dan biaya

Representasi adjacency lokal dan `heapq` Dijkstra dipakai karena NetworkX
tidak tersedia pada environment Python sistem; tidak menambah framework.
Semua stored directed parallel edges dipertimbangkan. Tidak ada reverse edge,
U-turn atau koneksi antarcomponent tambahan. Path tie-break: total weight →
fewest hops → lexicographic edge-ID sequence, termasuk zero-cost cycle handling.
Ini extension deterministik fixture, bukan klaim identik dengan insertion-order
ties NetworkX N1. Route nodes/edge IDs mempertahankan arah building→target.

Target/projected building points menggunakan transform eksplisit LI-1.
Target/building di luar bbox tidak disnap ke dalam graph. Nearest target
node memakai (distance,node_id); declared snap limit memakai `≤` tanpa
epsilon. Unknown/exceeded snap dan coverage outside menghasilkan route_found
null/NOT_EVALUATED melalui reason khusus, bukan no-directed-path false.

Access policy `EXPLICIT_FIXTURE_ACCESS_AND_N1_ROAD_CLASS` mensyaratkan road
class street/main street/highway, geometry tersedia, distance≤125m, serta
access_allowed=true. Bool/null itu **anotasi izin fixture**, bukan field OSM
yang diklaim terverifikasi. False/unknown ditahan; geometric proximity saja
tidak mengesahkan access. N1 road taxonomy digunakan untuk kandidat akses;
network path tetap dapat melalui stored service/gang edges.

Access point adalah nearest point sepanjang stored polyline. Kendaraan/model
berjalan hanya dari access point menuju v pada edge u→v. Partial cost memakai
remaining geometry-length fraction × stored edge length, seperti N1.
Network shortest path dimulai dari v menuju snapped target node. Output
memisahkan building connector, partial edge, network dan snap/target offset.
Full journey dari gedung/entrance legal tidak diasumsikan terbukti.

Target connector policy `OMIT_N1_REFERENCE_REPORT_OFFSET` mempertahankan
omission N1: reference distance=off-road + partial + network, tanpa snap-node→
actual-target. Omitted distance/time serta counterfactual total including
target tetap ditampilkan terpisah. Tidak mengadopsi omission sebagai bisnis.

Path weight memakai cost graph eksplisit, distance atau seconds. Network
stored time dan constant7km/h reference time tetap terpisah. Jika path weight
atau stored times berbeda dari N1 constant-speed model, output memberi
WEIGHTED_GRAPH_DIAGNOSTIC_VARIANT dan n1_network_cost_model_matches=false.
Tidak menyamakan varian weighted graph dengan N1 parity.

Candidate dipilih setelah reachability filter dengan `(round(offset_m,2),
round(reference_time_min,3),u,v,key,edge_id)`; nearest reachable, bukan minimum
total ETA. Network/connector raw costs full precision; threshold memakai
**Python round(total_distance/speed/60,3) <10**, sesuai N1. Tidak ada tolerance
baru. Tie IDs lokal string adalah extension deterministik, bukan mapping OSM
numeric IDs yang sudah diimplementasikan.

### Hasil, geometry dan gate

Envelope `location_intelligent_routing_v1` menyimpan analysis/target/source/
config/graph/policy hashes, satu row per selected building, seluruh candidates
dan rejected-candidate diagnostics. Network nodes dimulai dari v; partial
access edge direferensikan terpisah agar tidak mengklaim melewati u dahulu.
Road geometry jika lengkap berasal dari stored forward edges dan partial
polyline, ditransformasi ke **EPSG:4326** untuk interchange. road_coordinates_m
disediakan terpisah sebagai metric coordinate array. Off-road/target physical
entrance geometry tidak diciptakan. Missing network geometry→route_geometry
null dengan reason; route_found numerik masih dapat true.

route_found=true/false menilai rute di model graph; null berarti tidak
dievaluasi akibat snap/coverage/input. reference_accessible hanya membandingkan
model waktu di atas, bukan approval. **accessible selalu null pada v1**;
accessibility_gate=BLOCKED dan unresolved_decisions eksplisit. Route ditemukan
dapat reference_accessible=false karena waktu≥threshold.

Summary merekonsiliasi input_selected_buildings=route_found+no_route+
not_evaluated=accounted_routes. Reason counts cocok actual rows;
accepted_accessible=null, bukan0 yang mengesankan final count. Graph kosong
yang valid berbeda dari graph hilang/invalid. Routing subset dapat PASS dengan
overall status PARTIAL karena policy gate belum selesai. Missing input→
BLOCKED, invalid graph/config/provenance→FAILED, keduanya summary=null.
CLI exit3=PARTIAL,2=BLOCKED,1=FAILED; tidak ada full-accessibility PASS profile.

Semua fixture lokal/sintetis. Bukti command,130 tes dan dua CLI run identik
tanpa menghapus field ada di
[execution LI-2](evidence/location_intelligent/li2_20261022/execution.json).
