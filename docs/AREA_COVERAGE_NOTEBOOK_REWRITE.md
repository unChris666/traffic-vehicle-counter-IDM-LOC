<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Rewrite eksekusi notebook —25 Oktober2026

Permintaan owner: hilangkan kegagalan impor helper lama dan tangani kegagalan
upstream500/502 tanpa traceback berantai atau hasil perhitungan palsu.

## Diagnosis dan perubahan

`from ... import load_optional_osm_pois` dapat gagal walaupun file baru sudah
tertulis karena module Python lama masih ada di sys.modules. File source yang
belum ditulis ulang juga merupakan kemungkinan; traceback saja tidak membedakan
keduanya.

Notebook kini berurutan dan source implementasi tetap terlihat penuh. Sebelum
impor konfigurasi, seluruh helper diverifikasi terhadap hash source cell yang
diharapkan, bytecode milik folder notebook dibersihkan, namespace helper lama
dilepas, lalu API wajib diimpor dari direktori yang tepat. Jika helper belum
lengkap, konfigurasi ditandai FAILED dan downstream BLOCKED; tidak meneruskan
import acak. Tidak memakai bootstrap ZIP tersembunyi.

Semua tahap setelah penulisan source memiliki readiness sendiri: dependencies,
configuration, bq_auth, sources, calculation, stores, allocation dan output.
Runtime/import/upstream error dicatat tanpa exception message/locals agar key
credential tidak masuk report. Trace metadata hanya filename/line/function.
Tahap yang bergantung pada input gagal tidak berjalan. MARKET lama dibersihkan
ketika upstream diulang; hasil session sebelumnya tidak ditampilkan sebagai
hasil job sekarang.

POI tetap opsional; unknown fasilitas tidak menjadi nol. Jaringan3km tetap
road-only; enam query fitur eksternal tidak diaktifkan. Algoritma selection,
routing, Huff dan kontrak ekspor tidak berubah dalam rewrite ini.

## Arti keberhasilan

Kegagalan server luar tidak dapat ditiadakan oleh notebook. HTTP500/502 ditangani
sebagai sumber belum siap. Laporan tetap dapat dibuka, sementara counts=None,
statusNOT_READY; bukan hitungan0 atau klaim market selesai. Jika alokasi sudah
ada tetapi ekspor gagal, overall statusEXPORT_FAILED, bukan sukses.

Readiness terbaru:
`/kaggle/working/results/area_coverage_market/notebook_readiness.json`.
Bagian9 selalu menampilkan status dan tautan laporan, termasuk bila input belum
tersedia. Bila hasil siap, peta/CSV/JSON/ZIP yang sama tetap dihasilkan.

Buka versi terbaru lalu Run All dari awal. Source checksum memerlukan seluruh
cell implementasi dijalankan, bukan hanya cell konfigurasi. Snapshot finalized
sebelumnya tidak dihapus; reopen/retry tetap terpisah dari refresh.

## Validasi

71 tes Area:61 lulus dan10 skip untuk runtime GDAL terpisah. Tes mengeksekusi
cell sumber, kalkulasi, alokasi dan output aktual notebook dengan upstream500
serta502 yang disimulasikan. Tidak ada exception keluar; hasil999 dari run
lama dibuang, downstream BLOCKED, report counts=None. Tes lain memuat module
lama tanpa API optional lalu memverifikasi source baru benar-benar menggantinya.

Regresi ekspor diuji kembali dari code cell yang ditulis ulang: failure tidak
membuat manifest sukses, retry valid, reopen immutable, korupsi ditolak.
Notebook/helper/packet identik dan source parse. Domain smoke/correctness lama
bukan bukti input lokasi aktual lengkap.

Notebook baru disubmit CPU SAVE_AND_RUN_ALL untuk pemeriksaan aktual. Status
run/kelengkapan sumber harus dinilai dari readiness terpisah; status worker
COMPLETE tidak otomatis berarti perhitungan market sudah siap.
