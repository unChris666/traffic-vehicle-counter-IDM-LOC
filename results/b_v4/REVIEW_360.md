# Review 360° — perbaikan episode, eligibility, rider, dan audit B v4

Tanggal laporan: **20 Oktober 2026, Asia/Jakarta**.
Status: **implementasi dan pilot cache replay selesai; validasi fisik masih parsial**.

## Kesimpulan engineering

Empat perbaikan telah dibuat terpisah dari B v3: batas episode/origin/timer,
eligibility/deduplikasi passage, asosiasi rider berbatas, serta renderer/panel
audit. Pilot penuh 9.128 frame TGDI-WEEKDAY-SIANG selesai, dengan kontrol maksimum
residual dan branch review-assisted yang terpisah. Tidak ada inference detector,
tracker, ReID, atau enhancement baru. Source/model cache, geometri, dan review
lama tidak diubah. Ini belum bukti bahwa sistem dapat menghitung mandiri tanpa
kesalahan, dan belum validasi delapan video B v4 atau kondisi malam.

## Hasil yang benar-benar dieksekusi

| Varian pada input yang sama | Accepted | Terukur | Inferensi | Pending |
|---|---:|---:|---:|---:|
| B v3 tersimpan | 584 | 121 | 463 | 430 |
| B v4, kandidat median | 172 | 121 | 51 | 68 |
| B v4, kontrol maksimum | 172 | 121 | 51 | 87 |
| B v4 median + adjudikasi54 | 173 | 122 | 51 | 67 |

Machine tetap memuat review B v3 yang sudah ada; bukan eksperimen otonom tanpa
review dari nol. Branch adjudikasi54 menambahkan satu pedestrian berdasarkan
bukti Phase 9 dan cakupan terbatas; hasilnya tidak dijumlahkan dengan machine.

FAKTA EKSEKUSI: **121 pasangan raw ID/frame crossing terukur baseline seluruhnya
tetap ada, tanpa pasangan hilang atau tambahan pada machine**. Sebanyak 412
event inferensi baseline tidak lagi diterima. Itu perubahan keputusan software,
bukan 412 kendaraan palsu yang telah terbukti. Passage nyata yang hanya memiliki
bukti occlusion dapat ikut tertahan/terlewat; audit source masih diperlukan.

Inferensi machine sekarang terdiri dari 34 timeout dan 17 line-margin inferred;
label route LINE_MARGIN tidak otomatis berarti terukur. Subtotal kendaraan:
motorcycle 146, car 16, truck 10; arah A→B 78 dan B→A 94. Ini hasil operasional,
bukan jumlah traffic ground truth.

Kontrol median menghasilkan 19 pending lebih sedikit daripada maksimum, tetapi
total accepted sama. Kandidat median menerapkan 728 run asosiasi berbatas versus
646 pada maksimum. Jumlah run bukan jumlah rider fisik atau perbaikan role yang
sudah terbukti; median dapat menyembunyikan kontradiksi singkat.

Bukti: [ringkasan perbandingan](verification/comparison_summary.json),
[hasil/snapshot immutable yang dipertahankan](execution/retained_bytes_manifest.json).

## Review kasus prioritas

| Kasus | Hasil B v4 | Batas interpretasi |
|---|---|---|
|166/185 | Crossing motor185 tetap ada; event tambahan166 tidak ada.166 dipisahkan antara objek awal, rider185, dan fragmen kendaraan berikutnya. | Memperbaiki kegagalan yang ditargetkan pada pilot; tidak membuktikan semua pergantian ID selesai. ID tampilan185 sekarang M1004, bukan M1006 baseline. |
|20/218 | Exact-frame clique mengacu pada episode objek20 yang sedang diamati, bukan konteks awal yang sudah ditutup. Empat alignment lokal dicatat. | Clique adalah bukti asosiasi software sumber, bukan ground truth identitas fisik. Tidak diterapkan mundur ke frame sebelumnya. |
|856/857 | Timeout baru dari fragmen856 yang menjauhi garis tidak diterima.857 mendapat role rider 1082–1097 dan 1100–1113 pada kandidat median; 1161 tetap unknown. | Kandidat hubungan763/816/856 belum terverifikasi; jangan menyimpulkan kendaraan putih tidak pernah melintas atau jumlah fisiknya nol. |
|54 | Machine tetap pending role. Branch review-assisted memberi P1000/pedestrian+1 melalui pasangan BC 104→105, activation 112. | Adjudikasi AI dibatasi33–140; bukan klasifikasi otomatis pedestrian. Bbox bottom melonjak dan kaki tertutup overlay, sehingga waktu crossing kaki fisik belum terbukti langsung. |
|3025 | Tidak ada event baru; BC sumber di luar cakupan geometri saat ini. | Pedestrian positif tidak otomatis eligible. Tidak membuktikan tidak ada passage di luar cakupan kamera/ROI. |
|4149 | Crossing truck A→B 7422 tetap diterima; tidak ada timeout passage balik baru. | Pemisahan truck/motorcycle memakai review lama yang source-bound; bukan hasil ReID baru. |

