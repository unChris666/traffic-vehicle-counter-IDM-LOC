# Review Phase 6 — Opsi A, TOR3-PAGI

**EXPERIMENT RESULT:** prototype counting audit-gated berhasil dijalankan pada retained evidence TOR3-PAGI. Gate teknis Phase 6 **PASS untuk scope prototype ini**: event-level output, subtotal kategori, deduplikasi yang dapat diaudit, tes sintetis, review pixel nyata dan visualisasi keputusan. Hasil ini belum membuktikan total lalu lintas lengkap, keandalan identitas seluruh video, atau kesiapan produksi.

**USER DECISION:** pengguna mengizinkan Phase 6 dengan metrik passage, aturan unit/rider, kategori, deduplikasi, genuine return, eligibility serta parameter/schema eksplisit. Konflik ditahan di luar subtotal accepted. [Kontrak](COUNTING_CONTRACT.md), [tugas](PHASE_6_TASK.md) dan [authorization provenance](evidence/phase_6/authorization/phase_6_option_a.json) mempertahankan keputusan dan pilihan eksperimen secara terpisah.

## 1. Eksekusi dan input aktual

Run **`20261012T144625_030645Z`**, 12 Oktober 2026 UTC, dieksekusi dengan nbclient pada notebook [06_counting_audit.ipynb](../notebooks/06_counting_audit.ipynb), Python 3.12.14, CPU Codex. Counting retained evidence berlangsung sekitar 1,498 detik pada run ini; bukan pengukuran throughput pipeline video/model. GPU dan original video tidak diperlukan untuk counting.

Input yang diverifikasi:

- Cache Phase 4 `reid_on`, run `20261011T095924_205716Z_90cf7319`, 10.282 frame dan 48.228 raw detector-linked emitted-track observations.
- Diagnostik Phase 5 `b0_c1`, run `20261011T161440_100155Z_2e39a11c`.
- Geometri G3 diterima, native 1280×720, BC pengukuran mentah; koordinat dan aturan Phase 5 tidak diubah.
- [Konfigurasi eksplisit](evidence/phase_6/config/TOR3-PAGI_option_a_v0.json): `metric=passage`, `review_policy=audit_gated`, `neutral_band_px=0`, `confirmation_observations=1`.
- [Input review aktual](evidence/phase_6/reviews/TOR3-PAGI_option_a_reviews.json), terikat ke identitas input dan SHA/frame evidence.

**ENGINEERING EXPERIMENT:** b0_c1 dipakai sebagai kontrol tersimpan agar kontrak counting dapat diuji. Nilai tersebut bukan threshold produksi yang sudah dipilih. Tidak menjalankan ulang YOLO, BoT-SORT, ReID atau geometry state machine. Video hanya didecode sebelumnya untuk review pixel terarah, bukan untuk membentuk trajectory baru.

Hash input, source code, config/review bytes dan runtime tercatat dalam [report.json](evidence/phase_6/20261012T144625_030645Z/report.json). Store, koordinat lokasi dan day type yang tidak diketahui tetap null. Recording period pagi berasal dari deskripsi pengguna. Timestamp frame/FPS adalah estimasi; authoritative source PTS tetap UNKNOWN.

## 2. Hasil counting

| Lapisan output | Hasil aktual |
|---|---:|
| Complete measured geometry candidates | 160 |
| Ambiguous-gap audit items | 6 |
| Total keputusan kandidat/audit | 166 |
| Machine accepted sebelum review | 0 |
| Resolved accepted CountEvents unik | **18** |
| Pending audit items | **141** |
| Rejected rider/component candidates | **7** |

Machine-zero berarti belum ada acceptance tanpa review pada konfigurasi audit-gated, bukan tidak ada lalu lintas. Ketujuh rejected adalah kandidat/transisi dari empat track person yang direview, bukan tujuh orang unik.

| Kategori accepted | Subtotal passage |
|---|---:|
| Motorcycle | 16 |
| Car | 1 |
| Truck | 1 |
| Pedestrian | 0 |
| Bus/angkot | 0 |
| **Total** | **18** |

Arah accepted adalah A→B mendekati kamera **1**, B→A menjauhi kamera **17**. Nol kategori lain berarti belum ada event kategori itu yang diterima dalam snapshot ini; tidak membuktikan ketiadaannya di video.

[Accepted events](evidence/phase_6/20261012T144625_030645Z/accepted_events.jsonl.gz), [aggregate](evidence/phase_6/20261012T144625_030645Z/aggregate.json), [summary](evidence/phase_6/20261012T144625_030645Z/summary.json), [audit queue](evidence/phase_6/20261012T144625_030645Z/audit_queue.jsonl.gz) dan [CSV review](evidence/phase_6/20261012T144625_030645Z/review_queue.csv) disimpan terpisah. Pending/rejected tidak masuk subtotal. Tidak mengedit total manual atau menjumlahkan snapshot rerun.

