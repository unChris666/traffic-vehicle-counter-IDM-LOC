"""Presentation only: consolidated controls and compact verified display tables."""
from pathlib import Path
from unittest.mock import patch
from ....artifacts import read,write
from .._kernel.location_intelligent_kaggle_esri import render_esri as original_render


def consolidate(map_object):
    import folium
    groups={}
    for key,child in list(map_object._children.items()):
        name=getattr(child,'layer_name','')
        if name in ('POI','Indomaret & Kompetitor','Calon toko'):continue
        group=('POI' if name.startswith('POI ') else 'Indomaret & Kompetitor' if name.startswith(('Kompetitor','Indomaret')) else 'Calon toko' if name.startswith(('Calon toko','Calon —')) else None)
        if group:
            if group not in groups:groups[group]=folium.FeatureGroup(name=group,show=True)
            del map_object._children[key];child.add_to(groups[group])
    for group in groups.values():group.add_to(map_object)
    # LayerControl JS references the regrouped layers. Those variables must be
    # defined first; controls left in their old position stop map initialization.
    for key,child in list(map_object._children.items()):
        if isinstance(child,folium.LayerControl):
            del map_object._children[key];child.add_to(map_object)


def display_tables(config,pilot,facilities,result):
    from shapely.geometry import shape
    from pyproj import Geod
    # UI counts retain engine allocation; bins are explicitly centroid geodesic display radii.
    allocated={r['building_id'] for r in result['rows'] if r['count_candidate']==1}
    counts=[0,0,0];geod=Geod(ellps='WGS84')
    for f in read(Path(pilot)/'normalized/buildings.geojson')['features']:
        if f['properties']['building_id'] not in allocated:continue
        center=shape(f['geometry']).centroid
        _,_,distance=geod.inv(config['longitude'],config['latitude'],center.x,center.y)
        if distance<=2000:counts[0 if distance<=400 else 1 if distance<=800 else 2]+=1
    areas=[{'radius':radius,'jumlah_bangunan':count,'jumlah_KK':count} for radius,count in zip(('0–400 m','>400–800 m','>800–2000 m'),counts)]
    if sum(counts)!=len(allocated):areas.append({'radius':'Radius belum terpetakan / di luar 2000 m','jumlah_bangunan':len(allocated)-sum(counts),'jumlah_KK':len(allocated)-sum(counts)})
    def stores(kind):
        ordered=sorted((r for r in result['stores'] if r['kind']==kind),key=lambda r:(r['distance_to_candidate_m'],r['store_key']))[:5]
        source=Path(result['output_path']).parent/'work/bq_snapshot'/(kind+'.json')
        if not source.exists():source=Path(pilot).parent/'bq_snapshot'/(kind+'.json')
        snapshot=read(source).get('rows',[]) if source.exists() else []
        output=[]
        for r in ordered:
            identities={v['store_id'] for v in snapshot if v.get('latitude')==r['latitude'] and v.get('longitude')==r['longitude'] and v.get('store_id')}
            code=r.get('store_id') or (next(iter(identities)) if len(identities)==1 else None)
            output.append({'Kdtk':code,'nama_toko':r['name']})
        return output
    payload={'schema_version':'area_display_v1','area':areas,'area_basis':'ENGINE_ALLOCATED_BUILDINGS_GEODESIC_FOOTPRINT_CENTROID_RADIUS_NOT_PPAC_SHARES',
             'kk_basis':'OWNER_ASSUMPTION_ONE_ALLOCATED_BUILDING_ONE_KK_FOUR_PEOPLE','poi':[{'tipe_POI':r['category'],'nama_POI':r.get('name')} for r in (facilities.get('rows') or [])],
             'poi_status':facilities.get('status'),'competitors':stores('competitor'),'indomaret':stores('indomaret')}
    write(Path(result['output_path'])/'display-tables.json',payload)
    return payload


def render_esri(config,market_config,pilot,facilities,result,**kwargs):
    import folium
    display_tables(config,pilot,facilities,result)
    save=folium.Map.save
    def grouped(m,*args,**kw):consolidate(m);return save(m,*args,**kw)
    with patch.object(folium.Map,'save',grouped):
        return original_render(config,market_config,pilot,facilities,result,**kwargs)


def render_safely(config,policy,pilot,facilities,native):
    import shutil
    try:
        html=render_esri(config,policy,pilot,facilities,native)
        return {'status':'SUCCEEDED','html':str(html)}
    except Exception as exc:
        target=Path(native['output_path'])
        # Never publish a partially written map as a completed HTML artifact.
        shutil.rmtree(target/'views',ignore_errors=True)
        error={'status':'FAILED','stage':'presentation','code':type(exc).__name__,'message':str(exc)[:500]}
        write(target/'error.json',error)
        return error

__all__=['render_esri','render_safely','display_tables']
