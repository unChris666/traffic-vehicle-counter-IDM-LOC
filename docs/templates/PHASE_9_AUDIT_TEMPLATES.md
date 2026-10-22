# Phase 9 — template berkas audit dan daftar perbaikan

**PROPOSAL — template dokumentasi, belum merupakan hasil audit.** Gunakan bersama [protokol audit](../PHASE_9_AUDIT_PROTOCOL.md) dan [tugas Phase 9](../PHASE_9_TASK.md). Dokumen ini tidak menjalankan model, menghitung ulang video, menerapkan label, atau mengubah snapshot Phase 8. Semua kolom hasil diisi hanya setelah sumber benar-benar diperiksa.

Tujuan paket adalah menemukan hitungan palsu, duplikasi, salah penggabungan, passage terlewat, serta penyebabnya di Phase 1–8. Pending yang selesai sebagai **tidak eligible/+0** merupakan keputusan audit yang sah. Pending yang belum terselesaikan tetap tidak diketahui; jangan menggantinya dengan nol.

## 1. Paket keluaran yang direncanakan

Pilih `audit_id` baru dan simpan paket terpisah dari hasil machine yang dibekukan. Struktur berikut **rencana**, bukan pernyataan berkas sudah dihasilkan:

```text
results/phase_9/<audit_id>/
  audit_plan.md
  input_manifest.json
  segments.csv
  passage_inventory.csv
  cases.jsonl
  review_decisions.jsonl
  improvement_backlog.csv
  comparison.csv
  REPORT.md
  evidence/
    manifest.json
    <frame atau klip bukti yang benar-benar diperiksa>
```

`audit_id`, `segment_id`, `physical_object_ref`, `physical_passage_ref`, `case_id`, dan `decision_id` merupakan referensi audit lokal. Referensi tersebut **berbeda** dari raw tracker ID, ID tampilan seperti `M1006`, dan ID unit machine. Satu objek fisik dapat mempunyai beberapa raw ID dan beberapa passage; raw ID juga dapat dipakai bergantian oleh objek berbeda. Referensi manual tidak otomatis menjadi identitas produksi.

Gunakan JSON `null` atau sel CSV kosong untuk informasi tidak diketahui. `0` hanya berarti nol yang benar-benar dipastikan. Array kosong berarti sudah diperiksa dan tidak ada anggota; jika belum diperiksa, gunakan `null`. Pada CSV, pisahkan nilai majemuk dengan `|`, dan gunakan pengutipan CSV ketika teks berisi koma atau baris baru.

## 2. `audit_plan.md` — scope dan aturan sebelum review

Salin kerangka berikut sebagai rencana. Semua penanda `BELUM_DIISI` wajib diselesaikan atau dijelaskan sebagai batas audit.

