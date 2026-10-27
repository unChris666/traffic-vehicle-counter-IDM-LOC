<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Workflow aktif —27 Oktober2026

Navigasi: [Mulai dari sini](START_HERE.md). Pengembangan pada
`refactor/deployment-foundation`; main hanya dipromosikan melalui PR dan
[gate stabilitas](MERGE_READINESS.md).

Rujukan aktif: [CURRENT_STATUS](CURRENT_STATUS.md). Gate2 sudah menghubungkan Area, Traffic kandidat FP32, dan PPAC modular tanpa mencampur perhitungan analitik. Package0.6.0rc1 dan notebook14 adalah jalur integrasi aktif.

Urutan eksekusi: siapkan/priksa GCS dan runtime, jalankan Area independen, siapkan model Traffic sekali, antrekan video per GPU, validasi hasil, lalu jalankan PPAC bila seluruh input yang diperlukan tersedia. Kegagalan per engine/video dicatat terpisah.

MVP v2 menerima video300–306detik dan hasilPARTIAL; sepeda/lookup Residential serta balance dinonaktifkan sesuai keputusan owner. Untuk jam>15, sesi shift3 tetap wajib. Baseline FP32 masih dapat dipilih eksplisit; adoption kandidat tidak berarti akurasi identitas telah lulus.

Checkpoint0.6.0rc1:279tes,269lulus/10dilewati; pemeriksaan P0 terbaru di MERGE_READINESS. Uji dual-GPU nyata dan ground truth belum tersedia.

UI sementara Gradio tersedia: notebook14 -> URL publik -> input/probe/proses -> runtime yang sama. Publikasi UI tidak menjalankan engine; lihat [panduan](GRADIO_INTEGRATION_UI.md).

## Riwayat keputusan — dibaca menurut tanggal dan scope

# Workflow pengembangan aktif — evaluasi mandiri hingga review UI

**Area actual baseline + modular RC —26 Oktober2026:** tiga bagian input cocok
receipt/SHA;36.536baris direkonsiliasi,22bangunan calon tetap. Source diekstrak
menjadi package, isolated job/typed source-only contract/render/export tersedia.
Fresh GPU T4 version 5 dan source-only RC version 6 cocok baseline.
Engine menerima sumber tanpa hasil lama; unknown tetap dipertahankan. [Scope, gate dan batas](AREA_MODULARIZATION_RELEASE.md). Tidak
mengklaim generalisasi lokasi/produksi atau CPU–GPU equivalence sudah selesai.


**Area migration started —26 Oktober2026:** source freeze dan boundary
artefak freeze/reopen beserta adapter ZIP telah dibuat; full domain migration
belum dimulai karena golden output V5 belum dapat diakses Codex. Collector
read-only ditambahkan ke notebook sukses, tanpa analisis ulang. [Gate, status,
langkah akses dan batas bukti](AREA_MODULARIZATION_PROGRESS.md). Bukan Area RC.


**Audit modularisasi Area —26 Oktober2026:** owner melaporkan notebook sukses;
source Kaggle identik dengan baseline V5. Audit memperbolehkan rencana migrasi
bertahap, dengan gate freeze/verifikasi output aktual sebelum ekstraksi domain.
Package LI4/LI5 belum mewakili seluruh AreaGPU/market. [Temuan,29file rancangan,
M0–M6 dan acceptance criteria](AREA_COVERAGE_MODULARIZATION_AUDIT_20261026.md).
Tidak mengubah implementasi engine atau mengklaim parity/stabilitas produksi.


**Allocation V5 —26 Oktober2026:** POI pemicu <=400m tanpa routing;
kompetitor/Indomaret peserta <=800m. Reuse bagian6 dan rute per node, Huff/core
utuh. Policy allocation berversi terpisah agar cache calculation tetap dapat
dipakai. [Aturan dan batas](AREA_ESRI_GCS_DEVELOPMENT.md).


