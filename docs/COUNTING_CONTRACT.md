<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Kontrak counting Phase 6 — TOR3-PAGI, Opsi A

**USER DECISION:** pengguna memilih Opsi A dan mengizinkan Phase 6: metrik passage → unit/rider → kategori → deduplikasi → genuine return → eligibility → parameter dan schema event. Event hanya diterima ketika bukti geometri, unit, kategori, dan identitas memenuhi aturan eksplisit. Konflik ditahan dan tidak masuk subtotal accepted sebelum terselesaikan. Review menggunakan notebook dan berkas audit; tidak membuat UI.

**REQUIREMENT:** kontrak ini melengkapi [COUNTING_LOGIC.md](COUNTING_LOGIC.md), [GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md), [PRODUCT_SPEC.md](PRODUCT_SPEC.md), [API_CONTRACT.md](API_CONTRACT.md) dan [EVALUATION.md](EVALUATION.md). Ia menetapkan prototype counting satu video, bukan default produksi, dataset ground truth, atau evaluasi accuracy. Hasil eksekusi aktual dicatat terpisah dalam review Phase 6.

**ENGINEERING EXPERIMENT:** implementasi awal bersifat **audit-gated**. Semua kandidat yang belum mempunyai review positif atas unit, kategori, dan identitas tetap `pending_review`, termasuk kandidat tanpa overlap yang terdeteksi. Tidak ditemukannya konflik otomatis bukan bukti identitas fisik. Ini baseline konservatif dalam pilihan Opsi A, bukan janji seluruh passage akan ditemukan atau subtotal merupakan batas bawah yang pasti benar.

## 1. Metrik dan sumber kandidat

**USER DECISION — metrik:** hitung **passage fisik valid**, bukan kendaraan unik selama video. Kendaraan yang sama boleh menghasilkan event baru untuk passage kembali yang benar-benar berbeda dan direview. Dua ID pada kendaraan/passage yang sama tidak menjadi dua event.

Sumber kandidat hanya `GEOMETRY_TRANSITION` dari diagnostik Phase 5 tersimpan. Raw detections, jumlah bbox, presence awal, track updates, lifecycle/prediksi dan transisi ambigu tidak menjadi sumber count. Kandidat belum merupakan event accepted.

**FACT — input:** baseline menggunakan [diagnostik `b0_c1`](evidence/phase_5/20261011T161440_100155Z_2e39a11c/b0_c1_diagnostics.jsonl.gz), cache emitted-track `reid_on` Phase 4, dan [G3 diterima](evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json). Parameter yang sudah dijalankan adalah `neutral_band_px=0` native-pixel half-width dan `confirmation_observations=1`. Memilih kontrol tersimpan ini untuk eksperimen counting tidak berarti pengguna memilih nilai numerik atau bahwa nilai itu cocok untuk produksi. Tidak menjalankan ulang geometri, YOLO, tracker, ReID atau preprocessing.

**REQUIREMENT — geometri tidak berubah:** BC berasal dari `raw_bbox` emitted-track yang terhubung ke pengukuran Phase 2. Origin → passage pada interior segmen terbatas → opposite-ROI confirmation harus terukur dan kontinu sesuai kontrak Phase 5. Batas netral, touch-only, endpoint/gap ambigu dan prediksi tetap tidak dapat mengesahkan crossing. Review manual tidak boleh mengubah diagnostik ambigu menjadi crossing sah atau menyambungkan trajectory lintas ID/gap.

## 2. Unit kendaraan, rider dan pedestrian

**ENGINEERING EXPERIMENT — unit:** kendaraan dengan pengemudi/penumpang adalah satu unit kendaraan. Rider dan penumpang bukan passage kendaraan tambahan. Raw `person` bukan pemetaan otomatis ke pedestrian; dibutuhkan review bahwa orang tersebut berjalan sebagai pedestrian dan bukti pengukuran person yang mendukung passage lengkap.

Seluruh pengukuran emitted `raw_bbox` dalam interval **origin sampai confirmation, inklusif**, diperiksa, bukan hanya kelas terakhir/event. Tautan frame, track, source detection, video dan coordinate space harus konsisten.

