<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# LI-3 — review implementasi dan pilot N1

22 Oktober2026. Tugas: [brief owner](LI_3_TASK.md). Audit sebelum implementasi:
[LI_3_INITIAL_AUDIT](LI_3_INITIAL_AUDIT.md). Scope hanya Location Intelligence;
tidak menjalankan Traffic/model, UI, Recount atau PPAC.

**Status:** integrasi dan pilot teknis terlaksana, replay **PASS**; hasil
aksesibilitas pilot **PARTIAL**, bukan production/physical-access validation.
Unknown yang tersisa tidak diubah menjadi izin atau valid zero.

## Yang diimplementasikan

- Frozen N1 target/config/bounds: longitude106.8101931806858,
  latitude-6.430669461543375, metric CRS32748. Extraction memakai bbox radius
 5500m dari referensi N1; building radius400m tetap LI-1. Bukan lokasi TGDI.
- Adapter reuse actual Overture2026-10-21.0/schema2.0.0: checksum seluruh
  cached packet, re-normalize raw WKB dan compare canonical source, lalu
  existing LI-0/LI-1/capacity. Tidak mengunduh ulang Overture secara diam-diam.
- OSMnx2.1.1 drive_service filter + positive motor track/path dan
  motorcar=no/motorcycle=yes supplements; raw IDs/tags dipertahankan.
- Directed unsimplified graph berdasarkan source node IDs. Tidak membuat
  junction dari geometric crossing. Oneway/motorcycle direction override,
  per-direction access, private/prohibition, gate/portal dan unknown handling.
- Via-node no/only-turn normalization. Conditional/via-way/unsupported
  restrictions mengkarantina affected movements; tidak dilewati diam-diam.
- Entrance assumptions menghadap valid/reachable class tertinggi dalam125m;
  nearest valid road untuk toko tanpa numerical snap cap. Footprint obstacles,
  mapped water/fence/wall/gate, no direct entry to elevated/tunnel edges,
  reject ledger dan source-edge splitting dengan lineage.
- Existing motor/capacity helpers digunakan. Reverse edge-state index dan
  per-building geometry cache menggantikan pekerjaan berulang; baseline158tes
  tetap PASS. Original motor helper diarsipkan persis menurut hash di
  [before archive](evidence/location_intelligent/li3_before/manifest.json).
- Outcomes per source row, CSV/JSON, capacity per unit/per decision state,
  source-case review, static map, atomic manifest+DAG/checksums, code snapshot,
  software locks dan replay tanpa source retrieval.

## Sumber yang benar-benar digunakan

Bangunan adalah reuse packet nyata D34 yang diverifikasi kembali, bukan
fresh retrieval.2623records:1322selected+1301excluded+0rejected. Null subtype
pada seluruh1322selected memakai fallback legacy N1; bukan positive residential
classification. Consumed columns/types dan geometry/selection tervalidasi;
tidak mengklaim exhaustive official provider JSON Schema validation.

OSM benar-benar diambil dari `https://overpass-api.de/api/interpreter`, server
melaporkan `Overpass API 0.7.62.11 87bfad18`. Roads:170557elements,39926756
response bytes; barriers/water/turns:13879elements,3242929response bytes.
Angka tersebut bukan jumlah eligible roads. Payload semantic JSON lengkap
dipertahankan dalam gzip; transport response hash berbeda dari hash canonical
retained artifact, keduanya tidak disamakan. Attribution OSM/Overture tetap
ada pada raw sources dan building attrs.

Road timestamp03:58:06Z, feature timestamp03:59:06Z pada22 Oktober2026.
Historical timestamp-pinned request dan empat tile retries gagal karena
timeout/server memory; raw failure receipts dipertahankan. Pilot menggunakan
dua response awal, setelah semua overlapping elements cocok persis. Ini
**non-atomic source acquisition**, tetap warning/PARTIAL; tidak mengklaim
atomic snapshot atau mengendurkan izin motor untuk menambah accepted.

## Hasil dan denominator

| Outcome | Building count |
|---|---:|
| ACCEPTED menurut skenario |641|
| OVER_TIME_LIMIT |7|
| NO_VALID_CONNECTOR |54|
| ACCESS_UNVERIFIED |620|
| **Total selected LI-1** |**1322**|

1301source exclusions berada pada ledger/status terpisah; seluruh2623source
rows direkonsiliasi. Tidak menyatakan641 sebagai building yang terbukti bisa
diakses fisik. Semua route memakai7km/h sebagai asumsi dan Python
`round(total_minutes)<=10` (10.5 diterima;10.51 ditolak), bukan live ETA.

Graph setelah connector splitting:145318nodes/302820directed edges;
280576allowed,3559denied,18685unknown. Terdapat9119connectors dan90027rejected
candidate alternatives. Denominator rejection candidates berbeda dari buildings.
10108weak components mencakup8589isolated nodes pada allowed-edge subgraph;
239suspicious near-gaps hanya diagnostic10m, tidak diperbaiki dengan edge palsu.