**PBF provenance recovery —26 Oktober2026:** adapter menambahkan checksum
road-derived features dan validasi dini. Cache legacy utuh dipulihkan ke revisi
lokal baru dengan manifest baru; parent/PBF/extract dipertahankan. Kode error
provenance aman ditampilkan. [Recovery dan batas tes](AREA_ESRI_GCS_DEVELOPMENT.md).


**Area Esri development —25 Oktober2026 (keputusan terbaru):** setup dependency
langsung Kaggle; input analitik PBF generation/SHA GCS + snapshot BQ. PMTiles/
Planetiler dan bundle runtime bukan prasyarat. Browser memakai Esri Imagery/
Street dan CDN Folium; engine tetap GCS/BQ. ZIP hasil diunggah GCS dengan manifest
terakhir. [Langkah, pengujian, batas](AREA_ESRI_GCS_DEVELOPMENT.md). Checkpoint
Google-only/basemap nasional di bawah adalah riwayat yang disupersede untuk
notebook development ini; algoritma business/GPU tidak berubah.

**Basemap nasional —25 Oktober2026:** persiapan runtime kini juga membangun
vector PMTiles Indonesia dari PBF GCS, default native0–14/overzoom20. Runtime
READY hanya setelah basemap READY. Area mengambil range GCS dan meng-inline
tile viewport; tidak membutuhkan tile/CDN eksternal atau CORS/public bucket.
[Profil, resource, batas viewport dan bukti](NATIONAL_BASEMAP_PREPARATION.md).
Fixture Java nyata lulus; Indonesia penuh/upload masih menunggu Run All owner.
Pernyataan basemap pending di checkpoint sebelumnya adalah riwayat sebelum ini.

**Area Google-only —25 Oktober2026:** notebook GPU memakai generation/SHA PBF
GCS yang dilaporkan owner dan BigQuery; tidak Overpass/PyPI/apt/CDN saat run.
Runtime/frontend bundle GCS perlu disiapkan ingestion terpisah; prep otomatis
gagal Secret bootstrap, perlu Run All interaktif. Peta analitik tanpa tile
eksternal, basemap nasional masih pending. [Kontrak, langkah dan batas tes](AREA_GOOGLE_ONLY_NOTEBOOK.md).
PBF_LOCAL_V1 adalah snapshot baru, bukan klaim angka setara Overpass lama.

**Nasional / pengecualian BQ —25 Oktober2026:** owner meminta sumber Indonesia
nasional di GCS, bobot/video/config dan build container terkunci; BQ boleh live.
Owner melaporkan CRUD Kaggle PASS untuk feeder-location-intelligent/us-central1.
[Rencana dan status ingestion](NATIONAL_DATA_DEPLOYMENT_PLAN.md). PBF nasional
tersedia menurut probe HTTP; upload, indeks/adaptor, Overture/basemap nasional
dan container belum terbukti selesai. Hasil BQ per job perlu dipin untuk replay.
Ketentuan ini menggantikan larangan live-BQ pada checkpoint GCS di bawah.

**GCS / engine tanpa provider live —25 Oktober2026:** owner menetapkan data API
disiapkan dahulu dalam GCS; engine menghitung dari input tersimpan. Ingestion
terpisah, GCS staging lokal, snapshot/model/config immutable dan manifest wajib.
[Audit dependency dan langkah onboarding](EXTERNAL_DEPENDENCY_GCS_AUDIT.md).
Basemap/CDN serta unduhan bobot/setup juga masuk audit. ADC Codex belum tersedia;
bucket/IAM/CRUD dan adapter Kaggle-GCS belum diverifikasi. Tidak mempublikasikan
tile jalan yang belum lengkap sebagai snapshot siap pakai.

**Source OSM GPU —25 Oktober2026:** transport adapter memperbaiki retry/subdivisi
tile jalan dan diagnostik publik; tile/date/checksum dipertahankan. Kegagalan
sources bukan kegagalan GPU; endpoint HTTP spesifik pada log owner masih unknown.
Jalan belum lengkap tetap BLOCKED, bukan kosong/sukses. CPU/business baseline
beku dan kernel CUDA tidak berubah. [Aturan recovery dan tes](AREA_COVERAGE_GPU_NOTEBOOK.md).

