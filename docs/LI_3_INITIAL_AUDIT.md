# LI-3 — audit awal dan rencana pelaksanaan

Audit ini ditulis sebelum perubahan implementasi LI-3. Brief owner disimpan
sebagai sumber tugas; seluruh hasil berikutnya harus dibedakan dari audit ini.

## Fakta yang diverifikasi

- Repo memakai helper notebook/file, bukan framework app. AGENTS dan workflow
  mewajibkan perubahan kecil, deterministic evidence, tanpa metric/hasil palsu.
- LI-0 validator memeriksa context/source/artifact hashes dan coverage gate.
- LI-1 `location_intelligent_buildings.py` menerima canonical GeoJSON,
  menjalankan seleksi N1, dan menyimpan reject ledger. Tidak perlu ditulis ulang.
- Overture probe/normalizer dan validasi source nyata sudah ada. Retained
  package `results/location_intelligent/overture_20261021_n1_verified/`
  berisi2623record rilis2026-10-21.0/schema2.0.0,1322selected. Subtype seluruh
  selected null; jangan mengklaim positive residential atau population accuracy.
- Capacity helper sudah menghitung N1 dengan unit terpisah; unknown/final
  capacity tetap explicit. Sumber ini cukup untuk cache reuse yang tervalidasi.
- Motor helper memakai graph `li_directed_graph_v1`, evidence hash-bound,
  node-bound connector, directed edge-state routing, resolved blocked turns,
 7km/h dan round(total_minutes)<=10. Existing synthetic baseline158tests.
- Konfigurasi editable saat audit `motorcycle_experiment_v7`; approved N1
  longitude106.8101931806858, latitude-6.430669461543375, metric CRS32748;
  technical example, bukan TGDI. Building radius400m/125m access berasal
  reference/config; N1 source mencantumkan graph bbox5500m radius.
- System Python3.13.5 mempunyai GDAL/PROJ; source env Python3.12.14 mempunyai
  DuckDB2.0.0/httpfs. OSMnx belum dipasang di source env saat audit.
- Public Overture/OSM tidak memerlukan token pada flow ini. Managed network
  policy unrestricted; actual Overpass availability belum terbukti. Tidak
  memeriksa atau mengungkap nilai credential. Env Traffic tetap terpisah.
- Tracked changes milik pekerjaan sebelumnya: .gitignore, README.md,
  docs/PHASE_9_TASK.md. Tidak diubah oleh task LI-3. Existing results immutable.

## Gap dan risiko yang ditemukan

1. Belum ada acquisition OSM drive_service+motor supplements, snapshot atau
   graph nyata. Filter mobil dapat menghilangkan ruas motor-legal.
2. Raw conditional restrictions/via-way turn relations belum punya parser
   lengkap. Kondisi yang tidak didukung harus dikarantina/ditandai unknown,
   bukan dilewati diam-diam.
3. Belum ada connector generator/barrier geometry check. Proximity tidak
   membuktikan akses. Absence barrier di OSM bukan physical verification.
4. Node-bound routing memerlukan edge splitting yang menjaga arah, source
   IDs dan restriction mapping. Geometric crossings tidak boleh menjadi nodes.
5. Existing engine membangun adjacency/Dijkstra per candidate; real graph dan
   banyak connector memerlukan indeks reuse yang menjaga cost/hops/ID tie-break.
6. Belum ada frozen LI-3 scope, normalized provenance sidecars, atomic manifest
   dependencies/checksums, replay command dan per-building status reconciliation.
7. Snap toko terdekat versus kelas tertinggi lintas seluruh graph perlu
   klarifikasi; pertanyaan dikirim. Pekerjaan graph/tests tidak bergantung jawabannya.

## Rencana implementasi

1. Freeze target/config/source refs dan geographic bounds. Gunakan N1 graph
   bbox radius5500m sebagai extraction scenario terdokumentasi; bukan jaminan
   global completeness. Cache reuse bangunan harus memverifikasi bytes/hashes.
2. Tambah acquisition adapter terpisah dengan request/status/raw cache,
   drive_service serta supplementary motor filters, barrier/water/restriction
   extraction; gagal request menghasilkan RETRIEVAL_FAILED, bukan empty success.
3. Normalize raw OSM ke unsimplified directed graph per source node/way,
   permissions/unknowns, node barriers, grade separation dan turn relations.
4. Generate audited entrance assumptions, reject ledger dan connector geometry;
   split edge dengan source lineage. Tidak membuat bridge/U-turn baru.
5. Integrasikan helper existing, menambah indeks routing bila terbukti perlu;
   preserve API/baseline tests dan hash source sebelum perubahan.
6. Jalankan pilot, status per building, kapasitas terpisah, diagnostic cases,
   frozen outputs dan deterministic replay tanpa network. Full provider/physical
   completeness dan actual speed/population tetap tidak diklaim.

Ordinary tests harus offline. Live retrieval hanya melalui explicit acquire
command. Final report mengukur apa yang benar-benar dijalankan dan mencatat
blocker yang tersisa; UI/Recount/PPAC/TGDI/Traffic inference di luar scope.
