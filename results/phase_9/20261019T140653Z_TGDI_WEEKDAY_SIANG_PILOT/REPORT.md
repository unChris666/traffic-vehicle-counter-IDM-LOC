# Phase 9 — hasil pilot TGDI-WEEKDAY-SIANG

**Status: COMPLETE_SCOPE untuk pilot kasus terarah; audit menyeluruh delapan video belum dilakukan.** Pengguna memilih “Selesaikan pilot dan daftar perbaikan dahulu”. Hasil ini adalah audit bukti dan usulan overlay reviewed. Pipeline, konfigurasi, event, pending dan MP4 B v3 tetap utuh; revisi mesin berikutnya **NOT_RUN**.

Audit ID: `20261019T140653Z_TGDI_WEEKDAY_SIANG_PILOT`. Mulai ekstraksi bukti 19 Oktober 2026 pukul **21.06.53 WIB**. Waktu tersebut bukan waktu selesai audit.

## Input dan integritas yang diperiksa

- **303/303 pemeriksaan integritas tersimpan lulus**, termasuk delapan video asli, 53 artefak lokal, 112 artefak metadata/output Kaggle, sembilan snapshot executable, geometri, policy, review dan kesamaan byte hasil lokal/Kaggle. Ini pemeriksaan hash/record, bukan tes kualitas counting. [Rincian verifikasi](evidence/input-verification.json.gz).
- Video pilot asli cocok SHA sumber: `5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1`; 640×480, 9.128 frame, FPS tercatat29,781214. Sumber delapan video tersedia lokal dan cocok dengan identitas dataset Kaggle.
- Cache pilot memuat **75.850 deteksi tersimpan** dan **70.231 observasi track yang diterbitkan**. Keduanya jumlah observasi per frame, bukan jumlah kendaraan. Skor sebelum filter detector0,25 dan appearance vectors tidak tersedia pada donor lokal.
- MP4 anotasi **yang benar-benar diterbitkan** diunduh dari GitHub Releases: SHA `d8b7d58f39001eb29a080c4a6cd8c76c7653c3226232881bd6ec57acac79252a`, 122.934.659 byte, 1160×960. Seluruh9.128 frame didekode ulang; tidak dirender atau dienkode ulang. [Receipt](evidence/published-annotation-verification.json.gz).
- Baseline counting tetap run lokal `20261019T045405_106031Z`; anotasi Kaggle version2/run `20261019T070846_020453Z`. Nilai pilot-video baseline tetap **584 event operasional:121 terukur+463 inferensi; pending 430**. Ini bukan jumlah fisik yang selesai diaudit.

## Cakupan dan metode review

**70 frame sumber native unik** diperiksa visual dan setiap piksel BGR cocok dengan hash input detector tersimpan. Frame diperoleh melalui decode berurutan dari frame 0. **Tujuh frame anotasi rilis** diperiksa:127,226,273,296,1203,5003 dan9127. Manifest mencatat seluruh gambar/record beserta hash dan asalnya.

Review berfokus pada **tujuh objek target**, bukan seluruh lalu lintas: pedagang gerobak54; motor parkir yang sempat memakai166; motor 185; rider 166; skuter putih856 beserta dugaan riwayat sebelumnya; rider 857; pedestrian 3025. Kondisi sumber adalah siang dengan overlay peta/teks, kendaraan saling menutup dan objek yang terpotong tepi frame. Tidak ada audit visual malam baru.

Rentang konteks:0–330,900–1240,4950–5100. **Tidak semua frame dalam rentang tersebut dilihat.** [segments.csv](segments.csv) mencatat hanya run indeks yang benar-benar diperiksa; coverage visual sumber adalah70 frame, bukan panjang rentang konteks. Seluruh frame anotasi yang didekode juga tidak dianggap sudah direview visual.

Reviewer sudah mengetahui label pengguna dan sebagian temuan historis/record. Ini development dengan `ALREADY_EXPOSED`, bukan blind audit atau ground truth formal. Contact sheet sumber diperiksa sebelum frame anotasi rilis. Konteks skuter putih diperluas setelah penantang independen menemukan kendaraan tersebut tampak sebelum raw 856.

Label pengguna berasal dari review anotasi **V2**. Audit ini mencocokkannya ke video sumber dengan SHA yang sama, observasi tracker tersimpan, serta ledger/anotasi **B v3**. Versi V2 dan B v3 tetap dibedakan; tidak diasumsikan mempunyai keputusan counting yang sama.

