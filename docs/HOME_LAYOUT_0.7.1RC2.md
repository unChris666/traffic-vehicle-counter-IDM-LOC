# HOME baru — kandidat0.7.1rc2

Notebook: `notebooks/active/17_colab_l4_phase123_user_testing.ipynb`.
Gunakan runtime L4 baru, setup dan autentikasi, kemudian URL Gradio baru.

## Susunan HOME

1. **Pilih Mode**: Area Coverage / Traffic Counter / PPAC.
2. **PPAC**: identity, profil jalan, hari/jam operasional, faktor bisnis dan RWI.
3. **Area Coverage**: dua kolom. Kiri berisi Latitude, Longitude dan SAVE; kanan peta Esri/Leaflet penuh dengan pin calon toko. Peta awal dimuat saat halaman dibuka. SAVE hanya memvalidasi/menyimpan draft koordinat dan memperbarui peta; tidak membutuhkan video, nama toko atau RWI. Draft lokal bersifat sementara, input persisten masuk snapshot GCS saat Running diterima.
4. **Traffic Counter**: sumber video, accordion **Menu upload** dan **Menu edit geometri**, masing-masing dapat dibuka/ditutup dan awalnya tertutup. Review geometri tetap wajib untuk video yang akan diproses.
5. **Running**: pratinjau seluruh input, konfirmasi, Save Project, pemeriksaan kesiapan, tombol **Running**, status/progres. Konfirmasi seluruh input berbeda dari SAVE koordinat; SAVE bukan persetujuan menghitung job.

Perubahan koordinat menandai peta belum tersimpan dan membersihkan preview; perubahan parameter/video lain membatalkan konfirmasi job tanpa menghapus peta lokasi. SAVE/pemuatan peta memakai callback tanpa antrean engine. Itu tidak menjamin tetap bisa dipakai ketika server HTTP/tunnel/browser sendiri tidak merespons.

Grid PPAC, rumus okupansi/RWI, minimum lantai, status UNVERIFIED dan penyimpanan hasil tetap mengikuti0.7.1rc1. Routing/Huff/counting tidak diubah. Map preview memerlukan CDN Leaflet dan Esri pada jaringan browser; engine tidak dijalankan oleh SAVE.

## Temuan ZIP colab-diagnostics(2)

Waktu berikut memakai WIB/UTC+7 pada28Oktober2026:

- Job Area dimulai sekitar16:17:15. Input snapshot GCS berhasil disimpan.
- Persiapan snapshot BQ dimulai sekitar16:17:19.
- Watchdog terakhir16:17:23 melaporkan HTTP lokal200 dan nol kegagalan probe.
- Sekitar16:17:27, subprocess prepare-area dihentikan oleh **SIGINT**. Snapshot BQ baru berjalan sekitar7,7detik sebelum interupsi; Area belum sampai komputasi/peta.
- Server.log mencatat Keyboard interruption lalu penutupan tunnel. Status server pada diagnosis16:17:47 sudah STOPPED, proses tidak hidup.
- Tidak ada bukti dependency conflict, OOM, error query BQ spesifik, atau deadlock HTTP lokal sebelum interupsi pada ZIP ini. HTTP200 tidak membuktikan event stream/browser/tunnel sehat. Root cause freeze sebelum Stop belum terbukti; jangan menafsirkan SIGINT sebagai penyebab freeze awal.
- Pada saat penghentian metadata publikasi masih RUNNING. Itu bukan bukti hasil lengkap sudah terbit. Snapshot input yang tersimpan tidak sama dengan manifest hasil selesai.

Kategori SIGINT/SIGTERM kini **INTERRUPTED**, bukan COMPUTATION_ERROR. Ini memperbaiki diagnosis atas interupsi; bukan klaim bahwa freeze awal sudah diperbaiki.

## User testing

1. Pilih mode Area Coverage. Isi identity/RWI. Masukkan koordinat, tekan SAVE dan pastikan pin sesuai.
2. Pastikan SAVE juga dapat menampilkan peta sebelum video/RWI lengkap, tanpa memulai engine.
3. Buka/tutup Menu upload dan Menu edit geometri. Untuk Area-only, tidak perlu mengunggah video.
4. Tekan pratinjau seluruh input, konfirmasi, lalu Running sekali. Biarkan cell server berjalan; pantau tahap dan waktu checkpoint, bukan hanya animasi tombol.
5. Jika tampilan tidak bergerak, coba URL yang sama pada tab baru dan endpoint `/config`. Catat apakah halaman dan config dapat dibuka, waktu awal gejala, serta tahap terakhir.
6. Ambil diagnosis dari UI jika masih dapat dipakai. Jika UI tidak bisa diakses, watchdog menyimpan bukti hanya saat HTTP lokal gagal; beri kesempatan sekitar40detik bila runtime masih aman, lalu Stop sekali dan unduh diagnosis melalui notebook. Jangan memulai job kedua saat status job pertama belum jelas.
7. Setelah Stop atau runtime dihapus, URL lama tidak aktif. Runtime baru membutuhkan startup/autentikasi kembali. Tidak ada resume otomatis; periksa hasil job tersimpan sebelum mengulang perhitungan.

Validasi lokal meliputi unit/regresi, Folium/GIS, callback SAVE dan wiring layout. Perilaku browser Colab/tunnel serta akses cloud nyata tetap menunggu owner testing.
