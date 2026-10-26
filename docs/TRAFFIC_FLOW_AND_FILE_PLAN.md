<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Traffic Counter — input/output dan rencana file modular

24 Oktober 2026, Asia/Jakarta. **AUDIT/DESAIN — MENUNGGU PERSETUJUAN.**
Dokumen ini memperinci [audit kesiapan](TRAFFIC_MODULARIZATION_READINESS_AUDIT.md).
Tidak mengimplementasikan migrasi baru. Keberhasilan alur delapan video merupakan
asumsi perencanaan owner, bukan pengganti receipt hasil aktual atau bukti akurasi.

Rincian pemisahan kewenangan review, typed interface, versioning dan dependency
DAG ada di [klarifikasi batas kontrak/review](TRAFFIC_REVIEW_CONTRACT_BOUNDARIES.md).
Usulan30file sebelumnya digantikan oleh37file fungsional +6initializer.

## 1. Input awal pekerjaan

| Input | Isi yang diperlukan | Peran |
|---|---|---|
| Video sumber | Delapan file aktual untuk batch produk; ID, SHA256, ukuran, inventaris frame/dimensi/FPS, slot rekaman | Mengikat sumber dan cakupan; nama file saja tidak membuktikan identitas |
| Geometry tiap video | Polygon A/B, segmen counting line, margin, resolusi acuan dan revision | Memetakan pengamatan BC ke area/arah; template tidak otomatis cocok untuk lokasi baru |
| Model/runtime config | YOLO26M, BoT-SORT, ReID, asset SHA, versi dependencies, device/precision/seed dan parameter | Mengunci eksperimen dan mencegah fallback diam-diam |
| Policy counting | Unit/rider, role, kategori, dedup, return, eligibility, gap/timeout dan finalisasi | Menentukan keputusan; tidak dituning sebagai bagian pemindahan file |
| Preprocessing config | RAW saat ini; filter per video hanya bila profil itu didukung dan dikonfigurasi | Tidak menganggap semua video malam membutuhkan filter yang sama |
| Execution selection | Fresh, replay atau reopen; machine atau review-assisted yang didukung; artifact refs | Membedakan operasi dari asal measurement, serta menghindari pencampuran baseline/review |
| Review opsional | Source/episode/frame scope, bukti dan revision | Hanya dipakai pada capability/profile yang mendukung; bukan label global menurut raw ID |

Kaggle dataset mount adalah adapter input saat ini. UI upload/URL GCS adalah
adapter masa depan; interface engine tetap menerima source refs tervalidasi.
Store name/koordinat yang belum diketahui tetap unknown, tidak diisi rekaan.

## 2. Alur dari awal hingga akhir

```text
Video + geometry + model/runtime + policy + profile
    → verifikasi sumber/config
    → decode seluruh frame secara berurutan
    → preprocessing eksplisit
    → YOLO26M detection
    → BoT-SORT + ReID
    → measurement terukur dan source-linked
    → adapter + trajectory dasar
    → episode identitas / role / unit fisik
    → eligibility + geometry + kandidat crossing/passage
    → kategori temporal + finalisasi/dedup counting
    → snapshot machine
    → review opsional yang terikat bukti → snapshot reviewed terpisah
    → agregasi satu snapshot/video
    → JSON/CSV/audit + MP4 beranotasi
    → manifest final dan penyimpanan → reopen
```

Diagram menyederhanakan tampilan, bukan izin mengubah urutan algoritme. Resolver
identitas/role dan rule counting memiliki interaksi serta urutan override yang
sudah ada. Review konteks sumber tertentu masuk sebelum resolver; adjudikasi
kandidat masuk sesudah counting. Kedua jenis review tidak boleh disatukan menjadi
fungsi yang dapat mengubah crossing invalid menjadi valid.