## Review dari seluruh sisi sistem

| Sisi | Yang sudah kuat | Celah yang masih material |
|---|---|---|
| Tujuan produk | Hitungan mengikuti passage; rider+0, physical unit berbeda dari raw ID. | Belum ada bukti coverage/counting performance seluruh video; business taxonomy BUS/angkot tetap terbuka. |
| Episode/identitas | Origin/timer tidak diwariskan ke konteks baru; context split lokal tidak menutup unit yang masih diamati alias lain. | Identity raw-track yang belum direview tetap asumsi; tidak ada encoder kendaraan final atau appearance cache baru. |
| Eligibility/timer |60 frame sumber, reset saat origin terlihat, no post-EOF; pendekatan/gap/konflik eksplisit. |25 px dan 3 observasi adalah kontrol penelitian baru; berisiko menolak track pendek atau occlusion yang sebenarnya valid. |
| Geometri | Native640×480 dan BC kendaraan sumber dipertahankan; crossing terukur tidak memakai union/rider BC. | Jitter bbox, overlay, kaki cropped, dan generalisasi kamera/video lain tetap risiko. |
| Rider/pedestrian | Role dibatasi interval dan parent episode; UNKNOWN tidak diubah menjadi pedestrian. | Pedestrian dekat motor, rider berhenti, naik/turun motor, dan motor berdekatan memerlukan counterexample visual tambahan. |
| Audit/output | Semua raw ID terbaca, offline ID dibedakan dari activation, pivot/log/pending/clock/parent tersimpan. | Canvas/video lebih besar; label yang mudah dibaca tidak membuktikan hitungan benar. |
| Reproducibility | SHA video/cache/geometry/config, source snapshots, branch terpisah, retensi tervalidasi. | Eksekusi B v4 saat ini lokal dari cache Kaggle, belum run B v4 di Kaggle atau delapan sumber. |
| Biaya dan deployment | Replay counting pilot sekitar 29,74 detik; render+decode143,33 detik, tanpa inference model. | Ini biaya replay lokal, bukan latency end-to-end/GPU produksi. MP4 144,94 MB; belum benchmark memori/throughput deployment. |
| Fase pengembangan | Pilot Phase 9 menghasilkan perbaikan yang bisa diuji dan direview. | Audit Phase 9 keseluruhan, validasi malam, dan readiness produksi belum selesai; Phase 10–13 belum dijalankan. |

101 tes B v4 dan236 tes baseline lulus. Video1280×1160 dirender 9.128 frame,
didekode ulang 9.128 frame; raw link/pixel diverifikasi tiap frame dan pivot akhir
direkonsiliasi172 accepted/68 pending. Lima preview aktual disimpan; review visual
di laporan ini meninjau preview226,1089,127, bukan seluruh video secara manual.
82 berkas paket audit Phase 9 dan94 berkas retensi hasil B v4 lolos pemeriksaan SHA.

## Pending dan pekerjaan review berikutnya

Machine memiliki tiga kelompok pending unik pada snapshot ini:

| Kelompok | Jumlah | Keputusan yang dibutuhkan |
|---|---:|---|
| Role person belum positif |29| Rider/passenger+0; pedestrian hanya dengan bukti positif dan eligibility geometri; sisanya unknown.54 tersedia sebagai contoh adjudikasi. |
| Hubungan episode untuk timeout |31| Apakah episode pengganti benar kendaraan sama? Contoh raw228/decision336 belum diadjudikasi visual; jangan otomatis alias dari kedekatan bbox. |
| Konflik duplikasi dalam passage |8| Satu atau dua unit fisik? Contoh2549/2561 sekitar decision4129 perlu klip; jangan samakan overlap dengan satu kendaraan. |

