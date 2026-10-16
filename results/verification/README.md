# Validasi editor geometri

Jalankan dari root repository:

```bash
node results/verification/check_geometry_validation.js
python results/verification/check_review_editor.py
```

Pemeriksaan browser memerlukan Python Playwright dan Chromium pada `/usr/bin/chromium`. Ia merender HTML mandiri melalui `page.set_content`, menguji edit, pemetaan koordinat, download JSON, impor dan penolakan input invalid. Navigasi `file://` pada browser cloud diblokir kebijakan browser; pembukaan file lokal desktop belum diuji di mesin ini. Tidak ada inference atau replay counting.

`browser_validation.json` dan `geometry_validation.json` adalah hasil eksekusi aktual. Perubahan koordinat pengujian hanya berlangsung di memori browser/Node; bukan persetujuan geometri pengguna dan tidak tersimpan sebagai konfigurasi baru. Gambar screenshot pengujian sementara berada di `/tmp/`, di luar Git.