**Section8 GPU —25 Oktober2026:** window kandidat spekulatif32 dengan pemilihan
valid pertama tetap kanonik; footprint resident dan intersection/threshold GPU.
Smoke Kaggle TeslaT4 aktual PASS pada fixture sintetis, bukan lokasi penuh.
Default `GPU_EXECUTE` menghindari full CPU reference otomatis; output review
berlabel kesetaraan NOT_RUN, handoff NOT_READY. `VALIDATE` tetap wajib sebelum
handoff, dengan uji CPU pada snapshot yang sama. [Bukti dan batas](AREA_COVERAGE_GPU_NOTEBOOK.md).
Checkpoint V2 di bawah mencatat default VALIDATE sebelumnya.

**GPU V2 —25 Oktober2026:** backend notebook GPU ditingkatkan menjadi jarak
kandidat FP64, intersection batch dan weighted routing CUDA; CPU reference wajib
sebelum output/handoff. [Kontrak dan batas](AREA_COVERAGE_GPU_NOTEBOOK.md).
CPU/business baseline b84c850 tetap utuh. Tes oracle lulus, CUDA nyata belum
dieksekusi, dan tidak ada run Kaggle diajukan. V1 reachability saja disupersede.

**Notebook GPU hibrida —25 Oktober2026:** owner meminta notebook Area baru tanpa
perubahan business/perhitungan. [Backend, batas dan setup](AREA_COVERAGE_GPU_NOTEBOOK.md).
CPU baseline b84c850 tetap utuh; traversal/pruning integer disiapkan untuk CUDA,
angka/tie-break tetap kanonik CPU. Belum diuji CUDA nyata dan tidak ada run Kaggle
yang diajukan. Area -> artifact/handoff -> stop proses GPU Area -> Traffic GPU.

**Nearest dan kompetitor 800 m —25 Oktober2026:** owner mengotorisasi nearest
valid entrance untuk bangunan/toko, subset kompetitor <=800 m, primer/sekunder
terpisah, dan reuse rute berdasarkan node akses identik. Skor/keputusan tetap
per bangunan. [Aturan dan pengujian](AREA_COVERAGE_NEAREST_800_CLUSTER.md).
Profil entrance sebelumnya disimpan sebagai baseline; bagian 6 perlu job baru.

**Aturan akses terbaru —25 Oktober2026:** owner memilih skenario barrier/one-way;
izin/tag akses dan larangan belok tidak menjadi pembatas. Unknown yang tersisa
tidak mengesahkan rute. [Profil dan batas](AREA_COVERAGE_BARRIER_ONEWAY_PROFILE.md).
Ini menggantikan kebijakan akses strict hanya untuk job baru berprofil eksplisit;
baseline lama tetap disimpan. Bagian 6 perlu dihitung ulang, sumber dapat dipakai ulang.

**Konektor satu entrance —25 Oktober2026:** owner menetapkan batch per ruas,
maksimal satu entrance asumsi per bangunan, prioritas kelas tertinggi lalu
jarak terdekat; tidak ada entrance fallback jika rute gagal.
[Profil, batas dan pengujian](AREA_COVERAGE_SINGLE_ENTRANCE.md).
Baseline multi-access tetap tersimpan; ini perubahan kebijakan bisnis.

**POI opsional —25 Oktober2026:** jalan/footprint tetap wajib, jaringan memakai
parameter3km; unduhan POI gagal tidak menghentikan pipeline. Gate bisnis attractor
zona luar tetap terpisah dan menjadi UNKNOWN bila bukti tidak tersedia.
[Kontrak dan validasi](AREA_COVERAGE_OPTIONAL_POI.md). Gate tidak dihapus atau
menerima seluruh zona2km secara otomatis.


