<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# B v7 — konflik handoff trajectory sebelum publikasi offline

21 Oktober 2026. **PROPOSAL eksperimen**, bukan default produksi. Scope tugas
adalah blocker duplikasi B v6 pada TGDI-WEEKDAY-SIANG. Keputusan invalid/+0
mengikuti [kontrak B v6](B_V6_USER_POLICY_CONTRACT.md) dan
[keputusan pengguna](POST_P0_POLICY_DECISIONS.md). Semua executable, hasil,
review dan manifest B v1–v6 dipertahankan. Status eksperimen aktual disimpan
pada [review B v7](B_V7_HANDOFF_REVIEW.md).

## Input dan kontrol yang dibekukan

- Video aktual 640×480, 9.128 frame; donor measurements, geometri, review lama,
  YOLO26M, BoT-SORT, ReID dan raw preprocessing sama dengan B v6.
- Replay cache saja. Tidak ada inference detector/tracker/ReID/enhancement.
- Policy B v7 mengikat hash policy B v6; timeout tetap **60 frame sumber**.
- Machine output tidak memasukkan adjudikasi QC baru sebagai prediksi.
- `results/b_v7/verification/frozen_inputs_before.json` mengikat file historis
  sebelum perubahan B v7. Namespace baru hanya `notebooks/*v7*`, dokumen ini,
  review baru dan `results/b_v7/`.

## Hipotesis dan pemeriksaan konflik

**ASSUMPTION yang diuji:** gerak mendekati kecepatan konstan pada jendela
pendek dapat menyaring kandidat konflik lintas-ID. Prediksi tersebut tidak
membuktikan kendaraan fisik yang sama dan tidak mengisi BC selama occlusion.

1. Periksa pasangan kandidat aktif dengan raw ID berbeda, kategori dan arah
   sama, serta minimal satu event estimasi. Dua event terukur berada di luar
   eksperimen ini. Role rider/unknown-person tidak menjadi endpoint kendaraan.
2. Wajib ada dua konteks fisik yang eksplisit dan masa observasinya tidak
   bertumpang tindih. Gap positif maksimal horizon yang sudah ada, 60 frame.
3. Ambil **lima observasi kendaraan berurutan** terakhir sebelum gap dan lima
   pertama sesudahnya. Semua berasal dari raw bbox detector-linked, berada
   dalam window bukti kandidatnya sendiri. Tidak memakai observasi sesudah
   keputusan kandidat untuk melengkapi support. Lima adalah kontrol riset
   yang dinyatakan, belum parameter produksi atau hasil optimasi.
4. Fit OLS gerak center bbox pada kedua jendela. Gerak BC teramati harus
   mendukung arah event terhadap normal garis; kedua heading harus searah.
5. Translasi extent bbox endpoint memakai center hasil ekstrapolasi. Box
   prediksi maju harus beririsan dengan box endpoint sesudah gap dan box
   prediksi balik dengan box sebelum gap. Kedua irisan wajib berluas positif;
   sentuhan batas tidak cukup. Tidak ada toleransi piksel tambahan.
6. Bukti `DIFFERENT_UNIT` terverifikasi dan berscope konteks sumber menjadi
   veto. Bukti kategori/role tidak berubah menjadi bukti identitas. Kendaraan
   yang koeksis tidak dipasangkan oleh eksperimen handoff ini.

**PROPOSAL:** pasangan yang memenuhi pemeriksaan menghasilkan
`UNVERIFIED_ORIGIN_HANDOFF`, bukan alias atau penyambungan identitas. Hubungan
ini menyatakan konflik yang belum terpecahkan. Kendaraan berbeda yang mengikuti
jalur serupa tanpa bukti koeksistensi tetap merupakan risiko false conflict;
kontrol negatif dan review temporal diperlukan.

## Waktu keputusan dan perlakuan hasil

Engine B v6 dipakai sebagai kalkulasi kandidat privat. Kandidat tersebut belum
dipublikasikan atau diakumulasikan pada output B v7. Setelah seluruh video
tersedia, gate bersama memvalidasi endpoint/source support dan menyelesaikan
pasangan konflik sebelum mengembalikan hasil final offline.

- Hanya event aktif yang tepat disebut relasi konflik menjadi invalid/+0.
  Pending lama, kategori, unknown role dan passage lain tidak diubah.
- Kandidat target menyimpan `candidate_decision_frame`; keputusan invalid
  aktual memakai EOF sumber dan `finalization_mode=OFFLINE_BEFORE_PUBLICATION`.
- Log kandidat target memiliki `count_delta=0` serta
  `status=provisional_not_published`. Snapshot kompatibilitas bernama
  `cancelled_events` diberi `never_published=true`; bukan penambahan lalu
  pengurangan sementara pada panel.
- Tidak ada penggabungan episode, BC sintetis, alias raw ID global, event baru,
  atau perubahan estimasi menjadi measured. Passage balik sah tidak
  dideduplikasi karena arahnya berbeda.
- Satu passage yang terverifikasi pada review dapat menjadi **nol accepted**
  jika mesin hanya memperoleh konflik ambigu. Kehilangan tersebut dilaporkan
  secara eksplisit, bukan disebut pemulihan satu hitungan.

## Riwayat desain development

Percobaan awal meminta center prediksi masuk ke bbox lawannya. Pada fixture
aktual, pemeriksaan maju gagal, pemeriksaan balik lolos. Sumber dan hasil
gagal disimpan pada `verification/initial_center_gate_*`; kegagalan tidak
disembunyikan. Revisi menggunakan extent kedua box untuk pemeriksaan konflik
spasial dua arah, tanpa mengubah lima observasi, horizon 60, ukuran box mentah
atau parameter B v6. Ini revisi **development setelah melihat target**, bukan
hold-out atau validasi robustness. Kontrol jalur paralel terpisah, box hanya
bersentuhan, kendaraan berbeda, dan gerak satu arah saja wajib diuji.

## Validasi dan gate

Fixture aktual harus mereproduksi dua estimasi pada B v6, kemudian maksimal
satu accepted pada B v7 tanpa upgrade bukti. Jalankan regresi positif/negatif,
suite B v6/B v5 yang relevan, lalu seluruh cache 9.128 frame dengan policy dan
source snapshot yang dibekukan. Bandingkan berdasarkan scope passage dan
measurement sumber, karena namespace event berubah antarversi.

Review independen wajib memeriksa setiap event yang berubah, kendaraan berbeda
yang berdekatan, passage balik, serta estimasi yang tetap accepted. Gate target
dapat lulus ketika duplikasi yang diketahui tertahan dan kontrol terpelihara.
**Gate P0 keseluruhan tetap BLOCKED bila ada konflik identitas/crossing accepted
lain yang terkonfirmasi**, meskipun target dan seluruh tes software lulus.
Jumlah accepted/pending/invalid bukan ground truth, bukan jumlah kendaraan
fisik yang boleh dijumlahkan, dan bukan ukuran accuracy.
