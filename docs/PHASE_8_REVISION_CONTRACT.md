# Revisi Phase 8 — identitas fisik, passage, dan pedestrian

**REQUIREMENT — keputusan pengguna, 19 Oktober 2026:** perbaiki kode Phase 8, lakukan uji ulang, dan kelompokkan pending untuk keputusan bersama. Dokumen ini menetapkan kontrak revisi. Hasil eksekusi aktual harus dibaca pada artefak run revisi; status penulisan kode atau lulus tes sintetis tidak membuktikan delapan video selesai.

**FACT — baseline tersimpan:** [B v2](../results/b_v2/README.md) telah mereplay 72.590 frame dan menerbitkan delapan anotasi. Total operasional 3.717 mencakup 2.667 timeout estimasi. Sebanyak 244 baris pending mewakili 242 kunci unit/passage, bukan 242 kendaraan fisik yang sudah diverifikasi. Baseline, source snapshot, manifest, video, dan hasil review sebelumnya tetap tersimpan tanpa ditimpa. Revisi memakai namespace hasil terpisah.

## 1. Identitas dan unit hitung

**REQUIREMENT:** satu passage kendaraan fisik menghasilkan paling banyak satu event aktif. Identitas berikut berbeda:

| Identitas | Fungsi |
|---|---|
| Raw tracker ID | Menunjuk jejak model asli; dapat berpindah objek atau terfragmentasi. |
| Identitas fisik internal | Menghubungkan observasi kendaraan yang sama pada episode yang didukung bukti. |
| Passage ID internal | Menunjuk satu kejadian melintas; berbeda untuk genuine return yang sah. |
| ID tampilan passage | Label kategori/arah yang diminta pengguna; bukan bukti asosiasi identitas. |

Menghubungkan beberapa raw ID tidak menambah hitungan. Jika keduanya sudah menghasilkan kandidat/event untuk passage yang sama, rekonsiliasi menjadi satu event aktif dan simpan jejak pembatalan/penggantian. Event reviewed tidak dijumlahkan lagi dengan event machine atau baseline. Penyambungan identitas tidak mengubah interval observasi hilang menjadi crossing terukur.

## 2. Review pengguna yang wajib diterapkan secara terbatas

| Kasus TGDI | Keputusan pengguna | Batas penerapan |
|---|---|---|
| WEEKDAY-PAGI, 73 pada frame 219 dan 93 pada frame 221 | Kendaraan fisik sama. | Sambungkan episode yang direview dan rekonsiliasi kandidat passage. Keputusan sama kendaraan tidak sendirinya menyelesaikan pertentangan kategori/arah pada hasil lama. |
| WEEKDAY-SIANG, 4149 truck pada 7422/7449; motorcycle pada 7611 | Dua kendaraan berbeda yang memegang raw ID sama. | Pisahkan episode/state kategori, origin, timer, dan passage; motorcycle tidak mewarisi riwayat truck. Frame perpindahan persis antara sampel tersebut belum dinyatakan diketahui. |
| WEEKDAY-PAGI, rider 2471 dan motorcycle 2473, episode sekitar 4204–4254 | Rider adalah komponen motorcycle, tambahan hitungan 0. | Relasi `COMPONENT_OF`, bukan menyamakan orang dengan kendaraan. Jangan mengubah seluruh riwayat raw 2471 menjadi rider. |
| WEEKDAY-PAGI, 2507 | Menggantikan motorcycle 2473. | Kelanjutan kendaraan/passage yang sama memberi tambahan 0; relasi tidak menyatakan semua penggunaan raw ID tersebut sepanjang video adalah kendaraan yang sama. |

**FACT — batas bukti:** donor lama mempunyai penggunaan 2471 sebagai kendaraan pada relasi lain sekitar frame 4386–4388. Karena itu, aturan role/identitas global berdasarkan nomor raw ID tidak sah.

**FACT — pemeriksaan pengukuran tersimpan pada manifest revisi:** raw 93 juga mempunyai bagian truck sebelum frame 221; hanya bagian 221–224 dikaitkan dengan kendaraan 73. Pada frame 221, raw 73 berlabel truck dan raw 93 berlabel car mempunyai bbox hampir sama. Maka keputusan review tidak boleh menggabungkan truck terdahulu dengan car yang direview atau membatalkan seluruh hitungan raw 93. Asosiasi terbatas menangani dua jejak pada objek sama; pemisahan episode mempertahankan objek lain yang kebetulan memakai raw ID sama. Ini mengoreksi penyederhanaan diskusi sebelumnya yang memperlakukan seluruh riwayat 93 sebagai satu kendaraan.

Manifest awal merepresentasikan 73 pada 139–372 dan bagian car 93 pada 221–224; motorcycle 2473 pada 4199–4342 dan pengukuran raw-vehicle 2507 pada 4277–4278; rider-person 2471 hanya 4204–4254. Raw-person 2507 di interval lain tidak digunakan sebagai BC motorcycle. Untuk 4149, interval vehicle truck 7175–7449 dan vehicle motorcycle 7611–7631 dipisahkan, sedangkan interval person di antaranya tetap unresolved. Angka cakupan ini merupakan batas operasional yang diturunkan dari source measurements dan review anchor, bukan klaim bahwa seluruh frame sudah direview manusia. Manifest efektif pada run, beserta SHA-nya, menjadi acuan jika cakupan kemudian direvisi sebelum eksekusi.

