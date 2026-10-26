# Modul PPAC: STD per hari

`ppac.py` berisi perhitungan; `konstatna.py` berisi konstanta. Nama `konstatna`
mengikuti permintaan. Python 3.10+; runtime tanpa dependency eksternal.
Simpan kedua berkas dalam satu folder lalu `import ppac`.

## Kebijakan Residential terbaru

Input Area Coverage berupa bangunan; kalikan4 untuk memperoleh penghuni.
Jika Area Coverage sudah mengalikan4, gunakan unit='penghuni' agar tidak dua kali.
Tidak mengklaim bangunan sama dengan KK terverifikasi.

Total penghuni dialokasikan30% ke0–400m,50% ke>400–800m,20% ke>800m.
Ini estimasi kebijakan pemilik, bukan pengukuran geografis bangunan.
Porsi tidak dibulatkan di antara perhitungan agar jumlah tetap terjaga.
Pengali radius mengikuti Excel:1,0.5,0.25.

Rumus tiap kelompok:
STD = ROUND(penghuni_kelompok /30 ×pengali_radius ×koefisien_gabungan
            ×(hari_operasional_bulanan /30) ×faktor_SWOT, 0).
Hari bulanan mengikuti H96: hari mingguan×4; tambah2 jika >6hari.
STD Residential adalah jumlah STD tiga kelompok setelah pembulatan.
Koefisien gabungan mencakup frekuensi bulanan dan koreksi historis.

```python
import ppac

# Contoh sintetis; koef1.5 bukan default/koef lokasi nyata.
r = ppac.calculate_residential(
    1000, unit='bangunan', combined_coefficient=1.5,
    operating_days_per_week=7, swot_factor=1,
)
assert r['total_penghuni'] == 4000
assert (r['penghuni_400m'], r['penghuni_400_800m'], r['penghuni_gt800m']) == (1200, 2000, 800)
assert (r['std_400m'], r['std_400_800m'], r['std_gt800m']) == (60, 50, 10)
assert r['std_residential'] == 120
```

`combined_coefficient` adalah J96: AC17 dikurangi AK30, harus diselesaikan
pemanggil dari lookup NAS/cabang/domain. `swot_factor` adalah E92 (1 jika
penyesuaian tidak berlaku). Tidak memakai koefisien contoh menjadi default.
Kebijakan baru20%>800m dipakai default. `far_eligible=False` dapat mengecualikan
porsi luar jika pemanggil memutuskan demikian. Checklist satelit F98 Excel
belum diport otomatis; pemanggil bertanggung jawab bila ingin mempertahankan
gate tersebut. Ini perbedaan eksplisit dari input KK aktual/checklist Excel lama.

## Traffic, Fasum, dan hasil akhir

```python
samples = {
    'weekday': {'pagi': {'motor': 100, 'mobil': 0}},
    'weekend': {'pagi': {'motor': 80, 'mobil': None}},
}
t = ppac.calculate_traffic(samples, road_type='street', operating_hours=15,
                           balance_multiplier=.6)
# .6 di atas contoh input hasil lookup AE18, bukan koef universal.
result = ppac.calculate_ppac(
    residential=r, traffic=t, fasum_std=0,
    traffic_cut_factor=1, parking_factor=1,
)
assert result['status'] == 'sementara'
```

Kategori: motor,mobil,angkutan_umum,sepeda,pejalan_kaki.
Sesi normal: pagi,siang,sore,malam. Di atas15jam tambahkan sesi shift3:
tengah_malam,dini_hari,subuh. Setiap count adalah pencacahan5menit.
Nol = sudah dicacah tanpa arus; None/slot hilang = belum dicacah.
Kategori/sesi tidak dikenal, angka negatif, NaN, infinity, bool atau count
pecahan ditolak. Jangan mengubah hasil pending/gagal engine menjadi nol.

Koefisien Traffic memakai rasio MIN/MAX rata-rata weekday/weekend dikali
balance_multiplier AE18, lalu koef dasar jalan. Bila rasio nol gunakan
setengah koef dasar sebagai aturan penjaga estimasi yang dikonfirmasi pemilik.
Persentase jalan dan koef dasar kategori berasal dari PRINT PPAC N254:O276
serta G254:G276. STD kategori = ROUND(rerata_count×12×jam×persentase×koef).
Jam normal dibatasi15; sisa jam menggunakan rerata shift3. Bulatkan per
kategori/per shift, jumlahkan per hari, lalu ROUND((weekday×4+weekend×3)/7).

Hasil sebagian berstatus `sementara`. Tanpa semua pengamatan berstatus
`unavailable` dan STD None, sehingga bukan hasil nol yang terlihat sah.
`lengkap` hanya menyatakan slot tersedia, bukan validasi akurasi survei.
Jika seluruh satu kelompok hari kosong, kontribusinya nol pada bobot TETAP4/3
seperti Excel, tetapi hasil hari tetap None dan missing_observations disediakan.
Ini kompatibilitas teknis, bukan konfirmasi kebijakan penaksiran hari kosong.

`calculate_fasum` mengikuti L82:L88; terima penghuni/karyawan/siswa,
pengunjung harian, hari operasional bulanan, koefisien dan pengali jarak.
Jumlahkan hasil tiap fasum untuk fasum_std. Fasum tetap tambahan meskipun
arusnya telah masuk Traffic Counter, sesuai konfirmasi pemilik.

Agregasi mengikuti E103:E106:
Traffic_terkoreksi = ROUND(Traffic_raw×potongan×parkir−STD_drive_thru)+Fasum.
STD_total = ROUND(Traffic_terkoreksi+STD_Residential+STD_drive_thru).
Drive thru (opsional) = ROUND(Traffic_raw×40%×potongan), seperti W78.
Parameter traffic_cut_factor=E15, parking_factor=AF56, fasum_std=L89.
Koefisien netral1 hanya dipakai bila pemanggil menyatakannya secara eksplisit.

## Batas cakupan

Modul mandiri ini belum dipasang ke engine Area/Traffic atau UI.
Pemilihan domain, lookup NAS/cabang, interpolasi AK30, SWOT eksternal,
potongan dari Kpsc, faktor parkir, dan gate satelit belum diport menjadi
lookup otomatis. Hasil lookup harus disediakan pemanggil; tidak ditebak.
Tidak menghitung APC/SPD, margin atau proyeksi sales. Ini bukan port penuh
semua sheet workbook. Konstanta lokasi yang berubah tidak disalin sebagai
nilai default universal.

## Validasi yang dijalankan

`python -m unittest -v test_ppac`:8kasus lulus, meliputi alokasi30/50/20,
input bangunan/penghuni, tiga pengali jarak, pembulatan Excel, data kosong/nol,
penjaga estimasi, Fasum/agregasi dan input invalid.

`validate_workbook.py` memerlukan openpyxl dan workbook sumber lokal.
Perbandingan komponen terhadap nilai cache Excel cocok: weekday375,
weekend302,Traffic344,KK_fixture_asli33,Fasum19,total393.
Ini bukan menjalankan Excel atau menghitung ulang seluruh workbook.
Fixture memakai300KK seluruhnya pada400m; kesamaan393 bukan bukti bahwa
alokasi baru30/50/20 akan menghasilkan nilai sama dengan input Excel lama.
Contoh sintetis1000bangunan/koef1.5/7hari/SWOT1 menghasilkan STD Residential120.
