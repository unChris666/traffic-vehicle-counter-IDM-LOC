# Kontrak input/output Traffic dan Location — BASELINE PROVISIONAL

Versi dokumen `engine_io_contract/1.0.0-draft.1`, 23 Oktober 2026.
**Baseline interface provisional di bawah delegasi evaluasi teknis owner**,
bukan API/backend/validator yang sudah berjalan. Owner mereview melalui UI;
review Markdown bukan gate rutin. Ini bukan klaim C01–C09 disetujui formal
satu per satu atau standar produksi tervalidasi. Adapter offline scoped ke format
notebook kini diimplementasikan pada `src/traffic_location`; schema runtime dan
bukti kesetaraan dijelaskan dalam [review modularisasi](ENGINE_MODULARIZATION_REVIEW.md).
Draft ini tetap lebih luas daripada boundary CLI yang sudah berjalan. Format
historis dan event asli tidak diubah. LI-5 eksperimen tersedia secara terpisah.

## Keputusan kerja yang dapat ditinjau melalui UI

| No | Baseline kerja provisional | Pengaman/dampak |
|---|---|---|
| C01 | Dua engine independen: Traffic dan Location; backend hanya mengorkestrasi | UI/backend tidak menduplikasi algoritme counting/routing |
| C02 | Status eksekusi, kualitas hasil, cakupan dan keputusan objek dipisahkan | Job selesai tidak otomatis berarti semua objek terselesaikan atau production-valid |
| C03 | Null+alasan untuk unknown; 0 hanya hasil evaluasi yang berhasil | Missing video/source/role/route tidak menjadi false zero |
| C04 | Traffic measured dan estimated disajikan terpisah; total gabungan hanya field eksplisit sesuai policy | Estimasi timeout/gap bukan crossing terukur |
| C05 | Machine dan reviewed adalah alternatif hasil dengan lineage | Tidak menjumlahkan keduanya; reviewed tidak menghapus baseline |
| C06 | Reopen/replay memakai frozen inputs; refresh eksplisit menghasilkan versi baru | Koordinat sama saja tidak menjamin sumber live sama |
| C07 | Location accepted adalah keputusan skenario; nilai waktu/kapasitas adalah modeled | Tidak menyebut 7km/h sebagai measured ETA atau unit unresolved sebagai KK |
| C08 | Recount v1 memakai selected universe, covers, union dedup, no refetch; scope eksperimen dulu | All source rows tetap diaudit; unselected tidak diam-diam menjadi eligible |
| C09 | Versioned JSON manifests + artifact refs; database/object storage hanya adapter | Engine tidak tergantung framework UI atau vendor penyimpanan |

Arahan owner terbaru mengizinkan kelanjutan teknis dengan evaluasi mandiri
berdasarkan C01–C09 secara provisional. Jangan menunggu approval Markdown
sebelum menyiapkan schemas/adapters, modularisasi dan UI bertahap. Perubahan
kontrak harus versioned dan diuji; fakta/bisnis yang unknown tidak boleh
ditetapkan tanpa bukti. [Workflow aktif](CURRENT_DEVELOPMENT_WORKFLOW.md).

## 1. Envelope input bersama

Field wajib yang diusulkan:

| Field | Tipe/arti |
|---|---|
| `contract_version` | `engine_io_contract/1.0.0-draft.1` |
| `request_id` | ID idempotency permintaan; retry sama tidak menciptakan job logis baru |
| `engine` | `TRAFFIC` atau `LOCATION` |
| `operation` | Traffic: `PROCESS`, `REPLAY`, `RENDER`; Location: `AREA`, `RECOUNT`, `REOPEN` |
| `target` | `target_id`, kode toko, coordinate+CRS+source bila relevan; unknown mempunyai reason |
| `input_refs` | Daftar immutable ArtifactRef: `artifact_id`, locator stabil, sha256, bytes, media_type, source version |
| `config_ref` | Config tervalidasi, policy version, canonical hash; bukan referensi mutable ke file terakhir |
| `engine_ref` | Engine version, source/code hash, environment lock hash |
| `execution_profile` | CPU/GPU eksplisit, actual backend wajib direkam pada output; no silent model/frame/reid fallback |
| `parent_result_ref` | Null atau frozen result yang dipakai untuk replay/review/recount/re-render |
| `mode` | `FROZEN` atau `REFRESH`; REFRESH hanya untuk operation yang memerlukan retrieval/inference baru |