Setiap aturan review harus mempertahankan video/source hash, raw ID, frame pengukuran sumber, cakupan inklusif yang efektif, jenis relasi, keputusan pengguna, dan alasan. Jika cakupan implementasi lebih lebar daripada sampel review, bedakan asumsi perluasan tersebut dari observasi langsung. Hasil yang memakai aturan ini harus berlabel **review-assisted**, bukan peningkatan identitas otomatis yang sudah terbukti. Tidak ada appearance embedding atau kemampuan ReID baru yang boleh diklaim dari review ini.

**ENGINEERING CHOICE — relasi algoritmik tersimpan:** grouping duplicate lama dapat dipakai hanya dengan bukti `SUPPORTED SAME_VEHICLE` pada frame sumber yang sedang diproses: semua anggota vehicle harus koeksis, berada pada grouping operasional sama, dan setiap pasangan internal memiliki dukungan positif tanpa pasangan unresolved. Relasi di frame lain atau graph chain tidak memverifikasi frame ini. Simpan relation ID, frame, raw ID dan records SHA pada source reference. Flag `association_verified` dalam jalur ini menyatakan validasi dukungan algoritmik tersimpan, bukan keputusan reviewer manusia atau ground truth identitas fisik. Seluruh riwayat clique di luar frame dukungan tetap asumsi grouping operasional.

## 3. ID tampilan passage

**REQUIREMENT — dikonfirmasi pengguna:** satu huruf dan empat digit; `P` pedestrian, `M` motorcycle, `C` car, `T` truck. Digit pertama setelah huruf tidak nol. A→B memakai digit pertama 2/4/6/8; B→A memakai 1/3/5/7/9. Contoh `M2000` dan `C1759` hanya ilustrasi sampai nomor benar-benar dialokasikan.

ID tampilan berlaku per passage. Kendaraan yang kembali mempunyai passage/label baru sesuai arah, sementara identitas fisiknya dapat tetap sama. Raw ID dan internal ID tetap tersedia untuk audit. Koreksi kategori/arah harus dapat dilacak; label bukan tempat menyimpan state geometri. Alokasi harus deterministik dan bebas benturan pada namespace yang dinyatakan; kapasitas nomor terbatas dan tidak boleh diatasi dengan pemakaian ulang diam-diam. Huruf kategori bus/angkot serta ruang lingkup keunikan lintas video belum disepakati sebagai kontrak produk.

## 4. Pedestrian, rider, dan sumber BC

**REQUIREMENT — keputusan terbaru mengubah scope B v2 sebelumnya:** pedestrian dihitung dalam subtotal tersendiri; rider/passenger adalah komponen motorcycle dan memberi tambahan 0. Subtotal kendaraan dan pedestrian tidak disamarkan sebagai kategori yang sama.

**FACT:** raw kelas model `person` mencakup orang dengan peran berbeda. Person yang belum terasosiasi dengan motor bukan otomatis pedestrian. Asosiasi komponen yang tidak cukup tetap unresolved; jangan membuat rider menjadi pedestrian hanya agar pending turun. Kebutuhan aturan peran pedestrian otomatis di luar review positif tetap OPEN.

**ENGINEERING CHOICE — revisi B v3:** role pedestrian positif dapat berasal dari `USER_REVIEW` atau `AI_ASSISTED_PIXELS_REVIEW` yang menyimpan frame/pixel sumber. Catatan role AI-assisted dibedakan dari keputusan pengguna dan dari keluaran model otomatis. Person yang perannya belum diketahui masuk diagnostik/queue tersendiri; jumlahnya tidak disembunyikan dalam subtotal kendaraan atau disebut pedestrian valid. Dukungan software terhadap pedestrian dapat menghasilkan 0 accepted jika belum ada passage dengan role positif dan bukti geometri cukup; nol tersebut bukan bukti pedestrian tidak ada.

BC event kendaraan berasal dari bbox kendaraan mentah yang terukur dan terhubung ke deteksi sumber. Bbox union motorcycle+rider hanya tampilan. Untuk pedestrian yang benar-benar ditetapkan perannya, BC berasal dari bbox person mentah miliknya, bukan dari motor, union box, atau prediksi. Anchor yang dipakai harus eksplisit pada event.

## 5. Kebijakan yang tetap

Geometri native 640×480, finite line, half-margin 25 px/full 50 px, kategori pita sebagai prioritas, serta timer 60 frame sejak terakhir teramati di polygon asal tetap mengikuti [kontrak B v2](B_V2_COUNTING_CONTRACT.md). Tidak ada tuning detector, tracker, ReID, enhancement, atau threshold baru terselubung.

