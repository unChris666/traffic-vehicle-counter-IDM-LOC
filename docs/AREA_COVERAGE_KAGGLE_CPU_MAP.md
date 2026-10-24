# Area Coverage — notebook CPU800m dan layer toko/kompetitor2km

24 Oktober2026, Asia/Jakarta. **Implementasi prototype notebook yang diminta
owner; bukan pelaksanaan penuh audit modularisasi42file.** Core Area dan
baseline N1 lama tidak diubah. Koordinat serta radius baru merupakan analisis
baru, bukan penggantian label snapshot N1.

Notebook: [Kaggle CPU](https://www.kaggle.com/code/chrisbiran/area-coverage-800m-poi-2km-cpu)
→ [source di repo](../notebooks/area_coverage_cpu_800m_poi_2km.ipynb).
47cell,14source Python ditulis penuh melalui cell `%%writefile`, lalu diimpor
secara eksplisit dari folder source terlihat. Tidak ada base64/remote code
bootstrap atau implementasi diunduh dari Git. Dataset memuat data/provenance;
`engine_source` di data archive tidak digunakan sebagai runtime implementation.

## Update layer dan secret — 24 Oktober2026

**Label aktif terbaru: `LocatioIntelligent`**, persis ejaan owner. Source notebook
dan default helper diselaraskan ke label ini; PROJECT_PPAC di bawah adalah
riwayat versi4/5.22tes lokal lulus setelah perubahan label. Source disimpan ke
Kaggle melalui QUICK_SAVE, bukan klaim eksekusi/auth baru. Auth live label baru
belum terverifikasi. Jalankan [probe autentikasi](../notebooks/area_coverage_auth_check.py)
di session editor Kaggle yang mengaktifkan secret tersebut; probe membedakan
retrieval secret, format/identitas service account, metadata dan izin query.
Email yang diharapkan `locationinteligent@locdeproject.iam.gserviceaccount.com`.
Path `/kaggle/input/gcp-sa-key/nama-file-key-lu.json` hanya placeholder, bukan
file yang sudah ditemukan. Pengambilan secret tidak otomatis mengisi ADC;
client harus diberi Credentials.from_service_account_info secara eksplisit.

User mengonfirmasi secret Kaggle bernama **PROJECT_PPAC**. Default notebook dan
helper kini membaca label tersebut melalui `UserSecretsClient().get_secret()`;
value hanya dipakai di memory sebagai JSON service account, tidak dicetak.
Nama lama `GCP_SERVICE_ACCOUNT_JSON` pada baseline versi3 bukan default aktif.

Building counter menunjukkan jumlah **lolos seleksi800m**, termasuk filter area
dan subtype N1 yang dipertahankan; bukan seluruh9151source records. Layer toko
Indomaret/kompetitor tetap diseleksi≤2000m dari target pengguna. Setiap lokasi
marker toko memiliki lingkaran400m dalam layer tersendiri yang dapat di-toggle.
Lingkaran tetap utuh meskipun melewati lingkaran2km target; ia hanyalah radius
visual, tidak mengubah routing, eligibility bangunan atau kapasitas.

POI fasilitas menggunakan snapshot OpenStreetMap/Overpass terpisah dari BigQuery.
Delapan layer: rumah sakit, klinik, pasar, kantor polisi, sekolah, kantor
pemerintahan, kantor dan universitas. Rules/tag/query dan raw response ada pada
source helper terlihat dan [binding POI](../results/area_coverage_map/poi_binding.json).
Contoh: amenity=hospital/healthcare=hospital; klinik=clinic; pasar=marketplace;
polisi=police; sekolah=school; universitas=university; pemerintahan memakai
`office=government` atau `amenity=townhall`; kantor lain=office bertag non-vacant.
Satu feature memperoleh satu kategori dengan prioritas eksplisit. Building tag
saja tidak dipakai untuk mengarang fasilitas aktif.

Akuisisi aktual source-as-of **24 Oktober2026 pukul15:34:21 WIB** menghasilkan
73source features;71representative points masuk≤2000m: rumah sakit8, klinik13,
pasar1, polisi2, sekolah17, pemerintahan19, kantor10, universitas1. Dua feature
di luar radius akhir dikeluarkan. Ini fitur OSM, bukan inventori fasilitas fisik
lengkap atau deduplikasi seluruh node/way/relation yang mungkin mewakili site
sama. Center way/relation bukan entrance. Data tidak lengkap tidak boleh
ditafsirkan sebagai tidak adanya fasilitas.

Dataset sumber versi3 menambahkan `osm_poi_snapshot.data`43KB ber-checksum;
bytes archive bangunan/jalan lama tetap sama. `POI_MODE=FROZEN` normal tidak
melakukan re-fetch. Ganti target/radius/rules memerlukan snapshot/revision baru.
`store_buffer_radius_m=400` adalah config tampilan yang dapat diedit.

**21tes offline lulus**:13boundary tests lama+8tes POI/secret/radius toko.
Tes400m memakai fixture sintetis terpisah dan memeriksa satu lingkaran per lokasi
toko serta group toggle terpisah; bukan hasil eksperimen toko aktual. Preview
browser sumber publik nyata menampilkan71POI dan15layer toggle tanpa error JS
atau resource. [Bukti sumber publik dan tests](../results/area_coverage_map/verification/poi_v1/).

**Kaggle versi4: COMPLETE**, CPU saja, full source9151rows dihitung ulang,
selected3597 dan accepted skenario1048. Manifest kalkulasi identik dengan versi3
(`d9535d8a4297230e1a9ed88d535e60df4948baa0772096b825d75aaf75ba1577`), sehingga
penambahan layer tidak mengubah hasil domain. POI71berhasil diambil dari snapshot
terlampir dan diekspor sebagai CSV/GeoJSON. Browser pada HTML hasil Kaggle aktual
lulus dengan15toggle dan0JS/resource errors.

**Blocker aktual:** dua layer toko `BLOCKED`, jumlah null. Read `PROJECT_PPAC`
menghasilkan `ConnectionError` di runtime Kaggle sebelum credentials/query
BigQuery tersedia. Ini belum membuktikan key salah, role IAM salah, atau tidak
ada toko. Sumber resmi KaggleWebClient membungkus URLError/HTTPError sebagai
ConnectionError, sehingga kelas error ini saja tidak cukup menentukan sebab.
Owner perlu memeriksa akses secret pada notebook CPU yang sama; nilai key tidak
diminta. Radius400m sudah lulus test positif fixture, tetapi belum memiliki
marker toko aktual sampai query BigQuery berhasil. Map status
`PARTIAL_MAP_INPUTS_UNAVAILABLE`; jangan mengklaim peta seluruh layer lengkap.
[Bukti run versi4](../results/area_coverage_map/verification/kaggle_v4/retention.json).

### Retry setelah aktivasi secret — Kaggle versi5

Owner mengonfirmasi baru mengaktifkan `PROJECT_PPAC` pada notebook CPU. Versi5
dijalankan ulang setelah konfirmasi tersebut: **CPU COMPLETE**, bangunan3597,
POI71 dan manifest kalkulasi tetap sama dengan versi3/4. Namun, kedua sumber BQ
masih BLOCKED/null. Diagnostik aman kini mempertahankan chain
`ConnectionError → HTTPError400` pada tahap `KAGGLE_SECRET_READ`. Tidak ada
query/table metadata BigQuery yang berhasil; izin IAM dan isi key belum bisa
dinilai dari error ini. Aktivasi menurut owner tidak disamakan dengan sukses
pembacaan secret pada background run API.

Penambahan diagnostik hanya menyimpan class error dan kode HTTP; tidak mencetak
message/body/URL/header atau nilai secret.22tes lokal lulus, termasuk fixture
HTTP403 yang menguji chain tetap terbaca dan string rahasia tidak bocor.403pada
fixture bukan hasil run aktual; error aktual versi5 adalah **400**.

Langkah berikutnya untuk mengisolasi konteks eksekusi: buka editor notebook yang
sama, **Restart Session → Run All** melalui UI Kaggle dengan secret tetap aktif.
Ini uji melalui session owner, bukan bukti pasti bahwa run UI akan berhasil.
Peta bangunan/POI dan layer radius400m tetap bisa diperiksa pada output versi5;
lingkaran toko aktual belum ada karena query belum berjalan. Jangan mengulang
full CPU lewat API lagi hanya untuk mencoba secret yang sama tanpa perubahan
atau bukti tambahan. [Bukti versi5](../results/area_coverage_map/verification/kaggle_v5/retention.json).

## Konfigurasi dan sumber

| Komponen | Konfigurasi aktual |
|---|---|
| Target | latitude-6.409737552410453, longitude106.82835008971841 |
| Seleksi bangunan | radius800m pada EPSG:32748; min area45m² strict>; max standard550m² strict<; rules N1 dipertahankan |
| Footprint | Overture release2026-10-21.0/schema2.0.0, official STAC+Parquet; bukan tabel BigQuery |
| Jalan/access | OSM/Overpass, OSMnx2.1.1 drive_service+positive motor supplements; directed graph/barriers/turns asli |
| Graph acquisition | Bbox radius5500m kontrol eksperimen lama; network hanya ditampilkan dalam2km |
| Marker toko | `locdeproject.DWH_NS_LOC.AREA_COVERAGE`, jarak≤2000m |
| Marker kompetitor | `locdeproject.DWH_NS_LOC.COMPETITOR`, jarak≤2000m |
| Jarak POI | Parameter SQL, ST_DISTANCE WGS84 spheroid TRUE; bbox2100m hanya prefilter; final2000m tidak dinaikkan |
| Model akses | Motor-only,7km/jam seluruh segmen, highest valid/reachable road class, round(total_minutes)≤10 |
| Runtime | CPU saja; metadata enable_gpu=false/enable_tpu=false dan CUDA_VISIBLE_DEVICES=-1 |

Pengambilan footprint memakai bbox radius850m untuk menghindari kehilangan
kandidat di batas seleksi; **850m bukan radius kelayakan**. Seluruh512STAC item
bounds berasal dari inventory rilis yang sudah diverifikasi, hash inventory dan
catalog diperiksa, partisi terpilih dicek lagi ke metadata rilis. Raw footprint
lokasi baru benar-benar dibaca dari Parquet, bukan reuse footprint N1.
Max50000rows adalah fail-closed bound; data tidak dipotong agar terlihat lengkap.

## Hasil eksekusi nyata yang sudah ada

[Paket binding sumber](../results/area_coverage_map/source_binding.json) mengikat
snapshot baru. Dataset private:
`chrisbiran/area-coverage-800m-source-snapshot`.

| Hasil perhitungan CPU workspace pada lokasi baru | Jumlah |
|---|---:|
| Source records pada bbox pengambilan |9151|
| Selected dalam radius800m dan rules bangunan |3597|
| ACCEPTED menurut skenario |1048|
| ACCESS_UNVERIFIED |1083|
| NO_ROUTE |88|
| NO_VALID_CONNECTOR |740|
| OVER_TIME_LIMIT |638|

Jumlah selected direkonsiliasi:1048+1083+88+740+638=3597. Jangan menyebut9151
sebagai bangunan terpilih800m. Kapasitas standard menggunakan unit N1 unresolved;
bukan KK/populasi. Accepted bukan proof akses fisik/legal atau measured ETA.
Road/features source tidak atomic; warning waktu sumber dan quarantine tetap
ada, analysis PARTIAL tidak diubah menjadi COMPLETE.

Tiga kalkulasi workspace pada source/config/runtime yang sama: initial+2replay,
masing-masing21calculation artifacts byte-identical, network diblok saat replay.
Ini tidak otomatis membuktikan cross-runtime parity dengan Kaggle. Kaggle
merekam versi GDAL/Python/PROJ/source packages yang benar-benar digunakan dan
menjalankan source terlihat, bukan sekadar memuat angka di atas.

**Bukti baseline Kaggle versi3: COMPLETE**, benar-benar menjalankan CPU; Python
3.13.15, GDAL3.8.4, PyProj3.8.0. Seluruh angka di tabel juga diperoleh pada
Kaggle versi2 dan3. Manifest kalkulasi keduanya identik; ini bukti dua run
Kaggle pada profil tersebut, bukan klaim byte parity lintas runtime workspace.
Fingerprint source terlihat baseline versi3 (sebelum penambahan POI/secret baru):
`e8a8f3afdfea46374a9ca2e86687e35251cfa4d163b499f83690b3e286bfa539`.
[Bukti baseline run](../results/area_coverage_map/verification/kaggle_v3/retention.json).
Result view `29fd5925e13c40a852416f937eeeff4fb6d07d1805c1929da2f00b208e282d42`
tetap **PARTIAL_BQ_BLOCKED_OR_FAILED**: kedua tabel BLOCKED, jumlah null.
Sukses eksekusi notebook berbeda dari kelengkapan data bisnis.

13baseline boundary tests memeriksa schema binding numeric/geography/WKT,
unknown schema, parameter/identifier guard, duplicate history/conflicting IDs,
failed authentication bukan0, frozen BQ reopen tanpa auth, bbox dan target guard.
Peta aktual dengan footprint/network sudah diuji di browser: pan/zoom/layer
controls, target center, banner source-blocked,0JS errors dan resource failures.
Bukan uji positif data BigQuery yang belum bisa diakses.

## BigQuery: setup dan batas validasi

Pada baseline versi3 credential belum tersedia; SDK workspace mengembalikan
DefaultCredentialsError. User kemudian menyediakan label **PROJECT_PPAC** di
Kaggle; ini bukan bukti akses BigQuery sudah berhasil. Alias kolom berdasarkan referensi N1 dan
pilihan eksplisit baru dipakai setelah `get_table()` mengonfirmasi field/type.
Tidak mengarang nama/count marker dari basemap atau sumber lain.

Langkah owner:

1. Buka [Service Accounts proyek locdeproject](https://console.cloud.google.com/iam-admin/serviceaccounts?project=locdeproject).
   Create Service Account; contoh nama `kaggle-area-reader`.
2. Berikan **BigQuery Job User** (`roles/bigquery.jobUser`) pada project
   `locdeproject`. Ini izin menjalankan query; bukan izin membaca semua tabel.
3. Di BigQuery Explorer, buka masing-masing tabel → Sharing/Permissions → Add
   principal. Gunakan email service account tadi, lalu **BigQuery Data Viewer**
   (`roles/bigquery.dataViewer`). Lakukan untuk `COMPETITOR` dan `AREA_COVERAGE`
   pada dataset `DWH_NS_LOC`. Pastikan BigQuery API proyek aktif.
4. Kembali ke service account → Keys → Add key → Create new key → JSON.
   Salin **seluruh isi JSON**, bukan nama file atau hanya nilai `private_key`.
5. Buka [editor notebook CPU](https://www.kaggle.com/code/chrisbiran/area-coverage-800m-poi-2km-cpu/edit)
   → Add-ons → Secrets → Add a new secret. Label **PROJECT_PPAC**,
   value isi JSON tadi, lalu Save dan aktifkan akses secret untuk notebook ini.
6. Save/Run All. Jika session sudah mempunyai variabel/hasil CPU, cukup jalankan
   ulang bagian **6. Akses BigQuery → 6B. POI → 7. Peta → 8. Export**. Tidak perlu mengambil
   ulang footprint/jalan. Tanda akses berhasil: kedua layer `SUCCEEDED`, schema
   binding aktual tercetak, dan marker hasil query muncul jika tersedia.

Secret berada di **Kaggle**, bukan shell Codex/GitHub Secrets. Owner perlu
memberikan izin service account dan menautkan secret pada notebook; push source
notebook tidak otomatis memberikan akses ke data BigQuery private. Jika bukan
admin proyek, minta admin melakukan langkah IAM tersebut menggunakan email
service account; jangan memberikan role Owner/Editor hanya untuk membaca tabel.

Jangan mengirim key lewat chat/GitHub, menaruhnya di source, atau mencetaknya.
Notebook memakai memory-only `Credentials.from_service_account_info`; tidak
menulis key ke output. Source/hasil BQ tetap private; tidak dipublikasikan ke Git.

BigQuery client independen dari sukses layer lain. Query hanya memilih kolom
relevan, memakai parameter koordinat/radius, dry run dan maximum_bytes_billed
256MiB/query. Budget/schema/permissions yang gagal bukan valid-empty data.
SDK tidak memerlukan BigQuery Storage API; hasil dibaca melalui query iterator.
Audit parse koordinat global dilaporkan terpisah; invalid coordinates tidak
diasumsikan berada di luar radius.0marker valid bukan proof tidak ada toko.

Histori ID+lokasi sama digabung untuk marker, nama alias tetap ada; ID sama di
lokasi berbeda diberi conflict flag dan tidak dipilih pemenang arbitrer.
Namespace Indomaret dan kompetitor terpisah. Marker adalah lokasi menurut tabel,
bukan verifikasi current operating store atau definisi unique business store.
Belum ada filter active/latest-period bisnis yang ditambahkan diam-diam.

## Cara membuka dan membaca hasil

1. Buka notebook Kaggle. GPU OFF; Internet ON.
2. Semua konfigurasi ada pada cell1; schema overrides BQ dapat diedit setelah
   metadata aktual diperiksa. Radius bangunan dan radius POI berbeda field.
3. Cell runtime menyiapkan GDAL system worker terpisah dari notebook packages.
4. `SOURCE_MODE=FROZEN` memverifikasi input snapshot sebelum menghitung. Jika
   target/radius sumber berbeda, harus REFRESH/new revision; tidak relabel cache.
5. Cell CPU menghitung seluruh source rows, lalu cell BigQuery menyiapkan layers.
6. Cell peta menampilkan Folium interaktif langsung: footprint, status, network,
   target, dua radius, marker clusters, popups/tooltips, layer controls dan ukur.
7. Output berada di `/kaggle/working/results/area_coverage_cpu/<fingerprint>/`.
   View final disimpan di `views/<result_version>/area_coverage_map.html`,
   `run_summary.json`, CSV/GeoJSON POI sukses dan `view_manifest.json`.
   `latest_view.json` adalah pointer; view lama tidak ditimpa.

Jika BQ belum bisa dibaca, map publik tetap tersedia dengan banner jelas dan
status `PARTIAL_MAP_INPUTS_UNAVAILABLE`. Jumlah source BQ null, bukan0. Output
MAP_READY hanya ketika kedua query layer dan sumber POI sukses; analysis underlying tetap
memiliki status kualitas sendiri.

Basemap OSM/CDN membutuhkan Internet untuk tampilan. Angka domain berasal dari
snapshot frozen, bukan perubahan basemap. Peta hanya consumer hasil; tidak
mengulang routing saat zoom, toggle atau membuka popup.

## Stabilitas dan refresh

Normal source menggunakan data frozen. Reopen PILOT yang selesai tidak
menghitung ulang. View identity mengikat pilot manifest, source layer BQ dan
source code; source BQ baru setelah setup menghasilkan view revision baru,
tidak memperbaiki view lama secara mutable.

Sukses query pertama di-cache dalam session. Untuk lintas session yang sama,
lampirkan saved `bq_snapshot` dan isi `BQ_FROZEN_CACHE_INPUT`, gunakan mode
FROZEN. Jangan mengklaim tabel live tidak berubah hanya karena koordinat sama.
Mengedit helper Python sebaiknya diikuti restart session/Run All agar tidak
memakai module cache interpreter lama.

Kaggle ingestion mengekstrak arsip gzip otomatis. Dataset version1 menyebabkan
verifikasi file-set gagal; check tidak dilonggarkan. Version2 menyimpan ZIP data
sebagai `.snapshot` dan JSON inventory sebagai `.data`, sehingga nested gzip
bytes tetap utuh. Notebook memverifikasi checksum lalu mengekstrak **data saja**
secara aman; active helper source tetap dari cell source yang terlihat.

## Scope perubahan

File notebook baru, helper prototype sources/BQ/map, generator notebook, tests,
source binding dan documentation. Tidak mengubah package Area/Traffic, rumus
N1, model Traffic, PPAC, baseline lama, atau melaksanakan migrasi42file.
Lihat [audit modularisasi](AREA_COVERAGE_MODULARIZATION_READINESS_AUDIT.md) untuk
gate pekerjaan berikutnya. Konfigurasi400m di baseline N1 tetap historis;
permintaan baru800m berlaku pada analisis/notebook ini.
