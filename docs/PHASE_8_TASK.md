# Phase 8 — end-to-end delapan video satu lokasi

**REQUIREMENT — otorisasi awal pengguna 14 Oktober 2026, diperjelas 15 Oktober 2026:** pengguna meminta penjelasan input/metadata/geometri, penilaian objektif Phase 7, dan coding Phase 8 jika objektif tersebut selesai. [Review Phase 7](PHASE_7_REVIEW.md) dan [keputusan aktual](evidence/phase_7/selection/TOR3-MALAM_final_decision_v1.json) memenuhi gate eksperimen scoped TOR3-MALAM. Enhancement tidak wajib menang; raw tetap baseline penelitian.

## Objektif dan batas penerimaan

Phase 8 menyambungkan pipeline yang telah dikembangkan menjadi pemrosesan delapan input untuk **satu lokasi**: empat weekday dan empat weekend, masing-masing pagi/siang/sore/malam. Menghasilkan delapan snapshot per video, events/keputusan/audit queue, video anotasi, log/config/resource, serta dua tabel CSV accepted passage per kategori/periode.

Deteksi/tracking diproses dari frame0 hingga akhir setiap video, dengan state/video identity terpisah. Counting memakai seluruh source history, **tanpa** filter13ID PAGI atau lima window Phase7. B v1 mempertahankan measured vehicle BC, geometri finite, episode/unit/rider, category, duplicate dan return guards. Source lama tidak diubah. Cache raw yang identik dan kontrol model yang cocok dapat dipakai kembali dengan provenance eksplisit; hasil/review historis tidak otomatis menjadi hasil full-scope baru.

**ENGINEERING IMPLEMENTATION:** raw, YOLO26M/BoT-SORT/ReID dengan kontrol eksperimen tetap; dedicated person-domain ReID adalah kontrol yang teruji integrasinya, bukan vehicle-ReID final. Mulai sequential pada CUDA0 eksplisit, sambil melaporkan GPU yang benar-benar tersedia. Memakai dua GPU untuk scheduler paralel tetap tahap setelah correctness; notebook awal tidak menyatakan dua GPU dipakai hanya karena terlihat.

Kode/notebook dan synthetic correctness dapat diselesaikan sebelum input bisnis lengkap. **Eksekusi delapan video hanya diizinkan setelah manifest/source/geometri siap.** Keberhasilan pilot satu cache tidak memenuhi acceptance delapan video. Phase9 audit menyeluruh, Phase10 modularisasi, UI/Docker/deployment tidak dimulai.

## Apa arti delapan video, metadata dan geometri?

Delapan slot adalah daftar kebutuhan produk berikut. Pemetaan berikut mengikuti konvensi filename yang telah dikonfirmasi pengguna, lalu diverifikasi terhadap listing API dataset aktual.

| Kelompok | Pagi | Siang | Sore | Malam |
|---|---|---|---|---|
| Weekday | TGDI-WEEKDAY-PAGI.mp4 | TGDI-WEEKDAY-SIANG.mp4 | TGDI-WEEKDAY-SORE.mp4 | TGDI-WEEKDAY-MALAM.mp4 |
| Weekend | TGDI-WEEKEND-PAGI.mp4 | TGDI-WEEKEND-SIANG.mp4 | TGDI-WEEKEND-SORE.mp4 | TGDI-WEEKEND-MALAM.mp4 |

**CONFIRMED — dataset Phase8:** pengguna menetapkan `/kaggle/input/datasets/chrisbiran/tgdi-traffic-videos` dan konvensi `KODETOKO-KATEGORI-KEADAAN`. Listing API aktual mengonfirmasi tepat delapan MP4: TGDI×WEEKDAY/WEEKEND×PAGI/SIANG/SORE/MALAM. Karena konvensi telah dikonfirmasi secara eksplisit, `TGDI-WEEKEND-MALAM.mp4` dipetakan ke kode toko TGDI, weekend, malam. Nama lengkap toko, latitude/longitude dan persetujuan geometri tidak diberikan oleh filename. CreationDate Kaggle adalah tanggal penambahan file, bukan bukti tanggal rekaman. TOR3/G3/N1 tetap sumber regresi historis; tidak menjadi geometri TGDI secara otomatis.

Contoh record persiapan untuk salah satu file:

```json
{
  "filename": "TGDI-WEEKEND-MALAM.mp4",
  "store_code": "TGDI",
  "store_name": null,
  "latitude": null,
  "longitude": null,
  "day_type": "weekend",
  "recording_period": "malam",
  "recording_period_confirmed": true,
  "observed_dimensions": [640, 480],
  "observed_frame_count": 9032,
  "geometry": null
}
```

Metadata membedakan sumber dan kelompok laporan. Geometri menetapkan polygon A/B, counting line dan arah pada gambar sumber setiap video. Dua video boleh memakai koordinat template yang sama setelah review; persetujuan satu video tidak otomatis berlaku bagi video lain. Latitude/longitude adalah metadata lokasi, bukan sumbu polygon. Sumbu gambar tetap X ke kanan, Y ke bawah, dalam piksel frame asli.

## Input dan konfirmasi pengguna

