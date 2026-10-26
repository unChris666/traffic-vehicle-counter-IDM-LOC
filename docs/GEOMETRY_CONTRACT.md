<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Kontrak geometri Phase 5 — TOR3-PAGI

**FACT — keputusan dan asal persetujuan:** [feedback G3 001](evidence/phase_5/feedback/G3_review_001.json) mempertahankan G3 dan polygon B, serta memberi nama pada empat titik A yang sudah ada. Jawaban tersebut dibaca dalam konteks pertanyaan yang menyertakan aturan awal BC, segmen terbatas, batas netral, sentuhan, endpoint, gap, dan prediksi. Ini penerimaan kontekstual atas baseline kualitatif, bukan kutipan persetujuan terpisah untuk setiap aturan atau pemilihan threshold numerik. Pertanyaan, jawaban, dan interpretasi disimpan bersama; draft historis G1/G2/G3 tidak ditulis ulang.

**REQUIREMENT — cakupan:** kontrak ini mengatur diagnostik geometri atas trajectory satu track. Ia melengkapi [COUNTING_LOGIC.md](COUNTING_LOGIC.md), [API_CONTRACT.md](API_CONTRACT.md), [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md) dan [PHASE_5_TASK.md](PHASE_5_TASK.md). Phase 5 tidak menetapkan `CountEvent`, jumlah kendaraan, kategori produk, deduplikasi identitas fisik, atau kebijakan bisnis crossing berulang. Hasil tes/replay harus dilaporkan dari eksekusi nyata, bukan dianggap ada oleh dokumen ini.

## 1. Geometri dan koordinat

**FACT — template yang dipakai:** G3 menggunakan canvas baru **960 × 540**, bukan rekonstruksi ukuran gambar berskala terdahulu yang tetap UNKNOWN. [G3-L1](evidence/phase_5/review_drafts/G3-L1/README.md) hanya menambahkan label; angka tidak dipindahkan.

| Elemen | Koordinat pada template 960 × 540 |
|---|---|
| Segmen counting line | P1 `(4.5, 516.5)` → P2 `(936.4, 305.4)` |
| P1A | `(4.5, 516.5)` |
| P1B | `(4.5, 348.2)` |
| P1C | `(936.6, 305.8)` |
| P1D | `(557.5, 165.3)` |
| Polygon B, urutan keliling | `(4.5, 516.5)` → `(875, 319.72460036476775)` → `(875, 532.5)` → `(4.5, 532.5)` |

**REQUIREMENT — representasi polygon A:** gunakan keliling sederhana **P1A → P1B → P1D → P1C → P1A**. Nama titik menyatakan identitas titik, bukan instruksi traversal P1A → P1B → P1C → P1D. Urutan keliling sederhana mempertahankan empat koordinat yang diterima; urutan alfabet akan membuat tepi berpotongan. Ini pilihan representasi geometri untuk memenuhi validitas polygon, bukan pemindahan titik pengguna.

**REQUIREMENT — transform eksplisit:** normalisasi `u=x/960`, `v=y/540`; untuk frame native berukuran `W × H`, gunakan `(x_native, y_native)=(u×W, v×H)`. Origin di kiri atas, X ke kanan dan Y ke bawah. Koordinat geometri bersifat kontinu pada tepi citra `[0,W] × [0,H]`; indeks array pixel tetap `0..W-1` dan `0..H-1`. Lebar/tinggi frame wajib positif dan konsisten dengan observasi.

**REQUIREMENT — batas validitas:** titik harus finite, polygon sederhana dengan luas bukan nol, dan garis memiliki panjang bukan nol. Interior A/B tidak boleh overlap; tepi bersama boleh ada dan diperlakukan netral. Konfigurasi invalid harus ditolak dengan alasan, tanpa clamp, perubahan urutan diam-diam, atau snapping. Area di luar kedua polygon bukan A/B. Penyesuaian untuk crop, rotasi, resize/letterbox atau transform spasial lain harus dinyatakan sebelum digunakan; transform tersebut tidak diinferensikan oleh template.

