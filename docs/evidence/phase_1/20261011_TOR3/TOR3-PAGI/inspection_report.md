# Phase 1 — one-video inspection report

Run: `20261011T041657_637329Z_ee2d00c8`
Input: `/tmp/traffic-review-input/TOR3-PAGI.mp4`
Status: **evidence_saved_manual_review_recorded**; review: **manual_review_recorded_not_a_benchmark**
SHA-256: `606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c`

## Metadata (executed probe/decode evidence)

| Field | Value | Provenance |
|---|---|---|
| Filename | TOR3-PAGI.mp4 | selected discovered file |
| File size bytes | 53173467 | filesystem stat |
| width | 1280 | ffprobe.width |
| height | 720 | ffprobe.height |
| frame_count | 10282 | ffprobe.frame_count |
| fps | 29.81501660256117 | ffprobe average frame rate; constant-FPS status unknown |
| duration_seconds | 344.859778 | ffprobe.stream_duration_seconds |
| codec | h264 | ffprobe codec_name |
| Decoded frame count | 10282 | sequential OpenCV first pass; completeness unverified |

## Manual visual observations

| Item | Observation | Evidence |
|---|---|---|
| camera_position (VISUAL_OBSERVATION_AI_ASSISTED) | Kamera berada di tepi jalan; bahu/permukaan tepi jalan tampak di kiri bawah dan bangunan berada di seberang jalan. Posisi pengamatan tampak tetap pada sampel. Tinggi kamera dan lokasi fisik presisi UNKNOWN. | frames/frame_000000000.png, frames/frame_000002570.png, frames/frame_000010281.png |
| camera_orientation (VISUAL_OBSERVATION_AI_ASSISTED) | Pandangan kamera miring sepanjang ruas jalan: area jauh berada di kiri atas dan area jalan dekat meluas ke kanan/bawah. Atap, tiang, dan kabel tampak di latar. Orientasi kompas, pitch, yaw, serta roll numerik UNKNOWN. | frames/frame_000000000.png, frames/frame_000005140.png, frames/frame_000010281.png |
| road_orientation (VISUAL_OBSERVATION_AI_ASSISTED) | Ruas jalan berperspektif diagonal dari kejauhan kiri atas ke area dekat kanan bawah, dengan marka tengah dan dua arah gerak kendaraan terlihat. Arah geografis dan kemiringan jalan fisik tidak ditentukan. | frames/frame_000000000.png, frames/frame_000002570.png, frames/frame_000005140.png, frames/frame_000007711.png |
| approximate_viewing_angle (VISUAL_OBSERVATION_AI_ASSISTED) | Pandangan oblique dari tepi jalan dapat diamati, tetapi sudut terhadap sumbu jalan maupun sudut elevasi numerik UNKNOWN; gambar tanpa kalibrasi tidak mendukung penetapan 45 derajat. | frames/frame_000000000.png, frames/frame_000005140.png |
| handheld_shake (VISUAL_OBSERVATION_AI_ASSISTED) | Tidak terlihat guncangan besar atau perubahan arah pandang mendadak dalam lima burst pendek yang ditinjau; tiang dan atap relatif tetap sementara kendaraan bergerak. Guncangan halus dan kejadian di luar sampel belum dapat disimpulkan; jenis dudukan kamera UNKNOWN. | frames/frame_000000000.png, frames/frame_000000001.png, frames/frame_000002555.png, frames/frame_000002556.png, frames/frame_000005125.png, frames/frame_000005126.png, frames/frame_000007696.png, frames/frame_000007697.png, frames/frame_000010252.png, frames/frame_000010253.png, bursts/beginning/manifest.json, bursts/quarter/manifest.json, bursts/middle/manifest.json, bursts/three_quarters/manifest.json, bursts/end/manifest.json |
| camera_stability (VISUAL_OBSERVATION_AI_ASSISTED) | effectively_stationary: Penilaian kualitatif effectively_stationary pada lima burst pendek di awal, seperempat, tengah, tiga-perempat, dan akhir: latar relatif tetap dan gerak kendaraan dapat dibedakan dari gerak kamera. Ini bukan pengukuran shake maupun jaminan untuk seluruh durasi. | frames/frame_000000000.png, frames/frame_000000001.png, frames/frame_000000029.png, frames/frame_000002555.png, frames/frame_000002556.png, frames/frame_000002584.png, frames/frame_000005125.png, frames/frame_000005126.png, frames/frame_000005154.png, frames/frame_000007696.png, frames/frame_000007697.png, frames/frame_000007725.png, frames/frame_000010252.png, frames/frame_000010253.png, frames/frame_000010281.png, bursts/beginning/manifest.json, bursts/quarter/manifest.json, bursts/middle/manifest.json, bursts/three_quarters/manifest.json, bursts/end/manifest.json |
| lighting_condition (VISUAL_OBSERVATION_AI_ASSISTED) | Adegan terang dengan langit berawan yang sangat cerah; aspal, marka, dan bangunan dapat dilihat. Area bawah atap dan beberapa detail kendaraan lebih gelap. Teks waktu tertanam menampilkan pagi, tetapi bukan verifikasi independen jam perekaman. | frames/frame_000000000.png, frames/frame_000002570.png, frames/frame_000005140.png, frames/frame_000007711.png, frames/frame_000010281.png |
| vehicle_visibility (VISUAL_OBSERVATION_AI_ASSISTED) | Bentuk motor dekat serta pengendaranya dapat dilihat pada burst tengah dan tiga-perempat; kendaraan jauh lebih kecil dan detailnya berkurang. Sebagian kendaraan dekat tepi kanan tertutup teks putih tertanam atau terpotong batas frame. Ini pengamatan visual, bukan hasil deteksi model. | frames/frame_000005125.png, frames/frame_000005140.png, frames/frame_000005154.png, frames/frame_000007711.png, frames/frame_000007718.png, frames/frame_000007725.png |
| occlusion (VISUAL_OBSERVATION_AI_ASSISTED) | Teks putih tertanam di kanan bawah menimpa bagian motor saat masuk dari tepi kanan pada frame 7711; motor juga terpotong oleh batas frame sebelum tampil lebih utuh. Oklusi berat antarkendaraan tidak ditetapkan dari sampel default ini; frekuensinya sepanjang video UNKNOWN. | frames/frame_000007711.png, frames/frame_000007718.png, frames/frame_000007725.png |
| blur (VISUAL_OBSERVATION_AI_ASSISTED) | Latar dan kontur motor dekat masih terbaca secara visual, sementara detail kendaraan kecil/jauh dan sebagian detail motor tampak lembut. Penyebab blur gerak, fokus, dan kompresi belum dipisahkan; tidak ada pengukuran blur atau klaim seluruh video bebas blur. | frames/frame_000005125.png, frames/frame_000005140.png, frames/frame_000007718.png |
| reflections (VISUAL_OBSERVATION_AI_ASSISTED) | Sorotan terang tampak pada kaca spion dan permukaan motor, dengan langit sangat cerah. Pantulan jalan atau glare besar yang menghilangkan kendaraan tidak ditetapkan pada sampel ini; kondisi di luar sampel UNKNOWN. | frames/frame_000005125.png, frames/frame_000007711.png, frames/frame_000007718.png |
| shadows (VISUAL_OBSERVATION_AI_ASSISTED) | Area gelap tampak di bawah atap bangunan dan di sekitar bagian bawah motor; pencahayaan jalan relatif menyebar. Bayangan kendaraan yang panjang/tegas tidak dominan pada sampel yang ditinjau; dampak bayangan terhadap model belum diuji. | frames/frame_000000000.png, frames/frame_000005125.png, frames/frame_000007718.png |
| vehicles_entering_exiting (VISUAL_OBSERVATION_AI_ASSISTED) | Pada burst tiga-perempat, bagian motor muncul dari batas kanan frame pada 7711, lalu tampil lebih utuh pada 7718 dan bergerak ke area lebih jauh pada 7725. Burst tengah menunjukkan motor mengecil menuju kiri atas. Jalur keluar lengkap seluruh kendaraan tidak tercakup oleh burst pendek. | frames/frame_000007711.png, frames/frame_000007718.png, frames/frame_000007725.png, frames/frame_000005125.png, frames/frame_000005140.png, frames/frame_000005154.png |
| diagonal_vehicle_movement (VISUAL_OBSERVATION_AI_ASSISTED) | Motor pada burst tengah dan tiga-perempat bergerak diagonal menuju kiri atas serta mengecil, sesuai menjauhi titik kamera. Pergerakan ini memiliki perubahan posisi horizontal dan vertikal; arah tidak boleh ditetapkan dari sumbu X saja. Semantik Side A/B untuk video ini belum dikonfigurasi. | frames/frame_000005125.png, frames/frame_000005140.png, frames/frame_000005154.png, frames/frame_000007711.png, frames/frame_000007718.png, frames/frame_000007725.png |
| geometry_feasibility (VISUAL_OBSERVATION_AI_ASSISTED) | Batas jalan dan marka terlihat sehingga konfigurasi polygon Side A, garis melintang/diagonal, dan polygon Side B per video tampak memungkinkan secara visual. Penempatan perlu menghindari area kendaraan masih sangat kecil, teks kanan bawah, dan batas frame. Ini penilaian kelayakan; koordinat, anchor, serta label Side A/B TOR3-PAGI belum disahkan dan belum diuji crossing. | frames/frame_000000000.png, frames/frame_000002570.png, frames/frame_000005140.png, frames/frame_000007711.png, frames/frame_000010281.png |
| geometry_alignment_over_time (VISUAL_OBSERVATION_AI_ASSISTED) | Posisi jalan, tiang, dan atap relatif selaras pada lima sampel dan burst pendek; belum terlihat perubahan framing besar yang langsung menggagalkan geometry statis per video. Kesesuaian polygon/garis sepanjang seluruh durasi tetap belum diuji karena belum ada konfigurasi dan review kontinu. | frames/frame_000000000.png, frames/frame_000002570.png, frames/frame_000005140.png, frames/frame_000007711.png, frames/frame_000010281.png, bursts/beginning/manifest.json, bursts/middle/manifest.json, bursts/end/manifest.json, bursts/quarter/manifest.json, bursts/three_quarters/manifest.json |
| low_light_detection_risk (HYPOTHESIS_UNTESTED) | Sampel ini tidak menunjukkan kondisi malam/low-light global. Hipotesis: kendaraan jauh/kecil atau detail gelap dengan latar langit terang dapat menyulitkan deteksi. Tidak ada inference; hasil dan besar risikonya UNKNOWN. | frames/frame_000000000.png, frames/frame_000002570.png, frames/frame_000005140.png |
| low_light_tracking_risk (HYPOTHESIS_UNTESTED) | Hipotesis belum diuji: detail kecil/gelap, kendaraan masuk sebagian dari tepi frame, dan teks tertanam dapat memutus pengamatan yang diperlukan tracker. Sampel pagi ini tidak membuktikan ketahanan tracking pada malam hari; tidak ada tracker dijalankan. | frames/frame_000002570.png, frames/frame_000007711.png, frames/frame_000007718.png |
| low_light_reid_risk (HYPOTHESIS_UNTESTED) | Hipotesis belum diuji: kendaraan jauh dengan detail terbatas serta perubahan ukuran dan tampilan belakang dapat menyulitkan pembandingan identitas; teks tertanam dapat mencemari crop dekat tepi kanan. Risiko low-light malam tidak dapat diukur dari video pagi ini dan ReID belum dijalankan. | frames/frame_000002570.png, frames/frame_000005125.png, frames/frame_000005140.png, frames/frame_000007711.png, frames/frame_000007718.png |
| potential_failure_cases (HYPOTHESIS_UNTESTED) | Hipotesis kasus gagal yang perlu diuji nanti: kendaraan kecil di kejauhan; objek terpotong batas kanan saat masuk; teks putih menutupi piksel kendaraan; variasi skala besar sepanjang lintasan; arah diagonal keliru jika memakai sumbu X saja; crossing dekat batas frame dengan riwayat track terlalu pendek. Tidak ada kegagalan model atau counting yang telah dibuktikan. | frames/frame_000002570.png, frames/frame_000005125.png, frames/frame_000005154.png, frames/frame_000007711.png, frames/frame_000007718.png, frames/frame_000007725.png |
| technical_questions (OPEN) | OPEN: di mana garis dan polygon TOR3-PAGI ditempatkan agar kendaraan memiliki cukup riwayat sebelum crossing dan tidak bertumpuk dengan watermark? Bagaimana Side A/B serta mendekat/menjauh dikonfirmasi per video? Anchor center atau bottom-center? Apakah objek kecil/jauh dan crop berwatermark memenuhi kebutuhan fase model berikutnya? Adakah shake singkat di luar burst? Bagaimana source PTS berbeda dari waktu index/FPS? Semua perlu bukti/keputusan lanjutan, tanpa memulai Phase 2. | frames/frame_000000000.png, frames/frame_000002570.png, frames/frame_000005140.png, frames/frame_000007711.png, frames/frame_000010281.png |

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
