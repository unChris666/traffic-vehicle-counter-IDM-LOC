# Perbaikan akses502 — 0.7.2rc2

Notebook: `notebooks/active/17_colab_l4_phase123_user_testing.ipynb`.

## Bukti ZIP owner

ZIP colab-diagnostics(3) berisi NO_ENGINE_RUN: belum ada job engine. Pada28Oktober2026,17:00:14WIB watchdog masih memperoleh HTTP lokal200, nol kegagalan probe. Server kemudian mencatat Keyboard interruption, penutupan tunnel, dan STOPPED sekitar17:00:17WIB. Tidak ada exception aplikasi/dependency/BQ/PBF/inference yang menjelaskan502. Kode502 gateway yang dilaporkan owner belum terekam langsung sebelum Stop; ini bukan bukti lokasi pasti kegagalan gateway. HTTP lokal200 juga tidak membuktikan akses browser/tunnel publik sehat.

Ini menunjukkan bahwa persoalan akses dapat terjadi sebelum engine dimulai; mengubah rumus atau mengunduh ulang PBF bukan tindakan berdasarkan bukti ini. Perubahan0.7.2rc1 telah memisahkan submit/polling dari masa hidup engine;0.7.2rc2 memisahkan aplikasi dari share gateway gradio.live sebagai jalur utama.

## Akses utama: proxy Colab

- Pada cell server: `UI_ACCESS='colab'` (default).
- Notebook meminta URL melalui API browser resmi `google.colab.kernel.proxyPort(7860)`, bukan membangun hostname sendiri.
- URL resmi `.colab.googleusercontent.com` dan `.colab.dev` didukung, HTTPS tanpa credential/query/fragment. Endpoint/prefix hasil proxy digunakan sebagai root_path Gradio agar konfigurasi API/assets mengarah ke proxy yang sama.
- Server memakai port7860 dan `share=False`. Tidak membuat tunnel gradio.live.
- Setelah HTTP lokal READY, notebook mencetak UI_URL dan link **Buka aplikasi — colab**. Tunggu link ini, jangan buka URL gradio.live sesi lama.
- Buka pada browser yang sama, tetap login akun Colab dan pertahankan runtime/cell server aktif. Proxy ini dapat memerlukan autentikasi browser; pemeriksaan anonim dari Python tidak diperlakukan sebagai verifikasi akses proxy.
- Jika browser perlu membuka tab terpisah, gunakan link yang dicetak. Ini tidak membuat job baru.

Gradio tetap digunakan. HOME, formula RWI/okupansi, tooltip, submit singkat/background/polling, dan penyimpanan hasil tidak diubah.

## Opsi gradio.live

Jika proxy Colab tidak dapat dipakai, ubah hanya `UI_ACCESS='gradio'` pada cell server, setelah memastikan server/job lama berhenti. Jangan mengganti transport ketika job aktif. Opsi ini membuat URL gradio.live baru.

Monitor opsi gradio kini memeriksa `/config` publik secara terpisah dari localhost, timeout5detik tanpa redirect, dan menyimpan status/kode pada `server-status.json.public_http`. HTTP502 dipertahankan sebagai HTTP_ERROR/code502, tidak diubah menjadi error engine. Mode proxy Colab diberi label BROWSER_AUTH_REQUIRED_NOT_PROBED agar kegagalan probe anonim tidak disalahartikan sebagai kegagalan aplikasi. HTTP200 pada salah satu jalur tetap bukan bukti engine atau browser sehat.

## Retest

1. Buka notebook versi0.7.2rc2, jalankan setup/runtime-check/autentikasi pada L4.
2. Jalankan cell server dengan UI_ACCESS=colab. Tunggu HTTP lokal READY dan link Buka aplikasi — colab.
3. Pastikan HOME dapat dibuka/SAVE peta, lalu pratinjau dan Running. Pantau Job ID melalui polling/manual reconnect.
4. Jika gagal membuka HOME, catat URL jenis Colab atau gradio, HTTPcode dan apakah runtime/cell masih hidup; unduh ZIP diagnosis. Jangan langsung menganggap engine gagal ketika belum ada Job ID.
5. Stop/Interrupt menutup server/proxy dan dapat menghentikan job; menghapus runtime bukan pemulihan atau resume job. Gunakan hasil GCS/BQ yang benar-benar telah dipublikasikan sebagai sumber hasil persisten.

## Validasi dan batas

Tes pemilihan mode, domain proxy, penolakan URL tidak sah dan pemeliharaan kode502 lulus. HTTP Gradio loopback dengan root_path proxy simulasi mengembalikan rootURL yang tepat, submit/polling singkat tetap berfungsi dan klik ulang hanya memanggil satu engine fixture. Ini menguji konfigurasi root/polling, **bukan login browser/proxy Colab atau tunnel publik nyata**. Retest owner masih diperlukan; tidak ada jaminan seluruh gangguan gateway hilang.
