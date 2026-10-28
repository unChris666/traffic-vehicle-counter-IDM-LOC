# Running tanpa callback panjang — kandidat0.7.2rc1

Gunakan `notebooks/active/17_colab_l4_phase123_user_testing.ipynb`. Pastikan setup memakai0.7.2rc1 dan buka URL server baru. Jangan menjalankan setup ulang ketika server/job lama masih aktif.

## Temuan dan cakupan

Versi sebelumnya menjalankan generator Gradio untuk seluruh durasi job. Callback tersebut mengirim status berkala dan baru selesai setelah engine serta publikasi selesai. Browser/tunnel harus mempertahankan jalur progres selama pekerjaan berlangsung. Log owner membuktikan HTTP lokal pernah READY sebelum Stop/SIGINT, tetapi tidak membuktikan browser, event stream, atau tunnel sehat. Freeze awal tidak berhasil direproduksi; mekanisme request panjang adalah titik rapuh yang diperbaiki, bukan root cause tunggal yang dinyatakan sudah terbukti.

Perubahan ini mengganti transport Running pada notebook17; rumus, dependency locks, RWI, map, counting/routing dan publikasi engine tetap.

## Alur baru

1. Running memakai POST singkat tanpa antrean generator Gradio. Input/review divalidasi dan Job ID lokal disiapkan; request mengembalikan status penerimaan, bukan menunggu komputasi.
2. Satu runner latar belakang melanjutkan engine dan publikasi. Koneksi browser/polling tidak mengendalikan masa hidup job. Seluruh input tetap berupa salinan yang dikonfirmasi.
3. Timer browser mengambil snapshot status lewat request singkat setiap2detik. Poll tidak menjalankan inference, routing atau query hasil GCS/BQ. Pembacaan hasil cloud akhir berlangsung di worker latar belakang dan hasil tampil melalui polling berikutnya.
4. Klik berulang/concurrent saat job aktif menghubungkan ke job yang sama. Satu job aktif per instance UI prototipe. Pemeriksaan runtime baru/retry publikasi ditahan selama job aktif agar tidak bersaing dengan pekerjaan yang sedang berjalan.
5. Refresh/tab terputus tidak otomatis menjalankan ulang engine. Halaman baru otomatis mencari job aktif pada instance server yang sama; **Hubungkan kembali pantauan job** tersedia untuk job aktif/terakhir. **Perbarui status sekarang** mengambil snapshot bila timer browser tertahan.
6. Job selesai/error disimpan dalam maksimum20snapshot UI dalam memori. Receipt/manifest disk/GCS tetap sumber hasil sebenarnya. Polling lama tidak boleh menampilkan job yang sudah diganti oleh job baru.
7. Diagnosis `server-observation.json.ui_poll_observation` merekam waktu polling terakhir yang diterima server. Ini bukan bukti browser berhasil menggambar tabel maupun engine maju. Handle mentah tidak ditulis ke diagnosis; hanya hash.

**Server notebook harus tetap hidup.** Stop cell menutup server/tunnel dan dapat menghentikan engine. Runner ini bukan persistent queue/service terpisah, tidak melanjutkan job setelah proses/runtime mati, dan tidak menjamin tab browser selalu aktif. Request singkat masih memerlukan jaringan/tunnel yang sehat.

## User testing

- Pilih L4 dan jalankan setup, runtime-check, autentikasi, lalu server. Isi RWI/input, SAVE lokasi, pratinjau/konfirmasi, klik Running sekali.
- Status penerimaan Job ID seharusnya segera kembali, diikuti update berkala. Angka tes lokal bukan jaminan latensi Colab/GCS.
- Saat engine aktif, klik Running lagi: Job ID harus sama, tidak ada job/inference kedua. Perubahan HOME tidak mengubah input job aktif.
- Buka tab baru/refresh, gunakan Hubungkan kembali pantauan job atau Perbarui status sekarang. Jangan Stop notebook hanya untuk refresh browser. Membuka kembali pantauan tidak memulai engine.
- Jika tetap freeze, catat apakah Running sempat mengembalikan Job ID, apakah tab baru/config dapat dibuka, dan apakah polling manual merespons. Ambil ZIP diagnosis; bandingkan waktu watchdog HTTP lokal dengan waktu polling UI. Ini membedakan request tak sampai ke server dari engine yang belum menghasilkan checkpoint baru.
- Jika runtime telah dimatikan, gunakan pembacaan job tersimpan GCS/BQ untuk memeriksa hasil yang benar-benar terbit. Snapshot input bukan bukti hasil komputasi selesai. Jangan menganggap reconnect dapat memulihkan proses yang sudah mati.

## Bukti lokal

- Tes menahan engine dengan synchronization event: submit/poll tetap kembali, lima klik concurrent menghasilkan satu job, hasil selesai tanpa browser polling, dan reconnect tidak memulai engine lagi.
- HTTP Gradio sungguhan, server loopback/POST JSON: submit0,023detik, klik ulang0,020detik, poll0,010detik, final poll0,011detik; satu panggilan engine uji. Respons `is_generating=false`. Engine memakai fixture yang sengaja ditahan, bukan inference GPU atau koneksi publik Colab.
- Regresi utama383tes:365lulus,18dilewati. GIS/peta11tes lulus terpisah. Build, installed-wheel import dan mypy contracts/config lulus.
- Tunnel publik, browser Colab, L4 inference dan CRUD cloud nyata menunggu owner testing. Tidak ada klaim bahwa seluruh penyebab freeze sudah hilang atau program production-ready.
