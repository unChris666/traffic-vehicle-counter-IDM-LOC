<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Traffic modularization — release candidate 0.2.0rc1

24 Oktober 2026. **IMPLEMENTASI DIOTORISASI** oleh instruksi owner:
freeze acuan → kontrak/facade → adapter → domain → runtime/batch →
renderer/export/storage → release candidate. Branch:
`refactor/traffic-modularization-v2`.

Dokumen ini menggantikan status “menunggu approval” pada audit sebelumnya untuk
scope implementasi ini. Migrasi mempertahankan makna counting dan tidak memilih
model, threshold, kebijakan identitas atau kategori baru.

## Acuan dan batas bukti

[Freeze](../results/traffic_migration/20261024/frozen.json) mengikat source archive
sebelum migrasi, commit `1d878d8516ae097c278590f486769182c448e321`, hash seluruh
field native, source identity dan hasil aktual berikut:

- Delapan T7SL dari producer Kaggle `chrisbiran/t7sl-traffic-counter-readable`,
  versi5, **71.380 frame sumber**. Quicksave editor versi6 pada namespace notebook
  lain bukan pengganti baseline executed ini. Measurement lama5video dan fresh
  baru3video sama-sama mempunyai producer receipt yang diverifikasi.
- TGDI machine dan review-assisted pada golden23Oktober. Machine mempunyai
  historical source-context review yang eksplisit; bukan klaim model unassisted.
- Source `_kernel/` dan notebook/evidence historis tidak diubah. Archive dapat
  dibuka kembali untuk memeriksa source oracle sebelum migrasi.

Angka acuan T7SL: **664 passage accepted =642 measured+22 estimated**, pending294,
invalid321. Motorcycle537, car78, truck44, bus5, pedestrian0. Angka ini hasil mesin
pada sampel rekaman, bukan bukti jumlah kendaraan fisik benar atau traffic24jam.
Pending/invalid tetap di luar subtotal. Tidak ada klaim peningkatan akurasi.

## Implementasi dan keputusan teknis

| Tahap | Implementasi | Keputusan dan pengaman |
|---|---|---|
| Freeze | Source zip, native/source/field SHA, actual producer refs | Oracle immutable; tidak mengganti golden agar tes lulus |
| Kontrak/facade | `contracts/`, `config/`, `application.pipeline.process_video` | Frozen dataclass, canonical immutable JSON, enum, dispatcher versi; unknown schema ditolak |
| Adapter | `adapters/` | Notebook/fresh tetap berbeda, validasi raw bbox/link/BC dan source hash dipertahankan |
| Domain | `domain/` dan kernel compatibility | Urutan identity/role → eligibility/crossing/counting → finalization dipertahankan. Jangan menjalankan substage dua kali |
| Runtime/batch | `application.runtime`, `application.batch` | Proses model baru per video; locked8sources, full frame inventory, model/filter/tracker/policy hash dan producer receipt |
| Renderer/export | `adapters.renderer`, `adapters.exports` | Consumer hasil immutable; ubah panel tidak mengesahkan crossing atau menjalankan counting |
| Storage | `ArtifactStore`, `LocalArtifactStore` | Atomic publish, manifest/hash, retry idempotent, JSON+CSV+binary/video, kegagalan tidak menjadi sukses |
| Release | Wheel/sdist `0.2.0rc1`, tes, gate import/dependency | RC teknis dalam scope teruji; bukan pernyataan siap produksi |

Jumlah target tetap **37file fungsional+6initializer=43file**. Sembilan entry/helper
compatibility yang sudah ada tetap disimpan, selain kernel historis. Kernel
adalah implementation detail; konsumen baru memakai facade. Ekstraksi algoritme
internal kernel menjadi banyak fungsi baru sengaja tidak digabung dengan migrasi
ini: parity lebih mudah diaudit tanpa menulis ulang algoritme yang tervalidasi.
File `domain/eligibility`, `crossing`, `role_association` memberikan view/port
terbatas; keputusan atomic tetap dijalankan oleh kernel counting/resolver.

Tidak ada `domain/review.py` tunggal. **Source context PRE_RESOLVER** boleh memberi
konteks turunan dalam scope berbukti, tanpa mengubah pengukuran mentah.
**Candidate adjudication POST_COUNTING** hanya menyelesaikan kandidat pending
komponen sebagai `resolved_not_eligible/+0`, sesuai finalizer acuan. Tidak boleh
membuat passage atau mengubah gap/prediksi menjadi crossing terukur. Fresh
review-assisted belum didukung dan ditolak, bukan memakai overlay TGDI otomatis.

