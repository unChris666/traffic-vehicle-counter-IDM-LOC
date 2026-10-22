# Kontrol regresi34 accepted timeout

34 source contact sheets dengan267 frame awal unik diproses dan direview oleh
subreviewer AI; context/pair sheets tambahan dan challenge root memperkuat
temuan tertentu. Per_event_decisions.jsonl memberi status untuk semua 34 event.

14 event di kelompok timeout direkomendasikan cancel karena parked bbox,
objek campuran, false reverse atau duplikasi;20tetap unresolved sebagai
estimasi yang belum final secara QC. Object bergerak pada source bukan bukti
bahwa satu rawevent adalah satu-satunya representasi physical passage.

Cancel spesifik:
2536, 2584, 2583, 2680, 2697, 3512, 1107, 4367, 4541, 4569, 4567, 4627, 4934, 4946.
Lihat accepted_event_actions.jsonl di parentfolder untuk eventID/category/arah
dan evidence yang telah didedup. Dua cancel LINE_MARGIN tambahan(3555, 4281)
berasal dari review silang dan tidak dicampur menjadi 34timeout.

156dan927/988masih membutuhkan rekonsiliasi kendaraan/fragmen dan kategori;
root tidak memaksakan cancellation dari dugaan hubungan yang belum cukup
kuat. Honda4541/4567 mengandung salah reverse/objek campuran; physical passage
Honda mendekat tetap harus dicatat terpisah agar pembatalan reverse tidak
menutupi miss arah sebenarnya.4367merupakan ekor pickup4149yang sudah counted,
bukan genuine return. Gojek4934/4946/4953adalah satuunit, dengan canonical4953
tetap INFERRED_LINE_MARGIN, bukan measured.

Machine tetap172 accepted; tidak ada ledger yang diedit atau total QC final
yang diterbitkan. Keputusan AI ini dibatasi sourceframes yang dilihat.
