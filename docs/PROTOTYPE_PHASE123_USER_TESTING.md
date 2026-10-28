# Kandidat Fase 1–3 — 0.7.0rc1

Status: siap untuk user testing, belum diterima sebagai stable/production. Gunakan
`notebooks/active/17_colab_l4_phase123_user_testing.ipynb`. Notebook 15 dan 16
mempertahankan pilihan alur sebelumnya; konfirmasi input Fase 1 diaktifkan oleh notebook 17.
Main dan refactor/deployment-foundation belum dipromosikan.

## Keputusan dan cakupan

- Sumber nasional dianggap valid sebagai asumsi kerja. Tidak ada fase audit/verifikasi cakupan nasional.
- Snapshot persisten per job di GCS; BQ tetap rekap dan referensi artefak. File lokal hanya staging sementara untuk komputasi/publikasi.
- Pengujian lintas karakter wilayah berjalan bersama user testing, bukan prasyarat tersendiri.
- Routing, Huff, klasifikasi/counting Traffic, faktor PPAC dan policy bangunan alokasi + UNVERIFIED tidak diubah.
- Status COMPLETE untuk kelengkapan input tidak berarti data terverifikasi. Kualitas UNVERIFIED tetap dipertahankan.

## Memulai

1. Pilih L4, jalankan cell setup, pemeriksaan runtime dan autentikasi Google.
2. Buka URL Gradio. Isi KDTK4karakter, nama toko, koordinat, mode dan parameter.
3. Untuk Traffic/PPAC, siapkan video, tinjau dan simpan geometri per video. Pada mode PPAC, konfirmasi kesesuaian video dengan lokasi.
4. Klik **Pratinjau lokasi dan seluruh input sebelum Process**. Periksa titik calon toko pada peta serta ringkasan angka, mode, video dan parameter. Jika titik bukan lokasi toko, ubah angka dan pratinjau lagi; aplikasi tidak mengoreksi koordinat diam-diam.
5. Centang konfirmasi ringkasan lalu Process. Perubahan input setelah pratinjau menghapus konfirmasi. Job yang sudah diterima memakai salinan input tersendiri.
6. Biarkan cell server berjalan. Gunakan diagnosis dari Gradio saat job aktif; tidak perlu Stop untuk mengambil diagnosis.
7. Pada RESULT periksa ID/koordinat, scope, kualitas, status komponen, kelengkapan total, dan status publikasi. Buka kembali hasil BQ/GCS untuk job yang sama.
8. Hentikan cell server setelah job selesai. Stop/Interrupt menutup tunnel dan dapat menghentikan worker aktif.

Tidak perlu membuat tabel BQ baru atau menambah dependency. Akun runtime memerlukan izin create/read object pada bucket hasil yang sudah disiapkan.

## Fase 1 — Input dan identitas job

UI mengikat seluruh input yang ditinjau dengan Review SHA256. Process menolak
konfirmasi yang tidak cocok dengan nilai saat itu. Metadata job disalin sebelum
engine mulai; perubahan HOME setelah submit tidak mengubah job tersebut.

Sebelum engine berjalan, metadata input disimpan create-only/checksum ke:

```
gs://aretfak-location-intelligence/jobs/<KDTK>/<periode>/<job_id>/inputs/job-input.json
```

Jika penyimpanan snapshot gagal, engine tidak diluncurkan. ID job ini digunakan
lagi pada manifest hasil dan BQ. File memuat mode, konteks, parameter, video yang
dipilih/valid/dilewati, referensi SHA geometri/inspeksi, versi aplikasi, Review SHA
serta Input SHA. Review SHA mengikat pilihan yang ditinjau; Input SHA juga
mengikat ID dan waktu job sehingga kedua hash memang berbeda.

File nasional tidak perlu diduplikasi seluruhnya ke setiap job. Snapshot sumber
Area dan artefak input yang sudah tersedia tetap menggunakan kontrak GCS/manifest
sebelumnya. Penguncian metadata input sebelum engine bukan klaim bahwa pemulihan
komputasi dari SIGKILL sudah selesai; itu cakupan fase berikutnya.

| Kasus | Langkah | Tanda berhasil |
|---|---|---|
| P1-A | Pratinjau lokasi toko | Pin dan angka ringkasan sesuai koordinat yang dimaksud |
| P1-B | Sesudah pratinjau, ubah longitude/mode/parameter/video | Konfirmasi dihapus; Process meminta pratinjau ulang, tidak menjalankan engine |
| P1-C | Process input yang dikonfirmasi | Job ID muncul; snapshot GCS tersedia sebelum komputasi; ID sama pada hasil/receipt |
| P1-D | Ubah HOME saat job berjalan | Hasil dan snapshot tetap memakai input saat submit, bukan perubahan berikutnya |
| P1-E | Buka hasil job tersimpan | Longitude/latitude/Job ID/Review SHA pada RESULT cocok dengan input yang dikonfirmasi |

Contoh TGDI yang diberikan owner: latitude `-7.33058110387148`, longitude
`110.50486365193136`. `105.0486365193136` adalah longitude lain dan tidak boleh
dianggap sebagai lokasi yang sama. Contoh ini bukan pembatas lokasi nasional.

## Fase 2 — Progres dan diagnosis

Progres memisahkan persiapan BQ, PBF, pembekuan sumber, normalisasi, graf/routing,
alokasi pasar, pelepasan GPU, rendering, PPAC, dan publikasi. Checkpoint menyimpan
waktu awal/akhir serta riwayat tahap. Status sumber per job ikut disimpan sebagai
artefak diagnosis saat hasil dipublikasikan.

