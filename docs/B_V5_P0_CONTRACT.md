<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# B v5 — kontrak penelitian P0 setelah QC

Status: implementasi/eksperimen yang diotorisasi pengguna pada 20 Oktober 2026.
Ini versi penelitian baru, belum default produksi. Hasil aktual dan keputusan
kelulusan berada di [review B v5](B_V5_P0_REVIEW.md).

## Lingkup dan baseline

- Baseline machine B v4 TGDI-WEEKDAY-SIANG: 172 accepted, 68 pending, 9.128
  frame sumber. Snapshot, executable B v2–v4, dan paket QC tidak diubah.
- P0 memakai cache model terverifikasi dan geometri native 640×480 yang sama.
  Tidak menjalankan detector/tracker/ReID atau enhancement dalam replay P0.
- Eksperimen model dilakukan setelah replay P0 pada output yang terpisah,
  dengan otorisasi baru pengguna. Mengubah model bukan bagian terselubung dari
  perbaikan counting.
- Machine tetap mempertahankan input review lama yang sudah eksplisit.
  Rekomendasi QC baru tidak disisipkan menjadi prediksi otomatis.

## Perilaku yang diuji

| Lapisan | Kontrak penelitian | Pengaman |
|---|---|---|
| Identitas | Nama historical clique merupakan hipotesis; objek independen dipertahankan sampai ada bukti lokal positif atau review berbatas | Bukti masa depan tidak berlaku mundur; category sama bukan bukti same-unit |
| Episode | Konteks objek yang putus tidak mewariskan origin atau timer ke objek berikutnya | Gradual same-class handoff tetap bisa unresolved; jangan mengklaim semua reuse ID selesai |
| Relasi | SAME_UNIT, COMPONENT_OF, dan DIFFERENT_UNIT membawa scope episode/frame dan status bukti | Overlap/co-motion tanpa bukti cukup menjadi konflik, bukan penggabungan otomatis |
| Eligibility | Translasi badan bbox dan deformasi anchor diperiksa selain perpindahan BC | BC sumber tetap anchor crossing; tidak memakai bbox union, rider, cargo atau prediksi |
| Finalisasi | Selesaikan duplikasi passage sebelum agregasi; bukti terukur diutamakan atas estimasi untuk passage fisik yang sama | Upgrade +0, pergantian ID saja bukan genuine return; konflik tetap ditahan |

Algoritme numerik baru adalah **PROPOSAL penelitian yang diimplementasikan
untuk diuji**, bukan threshold produksi. Kontrolnya disimpan eksplisit pada
`results/b_v5/config/policy.json`; detail keputusan per kandidat ada pada audit
eligibility/finalization run. Perubahan hasil harus dinilai terhadap passage
fisik yang sama, termasuk regresi karena gate terlalu konservatif.

## Keputusan yang dipertahankan

Timeout tetap 60 **frame sumber** sejak observasi origin terakhir, setelah
eligibility terpenuhi dan tanpa konflik identitas terkait. Margin tetap 25 px
setengah lebar pada geometri TGDI native. Measured dan inferred tetap terpisah;
route LINE_MARGIN sendiri tidak membuktikan crossing terukur. Satu motor
beserta rider/passenger merupakan satu unit. Role unknown bukan pedestrian.
Kategori tetap memakai aturan in-band yang ada; taxonomy baru tidak dipilih.
Genuine return yang mempunyai bukti passage baru tetap dapat dihitung.

Band-born, perluasan role generik, taxonomy BUS/angkot/pickup/minivan, encoder
vehicle-ReID final, dan generalisasi malam/tujuh video lain adalah P1/keputusan
lanjutan. Tidak ada refactor Phase 10, UI, Docker atau deployment.

## Validasi dan interpretasi

Urutan wajib: fixture sintetis positif/negatif → replay seluruh riwayat pilot →
perbandingan sumber untuk 68 pending, 16 cancellation proposals dan discovery →
review regresi → eksperimen konfigurasi detector terpisah.

Jumlah accepted atau pending yang lebih kecil tidak membuktikan peningkatan
akurasi. Sebuah event lama yang hilang bisa menjadi false-count yang dicegah
atau passage benar yang ikut tertahan. Sebuah alias sumber di event canonical
tidak otomatis berarti duplikasi masih ada. Tidak ada ground truth formal dan
tidak ada klaim zero mistakes.

Koreksi terhadap narasi QC lama: event raw3555 pada baseline adalah
LINE_MARGIN **inferred**, tanpa pasangan crossing pada payload event; event
motor3563 mempunyai crossing terukur 6260→6261. Bukti keduanya berasal dari
satu motor bermuatan tetap relevan, tetapi 3555 tidak boleh dipromosikan menjadi
measured. Paket QC lama dipertahankan immutable; erratum ini terpisah.