**FACT — garis dan polygon berbeda:** P2 garis berbeda dari P1C sebesar `(-0.2,-0.4)` dalam unit template. B mengikuti tepi A–C dan berhenti di X875; garis tetap sampai X936.4. Pertahankan selisih ini. Keanggotaan polygon dan crossing garis dihitung terpisah: tanda signed distance tidak menggantikan pengujian polygon, dan passage setelah cap B tidak membuktikan kedatangan di B.

**OPEN:** template harus direview/diubah per video; keandalan di video/aspect ratio/viewpoint lain belum terbukti. Page setup geometri tetap Phase 11.

## 2. Observasi trajectory dan anchor

**REQUIREMENT — sumber BC:** untuk replay cache Phase 4, gunakan `raw_bbox=(x1,y1,x2,y2)` milik observasi yang sudah diasosiasikan ke persistent track dan benar-benar `emitted`, dengan `measurement_provenance="retained_phase_2_detection"`. Anchor adalah `((x1+x2)/2, y2)`. Kotak raw ini menjadi sumber pengukuran **setelah asosiasi track**; raw detections tanpa asosiasi tidak masuk state machine. Kotak Kalman `bbox`, `center`, dan posisi prediksi tidak menggantikan BC.

**REQUIREMENT — integritas:** setiap pengukuran mempertahankan video, variant/run, `track_id`, indeks frame, dimensi, `original_detection_index`, raw bbox, kelas mentah dan confidence bila tersedia. Rekaman frame harus berurutan; ID dan frame observasi harus cocok dengan barisnya, kotak harus finite/valid, dan native coordinate space harus cocok. Data invalid tidak boleh diubah menjadi trajectory yang seolah valid. Variant dan `parent_run_id` harus konsisten dalam satu cache; confidence finite; satu source-detection index hanya dipakai satu emitted ID per frame. Deteksi berbeda dengan bbox sama tetap boleh masuk diagnostik—ini validasi sumber, bukan deduplikasi kendaraan. `parent_run_id` record adalah run deteksi Phase2; wrapper merekam run ReID Phase4 secara terpisah.

**FACT — batas identitas:** ID adalah identitas software dalam satu video, bukan bukti satu kendaraan fisik. Semua kelas mentah boleh menghasilkan diagnostik geometri; tidak ada whitelist kategori produk atau pemetaan `person` menjadi pedestrian. Label/komponen yang berubah dan ID duplikat tetap terlihat dalam bukti.

## 3. Parameter eksperimen wajib

**REQUIREMENT — tidak ada default numerik produk:** setiap run wajib menyatakan dua parameter berikut.

| Parameter | Makna kontrak |
|---|---|
| `neutral_band_px` | Half-width nonnegatif dalam native pixel terhadap garis. Pengukuran dengan jarak absolut ≤ half-width bersifat netral untuk penetapan origin/konfirmasi destination. |
| `confirmation_observations` | Integer positif: jumlah observasi destination yang memenuhi syarat pada frame berturut-turut sebelum transisi dikonfirmasi. |

**PROPOSAL — ruang eksperimen:** nilai tertentu boleh dipakai sebagai fixture sintetis atau kontrol replay jika dicatat eksplisit sebagai konfigurasi eksperimen. Nilai nol untuk half-width berarti tidak ada band tambahan; kontak tepat pada garis tetap tidak membuktikan passage. Tidak ada nilai yang dinyatakan cocok untuk produksi melalui kontrak ini.

**REQUIREMENT — beda toleransi:** epsilon aritmetika hanya menangani roundoff floating point dalam predikat geometri. Nilai dan penggunaannya harus terlihat dalam helper; epsilon bukan threshold jitter, buffer fisik polygon, atau izin menjembatani gap.

**OPEN:** half-width dan jumlah konfirmasi yang cocok, pengaruh ukuran bbox/perspektif, serta robustness terhadap shake dan class/component handoff memerlukan bukti replay. Tidak ada threshold model/tracker/ReID yang dituning di Phase 5.

