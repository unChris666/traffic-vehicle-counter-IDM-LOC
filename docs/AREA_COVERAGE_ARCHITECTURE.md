# Location Intelligent / Area Coverage — arsitektur integrasi

## Workflow/storage direction — 23 Oktober 2026

Location dan Traffic adalah domain engine terpisah; backend/UI mengonsumsi
kontrak provisional dan artifact refs. Owner review ditunda sampai UI input/
output tersedia, sementara engineer mengevaluasi milestones secara mandiri.
[Workflow aktif](CURRENT_DEVELOPMENT_WORKFLOW.md) memperbarui urutan kerja,
bukan hasil/algoritme LI yang sudah dieksekusi.

Video/hasil/snapshot artifacts direncanakan memakai GCS sesuai keputusan owner,
belum merupakan integrasi yang diuji. Metadata DB masih OPEN. Normal reopen
membaca hasil frozen; fresh area/source refresh adalah revisi baru eksplisit.
[Stabilitas](REPRODUCIBILITY_POLICY.md) dan [GCS plan](GCS_STORAGE_ONBOARDING_PLAN.md).
Tidak membuat bucket, backend atau UI pada update Markdown ini.

## LI-4 boundary terbaru

`notebooks/location_intelligent_li4.py` membaca verified frozen LI-3, menyalin
source packet, join stored decisions/selection/capacity, mengekspor geometri
stored path via display-only transform, dan mempublikasikan paket setelah
verify. `location_intelligent_li4.html` adalah derived offline review view,
bukan production UI/framework. Tidak memanggil routing/acquisition/Traffic.
Peta, tabel dan ekspor berasal dari dataset kanonis sama. Snapshot LI-3 tidak
diubah. [Review LI-4](LI_4_REVIEW.md); review sumber akses terpisah.

## Implementasi LI-3 aktual

Helper baru tetap di notebooks/: source I/O, OSM normalization/restrictions,
connector generator, system-Python core worker, orchestration/replay dan
read-only source review. Tidak membuat framework/services baru. LI-0/LI-1/
capacity/motor helpers digunakan kembali. Source env (OSMnx/Shapely/PyProj)
terpisah dari GDAL core worker; file contracts+hash mengikat kedua lingkungan.
Core never fetches sources. Frozen config dan explicit acquire/build/replay
commands mencegah implicit rerun saat import/review. Full scope/results ada
di [LI_3_REVIEW](LI_3_REVIEW.md); diagram/proposal lama di bawah dipertahankan.

Replay mengeksekusi recorded code archive dengan software-version checks dan
raw frozen inputs. Publication manifest atomic, relative paths confined,
checksums/DAG/coverage dan per-building states eksplisit. Replay receipt
merujuk retained origin manifest agar tidak circular dengan final manifest.

Status **DOCUMENTED**. Ini rancangan, bukan daftar modul/router yang sudah ada.
LI-0/LI-1 dan LI-2 diagnostic subsets kini implemented secara offline; full
application/source integration dan final accessibility belum dinyatakan PASS.
Keadaan repo dan sumber: [overview](LOCATION_INTELLIGENT_OVERVIEW.md).
Perilaku referensi numerik: [spec](AREA_COVERAGE_SPEC.md).
Dokumen existing ini menjadi otoritas arsitektur; tidak membuat salinan
`LOCATION_INTELLIGENT_ARCHITECTURE.md`. Status aktual ada di
[PROJECT_STATUS](PROJECT_STATUS.md).

## Alur pengguna yang diusulkan

Target/context → pilih input dan konfigurasi → jalankan module secara
eksplisit → lihat hasil beserta status/coverage → review atau Recount pada
snapshot → pilih fitur tervalidasi → PPAC jika gate bisnis terpenuhi.
Traffic Counter dapat dijalankan terpisah tanpa koordinat toko; join ke
analisis lokasi membutuhkan mapping target yang benar. Home, navigasi dan
Recount adalah rancangan, bukan halaman terpadu yang sudah tersedia. Diagram
besar dan brief bisnis terpisah belum tersedia untuk mengonfirmasi detailnya.

## Batas tanggung jawab

