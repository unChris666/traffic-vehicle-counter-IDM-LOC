# Phase 6 — proposal pembanding Opsi B

**STATUS: PROPOSAL, belum diimplementasikan atau dijalankan.** Dokumen ini merancang resolusi unit fisik/kategori untuk dibandingkan dengan [Opsi A](COUNTING_CONTRACT.md). Tidak ada hasil counting baru, threshold yang dipilih, atau klaim bahwa otomatisasi mengurangi pending secara benar. [Snapshot awal](PHASE_6_REVIEW.md) tetap merupakan hasil historis tersendiri.

## 1. Keputusan pengguna dan masalah yang sebenarnya

**USER DECISION — kasus TOR3-PAGI:** [feedback 13 Oktober 2026](evidence/phase_6/feedback/user_review_20261013_001.json) menyatakan ID1772 dan ID1774 berada pada satu motorcycle; motorcycle bersama rider/penumpang dihitung satu motorcycle. ID1323 ditetapkan sebagai `car` untuk kasus ini. Arah A→B/B→A dan anchor raw-bbox bottom-center (BC) diterima. Keputusan kategori ID1323 bukan pemetaan otomatis seluruh minivan/pickup/bus/angkot.

**FACT — batas Opsi A:** menghubungkan dua ID ke unit fisik yang sama menyelesaikan hubungan identitas, tetapi tidak memperbaiki histori titik pengukuran. ID1774 adalah komponen person pada motorcycle, sehingga crossing BC orang tidak boleh menggantikan crossing BC kendaraan. ID1772 mempunyai awal person kemudian motorcycle; diagnostic lama tetap mempunyai hard block `UNIT_COMPONENT_CHANGE`. Jangan mengubah diagnostic itu menjadi accepted atau mengedit subtotal.

**FACT — inspeksi sumber terbatas:** [source inspection](evidence/phase_6/feedback/ID1772_motorcycle_episode_source_inspection.json) menunjukkan pengukuran emitted-track ID1772 berlabel person pada frame 7712, lalu motorcycle mulai 7713. BC motorcycle frame 7713–7715 berada di luar ROI; frame 7716–7721 berada di B, finite-line passage berada pada 7721→7722 dan titik 7722 berada di A. BC person ID1774 mempunyai passage berbeda, 7717→7718. Pemeriksaan sumber/predikat ini belum merupakan eksekusi resolver atau event counting baru.

## 2. Pemisahan tanggung jawab yang diusulkan

**PROPOSAL:** gunakan lapisan berikut, dengan provenance pada setiap hubungan:

`raw emitted tracks → physical-unit graph → vehicle-measurement episode → kontrak geometri → passage → aggregate`

| Lapisan | Keputusan dan batas |
|---|---|
| Raw track | Pertahankan seluruh raw bbox, label, frame, source-detection link dan track ID tanpa koreksi in-place. |
| Physical unit | `COMPONENT_OF(person, motorcycle)` berbeda dari `SAME_VEHICLE(track, track)`. Satu unit dapat mempunyai beberapa rider/penumpang dan beberapa ID kendaraan. |
| Measurement episode | Gunakan hanya observasi mentah kendaraan yang terkait track, dengan unit-family konsisten dan urutan terukur lengkap. Person bukan sumber BC kendaraan. |
| Geometry | Terapkan G3, raw BC, finite segment, neutral boundary dan aturan endpoint/gap/prediksi yang sudah disepakati. |
| Passage | Satu physical unit + satu passage menghasilkan satu event; sumber tambahan tetap dapat diaudit. Return memerlukan episode baru yang memenuhi kontrak. |

Tidak membuat bbox gabungan, titik tengah pasangan rider/motorcycle, trajectory sintetis dari dua ID, interpolasi gap, atau crossing berdasarkan deteksi frame tunggal. Graph relasi hanya menghubungkan bukti; ia tidak otomatis membuat trajectory valid.

## 3. Vehicle episode untuk kasus perubahan unit

