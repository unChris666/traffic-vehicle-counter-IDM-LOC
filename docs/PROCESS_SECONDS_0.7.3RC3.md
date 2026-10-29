# Processing seconds — 0.7.3rc3

Notebook18 tetap menampilkan detik selama proses, dengan polling tiap2detik:

- **Waktu total job**: dihitung dengan jam monotonic sejak job diterima, terus bertambah saat aktif, berhenti pada durasi akhir saat selesai.
- **Polling UI terakhir**: waktu respons polling server; membantu melihat apakah jalur pemantauan masih merespons.
- **Umur snapshot pemantauan**: waktu sejak pembaruan terakhir dari runner. Bertambah jika runner tidak menghasilkan pembaruan, meskipun polling UI tetap berjalan.
- **Durasi tahap dan umur checkpoint engine**: tetap ditampilkan pada rincian sebelumnya. Catatan yang tidak memiliki timestamp memakai waktu modifikasi file sebagai fallback, sehingga umur catatan tidak selalu nol.

Polling tetap memperbarui baris penghitung ketika revision snapshot belum berubah. Ini tidak membuat job baru, tidak menjalankan engine dari endpoint polling, dan tidak menambah koneksi streaming panjang. Snapshot engine yang lama tetap diberi konteks umur snapshot; detik/polling bergerak bukan bukti algoritme maju. Jika polling juga terhenti, tampilan browser dapat berhenti memperbarui detik; periksa HTTP/tunnel atau gunakan polling manual. Tidak menjanjikan pembaruan setiap detik pada jaringan/perangkat yang tertahan.

Engine gagal tetap memiliki status/reason. Durasi akhir tidak terus bertambah setelah runner selesai. Rumus, tabel Kontribusi, GPU scheduler dan penyimpanan tidak diubah.
