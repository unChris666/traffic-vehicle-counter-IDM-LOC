# B v4 — episode, eligibility, role, dan audit

Status: **eksperimen perbaikan yang diotorisasi pengguna**, bukan default produksi.
Baseline B v1/v2/v3, model cache, geometri, dan paket audit Phase 9 tetap immutable.
Implementasi berada di `notebooks/`; ini bukan refactor Phase 10.

## Batas perubahan

REQUIREMENT: raw ID, episode objek, identitas fisik, role, dan passage berbeda.
Satu physical unit/passage maksimal satu event aktif. Rider/passenger +0;
motorcycle + riders ditampilkan sebagai satu unit, tetapi anchor counting tetap
BC bbox kendaraan dari pengukuran sumber. Pergantian ID tidak membuktikan
passage baru atau crossing terukur selama gap.

B v4 mereplay seluruh riwayat cache video yang dipilih. Tidak menjalankan ulang
detector, tracker, ReID, atau enhancement. Video sumber digunakan hanya untuk
verifikasi dan rendering. Input tetap terikat SHA video/cache/geometri.

## Episode dan otoritas bukti

Riwayat dipisahkan ketika konteks menunjukkan raw ID berpindah objek/parent,
terdapat diskontinuitas spasial, atau gap melampaui horizon eksperimen.
Perubahan kelas saja tidak membuktikan pergantian objek. Role/kategori yang
direview bukan otorisasi penyambungan identitas. Penyambungan otomatis tanpa
bukti sumber positif tidak diaktifkan; pasangan yang mungkin terkait dapat
menahan estimasi terkait. Tidak ada appearance embedding baru yang diciptakan.

Episode baru tidak mewarisi origin, band, category votes, atau timer episode
lama. Kandidat lama ditutup sebelum observasi rider dikeluarkan dari counting.
Penutupan episode tidak membuktikan kendaraan sebelumnya tidak pernah melintas.
Physical identity yang belum direview tetap **asumsi**, termasuk ketika tidak
ada konflik yang ditemukan heuristik.

## Eligibility, clock, dan deduplikasi

Clock tetap **60 frame sumber sejak observasi terakhir di polygon asal**;
setiap observasi asal mereset clock, termasuk melalui handoff terverifikasi.
Tidak menambah frame sesudah EOF. Kandidat timeout memerlukan origin ROI,
pendekatan terukur yang positif, dan tidak memiliki konflik identitas relevan.
Pengukuran aktual yang masih menunjukkan objek terlihat menahan inferensi
hilang pada frame tersebut. Ini guard eligibility, bukan perubahan clock.

ASSUMPTION eksperimen baru: pendekatan memakai minimal tiga observasi pada
frame sumber berurutan dan net displacement menuju garis minimal 25 px,
dengan proyeksi akhir di segmen hingga. Angka 25 px meminjam half-margin geometri
native 640 saat ini; **bukan hasil tuning atau parameter lintasvideo tervalidasi**.
Gap tidak membentuk gerak terukur baru. Retreat sebesar displacement yang sama
membatalkan pendekatan sebelum band; jitter kecil saja tidak dianggap U-turn.
Crossing terukur tetap memakai finite intersection dan tidak dikenai gate
pendekatan ini, termasuk track pendek atau approach diagonal.

Fragmen yang pertama muncul di sisi tujuan lalu menjauhi garis tidak eligible
untuk timeout baru. Penyelesaian passage tidak dibuka ulang oleh elapsed time
atau raw ID baru. Upgrade estimasi menjadi bukti lebih kuat tetap +0 tambahan.
Genuine return terukur dapat menjadi passage baru. Kebijakan konservatif untuk
return timeout dan pedestrian inferred routes tetap mengikuti kontrol B v3.

## Role dan renderer

PROPOSAL eksperimen asosiasi komponen: bandingkan profil median temporal dengan
kontrol maksimum residual lama, sambil mempertahankan limit 0.15, minimal 3 frame,
BC-inside fraction1.0, dan center limit0.51. Median lebih tahan outlier tetapi
dapat menyembunyikan kegagalan singkat; ini harus diuji dengan counterexample.
Role hanya diterapkan pada observasi dalam interval positif yang didukung;
parent ambigu tetap UNKNOWN. Orang di dekat motor bukan otomatis rider.
UNKNOWN bukan pedestrian. Batas parent memakai episode, bukan raw ID saja.

Raw ID selalu ditampilkan lebih dulu, terpisah dari ID tampilan passage final.
Label offline sebelum activation ditandai belum dihitung. Panel memisahkan
accepted terukur/estimasi, log passage, pending, eligibility/timer, dan parent.
Union bbox hanya visual; anchor sumber tidak digeser. Ledger machine dan
review-assisted tidak dijumlahkan. Setiap frame render memiliki label sidecar.

## Penilaian dan keputusan terbuka

Uji sintetis memeriksa kontrak perangkat lunak, bukan akurasi video. Replay
membandingkan evidence raw/frame yang sama dengan baseline tersimpan; hash event
berbeda antarversi bukan bukti passage berbeda. Perubahan subtotal, pending,
atau jumlah asosiasi positif tidak cukup membuktikan perbaikan fisik.

Review wajib: kasus166/185, fragmen856 dan kemungkinan predecessor763/816,
role8571089 versus1161, pedestrian54 dengan BC tertutup overlay, pedestrian3025
di luar ROI, serta dua kendaraan berdekatan. Bounded adjudikasi AI54 disimpan
hanya pada branch review-assisted dengan provenance, bukan pelatihan model
atau ground truth independen. Taxonomy BUS, validasi malam yang lebih luas,
ReID kendaraan final, kontrol numerik produksi, dan audit seluruh video masih
terbuka.
