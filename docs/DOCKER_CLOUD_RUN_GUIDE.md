# Panduan Docker dan Cloud Run GPU untuk uji pribadi

Tanggal: 27 Oktober 2026. Rilis 0.5.1rc1. Panduan ini menyiapkan image dan pilot
privat; belum menyatakan delapan video berhasil sampai hasil cloud pada L4.
Owner melaporkan setup GCS/BQ sebelumnya sudah dijalankan. Jangan membuat ulang
bucket/dataset itu. Jangan deploy saat analisis pada instance lama masih aktif.

## A. Apa yang berubah setelah memakai Docker

Image adalah paket aplikasi, Python, pustaka CUDA dan dependency sistem.
Container adalah proses yang menjalankan image. Dockerfile adalah resep build.
Artifact Registry menyimpan image; Cloud Build membangun; Cloud Run menjalankan.

Pip/apt tetap dipakai **di dalam proses build image**, sekali per revisi. Pemakai
cukup menjalankan image. Startup dan pekerjaan engine pada mode `bundled` tidak
menjalankan pip/apt, bahkan bila dependency hilang: pemeriksaan gagal dengan kode
jelas dan image harus dibangun ulang. Mengunduh model/PBF dari GCS adalah staging
data, bukan instalasi software. Bobot diverifikasi terhadap SHA yang dikunci.

Error `bigframes`, `dopamine-rl`, `hf-gradio`, `google-adk`, dan lainnya pada
Kaggle berasal dari lingkungan umum Kaggle yang berisi aplikasi tidak terkait.
Image memakai venv terisolasi tanpa paket-paket tersebut. Jangan menambal semua
paket Kaggle agar cocok dengan aplikasi ini.

`deploy/requirements.in` menentukan dependency langsung; `requirements.lock`
mengunci dependency transitif beserta hash untuk Python3.12/Linux amd64.
Build memasang dengan `--require-hashes`, lalu `pip check` dan uji import/native
binary. Python GDAL/PROJ sistem berjalan di `/usr/bin/python3` secara terpisah dari
venv aplikasi. Base CUDA dipin digest. Paket apt dipilih resolver Ubuntu dan
inventorinya dicatat `/app/deploy/os-packages.txt`; apt belum snapshot-reproducible.
Setelah lulus uji, deploy **digest image hasil build**, bukan tag yang bisa berubah.

Profil baru container: CUDA12.6, Torch2.7.1, torchvision0.22.1, kandidat FP32.
Ini perubahan lingkungan dari Kaggle, sehingga parity/hasil L4 harus diuji.
`pip check` membuktikan konsistensi metadata dependency, bukan kompatibilitas
CUDA pada semua GPU atau akurasi model. Uji GPU terpisah di bawah wajib.

## B. Perbarui schema peta tanpa menghapus data

