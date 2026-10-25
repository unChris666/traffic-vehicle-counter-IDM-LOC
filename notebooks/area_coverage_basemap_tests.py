"""Real small PMTiles fixture, mocked GCS ranges, no national completeness claim."""
from pathlib import Path
import json,unittest,sys,hashlib
from copy import deepcopy
from types import SimpleNamespace
from location_intelligent_gcs_basemap import GcsRangeReader,load_tiles,tile_coordinates

ROOT=Path(__file__).resolve().parents[1]


class Response:
    def __init__(self,data,offset,length,total,generation):
        self.content=data;self.status_code=206
        self.headers={'Content-Range':f'bytes {offset}-{offset+length-1}/{total}','x-goog-generation':str(generation)}
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def raise_for_status(self):pass


class FixtureSession:
    def __init__(self,data,generation=123):self.data=data;self.generation=generation;self.calls=[];self.bad=False
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs));start,end=map(int,kwargs['headers']['Range'].split('=')[1].split('-'))
        self.last=Response(self.data[start:end+1],start,end-start+1,len(self.data),self.generation)
        if self.bad:self.last.status_code=200
        return self.last


def fixture():
    data=(ROOT/'results/area_coverage_map/basemap_validation/synthetic_fixture.pmtiles').read_bytes()
    stats=json.loads((ROOT/'results/area_coverage_map/basemap_validation/native_fixture_build.json').read_text())
    ref={'schema':'indonesia_basemap_v1','status':'READY','object':'TEST_ONLY/synthetic.pmtiles','generation':123,
         'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),**stats}
    return data,ref


class BasemapTests(unittest.TestCase):
    def test_actual_pmtiles_loads_and_cached_ranges_pin_generation(self):
        data,ref=fixture();session=FixtureSession(data)
        tiles,audit=load_tiles(session,ref,[106.82,-6.20,106.84,-6.18])
        self.assertGreater(len(tiles),0);self.assertLessEqual(len(tiles),ref['tiles'])
        self.assertEqual(audit['nonempty_tiles'],len(tiles))
        self.assertTrue(all(call[0].startswith('https://storage.googleapis.com/') for call in session.calls))
        self.assertTrue(all(call[1]['params']['generation']=='123' for call in session.calls))
        self.assertEqual(len({c[1]['headers']['Range'] for c in session.calls}),len(session.calls))

    def test_gcs_ignoring_range_is_error_not_empty_map(self):
        data,ref=fixture();session=FixtureSession(data);session.bad=True
        with self.assertRaisesRegex(RuntimeError,'RANGE_RESPONSE_INVALID'):load_tiles(session,ref,[106.82,-6.20,106.84,-6.18])

    def test_generation_wrong_blocks_read(self):
        data,ref=fixture()
        with self.assertRaisesRegex(RuntimeError,'GENERATION_CHANGED'):load_tiles(FixtureSession(data,456),ref,[106.82,-6.20,106.84,-6.18])

    def test_missing_manifest_or_wrong_bounds_never_succeeds(self):
        data,ref=fixture()
        with self.assertRaisesRegex(RuntimeError,'NOT_READY'):load_tiles(FixtureSession(data),{**ref,'status':'BUILDING'},[106.82,-6.20,106.84,-6.18])
        with self.assertRaisesRegex(RuntimeError,'OUTSIDE_ARCHIVE'):load_tiles(FixtureSession(data),ref,[100,-6,101,-5])
        with self.assertRaisesRegex(RuntimeError,'HEADER_MANIFEST_MISMATCH'):load_tiles(FixtureSession(data),{**ref,'tiles':99},[106.82,-6.20,106.84,-6.18])

    def test_tile_bounds_and_invalid_read_guard(self):
        data,ref=fixture();reader=GcsRangeReader(FixtureSession(data),ref)
        for offset,length in [(-1,1),(0,0),(0,len(data)+1),(0,33*1024*1024)]:
            with self.assertRaisesRegex(RuntimeError,'RANGE_INVALID'):reader(offset,length)
        self.assertEqual(tile_coordinates([-180,-85,180,85],0),[(0,0,0)])

    def test_preparation_has_visible_basemap_module_and_final_ready_gate(self):
        n=json.loads((ROOT/'notebooks/area_gcs_runtime_preparation.ipynb').read_text())
        source=next(''.join(c['source']) for c in n['cells'] if ''.join(c['source']).startswith('%%writefile /kaggle/working/national_basemap.py'))
        self.assertEqual(source.split('\n',1)[1],(ROOT/'tools/national_basemap.py').read_text())
        script=(ROOT/'tools/prepare_area_gcs_runtime.py').read_text()
        self.assertLess(script.index('basemap=ensure_basemap'),script.index("pointer.upload_from_string"))
        self.assertIn("'basemap':basemap",script)


if __name__=='__main__':unittest.main()
