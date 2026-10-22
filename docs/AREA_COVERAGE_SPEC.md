# Area Coverage — spesifikasi referensi dan gap

Status **DOCUMENTED**, belum engine aplikasi. Sumber [N1 dan definisi label](LOCATION_INTELLIGENT_OVERVIEW.md#register-sumber).
`NOTEBOOK_CODE` berarti terbaca pada source, `NOTEBOOK_OUTPUT` berarti output
tersimpan, bukan eksekusi/verifikasi ilmiah baru. Perilaku usulan tidak mengganti N1.

## Konfigurasi aktif N1

Cell4 `CFG` adalah sumber nilai aktif, bukan angka pada docstring.

| Kelompok | Nilai kode |
|---|---|
| Contoh target | lat `-6.430669461543375`, lon `106.8101931806858`, `target_kdtk=None`; bukan default lokasi aplikasi |
| Bangunan | `building_radius_m=400.0`, `min_area_m2=45.0`, `max_area_m2=550.0` |
| Special classes | apartment=`apartments`; dormitory=`dormitory`; hotel=`hotel` |
| Standard | `standard_residential_household=4`, occupancy=`1.00` |
| Apartment | net ratio=`0.70`, average unit=`45m²`, occupancy=`0.70` |
| Dormitory | net ratio=`0.70`, average room=`15m²`, occupancy=`0.75` |
| Hotel | net ratio=`0.65`, average room=`30m²`, occupancy=`0.45`, guests/occupied room=`2.0` |
| Floor fallback | `estimate_level_from_height=True`, floor height=`3.0m` |
| Access | `max_building_to_road_m=125.0`, `max_travel_min=10.0`, constant speed=`7.0km/h` |
| Graph | `network_radius_m=5500.0`, `network_type="drive"`; dist_type=`bbox`, simplify/retain_all/truncate_by_edge=`True` pada cell10 |
| Overture | release=`2026-08-19.0`; S3 `overturemaps-us-west-2/release/<release>/theme=buildings/type=building/*` |
| Optional BigQuery | project=`locdeproject`, dataset=`DWH_NS_LOC`, tables=`AREA_COVERAGE`, `COMPETITOR`; hanya untuk modul store/competitor, bukan sumber footprint |
| Map/output | zoom=`16`; `traffic_tile_url=""`; output root=`/kaggle/working/location_analysis`; UTC second-resolution `RUN_ID` |

Angka ini asumsi/kontrol reference notebook, **bukan approval bisnis atau
threshold produksi**. Docstring cell10 menyebut100m dan7menit, sementara call
site menggunakan125m dan10menit. Accessibility memakai **`time < 10`**, bukan≤10.
Jangan menyatukan access threshold dan kecepatan7km/h sebagai angka yang sama.

Cell4 juga mengatur modul di luar inti Area Coverage: `top_n_stores=5`,
`top_n_similar=5`, `nearest_candidate_n=100`, `similar_candidate_n=150`,
`similarity_min_score=0.40`; weights Jenis_bangunan0.15,
TIPE_TOKO_CALC0.15, TIPE_TOKO0.10, L_tanah0.15, L_bangunan0.15,
Lebar_toko0.15, DOMAIN0.15; tolerances25m²/10m²/3m. Target contoh
Ruko/Ruang Usaha, REG, STANDARD,135m² tanah,135m² bangunan,9m lebar,
RESIDENTIAL. `traffic_tile_attr="Traffic data provider"`; map_style competitor
red, clone blue, hospital green, police_station gray, bank darkblue, market
orange, park black. Nilai ini tidak otomatis menjadi rule PPAC.

## Input → proses → output aktual

### 1. Setup, target dan CRS — cell2/4/6/8

Cell2 memasang dependency dengan rentang versi, lalu import DuckDB/spatial,
PyArrow, GeoPandas, Shapely, PyProj, OSMnx, NetworkX, Folium, BigQuery,
Pandas/NumPy. Output menyebut OSMnx2.1.1, Pandas2.3.3, GeoPandas1.1.3 dan
warning konflik dependency. Ini bukan environment lock yang sudah tervalidasi.

Cell6 membuat Point(lon,lat), menghitung zona UTM `int((lon+180)//6)+1`,
EPSG326xx utara/327xx selatan, transformer `always_xy=True`. Contoh memakai
EPSG:32748. Buffer400m dibuat dalam CRS meter, diubah ke WGS84 untuk bbox.
Cell8 baru memeriksa range koordinat/positivitas controls dan tujuh ciri toko.
**Gap:** proyeksi terjadi sebelum validasi; polar/longitude180 dan finite input
perlu gate eksplisit. Ciri toko untuk similarity seharusnya tidak memblokir
engine Area Coverage yang hanya memerlukan target/config yang relevan.

### 2. Footprints dan kelayakan bangunan — cell10 `get_buildings`

DuckDB membaca Overture Parquet dengan bbox overlap di WGS84. WKB dibuka;
null/empty dan exception geometri dilewati. Tidak ada `is_valid`/repair/type
gate eksplisit atau reject ledger; jangan menyebut seluruh geometri valid
secara topologi. Representative point dihitung, bukan centroid. Distance
adalah target ke representative point dalam UTM; inclusion **≤400m**.
Area adalah seluruh footprint terproyeksi, bukan footprint yang dipotong lingkaran.

Klasifikasi prioritas: class apartments→apartment, dormitory→dormitory,
hotel→hotel; selain itu subtype kosong/residential→standard_residential.
Fallback ini dapat menerima class lain dengan subtype kosong: perlu keputusan
taxonomy, bukan asumsi semua footprint pasti rumah.

Semua tipe memerlukan area **>45m²**; standard juga **<550m²**, special tidak
punya batas atas550m². Tidak ada dedup building_id eksplisit. Data `building_valid`
adalah hasil seleksi tersebut, bukan seluruh footprint di dalam bbox/radius.

### 3. Floor dan kapasitas — cell6 lalu definisi ulang identik pada cell10

`num_floors` positif dibulatkan Python `round`, minimum1; jika hilang/invalid,
height positif dibagi3m dan dibulatkan jika estimation diaktifkan.
`level_source` membedakan sumber Overture dan estimasi height; jika keduanya
tidak diketahui, level dan GFA tetap null. GFA=footprint×level jika tersedia.

| Tipe | Rumus kode dan arti field legacy |
|---|---|
| Standard | `household=4` per footprint; estimated_units=1 dan occupied_units=1. Occupancy config dicatat tetapi tidak mengalikan nilai4. Makna4 orang/KK tidak didefinisikan secara sah. |
| Apartment | occupied_units=`GFA×0.70/45×0.70`; household=`int(round(occupied_units))`. Unknown GFA→household null. |
| Dormitory | occupied_rooms=`GFA×0.70/15×0.75`; household=`int(round(occupied_rooms))`, ditandai household-equivalent from occupied rooms. |
| Hotel | occupied_rooms=`GFA×0.65/30×0.45`; guests=`int(round(occupied_rooms×2))`; household selalu null. |

`household` mencampur konstanta, unit hunian dan kamar; totalnya **bukan
household atau penduduk yang tervalidasi**. Cell10 aggregate mengubah
unknown/non-numeric menjadi0 sebelum sum. Ini menyembunyikan kapasitas yang
belum diketahui. Simpan hasil legacy untuk parity; jangan mempromosikannya ke
PPAC sebelum [keputusan unit](AREA_COVERAGE_DECISIONS.md) ditutup.

### 4. Directed graph dan jalan akses — cell10

OSMnx mengambil directed drive graph dalam bbox radius5500m, lalu project ke
UTM. Setiap edge diberi `travel_time_s=length/(7km/h)`. Ini model kecepatan
konstan, bukan traffic langsung atau bukti semua edge legal untuk sepeda motor.

Road taxonomy: service/driveway/alley/parking_aisle dan path-like→gang;
residential/unclassified/living_street/road→street; secondary/tertiary dan
links→main street; primary/trunk/motorway dan links→highway; lainnya unknown.
**Candidate akses** hanya street/main street/highway. Graph routing tidak
disaring ulang dengan filter candidate tersebut; gang/service di graph dapat
berada pada rute lanjutan. Layer jaringan400m adalah audit/visual, bukan
jaringan routing yang dipotong400m.

Untuk setiap representative point, spatial index mencari **semua** eligible
directed edges pada jarak≤125m, bukan satu nearest edge. Access point adalah
proyeksi pada edge; offset building→road berupa jarak lurus. Tidak ada gate
fence/river/entrance yang membuktikan connector bisa dilewati.

### 5. Reachability, pemilihan dan waktu — cell10

Store disnap ke nearest graph node. Dijkstra dari store pada graph reversed
menghasilkan biaya node→store dalam graph asli; tidak membuat reverse edge
atau U-turn baru. Dari access point pada directed edge u→v, hanya bagian ke v
yang dipakai; v harus mempunyai directed path ke store node.

`total_distance = straight building-road offset + partial edge to v +
network v-to-store-node`. Waktu=`total_distance / constant_speed /60`.
Biaya connector terakhir store-node→koordinat toko tidak ditambahkan.
Orientasi geometri edge dan snap offset perlu diuji, bukan diasumsikan benar.

Di antara candidate reachable, pilih urutan `(distance_m,total_time_min,u,v,key)`;
**nearest reachable access**, bukan minimum total travel time. Nilai candidate
distance dibulatkan2desimal dan total time3desimal; nilai time yang telah
dibulatkan digunakan untuk `< max_travel_min`. Boundary dekat10menit dapat
terpengaruh pembulatan. `selected_candidate_rank` saat ini selalu1 setelah
daftar reachable disortir; bukan ranking pada seluruh candidate awal.

Tidak ada candidate / tidak ada reachable path menghasilkan alasan tersendiri.
Rute dibuat juga jika reachable tetapi waktu≥10menit: `route_generated`
tidak sama dengan `accessible`. Kegagalan rekonstruksi belakangan dapat
mengubah reason sementara flag accessible sudah ditulis; perlu konsistensi
state/route audit. Internal evaluated candidate tidak diekspor lengkap.

### 6. Agregasi, modul opsional, map dan persistence

Cell10 membentuk `building_accessible`, jumlah eligible/accessibles, rate,
legacy capacity sum, jumlah route/node/edge. Exception Area Coverage→FAILED
dan raise. POI cell12 independen menggunakan Overture Places/radius400m;
failure ditandai PARTIAL tetapi juga membuat table/count0—konsumen harus
membaca status, bukan memperlakukan0 sebagai tidak ada POI.

Cell14/16 menambahkan nearest/similar store dan competitor dari BigQuery.
Tabel mengandung SPD/PERIODE sebagai data historis, bukan formula prediksi SPD.
Snapping kandidat jauh ke graph terbatas dapat menghasilkan distance tak
sebanding dengan Haversine; pisahkan QA ini dari inti Area Coverage.

Cell18 mendefinisikan Folium: terrain, satellite QA, footprints, valid dan
accessible buildings, directed roads, target, POI, nearest/similar,
building→store routes. Traffic tiles kosong hanya placeholder berlabel,
bukan live traffic atau hasil Traffic Counter. Tidak ada Recount drawing.

Cell20 mendefinisikan export: `area_coverage/{valid_buildings,
accessible_buildings}.{csv,geojson}`, routes.geojson, road_network_400m.geojson;
POI CSV/GeoJSON; nearest/similar/details/routing CSV; competitor CSV; map HTML;
`result.json` dengan target, summary, rules, sources, module statuses/diagnostics.
Empty layers dapat tidak ditulis; CSV capacity_model masih repr dict, bukan
kontrak nested JSON. `result.json` ditulis sebelum status EXPORT=SUCCESS;
kelengkapan artifacts dan status final belum dijamin. Cell20 tidak mempunyai
output tersimpan: **file export tersebut baru terbukti didefinisikan kode**.

Output contoh cell10:1321 eligible,1304 accessible, legacy sum5216,
1321 routes,32186 nodes,77031 edges,77023 eligible directed edges. Ini satu
contoh run, bukan expected result semua lokasi atau validasi angka rumah tangga.

## Requirement aplikasi yang diusulkan

Tampilkan target/context/source timestamp, observed building count dan
capacity terpisah, unknown/rejected rows, alasan akses dan batas coverage.
Map, tabel, diagnostics dan downloads harus merujuk snapshot/run yang sama.
Recount diberi halaman sendiri dengan universe/predicate/coverage yang jelas;
business rule-nya masih [OPEN](AREA_COVERAGE_DECISIONS.md).

Tidak ada hasil retrieval/routing baru dalam tugas dokumentasi ini.
