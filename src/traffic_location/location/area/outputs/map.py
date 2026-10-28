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
    estimates={r['building_id']:r for r in result.get('population_estimates',[])}
    bins={};geod=Geod(ellps='WGS84')
    for f in read(Path(pilot)/'normalized/buildings.geojson')['features']:
        bid=f['properties']['building_id'];e=estimates.get(bid)
        if not (e['included'] if e else bid in allocated):continue
        center=shape(f['geometry']).centroid
        _,_,distance=geod.inv(config['longitude'],config['latitude'],center.x,center.y)
        radius='0–400 m' if distance<=400 else '>400–800 m' if distance<=800 else '>800–2000 m' if distance<=2000 else '>2000 m'
        kind=e['type'] if e else 'Residential';key=(radius,kind)
        value=bins.setdefault(key,{'radius':radius,'Tipe Bangunan':kind,'Jumlah bangunan':0,'jumlah kepala':0.,'jumlah_bangunan':0,'jumlah_KK':0})
        value['Jumlah bangunan']+=1;value['jumlah_bangunan']+=1;value['jumlah_KK']+=1
        if e and e['population'] is None:value['jumlah kepala']=None
        elif value['jumlah kepala'] is not None:value['jumlah kepala']+=e['population'] if e else 4
    areas=list(bins.values())
    road_tree=None;road_edges=[]
    graph_path=Path(pilot)/'graph/graph.json.gz'
    if graph_path.exists():
        from shapely.strtree import STRtree
        road_edges=[e for e in read(graph_path).get('edges',[]) if e.get('geometry')]
        if road_edges:road_tree=STRtree([shape(e['geometry']) for e in road_edges])
    def road_type(store):
        if road_tree is None:return None
        from shapely.geometry import Point
        from pyproj import Transformer
        x,y=Transformer.from_crs(4326,config['metric_crs'],always_xy=True).transform(store['longitude'],store['latitude'])
        return road_edges[int(road_tree.nearest(Point(x,y)))].get('highway')
    def stores(kind):
        ordered=sorted((r for r in result['stores'] if r['kind']==kind),key=lambda r:(r['distance_to_candidate_m'],r['store_key']))[:5]
        source=Path(result['output_path']).parent/'work/bq_snapshot'/(kind+'.json')
        if not source.exists():source=Path(pilot).parent/'bq_snapshot'/(kind+'.json')
        snapshot=read(source).get('rows',[]) if source.exists() else []
        output=[]
        for r in ordered:
            identities={v['store_id'] for v in snapshot if v.get('latitude')==r['latitude'] and v.get('longitude')==r['longitude'] and v.get('store_id')}
            code=r.get('store_id') or (next(iter(identities)) if len(identities)==1 else None)
            item={'Kdtk':code,'nama_toko':r['name'],'KDTK':code,'NAMA_TOKO':r['name'],'Jarak (m)':r['distance_to_candidate_m'],'Tipe Jalan':r.get('road_type') or r.get('highway') or road_type(r)}
            metadata=Path(source).parent/'indomaret-details.json'
            if kind=='indomaret' and metadata.exists():
                details=read(metadata).get('rows',[]);match=[v for v in details if str(v.get('KDTK'))==str(code)]
                if len(match)==1:item.update({k:v for k,v in match[0].items() if k not in ('KDTK','NAMA_TOKO')})
            output.append(item)
        return output
    payload={'schema_version':'area_display_v1','area':areas,'area_basis':'ENGINE_ALLOCATED_BUILDINGS_GEODESIC_FOOTPRINT_CENTROID_RADIUS_NOT_PPAC_SHARES',
             'population_basis':'OWNER_FOOTPRINT_LEVELS_OCCUPANCY_V1; ESTIMATED; includes allocated plus UNVERIFIED; disjoint centroid radii','poi':[{'tipe_POI':r['category'],'nama_POI':r.get('name')} for r in (facilities.get('rows') or []) if r.get('name') is not None and str(r['name']).strip() and str(r['name']).strip().lower() not in ('null','none','nan')],
             'poi_status':facilities.get('status'),'competitors':stores('competitor'),'indomaret':stores('indomaret')}
    write(Path(result['output_path'])/'display-tables.json',payload)
    return payload


def building_tooltips(m,result):
    import folium
    from branca.element import Element
    from html import escape
    estimates={r['building_id']:r for r in result.get('population_estimates',[])}
    folium.map.CustomPane('building-info',z_index=450).add_to(m,index=0)
    m.get_root().header.add_child(Element('<style>.building-tooltip{width:200px;max-width:200px;max-height:115px;overflow-y:auto;white-space:normal!important;overflow-wrap:anywhere;pointer-events:auto}.building-tooltip td,.building-tooltip th{white-space:normal!important;overflow-wrap:anywhere}</style>'))
    def visit(node):
        for child in list(node._children.values()):
            if isinstance(child,folium.GeoJson):
                features=child.data.get('features',[])
                if not features or 'ID' not in features[0].get('properties',{}):continue
                for feature in features:
                    p=feature['properties'];e=estimates.get(p['ID'],{})
                    p['Tipe Bangunan']=escape(e.get('type','Unknown'))
                    p['Populasi estimasi (orang)']=round(e['population'],2) if e.get('population') is not None else 'Belum tersedia'
                child.options['pane']='building-info'
                for key,c in list(child._children.items()):
                    if isinstance(c,(folium.GeoJsonTooltip,folium.GeoJsonPopup)):del child._children[key]
                fields=['ID','Tipe Bangunan','AREA','Status','Reason','Populasi estimasi (orang)']
                folium.GeoJsonTooltip(fields=fields,aliases=['ID Bangunan','Tipe Bangunan','Area (m²)','Status','Reason','Populasi estimasi (orang)'],class_name='building-tooltip',sticky=False).add_to(child)
                folium.GeoJsonPopup(fields=fields,max_width=300).add_to(child)
            else:visit(child)
    visit(m)


def render_esri(config,market_config,pilot,facilities,result,**kwargs):
    import folium
    display_tables(config,pilot,facilities,result)
    save=folium.Map.save
    def grouped(m,*args,**kw):
        building_tooltips(m,result)
        consolidate(m)
        return save(m,*args,**kw)
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