```markdown
# Rencana audit <audit_id>

Status: PLANNED
Tanggal dan reviewer: BELUM_DIISI
Snapshot baseline serta manifest SHA-256: BELUM_DIISI
Snapshot kebijakan yang benar-benar dijalankan: BELUM_DIISI
Keputusan pengguna terbaru yang akan dinilai terpisah: BELUM_DIISI

## Cakupan
- Video dan sumber aktual: BELUM_DIISI
- Full-video atau segmen yang diaudit: BELUM_DIISI
- Dasar pemilihan kondisi/kasus dan keterbatasan sampel: BELUM_DIISI
- Pilot/development dan validasi; riwayat paparan reviewer: BELUM_DIISI
- Aturan konteks sebelum/sesudah dan pembagian passage di batas segmen: BELUM_DIISI

## Urutan review
1. Validasi identitas sumber, frame, cache, snapshot dan versi anotasi.
2. Inventaris passage dari video mentah sebelum membuka keputusan machine.
3. Cocokkan inventaris dengan event accepted, estimasi, pending dan tanpa kandidat.
4. Periksa unit, role, identitas, kategori, arah, BC, geometri dan route.
5. Catat keputusan/ketidakpastian dan kaitkan akar masalah dengan Phase 1–8.
6. Rekonsiliasi dampak; susun backlog dan rencana pengujian perubahan berikutnya.

## Kebijakan dan batas
- Timer: 60 frame sumber sejak observasi terakhir di polygon asal.
- Observasi kendaraan yang sama di polygon asal memperbarui timer.
- Handoff identitas ambigu menahan eligibility estimasi yang terkait.
- Passage selesai tidak dibuka ulang hanya karena ID berubah/timer habis.
- Crossing terukur dan inferensi tetap terpisah.
- Rider +0; role positif tidak otomatis membuktikan passage +1.
- Kebijakan pedestrian inferred dan taxonomy BUS: status keputusan BELUM_DIISI.
- Tidak ada inference, replay counting, tuning, retraining atau perubahan aplikasi
  dalam audit ini; kebutuhan eksperimen menjadi backlog terpisah.

## Kriteria penutupan scope
- Coverage aktual dan bagian yang belum diperiksa tersedia.
- Setiap kasus dalam scope diputuskan atau tetap unresolved dengan perlakuan jelas.
- Setiap keputusan menunjuk bukti dan scope frame/episode/event.
- Perubahan agregat yang dapat dihitung telah direkonsiliasi tanpa menghitung ganda.
- Backlog Phase 1–8 mempunyai bukti, prioritas dan cara verifikasi/regresi.
- Tidak ada klaim peningkatan machine yang belum diuji.
```

Status paket dapat berupa `PLANNED`, `IN_PROGRESS`, `PARTIAL`, `COMPLETE_SCOPE`, atau `BLOCKED`. `COMPLETE_SCOPE` hanya menyatakan audit pada scope yang disebut selesai; tidak menyatakan semua video, kondisi malam, atau deployment tervalidasi.

**Pisahkan keadaan aktual dari kebijakan baru.** Input manifest harus merekam kontrol baseline yang dijalankan saat menghasilkan snapshot. Keputusan terbaru tentang timer/eligibility dicatat sebagai penilaian kebijakan, bukan ditulis seolah sudah ada pada kode atau hasil beku. Pedestrian `measured_only` pada run riset bukan persetujuan otomatis untuk semua penggunaan; taxonomy BUS tetap terbuka sampai diputuskan.

## 3. `input_manifest.json` — validasi input dan provenance

Kerangka berikut berisi nilai kosong yang disengaja. Tambahkan satu entri per berkas sumber/snapshot yang dipakai; jangan mengarang SHA, metadata video, commit atau versi library.

```json
{
  "audit_id": null,
  "status": "PLANNED",
  "reviewers": null,
  "created_at": null,
  "baseline": {
    "run_id": null,
    "repository_commit": null,
    "code_manifest_uri": null,
    "code_manifest_sha256": null,
    "config_uri": null,
    "config_sha256": null,
    "actual_policy_snapshot_uri": null,
    "event_snapshot_uri": null,
    "event_snapshot_sha256": null,
    "annotation_version": null
  },
  "latest_user_decision_refs": null,
  "inputs": [
    {
      "video_key": null,
      "readiness": "NOT_CHECKED",
      "source_uri": null,
      "source_file_sha256": null,
      "source_size_bytes": null,
      "width": null,
      "height": null,
      "fps_reported": null,
      "decoded_frame_count": null,
      "frame_index_base": 0,
      "frame_interval_end_inclusive": true,
      "cache_uri": null,
      "cache_manifest_sha256": null,
      "geometry_uri": null,
      "geometry_sha256": null,
      "geometry_reference_width": null,
      "geometry_reference_height": null,
      "geometry_review_ref": null,
      "annotated_asset_uri": null,
      "annotated_asset_sha256": null,
      "checks": {
        "source_identity": "NOT_CHECKED",
        "frame_cache_alignment": "NOT_CHECKED",
        "snapshot_code_config_binding": "NOT_CHECKED",
        "annotation_snapshot_match": "NOT_CHECKED"
      },
      "blockers": null
    }
  ],
  "review_environment": {
    "player_or_decoder": null,
    "version": null,
    "time_to_frame_mapping_method": null
  }
}
```

