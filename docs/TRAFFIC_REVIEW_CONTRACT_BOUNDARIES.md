# Revisi audit: acuan notebook, kewenangan review dan dependency kontrak

24 Oktober 2026. **PROPOSAL AUDIT — implementasi menunggu persetujuan.**
Melengkapi [audit induk](TRAFFIC_MODULARIZATION_READINESS_AUDIT.md) dan
[rencana file](TRAFFIC_FLOW_AND_FILE_PLAN.md). Tidak mengubah engine.

## 1. Notebook mana yang menjadi acuan?

Ya, basisnya implementasi Traffic Counter terbaru yang dipilih, termasuk
perbaikan adapter konteks person/kendaraan, cache codec dan jalur anotasi. Tetapi
**latest editor tidak otomatis menjadi golden**. Tiga hal perlu dibedakan:

| Acuan | Cara memakainya |
|---|---|
| Implementasi kandidat terbaru | Source readable notebook dan modul di Git, beserta commit/source SHA dan config; menjadi kandidat yang akan dipindahkan |
| Baseline yang sudah mempunyai bukti | Actual input/measurement, native result, config/model/runtime dan receipt dari versi yang benar-benar dijalankan; menjadi oracle parity pada scope tersebut |
| Working tree/draft atau quick-save yang belum diuji | Dicatat sebagai candidate; tidak diklaim tervalidasi hanya karena paling baru |

Contoh lineage yang sudah tercatat: run readable T7SL versi5 berasal dari
`notebooks/10_t7sl_readable_resume.ipynb` pada source saat submission; editor asli
`t7sl-fresh-modular-traffic-batch` kemudian menerima quick-save versi6 yang
menampilkan jalur anotasi terbaru. Itu dua version namespace berbeda. Notebook
CPU `10b_t7sl_full_annotation.ipynb` merupakan consumer hasil tersimpan, bukan
baseline inference baru. Nomor versi tidak dibandingkan lintas notebook untuk
menentukan mana yang lebih benar.

M0 wajib mencatat tuple: notebook ID + version/run ID + source SHA/commit +
input SHA/frame scope + geometry/review revision + model/config/runtime +
native/result/manifest refs. Runtime receipt menentukan status pengujian; nama
file, editor terbaru atau scheduler COMPLETE saja tidak cukup.

Jika fitur terbaru belum mempunyai receipt aktual, bagian yang belum teruji
tetap candidate/BLOCKED pada capability terkait. Tidak mengganti source baru
dengan algoritme lama diam-diam, dan tidak mengangkat asumsi sukses delapan video
menjadi bukti. Golden machine dan review-assisted tetap terpisah. Hash/code
version baru diperbolehkan; perilaku native acuan harus dipertahankan.

## 2. Pecah review menjadi dua modul dan dua kontrak berbeda

`domain/review.py` tunggal di proposal sebelumnya **dibatalkan**. Penggantinya:

| Aspek | `domain/source_context_review.py` | `domain/candidate_adjudication.py` |
|---|---|---|
| Tahap | PRE_RESOLVER | POST_COUNTING |
| Input bertipe | Measured frames, `SourceContextReview`, verified source/geometry/profile refs | Immutable machine snapshot, `CandidateAdjudication`, candidate/baseline/evidence refs |
| Fungsi | Menerapkan klaim konteks yang sudah diverifikasi pada frame/episode tertentu | Menyelesaikan kandidat yang sudah ada, sesuai capability finalizer acuan |
| Output | Derived context patch + audit trail; raw measurement tetap disimpan | Adjudication result/reviewed snapshot baru + audit trail; machine lama tetap utuh |
| Contoh yang diperbolehkan | Split raw-ID context, klaim same-unit, rider-parent, positive pedestrian role atau derived category dalam scope berbukti | Pada capability saat ini: menutup kandidat sebagai komponen tidak independen, `resolved_not_eligible/+0`; unresolved tetap pending |
| Yang tidak diperbolehkan | Menulis accepted event, mengubah raw bbox/class/index/frame, mengesahkan gap/prediksi sebagai pengukuran, mengubah geometry tanpa revision | Membuat kandidat/passage/crossing baru, mengubah raw role history atau geometri, menggabungkan ID global, mempromosikan pending menjadi accepted tanpa proses domain baru |

