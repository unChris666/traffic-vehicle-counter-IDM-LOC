# Revisi Phase 8 B v3

Status: implementasi dan uji ulang sedang dikerjakan. Hasil actual, jumlah video/frame dan tautan anotasi hanya dicatat setelah run selesai.

Revisi terpisah dari baseline [B v2](../b_v2/README.md), memakai cache model lama tanpa inference detector/tracker/ReID baru.

- [Kontrak revisi dan keputusan terbuka](../../docs/PHASE_8_REVISION_CONTRACT.md)
- [Tugas/objektif Phase 9](../../docs/PHASE_9_TASK.md)
- Notebook: notebooks/08c_reviewed_identity_replay.ipynb
- [Koreksi sumber/episode](input/review_decisions.json)
- [Policy eksperimen eksplisit](config/policy.json)

Penyatuan alias dan koreksi role terikat pada sumber dan episode yang direview; ini replay review-assisted, bukan resolver identitas otomatis yang telah teruji umum.
