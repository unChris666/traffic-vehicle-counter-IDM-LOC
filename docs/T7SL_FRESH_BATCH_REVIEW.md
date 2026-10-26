<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# T7SL fresh → counting → delapan video — 24 Oktober 2026

## Scope yang dijalankan

Dataset aktual `chrisbiran/t7sl-traffic-videos`, notebook baru
https://www.kaggle.com/code/chrisbiran/t7sl-fresh-modular-traffic-batch .
Submission V1 diterima; status terakhir RUNNING. Hasil counting delapan video
belum diklaim tersedia sebelum output terminal diunduh dan diverifikasi.

Seluruh delapan video diunduh tanpa modifikasi dan didekode berurutan secara
lokal:71.380 frame,720×480, FPS aktual28,31–29,95, durasi sekitar lima menit.
File, byte SHA dan framecount aktual ada di
`results/t7sl_modular/inspection/inventory.json`. Sampel awal/tengah/akhir
tersimpan sebagai JPG untuk inspeksi visual; bukan measurement model.

## Temuan inspeksi dan konfigurasi

Sampel memperlihatkan jalan dengan perspektif menuju kiri/jauh, area bangunan
pada kanan, kendaraan bergerak diagonal dan truck/motor yang dapat saling
menutup. Malam memperlihatkan latar gelap dan silau lampu; kondisi tersebut belum
membuktikan kinerja deteksi/tracking. Overlay peta dan tulisan tertanam di video
adalah potensi gangguan. Tidak ada klaim sudut45derajat atau ground truth.

Geometri kandidat T7SL G1 native720×480: garis (60,315)–(715,315), half-margin25px,
A jauh/atas dan B dekat/bawah. Polygon dibatasi secara eksplisit; gambar overlay
ada pada `inspection/geometry_contact.jpg`. Seluruhnya **engineering provisional**,
belum persetujuan owner atau bukti robustness temporal. Asumsi A→B mendekati,
B→A menjauhi perlu review melalui UI kelak. Tidak menggunakan persetujuan TGDI
sebagai persetujuan T7SL. Nilai kontrol counting Bv7 dipertahankan sebagai
kontrol penelitian, bukan dituning agar angka bertambah. Referensi template
historis di policy hanya provenance kontrol; geometri efektif berasal dari
berkas per-source T7SL dan hash-nya.

RAW adalah baseline. Filter malam dari video/toko lain tidak diterapkan diam-diam.
YOLO26M, BoT-SORT, encoder eksternal yolo26n-reid.onnx person-domain tetap sebagai
kontrol eksperimen. Vehicle-ReID final dan benchmark akurasi masih terbuka.

## Integrasi dan pengaman

- `fresh_bridge.py` memvalidasi source SHA, frame coverage, integritas records,
  dimensi, raw-detection index dan bbox terukur. Provenance tetap
  `fresh_modular_detection_v1`; tidak diganti menjadi cache Phase8.
- Fresh machine tidak menerima review/relationship lama atau overlay TGDI.
  Role person dimulai UNKNOWN; resolver role/episode lama tetap bekerja.
- Notebook meminta `NvidiaTeslaT4`; **runtime wajib membuktikan dua GPU T4** dan
  CUDA encoder. Satu video per proses/GPU; empat video berurutan per slot GPU.
  Tidak ada fallback CPU jika alokasi tidak memenuhi permintaan.
- Manifest sumber/code/policy/request/geometri dikunci sebelum submission.
  Mount Kaggle diverifikasi dari path aktual dan hash seluruh video.
- Smoke96frame pada weekday-pagi disimpan terpisah. Kegagalan smoke menghentikan
  full-video inference. Delapan full jobs baru dimulai setelah smoke lulus.
- Setiap full job menjalankan counting dari measurement yang sama tiga kali dan
  memeriksa native hash serta result version. Ini uji replay counting; bukan tiga
  fresh-inference penuh atau bukti GPU inference deterministik.