I/O file dan pembuktian integritas artifact dilakukan application/adapter. Modul
domain hanya menerima data dan evidence tervalidasi, tidak membaca PNG/GCS/Git
atau memanggil model sendiri. `contracts/review.py` hanya mendefinisikan tipe;
tidak menjalankan kedua proses tersebut.

Alur yang diizinkan:

```text
Frozen measurements
  → verifikasi source-context review jika capability/profile mengizinkan
  → derived context (raw evidence immutable)
  → resolver identity/role
  → eligibility/geometri/crossing/counting/finalization
  → machine atau source-review-assisted snapshot
  → verifikasi candidate adjudication
  → reviewed snapshot baru
```

Reviewer dapat mengubah konteks yang memengaruhi hasil re-evaluasi, tetapi
**tidak memiliki kewenangan mengesahkan crossing**. Crossing terukur tetap harus
dibuktikan oleh titik BC sumber dan geometri. Kategori/identitas yang benar
tidak menggantikan crossing yang tidak valid. Source review tidak mengubah
raw class; gunakan derived/resolved class dengan provenance.

Jika adjudikasi menemukan salah kategori/identitas yang membutuhkan perubahan
trajectory/eligibility, keluarkan kebutuhan source-context review dan replay
baru dari measurement frozen. Jangan memanggil pre-review secara tersembunyi
dari post-adjudicator atau mengedit event menjadi accepted. Finalizer saat ini
tidak diperluas menjadi fitur penerimaan manual generik lewat refactor.

### Contoh pengaman

- Raw ID166 berganti objek/kelas: pre-review dapat memberi batas konteks berbukti;
  resolver/counting dijalankan ulang untuk branch/revision baru. Post-adjudicator
  tidak boleh sekadar mengganti ID atau menghapus crossing yang berkonflik.
- Person857 dinyatakan rider856 pada interval tertentu: pre-review menambah
  hubungan pada interval berbukti saja. Kandidat komponen yang sudah ada dapat
  ditutup +0 melalui adjudikasi yang cocok scope. Keduanya tidak memberikan
  kendaraan parent +1 jika parent tidak memiliki bukti passage yang valid.
- Kendaraan menghilang sebelum garis: klaim kategori/identitas tidak membuat
  interval hilang menjadi crossing terukur. Estimasi tetap mengikuti policy;
  adjudikasi tidak boleh mengubah `measured_crossing=false` menjadi true.

### Kontrak review

`SourceContextReviewV1` memuat schema/version, phase PRE_RESOLVER, source hashes,
frame/detection/episode scope, action spesifik, evidence refs dan review origin.
`CandidateAdjudicationV1` memuat phase POST_COUNTING, baseline native SHA,
candidate/passage/episode refs, evidence refs dan action yang didukung.
Kedua action enum terpisah. Field unknown, phase salah dan payload tipe lain
ditolak. Reviewer identity/status manusia versus AI tetap dicatat.

Fresh review-assisted masih merupakan capability tersendiri: tidak otomatis
aktif hanya karena proposal interface ada. Profil yang belum mendukungnya
menolak request; tidak memakai overlay TGDI pada video T7SL.

## 3. Contracts menjadi package data, bukan pusat semua logika

Proposal delapan file:

| File | Batas |
|---|---|
| `contracts/source.py` | Artifact/source refs, source identity dan frame scope |
| `contracts/measurement.py` | MeasuredFrame, raw observation dan source measurement refs |
| `contracts/identity.py` | Episode/role/relation DTO dengan evidence scope |
| `contracts/passage.py` | Candidate/passages/evidence/status DTO |
| `contracts/execution.py` | Request, operasi, branch, capability dan execution identity |
| `contracts/review.py` | Dua review DTO/action enum terpisah, tanpa implementasi review |
| `contracts/results.py` | Video/batch/result envelopes dan provenance |
| `contracts/versioning.py` | Serializer/decoder registry, versi yang didukung dan mapping compatibility |

