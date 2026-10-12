# Analisis BC tersimpan — G3

**EXPERIMENT RESULT:** [anchor_variation_analysis.json](anchor_variation_analysis.json) dihitung dari cache ReID-on Phase 4, tanpa inference ulang. Metode [analyze_g3_anchor_variation.py](../verification/analyze_g3_anchor_variation.py) memeriksa raw-bbox/source links, BC, signed distance, pasangan frame kontinu, gap dan measured return excursions. Analisis ini terpisah dari state-machine replay; jumlah pasangan geometris bukan jumlah kendaraan.

```bash
python docs/evidence/phase_5/verification/analyze_g3_anchor_variation.py --root "$PWD" --output /tmp/g3_anchor_variation.json
```

Tiga excursion kembali masing-masing satu frame memiliki amplitudo **4.152545216412263**, **4.567185192815604**, **39.945593728512996** native pixel. Pixel tepat sekitar ketiga kasus tidak tersedia dalam bukti lokal: belum terbukti jitter, gerak balik fisik, atau pergantian komponen. Band eksperimen 0/median/maksimum dan konfirmasi 1/2 adalah kontrol/sensitivitas eksploratif. Band maksimum menguji sensitivitas ekstrem; tidak dipilih sebagai estimasi noise/default terbaik.

[retained_visual_review.json](retained_visual_review.json) memisahkan observasi pixel yang benar-benar dibuka dari aritmetika BC raw. Contact sheet interval 30 frame hanya memiliki enam sampel. Empat pasangan sign-change memiliki kedua frame exact dalam bukti pixel tersimpan; semua trajectory cache dapat dianalisis tetapi seluruh video belum direview secara visual. Box gambar tracking dapat terfilter: letak BC kuantitatif ditelusuri ke `raw_bbox`, bukan ditebak dari tepi kotak gambar.

Temuan skuter merah: ID964/973 dan komponen rider967 memiliki geometri lintasan yang saling berkaitan. ID software bukan kendaraan unik; penjumlahan transisi berisiko menduplikasi kendaraan. Tidak ada ground truth, kategori final, traffic count, atau klaim accuracy.
