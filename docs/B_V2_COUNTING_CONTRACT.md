# Kontrak eksperimen counting B v2

Status: perubahan yang diminta pengguna untuk replay pengukuran Phase 8 yang sudah tersimpan. Kontrak ini mendefinisikan perilaku perangkat lunak; bukan hasil delapan video, bukti akurasi, atau persetujuan produksi. Kebijakan, kode, event, dan bukti B v1 tetap menjadi pembanding historis yang terpisah.

## 1. Keputusan pengguna dan sumber geometri

**REQUIREMENT — pengguna:** geometri dari `TGDI-WEEKDAY-PAGI-geometry-review.json` menjadi acuan seluruh delapan video TGDI. Sumber asli disimpan tanpa mengubah byte pada [input geometri](../results/b_v2/input/TGDI-WEEKDAY-PAGI-geometry-review.json). File tersebut merupakan ekspor editor sebelumnya; flag bahwa counting belum disetujui di dalam ekspor adalah provenance waktu ekspor, bukan pembatalan permintaan implementasi pengguna yang datang sesudahnya.

**FACT:** delapan sumber TGDI yang sudah retained berukuran 640×480. Konfigurasi turunan per video mengikat template yang sama dengan identitas dan SHA sumber masing-masing pada [geometry manifest](../results/b_v2/config/geometry_manifest.json). Penerapan ke delapan video ini diizinkan pengguna; kesesuaian sepanjang waktu tetap perlu diperiksa dari replay.

- Ruang koordinat: pixel native frame penuh, origin kiri atas, x ke kanan, y ke bawah.
- Garis menggunakan endpoint asli pada JSON: P1≈(1,6844; 429,9945), P2≈(617,3266; 1,3159). Pembulatan pada kalimat ini hanya untuk pembaca; konfigurasi menyimpan presisi sumber.
- Margin adalah **half-width 25 pixel**, tegak lurus garis; lebar total pita **50 pixel**.
- Pita berbentuk persegi panjang dengan ujung datar, terbatas pada proyeksi P1–P2. Perpanjangan garis tak terbatas tidak menjadi bukti crossing segmen.
- Polygon A/B memakai semua vertex dalam lampiran tanpa penyesuaian diam-diam. Batas polygon netral menurut implementasi geometri yang digunakan.
- `A_TO_B` berarti mendekati kamera; `B_TO_A` berarti menjauhi kamera, mengikuti pemetaan TGDI yang sudah dikonfirmasi.

Kendaraan dapat berpindah sisi garis tak terbatas di luar endpoint jika lintasannya atau ROI berada di luar cakupan segmen. Jalur kendaraan di jalan tidak membuktikan setiap BC selalu memotong segmen yang dipilih. Pemeriksaan finite segment tetap diperlukan.

## 2. Unit, anchor, dan asumsi identitas

**REQUIREMENT — pengguna:** motorcycle bersama rider/passenger adalah satu motorcycle. Bbox gabungan dipakai untuk menampilkan komponen yang sudah terasosiasi sebagai satu unit. Rider tidak menambah hitungan.

**REQUIREMENT:** anchor counting tetap bottom-center bbox **kendaraan mentah yang diukur**, terhubung langsung ke deteksi sumber dan emitted track. Bbox gabungan tampilan, rider BC, prediksi tracker, dan rata-rata beberapa bbox tidak mengganti anchor tersebut.

**ENGINEERING ASSUMPTION:** untuk kendaraan yang tidak mempunyai grouping yang didukung, ID tracker yang tetap digunakan sebagai satu unit operasional. Asumsi ini tidak membuktikan identitas fisik dan tidak memperbaiki ID switch. Relasi duplicate/component yang didukung dari run tersimpan dapat digunakan kembali dengan kontrol aslinya; tidak ada algoritme asosiasi identitas atau model appearance baru pada eksperimen ini. Grouping duplicate memerlukan graph clique yang didukung dan tidak mempunyai pasangan internal yang unresolved.