`readiness` memakai `VERIFIED`, `AVAILABLE_UNVERIFIED`, `MISSING`, `INVALID`, atau `NOT_CHECKED`. Hasil check terpisah memakai `PASS`, `FAIL`, `UNAVAILABLE`, atau `NOT_CHECKED` dan harus disertai referensi bukti di manifest atau catatan kasus. Kolom `source_uri` cukup menunjuk lokasi yang bisa diakses ulang; **jangan menyimpan token atau URL bertanda tangan yang mengandung kredensial**. Untuk arsip gzip, bedakan SHA berkas arsip dari SHA byte asli menurut manifest retensi. Anotasi yang berbeda versi tidak boleh dianggap sama hanya karena filename sama.

Jika piksel random seek tidak cocok dengan frame cache, gunakan decode berurutan atau metode yang dapat diverifikasi; catat frame yang gagal cocok dan keluarkan dari bukti sampai terselesaikan. FPS yang dilaporkan bukan bukti bahwa frame tertentu sudah cocok. Interval timer60 tetap frame sumber; timestamp hanya alat navigasi tambahan.

## 4. `segments.csv` — coverage, kondisi sulit, dan paparan

```csv
segment_id,video_key,source_sha256,context_start_frame,review_start_frame,review_end_frame,context_end_frame,coverage_status,raw_first_status,reviewer,reviewed_at,lighting,glare,blur,occlusion,camera_shake,geometry_alignment,condition_evidence_refs,split,prior_exposure,overlap_group,passage_boundary_rule,notes
```

- Semua frame adalah **indeks0-based dengan akhir inklusif**. Konteks di luar interval review tidak otomatis masuk denominator coverage.
- `coverage_status`: `PLANNED`, `REVIEWED`, `PARTIAL`, `UNAVAILABLE`. Untuk partial, pecah menjadi interval aktual yang jelas; jangan mengklaim seluruh interval diperiksa.
- `raw_first_status`: `COMPLETED_BEFORE_MACHINE_VIEW`, `ALREADY_EXPOSED`, atau `NOT_COMPLETED`. Hanya status pertama menyatakan inventaris dibuat sebelum melihat output untuk review tersebut.
- `split`: `PILOT_DEV`, `VALIDATION`, atau `UNASSIGNED`; `prior_exposure`: `KNOWN_EXPOSED`, `UNSEEN_AT_FREEZE`, atau `UNKNOWN`. Kasus yang sudah dipakai membuat aturan tetap development. Video yang sudah pernah direview tidak disebut blind hold-out.
- Catat kondisi hanya berdasarkan bagian yang terlihat. Nilai `UNKNOWN` dapat digunakan jika kualitas bukti tidak cukup; “malam” pada filename tidak otomatis menjelaskan tingkat visibilitas.
- Coverage dihitung sebagai **gabungan interval frame**, bukan jumlah panjang klip yang overlap. Satu passage yang melintasi batas segmen mempunyai satu referensi dan satu pemilik segmen; segmen lain hanya memberi konteks.

## 5. `passage_inventory.csv` — inventaris fisik dari video mentah

```csv
physical_object_ref,physical_passage_ref,video_key,segment_id,first_evidence_frame,last_evidence_frame,role,parent_physical_object_ref,category,direction,observed_passage_state,manual_geometry_evidence,eligibility_review,reviewed_passage_count,evidence_refs,raw_ids,machine_candidate_ids,machine_event_ids,display_ids,match_status,inventory_author,inventory_created_before_machine_view,notes
```

Inventaris dimulai dari objek dan gerak yang benar-benar tampak pada video mentah. Kolom raw ID, kandidat, event, dan display ID baru dilengkapi saat pencocokan dengan machine; **objek tanpa kandidat tetap dicatat**. Gunakan `match_status=NO_MACHINE_CANDIDATE` jika sudah diperiksa dan memang tidak mempunyai kandidat. Jika belum diperiksa, biarkan kosong/`NOT_CHECKED`, bukan `NO_MACHINE_CANDIDATE`.