31+29=60 dari68 pending merupakan prioritas Pareto pada **kandidat software ini**.
Masih ada866 unknown-person role keys di luar/di dalam kandidat;68 pending tidak
berarti hanya68objek fisik yang belum jelas.16 decision sebelumnya ditutup
`resolved_not_eligible`; penutupan itu bukan label negatif ground truth.
Kendaraan/orang yang tidak pernah menjadi kandidat harus dicari dari video
sumber, bukan hanya dari CSV pending.

[CSV kelompok dan kebutuhan bukti](review/pending_case_groups.csv).

## Keputusan berikutnya dan SWOT

| Keputusan | Strength | Weakness | Opportunity | Threat | Rekomendasi |
|---|---|---|---|---|---|
| Handoff: positif source-bound vs alias otomatis dari kedekatan | Aturan positif menjaga jejak dan membatasi salah gabung. |31 timeout masih pending; fragmentasi belum pulih otomatis. | Review pasangan membentuk kasus terverifikasi untuk menguji linker. | Alias agresif menggabungkan dua kendaraan berdekatan atau membuka duplicate passage. | Pertahankan hold konservatif; uji linker sebagai eksperimen terpisah setelah pasangan diadjudikasi. |
| Rider: median vs maksimum residual | Median menangani outlier;19 pending lebih sedikit di pilot tanpa mengubah total accepted. | Dapat menutupi perpindahan role/parent sesaat; belum validasi visual semua 728 run. | Replay contoh pedestrian dekat motor, rider berhenti, dan naik/turun. | Salah menetapkan pedestrian sebagai rider membuat passage hilang. | Median tetap kandidat development; maksimum tetap kontrol, jangan langsung default produksi. |
| Timeout: gate25 px/3 observasi vs pelonggaran | Mengurangi eligibility dari jitter/fragmen menjauh dan mempertahankan seluruh crossing terukur baseline. |412 inferensi tidak diterima lagi; sebagian mungkin passage nyata. | Audit sampel inferensi yang hilang menurut arah/kategori/occlusion sebelum tuning. | Memilih angka hanya demi pending/subtotal berisiko false count atau missed passage. | Bekukan sebagai profil eksperimen sekarang; putuskan threshold setelah review, jangan menambah timeout untuk konflik identitas. |

Keputusan readiness: **B v4 layak untuk audit development berikutnya, belum
layak ditetapkan sebagai penghitung produksi otomatis**. Pertahankan measured
dan estimated terpisah sesuai keputusan pengguna; tidak menghapus timeout 60
yang sudah disepakati atau menjadikannya bukti crossing terukur.

Urutan berikutnya: adjudikasi tiga kelompok pending dan sampel inferensi yang
tidak diterima → periksa passage yang tidak pernah menjadi kandidat → bekukan
profil terpilih → uji video/segmen hold-out siang dan malam tanpa tuning bersama
enhancement/deduplikasi → selesaikan audit sebelum refactor/deploy.

## Berkas dan batas publikasi

Kode: `phase_8_b_v4_identity.py`, `phase_8_b_v4_counting.py`,
`phase_8_b_v4_batch.py`, `phase_8_b_v4_annotation.py`, empat berkas tes, dan
`08d_episode_eligibility_role_replay.ipynb`, semuanya di `notebooks/`.
Konfigurasi/overlay/hasil ada di `results/b_v4/`; kontrak baru di
`docs/B_V4_EPISODE_ELIGIBILITY_CONTRACT.md`.

Video lokal: [anotasi penuh machine](videos/TGDI-WEEKDAY-SIANG-b-v4-machine.mp4).
MP4 melebihi batas blob GitHub 100 MB dan dikecualikan dari Git; video B v4 baru
belum dipublikasikan ke GitHub/Kaggle. Tidak ada video sumber yang dimasukkan
ke repository. Laporan dan preview dapat dibuka tanpa menjalankan model.
