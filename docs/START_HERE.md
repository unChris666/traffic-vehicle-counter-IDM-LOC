# Mulai dari sini

Rujukan navigasi aktif, 27 Oktober 2026 (Asia/Jakarta). Package **0.6.0rc1**.
Branch konsolidasi: **`refactor/deployment-foundation`**, berawal dari
`e077672` pada `fix/kaggle-runtime-stability`. Ini kandidat pengembangan,
belum rilis stabil atau bukti siap deployment. `main` dipromosikan melalui PR
setelah pemeriksaan; development dilakukan pada branch lain.

## Pilih tujuan

| Tujuan | Mulai di sini |
| --- | --- |
| Mencoba aplikasi di Kaggle | [Notebook aktif](../notebooks/14_gate2_sorong_t7sl_gradio.ipynb), [panduan HOME/RESULT](HOME_RESULT_UI.md) |
| Menemukan kode engine | Peta package dan entry point di bawah |
| Memahami branch | [Audit branch](BRANCH_INVENTORY.md), [kebijakan main](BRANCH_POLICY.md) |
| Melihat bukti dan pekerjaan yang tertunda | [Pemeriksaan sebelum merge](MERGE_READINESS.md), [status sistem](CURRENT_STATUS.md) |
| Menangani Area gagal/peta kosong | [Diagnosis Area](AREA_FAILURE_RECOVERY.md) |
| Memeriksa setup GCS/BQ | [Setup cloud](CLOUD_STORAGE_SETUP.md), [SQL](../sql/location_intelligence_setup.sql) |
| Menyiapkan deployment berikutnya | [Panduan Docker/Cloud Run](DOCKER_CLOUD_RUN_GUIDE.md); belum bukti deployment lulus |

## Peta kode aktif

Tidak ada pemindahan package pada tahap P0. Gunakan path berikut untuk
pengembangan; folder riset dan referensi lama tetap disimpan.

| Bagian | Package/file aktif | Tanggung jawab |
| --- | --- | --- |
| Traffic Counter | [traffic/](../src/traffic_location/traffic/) | Inference, tracking, counting, artefak dan scheduling Traffic |
| Area Coverage | [location/area/](../src/traffic_location/location/area/) | Input snapshot, routing/alokasi, hasil Area dan peta |
| PPAC | [ppac/](../src/traffic_location/ppac/) | Residential, Traffic, Fasum dan agregasi STD |
| Integrasi | [integration/](../src/traffic_location/integration/) | Menjalankan engine, gate PPAC, publikasi dan pembacaan hasil |
| UI Kaggle | [gradio_app.py](../src/traffic_location/integration/gradio_app.py) | Form HOME, RESULT, callback dan diagnosis |
| BE produksi | Belum tersedia sebagai layanan API/job terpisah | Workflow headless sudah ada; antrean job durable/API produksi belum tersedia |
| FE produksi | Belum tersedia | Gradio adalah UI sementara; React/Next.js masih rekomendasi |
| Notebook | [notebooks/](../notebooks/) | Bootstrap dan eksperimen; notebook14 adalah jalur UI aktif |
| Docs | [docs/](./) | Halaman ini dan status aktif mendahului checkpoint historis |
| Deployment | [deploy/](../deploy/), [Dockerfile](../Dockerfile), [cloudbuild.yaml](../cloudbuild.yaml) | Recipe dan lock dependency; validasi runtime final belum lengkap |
| Validasi | [tests/](../tests/), [CI](../.github/workflows/traffic-migration.yml) | Kontrak, regresi, build dan wheel smoke |

Di Traffic, `domain/` memuat aturan analitik, `adapters/` menghubungkan model,
`contracts/` memvalidasi I/O, `application/` menyediakan facade. Area memakai
`application/`, `domain/`, `sources/`, `backends/`, dan `outputs/`.
`_kernel/` menyimpan implementasi referensi yang dibekukan; jangan mengubahnya
untuk merapikan struktur. `counter-ppac/` adalah referensi formula lama;
runtime memakai `src/traffic_location/ppac/`. Folder `results/` dan
`docs/evidence/` menyimpan bukti bertanggal, bukan entry point aplikasi.

## Entry point dan aliran I/O

