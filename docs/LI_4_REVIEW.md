# LI-4 — paket review N1 offline, scope terbatas

23 Oktober 2026. **PASS untuk persistence, rekonsiliasi dan tampilan/ekspor
snapshot N1. Hasil aksesibilitas tetap PARTIAL.** Bukan validasi produksi,
akses fisik/legal, waktu perjalanan nyata atau populasi.

Owner mengizinkan LI-4 memakai snapshot N1 yang sudah dibekukan, dengan review
sumber akses berjalan terpisah. Tidak menunggu semua unknown selesai dan tidak
mengubahnya menjadi allowed. LI-5/Recount, PPAC, sumber baru dan aplikasi UI
produksi belum dimulai.

## Input dan batas perubahan

Input: `results/location_intelligent/li3_n1_20261022_v1/` dengan manifest
SHA256 `0f309776b1e6302aa67183818b0354725ff9d07a4338f1b723241b5e53676eb9`.
Seluruh 76 artefak sumber diverifikasi dan disalin byte-identical ke `snapshot/`
dalam paket baru. Tidak mengubah snapshot, konfigurasi motor atau engine LI-3.

Hanya join keputusan/capacity/selection yang tersimpan, rekonstruksi geometri
rute dari edge yang sudah dipilih, dan transformasi koordinat tampilan ke
EPSG:4326. **Tidak menjalankan retrieval, pemilihan rute, perhitungan kapasitas,
detector, tracker, ReID, counting atau enhancement.**

## Output

[Paket](../results/location_intelligent/li4_n1_20261023_v1/README.md),
[review HTML](../results/location_intelligent/li4_n1_20261023_v1/review.html),
[ringkasan](../results/location_intelligent/li4_n1_20261023_v1/summary.json).

- `review.html`: seluruh data tampilan embedded; tanpa CDN/tiles/API/server.
  Peta skematis footprint, filter status/pencarian, pagination, pan/zoom,
  pemilihan bangunan dan tampilan rute/konektor tersimpan.
- `buildings.json`, `buildings.csv`, `buildings.geojson`: seluruh 2.623 baris
  sumber; source_row_index menjadi identitas baris yang konsisten.
- `routes.geojson`: 648 rute tersimpan, termasuk 7 over-time; MultiLineString
  berurutan konektor bangunan, ruas jaringan, konektor toko. Edge IDs dipertahankan.
- `connectors.geojson`: 9.119 konektor yang dibuat LI-3, dengan status/asumsi
  sumber. Bukan semuanya konektor yang dipilih atau terverifikasi di lapangan.
- `summary.json`: denominator, status, capacity per status/satuan, asumsi,
  warning sumber, hash manifest input, policy dan attribution.
- `snapshot/`: bukti LI-3 lengkap. `engine_source/`: verifier/exporter dan
  template yang benar-benar digunakan. `manifest.json`: 90 file terikat hash.

CSV empty cell berarti null, bukan 0. Structured properties memakai JSON;
formula-like text diekspor dengan apostrophe. GeoJSON memakai [longitude,
latitude], bukan koordinat meter. Detail kandidat terpilih dan kelompok alasan
konektor ditampilkan; ledger sumber lengkap tetap disimpan. Alasan generik
`EVIDENCE_INCOMPLETE` belum menunjuk satu ruas penyebab secara pasti dan tidak
boleh dianggap sebagai diagnosis legal/physical access per bangunan.

## Rekonsiliasi aktual

| Outcome selected | Bangunan |
|---|---:|
| ACCEPTED menurut skenario |641|
| ACCESS_UNVERIFIED |620|
| NO_VALID_CONNECTOR |54|
| OVER_TIME_LIMIT |7|
| Total selected |1322|
| EXCLUDED_BY_SELECTION, denominator terpisah |1301|
| Seluruh baris sumber |2623|

Semua keputusan sama dengan snapshot LI-3. Tidak ada kenaikan accepted atau
klaim peningkatan akurasi. Capacity standard seluruh selected 5.288 unit
unresolved; accepted 2.564 pada unit yang sama, **bukan KK/penduduk**.
`mixed_unit_total` dan `final_business_capacity` tetap null. Pada subtotal
capacity, `unknown_buildings` menghitung estimasi numerik yang tidak tersedia;
bukan jumlah akses unverified maupun pengesahan unit bisnis.

