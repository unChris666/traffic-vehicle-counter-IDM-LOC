# Daftar review pending B v2

[Buka tabel CSV di GitHub](pending_review.csv) · [Unduh CSV](https://raw.githubusercontent.com/unChris666/traffic-vehicle-counter-IDM-LOC/main/results/b_v2_pending_review/pending_review.csv) · [Semua video anotasi](https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC/releases/tag/phase8-b-v2-tgdi-review-v1)

Indeks ini dibuat langsung dari hasil Kaggle yang telah tersimpan, tanpa model/counting/render ulang dan tanpa mengubah keputusan. Ada **244 baris pending asli, untuk 242 kunci unit/passage berbeda**. CSV menggabungkan dua pengulangan diagnostik pada kunci yang sama sebagai satu baris review, sambil mencatat retained_decision_rows. Kunci tersebut belum membuktikan jumlah kendaraan fisik unik.

## Cara review

1. Buka atau unduh CSV, lalu pilih video dan ID. Klik video_url untuk video anotasi yang sesuai.
2. Cari FRAME atau waktu pada review_time_hhmmss. Putar beberapa detik sebelum/sesudahnya. Untuk timeout, lihat juga source_measurement_frames dan source_time_hhmmss karena keputusan terbit setelah observasi hilang.
3. Cocokkan kendaraan fisik, semua ID terkait, rider/pedestrian, kategori, arah, BC, pita dan asal crossing. Baca reason_explanation; gunakan evidence_url jika membutuhkan keputusan mentah.
4. Isi review_result dan review_notes pada salinan CSV, misalnya confirmed_vehicle_passage, duplicate, pedestrian_excluded, no_crossing, atau still_uncertain. Sertakan ID terkait dan frame bukti. Contoh nilai ini adalah catatan review, belum schema impor otomatis atau perintah mengubah accepted.
5. Kirim salinan CSV yang diisi. Review manual tetap terpisah dari hasil machine dan tidak otomatis memperbaiki crossing yang tidak valid.

Waktu dihitung dari indeks frame nol dibagi FPS video yang tersimpan, dibulatkan ke milidetik; bukan timestamp PTS sumber. CSV menampilkan kategori raw pada pengukuran bukti, bukan kategori final hasil review. Panel video hanya menampilkan dua pending terbaru yang telah muncul pada frame itu; CSV ini memuat seluruh daftar final.

## Penyebab aktual

| Alasan | Baris pending asli yang memuat alasan | Kunci unit/passage yang memuat alasan |
|---|---:|---:|
| Belum pasti satu kendaraan dengan beberapa ID atau kendaraan berbeda. (`UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE`) | 168 | 166 |
| Kategori pengukuran asal dan tujuan/terakhir berbeda tanpa kategori pita yang menyelesaikannya. (`CATEGORY_ENDPOINT_CONFLICT`) | 30 | 30 |
| Bukti jalur garis terbatas atau perpindahan polygon setelah gap belum memenuhi aturan. (`NO_VALID_FINITE_LINE_OR_OCCLUSION_EVIDENCE`) | 19 | 19 |
| Pergantian raw ID belum terselesaikan saat timeout. (`TIMEOUT_RAW_TRACK_HANDOFF_UNRESOLVED`) | 13 | 13 |
| Raw ID berubah selama passage; jalur ini memerlukan konsistensi ID. (`RAW_TRACK_CHANGED_DURING_PASSAGE`) | 9 | 9 |
| Kategori belum masuk pemetaan otomatis yang disepakati; bukan otomatis pedestrian. (`UNSUPPORTED_CATEGORY_TAXONOMY_OPEN`) | 6 | 6 |
| Jumlah vote kategori di dalam pita seri. (`CATEGORY_TIE_IN_BAND`) | 1 | 1 |

Satu kasus dapat memiliki lebih dari satu alasan. Angka pada kolom alasan tidak boleh dijumlahkan sebagai total kasus terpisah. Konflik identitas mendominasi: 166 dari 242 kunci (sekitar 69%). Ini prioritas review, bukan persentase perbaikan atau bukti error fisik.

| Video | Baris asli | Baris review CSV |
|---|---:|---:|
| weekday_pagi | 17 | 17 |
| weekday_siang | 102 | 102 |
| weekday_sore | 40 | 40 |
| weekday_malam | 6 | 6 |
| weekend_pagi | 15 | 15 |
| weekend_siang | 11 | 11 |
| weekend_sore | 49 | 47 |
| weekend_malam | 4 | 4 |

## Contoh awal untuk dibuka

| Video | ID pada keputusan | Frame | Waktu perkiraan | Alasan |
|---|---|---:|---|---|
| weekday_pagi | 73 | 219 | 00:00:07.323 | UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE |
| weekday_pagi | 87 | 240 | 00:00:08.026 | UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE |
| weekday_pagi | 551 | 854 | 00:00:28.558 | UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE |
| weekday_pagi | 976 | 1474 | 00:00:49.291 | UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE |
| weekday_pagi | 977 | 1480 | 00:00:49.492 | UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE |

## Pedestrian dan rider

**REQUIREMENT pengguna:** pedestrian tidak dihitung; rider/passenger adalah komponen motorcycle dan tidak menambah hitungan terpisah.

**FACT kode/hasil B v2:** raw person dikeluarkan dari counting. Rider digabung dalam tampilan hanya pada relasi COMPONENT_OF yang didukung di frame tersebut dan memiliki parent motorcycle tunggal. Person tanpa relasi tetap person yang perannya belum dipastikan; label tampilan lama component unknown +0 tidak membuktikan rider ataupun pedestrian.

**Batas:** filter memakai keluaran kelas model. Pedestrian yang salah terdeteksi sebagai kelas kendaraan masih bisa lolos filter; hasil accepted tanpa kategori person tidak membuktikan semua peran fisik sudah benar. Penyempurnaan label tampilan yang diusulkan adalah person | role unknown | excluded, tanpa mengubah orang yang belum jelas menjadi rider.

## Langkah berikut yang direkomendasikan

Mulai audit Phase 9 dengan kasus konflik identitas dan kasus negatif pedestrian/parkir. Periksa juga accepted timeout, termasuk [kasus ID 2/34 pada weekday_pagi](../b_v2/review/timeout_edge_car/review.md). Ini penting karena 2.667 dari 3.717 hitungan operasional berasal dari estimasi timeout. Jangan hanya mereview pending; accepted yang salah dan kendaraan yang tidak pernah menjadi kandidat juga harus dicatat.

Perbaikan kode berikutnya sebaiknya terikat kasus yang sudah direview: peran person/rider pada overlay, dua duplikasi baris pending, dan pemulihan identitas yang dapat dibuktikan. Bandingkan revisi pada passage fisik yang sama, simpan hasil B v2 ini sebagai baseline, dan jangan otomatis mengubah seluruh pending menjadi accepted. Refactor/UI/Docker menunggu hasil audit counting.

[Provenance dan pemeriksaan ekspor](provenance.json) mengikat CSV pada hash 16 artefak sumber yang dipakai. Ini indeks review; bukan audit manual yang sudah selesai, ground truth, atau perubahan hasil kendaraan.
