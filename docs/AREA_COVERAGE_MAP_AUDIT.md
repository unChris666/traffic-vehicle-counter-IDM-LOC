<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Audit tampilan Area Coverage —24 Oktober2026

Owner melaporkan koneksi BQ berhasil dan meminta audit bangunan/NO_ROUTE serta
tooltip luas/kelas dan warna jalan. Perubahan ini hanya presentation. Tidak
mengubah selection,125m, routing, kapasitas atau autentikasi. Hasil query privat
owner tidak diambil/dipublikasikan ulang; tes lokal memakai sumber publik frozen.

## Temuan terkonfirmasi pada snapshot target acuan

Target latitude-6.409737552410453/longitude106.82835008971841; Overture release
2026-10-21.0/schema2.0.0; sources9151, selected3597. Reject ledger mencatat5554
excluded:2328AREA_NOT_ABOVE_MIN,13AREA_NOT_BELOW_MAX,2CLASS_UNSUPPORTED dan
3211OUTSIDE_RADIUS. Batas area strict>45m² dan<550m² pada jenis standard.
Layer excluded sebelumnya show=false. Sekarang show=true; ini tidak menambah
jumlah selected atau accepted. Basemap OSM dan footprint Overture adalah sumber
berbeda; bangunan pada basemap tidak membuktikan polygon tersedia di Overture.
Belum ada ground truth inventori bangunan lengkap.

88NO_ROUTE memiliki reason NO_VALID_REACHABLE_CONNECTORS dan konektor valid.
Minimum candidate_distance_m per bangunan berkisar5.347–99.364m; semuanya<125m.
125m adalah jarak pencarian dari representative point ke geometri ruas, bukan
syarat cukup untuk rute sampai toko. Engine memisahkan NO_VALID_CONNECTOR,
ACCESS_UNVERIFIED, NO_ROUTE dan OVER_TIME_LIMIT. Kedekatan tidak memperbaiki
graph terputus, arah jalan, akses terlarang atau pembatasan manuver. Penyebab
individual rumah pada screenshot tidak dapat dipastikan tanpa ID/koordinat;
contoh kemungkinan tersebut bukan klaim diagnosis rumah tertentu.

## Implementasi dan cara review

- Tooltip: ID, luas full footprint dalam CRS proyeksi(m²), kelas/subtype sumber,
  status dan reason. Popup menambahkan selection status, connector count dan
  arti batas125m. Null class menjadi UNKNOWN, bukan label residential rekaan.
- Jalan: casing gelap; motorway/trunk oranye, primary/secondary kuning,
  tertiary krem, lokal putih, service abu, track/path putus-putus. *_link
  mengikuti kelas induk; unknown memiliki warna tersendiri. Ini ilustrasi
  hierarki OSM, bukan style resmi Google Earth. Warna bukan izin akses motor;
  tooltip jalan menyertakan access_allowed sebagai ALLOWED/DENIED/UNKNOWN.
- Cell9 notebook menjalankan renderer langsung dari source terlihat dan data
  PILOT/layers/facilities yang sudah dimuat. Tidak memanggil BQ, selection atau
  routing ulang. Tampilan mendapat revision/manifest terpisah pada
  OUTPUT/audit_views/<identity>/area_coverage_audit.html; hasil lama utuh.
- Source Kaggle diperbarui melalui QUICK_SAVE, bukan klaim background execution
  atas kredensial owner. Source auth pada saved version dipertahankan; perubahan
  hanya helper renderer dan cell9. Jalankan cell9 pada session dengan hasil
  sebelumnya untuk melihat peta baru. Generator lama bukan sumber authoritative
  notebook hand-edited ini; jangan menjalankannya tanpa menjaga auth/cell audit.

## Validasi aktual

23regression tests PASS. Fixture memeriksa luas123.45 dan null source class
ditampilkan sebagai UNKNOWN serta statusNO_ROUTE tetap utuh,400m per marker,
hierarki/link/unknown road styles. Fixture bukan bukti performa lokasi nyata.

Render seluruh9151footprint publik memuat luas/kelas/reason; tidak ada luas null
pada dataset valid tersebut. Layer excluded default aktif. Manifest kalkulasi
sebelum/sesudah identik. Browser:15layer toggle,0JS errors dan0resource failures.
Preview publik masih memakai BQ readiness lama BLOCKED, bukan hasil BQ owner
yang dilaporkan sudah berhasil. Tidak ada full query/routing/inference rerun.