| Kebutuhan | Entry point | Input → output |
| --- | --- | --- |
| Aplikasi Kaggle | `integration.gradio_app.launch(...)` melalui notebook14 | Identity, koordinat, video/geometri, parameter → status dan hasil tersimpan |
| Runtime Kaggle | `integration.kaggle_runtime.KaggleRuntime.execute(...)` | Mode, parameter, subset video yang ditinjau → hasil engine independen, gate PPAC dan publikasi |
| Workflow headless | `python -m traffic_location.integration --help` | Request JSON + root/output; operasi `area`, `traffic`, `ppac`, `run`, `reopen` |
| Traffic fresh inference | `traffic.application.runtime.fresh_inference(...)` | Request sumber/model/config terikat checksum → measurement worker |
| Traffic counting | `traffic.application.pipeline.process_video(...)` | Request bertipe + measurement/geometri/policy → hasil counting; bukan inference baru |
| Traffic batch replay | `traffic.application.batch.run_batch(...)` | Kontrak batch khusus delapan sumber terkunci → agregat; berbeda dari UI subset video |
| Area compute | `location.area.application.pipeline.execute(request, output)` | Request v2/snapshot sumber → worker terisolasi, hasil/receipt dan presentasi bila diminta |
| Area CLI | `python -m traffic_location.location.area --help` | Operasi `execute`, `freeze`, `reopen`; persyaratan request berbeda per operasi |
| PPAC | `ppac.service.calculate(features, parameters)` | Fitur upstream dan policy eksplisit → breakdown dan STD; observasi tidak lengkap ditolak |
| Publikasi | `integration.cloud_publish.CloudPublisher` | Artefak lokal → object GCS, manifest dan baris BQ per job |
| Baca hasil | `integration.cloud_results.ResultsReader` | Target/job → tabel BQ serta artefak GCS yang diverifikasi |

Alur UI: input → staging/inspeksi video → review geometri → engine Area/Traffic
→ gate kelengkapan → PPAC → publikasi → RESULT. Traffic dapat memakai subset
video. PPAC memerlukan observasi yang diwajibkan policy; input hilang bukan nol.
Kegagalan renderer peta terpisah dari kegagalan perhitungan Area. Status PPAC
`REQUIRED_ENGINE_UNAVAILABLE` perlu ditelusuri ke diagnosis engine upstream.

`traffic-location --help` adalah CLI tingkat package. Jangan menganggap
`location-selection`/`location-recount` legacy di CLI itu sebagai jalur fresh
Area Coverage yang sama; jalur Area aktif ada pada package `location.area`.

## Notebook aktif dan notebook khusus

| Notebook | Peran |
| --- | --- |
| [14_gate2_sorong_t7sl_gradio.ipynb](../notebooks/14_gate2_sorong_t7sl_gradio.ipynb) | **Utama**: HOME/RESULT, Area, Traffic, PPAC, GCS/BQ |
| [11_gate2_t7sl_sorong_quiz.ipynb](../notebooks/11_gate2_t7sl_sorong_quiz.ipynb) | Alternatif kuis/headless; bukan UI utama |
| [area_modular_v5_frozen_parity.ipynb](../notebooks/area_modular_v5_frozen_parity.ipynb) | Validasi Area pada snapshot beku; bukan alur upload pengguna |
| [10_t7sl_readable_resume.ipynb](../notebooks/10_t7sl_readable_resume.ipynb) | Workflow Traffic khusus; bukan aplikasi integrasi aktif |
| [indonesia_gcs_source_ingestion.ipynb](../notebooks/indonesia_gcs_source_ingestion.ipynb) | Persiapan sumber; bukan proses job pengguna |

Notebook riset lain dipertahankan dengan scope/tanggalnya; jangan memilihnya
sebagai versi aplikasi hanya karena nama file atau nomor versi Kaggle.
Notebook utama sudah dipublikasikan di
[Kaggle Gate2](https://www.kaggle.com/code/chrisbiran/gate2-t7sl-sorong-integration-quiz),
versi14 pada checkpoint terakhir. Aktifkan GPU, Internet, dan akses Secret
`LocatioIntelligent`. Setelah Run All, UI menunggu aksi pengguna; startup UI
tidak membuktikan engine berhasil. Kode tertanam notebook11/14 harus dibangun
ulang dan diverifikasi terhadap package bila source Python berubah.

## Penyimpanan dan batas validasi

Output besar: `gs://aretfak-location-intelligence/jobs/<target>/<period>/job_<uuid>/`.
Metadata Save Project: `projects/<KDTK>/<period>/<uuid>.json`; video browser
tidak otomatis disimpan oleh Save Project. Rekap: dataset
`locdeproject.location_intelligence`, tabel `job_runs`, `traffic_videos`,
`traffic_counts`, `area_results`, `ppac_results`. Input model/PBF/reference
berasal dari sumber terpisah; jangan mengganti sumber input dengan bucket output.

Checkpoint0.6.0rc1 sebelumnya:279tes,269lulus/10skip, mypy14file dan CI lulus;
UI Kaggle HTTP200. [Pemeriksaan P0 terbaru](MERGE_READINESS.md) mencatat hasil
ulang pada branch konsolidasi. Tes software bukan bukti akurasi atau produksi.

Masih perlu bukti: penyebab kegagalan Area pada sesi owner beserta run sukses
dan peta tersimpan; CRUD cloud end-to-end dengan identitas runtime owner;
render8video/capacity RAM/disk; pemisahan antrean GPU/CPU; image final non-root
dan runtime GPU. Belum ada BE/FE produksi atau deployment cloud terverifikasi.

Dokumen lama dapat menyebut versi dan jumlah tes terdahulu. Itu checkpoint
historis, bukan status rilis aktif. Jangan menimpa bukti/checksum historis.
