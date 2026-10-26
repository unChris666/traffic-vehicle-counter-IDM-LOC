<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

## Status implementasi aktif

Gate2 kini mempunyai facadeArea/Traffic, PPACmodular, validasi dan workflowheadless. MigrasiArea dan coreTraffic tersedia dalam package0.4.7rc1. KandidatTraffic diadopsi dengan batas kesetaraantrack yang diketahui. Statusblocked historis di bawah dibaca menurut gate/tanggalnya; bukan bukti bahwa seluruh modul saat ini belum dibuat.

## Konteks dan kontrak terdahulu

# Review modularisasi Traffic dan Location — 23 Oktober 2026

**Scope:** implementasi irisan pertama modularisasi yang diminta owner, dengan
perilaku domain dipertahankan. Ini bukan persetujuan kualitas produksi, UI,
backend, GCS atau model baru. Notebook, manifest dan hasil historis tetap utuh.

## Yang diimplementasikan

Package `src/traffic_location` memisahkan dua engine. CLI berjalan tanpa
menambahkan `notebooks/` ke import path. Schema JSON versi pertama dan validator
domain tersedia; ini boundary lokal untuk artefak frozen, belum API publik/job.

| Gate | Implementasi | Bukti yang harus diperiksa |
|---|---|---|
| Profil eksplisit | `machine`, `review_assisted`; operasi `replay` wajib menyebut branch | Validator dan negative tests menolak overlay/adjudikasi baru pada machine |
| Adapter Traffic | Measurement notebook asli, policy efektif, geometri, review berbukti, native passage dan ringkasan versi baru | Raw detection link, BC, source identity, urutan dan jumlah frame diverifikasi |
| Acuan per branch | Registry hash seluruh field hasil native dan policy efektif | Event ID, kategori, arah, measured/inferred, keputusan pending/invalid, assignments dan agregat dibandingkan |
| Batas pilot | Public request mewajibkan `video_id`, `frame_count`, native dimensions dan hash | Prefix teknis 32 frame dengan ID job berbeda diuji; batas bukti review tetap diperiksa |
| Isolasi state | Identity/counting dibangun per pemanggilan; inference satu proses baru per job | Repetisi, urutan A/B dan sumber input tidak termutasi |
| Dependensi versi | Kernel lokal bernama geometry/identity/eligibility/publication/reviews | Tidak mengimpor batch/notebook saat runtime; registry extraction mempertahankan asal algoritme |
| Renderer | Entry point frame/timeline/video hanya mengonsumsi hasil tersimpan | Frame aktual setara piksel dan state panel dengan renderer lama; event tidak berubah |
| Location | Adapter LI4 frozen → selection/capacity; adapter LI5 → Recount | Selection/capacity/membership setara baseline; revision baru mempunyai identitas kode baru |
| Publikasi | Direktori hasil immutable, staging + validasi manifest sebelum rename | Kegagalan ekspor/tamper/berkas tambahan ditolak; reopen tidak membutuhkan inference |

Urutan domain Traffic tetap: kontrak/config → measurement → geometri/identity/
counting/agregasi → review finalization → output. Renderer terpisah dari keputusan.
Orchestration fresh inference menyediakan proses terisolasi dengan runtime dan
asset hash eksplisit; tidak mengubah replay menjadi inference secara diam-diam.

## Makna branch dan hasil acuan

| Acuan pilot TGDI-WEEKDAY-SIANG | Accepted | Measured | Estimated native `inferred` | Pending | Invalid |
|---|---:|---:|---:|---:|---:|
| B v7 machine | 72 | 66 | 6 | 24 | 86 |
| B v8 review-assisted | 74 | 67 | 7 | 1 | 83 |

Ini alternatif snapshot, tidak dijumlahkan. **Konteks review historis 4149 sudah
ada pada sumber baseline machine lama.** Adapter mempertahankannya secara
eksplisit melalui pasangan `baseline_reviews` + `historical_baseline` terikat
hash. Output menandai `legacy_baseline_review_context_present=true`. Angka machine
ini tidak boleh dipresentasikan sebagai eksperimen tanpa keterlibatan review
apa pun. Review baru hanya diterapkan melalui profil review-assisted dengan
overlay, bukti sumber dan baseline adjudikasi yang terikat.

Field native, status, event ID dan istilah `inferred` tidak diubah. Ringkasan
boundary menyajikannya sebagai `accepted_estimated`; estimasi tidak menjadi
crossing terukur. Pending/invalid dikeluarkan dari accepted. Kualitas pilot tetap
`PARTIAL`, walaupun eksekusi `SUCCEEDED`.

## Location: kesetaraan tanpa mengubah backend geometri

Sumber adalah paket LI4 N1 yang dibekukan dan paket Recount LI5 R1/R2, bukan
pengambilan Overture/OSM baru. Seluruh 2.623 baris direkonsiliasi: 1.322 selected
dan 1.301 tidak selected. Keputusan akses/routing tersimpan tetap dipertahankan:
641 accepted skenario, 620 akses unverified, 54 tanpa konektor valid, 7 over-time.
**Tidak melakukan routing baru pada irisan ini.**

