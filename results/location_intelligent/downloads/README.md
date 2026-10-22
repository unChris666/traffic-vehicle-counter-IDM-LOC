# LI-4 — unduhan paket offline

Unduh **li4-n1-offline-review-v1.zip**, ekstrak seluruh folder, lalu buka
`review.html` di browser. Jika GitHub menampilkan halaman berkas ZIP, klik
**Download raw**. GitHub tidak mengeksekusi HTML di halaman source code.

Paket berisi data/snapshot/ekspor/manifest/verifier lengkap; HTML tidak
memerlukan Python atau internet. Hasil analisis tetap PARTIAL dan bukan
validasi akses lapangan atau populasi.

SHA256: `ebab01a49cfbb5f22ed32463abde90fcb7578644f19e28aca2cd8efbe335915f`.

Kode dan hasil: commit 53c7982. ZIP ditempatkan di repo karena API
uploads.github.com menolak unggah Release asset dengan HTTP401 pada kredensial
saat publikasi; push ke repo/API GitHub biasa berhasil. Tidak mengubah token
atau meminta kredensial baru.
