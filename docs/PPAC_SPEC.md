<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# PPAC modular — status aktif MVP v2

Formula referensi tersedia di `counter-ppac/`; implementasi modular berada di `src/traffic_location/ppac`. Entry point integrasi: `ppac_parameters_mvp_v2`. Hasil berunit STD/hari; ini belum validasi prediksi penjualan nyata.

Residential memakai jumlah bangunan yang dialokasikan ke calon toko x4 dan policy zona40/60 atau35/45/20. Fasum memakai penjumlahan jarak: <=400m mendapat2, >400..800m mendapat1. Traffic memakai profil jalan PPAC dan observasi weekday/weekend; sepeda tidak diwajibkan pada MVP. Lookup koefisien Residential dan balance tidak digunakan; multiplier1 adalah keputusan MVP, bukan hasil penelusuran lookup.

Input bisnis: hari operasional/minggu, faktorSWOT, profil jalan, jam/hari, drive-thru, potonganTraffic dan faktorparkir, beserta provenance. Durasi300–306detik diterima tanpa rescaling. Hasil PARTIAL dapat dipakai sambil mempertahankan kualitasPARTIAL; sumber/frame/context harus valid. Jam>15 menunggu sesi shift3 tambahan; dilarang mengekstrapolasi empat sesi untuk18jam.

Kegagalan atau input wajib hilang menghasilkan BLOCKED dan STD null. Gate v1 lama tetap lebih ketat dan memerlukan koefisien eksplisit. [Kontrak runtime](GATE2_INTEGRATION.md), [status lintasengine](CURRENT_STATUS.md).

## Riwayat audit sumber sebelum formula ditemukan

# PPAC — interface, batas makna dan gate bisnis

