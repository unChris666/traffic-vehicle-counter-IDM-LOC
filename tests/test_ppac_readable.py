import hashlib,json,tempfile,unittest
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from traffic_location.integration.ppac_view import rows
from traffic_location.integration.gradio_app import frame,build_app
from traffic_location.integration.cloud_schema import CloudDestination
from traffic_location.integration.cloud_results import ResultsReader
from traffic_location.artifacts import write

class ReadableTests(unittest.TestCase):
    def test_complete_breakdown_reads_saved_values_without_resumming_fasum(self):
        result={'execution_status':'SUCCEEDED','std_total':105,'residential':{'std_residential':40,'groups':[{'zone':'0_400m','std':20}]},'traffic':{'std_traffic_raw':60},'fasum':{'std_fasum':5},'total':{'std_traffic_including_fasum':65,'std_total':105}}
        view=rows(result)
        self.assertIn(['STD Total','STD/hari',105,'SUCCEEDED',''],view)
        self.assertEqual({r[0] for r in view},{'Breakdown Residential','Breakdown Traffic','Breakdown Fasum','Total','STD Total','Status','Reason'})
    def test_blocked_result_keeps_null_and_explains_reason(self):
        view=rows({'execution_status':'BLOCKED','std_total':None,'diagnostics':[{'code':'MISSING_VIDEO','message':'Weekend malam belum ada'}]})
        std=next(r for r in view if r[0]=='STD Total');self.assertIsNone(std[2]);self.assertIn('Weekend malam',std[-1])
    def test_bq_dataframe_is_strict_json_safe_with_dates_decimals_and_missing_numbers(self):
        import gradio as gr
        f=frame([{'date':datetime.now(timezone.utc),'value':Decimal('123.4')},{'value':float('nan')}],['date','value'])
        data=gr.Dataframe().postprocess(f).model_dump()
        encoded=json.dumps(data,allow_nan=False);self.assertIn('123.4',encoded);self.assertIn('null',encoded)
    def test_ui_has_no_json_viewer_or_json_download_component(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'config/experiment.json',{'videos':[]})
            app,c=build_app(root/'app',root/'config',runtime_factory=Mock())
            components=app.get_config_file()['components']
            self.assertFalse(any(v['type']=='json' for v in components))
            self.assertFalse(any(v['props'].get('label')=='Unduh ringkasan JSON' for v in components));app.close()
    def test_optional_bq_failure_keeps_other_tables_and_saved_ppac(self):
        bq=Mock();bq.get_dataset.return_value.location='US'
        bq.query.side_effect=[Mock(result=Mock(return_value=[{'job_id':'job_'+'a'*32,'target_id':'T','period_id':'P'}])),RuntimeError('query failed'),Mock(result=Mock(return_value=[])),Mock(result=Mock(return_value=[{'std_total':None}]))]
        data=ResultsReader(CloudDestination(),Mock(),bq).load('T')
        self.assertEqual(len(data['read_errors']),1);self.assertEqual(data['traffic_counts'],[])
        self.assertEqual(data['ppac_results'][0]['std_total'],None)

    def test_saved_ppac_document_is_authoritative_for_display_not_bq_total(self):
        from unittest.mock import patch
        from traffic_location.integration.gradio_app import display_frames
        bq=Mock();bq.get_dataset.return_value.location='US'
        job={'job_id':'job_'+'a'*32,'target_id':'T','period_id':'P','manifest_uri':'gs://aretfak-location-intelligence/jobs/T/P/job_a/manifest.json','manifest_sha256':'b'*64}
        bq.query.side_effect=[Mock(result=Mock(return_value=[job])),Mock(result=Mock(return_value=[])),Mock(result=Mock(return_value=[])),Mock(result=Mock(return_value=[{'std_total':999}]))]
        document={'execution_status':'SUCCEEDED','std_total':105,'residential':{'std_residential':40},'traffic':{'std_traffic_raw':60},'fasum':{'std_fasum':5},'total':{'std_total':105}}
        manifest={'files':[{'object':'jobs/T/P/'+job['job_id']+'/ppac/result.json','sha256':'c'*64}]}
        reader=ResultsReader(CloudDestination(),Mock(),bq)
        with patch.object(reader,'verified_bytes',side_effect=[json.dumps(manifest).encode(),json.dumps(document).encode()]):data=reader.load('T')
        display=display_frames(data)[-1];std=display[display['Bagian']=='STD Total'].iloc[0]
        self.assertEqual(std['Nilai'],105);self.assertNotEqual(std['Nilai'],999)

    def test_map_response_is_small_and_references_verified_cached_gcs_html(self):
        with tempfile.TemporaryDirectory() as d:
            storage=Mock();blob=storage.bucket.return_value.blob.return_value
            raw=b'<html><script>var map=1;</script>Folium</html>';digest=hashlib.sha256(raw).hexdigest()
            blob.size=len(raw);blob.generation=2;blob.download_as_bytes.return_value=raw
            reader=ResultsReader(CloudDestination(),storage,Mock(),map_cache=d)
            job={'target_id':'T','period_id':'P','job_id':'job_'+'a'*32}
            area={'map_html_uri':'gs://aretfak-location-intelligence/jobs/T/P/'+job['job_id']+'/engines/area/a/market_map.html','map_html_sha256':digest}
            html=reader.map_html(job,area)
            self.assertIn('/saved-maps/'+digest,html);self.assertNotIn('srcdoc',html)
            self.assertEqual((Path(d)/(digest+'.html')).read_bytes(),raw)

if __name__=='__main__':unittest.main()