- `role`: `PEDESTRIAN`, `RIDER_PASSENGER`, `VEHICLE`, atau `UNKNOWN`. Rider menunjuk parent kendaraan hanya dalam scope terbukti; tidak otomatis berlaku pada seluruh raw ID.
- `observed_passage_state`: `PASSAGE_OBSERVED`, `NO_PASSAGE_OBSERVED`, atau `UNCERTAIN`. Kendaraan yang tampak diam atau baru muncul di polygon tujuan dapat menjadi kasus tanpa passage; jangan memaksakan nomor passage untuknya.
- `physical_passage_ref` boleh kosong untuk kasus `NO_PASSAGE_OBSERVED` atau passage yang belum dapat dipisahkan. `physical_object_ref` tetap memungkinkan pelacakan kasus.
- `manual_geometry_evidence` mendeskripsikan bukti visual, sedangkan evidence machine `MEASURED/INFERRED` harus ditelusuri dari pengukuran sumber. Pengetahuan reviewer bahwa kendaraan melintas tidak membuat sistem memiliki observasi BC yang sebenarnya hilang.
- `eligibility_review`: `ELIGIBLE`, `INELIGIBLE`, `UNRESOLVED`, atau `OUT_OF_SCOPE`. `reviewed_passage_count` berisi 1/0 hanya jika sudah diputuskan; unresolved tetap kosong. Rider +0 tidak menghilangkan passage motorcycle parent.
- Arah boleh `A_TO_B`, `B_TO_A`, `UNKNOWN`, atau `NOT_APPLICABLE`. Jangan menyimpulkan arah hanya dari paritas ID tampilan.

Satu objek yang melakukan genuine return mendapatkan referensi passage baru. Dua raw ID yang merupakan kendaraan sama pada satu lintasan tidak mendapat dua referensi passage hanya karena tracker berganti ID. Sebaliknya, dua objek berbeda yang menggunakan raw ID sama harus dipisahkan.

## 6. `cases.jsonl` dan manifest bukti — penyebab beserta batas klaim

Simpan satu objek kasus per baris pada `cases.jsonl`; berikut **daftar field yang diusulkan**, bukan hasil kasus terisi:

| Kelompok field | Isi minimum |
|---|---|
| Identitas | `case_id`, `audit_id`, `video_key`, `source_sha256`, `segment_ids`, `physical_object_refs`, `physical_passage_refs`. |
| Scope | `start_frame`, `end_frame`, frame kritis, raw ID **bersama interval pemakaiannya**, machine unit/episode/event IDs, versi anotasi. |
| Fakta | Observasi piksel aktual dan `evidence_refs`; bedakan label pengguna, review manusia, analisis AI, dan keluaran machine. |
| Unit/peran | Role person, parent motorcycle, scope relasi, indikasi kendaraan berbeda atau riwayat campuran. |
| Kategori/arah | Kategori di margin, konflik kelas temporal, pemetaan taxonomy yang belum diputuskan, arah dari trajectory beserta bukti. |
| Crossing machine | `route`, `measurement_status`, frame dan ID record pengukuran BC sumber, asal BC `VEHICLE_RAW`/`PERSON_RAW`/`PREDICTION`/`UNAVAILABLE`, frame gap, interval band dan sumber konfirmasi. |
| Timeout | Waktu terakhir terlihat di asal, sumber frame timer, observasi origin berikutnya, reset, handoff terverifikasi/ambigu, U-turn, serta apakah passage sebelumnya sudah selesai. |
| Diagnosis | Satu atau beberapa jenis kegagalan, fase penyebab yang didukung, penyebab alternatif, bukti yang masih kurang. |
| Keadaan | Status aktual machine, penilaian kebijakan terbaru yang terpisah, `case_action` sesuai protokol, dan status `OPEN`/`DECIDED`/`UNRESOLVED`. |

