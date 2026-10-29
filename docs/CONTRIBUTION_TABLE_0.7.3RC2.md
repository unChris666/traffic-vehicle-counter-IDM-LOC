# Tabel Kontribusi — 0.7.3rc2

Notebook aktif: `notebooks/active/18_colab_l4_gradio_remote.ipynb`.

Tabel hasil PPAC diganti menjadi **Kontribusi**, dua kolom **Source | Kontribusi**, dengan tiga baris Traffic, Area, total. Angka30/30/60 dari permintaan owner adalah contoh tampilan, bukan nilai tetap.

- Satuan: STD/hari.
- Area = STD Residential + STD Fasum; tidak mengubah rumus/populasi engine.
- Traffic untuk hasil gabungan memakai `total.std_traffic_including_fasum − std_fasum + std_drive_thru`. Ini mempertahankan potongan, parkir dan drive-thru serta memindahkan Fasum ke Area tanpa menghitungnya dua kali. Pada hasil komponen tanpa agregasi gabungan, gunakan `traffic.std_traffic_raw` dan pertahankan status parsial.
- total berasal dari `std_total` tersimpan, tidak dihitung ulang atau diisi dari data contoh. Jika belum lengkap/BLOCKED, total tetap null. Komponen yang tidak tersedia juga tidak diubah menjadi nol.
- Status/diagnosis tetap ada pada status proses dan status hasil BQ; bukan baris tambahan dalam tabel Kontribusi.
- Hasil lokal saat publikasi gagal dan hasil yang dibuka dari ppac.json GCS menggunakan pemetaan tabel yang sama.
- HOME, transport publik notebook18, background job/polling dan algoritme engine tidak diubah. Keterbatasan tunnel publik dari0.7.3rc1 tetap berlaku.