**Scope sederhana owner —25 Oktober2026:** notebook market default memakai
`ROADS_ONLY_EXPERIMENT`, melewati enam query fitur eksternal. Jalan, node,
arah/izin yang tersedia tetap wajib; rute tidak ada tidak masuk cakupan calon.
[Makna coverage, snapshot dan tes](AREA_COVERAGE_ROADS_ONLY.md). Status model
bukan bukti akses fisik/kelengkapan barrier; mode FULL tetap terpisah.


**Checkpoint market Area Coverage —24 Oktober2026:** owner menetapkan target
-6.190690620514923,106.83819549844226, residential >=36 m², zona hingga2km,
core100m dan alokasi satu rumah utuh dengan skor Huff berbasis routing.
[Aturan, implementasi dan batas eksekusi](AREA_COVERAGE_MARKET_RULES_DRAFT.md).
Snapshot lokasi sebelumnya tidak direlabel. Run CPU aktual terhenti pada source
barrier dan BQ secret; tidak ada angka market target baru yang tervalidasi.

**Checkpoint sumber OSM —24 Oktober2026:** owner mengotorisasi perpindahan ke
OSM buildings→seleksi→OSM motor graph→routing/perhitungan→OSM basemap.
[Profil dan batas validasi](AREA_COVERAGE_OSM_MODE.md). Ini eksperimen sumber
baru; baseline Overture tetap immutable. Toko kompetitor/Indomaret tetap BQ.
Notebook aktif dipelihara langsung; generator Overture lama diblok agar tidak
menimpa provider, autentikasi dan cell audit. Tidak mengesahkan production
accuracy, kelengkapan footprint, atau perubahan aturan bisnis.


**Checkpoint notebook Area Coverage — 24 Oktober 2026:** owner mengotorisasi
prototype Kaggle CPU pada koordinat baru, radius bangunan800m dan layer toko/
kompetitor BigQuery2000m. [Notebook dan scope](AREA_COVERAGE_KAGGLE_CPU_MAP.md).
Ini bukan approval implementasi penuh rencana modularisasi Area. Audit tetap
menunggu persetujuan untuk migrasi package; baseline N1 dan Traffic RC utuh.


**Checkpoint Area Coverage — 24 Oktober 2026:** owner meminta audit kesiapan
modularisasi terlebih dahulu. [Audit Area Coverage](AREA_COVERAGE_MODULARIZATION_READINESS_AUDIT.md)
berstatus **menunggu persetujuan**. Pada scope Area Coverage, instruksi terbaru
ini membatasi pekerjaan pada audit/dokumentasi; implementasi migrasi dimulai
setelah audit disetujui. Traffic RC dan hasil historis tetap dipertahankan.

**Checkpoint implementasi, 24 Oktober 2026:** owner telah mengotorisasi urutan
freeze → kontrak/facade → adapter → domain → runtime/batch → renderer/export/storage
→ release candidate, dengan penyelesaian keputusan teknis secara mandiri.
Audit sebelumnya disetujui untuk dilaksanakan oleh instruksi terbaru ini.
Implementasi berada di branch `refactor/traffic-modularization-v2`; lihat
[catatan migrasi dan gate](TRAFFIC_MODULARIZATION_RELEASE.md).
Algoritma/kernel serta evidence historis tetap immutable. Perubahan angka bukan
bagian refactor ini. Hasil aktual8/8 T7SL kini tersedia; asumsi keberhasilan pada
checkpoint audit terdahulu tidak dipakai sebagai bukti. GCS nyata dan kesiapan
produksi tetap memiliki gate tersendiri.

**Arahan owner, 23 Oktober 2026 (Asia/Jakarta).** Dokumen ini menjadi otoritas
workflow terkini. Bagian roadmap/status lama dipertahankan sebagai riwayat;
larangan melanjutkan hanya karena menunggu approval Markdown tidak lagi menjadi
gate rutin. Batas Markdown-only pada permintaan sebelumnya sudah digantikan oleh
otorisasi implementasi adapter/modularisasi Traffic dan Location serta uji fresh
inference terbatas. Scope dan bukti aktual ada di
[ENGINE_MODULARIZATION_REVIEW](ENGINE_MODULARIZATION_REVIEW.md). Bucket, akun cloud,
UI dan deployment belum diimplementasikan dalam irisan kerja ini.

