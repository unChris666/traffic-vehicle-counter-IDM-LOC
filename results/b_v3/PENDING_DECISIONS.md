# Pending Phase 8 B v3 — keputusan per keluarga kasus

**EXPERIMENT RESULT:** replay aktual `20261019T045405_106031Z` menyelesaikan delapan video/72.590 frame dari cache terverifikasi, tanpa menjalankan detector, tracker, atau ReID ulang. Hasilnya 3.500 passage operasional: 895 crossing terukur dan 2.605 inferensi, termasuk 2.454 timeout. Angka ini bukan jumlah kendaraan fisik yang telah diaudit atau klaim akurasi. [Audit independen](verification/final_delta_audit.json) mengikat hitungan, konfigurasi, dan sembilan source executable ke SHA aktual.

Ada **2.890 kunci pending unik** `(video, physical_unit_id, episode_id, passage_id)`: **2.427 unknown-person, 462 vehicle, dan 1 pedestrian dengan role positif**. Kunci software tersebut bukan jumlah orang/kendaraan fisik. Queue semua episode person yang belum diketahui perannya berisi 6.099 kunci; sebagian tidak mempunyai kandidat passage. Queue itu tidak boleh ditambahkan lagi ke 2.890.

## Enam keputusan, bukan ribuan baris CSV

Kolom *jumlah utama* menempatkan tiap kunci tepat sekali dengan prioritas tabel. Kolom *semua anggota* mempertahankan konflik ganda: dua kunci mempunyai masalah kategori sekaligus geometri, dan satu kunci mempunyai masalah kategori sekaligus identitas. Karena itu kolom anggota tidak dijumlahkan sebagai total pending.

| Keluarga kasus | Jumlah utama | Semua anggota | Contoh aktual dan keputusan yang dibutuhkan | Rekomendasi — PROPOSAL |
|---|---:|---:|---|---|
| Peran `person` belum diketahui | 2.427 | 2.427 | `weekday_pagi` raw30, kandidat frame93: kelas person saja tidak membuktikan pedestrian atau rider. | Rider yang didukung relasi komponen memberi +0; pedestrian memerlukan bukti role positif dan geometri sendiri. Unknown tetap di queue tersendiri. Tetapkan protokol role otomatis sebelum menganggap semua person mandiri sebagai pedestrian. |
| Timeout passage berikutnya tanpa bukti perjalanan baru | 210 | 210 | Truck4149 sudah mempunyai crossing A→B pada7422; timeout dugaan balik pada7509 ditahan. | Setelah satu passage, pergantian/jitter arah atau habisnya timer saja tidak membuat passage baru. Terima kembali ketika ada bukti passage baru; genuine return yang benar tetap boleh dihitung. **Kontrol riset ini menunggu pilihan pengguna.** |
| Identitas duplicate atau handoff belum terverifikasi | 201 | 201 | 185 duplicate dan16 handoff. Review73/93 pada221–224 belum menyelesaikan konflik73/77 pada143–147 dan73/87 pada169–180. | Sambung hanya episode yang didukung bukti; satu unit/satu passage memberi maksimal satu event. Jangan menggabungkan seluruh riwayat raw ID atau menghapus konflik pasangan lain. |
| Kategori temporal atau taxonomy | 34 | 35 | 29 kunci kategori konflik/tie;6 kunci taxonomy belum didukung, misalnya `weekend_siang` raw6 pada76. | Pertahankan prioritas kategori di pita dan tie pending. Pisahkan objek yang memakai ulang raw ID sebelum memilih kategori. **Pilihan menambah BUS/hurufB masih terbuka**; jangan menyamakan bus dengan angkot tanpa keputusan bisnis. |
| Bukti crossing tidak cukup | 17 | 19 | `weekday_sore` raw1030 pada2687 mempunyai konflik kategori sekaligus tidak ada bukti finite-line/occlusion yang valid. | Review trajectory dan frame sebelum/sesudah. Koreksi kategori atau identitas tidak membuat crossing hilang menjadi terukur. Jangan menerima event hanya karena bbox pernah berada dekat garis. |
| Jalur inferensi pedestrian belum disepakati | 1 | 1 | `weekday_pagi` pedestrian6 yang direview pada0/38/76 mempunyai kandidat timeout pada136; belum ada crossing terukur yang memenuhi aturan. | Sementara gunakan pedestrian crossing terukur saja. **Pengguna perlu memilih** apakah timeout/occlusion juga berlaku untuk pedestrian; jangan menyalin izin timeout kendaraan secara diam-diam. |
| **Total kunci unik** | **2.890** | **2.893 membership** | Tiga membership tambahan berasal dari konflik ganda, bukan tiga passage tambahan. | Pending tidak masuk subtotal accepted. |

