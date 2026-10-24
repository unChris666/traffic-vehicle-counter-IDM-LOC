# Workflow pengembangan aktif — evaluasi mandiri hingga review UI


**Checkpoint Area Coverage — 24 Oktober 2026:** owner meminta audit kesiapan
modularisasi terlebih dahulu. [Audit Area Coverage](AREA_COVERAGE_MODULARIZATION_READINESS_AUDIT.md)
berstatus **menunggu persetujuan**. Pada scope Area Coverage, instruksi terbaru
ini membatasi pekerjaan pada audit/dokumentasi; implementasi migrasi dimulai
setelah audit disetujui. Traffic RC dan hasil historis tetap dipertahankan.

**Checkpoint implementasi, 24 Oktober 2026:** owner telah mengotorisasi urutan
freeze → kontrak/facade → adapter → domain → runtime/batch → renderer/export/storage
→ release candidate, dengan penyelesaian keputusan teknis secara mandiri.
Audit sebelumnya disetujui untuk dilaksanakan oleh instruksi terbaru ini.
Implementasi berada di branch `refactor/traffic-modularization-v2`; lihat
[catatan migrasi dan gate](TRAFFIC_MODULARIZATION_RELEASE.md).
Algoritma/kernel serta evidence historis tetap immutable. Perubahan angka bukan
bagian refactor ini. Hasil aktual8/8 T7SL kini tersedia; asumsi keberhasilan pada
checkpoint audit terdahulu tidak dipakai sebagai bukti. GCS nyata dan kesiapan
produksi tetap memiliki gate tersendiri.

**Arahan owner, 23 Oktober 2026 (Asia/Jakarta).** Dokumen ini menjadi otoritas
workflow terkini. Bagian roadmap/status lama dipertahankan sebagai riwayat;
larangan melanjutkan hanya karena menunggu approval Markdown tidak lagi menjadi
gate rutin. Batas Markdown-only pada permintaan sebelumnya sudah digantikan oleh
otorisasi implementasi adapter/modularisasi Traffic dan Location serta uji fresh
inference terbatas. Scope dan bukti aktual ada di
[ENGINE_MODULARIZATION_REVIEW](ENGINE_MODULARIZATION_REVIEW.md). Bucket, akun cloud,
UI dan deployment belum diimplementasikan dalam irisan kerja ini.

## 1. Pembagian kerja dan batas otonomi

Owner hanya dapat mereview ketika ada UI untuk input dan melihat output.
Engineer melanjutkan fase berikutnya dengan analisis, keputusan teknis yang
reversible, implementasi bertahap, tes, audit bukti dan laporan mandiri. Jangan
mengulang pertanyaan approval C01–C09 atau meminta polygon manual untuk sekadar
melanjutkan pekerjaan teknis. Gunakan fixture/polygon demo berlabel bila perlu.

C01–C09 pada [kontrak](ENGINE_IO_CONTRACT_DRAFT.md) menjadi **baseline kerja
provisional di bawah delegasi**, bukan klaim owner menyetujui setiap detail atau
hasil eksperimen menjadi standar produksi. Keputusan teknis dicatat beserta
alasan dan dampaknya, kemudian dapat ditinjau pada UI. Schema/API final harus
mengikuti bukti adapter/tes; draft bukan validator yang sudah berjalan.

Jangan mengarang data, bukti akses, labels, formula PPAC, satuan kapasitas atau
akurasi untuk menutup gap. Unknown dipertahankan. Bagian yang bergantung input
bisnis/bukti/credential wajib dapat BLOCKED, sementara bagian independen tetap
berjalan. Persiapan review, tes dan hasil konkret diselesaikan terlebih dahulu.
Jika membutuhkan tindakan pengguna di luar kemampuan engineer, jelaskan alasan
dan panduan spesifik; jangan memaksa review dokumen yang bisa ditunda ke UI.

Delegasi tidak berarti menjalankan pengeluaran cloud atau membuka akses publik
secara diam-diam. Provisioning hanya dilakukan dalam scope yang sudah berizin,
dengan identitas/runtime yang tersedia dan biaya/region yang jelas. Jangan
meminta nilai token/service-account key di chat.

## 2. Requirement stabilitas kedua engine

**REQUIREMENT owner:** angka hasil Area Coverage dan Traffic Counter stabil
ketika pekerjaan yang sama diulang. Requirement tidak dianggap terpenuhi hanya
karena UI menampilkan angka cached yang sama.

Identitas pekerjaan meliputi sumber bytes/snapshot dan coverage, target,
konfigurasi/policy, model/weights, decoder/frame scope, code/schema/environment,
actual execution backend/device profile, dan review/polygon revision jika ada.
Koordinat atau filename saja tidak menjadi fingerprint.

- **Reopen normal:** gunakan manifest finalized yang terikat fingerprint yang
  sama, verifikasi integritas, lalu buka hasil. UI rerender/relogin/retry tidak
  memicu retrieval/inference/routing ulang atau menambah hitungan.
- **Replay:** sumber/config/code/environment terkunci; perhitungan domain harus
  sama. Verifikasi hasil asli, bukan menyamakan nilai setelah terjadi mismatch.
