"""Data-only input contract. No previous calculation/market result is constructed."""
import json,tempfile,unittest
from pathlib import Path
from traffic_location.artifacts import write,sha
from traffic_location.location.area.sources.bundle import SourceBundle,create_source_bundle
from traffic_location.location.area._kernel.location_intelligent_market_config import get_market_config
from traffic_location.location.area._kernel.location_intelligent_market_scope import configure_scope

class SourceBundles(unittest.TestCase):
    def fixture(self,root):
        config={'CONFIG':{'latitude':-6.19,'longitude':106.83},'MARKET_CONFIG':configure_scope(get_market_config())}
        config['MARKET_CONFIG']['target'].update(latitude=-6.19,longitude=106.83)
        sources=root/'sources';bq=root/'bq';bq.mkdir()
        write(sources/'network_roads_only/raw/input.json',{'scope':'SYNTHETIC_INPUT_CONTRACT_FIXTURE'})
        network=sources/'network_roads_only'
        write(network/'config/pilot.json',{'scope':'SYNTHETIC_INPUT_CONTRACT_FIXTURE'})
        write(network/'raw/osm_roads.json.gz',{'scope':'SYNTHETIC_INPUT_CONTRACT_FIXTURE'})
        write(network/'raw/osm_features_roads_only.json.gz',{'scope':'SYNTHETIC_INPUT_CONTRACT_FIXTURE'})
        write(sources/'pbf_source.json',{'scope':'SYNTHETIC_INPUT_CONTRACT_FIXTURE'})
        write(sources/'osm_buildings_raw.json.gz',{'scope':'SYNTHETIC_INPUT_CONTRACT_FIXTURE'})
        write(sources/'optional_poi_result.json',{'scope':'SYNTHETIC_INPUT_CONTRACT_FIXTURE'})
        write(network/'network_manifest.json',{'files':{str(p.relative_to(network)):sha(p) for p in network.rglob('*') if p.is_file()}})
        write(sources/'source_manifest.json',{'config':config['CONFIG'],'files':{
            str(p.relative_to(sources)):sha(p) for p in sources.rglob('*') if p.is_file()}})
        for kind in ['competitor','indomaret']:
            write(bq/(kind+'.json'),{'status':'SUCCEEDED','rows':[],
                                   'request_binding':{'latitude':-6.19,'longitude':106.83}})
        return config,sources,bq,{'scientific':{'packages':{}},'core':{}}
    def test_source_bundle_has_no_result_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.fixture(root)
            output=create_source_bundle(*args,root/'input.zip');snapshot=SourceBundle(output)
            self.assertIsNone(snapshot.native);self.assertIsNone(snapshot.capacity)
            self.assertEqual(snapshot.config,args[0])
            second=create_source_bundle(*args,root/'same-input.zip')
            self.assertEqual(sha(output),sha(second))
    def test_optional_store_metadata_is_frozen_with_checksum(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.fixture(root)
            write(args[2]/'indomaret-details.json',{'status':'READY','rows':[{'KDTK':'TEST','STD':None}]})
            output=create_source_bundle(*args,root/'input.zip');SourceBundle(output)
            with zipfile.ZipFile(output) as z:
                self.assertIn('bq_snapshot/indomaret-details.json',z.namelist())
                metadata=json.loads(z.read('source_bundle_manifest.json'))
                self.assertEqual(metadata['files']['bq_snapshot/indomaret-details.json'],sha(args[2]/'indomaret-details.json'))
    def test_different_bq_location_is_rejected_without_publishing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.fixture(root)
            write(args[2]/'indomaret.json',{'request_binding':{'latitude':0,'longitude':0}})
            with self.assertRaisesRegex(ValueError,'BQ_LOCATION_MISMATCH'):create_source_bundle(*args,root/'input.zip')
            self.assertFalse((root/'input.zip').exists())

if __name__=='__main__':unittest.main()