Package status `SUCCEEDED_WITH_WARNINGS` menyatakan ekspor wajib lengkap;
analysis status tetap `PARTIAL`. Dua status ini dipisahkan di manifest dan view.
Warning non-atomic OSM timestamps, 23 restriction relations belum fully
interpreted, batas coverage, owner frontage/alley/gate assumptions dan 7km/h
sebagai skenario tetap dibawa ke hasil. Unknown tidak dianggap tidak dapat
diakses secara fisik.

## Kelulusan gate dan pengujian

**228 tes PASS:** 158 existing LI +43 LI-3 +27 LI-4; 0 failure/error/skip.
LI-4 regressions meliputi identity/source row gaps, candidate/summary drift,
unknown promotion, capacity multi-unit/null, edge continuity/permission,
CSV/JSON/GeoJSON equivalence, script/formula injection, missing/tampered files,
source symlink, overwrite refusal, partial write dan final verification failure.

Build memakai sibling staging directory. Manifest ditulis dan seluruh output
diverifikasi sebelum directory dipublikasikan. Exception menghapus staging;
output final tidak muncul pada simulated disk/export/verification failure.
Paket yang sudah ada tidak ditimpa. Tidak ada status sukses untuk ekspor gagal.

Paket nyata disalin ke direktori lain dan diverifikasi memakai archived engine,
socket connections diblok. Tidak membutuhkan repo asal atau re-fetch. CLI
archived juga diuji tanpa inherited Python bytecode settings agar tidak membuat
`__pycache__` yang merusak manifest paket.

Browser Chromium/Playwright diuji offline pada desktop 1440×1080 dan mobile
390×844: seluruh 2623 baris, filter unknown 620, pencarian, pagination, pemilihan
rute, reset selection saat filter berubah, tanpa overflow horizontal,
0 page errors dan 0 HTTP requests. Screenshot diperiksa sebagai QA tampilan.
**Batas:** managed browser memblokir navigasi `file://`; pengujian memasukkan
byte HTML ke browser lewat `setContent`. Pembukaan file langsung di browser
pengguna belum diuji di perangkat pengguna. HTML tidak memakai fetch/CDN.

[Bukti QA](../results/location_intelligent/li4_n1_20261023_validation/receipt.json)
terikat hash manifest paket dan source/test/browser script.

## Perintah

```bash
PROJ_NETWORK=OFF /workspace/.venvs/location-intelligent-sources/bin/python -B \
  notebooks/location_intelligent_li4.py build \
  --source results/location_intelligent/li3_n1_20261022_v1 \
  --output /tmp/li4-n1-new-package

PROJ_NETWORK=OFF /workspace/.venvs/location-intelligent-sources/bin/python -B \
  notebooks/location_intelligent_li4.py verify \
  --root results/location_intelligent/li4_n1_20261023_v1

PROJ_NETWORK=OFF /workspace/.venvs/location-intelligent-sources/bin/python -B \
  -m unittest discover -s notebooks -p 'li4_*tests.py' -v

node notebooks/li4_browser_smoke.cjs \
  results/location_intelligent/li4_n1_20261023_v1 /tmp/li4-browser-qa-new
```

Gunakan output baru; verifier semantic membutuhkan pyproj/PROJ sesuai versi
manifest. HTML sendiri tidak membutuhkan Python. Salin seluruh folder paket
agar link ekspor tetap tersedia. Browser QA membutuhkan Playwright dan Chromium,
bukan dependency kalkulasi atau paket HTML.

## Berikutnya

Review manusia terhadap peta/tabel N1 dan beberapa source-case unknown.
Perbaikan akses/restriksi/snapshot berjalan terpisah dengan run/version baru;
LI-4 tidak memberi izin motor baru untuk menaikkan accepted. Untuk LI-5,
sepakati universe Recount, predicate/batas polygon, overlap/union dan perlakuan
polygon di luar cakupan snapshot terlebih dahulu. Belum mengimplementasikan LI-5.

## Penjelasan kelengkapan dan kelanjutan

[Readiness, reproduksibilitas, cara membuka GitHub dan persiapan LI-5](LI_5_READINESS.md).
Mengganti koordinat saja belum cukup: cached building packet saat ini terikat
N1 dan target/CRS lain ditolak. GitHub blob tidak menjalankan HTML; distribusi
paket lengkap memakai Release ZIP, bukan klaim GitHub Pages aktif.
