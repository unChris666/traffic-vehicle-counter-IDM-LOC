# Notebook18 — Gradio lintas perangkat, 0.7.3rc1

Gunakan `notebooks/active/18_colab_l4_gradio_remote.ipynb`. Notebook17 tetap memakai proxy Colab sebagai default; notebook18 khusus Gradio publik. Keduanya berbagi package engine yang sama.

## Menjalankan

1. Buka notebook18 di komputer host, pilih L4. Jalankan setup, runtime-check dan autentikasi Google seperti sebelumnya. Kredensial tetap berada di host Colab.
2. Jalankan cell persiapan binary tunnel: binary frpc diunduh sekali ke cache workspace dan checksum diverifikasi oleh Gradio yang versinya terkunci. Log tersimpan di share-setup.log. Tidak ada instalasi library saat job engine bekerja.
3. Jalankan cell server. UI_ACCESS sudah **gradio**; jangan menggantinya ke colab untuk akses perangkat lain.
4. Tunggu PUBLIC_ACCESS berstatus READY dan tulisan **LINK PUBLIK SIAP**. Pemeriksaan meliputi GET halaman UI, GET/config dan POST/remote-check dengan nonce; tidak menjalankan engine.
5. Buka link Buka aplikasi—gradio pada ponsel/laptop lain. Perangkat kedua tidak perlu login akun Colab host. Bagikan hanya kepada tester yang diizinkan: siapa pun pemegang link dapat mengoperasikan prototipe ini.
6. Lengkapi HOME, SAVE lokasi, pilih RWI, pratinjau seluruh input, konfirmasi, lalu Running. Submit/background/polling dari0.7.2 tetap; klik ulang saat aktif tidak membuat job kedua.
7. Jika timer browser tertahan, gunakan Perbarui status sekarang atau Hubungkan kembali pantauan job. Refresh perangkat tidak menjalankan ulang engine. Host harus mempertahankan runtime/cell server hidup; Stop/Interrupt atau runtime berakhir menutup URL dan dapat mematikan job.

## Jika link belum siap

- Server lokal READY belum cukup.502/403/timeout/redirect atau respons yang bukan aplikasi membuat status publik NOT_READY. Probe diulang pada putaran monitor berikutnya, tanpa restart atau menjalankan engine.
- Jangan klik Running ketika link publik belum siap. Tunggu beberapa putaran; jika tetap gagal, simpan ZIP diagnosis. remote-access-check.json dan share-setup.log ikut disertakan.
- Tidak ada pergantian otomatis ke proxy Colab karena akses tersebut dapat memerlukan login host dan tidak memenuhi tujuan lintas perangkat.
- Link sementara tunduk pada masa hidup tunnel/runtime. Notebook tidak menjamin uptime layanan Gradio/ISP/jaringan perangkat. Pemeriksaan dari host bukan bukti akses browser perangkat kedua.
- Untuk video besar, referensi GCS pada slot tersedia; keberhasilan probe kecil tidak membuktikan upload1GiB melalui jaringan seluler/tunnel.

## Cakupan validasi

- Regresi392tes:374lulus,18dilewati;4tes remote diulang setelah finalisasi cell notebook, semuanya lulus.
- Server Gradio HTTP lokal sungguhan: GET halaman, GET config, POST echo nonce lulus tanpa memanggil runtime engine.502 diuji agar tidak pernah menjadi READY.
- Notebook bersih/kompilabel dengan wheel yang identik sumber; mode share publik dipilih eksplisit. Build dan mypy contracts/config lulus.
- Percobaan tunnel publik dari environment pengembangan **gagal** saat pembentukan koneksi layanan Gradio (`login to server failed: session shutdown`). Binary sudah berhasil disiapkan di cache yang bisa ditulis pada percobaan kedua. Penyebab jaringan pastinya belum dibuktikan. Tidak mengklaim tunnel publik/lintas perangkat berhasil diuji.
- L4 fresh inference, browser Colab dan perangkat kedua masih perlu retest owner. Package engine/formula/RWI/GCS/BQ dan tata letak HOME/RESULT tetap; tidak ada promosi ke main/foundation atau klaim production-ready.
