"""Offline OSM transport failures/recovery; these are not live Kaggle results."""
import io,json,tempfile,unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from location_intelligent_gpu_sources import RoadTransport,OsmAcquisitionError,explain_source_failure
from location_intelligent_li3_sources import read_json,write_json

STAMP='2026-10-24T00:00:00Z'


def queries(box,policy):
    w,s,e,n=box
    return {'roads':f'[out:json];(way["highway"]({s},{w},{n},{e}););(._;>;);out meta;',
            'features':'[out:json];features;'}


def ok(version=1):return {'status':'SUCCEEDED','payload':{'osm3s':{'timestamp_osm_base':STAMP},
    'elements':[{'type':'node','id':1,'version':version,'lon':106.8,'lat':-6.2}]},'attempts':[]}


def fail(code=502):return {'status':'RETRIEVAL_FAILED','payload':None,
    'attempts':[{'endpoint':'https://example.invalid/api/interpreter','http_status':code,'status':'HTTP_ERROR'}]}


class RoadTransportTests(unittest.TestCase):
    def transport(self,root,fetch,**kw):
        return RoadTransport(root,{'policy':{}},queries((0,0,4,4),{}),queries,fetch,sleep=lambda _:None,**kw)

    def test_502_subdivides_same_extent_and_pins_all_remaining_children(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'network';calls=[]
            def fetch(query,*a):
                calls.append(query);return fail() if len(calls)==1 else ok()
            transport=self.transport(root,fetch);q=queries((0,0,2,2),{})['roads'];r=transport(q,[],45,100000)
            self.assertEqual(r['status'],'SUCCEEDED');self.assertEqual(len(calls),5)
            self.assertEqual(len(r['payload']['elements']),1)
            self.assertTrue(all(f'[date:"{STAMP}"]' in q for q in calls[2:]))
            expected=[(0.,0.,1.,1.),(1.,0.,2.,1.),(0.,1.,1.,2.),(1.,1.,2.,2.)]
            self.assertEqual([queries(box,{})['roads'].replace(';',f'[date:"{STAMP}"];',1) for box in expected[1:]],calls[2:])
            with patch.object(transport,'fetch',side_effect=AssertionError('No refetch')):self.assertEqual(transport(q,[],45,100000),r)
            leaf=root/next(iter(r['subtile_sha256']));leaf.write_bytes(b'CORRUPT')
            with self.assertRaisesRegex(OsmAcquisitionError,'CHECKSUM'):transport(q,[],45,100000)

    def test_resume_retains_successful_children_and_does_not_retry_parent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'network';calls=[]
            def fetch(query,*a):
                calls.append(query)
                return fail() if len(calls)==1 else ok() if len(calls)==2 else fail(503)
            transport=self.transport(root,fetch,retries=0);q=queries((0,0,2,2),{})['roads']
            with self.assertRaisesRegex(OsmAcquisitionError,'UNAVAILABLE'):transport(q,[],45,100000)
            retained={p:p.read_bytes() for p in root.rglob('*.json.gz') if read_json(p)['status']=='SUCCEEDED'}
            later=[]
            def recovered(query,*a):later.append(query);return ok()
            result=self.transport(root,recovered)(q,[],45,100000)
            self.assertEqual(result['status'],'SUCCEEDED');self.assertEqual(len(later),3)
            self.assertNotIn(q,later);self.assertNotIn(calls[1],later)
            for path,data in retained.items():self.assertEqual(path.read_bytes(),data)

    def test_retry_503_is_bounded_and_never_fabricates_success(self):
        with tempfile.TemporaryDirectory() as d:
            calls=[]
            def fetch(*a):calls.append(a);return fail(503)
            t=self.transport(Path(d)/'network',fetch)
            with self.assertRaisesRegex(OsmAcquisitionError,'UNAVAILABLE'):t(queries((0,0,2,2),{})['roads'],[],45,100000)
            self.assertEqual(len(calls),2);self.assertEqual(read_json(t.journal)['status'],'UNAVAILABLE')

    def test_503_recovers_on_single_retry(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('time.sleep'):
                fetch=unittest.mock.Mock(side_effect=[fail(503),ok()]);t=self.transport(Path(d)/'network',fetch)
                self.assertEqual(t(queries((0,0,2,2),{})['roads'],[],45,100000)['status'],'SUCCEEDED')
                self.assertEqual(fetch.call_count,2)

    def test_permanent_403_not_retried_or_subdivided(self):
        with tempfile.TemporaryDirectory() as d:
            fetch=unittest.mock.Mock(return_value=fail(403));t=self.transport(Path(d)/'network',fetch)
            with self.assertRaisesRegex(OsmAcquisitionError,'UNAVAILABLE'):t(queries((0,0,2,2),{})['roads'],[],45,100000)
            self.assertEqual(fetch.call_count,1)

    def test_budget_stops_and_retains_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            t=self.transport(Path(d)/'network',lambda *a:fail(),max_calls=1)
            with self.assertRaisesRegex(OsmAcquisitionError,'BUDGET'):t(queries((0,0,2,2),{})['roads'],[],45,100000)
            self.assertEqual(read_json(t.journal)['status'],'PAUSED')
            self.assertEqual(len(list((Path(d)/'network/raw/adaptive_roads').glob('*.split.json'))),1)

    def test_version_conflict_never_accepted_as_success(self):
        with tempfile.TemporaryDirectory() as d:
            fetch=unittest.mock.Mock(side_effect=[fail(),ok(1),ok(2),ok(1),ok(1)])
            t=self.transport(Path(d)/'network',fetch)
            with self.assertRaisesRegex(ValueError,'conflict'):t(queries((0,0,2,2),{})['roads'],[],45,100000)

    def test_nested_subdivision_keeps_shared_snapshot_and_all_leaf_checksums(self):
        with tempfile.TemporaryDirectory() as d:
            fetch=unittest.mock.Mock(side_effect=[fail(),fail()]+[ok() for _ in range(7)])
            t=self.transport(Path(d)/'network',fetch);q=queries((0,0,2,2),{})['roads']
            result=t(q,[],45,100000)
            self.assertEqual(result['status'],'SUCCEEDED');self.assertEqual(len(result['subtile_sha256']),8)
            self.assertEqual(result['requested_snapshot_as_of'],STAMP)
            with patch.object(t,'fetch',side_effect=AssertionError('No refetch')):self.assertEqual(t(q,[],45,100000),result)

    def test_wrapper_restores_canonical_hook_after_error(self):
        from location_intelligent_gpu_sources import acquire_market_network_gpu
        import location_intelligent_network_acquisition as module
        original=module.acquire_network_sources
        with patch('location_intelligent_market_runtime.acquire_market_network',side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):acquire_market_network_gpu({},Path('/unused'))
        self.assertIs(module.acquire_network_sources,original)

    def test_canonical_partial_network_resumes_and_keeps_original_tile_bytes(self):
        from location_intelligent_gpu_sources import acquire_market_network_gpu
        config={'latitude':-6.19,'longitude':106.83,'metric_crs':'EPSG:32748','network_radius_m':3000.,
                'network_feature_mode':'ROADS_ONLY_EXPERIMENT','poi_overpass_endpoints':['https://example.invalid']}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'network'
            # Inject a no-op delay, keeping real orchestration/cache behavior.
            class NoDelay(RoadTransport):
                def __init__(self,*a,**kw):super().__init__(*a,sleep=lambda _:None,**kw)
            with patch('location_intelligent_gpu_sources.RoadTransport',NoDelay),patch(
                'location_intelligent_li3_sources.build_queries',side_effect=queries),patch(
                'location_intelligent_li3_sources.acquire_overpass',side_effect=[fail(),ok(),fail(503),fail(503)]):
                with self.assertRaisesRegex(OsmAcquisitionError,'UNAVAILABLE'):acquire_market_network_gpu(config,root)
            retained=(root/'raw/osm_roads_tile_0.json.gz').read_bytes()
            self.assertFalse((root/'network_manifest.json').exists())
            with patch('location_intelligent_li3_sources.build_queries',side_effect=queries),patch(
                'location_intelligent_li3_sources.acquire_overpass',side_effect=lambda *a:ok()) as fetch:
                acquire_market_network_gpu(config,root)
                self.assertEqual(fetch.call_count,3)
                self.assertTrue(all(f'[date:"{STAMP}"]' in call.args[0] for call in fetch.call_args_list))
            self.assertEqual(retained,(root/'raw/osm_roads_tile_0.json.gz').read_bytes())
            self.assertTrue((root/'network_manifest.json').exists())
            with patch('location_intelligent_li3_sources.build_queries',side_effect=queries),patch(
                'location_intelligent_li3_sources.acquire_overpass',side_effect=AssertionError('No refetch')):
                acquire_market_network_gpu(config,root)

    def test_diagnostic_shows_endpoint_status_without_generic_secret_message(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);network=root/'network';stages={'sources':{'status':'FAILED'}}
            write_json(root/'readiness.json',{'candidate_buildings':None,'stages':stages,'status':'NOT_READY'})
            write_json(network/'acquisition_status.json',{'status':'BLOCKED_SOURCE_UNAVAILABLE','failed_tile':2,'attempts':fail()['attempts']})
            log=io.StringIO()
            with redirect_stdout(log):explain_source_failure(RuntimeError('PRIVATE_VALUE'),network,stages,root/'readiness.json')
            self.assertIn('502',log.getvalue());self.assertNotIn('PRIVATE_VALUE',log.getvalue())
            self.assertIsNone(read_json(root/'readiness.json')['candidate_buildings'])

    def test_corrupt_diagnostic_cannot_mask_original_source_error(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);network=root/'network';network.mkdir()
            (network/'acquisition_status.json').write_text('BROKEN_JSON')
            log=io.StringIO();stages={'sources':{'status':'FAILED'}}
            with redirect_stdout(log):explain_source_failure(OsmAcquisitionError('OSM_ROAD_TILE_UNAVAILABLE'),network,stages,root/'absent.json')
            self.assertIn('OSM_ROAD_TILE_UNAVAILABLE',log.getvalue())
            self.assertIn('unreadable',log.getvalue())


class SourceCellTests(unittest.TestCase):
    def test_actual_gpu_cell_reports_source_failure_and_blocks_gpu_calculation(self):
        root_code=Path(__file__).parent
        notebook=json.loads((root_code/'area_coverage_market_gpu_2km.ipynb').read_text())
        sources=next(''.join(c['source']) for c in notebook['cells'] if "if begin_notebook_stage('sources'" in ''.join(c['source']))
        calculation=next(''.join(c['source']) for c in notebook['cells'] if "if begin_notebook_stage('calculation'" in ''.join(c['source']))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env={};exec((root_code/'location_intelligent_notebook_runtime.py').read_text(),env)
            env.update(Path=Path,GOOGLE_SESSION=object(),GCS_RUNTIME_ROOT=root/'runtime',SOURCES=root/'sources',
                NETWORK_FOLDER=root/'sources/network_roads_only',CONFIG={},NOTEBOOK_REPORT_PATH=root/'ready.json')
            env['STAGES']['configuration']={'status':'SUCCEEDED'}
            with patch('importlib.reload',side_effect=lambda m:m),patch(
                'location_intelligent_google_only.stage',side_effect=RuntimeError('GCS_INPUT_HASH_MISMATCH')):
                exec(sources,env)
            with patch('location_intelligent_gpu_runtime.build_gpu',side_effect=AssertionError('No GPU without roads')):
                exec(calculation,env)
            report=read_json(root/'ready.json')
            self.assertEqual(report['stages']['sources']['error_code'],'GCS_INPUT_HASH_MISMATCH')
            self.assertEqual(report['stages']['calculation']['status'],'BLOCKED')
            self.assertIsNone(report['candidate_buildings'])
            self.assertIsNone(env['MARKET'])


if __name__=='__main__':unittest.main()
