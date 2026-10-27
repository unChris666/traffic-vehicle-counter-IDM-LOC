# Hasil BQ, peta GCS dan PPAC — 0.5.3rc1

Arahan owner: Kaggle dahulu; Docker tidak diubah.

Owner melaporkan Gradio hanya menampilkan “error”, tanpa traceback, dan sesi
sudah dihentikan. Penyebab spesifik sesi itu belum dapat dipastikan. Perbaikan
ini menangani serialisasi timestamp/Decimal/NaN pada tabel, memisahkan kegagalan
baca per tabel dan mengurangi payload event peta. Query tetap memakai target/job,
lokasi dataset aktual, parameter SQL dan batas billing256MiB. Error BQ menampilkan
kelas kegagalan dan tabel terkait; kegagalan satu tabel tidak menghilangkan hasil
lain. Tidak mengganti input gagal/hilang menjadi angka nol.

## Peta

Renderer menghasilkan HTML Folium interaktif. Publikasi job menyimpan file HTML
ke `gs://aretfak-location-intelligence/jobs/<target>/<periode>/<job>/engines/area/.../market_map.html`
dengan Content-Type text/html. Rekap BQ menyimpan URI/SHA; manifest job juga
mengikat artefaknya. Gradio mengunduh HTML yang sama dari GCS dan memverifikasi
prefix job, generation, ukuran dan SHA256. Browser membuka `/saved-maps/<sha>`
dalam iframe sandbox; file tidak lagi di-inline puluhan megabyte ke JSON event.
Endpoint hanya menyajikan file cache dengan hash cocok, bukan path filesystem
sembarang. File GCS tetap private dan bisa diunduh melalui Console. CDN/basemap
Esri memerlukan koneksi browser. Tidak perlu membuat bucket public atau signed
URL permanen. Jika kolom peta BQ belum tersedia, loader dapat memakai referensi
HTML dari manifest job yang terverifikasi; error schema tetap diberitahukan.

## PPAC

Tabel PPAC memakai **`ppac/result.json` dari job GCS**, diverifikasi dengan manifest
job yang hash-nya tercatat di BQ. Tidak membentuk ulang breakdown dari std_total
BQ dan tidak menghitung formula ulang di UI. Ditampilkan sebagai baris:

- Breakdown Residential: alokasi bangunan/KK, penghuni, zona dan komponen STD.
- Breakdown Traffic: kategori/kelompok hari, komponen dan STD Traffic mentah.
- Breakdown Fasum: rincian yang tersedia dalam hasil.
- Total: rincian agregasi asli, termasuk penyesuaian/drive-thru bila tersedia.
- STD Total (STD/hari), Status eksekusi/kualitas, dan Reason/diagnosis.

Nilai Fasum sudah dapat masuk dalam komponen total Traffic tersimpan: UI tidak
menjumlahkannya lagi. Status BLOCKED/null tetap terlihat, bukan STD0. Jika
ppac.json belum tersedia atau gagal verifikasi, tabel menyatakan UNAVAILABLE.

Komponen JSON PPAC dan tombol unduh ringkasan JSON di Gradio dihapus. Hasil asli
tersimpan di GCS; retry publikasi tidak menulis ekspor UI lokal baru. Rincian BQ
Traffic/Area berada dalam accordion; JSON parameter PPAC mentah tidak ditampilkan.
Tidak ada perubahan formula PPAC atau perhitungan engine.

## Pengujian

269 tes lokal:259lulus,10dilewati; mypy14file lulus. Uji serialisasi strict JSON
mencakup timestamp, Decimal dan angka hilang. Uji sumber PPAC membedakan angka
BQ999 dan ppac.json105, memastikan UI memakai105. Uji peta HTTP menyajikan HTML
hasil tersimpan35.595.179byte dengan status200, sandbox dan tanpa attachment;
konfigurasi Gradio tidak memiliki komponen JSON atau unduh ringkasan JSON.
Validasi ini tidak menjalankan inference GPU baru dan bukan bukti error sesi
owner sebelumnya telah direproduksi ataupun akses GCS/BQ live telah lulus.
