# Pemeriksaan kelengkapan QC

| Permintaan | Cakupan yang benar-benar dikerjakan | Hasil/batas |
|---|---|---|
|31kontinuitas identitas|31 row join ke baseline dan bukti temporal perkasus|28 rekomendasi+0;3unresolved|
|29 role person|29 row dengan frame/scope/parent dan bukti sumber|27 rekomendasi selesai;2unresolved|
|8 konflik duplikasi|8 row, counterpart relasi, source/frame, geometry diagnostics|4 selesai;4 identity-resolved tetapi taxonomy-open|
|Kasus jangan hilang atau dobel|Set68passage_id QC dibandingkan set68 pending baseline; caseID unik|Tidak ada missing, extra, atau duplicate key|
|Inferensi yang tak diterima|Semua 463inferensi Bv3 dipetakan ke51Bv4 berdasarkan sumber|44 counterpart, 419old-unmatched, 7new-only; net−412|
|Review visual inferensi|24 kasus berstrata, termasuk9 OCCLUSION lama dan 7new-only dengan konteks|Bukan adjudikasi visual seluruh 419 event|
|Accepted sebagai kontrol regresi|Semua 34timeout mempunyai visual-sample status; LINE_MARGIN diperiksa pada temuan silang|14timeout cancel-proposed, 20QC-unresolved;2 LINE_MARGIN cancel-proposed tambahan|
|Tidak menghitung koreksi ganda|16cancel-proposal berdasarkan eventID unik; canonical keep tidak juga cancelled|4934direkonsiliasi sekali dalam kelompok4934/4946/4953|
|Passage tanpa kandidat|153 frame merata, 72dense awal/tengah/akhir, adaptive source review, root36 frame diagnostik tambahan|10discovery/diagnostic groups;49band-born dan 4552wrong-unit-group adalah temuan utama|
|Semua diagnosis discovery punya status|Warm-up, EOF, known-history, already-counted, coverage-hole dipisah|Tidak semua sign change menjadi missed passage; tidak memaksa+1|
|Input sah|Video/rawcache/relations SHA cocok; sourcepixel receipt disimpan|Cache di bawah confidence tersimpan tidak tersedia|
|Baseline immutable|117 artefak sebelum/sesudah dan executable dibandingkan hash|Tidak ada model/counting/enhancement rerun atau config/ledger lama berubah|
|Generalisasi|Kontrak/usulan uji lintasvideo tertulis|Tujuh video lain dan malam belum divalidasi oleh QC ini|

Selesai pada scope QC ini bukan jaminan zero-error atau audit kontinu semua
9.128 frame. Semua 68 pending mempunyai keputusan atau unresolved yang eksplisit.
Unresolved bukan pekerjaan yang diam-diam dibuang: case, alasan, risiko dan
kebutuhan buktinya tersedia.20 accepted-timeout juga belum dipromosikan sebagai
validated traffic count. Seluruh 172 accepted tidak dinyatakan sudah benar.

Lihat validation.json untuk pemeriksaan referensial/hash dan REPORT.md untuk
interpretasi. Tidak ada total reviewed video final yang diterbitkan.
