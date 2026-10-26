<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Keputusan pengguna setelah review P0 B v5

Tanggal: 20 Oktober 2026, Asia/Bangkok.

Status: **keputusan bisnis terbaru, belum diterapkan pada pipeline**. Dokumen
ini melengkapi [kontrak P0 sebelumnya](B_V5_P0_CONTRACT.md). Snapshot dan hasil
eksperimen B v5 tetap merupakan riwayat kebijakan sebelumnya; angka117/65 tidak
dihitung ulang atau dinyatakan sudah mengikuti keputusan ini.

## Keputusan yang dikonfirmasi

| Pokok | Keputusan pengguna | Dampak yang perlu dipertahankan |
|---|---|---|
| Arah berbeda | ID dan tipe sama tetapi arah passage berbeda tidak dideduplikasi | Perubahan arah saja tidak menambah count; passage baru tetap perlu bukti yang valid |
| Pasangan ambigu | Kendaraan berdekatan yang tidak dapat diputuskan boleh sama-sama tidak dihitung | Scope invalid per kandidat/passage terkait, bukan blacklist raw ID selamanya; catat pengurangan cakupan |
| Origin/timer | Tidak perlu memaksakan pemulihan konteks lama; gunakan skema hilang dari polygon asal | Eligibility dan konflik identitas tetap diperiksa sebelum timeout; raw ID baru bukan bukti kendaraan/passage baru |
| Muncul menjauhi garis | Kendaraan yang muncul di polygon dan bergerak menjauhi garis tidak dihitung dari kemunculan itu | Arah harus didukung trajectory; satu frame kemunculan tidak membuktikan gerak |
| Peran | Rider bergerak bersama kendaraan; pedestrian bukan pengendara | Ko-motion merupakan bukti pendukung, bukan bukti tunggal keanggotaan unit |

**REQUIREMENT — taxonomy terbaru:** pickup→TRUCK; cargo van, minivan dan
angkot→CAR; BUS→BUS. Pemetaan cargo van→CAR menggantikan usulan lama
cargo van→TRUCK. Motorcycle dan pedestrian tetap kategori yang sudah ada.
BUS perlu diteruskan ke schema, agregasi, panel dan ekspor. Prefix tampilan
`B` untuk BUS adalah **PROPOSAL implementasi**, mengikuti format ID per passage.

Pemetaan bisnis tidak mengarang hasil pengenalan subtipe: label mentah detector
tidak menyediakan label pickup/minivan/angkot. Ketika subtipe belum diketahui
dari bukti, sistem tidak boleh menganggapnya sudah teridentifikasi.

## Pengaman yang tetap berlaku

- Satu unit fisik, satu passage, maksimal satu event aktif. Pergantian raw ID
  tidak dengan sendirinya memulai passage baru.
- Timeout60 **frame sumber** sejak observasi origin terakhir tetap merupakan
  estimasi; hanya episode eligible tanpa konflik identitas relevan yang boleh
  menghasilkannya. Tidak diperlukan penyambungan paksa terhadap konteks lama.
- Passage yang sudah selesai tidak dibuka ulang oleh ID baru atau timer.
  Kendaraan berbalik sebelum crossing tidak otomatis menjadi passage baru.
- Jika ID berganti sebelum crossing dan hubungan antar-ID ambigu, dua timeout
  independen tidak boleh dianggap solusi. Kandidat terkait harus ditahan atau
  diselesaikan sebagai invalid/+0 sesuai scope konflik yang terbukti.
- Persetujuan +0 untuk pasangan ambigu tidak berarti semua kendaraan yang
  berdekatan harus dibuang. Kriteria konflik harus eksplisit; overlap/arah sama
  saja belum membuktikan dua observasi adalah satu unit.
- Rider pada motor yang berhenti tetap rider. Pedestrian yang berjalan di
  sebelah motor dapat bergerak searah tetapi tetap pedestrian. Role memerlukan
  hubungan tubuh/kendaraan dan scope temporal; unknown bukan pedestrian.
- Invalid akibat ambiguitas dipisahkan dari tidak eligible karena tidak
  melintas. Invalid/+0 tidak membuktikan lalu lintas sebenarnya nol. Hasil
  merupakan subtotal konservatif dengan jumlah invalid yang dilaporkan.
- Raw vehicle BC tetap sumber crossing; bbox union/rider/prediksi tidak
  menggantikannya. Measured, estimated, invalid dan pending tetap dibedakan.

## Tugas implementasi berikutnya

1. Versikan kebijakan baru secara terpisah dari B v5. Tambahkan keputusan
   invalid ambiguity, taxonomy BUS dan reason codes tanpa menimpa hasil lama.
2. Uji positif/negatif:4251/4281 satu motor; arah balik terukur yang berbeda;
   dua kendaraan terpisah yang berdekatan; ID berubah di polygon asal;
   namespace/family4934 berubah; gradual ID reuse2445; objek muncul menjauh.
3. Replay cache pilot yang sama tanpa inference model baru, lalu audit efek
   kebijakan baru per passage. Ukur hitungan palsu, duplikasi, salah merge,
   passage terlewat dan invalid yang disengaja; bukan pending saja.
4. Putuskan gate P0 ulang dengan kebijakan cakupan baru. Risiko undercount yang
   diterima pengguna tidak menyelesaikan kemampuan mengenali unit fisik secara
   otomatis; residual duplicate dan kebocoran timer tetap blocker.
5. P1 terkontrol: role temporal, band-born, vehicle-ReID, benchmark berlabel,
   dan kondisi malam. Confidence0,10 belum dipromosikan menjadi default.

Ini rencana berikutnya, bukan klaim implementasi atau hasil eksekusi baru.
