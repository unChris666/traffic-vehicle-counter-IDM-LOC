# Prioritas stabilitas dan deployment — 27 Oktober 2026

FACT: owner menyatakan notebook Gate2 tidak mengalami error. API Kaggle melaporkan
RUNNING saat pemeriksaan; server Gradio yang menunggu tombol memang tetap berjalan.
Tidak ada alasan membatalkan sesi sehat atau mengganti repository untuk perbaikan ini.
Status RUNNING bukan bukti seluruh pipeline GPU telah dijalankan atau tidak akan gagal.

## 1. Stabilitas notebook sekarang: package 0.4.9rc1

- Dependency tes IPython 9.6.0 dinyatakan dalam extra `test`; CI memasangnya.
- CI juga dipicu ketika notebook11/14 atau builder terkait berubah.
- Lock Area menggunakan POSIX flock, bukan keberadaan marker. Filename tetap ada,
  tetapi OS melepas kepemilikan ketika proses mati. Jangan menghapus file lock.
  Jangan mencampur worker versi lama/baru pada output aktif yang sama; upgrade pada sesi baru.
- Per-job `resources-start.json` / `resources-finished.json` memuat disk free,
  peak RSS coordinator dan observasi memori GPU host dari nvidia-smi. Worker
  inference juga merekam observasinya dalam environment hasil. Sampel bukan
  benchmark kapasitas, peak VRAM, batas aman, atau atribusi GPU per proses.
  Perintah GPU hilang/timeout dan kegagalan menyimpan diagnostik tidak menggagalkan engine.
- Notebook11/14 menyematkan exact wheel dengan hash/source verification. Cell
  Gradio menutup server pada interrupt; tunggu pekerjaan selesai sebelum restart.
- Model, profil kandidat FP32, geometri, policy counting, Area, PPAC dan data
  historis dipertahankan. Tidak ada klaim akurasi atau jaminan bebas crash.

## 2. Pisahkan scheduling dan ukur kapasitas

PROPOSAL: measurement finalized di disk menjadi handoff dari antrean GPU ke
proses CPU. Lepas slot GPU setelah inferensi; counting/finalization/publication
berjalan pada CPU pool terbatas dengan antrean bounded. Pertahankan state tracker
berurutan per video dan riwayat offline counting. Jangan menghapus frame atau
mengubah aturan episode untuk mengurangi RAM.

Gate: uji satu/dua GPU nyata, failure isolation, urutan hasil, peak RSS/VRAM total,
disk maksimum, dan hasil domain terhadap input yang sama. Observasi tahap1 belum
menentukan jumlah worker/batas video yang aman. Parameter baru dipilih dari bukti.

## 3. Persistensi GCS/BQ

PROPOSAL yang mengikuti arah owner: integration application mengorkestrasi adapter
storage; domain engine tidak bergantung pada SDK cloud. Artefak besar GCS,
rekap/run/version/quality di BQ, view terikat versi sebagai feeder PPAC. Publikasikan
artefak dan verifikasi dahulu; tandai rekap READY hanya setelah seluruh referensi
utuh. Uji retry tanpa duplikasi dan reopen pada compute baru. Hindari mengubah
input atau receipt historis. IAM/provisioning dan akses live harus diverifikasi.

## 4. Container setelah alur stabil

Build dependency OS/Python dalam image, startup memvalidasi tanpa pip/apt. Pisahkan
model/cache/artefak dari image, inject identitas runtime dan konfigurasi. Kaggle
menguji package; menjalankan Docker dengan GPU memerlukan host/daemon/toolkit yang
mendukung, bukan diasumsikan tersedia pada hosted notebook. Dockerfile, dependency
lock lengkap, adapter ADC dan deployment GPU diuji setelah tahap2/3.

Gradio tetap UI sementara untuk uji pribadi. FE/BE produk dan repository baru
bukan prasyarat tahap1. Paket/notebook baru harus diperiksa sebelum dipakai;
sesi notebook aktif menggunakan kode yang sudah dimuat, bukan otomatis versi GitHub baru.
