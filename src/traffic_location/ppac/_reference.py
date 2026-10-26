"""Perhitungan STD PPAC, Python standard library, tanpa mengubah engine sumber.

None = belum dicacah; 0 = sudah dicacah tanpa arus. Input Residential wajib
menyatakan satuan bangunan atau penghuni. Koefisien gabungan KK, SWOT,
potongan dan parkir adalah input hasil lookup/penilaian, bukan tebakan.
Lihat README_PPAC.md untuk cakupan, satuan, dan batas kesetaraan Excel.
"""
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from numbers import Real
from collections.abc import Mapping
from . import konstatna as K


def _number(value, name, *, maximum=None):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f'{name} harus angka, bukan bool/teks/None')
    value = float(value)
    if not isfinite(value) or value < 0 or (maximum is not None and value > maximum):
        raise ValueError(f'{name} di luar batas yang diizinkan')
    return value


def excel_round(value):
    """ROUND(x,0): .5 menjauh dari nol, berbeda dari round bawaan Python."""
    if not isfinite(float(value)):
        raise ValueError('Pembulatan memerlukan angka finite')
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def split_residential(total, *, unit):
    """Alokasi estimasi 30/50/20 dari total bangunan atau penghuni.

    Bangunan dikalikan 4; penghuni langsung dipakai (sudah dikali 4 oleh Area).
    Bukan hitungan KK terverifikasi atau pengukuran jarak aktual per bangunan.
    """
    total = _number(total, 'total_residential')
    if unit not in ('bangunan', 'penghuni'):
        raise ValueError("unit wajib 'bangunan' atau 'penghuni'")
    people = total * K.OCCUPANTS_PER_BUILDING if unit == 'bangunan' else total
    near = people * K.RESIDENTIAL_SHARES['0_400m']
    middle = people * K.RESIDENTIAL_SHARES['gt400_800m']
    far = people - near - middle
    return {'total_penghuni': people, 'penghuni_400m': near,
            'penghuni_400_800m': middle, 'penghuni_gt800m': far,
            'allocation_method': 'estimated_30_50_20',
            'source_unit': unit, 'source_total': total}


def calculate_residential(total, *, unit, combined_coefficient,
                          operating_days_per_week, swot_factor,
                          far_eligible=True):
    """K96:K100 dengan pengganti input berdasarkan keputusan pemilik.

    Total penghuni dibagi 30 lalu dikali koefisien, pengali jarak, hari/SWOT.
    combined_coefficient = J96 (AC17 - AK30), bukan persentase murni.
    swot_factor = E92 (1 jika penyesuaian tidak berlaku).
    Kebijakan baru mengalokasikan 20% ke >800m dan memakainya secara default.
    far_eligible=False dapat mengecualikannya atas keputusan pemanggil;
    fungsi tidak mengevaluasi otomatis checklist satelit Excel F98.
    """
    split = split_residential(total, unit=unit)
    coefficient = _number(combined_coefficient, 'combined_coefficient')
    days = _number(operating_days_per_week, 'operating_days_per_week', maximum=7)
    swot = _number(swot_factor, 'swot_factor')
    if not isinstance(far_eligible, bool):
        raise ValueError('far_eligible harus bool')
    monthly_days = days * K.WEEKS_PER_MONTH
    if days > 6:
        monthly_days += K.EXTRA_DAYS_FOR_SEVEN_DAY_WEEK
    common = coefficient / K.DAYS_PER_MONTH
    common *= monthly_days / K.DAYS_PER_MONTH * swot
    near = excel_round(split['penghuni_400m'] * common * K.RADIUS_MULTIPLIERS['0_400m'])
    middle = excel_round(split['penghuni_400_800m'] * common * K.RADIUS_MULTIPLIERS['gt400_800m'])
    far_people = split['penghuni_gt800m'] if far_eligible else 0
    far = excel_round(far_people * common * K.RADIUS_MULTIPLIERS['gt800m'])
    return {**split, 'std_400m': near, 'std_400_800m': middle,
            'std_gt800m': far, 'std_residential': near + middle + far,
            'operating_days_month': monthly_days, 'far_eligible': far_eligible,
            'combined_coefficient': coefficient, 'swot_factor': swot}


def _samples(samples):
    if not isinstance(samples, Mapping):
        raise ValueError('samples harus mapping weekday/weekend -> sesi -> kategori')
    if set(samples) - set(K.DAY_WEIGHTS):
        raise ValueError('Kelompok hari tidak dikenal')
    for day, sessions in samples.items():
        if not isinstance(sessions, Mapping):
            raise ValueError(f'{day}: sesi harus mapping')
        if set(sessions) - set(K.SESSIONS_NORMAL + K.SESSIONS_SHIFT3):
            raise ValueError(f'{day}: nama sesi tidak dikenal')
        for session, categories in sessions.items():
            if not isinstance(categories, Mapping) or set(categories) - set(K.CATEGORIES):
                raise ValueError(f'{day}/{session}: kategori tidak dikenal')
            for category, count in categories.items():
                if count is not None:
                    count = _number(count, f'{day}/{session}/{category}')
                    if not count.is_integer():
                        raise ValueError('Hasil pencacahan harus bilangan bulat')


def _mean(values):
    available = [v for v in values if v is not None]
    return sum(available) / len(available) if available else None


