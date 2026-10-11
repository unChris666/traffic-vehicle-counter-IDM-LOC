# Phase 1 — one-video inspection report

Run: `20261011T041536_431362Z_5467f20a`
Input: `/tmp/traffic-review-input/TOR3-MALAM.mp4`
Status: **evidence_saved_manual_review_recorded**; review: **manual_review_recorded_not_a_benchmark**
SHA-256: `a92e693b208813cccbac3921a5169b08443fdf425e352168d0ae9db3fe4f2082`

## Metadata (executed probe/decode evidence)

| Field | Value | Provenance |
|---|---|---|
| Filename | TOR3-MALAM.mp4 | selected discovered file |
| File size bytes | 52906523 | filesystem stat |
| width | 1280 | ffprobe.width |
| height | 720 | ffprobe.height |
| frame_count | 9590 | ffprobe.frame_count |
| fps | 29.419969502218617 | ffprobe average frame rate; constant-FPS status unknown |
| duration_seconds | 325.969067 | ffprobe.stream_duration_seconds |
| codec | h264 | ffprobe codec_name |
| Decoded frame count | 9590 | sequential OpenCV first pass; completeness unverified |

## Manual visual observations

| Item | Observation | Evidence |
|---|---|---|
| camera_position (VISUAL_OBSERVATION_AI_ASSISTED) | Pandangan berasal dari tepi jalan: bahu/trotoar tampak di kiri depan dan deretan bangunan di seberang jalan. Posisi pengamatan tampak tetap pada sampel awal, tengah, dan akhir; tinggi serta koordinat kamera tidak diketahui. | frames/frame_000000000.png, frames/frame_000004794.png, frames/frame_000009589.png |
| camera_orientation (VISUAL_OBSERVATION_AI_ASSISTED) | Frame landscape 1280 x 720; kamera menghadap serong sepanjang jalan menuju kejauhan kiri, dengan bangunan seberang di kanan. Arah kompas dan pitch/roll numerik tidak diketahui. | frames/frame_000000000.png, frames/frame_000004794.png |
| road_orientation (VISUAL_OBSERVATION_AI_ASSISTED) | Jalan tampak memanjang dari area dekat kanan/bawah menuju kejauhan kiri. Tepi jalan kiri dan sebagian permukaan aspal terlihat; marka tidak selalu jelas dalam gelap. Orientasi geografis tidak ditentukan dari gambar. | frames/frame_000000000.png, frames/frame_000002397.png, frames/frame_000007192.png |
| approximate_viewing_angle (VISUAL_OBSERVATION_AI_ASSISTED) | Sudut pandang oblique dari sisi jalan, bukan pandangan tegak lurus dari atas. Nilai sudut dalam derajat UNKNOWN: tidak ada kalibrasi atau ukuran acuan yang mendukung angka 45 derajat. | frames/frame_000000000.png, frames/frame_000004794.png |
| handheld_shake (VISUAL_OBSERVATION_AI_ASSISTED) | Pada lima burst sekitar satu detik, posisi tiang, atap, dan fasad bangunan relatif tetap ketika kendaraan bergerak. Tidak terlihat guncangan besar atau pan dalam burst yang diperiksa; perubahan framing kecil antarsampel mungkin ada. Cara memegang kamera dan gerak di sela sampel tidak dapat dipastikan. | bursts/beginning/manifest.json, bursts/quarter/manifest.json, bursts/middle/manifest.json, bursts/three_quarters/manifest.json, bursts/end/manifest.json |
| camera_stability (VISUAL_OBSERVATION_AI_ASSISTED) | effectively_stationary: Secara kualitatif effectively_stationary pada lima burst yang diperiksa: latar relatif tetap dan jalan tetap berada dalam bidang pandang yang sama. Penilaian visual ini bukan pengukuran jitter dan tidak mencakup setiap frame selama 325,969 detik. | bursts/beginning/manifest.json, bursts/quarter/manifest.json, bursts/middle/manifest.json, bursts/three_quarters/manifest.json, bursts/end/manifest.json |
| lighting_condition (VISUAL_OBSERVATION_AI_ASSISTED) | Kondisi malam sangat gelap: sebagian besar langit dan latar tidak memiliki detail yang mudah dilihat. Lampu bangunan memberi penerangan lokal, sedangkan lampu depan kendaraan menimbulkan silau/flare dan perubahan terang pada permukaan jalan. Teks tertanam menunjukkan sekitar 18.58-19.03; waktu tersebut belum diverifikasi terhadap metadata perekaman. | frames/frame_000000000.png, frames/frame_000002397.png, frames/frame_000007192.png, frames/frame_000009589.png |
| vehicle_visibility (VISUAL_OBSERVATION_AI_ASSISTED) | Motor/rider dekat masih dapat dikenali pada burst awal dan tiga-perempat, tetapi detail bodi/warna kendaraan jauh atau gelap sulit dipisahkan dari latar. Pada kendaraan berlampu depan terang, silau lebih dominan daripada detail bodi. Mobil dekat pada frame 7206 terlihat sebagian dan terpotong tepi kanan. | frames/frame_000000007.png, frames/frame_000000029.png, frames/frame_000002397.png, frames/frame_000007206.png, frames/frame_000009589.png |
| occlusion (VISUAL_OBSERVATION_AI_ASSISTED) | Teks lokasi/waktu tertanam di kanan bawah menutupi sebagian piksel kendaraan yang masuk dekat kamera, contohnya mobil pada frame 7206. Kendaraan dekat juga menutup bagian latar/jalan; tepi frame memotong objek saat masuk. Sampel ini tidak menetapkan frekuensi oklusi antar kendaraan sepanjang video. | frames/frame_000000007.png, frames/frame_000007206.png, frames/frame_000009589.png, bursts/three_quarters/manifest.json |
| blur (VISUAL_OBSERVATION_AI_ASSISTED) | Motor dekat pada frame 7/14/29 dan mobil yang masuk pada frame 7206 menunjukkan detail gerak yang lembut/kabur dibanding latar bangunan. Bodi kendaraan jauh juga kurang jelas dalam gelap. Penyebab relatif motion blur, fokus, noise, dan kompresi belum dipisahkan atau diukur. | frames/frame_000000007.png, frames/frame_000000014.png, frames/frame_000000029.png, frames/frame_000007206.png |
| reflections (VISUAL_OBSERVATION_AI_ASSISTED) | Terdapat pantulan cahaya lampu pada aspal, flare berbentuk garis/silang di sekitar sumber terang, dan area lampu depan sangat terang. Tampilan berkilau tidak membuktikan bahwa jalan basah. | frames/frame_000002397.png, frames/frame_000004794.png, frames/frame_000009589.png |
| shadows (VISUAL_OBSERVATION_AI_ASSISTED) | Area gelap kuat tampak di bawah/sekitar bangunan dan pada bagian jalan yang tidak tersinari. Terang serta pola gelap pada jalan berubah saat kendaraan berlampu lewat; bayangan kendaraan individual tidak selalu dapat dipisahkan dari latar gelap. Tidak ditetapkan ukuran atau arah bayangan. | frames/frame_000000000.png, frames/frame_000002397.png, frames/frame_000007192.png, bursts/three_quarters/manifest.json |
| vehicles_entering_exiting (VISUAL_OBSERVATION_AI_ASSISTED) | Pada burst awal motor masuk dari tepi kanan, bergerak ke arah kiri yang lebih jauh, lalu mengecil; mobil mulai masuk dari tepi kanan pada akhir burst tiga-perempat. Sampel tersebut memperlihatkan pemotongan objek di batas frame, tetapi tidak memuat setiap peristiwa keluar atau re-entry sepanjang video. | frames/frame_000000000.png, frames/frame_000000007.png, frames/frame_000000029.png, frames/frame_000007206.png, bursts/beginning/manifest.json, bursts/three_quarters/manifest.json |
| diagonal_vehicle_movement (VISUAL_OBSERVATION_AI_ASSISTED) | Motor pada frame 7 ke 29 bergerak dari kanan/dekat menuju kiri/lebih jauh dengan perubahan posisi vertikal dan ukuran; lintasan tampak diagonal dalam koordinat gambar. Arah A_TO_B/B_TO_A tidak disimpulkan dari tanda X/Y ini. | frames/frame_000000007.png, frames/frame_000000029.png, bursts/beginning/manifest.json |
| geometry_feasibility (VISUAL_OBSERVATION_AI_ASSISTED) | Secara visual geometri per-video dengan dua region dan garis yang memotong koridor perjalanan tampak memungkinkan karena ruas jalan dekat terlihat. Bagian kandidat perlu mempertimbangkan area gelap, silau, teks kanan bawah, objek terpotong, dan kendaraan parkir. Poligon, koordinat, anchor, serta pemetaan semantik A/B untuk video ini masih OPEN; tidak disalin dari screenshot contoh. | frames/frame_000000000.png, frames/frame_000002397.png, frames/frame_000007192.png, frames/frame_000007206.png |
| geometry_alignment_over_time (VISUAL_OBSERVATION_AI_ASSISTED) | Tepi jalan dan fasad relatif selaras dalam masing-masing burst dan koridor jalan tetap terlihat pada lima sampel tersebar. Pergeseran framing kecil antarsampel mungkin memengaruhi geometri yang sangat dekat batas. Belum ada garis/poligon terpasang, toleransi drift terukur, atau jaminan alignment kontinu. | bursts/beginning/manifest.json, bursts/quarter/manifest.json, bursts/middle/manifest.json, bursts/three_quarters/manifest.json, bursts/end/manifest.json |
| low_light_detection_risk (HYPOTHESIS_UNTESTED) | HIPOTESIS BELUM DIUJI: bodi gelap/berkontras rendah dan lampu depan yang menyilaukan mungkin menyebabkan deteksi terlewat atau kotak tidak stabil. Ini berasal dari visibilitas gambar, bukan hasil YOLO; tidak ada inference atau metrik model. | frames/frame_000002397.png, frames/frame_000004794.png, frames/frame_000009589.png |
| low_light_tracking_risk (HYPOTHESIS_UNTESTED) | HIPOTESIS BELUM DIUJI: perubahan terang, blur kendaraan dekat, batas frame, dan detail bodi yang sulit terlihat mungkin menimbulkan gap asosiasi, fragmentasi, atau pergantian ID. BoT-SORT belum dijalankan sehingga kejadian tersebut belum terbukti. | frames/frame_000000007.png, frames/frame_000002397.png, frames/frame_000007206.png, bursts/beginning/manifest.json, bursts/three_quarters/manifest.json |
| low_light_reid_risk (HYPOTHESIS_UNTESTED) | HIPOTESIS BELUM DIUJI: warna/tekstur bodi yang hilang dalam gelap, flare, dan teks yang menutup objek mungkin mengurangi informasi tampilan untuk membedakan identitas. Model/embedding ReID belum diuji dan manfaat ReID tidak dapat disimpulkan. | frames/frame_000000029.png, frames/frame_000002397.png, frames/frame_000007206.png, frames/frame_000009589.png |
| potential_failure_cases (HYPOTHESIS_UNTESTED) | HIPOTESIS BELUM DIUJI: kendaraan gelap di kejauhan, kendaraan didominasi lampu depan, kendaraan dekat kabur/terpotong/tertutup teks, dan motor yang tampak diam di tepi jalan dapat menjadi kasus sulit. Kesalahan deteksi, identitas, anchor, atau event crossing belum diobservasi karena pipeline model/counting belum dijalankan. | frames/frame_000000007.png, frames/frame_000002397.png, frames/frame_000007206.png, frames/frame_000009589.png |
| technical_questions (OPEN) | OPEN: di bagian jalan mana kedua arah dapat diamati cukup lama tanpa teks/silau dominan? Bagaimana poligon/garis serta semantik A/B ditetapkan untuk video ini? Anchor center atau bottom-center mana yang sesuai? Apakah jitter langka muncul di luar lima burst? Bagaimana source PTS dibanding rata-rata/nominal FPS? Pada fase terkait, apakah deteksi/BoT-SORT/ReID memadai untuk kendaraan gelap dan parkir? Eksperimen enhancement tetap Phase 7. | frames/frame_000002397.png, frames/frame_000007206.png, bursts/beginning/manifest.json, bursts/end/manifest.json |

