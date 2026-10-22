# QC B v4 — rencana dan batas audit

Tanggal:20 Oktober 2026, zona waktu klienAsia/Bangkok.

Audit pengguna meminta seluruh 68kunci pending pilot:31kontinuitas identitas, 29 role person, 8duplikasi; pemeriksaan inferensi yang tidak diterima dan pencarian passage di luar kandidat.

Baseline immutable adalah Bv4pilot_machine_final TGDI-WEEKDAY-SIANG172 accepted/68 pending dengan9.128 frame sumber. Bv3tersimpan hanya pembanding historis. Video mentah dan cache dipulihkan secara read-only dari Kaggle serta diverifikasi SHA. Tidak ada inferensi detector/tracker/ReID, counting replay, tuning, enhancement, atau rendering batch baru. Helper QC hanya mengekstrak bukti, menghitung diagnostik pengukuran, dan mencocokkan record; bukan penghasil event machine baru.

Seluruh 68case diinventaris dan direview temporal pada frame sumber terpilih percase. Inferensi lama dipetakan exhaustively secara dokumenter; pemeriksaan visualnya berstrata dan adaptif, bukan seluruh 412baris secara manual. Sebagai kontrol regresi tambahan, seluruh 34timeout accepted saat ini diperiksa agar pending turun tidak menyembunyikan false count. Inventaris source-first mencakup sampling merata sepanjangtimeline dengan perluasan lokal; frame yang dilihat dicatat, tanpa klaim semua 9.128 frame ditonton kontinu. Riwayat paparan output model ada: audit tidak blind dan merupakan development.

Keluaran QC adalah rekomendasi AI yang terikat frame/scope, terpisah dari baseline dan keputusan pengguna. Role, identitas fisik, validitas geometri, taxonomy dan countimpact mempunyai status berbeda. COUNT/NO_COUNT/UNRESOLVED tidak boleh disimpulkan hanya dari agreement antaragen. Tidak ada global label berdasarkan rawID atau inferred gap yang dipromosikan menjadi measured crossing. Rekomendasi lintasvideo berupa kebijakan/usulan tes; tujuh video lain dan kondisi malam belum divalidasi dalam audit ini.