| Tahap | Input | Proses | Output dan pengaman |
|---|---|---|---|
| 1. Verifikasi | Source refs, config, geometry, profile | Periksa keberadaan, SHA, schema, capability, dimensi dan scope | Job tervalidasi atau BLOCKED/FAILED dengan alasan; data hilang bukan traffic0 |
| 2. Decode | Video terverifikasi | Baca frame0 sampai akhir secara berurutan; verifikasi coverage | Frame asli dan indeks sumber; decode failure/extra/missing frame eksplisit. Tidak ada frame skipping untuk hasil penuh |
| 3. Preprocess | Frame asli dan filter config | RAW atau transformasi yang didukung; simpan lineage dan pemetaan koordinat | Detector input + hash/transform refs. Preview dan inference harus memakai transformasi sama bila filter digunakan |
| 4. Detection | Detector input dan weights YOLO26M | Inferensi bbox, raw class dan confidence | Raw detections per frame dalam koordinat frame sumber; detection belum merupakan hitungan |
| 5. Tracking/ReID | Deteksi, frame dan state tracker per video | Asosiasi temporal dengan BoT-SORT dan encoder ReID | Raw tracker ID, emitted observations dan source detection index. ID tracker belum menjamin identitas kendaraan fisik |
| 6. Measurement | Hasil tracker/detector | Validasi raw link, bbox, frame dan observed/emitted; simpan source/model/runtime | MeasuredFrame records. BC berasal dari bbox deteksi terukur; prediksi tidak menjadi pengukuran |
| 7. Trajectory dasar | Measurement chronological | Kelompokkan riwayat pengamatan per track; simpan gap dan arah gerak dari pengamatan | Riwayat source-linked. Tidak menginterpolasi gap agar terlihat sebagai crossing terukur |
| 8. Episode/role/unit | Trajectory, raw classes dan bukti asosiasi | Jalankan resolver konteks, rider/parent, konflik dan identitas sesuai acuan | Physical episode/relation/role beserta scope bukti. Person unknown bukan otomatis pedestrian; rider+0 |
| 9. Eligibility/geometri | Episode, BC, trajectory, polygon/line/margin | Periksa origin, arah, posisi, segmen terbatas dan clock | Kandidat eligible, crossing terukur, kandidat estimasi atau alasan tidak eligible/ambigu |
| 10. Passage/kategori/finalisasi | Kandidat dan bukti temporal | Terapkan policy kategori, dedup, genuine return, konflik dan finalisasi offline | Accepted measured/estimated, pending, invalid atau resolved-not-eligible/+0. Jumlah akhir bukan jumlah raw ID atau bbox |
| 11. Review opsional | Snapshot dan evidence/source refs | Terapkan review yang tervalidasi pada scope yang benar | Snapshot reviewed/revision baru, terpisah dari machine. Fresh review-assisted belum otomatis tersedia hanya karena adapter fresh ada |
| 12. Agregasi | Satu selected snapshot dari setiap video | Rekonsiliasi event dan pivot kategori×arah×evidence | Subtotal per video, gabungan dan coverage/status. Pedestrian terpisah; pending/invalid tidak masuk accepted |
| 13. Renderer/export | Snapshot immutable, frame/measurement dan geometry | Gambar bbox/ID/parent/BC/panel/log; tulis MP4 dan tabel | Visualisasi hasil tersimpan; renderer tidak menjalankan atau memperbaiki counting |
| 14. Persist/reopen | Semua mandatory artifacts dan manifest | Publikasi setelah integritas/coverage lulus; simpan versi dan refs | Hasil bisa dibuka tanpa model/refetch. Gagal ekspor bukan sukses; refresh menghasilkan revision baru |

Decoder/model boleh memakai letterbox internal, tetapi bbox/BC/geometri harus
kembali ke satu ruang koordinat sumber yang eksplisit. Pengecilan tensor model
bukan frame skipping. Sampel gambar untuk inspeksi dan smoke96frame terpisah dari
full-video result dan tidak masuk total batch.

## 3. Apa yang sebenarnya dihitung

Unit hitungan adalah **passage kendaraan fisik yang memenuhi policy**, bukan satu
bbox, satu frame, jumlah penampakan, atau jumlah tracker ID.

- Seratus frame berisi motor yang sama pada satu passage tidak berarti100motor.
- Motorcycle+rider/passenger yang memiliki bukti hubungan sesuai policy dihitung
  sebagai satu motorcycle; bbox union hanya tampilan dan tidak mengganti BC parent.
