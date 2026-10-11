# Review deteksi aktual — TOR3-PAGI

Run Kaggle: `20261011T052950_360560Z_ed399fb8`, batch versi 1. Review AI-assisted dilakukan di Codex setelah mengunduh dan melihat lima pasangan PNG asli/anotasi pada resolusi native. Laporan Kaggle asli dipertahankan tanpa perubahan.

Tidak ada ground truth atau klaim akurasi.

## visible_detections

Anotasi frame 0 menempatkan label car pada mobil yang terlihat di jalan. Frame 2570 dan 5140 memiliki box motorcycle dan person pada wilayah kendaraan/pengendara yang terlihat. Ini pengamatan sampel, bukan penilaian semua kendaraan atau performa model.

Bukti: [samples/frame_000000000_raw.png](samples/frame_000000000_raw.png), [samples/frame_000000000_annotated.png](samples/frame_000000000_annotated.png), [samples/frame_000002570_raw.png](samples/frame_000002570_raw.png), [samples/frame_000002570_annotated.png](samples/frame_000002570_annotated.png), [samples/frame_000005140_raw.png](samples/frame_000005140_raw.png), [samples/frame_000005140_annotated.png](samples/frame_000005140_annotated.png)

## missed_or_ambiguous_objects

Pada frame 7711, skuter dan bagian pengendara masuk dari batas kanan, terpotong frame dan tertutup teks tertanam. Wilayah kanan menerima label handbag/person, sementara seluruh box motorcycle pada catatan frame itu berada di bagian kiri frame. Tidak ada box motorcycle yang melokalisasi skuter kanan dalam hasil baseline ini. Kasus audit ini bukan estimasi recall atau frekuensi kegagalan.

Bukti: [samples/frame_000007711_raw.png](samples/frame_000007711_raw.png), [samples/frame_000007711_annotated.png](samples/frame_000007711_annotated.png), [representative_frame_detections.json](representative_frame_detections.json)

## class_ambiguities

Frame 2570/5140 memiliki person dan motorcycle pada pengendara yang sama; raw person belum berarti kategori pejalan kaki. Frame 0/10281 memiliki label bench pada struktur kayu pinggir jalan; frame 7711 memiliki handbag pada wilayah skuter/teks. Seluruh label asli tetap dipertahankan tanpa pemetaan kategori produk. Tidak ada angkot pada daftar kelas bobot; dukungan bus/angkot belum diputuskan.

Bukti: [samples/frame_000000000_raw.png](samples/frame_000000000_raw.png), [samples/frame_000000000_annotated.png](samples/frame_000000000_annotated.png), [samples/frame_000002570_raw.png](samples/frame_000002570_raw.png), [samples/frame_000002570_annotated.png](samples/frame_000002570_annotated.png), [samples/frame_000005140_raw.png](samples/frame_000005140_raw.png), [samples/frame_000005140_annotated.png](samples/frame_000005140_annotated.png), [samples/frame_000007711_raw.png](samples/frame_000007711_raw.png), [samples/frame_000007711_annotated.png](samples/frame_000007711_annotated.png), [samples/frame_000010281_raw.png](samples/frame_000010281_raw.png), [samples/frame_000010281_annotated.png](samples/frame_000010281_annotated.png), [detection_report.json](detection_report.json)

## overlay_and_occlusion_cases

Teks putih tertanam kanan bawah menghalangi piksel skuter yang baru masuk pada frame 7711. Kendaraan juga terpotong batas kanan. Label dan box anotasi kadang bertumpuk pada objek jauh; gunakan PNG asli dan catatan box, bukan hanya contact sheet. Efek masing-masing faktor pada model belum dipisahkan melalui eksperimen.

Bukti: [samples/frame_000007711_raw.png](samples/frame_000007711_raw.png), [samples/frame_000007711_annotated.png](samples/frame_000007711_annotated.png), [samples/frame_000005140_raw.png](samples/frame_000005140_raw.png), [samples/frame_000005140_annotated.png](samples/frame_000005140_annotated.png)

## questions_for_later_experiments

Bagaimana memisahkan pejalan kaki dari pengendara sebelum pemetaan kategori produk? Bagaimana skuter terpotong/tertutup teks pada frame 7711 berperilaku pada frame berurutan dan setting detektor yang diuji terkontrol? Bagaimana kelas berubah pada kendaraan jauh, dan apa konsekuensinya ketika tracking nanti diotorisasi? Pemetaan bus/angkot, threshold yang cocok, hasil malam, serta tracking/ReID tetap terbuka.

Bukti: [samples/frame_000002570_raw.png](samples/frame_000002570_raw.png), [samples/frame_000002570_annotated.png](samples/frame_000002570_annotated.png), [samples/frame_000005140_raw.png](samples/frame_000005140_raw.png), [samples/frame_000005140_annotated.png](samples/frame_000005140_annotated.png), [samples/frame_000007711_raw.png](samples/frame_000007711_raw.png), [samples/frame_000007711_annotated.png](samples/frame_000007711_annotated.png), [representative_frame_detections.json](representative_frame_detections.json)
