# Location Intelligent — hasil tugas D34

## Terbaru: LI-3 N1

Pilot aktual: [report](li3_n1_20261022_v1/report.md),
[final review](../../docs/LI_3_REVIEW.md),
[CSV per source row](li3_n1_20261022_v1/building_results/decisions.csv),
[source map](li3_n1_20261022_v1/validation/pilot_overview.png),
[replay receipt](li3_n1_20261022_v1/validation/replay_verification.json).
Hasil PARTIAL;201tests PASS;21calculation artifacts replay identik tanpa network.
Tidak mengubah historical D34 outputs di bawah.

Hasil yang dipilih:

- [Report sumber nyata](overture_20261021_n1_verified/report.json).
- [Seleksi bangunan](overture_20261021_n1_verified/selection.json).
- [Kapasitas per building dan unit](overture_20261021_n1_verified/capacity.json).
- [Motor routing fixture](motor_policy_offline/routing_result.json), **synthetic**.

Lokasi contoh N1 disetujui untuk uji teknis; bukan TGDI. Overture2026-10-21.0/
schema2.0.0 diperiksa pada kolom/types yang dikonsumsi, normalization dan LI-1;
bukan exhaustive official schema validation.2623records=1322selected+1301excluded+
0rejected. Cap10001 tidak terpotong;512 STAC item bboxes diverifikasi dan satu
partisi intersect query. Kelengkapan bounded query bukan physical map completeness.

Seluruh1322selected mempunyai subtype null dan memakai fallback N1. Subtotal
standard5288 berunit `N1_STANDARD_VALUE_UNIT_UNRESOLVED`, **bukan KK/penduduk**.
Tidak ada height/num_floors pada2623records. Special formulas diuji sintetis;
zero selected special bukan bukti tidak ada bangunan special di lapangan.
mixed_unit_total/final_business_capacity tetap null.

Folder `overture_20261021_n1_probe/` adalah first attempt BLOCKED sebelum
coverage diverifikasi. Dipertahankan; gunakan folder **verified**. Raw probe
dan partition verification disimpan gzip, beserta hashes dalam report.

## Replay tanpa network

```bash
PROJ_NETWORK=OFF /usr/bin/python3 -B notebooks/location_intelligent_buildings.py \
  --context results/location_intelligent/overture_20261021_n1_verified/context.json \
  --manifest results/location_intelligent/overture_20261021_n1_verified/manifest.json \
  --root results/location_intelligent/overture_20261021_n1_verified \
  --source-ref overture-bounded-probe

PROJ_NETWORK=OFF /usr/bin/python3 -B notebooks/location_intelligent_motor_routing.py \
  --context notebooks/fixtures/li1/context.json \
  --manifest notebooks/fixtures/li1/manifest.json \
  --buildings docs/evidence/location_intelligent/li01_20261022/li1_fixture_result.json \
  --graph results/location_intelligent/motor_policy_offline/graph.json \
  --evidence results/location_intelligent/motor_policy_offline/evidence.json \
  --policy results/location_intelligent/motor_policy_offline/policy.json \
  --root notebooks/fixtures/li1
```

Motor CLI menggunakan config aktif bila --policy tidak diberikan, tetapi
evidence harus cocok dengan hash config. Mengedit config tidak mengesahkan
evidence lama. Dua CLI fixture runs byte-identical; lima building teraccount.
Tidak membuktikan akses motor nyata. Real LI-1/capacity offline replay identik.

## Akuisisi ulang eksplisit, output baru

```bash
/workspace/.venvs/location-intelligent-sources/bin/python \
  notebooks/location_intelligent_overture_probe.py \
  --bbox 106.8064931806858 -6.434369461543375 106.8138931806858 -6.426969461543375 \
  --row-limit 10001 --output /tmp/li-overture-new/raw.json \
  --extension-directory /workspace/.venvs/location-intelligent-sources/duckdb_extensions \
  --verify-partitions-output /tmp/li-overture-new/partitions.json

PROJ_NETWORK=OFF /usr/bin/python3 -B notebooks/location_intelligent_overture_validation.py \
  --raw /tmp/li-overture-new/raw.json \
  --context-template notebooks/fixtures/li1/context.json \
  --manifest-template notebooks/fixtures/li1/manifest.json \
  --output /tmp/li-overture-new/validation \
  --longitude 106.8101931806858 --latitude -6.430669461543375 \
  --partition-verification /tmp/li-overture-new/partitions.json
```

Source env: Python3.12.14, DuckDB2.0.0+httpfs, terpisah dari Traffic. System
Python3.13.5/GDAL diperlukan untuk normalization. Probe membaca GeoParquet via
HTTP range dengan bbox+row cap, bukan full dataset download. Ukuran retained
JSON bukan pengukuran transfer network/biaya. Tidak memasang OSMnx.

Masih belum ada graph motor nyata, automatic entrance/barrier adapter atau
conditional/restriction parser. LI-3 full belum selesai; PPAC/UI/Traffic tidak
dijalankan. Semua status harus dibaca sesuai batas ini.

## LI-4 N1 offline review — 23 Oktober 2026

[Paket mandiri](li4_n1_20261023_v1/README.md) ·
[Review HTML](li4_n1_20261023_v1/review.html) ·
[Bukti QA](li4_n1_20261023_validation/receipt.json) ·
[Review engineering](../../docs/LI_4_REVIEW.md).
PASS packaging/reconciliation, analysis PARTIAL. Semua 2623 source rows
dipertahankan; tidak mengambil data atau menjalankan routing ulang.

## LI-5 offline N1 — 23 Oktober 2026

[Review engineering](../../docs/LI_5_REVIEW.md) ·
[Draf kontrak engine](../../docs/ENGINE_IO_CONTRACT_DRAFT.md) ·
[Demo R2](li5_n1_20261023_r2/review.html) ·
[QA receipt](li5_n1_20261023_validation/receipt.json).
Polygon otomatis berlabel demo; union1072selected,565accepted skenario dalam
union. Akses source tetap PARTIAL, bukan seluruh1072bangunan accessible.

[Unduh paket LI-5 offline ZIP](downloads/li5-n1-offline-review-v1.zip)
(ekstrak seluruh folder, lalu buka R2/review.html). Kontrak tetap DRAFT.
