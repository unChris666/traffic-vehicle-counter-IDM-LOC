# Status sistem —27 Oktober2026

Dokumen ini menjadi rujukan aktif; checkpoint bertanggal lain menjelaskan kondisi pada scope/tanggalnya. Versi package: **0.6.0rc1**. Tidak ada klaim siap produksi atau ground truth accuracy.

| Bagian | Kondisi kode saat ini | Batas bukti |
|---|---|---|
| Area Coverage | Engine modular mandiri, sumberPBF GCS terikat generation/SHA dan snapshotBQ; persiapan input Sorong otomatis | Parity Area pada sumberbaseline tertentu tersedia; tidak membuktikan semua lokasi/runtime setara |
| Traffic Counter | YOLO26M FP32 batch4, ReID ONNX FP32 IO binding, window8frame/cropbatch32; BoT-SORT berurutan | Totalcount pilot sama; identitastrack berbeda, precision/recall tidak diukur |
| GPU scheduling | Satu video aktif per GPU terlihat; workerprocess baru untuk setiap video; antrean lanjut setelah kegagalan | Unit/integration mock satu/duaGPU lulus; belum ada uji nyata duaGPU baru |
| Integration layer | `KaggleRuntime.execute` -> `_scheduled_tasks` -> `run_video_jobs` -> `run_video` -> `fresh_inference` -> worker kandidat -> counting -> gate -> PPAC | HasilArea/Traffic tetap independen. ReadinessGCS, runtime dan model adalah status terpisah |
| PPAC | Formula referensi tersedia; Residential/Traffic/Fasum/total dipisah di packagePPAC | STD/hari adalah outputformula; prediksi penjualan nyata belum tervalidasi |
| Storage | Adapter/probe/download/hash/cacheGCS diimplementasikan; SecretKaggle `LocatioIntelligent` | Hakakses dan isiobject tetap harus diperiksa pada sesi pengguna |
| UI/VM | Workflow headless dengan UI sementara Gradio pada notebook14 | Deployment produksiVM dan UIproduk belum diverifikasi |

## Upload dan penyimpanan hasil

Gradio menyediakan delapan slot weekday/weekend × pagi/siang/sore/malam, serta enam slot tambahan shift3. Upload memakai staging/hash/inspeksi frame dan tinjauan geometri per video. Template awal dapat diedit pada frame pertama; hari/sesi/arah disimpan eksplisit. Dataset T7SL tetap pilihan contoh. Output job memakai **gs://aretfak-location-intelligence** dan **locdeproject.location_intelligence**; input model/PBF/tabel referensi tetap terpisah. Panel BQ membaca traffic_counts, area_results dan ppac_results berdasarkan job/target; Folium Esri dibaca dari GCS via URI/SHA di area_results. SQL terbaru menambah dua kolom peta nullable pada tabel yang sudah ada. Lima tabel dan dua view disiapkan lewat SQL, bukan dibuat diam-diam saat inference. [Langkah owner dan layout job](CLOUD_STORAGE_SETUP.md). Adapter dan failure/retry diuji dengan transport mock; izin serta CRUD cloud owner belum diverifikasi di environment pengembangan. Publikasi gagal mempertahankan hasil lokal dan tidak menjadi false zero. Pemisahan antrean GPU/CPU dan benchmark kapasitas tetap pekerjaan berikutnya.

## Stabilitas notebook

Perbaikan CI, advisory lock Area, diagnostik resource dan exact-wheel notebook tersedia di0.4.9rc1. [Urutan kerja dan batas validasi](KAGGLE_STABILITY_PLAN.md). Sesi Kaggle yang sedang berjalan tidak otomatis memakai package baru. Angka validasi lama di bawah adalah checkpoint0.4.8, bukan hasil tes rilis ini.

## Pilihan runtime Traffic

CUDA fresh inference memakai `candidate_fp32` secara default. `baseline_fp32` tetap tersedia secara eksplisit; CPU memakai baseline. Filemodel, geometry, policycounting dan seluruhframe dipertahankan. Perubahanbatch dapat mengubah angka floatingpoint sekalipunFP32. Profileterekam dalam request/environment dan identitascache; jangan menganggap cachebaseline sebagai inferencekandidat.

Untuk1GPU, video diproses bergantian. Untuk2GPU, masing-masingGPU menangani satuvideo dan GPU yang bebas mengambil video berikutnya. MaskGPU ditetapkan pada environmentchild; parent tidak diubah. Torch danONNXRuntime pada child memakai local`cuda:0`, merujuk GPUfisik yang dialokasikan. Tidak ada pemecahan satuvideo ke duaGPU. CPU/disk tetap dibagi dan percepatan2x belum terbukti.

## Bukti pilot satuvideo

