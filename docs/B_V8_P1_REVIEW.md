# P1 / B v8 — review pending dan pemulihan passage konservatif

21 Oktober 2026. Status akhir dan angka kandidat terpilih dicatat setelah
rekonsiliasi replay penuh pada bagian hasil dan gate di bawah. Kontrak:
[B_V8_P1_CONTRACT.md](B_V8_P1_CONTRACT.md). Seluruh keluaran P1 adalah cabang
`review_assisted`; baseline mesin B v7 tetap tersimpan terpisah.

## Baseline terverifikasi dan ruang lingkup

Branch `work`, HEAD `806ae761998e487265f3a032d616a59af56bb9a7`. Workspace
memuat helper/notebook dan artefak eksperimen yang belum seluruhnya tercermin
pada commit publik. Perubahan pengguna dipertahankan. Baseline diikat oleh
hash executable/dokumen/artefak, bukan oleh HEAD saja.

**FACT:** baseline B v7 SHA256
`b72269090426172cd67f814a40403b2367151cbab80889fe6cb77ab37c183bad`
memiliki72 accepted (66 terukur,6 estimasi),24 pending dan86 invalid. Seluruh
132 artefak retensi B v7 dan11 binding source/dokumen cocok sebelum perubahan.
Snapshot sebelum P1 mengikat4.080 file historis.

Sumber TGDI-WEEKDAY-SIANG beresolusi640×480,9.128 frame. SHA video
`5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1`,
cache `bc484aff0372242925f8b87e6d91ffc2ac11ae696ed3f59201a73d44f98a145b`,
geometri `d4a3861f0a0130dc7fe0ba4cfe574b5ceeafd8cb9c7141be46ee4541163909d1`.
Detector/tracker/ReID/enhancement tidak dijalankan ulang. Model, margin25px,
timeout60 frame sumber dan kontrol handoff5 observasi B v7 tidak dituning.

**REQUIREMENT:** pengguna mengizinkan P1 meskipun gate mesin B v7 masih
BLOCKED. Ini tidak mengganti hasil mesin, menutup P0 mesin secara otomatis,
atau memulai refactor/produksi. Tidak ada ground truth seluruh video.

## Penyebab yang diperiksa dan perubahan implementasi

1. **Pending role berisi komponen yang sudah mempunyai bukti review positif.**
   Label detector `person` tetap measurement mentah; rider, occupant dan cargo
   tidak menjadi unit hitung independen. Finalizer baru menutup kandidat
   pending yang tepat dengan0, tanpa melabeli seluruh raw ID sebagai rider.
2. **Origin dan destination raw4843 berasal dari objek berbeda.** Wrapper
   source review memisahkan konteks biru dari merah, lalu menghubungkan
   measurement merah4808 sebelum gap dengan merah4843 sesudahnya. Raw BC dan
   gap tetap utuh; hasil merah harus inferred.
3. **Handoff palsu dengan kendaraan pesaing4798.** Source review merah saja
   belum cukup: gate lama menduga4798→4843 karena IoU endpoint≈0,707 dan
   center jump≈0,096. Sumber memperlihatkan motor4798 berbeda dan koeksis
   dengan merah/ biru. Review episode utuh7796–7903 memakai108 observasi
   kontinu dan anchor berpiksel; pengaman DISTINCT yang sudah ada menolak
   hipotesis handoff tersebut. Passage4798 yang sah tetap dipertahankan.
4. **Passage1049→1123 sebelumnya dibuang untuk mencegah duplikasi.** Review
   source yang sudah tersedia dibuka kembali untuk satu unit fisik, dengan
   scope berhenti pada konfirmasi1396. Riwayat raw1123 sesudah1396 tidak
   diberi label identitas yang sama. Ini menguji recovery berbukti tanpa
   melemahkan perlakuan input yang belum direview.

Kode baru terisolasi:

- `notebooks/phase_8_b_v8_review.py`: memakai validator overlay B v4 yang
  dipertahankan, memeriksa cache/pixel anchors, menambahkan typed review refs
  dan menerapkan scope per-track yang tepat.
- `notebooks/phase_8_b_v8_finalize.py`: finalisasi exact pending candidate
  menjadi `resolved_not_eligible` dengan alasan komponen tidak independen,
  bukan relabel semua unknown menjadi invalid.
- `notebooks/phase_8_b_v8_batch.py`: replay penuh reviewed dengan engine
  identity B v6 dan counting B v7 yang tidak diubah, provenance dan retensi
  per run. Baseline mesin dibaca, tidak diklaim dieksekusi ulang di P1.
- `notebooks/phase_9_v8_compare.py`: rekonsiliasi event berdasarkan source
  witnesses dan seluruh kasus pending berdasarkan unit/episode/proof.
- Notebook09e, tes baru dan script audit/source fixture melengkapi reproduksi.

Tidak ada raw ID, warna atau case ID sebagai aturan runtime counting. Nomor
kasus hanya terdapat pada data review, fixture, tes dan audit. Tidak ada
threshold asosiasi baru, alias global, BC sintetis, atau fitur model baru.

## Semua24 pending asal direview

[Inventory JSON](../results/b_v8/pending_review/pending_inventory.json) dan
[CSV](../results/b_v8/pending_review/pending_inventory.csv) berasal dari24
keputusan pending pada baseline, bukan68 kasus QC historis atau jumlah baris
CSV lama. Seluruh source witness diverifikasi terhadap cache aktual.

| Kelompok | Jumlah | Perlakuan |
|---|---:|---|
|Rider/vehicle occupant dengan bukti positif|21|Reviewed non-independent component,+0 |
|Cargo raw3555 pada motor3563|1|Cargo+0; motor3563 yang sudah accepted tetap satu |
|Pedestrian54|1|Role positif57–140 direplay lewat geometri B v7 |
|Role/identitas3185 belum cukup|1|Tetap pending; butuh bukti pada kandidat aktual |

**FACT:**21 review person tidak menetapkan parent global atau role seluruh
raw history. Contohnya4175 pernah mempunyai konflik continuity; bukti komponen
pada source sample7354 hanya menutup kandidat itu, tidak memperbaiki crossing
yang invalid. Raw class dan role measurement lama tetap disimpan bersama
`reviewed_role`, reason lama, proof dan asal keputusan.

Cargo3555 bukan perubahan taxonomy truck secara global. Bukti6269 menunjukkan
muatan pada motor3563; BC cargo tidak menjadi crossing kendaraan tambahan.

Person54 diterima hanya setelah replay source BC memenuhi geometri. Perubahan
bbox-bottom104→105 sekitar43px membuat waktu crossing fisik kaki tidak dapat
disamakan dengan hasil matematika BC. Review ini tidak membuktikan robustness
terhadap truncation/watermark. Sesudah140 role tetap unknown sesuai source
yang tidak diberi review baru; scope tidak diperluas demi menurunkan pending.

## Provenance dan waktu keputusan

Semua tambahan overlay memakai `ADJUDICATED_AI_PIXELS_REVIEW` dan
`NOT_NEWLY_ADJUDICATED_BY_USER`. Pengguna memberi keputusan fisik merah4843
dalam brief; pemetaan raw ID/frame tetap adjudikasi source oleh AI. Tidak ada
klaim anotasi manusia baru untuk setiap frame atau prediksi role otomatis.

**ASSUMPTION:** kontinuitas fisik di antara anchor review dibatasi scope
episode yang dinyatakan. Motion similarity, nama unit khusus atau kategori
sendiri tidak menjadi bukti identitas. Episode pesaing harus mempunyai bukti
positif yang tepat agar pengaman DISTINCT dapat dipakai.