| Bukti kandidat | Perlakuan prototype |
|---|---|
| Histori person konsisten, belum direview | Pending; tidak otomatis pedestrian. |
| Person dikonfirmasi sebagai rider/penumpang oleh review pixel | Rejected sebagai unit hitung tersendiri; sumber tetap tersimpan. |
| Person dikonfirmasi sebagai pedestrian berjalan, crossing terukur penuh, identitas/kategori jelas | Dapat accepted setelah semua gate lain terpenuhi. |
| Histori berpindah person ↔ kelas kendaraan dalam window | `UNIT_COMPONENT_CHANGE`, hard pending; tidak dapat diatasi hanya dengan override kategori atau konfirmasi identitas. |
| Histori kendaraan konsisten | Tetap memerlukan review positif; label model tidak membuktikan unit fisik. |
| Unit tidak jelas/occluded/unsupported | Pending dengan alasan dan kebutuhan bukti. |

**OPEN:** recovery dari trajectory yang mencampur komponen memerlukan eksperimen terpisah. Baseline ini tidak memilih sub-window baru agar candidate hard-blocked terlihat eligible.

## 3. Kategori dan stabilisasi kelas

**REQUIREMENT — kategori produk:** pedestrian, motorcycle, car, truck, dan bus/angkot. **ENGINEERING EXPERIMENT — serialisasi prototype:** `pedestrian`, `motorcycle`, `car`, `truck`, `bus_angkot`; ini bukan taxonomy model baru atau schema produksi final.

Raw class evidence disimpan utuh dalam window origin–confirmation. Kandidat single-label motorcycle/car/truck dapat memperoleh interpretasi kategori eksperimental tersebut **hanya setelah review unit/kategori/identitas positif**. Confidence tinggi, latest label, majority vote, atau label yang konsisten sendiri tidak memenuhi gate acceptance.

- Konflik `car↔truck` dalam keluarga kendaraan adalah konflik kategori yang dapat direview apabila aturan kategori yang berlaku dan bukti fisik memang mendukung resolusi. Perubahan unit person↔kendaraan tetap hard-blocked.
- Pickup ambigu tidak otomatis car ataupun truck. Taxonomy pickup tetap OPEN; review tidak boleh mengarang kebijakan bisnis untuk menyelesaikannya.
- Raw `bus` tidak otomatis menyelesaikan kategori bus/angkot. Pemetaan serta pembeda angkot tetap OPEN, sehingga kandidat terkait ditahan ketika keputusan itu diperlukan.
- Kategori final event harus mempunyai supporting class history, review/evidence reference dan alasan. Kategori bukan bagian identitas passage/event: koreksi kategori tidak menciptakan kendaraan atau passage baru.

## 4. Deduplikasi identitas dan passage

**ENGINEERING EXPERIMENT — screening, bukan bukti duplicate:** positive-area overlap bbox kandidat dengan **raw vehicle detections lain** pada window origin–confirmation menandai kebutuhan review identitas. Tidak memakai threshold IoU baru. Raw detections hanya bukti konflik tambahan dan tidak pernah menjadi count source. Overlap dengan person dapat merupakan rider; tidak otomatis membuat kendaraan ineligible. Tidak overlap juga bukan bukti satu ID = satu kendaraan.

**REQUIREMENT — positive identity evidence:** review menetapkan `physical_unit_id` dan `passage_id` dalam scope input video untuk kandidat yang dipahami. Dua kandidat boleh dideduplikasi hanya ketika review mengonfirmasi **unit fisik yang sama dan passage yang sama**. Spatial proximity atau ReID/tracker ID saja tidak cukup.

Dalam grup yang sudah dikonfirmasi, pilih satu kandidat representatif secara deterministik dari kandidat dengan geometri dan histori unit yang hard-eligible; gunakan urutan `crossing_frame_start`, `crossing_frame_end`, `confirmation_frame`, `origin_frame`, `track_id`, lalu `candidate_id`. Simpan semua candidate/track/source references dan alasan pemilihan. Kandidat dengan unit-changing history tidak menjadi representatif accepted. Pengelompokan sumber tidak menggabungkan pengukuran menjadi trajectory buatan.

**OPEN:** asosiasi/deduplikasi fisik otomatis, threshold overlap/appearance dan recovery lintas ID belum diimplementasikan sebagai resolver. Bukti review yang tidak cukup tetap pending.

## 5. Genuine return dan eligibility