## 1. Pembagian kerja dan batas otonomi

Owner hanya dapat mereview ketika ada UI untuk input dan melihat output.
Engineer melanjutkan fase berikutnya dengan analisis, keputusan teknis yang
reversible, implementasi bertahap, tes, audit bukti dan laporan mandiri. Jangan
mengulang pertanyaan approval C01–C09 atau meminta polygon manual untuk sekadar
melanjutkan pekerjaan teknis. Gunakan fixture/polygon demo berlabel bila perlu.

C01–C09 pada [kontrak](ENGINE_IO_CONTRACT_DRAFT.md) menjadi **baseline kerja
provisional di bawah delegasi**, bukan klaim owner menyetujui setiap detail atau
hasil eksperimen menjadi standar produksi. Keputusan teknis dicatat beserta
alasan dan dampaknya, kemudian dapat ditinjau pada UI. Schema/API final harus
mengikuti bukti adapter/tes; draft bukan validator yang sudah berjalan.

Jangan mengarang data, bukti akses, labels, formula PPAC, satuan kapasitas atau
akurasi untuk menutup gap. Unknown dipertahankan. Bagian yang bergantung input
bisnis/bukti/credential wajib dapat BLOCKED, sementara bagian independen tetap
berjalan. Persiapan review, tes dan hasil konkret diselesaikan terlebih dahulu.
Jika membutuhkan tindakan pengguna di luar kemampuan engineer, jelaskan alasan
dan panduan spesifik; jangan memaksa review dokumen yang bisa ditunda ke UI.

Delegasi tidak berarti menjalankan pengeluaran cloud atau membuka akses publik
secara diam-diam. Provisioning hanya dilakukan dalam scope yang sudah berizin,
dengan identitas/runtime yang tersedia dan biaya/region yang jelas. Jangan
meminta nilai token/service-account key di chat.

## 2. Requirement stabilitas kedua engine

**REQUIREMENT owner:** angka hasil Area Coverage dan Traffic Counter stabil
ketika pekerjaan yang sama diulang. Requirement tidak dianggap terpenuhi hanya
karena UI menampilkan angka cached yang sama.

Identitas pekerjaan meliputi sumber bytes/snapshot dan coverage, target,
konfigurasi/policy, model/weights, decoder/frame scope, code/schema/environment,
actual execution backend/device profile, dan review/polygon revision jika ada.
Koordinat atau filename saja tidak menjadi fingerprint.

- **Reopen normal:** gunakan manifest finalized yang terikat fingerprint yang
  sama, verifikasi integritas, lalu buka hasil. UI rerender/relogin/retry tidak
  memicu retrieval/inference/routing ulang atau menambah hitungan.
- **Replay:** sumber/config/code/environment terkunci; perhitungan domain harus
  sama. Verifikasi hasil asli, bukan menyamakan nilai setelah terjadi mismatch.
- **Fresh inference reproducibility:** diuji terpisah pada backend/device yang
  direkam. Jangan mengklaim inference stabil hanya dari detector-cache replay.
- **Refresh:** eksplisit, input/source/config yang berubah menghasilkan versi
  baru dan delta; tidak menimpa baseline atau silently mengubah hasil tersimpan.

Definisi gate dan bukti: [REPRODUCIBILITY_POLICY](REPRODUCIBILITY_POLICY.md).
Status saat ini: LI-3/LI-4/LI-5 mempunyai bukti replay scoped; Traffic fresh
inference/CPU/GPU/night/generalization tidak otomatis ikut PASS.

## 3. Batas modul yang dipertahankan

Satu repo, dua domain engine: Traffic dan Location. Modul bisnis/PPAC adalah
konsumen terpisah. Backend mengatur auth/job/state/storage; UI mengirim input,
menampilkan hasil/diagnostics dan review; keduanya tidak menduplikasi counting
atau routing. Config dan storage melalui interface terpisah dari algoritme.

