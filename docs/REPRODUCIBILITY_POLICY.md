<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

## Status implementasi aktif

Profilcandidate_fp32 adalah keputusanadoption owner27Oktober2026, bukan klaim kesetaraan denganbaseline. Pilot menunjukkan aggregate sama tetapi tracklinks/identitasevent berbeda. Reproducibility dinilai untuk sumber+model+kode+runtime+profile yang sama; cache bukan uji ulang determinisme. AssignmentGPU dan perubahanprofile terikatidentitascache.

## Konteks dan kontrak terdahulu

# Stabilitas hasil — Traffic dan Location

23 Oktober 2026. **Requirement owner**, berlaku pada pengembangan menuju UI.
Spesifikasi gate berikut adalah desain kerja untuk implementasi/validasi,
bukan klaim semua tests atau deterministic inference sudah terlaksana.

## Hasil yang harus stabil

| Domain | Kalkulasi yang dibandingkan |
|---|---|
| Traffic | Source frame coverage; keputusan per passage/episode dan sumber bukti; kategori/arah; measured/estimated; pending/invalid/non-unit; dedup groups dan agregat dalam branch yang sama |
| Location Area | Selected/excluded/rejected source rows; status bangunan, kandidat/rute terpilih, waktu/threshold, capacity per unit dan unknown; coverage/source warnings |
| Location Recount | Membership per source key/polygon, union, subtotal per status/unit dan delta untuk revision refs yang sama |

Job ID, wall-clock timings, timestamp pembuatan, upload metadata, video-container
encoding bytes atau ordering log tidak otomatis bagian kesetaraan kalkulasi.
Native frame/PTS/source observations dan source IDs tetap terikat bukti. Event
identity yang dapat memengaruhi dedup/aggregation tidak boleh diabaikan hanya
agar perbandingan terlihat sama. Video annotation dibandingkan isi audit dan
frame alignment; byte-identical codec/container perlu klaim terpisah.

## Fingerprint dan operasi

Fingerprint mengikat source bytes+snapshot/provider/release/as-of+coverage,
target, policy/config, model assets/labels/weights, frame/decoder/preprocessing,
code/schema/environment hashes, device/backend/provider dan polygon/review
revision. Resource run berbeda boleh memiliki job_id baru, tetapi result
lookup normal mengacu pada logical result yang sama bila fingerprint sama.

FROZEN adalah mode normal. Reopen memakai finalized artifacts; replay memakai
retained inputs tanpa retrieval. REFRESH atau perubahan config/model/source/
review/polygon/backend yang relevan adalah versi baru dengan delta eksplisit.
Tidak mengedit fingerprint agar input berbeda terlihat sebagai run sama.

## Gate implementasi mandiri

1. Validasi manifest/bytes/hash sebelum proses/reopen. Matching environment
   wajib untuk replay/fresh calculation. Membaca finalized outputs tidak
   membutuhkan model/GPU/engine runtime lama terpasang, selama schema adapter
   mendukung formatnya dan artifact integrity terverifikasi; jangan menjalankan
   ulang inference hanya untuk menampilkan hasil.
2. Canonical ordering, state reset per video/job, source-frame chronology,
   deterministic IDs/aggregation dan idempotent publication. Seed saja tidak
   membuktikan inference deterministik.
3. Sebagai gate engineering awal, jalankan **minimal tiga pengulangan independen**
   pada scope representatif dan execution profile yang sama. Angka3 adalah
   aturan pengujian engineering, bukan probabilitas reliabilitas/akurasi dan
   tidak membuktikan seluruh kemungkinan input. Tambahkan uji bila ada mismatch
   atau perubahan relevan. Scope mahal dimulai terikat sebelum full-video run.
4. Bedakan cache replay dari fresh detector/encoder inference. Catat GPU/CPU,
   model/runtime/provider, versions, precision, deterministic settings, thread/
   batching dan preprocessing yang benar-benar efektif.
5. Keputusan discrete dan agregat wajib konsisten untuk profile yang diluluskan.
   Jangan memilih tolerance yang menyembunyikan perubahan accepted/pending/
   category/direction. Jika memerlukan tolerance numerik untuk internal float,
   deklarasikan alasannya/version dan tetap cek dampak keputusan.
6. Mismatch menghasilkan laporan diff dan status reproducibility FAILED/NOT_
   VALIDATED pada scope itu; simpan kedua output, investigasi akar masalah,
   jangan mengubah angka secara manual agar match. Pilih execution profile
   yang terbukti stabil sebelum mengklaim mode itu stabil.
7. Retry/cancel/restart/concurrent duplicate request tidak menggandakan passage
   atau subtotal. Hasil final dipublikasikan setelah mandatory artifacts valid;
   lookup hasil lama tetap tersedia sesudah worker/session berakhir.

Cross-hardware/backend parity memerlukan uji tersendiri. CPU dan GPU tidak
boleh dianggap byte-identical. Bila fresh inference belum memenuhi gate,
replay hasil finalized tetap boleh tersedia dengan label yang akurat, tetapi
production fresh-processing readiness tetap belum lulus. Jangan mengganti
model, melewati frame atau mematikan ReID sebagai fallback diam-diam.

## Bukti yang sudah ada dan yang belum

LI-3:21calculation artifacts byte-identical pada replay tersimpan. LI-4:
rekonsiliasi/export dan relocated reopen. LI-5:5outputs byte-identical pada
repeat R2 serta compact relocated reopen. Lihat masing-masing review/receipts;
ini bukan bukti tiga fresh-inference runs Traffic atau semua lokasi/video.
Traffic mempunyai retained pipelines/pilot audits dan CPU smokes terbatas;
night/generalization/CPU throughput/independent fresh inference memerlukan
validasi berikutnya. Tidak melaporkan accuracy/zero-mistake guarantee tanpa
bukti ground truth/evaluation yang sesuai.