- **Fresh inference reproducibility:** diuji terpisah pada backend/device yang
  direkam. Jangan mengklaim inference stabil hanya dari detector-cache replay.
- **Refresh:** eksplisit, input/source/config yang berubah menghasilkan versi
  baru dan delta; tidak menimpa baseline atau silently mengubah hasil tersimpan.

Definisi gate dan bukti: [REPRODUCIBILITY_POLICY](REPRODUCIBILITY_POLICY.md).
Status saat ini: LI-3/LI-4/LI-5 mempunyai bukti replay scoped; Traffic fresh
inference/CPU/GPU/night/generalization tidak otomatis ikut PASS.

## 3. Batas modul yang dipertahankan

Satu repo, dua domain engine: Traffic dan Location. Modul bisnis/PPAC adalah
konsumen terpisah. Backend mengatur auth/job/state/storage; UI mengirim input,
menampilkan hasil/diagnostics dan review; keduanya tidak menduplikasi counting
atau routing. Config dan storage melalui interface terpisah dari algoritme.

Traffic menjaga unit/passage/BC/source-frame/role/identity safeguards dan
measured-estimated split. Location menjaga coverage/source/accessibility/
capacity units dan Recount provenance. Machine/reviewed adalah alternatif
snapshot. Refactor tidak boleh sekaligus mengubah algoritme tanpa eksperimen
versi terpisah. GPU/CPU provider dicatat; no silent model/frame/ReID fallback.

## 4. Urutan kerja aktif menuju UI

| Milestone | Pekerjaan mandiri | Gate/hasil konkret |
|---|---|---|
| M1 — contracts dan adapter | Machine-readable schemas, validators, adapters ke retained Traffic/Location outputs; working contract versions | Negative fixtures, null/status/branch/unit/provenance checks dan golden parity; keputusan provisional tercatat |
| M2 — modularisasi | Pisahkan domain Traffic/Location, config, orchestration dan storage adapters; CLI/API boundary | Hasil domain sama pada input terkunci; engine tidak tergantung UI; reproducibility tests PASS dalam scope |
| M3 — backend/job | Input validation, idempotency, queue/state/progress/retry/cancellation, result lookup | Tidak ada duplicate counting akibat retry; failures tidak sukses; finalized results persisten |
| M4 — GCS integration | Pandu owner setup project/bucket/identity ketika dependency storage nyata tiba; implement CRUD adapter dan tes sandbox | CRUD test object+generation/checksum/access tests, no public bucket, hasil lama immutable; metadata DB dievaluasi terpisah |
| M5 — UI review | Target/input video, config geometri/filter, job progress, map/video/table, measured/estimated/partial diagnostics, revisions/export | Owner bisa input dan melihat output nyata; replay/demo diberi label; fitur belum wired tidak disamarkan sebagai live processing |
| M6 — staging/deployment | Container/runtime CPU/GPU yang sesuai, health/jobs/restart/storage/auth tests | Scope tervalidasi dan keterbatasan terlihat; bukan production release hanya karena UI bisa dibuka |

Implement UI minimum boleh dimulai bertahap setelah adapter yang diperlukan
tersedia; tidak menunggu owner mereview Markdown/manual polygon. Stage awal
boleh membaca hasil retained dengan label jelas sambil proses baru diintegrasikan.
Jangan menampilkan tombol seolah memproses data jika backend hanya replay.
Validasi kualitas Traffic malam/identitas dan Location unknown/source berjalan
paralel secara agenda, bukan izin implisit untuk multi-agent atau multi-GPU.

Nomor fase Traffic0–13 dan LI0–7 tetap untuk melacak pekerjaan. M1–M6 adalah
milestone integrasi, bukan mengganti angka fase atau menyatakan semua gate
produksi sebelumnya selesai. LI-6 features/PPAC dapat dipersiapkan interface-nya;
angka bisnis tetap BLOCKED bila formula/unit/period wajib belum tersedia.

## 5. Penyimpanan dan review berikutnya

**KEPUTUSAN owner:** Google Cloud Storage untuk video dan artefak hasil.
GCS adalah object storage, bukan keputusan memilih database relasional.
Database metadata/job/user, framework UI/API, compute/GPU provider, region,
billing/bucket names, IAM identities, retention dan deployment belum dipilih
secara final. Engineer mengevaluasi pilihan teknis dalam milestone terkait.

[GCS_STORAGE_ONBOARDING_PLAN](GCS_STORAGE_ONBOARDING_PLAN.md) menyiapkan panduan
saat M4; sekarang belum membuat bucket atau menjalankan CRUD. Local adapter
untuk pengembangan tidak boleh dilabel sebagai integrasi GCS terverifikasi.

Review owner berikutnya berbasis UI: input aktual, hasil per engine, scope,
unknown/estimated/partial, perubahan konfigurasi dan versi, bukti passage/
bangunan, export dan pembukaan hasil ulang. Siapkan contoh before/after dan
failure cases yang benar-benar terjadi. Engineer melaporkan pekerjaan selesai,
bukti tes, batas klaim dan tindakan owner yang benar-benar diperlukan.
