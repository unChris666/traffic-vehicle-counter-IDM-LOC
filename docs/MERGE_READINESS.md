# Pemeriksaan kandidat sebelum merge

27 Oktober 2026. Kandidat `refactor/deployment-foundation` berasal dari
`e077672` (package0.6.0rc1); pembanding main saat audit `fef49db`.

**Keputusan: HOLD untuk merge ke main.** Pemeriksaan software tidak menggantikan
verifikasi kegagalan Area pada runtime owner. P0 menyelesaikan inventaris dan
navigasi tanpa mempromosikan kode eksperimen sebagai versi stabil.

| Pemeriksaan | Status/bukti |
| --- | --- |
| History lengkap, semua tip lama tercakup | PASS; [inventaris](evidence/deployment_foundation_20261027/branch_inventory.json) |
| Main leluhur baseline, tidak ada konflik ancestry | PASS; baseline10commit di atas main |
| Perubahan P0 mempertahankan engine/notebook/SQL/dependency | PASS; diff terhadap e077672 kosong untuk src/notebooks/sql/deploy serta recipe image/dependency |
| Unit/integration, mypy, build, wheel smoke | PASS lokal;279tes:269lulus/10skip; strict mypy14file, sdist/wheel dan3CLI/import facade pada venv terpisah lulus |
| CI SHA kandidat terbaru | Lihat check pada SHA terbaru PR foundation; hasil final ditautkan pada PR |
| Jalur Area owner yang gagal dan peta tersimpan dapat dibuka | OPEN; belum ada log sesi gagal atau run sukses baru pada lokasi itu |
| GCS/BQ end-to-end dengan runtime owner | OPEN; adapter/mocks tersedia, identitas GCP tidak tersedia pada executor ini |
| Render8video dan kapasitas RAM/disk | OPEN; bukan klaim dukungan kapasitas produksi |
| Pemisahan antrean GPU/CPU | OPEN; slotGPU masih mencakup counting/publication pada jalur aktif |
| Image final non-root + GPU dan deployment cloud | OPEN; pekerjaan lanjutan, Docker ditunda sesuai arahan sebelumnya |
| Proteksi server main | UNKNOWN; read API403, [langkah admin](BRANCH_POLICY.md) |

[Laporan validasi lokal](evidence/deployment_foundation_20261027/validation.json)
mencatat skip, scope, dan satu percobaan awal yang gagal karena SQL belum
termasuk sparse checkout lokal. Setelah checkout dilengkapi, seluruh suite
diulang dan lulus. Sebanyak123target tautan lokal README/panduan telah diperiksa.

Pemeriksaan fungsional sebelum promosi kandidat Kaggle: jalankan Area saja pada
lokasi owner dan simpan log/receipt; verifikasi peta/tabel GCS/BQ dengan job yang
sama; uji subset Traffic dan PPAC lengkap/kurang pada sumber yang valid. Jangan
menjalankan ulang Traffic hanya untuk menyelidiki Area, dan jangan mengubah
input hilang menjadi nol agar status tampak berhasil. Uji produksi terpisah
mencakup kapasitas, worker, image dan pengoperasian layanan.

Tidak ada inference baru, publikasi notebook, CRUD cloud, penghapusan branch,
atau merge main yang dilakukan untuk audit P0. Pemeriksaan software dapat
dijalankan ulang tanpa kredensial cloud; akses runtime owner diperlukan untuk
bukti yang masih OPEN. PR tetap draft selama syarat stabilitas inti belum jelas.
