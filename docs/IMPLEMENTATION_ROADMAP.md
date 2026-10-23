# Location Intelligent — roadmap implementasi

## Update LI-5 terbaru

Offline Recount pada N1 sudah PASS untuk scope eksperimen tanpa manual polygon.
[Review](LI_5_REVIEW.md) mencatat31tes baru/259total, revision/delta/union dan
snapshot preservation. Kebijakan bisnis Recount serta interface modularisasi
menunggu review [kontrak draf C01–C09](ENGINE_IO_CONTRACT_DRAFT.md). Berikutnya
schemas/adapters/golden parity setelah kontrak disetujui; tidak otomatis
menjalankan LI-6, PPAC, refactor atau UI. Tabel di bawah mempertahankan sejarah.

## Update LI-4 terbaru — 23 Oktober 2026

LI-4 scope terbatas selesai: paket N1 mandiri, peta/tabel/CSV/GeoJSON,
rekonsiliasi seluruh 2623 source rows dan reopen offline. **PASS packaging;
analysis tetap PARTIAL**, unknown tidak dipromosikan. 228 tes PASS.
[Review dan batas pengujian browser](LI_4_REVIEW.md). Tidak menjalankan sumber,
routing atau Traffic ulang. LI-5 belum dimulai; perlakuan universe/predicate/
boundary/union/coverage Recount perlu disepakati. Tabel historis di bawah
mempertahankan status sebelum implementasi terbaru.

## Update LI-3 terbaru

Brief owner sudah dijalankan pada N1: source/graph/connectors/pilot/replay
diimplementasikan; hasil pilot **PARTIAL**, replay **PASS**. Lihat
[audit](LI_3_INITIAL_AUDIT.md) dan [review](LI_3_REVIEW.md).641accepted scenario
bukan physical/legal verification. LI-4/UI/Recount/PPAC tidak dimulai otomatis.
Bagian di bawah mempertahankan sejarah; "belum dijalankan" adalah status
sebelum LI-3, bukan status terbaru.

22 Oktober 2026. LI-0/LI-1 **PASS offline**; LI-2 routing subset **PASS**,
final accessibility **BLOCKED**, overall **PARTIAL**. Tahap berikutnya
tetap **PROPOSAL**, bukan perubahan urutan fase
Traffic Counter0–13. Label LI di sini hanya dependensi integrasi lokasi.
[Arsitektur](AREA_COVERAGE_ARCHITECTURE.md),
[kontrak](AREA_COVERAGE_DATA_CONTRACT.md),
[inventaris](DATA_SOURCE_INVENTORY.md) dan
[keputusan terbuka](AREA_COVERAGE_DECISIONS.md) tetap otoritas masing-masing.

## Evaluasi urutan kerja

Urutan offline validator → frozen reference calculations → routing → live
source/map/export → Recount → feature adapters → PPAC masuk akal dengan
penjelasan penting: **source retrieval adapters mendahului validasi Area
end-to-end dengan data nyata**, berbeda dari feature adapters downstream.
Pembacaan snapshot dan ekspor dapat diuji offline lebih awal; map basemap
live bukan syarat kalkulasi. Mock/fixture sukses tidak membuktikan akses layanan.

## Tahap, input, proses dan gate