Overlap bbox saja tidak otomatis menahan atau menggabungkan kendaraan. Dua kendaraan yang berdekatan tetap dua unit. Konflik duplicate yang secara eksplisit tersimpan tetap dapat membuat passage pending. Jalur occlusion atau timeout tidak membuktikan dua ID adalah kendaraan yang sama.

## 3. Tiga jalur dan prioritas bukti

Satu unit/passage mempunyai satu event aktif. Urutan prioritas bukti adalah `LINE_MARGIN` → `OCCLUSION_DIFF_POLYGON` → `ESTIMATED_TIMEOUT`. Prioritas ini mengatur klasifikasi dan rekonsiliasi bukti, bukan tiga penjumlahan untuk passage yang sama.

### 3.1 Garis dengan margin

Log yang diminta: `ID-KATEGORI; A_TO_B/B_TO_A; CROSSING_LINE`.

- Kendaraan harus mempunyai pengukuran pada sisi asal dan kemudian pada sisi berlawanan di luar margin. Kehadiran pertama di pita, menyentuh garis, berhenti, atau masuk pita lalu kembali tidak langsung menghasilkan +1.
- Crossing terukur memerlukan bukti perpindahan sisi melalui interior segmen terbatas dari pengukuran berurutan. Kontak pada endpoint atau crossing pada perpanjangan garis tidak menjadi crossing finite yang terukur. Kontak tepat pada garis hanya sah sebagai bagian trajectory yang benar-benar berpindah sisi; kontak saja tidak cukup.
- Jika kendaraan teramati di pita lalu hilang dan muncul di polygon tujuan dengan ID yang sama, jalurnya tetap `LINE_MARGIN` sesuai prioritas pengguna. Interval hilang tetap disimpan; `measured_crossing=false` jika kontinuitas bukti crossing/konfirmasi tidak ada. Label jalur garis tidak menyatakan momen crossing terlihat langsung.
- Jika dua frame berurutan melompati seluruh pita tetapi segmen antar-BC memotong interior garis, crossing terukur dapat diterima tanpa sampel BC tepat di pita. Sumber kategorinya dicatat sebagai fallback endpoint, bukan kategori yang diamati di pita.

### 3.2 Polygon berbeda setelah occlusion

Log yang diminta: `ID-KATEGORI; A_TO_B/B_TO_A; OCCLUSION_DIFF_POLYGON`.

- Kendaraan teramati di polygon asal, mempunyai interval frame tanpa pengukuran, lalu muncul di polygon tujuan.
- Tidak ada BC kendaraan yang teramati di pita pada passage tersebut. Jika ada, jalur garis mendapat prioritas.
- ID mentah, kategori endpoint, serta arah gerak harus konsisten. Arah didukung perpindahan pengukuran menuju sisi tujuan; gerak yang berbalik tidak dianggap arah yang sama.
- ID baru tidak dihubungkan secara spekulatif ke ID yang hilang. Perpindahan raw track saat passage tetap unresolved meskipun caller mengenal group unit.
- Jalur ini menambah satu hitungan operasional, dengan `measured_crossing=false`. Kedatangan di polygon tujuan merupakan bukti perpindahan ROI setelah gap; momen crossing segmen tidak diobservasi langsung.

### 3.3 Timeout otomatis 60 frame

Log menampilkan label yang diminta `CHANGE_ID` serta penanda `ESTIMATED_TIMEOUT`. Label `CHANGE_ID` tidak berarti pergantian ID terbukti; `id_change_proven=false` tetap disimpan.

**REQUIREMENT — klarifikasi timer pengguna, persis:** **“Sejak terakhir terlihat di polygon asal”.**

