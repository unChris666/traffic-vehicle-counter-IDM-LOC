<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Area Coverage — keputusan, konflik dan readiness

21 Oktober 2026. Register ini membedakan fakta sumber, rekomendasi dan approval.
Sumber R1/N1/T1/F1/B1/L1/L2 didefinisikan pada
[overview](LOCATION_INTELLIGENT_OVERVIEW.md#register-sumber). Semua keputusan
OPEN di bawah belum menjadi rule produksi. Dokumentasi tidak menutupnya
secara implisit.

## Keputusan scope yang sudah jelas

- **CONFIRMED:** pengguna meminta repo yang sama; tidak membuat/memigrasi repo.
- **REQUIREMENT T1/T2 (historical):** hanya analisis/dokumentasi, tidak mengubah runtime,
  Traffic Counter, night filters, Area Coverage/Recount/PPAC atau hasil lama.
- **REQUIREMENT LI-0 sekarang:** implementasikan validator offline beserta
  fixture/tes dan klarifikasi kontrak minimum; larangan mengubah runtime
  Traffic/filter/baseline dan larangan implementasi engine tetap berlaku.
- **FACT:** R1 belum mempunyai Home/router/framework aplikasi terpadu.
- **REQUIREMENT:** N1 adalah reference calculation; diagram dan business brief
  punya peran berbeda. F1/B1 belum ditemukan, bukan dianggap cocok dengan kode.

## Register keputusan terbuka

| ID | Bukti/konflik | Dampak | Rekomendasi, belum approval | Keputusan/bukti yang diperlukan |
|---|---|---|---|---|
| D01 | T1 menyebut existing Home; R1 baru notebook/HTML review. L1 Streamlit dan L2 Gradio berasal dari repo lain | Tidak ada router atau UI state existing yang bisa diasumsikan | Pertahankan helper/file contracts; jangan memilih framework atau port legacy otomatis | Owner memilih host UI saat tugas UI diotorisasi; F1 untuk navigasi |
| D02 | N1 CFG125m; docstring100m | Candidate akses dan hasil capacity bisa berbeda | Freeze125 sebagai reference parity, bukan approval125 untuk bisnis | Owner menetapkan max access distance dan dasar empiris; version control |
| D03 | N1 CFG10menit dan strict<; docstring7menit; rounded3decimal dipakai sebelum gate | Inclusion berbeda, termasuk near-boundary | Reproduce kode10 untuk parity; full-precision gate hanya varian perubahan terdokumentasi | Threshold, strictness dan rounding policy bisnis |
| D04 | Standard household4, apartment occupied units, dormitory occupied rooms, hotel guests terpisah | Legacy sum tidak punya unit homogen; PPAC dapat salah dimensi | Split metrics; keep legacy field, unknown tetap null | Definisi KK/dwelling/resident-equivalent, occupancy conversion, floor/rounding assumptions dan approval constants |
| D05 | N1 memilih nearest reachable access, bukan minimum total time; store snapped node tanpa final connector | Akses/ETA dapat berbeda dari interpretasi pengguna dan endpoint sebenarnya | Preserve directed graph; expose candidate costs/snap offsets/coverage; bandingkan selection alternatives terpisah | Mode selection, entrance/store connector, snap limit dan QA; tidak mengarang angka baru |
| D06 | Recount diminta menghitung building; N1 table hanya eligible residential/special | Recount bisa undercount universe tanpa diketahui | Tampilkan explicit universe; representative-point predicate sebagai kandidat konsisten N1, bukan keputusan final | All footprints/eligible/accessible, boundary inclusion, polygon predicate dan overlap capacity aggregation |
| D07 | Query bbox/radius terbatas; Recount polygon bebas | Polygon di luar snapshot tidak bisa dihitung lengkap | Coverage relation dan incomplete flags; union dedup berdasarkan source building key | Re-fetch extent/authorization vs covered-only result, coverage definition dan source freshness |
| D08 | Geometry exceptions dilewati; tidak ada explicit validity/type gate; UTM dipilih sebelum validasi | Silent exclusions dan CRS salah | Validate early; reject ledger; repair hanya explicit/versioned | Geometry repair policy, valid CRS/domain dan duplicate/source-ID handling |
| D09 | Release N1 dipin, graph live, dependency ranges/warnings; export cell20 tidak punya output | Reproducibility belum lengkap | Source/archive hashes, graph snapshot, environment lock, output manifest | Dataset/schema/access availability, snapshot/freshness policy, replay fixture dan export evidence |
| D10 | drive graph+constant7km/h+straight connector dianggap akses motor; fence/entrance tidak diperiksa | Tidak membuktikan perjalanan/legal accessibility fisik | Label model/access assumption; pertahankan OSM topology tanpa artificial turn | Mode network/legal access, private/service/bridge/tunnel policy dan verifikasi lapangan bila diperlukan |
| D11 | Delapan Traffic samples bukan24jam; source dates/durations/slot coverage dan weight belum diputuskan | Daily traffic feature tidak terdefinisi | Preserve sample-level category/direction/duration; no automatic day extrapolation | Daily normalization, weekday/weekend/holiday/time-period and category weights |
| D12 | Formula approved/Excel/constants tidak tersedia; label dashboard PPAC/Huff bukan SPD formula | Tidak bisa menghitung SPD yang bermakna | Return BLOCKED/null; bangun interface/lineage dulu | Formula bisnis, workbook/sheet/version/hash, constants units/owner/approval |
| D13 | BQ memiliki SPD/PERIODE tetapi bukan reference label/evaluation protocol yang diverifikasi | Klaim manfaat model atau pembanding belum sah | Validate label/period/store alignment dan predefined spatial/temporal split | Statistical model scope, quality of labels, metrics dan acceptance criteria |
| D14 | Counter mempunyai measured/estimated/pending/invalid, machine/reviewed; P1 reviewed bukan otomasi produksi | PPAC raw sum dapat double count atau memakai estimasi sebagai fakta | Pilih satu snapshot, pisahkan evidence levels dan completeness | Kebijakan fitur measured vs estimated/reviewed/missing; jangan mengubah engine untuk menyesuaikan SPD |
| D15 | F1 diagram dan B1 business brief terpisah belum tersedia | Tidak bisa memverifikasi full workflow/requirement correspondence | Gunakan hanya T1 untuk proposal halaman; tandai detail belum terkonfirmasi | Diagram dan brief resmi, lalu review delta terhadap dokumen ini |
| D16 | N1 unknown capacity fillna0; flags route/accessible bisa berbeda; export success dicatat setelah JSON ditulis | False completeness/zero demand atau manifest menyesatkan | Known subtotal+unknown counts, normalized statuses, atomic publication dan candidate audit | Versioned output contract dan golden parity vs corrected behavior tests |
| D17 | T1 menyebut retain filter F1YV; JSON aktual+konfirmasi pengguna sebelumnya mengikat TKVQ-WEEKEND | Risiko rename/apply recipe ke video salah | Tidak mengubah kedua source/konfigurasi; status filter TKVQ tetap kandidat, bukan production baseline | Tidak perlu tuning ulang untuk dokumen Area; F1YV recipe tidak diasumsikan ada |
| D18 | L1 memakai Google Open Buildings/Huff/EPSG3857; N1 memakai Overture/UTM/directed accessibility | Menggabungkan prototype dapat mengganti semantik tanpa keputusan | N1 tetap reference Area sesuai T1; L1 hanya referensi legacy | Approval eksplisit sebelum reuse provider, constants atau capacity model legacy |
| D19 | RWI tidak ditemukan pada source lokal/N1; tidak ada asset/table/API identifier | Tidak bisa mengambil, geo-join atau membentuk fitur RWI | Pertahankan UNKNOWN; tidak memilih Meta/GEE/BigQuery berdasarkan nama fitur | Provider resmi, identifier/schema/sample, unit/CRS/vintage/coverage, join dan usage policy |
| D20 | SRC02/SRC03 memberi query expectations, bukan live physical schema; query store tanpa SQL period/spatial bound | Risiko full scan, join berulang atau unit salah meski client dibuat sukses | Metadata-only verification dan bounded-query/cost design pada tugas live terpisah | Table/view type, types/nullability, partition/location, grain keys, auth/grants, quota/pricing/freshness |
| D21 | SPD historis di-cast string; unit asal tidak terbukti sama dengan target PPAC struk/hari | Label/model dapat salah dimensi | Simpan raw SPD dan unit UNKNOWN; jangan auto-alias menjadi target | Definisi bisnis SPD, satuan/periode dan mapping observed label yang disetujui |
| D22 | Source retrieval adapter berbeda dari PPAC feature adapter | E2E Area tidak dapat dibuktikan hanya dengan mock atau downstream feature joins | Overture buildings+OSM retrieval sebelum real Area E2E; BigQuery/POI optional per scope; feature adapters sesudah hasil valid | Scope dan live verification terpisah pada [roadmap](IMPLEMENTATION_ROADMAP.md); tidak ada implementasi otomatis |
| D23 | Offline snapshot, request failure, successful empty dan stale adalah keadaan berbeda | Satu flag sukses/0 dapat menyembunyikan input hilang atau context lama | Availability, quality, freshness dan module status terpisah menurut kontrak; no request=NOT_ATTEMPTED | Freshness/as-of policy, required source scope dan treatment partial; tidak mengarang TTL |
| D24 | Competitor BQ dan POI Overture berbeda namespace; cell16 meminjam client cell14 | Double count/dedup salah dan hidden dependency module opsional | Adapter client mandiri; source-tagged keys; tidak merge by name saja | Cross-source entity mapping, brand semantics, POI confidence/status dan dedup policy |

## Klarifikasi kontrak teknis untuk tugas berikutnya

Bagian envelope v1 di [kontrak kanonis](AREA_COVERAGE_DATA_CONTRACT.md)
menetapkan **usulan** input lokal, types, ID/hash/path safety dan perbedaan
validity/readiness untuk LI-0. Itu cukup spesifik untuk membatasi tugas
validator berikutnya; bukan keputusan bisnis D02–D14 atau bukti runtime.
Policy yang belum disuplai harus menghasilkan diagnostic/BLOCKED, bukan
diisi CFG N1 secara implisit. Source/diagram/Excel yang belum tersedia tidak
menghalangi tes schema offline, tetapi tetap menghalangi klaim E2E/bisnis.

### D25 — clarification LI-0 yang sudah diimplementasikan

**TECHNICAL DECISION dalam otorisasi tugas LI-0**, bukan approval bisnis:
gunakan helper standard-library pada `notebooks/`, pola unittest repo, tanpa
framework/dependency baru. Bentuk envelope `location_intelligent_v1`, quantity,
checksum/provenance/status dan readiness diuraikan pada
[kontrak kanonis](AREA_COVERAGE_DATA_CONTRACT.md#klarifikasi-serialization-li-0-v1-yang-diimplementasikan).
Ini melengkapi bentuk field yang sebelumnya baru semantik, bukan schema
yang bersaing. Source/artifact version tetap provenance external; payload
schema/geometry tidak diverifikasi oleh LI-0.

**Gate yang dipilih:** LI-1 building-selection input contract saja, bukan
capacity/routing atau live E2E. Hanya building snapshot dan tiga parameter
seleksi N1+metric CRS wajib; parameter tidak diisi dari default. Keputusan
bisnis/routing D02–D14 tidak ditutup untuk membuat fixture READY. Unknown
metadata toko/vintage/freshness yang tidak wajib tetap terlihat, sedangkan
required data unknown menghalangi gate. RWI/PPAC opsional yang belum siap
tidak memblokir input seleksi bangunan.

**Hasil:**43 tes fokus PASS, CLI fixture VALID/READY dengan live NOT_VERIFIED.
Rincian command/scope di [PROJECT_STATUS](PROJECT_STATUS.md#hasil-eksekusi-li-0).
No known blocker untuk acceptance LI-0; global uniqueness ID, physical schema,
payload quality, actual coverage, freshness policy dan semantik capacity
tetap membutuhkan tahap/policy berikutnya.

## Perbandingan sumber dan contoh impact

- **R1 vs T1:** input store/lat/lon/eight slots adalah requirement, bukan Home
  teruji. Unknown TGDI location tidak diganti lokasi contoh N1.
- **N1 kode vs komentar:** building berjarak110m dari eligible road dapat masuk
  candidate dengan CFG125, tetapi tidak dengan interpretasi100. Rute8menit
  dapat accessible dengan CFG10, tetapi tidak jika mengikuti komentar7.
  Ini contoh logika, bukan hasil lokasi yang baru dihitung.
- **N1 kapasitas vs kebutuhan bisnis:** satu rumah memberikan4 sedangkan satu
  occupied apartment unit memberikan1. Menamai sum sebagai KK atau penduduk
  tanpa konversi mencampur unit. Hotel tidak boleh ditambahkan otomatis.
- **N1 routing vs interpretasi lokasi:** output similar store mempunyai contoh
  Haversine sekitar29,9km tetapi road distance sekitar7,0km pada graph lokal.
  Helper nearest-node tidak membatasi snap offset; hasil tersebut memerlukan
  QA endpoint, bukan bukti toko sebenarnya hanya7km. Isu auxiliary store
  routing tidak otomatis membatalkan seluruh building table Area.
- **N1 vs Recount requirement T1:** menambahkan polygon yang melampaui query
  coverage atau menghitung commercial buildings dari filtered residential
  table tidak memenuhi complete-building-count requirement.
- **N1 output vs proof:** contoh1321/1304/5216 hanya satu stored run. Cell20
  tanpa executed output tidak membuktikan CSV/GeoJSON/result.json tersedia.
- **F1/B1:** belum bisa dibandingkan detailnya. Tidak ada approval formula
  SPD yang dapat diturunkan dari nama PPAC atau keberadaan historical SPD.

## Prioritas rekomendasi

**Pareto sebagai cara memprioritaskan, bukan statistik80/20 yang diukur:**
dahulukan tiga kelompok risiko: (1) unit/unknown capacity D04/D16,
(2) routing/access semantics D02/D03/D05/D10, (3) lineage/coverage D06/D07/D09.
Memperindah map tidak menyelesaikan ketiganya.

| Pilihan implementasi berikutnya | Strength | Weakness | Opportunity | Threat |
|---|---|---|---|---|
| **Validator/context+fixture offline — rekomendasi** | Kecil, independen engine, melindungi target/unit/provenance | Belum menghasilkan map atau angka bisnis | Dasar reusable untuk semua module dan partial failure | Jika constraint diabaikan setelahnya, integrasi tetap dapat mencampur context |
| Port notebook sekaligus ke UI | Cepat memperlihatkan demo perhitungan referensi | Globals, mixed capacity dan sumber live ikut terbawa | Visual review workflow lebih awal setelah policy jelas | Label hasil tampak final padahal semantic/coverage/export belum tervalidasi |

### D26 — LI-0 audit dan LI-1 local selection

22 Oktober 2026. **IMPLEMENTED dalam scope tugas:**6 regresi LI-0 direproduksi,
diperbaiki dan baseline sebelum fix diarsipkan;49 tes termasuk43 existing
regressions lulus. Contract dan readiness meaning dipertahankan.

LI-1 memakai canonical local GeoJSON, subclass dari BuildingRecord, SourceRef
CRS4326 dan metric CRS context. Ini bukan schema provider baru. Installed
OGR/GEOS/PROJ dipilih untuk backend offline karena Shapely tidak tersedia;
provider dan aturan N1 tidak diganti. Seluruh duplicate ID ditolak dengan
PARTIAL snapshot; tidak dedup by first. Ordinary UTM domain gate dan no
geometry repair dipertahankan. Detail pada
[kontrak LI-1](AREA_COVERAGE_DATA_CONTRACT.md#perbaikan-li-0-dan-kontrak-li-1-offline--22-oktober-2026).

**RESULT:**40 tes LI-1+49 tes LI-0 lulus; hanya synthetic fixtures. Belum
real N1/Overture snapshot parity. D04 capacity, routing/accessibility,
Recount, physical source schema/coverage dan PPAC tetap terbuka. ID berbeda
dengan footprint identik belum diputuskan menjadi satu bangunan fisik;
tidak membuat spatial/entity merge pada task ini.

### D27 — LI-2 offline routing dan batas policy

22 Oktober2026. **Routing diagnostic subset IMPLEMENTED/PASS**, final
accessibility **BLOCKED**, overall LI-2 **PARTIAL**. Tidak ada approval baru
yang tersirat dari passing fixture. Source/contract evidence: N1cell4/10,
SPEC, D02/D03/D05/D10 dan kontrak LI-2.

| Decision | Status aktual dan evidence | Dampak implementasi | Reference yang dapat dikerjakan | Pertanyaan minimum yang belum selesai |
|---|---|---|---|---|
| D02 | OPEN: CFG125m vs docstring100m | Mengubah candidate eligibility dan hasil akhir |125m hanya reference profile, explicit quantity; nilai lain tidak silent default | Apakah125m atau batas lain disetujui untuk access bisnis, dengan bukti apa? |
| D03 | OPEN: CFG10min, strict< setelah round3 vs komentar7min | Mengubah inclusion near threshold | Reference `round(time,3)<10`; bukan threshold production approved | Tetapkan threshold, strictness dan apakah rounding tetap bagian gate |
| D05 | OPEN: nearest reachable, snap tanpa final connector, snap limit unknown | Pemilihan kandidat/target dan total biaya berubah | Explicit nearest-node diagnostics, fixture snap bound, nearest-reachable reference, omitted offset + what-if costs | Pilih selection objective, target/entrance connector treatment dan batas snap/coverage yang sah |
| D10 | OPEN: drive graph+7km/h+straight connector belum membuktikan akses motor/legal | Physical/semantic accessibility tidak bisa disahkan | Directional path, road taxonomy dan explicit fixture permission; label asumsi | Tentukan mode/legal access/private barriers serta bukti connector yang diperlukan |

Keputusan teknis: local normalized directed multigraph JSON, stdlib heapq
Dijkstra (NetworkX tidak tersedia pada environment ini), stable edge IDs,
cost/hops/lexicographic tie-break; tidak ada framework atau auto-reverse.
Access permission adalah anotasi fixture, bukan mapping OSM yang dibuat-buat.
Profile reference mempertahankan125m/10min/7kmh; diagnostic snap50m dalam
fixture bukan rekomendasi produksi. EPSG4326 output geometry dan metric
coordinates dipisahkan. Kontrak lengkap ada pada
[LI-2](AREA_COVERAGE_DATA_CONTRACT.md#li-2--directed-routing-offline-dan-policy-gate).

**RESULT:**41 tes LI-2 +89 regresi LI-0/LI-1 PASS. Main fixture5selected
buildings→5reference routes; final accessible semuanya null. Dua identical
CLI runs menghasilkan stdout byte-identical, tanpa membuang metadata.
Tidak ada real graph/live/physical-access validation.

**Next smallest task:** review dan tetapkan versioned policy D02/D03/D05/D10
menggunakan diagnostic cases, lalu uji gate accessibility offline. LI-3
tidak dimulai otomatis. Ikuti
[roadmap otoritatif](IMPLEMENTATION_ROADMAP.md). Full Area/Recount UI masih
DOCUMENTED dengan blockers di atas; PPAC numerik **BLOCKED**. Source retrieval
tetap tahap berikutnya setelah scope dan policy gate jelas.

### D28 — kebijakan motor dan konfigurasi tunggal

22 Oktober 2026. **REQUIREMENT owner**, memperbarui sebagian OPEN pada D27.
Konfigurasi editable: [location_intelligent_config.py](../notebooks/location_intelligent_config.py).

| Keputusan | Sudah ditetapkan | Masih OPEN |
|---|---|---|
| D02 |125m batas pencarian kandidat eksperimen; akses perlu bukti, jarak dekat saja tidak cukup | Definisi bukti/freshness; entrance versus representative point untuk pencarian |
| D03 |10min skenario bisnis sementara;7km/h asumsi N1 belum tervalidasi | `<`/`<=`, full precision/round3, model kecepatan tiap segmen. Kalimat owner tentang perbedaan N1 terpotong, bukan approval detail yang hilang |
| D05 | Gunakan akses bangunan/pintu toko bila tersedia dan didukung bukti; unknown tidak digunakan | Nearest reachable/minimum total time, multiple entrances, snap limit dan biaya konektor |
| D10 | Motorcycle; gang terbukti mendukung motor boleh; pedestrian-only/tangga/private/unknown tidak boleh; portal/larangan mengikuti pembatasan | Mapping provider/evidence, turn restrictions dan park-and-walk |

Unknown dikeluarkan dari routing sebagai `UNVERIFIED_EXCLUDED_FROM_ROUTING`,
bukan bukti akses fisik mustahil. Tidak ada fallback konektor lurus. Bukti
akses positif tidak membatalkan larangan yang berlaku.

**IMPLEMENTED: configuration snapshot saja**, belum profile routing baru.
`None` berarti belum diputuskan. Export bukan pengganti `li_routing_config_v1`.
LI-2 tetap N1_REFERENCE_ONLY/PARTIAL, final accessible=null. Mengedit file baru
belum mengubah mesin LI-2; baseline dan hasil historis tetap utuh.

### D29 — keputusan lanjutan owner: inclusive time dan motor-only

22 Oktober2026. Policy snapshot direvisi menjadi `motorcycle_experiment_v2`:
`<=10` menit, minimum total time di antara akses valid,7km/h tetap skenario
pembanding, motor-only tanpa segmen berjalan kaki. Keputusan ini memperbarui
bagian D28 yang bersangkutan; baseline N1 tidak berubah.

**ASSUMPTION diterima owner:** lokasi bangunan yang menghadap jalan dianggap
pintu masuk. Ini menggantikan kebutuhan observasi pintu untuk menentukan
lokasi entrance saja; tidak mengizinkan konektor menembus sungai/pagar atau
membatalkan larangan/private. Metode menentukan titik yang menghadap jalan
masih OPEN; representative point di dalam footprint bukan otomatis titik itu.
Tidak mengasumsikan koordinat pusat sebagai entrance tanpa mapping eksplisit.

Masih OPEN: rounding sebelum inclusive gate, batas snap target, geometri/biaya
konektor, mapping evidence/provider dan larangan belok. Kebijakan numerik baru
belum dikonsumsi mesin LI-2; config tidak menjadi bukti akses nyata.

### D30 — snap tanpa batas, asumsi gang/portal dan floor time

22 Oktober2026. Klarifikasi owner menggantikan bagian terkait D28/D29.
Snapshot `motorcycle_experiment_v3` mencatat:

- Snap target toko tidak memiliki batas jarak numerik. `limit_type=UNBOUNDED`
  dengan value=null berarti tidak dibatasi, bukan unresolved atau0. Search
  tetap hanya dalam graph yang benar-benar tersedia; tidak membuat graph
  lengkap atau mengizinkan konektor menembus barrier/larangan.
- Gang yang dipetakan dianggap bisa diakses kecuali ada larangan. Portal
  dianggap dapat dilalui bila tidak ada informasi penutupan/larangan.
  Ini **asumsi akses owner**, bukan observasi izin positif. Private,
  pedestrian-only, tangga dan larangan motor tetap tidak digunakan. Unknown
  di luar pengecualian eksplisit ini masih tidak digunakan.
- Entrance asumsi menghadap kelas jalan tertinggi. Hierarki kelas serta
  prioritas kelas tertinggi versus akses yang valid masih perlu ditetapkan;
  jalan layang/tol terdekat tidak otomatis menjadi akses.
- Jalur yang tidak ditemukan tidak masuk hitungan; reason/coverage tetap
  disimpan agar no-path tidak disamakan dengan data gagal/hilang.
- `floor(total_minutes) <= 10` dipakai untuk keputusan baru. Untuk waktu
  nonnegatif ini setara dengan `total_minutes < 11`:10.9 diterima,11 ditolak.
  Ini bukan full-precision <=10. Panel harus menampilkan waktu asli juga.

Baseline N1 dan engine LI-2 tidak berubah; konfigurasi belum terintegrasi.
Min total time tetap dihitung sebelum floor, agar urutan kandidat tidak
dipengaruhi pembulatan tampilan. Metode entrance, cost konektor, graph motor,
turn restrictions dan scope acquisition masih memerlukan implementasi/test.

### D31 — hierarki eksperimen dan kecepatan seluruh segmen disetujui

Owner menyetujui tiga jawaban lanjutan; policy snapshot menjadi
`motorcycle_experiment_v4`:

1. Validitas akses diperiksa sebelum ranking: pilih jalan tertinggi di antara
   akses yang valid. Sungai/pagar/larangan tetap tidak dikalahkan kelas jalan.
2.7km/h berlaku untuk seluruh segmen, termasuk bangunan–jalan, perjalanan
   jaringan dan jalan–toko. Waktu konektor dihitung dari jarak konektor pada
   kecepatan skenario tersebut; ini asumsi eksperimen, bukan ETA tervalidasi.
3. Hierarki: primary → secondary → tertiary →
   unclassified/residential/living_street → service → track/path yang boleh
   dilalui motor. Elemen dalam satu grup setara. Motorway/trunk tidak otomatis
   diberi izin; larangan motor/private mengalahkan ranking. Detail link roads
   dan tag di luar daftar belum diberi mapping implisit.

Keputusan ranking belum menjawab apakah akses kelas lebih rendah boleh dipilih
jika menghasilkan waktu total lebih rendah. `highest_class_vs_minimum_time_precedence`
tetap null; jangan menyimpulkan tiga jawaban ini sebagai approval prioritas
kelas versus minimum waktu. Geometri entrance/konektor, mapping tags dan
restrictions, serta target/scope acquisition masih terbuka. Config belum
diintegrasikan ke LI-2 dan tidak membuka gate accessibility otomatis.

### D32 — kelas akses tertinggi mendahului waktu perjalanan

Owner memilih primary8min daripada service5min jika keduanya memiliki akses
valid. Ini menyelesaikan konflik D31 dan menggantikan minimum total time
lintas semua kelas pada D29. Snapshot menjadi `motorcycle_experiment_v5`.

Urutan: saring akses valid → pilih kelas tertinggi yang tersedia menurut
hierarki eksperimen → pilih minimum waktu total asli di dalam kelas itu →
terapkan floor(total_min)<=10. Larangan/private/barrier tetap mengalahkan
ranking; jalan tertinggi tanpa akses valid tidak dipilih. Kelas yang setara
berada pada grup ranking yang sama. Tidak menambah fallback ke kelas lebih
rendah hanya karena rute di kelas terpilih lebih lambat.

Perubahan ini baru pada konfigurasi/dokumentasi. Engine LI-2 dan baseline N1
tidak berubah; mapping provider, entrance/connector geometry, penanganan
candidate no-route dan acquisition scope tetap memerlukan task implementasi.

### D33 — round time, drive_service dan sumber ber-versi

Owner mengganti floor dengan `round(total_minutes)<=10` dan memilih
`drive_service` sebagai filter acquisition sebelum policy motor diterapkan.
Policy snapshot menjadi `motorcycle_experiment_v6`. `round` ditafsirkan
persis sebagai Python round tanpa ndigits: nearest integer, ties-to-even.
Contoh9.8→10/pass,10.49→10/pass,10.5→10/pass,10.51→11/fail. Simpan total
asli; rounding hanya untuk threshold, bukan urutan kandidat pada kelas sama.
Baseline N1 round3 strict<10 tidak berubah.

Tabel owner menegaskan frontage kelas tertinggi. Tidak ada instruksi mencabut
D32, sehingga primary8min tetap mengalahkan service5min untuk kandidat akses
sesuai policy. Biaya seluruh segmen tetap7km/h dan izin mengalahkan ranking.

Source plan ditambahkan ke file config: Overture2026-10-21.0/schema2.0.0 dan
OSM via Overpass dengan OSMnx2.1.1/drive_service. Versi tersebut berdasar
metadata publik yang telah diverifikasi, **bukan source snapshot yang sudah
diambil atau kompatibilitas adapter yang telah diuji**. N1 release lama tetap
disimpan. OSM snapshot timestamp, endpoint/version server dan sumber koordinat
aktual belum tersedia; tidak diisi dengan versi library.

drive_service mengecualikan track/path dan motorcar=no, sehingga dapat
menghilangkan ruas yang sebenarnya boleh untuk motor. Policy tidak dapat
mengembalikan ruas yang tidak terambil. Catat keterbatasan ini dan unknown
coverage; perlu keputusan tambahan jika completeness semua gang motor wajib.

### D34 — kapasitas referensi, source probe dan integrasi motor offline

Owner mengotorisasi validasi nyata Overture2026-10-21.0/schema2.0.0 dan
integrasi konfigurasi motor. Jawaban lanjutan menerima lokasi contoh N1
(-6.430669461543375,106.8101931806858) **hanya uji teknis, bukan TGDI**, serta
kapasitas referensi N1 dengan satuan dipisahkan. Policy menjadi v7.

**Pilihan teknis terdokumentasi:** dari pilihan owner turun kelas atau invalid,
gunakan kelas tertinggi yang punya akses valid DAN rute berarah ke toko;
turun kelas hanya bila tidak reachable. Tidak turun kelas hanya karena waktu
lebih lama/di luar batas. *_link mengikuti kelas induk; kelas di luar hierarki
tetap tidak menjadi kandidat frontage. Larangan motor dan private tetap menang.

N1 capacity: rumah standard4 dengan unit unresolved; apartemen estimated
occupied dwelling units; kos estimated occupied rooms; hotel estimated guests.
Occupancy/net-area constants disimpan di file konfigurasi tunggal. Jumlah
campuran dan final business capacity tetap null; D04 belum tertutup sebagai
kapasitas bisnis homogen. Floor/height unknown tidak diganti0 untuk special.

**RESULT nyata:**2623record,1322selected/1301excluded/0rejected. Seluruh1322
selected memiliki null subtype; legacy fallback tidak membuktikan residential.
Subtotal referensi standard5288, bukan KK/penduduk. Tidak ada height/num_floors
pada2623sample. Semua512 STAC item bboxes diperiksa tanpa error; hanya satu
partisi intersect bbox. Query tidak terpotong pada cap10001. Ini kelengkapan
bounded acquisition, bukan bukti semua bangunan fisik telah dipetakan.

Integrasi motor tersedia pada helper/profile baru dengan effective policy hash,
explicit connector geometry/evidence, network permission dan edge-state turn
restrictions. Tidak membuat konektor lurus dari nearest road. Conditional tags
harus sudah dievaluasi oleh adapter/review; parser bahasa conditional dan
pembentukan entrance/barrier otomatis belum diimplementasikan. No unknown
connector menjadi false zero. N1 engine/source/evidence tidak berubah.

LI-1 real-source pass terbatas pada physical columns/types, normalization dan
seleksi sampel, bukan exhaustive provider schema validation. LI-2 PASS untuk
synthetic evidence scenario, real motorcycle graph/connector validation belum
ada. LI-3 adapter/source integration dapat dilanjutkan; jangan menyatakan
full Area/live motor accessibility selesai.

### D35 — LI-3 pilot nyata dan snap toko

Owner mengotorisasi [LI_3_TASK](LI_3_TASK.md) untuk graph/access/connectors/
replay pada N1. Klarifikasi owner: **toko ke jalan valid terdekat**, tanpa
batas numerik; kelas tertinggi tetap untuk kandidat bangunan<=125m. Config v8_li3.

Raw node topology dipertahankan, tanpa junction dari geometric crossings.
Unsupported conditional/via-way turns dikarantina dan tetap unknown.
restrictions_complete berarti setiap restriction ditemukan sudah diaccount
melalui exact normalization atau exclusion quarantine, bukan semua rule
terinterpretasi/seluruh map lengkap. Unknown tidak menjadi izin.

Numeric engineering inputs: dedup projection1e-6m, entrance inset0.01m untuk
roundoff boundary, diagnostic-gap10m tanpa menciptakan edge. Bukan business
threshold baru. Network bbox5500m dari N1 tetap bounded/PARTIAL.

Historical Overpass pin gagal. Dua response sukses berbeda satu menit,
shared elements cocok; non-atomic warning dan raw failures tetap disimpan.
641accepted scenario/7over-time/54no valid connector/620unverified dari1322
selected;2623source rows accounted.201tests PASS;21calculation artifacts
replay identik tanpa network. **Pilot PARTIAL**, bukan production/ETA/
population approval. [Review](LI_3_REVIEW.md).

## D36 — LI-4 terbatas pada snapshot N1 yang dibekukan

23 Oktober 2026, keputusan owner: lanjut persistence/map/table/export tanpa
menunggu seluruh unknown. Semua source rows direkonsiliasi; view/export sama;
reopen tanpa re-fetch; export failure tidak sukses; unknown tidak menjadi
zero/accepted; mixed capacity units tidak dijumlahkan; experimental label wajib.
Review sumber akses tetap pekerjaan terpisah. Implementasi dan bukti:
[LI_4_REVIEW](LI_4_REVIEW.md). Tidak mengubah izin motor, threshold atau unit
bisnis. Tidak mengesahkan produksi, LI-5, Recount atau PPAC.

## D37 — LI-5 offline tanpa polygon manual

Owner mengizinkan penyelesaian engine Recount offline dan meminta kontrak
Traffic/Location untuk review. Digunakan LI5_EXPERIMENT_V1 dengan demo polygon
otomatis; covers/selected/union/no-refetch ditetapkan sebagai profil eksperimen
tercatat, bukan approval batas/kebijakan bisnis produksi. C01–C09 pada
[ENGINE_IO_CONTRACT_DRAFT](ENGINE_IO_CONTRACT_DRAFT.md) tetap DRAFT.
[LI_5_REVIEW](LI_5_REVIEW.md) berisi actual execution. Tidak mengubah Traffic
atau mengesahkan PPAC, UI, refactor, dan universal location support.

## D38 — delegasi evaluasi, GCS dan stabilitas hasil

23 Oktober2026, arahan eksplisit owner: lanjut fase dengan evaluasi mandiri;
owner hanya dapat mereview melalui UI input/output. C01–C09 dipakai sebagai
baseline kerja provisional, bukan approval formal tiap detail. GCS dipilih
untuk video/result; pandu setup sampai CRUD saat milestone storage. Metadata
DB/project/bucket/region/IAM/retention belum dipilih. Kedua engine wajib
mempertahankan hasil stabil pada pekerjaan frozen yang sama; fresh inference
memiliki gate tersendiri, tidak dibuktikan oleh cache. [Workflow](CURRENT_DEVELOPMENT_WORKFLOW.md),
[policy](REPRODUCIBILITY_POLICY.md), [GCS plan](GCS_STORAGE_ONBOARDING_PLAN.md).
Scope task sekarang Markdown saja; tidak membuat code/cloud resources atau
mengklaim GCS/reproducibility production PASS.
