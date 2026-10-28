# Diagnosis Gradio freeze — kandidat 0.7.0rc2

Gunakan notebook `notebooks/active/17_colab_l4_phase123_user_testing.ipynb` versi0.7.0rc2. Ini kandidat perbaikan keterlacakan dan progres; penyebab freeze awal belum dapat direproduksi atau dibuktikan dari ZIP owner.

## Bukti dari ZIP owner

- Runtime NVIDIA L4, import/dependency dan CUDA smoke berhasil. `server.log` memuat `No broken requirements found.` Tidak ada bukti dependency conflict atau OOM dalam ZIP ini.
- Job `job_84201312253e4dc7bf3e85120b84a0e3`, mode workflow/PPAC, dua video terpilih.
- Area dan peta berstatus SUCCEEDED pada06:41:41UTC. Komputasi/presentasi86,762detik; persiapan sumber sekitar80detik. Ini tidak membuktikan seluruh job/Traffic/PPAC berhasil.
- Sesudah Area sukses, server mencatat `Keyboard interruption in main thread... closing server.` dan penutupan tunnel. Owner menegaskan freeze terjadi **sebelum** Stop/Interrupt: interrupt bukan penjelasan freeze awal.
- Dua video kemudian FAILED. ZIP lama tidak memuat receipt/error Traffic; tidak cukup bukti untuk menentukan apakah itu kegagalan asli atau efek penghentian worker.
- Sampel HTTP terakhir06:41:15UTC, lebih tua daripada Area selesai dan penutupan server. Itu observasi historis, bukan kondisi saat ZIP dibuat06:42:03UTC.
- Saat diagnosis dibuat, metadata publikasi masih RUNNING selama sekitar15detik; belum membuktikan publikasi macet atau hasil tersimpan lengkap.

Kemungkinan yang masih terbuka: perpindahan ke persiapan Traffic tanpa detail progres, stream/tunnel/browser tertahan, atau server/worker tertahan. Jangan menyebut salah satunya sebagai root cause tanpa bukti baru. Kelengkapan dua dari delapan sesi memengaruhi STD total, bukan alasan server harus freeze.

## Perubahan

1. Status lifecycle STARTING/SERVING/STOPPING/STOPPED ditulis oleh proses server sendiri. Diagnosis melakukan probe HTTP/proses baru; sampel monitor lama tetap tersimpan dengan label historis.
2. Watchdog thread memeriksa HTTP127.0.0.1/config tiap15detik di luar antrean Gradio. Dua kegagalan beruntun menyimpan stack seluruh thread ke `server-stacks.log` tanpa variabel lokal. Tidak melakukan restart otomatis atau menjalankan ulang job.
3. Diagnosis notebook melakukan probe URL publik Gradio/config terpisah, timeout5detik, tanpa redirect. HTTP200/config yang valid tidak membuktikan event streaming, browser, atau engine sehat.
4. Tahap Traffic diperinci: validasi runtime, persiapan model, pemeriksaan GPU, pemrosesan video. Shared preparation failures diberi checkpoint dan pesan error pada server.log.
5. Receipt Area/Traffic yang sudah selesai terlihat selama job lain masih berjalan; hanya milik Job ID saat ini. Grid hasil tersimpan tetap menunggu publikasi, tanpa memakai hasil job lama.
6. ZIP diagnosis memuat receipt/error engine, status persiapan Traffic, lifecycle/watchdog, stack jika ada, dan pemeriksaan HTTP baru. Jalur diagnosis juga bekerja untuk Traffic-only tanpa jejak Area. Collector tidak lagi melabel dirinya sebagai kegagalan komputasi.

Tidak ada perubahan dependency lock, rumus PPAC, kernel Area, counting, atau scheduler satu video per GPU. Ini tidak menyelesaikan pemisahan antrean GPU/CPU atau pemulihan job dari runtime mati.

## Cara memakai dan menguji

1. Simpan ZIP lama. Gunakan notebook17 versi0.7.0rc2 pada runtime baru; jalankan setup, runtime-check dan autentikasi. Jangan menimpa environment sewaktu server/job masih aktif.
2. Jalankan cell server, buka **URL baru**, lalu coba Area saja terlebih dahulu. Ulangi PPAC dengan video yang sama untuk mengamati transisi ke Traffic. Dua video boleh dihitung; STD total tetap belum lengkap.
3. Selama memakai UI, biarkan cell server berjalan. Receipt Area sukses kini dapat terlihat saat Traffic masih dipersiapkan. Jangan memulai job kedua saat job pertama belum jelas statusnya.
4. Jika browser terlihat freeze, coba buka URL yang sama pada tab baru. Bila masih bisa, ambil ZIP melalui tombol diagnosis. Catat waktu mulai freeze serta apakah tab baru dan URL/config dapat dibuka. Jangan menganggap HTTP200 membuktikan seluruh UI sehat.
5. Jika UI tetap tidak merespons, tunggu setidaknya40detik untuk memberi watchdog kesempatan mencatat kegagalan HTTP, kemudian Stop server satu kali dan jalankan cell unduh diagnosis. Watchdog hanya menangkap stack bila HTTP lokal ikut macet; jika lokal tetap READY, belum ada bukti deadlock HTTP dan stack mungkin tidak dibuat.
6. Pada ZIP periksa `server-observation.json` dan waktu observasinya, `server-watchdog.json`, `server-lifecycle.json`, `server-stacks.log` bila tersedia, serta `area-report.json.current_engine_receipts` dan `traffic_preparation_status`.
7. Setelah Stop, URL sesi lama tidak aktif. Jalankan kembali cell server untuk URL baru. Itu bukan resume otomatis; periksa publikasi/job tersimpan sebelum mengulang perhitungan.

Tanda lulus: tahap transisi terlihat, Area selesai tidak tampak sebagai Area masih bekerja, error Traffic memiliki kode/bukti, server yang berhenti tidak ditampilkan sebagai HTTP sehat saat ini, dan hasil/error tidak tertukar dengan job sebelumnya. Freeze Colab/tunnel nyata tetap menunggu retest owner; tidak ada klaim bahwa root cause freeze awal sudah diperbaiki.