| Tahap | Input | Proses/output yang direncanakan | Gate sebelum tahap berikutnya |
|---|---|---|---|
| **LI-0 — repaired validator, PASS gate terbatas** | JSON context/config/manifest lokal dengan schema v1, fixture valid/invalid, optional artifact lokal | Types/ranges/IDs/hash/references/status, validity dan gate input seleksi bangunan LI-1 |49 tes PASS termasuk43 baseline+6 repaired regressions; READY bukan bukti payload/live integration |
| **LI-1 — reader dan building selection, PASS offline** | Canonical local GeoJSON li_building_snapshot_v1 dan SourceRef/config; synthetic diberi label | Read-only reader, payload/geometry validation, N1 selection, reject ledger/reconciliation |40 tes PASS;9record=5selected+4excluded. Invalid sample=1selected+2excluded+6rejected/PARTIAL. Capacity sengaja belum implemented; real N1 snapshot belum tersedia |
| **LI-2 — routing offline, PARTIAL** | Directed multigraph fixture, selected LI-1 buildings, target, explicit config | Directed/parallel routing, candidates/connector costs, snap/coverage diagnostics dan deterministic routes |41 tes PASS; routing subset PASS. D02/D03/D05/D10 masih OPEN, final accessible=null; bukan business/live PASS |
| **LI-3 — source retrieval integration** | SRC04 buildings/SRC05 graph identifiers, explicit request scope, auth refs bila diperlukan, provider policy; SRC02/03/08 optional | Implement adapters terpisah, mock response/error/schema tests; kemudian minimal live metadata/schema/permission/cost checks hanya pada tugas live terpisah; freeze acquired inputs | Core Area perlu sumber buildings+graph kompatibel dan terverifikasi. BigQuery schema/grain/partition/cost belum confirmed; RWI blocked sampai mapping. Tidak menjalankan query store legacy tanpa bound karena contoh N1 melakukannya |
| **LI-4 — Area end-to-end, persistence/map/export** | Acquired/frozen real source package dari LI-3, validated target/config, calculation/routing policies | Bounded real run, candidate/reject diagnostics, atomic manifest, CSV/GeoJSON/JSON; map adalah derived view | Reopen tanpa re-fetch memberi hasil sama; scope/units/completeness jelas; output success setelah semua wajib finalized. Real source parity dan kualitas hasil dinilai terpisah dari pass fixture |
| **LI-5 — Recount** | Validated Area/source snapshot, polygon revision, approved universe/predicate/boundary/coverage policy | Membership per building, per-polygon subtotal, union unique keys dan completeness | D06/D07 selesai untuk scope implementasi; polygon outside snapshot tidak dianggap count lengkap; tidak menjalankan model Traffic/routing ulang saat edit polygon |
| **LI-6 — downstream feature adapters** | Selected Area/Recount dan Traffic result manifests yang sudah valid, mapping target/period/units, pilihan machine atau reviewed | Read-only feature records + source refs; flags measured/estimated/missing dan coverage | Tidak sum machine+reviewed; tidak extrapolate delapan klip ke24jam tanpa kebijakan; same-target/period gate terpenuhi; old events tidak dimodifikasi |
| **LI-7 — PPAC** | LI-6 features, approved formula/constants/units, Excel baseline version/hash dan evaluation protocol | Versioned PPAC input/output breakdown; comparison yang dapat direproduksi | D04/D11–D14 teratasi sesuai scope; historical SPD unit/label alignment confirmed; tidak menerbitkan angka SPD saat formula/input wajib BLOCKED |

Host UI D01 diputuskan sebelum implementasi Home/navigation; tidak perlu
memilih framework untuk LI-0–LI-3. Requirement framework tidak disimpulkan
dari legacy Streamlit/Gradio. Tidak menambah layanan terdistribusi.

## Batas offline dan live

- **Offline yang realistis:** schema/context/hash/file checks, synthetic
  building/graph tests, deterministic calculations, exports, Recount geometry
  fixtures dan feature joins. Fixture tidak membuktikan source freshness,
  credential permission, building completeness atau keberhasilan provider.
- **Offline dengan snapshot nyata:** replay deterministik dimungkinkan bila
  snapshot lengkap, hash/coverage/schema valid dan lisensi/mode pemakaian
  jelas. Full frozen building/graph N1 belum terbukti tersedia di workspace.
- **Memerlukan live access terpisah:** metadata physical schema/partition BQ,
  permission/billing/estimated scan, Overture release/schema availability,
  acquisition graph dan quota/freshness provider. Tidak ada pemeriksaan ini
  pada tugas dokumentasi sekarang.
- **Membutuhkan keputusan bisnis/bukti:** unit capacity, accessibility
  thresholds/selection, Recount universe, traffic daily normalization, RWI
  source, formula PPAC dan baseline Excel. Pass validator tidak menutupnya.

## Instruksi tepat untuk tugas coding berikutnya

