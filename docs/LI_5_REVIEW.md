# LI-5 — Recount offline tanpa polygon manual

## Workflow owner terbaru — 23 Oktober 2026

[CURRENT_DEVELOPMENT_WORKFLOW](CURRENT_DEVELOPMENT_WORKFLOW.md) mengizinkan
kelanjutan teknis dengan evaluasi mandiri; review owner melalui UI input/output.
C01–C09 adalah working baseline provisional, tidak lagi menahan pekerjaan
independen sampai approval Markdown. Riwayat instruksi menunggu approval di
bawah menjelaskan keadaan sebelum arahan ini. Bukti hasil/run lama tidak berubah.
GCS dipilih untuk video/result; [setup/CRUD](GCS_STORAGE_ONBOARDING_PLAN.md)
belum dijalankan. [Stabilitas hasil](REPRODUCIBILITY_POLICY.md) wajib; fresh
inference tidak dibuktikan oleh frozen replay saja. Update ini dokumentasi.

23 Oktober 2026. **PASS untuk scope teknis offline eksperimen N1.**
Polygon demo dibuat otomatis; bukan batas wilayah bisnis yang disetujui.
Underlying accessibility tetap PARTIAL; LI-5 tidak menyelesaikan unknown akses.

Owner meminta LI-5 selesai tanpa menyediakan polygon manual. Dipakai profil
`LI5_EXPERIMENT_V1`, approval status EXPERIMENT_ONLY_BUSINESS_APPROVAL_PENDING.
Representative point tersimpan, covers, selected universe, subtotal per status,
union dedup dan no-refetch adalah aturan eksperimen eksplisit. Keputusan bisnis
final berada pada draf [kontrak kedua engine](ENGINE_IO_CONTRACT_DRAFT.md),
terutama C08. Tidak mengimplementasikan backend/UI produksi/modularisasi/PPAC.

## Input dan hasil aktual

Input adalah verified LI-4 N1 packet dengan parent manifest SHA256
`909987bb3114316f513d3035a92d1ff21a4fce5b4aa0ae1c3dc7deee5a0be166`.
5 input files diekstrak byte-identical dan diikat ke manifest parent lengkap:
buildings.json, summary.json, selected buildings, frozen policy/context.
Konteks menyatakan radius analisis400m. Compact packet dapat dibuka ulang
sendiri; tidak mengklaim seluruh raw sources LI-4 disalin lagi ke LI-5.

Seluruh2623source rows ada pada membership ledger.1322selected dievaluasi;
1301excluded tetap tercatat dengan recount_evaluated=false dan reason eksplisit.
Stored representative point dipakai; tidak menghitung ulang anchor bangunan
atau mengubah keputusan/rute/kapasitas sumber.

Demo WEST/EAST dibuat dari projected circles, dipotong saling overlap. R1 memakai
0.75×radius analisis, R2 memakai0.90×radius; overlap halfwidth0.15×radius,
quad_segs64. Angka ini engineering inputs demonstrasi, **bukan default radius
bisnis baru**. Polygon disimpan WGS84 dengan metadata generation/revision/claim.

| Hasil | R1 | R2 |
|---|---:|---:|
| WEST membership |364|584|
| EAST membership |430|654|
| Jumlah subtotal polygon |794|1238|
| Union bangunan unik |663|1072|
| Overlap yang tidak dihitung dua kali dalam union |131|166|
| Accepted menurut skenario dalam union |391|565|
| Access unverified dalam union |258|463|
| No valid connector dalam union |14|42|
| Over time dalam union |0|2|

Delta R1→R2:409masuk,0keluar. Ini dampak perluasan polygon, bukan peningkatan
akurasi atau izin akses. Full input masih641accepted/620unverified/54no-valid-
connector/7over-time. Kapasitas hanya subtotal per status/satuan; mixed dan final
business totals null. Nilai standard unresolved tidak menjadi KK/penduduk.

Kedua polygon berada dalam disk analisis yang dibekukan. Ini klaim geometri,
bukan completeness fisik/legal source maps. Polygon di luar domain berstatus
PARTIAL_OUTSIDE_ANALYSIS_DOMAIN, tidak mengambil sumber atau menyebut bagian
yang tidak dievaluasi sebagai0. Source quality PARTIAL tetap diwariskan.

## Implementasi dan penyesuaian

- `notebooks/location_intelligent_recount.py`: validate profile/polygon,
  membership, scope/units, delta, atomic export, immutable output dan verifier.
- `notebooks/fixtures/li5/policy.json`: profil eksperimen yang bisa ditinjau.
  Predicate covers/contains didukung eksplisit; semantik lain memerlukan
  implementasi/version baru. Jangan mengubah policy agar satu contoh lolos.