- Clock dimulai ulang pada setiap pengukuran di polygon asal, termasuk ketika kendaraan berhenti. Event dapat terbit pada indeks frame sumber `last_observed_origin_frame + 60` jika semua syarat lain masih terpenuhi.
- Frame adalah indeks frame sumber, bukan jumlah observasi track. Konversi ke detik mengikuti FPS sumber; jangan menganggap seluruh video tepat 30 FPS.
- Harus ada bukti gerak menuju garis dan belum ada pengukuran di polygon tujuan. Kendaraan yang hanya muncul sekali atau tidak mempunyai arah pendekatan yang dapat ditentukan tidak otomatis mendapat arah faktual.
- U-turn sebelum menyentuh pita, dengan ID yang sama dan gerak berlawanan, membatalkan eligibility timeout. Gerak diukur dari perubahan signed distance terhadap garis; belum ada threshold smoothing/jitter baru yang dikalibrasi.
- Kendaraan yang masih terlihat di asal terus memperbarui clock. Tidak muncul di tujuan saja tidak membuat kendaraan yang sedang diam dihitung pada 60 frame sejak pertama masuk.
- Hanya frame yang benar-benar ada diproses. Akhir video tidak ditambah 60 frame fiktif; timer yang belum jatuh tempo tidak dipaksa menghasilkan event.
- Event ini **otomatis +1 sesuai keputusan pengguna**, tetapi merupakan estimasi operasional. Arah asal→tujuan dicatat sebagai asumsi pada event timeout; timeout sendiri tidak membuktikan crossing, pergantian ID, atau kendaraan fisik yang sama dengan ID lain.

## 4. Kategori di sekitar crossing

**REQUIREMENT — pengguna:** utamakan ID dan tipe kendaraan ketika BC berada pada garis beserta margin.

**ENGINEERING CHOICE — eksplisit untuk eksperimen ini:** setiap pengukuran kendaraan di dalam pita memberikan satu vote kategori mentah. Kategori dengan jumlah vote terbanyak menjadi kategori passage; seri tetap pending. Tidak ada persentase, confidence threshold, atau bobot temporal baru yang disisipkan.

Jika tidak ada pengukuran BC di pita, kategori origin dan destination harus cocok. Untuk timeout, gunakan kategori pengukuran asal dan pengukuran terakhir yang sesuai; sumber fallback disimpan. Bukti pita yang muncul setelah timeout dapat mengganti kategori estimasi pada event yang sama.

Cakupan kategori otomatis eksperimen ini adalah `motorcycle`, `car`, dan `truck`. Konflik kategori, vote seri, atau taxonomy yang belum didukung tetap pending. `bus` tidak diam-diam dipetakan ke angkot; pickup/minivan dan kategori bisnis lain tetap memerlukan keputusan terpisah.

## 5. Deduplikasi, genuine return, dan revisi offline

**REQUIREMENT — pengguna:** genuine return yang menghasilkan passage nyata boleh dihitung lagi. Setelah A→B selesai, lintasan baru B→A dapat menjadi event berikutnya. Izin tersebut tidak berarti jitter, pergantian cabang keputusan, atau kemunculan kembali dari satu passage dihitung ganda.

- Kunci passage mengikat unit dan urutan passage dalam source/policy namespace yang reproducible.
- Timeout yang kemudian memperoleh bukti arrival/crossing diperbarui pada event yang sama; increment rekonsiliasi adalah 0.
- Jika bukti berikutnya membantah timeout—misalnya return/U-turn sebelum crossing, konflik identitas, atau kategori yang belum terselesaikan—hasil offline dapat membatalkan estimasi dan menyimpan log koreksi −1.
- Event final, log perubahan, cancelled event, dan pending dipertahankan. Agregasi final berasal dari event aktif yang accepted; log +1/−1 tidak dijumlahkan lagi dengan event final.
- B v1, B v2, dan hasil reviewed adalah snapshot terpisah; tidak dijumlahkan menjadi satu subtotal.

Finalisasi tetap offline setelah replay video selesai. Panel menunjukkan replay ledger offline beserta lognya, bukan janji latensi atau reliabilitas sistem online.

## 6. Output dan batas modul

Implementasi notebook tetap berada di bawah `notebooks/`, tanpa refactor Phase 10 atau UI produksi:

