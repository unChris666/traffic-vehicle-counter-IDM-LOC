<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Status implementasi migrasi Area —26 Oktober2026

> Pembaruan: baseline aktual sudah diterima/diverifikasi dan migrasi dilanjutkan.
> Lihat [release candidate dan bukti aktual](AREA_MODULARIZATION_RELEASE.md).
> Isi berikut adalah checkpoint historis sebelum upload tiga bagian ZIP.


Instruksi owner: freeze -> kontrak/facade -> adapter -> domain/backend ->
runtime/job -> renderer/export/storage -> release candidate. Implementasi
mematuhi gate audit: output aktual wajib diverifikasi sebelum algoritme domain
dipindahkan. **Alur tersebut belum selesai end-to-end; tidak ada klaim Area RC.**

## Pekerjaan konkret yang diselesaikan

- Freeze source baseline V5: inventory35helper dan hash; algoritme yang sukses
  tetap di notebook, tidak dipindah/ditimpa tanpa golden output.
- Boundary `traffic_location.location.area`: request artefak typed/berversi,
  result boundary, local artifact refs, facade freeze/reopen dan CLI mandiri.
  Ini kontrak operasi artefak; kontrak fresh compute/replay belum dirilis.
- Adapter ZIP V5: validasi path/duplikasi/symlink/encryption, limit ekspansi50GiB
  eksplisit, outer SHA, manifest sumber/network/calculation/market, native
  fingerprint+config+pilot binding, denominator, ID, agregat/skor dan CSV IDs.
  Tidak mengimpor notebook, CUDA, GDAL atau Google untuk reopen.
- Freeze lokal atomik dan idempotent; baseline asli tidak diubah. Receipt
  menyimpan hashes kode/input, bukan mengklaim business accuracy. Result version
  mengikat bytesZIP/native identity/schema dan adapter implementation.
- Unknown/null, PARTIAL dan unit kapasitas dipertahankan. Equivalence tidak
  menjadi PASS hanya karena notebook selesai; reproducibility NOT_VERIFIED.
- Cell koleksi hasil read-only ditambahkan sebelum handoff terakhir pada draft
  notebook berhasil. Semua cell/helper engine yang lama byte-identical.
  Cell hanya menyalin ZIP lokal sukses + receipt field allowlist, tanpa routing,
  acquisition atau model. STAGES output belum sukses tidak mengekspor cache lama.
- Registry ekstraksi LI4 lama menunjuk source notebook yang berubah sesudah
  ekstraksi. Byte asli dengan hash tercatat ditemukan pada commit f83fc4a5 dan
  diarsipkan immutable. Registry sekarang menunjuk arsip tersebut, hash/module/
  algoritme lama tidak diubah. Tidak menyatakan N1 telah setara V5.

## Gate dan status yang jujur

| Tahap | Status |
|---|---|
| M0 source freeze | DONE |
| M0 output sukses aktual | BLOCKED_INPUT_ACCESS: ADC Codex unavailable, API Kaggle retained outputs kosong |
| M1 kontrak/facade | Artifact freeze/reopen diimplementasikan; full compute contract belum dirilis |
| M2 adapter | ZIP retained V5 diimplementasikan dan diuji fixture; penerimaan data aktual menunggu M0 |
| M3 domain/backend | NOT_STARTED: menunggu golden output aktual, sesuai audit |
| M4 runtime/job | NOT_STARTED untuk full computation |
| M5 renderer/export/storage | Belum dimigrasikan; implementasi baseline dipertahankan |
| M6 release candidate | NOT_READY; tidak ada production approval atau klaim parity aktual |

Tidak membuat29file kosong agar migrasi terlihat selesai. Tidak menjalankan
ulang analisis mahal untuk mengatasi masalah akses artefak. Tidak mengirim key
service account atau mengubah bucket privat menjadi publik.

## Satu tindakan untuk membuka gate

Buka https://www.kaggle.com/code/chrisbiran/area-coverage-market-gpu-hybrid/edit.
Muat draft baru pada session sukses yang masih hidup; **jangan restart session
atau Run All**. Jalankan hanya cell baru **Freeze acuan modularisasi — tanpa
menjalankan ulang analisis**. Keluaran:

```
/kaggle/working/area_modular_baseline_export/baseline.zip
/kaggle/working/area_modular_baseline_export/receipt.json
```

Keduanya input yang perlu tersedia bagi proses migrasi. ZIP berisi snapshot BQ
privat: jangan commit/public upload. Bila disediakan melalui artifact channel
privat atau output Kaggle yang dapat diakses API, Codex bisa memverifikasi dan
melanjutkan gate. Bila session telah berakhir, file lokal hilang; pengambilan
kembali ZIP dari GCS dengan credentials di Kaggle adalah langkah pemulihan,
bukan menjalankan ulang analisis. URI manifest saja tidak memberi Codex izin
baca bucket; environment belum mempunyai ADC/outbound GCP identity.

Tidak perlu mereview kode/polygon untuk ini. Satu langkah tersebut diperlukan
karena kontrol runtime interaktif Kaggle dan credentials GCP tidak tersedia
melalui koneksi Codex saat ini; ini dependency akses bukti, bukan approval skill.

## CLI setelah ZIP tersedia

Di environment yang memasang package repository:

```bash
python tools/area_artifact_request.py /path/privat/baseline.zip > /tmp/area-freeze.json
python -m traffic_location.location.area freeze --request /tmp/area-freeze.json --output /path/privat/frozen-area
python tools/area_artifact_request.py /path/privat/frozen-area/baseline.zip --operation reopen > /tmp/area-reopen.json
python -m traffic_location.location.area reopen --request /tmp/area-reopen.json
```

Outer SHA request harus dicocokkan dengan receipt hasil asli sebelum menerima
baseline sebagai golden. CLI tidak melakukan fresh routing/inference atau
mengunggah hasil bisnis. Jangan menganggap freeze fixture sebagai golden aktual.

## Verifikasi yang benar-benar dijalankan

-7tes baru: freeze/reopen tiga pengulangan fixture yang sama, preserved null/
PARTIAL, idempotence, wrong policy/schema/hash, unsafe ZIP/path, corrupt manifest,
no publish on failure, collector sukses/gagal dan tidak menyerialkan globals.
- Suite package114tes:105lulus,9skip sesudah registry historis dipin.
- Suite notebook Area184tes:169lulus,15skip.
- Ruff undefined-name checks PASS pada modules baru/tools; original engine
  cell sources identik sebelum/sesudah menghapus dua cell collector baru.
- Tes memakai fixture sintetis berlabel; **bukan** parity output V5 aktual,
  bukan tiga freshGPU run, bukan cloud credentials/bucket CRUD test baru.

Bukti lokal pada results/area_modularization/20261026. Tidak ada test count atau
fixture count yang dipresentasikan sebagai kualitas hasil bisnis.
