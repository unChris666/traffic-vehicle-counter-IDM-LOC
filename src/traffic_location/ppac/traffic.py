"""MVP v2 traffic: four categories, AE18 lookup disabled; other reference arithmetic unchanged."""
from . import konstatna as K
from ._reference import _samples, _number, _mean, excel_round

def calculate(samples, *, road_type, operating_hours,
                      drive_thru=False):
    """PRINT PPAC K53:P75, E77: rata-rata sampel -> STD per hari -> bobot 4/3.

    AE18 lookup omitted by owner MVP decision; multiplier is 1, not a lookup result.
    Missing hari tetap None; kontribusinya 0 pada bobot tetap Excel 4/3.
    Status hasil menjadi sementara. Tidak merekayasa sampel nol.
    """
    categories = tuple(c for c in K.CATEGORIES if c != "sepeda")
    _samples(samples)
    if road_type not in K.ROAD_RATES or not isinstance(drive_thru, bool):
        raise ValueError('road_type / drive_thru tidak valid')
    hours = _number(operating_hours, 'operating_hours', maximum=24)
    balance = 1.0  # Owner MVP: AE18 lookup omitted, no ratio multiplier adjustment.
    normal_hours = min(hours, K.NORMAL_HOURS)
    shift_hours = hours - normal_hours
    required = K.SESSIONS_NORMAL + (K.SESSIONS_SHIFT3 if shift_hours else ())
    missing = [f'{d}/{s}/{c}' for d in K.DAY_WEIGHTS for s in required for c in categories
               if samples.get(d, {}).get(s, {}).get(c) is None]
    means_all = {d: {c: _mean([samples.get(d, {}).get(s, {}).get(c) for s in
                              K.SESSIONS_NORMAL + K.SESSIONS_SHIFT3])
                     for c in categories} for d in K.DAY_WEIGHTS}
    factors = {}
    fallbacks = []
    for c, base in [(c,b) for c,b in zip(K.CATEGORIES, K.TRAFFIC_BASE_COEFFICIENTS[road_type]) if c in categories]:
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
        for c in categories:
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
