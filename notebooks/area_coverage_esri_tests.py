"""Esri view uses retained decisions; setup and cloud failures are isolated fixtures."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
from location_intelligent_kaggle_esri import setup_dependencies, render_esri, upload_result, PACKAGES


class EsriTests(unittest.TestCase):
    def test_setup_reuses_matching_packages_and_native_tools(self):
        versions=dict(s.split('==') for s in PACKAGES)
        with patch('importlib.metadata.version',side_effect=versions.__getitem__),patch('shutil.which',return_value='/usr/bin/osmium'),patch('subprocess.run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(setup_dependencies(),('/usr/bin/python3','/usr/bin/osmium'))
        self.assertFalse(any('pip' in c.args[0] or 'apt-get' in c.args[0] for c in run.call_args_list))

    def test_setup_failure_does_not_proceed_to_cloud(self):
        with patch('importlib.metadata.version',return_value='different'),patch('subprocess.run',side_effect=subprocess.TimeoutExpired('pip',900)):
            with self.assertRaises(subprocess.TimeoutExpired):setup_dependencies()

    def test_native_install_uses_resolver_not_recursive_deb_download(self):
        versions=dict(s.split('==') for s in PACKAGES)
        with patch('importlib.metadata.version',side_effect=versions.__getitem__),patch('shutil.which',return_value='/usr/bin/osmium'),patch('subprocess.run',side_effect=[SimpleNamespace(returncode=1)]+[SimpleNamespace(returncode=0)]*5) as run:
            setup_dependencies()
        commands=[c.args[0] for c in run.call_args_list]
        self.assertTrue(any('--no-install-recommends' in c for c in commands))
        self.assertFalse(any('download' in c or 'depends' in c for c in commands))

    def test_real_folium_view_has_both_basemaps_and_fallback_without_model_replay(self):
        import folium
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);result={'output_path':d,'summary':{'accepted':7}}
            (root/'result.json').write_text(json.dumps(result))
            def draw(config,market,pilot,facilities,data,output):
                output.parent.mkdir(parents=True)
                m=folium.Map([0,0],tiles='OpenStreetMap')
                folium.Marker([0,0],tooltip='retained accepted=7').add_to(m)
                folium.LayerControl().add_to(m);m.save(str(output))
                output.with_suffix('.geojson').write_text('{"features":[]}')
            with patch('location_intelligent_market_map.market_map',side_effect=draw) as draw_call:
                path=render_esri({}, {}, root, {}, result)
                html=path.read_text()
                for expected in ['World_Imagery','World_Street_Map','tileerror','Tanpa basemap','retained accepted=7']:
                    self.assertIn(expected,html)
                self.assertNotIn('tile.openstreetmap.org',html)
                self.assertNotIn('pmtiles',html)
                self.assertEqual(render_esri({}, {}, root, {}, result),path)
                self.assertEqual(draw_call.call_count,1)
                # Listener follows declaration; all inline JS syntax is checked by Node.
                import re,shutil
                if shutil.which('node'):
                    for script in re.findall(r'<script[^>]*>(.*?)</script>',html,re.S):
                        subprocess.run(['node','--check'],input=script,text=True,check=True,capture_output=True)
                path.write_text('changed')
                with self.assertRaisesRegex(RuntimeError,'ESRI_VIEW_CHANGED'):render_esri({}, {}, root, {}, result)

    def test_upload_verifies_before_completion_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'result.zip';p.write_bytes(b'fixture archive')
            bucket=Mock();bucket.name='fixture';blob=Mock();pointer=Mock()
            pointer.name='results/fixture/manifest.json'
            bucket.blob.side_effect=[blob,pointer];blob.exists.return_value=False;pointer.exists.return_value=False
            blob.size=p.stat().st_size;blob.generation=7;blob.crc32c='fixture';blob.name='results/fixture/result.zip'
            result=upload_result(None,p,bucket=bucket)
            self.assertEqual(result['status'],'STORED')
            self.assertEqual(blob.upload_from_filename.call_args.kwargs['if_generation_match'],0)
            pointer.upload_from_string.assert_called_once()

    def test_wrong_remote_object_or_upload_failure_cannot_publish_manifest(self):
        for failure in ['upload','verification']:
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'result.zip';p.write_bytes(b'fixture')
                bucket=Mock();blob=Mock();bucket.blob.return_value=blob;blob.exists.return_value=failure=='verification'
                blob.size=0;blob.metadata={}
                if failure=='upload':blob.upload_from_filename.side_effect=RuntimeError('cloud unavailable')
                with self.assertRaises(RuntimeError):upload_result(None,p,bucket=bucket)
                blob.upload_from_string.assert_not_called()

    def test_transfer_retries_transient_errors_but_not_hash_failure(self):
        import requests
        from location_intelligent_kaggle_esri import stage_input
        with patch('location_intelligent_google_only.stage',side_effect=[requests.Timeout(),Path('/fixture')]) as stage,patch('time.sleep'):
            self.assertEqual(stage_input(None,{},'/fixture'),Path('/fixture'))
            self.assertEqual(stage.call_count,2)
        with patch('location_intelligent_google_only.stage',side_effect=RuntimeError('GCS_INPUT_HASH_MISMATCH')) as stage:
            with self.assertRaisesRegex(RuntimeError,'HASH_MISMATCH'):stage_input(None,{},'/fixture')
            self.assertEqual(stage.call_count,1)

    def test_transfer_gives_actionable_failure_after_bounded_attempts(self):
        import requests
        from location_intelligent_kaggle_esri import stage_input
        with patch('location_intelligent_google_only.stage',side_effect=requests.Timeout()) as stage,patch('time.sleep'):
            with self.assertRaisesRegex(RuntimeError,'GCS_INPUT_TRANSFER_UNAVAILABLE'):stage_input(None,{},'/fixture')
            self.assertEqual(stage.call_count,3)

    def test_notebook_is_self_contained_and_pmtiles_is_not_required(self):
        root=Path(__file__).resolve().parents[1]
        n=json.loads((root/'notebooks/area_coverage_market_gpu_2km.ipynb').read_text())
        cells=[''.join(c['source']) for c in n['cells'] if c['cell_type']=='code']
        helper=next(s for s in cells if s.startswith('%%writefile ') and s.split('\n',1)[0].endswith('/location_intelligent_kaggle_esri.py'))
        self.assertEqual(helper.split('\n',1)[1],(root/'notebooks/location_intelligent_kaggle_esri.py').read_text())
        execution='\n'.join(s for s in cells if not s.startswith('%%writefile '))
        self.assertNotIn('bootstrap_runtime()',execution)
        self.assertNotIn('GCS_BASEMAP_REF',execution)
        self.assertIn('upload_result(GOOGLE_SESSION,archive)',execution)
        self.assertIn('OSMIUM_BINARY',execution)
        import ast
        for s in cells:ast.parse(s.split('\n',1)[1] if s.startswith('%%writefile ') else s)


if __name__=='__main__':unittest.main()
