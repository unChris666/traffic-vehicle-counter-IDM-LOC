"""Small real PBF fixture plus offline GCS/network tests; no national run claim."""
import hashlib,json,os,shutil,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from location_intelligent_google_only import stage,install_google_only_guard
from location_intelligent_pbf_sources import matches,materialize


class GoogleNetworkTests(unittest.TestCase):
    def test_preparation_notebook_contains_current_visible_script(self):
        root=Path(__file__).resolve().parents[1]
        notebook=json.loads((root/'notebooks/area_gcs_runtime_preparation.ipynb').read_text())
        self.assertEqual(''.join(notebook['cells'][-1]['source']),(root/'tools/prepare_area_gcs_runtime.py').read_text())
    def test_generated_execution_cells_have_no_provider_or_online_installs(self):
        notebook=json.loads(Path(__file__).with_name('area_coverage_market_gpu_2km.ipynb').read_text())
        execution='\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code' and not ''.join(c['source']).startswith('%%writefile'))
        for forbidden in ['apt-get','pip\',\'install','acquire_market_network(CONFIG','acquire_osm(CONFIG','from kaggle_secrets import UserSecretsClient']:
            self.assertNotIn(forbidden,execution)
        self.assertIn('GOOGLE_SESSION.credentials',execution)
        self.assertIn('google_only_render as render_market',execution)
    def test_external_and_redirects_blocked_google_allowed(self):
        import requests,urllib.request
        with patch.object(requests.sessions.Session,'request',return_value='GOOGLE') as send,patch.object(
            requests.sessions.Session,'send',return_value='SEND'),patch.object(urllib.request,'urlopen',return_value='URL'),patch.object(
            urllib.request.HTTPRedirectHandler,'redirect_request',return_value='REDIRECT'):
            install_google_only_guard();session=requests.Session()
            self.assertEqual(session.get('https://storage.googleapis.com/bucket'),'GOOGLE')
            self.assertEqual(session.get('https://bigquery.googleapis.com/query'),'GOOGLE')
            for url in ['https://overpass-api.de/api/interpreter','https://pypi.org/simple','https://storage.googleapis.com.evil.test/x','http://storage.googleapis.com/x']:
                with self.assertRaisesRegex(RuntimeError,'EXTERNAL_NETWORK_FORBIDDEN'):session.get(url)
            with self.assertRaisesRegex(RuntimeError,'EXTERNAL_NETWORK_FORBIDDEN'):
                session.send(requests.Request('GET','https://github.com').prepare())
            with self.assertRaisesRegex(RuntimeError,'EXTERNAL_NETWORK_FORBIDDEN'):
                urllib.request.HTTPRedirectHandler().redirect_request(None,None,302,None,{},'https://example.org')

    def test_generation_pinned_hash_verified_and_reopen_no_download(self):
        body=b'GCS fixture';ref={'object':'source.pbf','generation':123,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.iter_content.return_value=[body];session=Mock();session.get.return_value=response
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'input.pbf';stage(session,ref,path)
            self.assertEqual(session.get.call_args.kwargs['params']['generation'],'123')
            stage(session,ref,path);self.assertEqual(session.get.call_count,1)
            path.write_bytes(b'corrupt')
            with self.assertRaisesRegex(RuntimeError,'LOCAL_INPUT_HASH_MISMATCH'):stage(session,ref,path)

    def test_wrong_remote_bytes_never_finalize(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.iter_content.return_value=[b'bad'];session=Mock();session.get.return_value=response
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'input.pbf'
            with self.assertRaisesRegex(RuntimeError,'GCS_INPUT_HASH_MISMATCH'):
                stage(session,{'object':'bad','generation':1,'bytes':3,'sha256':'0'*64},path)
            self.assertFalse(path.exists())

    def test_frontend_inlining_is_cached_and_detects_tampering(self):
        from location_intelligent_google_only import google_only_render
        from location_intelligent_li3_sources import write_json
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);result={'output_path':str(root/'market')}
            write_json(root/'market/result.json',result)
            from location_intelligent_gcs_basemap import VECTORGRID_URL
            write_json(root/'frontend.json',{'https://cdn.example/test.js':'window.TEST=true;',
                'https://cdn.example/test.css':'body { color: black; }',VECTORGRID_URL:'window.GRID=true;'})
            def render(*args):
                path=args[-1];path.parent.mkdir(parents=True)
                path.write_text('<html><head></head><body><script src="https://cdn.example/test.js"></script><link href="https://cdn.example/test.css"></body></html>')
                write_json(path.with_suffix('.geojson'),{'type':'FeatureCollection','features':[]})
            config={'latitude':-6.19,'longitude':106.83,'building_radius_m':2000,'poi_radius_m':2000}
            ref={'maxzoom':14};kwargs={'session':object(),'basemap_ref':ref}
            with patch.dict(os.environ,{'LI_GCS_RUNTIME_ROOT':str(root)}),patch('location_intelligent_market_map.market_map',side_effect=render) as draw,patch(
                'location_intelligent_gcs_basemap.load_tiles',return_value=({}, {'scope':'STUB_ONLY'})):
                path=google_only_render(config, {},root,{},result,**kwargs)
                self.assertNotIn('src="https://',path.read_text());self.assertNotIn('<link',path.read_text())
                self.assertIn('window.TEST=true;',path.read_text())
                self.assertEqual(google_only_render(config, {},root,{},result,**kwargs),path);self.assertEqual(draw.call_count,1)
                path.write_text('CORRUPT')
                with self.assertRaisesRegex(RuntimeError,'GCS_PRESENTATION_CHANGED'):google_only_render(config, {},root,{},result,**kwargs)


class PbfTests(unittest.TestCase):
    def fixture(self,root):
        import osmium
        path=root/'fixture.osm.pbf';header=osmium.io.Header()
        header.set('osmosis_replication_timestamp','2026-10-24T20:21:00Z')
        header.add_box(osmium.osm.Box(osmium.osm.Location(106,-7),osmium.osm.Location(108,-5)))
        positions={1:(106.829,-6.19),2:(106.831,-6.19),3:(106.830,-6.19),
                   10:(106.8295,-6.1898),11:(106.8297,-6.1898),12:(106.8297,-6.1896),13:(106.8295,-6.1896),
                   20:(106.82955,-6.18975),21:(106.8296,-6.18975),22:(106.8296,-6.1897),23:(106.82955,-6.1897)}
        with osmium.SimpleWriter(str(path),header=header) as writer:
            for key,xy in positions.items():
                writer.add_node(osmium.osm.mutable.Node(id=key,location=xy,version=2,timestamp='2026-10-24T20:21:00Z',
                    tags={'amenity':'hospital','name':'Fixture hospital'} if key==3 else {}))
            for key,refs,tags in [(100,[1,2],{'highway':'residential','oneway':'yes'}),
                                  (200,[10,11,12,13,10],{}),(201,[20,21,22,23,20],{})]:
                writer.add_way(osmium.osm.mutable.Way(id=key,nodes=refs,tags=tags,version=3,timestamp='2026-10-24T20:21:00Z'))
            writer.add_relation(osmium.osm.mutable.Relation(id=300,members=[('w',200,'outer'),('w',201,'inner')],
                tags={'type':'multipolygon','building':'house'},version=1,timestamp='2026-10-24T20:21:00Z'))
        return path

    def test_filter_preserves_negative_tags_and_motor_supplements(self):
        rules=['["highway"]["area"!~"yes"]["highway"!~"^(footway|steps)$"]',
               '["highway"~"^(path|track)$"]["motorcycle"="yes"]']
        self.assertTrue(matches({'highway':'residential'},rules))
        self.assertFalse(matches({'highway':'footway'},rules))
        self.assertTrue(matches({'highway':'path','motorcycle':'yes'},rules))
        self.assertFalse(matches({'highway':'residential','area':'yes'},rules))

    def test_real_pbf_to_canonical_contract_holes_pois_direction_and_cache(self):
        from location_intelligent_market_runtime import verify_market_source_packet
        from location_intelligent_li3_sources import read_json
        from location_intelligent_li3_graph import build_graph
        from location_intelligent_map_poi import load_optional_osm_pois
        config={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748','network_radius_m':3000.,
            'building_radius_m':2000.,'building_query_padding_m':50.,'poi_radius_m':2000.,'poi_profile':'market_attractors_v2',
            'network_feature_mode':'ROADS_ONLY_EXPERIMENT','road_rule_profile':'BARRIER_ONEWAY_EXPERIMENT_V1'}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pbf=self.fixture(root);ref={'sha256':hashlib.sha256(pbf.read_bytes()).hexdigest()}
            def extract(command,**kw):
                self.assertEqual(command[command.index('--strategy')+1],'smart')
                shutil.copyfile(command[-1],command[command.index('--output')+1]);return SimpleNamespace(returncode=0)
            with patch('location_intelligent_pbf_sources.subprocess.run',side_effect=extract),patch(
                'location_intelligent_pbf_sources.__name__',__name__):
                materialize(config,root/'sources',pbf,'osmium',ref)
            verify_market_source_packet(root/'sources',config)
            raw=read_json(root/'sources/osm_buildings_raw.json.gz');building=raw['payload']['elements'][0]
            self.assertEqual(building['id'],300)
            self.assertEqual([m['role'] for m in building['members']],['outer','inner'])
            self.assertEqual(building['members'][1]['geometry'][0],{'lon':106.82955,'lat':-6.18975})
            pois=load_optional_osm_pois(config,root/'sources',mode='FROZEN');self.assertEqual(pois['count'],1)
            network=root/'sources/network_roads_only';frozen=read_json(network/'config/pilot.json')
            graph=build_graph(read_json(network/'raw/osm_roads.json.gz'),read_json(network/'raw/osm_features_roads_only.json.gz'),frozen)
            self.assertEqual(len(graph['graph']['edges']),1)
            self.assertEqual(graph['graph']['edges'][0]['u'],'n1')
            self.assertEqual(graph['graph']['edges'][0]['v'],'n2')
            with patch('location_intelligent_pbf_sources.subprocess.run',side_effect=AssertionError('No rescan')):
                materialize(config,root/'sources',pbf,'osmium',ref)
            (network/'raw/osm_roads.json.gz').write_bytes(b'CORRUPT')
            with self.assertRaisesRegex(ValueError,'SOURCE_SNAPSHOT_CHANGED'):
                materialize(config,root/'sources',pbf,'osmium',ref)

    def test_no_header_date_no_successful_source(self):
        import osmium
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'empty.osm.pbf'
            with osmium.SimpleWriter(str(path)):pass
            config={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748','network_radius_m':3000.,
                'building_radius_m':2000.,'building_query_padding_m':50.,'poi_radius_m':2000.,'network_feature_mode':'ROADS_ONLY_EXPERIMENT'}
            with self.assertRaisesRegex(RuntimeError,'PBF_HEADER_SNAPSHOT_TIMESTAMP_MISSING'):
                materialize(config,root/'sources',path,'unused',{'sha256':'test'})
            self.assertFalse((root/'sources/source_manifest.json').exists())


if __name__=='__main__':unittest.main()
