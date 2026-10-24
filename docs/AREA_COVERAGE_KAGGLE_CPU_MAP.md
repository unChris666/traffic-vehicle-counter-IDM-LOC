# Area Coverage — notebook CPU800m dan layer toko/kompetitor2km

24 Oktober2026, Asia/Jakarta. **Implementasi prototype notebook yang diminta
owner; bukan pelaksanaan penuh audit modularisasi42file.** Core Area dan
baseline N1 lama tidak diubah. Koordinat serta radius baru merupakan analisis
baru, bukan penggantian label snapshot N1.

Notebook: [Kaggle CPU](https://www.kaggle.com/code/chrisbiran/area-coverage-800m-poi-2km-cpu)
→ [source di repo](../notebooks/area_coverage_cpu_800m_poi_2km.ipynb).
43cell,13source Python ditulis penuh melalui cell `%%writefile`, lalu diimpor
secara eksplisit dari folder source terlihat. Tidak ada base64/remote code
bootstrap atau implementasi diunduh dari Git. Dataset memuat data/provenance;
`engine_source` di data archive tidak digunakan sebagai runtime implementation.

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

**Kaggle versi3 terakhir: COMPLETE**, benar-benar menjalankan CPU; Python
3.13.15, GDAL3.8.4, PyProj3.8.0. Seluruh angka di tabel juga diperoleh pada
Kaggle versi2 dan3. Manifest kalkulasi keduanya identik; ini bukti dua run
Kaggle pada profil tersebut, bukan klaim byte parity lintas runtime workspace.
Fingerprint source terlihat versi3 cocok dengan source notebook di repo:
`e8a8f3afdfea46374a9ca2e86687e35251cfa4d163b499f83690b3e286bfa539`.
[Bukti run terakhir](../results/area_coverage_map/verification/kaggle_v3/retention.json).
Result view `29fd5925e13c40a852416f937eeeff4fb6d07d1805c1929da2f00b208e282d42`
tetap **PARTIAL_BQ_BLOCKED_OR_FAILED**: kedua tabel BLOCKED, jumlah null.
Sukses eksekusi notebook berbeda dari kelengkapan data bisnis.

13offline boundary tests memeriksa schema binding numeric/geography/WKT,
unknown schema, parameter/identifier guard, duplicate history/conflicting IDs,
failed authentication bukan0, frozen BQ reopen tanpa auth, bbox dan target guard.
Peta aktual dengan footprint/network sudah diuji di browser: pan/zoom/layer
controls, target center, banner source-blocked,0JS errors dan resource failures.
Bukan uji positif data BigQuery yang belum bisa diakses.

## BigQuery: setup dan batas validasi

User mengonfirmasi credential belum tersedia. SDK workspace mengembalikan
DefaultCredentialsError. **Live schema, izin, job query dan jumlah toko pada
kedua tabel belum terverifikasi.** Alias kolom berdasarkan referensi N1 dan
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
   → Add-ons → Secrets → Add a new secret. Label **GCP_SERVICE_ACCOUNT_JSON**,
   value isi JSON tadi, lalu Save dan aktifkan akses secret untuk notebook ini.
6. Save/Run All. Jika session sudah mempunyai variabel/hasil CPU, cukup jalankan
   ulang bagian **6. Akses BigQuery → 7. Peta → 8. Export**. Tidak perlu mengambil
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
status `PARTIAL_BQ_BLOCKED_OR_FAILED`. Jumlah source BQ null, bukan0. Output
MAP_READY hanya ketika kedua query layer sukses; analysis underlying tetap
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