## Hasil koreksi contoh pengguna

- **73/93:** pengukuran car raw93 pada221–224 memakai identitas reviewed yang sama dengan73. Unit tersebut tetap pending karena dua pasangan konflik lain di atas. Raw93 pada188–204 adalah truck lain; timeout truck itu tetap satu event `T2000`, kini pada264 setelah alias car dikeluarkan dari clock. Keputusan sama kendaraan pada221 tidak menyatukan truck terdahulu.
- **4149:** truck7175–7449 menghasilkan satu crossing terukur `T2013`, A→B pada7422. Motorcycle7611–7631 memakai episode terpisah, tanpa mewarisi timer/category truck, lalu menghasilkan `M2213` pada7691 melalui **estimasi timeout**. Pemisahan identitas benar secara struktur, tetapi passage motorcycle tersebut masih harus diaudit; ini bukan crossing yang terlihat. Dugaan truck kembali pada7509 tetap pending.
- **2471/2473/2507:** rider2471 pada4204–4254 memberi +0. Unit motorcycle reviewed2473/2507 mempertahankan **satu** event `M1068`, B→A pada4241, dengan crossing BC vehicle pada4231→4232. Raw-person2507 tidak menjadi BC motorcycle. Pengukuran vehicle2507 pada4277–4278 disambung sesuai review pengguna; dua bbox simultan yang tidak overlap pada4277 tetap menjadi risiko salah asosiasi yang perlu replay temporal. Hasil ini belum membuktikan resolver handoff otomatis.
- **Pedestrian:** raw3/6 mendapat role positif melalui review piksel AI yang dibatasi0–76; role tersebut bukan keputusan pengguna atau klasifikasi role otomatis. **Nol accepted pedestrian tidak berarti pedestrian tidak ada.**

## Mengapa total berubah dari B v2?

Rekonsiliasi ledger tepat: **3.717 −208 timeout berulang yang ditahan −10 event dengan identitas clique belum terverifikasi +1 estimasi motorcycle4149 yang kini terpisah =3.500**. Dari10 event identitas yang ditahan,4 memakai route `LINE_MARGIN` dan6 timeout;3 di antaranya mempunyai crossing terukur tetapi identitas unit belum cukup. Raw93 hanya berubah waktu keputusan284→264, tanpa perubahan jumlah. Semua selisih tersebut dapat dilacak; ini tidak membuktikan semua event yang ditahan salah secara fisik atau bahwa akurasi naik.

B v2 melaporkan242 kunci pending dengan scope lama. B v3 juga menampilkan unknown-person dan menahan timeout passage berikutnya. Karena denominator dan kontrol berubah, membandingkan242 dengan2.890 sebagai tingkat kegagalan yang sama tidak sah.

## Urutan tindakan yang disarankan

1. Konfirmasi tiga pilihan kebijakan yang masih terbuka: pedestrian terukur saja/semua route; BUS kategori tersendiri; dan bukti baru untuk timeout passage berikutnya. Konfigurasi konservatif yang dipakai eksperimen **bukan persetujuan pengguna tersirat**.
2. Mulai Phase9 dengan contoh di atas, lalu audit accepted timeout, identitas201, dan segmen kontinu yang juga dapat mengungkap kendaraan tanpa kandidat. Dua keluarga vehicle terbesar—return dan identitas—mencakup411 dari462 kunci vehicle; ini prioritas beban review, bukan janji persentase perbaikan.
3. Pertahankan snapshot B v2/B v3, catat perubahan per passage fisik dan regresi. Turunnya pending bukan kriteria keberhasilan tunggal; accepted yang salah, kendaraan terlewat, dan role yang salah harus ikut dicari.

Berkas per-video yang perlu direview ada pada [snapshot aktual](execution/final_20261019T045405_106031Z/): `pending_groups.json.gz`, `person_role_review_queue.json.gz`, `counting_result.json.gz`, dan `comparison_b_v2.json.gz`. Preview anotasi berada di [annotated_previews](review/annotated_previews/). Status render penuh Kaggle dan publikasi video harus mengikuti bukti delivery tersendiri; replay lokal ini tidak merender delapan video.

**Update delivery aktual:** delapan anotasi penuh sudah terbit di [GitHub](VIDEOS.md); [bukti Kaggle/local](verification/actual_kaggle_local_comparison.json) identik untuk seluruh ledger dan [verifikasi publikasi](publication/final_verification.json) cocok untuk semua aset. Daftar kelompok di atas tetap mengacu pada snapshot keputusan yang sama.