Status **BLOCKED untuk perhitungan SPD**. Dokumentasi interface tersedia;
tidak ada implementasi atau formula produksi baru. [Register sumber](LOCATION_INTELLIGENT_OVERVIEW.md#register-sumber)
membedakan task, notebook, legacy dan materi yang belum tersedia.

## Yang ditemukan dan yang belum disetujui

N1 mengambil kolom historis `SPD`, `PERIODE`, PNL/EBIT/EBITDA dari BigQuery
untuk nearest/similar store detail; nilai itu di-cast string, bukan dihitung
sebagai prediksi baru. Kehadiran kolom SPD bukan approval formula PPAC.
Unit kolom historis tersebut **UNKNOWN**, belum terbukti struk/hari. Query
expectations dan missing schema evidence dirinci pada
[SRC02/SRC13](DATA_SOURCE_INVENTORY.md); jangan memakai nama kolom sebagai
mapping label bisnis.

Legacy LOC-PPAC mempunyai estimasi `KK_Total`, Huff attractiveness/distance
allocation dan `KK_Expected_Aman`; itu bukan rule struk-per-day Traffic+Area
yang disetujui. Data source/metodenya juga berbeda dari Overture N1.
Tidak ditemukan formula SPD yang approved pada sumber yang dapat diperiksa.
Workbook baseline Excel, business brief terpisah, constants dan ground-truth
evaluation belum tersedia. Jangan mengisi multiplier dengan nilai contoh.

## Interface yang diusulkan

Boundary konseptual, bukan API yang sudah implemented:

```text
evaluate_ppac(context, traffic_features, coverage_features,
              business_rules_ref, excel_baseline_ref, evaluation_policy_ref)
    -> status, missing_requirements, feature_lineage,
       spd_estimate, breakdown, assumptions, validation_scope
```

PPAC consumes versi immutable fitur; tidak mengubah engine Traffic Counter,
threshold akses Area Coverage, ledger review, atau polygon Recount.

| Input | Isi/constraint minimum |
|---|---|
| Context | Target sama, analysis ID/revision, date/time context dan unit |
| Traffic features | Passage per category/direction dan observed duration; branch pilihan; measured/estimated terpisah; coverage/missing-slot flags; source/run/config hashes |
| Coverage features | Eligible/accessible building count, capacity fields dengan unit yang disetujui, unknown/coverage flags, source/model version; legacy mixed household tidak dianggap resident count |
| Recount features jika dipakai | Polygon revision, universe/predicate, union membership dan coverage; tidak menjumlah overlapping subtotals |
| BusinessRulesRef | Formula ID/version, constants beserta units, source/owner/approval/effective date; perubahan membuat hasil revision baru |
| Excel baseline | Workbook/version/hash, sheet/range/column definitions, dates dan formula/reference provenance; bukan file yang dianggap ada karena disebut brief |
| Evaluation policy | Observed SPD labels, independent split/scope, metric dan batas penerimaan yang disepakati; tidak dipilih setelah melihat hasil agar lolos |

## Keputusan yang wajib diselesaikan

1. **Unit kapasitas:** household/KK vs dwelling unit vs resident-equivalent vs
   occupied room vs hotel guests. Pilih feature yang bermakna dan konversi
   bila ada bukti; jangan menjumlah mixed units N1.
2. **Traffic→harian:** definisi hari, lokasi/durasi tiap sample, interval yang
   diwakili pagi/siang/sore/malam, missing slots, weekday/weekend/holiday
   weighting. Delapan sample singkat tidak otomatis mewakili24jam.
3. **Unit traffic dan kategori:** physical passage bukan orang unik harian;
   rider+motorcycle tetap satu vehicle unit. Kategori/direction weights atau
   konversi passage→struk membutuhkan aturan bisnis, bukan asumsi CV.
4. **Evidence level:** measured-only vs penggunaan estimated timeout/gap,
   unknown identity/role, manual-reviewed vs machine. Simpan breakdown dan
   pilih satu snapshot; jangan menghitung ulang kendaraan karena ID berubah.
5. **Data tidak lengkap:** exclude/block vs estimasi bisnis yang approved,
   uncertainty/sensitivity policy dan syarat completeness. Missing input
   tidak boleh menjadi0 demand; tidak membuat synthetic video/traffic.
6. **Baseline bisnis:** formula/Excel yang sah, definisi observed SPD,
   target/period alignment dan owner persetujuan constants.
7. **Pembanding statistik:** tujuan/model/features, label quality, spatial/
   temporal split, baseline comparator, leakage controls, metrics dan minimum
   evidence. Belum ada model/threshold terbaik yang dipilih.

Per-video filter recipe berbeda diperbolehkan bila provenance dan validasinya
tercatat. Keberhasilan preview/smoke tidak mengesahkan fitur counting harian.
ReID final serta night generalization tetap mengikuti gate Traffic sendiri.

## Gate dan output

G0: target/source/unit/period sejalan → G1: engine output dan coverage layak
untuk feature yang dipilih → G2: formula/constants disetujui dan dimensionally
consistent → G3: baseline/label/evaluation tersedia → G4: hasil dapat direplay
dan breakdown direkonsiliasi. Gate belum lolos menghasilkan `status=BLOCKED`
dengan `spd_estimate=null`, bukan0 atau angka ilustratif.

Output usulan mencatat SPD dalam **struk/hari** dengan scope/calculation version,
contribution breakdown sesuai formula approved, raw/normalized features,
measured-estimated/review treatment, capacity units, missing inputs,
formula/constants/Excel hashes, uncertainty yang memang didefinisikan, dan
evaluation refs jika benar-benar dijalankan. Tidak mengarang confidence interval
atau accuracy dari satu lokasi. Simpan hasil business baseline dan pembanding
statistik sebagai metode berbeda; jangan mencampur prediksi dan label aktual.

Pekerjaan yang dapat dilakukan lebih dahulu hanya validasi schema/unit dan
adapter feature read-only dengan fixture. Engine SPD aktual menunggu keputusan
[D04/D11–D14](AREA_COVERAGE_DECISIONS.md).