- Pergantian ID tidak otomatis passage baru; konflik mengikuti pending/invalid.
- Return yang memenuhi bukti passage baru dapat dihitung lagi menurut policy.
- Timeout60frame sumber merupakan estimasi, berbeda dari crossing terukur.
- Satu kendaraan yang lewat pada dua rekaman berbeda dapat menghasilkan dua
  passage; total rekaman tidak berarti jumlah kendaraan unik global atau24jam.

## 4. Output yang diterima pengguna

| Keluaran | Isi | Contoh artifact boundary |
|---|---|---|
| Ringkasan per video | Kendaraan accepted per kategori/arah, measured/estimated, pedestrian, pending/invalid, processed frame scope | `videos/<id>/counting/result.json` |
| Audit per passage | Event/display/raw ID, unit/episode, kategori/arah, bukti/frame sumber, route dan alasan keputusan | `native.json.gz` dan daftar keputusan di dalamnya |
| Video beranotasi | Seluruh frame, bbox/warna/ID, rider-parent, BC, geometri/margin, pivot dan log | `annotated/<id>.mp4` + report JSON jumlah frame/hash |
| Gabungan delapan video | Pivot kategori×arah×measured/estimated; total kendaraan accepted terpisah dari pedestrian | `combined.json`, `combined.csv` |
| Integritas/versi | SHA sumber/model/config/review/geometry, runtime, result version, manifest dan status | Artifact manifest dan job reports |
| Review index | Tautan/player MP4 dan ringkasan | `review.html` atau UI kemudian |

Nama di atas mengikuti boundary yang sedang dikembangkan, bukan klaim seluruh
artifact delapan video sudah terbit. Pemisahan job inference/counting dan job
render memungkinkan penambahan anotasi tanpa menjalankan model lagi.

Untuk category/direction cell yang tersedia:

`accepted = accepted_measured + accepted_estimated`.

Total kendaraan tidak memasukkan pedestrian, pending atau invalid. Bila satu
video hilang/gagal, subtotal yang tersedia boleh ditampilkan sebagai partial,
sedangkan total lengkap delapan video tetap null/tidak tersedia. Nol hanya untuk
slot/kategori yang berhasil dievaluasi dan tidak memiliki accepted event; bukan
bukti tidak ada kendaraan fisik.

Tiga pengulangan counting pada measurement yang sama memeriksa replay counting.
Itu bukan tiga inference baru. Reopen membaca artifact final; rerender menggambar
ulang dari keputusan final; refresh/model/geometry/review baru membuat revision baru.

## 5. Jumlah file yang diusulkan

**PROPOSAL TARGET REVISI:37file Python fungsional Traffic +6file `__init__.py` =43file
Python pada package Traffic.** Ini bukan jumlah seluruh repository dan bukan
perintah menghapus/mengganti file sekarang. Tests, JSON schemas, konfigurasi,
notebook, CLI tingkat repo, shared utilities, storage adapters, backend/UI dan
engine Area Coverage berada di luar hitungan43ini. Modul compatibility lama
boleh tetap ada sementara, sehingga jumlah file selama transisi lebih besar.