**PROPOSAL TEKNIS:** gunakan immutable typed DTO, misalnya stdlib frozen
dataclasses, Enum, tuple dan typed references. Pilihan framework lain belum
ditetapkan. `dict[str, Any]` tidak menjadi kontrak publik tanpa validator.
Typed hints harus disertai runtime validation saat masuk dari JSON dan static
type-check gate; type hint saja tidak memvalidasi data dari luar.

DTO menyatakan data, bukan algoritme eligibility, threshold atau rule crossing.
Module tidak menginisialisasi GPU, membaca config file, mengakses storage atau
mengimpor application/domain. `__init__.py` tipis; jangan eager-import semua
submodule atau memakai lazy import untuk menyembunyikan siklus.

Setiap envelope mempunyai schema identifier/version eksplisit. Metadata operasi
dipisahkan dari asal measurement: input fresh-origin tidak berarti replay baru
menjalankan inference. Measurement origin/producer dan operation executed adalah
field/tipe berbeda. Known immutable source refs menyimpan hash, bukan mutable
object yang bisa berubah sesudah validasi.

Legacy notebook/native formats tetap dibaca lewat adapter versioned. Registry
hanya menerima versi yang dikenal; versi unknown ditolak, bukan ditebak atau
dianggap versi terkini. Perubahan arti/required fields membutuhkan versi baru
dan mapping yang diuji. Raw IDs, frame indices dan native event IDs tidak berubah
karena nama class atau file diganti. Versi bukan pengganti checksum input.

## 4. Config menjadi empat tanggung jawab terbatas

| File | Fungsi | Tidak berwenang |
|---|---|---|
| `config/schema.py` | Typed immutable declared/effective config dan schema version | Tidak membaca file, memuat weights atau mengubah state |
| `config/profiles.py` | Profil/version dan aturan merge/override yang eksplisit | Tidak memilih threshold berdasarkan jumlah pending atau hasil video |
| `config/validation.py` | Validasi nilai dan kombinasi/capability config | Tidak menjalankan crossing/counting untuk menentukan apakah config dianggap benar |
| `config/loader.py` | Baca artifact, dispatch versi, resolve overrides, validate, freeze/fingerprint | Tidak menjalankan job/model, menulis ulang config input atau menyisipkan fallback |

Contoh application signature konseptual, **bukan implementasi yang sudah dibuat**:

```python
load_effective_config(config_ref: ArtifactRef) -> EffectiveConfig
process_video(request: VideoRequest, config: EffectiveConfig) -> VideoResult
apply_source_context(frames: MeasuredSequence,
                     review: SourceContextReviewV1) -> ContextualizedSequence
adjudicate_candidate(snapshot: MachineSnapshot,
                     review: CandidateAdjudicationV1) -> AdjudicationResult
```

Config yang diminta dan config efektif disimpan terpisah. Prioritas merge harus
terdokumentasi; kandidat aman: base profile version → per-video overrides →
explicit job overrides yang diizinkan → validasi → immutable effective config.
Tidak boleh default/override dari global notebook state atau environment variable
tak tercatat. Frozen effective config yang sudah dipakai baseline tidak disusun
ulang dengan default terbaru. Perubahan model/filter/geometry/threshold tetap
eksperimen baru, bukan implikasi pemindahan loader.

## 5. Dependency DAG yang diwajibkan

Panah berarti **mengimpor/menggunakan**, bukan alur data:

```text
contracts.measurement → contracts.source
contracts.identity   → contracts.measurement, contracts.source
contracts.passage    → contracts.identity, contracts.measurement
contracts.execution  → contracts.source
contracts.review     → contracts.passage, contracts.identity, contracts.source
contracts.results    → contracts.execution, contracts.review, contracts.passage
contracts.versioning → DTO modules di atas (DTO tidak mengimpor registry)

config.schema        → contracts.source
config.profiles      → config.schema
config.validation    → config.schema, primitive contracts
config.loader        → config.profiles, config.validation, contracts.versioning

domain               → contracts + pure internal domain helpers
adapters             → contracts + infrastructure libraries
application          → domain, adapters/ports, config.loader
UI/backend/CLI       → application facade
```