- Agregasi memakai kategori×arah×measured/estimated. Pedestrian terpisah;
  pending/invalid tidak masuk subtotal. Smoke, rerun ganda, source ganda, branch
  reviewed dan eksperimen lain tidak boleh ditambahkan. Partial tidak menjadi
  total delapan video atau nol palsu.

Tes lokal:13kasus adapter/agregasi lulus,27tes batas lama lulus dan7tes schema/
publikasi lulus. Bridge ke counting diuji menggunakan actual retained32frame CPU
TGDI dengan class metadata dari weights aktual; menghasilkan1accepted measured.
Ini bukti kompatibilitas adapter, **bukan** hasil T7SL atau inference T7SL baru.

## Output Kaggle

`/kaggle/working/results/t7sl_fresh_machine_v1/`:

- environment.json, mounted_dataset.json, locked_config.json;
- smoke_status.json dan smoke/;
- videos/<video>/measurement/result.json.gz;
- videos/<video>/counting/{native.json.gz,result.json,request.json,repetitions.json};
- jobs.json, combined.json, combined.csv.

`combined.json` memuat event ledger gabungan, pivot10baris, subtotal kendaraan,
pedestrian, pending/invalid, daftar video gagal dan status partial. Total berarti
passage pada delapan rekaman, bukan kendaraan unik lintas video atau24jam.
Video anotasi penuh fresh belum diimplementasikan oleh irisan ini; renderer
cache historis tidak dipaksa menerima provenance baru tanpa pengujian.

Batas readiness: geometri provisional, kualitas malam/identitas, dan vehicle-ReID
produksi tetap belum terselesaikan. Tidak ada klaim accuracy atau zero mistakes.

## Pembaruan pengamatan runtime dan revisi geometri

Live log resmi Kaggle mengonfirmasi mount
`/kaggle/input/datasets/chrisbiran/t7sl-traffic-videos` serta dua perangkat
`Tesla T4`. Ini bukti alokasi hardware, bukan bukti delapan job selesai atau
encoder CUDA sukses pada setiap video; keduanya diverifikasi dari output nanti.

Review lanjutan geometri dilakukan **sebelum** melihat angka gabungan. G1
horizontal berisiko tidak berpotongan dengan trajectory lajur jauh yang tetap
di atas y315. G2, garis (60,340)–(715,230), menggunakan kemiringan negatif untuk
melintasi kedua lajur. Semua delapan config G2 dan hash kontrol dibekukan pada
`results/t7sl_modular/geometry_g2/revision.json`. Tetap provisional; tidak ada
threshold/model/filter yang dituning berdasarkan hitungan.

V1 Kaggle tetap immutable dan menghasilkan G1. Collector lokal menunggu status
terminal, memverifikasi measurement full-frame, encoder CUDA, tiga repeat
counting setiap video dan rekonsiliasi pivot. Bila delapan lolos, G2 dijalankan
sebagai **replay counting CPU lokal terpisah** pada measurement GPU V1 yang sama.
Sebelumnya G1 direplay lokal untuk memeriksa kesetaraan native lintas runtime;
mismatch menghentikan eksperimen G2. G2 direpeat tiga kali per video. Ini bukan
inference baru, bukan hasil G2 yang sudah tersedia, dan bukan klaim CPU/GPU
inference identik.

Monitoring/collection: `PYTHONPATH=src python -B tools/collect_t7sl.py`.
Receipt akhir G1 akan ditulis ke `results/t7sl_modular/execution/verified_summary.json`;
hasil G2 ke `results/t7sl_modular/g2_execution/` jika gate input lulus. Status
scheduler tersimpan terpisah; RUNNING bukan PASS. Snapshot notebook V1 menyimpan
source bundle sendiri. Schema working tree boleh berevolusi; cek
`verification/submitted_bundle_check.json` untuk hash source yang benar-benar
submitted, bukan menganggap semua file current identik dengan V1.
