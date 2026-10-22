# QC8 konflik duplikasi

Delapan kasus telah direview pada176 frame sumber terpilih. Ledger
[per_case_decisions.jsonl](per_case_decisions.jsonl) menyimpan scope, bukti,
counterpart relasi, geometry witness dan status taxonomy.

- 2615dan4990:objek parkir,+0.
- 4820:duplikat unit cargo van4774,+0tambahan.
- 3582/3587:satuSUV, rekomendasi+1CAR dengan BC6346→6347.
- 2549/2561:satuangkot/minivan putih-merah;fragmen2560 di grup identity
  merujuk passage yang sama,+0tambahan. Kategori tetapOPEN.
- 3761:pickup bergerak lalu rawID berpindah ke objek parkir;scope dipisah,
  kategori bisnis pickup tetapOPEN.
- 4115vehicle:satuminivan/angkot dengan rawclass campuran;taxonomyOPEN.
- 4774:satucargo van;taxonomyOPEN, bukan dua unit bersama4820.

Geometry diagnostics menemukan proper consecutive pairs2549:4117→4118,
3582:6346→6347, 3761:6770→6771, 4115:7214→7215, 4774:7853→7854.
Ini tidak memperbaiki kategori secara otomatis dan tidak mengubah gap menjadi
crossing terukur. Tiga accepted findings tambahan membatalkan2584/C1002,
3512/C1004 yang parkir, serta2697/T1001 yang duplikat MPV2706/C1003.
Root mendeduplikasi event actions; jangan menjumlahkan cancel subgroup lagi.

Empat pending direkomendasikan selesai(3×+0, 1×+1);empat masih taxonomy-open.
Semua rekomendasi AI, bukan perubahan ledger atau ground truth formal.