LI-0 repaired dan LI-1 selesai melalui
[validator](../notebooks/location_intelligent_validator.py),
[building helper](../notebooks/location_intelligent_buildings.py), tes dan fixture lokal.
Hasil/command dan batas acceptance ada di
[PROJECT_STATUS](PROJECT_STATUS.md#hasil-audit-li-0-dan-eksekusi-li-1).

LI-2 kini tersedia melalui [helper](../notebooks/location_intelligent_routing.py)
dan [tests](../notebooks/location_intelligent_routing_tests.py), dengan
[execution receipt](evidence/location_intelligent/li2_20261022/execution.json).
**Tugas terkecil berikutnya:** tetapkan versioned policy D02/D03/D05/D10,
kemudian uji gate accessibility offline. Source retrieval, capacity final,
UI dan PPAC tetap tahap lain. Passing fixture bukan real integration atau
physical access. LI-3 tidak dimulai otomatis.

## Kesiapan LI-3 setelah kebijakan motor D28

Konfigurasi: [location_intelligent_config.py](../notebooks/location_intelligent_config.py).
[D28](AREA_COVERAGE_DECISIONS.md#d28--kebijakan-motor-dan-konfigurasi-tunggal)
mencatat keputusan parsial terbaru; bagian sebelumnya mempertahankan sejarah LI-2.
**LI-3 belum dimulai.** Adapter dapat dikembangkan dengan mock sebelum seluruh
policy numerik selesai; final accessibility tetap memerlukan profile baru dan
pengujian. UI/PPAC tidak perlu diputuskan untuk membangun adapter.

| Prioritas | Keputusan/input yang kurang | Rekomendasi (PROPOSAL) dan dampak gate |
|---|---|---|
| P0 | Target nyata, koordinat dan entrance toko | Pilih satu lokasi yang dapat diperiksa. Koordinat contoh N1 bukan fakta toko TGDI; target diperlukan sebelum live validation |
| P0 | Versi/schema/acquisition sumber buildings dan graph motor | Pertahankan Overture+OSM sebagai referensi; verifikasi identifier/schema dan cakupan. Graph drive N1 belum menjamin gang motor tersedia; jangan mengganti provider diam-diam |
| P0 | Bukti akses, barriers, portal, konflik izin dan larangan belok | Tetapkan mapping source→evidence→izin dengan provenance; unknown excluded. Simpan bridge/tunnel/layer dan turn restrictions bila tersedia. Jangan infer koneksi dari perpotongan garis pada peta |
| P0 | Kandidat akses/entrance, snap dan biaya konektor | Usulan minimum total time termasuk konektor dibandingkan dengan nearest reachable N1;50m fixture bukan default bisnis. Multiple entrances perlu aturan eksplisit |
| P1 | Strictness/pembulatan10min dan model waktu | Usulan full precision `<10`, pembulatan tampilan saja;7km/h tetap asumsi berlabel, bukan ETA tervalidasi |
| P1 | Scope request, biaya/kuota, coverage, freshness dan partial | Bekukan response+hash+versi/as-of; request gagal bukan empty.5500m reference bukan jaminan graph lengkap. Jangan mengarang TTL |
| P1 | Motor sampai pintu atau parkir lalu berjalan | Usulan scope awal motor-only; segmen jalan kaki memerlukan izin kebijakan dan model biaya terpisah |

### Alur yang belum lengkap dan cara menyelesaikannya

1. **Target/scope → context:** validasi lokasi/CRS, tentukan acquisition extent
   dan snapshot konfigurasi. Target unknown memblokir run nyata, bukan mock tests.
2. **Acquire → freeze → normalize:** adapter buildings/roads terpisah; simpan
   raw bytes/provenance/coverage/status/hash, lalu canonical snapshot. Jangan
   mengubah unknown menjadi izin atau retrieval gagal menjadi count0.
3. **Evidence → graph motor:** petakan izin, barriers dan manuver yang sah;
   tentukan konektor yang dapat digunakan. LI-2 v1 belum memodelkan semua
   pembatasan belok; config flag tidak menambahkan kemampuan tersebut.
4. **LI-1 → routing profile baru:** seleksi bangunan, akses awal, jaringan dan
   entrance tujuan; bedakan no-route pada model dari belum terverifikasi.
   Unknown yang excluded tetap dilaporkan agar cakupan konservatif tidak
   disangka lengkap. Definisikan model waktu sebelum keputusan10min final.
5. **Bandingkan N1/policy baru:** input nyata sama, snapshot/output terpisah;
   review sungai/pagar/median, gang motor/private, missing entrance dan U-turn.
   Route-found bukan validasi ETA maupun akses legal di lapangan.
6. **LI-4 publication:** manifest/hash konfigurasi efektif, artifact immutable,
   subtotal terverifikasi dan unknown terpisah, export atomik. Tidak membuka
   gate hanya karena file config tersedia.

**Langkah terkecil berikutnya:** spesifikasi mapping provider/evidence dan
adapter mock tests, kemudian minimal source verification pada satu lokasi
setelah target/scope tersedia. Tidak perlu retrieval massal. D04 capacity
memblokir capacity final, bukan adapter footprints/graph; RWI, BigQuery
optional, PPAC dan UI tetap scope lain.

### Delta D30 sebelum LI-3

Snap target sudah diputuskan tanpa batas numerik, tetapi pencarian hanya pada
graph tersedia; connector cost belum diputuskan. Floor total menit sebelum
<=10 sudah disepakati (raw<11 untuk waktu nonnegatif). Gang dan portal diberi
asumsi akses eksplisit; unknown bukan lagi alasan menolak dua kasus itu saja.
Hierarki jalan tertinggi, prioritas terhadap minimum total time/valid access,
kecepatan konektor dan pemilihan titik entrance masih OPEN. Memilih jalan
tertinggi untuk frontage tidak sama dengan menghapus jalan lokal dari routing.
Data/versi terbaru yang diperiksa ada di
[inventaris sumber](DATA_SOURCE_INVENTORY.md#verifikasi-dokumentasi-publik--22-oktober2026).

Delta D31: ranking akses valid sebelum kelas, hierarki eksperimen dan7km/h
untuk seluruh segmen sudah disetujui. Open list sebelumnya berkurang:
connector time dihitung dari jarak dengan7km/h, tetapi geometri/jarak konektor
dan prioritas kelas tertinggi versus minimum total time belum ditetapkan.
LI-3 belum dijalankan; policy v4 tetap snapshot yang belum dikonsumsi LI-2.

Delta D32: konflik kelas versus waktu sudah diputuskan. Policy v5 memilih
kelas akses valid tertinggi dahulu, kemudian waktu total minimum di kelas
tersebut. Primary8min mengalahkan service5min. Konfigurasi belum terintegrasi
ke LI-2; open list sebelumnya harus dibaca dengan klarifikasi terbaru ini.

## Assessment LI-1/LI-2 setelah D33

- **LI-1 jelas untuk scope selection offline:** representative point WGS84,
  full metric footprint area, radius<=400m, area>45m2; standard<550m2,
  special class handling dan reject/duplicate rules sesuai N1.40 tes sudah
  tersedia. Capacity bukan bagian LI-1; D04 tidak dianggap selesai. Taxonomy
  null-subtype fallback merupakan perilaku legacy, bukan kebenaran bisnis
  yang terbukti. Real Overture schema2.0 normalization/parity belum diverifikasi.
- **LI-2 business scenario sebagian besar jelas, implementasi belum selesai:**
 125m access search, no numeric target snap cap, kelas valid tertinggi lalu
  minimum raw time,7km/h semua segmen, round(total_min)<=10, motor-only,
  larangan/private tetap menang, asumsi gang/portal/entrance eksplisit.
  Engine existing tetap N1_REFERENCE_ONLY; final accessibility masih BLOCKED.
- **Masih perlu rincian sebelum acceptance keseluruhan:** cara menghasilkan
  entrance/konektor dan menguji barrier; precedence raw access tags dan
  conditional/turn restrictions; link/unranked road mapping; highest class
  dengan akses valid tetapi tanpa directed route ke toko; snapshot/extent
  dan error/partial/freshness handling sumber nyata. Jangan mengisi silent
  fallback atau menyebutnya production-ready.
- **drive_service dipilih untuk LI-3**, tetapi diketahui tidak mencakup semua
  track/path/motorcar=no yang mungkin boleh dilalui motor. Bisa melanjutkan
  adapter terbatas dengan limitation ini terdokumentasi; klaim jaringan motor
  lengkap memerlukan scope/keputusan dan evidence tambahan.

Prioritas berikutnya: kontrak adapter/source normalizer + policy-aware routing
profile dan synthetic cases terpisah dari N1; live smoke setelah satu target
dan acquisition scope nyata tersedia. LI-3 tidak dijalankan oleh update config.

## Status setelah implementasi D34

Config v7 kini dikonsumsi motor helper dan kapasitas referensi; snapshot-only
di atas merupakan status historis. N1 helper tetap identik. Source probe nyata
dijalankan sesuai scope owner, bukan full LI-3 service.
[Hasil dan command](../results/location_intelligent/README.md).

| Gate | Hasil aktual |
|---|---|
| LI-1 source probe | PASS terbatas:2623actual records,1322selected/1301excluded/0rejected; bukan exhaustive provider schema validation |
| LI-1 capacity reference | PASS per-unit formulas; standard subtotal5288 berunit unresolved, bukan population/KK; special formulas hanya diuji sintetis |
| LI-2 motor integration | PASS offline fixture: ranking valid/reachable class, no-path fallback,7km/h seluruh segmen, target connector cost, round<=10, network permission dan blocked turns |
| LI-2 real accessibility | Belum verified; graph/entrance/barrier evidence nyata belum ada. Interior access membutuhkan adapter membelah edge untuk node-bound connector |
| LI-3 readiness | Bisa melanjutkan adapter: retrieval motor, normalization dan source QA berikutnya |

**Open:** conditional-access timestamp/timezone; restriction/exception mapping;
connector construction dan barrier topology; freshness/coverage extent nyata;
motorway/trunk/unranked treatment; kelayakan null-subtype fallback untuk
kapasitas bisnis. Ini tidak membatalkan scoped reference acceptance, tetapi
menghalangi klaim produksi/final business capacity.

Untuk melengkapi drive_service, **PROPOSAL belum dijalankan:** query tambahan
raw track/path dengan motorcycle atau motor_vehicle permission positif, serta
ruas motorcar=no/motorcycle=yes yang dibuang filter mobil. Union menurut OSM
way/node IDs sebelum simplification; preserve tags/barriers/restriction
relations. Specific motor prohibition/private tetap menang. Tidak membuat
edge karena garis bersilangan. Gunakan snapshot/as-of konsisten dan simpan
coverage/missing reasons. drive_service tetap base filter pilihan owner.