Jenis kasus dapat berupa `FALSE_COUNT`, `DUPLICATE`, `WRONG_MERGE`, `MISSED_PASSAGE`, `WRONG_ROLE`, `WRONG_CATEGORY`, `WRONG_DIRECTION`, `INVALID_CROSSING_EVIDENCE`, `OUTPUT_TRACEABILITY`, atau `UNKNOWN_CAUSE`. Satu kasus dapat mempunyai beberapa tag. Jangan menjumlahkan tag sebagai jumlah passage unik.

**Tingkat bukti diagnosis:**

- `OBSERVED`: fakta langsung yang menunjuk frame atau record aktual.
- `SUPPORTED_CAUSE`: sumber intermediate mendukung penyebab, misalnya objek tampak pada frame tetapi tidak ada box pada cache detector yang lengkap untuk frame itu.
- `HYPOTHESIS_UNTESTED`: penjelasan masuk akal yang belum dibuktikan; sebutkan alternatif dan eksperimen pembeda.
- `UNKNOWN`: bukti belum cukup untuk menentukan penyebab.

Tidak ada bbox pada anotasi saja belum membuktikan detector gagal. Pisahkan: deteksi tidak ada di cache, deteksi salah kelas, deteksi ada tetapi track hilang, track ada tetapi eligibility menolak, serta event ada tetapi panel gagal menampilkan. Jika cache sudah memfilter confidence, jangan menyebut deteksi di bawah filter sebagai “pasti tidak dideteksi model”. Catat keterbatasan retensi; kebutuhan inference baru masuk backlog dan tidak dijalankan dalam audit ini.

`evidence/manifest.json` memuat satu entri per gambar/klip/record yang dipakai:

| Field | Isi |
|---|---|
| `evidence_id`, `relative_path`, `file_sha256` | Identitas berkas bukti yang benar-benar disimpan. |
| `video_key`, `source_sha256` | Identitas video asal. |
| `source_start_frame`, `source_end_frame` | Frame sumber inklusif; untuk gambar keduanya sama. |
| `extraction_method`, `decoder_version` | Cara memperoleh bukti, termasuk decode berurutan atau sumber anotasi. |
| `evidence_type` | `SOURCE_FRAME`, `SOURCE_CLIP`, `ANNOTATED_FRAME`, `LOCAL_RENDER`, atau `RETAINED_RECORD`. |
| `pixel_alignment_status`, `cache_record_refs` | Hasil pemeriksaan kecocokan piksel/frame dan referensi pengukuran jika tersedia. |
| `crop_or_transform` | Koordinat crop/resize atau `NONE`; simpan hubungan ke frame penuh. |
| `reviewer`, `reviewed_at`, `notes` | Siapa yang memeriksa dan batas cakupannya. |

Preview renderer lokal tidak diberi label sebagai frame MP4 rilis. Crop person membantu pemeriksaan postur, tetapi hubungan orang–motor serta geometri tetap memerlukan konteks frame penuh/temporal. Bukti yang belum dapat dibuka atau diverifikasi ditandai unavailable; jangan menggantinya dengan screenshot rekaan.

## 7. `review_decisions.jsonl` — keputusan, bukan perubahan machine terselubung

Satu keputusan dapat menyelesaikan beberapa tag pada satu kasus, tetapi harus menunjuk event/passage dan scope yang jelas.

