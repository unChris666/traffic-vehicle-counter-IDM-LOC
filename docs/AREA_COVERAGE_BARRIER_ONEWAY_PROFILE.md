<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Profil eksperimen barrier/one-way — 25 Oktober 2026

## Keputusan owner terbaru

`BARRIER_ONEWAY_EXPERIMENT_V1` menjadi pilihan notebook market. Referensi strict
lama tetap tersedia, bukan ditimpa atau diberi label ulang. Profil baru adalah
skenario akses asumsi, bukan bukti izin motor/legalitas/akses fisik lapangan.

- Jalan yang berhasil diekstrak tidak disaring berdasarkan tag access, vehicle,
  motor_vehicle, motorcycle. Izin kosong, nilai tidak didukung dan conditional
  dianggap boleh dalam skenario. Karena owner menetapkan hanya barrier/one-way,
  tag larangan akses eksplisit/private juga tidak menjadi larangan pada profil
  ini. Ini secara eksplisit menggantikan kebijakan izin lama, bukan temuan data.
- One-way statis (termasuk -1 dan exception motor yang dapat dibaca) tetap
  diterapkan. Aturan roundabout/default OSM tetap berlaku. Conditional diabaikan;
  static oneway yang tidak dapat ditafsirkan tetap UNKNOWN, tidak dipakai untuk
  acceptance. Tidak membuat reverse edge pada ruas one-way yang diketahui.
- Barrier node dengan locked=yes/gate:status=closed dan barrier solid yang
  dikenali (wall, fence, block, jersey_barrier, guard_rail, retaining_wall)
  menutup akses. Barrier gate/bollard atau bentuk lain yang kondisinya tidak
  jelas diasumsikan bisa lewat. Ini bukan pengamatan portal terbuka.
- Untuk pemeriksaan konektor, barrier way yang tidak jelas juga tidak memblokir;
  bentuk fisik yang dikenali dan air yang geometrinya tersedia tetap memblokir
  konektor. Geometri barrier yang belum terselesaikan tidak menjadi veto global.
- Larangan belok (termasuk conditional/relasi belum didukung) diabaikan oleh
  profil eksplisit ini, baik bagian 6 maupun paket tambahan bagian 8.
- UNKNOWN yang masih tersisa tidak disertakan ke graph rute accepted.
  Potential reachability hanya menjelaskan hasil belum pasti, tidak mengesahkan
  hitungan. Ruas/node/geometri hilang tidak dibuat-buat.

Unknown izin yang kini diberi asumsi True berbeda dari sisa edge UNKNOWN yang
belum terpecahkan. Reason/policy menyatakan OWNER_ROAD_ACCESS_ASSUMPTION; bukan
mengklaim memperoleh bukti izin baru.

## Tetap berlaku

Satu entrance asumsi per bangunan, prioritas kelas dan jarak, pencarian 125 m,
biaya konektor, 7 km/jam, round(menit)<=10, jalan berarah, tidak ada penggabungan
jalan hanya karena tampak berpotongan, pemeriksaan konektor menembus bangunan
lain, dan keterbatasan entrance ke jalan layang/terowongan tetap berlaku.
Karena itu tidak menjanjikan ACCESS_UNVERIFIED menjadi nol. Rules geometris
tersebut bukan filter izin motor.

Tidak menambah kategori jalan yang tidak terambil pada snapshot. Mode default
ROADS_ONLY_EXPERIMENT tidak mengunduh inventori barrier lengkap; hanya barrier
pada sumber yang tersedia dapat diuji. Penskalaan atau asumsi tidak mengisi
kekosongan jaringan.

## Konfigurasi dan pengulangan

Satu pilihan pada location_intelligent_market_config.py:
`MARKET_CONFIG['access']['road_rule_profile']`.

CONFIG/frozen pilot/hasil routing dan market mengikat profil tersebut. Guard
motor membedakan profil baru dan strict; override larangan hanya diizinkan
ketika profil/flags/hash policy secara eksplisit sesuai. Metadata hasil mencatat
access-tag dan turn-restriction validation NOT_APPLIED_BY_OWNER_POLICY.

Parameter ini hanya kalkulasi: source key dan perbandingan manifest sumber
mengeluarkannya pada kedua sisi agar cache snapshot lama tetap dapat dibuka.
Job/config hasil baru berbeda. Baseline strict immutable; hasil lama tidak
bisa dianggap telah memakai aturan baru.

Untuk menerapkan aturan baru, muat notebook terbaru dan Run All: bagian 6 harus
menghitung graph/routing baru dari snapshot yang sama, kemudian bagian 8 memakai
konektor baru itu. Ini berbeda dari optimasi bagian 8 sebelumnya yang cukup
memakai ulang hasil bagian 6 tanpa mengganti kebijakan.

## Validasi aktual

- Suite Area Coverage: 104 tes, 89 lulus dan 15 skip pada interpreter utama.
- Worker GDAL: tes profil baru lulus (empat tes non-Shapely, lima skip untuk
  worker graph); 17 tes motor strict lama lulus. Worker graph: 43 tes LI-3 lama
  lulus. Tidak mengubah perilaku default strict pada fixture historis.
- Tes baru mencakup tag primary/private/conditional, gate tidak jelas vs locked,
  static/conditional/malformed oneway, turn policy, source identity dan penolakan
  acceptance bila seluruh ruas tetap UNKNOWN.
- Smoke SYNTHETIC bagian 6/8 dengan tiga bangunan dan jalan bertag primary serta
  access private/conditional: strict menghasilkan 3 ACCESS_UNVERIFIED, profil
  baru menghasilkan 3 ACCEPTED skenario. Seluruh baris direkonsiliasi dan market
  menggunakan profil yang sama. Bukti tersimpan pada
  results/area_coverage_map/barrier_oneway/synthetic_smoke.json.

Belum menjalankan ulang lokasi aktual dengan 17.227 bangunan. Tidak mengklaim
jumlah accepted baru, akses lapangan valid, atau peningkatan akurasi dari
perubahan asumsi ini.