def calculate_traffic(samples, *, road_type, operating_hours,
                      balance_multiplier, drive_thru=False):
    """PRINT PPAC K53:P75, E77: rata-rata sampel -> STD per hari -> bobot 4/3.

    balance_multiplier = AE18: 0.5/0.6 dari lookup YA/TIDAK di workbook;
    wajib input, agar tidak menafsirkan YA/TIDAK tanpa konteks.
    Missing hari tetap None; kontribusinya 0 pada bobot tetap Excel 4/3.
    Status hasil menjadi sementara. Tidak merekayasa sampel nol.
    """
    _samples(samples)
    if road_type not in K.ROAD_RATES or not isinstance(drive_thru, bool):
        raise ValueError('road_type / drive_thru tidak valid')
    hours = _number(operating_hours, 'operating_hours', maximum=24)
    balance = _number(balance_multiplier, 'balance_multiplier')
    normal_hours = min(hours, K.NORMAL_HOURS)
    shift_hours = hours - normal_hours
    required = K.SESSIONS_NORMAL + (K.SESSIONS_SHIFT3 if shift_hours else ())
    missing = [f'{d}/{s}/{c}' for d in K.DAY_WEIGHTS for s in required for c in K.CATEGORIES
               if samples.get(d, {}).get(s, {}).get(c) is None]
    means_all = {d: {c: _mean([samples.get(d, {}).get(s, {}).get(c) for s in
                              K.SESSIONS_NORMAL + K.SESSIONS_SHIFT3])
                     for c in K.CATEGORIES} for d in K.DAY_WEIGHTS}
    factors = {}
    fallbacks = []
    for c, base in zip(K.CATEGORIES, K.TRAFFIC_BASE_COEFFICIENTS[road_type]):
        a, b = (means_all[d][c] for d in K.DAY_WEIGHTS)
        ratio = min(a, b) / max(a, b) * balance if a is not None and b is not None and max(a, b) else 0
        if ratio == 0:
            fallbacks.append(c)
        factors[c] = base * (ratio if ratio else K.ZERO_RATIO_BASE_SHARE)
    rate = K.ROAD_RATES[road_type][int(drive_thru)]
    day_results = {}
    detail = {}
    for d in K.DAY_WEIGHTS:
        subtotal = 0
        has_observation = False
        detail[d] = {}
        for c in K.CATEGORIES:
            components = []
            for sessions, duration in ((K.SESSIONS_NORMAL, normal_hours), (K.SESSIONS_SHIFT3, shift_hours)):
                avg = _mean([samples.get(d, {}).get(s, {}).get(c) for s in sessions])
                if duration > 0 and avg is not None:
                    has_observation = True
                components.append(excel_round(avg * (K.MINUTES_PER_HOUR / K.SAMPLE_MINUTES)
                                               * duration * rate * factors[c]) if avg is not None else 0)
            detail[d][c] = sum(components)
            subtotal += sum(components)
        day_results[d] = subtotal if has_observation else None
    any_data = any(v is not None for v in day_results.values())
    std = excel_round(sum((day_results[d] or 0) * w for d, w in K.DAY_WEIGHTS.items())
                      / sum(K.DAY_WEIGHTS.values())) if any_data else None
    return {'std_traffic_raw': std, 'std_by_day': day_results, 'std_by_category': detail,
            'coefficients': factors, 'zero_ratio_fallback_categories': fallbacks,
            'missing_observations': missing,
            'status': 'unavailable' if not any_data else ('sementara' if missing else 'lengkap'),
            'missing_day_policy': 'fixed_excel_4_3_weights', 'sample_minutes': K.SAMPLE_MINUTES}


def calculate_fasum(*, employees_students_residents, daily_visitors,
                    monthly_operating_days, coefficient, distance_multiplier):
    """PRINT PPAC L82:L88. Satu fasum; jumlahkan hasil per fasum ke fasum_std.

    distance_multiplier = K82 (0/.5/.75), harus sudah diputuskan dari jarak/domain.
    Jangan deduplikasi terhadap Traffic: tambahan disengaja oleh pemilik bisnis.
    """
    people = _number(employees_students_residents, 'employees_students_residents')
    visitors = _number(daily_visitors, 'daily_visitors')
    days = _number(monthly_operating_days, 'monthly_operating_days')
    coef = _number(coefficient, 'coefficient')
    distance = _number(distance_multiplier, 'distance_multiplier')
    return excel_round((people + visitors) / K.DAYS_PER_MONTH * coef * distance
                       * (days / K.DAYS_PER_MONTH))


def calculate_ppac(*, residential, traffic, fasum_std, traffic_cut_factor,
                   parking_factor, drive_thru=False):
    """PRINT PPAC E103:E106, E112. Komponen disediakan fungsi di atas.

    traffic_cut_factor = E15; parking_factor = AF56; fasum_std = L89.
    Lookup NAS/cabang, SWOT, potongan dan parkir bukan bagian fungsi ini.
    """
    kk = _number(residential['std_residential'], 'std_residential')
    fasum = _number(fasum_std, 'fasum_std')
    cut = _number(traffic_cut_factor, 'traffic_cut_factor')
    parking = _number(parking_factor, 'parking_factor')
    if not isinstance(drive_thru, bool):
        raise ValueError('drive_thru harus bool')
    raw = traffic['std_traffic_raw']
    if raw is None:
        return {'std_total': None, 'std_residential': kk, 'std_fasum': fasum,
                'status': 'unavailable', 'reason': 'Belum ada pengamatan Traffic'}
    raw = _number(raw, 'std_traffic_raw')
    dt = excel_round(raw * K.DRIVE_THRU_SHARE * cut) if drive_thru else 0
    traffic_std = excel_round(raw * cut * parking - dt) + fasum
    return {'std_total': excel_round(traffic_std + kk + dt), 'std_residential': kk,
            'std_traffic_including_fasum': traffic_std, 'std_fasum': fasum,
            'std_drive_thru': dt, 'status': traffic['status'],
            'residential_allocation': residential['allocation_method']}