## 4. Semantik transisi

**REQUIREMENT — urutan bukti:** pengukuran di interior unik A/B dan di luar neutral band dapat menetapkan **origin geometri**. Setelah itu diperlukan passage teramati melalui segmen terbatas, lalu arrival di interior opposite polygon dan di luar neutral band selama jumlah konfirmasi yang dikonfigurasi. Ini belum menetapkan minimum umur track atau eligibility bisnis Phase 6.

| Kasus | Hasil yang diwajibkan |
|---|---|
| Kehadiran awal di A atau B | Dapat menetapkan origin; tidak menghasilkan transisi/counter sendiri. |
| A → finite line → B, atau B → finite line → A | Kandidat dapat dikonfirmasi setelah arrival memenuhi parameter eksplisit. |
| Intersection infinite-line extension, gerak paralel, atau tidak pernah sampai opposite ROI | Tidak menghasilkan transisi lengkap. |
| Titik pada batas polygon / di luar kedua polygon | Tidak menetapkan atau mengonfirmasi side. Batas bukan overlap interior. |
| Sentuhan garis lalu kembali / gerak sepanjang garis | Tidak membuktikan passage. |
| Pengukuran tepat pada garis, diapit pengukuran berlawanan tanda pada frame kontinu | Dapat mendukung passage melalui interior segmen; sentuhan tanpa kedua sisi tetap tidak cukup. |
| Passage tepat pada endpoint P1/P2 | `AMBIGUOUS_ENDPOINT`; tidak dikonfirmasi sebagai transisi. |
| Kandidat yang kembali ke origin / konfirmasi destination terputus | Tidak mempertahankan konfirmasi seolah arrival berkelanjutan; arrival wajib dibangun dari bukti kontinu yang memenuhi syarat. |

**REQUIREMENT — region/sign independen:** tanda masuk/keluar berasal dari passage terukur, bukan tanda titik origin pertama. Karena garis dan tepi A berbeda, beberapa observasi tetap di strip A setelah passage belum berarti kembali ke A. Pembatalan karena kembali ke region asal membutuhkan bukti telah keluar dari region itu lalu masuk kembali; entry-sign return tetap membatalkan passage. Konfirmasi destination wajib berturut-turut dan tidak memakai kandidat yang dibatalkan.

**REQUIREMENT — arah:** `A_TO_B` dan `B_TO_A` mengikuti urutan region, bukan arah X/Y atau tanda cross product saja. Metadata TOR3-PAGI menetapkan `A_TO_B` = mendekati kamera dan `B_TO_A` = menjauhi kamera. Titik yang sedang ada di A/B tidak dengan sendirinya memiliki arah gerak.

**REQUIREMENT — kontak berturut-turut:** bila passage didukung beberapa pengukuran tepat pada garis sebelum tiba di sisi lain, simpan awal/akhir interval kontak beserta pengukuran sebelum/sesudahnya. Titik kontak pertama boleh menjadi representative `crossing_point` untuk audit, bukan klaim lokasi/waktu crossing fisik yang unik. Gerak sepanjang garis tanpa keluar ke tanda berlawanan tetap tidak menghasilkan transisi. Interval kontak yang mencapai/melewati endpoint menjadi ambigu dan membatalkan kontak pending, sehingga kontak interior lama tidak dapat digunakan untuk keluar melalui perpanjangan garis.

**REQUIREMENT — gap/prediksi:** dua pengukuran berturut-turut untuk track harus memiliki selisih indeks frame satu agar jalur di antaranya dapat mendukung crossing/konfirmasi. Gap observasi lebih besar dari satu memutus bukti pending; kemungkinan passage selama gap dilaporkan `AMBIGUOUS_GAP`, bukan diinterpolasi menjadi crossing sah. Origin dapat dibangun kembali dari pengukuran setelah gap. Prediksi tidak mengesahkan passage maupun menambah konfirmasi, dan tidak menjadi penghubung antara dua observasi. Tidak ada stabilisasi atau GMC yang ditambahkan.

