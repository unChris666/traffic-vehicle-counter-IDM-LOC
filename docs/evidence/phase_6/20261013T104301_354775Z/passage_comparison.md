# Perbandingan per passage TOR3-PAGI — Opsi A/B

**EXPERIMENT RESULT:** pembacaan snapshot retained, tanpa menjalankan model, state machine atau resolver kembali. Scope memakai track **dan** frame crossing/confirmation dalam satu window inklusif. Lima passage adalah reference review terbatas, bukan ground truth atau total lalu lintas.

| Snapshot | Accepted passage | Manual | Otomatis | Item keputusan dalam scope |
|---|---:|---:|---:|---:|
| A_original | 3 | 3 | 0 | 14 |
| A_updated | 3 | 3 | 0 | 14 |
| episode_only | 0 | 0 | 0 | 6 |
| B_machine | 1 | 0 | 1 | 6 |
| B_reviewed | 4 | 3 | 1 | 6 |

| Passage / sumber unit | A original | A updated | Episode-only | B machine | B reviewed |
|---|---|---|---|---|---|
| car1 | 1 car; ID1 (manual) | 1 car; ID1 (manual) | pending; ID1 | pending; ID1 | 1 car; ID1 (manual) |
| motorcycle923_rider912 | 1 motorcycle; ID923 (manual) | 1 motorcycle; ID923 (manual) | pending; ID923 | pending; ID923 | 1 motorcycle; ID923 (manual) |
| red_scooter964_973_rider967 | 1 motorcycle; ID973 (manual) | 1 motorcycle; ID973 (manual) | pending; ID964, ID973 | pending; ID964, ID973 | 1 motorcycle; ID964 (manual) |
| car1323 | pending; ID1323 | pending; ID1323 | pending; ID1323 | pending; ID1323 | pending; ID1323 |
| motorcycle1772_rider1774 | pending; ID1772 | pending; ID1772 | pending; ID1772 | 1 motorcycle; ID1772 (otomatis) | 1 motorcycle; ID1772 (otomatis) |

## Audit salah gabung, duplikasi, kategori dan sumber crossing

- **ID1772/1774:** B mengeluarkan satu motorcycle dari episode kendaraan ID1772, origin7716, crossing7721→7722. Origin person7712 pada A tidak diwarisi; rider1774 crossing7717→7718 tidak menjadi sumber passage kendaraan. Event mesin dipertahankan verbatim pada B reviewed.
- **ID964/973:** A memakai ID973 untuk satu skuter yang sama; ID964 lama mixed person→motorcycle tetap pending. B membuat episode kendaraan baru origin5122 tetapi kedua kandidat otomatis pending. Pair motion residual maksimum0,057293 melampaui kontrol0,01, sehingga deduplikasi otomatis tidak terbukti berhasil. B reviewed secara eksplisit menyatukan satu passage, memilih kendaraan ID964 crossing5128→5129; ID973 menjadi duplicate support tanpa count tambahan.
- **ID923/912:** bukti hubungan yang lolos pada frame5116–5122/5128–5131 tidak membuktikan identitas crossing5028→5029. Gate passage-local v1 menahan kandidat; manual review frame origin5017 dan crossing5028/5029 mengesahkan satu motorcycle pada snapshot reviewed. Hubungan aktual in-window gagal kontrol relative motion; later pixel identity terhadap passage awal tetap UNKNOWN.
- **ID1323:** keputusan pengguna car tersimpan pada A updated review meskipun top-level kategori legacy HOLD tetap null. B raw temporal category car tidak menyelesaikan rawcar kecil/d3 di tepi kendaraan yang physical identity-nya UNKNOWN; seluruh snapshot tetap pending.
- **ID1:** A review mengonfirmasi satu car; overlap motorID3 merupakan kendaraan berbeda. B mempertahankan pending tanpa bukti identitas otomatis positif; B reviewed memakai bukti pixel retained yang sama.
- **Kontrol ID880/892:** review menunjukkan dua kendaraan berbeda; mesin menolak SAME_VEHICLE. Ini satu negative nyata lintas gerakan, bukan bukti generalisasi. COMPONENT_OF893/880 didukung, tetapi crossing kendaraan880 frame4987→4988 di luar window4975–4980; kontrol ini tidak menambah accepted passage pembanding.

Semua event accepted menggunakan raw vehicle BC dari source detection yang terhubung ke track. Tidak menggabungkan bbox, mengganti anchor dengan rider atau menyambung trajectory lintas ID. JSON menyimpan bbox/source-index/frame untuk origin, crossing dan confirmation serta keputusan tiap namespace.

## Batas

- Five passage references and bounded pixel reviews do not establish general performance.
- A is reviewed; B_machine is automatic; B_reviewed retains explicit manual decisions.
- The B grouping/category/episode policy differs from A; episode-only isolates removal of grouping, not every changed factor.
- Raw label unanimity on a full vehicle episode is an offline category control, not business taxonomy or online stability.
- Source IDs from separate configuration namespaces must not be appended or summed together.
- A track-only inventory in the executed notebook includes out-of-window880; this postprocessor applies both scope constraints.

Data lengkap: [JSON](passage_comparison.json), [CSV](passage_comparison.csv).