Finalisasi pending mencatat actual decision EOF9127, waktu kandidat asli,
status/reason sebelumnya, positive source sample dan hash proof. Event geometry
tetap mencatat waktu kandidatnya; waktu tersedianya keputusan offline berada
pada `v8_decision_provenance`. Machine dan reviewed tidak dijumlahkan.

## Perbandingan yang wajib dipertahankan

Replay penuh pertama (`pilot_p1_reviewed_v1`) menyelesaikan pending menjadi1
tetapi masih menolak merah4843 karena pesaing4798 belum direview. Run ini tetap
tersimpan dengan72 accepted dan86 invalid, tanpa mengklaim target telah lolos.

Replay kedua (`pilot_p1_reviewed_v2`) menambahkan proof episode pesaing, lalu
menghasilkan73 accepted:72 kendaraan+1pedestrian,67 terukur,6 estimasi,
1pending dan85 invalid. Merah4843 benar-benar satu inferred; hitungan4798
tetap satu measured. Ini kandidat yang lolos kasus utama, sebelum recovery
tambahan1049→1123 diuji.

Fixture tiga track tidak mewakili semua konflik scene penuh. Fixture empat
track ditambahkan untuk melibatkan4798. Jumlah accepted fixture yang difilter
tidak disamakan dengan baseline video penuh karena komponen/aktor lain tidak
ikut dalam fixture. Source frames tetap berasal dari urutan asli mulai0;
tidak ada pengukuran gap yang dibuat.

Kandidat data development yang mencoba memberi proof pada nama unit raw
`track:4798` ditolak oleh guard lama: nama raw tracker bukan identitas fisik
positif. Kandidat terpilih mereview episode fisik utuh dengan unit reviewed,
tanpa memotong passage4798 di tengah crossing. Gate lama tidak diubah.

Kandidat handoff recovery dengan scope sampai1424 tidak dipilih. Bukti yang
dibutuhkan hanya sampai konfirmasi1396; penampilan/identitas setelahnya tidak
dipropagasikan sebagai label unit yang sama. Semua revisi data development
dan run sebelumnya tetap tersimpan.

## Hasil kandidat terpilih dan gate

**EXPERIMENT RESULT — PASS untuk pilot development reviewed satu video**, bukan
kelulusan otomatisasi produksi. Kandidat terpilih adalah
`pilot_p1_reviewed_v3`, policy/overlay `v5`. Replay memproses seluruh9.128 frame
cache yang sama dalam244,10 detik; tidak ada detector, tracker, ReID atau
enhancement baru. Notebook disediakan sebagai entrypoint; eksekusi aktual memakai
CLI yang tercatat pada indeks hasil.

| Ukuran | Baseline mesin B v7 | Kandidat P1 reviewed |
|---|---:|---:|
| Accepted objek |72|74|
| Kendaraan |72|73|
| Pedestrian |0|1|
| Terukur |66|67|
| Estimasi |6|7|
| Pending |24|1|
| Invalid kandidat |86|83|

Estimasi kandidat terdiri dari4 timeout dan3 line-margin inferred. Kategori:
70 motorcycle,2 car,1 truck,1 pedestrian; BUS0 pada hasil ini. A→B27 dan
B→A47. Nol kategori bukan bukti kategori itu tidak ada pada video.

**Rekonsiliasi24 pending:**21 person sebagai rider/passenger atau occupant
serta1 cargo selesai `resolved_not_eligible`, semuanya+0;1 person54 diterima
sebagai pedestrian terukur;1 person3185 tetap pending. Ini bukan22 kendaraan
yang berhasil ditemukan. Pending3185 pada5579 memerlukan bukti role/identitas
positif: label rider pada5394 tidak mengesahkan riwayat sampai5579. Tidak ada
pending baru yang tidak terpetakan.