**PROPOSAL — kebijakan baru yang harus diuji:** perubahan unit-family memulai episode pengukuran baru. Episode kendaraan tidak mewarisi origin/crossing dari episode person. Origin eligible harus dibentuk kembali dari pengukuran kendaraan di ROI.

Untuk ID1772, episode motorcycle berpotensi mulai pada 7713, dengan origin eligible baru pada 7716 dan passage 7721→7722. Jika implementasi serta tes mendukungnya, hasilnya adalah **candidate baru**, bukan promosi candidate lama. Frame 7712 dan kaitannya ke rider tetap disimpan sebagai provenance yang dikeluarkan dari geometri episode kendaraan. Person1774 tetap komponen, tanpa count tersendiri.

Reset harus merupakan aturan eksplisit yang diterapkan ke seluruh input sebelum menilai hasil crossing, bukan pemotongan histori karena ingin menerima kasus tertentu. Kontinuitas, raw source links, unit evidence dan batas episode tetap diverifikasi. Bila family berganti lagi, observasi hilang, atau assignment tidak konsisten, episode tidak dapat disambung diam-diam. Detail konfirmasi family/reset masih OPEN; satu kasus di atas belum memilih aturan produksi.

## 4. Resolver otomatis: bukti dan kontradiksi

**PROPOSAL:** resolver deterministik mengeluarkan hubungan yang didukung atau `UNRESOLVED`, beserta bukti positif, bukti negatif dan alternatif assignment. Overlap hanya membuka pemeriksaan; overlap tidak membuktikan identity.

| Bukti | Penggunaan yang diusulkan | Risiko yang wajib diuji |
|---|---|---|
| Temporal | Person dan motorcycle muncul bersama dan bergerak konsisten pada window terukur. | Kebetulan melaju berdampingan tidak menunjukkan rider. |
| Spasial/trajectory | Hubungan posisi relatif person terhadap motorcycle dan perubahan posisi keduanya. | Persilangan dua motor, perspective, bbox jitter dan occlusion. |
| Koeksistensi | Bedakan komponen satu unit, dua bbox duplikat, dan dua kendaraan nyata pada frame yang sama. | Menyatukan dua motor yang berdekatan atau pedestrian di dekat motor. |
| Assignment unik | Bandingkan semua motorcycle/person yang relevan; tahan jika ada beberapa pasangan yang masuk akal. | Urutan processing tidak boleh menentukan pasangan pemenang. |
| Bukti negatif | Gerak yang berpisah, kendaraan berbeda terlihat serentak, perpindahan rider ke kendaraan lain, episode temporal bertentangan. | Hubungan transitif tidak boleh menyatukan unit lewat pasangan yang bertentangan. |
| Penampilan | Opsional hanya bila feature aktual tersedia dan provenance/encoder dapat diverifikasi. | Retained cache sekarang tidak mempunyai embeddings per observation. |

**OPEN:** algoritme assignment, window/durasi minimum, toleransi posisi/gerak, margin terhadap alternatif, contradiction rules dan threshold grouping. Jangan mengisi angka default berdasarkan asumsi atau hanya dari dua kasus target. Hubungan yang tidak cukup kuat tetap pending. ReID-on track provenance tetap digunakan; penggunaan embeddings baru memerlukan eksperimen feature extraction tersendiri, bukan berpura-pura feature lama tersimpan atau menghapus ReID dari arsitektur.

**PROPOSAL — kategori temporal:** kategori physical unit ditentukan dari bukti **vehicle measurements** pada episode terkait. Label person rider tidak menjadi suara melawan motorcycle. Confidence detector disimpan sebagai bukti, bukan peluang kategori yang terkalibrasi. Person→vehicle memicu episode boundary; konflik antar-kategori kendaraan belum otomatis terselesaikan oleh majority vote. ID1323=`car` adalah case-specific review reference, bukan alasan memilih semua raw `car` sebagai kategori bisnis final.

## 5. Pembanding A versus B

