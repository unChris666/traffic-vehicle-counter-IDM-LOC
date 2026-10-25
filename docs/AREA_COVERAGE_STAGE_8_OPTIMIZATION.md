# Optimasi bagian 8 — 25 Oktober 2026

## Scope dan kebijakan

Hanya implementasi market pada bagian 8. Sel sumber (5), kalkulasi (6), toko
BQ (7), dan seluruh helper konektor/motor/normalisasi tidak diubah. Notebook
mengubah cell writefile market runtime, digest instalasi helper tersebut,
petunjuk bagian 8 serta reload module di cell bagian 8.

Satu entrance, biaya konektor, hierarki, graph berarah, izin, turn restrictions,
Huff, zona/core, time threshold, status PARTIAL/UNKNOWN dan ledger semua baris
bangunan tetap berlaku. Tidak ada refetch dan tidak ada rerun kalkulasi nyata
bagian 6 untuk implementasi ini.

## Implementasi

1. Verifikasi paket beku bagian 6. Baca base graph/sumber edge dan konektor
   terpilih yang sudah disimpan; tidak mencari entrance bangunan lagi.
2. Generate konektor khusus target toko/POI dengan selected_buildings kosong;
   footprint semua bangunan tetap dipakai untuk pemeriksaan akses target.
   Cocokkan entrance calon toko dengan entrance beku yang dipakai bagian 6.
3. Gabungkan posisi akses bangunan lama dengan posisi target tambahan. Split
   ulang ruas dalam paket bagian 8 tanpa mengubah paket bagian 6. Reapply turn
   restrictions pada ID edge hasil split; node, edge, biaya dan bukti izin
   dibandingkan dengan rekonstruksi baseline pada tes.
4. Buat adjacency sekali per pemanggilan market. Untuk toko, gunakan algoritme
   reverse edge-state baseline dengan cost/hop/edge-ID tie-break yang sama.
   Dua toko dengan node akses sama berbagi satu pencarian tetapi tetap menyimpan
   biaya konektor, identitas dan skor toko masing-masing.
5. Validasi/panjang konektor bangunan dihitung sekali. Memo jarak/hash path
   digunakan selama satu tujuan, lalu indeks tujuan dilepas. Tidak menyimpan
   semua indeks rute toko sekaligus.
6. Jarak ke calon toko yang sudah tersedia di bagian 6 langsung dipakai.
   Routing alternatif hanya untuk bangunan residential berstatus ACCEPTED yang
   dapat mencapai tahap scoring; bangunan lain tetap punya baris/alasannya.
   Input toko tidak lengkap tidak memicu routing yang hasilnya akan dibuang.
7. Gate POI: satu penelusuran forward edge-state dari calon toko melayani semua
   tujuan POI. Bila ada edge UNKNOWN, satu penelusuran potential reachability
   tambahan hanya membantu klasifikasi UNKNOWN, tidak mengesahkan akses.
   Restoran tetap memerlukan luas, footprint, koridor dan cluster yang sama.
8. Cache hasil market lengkap tetap memverifikasi identitas/checksum. Timing
   dan progres ditampilkan untuk validasi, reuse konektor, adjacency, routing
   node toko serta gate POI. Pipeline tidak membuat klaim coverage dari input
   gagal/hilang.

Penelusuran gate forward memakai urutan akumulasi floating point maju. Tes
numerik random membandingkan jarak dengan reverse baseline pada toleransi
12 decimal places; ini bukan jaminan kesamaan bit untuk semua graph arbitrer.
Gate memeriksa keterjangkauan, bukan threshold atas jarak/waktu POI; threshold
bisnis dan jarak toko untuk Huff tetap memakai perhitungan baseline.

## Hasil pengujian aktual

- Suite Area Coverage: 95 tes, 81 lulus dan 14 skip (kebutuhan GDAL terpisah).
- Paket reused vs rebuilt: graph, edge sources, edge rules, turn restrictions
  dan seluruh konektor identik untuk profil multi/single, termasuk pembatasan
  belok supported dan conditional quarantine.
- Matriks rute toko: jarak, pilihan konektor, rank dan hash path sama dengan
  reachable_alternatives baseline. Dua toko pada node sama hanya membangun
  satu pencarian rute; kandidat dengan primary route tidak dicari ulang.
- Gate banyak POI memakai satu forward search. Random directed graphs dengan
  larangan transisi/edge UNKNOWN dibandingkan terhadap fungsi baseline;
  reachability sama, jarak setara pada toleransi di atas.
- Perbandingan end-to-end SYNTHETIC dengan commit 4a1e884: dua profil entrance
  x POI tersedia/tidak tersedia. Rows termasuk scores, summary, stores,
  excluded_stores, attractor_gate dan status input sama persis untuk empat
  fixture tersebut. Cache reopen sama dan tidak membentuk konektor ulang.
  Identity/fingerprint/output_path memang berbeda karena versi kode berubah.
- Bukti: results/area_coverage_map/stage8_optimization/synthetic_equivalence.json.
  Ini bukan hasil lokasi aktual atau benchmark durasi Kaggle. Tidak ada janji
  percepatan numerik pada seluruh dataset sebelum diukur.

## Menjalankan ulang hanya bagian 8

Bila kernel lama masih aktif dan bagian 6/7 sudah selesai:

1. Muat kode notebook terbaru dan jalankan cell
   `%%writefile .../location_intelligent_market_runtime.py` (helper implementasi).
2. Jalankan cell bagian 8. Cell ini reload helper sehingga tidak memakai module
   lama yang masih tersimpan dalam sys.modules.
3. Jalankan bagian 9 untuk memperbarui peta/ekspor.

Jangan Run All hanya untuk menguji optimasi ini pada sesi aktif, karena identitas
job notebook umum mengikat seluruh kode dan dapat membuat job kalkulasi baru.
Jika sesi sudah hilang, variabel dan paket hasil bagian 6/7 harus dipulihkan;
source cache saja tidak menggantikan paket kalkulasi. Tidak menyamarkan kondisi
itu sebagai hasil yang siap.