**ENGINEERING EXPERIMENT — return:** passage berikutnya dari ID/unit yang sama ditahan sebagai `RETURN_EPISODE_REVIEW_REQUIRED` sampai review membuktikan episode baru. Berikan `passage_id` berbeda dan bukti temporal yang menunjukkan crossing terukur terpisah; arah berlawanan saja, frame gap, atau nomor transisi baru tidak cukup. Tidak menerapkan once-per-lifetime-ID dan tidak menerima semua recross otomatis.

**ENGINEERING EXPERIMENT — temporal contradiction guard:** dua `passage_id` berbeda pada unit yang sama dengan interval passage terukur yang bertumpang tindih secara positif ditahan sebagai `OVERLAPPING_PASSAGE_EPISODES`, termasuk ketika review menandai independent return. Batas frame bersama boleh terjadi; tidak mensyaratkan pergantian arah atau cooldown baru. Episode yang waktunya terpisah tetap membutuhkan review positif, bukan diterima hanya karena lolos guard ini.

Satu event accepted memerlukan semuanya:

1. Sumber/coordinate/measurement dan geometri valid, dengan origin, passage dan confirmation terukur lengkap.
2. Histori unit tidak mempunyai hard block person↔kendaraan.
3. Review pixel positif untuk unit, kategori dan identitas; metadata audit serta frame evidence terverifikasi.
4. Tidak ada konflik kategori/identitas yang belum diselesaikan; grup duplicate terkonfirmasi menghasilkan satu representatif.
5. Jika passage berulang, episode baru dikonfirmasi secara terpisah.

Tidak menambahkan minimum umur track, confidence threshold, displacement, atau timeout numerik tanpa eksperimen yang memberi alasan. Aktivasi emitted-track dan bukti crossing tersimpan merupakan prasyarat teknis; keduanya bukan jaminan fisik. Initial-frame presence tidak pernah counted sendiri.

## 6. Keputusan mesin, review dan output resolved

**REQUIREMENT — pemisahan:** candidate evidence, keputusan mesin awal, input review, keputusan resolved dan accepted event adalah lapisan berbeda. Pertahankan seluruhnya; tidak mengedit hasil mesin agar seolah sudah otomatis mengesahkan kasus hasil review.

| Status | Makna |
|---|---|
| `pending_review` | Bukti/keputusan belum cukup atau ada hard block; tidak masuk subtotal. |
| `rejected` | Review mendukung non-unit hitung/rider atau keputusan penolakan eksplisit; alasan/source tetap ada. |
| `accepted` | Semua gate terpenuhi; menghasilkan atau mereferensikan satu event passage. |
| Duplicate member | Sumber tambahan untuk event yang sama; tidak mengeluarkan count tambahan. Encoding keputusan mengikuti helper yang tercatat. |

Review harus mempunyai identitas/versi reviewer, candidate references, disposition, unit/category/identity conclusions, physical unit dan passage references bila relevan, alasan dan evidence references. Review dapat dibantu AI dengan pemeriksaan pixel aktual; ini observasi audit terbatas, bukan formal ground truth.

Evidence reference mempertahankan path, SHA-256 dan frame index/range yang mendukung klaim. Review acceptance harus mencakup origin, passage/contact interval dan confirmation serta bukti cukup untuk identitas/komponen; satu gambar tanpa temporal support tidak membuktikan semuanya. Contact sheet harus menyebut frame sumbernya. Pemeriksaan hash memastikan artefak yang direview tetap sama, bukan kebenaran interpretasi visual. Jangan mengklaim seluruh video sudah diaudit dari review beberapa window.

Review tidak boleh menerima predicted/gap/endpoint crossing, menutupi `UNIT_COMPONENT_CHANGE`, atau menyelesaikan taxonomy yang masih OPEN lewat kategori tanpa kebijakan. Invalid/contradictory review input ditolak atau ditahan secara eksplisit; tidak silently diterima.

## 7. Schema event dan identitas deterministik

**ENGINEERING EXPERIMENT — prototype schema:** bentuk konkret JSON mengikuti helper yang dicatat bersama konfigurasi run. Minimum logical information berikut wajib tersedia; bukan public API produksi.