Selection/capacity tetap memakai runtime GDAL/OGR lama; Recount memakai runtime
Shapely/PyProj yang direkam. Jangan menggantinya dengan backend geometri lain
saat refactor. Unknown tetap punya status/null, kapasitas unit berbeda tidak
dijumlahkan. Nilai standar rumah4 tetap bersatuan belum disahkan; bukan KK atau
populasi tervalidasi.

Recount R1 memiliki union663 dan R2 union1.072. Delta geometrinya409 entered,
0 exited. Source status seluruh baris tidak berubah. Hash kode dan result version
modul baru memang berbeda dari engine notebook; seluruh field domain lainnya
serta membership dibandingkan tanpa toleransi yang menyembunyikan keputusan.
Delta baru hanya diterima dari hasil modul dengan source/policy/software/kode
yang sama. Hasil lama tidak diberi hash baru agar terlihat sama.

## Fresh inference: scope terpisah

Uji nyata menggunakan prefix32 frame sumber TGDI-WEEKDAY-SIANG, YOLO26M,
BoT-SORT dan encoder ReID eksternal `yolo26n-reid.onnx` pada **CPU**, RAW FP32,
seed0, threads4 dan Ultralytics8.4.175. Request, asset SHA, runtime aktual,
measurement dan receipt repetisi ada di direktori bukti. Tidak mematikan ReID.
Encoder person-domain tersebut tetap kontrol eksperimen, bukan vehicle-ReID
produksi yang sudah disahkan.

`fresh_inference_result_v1` adalah kontrak measurement eksperimen terpisah.
Belum dihubungkan otomatis ke adapter cache notebook `retained_phase_8_detection`.
Menambahkan bridge itu membutuhkan binding frame/provenance/policy baru dan uji
counting tersendiri; jangan mengganti label provenance agar adapter menerimanya.
Tidak ada uji GPU lokal karena CUDA tidak tersedia. Ini juga belum benchmark
full-video CPU, real-time, generalisasi malam atau bukti akurasi.

Uji renderer menemukan random seek pada sumber codec ini tidak identik piksel
dengan decode berurutan. Pembacaan berurutan cocok dengan hash frame cache.
Pengaman hash tidak dilonggarkan; renderer video tetap decode berurutan. Uji
frame1089 memeriksa output dan state panel lama versus modul baru. Full-video
encode baru tidak dijalankan hanya untuk membuktikan ekstraksi renderer.

## Kesiapan dan pekerjaan berikutnya

**HASIL EKSPERIMEN:** 51 kasus tes unik lulus pada runtime yang sesuai (54
eksekusi karena tiga tes snapshot dijalankan di dua runtime). Enam replay Traffic
penuh lulus: tiga per branch,9.128 frame per replay, seluruh field native sama
dengan golden dan versi hasil stabil dalam setiap branch. Selection/capacity
serta masing-masing Recount R1/R2 juga identik dalam tiga pengulangan.
Tiga proses fresh CPU menghasilkan measurement32 frame yang sama; smoke tambahan
melalui orchestration juga cocok. Request CUDA di mesin tanpa GPU gagal dengan
alasan eksplisit, tanpa output sukses/fallback CPU. Wheel berhasil dibangun,
diimpor di luar repo, dan dapat reopen hasil tanpa notebook/model runtime.

Runtime dicatat pada boundary. Selection mengikat Python/GDAL/GEOS/PROJ;
bundle Recount menambahkan Python di atas software geometri native. Versi
bundle memuat runtime dan referensi previous bila ada. Ini tidak menjanjikan
kesetaraan pada perangkat/backend yang belum diuji.

Traffic sudah mempunyai boundary untuk modularisasi bertahap berbasis frozen
measurement. Kernel berlapis masih mempertahankan urutan algoritme versi lama
secara internal untuk kesetaraan; ini penghilangan dependensi notebook, belum
penyederhanaan seluruh algoritme. Default pilot privat yang dipertahankan saat
ekstraksi tidak digunakan facade publik, yang selalu mengirim input eksplisit.

**Gate engineering modularisasi berbeda dari gate kualitas QC P0.** Kasus
identitas4843 pada machine, final vehicle-ReID, benchmark berlabel, kualitas
malam dan generalisasi tetap belum selesai. Kesetaraan dapat mempertahankan
kesalahan baseline; tidak membuktikan hitungan benar. Tidak ada klaim zero mistakes.

Berikutnya: bridge measurement fresh yang diuji terpisah; migrasi routing Location
secara parity; kemudian backend idempotent/job dan UI review. GCS mengikuti
milestone onboarding tersendiri. Tidak perlu meminta owner menyetujui ulang
threshold lama hanya untuk melanjutkan irisan teknis yang reversible.

Perintah, hasil pengujian dan status aktual: [paket bukti](../results/engine_modularization/README.md).
