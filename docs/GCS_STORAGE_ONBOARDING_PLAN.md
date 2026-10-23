# Google Cloud Storage — keputusan dan panduan tahap integrasi

23 Oktober 2026. **Provider video/result dipilih owner: Google Cloud Storage.**
Ini rencana onboarding ketika milestone storage dicapai, bukan setup yang
sudah dijalankan. Bucket/project/IAM/CRUD belum dibuat atau diuji pada task ini.
Metadata database belum dipilih; GCS bukan pengganti otomatis relational job DB.

## Waktu meminta tindakan owner

Setelah local artifact/storage interface, contract tests dan concrete upload/
read/update/delete test siap, pandu owner melalui langkah di bawah dengan
project/bucket/identity aktual. Jangan meminta owner membaca proposal storage
sekarang atau memberikan credential rahasia lewat chat. Pekerjaan independen
menggunakan local adapter tetap berjalan dengan label local, bukan GCS.

## Panduan setup yang harus diberikan pada tahap M4

1. Pilih/buat Google Cloud project yang dimiliki owner, verifikasi billing yang
   diperlukan dan hak administratif. Region dipilih sesuai compute/pengguna/
   biaya; nama bucket global belum diketahui, tidak dikarang sebagai fakta.
2. Buat bucket private dengan uniform bucket-level access dan public access
   prevention. Buktikan akses yang benar-benar tersedia; jangan memakai public
   bucket untuk mengatasi error permission.
3. Tentukan identitas backend/worker dan developer. Prioritaskan attached
   service account/ADC/Workload Identity sesuai runtime, dengan izin object
   minimum pada bucket yang dimaksud; admin provisioning terpisah. Jangan
   membuat/download long-lived JSON key sebagai default.
4. Tetapkan budget/region/storage class, retention/lifecycle, soft-delete atau
   versioning dan backup/recovery sesuai kebutuhan/biaya nyata. Jangan
   mengaktifkan semua opsi tanpa memahami konsekuensi biaya dan deletion.
5. Konfigurasikan bucket/project/prefix lewat environment/config refs.
   Rahasia tidak disimpan di GitHub. Frontend tidak menerima service-account
   credentials; akses user melalui backend authorization dan signed URLs
   terbatas bila diperlukan.
6. Jalankan CRUD hanya pada prefix sandbox yang teridentifikasi. Verifikasi
   checksum, generations, permission failures dan cleanup; dokumentasikan
   perintah, input, hasil, identities non-secret dan output aktual.
7. Integrasikan UI: upload/status/play/download hasil tersimpan, lalu uji tutup
   browser/restart worker dan buka ulang. CRUD test saja bukan production-ready.

## Semantik CRUD yang akan diuji

| Operasi | Bukti minimum dan batas |
|---|---|
| Create | Upload test object dengan if_generation_match=0; object, size/checksum/generation dapat dibaca kembali; collision tidak menimpa input/result lama |
| Read | Download/list/metadata sesuai role; SHA256 isi cocok; GCS CRC32C dipakai sebagai validasi transport tambahan |
| Update | Update hanya test object, mutable draft config atau pointer dengan generation precondition; finalized results/raw video tetap immutable dan memakai revisi baru |
| Delete | Hapus test object pada sandbox, verifikasi not-found sesuai kebijakan; bukan menghapus historical baseline atau seluruh bucket |

Kasus negatif: identitas salah, forbidden role, object hilang vs permission
error, upload interrupted, stale generation/concurrent writers, retry yang
sama, checksum mismatch, partial result publication dan cleanup. Signed URL
kedaluwarsa tidak disamakan dengan object hilang; URL sementara bukan identity.
Tidak menyamakan empty listing dengan video/dataset berhasil diproses0.

## Layout artefak yang diusulkan

Bucket name dan region tetap OPEN. Prefix adalah rancangan, belum resource:

```text
tenants/<tenant_id>/targets/<target_id>/inputs/<source_sha256>/...
tenants/<tenant_id>/targets/<target_id>/snapshots/<snapshot_id>/...
tenants/<tenant_id>/targets/<target_id>/results/<engine>/<fingerprint>/<revision>/...
tenants/<tenant_id>/targets/<target_id>/reviews/<review_revision>/...
sandbox/<test_run_id>/...
```

ArtifactRef menyimpan bucket/object, generation, bytes, media/schema type dan
SHA256. Locator `gs://...` belum membuktikan object ada/izin benar. Manifest
final ditulis setelah seluruh mandatory objects selesai dan diverifikasi;
GCS multi-object upload bukan satu transaksi atomik. Reader hanya memakai
manifest yang sudah committed/finalized. Update latest pointer memakai
conditional write. Restart/retry tidak menggandakan result counts.

Original video, detector/tracker cache, snapshot dan machine/reviewed hasil
berversi tidak ditimpa. Disk worker hanya sementara. GCS menyimpan binary dan
JSON/CSV/GeoJSON/manifest hasil; transaksi job/user/permissions yang kompleks
mungkin memerlukan metadata DB tersendiri, diputuskan saat backend dievaluasi.
Tidak memindahkan operasi counting/routing ke storage layer.

## Gate selesai storage

Project/bucket/identity yang benar tercatat tanpa secrets; CRUD positive/
negative tests PASS; akses user terisolasi; finalized results immutable dan
checksummed; upload/retry/reopen/restart benar; budget/retention/recovery
jelas. Laporan harus memisahkan local tests, GCS sandbox integration dan
production deployment. Tidak ada klaim CRUD PASS sebelum benar-benar dijalankan.