| Informasi | Isi |
|---|---|
| Identity layers | `candidate_id`, review reference, `event_id`, `physical_unit_id`, `passage_id`, semua member/source track references. |
| Input/config namespace | Video SHA-256, cache Phase 4 SHA-256, diagnostik Phase 5 SHA-256, geometry SHA-256, versi dan identitas konfigurasi counting. |
| Geometry evidence | A→B/B→A, origin/passage/confirmation frame/point, measured raw bbox dan source-detection references, kontak bila ada. |
| Category evidence | Kategori resolved, raw class history/window, dasar keputusan dan review source. |
| Decision evidence | Status/reasons, duplicate resolution, return-episode resolution, evidence path/hash/frame scope. |
| Time | Passage frame/contact interval dan confirmation frame disimpan berbeda. Frame/FPS timestamp adalah estimasi; authoritative source PTS tetap UNKNOWN. |
| Context | Metadata store/day type yang diketahui; nilai tidak diketahui disimpan `null`, tidak diinferensikan dari filename. |

Logical IDs deterministik dalam namespace input/config. Candidate identity berasal dari measured transition/source references; event identity dari physical unit + passage dalam namespace tersebut, **tidak kategori, UTC waktu eksekusi atau random run ID**. Mengoreksi kategori tidak membuat event fisik kedua. Perubahan input/config substantif menghasilkan snapshot namespace berbeda yang tidak dijumlahkan silang sebagai satu hasil.

## 8. Agregasi, rerun dan koreksi

**REQUIREMENT — rekonsiliasi:** satu snapshot aggregate dihitung hanya dari event accepted unik pada hasil resolved dan konfigurasi yang dipilih. Per-category subtotal harus sama dengan jumlah accepted event kategori itu. Pending/rejected/duplicate members terlihat dalam laporan terpisah dan tidak masuk subtotal. Arah dipertahankan dalam event/audit; tidak mengubah requirement layout final produk.

**ENGINEERING EXPERIMENT — idempotensi:** duplicate update atau rerun atas input/config/review yang sama menghasilkan event IDs dan total yang sama. Menulis snapshot tidak append/menjumlahkan rerun lama. `machine_events`/`machine_aggregate` dan resolved `accepted_events`/`aggregate` disimpan terpisah; dalam audit-gated v0 kandidat tanpa review positif tidak menghasilkan machine accepted event.

Manual correction berupa review yang dapat direkonstruksi, bukan edit total tanpa event. Simpan input review dan kedua hasil untuk audit. UI Edit Value dan audit/versioning produksi tetap fase berikutnya.

## 9. Interface, validasi dan batas

**ENGINEERING EXPERIMENT — interface notebook prototype:** `run_counting(diagnostics_path, records_path, geometry_path, *, config, reviews=None, evidence_root=None)` mengembalikan `machine_decisions`, `resolved_decisions`, `machine_events`, `accepted_events`, `machine_aggregate`, `aggregate`, dan `report`. Helper berada di `notebooks/phase_6_counting_helpers.py`; bukan refactor `src/` Phase 10.

Jalankan tes deterministik dalam `notebooks/phase_6_synthetic_tests.py` sebelum memproses artefak aktual. Kasus wajib: unreviewed hold, full measured A→B/B→A, unit changes, rider/pedestrian, category conflict, evidence/hash validity, duplicate same passage, distinct genuine return, initial presence, immutable geometry ambiguity, idempotensi dan aggregate reconciliation. Gunakan review fixture sebagai fixture software, bukan review video nyata.

Notebook `notebooks/06_counting_audit.ipynb` memproses evidence tersimpan dan menyimpan event-level output, subtotal, audit queue, konfigurasi/provenance dan visualisasi crossing dari frame aktual tersedia. Review real pixel harus benar-benar dilakukan dan cakupannya dicatat sebelum hasil disebut evidence-backed. Laporan hasil eksekusi dibuat setelah eksekusi, terpisah dari kontrak ini.

**OPEN:** suitability numerik, taxonomy pickup/bus/angkot, recovery unit-changing histories, otomatisasi identity resolver, whole-video audit completeness, final vehicle-ReID configuration, source PTS dan generalisasi video lain. ReID tetap bagian arsitektur. Tidak memulai Phase 7 night enhancement, Phase 8 delapan-video, UI, Docker, GMC/stabilisasi atau inference baru.

**FACT — batas evaluasi:** belum ada formal ground truth. Tes dan rekonsiliasi menguji correctness software; bounded pixel review mendukung kasus yang benar-benar dilihat. Subtotal accepted bukan total traffic lengkap yang tervalidasi dan tidak mendukung klaim accuracy/precision/recall/F1/MAPE atau keunggulan Opsi A.