## Temuan dan keputusan per kasus

| Kasus | Bukti yang terkonfirmasi | Keputusan audit / dampak yang diusulkan |
|---|---|---|
| **54 — pedestrian mendorong gerobak** | Sumber mendukung orang berjalan yang sama hingga 140. Raw BC104→105 melintasi interior segmen secara matematis tanpa gap; first exclusiveA127. Pending127 hanya mempunyai alasan `PERSON_ROLE_UNRESOLVED`. | **Usulan reviewed PEDESTRIAN+1** menurut kontrak raw bbox BC. Role diperluas melalui review AI secara terbatas33–140; label pengguna tetap57–107. Jangan melabeli seluruh54 hingga 999. |
| **166/185 — sumber passage tercampur** | Raw166 mula-mula motor parkir188–213, lalu rider pada 185, kemudian bbox motor yang sedang lewat296/299–301. M1006 menggunakan BC kendaraan242→243 dan konfirmasi251. M1007 pertama menambah1 melalui timeout273, lalu diperbarui ke occlusion296 dengan delta0. | **Pertahankan satu M1006; usulkan pembatalan M1007.** Ada satu event tambahan pada passage target, dengan gejala salah gabung sekaligus duplikasi/hitungan palsu. Tiga tag tersebut tidak berarti tiga kesalahan fisik independen. |
| **166 — rider motor 185** | Keduanya terdeteksi. Relasi215–292 ditolak karena maksimum residual0,18585 melewati kontrol0,15, meskipun78 frame bersama dan BC-inside fraction1. | Rider tambahan **+0** pada interval yang didukung. Perbaiki batas episode sebelum menguji asosiasi; jangan menaikkan threshold global hanya agar contoh ini lolos. |
| **856/M1021 — timeout fragmen yang menjauh** | Semua57 observasi BC856 berada diB, tidak pernah band/A. M1021 menambah1 pada 1203=1143+60, arahB→A diasumsikan. Namun skuter putih terlihat sebelumnya; raw 816 pertama1049 berada sekitar22,10 px dari garis, di dalam margin25 px. | **Jumlah passage fisik tetap UNRESOLVED.** Fragmen856 sendiri tidak membenarkan timeout baru menurut aturan terbaru. Akan tetapi, tidak boleh menyimpulkan kendaraan fisiknya tidak pernah crossing. Riwayat763/816/856 dan kemungkinan event sebelumnya harus direkonsiliasi. |
| **857 — rider skuter856** | Review pengguna1089 mendukung rider; resolver hanya mendukung1100–1113. Pending1221 memakai observasi person 1161, di luar scope role positif ini. Tidak ada accepted person 857 tersendiri. | Rider tambahan **+0** dalam scope 1089–1113. Pending1221 belum ditutup oleh keputusan ini. Koreksi role tidak membuktikan crossing M1021. |
| **3025 — pedestrian dekat kamera** | Orang berjalan terlihat. Semua60 BC tersimpan berada di luar polygonA/B dan margin; kaki terpotong frame. Tidak ada event/pending passage3025; hanya role queue dan diagnostic `NO_ORIGIN_ROI_FOR_TIMEOUT`. | **Kontribusi operasional+0 menurut geometri BC saat ini.** Ini bukan kesimpulan orang tersebut tidak pernah melintas secara fisik. Perlu keputusan cakupan pedestrian dekat kamera; role positif saja tidak menghasilkan+1. |
| **Output B v3** | Raw ID tersedia, tetapi label bertumpuk pada frame 226/273. Log273 memperlihatkan M1007 timeout+1 dan296 memperlihatkan revisi+0. Panel akhir cocok dengan angka event/agregat tersimpan. | Prioritaskan raw ID pendek yang terbaca, parent rider dan status passage. Perubahan renderer harus menjadi tugas tersendiri yang tidak mengubah ledger. |

Seluruh keputusan baru adalah **AI-assisted review**, dengan sumber label pengguna ditandai terpisah. Tidak ditulis seolah pengguna telah mengadjudikasi seluruh interval baru. Detail ada pada [cases.jsonl](cases.jsonl), [review_decisions.jsonl](review_decisions.jsonl) dan [inventory fisik](passage_inventory.csv).

Bukti yang bisa langsung dibuka:

- [Pedagang54: sumber104–105 dan sekitarnya](evidence/raw-contact-S1-cross54-01.jpg), [konfirmasi127 dan konteks](evidence/raw-contact-S1-cross54-02.jpg).
- [Motor parkir188/213](evidence/raw-contact-S1-02.jpg), [rider/motor185](evidence/raw-contact-S1-03.jpg), [motor yang sama pada296](evidence/raw-contact-S1-04.jpg).
- [Log rilis M1007+1 pada273](evidence/published-b-v3-frame-000273.png), [revisi+0 pada296](evidence/published-b-v3-frame-000296.png).
- [Riwayat skuter sebelum856](evidence/raw-contact-S2-prehistory-02.jpg), [bagian1082–1100](evidence/raw-contact-S2-01.jpg), [log M1021 pada1203](evidence/published-b-v3-frame-001203.png).
- [Pedestrian3025 dan kaki terpotong](evidence/raw-contact-S3-01.jpg), [bbox pada anotasi5003](evidence/published-b-v3-frame-005003.png).
- [Panel akhir MP4 yang diterbitkan](evidence/published-b-v3-frame-009127.png).

### Batas khusus kasus 54

BC berubah dari `(110,356;400,304)` pada 104 menjadi `(104,515;356,999)` pada 105: bottom bbox bergeser sekitar43,3 px dalam satu frame. Peta bawaan video menutupi bagian kaki. Jadi **crossing raw bbox BC terukur didukung; waktu crossing kaki fisik104→105 tidak terbukti langsung**. Kedatangan BC padaA dan keberlanjutan orang yang sama mendukung usulan satu passage menurut anchor yang disepakati. Risiko ini menjadi kasus regresi overlay/jitter; tidak ada threshold baru ditentukan.

### Mengapa kasus skuter putih belum dipaksa menjadi0

Pemeriksaan awal terhadap raw 856 saja akan mengarah pada kesimpulan tidak eligible. Reviewer penantang menemukan source history lebih awal, sehingga konteks diperluas. Raw763 dan816 belum memiliki event; raw 717 mempunyai M2036 dan raw 689 mempunyai M2033, tetapi **belum terverifikasi sebagai kendaraan fisik yang sama**. Kendaraan777/810 di dekatnya juga mempunyai event sendiri dan tidak boleh ikut digabung berdasarkan kedekatan.

Dengan demikian, aturan “fragmen muncul diB dan menjauh:+0 untuk fragmen baru” harus bekerja bersama penyambungan episode. Menghapus seluruh passage fisik tanpa menelusuri asalnya dapat membuat kendaraan terlewat. Tidak ada alias otomatis763→816→856 atau717 yang diterapkan. [Bukti prehistory](evidence/white-scooter-prehistory.json.gz), [review penantang](evidence/independent-challenge.json.gz).

## Rekonsiliasi reviewed dan baseline

| Kelompok yang dapat diputuskan | Baseline accepted | Usulan reviewed | Delta |
|---|---:|---:|---:|
| Passage pedagang54 |0 pedestrian|1 pedestrian|+1|
| Passage motor 185 beserta event tambahan166 |2 motorcycle|1 motorcycle|−1|

**Total dua kelompok tersebut sama-sama2**, tetapi komposisinya berubah dari2motorcycle menjadi1motorcycle+1pedestrian. Total agregat yang terlihat sama dapat menyembunyikan duplikasi dan pedestrian yang terlewat.

Ini adalah aritmetika overlay reviewed pada kelompok terpisah, **bukan hasil pipeline baru**. Kelompok skuter putih tetap memiliki reviewed count/delta null dan tidak dimasukkan ke total final yang dipaksakan. Tidak ada total reviewed final untuk seluruh video/delapan video. Nilai machine584/pending 430 tidak ditimpa, serta machine dan reviewed tidak dijumlahkan. [Perbandingan per kelompok](comparison.csv).

Tiga keputusan+0 yang dicatat adalah rider 166, rider 857 pada scope terbatas, dan pedestrian 3025 menurut eligibility geometri saat ini; motor parkir juga tidak mempunyai passage dalam sampel yang ditinjau. Ini tidak berarti seluruh pending terkait otomatis selesai. Khusus3025, tidak ada pending passage yang bisa diklaim telah dikurangi.

## Rekonsiliasi panel yang benar-benar dilihat