**PROPOSAL — kontrol:** snapshot A awal dengan 18 accepted tetap immutable; A dengan feedback manusia disimpan sebagai snapshot terpisah. B memakai input video/cache, G3 dan kontrol numerik `b0_c1` yang sama. Nilai 0px/C1 tetap kontrol eksperimen, bukan pilihan produksi. Episode reset baru harus diberi versi policy; laporkan pengaruhnya terpisah dari pengaruh grouping/category resolver agar penyebab perubahan jelas.

**REQUIREMENT — pembanding yang jujur:** keputusan pengguna tentang pasangan ID1772/1774 dan kategori ID1323 menjadi review references untuk evaluasi kasus, bukan aturan ID yang di-hardcode ke B atau bukti feature otomatis. Pisahkan `B_machine` dari `B_reviewed` bila feedback manusia dipakai sebagai input resolusi. Bila kedua opsi memakai override ID1323=`car`, perubahan itu bukan keberhasilan klasifikasi otomatis. Dokumen ini tidak mengubah total saat ini atau menyatakan B sudah dieksekusi.

Urutan eksperimen: tes sintetis → targeted source replay → pemeriksaan foto/temporal → perbandingan keputusan. Tidak perlu menjalankan ulang YOLO, BoT-SORT atau ReID. Episode baru membutuhkan evaluasi geometri pada episode sumber terpilih; diagnostic historis tetap immutable.

Kasus audit mencakup ID1,964/973,1772/1774,1323 dan893/912. Kontrol negatif sintetis dan contoh video yang benar-benar ditemukan mencakup dua motor berdekatan, pedestrian di samping motor, passenger, bbox duplikat, class flip, gap/endpoint, fragment ID dan genuine return/U-turn. Jangan mengklaim contoh video yang belum direview sudah tersedia. Pisahkan kasus kalibrasi threshold dari kasus held-out; kebijakan/parameter dikunci sebelum evaluasi held-out. Agreement pada kasus yang dipakai menyusun aturan belum membuktikan generalisasi atau accuracy.

Bandingkan status/reason per candidate dan physical passage, jumlah auto-resolved/pending, provenance serta hasil audit false merge, duplicate/missed passage dan konflik kategori pada window yang benar-benar dilihat. Lebih sedikit pending atau lebih banyak accepted saja tidak membuktikan perbaikan. Tidak ada accuracy/precision/recall/F1/MAPE tanpa protokol dan reference ground truth yang sesuai.

## 6. Gate dan berkas untuk tugas implementasi berikutnya

**REQUIREMENT:** sebelum B mengeluarkan event accepted, seluruh gate geometri/unit/kategori/identity terpenuhi; unresolved conflict tetap di luar subtotal. Mesin A, feedback, resolusi B, candidate baru dan aggregate masing-masing disimpan terpisah. Synthetic tests wajib membuktikan rider tidak dihitung dua kali, negative pairs tidak digabung, hard geometry tidak dipromosikan, episode reset traceable, genuine return terpisah, dan rerun idempotent.

**PROPOSED files — belum dibuat dalam proposal ini:**

- `notebooks/06b_identity_resolution_comparison.ipynb` — kontrol A/B, targeted replay, audit dan output.
- `notebooks/phase_6_identity_resolution_helpers.py` — relasi unit, episode extraction dan resolver terinspeksi.
- `notebooks/phase_6_identity_resolution_tests.py` — fixtures positif/negatif dan regression gates.
- `docs/evidence/phase_6/config/TOR3-PAGI_option_b_v0.json` — policy/parameter eksperimen eksplisit setelah ditentukan.
- `docs/evidence/phase_6/<run_id>/option_b/` — keputusan, source/feature references, event, aggregate dan comparison report aktual.

Perubahan kontrak/API/config yang dibutuhkan dicatat setelah policy baru ditetapkan. UI, enhancement malam, detector/tracker tuning dan refactor produksi tetap di luar scope. Rekomendasi terdekat adalah menyepakati serta menguji **vehicle episode + component relation** terlebih dahulu, kemudian menjalankan resolver B bertahap dengan konfigurasi eksperimen yang transparan.