**REQUIREMENT — jitter:** band netral dan konfirmasi destination bekerja dengan parameter eksplisit. Fluktuasi near-line yang tidak memenuhi kontrak tidak menjadi transisi lengkap. Hal ini membuktikan semantik software pada kasus yang dites, bukan bahwa semua jitter video akan tersaring.

**REQUIREMENT — setelah transisi:** origin geometri boleh direbase ke destination yang telah dikonfirmasi. Pembaruan same-side tidak menerbitkan kembali transisi yang sama. Passage balik yang benar-benar memenuhi kontrak dapat menghasilkan diagnostik berikutnya, dengan `repeat_business_policy_open=True`; jangan menerapkan kebijakan hitung sekali seumur ID.

## 5. Interface prototype dan audit

**PROPOSAL — interface helper, bukan API produk:** prototype notebook menggunakan `Geometry.from_draft(path, width, height)`, predikat `point_in_polygon`, `signed_distance`, `segment_intersection`, serta `GeometryStateMachine(geometry, *, neutral_band_px, confirmation_observations)` dan `update(frame_index, point, *, observed=True, metadata=None)`. Predikat polygon membedakan `inside`, `boundary`, dan `outside`; intersection segmen membedakan proper passage, endpoint, touch, overlap, dan none. Detail encoding diagnostik mengikuti helper dan dicatat bersama konfigurasi run.

`replay_cached_records(records_path, geometry, *, neutral_band_px, confirmation_observations)` membaca cache track terarsip, mempertahankan frame kosong/gap dan provenance, lalu mengeluarkan diagnostik serta laporan integritas software. Replay tidak memanggil YOLO, tracker, encoder, atau decoder video untuk membentuk ulang pengukuran.

**REQUIREMENT — diagnostik:** transisi lengkap diberi jenis `GEOMETRY_TRANSITION` dan `accepted_count_event=False`. Bukti menyertakan track/frame/point origin, passage dan konfirmasi, arah region, geometry/configuration reference, parameter, serta link pengukuran sumber. Jumlah diagnostik bukan jumlah kendaraan. Alasan ambigu/rejected disimpan sehingga hasil dapat diaudit; raw class tetap bukti, bukan kategori final.

**REQUIREMENT — reproducibility:** rekam path dan SHA-256 cache/geometry/helper, identitas source video dan run Phase 4, dimensi efektif, parameter eksplisit, versi Python, serta scope frame yang benar-benar diproses. Pertahankan timestamp yang ada dengan maknanya: indeks/FPS adalah estimasi; belum ada authoritative source PTS. Jangan mengubah estimasi menjadi waktu crossing terukur.

## 6. Validasi dan keputusan yang tetap terbuka

**REQUIREMENT — gate eksekusi:** jalankan tes trajectory sintetis terlebih dahulu untuk arah diagonal dua arah, kontak/return, kontak diapit passage, paralel/extension, endpoint, initial presence, batas/area luar, incomplete arrival, band jitter, konfirmasi terputus, missing/predicted observations, line/region-edge offset dan reverse diagnostic. Replay temporal hanya mengikuti gate software tersebut; review visual memakai frame/clip yang benar-benar tersedia dan mencatat cakupannya.

**OPEN — Phase 6 dan eksperimen lanjutan:** deduplikasi kendaraan/ID, rider-versus-vehicle association, kategori produk/stabilisasi kelas, eligibility/minimum umur, genuine repeat/re-entry/U-turn, final vehicle-ReID configuration, threshold yang layak, generalisasi video lain, dan kebutuhan GMC/stabilisasi belum diputuskan oleh kontrak ini. Diagnostik Phase 5 tidak otomatis membuka implementasi counting yang bergantung pada keputusan itu.

**FACT — batas evaluasi:** belum ada formal ground truth. Tes deterministik menguji software; replay dan review visual menguji konsistensi terhadap bukti tersimpan. Keduanya tidak mendukung klaim accuracy, precision, recall, F1, MAPE, counting accuracy, atau keuntungan ReID yang belum diukur.