Policy artifact frozen menjadi sumber konfigurasi efektif. Precedence eksplisit:
base → video override → job override; unknown/protected key dan perubahan tipe
ditolak. Untuk eksekusi, config efektif harus sama dengan policy artifact yang
hash-bound pada request. Override untuk eksperimen harus disimpan sebagai policy
revision/request baru. Tidak ada default dari state notebook atau environment
yang mengubah threshold diam-diam.

Kontrak hasil **v2** memisahkan `operation_executed=count_replay` dari
`measurement_origin=fresh_inference|notebook_measurement`.
`fresh_inference_executed=false` pada counting replay, walaupun measurement
berasal dari inference GPU sebelumnya. Operasi fresh mempunyai receipt sendiri.
Native event/category/direction/evidence/disposition tetap menjadi oracle parity;
wrapper version/code hash berubah secara eksplisit akibat migrasi.

## Cara menjalankan

```bash
python -m pip install '.[validation,migration]'
python -m traffic_location traffic \
  --request /path/request.json --root /path/input-root \
  --output /path/results/job-revision
python -m traffic_location reopen --output /path/results/job-revision
python -m unittest discover -s tests -v
python -m mypy --strict --follow-imports=silent \
  src/traffic_location/traffic/contracts src/traffic_location/traffic/config
python -m build
```

Request v1 lama tetap diterima lewat `traffic.pipeline.run`, yang kini mendelegasi
ke facade baru. Contoh typed interface:

```python
from traffic_location.traffic.contracts.versioning import decode_request
from traffic_location.traffic.application.pipeline import process_video
result = process_video(decode_request(request_json), root=input_root)
# result.envelope, result.native, result.adapter_audit: immutable FrozenDocument.
```

Retry CLI dengan request/code/input sama membuka paket yang sudah diverifikasi;
request atau code berubah memerlukan revision baru. Reopen tidak memerlukan
model/video asli; count replay memerlukan measurement/config/evidence aslinya.
Perubahan file input setelah publikasi tidak mengubah paket finalized.

Batch facade menerima `traffic_batch_run_v2` manifest yang memuat8slot dengan
source SHA, frame count hasil inspeksi, measurement/geometry SHA, producer request
ref, policy SHA dan inference profile SHA. Seluruh input diperiksa sebelum
counting. Callback `on_video_result` dapat menyimpan per-video artifact untuk
progress/resume. Fungsi aggregate tetap dapat menampilkan batch partial; missing
slot tidak diubah menjadi nol dan total lengkap tetap null.

## Reproduksi parity

Video/model tidak ditambahkan ke Git. Download output producer yang sudah
completed, tanpa inference ulang, menggunakan Kaggle CLI pada environment yang
memiliki akses. Verifikasi hash native/measurement terhadap freeze sebelum replay.

```bash
kaggle kernels output chrisbiran/t7sl-traffic-counter-readable -p /path/cache
PYTHONPATH=src python tools/verify_traffic_migration.py \
  --cache-root /path/cache/results/t7sl_readable_v2/videos \
  --output /path/new-verification --workers 4 --repetitions 3
```

Producer bisa memiliki versi baru di masa depan: output terkini yang berbeda
hash harus ditolak sebagai acuan ini. TGDI cache tersedia pada path asli yang
tercatat di request23Oktober; jika download ulang diperlukan, gunakan byte/hash
identik dan rebase locator secara eksplisit. Jangan mengedit source identity,
geometry/review atau native golden untuk menyesuaikan lokasi file.

Hasil final gate dan lokasi receipt dicatat setelah seluruh pemeriksaan selesai.

## Batas kelulusan dan langkah berikut

RC ini menutup migrasi struktur dan compatibility dalam scope acuan tersebut.
Belum menutup vehicle-ReID final, akurasi identitas/role/counting pada lokasi baru,
benchmark berlabel, generalisasi filter malam, ataupun kualitas geometri T7SL yang
masih provisional. Fresh GPU worker tidak ditulis ulang; pengujian GPU full8baru
bukan syarat pembuktian ulang untuk pemindahan wrapper ini. CPU smoke tidak
membuktikan CPU memenuhi kebutuhan throughput delapan video.

**Storage yang teruji adalah lokal.** Integrasi bucket GCS nyata belum diuji:
project, bucket/region dan identitas IAM belum tersedia sebagai input tervalidasi.
Port telah dipisah agar adapter GCS tidak mengubah domain. Ikuti
[panduan onboarding GCS](GCS_STORAGE_ONBOARDING_PLAN.md) pada milestone cloud:
private bucket, ADC/attached service account, prefix sandbox, generation
preconditions, CRUD/checksum dan cleanup; jangan kirim secret di chat.

