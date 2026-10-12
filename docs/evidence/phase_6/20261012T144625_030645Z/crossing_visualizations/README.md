# Visualisasi keputusan passage — snapshot Phase6

**EXPERIMENT RESULT:**12 PNG dari enam kasus dibuat berdasarkan
`resolved_decisions.jsonl.gz` dan `accepted_events.jsonl.gz` pada run
`20261012T144625_030645Z`. Setiap kasus memiliki versi raw dan versi overlay
yang berasal dari contact sheet pixel aktual yang sudah disimpan. Semua12
gambar hasil dibuka dan diperiksa; tidak ada eksekusi counting, model,
tracker, ReID, decoder video atau state machine geometri pada langkah ini.

Header di luar foto menyatakan **keputusan akhir pada level kasus**, bukan
counter atau status yang berlaku pada tiap frame foto. Header mencantumkan
candidate/event ID, kategori event yang telah disahkan, arah, interval
passage, frame konfirmasi geometri, waktu estimasi indeks/FPS, alasan dan
frame pada gambar sumber. Estimasi waktu bukan authoritative source PTS.
Foto/contact sheet tidak di-resize atau digambar ulang; padding putih hanya
memperlebar canvas untuk header yang dapat dibaca.

| Target | Snapshot akhir | Gambar overlay |
|---|---|---|
|track1|accepted, car|[Mobil](id1_accepted_overlay_case.png)|
|track973|accepted, motorcycle; satu skuter dengan representative973|[Skuter merah](id973_accepted_overlay_case.png)|
|track1520|accepted, truck|[Truk](id1520_accepted_overlay_case.png)|
|track1772|pending_review, UNIT_COMPONENT_CHANGE|[Konteks kendaraan](id1772_pending_review_overlay_case.png)|
|track1774|rejected, komponen pengendara|[Komponen orang](id1774_rejected_overlay_case.png)|
|track1323|pending_review, kategori/identitas belum disahkan|[Minivan/minibus](id1323_pending_review_overlay_case.png)|

**Batas bukti track1772:** gambar menggunakan contact sheet **track1774**
pada kendaraan yang sama, dengan frame7713/7716/7717/7718. Header dan index
secara eksplisit mempertahankan label sumber tersebut. Gambar ini tidak
menampilkan origin/passage/confirmation frame7712/7721/7722 dari track1772
dan tidak diklaim sebagai crop atau bukti passage lengkap track1772.
Alasan pending berasal dari snapshot retained, bukan dari inferensi atas
foto konteks.

Keputusan root untuk973 dicatat dalam review input run ini. Rekomendasi HOLD
yang lebih awal pada pixel review tidak ditulis ulang menjadi persetujuan.
Kandidat964 tetap pending dan tidak disajikan sebagai kendaraan kedua.

[visualization_index.json](visualization_index.json) mengikat source image
hash, input resolved/accepted hash, method hash, frame, dimensi dan posisi
penempelan foto. [validation.json](validation.json) merekam36 pemeriksaan
komposisi yang benar-benar lulus, termasuk kesamaan **seluruh pixel** gambar
sumber setelah header ditambahkan. Guard tersebut sempat menangkap satu
baris pixel yang tertimpa batas rectangle; batas diperbaiki menjadi
`header_height-1` sebelum artefak final dibuat. Ini pemeriksaan software,
bukan metrik performa counting.

[visual_review.json](visual_review.json) mencatat pemeriksaan visual aktual
terhadap12 artefak final. View tool dapat mengecilkan contact sheet truk
untuk display, tetapi berkas native dan pixel fotografi tetap utuh. Tidak
ada trajectory baru, cumulative counter, atau count event baru yang
digambar/diciptakan. Review ini tidak merupakan audit lengkap video atau
ground truth.

Reproduksi komposisi dari root checkout lengkap memerlukan Python dengan
Pillow, tanpa GPU atau video asli:

```bash
python docs/evidence/phase_6/verification/build_phase6_counting_visualizations.py --root "$PWD" --run "$PWD/docs/evidence/phase_6/20261012T144625_030645Z"
```

Command tersebut hanya menghasilkan PNG/index/validation. Catatan visual
merupakan hasil gambar yang benar-benar dibuka, bukan hasil otomatis script.