Jalankan ulang seluruh `sql/location_intelligence_setup.sql` di BigQuery.
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` menambah dua kolom nullable pada
`area_results`: `map_html_uri` dan `map_html_sha256`. Lima tabel dan dua view yang
sudah ada tetap dipertahankan. Job lama memiliki NULL dan tampil tanpa peta.
Job Area baru meminta renderer Folium/Esri yang sudah tersedia pada engine.
HTML/GeoJSON besar tetap di GCS; BQ menyimpan referensi dan checksum.

Gradio menyediakan delapan slot weekday/weekend × pagi/siang/sore/malam.
Hari/sesi ditentukan slot; pengguna meninjau geometri dan arah setiap video.
Slot tambahan shift3 tersedia untuk jam operasional>15. Traffic boleh subset,
PPAC tetap menunggu kelengkapan dan durasi300–306detik per sampel. Video gagal,
pending, dan kategori tidak tersedia tidak menjadi nol.

Panel hasil memuat `traffic_counts`, `area_results`, `ppac_results` **dari BQ**
berdasarkan kode toko + job_id READY. Job kosong berarti job terbaru target itu.
Setelah publikasi berhasil panel memuat job baru otomatis. Tombol buka hasil
tersimpan tidak menjalankan engine. HTML peta diambil server dari GCS private,
diverifikasi generation/SHA, lalu tampil pada iframe sandbox dengan basemap Esri.
Data tabel tidak hilang bila peta/Esri gagal. Jangan menjumlahkan rerun lintas job.

## C. Mengambil source

Di Cloud Shell atau terminal lokal:

```bash
git clone --branch fix/kaggle-runtime-stability https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC.git
cd traffic-vehicle-counter-IDM-LOC
git rev-parse HEAD
```

Repository private memerlukan login GitHub yang berizin. Catat commit untuk build.
PR masih perlu ditinjau/digabung sesuai workflow owner; jangan build `main` lama.
Jangan menyimpan credential JSON di folder source. `.dockerignore` memasukkan hanya
kode, config dan dependency lock. `.gcloudignore` membatasi unggahan source build.

## D. Uji Docker lokal (opsional; Cloud Shell cukup untuk build CPU)

1. Install Docker Desktop pada Windows/macOS, atau Docker Engine pada Linux.
   Jalankan `docker version`: Client dan Server harus tersedia.
2. Untuk menjalankan GPU lokal diperlukan host Linux/WSL2 dengan NVIDIA driver
   serta NVIDIA Container Toolkit. Docker tidak menyediakan GPU fisik.
3. Build pada arsitektur Linux amd64:

```bash
docker build --platform linux/amd64 -t li-engine:0.5.1rc1 .
docker run --rm li-engine:0.5.1rc1 python -m pip check
docker run --rm li-engine:0.5.1rc1 python -m traffic_location.integration.container_runtime --verify
```

Harus menghasilkan `No broken requirements found` dan `BUNDLED_RUNTIME_OK
CPU_IMPORTS_ONLY`. Build pertama mengunduh beberapa GB; siapkan disk memadai
(setidaknya30GB tersedia untuk build+cache, bisa lebih tergantung Docker).
Cache mempercepat build berikutnya. Build CPU tidak menjalankan inference.

4. Pada mesin NVIDIA yang sudah mendukung container GPU:

```bash
docker run --rm --gpus all li-engine:0.5.1rc1 python -m traffic_location.integration.container_runtime --verify --gpu
```

Ini menguji Torch CUDA dan CuPy JIT/reduksi serta provider ONNX. Verifikasi sesi
ReID/model nyata tetap diperlukan pada smoke engine; daftar provider saja tidak
membuktikan inference GPU berhasil. Jangan melanjutkan jika verifikasi gagal.

5. Untuk menguji UI tanpa GCP, jalankan:

```bash
docker run --rm -p 8080:8080 li-engine:0.5.1rc1
```

Buka `http://localhost:8080`. UI dapat terbuka tanpa credential; membaca hasil atau
menjalankan engine membutuhkan ADC. Container dihentikan dengan Ctrl+C.

Untuk ADC lokal gunakan `gcloud auth application-default login`, lalu mount file
ADC lokal **read-only**, bukan COPY ke image:

```bash
docker run --rm --gpus all -p 8080:8080 \
  --mount type=bind,src="$HOME/.config/gcloud/application_default_credentials.json",dst=/run/adc.json,readonly \
  -e GOOGLE_APPLICATION_CREDENTIALS=/run/adc.json \
  li-engine:0.5.1rc1
```

Contoh path untuk Linux; sesuaikan pada Windows. Jangan mempublikasikan port
mesin ke internet untuk pilot ini. Workspace default hilang saat container
`--rm` berhenti; hasil yang sudah READY tetap dapat dibuka dari BQ/GCS.
Volume lokal opsional harus writable oleh UID10001, bukan mengubah image ke root.

Kaggle umumnya tidak menyediakan daemon/privilege Docker untuk container GPU
bersarang. Periksa `docker info`; bila tidak tersedia, uji notebook biasa di Kaggle,
build via Cloud Build, lalu uji image pada Cloud Run/VM GPU. Menjalankan notebook
Kaggle bukan bukti image Docker sudah diuji. Cloud Shell juga bukan host GPU.