[Daftar TGDI aktual](evidence/phase_8/inventory/tgdi_kaggle_file_listing_20261015.csv) mengonfirmasi delapan filename dan ukurannya. Ini menggantikan sumber lama13video sebagai batch target. [Klarifikasi pengguna](evidence/phase_8/authorization/dataset_clarification_20261015.json) mengotorisasi parsing kode/day/period dari konvensi yang diberikan. Pengguna kemudian mengonfirmasi nama toko/koordinat belum diketahui dan menerima seluruh geometri/arah G3-T1 TGDI untuk uji awal; feedback disimpan per sumber, tanpa menyalin persetujuan TOR3.

Manifest memuat kode/nama toko, latitude/longitude, delapan assignment weekday/weekend/periode, sourcepath/SHA, observed metadata, dan geometry/source-specific review. Metadata teknis delapan TGDI telah diukur dari72.590frame decoder aktual; masing-masing640×480. Nama lengkap toko/latitude/longitude tetapnull sesuai jawaban eksplisit pengguna. Manifest research v2 menerima unknown ini hanya dengan review metadata terikat delapan SHA sumber dan business_metadata_complete=false. Delapan geometri G3-T1/arah telah disetujui untuk uji awal. Missing source, geometry belum disetujui, duplikat input, native mismatch atau missing fakta yang belum diakui memblok eksekusi; tidak diubah menjadi angka nol.

## Output dan interpretasi

- Setiap video mempertahankan snapshot machine dan reviewed terpisah; agregat memilih tepat satu snapshot per input, tanpa menjumlahkan rerun/raw/gamma/machine+reviewed.
- Hanya accepted CountEvent unik masuk subtotal; pending/rejected/duplicate tetap audit evidence. Satu motorcycle dan rider/passenger dihitung sebagai satu unit berdasarkan bukti, crossing dari BC kendaraan yang diukur.
- Tabel weekday/weekend menjumlahkan empat rekaman periode yang nyata. Total bukan estimasi seluruh24jam atau jumlah kendaraan unik lintas video.
- Profil B v1 saat ini berfokus pada vehicle episodes. Pedestrian belum didukung sebagai accepted counting; bus/angkot dan taxonomy tertentu belum terselesaikan. Cakupan tersebut dinyatakan eksplisit dengan sel nullable/coverage status, tanpa menafsirkan nol accepted sebagai ketiadaan objek fisik.
- Failed/missing slot bernilai null dengan status; tabel parsial tidak disebut batch lengkap. Source video/modelweights tetap eksternal; video anotasi disimpan pada output Kaggle, bukan video sumber di GitHub.

## Validasi

Tes sintetis mendahului inference. Periksa manifest delapan slot, source/geometry hashes, state reset, full contiguous frame history, BC sumber, pending exclusion, event/schema/category/direction reconciliation, snapshot dedup, null/coverage dan output annotation decode/frame alignment. Synthetic fixture tidak boleh dilaporkan sebagai dataset nyata atau hasil model.

Pilot CPU boleh mereplay cache TOR3-MALAM raw yang sudah ditahan, menggunakan N1 dan frozen B controls dalam scope lengkap. Pilot tidak memilih metadata bisnis atau memberi dua tabel delapan input sebelum assignment dikonfirmasi. Actual eight-video GPU execution, biaya dan audit hanya dilaporkan setelah benar-benar dijalankan.

Tidak ada ground truth/accuracy/precision/recall/F1/MAPE. Final vehicle-ReID, produksi/taxonomy/parameter suitability dan kelengkapan fisik memerlukan eksperimen/audit terpisah. [Arsip konteks Phase7](evidence/phase_8/baseline_retention/context_retention_mapping.json) mempertahankan bytes status sebelum dokumentasi berikutnya berkembang.

## Konfirmasi lanjutan — research v2

[Feedback aktual](evidence/phase_8/feedback/TGDI_all_eight_user_confirmation_20261015.json) menetapkan geometri/arah untuk seluruh delapan input. [Manifest aktif v2](evidence/phase_8/config/batch_manifest_TGDI_G3_T1_v2.json) mengikat accepted geometry, review native frames, dan pengakuan metadata lokasi belum diketahui. [Full source preflight](evidence/phase_8/verification/TGDI_research_v2_full_source_preflight.json) membaca seluruh72.590frame lagi untuk memeriksa sumber dan PNG geometri: ready=true, tanpa isu. Ini bukan model run atau hitungan traffic. Mode penelitian tidak menyatakan produk bisnis lengkap; persetujuan awal bukan hasil uji robustness.

Mount dataset Kaggle dapat berbeda antar-run. Notebook memverifikasi tepat delapan identitas SHA pada input aktual, mempertahankan manifest asli, lalu membuat manifest efektif yang hanya mengubah `videos[*].source_path`. READINESS dan batch wajib memakai manifest efektif yang sama; perubahan label, geometri, parameter atau byte sumber tidak diizinkan oleh relokasi. Simpan pemetaan dan kedua SHA manifest bersama output. Kegagalan versi1 sebelum model serta retry versi2 didokumentasikan dalam [review aktual](PHASE_8_REVIEW.md).
