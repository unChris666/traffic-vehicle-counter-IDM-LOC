# Area gagal vs peta gagal — 0.5.4rc1

Screenshot owner menunjukkan Traffic weekday/pagi berhasil dan PPAC BLOCKED
`REQUIRED_ENGINE_UNAVAILABLE`. Kode ini menyatakan ada engine/video wajib yang
gagal; tidak membuktikan penyebab kegagalan Area, maupun membuktikan bahwa semua
video lain berhasil. Belum ada log error Area dari sesi owner. Jangan menebak
root cause sebagai IAM, CUDA, dependency atau renderer tanpa bukti.

## Cacat yang diperbaiki

- Error detail worker tertutup oleh `ENGINE_JOB_FAILED`/`CalledProcessError`.
  Kegagalan Area kini meneruskan diagnosis worker, mencari error relevan pada log
  setup/preparation/worker sesuai waktu run dan menyimpan diagnosis ke receipt,
  ringkasan GCS serta alasan PPAC. Token/key disaring; pembacaan log dibatasi.
- Setup dependency Area sebelumnya berjalan di interpreter UI yang hidup lama.
  Sekarang setup berjalan dalam proses Python baru dan output pip/apt/native
  probe disimpan ke `area-setup.log`. Ini menghindari reuse modul scientific
  yang telah diimport sebelum setup; tidak membuktikan itu penyebab sesi owner.
- Renderer exception sebelumnya menggagalkan seluruh paket hasil Area meskipun
  perhitungan sudah selesai. Kini status render dipisah. Tabel display dibuat
  sebelum render; hasil numerik/quality tetap disimpan. HTML parsial dihapus,
  `presentation/error.json` menyatakan kegagalan. PPAC tidak memerlukan HTML,
  tetapi tetap wajib melewati gate kualitas dan kelengkapan input.
- Gradio menyediakan tombol **Periksa penyebab kegagalan Area (tanpa proses ulang)**.
  Pembukaan hasil GCS menampilkan status gagal Area atau renderer, jika informasi
  tersebut tersedia pada job baru. Job lama yang tidak menyimpan log tidak bisa
  dipulihkan penyebab pastinya hanya dari screenshot.

## Langkah owner

1. Buka notebook versi terbaru, aktifkan Internet/GPU dan Secret
   `LocatioIntelligent`. Gunakan URL Gradio dari sesi baru.
2. Pada workspace/sesi yang gagal, klik tombol diagnosis Area dan salin hasilnya.
   Tombol hanya membaca log; tidak menjalankan Traffic atau Area.
3. Bila sesi lama/log sudah hilang, pilih **Area Coverage** dan jalankan Area
   sendiri pada target/koordinat yang benar. Tidak perlu mengunggah atau
   menjalankan ulang Traffic untuk diagnosis ini. Hasil Area baru dipublikasikan
   sebagai job tersendiri; tidak otomatis menggabungkannya dengan job Traffic lama.
4. Jika Area berhasil, tabel dan HTML tersedia dari artefak GCS. Jika hanya render
   gagal, tabel numerik tetap ada dan status menyebut error renderer. Jika
   perhitungan gagal, kirim teks diagnosis yang baru agar akar masalah yang
   spesifik dapat diperbaiki; tidak diisi dengan nilai0 atau peta contoh.
5. PPAC tetap memerlukan Area valid dan seluruh slot video yang diwajibkan.
   Traffic satu sesi tidak mencukupi PPAC delapan sesi normal. Jangan menafsirkan
   hasil Area-only (PPAC NOT_RUN) sebagai PPAC gabungan yang lengkap.

## Validasi dan batas

274tes lokal:264lulus,10dilewati; mypy14file lulus. Pengujian mencakup pemunculan
error interpreter child, pemisahan log lama vs run baru, redaksi token, setup
Area terisolasi dan pemeliharaan tabel/numerik saat renderer sengaja gagal.
Render ulang hasil Area tersimpan berhasil dengan22bangunan dan HTML35MB,
tanpa perhitungan GPU baru. Itu bukti jalur presentasi fixture lama, bukan bukti
fresh Area Sorong pada sesi owner berhasil. Root cause sesi owner masih menunggu
log; akses secret/GCP dan fresh compute pada sesi itu belum dapat diverifikasi.