**Batas:** 18 adalah subtotal passage yang didukung review terbatas menurut kontrak, bukan complete-video traffic count, jumlah kendaraan unik seluruh video, batas bawah yang dijamin benar, atau evaluasi accuracy.

## 3. Review pixel dan penyelesaian kasus

[Review aktual](evidence/phase_6/review_samples/TOR3-PAGI/pixel_review.json) mencakup **23 kasus, 94 frame unik dan 46 contact sheets raw/overlay yang benar-benar dibuka**. Review dibantu AI Codex; bukan human review formal atau ground truth. Input counting berisi 27 keputusan eksplisit: 18 CONFIRM_PASSAGE, 7 REJECT_COMPONENT, 2 HOLD. Kandidat lain tetap pending. Frame/crop/native-source hashes dan transforms dipertahankan dalam [sample index](evidence/phase_6/review_samples/TOR3-PAGI/sample_index.json).

| Kasus | Bukti dan keputusan |
|---|---|
| Car ID1 | Hatchback perak konsisten pada origin/passage/confirmation. Raw overlap dengan motorcycle ID3 pada frame60 merupakan dua kendaraan yang berbeda pada foto; konflik screening diselesaikan lewat review, bukan auto-merge. Accepted satu car passage. |
| Motorcycle ID973 / ID964 | Raw dan overlay frame5128/5129/5130 menunjukkan satu skuter merah. Root membuka kembali kedua sheets untuk adjudikasi. ID973 mempunyai pengukuran motorcycle dari origin5129 sampai confirmation5130 dan mewakili **satu** passage. ID964 mempunyai histori origin→confirmation person→motorcycle, tetap HOLD/hard pending `UNIT_COMPONENT_CHANGE`; linkage same physical unit/passage tidak memperbaiki anchor history atau menghasilkan count kedua. Event973 menyimpan related nonaccepted candidate964. |
| Person IDs893,912,967,1774 | Foto menunjukkan komponen orang yang duduk pada sepeda motor, bukan pedestrian berjalan tersendiri. Ketujuh geometry candidates ditolak sebagai unit hitung mandiri. Transisi balik bbox person tidak membuktikan U-turn/genuine return. |
| Truck ID1520 | Foto origin/passage/confirmation menunjukkan truk kargo kuning dengan bak tinggi dan kabin terpisah. Accepted truck; keputusan ini tidak menetapkan taxonomy pickup. |
| Car ID1323 | Bentuk minivan/minibus merah terlihat, tetapi kategori bisnis car versus angkot belum dapat diputuskan dari evidence/kebijakan saat ini. HOLD, di luar subtotal. |
| ID1772 | Origin person→motorcycle merubah unit pengukuran. Tetap hard pending; mereview rider ID1774 tidak mengesahkan vehicle crossing1772. |
| Gap candidates | Enam ambiguous gaps tetap pending dan tidak bisa disahkan lewat review/interpolasi. |

Sisa motorcycle accepted: IDs311,394,443,461,693,829,923,1144,1346,1372,1389,1408,1478,1824,1887. Evidence scope untuk masing-masing ada dalam input review; physical unit references bersifat lokal pada window yang direview, bukan jaminan global-video identity.

Frekuensi alasan pending dalam summary **tidak saling eksklusif**: termasuk overlap identity screening135, unit-component change24, role unresolved61, category conflict4, bus/angkot mapping1 dan ambiguous gap6. Angka overlap bukan jumlah duplikasi fisik yang terkonfirmasi. Banyak kandidat belum direview; backlog tidak boleh dianggap seluruhnya false positive.

[Visualisasi crossing](evidence/phase_6/20261012T144625_030645Z/crossing_visualizations/README.md) menghubungkan foto aktual dengan keputusan akhir kasus, source frames dan event/candidate references. Header menunjukkan hasil akhir review kasus, bukan running counter pada setiap frame; foto sumber tidak diubah untuk menggambarkan trajectory baru.

## 4. Validasi yang benar-benar dijalankan