**OPEN untuk kategori pedestrian yang baru diaktifkan:** apakah occlusion/timeout estimasi juga boleh menghasilkan hitungan pedestrian, atau hanya crossing yang terukur. Kode dapat mendukung pilihan eksplisit; policy efektif pada run harus menyatakan pilihannya. Tanpa persetujuan perluasan jalur inferensi, pilihan konservatif adalah crossing pedestrian terukur saja, sementara kandidat inferensi tetap pending. Ini perlu dibedakan dari keputusan lama tentang timeout kendaraan.

- `LINE_MARGIN`: bedakan crossing terukur dari perpindahan yang diinferensikan selama gap.
- `OCCLUSION_DIFF_POLYGON`: asosiasi identitas terverifikasi boleh menyambungkan raw ID; tetap membutuhkan bukti perpindahan dan role/kategori yang sesuai. Gap bukan bukti momen crossing terlihat.
- `ESTIMATED_TIMEOUT`: tetap estimasi operasional otomatis sesuai keputusan pengguna. Penyambungan ID atau perubahan format label tidak membuktikan crossing terjadi.
- Origin yang masih diam dan teramati memperbarui clock; pre-band U-turn membatalkan eligibility sesuai kontrak. Jitter bbox/kamera dapat menyerupai gerak; belum ada threshold gerak fisik yang tervalidasi.
- Genuine return yang sah boleh menjadi passage baru. Pergantian ID, perubahan label, atau muncul kembali dalam passage sama memberi tambahan 0.

## 6. Pending dikelompokkan menjadi keputusan kebijakan

Kelompok berikut digunakan untuk diskusi, bukan instruksi menerima semua anggotanya. Jumlah aktual revisi harus dihitung dari kunci pending unik pada run yang benar-benar selesai; beberapa alasan dapat mengenai kunci sama.

| Keluarga | Pertanyaan review | Rekomendasi | Masih OPEN |
|---|---|---|---|
| Identitas: duplicate atau handoff | Satu kendaraan dengan beberapa jejak, atau kendaraan berbeda? | Hubungkan hanya bukti positif dalam episode; rekonsiliasi satu passage. | Asosiasi otomatis yang tahan occlusion dan salah gabung. |
| Peran unit: pedestrian/rider/vehicle | Orang berjalan atau komponen motor? | Rider +0; pedestrian positif subtotal sendiri; unknown tetap unresolved. | Kriteria role otomatis dan kasus orang turun/naik kendaraan. |
| Pergantian objek/kategori | Salah label pada objek sama atau raw ID berpindah objek? | Pisahkan episode fisik sebelum pemilihan kategori; prioritaskan bukti pita. | Batas episode jika handoff berlangsung di interval tak teramati. |
| Geometri/crossing/gap | Ada bukti crossing atau hanya perpindahan/timeout? | Simpan measured/inferred; kategori manual tidak memperbaiki geometri invalid. | Kendaraan yang pertama terlihat setelah crossing; cakupan ROI temporal. |
| Taxonomy/label tampilan | Apa kategori bisnis dan huruf tampilannya? | Kategori yang sudah diputuskan saja memperoleh label final. | Bus/angkot dan taxonomy lain; overflow/keunikan lintas video. |

Accepted timeout, kendaraan diam, salah gabung, missed passage, dan objek tanpa kandidat juga wajib direview. Mereka tidak selalu muncul di daftar pending.

## 7. Validasi dan gate

Kode revisi terpisah berada di `notebooks/phase_8_b_v3_counting.py`, `notebooks/phase_8_b_v3_batch.py`, `notebooks/phase_8_b_v3_annotation.py`, dan `notebooks/08c_reviewed_identity_replay.ipynb`. Keputusan review efektif disimpan pada `results/b_v3/input/review_decisions.json`. Keberadaan path ini adalah rancangan penempatan, bukan bukti eksekusi.

Uji sintetis wajib membedakan same-unit/same-passage, objek berbeda dengan raw ID sama, rider +0, pedestrian sendiri, raw ID berganti dalam gap, genuine return, rekonsiliasi event, namespace label/paritas, serta pending berulang pada kunci yang sama. Replay memakai cache pengukuran terverifikasi dan menyimpan input/config/source hashes serta perbandingan event baseline→revisi. Tidak diperlukan inference YOLO/BoT-SORT/ReID baru untuk perubahan kebijakan ini.

**Status awal dokumen:** eksekusi revisi belum dinyatakan selesai di sini. Root laporan run harus mencatat video/frame yang benar-benar direplay, tes lulus/gagal, hasil per passage, jumlah measured/inferred/timeout, pending per keluarga, regresi, serta apa yang belum dirender/direview. Penurunan pending pada kasus yang menerima review manual bukan bukti otomatisasi umum.

Phase 9 dapat dimulai untuk mengaudit snapshot reproducible yang sudah tersedia; tidak perlu menunggu pending nol. Izin audit bukan persetujuan produksi. [PHASE_9_TASK.md](PHASE_9_TASK.md) menetapkan tujuannya.
