"""Synthetic policy/regression tests; never actual market or access evidence."""
import math
import tempfile
import unittest
import json
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from location_intelligent_market_config import get_market_config, require_market_decisions
from location_intelligent_market import (corridor_tokens,classify_store,huff,allocate_building,
                                         restaurant_cluster,reconcile)
from location_intelligent_buildings import selection_reason
from location_intelligent_map_poi import classify_poi,build_poi_query,poi_binding


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.policy=get_market_config()['allocation_requirements']
        self.candidate=classify_store({'store_key':'candidate','kind':'candidate','distance_to_candidate_m':0},[],self.policy)
        self.comp=classify_store({'store_key':'comp','kind':'competitor','distance_to_candidate_m':200,'corridor_tokens':['name:jalan a']},['name:jalan a'],self.policy)
    def building(self,distance=200):
        return {'building_id':'SYNTHETIC','area_m2':60,'residential':True,'access_status':'ACCEPTED',
                'distance_to_candidate_m':distance,'store_distances_m':{'candidate':distance,'comp':150}}
    def run_case(self,b=None,stores=None,routes=None,gate=None,complete=True):
        return allocate_building(b or self.building(),stores or [self.candidate,self.comp],
          routes or {'candidate':{'total_distance_m':100},'comp':{'total_distance_m':200}},
          gate or {'state':'OPEN'},self.policy,inputs_complete=complete)
    def test_huff_80_20_whole_house(self):
        row=self.run_case();self.assertEqual(row['count_candidate'],1)
        self.assertEqual(row['scores'][0]['huff_score'],.8)
        self.assertEqual(row['scores'][1]['huff_score'],.2)
        self.assertEqual(reconcile([row])['candidate_whole_buildings'],1)
    def test_no_huff_draw_reordering_is_identical(self):
        a=[{'store_key':'a','total_distance_m':100},{'store_key':'b','total_distance_m':100}]
        self.assertEqual(huff(a),huff(a[::-1]));self.assertEqual(huff(a)[0]['store_key'],'a')
    def test_zero_and_invalid_distance(self):
        a=huff([{'store_key':'a','total_distance_m':0},{'store_key':'b','total_distance_m':100}])
        self.assertEqual(a[0]['huff_score'],1)
        with self.assertRaises(ValueError):huff([{'store_key':'a','total_distance_m':math.nan}])
    def test_candidate_wins_100m_overlap_not_whole_other_core(self):
        comp={**self.comp,'distance_to_candidate_m':90}
        b=self.building(80);b['store_distances_m']['comp']=30
        row=self.run_case(b,[self.candidate,comp]);self.assertEqual(row['count_candidate'],1)
        b=self.building(140);b['store_distances_m']['comp']=50
        self.assertEqual(self.run_case(b,[self.candidate,comp])['winner_store_key'],'comp')
    def test_indomaret_bands_and_outside_core_influence(self):
        for d,core in [(399.99,0),(400,100),(799.99,100),(800,0),(1500,0)]:
            s=classify_store({'store_key':'indo','kind':'indomaret','distance_to_candidate_m':d},[],self.policy)
            self.assertEqual(s['core_m'],core)
        s=classify_store({'store_key':'indo','kind':'indomaret','distance_to_candidate_m':900},[],self.policy)
        b=self.building(600);b['store_distances_m']['indo']=150
        r=self.run_case(b,[self.candidate,s],{'candidate':{'total_distance_m':600},'indo':{'total_distance_m':150}})
        self.assertEqual(r['winner_store_key'],'indo')
    def test_inner_zone_competition_only_outside_cores(self):
        s=classify_store({'store_key':'indo','kind':'indomaret','distance_to_candidate_m':300},[],self.policy)
        r=self.run_case(self.building(),[self.candidate,s],{'candidate':{'total_distance_m':300},'indo':{'total_distance_m':1}})
        self.assertEqual(r['winner_store_key'],'candidate');self.assertEqual(len(r['scores']),1)
    def test_unreachable_competitor_gets_no_score(self):
        r=self.run_case(routes={'candidate':{'total_distance_m':100}})
        self.assertEqual(len(r['scores']),1)
    def test_no_route_unknown_or_overtime_cannot_win_by_core(self):
        for status in ['NO_ROUTE','ACCESS_UNVERIFIED','OVER_TIME_LIMIT']:
            b=self.building(20);b['access_status']=status
            r=self.run_case(b);self.assertIsNone(r['winner_store_key'])
    def test_outer_gate_unknown_closed_and_open(self):
        for state in ['UNKNOWN','CLOSED']:
            r=self.run_case(self.building(900),gate={'state':state})
            self.assertIsNone(r['winner_store_key']);self.assertIn(state,r['reason'])
        self.assertIsNotNone(self.run_case(self.building(900),gate={'state':'OPEN'})['winner_store_key'])
    def test_unknown_bq_not_false_unopposed(self):
        self.assertEqual(self.run_case(complete=False)['market_status'],'UNVERIFIED')
    def test_minimum36_boundary_keeps_legacy_strict_rule(self):
        self.assertEqual(selection_reason(0,36,'standard_residential',radius=2000,minimum=36,maximum=550),'AREA_NOT_ABOVE_MIN')
        self.assertIsNone(selection_reason(0,36,'standard_residential',radius=2000,minimum=36,maximum=550,minimum_inclusive=True))
        self.assertEqual(selection_reason(0,35.99,'standard_residential',radius=2000,minimum=36,maximum=550,minimum_inclusive=True),'AREA_BELOW_MIN')
        b=self.building();b['area_m2']=550;self.assertIsNone(self.run_case(b)['winner_store_key'])
    def test_primary_same_corridor_both_sides_but_no_fuzzy_unnamed(self):
        tokens=corridor_tokens({'name':'Jl. A'})
        self.assertEqual(tokens,['name:jalan a'])
        for k in ['north','south']:
            s=classify_store({'store_key':k,'kind':'competitor','distance_to_candidate_m':799,'corridor_tokens':tokens},tokens,self.policy)
            self.assertEqual(s['tier'],'PRIMARY')
        s=classify_store({'kind':'competitor','distance_to_candidate_m':20},tokens,self.policy)
        self.assertEqual(s['tier'],'UNVERIFIED_CORRIDOR')
    def test_five_distinct_restaurants_pairwise_not_chain(self):
        def sites(xs):return [{'source_id':str(i),'building_id':str(i),'xy':[x,0],'corridor_tokens':['name:jalan a']} for i,x in enumerate(xs)]
        self.assertIsNotNone(restaurant_cluster(sites([0,50,100,150,200])))
        self.assertIsNone(restaurant_cluster(sites([0,100,200,300,400])))
        self.assertIsNone(restaurant_cluster(sites([0,10,20,30])))
        a=sites([0,10,20,30,40]);a[-1]['building_id']=a[0]['building_id'];self.assertIsNone(restaurant_cluster(a))
    def test_poi_expansion_is_optin_legacy_cache_identity_preserved(self):
        base={'latitude':-6.19,'longitude':106.83,'poi_radius_m':2000}
        market={**base,'poi_profile':'market_attractors_v2'}
        for tag,category in [({'railway':'station'},'station'),({'leisure':'park'},'recreation'),({'amenity':'bank'},'bank'),({'amenity':'restaurant'},'restaurant'),({'shop':'mall'},'mall')]:
            self.assertEqual(classify_poi(tag,market=True),category);self.assertIsNone(classify_poi(tag))
        self.assertNotEqual(poi_binding(base),poi_binding(market));self.assertIn('restaurant',build_poi_query(market))
    def test_config_copy_and_unresolved_guard(self):
        a=get_market_config();require_market_decisions(a);a['open_decisions']['x']=None
        with self.assertRaises(ValueError):require_market_decisions(a)
        self.assertEqual(get_market_config()['open_decisions'],{})
    def test_network_tile_fallback_all_or_nothing_and_no_refetch(self):
        from location_intelligent_market_runtime import acquire_market_network
        from location_intelligent_li3_sources import read_json
        cfg={'latitude':-6.190690620514923,'longitude':106.83819549844226,
             'metric_crs':'EPSG:32748','network_radius_m':5500.,'poi_overpass_endpoints':['https://example.invalid']}
        success={'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':'2026-10-24T00:00:00Z'},'elements':[]}}
        fail={'status':'RETRIEVAL_FAILED','attempts':[{'http_status':502}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'network'
            with patch('location_intelligent_li3_sources.build_queries',return_value={'roads':'[out:json];roads;','features':'[out:json];features;'}),patch('location_intelligent_li3_sources.acquire_overpass',side_effect=[success,fail,*[deepcopy(success) for _ in range(4)]]) as fetch:
                acquire_market_network(cfg,p);self.assertEqual(fetch.call_count,6)
            self.assertEqual(read_json(p/'raw/osm_features_pinned.json.gz')['status'],'SUCCEEDED')
            history=list((p/'raw/attempt_history').glob('*.gz'))
            self.assertTrue(any(read_json(f)['status']=='RETRIEVAL_FAILED' for f in history))
            with patch('location_intelligent_li3_sources.acquire_overpass',side_effect=AssertionError('No re-fetch')):
                acquire_market_network(cfg,p)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'network'
            with patch('location_intelligent_li3_sources.build_queries',return_value={'roads':'[out:json];roads;','features':'[out:json];features;'}),patch('location_intelligent_li3_sources.acquire_overpass',side_effect=[success,fail,fail,fail]):
                with self.assertRaisesRegex(RuntimeError,'feature category node_barriers unavailable'):acquire_market_network(cfg,p)
            self.assertFalse((p/'network_manifest.json').exists())
    def test_failed_roads_resume_only_missing_tiles_and_preserve_snapshot(self):
        from location_intelligent_market_runtime import acquire_market_network
        from location_intelligent_li3_sources import read_json
        cfg={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748',
             'network_radius_m':5500.,'poi_overpass_endpoints':['https://example.invalid']}
        ok={'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':'2026-10-24T00:00:00Z'},'elements':[]}}
        fail={'status':'RETRIEVAL_FAILED','attempts':[{'http_status':429}]}
        queries={'roads':'[out:json];roads;','features':'[out:json];features;'}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'network'
            with patch('location_intelligent_li3_sources.build_queries',return_value=queries),patch('location_intelligent_li3_sources.acquire_overpass',side_effect=[fail,deepcopy(ok),fail]):
                with self.assertRaisesRegex(RuntimeError,'roads tile 2/4 unavailable'):acquire_market_network(cfg,root)
            first=(root/'raw/osm_roads_tile_0.json.gz').read_bytes()
            self.assertFalse((root/'network_manifest.json').exists())
            with patch('location_intelligent_li3_sources.build_queries',return_value=queries),patch('location_intelligent_li3_sources.acquire_overpass',side_effect=[deepcopy(ok) for _ in range(4)]) as fetch:
                acquire_market_network(cfg,root)
                self.assertEqual(fetch.call_count,4) # Three missing road tiles + features.
                for call in fetch.call_args_list:self.assertIn('[date:"2026-10-24T00:00:00Z"]',call.args[0])
            self.assertEqual(first,(root/'raw/osm_roads_tile_0.json.gz').read_bytes())
            self.assertEqual(read_json(root/'acquisition_status.json')['status'],'SUCCEEDED')
            with patch('location_intelligent_li3_sources.acquire_overpass',side_effect=AssertionError('No refetch')):
                acquire_market_network(cfg,root)
            (root/'raw/osm_roads_tile_0.json.gz').write_bytes(b'CORRUPT')
            with self.assertRaisesRegex(ValueError,'corrupted'):acquire_market_network(cfg,root)
    def test_permanent_http_rejection_does_not_retry_as_tiles(self):
        from location_intelligent_market_runtime import acquire_market_network
        cfg={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748',
             'network_radius_m':5500.,'poi_overpass_endpoints':['https://example.invalid']}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'network'
            with patch('location_intelligent_li3_sources.build_queries',return_value={'roads':'[out:json];r;','features':'[out:json];f;'}),patch('location_intelligent_li3_sources.acquire_overpass',return_value={'status':'RETRIEVAL_FAILED','attempts':[{'http_status':403}]}) as fetch:
                with self.assertRaisesRegex(RuntimeError,'request rejected'):acquire_market_network(cfg,root)
                self.assertEqual(fetch.call_count,1)
            self.assertFalse((root/'network_manifest.json').exists())
    def test_feature_categories_resume_without_repeating_union_or_success(self):
        from location_intelligent_market_runtime import acquire_market_network
        cfg={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748',
             'network_radius_m':5500.,'poi_overpass_endpoints':['https://example.invalid']}
        ok={'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':'2026-10-24T00:00:00Z'},'elements':[]}}
        fail={'status':'RETRIEVAL_FAILED','attempts':[{'http_status':502}]}
        queries={'roads':'[out:json];roads;','features':'[out:json];features;'}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'network'
            with patch('location_intelligent_li3_sources.build_queries',return_value=queries),patch('location_intelligent_li3_sources.acquire_overpass',side_effect=[ok,fail,fail,ok,fail]):
                with self.assertRaisesRegex(RuntimeError,'feature category way_barriers unavailable'):acquire_market_network(cfg,root)
            node=root/'raw/feature_parts/0/node_barriers.json.gz';saved=node.read_bytes()
            with patch('location_intelligent_li3_sources.build_queries',return_value=queries),patch('location_intelligent_li3_sources.acquire_overpass',return_value=ok) as fetch:
                acquire_market_network(cfg,root)
                self.assertEqual(fetch.call_count,8)
                self.assertTrue(all('node["barrier"]' not in c.args[0] for c in fetch.call_args_list))
            self.assertEqual(saved,node.read_bytes())
    def test_server_resource_remark_subdivides_only_failed_category(self):
        from location_intelligent_market_runtime import acquire_market_network
        cfg={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748',
             'network_radius_m':5500.,'poi_overpass_endpoints':['https://example.invalid']}
        ok={'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':'2026-10-24T00:00:00Z'},'elements':[]}}
        fail={'status':'RETRIEVAL_FAILED','attempts':[{'http_status':502}]}
        timedout={'status':'RETRIEVAL_FAILED','attempts':[{'http_status':200,'status':'PARTIAL_OR_INVALID','remark':'runtime error: Query timed out'}]}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'network'
            replies=[ok,fail,fail,timedout,*[deepcopy(ok) for _ in range(12)]]
            with patch('location_intelligent_li3_sources.build_queries',return_value={'roads':'[out:json];roads;','features':'[out:json];features;'}),patch('location_intelligent_li3_sources.acquire_overpass',side_effect=replies) as fetch:
                acquire_market_network(cfg,root)
                self.assertEqual(sum('node["barrier"]' in c.args[0] for c in fetch.call_args_list),5)
            self.assertTrue((root/'network_manifest.json').exists())
    def test_feature_parts_preserve_original_six_selectors_and_snapshot(self):
        from location_intelligent_network_acquisition import feature_part_queries
        from location_intelligent_config import get_config
        parts=feature_part_queries((1,2,3,4),get_config(),'2026-10-24T00:00:00Z')
        self.assertEqual(len(parts),6)
        for selector in ['node["barrier"]','way["barrier"]','way["waterway"]','way["natural"="water"]','relation["natural"="water"]','relation["type"="restriction"]']:
            self.assertTrue(any(selector in q for q in parts.values()))
        self.assertTrue(all('[date:"2026-10-24T00:00:00Z"]' in q for q in parts.values()))
    def test_http200_with_server_remark_is_not_source_success(self):
        from types import SimpleNamespace
        from location_intelligent_li3_sources import acquire_overpass
        payload=json.dumps({'elements':[],'osm3s':{},'remark':'runtime error: Query timed out'}).encode()
        response=SimpleNamespace(status_code=200,iter_content=lambda n:iter([payload]),close=lambda:None)
        session=SimpleNamespace(post=lambda *a,**kw:response)
        result=acquire_overpass('QUERY',['https://example.invalid'],20,10000,session=session)
        self.assertEqual(result['status'],'RETRIEVAL_FAILED')
        self.assertEqual(result['attempts'][0]['failure_reason'],'OVERPASS_REMARK')
        self.assertIn('Query timed out',result['attempts'][0]['remark'])
    def test_road_only_reuses_existing_roads_and_makes_no_feature_requests(self):
        from location_intelligent_market_runtime import acquire_market_network
        from location_intelligent_li3_sources import read_json
        cfg={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748',
             'network_radius_m':5500.,'poi_overpass_endpoints':['https://example.invalid']}
        ok={'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':'2026-10-24T00:00:00Z'},'elements':[]}}
        fail={'status':'RETRIEVAL_FAILED','attempts':[{'http_status':502}]}
        q={'roads':'[out:json];roads;','features':'[out:json];features;'}
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/'network'
            with patch('location_intelligent_li3_sources.build_queries',return_value=q),patch('location_intelligent_li3_sources.acquire_overpass',side_effect=[ok,fail,fail,fail]):
                with self.assertRaises(RuntimeError):acquire_market_network(cfg,old)
            saved=(old/'raw/osm_roads.json.gz').read_bytes()
            new=Path(d)/'network_roads_only'
            with patch('location_intelligent_li3_sources.build_queries',return_value=q),patch('location_intelligent_li3_sources.acquire_overpass',side_effect=AssertionError('No external calls; roads cached')):
                acquire_market_network({**cfg,'network_feature_mode':'ROADS_ONLY_EXPERIMENT'},new)
            derived=read_json(new/'raw/osm_features_roads_only.json.gz')
            self.assertFalse(derived['restrictions_complete']);self.assertFalse(derived['external_features_requested'])
            self.assertEqual(saved,(old/'raw/osm_roads.json.gz').read_bytes())
            self.assertTrue((new/'network_manifest.json').exists())
    def test_optional_poi_failure_is_frozen_unknown_not_zero_or_refetch(self):
        from location_intelligent_map_poi import load_optional_osm_pois
        cfg={'latitude':-6.19,'longitude':106.83,'poi_radius_m':2000,
             'poi_profile':'market_attractors_v2','poi_overpass_endpoints':['https://example.invalid']}
        with tempfile.TemporaryDirectory() as d:
            with patch('location_intelligent_map_poi.acquire_overpass',return_value={'status':'RETRIEVAL_FAILED','attempts':[{'http_status':502}]}):
                result=load_optional_osm_pois(cfg,d)
            self.assertEqual(result['status'],'FAILED');self.assertIsNone(result['count']);self.assertIsNone(result['rows'])
            with patch('location_intelligent_map_poi.acquire_overpass',side_effect=AssertionError('Frozen unavailability; no refetch')):
                self.assertEqual(result,load_optional_osm_pois(cfg,d,mode='FROZEN'))
    def test_optional_poi_success_retains_real_inventory_for_reopen(self):
        from location_intelligent_map_poi import load_optional_osm_pois
        cfg={'latitude':-6.19,'longitude':106.83,'poi_radius_m':2000,
             'poi_profile':'market_attractors_v2','poi_overpass_endpoints':['https://example.invalid']}
        payload={'osm3s':{'timestamp_osm_base':'2026-10-25T00:00:00Z'},'elements':[
            {'type':'node','id':1,'lat':-6.19,'lon':106.83,'tags':{'amenity':'hospital'}}]}
        with tempfile.TemporaryDirectory() as d:
            with patch('location_intelligent_map_poi.acquire_overpass',return_value={'status':'SUCCEEDED','payload':payload,'attempts':[]}):
                result=load_optional_osm_pois(cfg,d)
            self.assertEqual(result['count'],1)
            with patch('location_intelligent_map_poi.acquire_overpass',side_effect=AssertionError('No re-fetch')):
                self.assertEqual(result,load_optional_osm_pois(cfg,d,mode='FROZEN'))
    def test_optional_input_failure_and_business_gate_are_separate(self):
        from location_intelligent_market_runtime import _poi_gate
        unavailable={'status':'FAILED','rows':None,'count':None}
        gate=_poi_gate({},self.policy,unavailable,{},[],{})
        self.assertEqual(gate['state'],'UNKNOWN')
        self.assertEqual(self.run_case(gate=gate)['count_candidate'],1)
        outer=self.run_case(self.building(900),gate=gate)
        self.assertEqual(outer['market_status'],'UNVERIFIED');self.assertIsNone(outer['winner_store_key'])
        p={**self.policy,'outer_zone_requires_attractor':False}
        self.assertEqual(_poi_gate({},p,unavailable,{},[],{})['state'],'OPEN')
    def test_main_notebook_has_optional_poi_and_3km_network(self):
        n=json.loads(Path(__file__).with_name('area_coverage_market_cpu_2km.ipynb').read_text())
        cell=next(''.join(c['source']) for c in n['cells'] if 'load_optional_osm_pois=poi_runtime.' in ''.join(c['source']))
        self.assertNotIn("assert facilities['status']",cell)
        self.assertIn("load_optional_osm_pois(CONFIG,SOURCES,mode='FROZEN')",cell)
        self.assertEqual(get_market_config()['sources']['network_radius_m'],3000)
    def test_notebook_export_failure_retry_reopen_and_private_bq_included(self):
        import zipfile
        from location_intelligent_map_pilot import sha
        from location_intelligent_li3_sources import read_json,write_json
        n=json.loads(Path(__file__).with_name('area_coverage_market_cpu_2km.ipynb').read_text())
        source=''.join(n['cells'][-1]['source']).split('# Keep the complete packet',1)[1]
        source=source[source.index('archive='):].split("  finish_notebook_stage('output'",1)[0]
        import textwrap
        source=textwrap.dedent('  '+source)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for folder in ['sources','pilot','bq_snapshot','market','code/notebooks','output']:
                (root/folder).mkdir(parents=True)
            (root/'sources/source.json').write_text('{}')
            (root/'bq_snapshot/competitor.json').write_text('{"SYNTHETIC":true}')
            (root/'code/notebooks/f.py').write_text('# SYNTHETIC')
            env={'OUTPUT':root/'output','SOURCES':root/'sources','PILOT':root/'pilot',
                 'BQ_CACHE':root/'bq_snapshot','MARKET':{'output_path':str(root/'market')},
                 'SOURCE_ROOT':root/'code','CONFIG':{},'MARKET_CONFIG':{},
                 'sha':sha,'read_json':read_json,'write_json':write_json,'json':json,'Path':Path,
                 'display':lambda *a:None,'FileLink':lambda p:p}
            with patch('zipfile.ZipFile.write',side_effect=OSError('SYNTHETIC export failure')):
                with self.assertRaises(OSError):exec(source,env)
            self.assertFalse((root/'output/archive_manifest.json').exists())
            exec(source,env)
            archive=root/'output/market_result_and_sources.zip'
            with zipfile.ZipFile(archive) as z:
                self.assertIn('bq_snapshot/competitor.json',z.namelist());self.assertIsNone(z.testzip())
            with patch('zipfile.ZipFile.write',side_effect=AssertionError('No rewrite on reopen')):
                exec(source,env)
            archive.write_bytes(b'CORRUPT')
            with self.assertRaisesRegex(AssertionError,'Saved export archive changed'):exec(source,env)
    def test_visible_notebook_sources_and_packet_match(self):
        root=Path(__file__).resolve().parents[1]
        p=root/'notebooks/area_coverage_market_cpu_2km.ipynb'
        self.assertEqual(p.read_bytes(),(root/'results/area_coverage_map/kaggle_packet'/p.name).read_bytes())
        for c in json.loads(p.read_text())['cells']:
            s=''.join(c['source'])
            if not s.startswith('%%writefile '):continue
            header,body=s.split('\n',1);name=header.rsplit('/',1)[1]
            local=(root/'notebooks'/name).read_text()
            if name=='location_intelligent_map_pilot.py':
                local=local.replace('    import google.auth\n',"    if globals().get('_NOTEBOOK_BQ_CREDENTIALS') is not None:return _NOTEBOOK_BQ_CREDENTIALS\n    import google.auth\n",1)
            self.assertEqual(body,local,name)
    def test_import_failure_leaves_no_network_directory(self):
        from location_intelligent_market_runtime import acquire_market_network
        cfg={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748',
             'network_radius_m':5500.,'poi_overpass_endpoints':[]}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'network'
            with patch('location_intelligent_li3_sources.build_queries',side_effect=AttributeError('numpy binary mismatch')):
                with self.assertRaises(AttributeError):acquire_market_network(cfg,root)
            self.assertFalse(root.exists())
    def test_numpy_dependency_cell_retains_loaded_versions_and_stops_stale_session(self):
        import ast
        from types import SimpleNamespace
        n=json.loads(Path(__file__).with_name('area_coverage_market_cpu_2km.ipynb').read_text())
        s=next(''.join(c['source']) for c in n['cells'] if '# Preserve the scientific stack' in ''.join(c['source']))
        # Exercise the exact pre-install guard without pip or heavy imports.
        import textwrap
        prefix=textwrap.dedent('  '+s[s.index('# Preserve the scientific stack'):s.index('packages=')])
        with patch('importlib.metadata.version',return_value='2.3.0'):
            with self.assertRaisesRegex(RuntimeError,'Restart Session'):
                exec(prefix,{'sys':SimpleNamespace(modules={'numpy':SimpleNamespace(__version__='2.2.0')})})
            env={'sys':SimpleNamespace(modules={'numpy':SimpleNamespace(__version__='2.3.0')})}
            exec(prefix,env);self.assertEqual(env['retained']['numpy'],'2.3.0')
        self.assertNotIn('numpy==2.5.4',s)
