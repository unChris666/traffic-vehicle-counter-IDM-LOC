"""Konstanta PPAC. Nama berkas mengikuti permintaan pemilik bisnis.

Sumber: PPAC RESIDENTIAL & TRAFFIC v.12062026.5323.xlsx, PRINT PPAC.
30/50/20: instruksi pemilik bisnis di percakapan; bukan pengukuran geografis.
Koefisien NAS/cabang, SWOT, potongan dan parkir harus diselesaikan pemanggil;
tidak ada koefisien lokasi yang disalin menjadi default universal.
"""
from types import MappingProxyType

RESIDENTIAL_SHARES = MappingProxyType({
    '0_400m': 0.30, 'gt400_800m': 0.50, 'gt800m': 0.20,
})
OCCUPANTS_PER_BUILDING = 4  # Konfirmasi pemilik: bangunan ×4 penghuni.
DAYS_PER_MONTH = 30  # K96:K98
WEEKS_PER_MONTH = 4  # H96
EXTRA_DAYS_FOR_SEVEN_DAY_WEEK = 2  # H96
RADIUS_MULTIPLIERS = MappingProxyType({
    '0_400m': 1.0, 'gt400_800m': 0.5, 'gt800m': 0.25,
})  # I96:I98; tiga kelompok terpisah tanpa tumpang tindih.
SAMPLE_MINUTES = 5
MINUTES_PER_HOUR = 60
NORMAL_HOURS = 15  # AE8; sisa jam memakai pengamatan shift 3
DAY_WEIGHTS = MappingProxyType({'weekday': 4, 'weekend': 3})  # E77
ZERO_RATIO_BASE_SHARE = 0.5  # AF20:AF24
DRIVE_THRU_SHARE = 0.40  # X78
CATEGORIES = ('motor', 'mobil', 'angkutan_umum', 'sepeda', 'pejalan_kaki')
SESSIONS_NORMAL = ('pagi', 'siang', 'sore', 'malam')
SESSIONS_SHIFT3 = ('tengah_malam', 'dini_hari', 'subuh')
# N254:O276: kolom tanpa / dengan drive thru. Berlaku semua kategori per jalan.
ROAD_RATES = MappingProxyType({
    'highway': (0.01, 0.03), 'mainstreet': (0.015, 0.028),
    'street': (0.02, 0.026), 'substreet': (0.025, 0.025),
})
# G254:G276: urutan kategori sama dengan CATEGORIES.
TRAFFIC_BASE_COEFFICIENTS = MappingProxyType({
    'highway': (0.5, 1.0, 0.5, 0.5, 0.25),
    'mainstreet': (0.5, 0.75, 0.5, 0.5, 0.5),
    'street': (0.5, 0.5, 0.5, 0.5, 0.75),
    'substreet': (0.5, 0.25, 0.75, 1.0, 1.0),
})
