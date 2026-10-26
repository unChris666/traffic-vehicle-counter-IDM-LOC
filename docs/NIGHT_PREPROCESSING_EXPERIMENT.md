<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Protokol eksperimen enhancement TOR3-MALAM

**REQUIREMENT — Phase 7:** bandingkan kontribusi enhancement terhadap input malam dengan pipeline tetap dan raw sebagai kontrol. [Task/gate](PHASE_7_TASK.md) memisahkan photometric/YOLO screen DEV dari eksperimen temporal. N1/arah malam telah diterima untuk uji awal; shortlist DEV dibekukan sebelum inference temporal/hold-out. Screen dan raw-versus-gamma temporal benar-benar selesai di Kaggle pada 14 Oktober 2026. Dokumen ini menyatakan recipe, metode penilaian dan execution yang tersedia; penilaian passage serta keputusan akhir berada di [PHASE_7_REVIEW.md](PHASE_7_REVIEW.md).

## 1. Raw baseline dan kandidat awal

Raw baseline adalah frame BGR uint8 hasil decoder TOR3-MALAM tanpa tambahan enhancement. Pemrosesan standar model—resize/letterbox, konversi channel dan normalisasi—tetap berlaku. Tidak memakai hasil PAGI sebagai raw baseline malam dan tidak menghapus burned-in text agar perbandingan terlihat lebih baik.

**ENGINEERING EXPERIMENT — kontrol awal:** satu recipe per kandidat, tidak ada kombinasi pada tahap pertama. Nilai berikut adalah kontrol development yang eksplisit, bukan threshold optimum, produk requirement, atau angka hasil tuning video malam.

| ID | Recipe awal | Tujuan yang diuji | Risiko yang perlu direview |
|---|---|---|---|
| `raw` | Frame asli | Pembanding wajib | Detail bodi gelap mungkin tidak terlihat. |
| `gamma_070` | `255 × (x/255)^0.7` | Menguji perubahan detail gelap tanpa pergeseran spasial | Noise/teks/latar bisa ikut terang; hubungan warna atau edge dapat berubah. |
| `exposure_125` | `1.25 × x` | Menguji gain linear sederhana | Saturasi dan glare dapat bertambah; detail yang sudah clipped tidak dipulihkan. |
| `contrast_125` | `128 + 1.25 × (x − 128)` | Menguji pemisahan intensitas dengan pivot tetap | Piksel gelap dapat makin gelap dan highlight makin clipped. |
| `unsharp_s1_a05` | `x + 0.5 × (x − GaussianBlur(x, σ=1))` | Menguji peningkatan edge lokal | Noise, halo pada lampu, dan burned-in text dapat ikut menajam. |

Di sini `x` berarti intensitas setiap channel BGR uint8. [Helper](../notebooks/phase_7_night_helpers.py) menghitung float64, memakai `np.rint` (ties-to-even), lalu clipping `[0,255]` dan encoding uint8. Gaussian memakai OpenCV kernel otomatis `(0,0)`, sigmaX/sigmaY `1`, dan `BORDER_REFLECT_101`; simpan versi OpenCV aktual. Transform dihitung per-channel BGR, tanpa adaptive pivot atau lookup inverse-gamma. Recipe tidak mengubah lebar/tinggi, tidak crop/rotate/stabilize, tidak menggunakan model enhancement lain, dan tidak menginpaint tulisan. `raw` menghasilkan array copy yang identik agar source tidak berubah.

Formula gamma memakai **eksponen langsung 0,7**, bukan konvensi inverse-gamma tersembunyi. Gain 1,25 adalah pengalian intensitas digital, bukan klaim mengubah exposure sensor. Contrast pivot128 tetap antarkondisi dan tidak diestimasi dari tiap frame; sharpening bukan deblurring. Tidak ada kandidat yang dijanjikan memulihkan detail yang tidak direkam kamera.

## 2. Sampel, DEV dan hold-out

