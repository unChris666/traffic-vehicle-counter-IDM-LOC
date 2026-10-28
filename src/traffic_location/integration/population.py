"""Owner footprint/levels/occupancy scenario, separate from allocation kernels."""
import math
POLICY='owner_footprint_occupancy_v1'
RWI=('MENENGAH ATAS','MENENGAH BAWAH')
RULES={'Hotel':(2,2,3,(8,5),(60,45),(.60,.30)),
       'Apartement':(2,2,10,(20,10),(45,36),(.70,.75)),
       'Kost':(1,2,2,(5,3),(45,36),(.98,.95)),
       'Dormitory':(1,1,2,(3,2),(60,45),(.98,.95))}
def number(v):
    try:
        n=float(v);return n if math.isfinite(n) and n>0 else None
    except (TypeError,ValueError):return None

def estimate(props,area,rwi):
    if rwi not in RWI:raise ValueError('RWI_REQUIRED: pilih MENENGAH ATAS/MENENGAH BAWAH')
    tags=props.get('osm_tags') or {}
    tokens={str(v).lower().strip() for v in (props.get('class'),props.get('subclass'),tags.get('building'),tags.get('tourism'),props.get('building_type')) if v}
    kind=next((k for k,terms in [('Hotel',{'hotel'}),('Apartement',{'apartment','apartments','apartement'}),('Kost',{'kost','boarding_house','boarding house','boardinghouse'}),('Dormitory',{'dorm','dormitory'})] if tokens & terms),'Residential')
    out={'type':kind,'footprint_m2':number(area),'rwi':rwi,'policy_version':POLICY,'quality':'ESTIMATED','actual_levels':number(props.get('num_floors') or tags.get('building:levels'))}
    if kind=='Residential':return {**out,'population':4.,'occupancy':1.,'basis':'ONE_BUILDING_FOUR_PEOPLE; unknown use grouped as Residential'}
    offset,people,minimum,levels,rooms,occupancy=RULES[kind];i=RWI.index(rwi)
    actual=out['actual_levels'];effective=max(actual or levels[i],minimum)
    return {**out,'effective_levels':effective,'levels_basis':'RWI_DEFAULT' if actual is None else 'OWNER_MINIMUM_OVERRIDE' if effective!=actual else 'SOURCE',
            'room_m2':rooms[i],'floor_offset':offset,'people_per_room':people,'occupancy':occupancy[i],
            'population':None if out['footprint_m2'] is None else out['footprint_m2']/rooms[i]*(effective-offset)*people*occupancy[i]}

def records(features,rows,rwi):
    by_id={r['building_id']:r for r in rows};out=[]
    for f in features:
        props=f['properties'];bid=props['building_id'];row=by_id[bid]
        area=row.get('area_m2')
        if number(area) is None:
            from shapely.geometry import shape
            from pyproj import Geod
            area=abs(Geod(ellps='WGS84').geometry_area_perimeter(shape(f['geometry']))[0])
        out.append({'building_id':bid,'status':row.get('market_status'),'reason':row.get('reason'),
                    'included':row.get('count_candidate')==1 or row.get('market_status')=='UNVERIFIED',
                    **estimate(props,area,rwi)})
    return out

def total(native,rwi):
    if rwi not in RWI:raise ValueError('RWI_REQUIRED')
    rows=native.get('population_estimates')
    if rows is None:raise ValueError('POPULATION_METADATA_UNAVAILABLE: jalankan Area baru dengan RWI')
    selected=[r for r in rows if r['included']]
    if native.get('rows') is not None:
        expected={r['building_id'] for r in native['rows'] if r.get('count_candidate')==1 or r.get('market_status')=='UNVERIFIED'}
        if {r['building_id'] for r in selected}!=expected or len({r['building_id'] for r in rows})!=len(rows):raise ValueError('POPULATION_BUILDING_MEMBERSHIP_MISMATCH')
    if any(r['rwi']!=rwi or r['population'] is None for r in selected):raise ValueError('POPULATION_INPUT_INCOMPLETE_OR_RWI_MISMATCH')
    return {'policy_version':POLICY,'rwi':rwi,'population':sum(r['population'] for r in selected),'buildings':len(selected),'quality':'ESTIMATED'}