**Pemulihan passage fisik:**1049→1123 menjadi satu motorcycle inferred,
dengan scope reviewed berakhir1396. Motorcycle merah4808→4843 menjadi satu
inferred dengan origin/destination bersih; perubahan ini mengganti event lama
yang mencampur biru/merah, sehingga tidak menambah agregat sendiri. Motorcycle
foreground4798 tetap satu measured. Biru yang muncul di tujuan tanpa crossing
baru menghasilkan0 accepted tambahan. Cargo3555 tetap+0, parent3563 tetap
satu measured; raw BC cargo/rider tidak menggantikan sumber crossing kendaraan.

Perbandingan event menghasilkan70 unchanged,2 changed,0 removed,2 added.
Dua changed adalah metadata unit4798 dan koreksi sumber4843; dua added adalah
pedestrian54 dan motor1049→1123. Tidak ada perubahan kategori/arah event lama
atau peningkatan inferred menjadi measured. Sebanyak17 ID tampilan bernomor
urut bergeser; gunakan mapping dan source proof, bukan kesamaan nomor tampilan.
Penurunan3 invalid adalah perubahan scope kandidat, bukan bukti3 passage pulih.

**Verifikasi:**302 tes software lulus, termasuk211 tes warisan B v5/v6/v7.
QC memeriksa1.043 referensi pengukuran dari998 frame cache serta13 kelompok
kontrol sumber. Relasi identitas dibandingkan berdasarkan endpoint pengukuran,
konteks fisik, support dan provenance; hash relasi yang berubah karena versi
policy bukan perubahan fisik otomatis. Pembanding yang awalnya terlalu ketat
tetap tersimpan, bersama koreksinya. Tes bukan ukuran accuracy.

Bukti source awal diperiksa terpisah dari implementasi. Review scope tambahan
4798/handoff dan QC hasil akhir dilakukan engineer AI utama; tidak diklaim
sebagai anotasi manusia baru atau audit akhir buta yang independen.

Artefak: [indeks paket](../results/b_v8/README.md),
[gate](../results/b_v8/review/p1_gate.json),
[rekonsiliasi pending](../results/b_v8/comparison/pilot_p1_reviewed_v3/pending_dispositions.csv),
[QC sumber](../results/b_v8/review/full_pilot_v3_qc.json),
[mapping tampilan](../results/b_v8/review/display_id_mappings.csv).

## Keputusan terbuka dan rekomendasi berikutnya

**FACT:** baseline mesin B v7 tidak berubah dan blocker identitasnya tidak
secara otomatis diperbaiki oleh review P1. Hasil74 bergantung pada overlay
review positif. Belum ada ground truth lengkap, audit semua passage terlewat,
validasi delapan video atau kondisi malam baru; zero mistakes belum terbukti.
Tidak ada annotated MP4 baru yang dirender pada tugas ini.

**PROPOSAL (Pareto):** dahulukan paket review source untuk pergantian episode
fisik dan komponen person;22 dari24 pending pilot selesai sebagai+0, sedangkan
pemulihan kendaraan memerlukan bukti identitas spesifik. Setelah menetapkan
benchmark passage berlabel dengan segmen development/hold-out, baru uji otomasi
role/identity pada konfigurasi tetap dan lintas video. Jangan menyetel threshold
supaya3185 atau satu pasangan ID tertentu lolos.

| SWOT rekomendasi otomasi berikutnya | Pertimbangan |
|---|---|
| Strength | Gate konservatif dan bukti per passage tersedia untuk regresi. |
| Weakness | Role/identitas positif saat ini masih memerlukan review terbatas. |
| Opportunity | Gunakan kasus terverifikasi sebagai benchmark otomasi dan audit false merge. |
| Threat | Propagasi role global atau handoff berbasis kemiripan saja dapat menambah hitungan palsu. |

Keputusan berikutnya adalah cakupan audit lintas video serta kriteria penerimaan
berlabel, bukan promosi B v8 menjadi default produksi. ReID tetap bagian
arsitektur; konfigurasi kendaraan final tetap terbuka.
