# TOR3-MALAM — kandidat geometri N1

**Update terpisah:** pengguna kemudian menerima N1 untuk uji awal dan mengonfirmasi arah malam; lihat [accepted artifact](../accepted_geometry/README.md). JSON/PNG proposal dan isi proposal awal berikut tetap menjadi bukti sebelum keputusan.

**PROPOSAL, belum disetujui pengguna.** [N1](TOR3-MALAM-N1.png) memetakan template relatif G3 ke frame malam native 1280×720 tanpa crop, rotasi, snapping atau perubahan koordinat. Ini transfer template, bukan geometri malam yang sudah tervalidasi. [JSON lengkap](TOR3-MALAM-N1.json) menyimpan sumber template, SHA video/frame, normalisasi, koordinat, cap B dan selisih endpoint garis terhadap vertex A.

| Elemen | Native pixel, origin kiri atas |
|---|---|
| P1 garis | `(6.0, 688.6666666666666)` |
| P2 garis | `(1248.5333333333333, 407.19999999999993)` |
| B cap X | `1166.6666666666667` |
| A, keliling | `(6,688.6667) → (6,464.2667) → (743.3333,220.4) → (1248.8,407.7333)`; angka lengkap di JSON |
| B, keliling | `(6,688.6667) → (1166.6667,426.2995) → (1166.6667,710) → (6,710)`; angka lengkap di JSON |

Frame utama **7192** berasal dari video Kaggle yang SHA-nya sama dengan bukti Phase 1. Polygon diberi tint ringan; P1/P2 dan dua region diberi label. Header/footer berada di luar frame, sehingga tambahan panel tidak mengubah koordinat video. [Lembar alignment](TOR3-MALAM-N1_alignment.png) menampilkan proposal pada frame 0, 2397 dan 7192.

**VISUAL OBSERVATION AI-ASSISTED:** garis transfer terlihat melintasi koridor jalan. A juga mencakup latar gelap/bangunan; B mencakup sebagian teks tertanam kanan bawah. Belum ada bbox/track malam untuk membuktikan kelayakan anchor di area ini. Posisi endpoint di area selain aspal sendiri belum membuktikan garis invalid; diperlukan review koridor perjalanan dan bukti temporal setelah asosiasi.

Pertanyaan review yang diajukan saat proposal:

1. Apakah garis dan ruang pengamatan polygon sebelum/sesudahnya sesuai? Jika perlu, sebutkan endpoint atau tepi polygon dan arah pergeseran.
2. Apakah cap B tetap sesuai, dengan teks tertanam di kanan bawah?
3. Apakah **usulan** `A_TO_B = mendekati kamera` dan `B_TO_A = menjauhi kamera` benar pada TOR3-MALAM? Pemetaan PAGI tidak diterima otomatis untuk malam.

BC dari bbox raw kendaraan terhubung ke track tetap menjadi kontrol pengukuran yang disepakati. Band 0/confirmation 1 adalah kontrol eksperimen yang dibekukan, bukan default produksi. Geometry/counting malam belum boleh dijalankan memakai N1 sampai feedback dicatat. Screening enhancement/detection pada DEV tidak membutuhkan keputusan counting ini.

Reproduksi dari bytes video yang sama:

```bash
/workspace/.venvs/traffic-inspection/bin/python \
  docs/evidence/phase_7/verification/build_night_geometry_and_sampling.py \
  --repo . --video /tmp/traffic-phase7-source/TOR3-MALAM.mp4
```

Builder juga membuat sampel raw dan clip runtime untuk review; tidak menjalankan model, enhancement, stabilization atau counting. Source video tidak disimpan di GitHub.