Koordinat Traffic boleh null+reason untuk analisis video lokal bila policy
mengizinkan; tidak boleh disambung ke fitur Location/PPAC sebelum target match.
Location AREA wajib target koordinat finite dan CRS. Lokasi baru perlu sources
sesuai coverage, bukan relabel input N1. RECOUNT/REOPEN wajib parent snapshot.

ArtifactRef tidak menyimpan token, password atau URL bertanda tangan sementara
sebagai identitas permanen. Provider video/result ditetapkan owner: Google
Cloud Storage. Local adapter
untuk development tetap boleh, dengan label local. ArtifactRef GCS mengikat
bucket/object/generation/bytes/SHA256; signed URL bukan identity permanen.
Metadata database belum dipilih. Checksum mengikat isi. Credential/storage
download ditangani adapter/backend.

## 2. Envelope output bersama

| Field | Isi wajib |
|---|---|
| `contract_version`, `engine`, `operation` | Sesuai request dan versi adapter yang benar-benar digunakan |
| `request_id`, `job_id`, `result_id`, `result_revision` | Identitas permintaan, eksekusi, dan hasil immutable |
| `execution_status` | Enum eksekusi di bawah |
| `result_quality` | `COMPLETE_WITHIN_DECLARED_SCOPE`, `PARTIAL`, `NOT_EVALUATED` |
| `validation_level` | `SOFTWARE_FIXTURE`, `TECHNICAL_PILOT`, `AUDITED_SCOPE`, `PRODUCTION_VALIDATED`; bukti wajib untuk klaim |
| `scope` | Target, sumber/frame/area/period yang diminta dan benar-benar diproses, alasan gap |
| `summary` | Output domain berunit; null bila tidak dapat dievaluasi |
| `artifacts` | Daftar berkas finalized beserta checksum/bytes/schema/role |
| `diagnostics` | Code stabil, severity, scope/object ref, reason, evidence refs; pesan presentasi boleh berubah |
| `versions` | Schema/engine/code/environment/policy/model/source/polygon/result versions+hashes yang berlaku |
| `lineage` | Input refs, parent, machine/review branch, review overlay hash dan dependency DAG |
| `reproducibility` | Input fingerprint, actual device/backend/provider, deterministic settings, replay evidence bila ada |

`result_id`/revision immutable. Input fingerprint membedakan sumber, target,
config, policy, code/model dan environment; tidak sekadar longitude/latitude.
Timestamp/job ID dapat berbeda pada eksekusi ulang. Kesetaraan kalkulasi dinilai
pada outputs domain yang didefinisikan, bukan memaksa timestamp identik.

### Status eksekusi dan kualitas

| `execution_status` | Makna |
|---|---|
| NOT_RUN / QUEUED / RUNNING | Belum ada hasil final |
| BLOCKED | Input/policy/dependency wajib belum tersedia; summary yang belum dievaluasi null |
| SUCCEEDED | Output wajib telah finalized dan diverifikasi; kualitas bisa PARTIAL |
| FAILED | Eksekusi/output wajib gagal; intermediate artifacts tidak berlabel final |
| CANCELLED | Dihentikan; processed scope dan intermediate dibedakan dari final |

Contoh: semua frame berhasil diproses tetapi ada pending identity → eksekusi
SUCCEEDED, kualitas PARTIAL. Provider gagal diambil → FAILED/BLOCKED menurut
jenis kegagalan; bukan bangunan0. Empty query yang sukses dan mencakup scope
request dapat menghasilkan0 dengan bukti empty yang eksplisit.

Status existing SUCCEEDED_WITH_WARNINGS/PARTIAL dipetakan oleh **adapter versi
baru**, sambil menyimpan `native_status`. Belum melakukan migrasi. Package
publication status LI-4/LI-5 tidak disamakan dengan physical/business validity.