- [phase_8_b_v2_counting.py](../notebooks/phase_8_b_v2_counting.py): state/passage ledger murni dari frame pengukuran terverifikasi; entry point `replay_frames(...)`.
- [phase_8_b_v2_batch.py](../notebooks/phase_8_b_v2_batch.py): validasi donor run, deteksi-source linkage, geometri, grouping retained, dan replay terpisah.
- [phase_8_b_v2_annotation.py](../notebooks/phase_8_b_v2_annotation.py): gambar bbox unit, raw vehicle BC, pita, pivot, dan log passage.
- [08b_counting_b_v2_replay.ipynb](../notebooks/08b_counting_b_v2_replay.ipynb): entry point Kaggle CPU untuk konfigurasi, validasi, replay cache, dan annotated video.
- [policy.json](../results/b_v2/config/policy.json): margin, timer, category policy, serta asumsi eksperimen yang eksplisit.

Output replay dipisahkan dari hasil historis. Simpan event aktif, cancelled event, pending/decisions, passage log, subtotal kategori/arah/jalur, input/config hashes, dan laporan eksekusi. Setiap event memuat frame aktivasi/keputusan, raw vehicle measurement references, kategori dan basisnya, gap, route, serta flag crossing terukur/inferensi.

**Batas perbandingan pending:** kontrak B v2 menghendaki satu keputusan pending per unit/passage dengan kumpulan alasannya. Audit replay aktual menemukan keterbatasan diagnostik: 244 baris pending mewakili 242 kunci unit/passage berbeda; dua kunci weekend_sore mempunyai baris berulang setelah reset state. Hasil asli tetap dipertahankan dan jumlah baris tidak disebut kendaraan unik. Sebanyak 1.825 pending B v1 adalah kandidat/diagnostik geometri, termasuk diagnostik gap, bukan unit/passage fisik yang unik. Kedua angka memakai penyebut berbeda dan tidak boleh dipakai langsung untuk menyatakan persentase penurunan pending. Kehadiran awal tanpa bukti passage dan trajectory yang belum selesai pada EOF tetap dilaporkan melalui counter serta `open_passage_diagnostics`; kasus tersebut tidak diam-diam diartikan nol kendaraan atau seluruhnya dihitung sebagai pending. Audit tetap perlu memeriksa kendaraan yang tidak pernah menghasilkan kandidat/event.

Pada annotated video, **log kendaraan lewat berada di bawah bagian passage accepted dan di atas pending**. Log memuat ID, kategori, arah, label jalur, frame, dan perubahan hitungan. Subtotal tiap jalur menjaga kontribusi timeout terlihat. Bbox gabungan tidak mengganti penanda BC kendaraan mentah.

Folder tingkat atas `results/` tetap menjadi pintu masuk hasil dan indeks unduhan. Video besar dapat dipublikasikan sebagai release asset dengan tautan dari folder tersebut; sumber video asli tidak dimasukkan ke Git.

## 7. Validasi dan batas klaim

Uji sintetis memeriksa finite band, kontak tanpa crossing, endpoint/perpanjangan, gap, kategori pita, timeout tepat waktu, stationary clock reset, U-turn, upgrade/cancellation, genuine return, rider +0, dan deduplikasi known unit. Uji perangkat lunak tidak mengukur counting accuracy.

Replay awal menggunakan cache Phase 8 yang sudah ada; detector, tracker, ReID, dan encoder tidak perlu dijalankan ulang. Kode atau notebook yang selesai dibuat tidak membuktikan replay delapan video telah selesai.

Hal yang masih membutuhkan bukti: kesesuaian geometri temporal delapan video, salah gabung/duplikasi fisik, stabilitas kategori, akibat jitter pada arah/U-turn, hitungan timeout yang benar/salah, kendaraan yang tidak mempunyai track/kandidat, biaya pemrosesan, serta perbandingan passage fisik B v1 dan B v2. Tidak ada ground-truth dataset; penurunan pending atau kenaikan total operasional saja tidak membuktikan peningkatan reliabilitas.