Capacity seluruh selected:5288 standard reference units unresolved. Untuk
accepted scenario:2564 pada unit unresolved yang sama. **Keduanya bukan KK
atau penduduk.** Apartment/kos/hotel units tetap terpisah; special formulas
dibuktikan sintetis karena sampel ini tidak mempunyai selected special.
Tidak ada height/num_floors pada2623record. Mixed/final business capacity null.

## Review kasus

[Case inventory](../results/location_intelligent/li3_n1_20261022_v1/validation/case_review.json)
mencatat actual source IDs/tags dan contoh per decision state. Teramati pada
source:908one-way/roundabout ways,1774service/alley ways,416track/path dengan
positive motor tags,1847motorcar-ban/motorcycle-exception candidates,222private
ways dan17motorcycle-prohibition ways. Ini source observations, bukan semua
ruas tersebut lolos permission gate atau gang terbukti sempit.

53restriction relations diperiksa:30via-node normalized,23unsupported/conditional
quarantined. Delapan mapped bridge ways digunakan pada selected model paths;
off-road connector tidak dibuat menyeberangi water barrier. Grade-separated
entry ditahan; known geometric crossings tidak digabung. Source map telah
dilihat untuk QA spasial, bukan inspeksi jalan di lapangan.

Synthetic fixtures melengkapi kasus yang tidak dapat dibuktikan penuh di pilot:
oneway overrides, no/only/U-turn, conditional/via-way quarantine, private/gates,
river/open-gate distinction, grade separation, missing nodes/sources,
valid-empty versus retrieval error, connector125m boundary/unbounded target,
class/fallback/ties, exact rounded threshold, capacity units, checksum/DAG dan
determinism. Unit-test PASS bukan bukti semua real-world cases sudah teruji.

## Pengujian dan replay

**201tes PASS**:158existing LI tests pada system Python +43LI-3 offline tests
pada source env,0failure/error/skip. Log tersimpan di validation/.

Replay menggunakan snapshot code pada engine_source/, raw source/config dan
software versions yang sama. Network requests diblok selama replay, PROJ
network dimatikan pada core worker. **21calculation artifacts byte-identical,
0differences**, termasuk decisions, CSV, routes, graph, connectors, capacity,
normalized inputs dan reports. QA images/test logs bukan perhitungan yang
diklaim dibandingkan. Artifact hashes diverifikasi sebelum replay.

Replay receipt merujuk hash manifest origin yang disimpan terpisah, sehingga
final publication manifest dapat mencakup receipt tanpa circular hash.
[Replay receipt](../results/location_intelligent/li3_n1_20261022_v1/validation/replay_verification.json).

## Command dan lokasi hasil

Output: [li3_n1_20261022_v1](../results/location_intelligent/li3_n1_20261022_v1/report.md),
[CSV](../results/location_intelligent/li3_n1_20261022_v1/building_results/decisions.csv),
[map](../results/location_intelligent/li3_n1_20261022_v1/validation/pilot_overview.png).

```bash
PROJ_NETWORK=OFF /usr/bin/python3 -B -m unittest discover \
  -s notebooks -p 'location_intelligent_*tests.py' -v

PROJ_NETWORK=OFF /workspace/.venvs/location-intelligent-sources/bin/python \
  -m unittest discover -s notebooks -p 'li3_*tests.py' -v

PROJ_NETWORK=OFF /workspace/.venvs/location-intelligent-sources/bin/python \
  results/location_intelligent/li3_n1_20261022_v1/engine_source/notebooks/location_intelligent_li3.py \
  replay --root results/location_intelligent/li3_n1_20261022_v1 \
  --output /tmp/li3-n1-replay-new
```

Gunakan output baru. Freeze/acquire/build/manifest commands tersedia pada
notebooks/location_intelligent_li3.py. Source env diisolasi dari Traffic,
OSMnx/GEOS/PROJ/package versions dipin dalam config/source_requirements.lock;
system GDAL/core versions juga direkam. Tidak mengubah N1 engine/fixtures,
Traffic runtime atau data/results terdahulu.

## Keputusan status dan next action

Tidak ada klaim accuracy ETA, population, legal access atau production readiness.
LI-3 sudah menunjukkan integrasi nyata dan replay untuk scope pilot. **Status
hasil tetap PARTIAL**, karena620unverified, bounded/incomplete map coverage,
non-atomic timestamps dan23restriction relations belum fully interpreted.

Rekomendasi berikutnya: review unknown-access source cases dan source gap
sebelum mengubah kebijakan, prioritaskan23restriction relations serta
snapshot acquisition konsisten.18685unknown edges terdiri15998missing access,
2064access values requiring review,178turn quarantine, serta barrier/direction
uncertainties; jangan menambah izin hanya untuk menaikkan641accepted.
LI-4/UI/Recount/PPAC tidak dimulai otomatis.
