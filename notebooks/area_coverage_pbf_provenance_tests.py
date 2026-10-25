"""Regression for the adapter -> calculation source gate; no external downloads."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from location_intelligent_li3_sources import read_json, write_json
from location_intelligent_map_pilot import sha
from location_intelligent_pbf_sources import recover_legacy_packet, validate_road_provenance
from location_intelligent_market_runtime import verify_market_source_packet
from location_intelligent_li3 import select_feature_source


class ProvenanceTests(unittest.TestCase):
    def packet(self, root, *, checksum=False):
        config={'latitude':-6.19,'longitude':106.83}
        ref={'sha256':'fixture'}
        network=root/'network_roads_only'
        payload={'elements':[]}
        write_json(network/'raw/osm_roads.json.gz',{'status':'SUCCEEDED','provider':'GCS_PBF','pbf_input':ref,'payload':payload})
        features={'status':'SUCCEEDED','payload':payload,'external_features_requested':False,
                  'coverage':'ROAD_EXTRACT_ONLY_EXTERNAL_FEATURES_NOT_REQUESTED'}
        if checksum:features['source_roads_sha256']=sha(network/'raw/osm_roads.json.gz')
        write_json(network/'raw/osm_features_roads_only.json.gz',features)
        write_json(network/'config/pilot.json',{'policy':{'li3':{'feature_source_mode':'ROADS_ONLY_EXPERIMENT'}}})
        write_json(root/'pbf_source.json',{'input':ref})
        self.seal(root,config)
        return config,ref

    def seal(self,root,config):
        network=root/'network_roads_only'
        write_json(network/'network_manifest.json',{'config':config,'files':{
            str(p.relative_to(network)):sha(p) for p in network.rglob('*') if p.is_file() and p.name!='network_manifest.json'}})
        write_json(root/'source_manifest.json',{'config':config,'files':{
            str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and p.name!='source_manifest.json'}})

    def test_legacy_defect_reproduced_and_recovery_passes_calculation_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'sources';config,ref=self.packet(root)
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(ValueError,'Road-derived feature source does not match roads'):
                select_feature_source(root/'network_roads_only')
            with patch('subprocess.run',side_effect=AssertionError('No extraction or download')):
                recovered=recover_legacy_packet(root,config,ref)
            self.assertNotEqual(root,recovered)
            self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})
            verify_market_source_packet(recovered,config);validate_road_provenance(recovered)
            select_feature_source(recovered/'network_roads_only')
            self.assertEqual(recover_legacy_packet(root,config,ref),recovered)
            self.assertEqual(sha(root/'network_roads_only/raw/osm_roads.json.gz'),sha(recovered/'network_roads_only/raw/osm_roads.json.gz'))

    def test_correct_packet_reopens_without_migration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'sources';config,ref=self.packet(root,checksum=True)
            self.assertEqual(recover_legacy_packet(root,config,ref),root)
            select_feature_source(root/'network_roads_only')

    def test_corrupt_parent_is_never_repaired(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'sources';config,ref=self.packet(root)
            (root/'network_roads_only/raw/osm_roads.json.gz').write_bytes(b'CORRUPT')
            with self.assertRaisesRegex(ValueError,'SOURCE_SNAPSHOT_CHANGED'):recover_legacy_packet(root,config,ref)
            self.assertFalse(root.with_name(root.name+'-provenance-v2').exists())

    def test_different_payload_cannot_be_blessed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'sources';config,ref=self.packet(root)
            p=root/'network_roads_only/raw/osm_features_roads_only.json.gz';f=read_json(p);f['payload']={'elements':[{'id':99}]};write_json(p,f);self.seal(root,config)
            with self.assertRaisesRegex(ValueError,'PBF_LEGACY_RECOVERY_UNSAFE'):recover_legacy_packet(root,config,ref)

    def test_wrong_declared_checksum_is_not_missing_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'sources';config,ref=self.packet(root,checksum=True)
            p=root/'network_roads_only/raw/osm_features_roads_only.json.gz';f=read_json(p);f['source_roads_sha256']='wrong';write_json(p,f);self.seal(root,config)
            with self.assertRaisesRegex(ValueError,'PBF_ROAD_PROVENANCE_HASH_MISMATCH'):recover_legacy_packet(root,config,ref)

    def test_interrupted_recovery_does_not_publish_or_mutate_parent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'sources';config,ref=self.packet(root)
            before=sha(root/'source_manifest.json')
            with patch('location_intelligent_pbf_sources.write_json',side_effect=OSError('fixture disk unavailable')):
                with self.assertRaises(OSError):recover_legacy_packet(root,config,ref)
            self.assertFalse(root.with_name(root.name+'-provenance-v2').exists())
            self.assertEqual(before,sha(root/'source_manifest.json'))
            verify_market_source_packet(root,config)

    def test_notebook_diagnostic_exposes_safe_provenance_code(self):
        from location_intelligent_pbf_sources import PbfProvenanceError
        with tempfile.TemporaryDirectory() as d:
            notebook=Path(__file__).with_name('area_coverage_market_gpu_2km.ipynb')
            first=next(''.join(c['source']) for c in json.loads(notebook.read_text())['cells'] if c['cell_type']=='code')
            first=first.replace('/kaggle/working',d)
            env={};exec(first,env)
            env['STAGES']['sources']['status']='SUCCEEDED'
            env['begin_notebook_stage']('calculation',['sources'])
            env['fail_notebook_stage']('calculation',PbfProvenanceError('PBF_ROAD_PROVENANCE_HASH_MISMATCH'))
            report=read_json(env['NOTEBOOK_REPORT_PATH'])
            self.assertEqual(report['stages']['calculation']['error_code'],'PBF_ROAD_PROVENANCE_HASH_MISMATCH')
            self.assertIn('do not delete PBF cache',report['stages']['calculation']['action'])

    def test_input_reference_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'sources';config,ref=self.packet(root)
            with self.assertRaisesRegex(ValueError,'PBF_INPUT_REFERENCE_MISMATCH'):recover_legacy_packet(root,config,{'sha256':'different'})


if __name__=='__main__':unittest.main()
