# Colab UI dan estimasi penduduk — 0.7.1rc1

Notebook aktif: `notebooks/active/17_colab_l4_phase123_user_testing.ipynb`.
Gunakan runtime baru, pilih L4, jalankan setup/autentikasi, lalu buka URL Gradio baru.
Pilih RWI, pratinjau input, konfirmasi, kemudian Process. Mulai Area saja sebelum PPAC gabungan.
Tidak perlu membuat tabel BigQuery baru; snapshot parameter, native result, display tables dan map tetap melalui publikasi GCS/manifest sebelumnya. Hasil lama tidak dihitung ulang diam-diam; jalankan job baru untuk memakai formula ini.

## Aturan penduduk

Jumlah kepala berarti **estimasi orang**, bukan KK atau jumlah penghuni terverifikasi.
Residential dan Unknown: satu bangunan ×4orang, okupansi1. Unknown dikelompokkan pada Residential di tabel; status sumber/UNVERIFIED tetap dipertahankan pada peta/native result.

Tipe lain: **luas tapak / luas kamar × (lantai efektif − pengurang) × penghuni/kamar × okupansi**.

| Tipe | Minimum lantai | Default lantai Atas/Bawah | Luas kamar Atas/Bawah, m² | Pengurang lantai | Orang/kamar | Okupansi Atas/Bawah |
|---|---:|---|---|---:|---:|---|
| Hotel |3|8 /5|60 /45|2|2|60% /30%|
| Apartement |10|20 /10|45 /36|2|2|70% /75%|
| Kost |2|5 /3|45 /36|1|2|98% /95%|
| Dormitory |2|3 /2|60 /45|1|1|98% /95%|

RWI Atas/Bawah adalah MENENGAH ATAS/MENENGAH BAWAH. Lantai sumber positif digunakan bila tersedia; jika tidak, gunakan default RWI. **Minimum diterapkan sebagai batas bawah lantai efektif**, termasuk bila lantai sumber lebih rendah. Contoh Kost sumber1lantai → efektif2lantai. Lantai sumber tidak ditimpa; `levels_basis=OWNER_MINIMUM_OVERRIDE` menjelaskan asumsi tersebut. Ini keputusan implementasi atas instruksi minimum owner, bukan bukti jumlah lantai bangunan nyata.

Estimasi menyimpan luas tapak, tipe, RWI, lantai sumber/efektif, basis lantai, luas kamar, okupansi dan policy `owner_footprint_occupancy_v1`. Nilai sebelum pembulatan menjadi feeder Residential PPAC; okupansi tidak dikalikan lagi. Pembagian zona/faktor SWOT/hari/formula Traffic tetap mengikuti policy PPAC sebelumnya. Hotel/Apartment/Kost/Dormitory yang kehilangan luas tidak dianggap populasi0; komponen terkait ditolak sebagai input tidak lengkap.

PPAC tetap memakai himpunan bangunan teralokasi + UNVERIFIED menurut keputusan owner sebelumnya, tanpa menggandakan ID. Tabel mengikuti himpunan sama; peta juga menampilkan bangunan lain untuk peninjauan, tetapi tidak otomatis memasukkannya ke PPAC. Routing/Huff, batas seleksi Area, kepemilikan/status asli, serta aturan counting tidak diubah.

## Tampilan

- Tooltip bangunan: lebar200px, tinggi maksimum115px, word wrap/gulir. ID, tipe, luas tapak, status, reason dan estimasi orang. Layer bangunan diletakkan di atas garis jalan agar hover/klik tidak tertutup jalan; marker tetap di atasnya.
- Area: radius, Tipe Bangunan, Jumlah bangunan, jumlah kepala. Radius berupa zona terpisah 0–400m, >400–800m, >800–2000m; kelompok kosong tidak dibuat sebagai populasi yang hilang. Tipe ditampilkan jika ditemukan dalam kelompok tersebut.
- Indomaret: KDTK, NAMA_TOKO, TGL_GO, TIPE_TOKO, DOMAIN, SOCIO_CLASS, Investasi, RAB, STD, Jarak(m), Tipe Jalan. Metadata tambahan dibaca dari kolom sumber yang tersedia dan dibekukan dalam source bundle. Tidak ada nilai komersial yang ditebak; sumber/kolom/query opsional yang tidak tersedia meninggalkan nilai kosong. Join kode ambigu juga tidak dipilih sembarang.
- Jarak mengikuti jarak kandidat pada output engine. Tipe Jalan adalah kelas segmen graf terdekat ke titik toko, **bukan verifikasi akses atau jalan depan toko**.
- POI tanpa nama (null/kosong/whitespace/literal null) dihapus dari tabel; kontribusi analitik POI tidak dihapus dari engine.
- Grid PPAC: SOURCE, Jumlah, Konstanta, Total; Residential, Traffic, Fasum, STD total, Status dan Reason. Jumlah Residential=estimasi orang. Jumlah Traffic=jumlah sampel kategori yang dipakai PPAC (bukan arus kendaraan/hari); truck yang tidak dipetakan bukan feeder. Konstanta Residential/Traffic adalah **rasio efektif Total/Jumlah**, bukan pengganti koefisien/rumus asli. Fasum menampilkan policy jarak. STD total dibaca dari ppac.json, tidak dijumlah ulang dari grid; null/BLOCKED dan UNVERIFIED tetap terlihat. Fasum dipertahankan agar kontribusinya tidak tersembunyi.

## Checklist owner

1. Pastikan startup menampilkan versi0.7.1rc1 dan alokasi L4.
2. Pilih RWI Atas, preview, ubah ke Bawah: konfirmasi harus terhapus dan wajib preview ulang.
3. Jalankan Area pada lokasi yang memiliki tipe bangunan terkait; periksa popup/tooltip, ukuran/gulir, status UNVERIFIED.
4. Cocokkan satu bangunan terhadap formula dan metadata lantai; cocokkan jumlah estimasi tabel dengan feeder Residential PPAC. Tabel memakai radius centroid nyata; PPAC masih memakai proporsi zona bisnis lama, sehingga breakdown zona PPAC tidak otomatis sama dengan jumlah centroid tiap radius.
5. Jalankan job baru dengan RWI lain, bandingkan bangunan identik. Ini job/skenario terpisah, bukan overwrite hasil sebelumnya.
6. Periksa Indomaret/POI dan grid, lalu buka kembali job yang sama dari GCS/BQ untuk memastikan bukan hasil lama.
7. Uji Traffic-only dan PPAC gabungan. Komponen berhasil tetap tampil; STD total menunggu kelengkapan sumber/observasi wajib. Jika freeze, gunakan prosedur diagnosis0.7.0rc2 yang tetap tersedia.

Validasi lokal menggunakan fixture; eksekusi L4, ketersediaan kolom komersial BQ nyata, serta tampilan tooltip pada browser Colab menunggu user testing. Tidak ada klaim akurasi penduduk atau kesiapan produksi.
