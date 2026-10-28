import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from traffic_location.integration.upload_transport import disconnected_upload,resolve_reference
from traffic_location.integration.gradio_app import display_frames

class TransportTests(unittest.TestCase):
    def test_disconnect_is_a_recoverable_request_and_server_stays_alive(self):
        from fastapi import FastAPI
        from starlette.requests import ClientDisconnect
        import asyncio,json
        app=FastAPI(exception_handlers={ClientDisconnect:disconnected_upload})
        @app.post('/upload')
        async def upload():raise ClientDisconnect()
        @app.get('/health')
        async def health():return {'ok':True}
        async def request(method,path):
            messages=[]
            async def receive():return {'type':'http.request','body':b'','more_body':False}
            async def send(message):messages.append(message)
            await app({'type':'http','http_version':'1.1','method':method,'scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'','headers':[],'server':('test',80),'client':('test',1)},receive,send)
            return messages
        response=asyncio.run(request('POST','/upload'))
        self.assertEqual(response[0]['status'],400);self.assertIn('Upload terputus',json.loads(response[1]['body'])['detail'])
        self.assertEqual(asyncio.run(request('GET','/health'))[0]['status'],200)
    def test_local_reference_does_not_allow_credentials_or_arbitrary_files(self):
        with tempfile.TemporaryDirectory() as t:
            for path in ('/etc/passwd','/kaggle/working/key.json','gs://other-bucket/key'):
                with self.assertRaises(ValueError):resolve_reference(path,t,Mock())
    def test_gcs_download_uses_generation_crc_and_reuses_only_same_generation(self):
        with tempfile.TemporaryDirectory() as t:
            client=Mock();blob=client.bucket.return_value.blob.return_value;blob.size=4;blob.generation=7
            blob.download_to_filename.side_effect=lambda path,**kw:Path(path).write_bytes(b'data')
            first=resolve_reference('gs://aretfak-location-intelligence/incoming/a.mp4',t,lambda:client)
            self.assertEqual(Path(first).read_bytes(),b'data')
            self.assertEqual(blob.download_to_filename.call_args.kwargs['if_generation_match'],7)
            self.assertEqual(blob.download_to_filename.call_args.kwargs['checksum'],'crc32c')
            resolve_reference('gs://aretfak-location-intelligence/incoming/a.mp4',t,lambda:client)
            self.assertEqual(blob.download_to_filename.call_count,1)
            blob.generation=8
            self.assertNotEqual(first,resolve_reference('gs://aretfak-location-intelligence/incoming/a.mp4',t,lambda:client))
    def test_display_aggregates_accepted_but_preserves_missing_std(self):
        frames=display_frames({'traffic_counts':[{'day_group':'weekday','session':'pagi','category':'car','accepted_count':2},{'day_group':'weekday','session':'pagi','category':'car','accepted_count':3}], 'ppac_results':[{'std_total':None}]})
        self.assertEqual(frames[0].iloc[0]['jumlah kendaraan lewat'],5)
        self.assertIn('UNAVAILABLE',frames[-1]['Jumlah'].tolist())  # Never invent a breakdown from BQ totals.
    def test_map_controls_merge_markers_and_radii_without_changing_layers(self):
        try:import folium
        except ImportError:self.skipTest('Optional Area presentation dependency absent')
        from traffic_location.location.area.outputs.map import consolidate
        m=folium.Map()
        for name in ('POI Sekolah','POI Pasar','Indomaret — pin','Kompetitor primer — radius','Calon toko — pin putih','Calon — radius 400 m'):
            folium.FeatureGroup(name=name).add_to(m)
        consolidate(m)
        names=[getattr(c,'layer_name',None) for c in m._children.values()]
        for name in ('POI','Indomaret & Kompetitor','Calon toko'):self.assertEqual(names.count(name),1)
        self.assertNotIn('POI Pasar',names);self.assertNotIn('Kompetitor primer — radius',names)

if __name__=='__main__':unittest.main()