T7SL-WEEKDAY-PAGI,9015frame, satu run per konfigurasi. Baseline714,84detik, kandidat477,79detik: **hemat33,16% (1,50x)**. Keduanya133kendaraan:112motor,4mobil,2bus,15truk; arah6/127; pending28,invalid11,cancelled10. **Tracklinks dan identitasevent berbeda; gatekesetaraan gagal.** Owner meminta kandidat diadopsi dengan batas ini tetap tercatat. Totalcount sama tidak berarti akurasi100%.

[Reportasli](evidence/traffic_performance/pair_fp32/report.json), [analisis](evidence/traffic_performance/pair_fp32/comparison.md), [runtimeTraffic](TRAFFIC_CANDIDATE_GPU_RUNTIME.md).

## Kontrak PPAC aktif

Notebook memakai `ppac_parameters_mvp_v2`. Residential memakai bangunan yang dialokasikan ke calon toko x4 dengan policyzona40/60 atau35/45/20. Fasum: <=400m +2, >400..800m +1. ProfiljalanPPAC, hari/jamoperasional, drive-thru, SWOT, potonganTraffic dan parkir adalah inputbisnis.

MVP menerima video300–306detik tanpa rescaling; sepeda tidak diwajibkan. LookupResidential/balance dinonaktifkan sesuai keputusanowner; multiplier1 bukan hasil lookup. HasilPARTIAL boleh dipakai sambil mempertahankan kualitasPARTIAL. Kontraksource/context/branch, keutuhanframe dan kelengkapanobservasi tetap divalidasi. Truck secara eksplisit tidak dipakai dalam mappingPPAC saat ini.

**Jam>15 tetap memerlukan sesi tambahan shift3.** Delapanvideo normal tidak cukup untuk PPAC18jam. Engine masih dapat dijalankan; PPACmenungguinput dengan statusBLOCKED/STDnull. Inputgagal/hilang/tidakkompatibel bukan nilai0. Gatev1 lama tetap tersedia dengan syarat lebih ketat.

## Notebook dan cara mencoba

[WorkflowSorong+T7SL diKaggle](https://www.kaggle.com/code/chrisbiran/gate2-t7sl-sorong-integration-quiz) **versi terbaru** memakai [notebook14 Gradio](../notebooks/14_gate2_sorong_t7sl_gradio.ipynb), exactwheel0.5.1rc1 besertaSHA, force-reinstall dan verifikasisource. Server Gradio dapat berjalan saat notebook dijalankan; engine menunggu tombol pengguna.

Buka revisiterbaru, aktifkanGPU danInternet serta Secret`LocatioIntelligent`, jalankan notebook, lalu buka GRADIO_PUBLIC_URL. Isi form -> Periksa kesiapan -> Mulai proses. Pastikan jam<=15 bila hanya memakai8video dan ingin mencobaPPAC. KoordinatSorong: latitude-0.8994976613947719, longitude131.3221639428227. GCSmodel memakai prefix`models/traffic/` terikatSHA.

[Notebookduakonfigurasi](https://www.kaggle.com/code/chrisbiran/t7sl-single-gpu-config-sweep) adalah benchmark terpisah. Ia sengaja menguji satuGPU dan tidak menjalankanArea/PPAC.

## Validasi dan dokumentasi

Rilis kode:208tes lokal selesai,8dilewati; wheel berhasil dibangun. Perbandinganpilot bukan uji baru dualGPU dan bukan evaluasi anotasi. DokumenMarkdown naratif mendapat penunjukstatus; artefakhasil, bukti dan referensihistoris dipertahankan byte-nya agarhash/receipt tetap bermakna. [Inventarisaudit](evidence/documentation_sync_20261027/inventory.json) mencatat seluruhMarkdown pada awalaudit, klasifikasi danchecksum. Dokumen ini ditambahkan setelah inventarisawal.

UI sementara: [Gradio](GRADIO_INTEGRATION_UI.md), source integration/gradio_app.py. Notebook menyalakan server dan mencetak URL publik; engine tetap menunggu tombol pengguna. Notebook11 adalah alternatif kuis klasik.

Arahan terbaru: fokus Kaggle; Docker ditunda. Upload terputus ditangani per-request, tersedia referensi GCS/Kaggle Input per slot. Peta dan tabel ringkas serta asumsi1bangunan=1KK=4penduduk: [pemulihan dan penggunaan](KAGGLE_UPLOAD_RECOVERY.md).

Tampilan hasil terbaru: [BQ, HTML peta GCS dan PPAC terbaca](KAGGLE_READABLE_RESULTS.md).

Kegagalan Area dan renderer dipisah; setup Area child/log dan diagnosis tersedia. [Pemulihan serta batas bukti](AREA_FAILURE_RECOVERY.md).

UI HOME/RESULT, snapshot Save Project dan annotated links: [panduan](HOME_RESULT_UI.md).