- `notebooks/li5_recount_tests.py`:31tes baru.
- Polygons masuk melalui CLI `build --polygons`, atau `demo` menghasilkan
  polygon otomatis. Belum ada drawing UI; tidak diperlukan untuk task ini.

Result version mengikat input fingerprint, polygon, policy, engine code hash
serta geometry/software versions. Hasil/run lama tidak ditimpa. Delta menuntut
source/policy/code/software sama dan revision ID baru bila geometri berubah.
Kapasitas dibaca dari hasil lama, hanya dijumlahkan per unit/status; tidak
mengulang formula. Tidak ada detector/tracker/ReID/counting/enhancement,
provider retrieval atau pemilihan rute yang dijalankan.

Output: result.json, membership.json/CSV (2623rows), polygons.geojson,
policy.json, delta.json, review.html SVG/tabel offline, compact frozen inputs,
archived engine dan manifest. Source keys memakai provider+snapshot/version+ID,
bukan hanya ID di satu file. CSV formula-like text escaped; null tetap null
pada JSON, tidak mengisi unknown capacity0.

## Pengujian dan reproducibility

**259tes PASS** =158existing LI +43LI-3 +27LI-4 +31LI-5,0failure/error/skip.
Kasus baru: inside/outside/boundary, covers vs contains, hole/hole boundary,
multipolygon, footprint-touch vs representative membership, invalid polygons,
duplicate IDs/source keys, empty request/records, nonfinite points, overlap,
outside domain, unknown access, null/mixed units, deterministic order, source
preservation, delta/version mismatch, overwrite refusal dan partial export failure.
Empty polygon set adalah explicit empty request, bukan missing source.

R2 dibuat ulang dengan sumber/config/polygon sama: **5outputs byte-identical**
(result.json, membership.json, membership.csv, delta.json, review.html).
Compact packet dipindahkan dan diverifikasi dengan archived engine saat socket
connections diblok. Geometry versions Shapely/GEOS/PyProj/PROJ dipin dalam
manifest/result dan diperiksa saat reopen. No upstream repo path diperlukan.

Browser QA offline:1322representative points,2623ledger rows, union1072,
0page errors/HTTP requests; desktop/mobile screenshots disimpan dan desktop
sudah diperiksa visual. Seperti LI-4, managed browser memblok file://; pengujian
memasukkan byte HTML via setContent. Bukan user-device/browser compatibility
certification. Peta skematis read-only, bukan surveyed positions atau drawing UI.

Bukti: [QA receipt](../results/location_intelligent/li5_n1_20261023_validation/receipt.json).

## Lokasi dan command

[R1](../results/location_intelligent/li5_n1_20261023_r1/result.json),
[R2](../results/location_intelligent/li5_n1_20261023_r2/result.json),
[delta](../results/location_intelligent/li5_n1_20261023_r2/delta.json),
[review HTML](../results/location_intelligent/li5_n1_20261023_r2/review.html).

```bash
PROJ_NETWORK=OFF /workspace/.venvs/location-intelligent-sources/bin/python -B \
  notebooks/location_intelligent_recount.py demo \
  --source results/location_intelligent/li4_n1_20261023_v1 \
  --output /tmp/li5-demo-r1-new --revision demo-r1

PROJ_NETWORK=OFF /workspace/.venvs/location-intelligent-sources/bin/python -B \
  notebooks/location_intelligent_recount.py demo \
  --source results/location_intelligent/li4_n1_20261023_v1 \
  --output /tmp/li5-demo-r2-new --revision demo-r2 --previous /tmp/li5-demo-r1-new

PROJ_NETWORK=OFF /workspace/.venvs/location-intelligent-sources/bin/python -B \
  results/location_intelligent/li5_n1_20261023_r2/engine_source/location_intelligent_recount.py \
  verify --root results/location_intelligent/li5_n1_20261023_r2
```

## Berikutnya: review kontrak, belum refactor

Tinjau C01–C09 pada [ENGINE_IO_CONTRACT_DRAFT](ENGINE_IO_CONTRACT_DRAFT.md).
Kontrak memisahkan execution/quality/coverage/disposition/evidence, Traffic
measured/estimated dan machine/reviewed, Location modeled/unknown/unit, serta
schema/code/model/source/result versions. Ini draf interface, bukan validator
atau API baru yang diklaim sudah berjalan. Setelah disetujui, buat schemas/
adapters+golden parity dan modularisasi bertahap. LI-6/PPAC/UI belum dimulai.