| Batas konseptual | Tanggung jawab | Tidak boleh mengambil alih |
|---|---|---|
| Application/context adapter | Target immutable, manifest status, navigasi, pemanggilan eksplisit, artifact refs | Rumus kapasitas, counting, routing atau PPAC di komponen UI |
| Source adapter | Overture snapshot, response/schema/version, graph OSM snapshot, optional BigQuery | Mengganti provider/threshold saat request gagal |
| Geometry/building calculation | CRS, seleksi footprint, source/derived fields, capacity model versi | Menganggap estimasi sebagai observasi penghuni |
| Routing | Graph directed, access candidates, path dan decision diagnostics | Artificial reverse edges, U-turn atau koneksi antarruas yang tidak ada |
| Recount | Polygon revisions, membership pada snapshot, union dedup, coverage | Mengubah area run asli atau mengklaim bangunan di area yang tidak diambil |
| Traffic Counter adapter | Validasi referensi video/run/config dan feature extraction dari ledger | Menjalankan model dari rerender, mengubah BC/policy, atau menjumlah machine dan reviewed |
| PPAC adapter | Gate fitur, rules/constants/baseline version dan breakdown | Formula default yang belum disetujui atau menganggap kegagalan sebagai0 |

Source adapter **mengambil sumber**, sedangkan Traffic/Area feature adapter
**mengubah hasil tervalidasi menjadi fitur PPAC**. Keduanya bukan satu tahap.
Identitas fisik source dan kolom/query ada pada
[DATA_SOURCE_INVENTORY](DATA_SOURCE_INVENTORY.md); source belum terbukti
tidak boleh diberi default provider.

Ini dapat dimulai sebagai helper notebook/file I/O dalam repo yang sama;
bukan alasan menambah microservice, database, container atau framework baru.
Pilihan host UI masih [D01](AREA_COVERAGE_DECISIONS.md). Referensi legacy
Streamlit/Gradio tidak menetapkan framework R1 secara otomatis.

## Context, execution dan state

**PROPOSAL:** Home menghasilkan `analysis_run_id` dan snapshot target/config.
Setiap engine mempunyai `module_run_id` dan lifecycle sendiri. Wrapper
menghubungkan `run_id` lama ke context tanpa menulis ulang hasil lama.
Context memastikan satu target eksplisit; jangan menyamakan target contoh
notebook dengan toko TGDI yang metadata lokasinya masih unknown.

- Engine dipanggil hanya lewat aksi run eksplisit. Import, navigasi, download,
  rerender atau mengganti tab tidak menjalankan query/model.
- UI/session memory hanya menyimpan selection/reference; disk manifest
  mempertahankan status dan hasil yang dapat dibuka kembali setelah session.
- Perubahan lat/lon/CRS/policy/source membuat revision baru. Downstream result
  ditandai STALE terhadap revision baru, tetapi historical result tetap utuh.
- Konfigurasi filter per video terpisah dari geometri. Mengubah photometric
  filter tidak memindahkan koordinat, tetapi membatalkan reuse detection/ReID
  cache yang dibuat dari input photometric berbeda.
- Snapshot input, job scope dan output refs harus cocok sebelum UI menampilkan
  hasil atau PPAC mengonsumsi fitur. Rerun menghasilkan namespace baru.

Layout **usulan**, belum dibuat oleh tugas ini:

```text
results/location_intelligent/<analysis_run_id>/
  context.json
  manifest.json
  area_coverage/<module_run_id>/
    config.json + provenance.json + diagnostics.json
    buildings.* + routes.geojson + access_candidates.* + summary.json
  recount/<revision_id>/
    polygons.geojson + membership.* + summary.json
  traffic_refs.json
  ppac/<module_run_id>/
    inputs.json + result.json
```

Existing `results/b_v7/`, `results/b_v8/`, `results/phase_9/` dan Kaggle exports
tidak dipindah atau ditimpa. `traffic_refs.json` hanya merujuk manifest/hash
yang sudah ada. Folder usulan bukan bukti artifact tersebut sudah tersedia.

## Failure dan persistence

Bedakan NOT_RUN, BLOCKED, RUNNING, SUCCEEDED, SUCCEEDED_WITH_WARNINGS,
PARTIAL, FAILED dan STALE; definisinya pada [data contract](AREA_COVERAGE_DATA_CONTRACT.md).
Status parent tidak mengubah module gagal menjadi sukses atau menghapus module
yang sukses. PPAC BLOCKED bila input/formula wajib tidak valid.

Retrieval gagal→error+null coverage/count; valid query kosong→observed_count0
dengan source/coverage status. Unknown capacity tetap null dengan jumlah
unknown. Directed no-path yang benar adalah decision row, bukan service outage;
graph tidak lengkap/snap di luar coverage adalah unresolved/coverage failure.

**PROPOSAL:** tulis artifact ke direktori job baru, checksum dan validasi semua
output, lalu publish manifest final secara atomik. Failure menyimpan diagnostic
dan artifact parsial berlabel; UI tidak mengambil file parsial sebagai final.
Manifest harus mencatat status EXPORT setelah finalisasi, memperbaiki masalah
urutan N1 melalui versi implementasi baru, bukan mengedit hasil contoh N1.