## 3. Kontrak Traffic Engine

### Input domain

- VideoRef: hash, actual filename, size; decoder/software; metadata probe
  FPS/frame count/duration/codec beserta unknown reasons. Source frame index
  menjadi acuan; frame skipping tidak boleh implisit.
- GeometryRef per video: reference width/height, polygons A/B, finite counting
  segment+margin, BC anchor, direction mapping, reviewed/source hash.
- PreprocessingRef: RAW atau profile per video+version/hash, urutan dan angka
  gamma/exposure/sharpness/brightness/shadows; preview dan inference setara.
- ModelRef: detector asset+hash, label map, library; tracker config; ReID asset,
  provider/config. Mengganti salah satu menghasilkan experiment/result baru.
- CountingPolicyRef: identity episodes, role/unit/category, eligibility,
  dedup/genuine return, timeout60 **source frames**, gap rules, evidence mapping.
- Run scope: whole video atau explicit frame interval; boundary state/context
  diperlukan untuk interval. Night/CPU scopes tidak dianggap validated hanya
  karena GPU/morning baseline berhasil.

### Output domain

- Per-frame/process coverage ledger, track/episode/source-ID lineage dan alasan
  pemutusan/penyambungan. Tracker raw ID berbeda dari physical identity dan
  passage ID tampilan.
- Passage ledger: `passage_id`, physical-unit/episode ref, raw IDs+frame scopes,
  category, direction, decision frame, origin/timer refs, crossing source refs,
  evidence kind, disposition, reasons, dedup group dan version/branch.
- Kategori bisnis saat ini: PEDESTRIAN/MOTORCYCLE/CAR/TRUCK/BUS; role person
  RIDER/PASSENGER/PEDESTRIAN/UNKNOWN berada pada interval berbukti. Rider+0;
  motorcycle+rider/passenger adalah satu unit, dengan hubungan parent eksplisit.
- Agregat per kategori/arah/video dan observasi waktu, dengan `accepted_measured`,
  `accepted_estimated`, `pending`, `invalid`, `rejected_non_unit` terpisah.
  Reason non-unit berbeda dari kegagalan processing. `accepted_total` hanya
  penjumlahan dua accepted buckets yang disjoint dalam branch/policy yang sama.
- Annotated video, readable source IDs/display IDs, source frame/time, unit
  parent, evidence/disposition logs, report dan audit frame refs.

### Measured/estimated dan unknown

EvidenceKind proposed: `MEASURED_CROSSING`, `ESTIMATED_TIMEOUT`,
`ESTIMATED_OCCLUSION_TRANSITION`, `INSUFFICIENT`, `NOT_APPLICABLE`.
Ini taksonomi **draf adapter**, bukan klaim seluruh event existing sudah dipetakan.
Source crossing_kind asli wajib disimpan. Jika mapping tidak jelas, record
unknown/diagnostic; jangan menebak measured dari accepted/display ID.

Timeout/gap/occlusion inference tidak menjadi measured hanya karena review
menyetujui kategori/identitas. Pending/invalid/non-unit tidak masuk accepted.
Estimasi hanya diterima jika policy dan eligibility/identity safeguards lolos.
Review dapat menyelesaikan pending sebagai +0; tidak harus menambah accepted.

Machine dan reviewed memakai hasil/branch berbeda. Annotasi ulang tidak
menciptakan event counting baru. Traffic sample tidak otomatis diproyeksikan
menjadi traffic24jam, orang unik atau transaksi toko.

## 4. Kontrak Location Engine

### Input domain

- TargetRef+provenance, projected metric CRS yang sesuai, analysis domain.
- BuildingSnapshotRef dan graph/barrier/turn/access snapshot, provider/release/
  schema/as-of/coverage/query/projection/software hashes; valid-empty terpisah
  dari retrieval failure.
- Routing/access/capacity policy refs: engine menghormati konfigurasi motor
  versi yang dipilih. Angka7km/h dan waktu round<=10 tetap asumsi skenario.