| No | Target file relatif ke `src/traffic_location/traffic/` | Fungsi dan batas tanggung jawab |
|---|---|---|
| 1 | `config/schema.py` | Typed immutable model/runtime/geometry/counting config; hanya data dan schema version |
| 2 | `config/profiles.py` | Profil dan override eksplisit; menghasilkan effective config tanpa aturan counting baru |
| 3 | `config/validation.py` | Validasi kombinasi/nilai config dan capability; tidak menjalankan domain |
| 4 | `config/loader.py` | Baca config artifact, dispatch versi, validasi dan fingerprint; tanpa side effect model/GPU |
| 5 | `contracts/source.py` | ArtifactRef, SourceVideoRef dan FrameScope; primitive evidence/source DTO |
| 6 | `contracts/measurement.py` | MeasuredFrame, raw observation dan MeasurementRef; tanpa resolver |
| 7 | `contracts/identity.py` | EpisodeRef, scoped role dan relation evidence; tanpa algoritme asosiasi |
| 8 | `contracts/passage.py` | CandidateRef, PassageEvent dan evidence/status; tanpa keputusan counting |
| 9 | `contracts/execution.py` | Request/profile/operation DTO; config dan review dirujuk sebagai artifact refs |
| 10 | `contracts/results.py` | VideoResult, BatchSelection/BatchResult dan provenance envelope |
| 11 | `contracts/review.py` | Dua tipe terpisah: SourceContextReview dan CandidateAdjudication; action/scope tidak dapat dipertukarkan |
| 12 | `contracts/versioning.py` | Registry serializer/decoder versi dan compatibility mapping; versi unknown ditolak |
| 13 | `validation.py` | Validasi schema/semantik, capability, source binding, coverage dan profile |
| 14 | `adapters/video_input.py` | Inventaris video, metadata, hash dan decoder berurutan; tidak menghitung kendaraan |
| 15 | `adapters/preprocessing.py` | Implementasi RAW/filter yang disetujui serta koordinat/lineage; tanpa auto-enhancement tersembunyi |
| 16 | `adapters/detector.py` | Wrapper YOLO26M, asset/backend/precision checks dan raw detections |
| 17 | `adapters/tracker_reid.py` | Wrapper BoT-SORT+ReID dan lifecycle state per video; tidak menentukan accepted passage |
| 18 | `adapters/measurement.py` | Writer/reader measurement dan indeks/hash frame; mencegah hilangnya raw links |
| 19 | `adapters/notebook_measurements.py` | Format notebook historis → kontrak measurement, mempertahankan makna/provenance |
| 20 | `adapters/fresh_measurements.py` | Format fresh → kontrak yang sama; konteks person/kendaraan tetap terpisah |
| 21 | `domain/geometry.py` | Polygon, finite segment/margin, side dan operasi geometri |
| 22 | `domain/trajectory.py` | Riwayat titik terukur, observed motion, gap dan direction evidence |
| 23 | `domain/identity.py` | Batas episode, raw-ID/context reuse, alias/association dan konflik identitas |
| 24 | `domain/role_association.py` | Rider/parent, pedestrian/unknown dan relasi unit dengan scope bukti |
| 25 | `domain/eligibility.py` | Kelayakan origin/arah/observasi, timeout clock dan appearing-away safeguards |
| 26 | `domain/crossing.py` | Bukti line/margin/polygon transition dan klasifikasi measured versus unobserved; tidak menambah total sendiri |
| 27 | `domain/counting.py` | State machine passage dan kandidat; tidak menerima raw detection sebagai hitungan langsung |
| 28 | `domain/finalization.py` | Kategori temporal, dedup/konflik, finalisasi offline dan keputusan akhir; urutan policy acuan dipertahankan |
| 29 | `domain/source_context_review.py` | Terapkan klaim konteks berbukti sebelum resolver; hanya derived context, bukan raw measurement/crossing |
| 30 | `domain/candidate_adjudication.py` | Adjudikasi kandidat sesudah counting; capability acuan +0 atau tetap pending, tanpa menciptakan crossing/passage |
| 31 | `domain/aggregation.py` | Proyeksi event accepted ke subtotal/pivot per video dan batch, dengan rekonsiliasi |
| 32 | `application/pipeline.py` | Mengorkestrasi satu video atau replay; domain rules tetap berada di domain |
| 33 | `application/batch.py` | Pemilihan snapshot, orkestrasi delapan slot produk dan partial/failure handling |
| 34 | `application/runtime.py` | Process/device/resource scheduling, progress, timeout, cancellation dan state isolation |
| 35 | `adapters/renderer.py` | View-model/bbox/panel/MP4 dari snapshot immutable; raw BC tidak berubah |
| 36 | `adapters/exports.py` | JSON/CSV/review index dan validasi konsistensi ekspor, tanpa menghitung ulang |
| 37 | `artifact_store.py` | Port akses artifact/result manifest; implementasi lokal/GCS di lapisan storage terpisah |
Enam `__init__.py` berada di `traffic/`, `traffic/adapters/`, `traffic/domain/`,
`traffic/application/`, `traffic/contracts/` dan `traffic/config/`. Tidak perlu file per kelas atau per fungsi kecil.
Detektor dan tracker diganti/dievaluasi melalui adapter, bukan dengan mengubah
rule domain. Area Coverage tetap di `src/traffic_location/location/` dan hanya
berbagi utilitas umum; tidak mengimpor aturan traffic.