**ENGINEERING EXPERIMENT:** tiga segmen DEV dan dua hold-out, masing-masing 240 frame kontinu, menjadi anggaran awal. Konfigurasi machine-readable harus menyebut start/end frame inclusive, split, source SHA, frame screen dan alasan pemilihan. Semua recipe menerima frame yang sama; raw selalu ikut.

Plan v1: [TOR3-MALAM_sampling_plan_v1.json](evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json).

| Split | Frame sumber inclusive | Frame screen 7A |
|---|---|---|
| DEV awal | 0–239 | 0, 7, 14, 29, 239 |
| DEV sekitar seperempat | 2277–2516 | 2277, 2337, 2397, 2457, 2516 |
| DEV sekitar tiga-perempat | 7072–7311 | 7072, 7132, 7192, 7252, 7311 |
| Hold-out sekitar tengah | 4674–4913 | Tidak dieksekusi pada screen 7A |
| Hold-out akhir | 9350–9589 | Tidak dieksekusi pada screen 7A |

Posisi berasal dari sampling source Phase 1 dan pembagian development/hold-out yang ditentukan sebelum inference Phase 7, bukan pemilihan berdasar keluaran kandidat. Lima foto per segmen adalah screen frame-level. Pada tahap temporal, seluruh 9.590 frame diproses per branch untuk menjaga konteks source/entry/episode; window 240 frame adalah scope review, bukan reset tracker atau potongan yang dianggap passage lengkap otomatis.

Counting tetap scoped pada kelima window deklarasi, bukan full-video traffic aggregate. IDs case berasal dari actual emitted observations di windows secara terpisah per variant; jangan menyalin IDs PAGI atau menyamakan ID lintas raw/kandidat. Seluruh cache source divalidasi/dibagi episode sebelum memilih scope, sehingga origin/person/gap/return tidak hilang karena potongan window. Window tidak digeser sesudah outcome untuk memperbaiki subtotal.

Decoder sequential dapat membaca lalu membuang frame di antara DEV windows, termasuk posisi hold-out di tengah. Ini berbeda dari menyimpan enhancement/output model hold-out untuk pemilihan: screen mengambil hanya 15 indeks DEV yang diumumkan, tidak melakukan enhancement atau inference pada frame reserved tersebut.

Saat memilih kandidat/nilai, gunakan DEV saja. Hold-out disimpan sebagai sample plan namun tidak diinferensikan/enhanced untuk pemilihan screen tahap awal. Setelah shortlist dan nilai dibekukan, full-video temporal inference juga mencakup hold-out dan menyediakan outcome untuk review terpisah. Jika hold-out dipakai untuk revisi, nyatakan hasil sebagai development baru dan gunakan hold-out lain/version baru untuk penilaian berikutnya.

Source Phase 1 sudah pernah direview dan builder plan membuka raw temporal sheets kelima window, termasuk hold-out. Split ini menahan hasil enhancement/inference hold-out dari pemilihan parameter; tidak disebut blind dataset. Lima window di satu video tidak mewakili seluruh kondisi malam. Kebutuhan konteks crossing berlaku: vehicle harus terlihat cukup sebelum/sesudah; passage di tepi segmen diberi status incomplete bila bukti tidak cukup. Tambahkan konteks hanya melalui perubahan manifest terdokumentasi sebelum perbandingan yang bergantung pada konteks baru, bukan menyambung trajectory dari frame tidak diamati.

## 3. Konfigurasi tetap dan attribution

Detector memakai asset/config Phase 2 terverifikasi; catat resolved settings dan actual backend. Re-run night inference memang dibutuhkan karena input berubah. Gunakan full-frame inference dengan semua raw class, tanpa crop/ROI filtering yang mengubah kumpulan bukti.

