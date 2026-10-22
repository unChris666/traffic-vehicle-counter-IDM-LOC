# B v4 — hasil perbaikan berbasis pilot Phase 9

Implementasi dan replay aktual selesai pada **satu video TGDI-WEEKDAY-SIANG,
9.128 frame sumber**. Ini kandidat penelitian; belum default produksi atau
validasi delapan video/malam. Detector, tracker, ReID, dan enhancement tidak
dijalankan ulang. Machine mempertahankan review lama; review-assisted menambah
adjudikasi AI54 yang dibatasi frame 33–140, bukan ground truth independen.

- [Review 360°, hasil, keputusan dan SWOT](REVIEW_360.md).
- [Kontrak perubahan dan asumsi eksperimen](../../docs/B_V4_EPISODE_ELIGIBILITY_CONTRACT.md).
- [Notebook reproduksi](../../notebooks/08d_episode_eligibility_role_replay.ipynb).
- [Perbandingan hasil aktual](verification/comparison_summary.json).
- [Tiga kelompok pending untuk keputusan](review/pending_case_groups.csv).
- [101 tes baru dan 236 tes baseline](verification/software_validation.json).
- [94 berkas hasil/source snapshot yang dipertahankan](execution/retained_bytes_manifest.json).
- [Verifikasi retensi](verification/retained_bytes_validation.json) dan
  [82 berkas audit Phase 9 tetap utuh](verification/phase9_evidence_preservation.json).
- [Preview aktual](previews/manifest.json) dan
  [laporan video anotasi penuh](videos/annotation_report.json).

Video lokal berada di `results/b_v4/videos/TGDI-WEEKDAY-SIANG-b-v4-machine.mp4`.
Seluruh 9.128 frame telah dirender dan didekode ulang. Ukuran 144.935.634 byte
melebihi batas satu blob GitHub 100 MB, sehingga MP4 dikecualikan dari Git.
**Video B v4 baru belum dipublikasikan ke GitHub**; publikasi berikutnya harus
memakai Release asset dengan pointer di folder results, bukan commit MP4 besar.
Sidecar label dan laporan tetap dapat disimpan dalam Git.

Retensi berkas besar menggunakan gzip. Manifest mencantumkan SHA berkas asli,
SHA arsip, ukuran, dan jenis kompresi. Contoh membaca hasil:

```python
import gzip, json
from pathlib import Path
path = Path('results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz')
result = json.loads(gzip.decompress(path.read_bytes()))
```

Branch berbeda **tidak boleh dijumlahkan**. Log menggunakan frame sumber
zero-based. ID tampilan M/P/C/T dapat berubah antarversi; review memakai
videoSHA + rawID + frame + episode, bukan ID tampilan saja.
