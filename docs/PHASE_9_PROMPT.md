<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Prompt Phase 9 — audit bukti dan backlog perbaikan Phase 1–8

**Status: prompt tugas, belum merupakan hasil audit.** Salin blok berikut untuk memulai audit. Paket ini tidak menjalankan ulang model/counting atau mengubah hasil Phase 8. Protokol operasional ada di [PHASE_9_AUDIT_PROTOCOL.md](PHASE_9_AUDIT_PROTOCOL.md); gunakan [template audit](templates/PHASE_9_AUDIT_TEMPLATES.md) untuk mencatat input, cakupan, kasus, keputusan, dan backlog. [PHASE_9_TASK.md](PHASE_9_TASK.md) menjelaskan tujuan dan batas fase.

```text
Anda adalah engineer/reviewer untuk repository
unChris666/traffic-vehicle-counter-IDM-LOC.

TUGAS: PHASE 9 — AUDIT BERBASIS BUKTI DAN BACKLOG PERBAIKAN PHASE 1–8.
Respons dan dokumen audit menggunakan Bahasa Indonesia.

TUJUAN
Bangun referensi audit yang dapat ditelusuri untuk menemukan hitungan palsu,
duplikasi, salah penggabungan, kesalahan peran/kategori/arah, dan passage yang
terlewat. Hasilnya adalah daftar perbaikan Phase 1–8 dengan bukti, dampak,
usulan eksperimen, dan kriteria verifikasi. Pending turun bukan satu-satunya
ukuran keberhasilan. Pending dapat diselesaikan sebagai tidak eligible/+0;
kasus yang tidak pasti tetap unresolved.

BACA DAHULU
- AGENTS.md dan CODEX_WORKFLOW.md.
- docs/PROJECT_CONTEXT.md, docs/PRODUCT_SPEC.md, docs/MODEL_SPEC.md.
- docs/COUNTING_LOGIC.md, docs/ARCHITECTURE.md, docs/API_CONTRACT.md.
- docs/TEST_PLAN.md, docs/EVALUATION.md, docs/OPEN_DECISIONS.md,
  docs/CONFIG_SCHEMA.md.
- docs/PHASE_9_TASK.md, docs/PHASE_9_AUDIT_PROTOCOL.md,
  docs/templates/PHASE_9_AUDIT_TEMPLATES.md.
- docs/PHASE_9_ROLE_REVIEW_WORKFLOW.md,
  docs/PHASE_8_REVISION_CONTRACT.md, docs/B_V2_COUNTING_CONTRACT.md,
  docs/PHASE_7_REVIEW.md.
- results/b_v3/README.md, results/b_v3/PENDING_DECISIONS.md,
  results/b_v3/VIDEOS.md, results/b_v3/config/policy.json,
  results/b_v3/input/review_decisions.json.
- Manifest retensi, source/config hashes, ledger dan pending aktual yang
  dirujuk berkas di atas; jangan mengambil temuan hanya dari source notebook.

BEDAKAN TIGA LAPIS
1. Bukti hasil frozen B v3 yang benar-benar dieksekusi.
2. Keputusan pengguna terbaru yang disepakati untuk revisi berikutnya.
3. Usulan/hipotesis perbaikan yang belum diimplementasikan atau diuji.
Dokumen historis dapat memuat status keputusan lama. Jika berbeda dengan
keputusan pengguna terbaru, catat perbedaannya tanpa mengubah snapshot lama.

SNAPSHOT BASELINE UNTUK DIKUNCI DAN DIVERIFIKASI
- Lokal: results/b_v3/execution/final_20261019T045405_106031Z/.
- Kaggle B v3 version 2: run 20261019T070846_020453Z,
  chrisbiran/phase-8-tgdi-b-v3-review.
- Delapan video TGDI, 72.590 frame sumber; ledger lokal/Kaggle tersimpan.
- Angka snapshot: 3.500 event operasional, 895 terukur dan 2.605 inferensi,
  termasuk 2.454 timeout. Pending: 2.890 kunci software unik, bukan jumlah
  kendaraan/orang fisik. Pedestrian accepted 0 bukan bukti pedestrian tidak ada.
- Verifikasi angka melalui artefak tersimpan. Jika tidak tersedia atau tidak
  cocok, laporkan; jangan menyatakan verifikasi berhasil berdasarkan prompt ini.
- Video anotasi GitHub Releases adalah alat pencocokan model. Video sumber
  mentah tetap diperlukan untuk inventaris passage tanpa bias overlay.

INPUT YANG DIHARAPKAN
- Video mentah aktual pada Kaggle:
  /kaggle/input/datasets/chrisbiran/tgdi-traffic-videos
  (jangan menganggap path Kaggle tersedia di Codex).
- Manifest delapan sumber: nama tepat, hash bila tersedia, resolusi, FPS,
  jumlah frame, aturan indeks frame, serta ketersediaan/decode.
- Anotasi B v3 dengan versi dan checksum; gunakan B v2 hanya jika ditandai
  sebagai pembanding historis yang berbeda.
- Ledger event, pending/role queue, deteksi tersimpan, pengukuran track,
  trajectory, relasi komponen/identitas, geometri per video dan config efektif.
- Review manusia terdahulu dengan video/versi/frame/scope yang jelas.
- Kesepakatan cakupan audit: penuh delapan video atau segmen yang ditentukan.
  Jangan membuat target persentase, durasi, atau jumlah sampel sendiri.

Jika input belum lengkap, buat daftar readiness dan lanjutkan bagian yang
tidak bergantung padanya. Pakai readiness VERIFIED, AVAILABLE_UNVERIFIED,
MISSING, INVALID atau NOT_CHECKED; bedakan dari status review NOT_REVIEWED
dan temuan tidak ada passage. Mintalah hanya input/keputusan
yang benar-benar diperlukan untuk bagian berikutnya. Jangan mengarang hasil
visual ketika video hanya ada di Kaggle dan belum dapat dibuka.

ATURAN TERBARU YANG HARUS DIHORMATI
- Satu kendaraan fisik menghasilkan maksimal satu hitungan per passage.
  Pergantian raw tracker ID saja tidak membuat passage baru. ID tampilan
  seperti M1006 adalah ID passage; raw ID tetap menjadi referensi sumber.
- Motorcycle + rider/passenger adalah satu motorcycle; rider +0. Pedestrian
  berbeda dengan rider dan harus mempunyai bukti peran positif. Label person
  saja, ketiadaan relasi motor, helm atau overlap saja tidak cukup.
- Hubungan role/identitas berlaku pada episode/interval yang terbukti, bukan
  otomatis seluruh riwayat raw ID. Satu raw ID dapat berpindah objek.
- BC kendaraan berasal dari pengukuran vehicle sumber yang terhubung ke
  track. Rider BC dan union bbox tampilan tidak menggantikannya.
- Koreksi identitas/kategori tidak mengubah gap atau prediksi menjadi
  crossing terukur. Review positif role tidak otomatis menghasilkan +1.
- Timeout pertama tetap 60 FRAME SUMBER sejak terakhir terlihat di polygon
  asal, setelah kandidat eligible dan tanpa konflik identitas relevan.
  Ini keputusan terbaru untuk revisi berikutnya, bukan klaim kode frozen
  sudah menerapkannya sepenuhnya.
- Handoff ID terverifikasi melanjutkan kandidat passage dan clock yang sama.
  Observasi unit yang sama di polygon asal memperbarui/reset clock. Jika
  identitas belum pasti, tahan estimasi yang berpotensi duplikat; jangan
  menyatukan dua kendaraan hanya karena dekat atau kelas sama.
- Timeout tetap estimasi: kendaraan bisa masih tertutup di polygon asal.
  Measured dan inferred tetap dipisahkan dalam laporan/rekonsiliasi.
- Passage selesai tidak dibuka lagi karena timer atau perubahan ID. Fragmen
  baru di polygon tujuan yang terbukti menjauhi garis tidak eligible/+0;
  jika arah/konteks belum jelas, jangan menebaknya. Genuine return yang
  benar dapat dihitung sebagai passage baru bila ada bukti perjalanan baru.
- Ambang numerik handoff, approach/away, pemisahan episode dan role belum
  ditentukan. Audit mencari bukti dan merancang uji; jangan memilih angka
  hanya agar contoh tertentu lolos.
- Izin timeout kendaraan tidak otomatis berlaku bagi pedestrian. Jalur
  inferensi pedestrian serta taxonomy BUS/angkot masih OPEN. Catat dampaknya
  tanpa memilih kebijakan bisnis secara diam-diam.
- YOLO26M, BoT-SORT dan ReID tetap arsitektur yang disepakati. Konfigurasi
  vehicle-ReID final masih OPEN. Tidak ada pemilihan model/retraining baru.

URUTAN KERJA
1. Kunci snapshot, input dan cakupan.
   Baca manifest dan status ketersediaan. Cocokkan versi sumber/anotasi/
   ledger, hash, frame index dan timebase. Jika pencarian frame tidak cocok,
   gunakan decode berurutan yang dapat diverifikasi; jangan menebak offset.
   Catat rencana pilot dan minta konfirmasi cakupan penuh/sampel bila belum
   diputuskan. Persiapan manifest tidak perlu menunggu keputusan cakupan.

2. Inventaris mentah terlebih dahulu untuk setiap segmen audit baru.
   Tonton video sumber tanpa overlay sebelum membaca keputusan model;
   catat unit fisik, passage, arah, role/kategori yang terlihat dan interval
   bukti. Raw ID boleh kosong karena objek dapat tidak pernah terdeteksi.
   Tandai batas segmen/occlusion yang membuat penilaian tidak pasti.
   Catat bila reviewer sudah pernah melihat output model; jangan mengklaim
   review blind. Inventaris ini referensi audit terbatas, bukan GT formal.

3. Cocokkan inventaris dengan output model tersimpan.
   Tinjau accepted (termasuk estimasi), pending, rejected dan unit tanpa
   kandidat. Relasi boleh 1:1, 1:many, many:1 atau unmatched. Jangan memaksa
   pencocokan hanya agar jumlah manual sama dengan machine. Pertahankan
   hubungan objek fisik, episode, passage, raw ID dan event ID secara terpisah.

4. Telusuri akar masalah menurut input–proses–output tiap fase.
   Phase 1: identitas/decode/timebase; segmen gelap, silau, blur, occlusion,
            shake dan alignment geometri, dengan frame bukti.
   Phase 2: bedakan tidak terdeteksi, salah kelas, observasi yang sudah ada
            tetapi tersaring, dan kegagalan downstream. Bila cache tidak
            menyimpan kandidat tertentu, tandai UNKNOWN; jangan mengklaim
            model tidak mendeteksi. Cache TOR3 berskor minimum 0,25 tidak
            dapat dipakai menguji deteksi di bawah batas itu lewat replay.
   Phase 3/4: bedakan fragmentasi/handoff, satu ID berganti objek, salah
              gabung dan asosiasi rider. Gunakan trajectory/appearance yang
              benar-benar tersimpan; jangan mengarang embedding.
   Phase 5: verifikasi koordinat/resolusi acuan, polygon, finite endpoints,
            margin, raw BC, arah, alignment temporal, gap dan sentuhan.
   Phase 6: periksa eligibility, unit/category/identity, clock sumber,
            deduplikasi, completed passage, return serta measured/inferred.
   Phase 7: audit kondisi malam yang tersedia dan bukti eksperimen historis.
            Raw tetap pembanding. Generalisasi enhancement belum terbukti;
            rancang eksperimen baru tanpa menjalankannya pada tugas ini.
   Phase 8: periksa raw ID terbaca, parent rider, sumber/alasan event,
            panel vs ledger, pending di luar accepted, dan agregat yang
            tidak mencampur machine dengan reviewed.
   Bedakan root cause terbukti, contributing factor dan hipotesis yang
   memerlukan eksperimen. Satu kasus boleh melibatkan beberapa fase.

5. Pilot kasus development yang sudah diketahui.
   TGDI-WEEKDAY-SIANG: person 54 frame 57–107 (pedagang gerobak,
   pedestrian saja); 166/185 frame 226 (rider, riwayat166 tercampur);
   857/856 frame 1089 (rider, relasi hanya didukung pada sebagian interval);
   person 3025 frame 5003 (pedestrian; 50003 sudah dikoreksi pengguna).
   Tambahkan konteks sebelum/sesudah yang diperlukan dan catat frame yang
   benar-benar dilihat; jangan menganggap seluruh interval sudah direview.
   Cocokkan sumber review pengguna V2 dengan ledger V3 secara eksplisit.
   Periksa juga contoh73/93, 4149 dan2471/2473/2507 dari bukti tersimpan.
   Kasus yang sudah dipakai menetapkan aturan adalah development, bukan
   hold-out blind. Jangan memilih threshold dari contoh ini saja.

6. Kelompokkan kasus unik dan buat keputusan audit.
   Kelompokkan berdasarkan mekanisme kegagalan sambil mempertahankan semua
   referensi passage fisik; jangan menyamakan ribuan baris CSV dengan ribuan
   kendaraan. Tulis keputusan reviewer, scope, alasan dan bukti penyangkal.
   Contoh hasil: valid measured passage, valid operational estimate menurut
   policy (tetap inferred), duplicate/+0, rider component/+0,
   ineligible/+0, missed passage, wrong merge, wrong category/direction,
   source invalid atau unresolved. Salah satu keputusan tidak otomatis
   menyelesaikan masalah lain dalam kasus yang sama.

7. Bangun backlog perbaikan Phase 1–8.
   Untuk setiap item, isi masalah, kasus/frame bukti, fase akar masalah,
   dampak/ketidakpastian, keputusan yang dibutuhkan, usulan perubahan kecil,
   input eksperimen, baseline/kontrol tetap, proses uji, keluaran yang
   diharapkan dan pengaman regresi. Prioritaskan bukti hitungan palsu,
   duplikasi, salah gabung dan missed passage; jangan hanya volume pending.
   Bedakan rekomendasi dari keputusan pengguna, dan evaluasi desain dari
   hasil eksperimen yang benar-benar sudah dieksekusi.

8. Rekonsiliasi hasil audit dan laporkan batasannya.
   Baseline machine tetap immutable. Simpan keputusan reviewed terpisah.
   Satu keputusan manual yang menambah/mengurangi subtotal harus menunjuk
   event/passage, dimensi kategori/arah dan alasan; machine dan reviewed
   tidak dijumlahkan. Hitung dampak hanya jika bukti dan policy cukup.
   Jika belum ada revisi dieksekusi, tulis future_machine_status=NOT_RUN; delta usulan
   bukan hasil pengujian. Kasus unresolved tidak dikonversi menjadi nol
   kendaraan yang lewat atau otomatis diterima.

KELUARAN
Gunakan folder audit baru results/phase_9/<audit_id>/ setelah mulai mencatat
bukti nyata. Folder ini adalah lokasi rencana, bukan klaim artefak sudah ada.
Ikuti kontrak field di template; minimal tersedia:
- audit_plan.md: cakupan yang disepakati dan prioritas review.
- input_manifest.json: identitas/hash, versi dan readiness sumber/artefak.
- segments.csv: planned, reviewed, partial, unavailable dan belum dilihat.
- passage_inventory.csv: inventaris passage fisik dari video mentah,
  termasuk tanpa raw ID/kandidat.
- cases.jsonl dan evidence/manifest.json: kasus dan indeks bukti yang
  dapat dibuka kembali.
- review_decisions.jsonl: keputusan dengan scope dan dampak event/agregat.
- improvement_backlog.csv: prioritas perbaikan Phase 1–8, rencana uji
  dan open decision.
- comparison.csv: bedakan baseline existing, machine candidate NOT_RUN,
  dan review-assisted assessment. Jangan menganggap assessment manual
  sebagai bukti hasil sistem baru atau eksperimen regresi yang dieksekusi.
- REPORT.md: temuan terkonfirmasi, hipotesis, cakupan, blocker, risiko,
  keputusan pengguna dan rekomendasi tugas implementasi terpisah.
  Jangan membuat laporan berisi hasil kosong seolah audit selesai.

BATAS TUGAS DAN PENERIMAAN
- Audit saja: jangan menjalankan ulang detector, tracker, ReID, counting,
  tuning, preprocessing/enhancement baru atau rendering ulang batch.
  Membuka/decode video sumber dan membaca bukti tersimpan diizinkan.
- Jangan mengubah executable, config frozen, ledger, baseline, manifest
  historis atau anotasi rilis. Perubahan dokumentasi hanya untuk temuan yang
  didukung bukti dan harus mempertahankan konteks snapshot historis.
- Jangan mengimplementasikan backlog, role model, agentic core, Phase 10,
  UI, Docker atau deployment. Reviewer kedua/AI boleh membantu audit;
  kesepakatan reviewer tidak menggantikan bukti dan tidak menjamin nol salah.
- Jangan mengarang dataset, label global, hasil eksperimen, threshold,
  accuracy/precision/recall/F1/MAPE atau peningkatan performa. Tidak ada GT
  formal dan tidak ada target kelulusan persentase yang ditetapkan.
- Audit dapat ditutup pada cakupan yang disepakati bila inventaris dan
  pencocokan tercatat, tiap kasus berstatus diputuskan/unresolved dengan
  alasan, dampak dapat ditelusuri, backlog mempunyai bukti dan rencana uji,
  dan blocker dinyatakan. Pending tidak wajib nol. Penutupan audit tidak
  otomatis berarti semua perbaikan selesai atau sistem siap produksi.

LAPORKAN
1. Input tersedia/hilang/invalid, snapshot dan cakupan yang benar-benar dilihat.
2. Temuan terkonfirmasi, kasus unik, contoh frame dan akar masalah per fase.
3. Accepted yang keliru, duplikasi, salah gabung, passage terlewat dan pending
   yang terselesaikan sebagai +0; gunakan jumlah aktual hanya jika diaudit.
4. Backlog prioritas dan input–proses–output eksperimen per fase.
5. Keputusan yang tetap OPEN, persoalan decode/review dan keterbatasan malam.
6. Artefak yang dibuat, apa yang tidak dijalankan, serta langkah berikutnya.
7. Status audit: belum dimulai/partial/selesai pada cakupan tertentu; jangan
   menyatakan perbaikan counting telah terbukti sebelum pengujian terpisah.
```
