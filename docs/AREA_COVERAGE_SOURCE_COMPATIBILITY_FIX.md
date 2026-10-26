<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Perbaikan kompatibilitas sumber — 25 Oktober 2026

## Bug yang direproduksi

Setelah profil satu entrance ditambahkan, source key tetap memakai snapshot
lama (kebijakan entrance adalah kalkulasi, bukan akuisisi). Namun sel 5 masih
memakai `assert source_manifest['config'] == CONFIG`. Snapshot lama tidak
mempunyai `building_entrance_profile`, sehingga assertion gagal dan sel 6
BLOCKED walaupun sumber yang sama masih valid. Perbandingan lama direproduksi
menjadi AssertionError pada fixture dengan satu-satunya perubahan field itu.

## Perbaikan

- `source_request_config` mengeluarkan hanya `building_entrance_profile` dari
  identitas akuisisi. Dipakai untuk konfigurasi network, validasi manifest
  sumber lama/baru, dan pembuatan manifest sumber baru.
- Manifest lama dibandingkan dengan aturan yang sama tanpa ditulis ulang.
  Source key notebook sudah mengecualikan field tersebut; konfigurasi entrance
  tetap masuk job key, frozen pilot, policy dan identitas hasil market.
- Sel 5 memakai `verify_market_source_packet`; koordinat, radius, mode network,
  config sumber lainnya, lokasi file dan checksum tetap diverifikasi.
- Assertion operasional sumber diganti exception berkode: SOURCE_CONFIG_MISMATCH,
  SOURCE_SNAPSHOT_CHANGED, SOURCE_PATH_INVALID, FROZEN_SOURCE_PACKET_MISSING,
  BUILDING_SOURCE_CAP_REACHED. Readiness/log menampilkan kode tanpa isi secret
  atau raw exception message. Source cap dan kebutuhan footprint/network tidak
  dilewati untuk menghasilkan status sukses.

## Pengujian yang dijalankan

- Empat regresi baru: reproduksi assertion lama; snapshot lama tanpa perubahan
  bytes; sel 5 -> sel 6 dalam ACQUIRE_ONCE/FROZEN dengan POI opsional gagal;
  serta penolakan perubahan koordinat/mode/radius/checksum dengan kode jelas.
- Suite Area Coverage: 89 tes, 75 lulus, 14 skip pada interpreter tanpa GDAL.
  Pengujian worker dan profil motor baru sudah dicatat pada dokumen single
  entrance; logika konektor/routing tidak diubah oleh fix ini.
- Smoke actual cells menggunakan sumber SYNTHETIC lama: sel 5 SUCCEEDED tanpa
  refetch, sel 6 kalkulasi fresh PARTIAL sesuai keterbatasan eksperimen; tiga
  baris sumber direkonsiliasi, profil single entrance aktif, manifest terverifikasi.
  Evidence: results/area_coverage_map/single_entrance/source_compatibility_smoke.json.
  Transport POI dimock dengan observasi fixture; tidak mengklaim API live diuji.

Tidak ada rerun penuh lokasi aktual Kaggle. Notebook terbaru harus dimuat dan
Run All agar helper/hash/perbandingan manifest sinkron. Jangan hapus snapshot
sumber untuk mengatasi bug ini. Gangguan API, sumber hilang/korup dan konfigurasi
lokasi berbeda tetap perlu dibedakan dari kesalahan kompatibilitas kode.