Berikutnya UI/backend mengonsumsi facade dan hasil finalized, bukan menjalankan
notebook dari request browser. Traffic dan Area Coverage tetap engine terpisah;
proyek ini tidak mengubah algoritme atau data Location. Container/GPU VM dan
publikasi RC sebagai default produksi tetap milestone tersendiri.

## Gate yang benar-benar dijalankan

- [30 replay acuan](../results/traffic_migration/20261024/parity/verification.json):
  3pengulangan independen per kasus pada8T7SL+2branch TGDI. Semua field native
  identik, termasuk event/category/direction, measured/estimated, pending/invalid,
  source refs, component/episode assignments dan aggregate.
- [Pemeriksaan source final](../results/traffic_migration/20261024/parity_final/verification.json):
  setelah pengetatan tipe/runtime guard serta pemisahan dependency renderer,
  replay penuh1kali lagi pada seluruh10kasus dan rekonsiliasi batch tetap identik.
  Source kernel/numerical policies tidak berubah. Ini bukan eksperimen inference
  determinism baru. Versi wrapper baru memang berbeda dari versi acuan.
- [Locked batch](../results/traffic_migration/20261024/locked_batch/verification.json):
  8source/producer/config diperiksa; seluruh71.380frame direplay, pivot/event dan
  subtotal cocok acuan. Lima cache memakai producer request aslinya, bukan
  mengaku berasal dari request resume. Producer model profile hash seragam.
- [Smoke32](../results/traffic_migration/20261024/final_smoke32.json):
  actual fresh CPU detector–tracker–ReID berhasil pada32frame; counting source
  final diulang3kali dengan native/result version stabil. Retry/reopen dibuktikan
  tidak memanggil counting kembali. Ini prefix smoke, tidak masuk batch totals.
- [Renderer32](../results/traffic_migration/20261024/render_smoke32.json):
  32frame encoded dan32frame didekode ulang, setiap pixel sumber diverifikasi;
  native tidak berubah. Uji frame1089 TGDI juga pixel-identik dengan renderer
  lama, memakai runtime CPU yang sesuai. Tidak merender/infer ulang full8video
  untuk refactor ini.
- Contract/config strict mypy, import DAG, wrong-phase review, nested immutability,
  branch mixing, prefix/foreign source, config precedence, export failure/tamper,
  competing publisher dan crash/retry lock diuji. Lock lokal menggunakan POSIX
  advisory lock yang dilepas OS ketika publisher crash; platform diuji Linux.
- [Installed wheel](../results/traffic_migration/20261024/installed_wheel.json):
  dipasang di venv bersih dan dipanggil dari `/tmp`, tanpa source-path injection.
  Tidak mengimpor library model pada facade/import. Native dan result version
  smoke cocok source; semua83file Python wheel cocok byte source package.

Ringkasan final jumlah tes/runtime/package SHA disimpan pada
[receipt release](../results/traffic_migration/20261024/release/verification.json).
Skipped di suite default berarti runtime opsional tidak tersedia pada interpreter
tersebut; renderer dan Location diuji pula di runtime masing-masing. CI workflow
baru tersedia; status GitHub Actions aktual bukan diasumsikan dari uji lokal.

Output review yang benar-benar diekspor dari snapshot yang sama:
[CSV](../results/traffic_migration/20261024/exports/t7sl_rc1/combined.csv),
[JSON](../results/traffic_migration/20261024/exports/t7sl_rc1/combined.json), dan
[HTML unduh/buka lokal](../results/traffic_migration/20261024/exports/t7sl_rc1/review.html).
GitHub file viewer menampilkan source HTML; bukan hosting web otomatis. CSV
menandai scope subtotal ketika batch partial dan HTML tidak mengubah unknown
complete total menjadi0.

Smoke replay ringan tanpa video/model:

```bash
python -m traffic_location traffic \
  --request results/traffic_migration/20261024/smoke/request.json \
  --root . --output /tmp/traffic-rc-smoke
python -m traffic_location reopen --output /tmp/traffic-rc-smoke
```

Pengukuran smoke yang disimpan adalah hasil CPU aktual, bukan fixture buatan.
Hash input/model/provenance tetap ada; angka32 tidak menggantikan71.380frame pada
bukti batch. Library ML hanya diperlukan saat memilih operasi fresh inference.
