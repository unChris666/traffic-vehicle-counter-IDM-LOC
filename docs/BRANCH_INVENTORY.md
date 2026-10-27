# Audit branch dan baseline konsolidasi

Snapshot 27 Oktober 2026. Seluruh history Git sudah diambil (`is-shallow-repository=false`)
sebelum keputusan ancestry dibuat. [Inventaris lengkap JSON](evidence/deployment_foundation_20261027/branch_inventory.json)
menyimpan SHA penuh, merge base, commit unik, dan delta setiap path.

## Hasil

Baseline dipilih: **`fix/kaggle-runtime-stability` @ `e077672`**, package0.6.0rc1.
Branch kerja baru: **`refactor/deployment-foundation`** langsung dari baseline.

| Branch remote saat audit | Tip | Commit baseline yang belum ada di branch | Commit branch di luar baseline | Keputusan |
| --- | --- | ---: | ---: | --- |
| `main` | `fef49db` | 10 | 0 | Pertahankan; promosi kandidat hanya melalui PR dan gate stabilitas |
| `fix/kaggle-runtime-stability` | `e077672` | 0 | 0 | Baseline konsolidasi; lanjutan pekerjaan di branch baru |
| `feature/traffic-candidate-gpu-queue` | `fef49db` | 10 | 0 | Tip identik main; tidak perlu merge ulang |
| `feature/area-coverage-kaggle-cpu-map` | `fc5e63f` | 19 | 0 | Riwayat sudah tercakup; pertahankan untuk referensi |
| `audit/area-coverage-modularization` | `dd33933` | 60 | 0 | Riwayat sudah tercakup; pertahankan untuk referensi |
| `refactor/traffic-modularization-v2` | `0564ae8` | 61 | 0 | Riwayat sudah tercakup; pertahankan untuk referensi |
| `codex/engine-adapters-20261023` | `1d878d8` | 62 | 0 | Riwayat sudah tercakup; pertahankan untuk referensi |

Seluruh tip di atas adalah leluhur baseline. Tidak ada commit unik yang perlu
di-cherry-pick dan tidak ada path lama yang hilang pada tree baseline.
Ancestry membuktikan riwayat tercakup, bukan semua perilaku lama tetap aktif:
perubahan berikutnya memang mengganti beberapa file. Delta path di JSON
memperlihatkan perbedaan isi; bukti baseline dan hasil lama tetap dipertahankan.
Tidak ada branch dihapus atau digabung ulang pada P0.

## Sepuluh commit di atas main

| Commit | Perubahan |
| --- | --- |
| `bcdac5f` | Pemulihan runtime Kaggle, advisory lock, resource diagnostics dan CI |
| `c23f461` | Upload ditinjau dan publikasi job ke GCS/BQ owner |
| `ade47a5` | Sinkronisasi metadata package dengan wheel tertanam |
| `9a30eca` | Ikatan provenance video dengan sumber yang ditinjau |
| `f25fd22` | Delapan slot, pembacaan hasil BQ dan recipe image GPU |
| `0f12c0d` | Akses konfigurasi non-root dan batas validasi image |
| `a9f579b` | Pemulihan upload terputus dan penyederhanaan hasil |
| `5198014` | PPAC terbaca dan serving peta GCS terverifikasi |
| `1f6e22c` | Diagnosis kegagalan Area dan isolasi renderer |
| `e077672` | HOME/RESULT, snapshot project dan link annotated |

Kandidat berisi pekerjaan eksperimental dan adapter yang belum diverifikasi
end-to-end. Pilihan baseline paling lengkap tidak berarti paling stabil sudah
terbukti. [Gate merge](MERGE_READINESS.md) berlaku untuk seluruh delta ke main,
bukan hanya perubahan dokumentasi P0.

## Memeriksa ulang sebelum tindakan berikutnya

```bash
git fetch origin '+refs/heads/*:refs/remotes/origin/*'
git rev-parse --is-shallow-repository
# Jika true, ambil history lengkap dahulu: git fetch --unshallow origin
git rev-list --left-right --count origin/main...origin/refactor/deployment-foundation
git merge-base --is-ancestor origin/main origin/refactor/deployment-foundation
git log --oneline origin/main..origin/refactor/deployment-foundation
git diff --stat origin/main...origin/refactor/deployment-foundation
```

Snapshot ini tidak otomatis mengikuti push berikutnya. Bila branch lama menerima
commit baru, ulangi perbandingan sebelum mengarsip atau menghapusnya. Persetujuan
P0 ini tidak dipakai untuk menghapus branch atau mengubah formula engine.
