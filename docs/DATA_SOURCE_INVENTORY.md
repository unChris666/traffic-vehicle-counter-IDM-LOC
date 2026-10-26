<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Location Intelligent — inventaris sumber data

## LI-3 — sumber OSM nyata kini tersedia

OSM source benar-benar diambil melalui Overpass API, bukan hanya metadata.
Server generator melaporkan0.7.62.11; library filter OSMnx2.1.1. Roads170557
elements dan feature/barrier/turn13879elements tersimpan. Successful source
timestamps03:58:06Z/03:59:06Z22 Oktober2026 berbeda satu menit. Pin requests
gagal dan tetap disimpan; tidak ada atomic snapshot claim. Overlapping source
elements diverifikasi sama sebelum merge. Overture packet nyata D34 direuse
setelah hash/re-normalization checks, bukan fresh download. Cache/source
versions tetap jelas. [Review dan artifact](LI_3_REVIEW.md).
Tidak mengambil BigQuery/RWI/POI lain atau menjalankan Traffic.

## D34 — akuisisi sampel nyata sudah dilakukan

Metadata-only di bawah adalah tahap historis sebelum tugas D34. Kini bounded
Overture2026-10-21.0 benar-benar diakses via official AWS GeoParquet dan STAC;
OSM graph/BQ/RWI belum diambil. Lokasi contoh N1 disetujui owner untuk technical
pilot, bukan lokasi TGDI.

[Report aktual](../results/location_intelligent/overture_20261021_n1_verified/report.json):
2623records, tidak truncated,1322selected/1301excluded/0rejected.512item bboxes
diperiksa dan satu partisi intersect bbox. Raw rows/proof tersimpan gzip;
class/subtype/version/sources/WKB dipertahankan. Schema2.0.0 validation terbatas
pada consumed Parquet columns/types dan canonical geometry/selection, bukan
full official JSON Schema conformity. Buildings tetap berasal dari September
sesuai release notes, bukan observasi lapangan baru Oktober. Source env
DuckDB2.0.0 terpisah dari Traffic.

Semua1322selected subtype null; fallback N1 bukan positive residential label.
Standard capacity5288 berunit unresolved; height/num_floors seluruh2623sample
kosong. Lihat capacity report sebelum memakai sebagai fitur bisnis. Tidak ada
real motorcycle accessibility result pada tugas ini.

## Verifikasi dokumentasi publik — 22 Oktober2026

Update ini memeriksa dokumentasi/metadata rilis saja, bukan retrieval data
lokasi, graph atau validasi izin motor. Bagian21 Oktober di bawah adalah
catatan historis; versi N1 tidak diubah otomatis.

