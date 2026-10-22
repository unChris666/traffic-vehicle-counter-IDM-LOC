# Pilot audit Phase 9 — TGDI-WEEKDAY-SIANG

Status: COMPLETE_SCOPE — targeted pilot only; source/config baseline tetap beku.
Audit ID: 20261019T140653Z_TGDI_WEEKDAY_SIANG_PILOT

## Cakupan yang diotorisasi

Pengguna meminta verifikasi input dan pilot development TGDI-WEEKDAY-SIANG, lalu memilih “Selesaikan pilot dan daftar perbaikan dahulu”. Tidak ada perluasan full-video/delapan video. Pilot adalah review kasus terarah, bukan inventory lengkap seluruh lalu lintas. Raw source tersedia lokal dan hash/frame pixels diverifikasi.

Target: pedestrian 54 frame 57–107; episode166/motor 185 sekitar188–301; rider 857/motor 856 sekitar1082–1203; pedestrian 3025 sekitar4986–5053. Rentang pilot awal dicatat pada ekstraksi; konteks tambahan900–1080 serta frame 104–140 diperiksa setelah tantangan independen untuk menguji hipotesis. Perluasan konteks bukan hold-out.

## Metode dan keterbatasan

Review visual memakai urutan sampel frame native dari decode berurutan, bukan klaim seluruh frame/klip telah dilihat. Reviewer sudah mengetahui label pengguna dan kasus historis, sehingga KNOWN_EXPOSED, bukan blind. Inventory target berasal dari frame mentah; reviewer sudah terpapar hasil historis dan ringkasan record baru. Karena itu raw_first_status=ALREADY_EXPOSED, bukan klaim inventory blind. Sampel tidak membuktikan tidak ada kendaraan lain yang terlewat di antara frame; jumlah missed passage seluruh segmen/video tidak dihitung dari pilot ini.

Baseline lokal: 20261019T045405_106031Z. Anotasi Kaggle: version2/run20261019T070846_020453Z. Assessment policy: timeout60 frame sumber hanya kandidat eligible tanpa konflik identitas relevan, last-origin diperbarui observasi/verifiedhandoff, passage selesai tidak dibuka karena timer/ID. Policy terbaru tidak ditulis ulang ke snapshot.

Pedestrian inferred-route, taxonomyBUS dan kriteria numerik identity/role tetap OPEN. Tidak ada inference, replay counting, enhancement, tuning atau perubahan pipeline. Decode sumber dan pembacaan artefak saja.

Output: manifest input; evidence dan cakupan sampel; inventory target; cases dan overlay review; backlogPhase1–8; comparison reviewed vs baseline dengan future machine NOT_RUN; REPORT. Tidak ada promosi otomatis Phase 10.

## Cakupan aktual dan penutupan

70 frame native unik diperiksa visual (lihat input_manifest dan segments.csv), bukan seluruh rentang enclosing. 7 frame anotasi rilis diperiksa setelah checksum MP4 diverifikasi; seluruh 9.128 frame anotasi hanya didekode untuk integritas. Inventory mencakup 7 objek target, bukan seluruh kendaraan di antara sampel. Konteks S2 diperluas900–1080 setelah reviewer penantang menemukan kemungkinan riwayat sebelum raw 856.

7 keluarga kasus dicatat, termasuk satu usulan reviewed pedestrian +1, satu event tambahan M1007 yang diusulkan dibatalkan, satu passage skuter putih tetap unresolved, rider +0 dalam scope terbatas, dan pedestrian 3025 operasional +0 dengan coverage OPEN. Tidak ada total reviewed final untuk seluruh objek pilot atau video. Tidak ada hasil mesin baru; eksperimen perbaikan NOT_RUN.
