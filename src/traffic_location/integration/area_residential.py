"""Owner PPAC policy: count unresolved buildings without asserting verification.

This adapts the PPAC input only. Native Area ownership/status and Huff remain intact.
"""
def building_basis(native):
    rows=native['rows']
    allocated={r['building_id'] for r in rows if r.get('count_candidate')==1}
    unverified={r['building_id'] for r in rows if r.get('market_status')=='UNVERIFIED'}
    unresolved=unverified-allocated
    return {'policy':'OWNER_ALLOCATED_PLUS_UNVERIFIED_V1',
            'allocated_buildings':len(allocated),'unverified_buildings_included':len(unresolved),
            'ppac_buildings':len(allocated|unresolved),
            'status':'UNVERIFIED' if unverified else native.get('status','UNKNOWN'),
            'kk_basis':'ONE_BUILDING_ONE_KK_FOUR_PEOPLE',
            'reason':'UNVERIFIED included by owner policy; ownership/access uncertainty remains.' if unresolved else 'No additional UNVERIFIED buildings.'}