CPU/RAM adalah observasi proses aktif beserta child yang masih ada, bukan peak
kapasitas seluruh job. GPU adalah sampel runtime dengan cache15detik, bukan
atribusi eksklusif job. Proses hidup/HTTP200 atau checkpoint lama tidak membuktikan
pekerjaan maju. Persentase/ETA tidak dibuat apabila pekerjaan tidak terukur.

Kategori diagnosis memisahkan INPUT_ERROR, SOURCE_DATA_UNAVAILABLE,
RUNTIME_ERROR, PRESENTATION_ERROR, STORAGE_OR_ACCESS_ERROR dan COMPUTATION_ERROR.
FAILED berarti eksekusi tidak selesai; kategori menjelaskan penyebab, bukan
menuduh semua kasus sebagai kerusakan algoritma. Misalnya ekstrak kosong tidak
diubah menjadi jumlah bangunan/STD0. Metadata RUNNING yang prosesnya sudah keluar
dapat ditampilkan sebagai INTERRUPTED_PROCESS_EXITED saat diagnosis dibuka kembali.

| Kasus | Langkah | Tanda berhasil |
|---|---|---|
| P2-A | Jalankan Area di wilayah padat | Tahap aktif terlihat, terutama alokasi pasar dan renderer; durasi/umur checkpoint berubah dan observasi resource tersedia bila diizinkan |
| P2-B | Buka diagnosis saat engine aktif | Tombol tidak menunggu antrean engine dan tidak memulai perhitungan baru |
| P2-C | Ada kegagalan | Kategori, tahap dan bukti log tersedia; data tidak tersedia dibedakan dari error runtime/komputasi |
| P2-D | Unduh diagnosis sesudah job | Paket mencakup metadata job/status, trace/log yang tersedia, tanpa credential/video/raw source rows |

Tidak ada janji durasi nasional yang seragam. Catat karakter wilayah dan waktu
setiap tahap; batas kapasitas dan optimasi worker adalah fase berikutnya.

## Fase 3 — Mode dan kelengkapan hasil

| Mode | Engine | Komponen PPAC | STD total |
|---|---|---|---|
| Area Coverage | Area saja | Residential + Fasum | INCOMPLETE/null |
| Traffic Counter | Video valid saja, tanpa Area | Traffic; provisional jika sampel belum lengkap | INCOMPLETE/null |
| PPAC | Area lalu Traffic | Semua komponen tersedia | Hanya numerik jika input gabungan lengkap |

Komponen berstatus AVAILABLE, UNVERIFIED, INCOMPLETE, NOT_REQUESTED atau
UNAVAILABLE. Engine yang tidak diminta tidak menjadi angka0. Area/Traffic gagal
tidak disamarkan menjadi data0; komponen yang berhasil tetap terlihat. Jika
publikasi gagal, grid PPAC mempertahankan hasil komputasi lokal dengan peringatan
belum tersimpan, dan tidak mengambil job lama untuk menggantikannya. Data RESULT
job sebelumnya dibersihkan saat proses baru diterima agar tidak tercampur.

Traffic harus lolos inspeksi dan review geometri. File rusak, berubah, duplikat,
atau belum ditinjau dilewati dengan alasan. Video yang dapat dicacah tetapi di
luar300–306detik tidak otomatis menjadi sampel PPAC5menit. Sesi hilang tidak dibuat
sebagai sampel nol. Komponen Traffic sementara tetap mengikuti formula MVP dan
bobot hari Excel4/3 yang sudah ada; statusnya bukan STD total final.

| Kasus | Tanda berhasil |
|---|---|
| P3-A — Area saja, tanpa video | Tidak ada inference Traffic; Residential/Fasum tampil; total null |
| P3-B — satu video valid + slot invalid | Video valid selesai; slot invalid punya alasan SKIPPED; Traffic sementara; total null |
| P3-C — PPAC dengan seluruh observasi wajib | Urutan Area→Traffic→PPAC, total numerik dan scope combined |
| P3-D — PPAC dengan observasi kurang/engine gagal | Total BLOCKED/null, komponen berhasil tidak hilang dan alasan jelas |
| P3-E — bangunan UNVERIFIED | Ikut policy Residential, tetap berstatus UNVERIFIED; tidak berubah menjadi terverifikasi |
| P3-F — buka kembali job | Grid berasal dari PPAC JSON terverifikasi milik job yang sama; koordinat/identitas sesuai |

Untuk jam<=15, observasi normal adalah weekday/weekend x pagi/siang/sore/malam.
Jam>15 tetap memerlukan sesi tambahan. Konfirmasi lokasi/video tetap wajib untuk
mode PPAC. Notebook tidak menggabungkan job lama secara diam-diam.

## Catatan hasil user testing

Catat: versi aplikasi, Job ID, mode, karakter wilayah, koordinat yang dikonfirmasi,
Review SHA, durasi per tahap, kualitas komponen/total, hasil publikasi, perilaku
yang diharapkan, temuan, dan tautan diagnosis. Jangan menyertakan credential.

Penerimaan Fase1–3 masih menunggu user testing nyata. Pengujian lokal memakai
fixture terikat SHA dan mock storage untuk boundary; bukan fresh inference L4
atau bukti akurasi/kapasitas nasional. Fase4–7, pemisahan antrean GPU/CPU, capacity
benchmark, image produksi dan deployment staging belum dinyatakan selesai.