Traffic menjaga unit/passage/BC/source-frame/role/identity safeguards dan
measured-estimated split. Location menjaga coverage/source/accessibility/
capacity units dan Recount provenance. Machine/reviewed adalah alternatif
snapshot. Refactor tidak boleh sekaligus mengubah algoritme tanpa eksperimen
versi terpisah. GPU/CPU provider dicatat; no silent model/frame/ReID fallback.

## 4. Urutan kerja aktif menuju UI

| Milestone | Pekerjaan mandiri | Gate/hasil konkret |
|---|---|---|
| M1 — contracts dan adapter | Machine-readable schemas, validators, adapters ke retained Traffic/Location outputs; working contract versions | Negative fixtures, null/status/branch/unit/provenance checks dan golden parity; keputusan provisional tercatat |
| M2 — modularisasi | Pisahkan domain Traffic/Location, config, orchestration dan storage adapters; CLI/API boundary | Hasil domain sama pada input terkunci; engine tidak tergantung UI; reproducibility tests PASS dalam scope |
| M3 — backend/job | Input validation, idempotency, queue/state/progress/retry/cancellation, result lookup | Tidak ada duplicate counting akibat retry; failures tidak sukses; finalized results persisten |
| M4 — GCS integration | Pandu owner setup project/bucket/identity ketika dependency storage nyata tiba; implement CRUD adapter dan tes sandbox | CRUD test object+generation/checksum/access tests, no public bucket, hasil lama immutable; metadata DB dievaluasi terpisah |
| M5 — UI review | Target/input video, config geometri/filter, job progress, map/video/table, measured/estimated/partial diagnostics, revisions/export | Owner bisa input dan melihat output nyata; replay/demo diberi label; fitur belum wired tidak disamarkan sebagai live processing |
| M6 — staging/deployment | Container/runtime CPU/GPU yang sesuai, health/jobs/restart/storage/auth tests | Scope tervalidasi dan keterbatasan terlihat; bukan production release hanya karena UI bisa dibuka |

Implement UI minimum boleh dimulai bertahap setelah adapter yang diperlukan
tersedia; tidak menunggu owner mereview Markdown/manual polygon. Stage awal
boleh membaca hasil retained dengan label jelas sambil proses baru diintegrasikan.
Jangan menampilkan tombol seolah memproses data jika backend hanya replay.
Validasi kualitas Traffic malam/identitas dan Location unknown/source berjalan
paralel secara agenda, bukan izin implisit untuk multi-agent atau multi-GPU.

Nomor fase Traffic0–13 dan LI0–7 tetap untuk melacak pekerjaan. M1–M6 adalah
milestone integrasi, bukan mengganti angka fase atau menyatakan semua gate
produksi sebelumnya selesai. LI-6 features/PPAC dapat dipersiapkan interface-nya;
angka bisnis tetap BLOCKED bila formula/unit/period wajib belum tersedia.

## 5. Penyimpanan dan review berikutnya

**KEPUTUSAN owner:** Google Cloud Storage untuk video dan artefak hasil.
GCS adalah object storage, bukan keputusan memilih database relasional.
Database metadata/job/user, framework UI/API, compute/GPU provider, region,
billing/bucket names, IAM identities, retention dan deployment belum dipilih
secara final. Engineer mengevaluasi pilihan teknis dalam milestone terkait.

[GCS_STORAGE_ONBOARDING_PLAN](GCS_STORAGE_ONBOARDING_PLAN.md) menyiapkan panduan
saat M4; sekarang belum membuat bucket atau menjalankan CRUD. Local adapter
untuk pengembangan tidak boleh dilabel sebagai integrasi GCS terverifikasi.

Review owner berikutnya berbasis UI: input aktual, hasil per engine, scope,
unknown/estimated/partial, perubahan konfigurasi dan versi, bukti passage/
bangunan, export dan pembukaan hasil ulang. Siapkan contoh before/after dan
failure cases yang benar-benar terjadi. Engineer melaporkan pekerjaan selesai,
bukti tes, batas klaim dan tindakan owner yang benar-benar diperlukan.