Saat tahap temporal dibuka, detector, BoT-SORT, encoder ReID, geometry, BC, grouping/category/counting dan review schema tetap sama antarkondisi. Tracker baru/reset pada awal setiap variant, lalu berjalan dari frame 0 hingga 9589 tanpa reset antarsample-window. Tidak membawa state raw ke enhanced. Kedua branch menerima urutan source/konteks lengkap yang sama; lifecycle/gallery dan offline whole-episode category dapat melintasi DEV/hold-out. Ini perbandingan longitudinal satu video, bukan dua kelompok iid/blind atau independen secara state.

**ENGINEERING EXPERIMENT — encoder input dibekukan:** enhancement mengubah frame yang masuk detector **dan** ReID pada branch kandidat. Encoder menerima frame native/transformed yang sama dengan detector (`SAME_TRANSFORMED_FRAME_AS_DETECTOR`); pada raw keduanya menerima frame asli. Ini menguji faktor enhancement pada pipeline menyeluruh, bukan mengisolasi efek detector dari appearance. Eksperimen isolasi memakai encoder raw tetap adalah tugas lain; tidak mengubah policy di tengah perbandingan. Screen 7A tidak menjalankan encoder dan belum membuktikan policy ini membantu.

**DECISION:** architecture tetap ReID; final vehicle encoder masih OPEN. Kandidat eksternal resmi Phase 4 `yolo26n-reid.onnx`, SHA-256 `8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb`, menjadi kontrol temporal malam karena kompatibilitas sudah dieksekusi pada PAGI, bukan vehicle default yang diterima. Pertahankan source/settings/preprocessing yang diverifikasi dalam [REID_EXPERIMENT.md](REID_EXPERIMENT.md), termasuk provenance person-domain dan keputusan sebelumnya; jangan menyebutnya encoder vehicle terverifikasi. Pin ONNX/ONNXRuntime dan actual CUDA provider dicatat dan diverifikasi saat execution, bukan diinferensikan dari `cuda_available` saja.

Kontrol association B v1 dan geometri numeric tidak dituning bersamaan dengan enhancement. Night source hashes, IDs, frame windows, parent run dan geometry namespace harus berasal dari eksekusi malam aktual. Jumlah observasi/ID/confidence dapat berubah; ini outcome yang diperiksa, bukan pelanggaran kontrol. Nomor track lintas run bukan identity kendaraan fisik.

Shortlist/config temporal: [DEV_shortlist](evidence/phase_7/selection/TOR3-MALAM_DEV_shortlist_v1.json), [config](evidence/phase_7/config/TOR3-MALAM_temporal_v1.json), dan [notebook 07b](../notebooks/07b_night_temporal_comparison.ipynb). Recipe gamma0,7 dibekukan dari hasil 15 frame screen DEV beserta alasan/pixel references sebelum inference temporal baru. [Run aktual](evidence/phase_7/temporal/20261014T062858_002323Z/report.json) kemudian menyelesaikan seluruh 9.590 frame pada masing-masing branch raw/gamma. Menghasilkan record model hold-out setelah freeze tidak sama dengan memakai outcome hold-out untuk pemilihan recipe; tidak ada retuning setelah outcome hold-out.

## 4. Geometri dan audit temporal

**USER-CONFIRMED INITIAL EXPERIMENT — N1:** [feedback pengguna](evidence/phase_7/feedback/N1_review_001.json) menerima garis/polygon N1 dan A→B=mendekati/B→A=menjauhi kamera untuk TOR3-MALAM. [Accepted N1](evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json), SHA-256 `89ff1d6201fba37d6edb9501f1524a5c96781ff1b9f442f25b728cb4d543c7a4`, terpisah dari proposal historis immutable. Polygons/line memakai BC raw vehicle bbox, finite segment, batas netral dan gap/endpoint/prediction gate yang sama; enhancement photometric tidak mengubah koordinat, tetapi bbox hasil detector dapat berubah. Persetujuan uji awal bukan bukti continuous alignment, reliabilitas semua video atau parameter produksi.

Geometri/semantik trial sudah diulas dan dikonfirmasi langsung untuk malam; tidak menyalin approval PAGI sebagai evidence MALAM. Pada actual temporal review, tetap periksa area silau/teks, kendaraan terpotong, alignment dan sumber crossing. Jangan menganggap satu screenshot membuktikan seluruh video atau menerima crossing yang diblok melalui review kategori.