## Source adapters dan reuse

Alur yang direncanakan: request/context terikat → retrieval raw → validasi
response/schema/coverage → normalisasi CRS/type/unit disertai reject ledger →
freeze snapshot+fingerprints → engine kalkulasi → output manifest. Source
retrieval, normalization dan calculation mempunyai diagnostics sendiri;
request sukses belum menjamin schema atau hasil kalkulasi valid.

| Boundary adapter | Input/output dan isolasi |
|---|---|
| BigQuery stores/competitors | Client/binding di-inject per adapter; parameter query, schema/grain/as-of dan cost/partition policy dicatat. Tidak memakai global client sukses dari module lain; SRC02/SRC03 bukan syarat core building accessibility |
| Overture object storage | Release/path/schema/bbox eksplisit; freeze raw subset dan normalized buildings/places terpisah; POI opsional tidak memblokir building core bila scope menyatakannya |
| OSM/API network | Request extent/filter/snapshot, directed graph dan source time; tidak menyebut local constant-speed routing sebagai live ETA |
| Local snapshot reader | Baca artifact/manifest dengan hash/schema/coverage checks; tanpa fallback network tersembunyi jika snapshot hilang |
| Traffic/Area feature adapters | Read-only hasil yang sudah dipilih; validasi target/period/units/completeness; output feature record+lineage, bukan retrieval ulang atau model run |

Source adapters Overture buildings dan OSM graph diperlukan untuk validasi
end-to-end Area dengan akuisisi sumber nyata. Implementasinya bisa memakai
mock terlebih dahulu, tetapi pass mock bukan pass layanan. Snapshot nyata
yang sudah terverifikasi juga dapat direplay offline; saat ini full snapshot
Area tersebut belum tersedia dalam bukti lokal. BigQuery diperlukan untuk
fitur nearest/similar/competitor, bukan untuk mengklaim core Area gagal saat
modul opsional tersebut tidak tersedia. RWI menunggu mapping sumber.

| Adapter/cache | Identitas minimum sebelum reuse |
|---|---|
| Buildings | Provider/release/schema, query bbox/footprint coverage, checksum, acquired_at, selection/version dan CRS; simpan retrieved vs eligible vs accessible terpisah |
| OSM graph | Snapshot/request envelope, network filters/type, graph checksum, timestamp, CRS, directed topology; tidak menganggap radius400m sama dengan graph5500m |
| Routing decisions | Graph/config/CRS/building snapshot hashes, access selection/time/rounding rule versi, target/snap metadata |
| Recount | Snapshot hash, universe eligible/all-footprints/accessible, polygon hash/revision, predicate/boundary version dan coverage result |
| Traffic | Original video, transformed-input/filter, detector/tracker/ReID/geometry/policy hashes, frame scope, branch, review refs |

Perubahan polygon dapat reuse snapshot hanya bila geographic **dan semantic
coverage** memadai. N1 `building_valid` sudah membuang bangunan tertentu;
meski polygon di dalam400m, table itu bukan inventaris semua tipe bangunan.
Perubahan target di luar snapshot perlu retrieval baru atau status coverage
limited. Tidak ada perluasan area diam-diam atau padding rule yang dianggap
approved. Freshness/TTL dan graph snap limits masih OPEN.

Dependencies geospasial dipasang/diuji pada lingkungan riset terpisah terlebih
dahulu; N1 memiliki broad version ranges dan dependency warnings. Jangan
menjalankan cell install N1 ke environment Traffic Counter yang dibekukan.
Konfigurasi/source-provider request diteruskan sebagai input, bukan globals
lat/lon yang dapat bocor antaranalisis.

## Urutan implementasi dan gate

Urutan terperinci dan acceptance gates hanya pada
[IMPLEMENTATION_ROADMAP](IMPLEMENTATION_ROADMAP.md). Tahap pertama terbatas
validator context/koordinat/config/manifest offline. Selanjutnya deterministic
snapshot/calculation dan routing fixtures, source retrieval integration,
Area E2E/map/export, Recount, feature adapters, lalu PPAC setelah gate bisnis.
Keputusan threshold/rumus yang belum disetujui tidak diisi oleh validator.

Tidak ada source fetch geospasial, engine execution atau coding runtime pada
tugas dokumentasi ini. Tahap baru tidak membatalkan keputusan/gate Traffic
Counter; application adapter harus mempertahankan kontraknya.
