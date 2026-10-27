# Kebijakan main dan pengembangan

Arahan owner,27Oktober2026: **main untuk versi paling stabil yang telah
diverifikasi; pengembangan dilakukan pada branch lain**. Ini target tata kelola,
bukan klaim bahwa isi main saat ini sudah production-ready.

## Alur kerja

1. Gunakan `refactor/deployment-foundation` untuk konsolidasi sementara dari
   `e077672`. Jangan memindahkan package atau mengganti perhitungan pada P0.
2. Pekerjaan berikutnya memakai branch pendek seperti `fix/area-runtime-...`,
   `feat/backend-...`, atau `chore/deploy-...`, dengan PR ke branch konsolidasi
   selama kandidat belum dipromosikan. Perubahan tetap harus mendapat tes relevan.
3. Kandidat ke `main` menggunakan PR. Jelaskan hasil sebelum/sesudah, bukti,
   batas validasi, dan risiko. Draft dipakai selama gate belum terpenuhi.
4. Jalankan CI pada **SHA terbaru**, periksa keseluruhan delta terhadap main,
   dan selesaikan kegagalan fungsi inti sebelum promosi. CI hijau saja tidak
   cukup untuk kegagalan Area/cloud yang hanya bisa diperiksa pada runtime nyata.
5. Setelah lolos, merge melalui GitHub tanpa force-push main. Tandai checkpoint
   yang benar-benar diterima dengan tag rilis dan catatan batas dukungan.
6. Setelah promosi, buat branch berikutnya dari main terbaru. Branch konsolidasi
   tidak menjadi branch paralel permanen. Penghapusan branch lama adalah tindakan
   tersendiri setelah pemeriksaan ulang ancestry; belum dilakukan pada P0.

PR#2 dari `fix/kaggle-runtime-stability` adalah jalur review sebelumnya.
PR foundation menjadi jalur konsolidasi baru yang mencakup delta tersebut.
Jangan merge kedua PR secara independen tanpa memperbarui base/delta.
PR lama tidak ditutup otomatis pada P0 agar diskusi dan bukti tetap mudah dilacak.

## Gate merge ke main

- Working tree bersih, history lengkap, main terbaru merupakan leluhur kandidat,
  tidak ada perubahan unik lama yang belum direkonsiliasi.
- Unit/integration software, strict mypy, build dan wheel smoke lulus. Source
  notebook11/14 harus cocok package aktif; skip dicatat beserta batasnya.
- Jalur yang berubah dan berisiko diuji di runtime sasaran. Untuk kandidat ini:
  Area selesai dan peta dapat ditampilkan, hasil job dibaca kembali dari GCS/BQ,
  serta Traffic/PPAC menunjukkan status yang benar untuk input lengkap/kurang.
  Identitas job, input, package, log dan receipt dicatat tanpa kredensial.
- Tidak ada regresi fungsi inti yang belum dijelaskan; BLOCKED karena input
  memang kurang dibedakan dari kegagalan runtime yang belum diketahui.
- Dokumentasi versi/status cocok dan ada langkah pemulihan. Memakai main/image
  sebelumnya hanya untuk kode/runtime; jangan menimpa artefak job atau memaksa
  rollback skema BQ yang aditif.

Kriteria stabilitas aplikasi Kaggle dan kesiapan produksi adalah dua milestone.
Docker/GPU VM/Cloud Run, job durable dan kapasitas produksi memerlukan validasi
tambahan; merge aplikasi Kaggle tidak boleh diklaim sebagai deployment siap.

Workflow CI berjalan pada setiap push/PR (tanpa filter path) serta dapat
dijalankan manual. Dengan demikian perubahan dokumentasi atau file baru tidak
melewati pemeriksaan yang nantinya diwajibkan untuk main.

## Proteksi GitHub yang perlu diberlakukan

Konfigurasi yang dituju pada **Settings → Rules → Rulesets**, target branch main:

- Require a pull request before merging; untuk repo solo, atur reviewer sesuai
  orang yang tersedia agar tidak menciptakan kewajiban self-approval yang mustahil.
- Require status checks: job **`boundaries`** dari workflow
  **Traffic migration contracts and parity gates**. Pilih check yang benar dari
  daftar hasil GitHub; require branch up to date sebelum merge.
- Block force pushes dan deletions; batasi bypass seminimal mungkin.
- Aktifkan ruleset dan periksa efektivitas sesuai paket/visibility repository.

**Status enforcement belum terverifikasi.** Pembacaan endpoint branch protection
main oleh identitas sesi ini mendapat HTTP403 `Resource not accessible by integration`.
403 tidak membuktikan proteksi tidak ada. Tidak ada aturan GitHub yang diubah,
dan instruksi dokumen/CI bukan pengganti proteksi server. Owner/admin perlu
memeriksa atau menerapkan pengaturan di GitHub bila akses sesi tetap terbatas.
