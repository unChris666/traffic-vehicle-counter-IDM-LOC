# HOME / RESULT — 0.6.0rc1

Keputusan teknis untuk tahap Kaggle: tetap Gradio, dengan dua tab HOME dan RESULT.
Untuk aplikasi cloud multiuser direkomendasikan frontend React/Next.js + FastAPI,
upload resumable langsung ke GCS, job asynchronous dan log/progress per job.
Mengganti framework UI sendiri tidak memperbaiki koneksi upload yang terputus.
Docker tidak diubah pada pekerjaan ini.

HOME: Identity (Periode tanggal pembuatan today Asia/Jakarta, KDTK4karakter,
Nama Toko), input Area (latitude/longitude), input Traffic (8slot utama serta
geometri per-video), Action (Save Project, Process, pilihan mode dan parameter
PPAC dalam accordion). Periode menggunakan date picker tanpa waktu dan tidak
bisa diedit pada pembuatan project. Mode Traffic tetap menerima subset slot.

Save Project membuat snapshot metadata/parameter/geometri di
`gs://aretfak-location-intelligence/projects/<KDTK>/<periode>/<uuid>.json` dengan
create-only. Ini bukan penyimpanan otomatis file video browser, bukan database
proyek penuh dan belum menyediakan load/edit project. Status UI menjelaskan
batasnya; draft lokal tersedia jika publikasi metadata gagal. Input video GCS
atau Kaggle Input tetap harus dapat diakses pada sesi pemrosesan.

RESULT: identity job tersimpan dari BQ/context GCS (nama lama tidak dikarang),
status/progress/log engine, peta dan tabel Area, kompetitor/Indomaret/POI,
Traffic, annotated video8baris×2kolom, lalu grid PPAC. Identity hasil tidak
mengikuti perubahan form HOME setelah job lama dibuka.

Annotated video menggunakan renderer audit yang sudah ada, membaca video asli,
measurement dan native counting terikat SHA. Tidak menjalankan inference atau
counting lagi. Checkbox pada Action mengaktifkan tahap CPU ini. MP4 dan receipt
render disimpan ke GCS `jobs/.../annotations/<video_id>/`. Metadata URI/hash masuk
manifest job; loader hanya mengaktifkan link yang cocok manifest. Nama video
mengikuti sumber, bukan URL video asli yang dilabel ulang sebagai annotated.
Link membuka object Cloud Console, sehingga memerlukan login/hak baca GCS;
bucket tidak dibuat public. Jika renderer gagal, counts/hasil engine tetap
dipublikasikan dan error annotated muncul pada status hasil. Hasil lama yang
belum mempunyai annotated menampilkan tombol nonaktif.

Renderer tetap mempunyai batas aslinya: H264 dimensi output genap, frame/pixel
binding penuh, audio tidak dipertahankan, output CFR menurut reported FPS
(bukan original VFR PTS). Receipt mempertahankan cakupan dan checksums. Performa
RAM/disk/CPU dan rendering8video nyata belum dibenchmark. Tahap ini menambah
waktu CPU; bukan jaminan kapasitas produksi.

PPAC final tetap memerlukan Area valid dan seluruh sesi yang diwajibkan, termasuk
shift3 bila jam>15, serta durasi300–306detik per sampel. Sesi hilang tidak
digantikan nol. Estimasi STD parsial membutuhkan aturan/label tersendiri dan
belum diaktifkan. Log proses menggunakan status/progress per engine dan tombol
pembaca log Area/Traffic; path log relatif workspace membantu mengidentifikasi
run/stage. Diagnosis dependency/source/GPU yang spesifik tetap harus berasal
dari log, bukan dugaan pada UI.

Validasi:279tes lokal (269lulus,10dilewati), mypy14file lulus. Tes meliputi dua
tab, delapan baris video, KDTK/name, snapshot metadata tanpa execute engine,
link annotated yang tidak dikarang, kegagalan annotated terisolasi dan publikasi
MP4/receipt melalui renderer mock. Tidak mengklaim render8video/codec live,
save project live GCS, pemulihan project lintas sesi atau deployment cloud lulus.
