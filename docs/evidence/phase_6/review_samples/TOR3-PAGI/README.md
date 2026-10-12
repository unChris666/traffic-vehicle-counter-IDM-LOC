# Review pixel terbatas — kandidat passage TOR3-PAGI

**EXPERIMENT RESULT:** decoder asli memproses 10.282 frame native1280×720
untuk mengekstrak 94 frame exact yang dipilih pada 23 kasus. Frame5140
dibandingkan dengan PNG retained Phase2 dan memiliki pixel identik. Video asli
dan full frame tidak dimasukkan ke repository. Indeks decoder bukan
authoritative source PTS.

**Review yang benar-benar dilakukan:** 46 artefak contact sheet distinct,
masing-masing raw dan overlay untuk 23 kasus, dibuka dengan `view_image`.
[pixel_review.json](pixel_review.json) mencatat reviewer
`AI_ASSISTED_CODEX`, bukan reviewer manusia dan bukan formal ground truth.
Kontak yang lebih besar dapat diskalakan oleh viewer; berkas PNG yang
disimpan mempertahankan crop native tanpa resize.

[sample_index.json](sample_index.json) mencatat frame, crop, mapping panel,
source-detection index, emitted raw bbox, hash pixel native dan hash artefak.
Overlay terpisah memperlihatkan BC dari raw bbox track, garis G3, serta bbox
deteksi kendaraan pesaing yang beririsan positif. Raw detections hanya menjadi
bukti tambahan; tidak menghasilkan count event. Margin tampilan24px bukan
threshold model, identity association atau eligibility.

Semua 16 survivor screening kelas tunggal/tanpa overlap kendaraan direview,
ditambah ID973,967,1774,893,912 serta car1 dan car1323. Selection mencakup
origin, awal/akhir passage dan confirmation; frame yang sama didedup dan
konteks sebelum passage ditambahkan. Frame60 ditambahkan pada car1 karena
merupakan satu-satunya overlap kendaraan pada support window tersebut.
Seluruh support window diperiksa sebagai record, namun **hanya frame yang
dicantumkan** direview secara visual.

## Rekomendasi dari review ini

- 15 kandidat Motor dan satu Truck1520 didukung oleh unit/kategori/trajectory
  yang tampak konsisten pada sampel. Pengendara, penumpang dan barang bukan
  kendaraan tambahan.
- Car1 tampak sebagai hatchback perak. Motorcycle3 pada frame60 terlihat
  sebagai kendaraan berbeda; overlap bbox kecil tidak merupakan duplikasi
  mobil. Ini mendukung satu kandidat Mobil dalam scope review terbatas.
- Car1323 tampak sebagai minivan/minibus merah. Product-category mapping
  untuk minivan/angkot belum ditetapkan; review ini tidak memaksakan Mobil.
- ID973 dan964 mempunyai bbox motorcycle pada satu skuter merah. Rekomendasi
  review ini adalah HOLD identitas sampai kelompok dan representatif
  passage ditetapkan; tidak otomatis menambahkan kendaraan kedua.
- Person967,1774,893,912 merupakan komponen orang yang duduk pada kendaraan
  pada frame yang direview. Mereka bukan pedestrian independen dalam scope
  tersebut. Sampel893/912 tidak memperlihatkan U-turn yang mendukung
  genuine return; perubahan bbox person tidak membuktikan passage tambahan.

**Batas:** 17 rekomendasi kandidat kendaraan tersebut belum merupakan
`CountEvent` dan tidak menyatakan total traffic lengkap. Review ini tidak
mengaudit semua160 kandidat, tidak menjamin identitas unik sepanjang video,
dan tidak mendukung klaim accuracy/precision/recall/F1/MAPE. Mesin counting
dan schema review binding ditangani terpisah. Resolusi baru setelah review
ini harus memiliki provenance sendiri.

## Reproduksi ekstraksi

Input inventaris aktual dipertahankan dalam
[candidate_inventory_input.json.gz](candidate_inventory_input.json.gz),
termasuk source hashes dan label jelas bahwa hasilnya inventory, bukan event.
Script pembangun tetap sama dengan versi yang dieksekusi. Dari root checkout,
dengan video byte-identik tersedia di `/tmp` dan Python yang mempunyai OpenCV,
numpy serta Pillow:

```bash
python -c 'import gzip,pathlib; pathlib.Path("/tmp/phase6-review-inventory.json").write_bytes(gzip.decompress(pathlib.Path("docs/evidence/phase_6/review_samples/TOR3-PAGI/candidate_inventory_input.json.gz").read_bytes()))'
/workspace/.venvs/traffic-inspection/bin/python docs/evidence/phase_6/verification/build_phase6_review_samples.py --root "$PWD" --video /tmp/traffic-phase5-source/TOR3-PAGI.mp4 --inventory /tmp/phase6-review-inventory.json
```

Ekstraksi menghasilkan sample index dan contact sheets; ia **tidak**
menghasilkan verdict review atau count event. File review tersimpan hanya
mendokumentasikan gambar yang benar-benar dibuka dan hasil inspeksinya.
Tambahan manifest/archive input merupakan provenance arsip, bukan hasil
ekstraksi baru. Detector, tracker, ReID dan state machine geometri tidak
dijalankan ulang. Decoder video digunakan hanya untuk pixel review dari
indeks kandidat yang sudah tersimpan.