| Komponen | Hasil yang benar-benar diperiksa | Implikasi |
|---|---|---|
| OSMnx | [PyPI JSON](https://pypi.org/pypi/osmnx/json) melaporkan2.1.1, file diunggah21 Juli2026 | Kandidat pin library; belum diinstal/diuji untuk LI-3. Bukan versi data OSM |
| Network filters OSMnx2.1.1 | [source resmi](https://github.com/gboeing/osmnx/blob/v2.1.1/osmnx/_overpass.py) | drive mengecualikan service dan alley; drive_service lebih luas tetapi bukan filter motor lengkap. all/all_public masih perlu filtering mode, arah dan larangan |
| Overture dataset | [STAC root](https://stac.overturemaps.org/catalog.json) menunjuk latest2026-10-21.0; [release notes](https://docs.overturemaps.org/blog/2026/10/21/release-notes/) mengonfirmasi schema2.0.0 | Buildings GA; release ini mempromosikan ulang buildings September, OSM cutoff12 September2026. Latest release tidak berarti semua footprint baru. Upgrade dari2026-08-19.0 memerlukan adapter/schema tests |
| OSM core API | [API v0.6](https://wiki.openstreetmap.org/wiki/API_v0.6) | Berbeda dari Overpass yang digunakan untuk query jaringan; bukan API routing/ETA |
| Overpass software | [GitHub latest release](https://github.com/drolbr/Overpass-API/releases/tag/osm3s_v0.7.62.4) melaporkan0.7.62.4,21 November2024 | Bukan bukti versi instance server tertentu; endpoint, query dialect dan as-of response perlu dicatat saat acquisition |

Endpoint dokumentasi `/release/` dan `/release-notes/` Overture mengembalikan404;
diganti dengan sitemap/STAC dan release-note resmi bertanggal di atas. Request
ulang docs OSMnx menerima403; filter dikonfirmasi lewat source tag2.1.1 resmi.
Tidak menginstal package, melakukan query Overpass atau mengunduh dataset.

### Paket data minimum Area Coverage yang direkomendasikan untuk LI-3

Plan terbaru D33, bukan hasil acquisition; source config pada
[file Python](../notebooks/location_intelligent_config.py).

| Data | Atribut minimum/preservasi | Sumber yang direncanakan | Versi/snapshot |
|---|---|---|---|
| Target toko | ID, lon/lat, CRS, sumber koordinat | Input target eksplisit; bukan otomatis lokasi contoh N1/TGDI | Context schema location_intelligent_v1; versi/as-of sumber koordinat aktual belum diketahui |
| Bangunan | ID, footprint, class/subtype, sources/version; height/num_floors jika capacity memerlukannya | Overture buildings, GeoParquet dari storage resmi | Plan2026-10-21.0, schema2.0.0; belum diambil/diuji. N1 tetap2026-08-19.0 |
| Jalan | Node/way IDs, geometry/topology, highway/service/oneway/junction | OSM via Overpass, acquisition OSMnx drive_service | Plan OSMnx2.1.1; data OSM snapshot/as-of dicatat saat retrieval, bukan versi library |
| Izin motor | access/vehicle/motor_vehicle/motorcycle dan directional/conditional jika tersedia | Raw tags OSM, lalu mapping policy motor | Snapshot sama dengan roads; versi mapping belum diimplementasikan |
| Hambatan/manuver | barrier/gate nodes, bridge/tunnel/layer, restriction relations | OSM; relation/node acquisition perlu explicit adapter, tidak dijamin oleh hasil graph sederhana | Timestamp/source IDs sama snapshot; versi server/kemampuan parser belum diverifikasi |
| Provenance | Acquisition time, extent, source version, query/filter, raw/normalized checksums dan missing reason | Response metadata + manifest yang dibuat aplikasi | Canonical manifest location_intelligent_v1; metadata acquisition aktual masih unknown |

Filter drive_service adalah keputusan owner, bukan jaminan lengkap semua
gang motor. Track/path dikeluarkan oleh filter dan motorcar=no juga dapat
membuang ruas motor-legal. Aturan mengizinkan track/path tidak akan bekerja
pada ruas yang tak diambil. Jangan mengklaim full motorcycle coverage.

- **Target input:** ID toko, lon/lat, CRS, sumber koordinat dan policy snapshot.
- **Buildings Overture:** ID, geometry/bbox, class/subtype bila tersedia,
  version/sources dan release/schema. Height/num_floors dibutuhkan jika capacity
  kelak memakai estimasi lantai; unknown tidak diisi otomatis. Floor/capacity
  final masih menunggu D04.
- **OSM roads:** node/way ID, geometri dan konektivitas, highway/service,
  name bila tersedia, oneway/junction serta access/vehicle/motor_vehicle/
  motorcycle dan pembatasan conditional/directional bila tersedia.
- **Akses/topologi:** barrier/gate nodes, bridge/tunnel/layer dan restriction
  relations. Tidak semuanya otomatis menjadi aturan graph OSMnx; adapter harus
  mempertahankan raw tags dan mencatat kemampuan yang belum diimplementasikan.
- **Penghalang:** water/waterway atau fence/wall dapat membantu QA konektor
  jika tersedia; ketiadaan fitur pada peta bukan bukti tidak ada penghalang.
- **Provenance:** extent, timestamp/as-of, request/filter, versi parser/library,
  checksum raw/normalized, coverage, missing/rejected reason dan lisensi.

POI/competitor/BQ, RWI, tiles dan Traffic tidak diperlukan untuk smoke test
core building-to-store routing. Jangan memperluas scope sumber wajib tanpa
requirement. API/library/schema terbaru adalah kandidat, bukan kompatibilitas
LI-3 yang sudah terbukti.

21 Oktober 2026. **DOCUMENTED melalui inspeksi offline**, bukan verifikasi
layanan langsung. Tidak ada query BigQuery, request data, metadata API,
download dataset atau eksekusi notebook pada tugas ini. `UNKNOWN` berarti
bukti belum tersedia; tidak berarti layanan tidak ada atau gagal.

N1 adalah [arsip notebook asli](evidence/location_intelligent/arcov-v2.ipynb.gz),
SHA256 uncompressed `31cda6340111f2a2cf62d3df27b9dba39f90b7ea996d4a10c150d7535c375c5a`.
Cell memakai indeks JSON0-based. Source label **CODE** mengonfirmasi identifier
dan query tertulis, **STORED_OUTPUT** hanya output contoh tersimpan, bukan live
schema/ketersediaan/izin saat ini. L1/L2 pada [register](LOCATION_INTELLIGENT_OVERVIEW.md#register-sumber)
hanya referensi legacy yang pernah ditinjau; tidak diretrieval ulang atau diadopsi.

## Peta fitur → sumber

| ID | Fitur | Sumber yang didukung bukti | Status/batas |
|---|---|---|---|
| SRC01 | Target store identity/coordinates | Input manual `CFG.lat/lon/target_kdtk` N1cell4; kontrak metadata Traffic lokal | CODE; master Home/database target aplikasi **UNKNOWN**, Home belum implemented |
| SRC02 | Indomaret/nearest/similar stores + historical performance | BigQuery `locdeproject.DWH_NS_LOC.AREA_COVERAGE`, N1cell14 | CODE query/required columns; live table schema dan brand semantics belum direvalidasi |
| SRC03 | Competitor stores | BigQuery `locdeproject.DWH_NS_LOC.COMPETITOR`, N1cell16 | CODE; `LAT`/`LONG`, bukan `KOORDINAT` seperti store source |
| SRC04 | Building footprints | Overture S3 Parquet buildings, release2026-08-19.0, N1cell10 | CODE/STORED_OUTPUT; bukan BigQuery atau GEE pada reference N1 |
| SRC05 | Directed roads/routes/accessibility/travel time | OSM via OSMnx `graph_from_point`, N1cell10 | CODE/STORED_OUTPUT; route/time adalah derived output, bukan live ETA API |
| SRC06 | Isochrones | Tidak ditemukan retrieval/result isochrone polygon pada N1/R1 | **UNKNOWN** untuk current integration; accessible buildings bukan isochrone polygon |
| SRC07 | RWI/demografi | Tidak ditemukan identifier/query/file RWI pada N1 atau source lokal yang ditelusuri | **UNKNOWN** provider, table/API, asset, fields, unit, vintage dan join |
| SRC08 | POI/brand layers | Overture S3 Parquet places, N1cell12 | CODE/STORED_OUTPUT; BigQuery competitor dan Overture competitor adalah dua sumber berbeda |
| SRC09 | Basemap/satellite/live traffic tiles | Esri tile templates; traffic URL kosong, N1cell18 | CODE; live traffic provider tidak dikonfigurasi dan bukan Traffic Counter |
| SRC10 | Traffic videos | Kaggle datasets dan uploaded source identity; inventory/manifest lokal | Prior retained evidence; tidak diakses ulang via API pada tugas ini |
| SRC11 | Traffic machine/reviewed output | Immutable local `results/`, gzip records, per-run manifests | STORED_ARTIFACT; bukan table BigQuery atau feature PPAC otomatis |
| SRC12 | Area results/Recount | N1 output contoh; export code; rencana snapshot/polygon kontrak lokal | Full spatial snapshot/export belum diverifikasi tersedia; Recount belum implemented |
| SRC13 | PPAC features/Excel baseline | Rancangan feature adapters; workbook dan approved formula belum tersedia | **UNKNOWN** physical sources/baseline file/formula; tidak diasumsikan BigQuery |

## SRC01 — target/context

N1 memakai contoh lat `-6.430669461543375`, lon `106.8101931806858`,
`target_kdtk=None`. Ini bukan lokasi default aplikasi atau bukti lokasi toko
TGDI. [Review metadata TGDI](evidence/phase_8/feedback/TGDI_unknown_location_metadata_review_v1.json)
secara eksplisit mempertahankan store_name/latitude/longitude sebagai unknown.
Belum ada UI Home yang membaca master toko dan mengikat delapan video ke
target geografis yang terverifikasi. Kunci join target→KDTK perlu mapping
eksplisit; nama/prefix video saja tidak membuktikan physical store/location.

## SRC02 — BigQuery stores/performance

**CODE:** project `locdeproject`, dataset `DWH_NS_LOC`, object `AREA_COVERAGE`.
Nama yang dipanggil adalah fully-qualified SQL identifier
`locdeproject.DWH_NS_LOC.AREA_COVERAGE`; apakah object berupa table/view,
physical types/nullability, location, partition/clustering, owners/permissions,
freshness/update schedule dan row count saat ini adalah **UNKNOWN**.

Kolom SELECT/`STORE_REQUIRED` N1cell14:

```text
KDTK, NAMA_TOKO, TGL_GO, KOORDINAT,
Jenis_bangunan, TIPE_TOKO_CALC, TIPE_TOKO,
L_tanah, L_bangunan, Lebar_toko, DOMAIN,
RAB, PERIODE, SPD, PNL, EBIT, EBITDA
```

SQL filter aktual: `KDTK IS NOT NULL AND KOORDINAT IS NOT NULL`.
Tidak ada SQL time/partition/spatial bound pada query store tersebut; jangan
menyebutnya bounded query. Sesudah download, parser menerima shapely Point
atau teks `POINT(lon lat)` menjadi LAT/LON; malformed dibuang, lalu Indonesia
LAT[-11,6]/LON[95,141] difilter lokal. Ini bukan bukti type BigQuery GEOGRAPHY.
Target KDTK opsional dikecualikan lokal. Identitas store didedup KDTK setelah
sort TGL_GO ascending, keep first; bukan otomatis record terbaru.

Nearest/similar store features berasal dari kolom karakteristik tersebut.
Periode performance dipertahankan dan di-inner-join route metrics pada
`KDTK_STR`; detail diurutkan road-distance lalu PERIODE sebagai string.
Uniqueness key untuk performance belum dibuktikan cukup `(KDTK,PERIODE)`;
grain/dedup/sort period masih perlu konfirmasi. Luas/lebar numeric di-coerce;
SPD/PNL/EBIT/EBITDA dan period di-cast string. Itu transform Pandas, **bukan
physical schema atau konfirmasi unit**. Unit SPD table ini **UNKNOWN**;
jangan menyamakannya dengan target PPAC struk/hari hanya karena namanya sama.

Auth tertulis: `google.cloud.bigquery.Client(project=CFG['project_id'])`
dengan default credential resolution. Active identity/roles/ADC source dan
akses BigQuery Storage saat ini **UNKNOWN**. Konstruksi client tidak menguji
izin query. Library BigQuery Storage terpasang bukan bukti accelerated read
benar-benar dipakai. Quota, pricing, billing limits dan estimated bytes
**UNKNOWN**; tidak dilakukan dry run pada tugas ini.

## SRC03 — BigQuery competitor

**CODE:** `locdeproject.DWH_NS_LOC.COMPETITOR`. N1cell16 memakai `SELECT *`
dengan `SAFE_CAST(LAT AS FLOAT64)` dan `SAFE_CAST(LONG AS FLOAT64)` non-null
serta BETWEEN bbox target. Bbox dihitung dari
`candidate_box_km=max(10.0,network_radius_m/1000*1.25)`; default config memberi
10km parameter bbox. Ini prefilter, bukan circle radius10km atau partition
filter. Availability/index/partition/cost/live schema tetap **UNKNOWN**.

Normalizer mengubah `LONG`→canonical `longitude`/LON dan LAT→latitude.
Preferred display columns `KDTK,NAMA_TOKO,LAT,LON` terdapat pada output contoh;
source code hanya mengharuskan koordinat untuk query. `KDTK` competitor
uniqueness, field brand/category, join ke store master dan freshness adalah
**UNKNOWN**. Tidak boleh menyamakan ID competitor dan Indomaret sebagai satu
namespace atau union tanpa source tag.

Haversine shortlist kemudian directed routing; no-path/error disimpan sebagian
dalam routed dataframe. Current cell16 bergantung pada global `client` yang
dibuat cell14; adapter baru harus independen dari sukses modul similar-store.
Auth mengikuti SRC02; quota/pricing/provider permissions belum diverifikasi.

## SRC04/SRC08 — Overture object storage

Source URI aktual:

```text
s3://overturemaps-us-west-2/release/2026-08-19.0/theme=buildings/type=building/*
s3://overturemaps-us-west-2/release/2026-08-19.0/theme=places/type=place/*
```

DuckDB `read_parquet(...,hive_partitioning=1)` dengan httpfs/spatial,
`s3_region='us-west-2'`. Bukan BigQuery, Google Open Buildings atau JSON REST
endpoint yang boleh diganti diam-diam. Tidak ada explicit credential values
di adapter N1; access mode/runtime authorization sekarang **UNKNOWN**.
Release identifier terbukti tertulis; service freshness, availability, complete
coverage, usage/transfer pricing dan throttling **UNKNOWN**, bukan gratis
atau unlimited yang dianggap terjamin.

Buildings SELECT: `id,class,subtype,num_floors,height,ST_AsWKB(geometry) AS geom`.
Places SELECT: `id,names.primary,brand.names.primary,basic_category,
taxonomy.primary,taxonomy.hierarchy,taxonomy.alternates,confidence,
operating_status,ST_AsWKB(geometry) AS geom`. Keduanya memakai bbox.xmin/xmax/
ymin/ymax overlap SQL dan exact projected representative-point radius lokal.
Typed nesting/schema tersebut adalah **query expectation**, bukan live-schema
verification. Building PK usulan source+release+id; POI PK source+release+id.

Class/area/capacity rules hanya pada [SPEC](AREA_COVERAGE_SPEC.md). POI brand
Indomaret→clone dan Alfamart→competitor berasal dari classifier kode, bukan
validated store master join. Confidence/operating_status dibaca tetapi tidak
menjadi filter wajib pada source code. Clinic dapat diklasifikasi tetapi
tidak termasuk seluruh requested map-layer set. Provider taxonomy, join brand,
confidence policy dan dedup lintas SRC03/SRC08 perlu keputusan terpisah.

## SRC05/SRC06 — network dan hasil turunan

Operasi N1: `ox.graph_from_point((LAT,LON),dist=5500,dist_type='bbox',
network_type='drive',simplify=True,retain_all=True,truncate_by_edge=True)`.
Data berasal OSM melalui OSMnx. Endpoint/server URL, Overpass credentials,
retry/cache defaults dan quota tidak diset eksplisit pada notebook, sehingga
**UNKNOWN** untuk konfigurasi aplikasi; jangan mengarang endpoint tertentu.
Tidak ada API directions/travel-time vendor pada N1.

Fields yang dikonsumsi: node x/y/ID, directed edge `(u,v,key)`, geometry,
length, highway, service, name, oneway, bridge, tunnel, junction. Actual source
completeness, OSM snapshot/as-of dan update schedule **UNKNOWN**. Derived
time memakai constant7km/h; reverse-Dijkstra dan road selection lokal.
Isochrone polygon tidak dihasilkan N1. Membentuknya nanti adalah kalkulasi
baru dengan mode/topology/coverage contract, bukan source lookup tersendiri
yang sudah tersedia. Legacy demo tidak menjadi bukti current engine.

## SRC07 — RWI/demografi

Tidak ditemukan mapping di source lokal/notebook. Provider, project/dataset/
table/view, API URL, asset/file path, ID, units, CRS/grid resolution, timestamp/
vintage, geo-join key, population coverage, auth, quota dan pricing semuanya
**UNKNOWN**. Jangan mengisi dengan asumsi Facebook/Meta, GEE atau BigQuery.
Sebelum integrasi, perlu sumber resmi+schema/sample berizin serta definisi
agregasi per target/polygon dan treatment missing/out-of-coverage.

## SRC09 — display tiles

N1cell18 menetapkan:

```text
https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}
https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}
```

Rendering tile dilakukan browser saat map dibuka, bukan input kalkulasi area/
travel time. Source-code request tidak menambahkan token; current access,
provider terms/limits, coverage/freshness, billing/pricing adalah **UNKNOWN**.
`traffic_tile_url=''` dan placeholder bukan feed traffic langsung. Provider/
endpoint/auth/response/price feed traffic masih **UNKNOWN**. Offline map dapat
menampilkan geometri tanpa live basemap, dengan label mode yang jelas.

## SRC10/SRC11 — video dan output Traffic Counter

Dataset IDs dari evidence yang tersedia:

- `chrisbiran/traffic-tracker-videos`: prototype TOR3; actual source identity
  mengikuti report masing-masing, bukan substitusi ke store lain.
- `chrisbiran/tgdi-traffic-videos`: delapan TGDI slots dengan
  [source hashes dan metadata review](evidence/phase_8/feedback/TGDI_unknown_location_metadata_review_v1.json).
- `chrisbiran/video-traffic-malam`: dataset malam resmi,10 files pada
  [inventory Kaggle tersimpan](../results/nighttime_validation/kaggle_execution/nighttime_input_inspection/inventory.json).

Mount `/kaggle/input/...` pada inventory adalah bukti eksekusi terdahulu,
bukan mount yang diasumsikan ada di Codex sekarang. CLI/Kaggle access memakai
runtime credential binding; nilai credential tidak didokumentasikan. Current
API availability, quotas, GPU allowance dan biaya **UNKNOWN** karena tidak
diperiksa langsung pada tugas ini. Uploaded videos di luar repo juga memerlukan
hash/metadata source; upload storage aplikasi belum implemented.

Authoritative selected pilot: [B v8 selected_run](../results/b_v8/selected_run.json),
policy/overlay `v5`, `pilot_p1_reviewed_v3`, branch `review_assisted`.
Machine B v7 di `results/b_v7/execution/pilot_v7_machine_final/weekday_siang/`;
B v8 di `results/b_v8/execution/pilot_p1_reviewed_v3/weekday_siang/`.
Count/track records adalah local gzip snapshots; annotated videos/link manifests
mengikuti masing-masing run. Tidak ada sink BigQuery yang terbukti di engine.

Filter user yang terikat TKVQ-WEEKEND-MALAM memakai source SHA
`82b8973c280440a77515a9be1381c503829d25561adcd2c358d4f3a5fb40efee`;
config file SHA `f317031635efdefa4cb67b12b5beddd243cb178119a61673a6c67a0f97f7dd13`.
Setting gamma0.65/exposure0.2/sharpness0.35/brightness0/shadows0 tidak diubah;
ini kandidat preview, belum validated nighttime counting.

## SRC12/SRC13 — geospatial hasil dan fitur bisnis

N1 menyimpan output contoh1321 eligible/1304 accessible/legacy sum5216 pada
notebook. Itu **bukan frozen dataset1321 footprint lengkap** yang siap dibaca.
Export CSV/GeoJSON/map/result.json hanya didefinisikan cell20 yang tidak punya
executed output. Belum ada Recount polygon/membership/result yang verified;
polygon video adalah domain berbeda. Lokasi output pada kontrak adalah rencana,
bukan file source yang diasumsikan tersedia.

Update22 Oktober2026: LI-1 mendukung canonical local GeoJSON
`li_building_snapshot_v1` dengan field BuildingRecord dan SourceRef CRS/units
eksplisit. [Fixture](../notebooks/fixtures/li1/manifest.json) dan
[hasil seleksi](evidence/location_intelligent/li01_20261022/li1_fixture_result.json)
berlabel SYNTHETIC, bukan retrieval Overture atau frozen dataset1321 N1.
Reader tidak membuka Parquet/CSV/WKB dan tidak melakukan source normalization
live. Full real source snapshot tetap belum tersedia/tervalidasi.

PPAC feature views/tables belum terbukti ada. Kolom historis SPD pada SRC02
tidak menggantikan Excel business baseline. Workbook/path/sheet/range/hash,
formula, constants, period grain, target identity, approval dan units baseline
**UNKNOWN**. Tidak membuat mapping table PPAC/RWI berdasarkan nama fitur saja.

## Pemeriksaan langsung yang ditunda

Jika kelak diberi tugas terpisah: cek metadata-only schema/object type,
partition/location dan permission BQ; desain bounded query dan estimate bytes
sebelum eksekusi; cek minimal object/schema Overture serta snapshot graph OSM;
konfirmasi RWI/Excel sumbernya dahulu; verifikasi provider-specific quotas,
pricing dan freshness. **Tidak satu pun pemeriksaan live ini dilakukan sekarang.**
Kode source adapter adalah prerequisite akuisisi data nyata, bukan adapter
downstream feature PPAC. Dependensi dan gate ada pada
[IMPLEMENTATION_ROADMAP](IMPLEMENTATION_ROADMAP.md).