| Field | Isi yang diharapkan |
|---|---|
| `decision_id`, `case_id`, `reviewer`, `decided_at`, `source_type` | Provenance keputusan; bedakan `USER_REVIEW`, `HUMAN_REVIEW`, `AI_ASSISTED_PIXELS_REVIEW`, dan `MACHINE_OUTPUT`. |
| `evidence_refs`, `scope_start_frame`, `scope_end_frame` | Bukti dan batas penerapan. |
| `decision_status` | `ADJUDICATED`, `UNRESOLVED`, atau `OUT_OF_SCOPE`. |
| `role_decision`, `identity_decision`, `category_decision`, `passage_decision` | Putusan masing-masing aspek; gunakan unknown ketika belum jelas. |
| `parent_vehicle_ref`, `same_physical_unit_refs`, `different_physical_unit_refs` | Relasi terbukti, bukan alias global raw ID. |
| `policy_snapshot_ref`, `latest_policy_assessment_ref` | Kebijakan aktual snapshot dan penilaian kebijakan baru terpisah. |
| `event_actions` | Usulan terhadap event tertentu: `KEEP`, `PROPOSE_ADD`, `PROPOSE_CANCEL`, `PROPOSE_MERGE`, `PROPOSE_SPLIT`, atau `PROPOSE_RECLASSIFY`; setiap tindakan disertai alasan dan tidak mengeksekusi perubahan machine. |
| `reviewed_disposition` | `COUNT`, `NO_COUNT`, `UNRESOLVED`, atau `OUT_OF_SCOPE`. |
| `reviewed_passage_count` | 1, 0, atau null sesuai keputusan fisik; rider+0 tidak menjadikan parent+0. |
| `event_count_delta`, `category_deltas`, `direction_deltas` | Koreksi terhadap event baseline yang disebut eksplisit; null jika belum dapat dipastikan. |
| `rationale`, `remaining_questions` | Mengapa diputuskan dan apa yang masih menggantung. |
| `supersedes_decision_ids` | Referensi keputusan audit yang digantikan beserta alasan; keputusan terdahulu tetap disimpan. |

`NO_COUNT` berarti telah diputuskan tidak berkontribusi, misalnya rider, duplicate event, atau kendaraan tanpa passage eligible. `UNRESOLVED` tidak sama dengan keputusan+0. Pending tetap di luar subtotal accepted, tetapi jumlah fisik sebenarnya belum diketahui.

**Jangan campur jumlah event yang dibatalkan dengan jumlah passage reviewed.** Jika dua event machine mewakili satu passage, reviewed passage count adalah1 sementara delta event terhadap baseline adalah−1. Jika kategori berubah, total event dapat tetap sama tetapi subtotal kategori berubah. Jangan mengisi delta untuk kasus nyata sebelum baseline dan keputusan benar-benar diperiksa. Review yang membenarkan rider/kategori/identitas tidak mempromosikan route inferred menjadi measured.

Keputusan reviewed disimpan sebagai overlay audit terpisah. Berkas machine beku tetap utuh; mesin belum “diperbaiki” hanya karena review telah diselesaikan.

Untuk `PROPOSE_ADD` pada passage yang terlewat tanpa kandidat/event, gunakan referensi passage manual dan biarkan baseline event IDs kosong; jangan membuat ID event mesin fiktif. `case_action` mencatat tindak lanjut keseluruhan kasus, termasuk `NEEDS_EVIDENCE` atau `POLICY_OPEN`; `event_actions` hanya merinci usulan terhadap event atau passage yang ditunjuk.

## 8. `improvement_backlog.csv` — keluaran perbaikan Phase 1–8

```csv
issue_id,phase,problem_family,problem_statement,case_ids,physical_passage_refs,evidence_level,evidence_refs,affected_scope,observed_impact,occurrence_unit,occurrence_count,proposed_change,alternative_explanation,dependencies,open_decision,priority,priority_reason,verification_input,verification_process,expected_output,regression_cases,execution_cost_known,estimated_cost_assumption,owner,status
```

Prioritas ditentukan dari dampak pada passage fisik, kekuatan bukti, cakupan kondisi, risiko regresi, dan biaya verifikasi. Jangan memakai banyaknya baris CSV atau penurunan pending sebagai satu-satunya dasar. `occurrence_unit` wajib menyebut apakah yang dihitung kasus, passage unik, raw ID, atau tag; jika frekuensi belum diaudit, jumlah tetap kosong.

Untuk tiap fase, rumuskan perbaikan sebagai berikut:

| Fase | Input verifikasi | Proses yang direncanakan | Output yang diminta dari backlog |
|---|---|---|---|
|1 — inspeksi | Video sumber, coverage, kondisi visual, metadata frame. | Petakan gelap/silau/blur/occlusion/shake/alignment pada interval berbukti. | Daftar segmen sulit dan keterbatasan input, bukan skor kualitas rekaan. |
|2 — deteksi | Passage manual, frame sumber, cache bbox/kelas/confidence beserta filter retensinya. | Bedakan tidak ada deteksi, salah kelas dan masalah downstream; catat bukti yang tidak tersimpan. | Kasus detector yang dapat direproduksi dan kebutuhan eksperimen; retraining belum otomatis dipilih. |
|3/4 — tracking/ReID | Deteksi, riwayat track/appearance yang benar-benar tersedia, klip temporal. | Uji kontinuitas, handoff, ID berpindah objek dan kendaraan berdekatan tanpa mengarang embedding. | Kandidat aturan split/stitch beserta kontra-contoh; konfigurasi vehicle-ReID final tetap terbuka. |
|5 — geometri | Geometri/SHA/resolusi acuan, review per video, BC sumber, frame temporal. | Periksa pemetaan ukuran, finite endpoints, margin, polygon dan alignment ketika shake. | Koreksi geometri atau kasus geometri valid yang harus dipertahankan; tanpa default universal. |
|6 — counting | Episode fisik, sumber crossing, log timer/eligibility, event dan keputusan pengguna. | Periksa satu passage/satu event, reset origin, konflik ID, passage selesai, measured vs inferred. | Kebutuhan perubahan aturan dan tes sintetis/regresi yang eksplisit; bukan counting ulang saat audit. |
|7 — malam | Segmen malam raw, output baseline, riwayat eksperimen TOR3, kondisi sulit. | Identifikasi risiko dan rancang pembanding raw/enhancement dengan kontrol sama; bedakan DEV/validasi. | Rencana eksperimen malam berikut beserta passage/regresi/cost yang harus direkam; tidak ada enhancement produksi baru. |
|8 — output | Event snapshot, panel/anotasi versi terikat, raw ID, role/parent dan agregat. | Cocokkan panel dengan event per frame dan akhir video; uji keterbacaan serta pemisahan pending/estimasi. | Daftar perbaikan traceability dan rekonsiliasi, tanpa mengubah counting demi tampilan. |

`status` backlog: `PROPOSED`, `NEEDS_EVIDENCE`, `NEEDS_DECISION`, `READY_FOR_SCOPED_EXPERIMENT`, `BLOCKED`, atau `DEFERRED`. Jangan memberi status implemented/passed ketika hanya ada rancangan. Biaya aktual hanya diisi dari pengukuran; perkiraan diberi label asumsi.

## 9. `comparison.csv` — satu baris per passage fisik atau kasus non-passage

```csv
comparison_ref,reconciliation_group_id,physical_object_ref,physical_passage_ref,video_key,segment_id,case_ids,match_status,baseline_run_id,baseline_event_ids,baseline_measured_event_count,baseline_inferred_event_count,baseline_pending_keys,review_decision_ids,reviewed_disposition,reviewed_passage_count,reviewed_category,reviewed_direction,baseline_false_count,baseline_duplicate,baseline_wrong_merge,baseline_missed_passage,baseline_wrong_role,baseline_wrong_category,baseline_wrong_direction,future_machine_status,future_run_id,future_event_ids,future_event_count,future_failure_tags,event_delta_reviewed_vs_baseline,event_allocation_note,new_regressions,comparison_scope_complete,notes
```

Untuk machine yang belum dibuat/dijalankan, isi `future_machine_status=NOT_RUN` dan biarkan hasilnya kosong. Keputusan manual tidak boleh disalin sebagai hasil machine masa depan. Untuk koreksi yang hanya ada di overlay reviewed, sebutkan `REVIEW_ONLY` dalam catatan.

Tag kegagalan baseline hanya `YES`/`NO` setelah adjudikasi; ketika belum pasti gunakan `UNKNOWN` atau kosong. Satu kasus salah gabung dapat menghubungkan beberapa passage: pakai `case_id` yang sama dan jangan menghitungnya berulang sebagai beberapa kegagalan independen. Pembatalan beberapa event dari satu passage juga tidak berarti beberapa kendaraan fisik telah dikoreksi.