- RECOUNT: verified parent result, polygon FeatureCollection WGS84 [lon,lat],
  polygon_id/revision/hash/claim, universe/predicate/boundary/overlap/coverage
  policy. Source-boundary bisnis tidak disimpulkan dari polygon demo otomatis.

### Output domain

- Semua source rows direkonsiliasi: selected/excluded/invalid dan alasan.
- Keputusan per bangunan: ACCEPTED, OVER_TIME_LIMIT, NO_VALID_CONNECTOR,
  NO_ROUTE, ACCESS_UNVERIFIED, SOURCE_MISSING, RETRIEVAL_FAILED,
  INVALID_GEOMETRY, PROCESSING_ERROR, EXCLUDED_BY_SELECTION sesuai stage.
- Route/candidate/connectors dengan source lineage, selected road class, biaya
  setiap segmen, original/full-precision dan threshold-rounded time, asumsi,
  known restrictions/quarantine. Unknown route boleh null, bukan false0.
- Kapasitas: nilai+unit/model/source/assumption per bangunan; subtotal per status
  dan unit, known subtotal+unknown numeric count; mixed/final business total
  null jika unit belum disahkan. UNKNOWN unit berbeda dari null numeric value.
- RECOUNT: per-source-key membership, per-polygon subtotal, union unique keys,
  delta revisi, coverage relation, inherited source quality. Polygon edit
  tidak mengubah original routing/capacity/decision atau mengambil sumber baru.
- Export JSON/CSV/GeoJSON dan offline map/table merupakan view hasil sama,
  bukan engine alternatif.

Location mempunyai `SOURCE_OBSERVATION`, `MODELED_SCENARIO`, `OWNER_ASSUMPTION`,
`UNVERIFIED` untuk evidence/claim, **tidak memakai MEASURED_CROSSING**. Geometri
sumber diobservasi/provider-derived tidak membuktikan modeled accessibility.

## 5. Konsistensi dan modularisasi

Engine menghitung domain; backend menyimpan job/auth/akses artefak; UI membaca
hasil dan mengirim konfigurasi/revisi. PPAC adalah konsumen dengan formula
tersendiri, belum diimplementasikan pada kontrak ini. Fitur lintas engine wajib
same target/period/unit/branch gates; Area PARTIAL tidak otomatis membatalkan
Traffic yang valid, tetapi konsumen harus menghormati missing prerequisites.

No silent fallback: video gagal bukan0; missing building/road access bukan
inaccessible fact; pending bukan accepted; unknown role bukan pedestrian;
mixed-unit kapasitas bukan population. Actual CPU/GPU provider wajib tercatat.
Hasil GPU dan CPU tidak diklaim byte-identical tanpa uji backend yang relevan.

Setiap perubahan incompatible menaikkan major contract/schema version. Perubahan
policy/model/source/polygon/review membuat revision/run baru, bukan mengedit
hasil lama. Sebelum refactor, golden outputs per domain dan validation gates
harus tersedia. Draft ini tidak memindahkan notebook ke framework atau DB.

## 6. Gate acceptance implementasi berikutnya

Dalam delegasi saat ini, engineer melanjutkan evaluasi dan membuat
machine-readable schemas, schema validators/adapters,
negative fixtures untuk missing/partial/unknown/unit/branch/target mismatches,
round-trip artifact refs dan golden parity. Baru kemudian refactor boundaries.
**Belum ada klaim validators/adapters untuk draft envelope ini sudah dibuat.**

## Workflow dan stabilitas terkini

[REPRODUCIBILITY_POLICY](REPRODUCIBILITY_POLICY.md) berlaku: FROZEN normal,
reopen/replay/fresh inference/refresh dibedakan; retry tidak menambah hitungan.
Update ini tidak mengimplementasikan lookup/cache/API. [GCS plan](GCS_STORAGE_ONBOARDING_PLAN.md)
akan memandu owner saat storage milestone dengan CRUD sandbox terverifikasi.
Kontrak tetap versioned draft/provisional sampai evidence schema/adapters dan
review UI mendukung finalisasi; tidak memberi klaim akurasi atau legal access.
