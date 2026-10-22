# Validasi malam resmi dan Review-Filter

21 Oktober 2026. **Status: PARTIAL — inspeksi dan tool review selesai; smoke
end-to-end belum dijalankan.** Dataset resmi pengguna adalah
`chrisbiran/video-traffic-malam`; tidak diasumsikan berisi delapan video.

## Akses dan eksekusi aktual

**EXPERIMENT RESULT:** Kaggle API berhasil mengakses dataset. Inspeksi lokal
dilanjutkan eksekusi CPU di notebook privat
[B v8 nighttime input inspection](https://www.kaggle.com/code/chrisbiran/b-v8-nighttime-input-inspection),
version1, status COMPLETE. Source notebook ada pada
[09f_nighttime_validation.ipynb](../notebooks/09f_nighttime_validation.ipynb).
Ini kelanjutan inspeksi B v8; `09e_p1_pending_recovery.ipynb` dan hasil
reviewed TGDI sebelumnya tidak diubah.

Actual mount yang ditemukan oleh kode Kaggle:
`/kaggle/input/datasets/chrisbiran/video-traffic-malam`. Seluruh 10 file
diperiksa, bukan diseleksi menurut slot weekday/weekend. Total 89.199 frame
terdecode sampai EOF dan sesuai header. SHA256 file, count dan 50 sample pixel
native cocok antara Codex dan Kaggle. OpenCV lokal 5.0.0 dan Kaggle 4.14.0;
Python Kaggle 3.13.15, 4 CPU, GPU tidak diperlukan/diminta untuk inspeksi.

Resolusi aktual adalah 640×480,1024×576 dan 1280×720; codec semua H.264.
Durasi dilaporkan 301,308–315,659detik dan FPS rata-rata 26,873974–29,992922.
FPS rata-rata bukan bukti constant-frame-rate. Timeout 60 tetap **frame sumber**.
Tidak ada file unsupported atau gagal decode yang ditemukan. Batas pemeriksaan
decode: sequential OpenCV dan count header, bukan sertifikasi bitstream.

[Inventory lengkap dan observasi](../results/nighttime_validation/inspection_report.md)
berisi ukuran file, metadata, codec, frame, sampel dan bukti asli. Original
report Kaggle tetap mempertahankan status visual `PENDING` saat notebook
berjalan; adjudikasi visual sesudahnya disimpan terpisah pada
[visual_review.json](../results/nighttime_validation/visual_review.json).

## Observasi yang relevan

- FMMQ sangat gelap pada beberapa sampel dengan headlight terang; exposure
  berubah antarsampel. Penambahan brightness tidak mengembalikan informasi
  yang tidak terekam atau sudah clipped.
- TC0Q relatif lebih terang dengan glare/haze, bayangan, frame miring dan
  sebagian foreground terhalang. TKVQ mempunyai occlusion kendaraan besar.
- TQHD mempunyai foreground/angle berbeda antarkedua source; motor parkir
  pada weekend menutupi jalan. Template TGDI tidak dianggap cocok otomatis.
- TKVQ-WEEKDAY-MALAM frame 0 hitam; frame 1, 2, 5, 15, 30 berisi scene dan terdecode.
  Ini peringatan input, bukan kegagalan seluruh file atau alasan mengubahnya.
- `FMMQ-MALAM.mp4` tidak dipaksa menjadi weekend. Assignment kondisi semua
  source tetap null sampai review eksplisit. Filename tidak membuktikan
  kondisi kamera, tingkat gelap atau kelompok bisnis.

Pengamatan berasal dari 50 frame representatif dan 12 anchor tambahan, bukan
audit semua passage. Noise sensor belum dipisahkan dari artefak kompresi;
stabilitas kamera/blur tidak diberi skor kuantitatif. Dampak terhadap detector,
tracking/ReID dan counting masih **HYPOTHESIS_UNTESTED** pada dataset baru ini.

## Review-Filter yang dibuat

[review-filter.html](../results/review-filter.html) adalah halaman standalone
yang dapat diunduh lalu dibuka di browser. Script transform ikut tertanam;
tidak memerlukan file JS pendamping. Pilih video asli melalui file picker;
video tidak diunggah oleh halaman. Sumber terikat SHA256, bukan filename saja.

Delapan profil independen: weekday/weekend × pagi/siang/sore/malam. Ini profil
setting, bukan delapan input yang dibuat-buat. Sepuluh video aktual dapat
dibuka dan masing-masing mempunyai snapshot setting sendiri. Mengubah satu
profil tidak diam-diam mengubah video lain. Kondisi dipilih manual; null valid.
Local storage membantu melanjutkan review; ekspor JSON diperlukan untuk Kaggle.

Urutan transform eksplisit, native dimensions dan channel dipertahankan:

| Kontrol | Definisi eksperimen |
|---|---|
| Gamma | `255 * (x/255)^gamma`; eksponen langsung, default 1. |
| Exposure | `x * 2^EV`; pengalian digital, default 0EV. |
| Brightness | `x + brightness`; offset intensitas, default 0. |
| Shadows | `x + 0.64 * shadows * (1-x/255)^2`; per channel, default 0. |
| Sharpness | Unsharp terhadap kernel binomial3×3 `[1,2,1]⊗[1,2,1]/16`, edge replicate, default 0. |

Setiap stage memakai clip0…255 dan pembulatan half-up. Semua default identitas
(raw). Rentang slider adalah batas tool eksperimen, **bukan hasil tuning**.
Shadows dan sharpness ini belum diuji pada model; kernel sharpness berbeda
dari Gaussian sigma1 eksperimen Phase7, sehingga keduanya bukan varian identik.
Gamma 0.7 Phase7 tidak otomatis menjadi default produksi.

Backend baru [nighttime_review_filter.py](../notebooks/nighttime_review_filter.py)
memvalidasi schema, delapan profil, video hash dan urutan operasi. Tidak ada
fallback diam-diam ke filename/profil source lain. `prepare_inference_frame`
menghasilkan frame/provenance yang nantinya harus dipakai sama untuk detector
dan ReID. **API preprocessing sudah diuji; penyambungan ke job inference malam
aktual belum divalidasi.** Modul lama tidak dimonkeypatch atau diganti.

## Verifikasi aktual dan koreksi

**EXPERIMENT RESULT:** 16 tes software lulus. Uji Playwright/system Chromium
membuka 10 file asli, mengubah seluruh 8 profil melalui kontrol halaman,
menguji isolasi per source, impor/ekspor, persistensi, seek dan play/pause.

Uji awal tombol saja kurang: `readyState` browser dapat siap sebelum frame
pertama tergambar ke canvas. Pemeriksaan pixel menangkap preview transparan;
pengaman presentasi frame pertama ditambahkan dan regression browser kemudian
dijalankan ulang. Attempt awal/failure tetap tersimpan, tidak dianggap pixel PASS.

Output filter browser dan Python cocok tepat pada 307.200 pixel frame uji
640×480 dengan input decoded yang sama. Decoder browser versus OpenCV pada
frame itu berbeda sampai 3 tingkat per channel; ini batas konversi decoder,
bukan bukti transform matematik berbeda. Jangan menjanjikan bit-identical
source decode lintas browser/platform. Tidak memakai CSS visual filters yang
diam-diam berbeda dari backend.

Config pada `browser_validation/test_export_not_selected_for_inference.json`
berisi **nilai tes**, bukan hasil review/recipe yang dipilih untuk inferensi.

Baseline B v7: 132 artefak dan 11 binding source tetap cocok. B v8: 451 artefak
dan 15 binding source tetap cocok. Area Coverage dan PPAC tidak diubah.

## Smoke dan gate perluasan

**BELUM DIJALANKAN:** smoke detector→tracker→ReID→counting→annotated video.
Tidak ada accepted/pending/accuracy baru yang dilaporkan untuk dataset ini.

**PROPOSAL:** mulai F1YV-WEEKDAY-MALAM, 600 frame sumber kontinu 0…599 sebagai
smoke teknis terbatas; raw dibandingkan dengan satu recipe yang disetujui,
kontrol model/counting sama dan state baru tiap branch. Ini bukan penetapan
sample performance atau threshold acceptance. Lalu perluas menurut kegagalan
yang benar-benar terlihat, termasuk FMMQ gelap dan TKVQ occlusion.

Prasyarat yang belum terpenuhi:

1. JSON Review-Filter yang benar-benar dipilih untuk eksperimen; nilai tes
   browser tidak dipromosikan menjadi pilihan pengguna.
2. Geometri native, arah A/B dan margin yang direview untuk video sumber baru.
3. Adapter/konfigurasi source malam pada jalur B v8 yang divalidasi terisolasi.
   Batch B v8 saat ini secara sengaja dibatasi pilot cache TGDI 9.128 frame.
   Jangan menghapus guard, menyalin role/identity overlay Siang, atau memakai
   full-video helper lama yang masih menghitung dengan B v1.
4. Freeze konfigurasi dan pemeriksaan GPU/model pada job smoke sebelum loading
   model. ReID tetap arsitektur; konfigurasi vehicle-ReID final masih terbuka.

[smoke_plan.json](../results/nighttime_validation/smoke_plan.json) mencatat
source hash, scope usulan, prasyarat dan output yang perlu disimpan. Masalah
tersebut tidak diselesaikan dengan menjalankan ulang full-video inference.

Langkah pengguna berikutnya: buka Review-Filter, pilih F1YV-WEEKDAY-MALAM,
bandingkan beberapa posisi raw/filtered, kemudian ekspor JSON. Review geometri
source tersebut menyusul sebelum smoke counting. Tidak ada pembuktian
keandalan malam hanya dari decode atau preview yang berhasil.
