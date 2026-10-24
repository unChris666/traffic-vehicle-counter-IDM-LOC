"""Pure deterministic market allocation. No retrieval, rendering or random draws."""
import math
import re
import unicodedata
from collections import Counter


def corridor_tokens(tags):
    """Exact normalized names/refs; no fuzzy join of unnamed roads."""
    tokens = set()
    for key in ('name', 'ref'):
        for value in str(tags.get(key) or '').split(';'):
            value = unicodedata.normalize('NFKC', value).casefold().strip()
            value = re.sub(r'^(?:jl\.?|jln\.?)\s+', 'jalan ', value)
            value = re.sub(r'\s+', ' ', value)
            if value:
                tokens.add(key + ':' + value)
    return sorted(tokens)


def classify_store(store, target_tokens, policy):
    out = dict(store)
    core_radius = policy['exclusive_core_m']
    if store['kind'] == 'candidate':
        out.update(tier='CANDIDATE', core_m=core_radius, display_radius_m=None)
    elif store['kind'] == 'indomaret':
        distance = store['distance_to_candidate_m']
        core = core_radius if policy['indomaret_core_target_min_m'] <= distance < policy['indomaret_core_target_max_m'] else 0.0
        out.update(tier='INDOMARET', core_m=core, display_radius_m=core)
    elif store['distance_to_candidate_m'] > policy['primary_same_corridor_within_m']:
        out.update(tier='SECONDARY', core_m=core_radius, display_radius_m=100.0)
    elif not target_tokens or not store.get('corridor_tokens'):
        out.update(tier='UNVERIFIED_CORRIDOR', core_m=core_radius, display_radius_m=None)
    else:
        primary = bool(set(target_tokens) & set(store['corridor_tokens']))
        out.update(tier='PRIMARY' if primary else 'SECONDARY', core_m=core_radius,
                   display_radius_m=400.0 if primary else 100.0)
    return out


def route_eligible(route, policy):
    if route is None:
        return False
    distance = route.get('total_distance_m')
    if type(distance) not in (int, float) or not math.isfinite(distance) or distance < 0:
        raise ValueError('Invalid route distance')
    minutes = distance / (policy['speed_kmh'] * 1000) * 60
    return round(minutes) <= policy['max_travel_minutes']


def huff(options, exponent=2.0):
    """Stable inverse-distance scores. Zero distance uses a defined limiting rule."""
    if not options:
        return []
    if not math.isfinite(exponent) or exponent <= 0:
        raise ValueError('Huff exponent must be positive and finite')
    if len({r['store_key'] for r in options}) != len(options):
        raise ValueError('Duplicate store identity in Huff input')
    for r in options:
        if type(r['total_distance_m']) not in (float, int) or not math.isfinite(r['total_distance_m']) or r['total_distance_m'] < 0:
            raise ValueError('Invalid Huff distance')
    minimum = min(r['total_distance_m'] for r in options)
    weights = [float(r['total_distance_m'] == 0) if minimum == 0 else (minimum / r['total_distance_m']) ** exponent for r in options]
    total = math.fsum(weights)
    rows = [{**r, 'huff_score': w / total} for r, w in zip(options, weights)]
    return sorted(rows, key=lambda r: (-r['huff_score'], r['total_distance_m'], r['store_key']))


def restaurant_cluster(sites, maximum_pair_distance_m=200.0, minimum_sites=5):
    """Find a deterministic complete-link group, not a chain spanning a district.

    Coordinates are projected metres. Each footprint can count only once; the
    orchestrator must establish >=40m² and a route before supplying sites.
    """
    by_id = {}
    for site in sorted(sites, key=lambda r: r['source_id']):
        by_id.setdefault(site['building_id'], site)
    sites = sorted(by_id.values(), key=lambda r: r['source_id'])
    neighbors = {i: set() for i in range(len(sites))}
    for i, a in enumerate(sites):
        for j in range(i + 1, len(sites)):
            b = sites[j]
            if math.dist(a['xy'], b['xy']) <= maximum_pair_distance_m and set(a['corridor_tokens']) & set(b['corridor_tokens']):
                neighbors[i].add(j); neighbors[j].add(i)
    # A common corridor token is required across all five, not just each pair.
    def search(chosen, available, tokens):
        if len(chosen) >= minimum_sites:
            return [sites[i]['source_id'] for i in chosen]
        while available:
            if len(chosen) + len(available) < minimum_sites:
                return None
            i = min(available); available.remove(i)
            common = set(sites[i]['corridor_tokens']) if tokens is None else tokens & set(sites[i]['corridor_tokens'])
            if not common:
                continue
            found = search(chosen + [i], available & neighbors[i], common)
            if found:
                return found
        return None
    return search([], set(neighbors), None)


