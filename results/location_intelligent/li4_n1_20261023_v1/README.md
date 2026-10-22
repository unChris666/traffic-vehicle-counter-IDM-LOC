# LI-4 N1 — paket eksperimen offline

SKENARIO EKSPERIMEN — bukan validasi akses fisik/legal, ETA nyata, atau populasi. Unknown tetap unknown. Kapasitas dipisahkan menurut satuan. Peta skematis offline tanpa basemap; posisi mengikuti snapshot.

Buka **review.html** langsung di browser. Tidak memerlukan server/CDN/basemap.
Semua baris ada pada buildings.json/CSV/GeoJSON; routes dan connectors memakai EPSG:4326 [lon,lat].
Waktu kosong/null berarti tidak diketahui, bukan nol. Rute over-time juga diekspor.
snapshot/ adalah salinan lengkap LI-3, termasuk bukti dan manifest. Tidak ada inference/routing ulang.
Klik bangunan untuk status, alasan, rute, dan referensi bukti. Warna bukan bukti akses lapangan.

Verifikasi dari direktori paket dengan environment pyproj yang direkam:
```bash
PROJ_NETWORK=OFF python -B engine_source/location_intelligent_li4.py verify --root .
```