## E. Persiapan Google Cloud (Cloud Shell)

Billing harus aktif. Jalankan perintah dari folder repository, dengan akun admin
project yang tepat. Contoh memilih Singapore L4; periksa dukungan region dan
quota GPU Cloud Run aktual sebelum build/deploy. Lokasi GCS/BQ yang sudah ada
tidak diubah. Beda region dapat menambah transfer/latensi.

```bash
export PROJECT_ID=locdeproject
export REGION=asia-southeast1
export REPOSITORY=location-intelligence
export SERVICE=location-intelligence-pilot
export RUNTIME_SA=li-engine
export BUILD_SA=li-image-builder
export IMAGE_TAG="$(git rev-parse --short=12 HEAD)"
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/engine:${IMAGE_TAG}"
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com storage.googleapis.com bigquery.googleapis.com iam.googleapis.com logging.googleapis.com

gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker --location="$REGION" --description="Location Intelligence runtime images"
gcloud iam service-accounts create "$RUNTIME_SA" --display-name="Location Intelligence engine"
gcloud iam service-accounts create "$BUILD_SA" --display-name="Location Intelligence image builder"
```

Jika resource sudah ada, gunakan yang ada; tidak perlu menghapus/membuat ulang.
Aktivasi API tidak menyediakan quota GPU otomatis. Tidak perlu membuat dataset
BigQuery/bucket hasil kembali, dan tidak perlu database dalam container.

## F. Izin minimum runtime dan build

Runtime Cloud Run memakai attached service account lewat ADC, **tanpa key JSON**
dan tanpa Kaggle Secret. Identitas baru berbeda dari service account Kaggle,
sehingga perlu izin tersendiri:

```bash
export RUNTIME_EMAIL="${RUNTIME_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
export BUILD_EMAIL="${BUILD_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
for ROLE in roles/storage.objectCreator roles/storage.objectViewer roles/storage.legacyBucketReader; do
  gcloud storage buckets add-iam-policy-binding gs://aretfak-location-intelligence --member="serviceAccount:${RUNTIME_EMAIL}" --role="$ROLE"
done
gcloud storage buckets add-iam-policy-binding gs://feeder-location-intelligent --member="serviceAccount:${RUNTIME_EMAIL}" --role=roles/storage.objectViewer
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${RUNTIME_EMAIL}" --role=roles/bigquery.jobUser
```

Di BigQuery Console dataset `location_intelligence` → Sharing → Permissions,
tambahkan `RUNTIME_EMAIL` sebagai BigQuery Data Editor pada **dataset hasil**.
Pada dataset sumber Area `DWH_NS_LOC`, berikan Data Viewer; cek sumber tabel pada
config bila berubah. Data Editor pada dataset hasil mencakup hak baca tabel
untuk panel hasil. Tidak perlu BigQuery Admin, Storage Admin atau Project Editor.
Cache upload ke bucket sumber bersifat opsional; read-only sumber cukup untuk
komputasi, hasil wajib masuk bucket hasil. Runtime tidak membuat schema otomatis.

Untuk builder:

```bash
gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" --location="$REGION" --member="serviceAccount:${BUILD_EMAIL}" --role=roles/artifactregistry.writer
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${BUILD_EMAIL}" --role=roles/logging.logWriter
gcloud storage buckets create "gs://${PROJECT_ID}-li-build-source" --location="$REGION" --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding "gs://${PROJECT_ID}-li-build-source" --member="serviceAccount:${BUILD_EMAIL}" --role=roles/storage.objectViewer
```

Builder hanya membaca source build, menulis log dan image. Operator yang
menjalankan `gcloud builds submit` membutuhkan izin Cloud Build Editor,
Artifact Registry Reader, upload ke staging bucket dan `iam.serviceAccounts.actAs`
pada builder. Operator deploy membutuhkan Cloud Run Developer, Artifact Registry
Reader dan Service Account User pada runtime SA; mengubah IAM membutuhkan hak
admin tersendiri. Akun runtime tidak perlu bisa deploy atau mengubah IAM.