Frame9127 menunjukkan584=121terukur+463inferensi; vehicle584/pedestrian 0/pending 430. Kategori motorcycle 342+car 169+truck 73=584; arahA→B327+B→A257=584; routeLINE138+POLYGON9+TIMEOUT 437=584. Nilai tersebut cocok dengan field agregat tersimpan. Route LINE tidak otomatis selalu measured karena gap dapat tetap inferred.

M1006 sudah menjadi label bbox pada 226, sebelum aktivasi251. Ini sesuai tampilan **offline final ledger** yang dijelaskan pada panel; keberadaan ID tampilan bukan bukti hitungan sudah ditambahkan pada frame tersebut. Status ini perlu dibuat lebih mudah dibaca. Spot check ini tidak membuktikan seluruh frame/panel sudah benar. [Transkripsi dan agregat pembanding](evidence/panel_spotcheck.json).

## Daftar perbaikan Phase 1–8

[improvement_backlog.csv](improvement_backlog.csv) memuat input, proses uji, output, bukti dan regresi setiap item. Urutan berikut rekomendasi berdasarkan dampak pada kasus pilot, bukan ranking frekuensi seluruh dataset:

1. **P9-F3 + P9-F6:** batas episode fisik, verified handoff, eligibility dan clock timeout. Uji salah gabung166, kendaraan diam berganti ID, fragmen sesudah crossing, konflik yang ditahan dan genuine return yang benar.
2. **P9-F6-ROLE:** asosiasi rider–motor dan scope temporal. Uji166/185,857/856, pedestrian dekat motor, rider berhenti, gerobak dan pergantian peran; identity episode harus benar dahulu.
3. **P9-F8:** label raw ID yang terbaca, parent rider, serta perbedaan final passage ID dan status counted-at-frame. Ini calon tugas render-only dengan ledger tetap identik.
4. **P9-F1 + P9-F5:** visibility kaki, overlay, clipping, dan keputusan cakupan pedestrian/geometri. Jangan mengubah BC atau menghitung berdasarkan keberadaan person secara diam-diam.
5. **P9-F2:** inventory sumber yang lebih lengkap untuk mencari passage tanpa kandidat dan mengatribusikan masalah detector versus downstream. Pilot kasus ini tidak dapat menyatakan total missed passage.
6. **P9-F4 + P9-F7:** kumpulkan bukti identity/ReID dan malam, lalu rancang eksperimen terkontrol setelah aturan counting dibekukan. Vehicle-ReID final dan enhancement produksi belum dipilih.

Semua item merupakan backlog atau rencana eksperimen; **belum implemented/passed**. Belum ada pengukuran manfaat atau biaya revisi. Kasus development ini tidak menjadi hold-out blind untuk mengklaim generalisasi.

## Keputusan terbuka dan langkah berikutnya

- Verifikasi scope handoff skuter putih dan event sebelumnya sebelum menentukan perubahan hitungan/arah fisiknya.
- Tentukan cakupan produk untuk pedestrian dekat kamera yang kaki/BC-nya tidak terlihat dalam ROI saat ini.
- Jalur inferred/timeout pedestrian, taxonomy BUS/angkot, kriteria numerik identity/role/gerak, serta vehicle-ReID final masih OPEN.
- Belum ada bukti filter malam reliable lintas video; pilot siang ini tidak menutup validasi malam.
- Brief pivot pengguna menentukan implementasi berikutnya. Rekomendasi pertama adalah batas episode dan eligibility timeout, disertai uji sintetis serta replay terpisah yang baru boleh dilaporkan setelah dijalankan.

## Validasi paket audit

[Validasi akhir](verification.json) meluluskan 473 pemeriksaan struktur/provenance, termasuk 71 berkas bukti, 70 kecocokan piksel frame native, referensi kasus/keputusan, aritmetika overlay, geometri/policy tersimpan, 53 artefak baseline lokal dan 11 executable/config yang dilindungi. Jumlah pemeriksaan ini bukan jumlah passage yang benar atau tes performa model. [Manifest paket](audit_artifact_manifest.json) mengikat byte artefak hasil audit, dengan manifest itu sendiri dikecualikan dari self-hash.

**Pilot dapat ditutup pada scope yang dipilih:** input, bukti, keputusan/ketidakpastian dan backlog tersimpan. Audit seluruh video, frekuensi kegagalan, seluruh kendaraan tanpa kandidat, validasi malam dan kesiapan produksi belum selesai. Phase 10 tidak otomatis dimulai.