- **59/59 tes sintetis PASS**, tanpa failures/errors/skips; dijalankan independen dan kembali sebagai guard notebook sebelum input aktual. [Laporan guard](evidence/phase_6/20261012T144625_030645Z/synthetic_test_results.json).
- **195/195 pemeriksaan artefak sample review PASS**: hashes, native/crop source links dan source evidence. [Validation](evidence/phase_6/review_samples/TOR3-PAGI/artifact_validation.json).
- **5.183/5.183 independent retained-artifact assertions PASS**: 10.282 cache rows dibaca tanpa pipeline rerun, 4.003 referensi pengukuran diverifikasi, source/full class windows, declared photo frame/hash scope, hard gates, candidate/review/config/event ID math, pemisahan output mesin/resolved dan rekonsiliasi agregasi. [Independent audit](evidence/phase_6/20261012T144625_030645Z/independent_artifact_audit.json), [script reproduksi](evidence/phase_6/verification/check_phase6_artifacts.py).
- **36/36 pemeriksaan komposisi visualisasi PASS**: 12 gambar dari enam kasus benar-benar dibuka; seluruh pixel foto sumber tetap identik sesudah penambahan header di luar foto. [Validation dan cakupan](evidence/phase_6/20261012T144625_030645Z/crossing_visualizations/README.md). Gambar pending1772 memakai konteks track1774 dengan label eksplisit, bukan bukti passage lengkap1772.

Dua bug fixture ditemukan sebelum eksekusi input aktual dan diperbaiki: intersection touch yang mempercayai titik retained, serta episode simultan same-unit yang dapat diterima sebagai return hanya lewat review flag. Intersection kini dihitung dari titik terukur dan divalidasi; distinct passage IDs dengan positive temporal overlap ditahan. Regresi mempertahankan return terpisah, termasuk arah sama dan shared boundary. Tidak mengklaim ada genuine return fisik yang berhasil divalidasi pada video ini: kemampuan tersebut baru diuji sintetis; kandidat person recross yang direview ditolak.

Idempotensi rerun, repeated updates dan koreksi kategori diuji pada fixture. Actual video counting dieksekusi sekali; tidak ada klaim actual whole-video rerun comparison. Independent audit menghitung ID/agregat dari output tersimpan, bukan menjalankan model/helper pipeline kembali.

Hash memverifikasi identitas artefak, bukan kebenaran interpretasi visual. Tes dan reconciliation membuktikan perilaku software yang diuji; tidak menggantikan formal evaluation. Tidak ada accuracy, precision, recall, F1 atau MAPE yang dilaporkan.

## 5. Keputusan yang ditetapkan dan yang masih OPEN

**Ditetapkan untuk prototype Opsi A:** physical passage; kendaraan bersama rider/penumpang satu unit; raw person wajib role review; full origin–confirmation class/unit history; identity overlap screening; explicit same-unit/same-passage dedup tanpa trajectory merge; representatif hard-eligible deterministik; independent return review dan temporal contradiction guard; immutable machine/review/resolved layers; typed accepted CountEvent dengan stable IDs; accepted-only aggregate snapshot.

**OPEN:**

1. Taxonomy/pemetaan pickup, minivan, bus/angkot dan aturan category evidence yang sesuai bisnis.
2. Suitable jitter/neutral-band/confirmation defaults: 0px/C1 tetap kontrol eksperimen, tidak dipilih dari subtotal accepted.
3. Recovery unit-changing anchor history dan resolusi identitas otomatis/lintas ID; tidak diselesaikan dengan override latest class.
4. Suitable vehicle-domain ReID configuration dan manfaat fisiknya. ReID tetap arsitektur, encoder person-domain Phase4 belum dipilih sebagai vehicle default.
5. Penyelesaian backlog dan completeness audit seluruh video; low-light/other-video generalization belum diuji counting.
6. Authoritative source PTS, metadata lokasi/day type yang belum tersedia, dan keputusan production versioning/schema.

## 6. Langkah berikutnya

Gate **software prototype Phase6 PASS**, sementara penerimaan hasil traffic lengkap/produksi belum terpenuhi. Rekomendasi terdekat adalah melanjutkan audit pending Phase6: prioritaskan kategori/unit/duplicate yang memblokir counting, tetapkan taxonomy bisnis, lalu tambahkan review hash-bound dan hasilkan snapshot baru. Jangan mengurangi pending dengan melonggarkan hard geometry/unit gates atau mengedit subtotal.

Untuk membaca hasil sekarang tidak perlu rerun. Buka report, audit queue dan contact sheets. Untuk mereproduksi kemudian dari root checkout:

```bash
python notebooks/phase_6_synthetic_tests.py
python docs/evidence/phase_6/verification/check_phase6_artifacts.py \
  docs/evidence/phase_6/20261012T144625_030645Z \
  /tmp/phase6_independent_artifact_audit.json
```

Script audit menerima run directory dan output report sebagai dua argumen positional; output di `/tmp` mempertahankan laporan audit pertama tanpa menimpanya. Untuk generating counting snapshot, buka `notebooks/06_counting_audit.ipynb`, sesuaikan explicit paths dan pilih **Run All**; Kaggle dapat memakai checkout yang sama tanpa GPU untuk fase ini. Phase7, UI, Docker, multi-GPU dan refactor produksi belum dimulai.
