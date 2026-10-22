# QC independen B v7 — pilot TGDI-WEEKDAY-SIANG

**EXPERIMENT RESULT — duplikasi target 1049→1123 tertahan; P0 keseluruhan tetap BLOCKED.** Review ini membaca hasil replay tersimpan dan gambar sumber. Tidak menjalankan detector, tracker, ReID, counting, atau enhancement. Sumber dan anotasi development sudah diketahui reviewer; ini bukan audit blind, hold-out, atau ground truth formal.

| Keluaran operasional | B v6 | B v7 |
|---|---:|---:|
| Accepted | 74 | 72 |
| Terukur | 66 | 66 |
| Estimasi timeout | 5 | 4 |
| Inferensi line-margin | 3 | 2 |
| Pending | 24 | 24 |
| Invalid/+0 | 84 | 86 |

**FACT — perubahan hitungan hanya dua kandidat target.** Dua event A→B motor merah yang sama, raw1049 timeout dan raw1123 line-margin inferred pada frame1396, tidak dipublikasikan sebagai accepted. Keduanya menjadi invalid/+0 pada finalisasi offline frame9127. Riwayat sumber dan waktu kandidat1396 tetap tersedia. Machine tidak menggabungkan identitas dan tidak menghasilkan crossing terukur dari interval hilang. Pada satu passage fisik yang terlihat di sumber, keluaran machine berubah2→0: duplikasi hilang, tetapi satu passage fisik belum dipulihkan. Ini kehilangan cakupan yang disengaja oleh kebijakan ambigu, bukan bukti hitungan sudah benar.

**EXPERIMENT RESULT — 72 passage yang bertahan mempunyai bukti sumber, kategori, arah, route, waktu, dan scope fisik yang sama.** Tidak ada event baru, perubahan kategori, perubahan arah, atau promosi inferred menjadi measured. Sebanyak17 label tampilan A→B dinomori ulang setelah dua kandidat dihapus; contohnya raw1496 berubah M2012→M2010. Perubahan label tersebut dicatat di `display_only_renumberings`, sehingga ID tampilan harus dirujuk bersama versi hasil, rawID dan frame. Seluruh assignment identitas sumber dan24 keputusan pending identik. Jumlah `count_delta` pada log publik72 cocok dengan agregat.

**EXPERIMENT RESULT — tidak ada perubahan pada kontrol terdahulu.** Scope keputusan dan assignment untuk4251/4281,4149/4367,4934/4946/4953,2445,4552/4480,1101 dan1070 tetap sama. Source sheet menunjukkan4251/4281 adalah box komponen pada satu skuter,4149/4367 memuat pergantian konteks truck/person,4934/4946/4953 memuat komponen motor dan rider, serta4552 terpisah dari SUV4480. Review ini tidak mengesahkan seluruh invalid lama sebagai keputusan fisik yang benar. Kontrol2445 dipertahankan menurut artefak/kontrak terdahulu; tidak dibuat klaim review visual baru atas kasus itu.

**FACT — batas kontrol negatif aktual.** Motor1123 merah berbeda dari1101 yang mengikuti dan koeksis pada1376;1123 juga berbeda dari1070 yang bergerak berlawanan pada1355/1376. Raw1101/1070 tidak mempunyai event accepted pada baseline. Karena itu bukti aktual ini menunjukkan unit dan assignment tetap terpisah, bukan pembuktian bahwa dua hitungan accepted atau genuine return aktual berhasil dipertahankan. Kelulusan kontrol accepted/genuine-return sintetis dilaporkan terpisah oleh pengujian perangkat lunak.

**EXPERIMENT RESULT — inventory QC lama tidak tertinggal.** Pembanding documentary yang sudah ada dijalankan terhadap hasil baru dan disimpan sebagai `legacy_inventory_comparison.json`. Seluruh68 kasus pending,16 cancellation, dan10 discovery mempunyai caseID dan disposition sumber yang sama dengan QC B v6 setelah hanya eventID/namespace yang terikat policy dikecualikan dari pembandingan. Tidak ada blocker duplikasi baru pada16 kontrol tersebut. Kelengkapan inventory ini tidak sama dengan audit menyeluruh semua passage video.

**FACT — seluruh delapan inferred baseline telah dibaca bersama source sheet; enam tetap inferred.** Pada368,717,2551 dan3211, occlusion dan identitas successor belum cukup untuk menyatakan estimasi sebagai crossing terukur. Motor3670 putih dan3682 arah lawan merupakan unit terpisah pada sampel yang dibuka. Dua target1049/1123 telah dijelaskan di atas. Kasus4843 berikut tetap membatasi kelulusan keseluruhan; tidak ada klaim semua estimasi valid atau tidak ada kesalahan lain di luar window review.

**FACT — blocker sumber yang masih aktif: raw4843.** Pada7888/7899/7905 terdapat dua motor berbeda, merah4808 dan biru4843. SUV hitam menutup pandangan. Bbox4843 pada7928/7935 mencakup motor merah; pada7950 motor biru tampak sebagai4913 dan motor merah masih berada dalam bbox4843. Event inferred A→B7935 yang tetap accepted memakai origin7899 dari motor biru dan destination7935 dari motor merah. Ini kontaminasi identitas pada rawID/kelas yang tetap, sudah ada di B v6 dan berada di luar matcher handoff lintas-ID. Bukti ini belum menetapkan alias otomatis, jumlah passage salah global, atau extra accepted duplicate:4808 sudah invalid,4913 tidak accepted.

**PROPOSAL — langkah berikutnya:** buat fixture pemisahan episode untuk rawID dan kelas yang tetap setelah occlusion, menggunakan4843 sebagai development dan kendaraan berdekatan sebagai kontrol negatif. Origin, timer dan destination harus berasal dari episode fisik yang sama. Hubungan yang belum terbukti tetap mengikuti kebijakan konflik; jangan memilih alias dari kemiripan trajectory atau mengubah inferred menjadi measured. Pulihkan satu passage target melalui bukti identitas positif dalam eksperimen/overlay reviewed yang terpisah bila dibutuhkan, tanpa mencampur subtotal machine.

**Keputusan QC:** PASS hanya untuk regresi pencegahan duplikasi1049→1123 dengan kehilangan cakupan yang dinyatakan. P0 keseluruhan **BLOCKED** oleh kontaminasi sumber4843 dan kebutuhan disposition berbukti atas episode tersebut. Tidak ada dasar untuk klaim akurasi, zero mistakes, kelulusan delapan video, malam, atau produksi.

Artefak yang dapat diperiksa:

- `independent_replay_qc.json`: dua perubahan event,17 perubahan label, kontrol, dan rekonsiliasi log.
- `legacy_inventory_comparison.json`: seluruh inventory68+16+10.
- `independent_4843_identity_review.json`, `inferred_source_4843.jpg`, `inferred_detail_4843.jpg`: bukti blocker yang tersisa.
- `all_baseline_inferred_review.json`: delapan estimasi baseline beserta batas review.
- `independent_retained_evidence_verification.json`: hash sumber aktual, tujuh image binding, dan10 hash fixture target.

Perintah QC aktual:

```bash
/workspace/.venvs/traffic-inspection/bin/python \
  results/b_v7/review/independent_replay_qc.py \
  results/b_v7/execution/pilot_v7_machine_final/weekday_siang/counting_result.json.gz
```
