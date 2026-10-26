# UI sementara Gradio untuk integration layer

Package **0.4.8rc1**, Gradio **5.49.1**. Frontend ada di `integration/gradio_app.py`; seluruh perhitungan tetap dilakukan oleh `KaggleRuntime`, engine Area/Traffic, validator dan PPAC. UI tidak menyimpan kredensial di browser.

[Notebook Kaggle versi7](https://www.kaggle.com/code/chrisbiran/gate2-t7sl-sorong-integration-quiz) memakai [notebook14](../notebooks/14_gate2_sorong_t7sl_gradio.ipynb). Notebook11 tetap tersedia sebagai alternatif kuis klasik. Source paket tertanam di wheel dengan checksum dan verifikasi file Python; tidak perlu clone repository privat dari Kaggle.

## Penggunaan

1. Buka notebook Kaggle, aktifkan Internet, GPU, dan Secret `LocatioIntelligent`.
2. Jalankan notebook. Setup memasang UI/runtime adapter; engine belum berjalan.
3. Cell terakhir memanggil `launch(share=True)` dan mencetak `GRADIO_PUBLIC_URL`.
4. Buka URL publik tersebut, isi kode/lokasi/tanggal analisis, pilih mode dan video T7SL.
5. Isi parameter bisnis untuk mode Gabungan + PPAC dan konfirmasi target.
6. Tekan Periksa kesiapan, lalu Mulai proses. Hasil engine, status PPAC, progres dan unduhan JSON tersedia di UI.

Notebook harus tetap berjalan agar URL dapat diakses. Hentikan cell terakhir untuk menutup server. URL mengikuti masa sesi notebook dan kebijakan tunnel Gradio; bukan alamat deployment permanen. Jika tunnel gagal dibuat, notebook menampilkan error dan tidak menjalankan engine secara otomatis.

## Cakupan

Mode Area, Traffic, atau gabungan + PPAC. Lokasi default Sorong dan delapan video terikat T7SL. Pengguna dapat memilih satu video untuk menguji Traffic; PPAC tetap menunggu slot wajib bila hanya sebagian video dipilih. UI belum menerima upload video bebas karena model/geometry/source validation masih mengikuti dataset yang dipin.

Input bisnis: profil jalan highway/mainstreet/street/substreet, hari/minggu, jam/hari, drive-thru, SWOT, faktor potongan Traffic dan parkir. Nilai1 berarti tanpa penyesuaian dan terlihat jelas di UI. Jam>15 tetap memerlukan sesi tambahan. Koefisien lookup dan sepeda tetap mengikuti MVPv2 yang telah disepakati.

Satu antrean UI membatasi eksekusi pipeline bersamaan dari pengunjung. Di dalam satu pekerjaan, penjadwal tetap menjalankan satu video per GPU. Tiap video mempunyai child process/tracker terpisah. Pilihan/input ditangkap saat tombol ditekan; mengedit form tidak mengubah pekerjaan yang sedang berjalan.

Ringkasan JSON yang disediakan UI tidak mengekspor objek sistem/credential atau membuka folder log backend sebagai unduhan. Progres dibaca dari file status kecil; array measurement besar tidak dikirim ke browser. Log setup dan worker terperinci tetap tersedia di notebook.

## Validasi dan batas

Enam tes UI mencakup validasi sebelum runtime, mode engine independen, subset video, aturan18jam, hasil gagal/PPAC terblokir, ekspor tanpa objek sistem, dan konstruksi Gradio tanpa engine/cloud. Server lokal mengembalikan HTTP200 dan antrean aktif. Suite paket selesai214tes,9dilewati pada lingkungan tanpa dependency UI; enam tes UI dijalankan terpisah dengan Gradio terpasang.

Ini bukan pengukuran akurasi baru. Kandidat Traffic masih mempunyai perbedaan identitas track terhadap baseline; benchmark duaGPU nyata dan hasil PPAC lokasi nyata belum diverifikasi melalui UI.