## Decode warnings and limitations

- Average and nominal frame rates differ. This alone does not prove variable frame rate; inspect timestamps if needed.
- This actual-video inspection and AI-assisted pixel review executed in Codex using Kaggle-downloaded bytes, not in the Kaggle notebook runtime.
- Identity against the uploaded Sediment bytes is UNKNOWN; only Kaggle-downloaded bytes were inspected and SHA-256 computed.
- Numeric viewing angle, exact height, geometry coordinates/anchor/side labels, source integrity, and model outcomes remain UNKNOWN/OPEN despite all review items containing observations.
- Git archive retains display sheets and frame hashes; native PNGs and HTML previews remain runtime artifacts. Reproduce them from the same input SHA-256 and sampling indices.
- No detector/tracker/ReID/counting execution or ground-truth evaluation.
- Human observations depend on inspected evidence; unknown items are not fabricated.
- Representative fractions use decoded frame indices; VFR elapsed-time quartiles may differ.
- OpenCV read failure does not distinguish EOF from damaged/unsupported frames.
- Backend timestamps and FPS-derived timing are recorded with uncertainty.
- Short bursts can miss rare shake/events; inspect more evidence if needed.
- Display copies are resized; geometry/visibility assessment should also use native PNGs.

## Evidence

- Native frames and burst manifests: see `run_manifest.json`.
- The contact sheet and temporal previews are display aids; native PNGs retain decoded dimensions.
- No Phase 2 work is started or validated by this report.
