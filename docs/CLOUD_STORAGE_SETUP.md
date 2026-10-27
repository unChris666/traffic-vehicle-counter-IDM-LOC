# Setup upload, GCS dan BigQuery — 27 Oktober 2026

Tujuan hasil yang ditetapkan owner:

- Bucket: **gs://aretfak-location-intelligence** (ejaan sesuai nama bucket owner).
- Dataset: **locdeproject.location_intelligence**.
- Package **0.5.1rc1**, Gradio sementara di notebook14. Tidak ada klaim akurasi baru.

Bucket/dataset ini adalah OUTPUT. Sumber PBF/model di bucket lama dan tabel
referensi Area `locdeproject.DWH_NS_LOC.*` tetap INPUT terpisah. Dataset hasil
kosong bukan pengganti tabel sumber kompetitor/toko. Tidak ada migrasi atau
penghapusan sumber lama secara otomatis.

Rilis 0.5.1rc1 menambahkan referensi peta pada `area_results`. Jika setup sebelumnya
sudah dijalankan, **jalankan ulang SQL setup terbaru**: hanya menambah kolom
`map_html_uri` dan `map_html_sha256` dengan `ADD COLUMN IF NOT EXISTS`.
Lihat [panduan Docker/Cloud Run](DOCKER_CLOUD_RUN_GUIDE.md) untuk image dan deployment.

## 1. GCS: tidak perlu membuat folder manual

GCS menyimpan object dengan prefix, bukan direktori lokal. Prefix muncul ketika
aplikasi mengunggah file pertama. Tidak perlu membuat folder kosong atau file `.keep`.
Jangan membuat bucket public; upload browser masuk melalui Gradio, bukan langsung
ke browser-GCS, sehingga CORS bucket tidak diperlukan untuk alur ini.

Contoh satu job:

```text
gs://aretfak-location-intelligence/
  jobs/TOKO001/2026-10-27/job_<uuid>/
    inputs/
      context.json
      parameters.json
      video-inventory.json
      videos/<video_id>/source.mp4
      videos/<video_id>/inspection.json
      config/<video_id>/geometry.json
      config/<video_id>/policy.json
      config/<video_id>/measurements.json.gz
      area/source-bundle.zip
    engines/traffic/<video_id>/
      result.json
      native.json.gz
      request.json
      manifest.json
    engines/area/area/...
    ppac/result.json
    summary.json
    manifest.json
```

File hanya ada bila tahap/input terkait tersedia. UUID membedakan job; jangan
menjumlah rerun job lama dan baru sebagai satu observasi. Hasil engine dapat
memakai cache tervalidasi, tetapi setiap job punya manifest dan rekap sendiri.

Aplikasi memakai create-only `if_generation_match=0`, memverifikasi ukuran,
SHA metadata dan CRC32C lokal/server. Object berbeda tidak ditimpa. Manifest job
diunggah setelah seluruh artefak. Rekap BQ kemudian dikomit dalam satu transaksi.
Retry pada host yang sama dilindungi advisory lock per job. Koordinasi worker lintas host
masih termasuk tahap deployment, bukan jaminan distributed exactly-once pada rilis ini.
`publication_status=READY` menyatakan publikasi selesai, bukan hasil model akurat
atau seluruh engine berhasil; status eksekusi/kualitas masing-masing tetap terpisah.

## 2. Izin service account

Gunakan service account yang sudah ada dalam Secret Kaggle **LocatioIntelligent**.
Tidak perlu menyalin private key ke notebook source, repository, atau browser.

Di Console **Cloud Storage → bucket aretfak-location-intelligence → Permissions**,
tambahkan identitas service account itu pada bucket ini dengan:

- Storage Object Creator (`roles/storage.objectCreator`), untuk membuat object baru.
- Storage Object Viewer (`roles/storage.objectViewer`), untuk membaca metadata/verifikasi object.
- Storage Legacy Bucket Reader (`roles/storage.legacyBucketReader`), untuk metadata bucket
  yang diperiksa readiness. Alternatif role kustom dengan `storage.buckets.get` sesuai
  kebijakan organisasi. Aplikasi tidak memerlukan penghapusan object.

Di **BigQuery → dataset location_intelligence → Sharing/Permissions**, berikan
BigQuery Data Editor (`roles/bigquery.dataEditor`) pada dataset ini.
Di **IAM project locdeproject**, berikan BigQuery Job User (`roles/bigquery.jobUser`).
Izin membaca tabel sumber Area di dataset lama tetap diperlukan secara terpisah.

Jangan mengganti seluruh policy IAM. Tambahkan binding pada resource yang tepat.
Pertahankan identitas lain yang sudah ada. Akun yang menjalankan setup SQL juga
memerlukan izin membuat tabel/view dan menjalankan query.

## 3. Buat tabel/view satu kali

1. Buka BigQuery Console pada project **locdeproject**.
2. Pastikan dataset **location_intelligence** sudah ada. Periksa tab Details untuk
   lokasi dataset; query harus berjalan pada lokasi tersebut, bukan menebaknya dari lokasi toko.
3. Buka Query editor, salin seluruh isi [SQL setup](../sql/location_intelligence_setup.sql),
   pilih GoogleSQL/Standard SQL, lalu Run.
4. Pastikan muncul lima tabel dan dua view berikut.

| Object | Jenis | Isi |
|---|---|---|
| job_runs | Tabel | Target/periode, status engine/PPAC/publikasi, URI/hash manifest |
| traffic_videos | Tabel | Identitas video, hari/sesi, durasi, frame, kualitas, pending/invalid |
| traffic_counts | Tabel | Accepted count per video/kategori/arah/measured-estimated |
| area_results | Tabel | Alokasi bangunan, kualitas/UNVERIFIED, gate zona, kontribusi fasilitas |
| ppac_results | Tabel | STD, breakdown, parameter/policy dan alasan BLOCKED |
| traffic_ppac_samples | View | Pivot motor/mobil/bus/pejalan kaki per sampel, durasi/kualitas |
| ppac_feeder | View | Sampel Traffic digabung dengan fitur Area dan status admission Gate2 |