def allocate_building(building, stores, routes, gate, policy, *, inputs_complete=True):
    """One row per footprint. Routing and market classifications stay separate."""
    row = {'building_id': building['building_id'], 'access_status': building['access_status'],
           'market_status': 'OTHERS', 'reason': None, 'winner_store_key': None,
           'count_candidate': 0, 'scores': [], 'estimated': True}
    if not building.get('residential') or not (policy['residential_min_area_m2'] <= building['area_m2'] < policy['residential_max_area_m2_exclusive']):
        row['reason'] = 'NOT_ELIGIBLE_RESIDENTIAL'; return row
    distance = building['distance_to_candidate_m']
    if distance > policy['zones_m'][-1]:
        row['reason'] = 'OUTSIDE_2000M'; return row
    if building['access_status'] != 'ACCEPTED':
        row['reason'] = 'CANDIDATE_ACCESS_' + building['access_status']; return row
    if distance > policy['competition_cannibalization_zone_m'] and gate['state'] != 'OPEN':
        row['reason'] = 'OUTER_GATE_' + gate['state']; return row
    if not inputs_complete:
        row.update(market_status='UNVERIFIED', reason='MARKET_INPUTS_INCOMPLETE'); return row
    by_key = {s['store_key']: s for s in stores}
    if 'candidate' not in by_key:
        raise ValueError('Candidate missing')
    eligible = {k: r for k, r in routes.items() if k in by_key and route_eligible(r, policy)}
    if 'candidate' not in eligible:
        row['reason'] = 'CANDIDATE_ROUTE_NOT_ELIGIBLE'; return row
    # Core ownership precedes statistical zones. Candidate's core wins only
    # eligible overlaps when store centres are <=100m, as owner confirmed.
    cores = []
    for key in eligible:
        store = by_key[key]
        if store['core_m'] > 0 and building['store_distances_m'].get(key, math.inf) <= store['core_m']:
            cores.append(key)
    if 'candidate' in cores:
        cores = [k for k in cores if k == 'candidate' or by_key[k]['distance_to_candidate_m'] > policy['exclusive_core_m']]
    if cores:
        scored = huff([{**eligible[k], 'store_key': k} for k in cores], policy['huff_exponent'])
        method = 'EXCLUSIVE_100M_CORE' if len(cores) == 1 else 'OVERLAPPING_CORES_HUFF'
    else:
        contenders = ['candidate']
        unresolved = False
        for key in eligible:
            if key == 'candidate':
                continue
            store = by_key[key]
            if distance <= policy['candidate_competitor_contest_inner_radius_m']:
                if store['kind'] == 'competitor' and store['tier'] == 'UNVERIFIED_CORRIDOR':
                    unresolved = True
                elif store['kind'] == 'competitor' and store['tier'] == 'PRIMARY':
                    contenders.append(key)
            else:
                contenders.append(key)
        if unresolved:
            row.update(market_status='UNVERIFIED', reason='PRIMARY_CORRIDOR_UNVERIFIED'); return row
        scored = huff([{**eligible[k], 'store_key': k} for k in contenders], policy['huff_exponent'])
        method = 'HUFF_ROUTE_DISTANCE'
    winner = by_key[scored[0]['store_key']]
    kinds = {by_key[r['store_key']]['kind'] for r in scored}
    if winner['kind'] == 'competitor':
        status = 'COMPETITOR_OWNED'
    elif winner['kind'] == 'indomaret':
        status = 'INDOMARET_OWNED'
    elif 'indomaret' in kinds:
        status = 'MARKET_CANNIBALIZATION'
    elif 'competitor' in kinds:
        status = 'MARKET_COMPETITION'
    else:
        status = 'VALID'
    row.update(market_status=status, reason=method, winner_store_key=winner['store_key'],
               count_candidate=int(winner['kind'] == 'candidate'), scores=scored,
               contest_kinds=sorted(kinds - {'candidate'}))
    return row


def reconcile(rows):
    if len({r['building_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate building row in market ledger')
    assigned = [r for r in rows if r['winner_store_key'] is not None]
    for r in assigned:
        if not math.isclose(math.fsum(s['huff_score'] for s in r['scores']), 1.0, abs_tol=1e-12):
            raise ValueError('Huff scores do not reconcile')
    owners = dict(sorted(Counter(r['winner_store_key'] for r in assigned).items()))
    assert sum(owners.values()) + len(rows) - len(assigned) == len(rows)
    assert owners.get('candidate', 0) == sum(r['count_candidate'] for r in rows)
    return {'rows': len(rows), 'assigned': len(assigned), 'unassigned': len(rows) - len(assigned),
            'candidate_whole_buildings': owners.get('candidate', 0), 'whole_buildings_by_store': owners,
            'market_status_counts': dict(sorted(Counter(r['market_status'] for r in rows).items())),
            'reason_counts': dict(sorted(Counter(r['reason'] for r in rows).items()))}
