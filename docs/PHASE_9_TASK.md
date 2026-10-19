# Phase 9 — audit manual passage fisik

**PROPOSAL — tugas berikut setelah snapshot revisi Phase 8 tersimpan:** audit hasil aktual dengan video sumber dan jejak keputusan. Phase 9 belum selesai hanya karena kode, tes, replay, atau anotasi selesai. Keputusan pengguna untuk contoh Phase 8 menjadi bukti review yang terbatas pada contoh tersebut.

**FACT — kesiapan teknis saat ini:** snapshot revisi `20261019T045405_106031Z` telah mereplay seluruh delapan video/72.590 frame dari cache terverifikasi, tanpa detector/tracker/ReID ulang. [Retensi aktual](../results/b_v3/execution/final_20261019T045405_106031Z/) dan [audit independen](../results/b_v3/verification/final_delta_audit.json) menyediakan event, pending, konfigurasi, source SHA, serta rekonsiliasi baseline. **Phase 9 sudah dapat dimulai untuk audit snapshot ini**; pending tidak perlu nol. Izin memulai audit bukan kesimpulan siap produksi dan bukan pernyataan audit telah selesai. Render penuh/publikasi anotasi mempunyai bukti delivery tersendiri; replay lokal yang dirujuk di sini tidak merender delapan video.

## Objektif

Membangun referensi audit yang dapat ditelusuri tanpa menyebutnya ground truth formal. Pastikan setiap event yang direview mewakili passage fisik yang dimaksud, dan catat passage yang terlewat atau dihitung keliru. Tujuan bukan membuat pending nol.

Audit dimulai dari snapshot reproducible: identitas input, konfigurasi efektif, kode/source hash, event dan agregat konsisten, serta frame/time sumber tersedia. Jika revisi masih partial, audit hanya menyatakan cakupan slot yang tersedia. Keberhasilan Phase 8 teknis tidak membuktikan kualitas counting produksi; pending yang sudah dijelaskan tetap dapat diaudit.

Snapshot sekarang berisi3.500 accepted operasional:895 crossing terukur dan2.605 inferensi, termasuk2.454 timeout. Pedestrian accepted0 tidak membuktikan tidak ada pedestrian. Pending2.890 kunci mencakup2.427 unknown-person,462 vehicle dan1 positive-role pedestrian; ini bukan2.890 kendaraan yang gagal dihitung. Gunakan [enam keluarga keputusan](../results/b_v3/PENDING_DECISIONS.md), bukan mengaudit baris CSV berulang sebagai kasus fisik terpisah. Dua keluarga vehicle terbesar adalah return-timeout210 dan identitas201, tetapi accepted yang salah dan kendaraan tanpa kandidat tetap wajib diperiksa.

## Urutan review yang diusulkan

1. Periksa contoh regresi 73/93, 4149, dan motorcycle 2473→2507 bersama rider 2471. Cocokkan satu kendaraan/satu passage, pemisahan objek, sumber BC, kategori, arah, serta efeknya pada event lama.
2. Review contoh per keluarga pending: identitas, peran pedestrian/rider, kategori/episode, geometri/gap, dan taxonomy. Pilih sampel yang mewakili kondisi berbeda, bukan hanya contoh berhasil.
3. Audit accepted, terutama timeout dan perpindahan setelah gap, termasuk dugaan kendaraan diam ID 2/34. Periksa salah gabung, hitungan ganda, arah salah, pedestrian/rider, dan event tanpa crossing terukur.
4. Tinjau segmen kontinu sebelum/sesudah passage pada delapan video, termasuk malam dan occlusion. Catat kendaraan yang tidak pernah menjadi kandidat; daftar pending saja tidak dapat menemukan semua missed passage.
5. Bandingkan baseline, machine revision, dan review-assisted pada passage fisik yang sama. Pertahankan semua snapshot dan catat perubahan serta regresi secara terpisah.

Untuk contoh awal:73/93 hanya disambung pada episode car yang direview dan masih pending karena73/77 serta73/87; truck raw93 terdahulu berbeda. Truck4149 `T2013` memakai crossing terukur7422, sedangkan motorcycle4149 `M2213` memakai timeout7691 dan harus diperiksa secara fisik. Motorcycle2473/2507 `M1068` mempunyai satu crossing BC vehicle4231→4232 dengan keputusan4241; relasi2507 bersifat review-assisted, dan bbox simultan pada4277 memerlukan pemeriksaan agar tidak salah menyambung objek. Rider2471 hanya +0 dalam cakupan4204–4254.

