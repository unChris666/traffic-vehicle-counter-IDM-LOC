"""CLI synthetic CPU/GDAL integration smoke; no live data/API or customer claims."""
import sys,json,tempfile,math,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))

def main():
    from location_intelligent_li3_sources import write_json,read_json
    from location_intelligent_market_config import get_market_config
    from location_intelligent_config import get_config
    from location_intelligent_validator import canonical_hash
    from pyproj import Transformer
    from location_intelligent_osm_buildings import prepare_osm_from_network,SCHEMA
    from location_intelligent_li3 import build,make_manifest
    from location_intelligent_market_runtime import build_market
    from location_intelligent_map_poi import normalize_pois
    from location_intelligent_market_map import render_market
    from unittest.mock import patch
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    parser.add_argument('--feature-mode',choices=['FULL','ROADS_ONLY_EXPERIMENT'],default='ROADS_ONLY_EXPERIMENT')
    args=parser.parse_args()
    root=args.output or Path(tempfile.mkdtemp(prefix='SYNTHETIC-market-'))
    root.mkdir(parents=True,exist_ok=True)
    market=get_market_config();target=market['target']
    market['sources']['network_feature_mode']=args.feature_mode
    config={'latitude':target['latitude'],'longitude':target['longitude'],'metric_crs':'EPSG:32748',
     'building_radius_m':2000.,'poi_radius_m':2000.,'min_area_m2':36.,'max_area_m2':550.,
     'selection_profile':'area-market-ge36-v1','network_radius_m':5500.,'osm_use_policy_version':'osm_poi_use_v2',
     'poi_profile':'market_attractors_v2','core_python':'/usr/bin/python3'}
    config['network_feature_mode']=args.feature_mode
    tx=Transformer.from_crs(4326,32748,always_xy=True);inv=Transformer.from_crs(32748,4326,always_xy=True)
    x,y=tx.transform(target['longitude'],target['latitude'])
    def point(a,b):
     lon,lat=inv.transform(x+a,y+b);return {'lon':lon,'lat':lat}
    seed=root/'seed';p=get_config();p['li3'].update(latitude=target['latitude'],longitude=target['longitude'],network_bbox_radius_m=5500.,metric_crs=config['metric_crs'])
    f={'schema_version':'li3_pilot_config_v1','algorithm_version':'LI3_V1','analysis_run_id':'SYNTHETIC',
     'frozen_at':'2026-10-24T00:00:00Z','policy':p,'target_xy':[x,y],'reference_metric_bbox':[x-5500,y-5500,x+5500,y+5500],
     'diagnostic_gap_m':10.,'building_cache_files':{}}
    f['config_hash']=canonical_hash(f);write_json(seed/'config/pilot.json',f)
    meta={'timestamp_osm_base':'2026-10-24T00:00:00Z'}
    road={'status':'SUCCEEDED','payload':{'osm3s':meta,'elements':[
     {'type':'node','id':1,**point(-100,10)},{'type':'node','id':2,**point(1000,10)},
     {'type':'way','id':10,'nodes':[1,2],'tags':{'highway':'residential','name':'Jalan SYNTHETIC'}}]}}
    write_json(seed/'raw/osm_roads.json.gz',road)
    if args.feature_mode=='ROADS_ONLY_EXPERIMENT':
     write_json(seed/'raw/osm_features_roads_only.json.gz',{'status':'SUCCEEDED',
      'provider':'DERIVED_FROM_ACTUAL_OSM_ROAD_EXTRACT','coverage':'ROAD_EXTRACT_ONLY_EXTERNAL_FEATURES_NOT_REQUESTED',
      'source_roads_sha256':__import__('hashlib').sha256((seed/'raw/osm_roads.json.gz').read_bytes()).hexdigest(),
      'external_features_requested':False,'restrictions_complete':False,'payload':road['payload']})
    write_json(seed/'raw/osm_features_pinned.json.gz',{'status':'SUCCEEDED','payload':{'osm3s':meta,'elements':[]}})
    elements=[]
    for i,a in enumerate([40,120,400],start=1):
     elements.append({'type':'way','id':100+i,'tags':{'building':'house'},'geometry':[point(a+dx,40+dy) for dx,dy in [(-5,-3),(5,-3),(5,3),(-5,3),(-5,-3)]]})
    raw={'provider':'OPENSTREETMAP','schema_version':SCHEMA,'release':meta['timestamp_osm_base'],
     'source_as_of':meta['timestamp_osm_base'],'acquired_at':'2026-10-24T00:00:00Z',
     'bounded_query_complete':True,'truncated':False,'bbox':[106.8,-6.3,106.9,-6.1],
     'payload':{'osm3s':meta,'elements':elements},'use_poi_nodes':[]}
    rawpath=root/'raw.json.gz';write_json(rawpath,raw)
    facilities=normalize_pois(config,{'osm3s':meta,'elements':[{'type':'node','id':999,**{'lat':point(700,0)['lat'],'lon':point(700,0)['lon']},'tags':{'amenity':'hospital','name':'SYNTHETIC HOSPITAL'}}]})
    poipath=root/'pois.json';write_json(poipath,facilities);config['osm_poi_snapshot_path']=str(poipath)
    pilot=root/'pilot';prepare_osm_from_network(config,pilot,seed,rawpath)
    r=build(pilot);make_manifest(pilot)
    print('SYNTHETIC ACTUAL PIPELINE:',r['decision_counts_selected'])
    binding={'latitude':config['latitude'],'longitude':config['longitude'],'radius_m':2000.}
    layers={}
    from pyproj import Geod
    for kind,a in [('competitor',160),('indomaret',500)]:
     q=point(a,0);dist=Geod(ellps='WGS84').inv(config['longitude'],config['latitude'],q['lon'],q['lat'])[2]
     layers[kind]={'status':'SUCCEEDED','request_binding':binding,'rows':[{'store_id':kind,'store_name':'SYNTHETIC '+kind,'latitude':q['lat'],'longitude':q['lon'],'distance_m':dist}]}
    result=build_market(config,market,pilot,layers,facilities,root/'market')
    print('SYNTHETIC MARKET:',result['summary'],'GATE',result['attractor_gate']['state'])
    assert result['summary']['rows']==3 and result['summary']['assigned']==3
    assert result['attractor_gate']['state']=='OPEN'
    with patch('location_intelligent_li3_graph.build_graph',side_effect=AssertionError('Reopen must not rebuild')):
     assert result==build_market(config,market,pilot,layers,facilities,root/'market')
    html=render_market(config,market,pilot,facilities,result)
    assert html==render_market(config,market,pilot,facilities,result)
    print('PASS immutable result and presentation reopen:',html)
    print('ROOT',root)

if __name__ == '__main__':
    main()
