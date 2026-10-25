"""Synthetic archive tests. These do NOT stand in for V5 production parity."""
import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from traffic_location.artifacts import canonical,sha,semantic_hash
from traffic_location.location.area import freeze,reopen
from traffic_location.location.area.sources.snapshots import MarketSnapshot


def fixture(path,*,mutation=None):
    files={}
    def add(name,value):files[name]=canonical(value)
    def seal(name,prefix):
        add(name,{'files':{k[len(prefix):]:__import__('hashlib').sha256(v).hexdigest() for k,v in files.items() if k.startswith(prefix)}})
    policy={'sources':{'competitor_calculation_radius_m':800,'indomaret_calculation_radius_m':800},
            'allocation_requirements':{'attractor_gate':'RADIAL_ATTRACTOR_400M_NO_POI_ROUTING','attractor_radius_m':400}}
    config={'CONFIG':{'latitude':0,'longitude':0},'MARKET_CONFIG':policy}
    add('job_config.json',config);add('runtime_environment.json',{'scope':'SYNTHETIC_FIXTURE'})
    add('gpu_execution.json',{'validation_mode':'GPU_EXECUTE'})
    add('gpu_equivalence.json',{'calculation':{'status':'NOT_RUN'},'market':{'status':'NOT_RUN'}})
    add('pilot/report.json',{'source_records':1,'all_source_rows_accounted':1})
    add('pilot/building_results/capacity.json',{'mixed_unit_total':None,'unknown':None})
    files['pilot/building_results/decisions.json.gz']=b'fixture';add('pilot/normalized/buildings.geojson',{'features':[]})
    seal('pilot/manifest.json','pilot/')
    add('sources/network_roads_only/raw/roads.json',{'scope':'FIXTURE'})
    seal('sources/network_roads_only/network_manifest.json','sources/network_roads_only/')
    seal('sources/source_manifest.json','sources/')
    files['source/fixture.py']=b'# synthetic fixture only\n'
    identity={'config':config['CONFIG'],'market_config':policy,'pilot':__import__('hashlib').sha256(files['pilot/manifest.json']).hexdigest()}
    row={'building_id':'fixture/1','market_status':'OTHERS','winner_store_key':None,'count_candidate':0,'reason':'UNKNOWN','scores':[]}
    summary={'rows':1,'assigned':0,'unassigned':1,'candidate_whole_buildings':0,'whole_buildings_by_store':{},'market_status_counts':{'OTHERS':1},'reason_counts':{'UNKNOWN':1}}
    add('market/v5/result.json',{'schema_version':'area_market_result_v1','status':'PARTIAL','identity':identity,'fingerprint':semantic_hash(identity),'rows':[row],'summary':summary})
    buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=['building_id']);w.writeheader();w.writerow({'building_id':'fixture/1'})
    files['market/v5/market_buildings.csv']=buf.getvalue().encode();seal('market/v5/manifest.json','market/v5/')
    if mutation:mutation(files)
    with zipfile.ZipFile(path,'w') as z:
        for name,data in files.items():z.writestr(name,data)

class AreaArtifacts(unittest.TestCase):
    def request(self,path,operation):return {'schema_version':'area_artifact_request_v1','operation':operation,'path':str(path),'sha256':sha(path)}
    def test_freeze_reopen_three_repetitions_no_compute_preserves_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'input.zip';fixture(archive)
            runs=[reopen(self.request(archive,'reopen')) for _ in range(3)]
            self.assertTrue(all(v==runs[0] for v in runs))
            self.assertEqual(runs[0]['data_quality_status'],'PARTIAL')
            self.assertEqual(runs[0]['equivalence_status'],'NOT_VERIFIED')
            self.assertIsNone(runs[0]['capacity']['unknown'])
            out=root/'freeze';self.assertEqual(freeze(self.request(archive,'freeze'),out),runs[0])
            self.assertEqual(freeze(self.request(archive,'freeze'),out),runs[0])
            self.assertEqual(sha(out/'baseline.zip'),sha(archive))
    def test_malicious_path_and_changed_internal_hash_rejected(self):
        for kind in ['path','hash']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'input.zip'
                fixture(p,mutation=lambda files:files.update({'../escape':b'x'} if kind=='path' else {'pilot/report.json':b'{}'}))
                with self.assertRaises(ValueError):MarketSnapshot(p)
    def test_wrong_policy_is_not_silently_imported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.zip'
            def change(files):
                c=json.loads(files['job_config.json']);c['MARKET_CONFIG']['allocation_requirements']['attractor_radius_m']=2000
                files['job_config.json']=canonical(c)
            fixture(p,mutation=change)
            with self.assertRaisesRegex(ValueError,'NOT_V5'):MarketSnapshot(p)
    def test_unknown_contract_and_wrong_outer_sha_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.zip';fixture(p);q=self.request(p,'reopen')
            q['schema_version']='v999'
            with self.assertRaises(ValueError):reopen(q)
            q=self.request(p,'reopen');q['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'MISSING_OR_CHANGED'):reopen(q)
    def test_failure_does_not_publish_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.zip';fixture(p,mutation=lambda f:f.update({'pilot/report.json':b'{}'}))
            out=Path(d)/'out'
            with self.assertRaises(ValueError):freeze(self.request(p,'freeze'),out)
            self.assertFalse(out.exists())

class BaselineCollector(unittest.TestCase):
    def test_failed_output_does_not_export_stale_archive(self):
        env={'__name__':'collector_test'}
        exec((Path(__file__).resolve().parents[1]/'tools/collect_area_baseline.py').read_text(),env)
        self.assertIsNone(env['collect']({'STAGES':{'output':{'status':'FAILED'}}}))

    def test_successful_output_exports_existing_zip_without_credentials(self):
        from unittest.mock import patch
        env={'__name__':'collector_test'}
        exec((Path(__file__).resolve().parents[1]/'tools/collect_area_baseline.py').read_text(),env)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'source.zip';fixture(archive)
            receipt={'manifest_uri':'gs://fixture/manifest.json','object':'fixture.zip','generation':1,
                     'bytes':archive.stat().st_size,'sha256':sha(archive),'crc32c':'fixture'}
            def local_path(value):return root/'export' if str(value)=='/kaggle/working/area_modular_baseline_export' else Path(value)
            env['Path']=local_path
            with patch('IPython.display.display'):
                env['collect']({'STAGES':{'output':{'status':'SUCCEEDED'}},'archive':archive,
                                'GCS_RECEIPT':receipt,'credential_fixture':'MUST_NOT_BE_SERIALIZED'})
            self.assertEqual(sha(root/'export/baseline.zip'),sha(archive))
            self.assertNotIn('MUST_NOT_BE_SERIALIZED',(root/'export/receipt.json').read_text())

if __name__=='__main__':unittest.main()