Sebelum memakai audit untuk menyetujui konfigurasi berikutnya, konfirmasi tiga preferensi yang masih terbuka: pedestrian hanya measured atau juga inferred route, BUS/huruf tampilannya, dan timeout passage berikutnya tanpa bukti baru. Run yang dibekukan memakai kontrol riset konservatif `measured_only`/`require_new_passage_evidence`; ini tidak boleh ditulis sebagai persetujuan pengguna. Untuk membandingkan varian kebijakan, simpan varian baru terpisah dan jangan menimpa snapshot audit.

Jumlah/durasi segmen audit, cakupan penuh atau sampel, dan pembagian development/hold-out harus disepakati sebelum menyebut audit representatif. Contoh yang sudah dipakai memperbaiki kode adalah development, bukan hold-out yang belum pernah dilihat. Tidak ada target performa atau ambang kelulusan persentase yang dibuat tanpa protokol dan bukti.

## Catatan minimum per kasus

Simpan video/source hash, frame awal/akhir, raw ID dan ID passage/internal terkait, objek fisik, role pedestrian/rider, kategori, arah, asal BC, route, measured/inferred, event baseline/revisi, keputusan reviewer, alasan, dan frame bukti. Tandai `same_vehicle`, `different_vehicle`, `valid_passage`, `duplicate`, `missed_passage`, `wrong_category`, `wrong_direction`, `stationary_or_no_passage`, atau `still_uncertain` sesuai fakta; satu kasus dapat memiliki beberapa masalah.

Keputusan koreksi harus menunjuk cakupan episode dan event yang diubah. Review yang tidak pasti tidak dipaksa menjadi accepted. Manual category/identity review tidak mengubah gap/prediksi menjadi crossing terukur. Review rider tidak berlaku otomatis pada penggunaan raw ID tersebut di kemudian hari.

## Keluaran dan penerimaan audit

- Register kasus dan keputusan reviewer, dibedakan antara machine dan reviewed.
- Daftar kegagalan per keluarga, contoh evidence, dampak terhadap event/aggregat, dan prioritas perbaikan.
- Ringkasan cakupan audit: video/segmen/frame yang benar-benar dilihat dan cakupan yang belum dilihat.
- Perbandingan passage fisik yang sama dan regresi, termasuk accepted salah serta passage tanpa kandidat.
- Keputusan terdokumentasi: kontrol yang dibekukan, perubahan berikut yang dibutuhkan, dan risiko yang belum terselesaikan.

Audit selesai pada cakupan yang disepakati ketika setiap kasus dalam cakupan mempunyai keputusan atau status unresolved beserta perlakuannya, koreksi dapat ditelusuri, dan isu yang menghalangi tahap berikut dinyatakan. Ini tidak menjamin seluruh dunia nyata sudah tervalidasi. Klaim accuracy/precision/recall/F1/MAPE tetap memerlukan protokol ground truth yang belum tersedia; ikuti [EVALUATION.md](EVALUATION.md).

## Fase menuju deployment

Masih ada **lima fase jika Phase 9 ikut dihitung**, atau **empat fase setelah Phase 9 selesai**:

| Fase | Objektif |
|---|---|
| 9 — audit manual | Bukti keputusan, kegagalan, prioritas perbaikan, dan batas kepercayaan hasil. |
| 10 — modular Python | Pindahkan logika yang sudah stabil dari notebook dengan perilaku tetap dan regresi teruji. |
| 11 — UI | Upload/setup geometri, proses, hasil dan audit melalui engine yang sama. |
| 12 — Docker | Paket runtime/dependensi dan GPU yang reproducible, dengan smoke test. |
| 13 — GPU VM | Deploy, uji GPU/model/job, persistensi hasil, resource, serta restart. |

Urutan ini berasal dari [CODEX_WORKFLOW.md](../CODEX_WORKFLOW.md), bukan estimasi lama pengerjaan. Phase 10–13 tidak diimplementasikan dalam revisi Phase 8 ini. Keputusan produksi, vehicle-ReID final, taxonomy, ketahanan identitas, serta kebijakan timeout yang reliable tetap memerlukan bukti dan dapat menghasilkan perbaikan sebelum logika dibekukan untuk modularisasi.