Pada pencocokan many-to-many, gunakan `reconciliation_group_id` yang sama untuk baris terkait. Total baseline dalam kelompok menghitung event IDs unik satu kali; hasil reviewed menghitung passage fisik unik yang diputuskan. Jangan menjumlahkan baseline count atau delta baris yang berbagi event. `event_allocation_note` menjelaskan kepemilikan/alokasi; jika dampak belum bisa dipisahkan per baris, biarkan delta baris kosong dan laporkan delta kelompok pada REPORT.

Jika sumber atau snapshot tidak tersedia, gunakan `UNAVAILABLE`; ketidaktersediaan bukan nol event. Inventaris yang belum lengkap tidak boleh dipakai menyatakan tidak ada missed passage. Rekonsiliasi delta hanya dilakukan pada himpunan unik dengan cakupan dan keputusan lengkap; kasus unresolved dilaporkan terpisah. Jumlah machine dan reviewed merupakan alternatif hasil untuk scope sama, **bukan dijumlahkan**.

Audit ini dapat melaporkan jumlah kasus terkonfirmasi dalam scope. Klaim penurunan kesalahan **machine** baru boleh dibuat sesudah perubahan yang terpisah dijalankan dan passage yang sama dibandingkan, termasuk regresi. Jangan menghitung accuracy, precision, recall, F1, atau MAPE dari template/label pengembangan ini tanpa protokol referensi yang sesuai.

## 10. `REPORT.md` — laporan akhir audit pada scope yang nyata

```markdown
# Phase 9 — laporan audit <audit_id>

Status audit: BELUM_DIISI
Scope dan snapshot yang diperiksa: BELUM_DIISI

## Input dan integritas
- Sumber/versi/hashes/checks yang terverifikasi: BELUM_DIISI
- Decode, alignment, sumber unavailable, serta batas bukti: BELUM_DIISI

## Coverage aktual
- Video dan gabungan interval yang benar-benar direview: BELUM_DIISI
- Raw-first, pilot/development, validasi dan riwayat paparan: BELUM_DIISI
- Bagian/kondisi yang belum direview: BELUM_DIISI

## Temuan terkonfirmasi
- Hitungan palsu, duplikasi, salah gabung, passage terlewat: BELUM_DIISI
- Role, kategori, arah, crossing, estimasi dan output: BELUM_DIISI
- Satuan jumlah dan case/evidence refs: BELUM_DIISI
- Hipotesis penyebab yang belum teruji: BELUM_DIISI

## Keputusan dan dampak
- COUNT, NO_COUNT/+0, UNRESOLVED dan OUT_OF_SCOPE: BELUM_DIISI
- Rekonsiliasi event dan subtotal pada scope yang dapat diputuskan: BELUM_DIISI
- Koreksi reviewed terpisah dari machine beku: BELUM_DIISI
- Implementasi/eksperimen berikut: NOT_RUN kecuali benar-benar diotorisasi dan dijalankan.

## Daftar perbaikan Phase 1–8
- Prioritas, bukti, input, proses, output, dependensi dan regresi: BELUM_DIISI
- Keputusan pengguna yang masih dibutuhkan: BELUM_DIISI
- Rencana verifikasi malam dan keterbatasan generalisasi: BELUM_DIISI

## Penutupan scope dan langkah berikut
- Kasus selesai serta unresolved dengan perlakuannya: BELUM_DIISI
- Alasan scope selesai/partial/blocked: BELUM_DIISI
- Rekomendasi eksperimen/perbaikan terpisah sebelum pembekuan logika: BELUM_DIISI
- Tidak ada promosi otomatis ke Phase 10, produksi, atau klaim zero-error.
```

Phase 9 menghasilkan **referensi audit dan backlog berbasis bukti**. Keputusan implementasi, pemilihan threshold/model, replay perbaikan, serta pengujian kontribusi enhancement malam merupakan pekerjaan lanjutan yang harus mempunyai scope dan hasil aktual tersendiri.