Pada tahap temporal, pasangkan kendaraan/passage fisik memakai frame/trajectory/pixel evidence; simpan `physical_passage_reference` audit lintas variant terpisah dari tracker ID. Setiap row harus menunjukkan raw, kandidat, keputusan mesin, review dan sumber crossing; review tidak mengganti output mesin asli.

| Pertanyaan | Bukti minimum yang perlu disimpan |
|---|---|
| Salah penggabungan? | Kendaraan berbeda yang coexist, full-frame/temporal references, parent/group relations. |
| Duplikasi? | Dua kandidat untuk kendaraan/passage sama, source episode/bbox, group dan event unik. |
| Rider dihitung sebagai kendaraan tambahan? | Vehicle/rider roles, group, dan crossing BC kendaraan yang aktual. |
| Kategori berubah? | Raw class history, vehicle-only category evidence, manual taxonomy basis atau pending reason. |
| Crossing berubah? | Origin, line interval, confirmation, raw vehicle BC/source detection, gap/endpoint validity. |
| Kendaraan masih tidak terlihat? | Raw/enhanced frame yang sama, occlusion/clipping/blur/glare notes, missing observation context. |
| Ada regresi baru? | Contoh nyata kegagalan tambahan dibanding raw, bukan hanya contoh kandidat yang bagus. |

Reviewer membedakan confirmed observation, UNKNOWN dan HYPOTHESIS_UNTESTED. Kasus pending tetap tidak masuk subtotal accepted. Review manual `car` tidak menutup competitor identity yang tidak jelas; genuine return memerlukan bukti passage baru yang terpisah. Tidak menggunakan lower pending count sebagai satu-satunya tujuan.

## 5. Output dan pemilihan kandidat

Setiap run menyimpan input/code/config hashes, sample plan, versions/device, recipe lengkap, raw/enhanced images, detector raw records, output arrays yang tervalidasi, annotations/contact sheets, timestamps/frame indices, errors serta timing/resource yang benar-benar diukur. Bila CPU/GPU/RAM value tidak tersedia, simpan `null`/UNKNOWN dengan sebab; jangan mengarang angka.

Pisahkan preprocessing wall time, detector inference wall time (synchronization CUDA yang konsisten bila relevan), decode/export/setup, dan total wall time. Catat warmup/state serta pengaruh sequential order. GPU memory CUDA allocated/reserved bukan total VRAM proses atau utilisasi; nilai `nvidia-smi` memakai definisi tersendiri. Screen jarang per frame bukan full-video throughput.

**ENGINEERING EXPERIMENT — warmup screen:** setiap variant melakukan satu prediction warmup memakai frame DEV pertamanya, di luar serialized measured predictions dan statistik inference terukur. Raw dan kandidat mendapat policy warmup yang sama; simpan warmup sebagai call nyata terpisah. Total model calls tidak sama dengan jumlah JSONL prediction rows ketika warmup ada.

Before/after dan confidence/detection counts adalah diagnostik, bukan accuracy. Screen DEV menghasilkan observasi dan shortlist/proposal; tidak memberi traffic total, tracking/reID benefit, selected production preprocessing, atau Phase 7 acceptance penuh.

Sesudah temporal + hold-out benar-benar dieksekusi, keputusan terikat scope:

- Pilih kandidat bila review menunjukkan kontribusi yang didukung bukti dan regresi/resource yang dapat diterima untuk scope tersebut.
- Pertahankan raw bila kontribusi tidak terbukti atau regresi dominan.
- Tetap OPEN bila physical identity/crossing/coverage belum dapat dievaluasi.

Tidak ada kriteria numerik improvement yang diciptakan dari absennya ground truth. Pemilihan kandidat tidak menutup taxonomy, final vehicle-ReID, tuning deduplikasi, genuine return automation atau kelengkapan full-video traffic. Tidak melaporkan accuracy, precision, recall, F1, MAPE atau tracking/counting performance tanpa protokol dan evidence ground truth.