Domain menerima config/nilai tervalidasi melalui argument, tidak mengimpor
loader. Execution request merujuk config sebagai artifact ref; contracts tidak
mengimpor config sehingga tidak terjadi contracts↔config. Domain dependency
antar identity/role/crossing tetap dipetakan terhadap algoritme acuan; bila ada
interaksi berulang, coordinator application memanggil tahap eksplisit dengan
data, bukan kedua modul saling mengimpor facade.

Jangan memindahkan siklus ke registry dinamis, global singleton atau callback
yang diam-diam memanggil pipeline. Tipe data tidak mengimpor service pemakainya.

## 6. Gate tambahan sebelum migrasi diterima

1. Uji pertukaran payload: source review ke adjudicator dan sebaliknya harus
   ditolak; fase/action unknown atau capability unsupported juga ditolak.
2. Pre-review tidak mengubah raw ID/class/bbox/frame/hash. Derived patch/revision
   terlacak; source scope salah/terlalu luas ditolak.
3. Post-adjudication +0 terikat baseline/candidate/source frame; tidak membuat
   event, mempromosikan crossing atau mengubah episode history. Command yang
   mencoba `force_accept`/`measured=true` ditolak.
4. Kasus category/identity correction harus menghasilkan replay revision, bukan
   mutable edit snapshot. Positive role tidak otomatis +1.
5. Capability parity terpisah: machine tanpa review, historical review context,
   pre-reviewed, post-adjudicated, dan kombinasi yang memang didukung diuji
   terhadap golden masing-masing; tidak mencampur total antarbranch.
6. Serializer/decoder roundtrip, unknown-version rejection dan known legacy
   mapping lulus tanpa kehilangan frame/source refs, null/status atau evidence.
7. Static type check dan runtime JSON validation sepakat; frozen DTO/config
   tidak dapat dimutasi melalui nested list/dict. Boundary codec mengubah nested
   collections menjadi bentuk immutable atau salinan terkontrol.
8. Dependency graph diperiksa di CI, import setiap submodule/entry point diuji
   dari clean process di luar repo; no circular import, GPU/file/network side
   effect saat import contract/config schema/domain.
9. Config precedence, unsupported override rejection dan effective config hash
   stabil diuji. Nilai environment yang memengaruhi hasil masuk provenance.
10. Seluruh AC01–AC11 audit induk tetap berlaku. Tidak mengubah golden untuk
    menutupi perubahan keputusan akibat pemisahan file.

## 7. Dampak jumlah file dan status persetujuan

Proposal lama26file fungsional berubah menjadi **37file fungsional**:
contracts1→8 (+7), config1→4 (+3), review1→2 (+1). Tambahan package contracts/config
membuat initializer4→6. Total target package Traffic menjadi **43file Python**,
bukan total repository. Test/schema/compatibility sementara/shared/storage/CLI
dan engine Location tetap di luar hitungan tersebut.

Tambahan file memiliki pemilik data/kewenangan yang spesifik. Ini tidak
mengharuskan file per class atau pemecahan helper kecil. Target dapat direvisi
tercatat saat review interface; yang wajib adalah batas tanggung jawab, parity
dan dependency DAG. Jumlah file bukan ukuran keberhasilan modularisasi.

**Status:** dua masalah desain sudah diperbaiki di dokumen audit. Belum ada
migrasi kode, pembuatan branch refactor atau kelulusan acceptance baru. Persetujuan
audit tetap diperlukan sebelum implementasi rancangan ini.


## Pelaksanaan audit yang diotorisasi

Instruksi owner berikutnya mengotorisasi migrasi ini. Status proposal/menunggu
persetujuan di atas merupakan checkpoint historis; hasil implementasi, keputusan
dan bukti uji ada di [release migrasi](TRAFFIC_MODULARIZATION_RELEASE.md).