## G. Build dan push via Cloud Build

```bash
gcloud builds submit . --config=cloudbuild.yaml \
  --substitutions="_IMAGE=${IMAGE}" \
  --service-account="projects/${PROJECT_ID}/serviceAccounts/${BUILD_EMAIL}" \
  --gcs-source-staging-dir="gs://${PROJECT_ID}-li-build-source/source"
```

Cloud Build membaca Dockerfile, memverifikasi dependency/import dan mendorong
image melalui field `images`. **Tidak perlu `docker push` terpisah**. Builder
standar tidak memiliki GPU; tes CUDA harus dilakukan pada runtime GPU.
Jika `pip check` atau import gagal, build berhenti dan image tidak dipromosikan.
Jangan menghapus lock atau memakai `--no-deps` untuk menutupi resolver error.

Setelah build sukses, ambil digest:

```bash
export IMAGE_DIGEST="$(gcloud artifacts docker images describe "$IMAGE" --format='value(image_summary.digest)')"
export IMAGE_REF="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/engine@${IMAGE_DIGEST}"
printf '%s\n' "$IMAGE_REF"
```

Simpan commit, image digest, build ID dan hasil smoke untuk rollback. Log dependency
build bukan credential; jangan mencetak token/private key pada log.

## H. Deploy pilot privat ke Cloud Run GPU

Konfigurasi awal **usulan pilot**, bukan hasil benchmark kapasitas:1×L4,8vCPU,
32GiB RAM, satu instance maksimum. CPU selalu dialokasikan karena queue Gradio
mengerjakan tugas di background. HTTP concurrency8 memberi ruang SSE/progress,
upload dan health; antrean aplikasi tetap membatasi **satu job engine**.
Concurrency1 pada HTTP dapat menghambat polling/progress selama SSE aktif.

```bash
gcloud run deploy "$SERVICE" --image="$IMAGE_REF" --region="$REGION" \
  --service-account="$RUNTIME_EMAIL" --execution-environment=gen2 \
  --gpu=1 --gpu-type=nvidia-l4 --no-gpu-zonal-redundancy \
  --cpu=8 --memory=32Gi --no-cpu-throttling \
  --concurrency=8 --max-instances=1 --min-instances=0 \
  --timeout=3600 --session-affinity --use-http2 --port=8080 \
  --no-allow-unauthenticated \
  --set-env-vars="LI_RUNTIME_MODE=bundled,LI_AUTH_MODE=adc,LI_ARTIFACT_BUCKET=aretfak-location-intelligence,LI_OUTPUT_DATASET=locdeproject.location_intelligence"
```

Image menjalankan Hypercorn h2c. `--use-http2` penting karena HTTP/1 Cloud Run
membatasi body request32MiB; upload video normal bisa lebih besar. Uji upload
>32MiB melalui ingress sebenarnya tetap wajib. Di arsitektur produksi sebaiknya
upload langsung resumable ke GCS dengan signed URL terbatas; UI kini server-upload.

Layanan privat tidak otomatis terbuka dari browser yang login Google. Untuk uji
pribadi beri akun operator role Cloud Run Invoker pada service, lalu gunakan:

```bash
# Ganti alamat email ini dengan akun operator Anda.
gcloud run services add-iam-policy-binding "$SERVICE" --region="$REGION" --member='user:EMAIL_OPERATOR_ANDA' --role=roles/run.invoker
gcloud run services proxy "$SERVICE" --region="$REGION" --port=8080
```

Buka `http://localhost:8080` dari mesin yang menjalankan proxy. Di Cloud Shell
pakai Web Preview port8080. Jangan memakai URL publik Gradio share pada Cloud Run.
Proxy/jalur browser dapat memiliki batas upload sendiri: uji video nyata. Untuk
multiuser browser, rencanakan IAP/login dan otorisasi per user/target sebelum
membuka akses. Kode toko adalah filter, bukan otorisasi antar pengguna.