## 6. Execution aktual dan batas interpretasi

**EXPERIMENT RESULT:** [screen `20261014T060849_366767Z`](evidence/phase_7/screening/20261014T060849_366767Z/report.json) menjalankan kelima recipe pada 15 frame DEV; [review DEV](evidence/phase_7/screening/20261014T060849_366767Z/visual_review/visual_review.json) merekam perubahan gambar serta regresi sebelum gamma0,7 dibekukan. [Temporal `20261014T062858_002323Z`](evidence/phase_7/temporal/20261014T062858_002323Z/report.json) menjalankan YOLO26M dan encoder pada Tesla T4 `cuda:0`, association CPU, 9.590 frame raw lalu 9.590 frame gamma. Dua GPU terlihat tetapi eksperimen memakai satu GPU; tidak ada multi-GPU orchestration.

| Snapshot mesin | Accepted | Pending | Lingkup |
|---|---:|---:|---|
| Raw — DEV | 0 | 6 | Tiga window DEV, enam kandidat crossing mesin |
| Gamma0,7 — DEV | 1 | 5 | Window dan input source yang sama |
| Raw — hold-out | 0 | 2 | Dua window hold-out, dua kandidat crossing mesin |
| Gamma0,7 — hold-out | 0 | 2 | Recipe/kontrol yang sudah dibekukan |

Sumbernya adalah [keputusan raw](evidence/phase_7/temporal/20261014T062858_002323Z/raw/machine_passage_decisions.json.gz) dan [keputusan gamma](evidence/phase_7/temporal/20261014T062858_002323Z/gamma_070/machine_passage_decisions.json.gz). Tabel ini mempertahankan **machine output**, bukan keputusan setelah review; tidak menjamin semua passage fisik di window telah ditemukan. Satu accepted mesin gamma memakai vehicle motorcycle, bukan rider BC. Review fisik harus tetap memeriksa unit/rider, sumber crossing, duplicate, salah gabung, kategori dan kegagalan yang tidak menghasilkan kandidat. Output review disimpan terpisah; status pending review pada report asli tidak diedit untuk menyamakan hasil dengan snapshot final.

| Wall time aktual | Raw, detik | Gamma0,7, detik |
|---|---:|---:|
| Decode | 10,241 | 12,225 |
| Transform | 3,337 | 450,340 |
| Detector | 181,779 | 257,648 |
| Tracker, termasuk encoder | 392,491 | 397,027 |
| Encoder, bagian dari tracker | 380,939 | 384,935 |
| Loop penuh terinstrumentasi | 673,549 | 1.205,209 |

Encoder tidak dijumlahkan lagi ke tracker. Loop gamma sekitar `1,79×` raw pada run sequential ini; transform menyumbang waktu besar pada implementasi float64 yang benar-benar diuji. Urutan branch, warmup dan instrumentasi membatasi atribusi cost; hasil ini tidak menetapkan throughput produksi atau biaya moneter. CUDA peak allocated/reserved yang dilaporkan adalah alokasi Torch, bukan keseluruhan VRAM proses encoder ONNXRuntime. Model weights dan video source tidak disimpan di GitHub; SHA/URL/runtime serta artefak derivasi mendukung reproduksi di Kaggle.

**DECISION BOUNDARY:** manfaat, regresi, keputusan raw/kandidat dan penerimaan Phase 7 mengikuti [review akhir](PHASE_7_REVIEW.md). Full-video model execution memberi konteks historis untuk lima window scoped; tidak mengubahnya menjadi total traffic video, audit lengkap atau bukti generalisasi. Final vehicle-ReID, taxonomy terbuka, tuning numeric yang tahan jitter, genuine return automation dan audit kelengkapan tetap tugas terpisah. Phase 8 belum dimulai melalui dokumen ini.