Pemetaan awal: pipeline/batch/contracts yang sudah ada menjadi facade; notebook
dan fresh adapter dipindah dengan compatibility wrapper; `_kernel/identity*` serta
`passage/eligibility/publication/handoff` tetap dibungkus dahulu. Pemisahan fungsi
ke modul domain tidak berarti mengganti urutan override atau menggabungkan lapisan
historis sekaligus. Rendering/cache/codec normalization juga dipisahkan dari
keputusan counting.

## 6. Urutan migrasi dan syarat kelulusan

| Langkah setelah approval | Output | Acceptance criteria |
|---|---|---|
| 0. Freeze | Registry actual inputs, snapshots, config/model/runtime, source code dan known limitations | Hash dan artifact dapat diverifikasi; asumsi sukses tidak dipakai sebagai golden rekaan |
| 1. Kontrak/facade | Contracts/config/validation + API satu video/replay | Invalid source/profile/coverage ditolak; machine/reviewed dan fresh/replay/reopen terpisah |
| 2. Adapter | Decoder, model/tracker wrapper dan dua measurement adapters | Raw ID/class/bbox/index/BC/frame tetap sama; tidak ada frame skipping, relabel provenance atau fallback model |
| 3. Domain | Pisahkan trajectory/episode/role/eligibility/crossing/count/finalization bertahap | Exact native parity event/keputusan, kategori/arah/evidence, pending/invalid/+0, relasi dan agregat |
| 4. Runtime/batch | Resource scheduling, state isolation dan selected snapshots | Tiga replay independen/profile stabil; urutan/retry/concurrency tidak mewariskan state atau menggandakan hitungan |
| 5. Render/export/store | MP4, pivot, ekspor, manifest dan reopen | Seluruh frame terverifikasi, panel cocok ledger, render tidak mengubah native hash, kegagalan ekspor tidak sukses |
| 6. Release candidate | Wheel/CLI, dokumentasi capability, diff dan rollback refs | Jalan di luar repo tanpa notebook import path; engine independen UI/storage vendor; seluruh gate relevan lulus |

Detail acceptance utama tetap AC01–AC11 di audit induk. Uji source-bound perlu
mencakup class/ID reuse, rider versus pedestrian, duplikasi, occlusion/gap,
appearing-away, timeout origin, genuine return dan finite endpoints. Uji fresh
inference terpisah pada backend yang direkam; keberhasilan replay atau cache
tidak otomatis meluluskan determinisme GPU/CPU maupun akurasi.

Code/schema/runtime baru dapat membuat result version baru; keputusan domain
harus setara pada input acuan. Perubahan metadata yang diperlukan dipetakan
eksplisit, bukan menghapus field pembanding. Snapshot/golden tidak ditimpa untuk
membuat test match. Jika ada mismatch, hentikan irisan migrasi dan rollback
facade/selection ke baseline; perbaikan perilaku diuji pada eksperimen terpisah.

## 7. Keputusan yang diminta dari audit

Persetujuan yang diperlukan adalah: batas37file fungsional/43file package,
urutan migrasi, perilaku yang dipertahankan, serta acceptance/rollback gates.
Nama file adalah proposal desain; hasil inspeksi interface dapat memerlukan
revisi tercatat sebelum coding, bukan penambahan aturan bisnis diam-diam.
Approval ini bukan approval produksi atau perubahan model/threshold/geometri.

Setelah dokumen disepakati, lakukan audit Area Coverage sebagai agenda berikutnya.
Penyelesaian eksperimen lama tidak menjadi izin otomatis menjalankan migrasi baru.


## Pelaksanaan audit yang diotorisasi

Instruksi owner berikutnya mengotorisasi migrasi ini. Status proposal/menunggu
persetujuan di atas merupakan checkpoint historis; hasil implementasi, keputusan
dan bukti uji ada di [release migrasi](TRAFFIC_MODULARIZATION_RELEASE.md).