`min-instances=0` mengurangi idle cost tetapi cold start dan kehilangan session
lokal tetap mungkin. `min-instances=1` menambah biaya dan tidak menjamin durabilitas.
File pada filesystem Cloud Run bersifat sementara dan ikut memakai memori;
PBF nasional, salinan upload, cache, measurements dan hasil dapat melampaui32GiB.
Jangan menganggap32GiB terbukti cukup. Perlu mengukur RSS+disk+VRAM dan membatasi
admission, atau menyiapkan regional input/cache dan compute dengan disk memadai.

## I. Urutan pengujian sebelum deployment dianggap siap

1. Ulang setup SQL additive, lalu tombol **Periksa kesiapan**; verifikasi sumber
   PBF/model, sumber BQ Area dan tujuan hasil dapat diakses identitas runtime.
2. Uji import image dan `--verify --gpu` pada GPU nyata (VM/container atau
   task smoke GPU terpisah). Cloud Build biasa hanya memeriksa CPU/import.
3. Upload satu video singkat, tinjau geometri, jalankan Traffic. Hitungan tetap
   hasil eksperimen; PPAC BLOCKED karena slot/durasi tidak lengkap adalah benar.
4. Jalankan Area sendiri. Pastikan peta Folium/Esri dan baris `area_results`
   terbaca kembali dari BQ/GCS. Periksa UNVERIFIED dan sumber geometri.
5. Uji8video300–306detik dengan geometri benar. Catat waktu total, RSS proses
   dan child, workspace bytes, VRAM Torch+CuPy+ONNX/NVML, serta batas upload.
   Bandingkan input/config/model yang sama dengan hasil Kaggle; FP32 lintas
   T4/L4 tidak menjamin hasil bit-identik.
6. Verifikasi traffic_counts/area_results/ppac_results untuk job yang sama,
   null/blocked/partial tidak disembunyikan. Simulasikan izin gagal dan retry
   penyimpanan; tidak boleh inference/counting berulang atau hitungan ganda.
7. Tutup browser dan buka hasil job dari BQ lagi. Hasil READY harus dapat dibuka
   pada instance baru. Matikan worker saat job berlangsung untuk menilai kehilangan
   progres; request yang belum dipublikasikan belum tahan restart.
8. Tetapkan budget/alert, log retention, lifecycle artefak, rollback image digest,
   batas antrean/admission, akses pengguna dan prosedur retry.

Sebelum produksi multiuser masih diperlukan antrean persisten + status/checkpoint
job (misalnya Cloud Tasks/PubSub + metadata job), upload persisten sebelum compute,
pemisahan worker GPU/CPU, admission berdasar memori terukur dan penanganan SIGTERM.
BQ adalah rekap analitik, bukan pengganti broker antrean/transactional job store.
Request layanan Cloud Run maksimal60menit; delapan video/Area bisa melampauinya.
Jika benchmark melampaui batas, gunakan worker asinkron/Cloud Run Jobs GPU sesuai
batas task yang berlaku atau GPU VM, dengan UI terpisah. Timeout3600 tidak membuat
job panjang otomatis andal. Satu-instance pilot juga bukan distributed locking.

## Referensi resmi

- [Docker Get Started](https://docs.docker.com/get-started/)
- [Cloud Run GPU: region, resource dan driver](https://cloud.google.com/run/docs/configuring/services/gpu)
- [HTTP/2 h2c](https://cloud.google.com/run/docs/configuring/http2)
- [Cloud Run quotas dan batas upload](https://cloud.google.com/run/quotas)
- [Timeout layanan](https://cloud.google.com/run/docs/configuring/request-timeout)
- [Cloud Build image dan push](https://cloud.google.com/build/docs/building/build-containers)
- [Cloud Run service identity](https://cloud.google.com/run/docs/securing/service-identity)