SQL memakai `CREATE ... IF NOT EXISTS`: dapat dijalankan ulang tanpa menghapus data.
Ia tidak mengubah tabel sumber Area. Bila sudah ada schema berbeda, publikasi menolak
schema mismatch; jangan menghapus tabel berisi data untuk memaksakan kelulusan.

Alternatif pada Cloud Shell dengan Python >=3.12 setelah mengambil source branch yang sesuai:

```bash
python -m venv /tmp/li-setup
/tmp/li-setup/bin/python -m pip install '.[gcp]'
/tmp/li-setup/bin/python -m traffic_location.integration.cloud_setup
/tmp/li-setup/bin/python -m traffic_location.integration.cloud_setup --apply
```

Perintah tanpa `--apply` hanya mencetak SQL. `--apply` memakai ADC akun Cloud Shell,
memeriksa lokasi dataset yang sudah ada dan membuat object yang belum ada. Tidak
membuat dataset atau memindahkan region. Aplikasi Gradio tidak membuat tabel diam-diam.

## 4. Jalankan notebook dan upload

1. Buka notebook Gate2 versi terbaru, aktifkan Internet, GPU dan Secret
   `LocatioIntelligent`, lalu jalankan dan buka URL Gradio yang dicetak.
2. Masukkan kode toko, koordinat dan tanggal/periode analisis.
3. Pilih **Upload video**, isi delapan slot weekday/weekend × pagi/siang/sore/malam, lalu **Siapkan video dan geometri**.
4. Untuk setiap video pada dropdown: tinjau frame pertama/template dan arti arah; hari/sesi mengikuti slot upload. Jika perlu ubah geometri: pilih bagian, **Ulangi bagian**, klik
   titik perimeter (garis dua titik; polygon minimal tiga), lalu konfirmasi dan
   **Simpan tinjauan video**. Perubahan metadata/geometri membatalkan tinjauan lama.
5. Tekan **Periksa kesiapan**. Penyimpanan GCS/BQ harus READY setelah tabel dan IAM siap.
6. Pilih Area/Traffic/Gabungan dan tekan **Mulai proses**. Hasil disimpan di prefix job
   dan tabel di atas. Jika penyimpanan FAILED, hasil lokal tetap ada; perbaiki IAM/tabel
   lalu tekan **Ulangi penyimpanan hasil**. Tombol ini tidak menjalankan inference/counting.
7. Panel hasil BQ menampilkan tiga tabel dan peta job yang baru dipublikasikan.
   Gunakan kode toko dan Job ID untuk membuka hasil sebelumnya tanpa engine.
   Job lama yang belum menyimpan referensi peta tetap dapat dibuka tabelnya.

Batas teknis upload awal: 1 GiB/file, 2 GiB/batch, maksimal14 video, maksimal32 megapixel.
Ini batas operasional awal, bukan hasil benchmark kapasitas. Video disalin tanpa
re-encoding/resampling; FFprobe menghitung seluruh frame. Dataset T7SL tetap opsi
contoh. Probe/preview bukan bukti kecocokan model untuk semua kamera/scene.

PPAC tetap memerlukan seluruh weekday/weekend × pagi/siang/sore/malam, durasi
300–306detik per sampel tanpa rescaling. Jam>15 memerlukan sesi tengah_malam,
dini_hari, subuh tambahan untuk kedua kelompok hari. Video singkat tetap dapat
menjalankan Traffic; PPAC BLOCKED/STDnull sampai syaratnya terpenuhi. Tidak mengisi
slot hilang/pending dengan nol. Truck tetap tidak dipakai dalam mapping PPAC MVP.

## 5. Membaca feeder dengan aman

Pilih satu `job_id` yang benar terlebih dahulu:

```sql
SELECT job_id, target_id, period_id, execution_status, ppac_status,
       publication_status, manifest_uri
FROM `locdeproject.location_intelligence.job_runs`
ORDER BY created_at DESC
LIMIT 20;
```

Lalu ganti placeholder berikut dengan ID yang dipilih:

```sql
SELECT *
FROM `locdeproject.location_intelligence.ppac_feeder`
WHERE job_id = 'job_<ID_yang_dipilih>';
```

View berisi satu baris per video/sesi, bukan satu total gabungan semua job.
Kategori yang tidak tersedia tetap NULL; accepted zero hanya berasal dari
kategori yang memang didukung/diamati dalam hasil sukses. Pending/invalid tetap
terpisah. `sample_duration_compatible` dan kualitas harus dipertahankan saat dipakai.
`gate2_admission_verified_for_saved_parameters` mengacu parameter yang tersimpan
pada job itu; tidak mengesahkan parameter baru atau akurasi bisnis. Formula PPAC
saat ini tetap dijalankan melalui gate integrasi, bukan otomatis dari SUM seluruh BQ.

## Validasi dan batas akses

Pengujian software meliputi inspeksi/preview fixture video nyata secara teknis,
binding upload-geometri, failure isolation, konflik object, retry idempotent,
query parameter/transaction dan schema SQL. Tidak ada inference GPU baru atau
provisioning cloud yang dilakukan hanya dengan menjalankan tes. Pembuatan tabel,
IAM dan CRUD live pada bucket/dataset owner perlu dijalankan/diverifikasi pada akun
owner. File request asli di artefak mempertahankan provenance path; pemulihan ulang
ke compute lain memerlukan resolusi path berdasarkan manifest/hash.
